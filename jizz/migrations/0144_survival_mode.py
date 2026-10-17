from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0143_usageevent_referer_utm'),
    ]

    operations = [
        migrations.AlterField(
            model_name='game',
            name='game_type',
            field=models.CharField(
                choices=[
                    ('standard', 'Standard'),
                    ('extreme', 'Extreme'),
                    ('pair_practice', 'Pair practice'),
                    ('species_practice', 'Species practice'),
                    ('flock_challenge', 'Flock challenge'),
                    ('survival', 'Survival'),
                ],
                default='standard',
                help_text='Extreme: favor rare species and species this player has missed before.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='playerscore',
            name='streak',
            field=models.PositiveIntegerField(
                db_index=True,
                default=0,
                help_text='Survival games: number of correct answers before the first strike.',
            ),
        ),
    ]
