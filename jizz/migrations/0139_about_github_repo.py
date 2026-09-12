from django.db import migrations
from django.db.models.functions import Replace
from django.db.models import Value

OLD_REPO = 'https://github.com/gannetson/birdr'
NEW_REPO = 'https://github.com/birdr-app/birdr'


def _swap(apps, old, new):
    Page = apps.get_model('jizz', 'Page')
    MarketingPage = apps.get_model('jizz', 'MarketingPage')
    Page.objects.filter(content__contains=old).update(
        content=Replace('content', Value(old), Value(new)),
    )
    MarketingPage.objects.filter(body__contains=old).update(
        body=Replace('body', Value(old), Value(new)),
    )


def forwards(apps, schema_editor):
    _swap(apps, OLD_REPO, NEW_REPO)


def backwards(apps, schema_editor):
    _swap(apps, NEW_REPO, OLD_REPO)


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0138_playerscore_app_version_device_type'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
