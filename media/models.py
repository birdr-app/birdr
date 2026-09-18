from django.db import models
from django.core.validators import FileExtensionValidator


# Source choices for media
IMAGE_SOURCES = [
    ('inaturalist', 'iNaturalist'),
    ('wikimedia', 'Wikimedia'),
    ('gbif', 'GBIF'),
    ('flickr', 'Flickr CC'),
    ('observation', 'Observation.org'),
    ('xeno_canto', 'Xeno-Canto'),
]

MEDIA_TYPES = [
    ('image', 'Image'),
    ('video', 'Video'),
    ('audio', 'Audio'),
]


class Media(models.Model):
    """Model for storing image files related to species."""
    species = models.ForeignKey(
        'jizz.Species',
        related_name='media',
        on_delete=models.CASCADE
    )
    source = models.CharField(max_length=200, choices=IMAGE_SOURCES, blank=True, default='')
    contributor = models.CharField(max_length=500, blank=True, default='')
    copyright_text = models.CharField(max_length=500, blank=True, default='', help_text='Copyright text as received from scraper')
    copyright_standardized = models.CharField(max_length=100, blank=True, default='', help_text='Standardized copyright notation (e.g., CC BY, CC BY-NC, etc.)')
    non_commercial_only = models.BooleanField(default=False, help_text='If checked, media is for non-commercial use only. If unchecked, media is free to use with attribution.')
    url = models.URLField(blank=True, null=True, max_length=2000)
    link = models.URLField(blank=True, null=True, max_length=2000)  
    hide = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    type = models.CharField(max_length=200, choices=MEDIA_TYPES, blank=True, default='image')

    class Meta:
        verbose_name = 'Media'
        verbose_name_plural = 'Media'
        ordering = ['-created']
        indexes = [
            models.Index(
                fields=['species', 'type', 'hide'],
                name='media_species_type_hide_idx',
            ),
            models.Index(
                fields=['species', 'id'],
                name='media_image_species_idx',
                condition=models.Q(type='image', hide=False),
            ),
        ]

    def __str__(self):
        return f"{self.species.name} - {self.type} ({self.id})"

    @property
    def effective_review_status(self):
        """Latest review as 'approved' or 'rejected' (not_sure counts as rejected). None if no reviews."""
        reviews = list(self.reviews.all())
        if not reviews:
            return None
        latest = max(reviews, key=lambda r: r.id)
        if latest.review_type == MediaReview.APPROVED:
            return 'approved'
        return 'rejected'


class MediaReview(models.Model):
    """Model for reviewing media items (positive, negative, or neutral)."""
    APPROVED = 'approved'
    REJECTED = 'rejected'
    NOT_SURE = 'not_sure'
    REVIEW_CHOICES = [
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (NOT_SURE, 'Not Sure'),
    ]

    media = models.ForeignKey(
        Media,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    player = models.ForeignKey(
        'jizz.Player',
        on_delete=models.CASCADE,
        related_name='media_reviews',
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='media_reviews',
        null=True,
        blank=True,
    )
    review_type = models.CharField(max_length=20, choices=REVIEW_CHOICES)
    description = models.CharField(max_length=500, null=True, blank=True)
    reply = models.TextField(
        blank=True,
        default='',
        help_text='Explain why this review was wrong. Saving with a reply emails the reviewer once.',
    )
    reply_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Set automatically when the reply email is sent.',
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Media Review'
        verbose_name_plural = 'Media Reviews'
        ordering = ['-created']
        indexes = [
            models.Index(
                fields=['media', 'review_type'],
                name='mediareview_media_type_idx',
                include=['id'],
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['media', 'player'],
                condition=models.Q(player__isnull=False),
                name='media_review_unique_media_player',
            ),
            models.UniqueConstraint(
                fields=['media', 'user'],
                condition=models.Q(user__isnull=False),
                name='media_review_unique_media_user',
            ),
            models.CheckConstraint(
                check=models.Q(player__isnull=False) | models.Q(user__isnull=False),
                name='media_review_reviewer_set',
            ),
        ]

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        sync_media_hide(self.media_id)
        return result

    def delete(self, *args, **kwargs):
        media_id = self.media_id
        result = super().delete(*args, **kwargs)
        sync_media_hide(media_id)
        return result

    @property
    def is_effectively_rejected(self):
        return self.review_type in (self.REJECTED, self.NOT_SURE)

    def __str__(self):
        reviewer = self.user or self.player
        return f"{self.get_review_type_display()} for {self.media} by {reviewer}"


def sync_media_hide(media_id: int | None) -> None:
    """hide=True when any review is rejected; otherwise hide=False."""
    if not media_id:
        return
    should_hide = MediaReview.objects.filter(
        media_id=media_id,
        review_type=MediaReview.REJECTED,
    ).exists()
    Media.objects.filter(pk=media_id).exclude(hide=should_hide).update(hide=should_hide)


class FlagMedia(models.Model):
    """Model for flagging problematic media items."""
    media = models.ForeignKey(
        Media,
        on_delete=models.CASCADE,
        related_name='flags'
    )
    player = models.ForeignKey(
        'jizz.Player',
        on_delete=models.CASCADE,
        related_name='media_flags'
    )
    description = models.CharField(max_length=500, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Flagged Media'
        verbose_name_plural = 'Flagged Media'
        ordering = ['-created']
        unique_together = ('media', 'player')  # One flag per player per media

    def __str__(self):
        return f"Flag for {self.media} by {self.player}"


class MediaPrediction(models.Model):
    """Machine first-assertion (approved vs rejected) for image media; precomputed offline."""
    APPROVED = 'approved'
    REJECTED = 'rejected'
    PRED_CHOICES = [
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]

    media = models.OneToOneField(
        Media,
        on_delete=models.CASCADE,
        related_name='first_assertion_prediction',
    )
    predicted_review_type = models.CharField(max_length=20, choices=PRED_CHOICES)
    confidence = models.FloatField(
        null=True,
        blank=True,
        help_text='Model confidence (e.g. max class probability).',
    )
    model_version = models.CharField(max_length=64, db_index=True)
    features_version = models.CharField(max_length=64, blank=True, default='')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Media prediction'
        verbose_name_plural = 'Media predictions'

    def __str__(self):
        return f"{self.predicted_review_type} ({self.model_version}) for {self.media_id}"