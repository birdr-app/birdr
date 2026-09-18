from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('media', '0017_mediareview_reply'),
    ]

    operations = [
        AddIndexConcurrently(
            model_name='media',
            index=models.Index(
                fields=['species', 'id'],
                name='media_image_species_idx',
                condition=models.Q(type='image', hide=False),
            ),
        ),
        AddIndexConcurrently(
            model_name='mediareview',
            index=models.Index(
                fields=['media', 'review_type'],
                name='mediareview_media_type_idx',
                include=['id'],
            ),
        ),
    ]
