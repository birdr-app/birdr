"""Import AVONET morphometrics into SpeciesFact (CC BY 4.0)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from django.db import transaction

from compare.facts import AVONET_ATTRIBUTION, AVONET_LICENSE, upsert_fact
from compare.models import SpeciesFact
from jizz.models import Species

logger = logging.getLogger(__name__)

# AVONET eBird sheet column aliases → (category, key)
_NUMERIC_COLUMNS = {
    'Mass': ('measurements', 'body_mass_g'),
    'Wing.Length': ('measurements', 'wing_length_mm'),
    'Beak.Length_culmen': ('measurements', 'bill_culmen_mm'),
    'Beak.Length_nares': ('measurements', 'bill_nares_mm'),
    'Beak.Width': ('measurements', 'bill_width_mm'),
    'Beak.Depth': ('measurements', 'bill_depth_mm'),
    'Tarsus.Length': ('measurements', 'tarsus_mm'),
    'Tail.Length': ('measurements', 'tail_length_mm'),
    'Hand-Wing.Index': ('measurements', 'hand_wing_index'),
    'Kipps.Distance': ('measurements', 'kipps_distance_mm'),
}

_TEXT_COLUMNS = {
    'Habitat': ('habitat', 'habitat'),
    'Migration': ('behavior', 'migration'),
    'Trophic.Level': ('diet', 'trophic_level'),
    'Trophic.Niche': ('diet', 'trophic_niche'),
    'Primary.Lifestyle': ('behavior', 'primary_lifestyle'),
}


def _parse_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() in ('NA', 'NAN', 'NULL', '-'):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _row_species_code(row: dict[str, str]) -> str | None:
    for key in ('Species.Code', 'speciesCode', 'SpeciesCode', 'species_code', 'Code'):
        value = (row.get(key) or '').strip()
        if value:
            return value
    return None


def _row_scientific_name(row: dict[str, str]) -> str | None:
    for key in ('Species', 'Scientific.Name', 'scientificName', 'name_latin'):
        value = (row.get(key) or '').strip()
        if value:
            return value
    return None


def import_avonet_csv(path: str | Path, *, limit: int | None = None) -> dict[str, int]:
    """
    Load an AVONET eBird-taxonomy CSV and upsert SpeciesFact rows.

    Matches Birdr species by eBird ``code`` when present, else by ``name_latin``.
    """
    path = Path(path)
    created = updated = skipped = unmatched = 0
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f'No header row in {path}')

        species_by_code = {s.code: s for s in Species.objects.exclude(code='').iterator()}
        species_by_latin = {
            (s.name_latin or '').strip().lower(): s
            for s in Species.objects.exclude(name_latin='').iterator()
            if (s.name_latin or '').strip()
        }

        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            code = _row_species_code(row)
            latin = _row_scientific_name(row)
            species = None
            if code and code in species_by_code:
                species = species_by_code[code]
            elif latin and latin.lower() in species_by_latin:
                species = species_by_latin[latin.lower()]
            if species is None:
                unmatched += 1
                continue

            with transaction.atomic():
                for col, (category, key) in _NUMERIC_COLUMNS.items():
                    if col not in row:
                        continue
                    num = _parse_float(row.get(col))
                    if num is None:
                        continue
                    before = SpeciesFact.objects.filter(
                        species=species,
                        source=SpeciesFact.SOURCE_AVONET,
                        category=category,
                        key=key,
                    ).first()
                    upsert_fact(
                        species,
                        source=SpeciesFact.SOURCE_AVONET,
                        category=category,
                        key=key,
                        value_text=str(num),
                        value_num=num,
                        license=AVONET_LICENSE,
                        attribution=AVONET_ATTRIBUTION,
                    )
                    if before:
                        updated += 1
                    else:
                        created += 1

                for col, (category, key) in _TEXT_COLUMNS.items():
                    if col not in row:
                        continue
                    text = (row.get(col) or '').strip()
                    if not text or text.upper() == 'NA':
                        continue
                    before = SpeciesFact.objects.filter(
                        species=species,
                        source=SpeciesFact.SOURCE_AVONET,
                        category=category,
                        key=key,
                    ).first()
                    upsert_fact(
                        species,
                        source=SpeciesFact.SOURCE_AVONET,
                        category=category,
                        key=key,
                        value_text=text,
                        license=AVONET_LICENSE,
                        attribution=AVONET_ATTRIBUTION,
                    )
                    if before:
                        updated += 1
                    else:
                        created += 1

            skipped += 0  # keep counters explicit

    stats = {
        'created': created,
        'updated': updated,
        'unmatched': unmatched,
    }
    logger.info('AVONET import from %s: %s', path, stats)
    return stats
