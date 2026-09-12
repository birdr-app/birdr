# Generated manually for optional client metadata on game start/join

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0137_species_group_locales'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerscore',
            name='app_version',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='playerscore',
            name='device_type',
            field=models.CharField(
                blank=True,
                choices=[('ios', 'iOS'), ('android', 'Android'), ('web', 'Web')],
                default='',
                max_length=20,
            ),
        ),
    ]
