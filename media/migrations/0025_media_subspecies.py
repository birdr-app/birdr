import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0165_subspecies_taxonomy_changes'),
        ('media', '0024_mediaplumage'),
    ]

    operations = [
        migrations.AddField(
            model_name='media',
            name='subspecies',
            field=models.ForeignKey(blank=True, help_text='Form this media shows (set on a lump so a later split can move it).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='media', to='jizz.subspecies'),
        ),
    ]
