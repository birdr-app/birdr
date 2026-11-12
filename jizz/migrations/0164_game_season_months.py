from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jizz', '0163_regionspeciesmonth'),
    ]

    operations = [
        migrations.AlterField(
            model_name='game',
            name='season',
            field=models.CharField(
                blank=True,
                choices=[
                    ('spring', 'Spring'), ('summer', 'Summer'), ('autumn', 'Autumn'), ('winter', 'Winter'),
                    ('m1', 'Month 1'), ('m2', 'Month 2'), ('m3', 'Month 3'), ('m4', 'Month 4'),
                    ('m5', 'Month 5'), ('m6', 'Month 6'), ('m7', 'Month 7'), ('m8', 'Month 8'),
                    ('m9', 'Month 9'), ('m10', 'Month 10'), ('m11', 'Month 11'), ('m12', 'Month 12'),
                ],
                help_text='When set, question selection uses monthly eBird frequency for this season or month (m1..m12).',
                max_length=10,
                null=True,
            ),
        ),
    ]
