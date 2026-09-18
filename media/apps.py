from django.apps import AppConfig


class MediaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'media'

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from media.models import MediaReview, sync_media_hide
        from media.review_stats import invalidate_species_media_review_stats

        def _invalidate_review_stats(sender, instance, **kwargs):
            invalidate_species_media_review_stats()

        def _sync_hide_on_delete(sender, instance, **kwargs):
            sync_media_hide(instance.media_id)
            invalidate_species_media_review_stats()

        post_save.connect(
            _invalidate_review_stats,
            sender=MediaReview,
            dispatch_uid='media.invalidate_review_stats_save',
        )
        post_delete.connect(
            _sync_hide_on_delete,
            sender=MediaReview,
            dispatch_uid='media.sync_hide_on_review_delete',
        )

