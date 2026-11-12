import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Subspecies, retired-code aliases and the taxonomy change queue.

    Hand-trimmed: makemigrations also emits unrelated destructive drift (see the
    makemigrations-drift note), which is deliberately left out.
    """

    dependencies = [
        ('jizz', '0164_game_season_months'),
    ]

    operations = [
        migrations.AddField(
            model_name='species',
            name='ebird_category',
            field=models.CharField(blank=True, default='species', max_length=20),
        ),
        migrations.AddField(
            model_name='species',
            name='taxon_concept_id',
            field=models.CharField(blank=True, default='', help_text='eBird/Avibase taxon concept id, when the taxonomy export provides it.', max_length=30),
        ),
        migrations.AddField(
            model_name='species',
            name='retired_at',
            field=models.DateTimeField(blank=True, help_text='Set when eBird no longer lists this species (lumped or otherwise retired).', null=True),
        ),
        migrations.AddField(
            model_name='species',
            name='merged_into',
            field=models.ForeignKey(blank=True, help_text='Audit only: surviving species after a lump.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='merged_from', to='jizz.species'),
        ),
        migrations.CreateModel(
            name='Subspecies',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('name_latin', models.CharField(blank=True, default='', max_length=200)),
                ('ebird_category', models.CharField(blank=True, default='issf', max_length=20)),
                ('tax_ordering', models.FloatField(blank=True, null=True)),
                ('active', models.BooleanField(default=True)),
                ('source', models.CharField(choices=[('ebird-import', 'eBird import'), ('lump', 'Former species (lump)')], default='ebird-import', max_length=20)),
                ('former_species_id', models.IntegerField(blank=True, help_text='Audit: id of the Species row this was before a lump.', null=True)),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subspecies', to='jizz.species')),
            ],
            options={
                'verbose_name': 'subspecies',
                'verbose_name_plural': 'subspecies',
                'ordering': ['species_id', 'tax_ordering', 'id'],
            },
        ),
        migrations.CreateModel(
            name='SpeciesAlias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True)),
                ('reason', models.CharField(choices=[('lump', 'Lump'), ('split', 'Split'), ('rename', 'Rename')], default='lump', max_length=10)),
                ('taxonomy_version', models.CharField(blank=True, default='', max_length=20)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='aliases', to='jizz.species')),
            ],
            options={
                'verbose_name_plural': 'species aliases',
            },
        ),
        migrations.CreateModel(
            name='TaxonomyVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=20, unique=True)),
                ('imported_at', models.DateTimeField(auto_now_add=True)),
                ('summary', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'ordering': ['-imported_at'],
            },
        ),
        migrations.CreateModel(
            name='TaxonomyChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_type', models.CharField(choices=[('lump', 'Lump'), ('split', 'Split'), ('rename', 'Rename'), ('new', 'New species'), ('retired', 'Retired')], max_length=10)),
                ('old_codes', models.JSONField(blank=True, default=list)),
                ('new_codes', models.JSONField(blank=True, default=list)),
                ('status', models.CharField(choices=[('proposed', 'Proposed'), ('applied', 'Applied'), ('ignored', 'Ignored')], default='proposed', max_length=10)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
                ('report', models.JSONField(blank=True, default=dict)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('version', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='changes', to='jizz.taxonomyversion')),
            ],
            options={
                'ordering': ['-created', 'id'],
            },
        ),
    ]
