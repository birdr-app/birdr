from django.db import migrations


def normalize_journey_step_types(apps, schema_editor):
    JourneyStep = apps.get_model('jizz', 'JourneyStep')
    JourneyStep.objects.filter(step_type='familiy').update(step_type='family')
    JourneyStep.objects.filter(step_type='dificult').update(step_type='difficult')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0141_answer_wrong_pair_index'),
    ]

    operations = [
        migrations.RenameField(
            model_name='game',
            old_name='dificult_species',
            new_name='difficult_species',
        ),
        migrations.RunPython(normalize_journey_step_types, noop_reverse),
    ]
