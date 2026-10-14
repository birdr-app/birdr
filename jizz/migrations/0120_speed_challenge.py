from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0119_game_type_extreme_journey_step'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='speed_seconds',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='When set, the player must answer within this many seconds or the round counts as wrong.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='journeystep',
            name='speed_seconds',
            field=models.PositiveSmallIntegerField(
                default=10,
                help_text='Seconds to answer each question (speed steps only).',
            ),
        ),
        migrations.AlterField(
            model_name='journeystep',
            name='step_type',
            field=models.CharField(
                choices=[
                    ('plain', 'Plain'),
                    ('sounds', 'Sounds'),
                    ('family', 'family'),
                    ('family', 'Family'),
                    ('dificult', 'Dificult'),
                    ('difficult', 'Difficult'),
                    ('extreme', 'Extreme'),
                    ('speed', 'Speed'),
                ],
                default='plain',
                max_length=32,
            ),
        ),
    ]
