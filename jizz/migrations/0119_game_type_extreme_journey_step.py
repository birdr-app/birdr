from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0118_sanitize_email_usernames'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='game_type',
            field=models.CharField(
                choices=[('standard', 'Standard'), ('extreme', 'Extreme')],
                default='standard',
                help_text='Extreme: favor rare species and species this player has missed before.',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='journeystep',
            name='step_type',
            field=models.CharField(
                choices=[
                    ('plain', 'Plain'),
                    ('sounds', 'Sounds'),
                    ('family', 'Family'),
                    ('family', 'Family'),
                    ('dificult', 'Dificult'),
                    ('difficult', 'Difficult'),
                    ('extreme', 'Extreme'),
                ],
                default='plain',
                max_length=32,
            ),
        ),
    ]
