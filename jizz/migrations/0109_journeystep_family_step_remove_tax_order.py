from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0108_populate_taxonomy_texts'),
    ]

    operations = [
        migrations.AlterField(
            model_name='journeystep',
            name='step_type',
            field=models.CharField(
                choices=[
                    ('plain', 'Plain'),
                    ('sounds', 'Sounds'),
                    ('family', 'Familiy'),
                    ('family', 'Family'),
                    ('dificult', 'Dificult'),
                ],
                default='plain',
                max_length=32,
            ),
        ),
        migrations.RemoveField(
            model_name='journeystep',
            name='tax_order',
        ),
    ]
