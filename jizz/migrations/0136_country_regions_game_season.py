# Country parent/kind/hemisphere and Game.season

import django.db.models.deletion
from django.db import migrations, models


def backfill_country_regions(apps, schema_editor):
    Country = apps.get_model("jizz", "Country")
    from jizz.playable_regions import (
        inferred_hemisphere,
        inferred_kind,
        inferred_parent_code,
    )

    countries = {c.code: c for c in Country.objects.all()}
    for country in countries.values():
        country.kind = inferred_kind(country.code)
        country.hemisphere = inferred_hemisphere(country.code)
        parent_code = inferred_parent_code(country.code)
        if parent_code and parent_code in countries and parent_code != country.code:
            country.parent_id = parent_code
        else:
            country.parent_id = None
        country.save(update_fields=["kind", "hemisphere", "parent_id"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("jizz", "0135_species_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="country",
            name="hemisphere",
            field=models.CharField(
                choices=[("north", "Northern"), ("south", "Southern")],
                default="north",
                help_text="Used to map calendar seasons to months.",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="country",
            name="kind",
            field=models.CharField(
                choices=[
                    ("country", "Country"),
                    ("subnational", "Subnational"),
                    ("aggregate", "Aggregate"),
                    ("specialty", "Specialty"),
                ],
                db_index=True,
                default="country",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="country",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                help_text="Sovereign country this region belongs to (e.g. US-MA → US).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="children",
                to="jizz.country",
            ),
        ),
        migrations.AddField(
            model_name="game",
            name="season",
            field=models.CharField(
                blank=True,
                choices=[
                    ("spring", "Spring"),
                    ("summer", "Summer"),
                    ("autumn", "Autumn"),
                    ("winter", "Winter"),
                ],
                help_text="When set, question selection uses monthly eBird frequency for this season.",
                max_length=10,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_country_regions, noop_reverse),
    ]
