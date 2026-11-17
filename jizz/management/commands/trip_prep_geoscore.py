"""Score a trip's birds with BirdNET GeoModel, per region pack and month.

    manage.py trip_prep_geoscore --country CO              # model -> DB + geoscore.csv
    manage.py trip_prep_geoscore --country CO --from-csv   # CSV -> DB only (no model needed, e.g. production)
    manage.py trip_prep_geoscore --country CO --dry-run    # print only

Samples the model at every area of the trip and of its region packs (``areas.json``, seeded by
``trip_prep_areas``), summarises per bird and month (see ``jizz/trips/geoscore.py``) and fills
``RegionSpeciesScore``. Writes ``jizz/trips/data/<cc>/geoscore.csv`` and ``geoscore.meta.json`` so
the result is committed and reproducible. Birds are matched to ``Species`` by scientific name.
"""

import csv
import datetime
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from jizz.models import RegionSpeciesScore, Species
from jizz.services.geomodel import GeoModel
from jizz.trips.content import TRIPS, country_dir, read_json, write_json
from jizz.trips.geoscore import SOURCE, STORE_MIN_P_MAX, TAU, summarize, trip_areas

CSV_FIELDS = ['region', 'species_code', 'month', 'p_mean', 'p_max', 'breadth']


def species_by_latin(species) -> dict:
    """Lowercased scientific name -> Species. A species stored under a trinomial (Collared Aracari,
    ``Pteroglossus torquatus torquatus``) is also found by its binomial, unless another species owns it."""
    by_latin = {s.name_latin.strip().lower(): s for s in species}
    for s in list(by_latin.values()):
        parts = s.name_latin.strip().lower().split()
        if len(parts) == 3 and ' '.join(parts[:2]) not in by_latin:
            by_latin[' '.join(parts[:2])] = s
    return by_latin


def trips_of(country: str) -> list[str]:
    """The country's own trip and its region packs (drafts too), in ``TRIPS`` order."""
    return [country] + [c for c, meta in TRIPS.items() if meta.get('parent') == country]


class Command(BaseCommand):
    help = 'Compute GeoModel scores per trip, region pack and month.'

    def add_arguments(self, parser):
        parser.add_argument('--country', required=True, help='Trip id of the country, e.g. CO')
        parser.add_argument('--from-csv', action='store_true', help='Load geoscore.csv instead of running the model')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        country = opts['country'].upper()
        if country not in TRIPS:
            raise CommandError(f'{country} is not a trip in TRIPS')
        folder = country_dir(country)
        if opts['from_csv']:
            return self.load_csv(country, folder / 'geoscore.csv')

        trips = [t for t in trips_of(country) if trip_areas(t)]
        if not trips:
            raise CommandError(f'no areas.json for {country} or its packs: run trip_prep_areas first')
        model = GeoModel()
        by_latin = species_by_latin(Species.objects.filter(retired_at__isnull=True).only('id', 'code', 'name_latin'))
        label_to_species = {i: by_latin[n] for n, i in model.species_index().items() if n in by_latin}
        self.stdout.write(f'model labels {model.label_count}, matched to species {len(label_to_species)}')
        idx = np.array(sorted(label_to_species))

        # Each distinct point is scored once; packs may share places.
        points = sorted({(a.lat, a.lon) for t in trips for a in trip_areas(t)})
        self.stdout.write(f'scoring {len(points)} points for {len(trips)} trips')
        scored = dict(zip(points, model.predict_months(points)[:, :, idx]))

        csv_rows, meta_regions = [], {}
        for trip in trips:
            areas = trip_areas(trip)
            cube = np.stack([scored[(a.lat, a.lon)] for a in areas])
            p_mean, p_max, breadth = summarize(cube, [a.weight for a in areas])
            keep = np.where(p_max.max(axis=0) >= STORE_MIN_P_MAX)[0]
            rows = []
            for k in keep:
                code = label_to_species[int(idx[k])].code
                for m in range(12):
                    rows.append((trip, code, m + 1, round(float(p_mean[m, k]), 3), round(float(p_max[m, k]), 3), round(float(breadth[m, k]), 3)))
            csv_rows += rows
            meta_regions[trip] = {'areas': len(areas), 'species': len(keep)}
            self.stdout.write(f'  {trip}: {len(areas)} areas, {len(keep)} species kept')

        if opts['dry_run']:
            return
        with open(folder / 'geoscore.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(CSV_FIELDS)
            w.writerows(csv_rows)
        write_json(folder / 'geoscore.meta.json', {
            'model': f'BirdNET GeoModel {settings.GEOMODEL_VERSION} (Apache-2.0, birdnet-team/geomodel)',
            'model_version': settings.GEOMODEL_VERSION,
            'likely_threshold': TAU,
            'month_score': 'mean of the 4 BirdNET weeks of the month',
            'generated': datetime.date.today().isoformat(),
            'regions': meta_regions,
        })
        self.save(csv_rows, settings.GEOMODEL_VERSION)

    def load_csv(self, country: str, path: Path):
        if not path.exists():
            raise CommandError(f'{path} not found')
        meta = read_json(path.with_name('geoscore.meta.json'), {}) or {}
        with open(path, newline='') as f:
            rows = [(r['region'], r['species_code'], int(r['month']), float(r['p_mean']), float(r['p_max']), float(r['breadth'])) for r in csv.DictReader(f)]
        self.save(rows, meta.get('model_version') or settings.GEOMODEL_VERSION)

    def save(self, rows, version: str):
        ids = dict(Species.objects.filter(retired_at__isnull=True).values_list('code', 'id'))
        regions = sorted({r[0] for r in rows})
        RegionSpeciesScore.objects.filter(region_code__in=regions, source=SOURCE).delete()
        objs, missing = [], set()
        for region, code, month, p_mean, p_max, breadth in rows:
            if code not in ids:
                missing.add(code)
                continue
            objs.append(RegionSpeciesScore(
                region_code=region, species_id=ids[code], month=month, p_mean=p_mean, p_max=p_max,
                breadth=breadth, source=SOURCE, model_version=version,
            ))
        RegionSpeciesScore.objects.bulk_create(objs, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(f'saved {len(objs)} rows for {", ".join(regions)}; {len(missing)} codes not in Species'))
