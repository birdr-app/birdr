from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('media', '0019_sync_media_hide'),
    ]

    operations = [
        migrations.CreateModel(
            name='MediaBirdDetection',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('bird', 'Bird detected'),
                            ('no_bird', 'No bird detected'),
                            ('uncertain', 'Uncertain'),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                (
                    'bird_confidence',
                    models.FloatField(
                        help_text='Highest raw YOLO confidence for the COCO bird class.'
                    ),
                ),
                ('bird_box_count', models.PositiveSmallIntegerField(default=0)),
                (
                    'bird_max_area_ratio',
                    models.FloatField(
                        default=0.0,
                        help_text='Largest detected bird box as a fraction of image area.',
                    ),
                ),
                ('detector_version', models.CharField(db_index=True, max_length=64)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                (
                    'media',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='bird_detection',
                        to='media.media',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Media bird detection',
                'verbose_name_plural': 'Media bird detections',
            },
        ),
    ]
