from django.db import migrations, models


def move_default_players_to_tody(apps, schema_editor):
    # 'classic' (Bertie) was the default, so almost nobody chose it on purpose.
    # Everyone moves to Tody; Bertie stays available in the profile.
    UserProfile = apps.get_model('jizz', 'UserProfile')
    UserProfile.objects.filter(visual_style='classic').update(visual_style='tody')


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0154_rebrand_cms_pages_motmot'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='visual_style',
            field=models.CharField(
                choices=[('tody', 'Tody'), ('classic', 'Bertie'), ('stylish', 'Classic'), ('none', 'None')],
                default='tody',
                help_text='In-app illustration style: Tody, Bertie (classic comic), Classic (notebook art) or none',
                max_length=16,
            ),
        ),
        migrations.RunPython(move_default_players_to_tody, migrations.RunPython.noop),
    ]
