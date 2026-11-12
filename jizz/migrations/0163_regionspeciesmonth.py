import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0162_tripphotopick'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegionSpeciesMonth',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('region_code', models.CharField(db_index=True, max_length=12)),
                ('month', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)])),
                ('records', models.PositiveIntegerField(default=0)),
                ('total_records', models.PositiveIntegerField(default=0, help_text='All bird records in region+month.')),
                ('rel_freq', models.FloatField(default=0.0)),
                ('source', models.CharField(default='gbif_ebird', max_length=32)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='region_months', to='jizz.species')),
            ],
            options={
                'ordering': ['region_code', 'month', '-rel_freq'],
            },
        ),
        migrations.AddConstraint(
            model_name='regionspeciesmonth',
            constraint=models.UniqueConstraint(fields=('region_code', 'species', 'month'), name='jizz_regionspeciesmonth_unique'),
        ),
    ]
