from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0142_rename_dificult_species'),
        ('compare', '0004_comparisontranslation'),
    ]

    operations = [
        migrations.CreateModel(
            name='SpeciesFact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('wikipedia', 'Wikipedia'), ('wikidata', 'Wikidata'), ('avonet', 'AVONET'), ('ebird', 'eBird'), ('community', 'Community'), ('botw', 'Birds of the World')], max_length=32)),
                ('category', models.CharField(default='other', max_length=50)),
                ('key', models.CharField(help_text='Stable fact key, e.g. body_mass_g or intro', max_length=80)),
                ('value_text', models.TextField(blank=True, default='')),
                ('value_num', models.FloatField(blank=True, null=True)),
                ('value_json', models.JSONField(blank=True, null=True)),
                ('source_url', models.URLField(blank=True, null=True)),
                ('license', models.CharField(blank=True, default='', max_length=64)),
                ('attribution', models.CharField(blank=True, default='', max_length=400)),
                ('fetched_at', models.DateTimeField(auto_now=True)),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='facts', to='jizz.species')),
            ],
            options={
                'ordering': ['source', 'category', 'key'],
            },
        ),
        migrations.AddField(
            model_name='speciescomparison',
            name='sources_used',
            field=models.JSONField(blank=True, default=list, help_text='Attribution list: [{source, url, attribution}, ...]'),
        ),
        migrations.AddIndex(
            model_name='speciesfact',
            index=models.Index(fields=['species', 'source'], name='compare_spe_species_8f0a1a_idx'),
        ),
        migrations.AddIndex(
            model_name='speciesfact',
            index=models.Index(fields=['species', 'category'], name='compare_spe_species_3c2b1b_idx'),
        ),
        migrations.AddConstraint(
            model_name='speciesfact',
            constraint=models.UniqueConstraint(fields=('species', 'source', 'category', 'key'), name='species_fact_source_key_uniq'),
        ),
    ]
