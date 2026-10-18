from django.db import migrations


def fill_timezones(apps, schema_editor):
    from jizz.country_timezones import capital_timezone

    Country = apps.get_model('jizz', 'Country')
    for country in Country.objects.filter(timezone=''):
        zone = capital_timezone(country.code)
        if zone:
            country.timezone = zone
            country.save(update_fields=['timezone'])


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0145_national_league'),
    ]

    operations = [
        migrations.RunPython(fill_timezones, migrations.RunPython.noop),
    ]
