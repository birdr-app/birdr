from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0165_subspecies_taxonomy_changes'),
        ('media', '0025_media_subspecies'),
    ]

    operations = [
        migrations.AddField(
            model_name='media',
            name='held_for_change',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='held_media', to='jizz.taxonomychange',
                help_text='Hidden because a species split left it unclear which new species it shows; '
                          'released (and unhidden) once classified or assigned by hand.',
            ),
        ),
    ]
