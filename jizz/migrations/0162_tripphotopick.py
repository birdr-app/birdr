from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jizz', '0161_userprofile_home_region'),
    ]

    operations = [
        migrations.CreateModel(
            name='TripPhotoPick',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trip', models.CharField(max_length=32)),
                ('card', models.JSONField(blank=True, default=list)),
                ('quiz', models.JSONField(blank=True, default=list)),
                ('reject', models.JSONField(blank=True, default=list)),
                ('done', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trip_photo_picks', to='jizz.species')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['trip', 'species_id'],
                'unique_together': {('trip', 'species')},
            },
        ),
    ]
