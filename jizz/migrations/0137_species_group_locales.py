# Generated manually for species-group names in all app languages

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0136_country_regions_game_season'),
    ]

    operations = [
        migrations.AddField(
            model_name='speciesgroup',
            name='name_de',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='speciesgroup',
            name='name_es',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='speciesgroup',
            name='name_fr',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='speciesgroup',
            name='name_it',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='speciesgroup',
            name='name_ja',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='speciesgroup',
            name='name_pt_br',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
