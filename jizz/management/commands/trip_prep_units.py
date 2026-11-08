"""Write a Trip prep country's units.json: its groups, units of 4-7 species and endemics units.

Species come from CountrySpecies (regular natives and introduced birds, plus every endemic) with the
changes in the country's scope.json. "Your first day" comes from scope.json's ``first_day``; without
one, the 20 commonest species are suggested.

Unit titles may be edited by hand in units.json. Running again keeps edited titles of units whose
slug still exists; use --reset-titles to regenerate them.

Examples:
  ./manage.py trip_prep_units --country LK
  ./manage.py trip_prep_units --country LK --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from jizz.trips.content import country_dir, load_scope, read_json, scope_species, write_json
from jizz.trips.units import build_units


class Command(BaseCommand):
    help = "Group a Trip prep country's species into units and write units.json."

    def add_arguments(self, parser):
        parser.add_argument('--country', required=True, help='Country code, e.g. LK')
        parser.add_argument('--dry-run', action='store_true', help='Print the units without writing')
        parser.add_argument('--reset-titles', action='store_true', help='Regenerate unit titles edited by hand')

    def handle(self, *args, **options):
        country = options['country'].upper()
        try:
            species = scope_species(country)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if not species:
            raise CommandError(f'No species in scope for {country}')

        scope = load_scope(country)
        data = build_units(species, scope['first_day'])

        path = country_dir(country) / 'units.json'
        old = read_json(path, {}) or {}
        if not options['reset_titles']:
            old_titles = {u['slug']: u['title'] for u in old.get('units', [])}
            for unit in data['units']:
                unit['title'] = old_titles.get(unit['slug'], unit['title'])

        names = {s.code: s.name for s in species}
        endemic_count = sum(s.endemic for s in species)
        self.stdout.write(
            f'{country}: {len(species)} species ({endemic_count} endemic), {len(data["groups"])} groups, '
            f'{len(data["units"])} units, {len(data["endemic_units"])} endemics units'
        )
        for unit in data['units']:
            self.stdout.write(f'  {unit["slug"]:40} {len(unit["species"])}  {", ".join(names[c] for c in unit["species"])}')
        if not scope['first_day']:
            self.stdout.write('First day (suggested; set first_day in scope.json to choose):')
        else:
            self.stdout.write('First day:')
        self.stdout.write('  ' + ', '.join(names[c] for c in data['first_day']))
        missing = [c for c in scope['first_day'] if c not in names]
        if missing:
            self.stdout.write(self.style.WARNING(f'first_day codes not in scope: {", ".join(missing)}'))

        if options['dry_run']:
            return
        write_json(path, {'country': country, **data})
        self.stdout.write(self.style.SUCCESS(f'Wrote {path}'))
