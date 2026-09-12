"""
eBird Status & Trends regional_stats CSV and future Basic Dataset hooks.

Supports ingesting per-species ``*_regional_stats.csv`` files (downloaded via eBird ST) and mapping
their seasonal metrics onto calendar months (coarse but useful).
"""

from __future__ import annotations

import csv
import logging
import os
import re
from collections import defaultdict
from typing import Iterable

from django.conf import settings

from jizz.models import CountrySpecies, Species
from jizz.services.ebird_frequency.constants import SOURCE_ST_PCT_RANK
from jizz.services.ebird_frequency.types import MonthlyFrequencyRow
from jizz.st_subnational_regions import app_code_for_st_region

logger = logging.getLogger(__name__)

_SEASON_TO_MONTHS: dict[str, tuple[int, ...]] = {
    "winter": (12, 1, 2),
    "spring": (3, 4, 5),
    "summer": (6, 7, 8),
    "fall": (9, 10, 11),
    "autumn": (9, 10, 11),
    # ST labels seen in regional_stats.csv
    "breeding": (5, 6, 7),
    "nonbreeding": (12, 1, 2),
    "prebreeding_migration": (3, 4),
    "postbreeding_migration": (8, 9, 10),
    "q1": (1, 2, 3),
    "q2": (4, 5, 6),
    "q3": (7, 8, 9),
    "q4": (10, 11, 12),
}


def _default_st_data_dir() -> str:
    base = str(getattr(settings, "BASE_DIR", "."))
    nested = os.path.join(base, "jizz", "ebird_st_csv")
    flat = os.path.join(base, "ebird_st_csv")
    return nested if os.path.isdir(nested) else flat


def _infer_species_code_from_filename(path: str) -> str | None:
    name = os.path.basename(path).lower()
    m = re.match(r"([a-z0-9]{4,10})_regional_stats\.csv$", name)
    if m:
        return m.group(1)
    m = re.match(r"([a-z0-9]{4,10})_regional_.*\.csv$", name)
    if m:
        return m.group(1)
    return None


def _get_region_col(fieldnames: list[str]) -> str | None:
    for c in ("region_code", "region", "country_code"):
        if c in fieldnames:
            return c
    return None


def _get_pct(row: dict, fieldnames: list[str]) -> float | None:
    for k in (
        "range_occupied_percent",
        "range_occupied_pct",
        "range_occupied",
        "occurrence",
        "frequency_pct",
    ):
        if k in fieldnames and row.get(k) not in (None, ""):
            try:
                v = float(row[k])
                # ST columns like range_occupied_percent are often 0..1 fractions despite the name.
                # Normalize to 0..100 so classify_frequency thresholds make sense.
                if 0.0 <= v <= 1.0:
                    v *= 100.0
                return v
            except (TypeError, ValueError):
                return None
    return None


def fetch_monthly_metrics_st_csv(
    country_code: str,
    year: int,
    months: list[int],
    *,
    csv_path: str | None = None,
    data_dir: str | None = None,
    region_codes: set[str] | None = None,
) -> Iterable[MonthlyFrequencyRow]:
    """
    Import from eBird Status & Trends per-species ``*_regional_stats.csv``.

    If ``csv_path`` is provided, parses just that file. Otherwise scans ``data_dir`` (default:
    BASE_DIR/jizz/ebird_st_csv or BASE_DIR/ebird_st_csv) for ``*_regional_stats.csv``.

    ST regional stats are not “% of checklists”; we store the best-available percent-like metric
    in ``frequency_pct`` and annotate via ``notes`` + ``source``.
    """
    cc = country_code.strip().upper()
    from jizz.country_region_codes import st_region_codes_for_app_country

    region_code_set = set(st_region_codes_for_app_country(cc))
    region_code_set.add(cc)
    if region_codes:
        region_code_set |= {c.strip().upper() for c in region_codes if str(c).strip()}
    month_set = {m for m in months if 1 <= m <= 12}
    if not month_set:
        return

    paths: list[str] = []
    if csv_path:
        paths = [csv_path]
    else:
        base = data_dir or _default_st_data_dir()
        if not os.path.isdir(base):
            logger.warning("st_csv: data dir not found: %s", base)
            return
        for name in os.listdir(base):
            if name.lower().endswith("_regional_stats.csv"):
                paths.append(os.path.join(base, name))
        if not paths:
            logger.warning("st_csv: no *_regional_stats.csv found under %s", base)
            return

    codes = {c for c in (_infer_species_code_from_filename(p) for p in paths) if c}
    if not codes:
        logger.warning("st_csv: could not infer any species code(s) from filenames")
        return
    species_by_code = {s.code.lower(): s for s in Species.objects.filter(code__in=sorted(codes))}
    cs_by_species_id = {
        cs.species_id: cs.id
        for cs in CountrySpecies.objects.filter(country_id=cc, species__code__in=sorted(codes))
    }

    # Collect raw proxy values first, then convert to per-month percentiles so tiers are meaningful.
    # Key: (country_species_id, month) -> list of raw proxy values (0..100)
    raw_vals: dict[tuple[int, int], list[float]] = defaultdict(list)

    for path in sorted(paths):
        sp_code = _infer_species_code_from_filename(path)
        if not sp_code:
            continue
        sp = species_by_code.get(sp_code.lower())
        if not sp:
            continue
        cs_id = cs_by_species_id.get(sp.id)
        if not cs_id:
            continue

        try:
            with open(path, newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                if not fieldnames:
                    continue
                region_col = _get_region_col(fieldnames)
                if not region_col:
                    continue

                for row in reader:
                    rc = (row.get(region_col) or "").strip().upper()
                    mapped = app_code_for_st_region(rc, row.get("region_name"))
                    if rc not in region_code_set and mapped != cc:
                        continue
                    pct = _get_pct(row, fieldnames)
                    if pct is None:
                        continue

                    row_months: tuple[int, ...] = ()
                    if "month" in fieldnames and row.get("month") not in (None, ""):
                        try:
                            row_months = (int(row["month"]),)
                        except (TypeError, ValueError):
                            row_months = ()
                    if not row_months and "season" in fieldnames:
                        season = (row.get("season") or "").strip().lower()
                        row_months = _SEASON_TO_MONTHS.get(season, ())
                    if not row_months and "monthQt" in fieldnames:
                        q = (row.get("monthQt") or "").strip()
                        row_months = _SEASON_TO_MONTHS.get(f"q{q}", ())

                    for m in row_months:
                        if m not in month_set:
                            continue
                        raw_vals[(cs_id, m)].append(float(pct))
        except OSError as e:
            logger.warning("st_csv: could not read %s: %s", path, e)
            continue

    # Compute percentile ranks per month across species.
    per_month_values: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for (cs_id, m), vals in raw_vals.items():
        if not vals:
            continue
        per_month_values[m].append((cs_id, sum(vals) / len(vals)))

    for m, items in per_month_values.items():
        if not items:
            continue
        # Higher proxy value => more common; percentile 0..100.
        items_sorted = sorted(items, key=lambda x: x[1])
        n = len(items_sorted)
        for idx, (cs_id, raw_mean) in enumerate(items_sorted, start=1):
            percentile = 100.0 * idx / n if n else 100.0
            yield MonthlyFrequencyRow(
                country_species_id=cs_id,
                month=m,
                reference_year=year,
                frequency_pct=round(percentile, 4),
                checklist_count=None,
                observation_count=None,
                occupied_subregions=None,
                occurrence_event_count=None,
                source=SOURCE_ST_PCT_RANK,
                notes=(
                    f"ST regional_stats proxy→percentile for tiering; raw_mean={raw_mean:.6f}; "
                    "not checklist-based"
                ),
            )
