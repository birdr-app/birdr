from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media', '0016_media_species_type_hide_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='mediareview',
            name='reply',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Explain why this review was wrong. Saving with a reply emails the reviewer once.',
            ),
        ),
        migrations.AddField(
            model_name='mediareview',
            name='reply_sent_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Set automatically when the reply email is sent.',
                null=True,
            ),
        ),
    ]
