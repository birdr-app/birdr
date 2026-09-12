# Generated manually for app identity on usage events

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0139_about_github_repo'),
    ]

    operations = [
        migrations.AddField(
            model_name='usageevent',
            name='app_version',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='usageevent',
            name='app_build',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='usageevent',
            name='os_version',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(fields=['app_version', 'created_at'], name='jizz_usagee_app_ver_idx'),
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(fields=['app_build', 'created_at'], name='jizz_usagee_app_bui_idx'),
        ),
    ]
