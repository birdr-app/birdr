from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('compare', '0003_communitycomparison'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComparisonTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(max_length=10)),
                ('source_hash', models.CharField(max_length=32)),
                ('fields', models.JSONField(default=dict)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                (
                    'comparison',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='translations',
                        to='compare.speciescomparison',
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name='comparisontranslation',
            index=models.Index(
                fields=['comparison', 'language', 'source_hash'],
                name='compare_com_compari_0f987c_idx',
            ),
        ),
        migrations.AddConstraint(
            model_name='comparisontranslation',
            constraint=models.UniqueConstraint(
                fields=('comparison', 'language'),
                name='comparison_translation_lang_uniq',
            ),
        ),
    ]
