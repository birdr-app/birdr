from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('jizz', '0140_usageevent_app_identity'),
    ]

    operations = [
        AddIndexConcurrently(
            model_name='answer',
            index=models.Index(
                fields=['question', 'answer'],
                name='jizz_answer_wrong_pair_idx',
                condition=models.Q(correct=False),
            ),
        ),
    ]
