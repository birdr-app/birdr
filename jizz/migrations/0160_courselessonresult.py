from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jizz", "0158_game_type_trip_prep"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourseLessonResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("course", models.SlugField(max_length=64)),
                ("week", models.PositiveSmallIntegerField()),
                ("score", models.PositiveSmallIntegerField(default=0)),
                ("total", models.PositiveSmallIntegerField(default=0)),
                ("completed_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_lesson_results",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-completed_at"],
                "unique_together": {("user", "course", "week")},
            },
        ),
    ]
