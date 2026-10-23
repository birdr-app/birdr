from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jizz', '0150_shared_games'),
    ]

    operations = [
        migrations.CreateModel(
            name='FlockSharedGame',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('added_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='flock_shared_games', to=settings.AUTH_USER_MODEL)),
                ('flock', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shared_games', to='jizz.flock')),
                ('shared_game', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flock_links', to='jizz.sharedgame')),
            ],
            options={
                'ordering': ['-created'],
            },
        ),
        migrations.AddConstraint(
            model_name='flocksharedgame',
            constraint=models.UniqueConstraint(fields=('flock', 'shared_game'), name='flock_shared_game_once'),
        ),
    ]
