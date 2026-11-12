"""GBIF facet queries on the eBird dataset (no h3 dependency)."""

from __future__ import annotations

import time
from typing import Any

import httpx



EBIRD_GBIF_DATASET_KEY = '4fa7b334-ce0d-4e88-aaae-2e0c138d049e'


def fetch_region_month_counts(
    country: str,
    states: list[str] | None = None,
    *,
    api_base: str = 'https://api.gbif.org/v1',
    timeout: float = 60.0,
    dataset_key: str = EBIRD_GBIF_DATASET_KEY,
) -> tuple[dict[int, dict[str, int]], dict[int, int]]:
    """Per month: ``{month: {scientificName: records}}`` and ``{month: total_records}``.

    Uses GBIF facets on the eBird dataset (no key, CC BY 4.0). ``states`` are GBIF
    ``stateProvince`` values (repeat-param OR); omit for the whole country.
    Names come back with authorship; callers reduce them to the binomial.
    """
    base = api_base.rstrip('/')
    url = f'{base}/occurrence/search'
    species_by_month: dict[int, dict[str, int]] = {}
    totals: dict[int, int] = {}
    with httpx.Client(
        timeout=httpx.Timeout(timeout),
        headers={'User-Agent': 'jizz-django/GBIF-region-months'},
    ) as client:
        for month in range(1, 13):
            params: list[tuple[str, Any]] = [
                ('datasetKey', dataset_key),
                ('country', country.upper()),
                ('month', month),
                ('limit', 0),
                ('facet', 'scientificName'),
                ('facetLimit', 5000),
            ]
            params += [('stateProvince', s) for s in (states or [])]
            for attempt in range(5):
                r = client.get(url, params=params)
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                break
            data = r.json()
            totals[month] = int(data.get('count') or 0)
            counts = (data.get('facets') or [{}])[0].get('counts') or []
            species_by_month[month] = {c['name']: int(c['count']) for c in counts}
    return species_by_month, totals
