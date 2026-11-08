"""Check a Trip prep country before it ships: units, texts and the species list in the database.

Errors (exit code 1): a species in no unit or in two, missing texts, endemics units that don't match.
Warnings: long look_for lines, texts for units or species that no longer exist, no media.json yet,
species in the database scope that units.json doesn't have (run trip_prep_units again).

Examples:
  ./manage.py trip_prep_build --country LK
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from jizz.trips.checks import check_files
from jizz.trips.content import country_dir, read_json, scope_species


class Command(BaseCommand):
    help = "Check a Trip prep country's files against each other and the database."

    def add_arguments(self, parser):
        parser.add_argument('--country', required=True, help='Country code, e.g. LK')

    def handle(self, *args, **options):
        country = options['country'].upper()
        errors, warnings = check_files(country)

        units_data = read_json(country_dir(country) / 'units.json') or {}
        in_files = {c for g in units_data.get('groups', []) for c in g['species']}
        in_db = {s.code for s in scope_species(country)}
        for code in sorted(in_db - in_files):
            warnings.append(f'{code} is in scope in the database but not in units.json')
        for code in sorted(in_files - in_db):
            warnings.append(f'{code} is in units.json but no longer in scope in the database')

        for line in warnings:
            self.stdout.write(self.style.WARNING(f'warning: {line}'))
        for line in errors:
            self.stdout.write(self.style.ERROR(f'error: {line}'))
        summary = f'{country}: {len(in_files)} species, {len(errors)} errors, {len(warnings)} warnings'
        if errors:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(summary))
