"""Audit a country's Trip prep lists against its GeoModel scores.

    manage.py trip_prep_audit --country CO            # prints, writes docs/trip-prep/audit-co.md
    manage.py trip_prep_audit --country CO --no-write

For the country trip and each region pack: regional birds in the country trip, pack birds that are
stronger in another pack or widespread, birds the model has no view on, and birds likely there but
in no list. Needs ``trip_prep_geoscore`` first.
It changes nothing: edit ``scope.json`` ``add`` / ``drop`` by hand after reading it.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from jizz.models import CountrySpecies, Species
from jizz.trips.audit import audit, render_markdown
from jizz.trips.content import TRIPS, country_dir, read_json, trip_countries
from jizz.trips.geoscore import load_scores

DOCS = Path(__file__).resolve().parents[3] / 'docs' / 'trip-prep'


class Command(BaseCommand):
    help = 'Report birds that look misplaced or missing in a country\'s trip lists.'

    def add_arguments(self, parser):
        parser.add_argument('--country', required=True)
        parser.add_argument('--no-write', action='store_true')
        parser.add_argument('--max-gaps', type=int, default=40)

    def handle(self, *args, **opts):
        country = opts['country'].upper()
        if country not in TRIPS:
            raise CommandError(f'{country} is not a trip in TRIPS')
        regions = [country] + [c for c, meta in TRIPS.items() if meta.get('parent') == country]
        lists, scores = {}, {}
        for region in regions:
            units = read_json(country_dir(region) / 'units.json')
            if not units:
                continue
            lists[region] = {c for g in units['groups'] for c in g['species']}
            scores[region] = load_scores(region)
        if not any(scores.values()):
            raise CommandError('no scores: run trip_prep_geoscore first')

        ok = set(
            CountrySpecies.objects.filter(country_id__in=trip_countries(country), status__in=('native', 'endemic', 'introduced'))
            .exclude(frequency='vagrant').values_list('species__code', flat=True)
        )
        result = audit(scores, lists, country, countries_ok=ok, max_gaps=opts['max_gaps'])
        names = dict(Species.objects.values_list('code', 'name'))
        meta = read_json(country_dir(country) / 'geoscore.meta.json', {}) or {}
        note = f"BirdNET GeoModel {meta.get('model_version') or settings.GEOMODEL_VERSION}"
        text = render_markdown(country, result, names, note)

        for region, parts in result.items():
            self.stdout.write(
                f'{region}: {len(parts["look"])} to look at, {len(parts["no_signal"])} without a model view, {len(parts["gaps"])} gaps'
            )
        if not opts['no_write']:
            path = DOCS / f'audit-{country.lower()}.md'
            path.write_text(text + '\n', encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'wrote {path}'))
