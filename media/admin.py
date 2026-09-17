from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Exists, OuterRef
from django.utils.html import format_html
from .models import Media, FlagMedia, MediaReview, MediaPrediction
from .review_email import media_review_recipient, send_media_review_reply_if_needed
from .wikimedia_urls import wikimedia_video_playback_url


def media_preview_html(media, thumbnail=False):
    """Image, video, or audio player for a Media instance."""
    if not media or not media.url:
        return '-' if thumbnail else 'No preview available'

    url = media.url
    if media.type == 'image':
        style = (
            'max-height:60px; max-width:60px;'
            if thumbnail
            else 'max-height:300px; max-width:100%;'
        )
        return format_html('<img src="{}" style="{}" />', url, style)
    if media.type == 'video':
        playback = wikimedia_video_playback_url(url) or url
        style = (
            'max-height:60px; max-width:60px;'
            if thumbnail
            else 'max-width:100%; max-height:600px;'
        )
        return format_html(
            '<video controls src="{}" style="{}"></video>',
            playback,
            style,
        )
    if media.type == 'audio':
        style = 'max-width:200px;' if thumbnail else 'width:100%; max-width:800px;'
        return format_html('<audio controls src="{}" style="{}"></audio>', url, style)
    return '-' if thumbnail else 'No preview available'


def media_link_html(media):
    if not media:
        return '-'
    url = (media.link or media.url or '').strip()
    if not url:
        return '-'
    return format_html(
        '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
        url,
        url,
    )


class VisibilityFilter(admin.SimpleListFilter):
    title = 'Visibility'
    parameter_name = 'visibility'

    def lookups(self, request, model_admin):
        return (
            ('visible', 'Visible'),
            ('hidden', 'Hidden'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'hidden':
            return queryset.filter(hide=True)
        if value == 'all':
            return queryset
        # Default to visible
        return queryset.filter(hide=False)


class ReviewStatusFilter(admin.SimpleListFilter):
    title = 'Reviews'
    parameter_name = 'reviews'

    def lookups(self, request, model_admin):
        return (
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('both', 'Both'),
            ('none', 'None'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset

        has_accepted = Exists(
            MediaReview.objects.filter(
                media_id=OuterRef('pk'),
                review_type=MediaReview.APPROVED,
            )
        )
        has_rejected = Exists(
            MediaReview.objects.filter(
                media_id=OuterRef('pk'),
                review_type__in=[MediaReview.REJECTED, MediaReview.NOT_SURE],
            )
        )

        if value == 'none':
            return queryset.filter(~has_accepted, ~has_rejected)
        if value == 'accepted':
            return queryset.filter(has_accepted, ~has_rejected)
        if value == 'rejected':
            return queryset.filter(has_rejected, ~has_accepted)
        if value == 'both':
            return queryset.filter(has_accepted, has_rejected)
        return queryset


class HideableAdminMixin:
    actions = ['mark_hidden', 'mark_visible']

    def mark_hidden(self, request, queryset):
        updated = queryset.update(hide=True)
        self.message_user(request, f"{updated} item(s) marked as hidden.")

    mark_hidden.short_description = 'Hide selected items'

    def mark_visible(self, request, queryset):
        updated = queryset.update(hide=False)
        self.message_user(request, f"{updated} item(s) marked as visible.")

    mark_visible.short_description = 'Show selected items'


class MediaReviewInline(admin.TabularInline):
    model = MediaReview
    fk_name = 'media'
    extra = 0
    raw_id_fields = ['player', 'user']
    readonly_fields = ['created', 'reply_sent_at']
    fields = ['player', 'user', 'review_type', 'description', 'reply', 'reply_sent_at', 'created']


@admin.register(Media)
class MediaAdmin(HideableAdminMixin, admin.ModelAdmin):
    list_display = ['id', 'species', 'type', 'source', 'hide', 'review_count', 'image_thumbnail', 'created']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'first_assertion_prediction'
        ).annotate(
            _review_count=Count('reviews'),
        )

    list_filter = [VisibilityFilter, ReviewStatusFilter, 'type', 'created', 'source', 'copyright_standardized', 'non_commercial_only', 'species']
    search_fields = ['species__name', 'contributor', 'copyright_text', 'copyright_standardized', 'url']
    raw_id_fields = ['species']
    readonly_fields = ['created', 'updated', 'image_preview', 'machine_assertion_summary']
    date_hierarchy = 'created'
    list_per_page = 25
    inlines = [MediaReviewInline]

    fieldsets = (
        ('Species', {
            'fields': ('species',)
        }),
        ('Media Information', {
            'fields': ('source', 'type', 'contributor', 'url', 'link', 'hide', 'image_preview')
        }),
        ('Machine first assertion', {
            'fields': ('machine_assertion_summary',),
            'classes': ('collapse',),
        }),
        ('Copyright', {
            'fields': ('copyright_text', 'copyright_standardized', 'non_commercial_only')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    def review_count(self, obj):
        if obj is None:
            return 0
        return getattr(obj, '_review_count', obj.reviews.count())
    review_count.short_description = 'Reviews'
    review_count.admin_order_field = '_review_count'

    def image_thumbnail(self, obj):
        return media_preview_html(obj, thumbnail=True)
    image_thumbnail.short_description = 'Preview'

    def image_preview(self, obj):
        return media_preview_html(obj, thumbnail=False)
    image_preview.short_description = 'Preview'

    def machine_assertion_summary(self, obj):
        if not obj or not obj.pk or obj.type != 'image':
            return format_html('<span style="color:#666;">— (only image media)</span>')
        try:
            p = obj.first_assertion_prediction
        except ObjectDoesNotExist:
            return format_html('<span style="color:#666;">No machine prediction yet</span>')
        conf = f'{p.confidence:.3f}' if p.confidence is not None else '—'
        fv = f' · features {p.features_version}' if p.features_version else ''
        return format_html(
            '<strong>{}</strong> · confidence {}<br/>'
            '<span style="color:#444;">Model: {}{}</span> · updated {}',
            p.get_predicted_review_type_display(),
            conf,
            p.model_version,
            fv,
            p.updated.strftime('%Y-%m-%d %H:%M') if p.updated else '—',
        )

    machine_assertion_summary.short_description = 'Machine prediction'

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if formset.model is MediaReview:
            for review in list(formset.new_objects) + list(formset.changed_objects):
                instance = review[0] if isinstance(review, tuple) else review
                send_media_review_reply_if_needed(instance)


@admin.register(MediaPrediction)
class MediaPredictionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'media',
        'predicted_review_type',
        'confidence',
        'model_version',
        'features_version',
        'updated',
    ]
    list_filter = ['model_version', 'predicted_review_type', 'features_version']
    search_fields = ['media__id', 'model_version']
    raw_id_fields = ['media']
    readonly_fields = ['created', 'updated']


@admin.register(MediaReview)
class MediaReviewAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'media',
        'media_thumbnail',
        'player',
        'user',
        'review_type',
        'description',
        'reply_sent',
        'created',
    ]
    list_filter = ['review_type', 'created']
    search_fields = ['description', 'reply', 'media__species__name', 'player__name', 'user__username']
    raw_id_fields = ['media', 'player', 'user']
    readonly_fields = ['created', 'reply_sent_at', 'media_preview', 'media_link']
    date_hierarchy = 'created'
    fieldsets = (
        (None, {
            'fields': ('media', 'player', 'user', 'review_type', 'description'),
        }),
        ('Media', {
            'fields': ('media_preview', 'media_link'),
        }),
        ('Reply', {
            'fields': ('reply', 'reply_sent_at'),
            'description': (
                'If you fill in a reply, the reviewer is emailed once '
                '(when they have an email address). Replies go to info@birdr.pro.'
            ),
        }),
        ('Timestamps', {
            'fields': ('created',),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'media',
            'media__species',
            'player',
            'player__user',
            'user',
        )

    def media_preview(self, obj):
        return media_preview_html(obj.media if obj else None, thumbnail=False)
    media_preview.short_description = 'Preview'

    def media_thumbnail(self, obj):
        return media_preview_html(obj.media if obj else None, thumbnail=True)
    media_thumbnail.short_description = 'Preview'

    def media_link(self, obj):
        return media_link_html(obj.media if obj else None)
    media_link.short_description = 'Media link'

    def reply_sent(self, obj):
        return bool(obj.reply_sent_at)
    reply_sent.boolean = True
    reply_sent.short_description = 'Reply sent'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if send_media_review_reply_if_needed(obj):
            recipient = media_review_recipient(obj)
            email = recipient.email if recipient else ''
            self.message_user(request, f'Reply email sent to {email}.')
