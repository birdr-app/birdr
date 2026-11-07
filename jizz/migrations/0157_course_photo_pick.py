from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jizz", "0156_userprofile_visual_style_bertie_to_tody"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoursePhotoPick",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("course", models.SlugField(max_length=64)),
                ("week", models.PositiveSmallIntegerField()),
                ("card", models.JSONField(blank=True, default=list)),
                ("quiz", models.JSONField(blank=True, default=list)),
                ("reject", models.JSONField(blank=True, default=list)),
                ("done", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "species",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_photo_picks",
                        to="jizz.species",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["course", "week", "species_id"],
                "unique_together": {("course", "week", "species")},
            },
        ),
    ]
