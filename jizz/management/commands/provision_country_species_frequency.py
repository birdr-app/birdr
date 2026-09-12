"""
Provision CountrySpecies.frequency and frequency_pct from eBird Status and Trends regional data.

Downloads CSV by composing the URL from species code and EBIRD_ST_ACCESS_KEY (from settings;
override with --key). Parses region_code and abundance_mean, aggregates by mean across seasons,
computes tier from normalized abundance (single-species) or percentile rank (all-species mode),
and updates CountrySpecies.

Usage:
  Single species (URL built from --species and settings.EBIRD_ST_ACCESS_KEY):
    manage.py provision_country_species_frequency --species tunswa
  With country filter:
    manage.py provision_country_species_frequency --species tunswa --country NL
  All countries in CSV, skip already-provisioned:
    manage.py provision_country_species_frequency --species tunswa --skip-existing
  All-species mode (percentile tiers, requires --country; key from settings):
    manage.py provision_country_species_frequency --country NL --all-species
"""

import csv
import io
import time
from django.conf import settings
from django.core.management.base import BaseCommand

from jizz.models import CountrySpecies, Country, Species
from jizz.st_subnational_regions import app_code_for_st_region
from jizz.utils import (
    download_ebird_regional_zip,
    ebird_st_list_files,
    ST_DOWNLOAD_BASE,
)


# Single-species: normalized (0-1) -> tier. Plan thresholds.
def normalized_to_tier(normalized: float) -> str:
    if normalized > 0.5:
        return 'very_common'
    if normalized > 0.25:
        return 'common'
    if normalized > 0.1:
        return 'fairly_common'
    if normalized > 0.03:
        return 'uncommon'
    if normalized > 0.01:
        return 'rare'
    return 'very_rare'


# All-species: percentile rank (0-100, higher = more common) -> tier.
def percentile_to_tier(pct: float) -> str:
    if pct >= 95:
        return 'very_common'
    if pct >= 85:
        return 'common'
    if pct >= 70:
        return 'fairly_common'
    if pct >= 45:
        return 'uncommon'
    if pct >= 20:
        return 'rare'
    return 'very_rare'


def _percentile_95(values):
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = min(int(len(sorted_vals) * 0.95), len(sorted_vals) - 1)
    return sorted_vals[idx] if idx >= 0 else sorted_vals[0]


class Command(BaseCommand):
    help = (
        'Provision CountrySpecies.frequency and frequency_pct from eBird Status and Trends. '
        'Single-species: use --species (URL is built from species code; key from settings.EBIRD_ST_ACCESS_KEY). '
        'All-species: use --all-species with --country (key from settings).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--country',
            type=str,
            default=None,
            help='Limit to one country code (e.g. NL). If omitted, process all countries in the CSV.',
        )
        parser.add_argument(
            '--species',
            type=str,
            default=None,
            help='Species code (e.g. tunswa). URL is composed as {year}/{code}/web_download/{code}_regional_{year}.zip.',
        )
        parser.add_argument(
            '--key',
            type=str,
            default=None,
            help='eBird Status and Trends access key (overrides settings.EBIRD_ST_ACCESS_KEY / local.py).',
        )
        parser.add_argument(
            '--version-year',
            type=int,
            default=2023,
            help='Version year for eBird ST URL (default 2023).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only print what would be updated.',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            default=None,
            help='Skip CountrySpecies that already have frequency_pct set (default when processing all countries).',
        )
        parser.add_argument(
            '--no-skip-existing',
            action='store_false',
            dest='skip_existing',
            help='Do not skip rows that already have frequency_pct (overwrite).',
        )
        parser.add_argument(
            '--all-species',
            action='store_true',
            help='Iterate over all species for --country, compute percentile tiers. Requires --country; key from settings.',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Seconds between API requests in --all-species mode (default 1.0).',
        )

    def handle(self, *args, **options):
        country_code = options['country']
        dry_run = options['dry_run']
        skip_existing = options['skip_existing']
        if skip_existing is None:
            skip_existing = country_code is None

        if options['all_species']:
            access_key = options.get('key') or getattr(settings, 'EBIRD_ST_ACCESS_KEY', None) or ''
            if not country_code:
                self.stdout.write(self.style.ERROR('--all-species requires --country.'))
                return
            if not access_key:
                self.stdout.write(
                    self.style.ERROR(
                        'eBird Status and Trends access key required. '
                        'Set EBIRD_ST_ACCESS_KEY in settings (e.g. local.py) or use --key. '
                        'Get a key at https://ebird.org/st/request'
                    )
                )
                return
            self._provision_all_species(
                country_code=country_code,
                dry_run=dry_run,
                skip_existing=skip_existing,
                access_key=access_key,
                version_year=options['version_year'],
                delay=options['delay'],
            )
            return

        species_code = (options.get('species') or '').strip()
        if not species_code:
            self.stdout.write(
                self.style.ERROR('Provide --species (e.g. tunswa). URL is composed from species code and key from settings.')
            )
            return
        access_key = options.get('key') or getattr(settings, 'EBIRD_ST_ACCESS_KEY', None) or ''
        if not access_key:
            self.stdout.write(
                self.style.ERROR(
                    'eBird Status and Trends access key required. '
                    'Set EBIRD_ST_ACCESS_KEY in settings (e.g. local.py) or use --key. '
                    'Get a key at https://ebird.org/st/request'
                )
            )
            return
        year = options['version_year']
        obj_key = f'{year}/{species_code}/web_download/{species_code}_regional_{year}.zip'
        url = f'{ST_DOWNLOAD_BASE}/fetch?objKey={obj_key}&key={access_key}'

        self._provision_from_url(
            url=url,
            country_code=country_code,
            dry_run=dry_run,
            skip_existing=skip_existing,
        )

    def _provision_from_url(self, url, country_code=None, dry_run=False, skip_existing=False):
        """Download from URL (ZIP or CSV), parse, aggregate, assign tiers, update DB."""
        try:
            content = download_ebird_regional_zip(url)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Download failed: {e}'))
            return

        region_col = None
        rows_by_region = {}  # region_code -> list of abundance_mean
        all_abundances = []
        species_code_from_csv = None
        reader = csv.DictReader(io.StringIO(content))
        fieldnames = reader.fieldnames or []
        for col in ('region_code', 'region', 'country_code'):
            if col in fieldnames:
                region_col = col
                break
        if not region_col or 'abundance_mean' not in fieldnames:
            self.stdout.write(
                self.style.ERROR('CSV must have region_code (or region/country_code) and abundance_mean.')
            )
            return
        if 'species_code' in fieldnames:
            pass  # will read from first row

        for row in reader:
            region_code = (row.get(region_col) or '').strip().upper()
            if not region_code:
                continue
            region_code = app_code_for_st_region(region_code, row.get('region_name')) or region_code
            if species_code_from_csv is None and 'species_code' in fieldnames:
                species_code_from_csv = (row.get('species_code') or '').strip()
            try:
                ab = float(row.get('abundance_mean', 0))
            except (ValueError, TypeError):
                continue
            if region_code not in rows_by_region:
                rows_by_region[region_code] = []
            rows_by_region[region_code].append(ab)
            all_abundances.append(ab)

        if not all_abundances:
            self.stdout.write(self.style.WARNING('No abundance data in CSV.'))
            return

        species_peak = _percentile_95(all_abundances)
        if species_peak <= 0:
            self.stdout.write(self.style.WARNING('Species peak is 0, skipping.'))
            return

        countries = {c.code: c for c in Country.objects.all()}
        if country_code:
            country_code = country_code.upper()
            regions_to_process = [country_code] if country_code in rows_by_region else []
        else:
            regions_to_process = [r for r in rows_by_region if r in countries]

        if not regions_to_process:
            self.stdout.write(self.style.WARNING('No matching regions to process.'))

        species = None
        if species_code_from_csv:
            species = Species.objects.filter(code=species_code_from_csv).first()
        if not species and regions_to_process:
            for r in regions_to_process:
                cs = CountrySpecies.objects.filter(country_id=r).select_related('species').first()
                if cs:
                    species = cs.species
                    break
        if not species:
            self.stdout.write(self.style.ERROR('Could not determine species from CSV or DB.'))
            return

        to_update = []
        for region_code in regions_to_process:
            country = countries.get(region_code)
            if not country:
                continue
            vals = rows_by_region.get(region_code, [])
            if not vals:
                continue
            mean_abundance = sum(vals) / len(vals)
            normalized = min(mean_abundance / species_peak, 1.0)
            tier = normalized_to_tier(normalized)
            frequency_pct = normalized * 100.0

            cs = CountrySpecies.objects.filter(
                country_id=country.code,
                species_id=species.id,
            ).first()
            if not cs:
                continue
            if skip_existing and cs.frequency_pct is not None:
                continue
            if cs.frequency != tier or cs.frequency_pct != frequency_pct:
                cs.frequency = tier
                cs.frequency_pct = frequency_pct
                to_update.append(cs)

        if dry_run:
            self.stdout.write(f'Would update {len(to_update)} CountrySpecies ({species.code} / {species.name}).')
            for cs in to_update[:15]:
                self.stdout.write(f'  {cs.country_id} -> {cs.frequency} ({cs.frequency_pct:.1f}%)')
            if len(to_update) > 15:
                self.stdout.write(f'  ... and {len(to_update) - 15} more')
            return

        if to_update:
            CountrySpecies.objects.bulk_update(to_update, ['frequency', 'frequency_pct'], batch_size=500)
            self.stdout.write(self.style.SUCCESS(f'Updated {len(to_update)} CountrySpecies.'))

    def _provision_all_species(
        self,
        country_code,
        dry_run=False,
        skip_existing=False,
        access_key='',
        version_year=2023,
        delay=1.0,
    ):
        """Download regional stats for all species in country, then assign percentile-based tiers."""
        import requests
        country_code = country_code.upper()
        qs = Species.objects.filter(
            countryspecies__country_id=country_code,
        ).distinct()
        species_codes = list(qs.values_list('code', flat=True))
        if not species_codes:
            self.stdout.write(self.style.WARNING('No species for this country.'))
            return

        countries = {c.code: c for c in Country.objects.all()}
        if country_code not in countries:
            self.stdout.write(self.style.ERROR(f'Country {country_code} not found.'))
            return

        # (species_id, mean_abundance) for this country
        species_abundances = []  # (species_id, mean_abundance)
        code_to_species = {s.code: s for s in Species.objects.filter(code__in=species_codes)}

        for i, sp_code in enumerate(species_codes):
            if i > 0 and delay > 0:
                time.sleep(delay)
            obj_key = None
            try:
                paths = ebird_st_list_files(sp_code, access_key, version_year)
                for p in paths:
                    if isinstance(p, str):
                        if p.endswith('regional_stats.csv'):
                            obj_key = p
                            break
                        if '_regional_' in p and p.endswith('.zip'):
                            obj_key = p
                            break
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  {sp_code}: list error - {e}'))
                continue
            if not obj_key:
                continue
            try:
                url = f'{ST_DOWNLOAD_BASE}/fetch'
                r = requests.get(url, params={'objKey': obj_key, 'key': access_key}, timeout=120)
                r.raise_for_status()
                if obj_key.endswith('.zip') or r.content[:4] == b'PK\x03\x04':
                    import zipfile
                    with zipfile.ZipFile(io.BytesIO(r.content), 'r') as zf:
                        for name in zf.namelist():
                            if name.lower().endswith('.csv'):
                                content = zf.read(name).decode('utf-8', errors='replace')
                                break
                        else:
                            continue
                else:
                    content = r.text
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  {sp_code}: fetch error - {e}'))
                continue

            region_col = None
            reader = csv.DictReader(io.StringIO(content))
            fieldnames = reader.fieldnames or []
            for col in ('region_code', 'region', 'country_code'):
                if col in fieldnames:
                    region_col = col
                    break
            if not region_col or 'abundance_mean' not in fieldnames:
                continue

            vals = []
            for row in reader:
                rc = (row.get(region_col) or '').strip().upper()
                if rc != country_code:
                    continue
                try:
                    vals.append(float(row.get('abundance_mean', 0)))
                except (ValueError, TypeError):
                    pass
            if not vals:
                continue
            mean_ab = sum(vals) / len(vals)
            species = code_to_species.get(sp_code)
            if species:
                species_abundances.append((species.id, mean_ab))

        if not species_abundances:
            self.stdout.write(self.style.WARNING('No abundance data collected for this country.'))
            return

        species_abundances.sort(key=lambda x: -x[1])
        n = len(species_abundances)
        to_update = []
        for rank, (species_id, mean_ab) in enumerate(species_abundances):
            pct = 100.0 * (n - rank) / n if n else 100.0
            tier = percentile_to_tier(pct)
            cs = CountrySpecies.objects.filter(
                country_id=country_code,
                species_id=species_id,
            ).first()
            if not cs:
                continue
            if skip_existing and cs.frequency_pct is not None:
                continue
            if cs.frequency != tier or cs.frequency_pct != pct:
                cs.frequency = tier
                cs.frequency_pct = pct
                to_update.append(cs)

        if dry_run:
            self.stdout.write(f'Would update {len(to_update)} CountrySpecies (percentile tiers).')
            for cs in to_update[:15]:
                self.stdout.write(f'  {cs.species.code} -> {cs.frequency} ({cs.frequency_pct:.1f}%)')
            return

        if to_update:
            CountrySpecies.objects.bulk_update(to_update, ['frequency', 'frequency_pct'], batch_size=500)
            self.stdout.write(self.style.SUCCESS(f'Updated {len(to_update)} CountrySpecies (all-species percentile).'))
