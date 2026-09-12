"""
eBird region bar-chart / histogram frequency (all species × 48 weeks).

One HTTP request per region. Weekly values are averaged into calendar months.
Not an official documented API; the web histogram download is the source eBird
documents for bulk frequency. Tests mock the HTTP call.
"""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from typing import Iterable
from urllib.parse import urlencode

import requests
from django.conf import settings

from jizz.models import CountrySpecies, Species
from jizz.services.ebird_frequency.constants import SOURCE_BARCHART
from jizz.services.ebird_frequency.errors import BarchartLoginRequired
from jizz.services.ebird_frequency.types import MonthlyFrequencyRow

logger = logging.getLogger(__name__)

BARCHART_URL = "https://ebird.org/barchartData"
BARCHART_PAGE_URL = "https://ebird.org/barchart"
DEFAULT_BYR_SPAN = 10


def barchart_query_params(region_code: str, year: int, *, include_fmt: bool = True) -> dict[str, int | str]:
    params: dict[str, int | str] = {
        "r": region_code.strip().upper(),
        "bmo": 1,
        "emo": 12,
        "byr": max(1900, year - DEFAULT_BYR_SPAN + 1),
        "eyr": year,
    }
    if include_fmt:
        params["fmt"] = "tsv"
    return params


def barchart_page_url(region_code: str, year: int) -> str:
    return f"{BARCHART_PAGE_URL}?{urlencode(barchart_query_params(region_code, year, include_fmt=False))}"


def barchart_data_url(region_code: str, year: int) -> str:
    return f"{BARCHART_URL}?{urlencode(barchart_query_params(region_code, year))}"


def looks_like_login_html(text: str) -> bool:
    head = (text or "")[:8000].lstrip().lower()
    if not (head.startswith("<!doctype") or head.startswith("<html") or "<html" in head[:200]):
        return False
    return any(token in head for token in ("cassso", "login", "sign in", "password"))


def week_index_to_month(week: int) -> int:
    """Map eBird's 48 four-week bins (1–48) onto calendar months 1–12."""
    if week < 1:
        return 1
    return min(12, max(1, (week - 1) // 4 + 1))


def _to_pct(value: str) -> float | None:
    raw = (value or "").strip()
    if not raw or raw in {".", "-", "NA", "na"}:
        return None
    try:
        num = float(raw)
    except ValueError:
        return None
    if 0.0 <= num <= 1.0:
        return num * 100.0
    return num


def parse_barchart_tsv(text: str) -> list[tuple[str, str, list[float | None]]]:
    """
    Return (common_name, scientific_name, 48 weekly pct-or-None) rows.

    Ignores sample-size / header rows. Accepts tab-separated histogram downloads.
    """
    rows: list[tuple[str, str, list[float | None]]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        lower = line.lower()
        if lower.startswith("sample size") or lower.startswith("frequency"):
            continue
        parts = line.split("\t")
        if len(parts) < 10:
            parts = [p for p in next(csv.reader(io.StringIO(line), delimiter="\t"))]
        if len(parts) < 10:
            continue
        # Skip the sample-size numeric row if it has no species name.
        first = parts[0].strip()
        if first.lower() in {"sample size", "samplesize"}:
            continue
        sci_idx = 1
        common = first
        scientific = parts[sci_idx].strip() if len(parts) > 1 else ""
        # Some dumps put a 6-letter eBird code first.
        numeric_start = 2
        if len(first) <= 8 and first.isalnum() and first.isascii() and " " not in first:
            # code, common, scientific, weeks...
            if len(parts) > 50:
                common = parts[1].strip()
                scientific = parts[2].strip()
                numeric_start = 3
        week_vals: list[float | None] = []
        for cell in parts[numeric_start:]:
            week_vals.append(_to_pct(cell))
            if len(week_vals) >= 48:
                break
        if len(week_vals) < 12:
            continue
        if not any(v is not None for v in week_vals):
            continue
        while len(week_vals) < 48:
            week_vals.append(None)
        rows.append((common, scientific, week_vals[:48]))
    return rows


def weekly_to_monthly(week_vals: list[float | None]) -> dict[int, float]:
    buckets: dict[int, list[float]] = defaultdict(list)
    for i, val in enumerate(week_vals, start=1):
        if val is None:
            continue
        buckets[week_index_to_month(i)].append(val)
    return {month: sum(vals) / len(vals) for month, vals in buckets.items() if vals}


def _match_species(
    common: str,
    scientific: str,
    by_latin: dict[str, Species],
    by_name: dict[str, Species],
    by_code: dict[str, Species],
) -> Species | None:
    sci = scientific.strip().lower()
    if sci and sci in by_latin:
        return by_latin[sci]
    code = common.strip().lower()
    if code and code in by_code:
        return by_code[code]
    name = common.strip().lower()
    if name and name in by_name:
        return by_name[name]
    return None


def fetch_barchart_tsv(
    region_code: str,
    *,
    year: int,
    session: requests.Session | None = None,
) -> str:
    cc = region_code.strip().upper()
    sess = session or requests.Session()
    headers = {
        "User-Agent": "birdr-jizz/1.0 (eBird bar-chart frequency import)",
        "Accept": "text/tab-separated-values, text/plain, */*",
    }
    token = (getattr(settings, "EBIRD_API_TOKEN", None) or "").strip()
    if token:
        headers["X-eBirdApiToken"] = token
    response = sess.get(
        BARCHART_URL,
        params=barchart_query_params(cc, year),
        headers=headers,
        timeout=120,
        allow_redirects=True,
    )
    response.raise_for_status()
    if looks_like_login_html(response.text):
        raise BarchartLoginRequired(
            cc,
            year,
            page_url=barchart_page_url(cc, year),
            data_url=barchart_data_url(cc, year),
        )
    return response.text


def fetch_monthly_metrics_barchart(
    country_code: str,
    year: int,
    months: list[int],
    *,
    tsv_text: str | None = None,
) -> Iterable[MonthlyFrequencyRow]:
    """Yield monthly rows for CountrySpecies in ``country_code`` from a bar chart."""
    cc = country_code.strip().upper()
    month_set = {m for m in months if 1 <= m <= 12}
    if not month_set:
        return

    text = tsv_text
    if text is None:
        try:
            text = fetch_barchart_tsv(cc, year=year)
        except requests.RequestException as exc:
            logger.warning("barchart fetch failed for %s: %s", cc, exc)
            raise
    if looks_like_login_html(text or ""):
        raise BarchartLoginRequired(
            cc,
            year,
            page_url=barchart_page_url(cc, year),
            data_url=barchart_data_url(cc, year),
        )
    parsed = parse_barchart_tsv(text)
    if not parsed:
        logger.warning("barchart: no species rows parsed for %s", cc)
        return

    species_by_latin = {
        (s.name_latin or "").strip().lower(): s
        for s in Species.objects.exclude(name_latin="").exclude(name_latin__isnull=True)
        if (s.name_latin or "").strip()
    }
    species_by_name = {
        (s.name or "").strip().lower(): s
        for s in Species.objects.exclude(name="").exclude(name__isnull=True)
        if (s.name or "").strip()
    }
    species_by_code = {
        (s.code or "").strip().lower(): s
        for s in Species.objects.exclude(code="").exclude(code__isnull=True)
        if (s.code or "").strip()
    }
    cs_by_species_id = {
        cs.species_id: cs.id
        for cs in CountrySpecies.objects.filter(country_id=cc).only("id", "species_id")
    }

    for common, scientific, weeks in parsed:
        species = _match_species(
            common, scientific, species_by_latin, species_by_name, species_by_code
        )
        if species is None:
            continue
        cs_id = cs_by_species_id.get(species.id)
        if not cs_id:
            continue
        monthly = weekly_to_monthly(weeks)
        for month, pct in monthly.items():
            if month not in month_set:
                continue
            yield MonthlyFrequencyRow(
                country_species_id=cs_id,
                month=month,
                reference_year=year,
                frequency_pct=round(pct, 4),
                checklist_count=None,
                source=SOURCE_BARCHART,
                notes=f"eBird barchart {cc} year={year} month={month}",
            )
