from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0147_league_daily_results_kind'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='show_all_modes',
            field=models.BooleanField(
                default=False,
                help_text='Show every game mode full size, even before 3 finished games.',
            ),
        ),
    ]
