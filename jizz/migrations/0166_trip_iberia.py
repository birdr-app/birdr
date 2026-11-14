from django.db import migrations

# Trip prep Spain became Iberia (Spain and Portugal), and its Canary Islands pack went with it.
RENAMES = {'ES': 'IBERIA', 'ES-CANARIES': 'IBERIA-CANARIES'}


def rename_trips(apps, schema_editor):
    TripPhotoPick = apps.get_model('jizz', 'TripPhotoPick')
    for old, new in RENAMES.items():
        TripPhotoPick.objects.filter(trip=old).update(trip=new)


def restore_trips(apps, schema_editor):
    TripPhotoPick = apps.get_model('jizz', 'TripPhotoPick')
    for old, new in RENAMES.items():
        TripPhotoPick.objects.filter(trip=new).update(trip=old)


class Migration(migrations.Migration):
    dependencies = [
        ('jizz', '0165_subspecies_taxonomy_changes'),
    ]

    operations = [
        migrations.RunPython(rename_trips, restore_trips),
    ]
