from django.db import migrations


def move_bertie_players_to_tody(apps, schema_editor):
    # 0155 already moved everyone off Bertie; this sweeps up whoever is on it again.
    # Bertie stays available in the profile.
    UserProfile = apps.get_model('jizz', 'UserProfile')
    UserProfile.objects.filter(visual_style='classic').update(visual_style='tody')


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0155_userprofile_visual_style_tody'),
    ]

    operations = [
        migrations.RunPython(move_bertie_players_to_tody, migrations.RunPython.noop),
    ]
