from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0158_game_type_trip_prep'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='home_region',
            field=models.CharField(
                blank=True,
                choices=[('na', 'North America'), ('eu', 'Europe'), ('other', 'Other')],
                default='',
                help_text='Birds you know from home (Trip prep tailoring). Empty = inferred from the preferred country.',
                max_length=8,
            ),
        ),
    ]
