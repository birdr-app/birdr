from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0152_game_mixup_species'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='receive_updates',
            field=models.BooleanField(default=True, help_text='Receive Motmot news and update emails'),
        ),
    ]
