"""List the Trip prep texts a country still needs, and optionally write a worklist for writers.

Shared texts (group ``about``, species ``look_for``) are written once and reused by every country,
so a second country only needs the ones that are new. The writing guide is docs/trip-prep/STYLE.md.

Examples:
  ./manage.py trip_prep_texts --country LK
  ./manage.py trip_prep_texts --country LK --worklist /tmp/lk-worklist.json
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from jizz.trips.content import DATA_DIR, LANGUAGES, country_dir, read_json, scope_species


def has_text(value) -> bool:
    return isinstance(value, dict) and all((value.get(lang) or '').strip() for lang in LANGUAGES)


def missing_texts(country: str) -> dict:
    units_data = read_json(country_dir(country) / 'units.json')
    if not units_data:
        raise CommandError(f'No units.json for {country}; run trip_prep_units first')
    texts = read_json(country_dir(country) / 'texts.json', {}) or {}

    groups = []
    for group in units_data['groups']:
        shared = read_json(DATA_DIR / 'groups' / f'{group["slug"]}.json', {}) or {}
        if not has_text(shared.get('about')):
            groups.append(group['slug'])

    species = []
    for path_code in (c for g in units_data['groups'] for c in g['species']):
        shared = read_json(DATA_DIR / 'species' / f'{path_code}.json', {}) or {}
        lines = shared.get('look_for') or []
        if len(lines) != 3 or not all(has_text(line) for line in lines):
            species.append(path_code)

    country_missing = []
    if not has_text(texts.get('intro')):
        country_missing.append('intro')
    for group in units_data['groups']:
        if not has_text(texts.get('groups', {}).get(group['slug'], {}).get('here')):
            country_missing.append(f'groups.{group["slug"]}.here')
    for unit in units_data['units']:
        entry = texts.get('units', {}).get(unit['slug'], {})
        for part in ('title', 'intro'):
            if not has_text(entry.get(part)):
                country_missing.append(f'units.{unit["slug"]}.{part}')
    for part in ('title', 'intro'):
        if not has_text(texts.get('first_day', {}).get(part)):
            country_missing.append(f'first_day.{part}')
    endemics = texts.get('endemics', {})
    if units_data['endemic_units']:
        if not has_text(endemics.get('why_here')):
            country_missing.append('endemics.why_here')
        if not endemics.get('where'):
            country_missing.append('endemics.where')
        for unit in units_data['endemic_units']:
            if not has_text(endemics.get('units', {}).get(unit['slug'], {}).get('title')):
                country_missing.append(f'endemics.units.{unit["slug"]}.title')
    return {'groups': groups, 'species': species, 'country': country_missing}


class Command(BaseCommand):
    help = 'List the Trip prep texts a country still needs.'

    def add_arguments(self, parser):
        parser.add_argument('--country', required=True, help='Country code, e.g. LK')
        parser.add_argument('--worklist', help='Write a JSON worklist with everything a writer needs to this file')

    def handle(self, *args, **options):
        country = options['country'].upper()
        missing = missing_texts(country)
        self.stdout.write(
            f'{country}: {len(missing["groups"])} group texts, {len(missing["species"])} species texts, '
            f'{len(missing["country"])} country texts missing'
        )
        for key in ('groups', 'species', 'country'):
            if missing[key]:
                self.stdout.write(f'  {key}: {", ".join(missing[key][:30])}{" ..." if len(missing[key]) > 30 else ""}')

        if options['worklist']:
            path = Path(options['worklist'])
            path.write_text(json.dumps(worklist(country, missing), ensure_ascii=False, indent=1), encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'Wrote {path}'))


def worklist(country: str, missing: dict) -> dict:
    from jizz.models import SpeciesGroup

    units_data = read_json(country_dir(country) / 'units.json')
    species = {s.code: s for s in scope_species(country)}
    unit_of = {code: u['slug'] for u in units_data['units'] for code in u['species']}
    return {
        'country': country,
        'guide': 'docs/trip-prep/STYLE.md',
        'missing': missing,
        'species': [
            {
                'code': s.code,
                'name': {'en': s.name, 'nl': s.name_nl},
                'latin': s.latin,
                'group': s.group_slug,
                'unit': unit_of.get(s.code),
                'status': s.status,
                'frequency': s.frequency,
                'range_pct': round(s.frequency_pct, 1) if s.frequency_pct is not None else None,
            }
            for s in species.values()
        ],
        'groups': [
            {**g, 'species_names': [species[c].name for c in g['species']]} for g in units_data['groups']
        ],
        'units': [
            {**u, 'species_names': [species[c].name for c in u['species']]} for u in units_data['units']
        ],
        'endemic_units': [
            {**u, 'species_names': [species[c].name for c in u['species']]} for u in units_data['endemic_units']
        ],
        'first_day': [species[c].name for c in units_data['first_day']],
        'all_groups': [
            {'slug': g.slug, 'en': g.name_en, 'nl': g.name_nl} for g in SpeciesGroup.objects.order_by('sort_order')
        ],
    }
