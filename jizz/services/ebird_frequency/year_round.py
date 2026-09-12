"""Fill year-round CountrySpecies.frequency from monthly checklist data.

Status & Trends has no model for many species (the ``not found`` CSV downloads).
Those birds can still be common on eBird bar charts. Use peak monthly
``frequency_pct`` when ST never wrote ``CountrySpecies.frequency_pct``.
"""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Q

from jizz.models import CountrySpecies, CountrySpeciesFrequency
from jizz.services.ebird_frequency.classify import classify_frequency


def apply_year_round_from_monthly(
    country_id: str,
    *,
    only_without_st: bool = True,
    dry_run: bool = False,
) -> int:
    """
    Set ``CountrySpecies.frequency`` from the peak month in ``CountrySpeciesFrequency``.

    When ``only_without_st`` is true (default), skip rows that already have
    ``frequency_pct`` from Status & Trends scoring.
    """
    cc = (country_id or "").strip().upper()
    if not cc:
        return 0

    cs_qs = CountrySpecies.objects.filter(country_id=cc)
    if only_without_st:
        cs_qs = cs_qs.filter(Q(frequency_pct__isnull=True))
    cs_rows = list(cs_qs.values_list("id", "frequency", "frequency_pct"))
    if not cs_rows:
        return 0
    cs_ids = [cs_id for cs_id, _, _ in cs_rows]
    by_id = {cs_id: (freq, pct) for cs_id, freq, pct in cs_rows}

    grouped: dict[int, list[tuple[int, float | None]]] = defaultdict(list)
    for cs_id, year, pct in CountrySpeciesFrequency.objects.filter(
        country_species_id__in=cs_ids,
    ).values_list("country_species_id", "reference_year", "frequency_pct"):
        grouped[cs_id].append((int(year or 0), pct))

    updates: list[CountrySpecies] = []
    for cs in CountrySpecies.objects.filter(id__in=cs_ids):
        rows = grouped.get(cs.id)
        if not rows:
            continue
        latest = max(year for year, _ in rows)
        pcts = [pct for year, pct in rows if year == latest and pct is not None]
        if not pcts:
            continue
        peak = max(pcts)
        tier, _conf = classify_frequency(peak)
        if not tier:
            continue
        old_freq, old_pct = by_id[cs.id]
        if old_freq == tier and old_pct == peak:
            continue
        cs.frequency = tier
        cs.frequency_pct = peak
        updates.append(cs)

    if dry_run or not updates:
        return len(updates)
    CountrySpecies.objects.bulk_update(updates, ["frequency", "frequency_pct"])
    return len(updates)
