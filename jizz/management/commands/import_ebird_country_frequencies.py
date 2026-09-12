"""
Import per-month CountrySpeciesFrequency from eBird bar chart, ST CSV, or API.

eBird has no public frequency product (`/v2/product/freqlist` 404s). Histogram TSV
from a logged-in browser is the working source.

Examples:
  python manage.py import_ebird_country_frequencies --country NL --source barchart --tsv-path ./nl.txt
  python manage.py import_ebird_country_frequencies --country NL --source st_csv --data-dir ./jizz/ebird_st_csv
  python manage.py import_ebird_country_frequencies --country NL --source st_csv --csv-path ./data/eurrob1_regional_stats.csv
"""

from __future__ import annotations

import csv
import os
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from jizz.models import Country
from jizz.services.ebird_frequency.errors import (
    BarchartLoginRequired,
    EbirdFreqlistUnavailable,
    EbirdFrequencySourceError,
)
from jizz.services.ebird_frequency.persist import upsert_country_species_frequency
from jizz.services.ebird_frequency.sources.api import fetch_monthly_metrics_ebird_api
from jizz.services.ebird_frequency.sources.barchart import (
    barchart_page_url,
    fetch_monthly_metrics_barchart,
)
from jizz.services.ebird_frequency.sources.st_csv import fetch_monthly_metrics_st_csv
from jizz.services.ebird_frequency.year_round import apply_year_round_from_monthly


def _histogram_howto(country_code: str, year: int) -> str:
    page = barchart_page_url(country_code, year)
    return (
        f"While logged into eBird, open:\n  {page}\n"
        "Click “Download Histogram Data”, save the file, then:\n"
        f"  ./manage.py import_ebird_country_frequencies --country {country_code} "
        f"--source barchart --tsv-path /path/to/histogram.txt"
    )


class Command(BaseCommand):
    help = (
        'Fill CountrySpeciesFrequency from eBird histogram TSV or Status & Trends CSV. '
        'Region code = ISO or eBird subnational (US-MA). --source api is not supported by eBird.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--country', type=str, required=True, help='Country code (e.g. NL)')
        parser.add_argument(
            '--year',
            type=int,
            default=None,
            help=f'Reference calendar year (default: {date.today().year})',
        )
        parser.add_argument(
            '--months',
            type=str,
            default='1,2,3,4,5,6,7,8,9,10,11,12',
            help='Comma-separated month numbers (default all)',
        )
        parser.add_argument(
            '--source',
            type=str,
            choices=('api', 'st_csv', 'barchart', 'auto'),
            default='auto',
            help='auto: st_csv if --csv-path/--data-dir set, else barchart (not the missing freqlist API)',
        )
        parser.add_argument(
            '--tsv-path',
            type=str,
            default=None,
            help='For barchart: local TSV/histogram file instead of downloading',
        )
        parser.add_argument(
            '--csv-path',
            type=str,
            default=None,
            help='For st_csv: a single *_regional_stats.csv file',
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            default=None,
            help='For st_csv: directory containing *_regional_stats.csv (default uses jizz/ebird_st_csv if present)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and classify only; do not write DB',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite existing rows for same country_species/month/year',
        )
        parser.add_argument(
            '--limit-species',
            type=int,
            default=None,
            help='Max CountrySpecies rows to query (API only; for testing)',
        )
        parser.add_argument(
            '--skip-year-round',
            action='store_true',
            help=(
                'Do not copy peak monthly frequency onto CountrySpecies.frequency. '
                'By default, fills rows that Status & Trends never scored.'
            ),
        )

    def handle(self, *args, **options):
        cc = options['country'].strip().upper()
        year = int(options['year'] if options['year'] is not None else date.today().year)
        months = [int(x.strip()) for x in options['months'].split(',') if x.strip()]
        for m in months:
            if m < 1 or m > 12:
                raise CommandError(f'Invalid month: {m}')

        if not Country.objects.filter(pk=cc).exists():
            raise CommandError(f'Country {cc} not in database')
        country = Country.objects.get(pk=cc)
        extra_codes = set()
        if country.codes:
            for part in str(country.codes).split(','):
                part = part.strip()
                if part:
                    extra_codes.add(part.upper())

        source = options['source']
        csv_path = options.get('csv_path')
        if source == 'auto':
            source = 'st_csv' if (csv_path or options.get('data_dir')) else 'barchart'

        def _infer_st_region_code_from_csv(path: str) -> str | None:
            try:
                with open(path, newline="", encoding="utf-8", errors="replace") as f:
                    dr = csv.DictReader(f)
                    fns = dr.fieldnames or []
                    if not fns:
                        return None
                    if "region_code" not in fns or "region_name" not in fns:
                        return None
                    for row in dr:
                        if (row.get("region_type") or "").strip().lower() != "country":
                            continue
                        rn = (row.get("region_name") or "").strip().lower()
                        if rn and rn == (country.name or "").strip().lower():
                            rc = (row.get("region_code") or "").strip().upper()
                            return rc or None
            except OSError:
                return None
            return None

        if source == "st_csv" and not extra_codes:
            # Try to infer ISO3-like ST region code (e.g. NLD) by matching region_name.
            data_dir = options.get("data_dir")
            probe_paths: list[str] = []
            if csv_path:
                probe_paths = [csv_path]
            else:
                base = data_dir or os.path.join(str(getattr(settings, "BASE_DIR", ".")), "jizz", "ebird_st_csv")
                if os.path.isdir(base):
                    for name in os.listdir(base):
                        if name.lower().endswith("_regional_stats.csv"):
                            probe_paths.append(os.path.join(base, name))
                            if len(probe_paths) >= 5:
                                break
            for p in probe_paths:
                inferred = _infer_st_region_code_from_csv(p)
                if inferred and inferred != cc:
                    extra_codes.add(inferred)
                    break
            if extra_codes:
                self.stdout.write(f"Inferred ST region_code(s) for {cc}: {sorted(extra_codes)} (set Country.codes to persist)")

        rows = []
        try:
            if source == 'api':
                rows = list(
                    fetch_monthly_metrics_ebird_api(
                        cc,
                        year,
                        months,
                        limit_species=options.get('limit_species'),
                    )
                )
                self.stdout.write(f'API collected {len(rows)} month/species rows')
            elif source == 'st_csv':
                rows = list(
                    fetch_monthly_metrics_st_csv(
                        cc,
                        year,
                        months,
                        csv_path=csv_path,
                        data_dir=options.get('data_dir'),
                        region_codes=extra_codes,
                    )
                )
                self.stdout.write(f'CSV collected {len(rows)} rows')
            elif source == 'barchart':
                tsv_text = None
                tsv_path = options.get('tsv_path')
                if tsv_path:
                    try:
                        with open(tsv_path, encoding='utf-8', errors='replace') as handle:
                            tsv_text = handle.read()
                    except OSError as exc:
                        raise CommandError(f'Could not read {tsv_path}: {exc}') from exc
                rows = list(
                    fetch_monthly_metrics_barchart(
                        cc,
                        year,
                        months,
                        tsv_text=tsv_text,
                    )
                )
                self.stdout.write(f'Bar chart collected {len(rows)} month/species rows')
        except EbirdFreqlistUnavailable as exc:
            raise CommandError(
                "eBird has no public frequency API (/v2/product/freqlist does not exist), "
                "so --source api cannot collect rows.\n"
                f"{_histogram_howto(cc, year)}"
            ) from exc
        except BarchartLoginRequired as exc:
            raise CommandError(
                "eBird bar-chart downloads require a logged-in browser; the API token is not enough.\n"
                f"{_histogram_howto(cc, year)}"
            ) from exc
        except EbirdFrequencySourceError as exc:
            raise CommandError(str(exc)) from exc

        if not rows:
            extra = ""
            if source == "barchart" and not options.get("tsv_path"):
                extra = "\n" + _histogram_howto(cc, year)
            raise CommandError(f"Nothing to import from {source} for {cc}.{extra}")

        n_ok, n_skip = upsert_country_species_frequency(
            rows,
            dry_run=options['dry_run'],
            force=options['force'],
        )
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f'Dry-run: would process {n_ok} rows'))
            return

        self.stdout.write(
            self.style.SUCCESS(f'Wrote {n_ok} rows, skipped {n_skip} (use --force to overwrite)')
        )

        if not options.get('skip_year_round'):
            n_year = apply_year_round_from_monthly(cc, only_without_st=True)
            if n_year:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Set year-round frequency from monthly peak on {n_year} '
                        f'CountrySpecies row(s) that had no Status & Trends score'
                    )
                )
