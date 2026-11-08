from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0157_course_photo_pick'),
    ]

    operations = [
        migrations.AlterField(
            model_name='game',
            name='game_type',
            field=models.CharField(choices=[('standard', 'Standard'), ('extreme', 'Extreme'), ('pair_practice', 'Pair practice'), ('species_practice', 'Species practice'), ('mixup_practice', 'Mixed-up flock practice'), ('flock_challenge', 'Flock challenge'), ('survival', 'Survival'), ('league', 'National league'), ('trip_prep', 'Trip prep')], default='standard', help_text='Extreme: favor rare species and species this player has missed before.', max_length=20),
        ),
    ]
