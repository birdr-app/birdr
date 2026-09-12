# Generated manually for eBird species groups

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0134_update_translation'),
    ]

    operations = [
        migrations.CreateModel(
            name='SpeciesGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=80, unique=True)),
                ('ebird_name', models.CharField(max_length=200, unique=True)),
                ('name_en', models.CharField(max_length=200)),
                ('name_nl', models.CharField(max_length=200)),
                ('sort_order', models.PositiveIntegerField(db_index=True, default=0)),
                ('description_en', models.TextField(blank=True, default='')),
                ('description_nl', models.TextField(blank=True, default='')),
            ],
            options={
                'verbose_name': 'species group',
                'verbose_name_plural': 'species groups',
                'ordering': ['sort_order', 'name_en'],
            },
        ),
        migrations.AddField(
            model_name='species',
            name='species_group',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='species',
                to='jizz.speciesgroup',
            ),
        ),
        migrations.AddField(
            model_name='game',
            name='species_group',
            field=models.CharField(
                blank=True,
                help_text='Only show birds from this group (e.g. shorebirds, warblers)',
                max_length=80,
                null=True,
                verbose_name='Species group',
            ),
        ),
    ]
