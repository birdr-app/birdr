from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0133_userprofile_visual_style_none'),
    ]

    operations = [
        migrations.CreateModel(
            name='UpdateTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(max_length=10)),
                ('source_hash', models.CharField(max_length=32)),
                ('title', models.CharField(max_length=200)),
                ('body_html', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                (
                    'update',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='translations',
                        to='jizz.update',
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name='updatetranslation',
            index=models.Index(
                fields=['update', 'language', 'source_hash'],
                name='jizz_update_update__71e736_idx',
            ),
        ),
        migrations.AddConstraint(
            model_name='updatetranslation',
            constraint=models.UniqueConstraint(
                fields=('update', 'language'),
                name='update_translation_lang_uniq',
            ),
        ),
    ]
