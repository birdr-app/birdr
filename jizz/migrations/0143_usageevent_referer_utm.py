# Generated manually for referer / UTM attribution on usage events

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0142_rename_dificult_species'),
    ]

    operations = [
        migrations.AddField(
            model_name='usageevent',
            name='referer_host',
            field=models.CharField(
                blank=True,
                default='',
                help_text='External Referer host (empty for direct/same-origin).',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='usageevent',
            name='utm_source',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='usageevent',
            name='utm_medium',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='usageevent',
            name='utm_campaign',
            field=models.CharField(blank=True, default='', max_length=180),
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(fields=['referer_host', 'created_at'], name='jizz_usagee_ref_host_idx'),
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(fields=['utm_source', 'created_at'], name='jizz_usagee_utm_src_idx'),
        ),
    ]
