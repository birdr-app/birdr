from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0151_flock_shared_games'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='mixup_species',
            field=models.ManyToManyField(blank=True, help_text='The 3-6 species of a mixup_practice (mixed-up flock) game.', related_name='mixup_practice_games', to='jizz.species'),
        ),
        migrations.AlterField(
            model_name='game',
            name='game_type',
            field=models.CharField(choices=[('standard', 'Standard'), ('extreme', 'Extreme'), ('pair_practice', 'Pair practice'), ('species_practice', 'Species practice'), ('mixup_practice', 'Mixed-up flock practice'), ('flock_challenge', 'Flock challenge'), ('survival', 'Survival'), ('league', 'National league')], default='standard', help_text='Extreme: favor rare species and species this player has missed before.', max_length=20),
        ),
    ]
