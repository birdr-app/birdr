from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jizz', '0148_userprofile_show_all_modes'),
    ]

    operations = [
        migrations.AddField(
            model_name='flock',
            name='auto_renew_challenges',
            field=models.BooleanField(default=False, help_text='Start a new challenge (same title, country and length) when one ends.'),
        ),
        migrations.AddField(
            model_name='flockmembership',
            name='notifications_enabled',
            field=models.BooleanField(default=True, help_text='Push notifications for this flock (new challenge, last day, results).'),
        ),
        migrations.AddField(
            model_name='flockchallenge',
            name='results_sent_at',
            field=models.DateTimeField(blank=True, null=True, help_text='When the end-of-challenge results push went out (and the challenge was closed).'),
        ),
        migrations.CreateModel(
            name='FlockNotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('last_day', 'One day left'), ('results', 'Results')], max_length=16)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('challenge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='jizz.flockchallenge')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='flock_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={'unique_together': {('user', 'challenge', 'kind')}},
        ),
    ]
