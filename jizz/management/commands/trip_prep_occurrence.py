"""Fetch per-region, per-month bird occurrence from GBIF's copy of the eBird dataset.

    manage.py trip_prep_occurrence --country CO
    manage.py trip_prep_occurrence --country CO --pack CO-ANDES=Antioquia,Caldas,Risaralda

Fills ``RegionSpeciesMonth`` and writes ``jizz/trips/data/<cc>/occurrence.csv`` so
region picks are reproducible. Records are a ranking signal, not checklist %.
"""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from jizz.models import RegionSpeciesMonth, Species
from jizz.services.gbif_region_months import fetch_region_month_counts

DATA = Path(__file__).resolve().parents[2] / 'trips' / 'data'


def binomial(name: str) -> str:
    """'Coragyps atratus (Bechstein, 1793)' -> 'Coragyps atratus'."""
    parts = name.split()
    return ' '.join(parts[:2])


class Command(BaseCommand):
    help = 'Import per-month species occurrence per region (GBIF/eBird).'

    def add_arguments(self, parser):
        parser.add_argument('--country', required=True, help='ISO alpha-2, e.g. CO')
        parser.add_argument(
            '--pack', action='append', default=[],
            help='REGION_CODE=State1,State2 (GBIF stateProvince names). Repeatable.',
        )

    def handle(self, *args, **opts):
        cc = opts['country'].upper()
        targets = [(cc, None)]
        for spec in opts['pack']:
            if '=' not in spec:
                raise CommandError(f'--pack needs CODE=State,State: {spec}')
            code, states = spec.split('=', 1)
            targets.append((code.strip().upper(), [s.strip() for s in states.split(',') if s.strip()]))

        by_latin = {}
        for sp in Species.objects.all().only('id', 'code', 'name_latin'):
            by_latin[sp.name_latin.strip().lower()] = sp

        out_rows = []
        for code, states in targets:
            self.stdout.write(f'{code}: fetching 12 months ({"country" if not states else ", ".join(states)})')
            counts, totals = fetch_region_month_counts(cc, states)
            RegionSpeciesMonth.objects.filter(region_code=code).delete()
            rows, missed = [], set()
            for month, species in counts.items():
                total = totals.get(month, 0) or 1
                merged = {}
                for name, n in species.items():
                    merged[binomial(name).lower()] = merged.get(binomial(name).lower(), 0) + n
                for latin, n in merged.items():
                    sp = by_latin.get(latin)
                    if sp is None:
                        missed.add(latin)
                        continue
                    rows.append(RegionSpeciesMonth(
                        region_code=code, species=sp, month=month,
                        records=n, total_records=totals.get(month, 0), rel_freq=n / total,
                    ))
                    out_rows.append((code, sp.code, month, n, totals.get(month, 0)))
            RegionSpeciesMonth.objects.bulk_create(rows, batch_size=2000)
            self.stdout.write(f'  saved {len(rows)} rows; {len(missed)} GBIF names unmatched')

        folder = DATA / cc.lower()
        if folder.is_dir():
            with open(folder / 'occurrence.csv', 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['region', 'species_code', 'month', 'records', 'total_records'])
                w.writerows(out_rows)
            self.stdout.write(f'wrote {folder / "occurrence.csv"}')
