"""
eBird API 2.0: species frequency by week/quarter → calendar month.

Uses GET /v2/product/freqlist/{regionCode}/{speciesCode} if eBird ever adds it.
That product currently 404s ("No endpoint"); the importer raises EbirdFreqlistUnavailable
instead of looping every CountrySpecies.
Token: settings.EBIRD_API_TOKEN (or EBIRD_API_KEY via settings alias).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Iterable

import requests
from django.conf import settings

from jizz.models import CountrySpecies
from jizz.services.ebird_frequency.errors import EbirdFreqlistUnavailable
from jizz.services.ebird_frequency.types import MonthlyFrequencyRow

logger = logging.getLogger(__name__)

EBIRD_API_ROOT = 'https://api.ebird.org/v2'
DEFAULT_DELAY_SEC = 0.15


def _missing_freqlist_endpoint(status_code: int, body: str) -> bool:
    if status_code != 404:
        return False
    text = (body or "").lower()
    return "no endpoint" in text or "/product/freqlist" in text


def _token() -> str:
    return (getattr(settings, 'EBIRD_API_TOKEN', None) or '').strip()


def _week_to_month(week: int, year: int) -> int | None:
    """ISO week number → month (1–12), approximate using mid-week."""
    try:
        import datetime as dt

        # Thursday in given ISO week
        d = dt.date.fromisocalendar(year, min(max(week, 1), 53), 4)
        return d.month
    except (ValueError, TypeError):
        return None


def _parse_freqlist_payload(data: object, year: int, months: set[int]) -> dict[int, list[float]]:
    """Map month -> list of frequency values (0–100) from API JSON."""
    by_month: dict[int, list[float]] = defaultdict(list)
    if not isinstance(data, list):
        return by_month

    for row in data:
        if not isinstance(row, dict):
            continue
        pct = None
        for key in ('percentOfChecklists', 'frequency', 'percent', 'pct'):
            v = row.get(key)
            if v is not None:
                try:
                    pct = float(v)
                    if pct <= 1.0:
                        pct *= 100.0
                    break
                except (TypeError, ValueError):
                    pct = None
        if pct is None:
            continue
        mo = None
        if 'month' in row:
            try:
                mo = int(row['month'])
            except (TypeError, ValueError):
                pass
        if mo is None and 'monthQt' in row:
            try:
                q = int(row['monthQt'])
                if q == 1:
                    for m in (1, 2, 3):
                        if m in months:
                            by_month[m].append(pct)
                    continue
                if q == 2:
                    for m in (4, 5, 6):
                        if m in months:
                            by_month[m].append(pct)
                    continue
                if q == 3:
                    for m in (7, 8, 9):
                        if m in months:
                            by_month[m].append(pct)
                    continue
                if q == 4:
                    for m in (10, 11, 12):
                        if m in months:
                            by_month[m].append(pct)
                    continue
            except (TypeError, ValueError):
                pass
        if mo is None and 'week' in row:
            try:
                wk = int(row['week'])
                mo = _week_to_month(wk, year)
            except (TypeError, ValueError):
                pass
        if mo is not None and mo in months:
            by_month[mo].append(pct)

    return by_month


def fetch_freqlist_for_species(
    region_code: str,
    species_code: str,
    *,
    session: requests.Session | None = None,
    year: int | None = None,
) -> list | dict:
    tok = _token()
    if not tok:
        logger.warning('EBIRD_API_TOKEN missing; skipping eBird API')
        return []
    sess = session or requests.Session()
    url = f'{EBIRD_API_ROOT}/product/freqlist/{region_code.strip().upper()}/{species_code.strip().lower()}'
    params: dict = {'fmt': 'json'}
    if year:
        params['year'] = year
    r = sess.get(
        url,
        params=params,
        headers={'X-eBirdApiToken': tok},
        timeout=90,
    )
    if _missing_freqlist_endpoint(r.status_code, r.text):
        raise EbirdFreqlistUnavailable(
            "eBird has no /v2/product/freqlist API "
            f"({r.status_code} for {url})"
        )
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json()


def fetch_monthly_metrics_ebird_api(
    country_code: str,
    year: int,
    months: list[int],
    *,
    delay_sec: float = DEFAULT_DELAY_SEC,
    limit_species: int | None = None,
) -> Iterable[MonthlyFrequencyRow]:
    """
    For each CountrySpecies in country, call freqlist and aggregate rows into requested months.

    Sets frequency_pct to mean of available weekly/quarterly points in that month; checklist_count
    often unavailable from this endpoint (left None). confidence assigned later in classify.
    """
    tok = _token()
    if not tok:
        return

    month_set = set(months)
    qs = CountrySpecies.objects.filter(country_id=country_code.strip().upper()).select_related(
        'species'
    )
    if limit_species is not None:
        qs = qs[: max(0, limit_species)]

    session = requests.Session()
    for cs in qs.iterator(chunk_size=200):
        sp = cs.species
        if not sp or not sp.code:
            continue
        try:
            payload = fetch_freqlist_for_species(
                country_code, sp.code, session=session, year=year
            )
        except requests.RequestException as e:
            logger.debug('freqlist %s %s: %s', country_code, sp.code, e)
            if delay_sec:
                time.sleep(delay_sec)
            continue

        by_m = _parse_freqlist_payload(payload, year, month_set)
        for m in months:
            vals = by_m.get(m)
            if not vals:
                continue
            pct = sum(vals) / len(vals)
            yield MonthlyFrequencyRow(
                country_species_id=cs.id,
                month=m,
                reference_year=year,
                frequency_pct=round(pct, 4),
                checklist_count=None,
                observation_count=None,
                occupied_subregions=None,
                occurrence_event_count=None,
                source='ebird_api_freqlist',
                notes=f'eBird product/freqlist {country_code.upper()}/{sp.code} year={year}',
            )
        if delay_sec:
            time.sleep(delay_sec)
