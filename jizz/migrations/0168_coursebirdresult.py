import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jizz', '0167_regionspeciesscore'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseBirdResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('course', models.SlugField(max_length=64)),
                ('plumage', models.CharField(blank=True, default='', max_length=100)),
                ('box', models.PositiveSmallIntegerField(default=0)),
                ('due_at', models.DateTimeField()),
                ('last_seen', models.DateTimeField()),
                ('right', models.PositiveIntegerField(default=0)),
                ('wrong', models.PositiveIntegerField(default=0)),
                ('species', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_bird_results', to='jizz.species')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_bird_results', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['due_at'],
                'indexes': [models.Index(fields=['user', 'course', 'due_at'], name='coursebird_user_due_idx')],
                'unique_together': {('user', 'course', 'species', 'plumage')},
            },
        ),
    ]
