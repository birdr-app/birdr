from django.db import migrations


def sync_media_hide_from_reviews(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE media_media AS m
                SET hide = exists_rejected.has_reject
                FROM (
                    SELECT
                        m2.id,
                        EXISTS (
                            SELECT 1
                            FROM media_mediareview AS r
                            WHERE r.media_id = m2.id
                              AND r.review_type = 'rejected'
                        ) AS has_reject
                    FROM media_media AS m2
                ) AS exists_rejected
                WHERE m.id = exists_rejected.id
                  AND m.hide IS DISTINCT FROM exists_rejected.has_reject
                """
            )
        return

    Media = apps.get_model('media', 'Media')
    MediaReview = apps.get_model('media', 'MediaReview')
    rejected_ids = set(
        MediaReview.objects.filter(review_type='rejected').values_list('media_id', flat=True)
    )
    Media.objects.filter(id__in=rejected_ids, hide=False).update(hide=True)
    Media.objects.exclude(id__in=rejected_ids).filter(hide=True).update(hide=False)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('media', '0018_media_review_stats_indexes'),
    ]

    operations = [
        migrations.RunPython(sync_media_hide_from_reviews, noop_reverse),
    ]
