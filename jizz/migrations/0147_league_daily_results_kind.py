from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0146_country_capital_timezones'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leaguenotificationlog',
            name='kind',
            field=models.CharField(
                choices=[
                    ('invite', 'Invite'),
                    ('reminder_18', 'Reminder 18:00'),
                    ('reminder_20', 'Reminder 20:00'),
                    ('final_day', 'Final day of the week'),
                    ('weekly_recap', 'Weekly recap'),
                    ('fresh_start', 'New week, fresh start'),
                    ('daily_win', 'Daily win'),
                    ('week_champion', 'Week champion'),
                    ('daily_results', 'Morning results'),
                ],
                max_length=16,
            ),
        ),
    ]
