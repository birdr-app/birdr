import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('jizz', '0166_trip_iberia'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegionSpeciesScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('region_code', models.CharField(db_index=True, max_length=24)),
                ('month', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)])),
                ('p_mean', models.FloatField(default=0.0)),
                ('p_max', models.FloatField(default=0.0)),
                ('breadth', models.FloatField(default=0.0)),
                ('source', models.CharField(default='birdnet_geomodel', max_length=32)),
                ('model_version', models.CharField(default='', max_length=16)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='region_scores', to='jizz.species')),
            ],
            options={
                'ordering': ['region_code', 'month', '-p_mean'],
            },
        ),
        migrations.AddConstraint(
            model_name='regionspeciesscore',
            constraint=models.UniqueConstraint(fields=('region_code', 'species', 'month', 'source'), name='jizz_regionspeciesscore_unique'),
        ),
    ]
