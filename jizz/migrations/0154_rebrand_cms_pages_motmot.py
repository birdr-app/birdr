import re

from django.db import migrations

MARKETING_FIELDS = ['title', 'meta_description', 'body', 'nav_label']
PAGE_FIELDS = ['title', 'content']


def _word(name):
    # Standalone word only, so URLs (birdr.pro), identifiers and paths stay as they are.
    return re.compile(r'(?<![A-Za-z0-9_/\-])' + name + r'(?![A-Za-z0-9_/]|\.(?:app|xc))')


def _rebrand_rows(model, fields, old, new):
    pattern = _word(old)
    for row in model.objects.values_list('pk', *fields):
        pk, values = row[0], row[1:]
        changes = {}
        for field, value in zip(fields, values):
            if isinstance(value, str):
                updated = pattern.sub(new, value)
                if updated != value:
                    changes[field] = updated
        if changes:
            model.objects.filter(pk=pk).update(**changes)


def rebrand(apps, schema_editor):
    _rebrand_rows(apps.get_model('jizz', 'MarketingPage'), MARKETING_FIELDS, 'Birdr', 'Motmot')
    _rebrand_rows(apps.get_model('jizz', 'Page'), PAGE_FIELDS, 'Birdr', 'Motmot')


def unbrand(apps, schema_editor):
    _rebrand_rows(apps.get_model('jizz', 'MarketingPage'), MARKETING_FIELDS, 'Motmot', 'Birdr')
    _rebrand_rows(apps.get_model('jizz', 'Page'), PAGE_FIELDS, 'Motmot', 'Birdr')


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0153_userprofile_receive_updates_help_text'),
    ]

    operations = [
        migrations.RunPython(rebrand, unbrand),
    ]
