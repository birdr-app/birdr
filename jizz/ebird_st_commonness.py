"""
eBird Status & Trends → commonness scoring helpers.

Used by ``manage.py ebird_st_commonness``. Downloads regional/species_stats CSVs from
``st-download.ebird.org`` and computes per-country scores from regional_stats.
"""
from __future__ import annotations

import glob
import io
import math
import os
import re
import sqlite3
import sys
import zipfile
from typing import Any, List, Optional, Tuple

import pandas as pd
import requests

from jizz.country_region_codes import (
    expand_region_codes,
    resolve_app_country_for_st_region,
)
from jizz.playable_regions import AGGREGATE_MEMBERS, scoring_region_codes
from jizz.st_subnational_regions import (
    ST_PLAYABLE_REGION_TYPES,
    app_code_for_st_region,
)

ST_DOWNLOAD_BASE = "https://st-download.ebird.org/v1"
SCIENCE_ST_DOWNLOADS_BASE = "https://science.ebird.org"

# Fallback when the science downloads page does not expose model years.
_ST_CATALOG_YEARS = (2024, 2023, 2022, 2021)

_ST_HTTP_HEADERS = {
    "User-Agent": (
        "jizz-ebird-st-commonness/1.0 (+https://github.com/; "
        "eBird Status & Trends regional_stats importer)"
    ),
}

_RE_SCIENCE_STATUS_MODEL_YEAR = re.compile(r"statusModelYear:(\d{4})")
_RE_SCIENCE_TREND_END_YEAR = re.compile(r"trendEndYear:(\d{4})")

# Peak-abundance tier order: most common → rarest (for caps / one-step upgrades).
_FREQUENCY_ORDER = (
    "abundant",
    "common",
    "fairly_common",
    "uncommon",
    "rare",
    "very_rare",
)

_COMMONNESS_BASIS = "peak_abundance_with_occupancy_days_modifiers"

# log10(1 + 10) — denominator for normalized abundance score in [0, 1].
_SCORE_LOG_DENOM = math.log10(11.0)


def _repo_root() -> str:
    """Project root (parent of the ``jizz`` package)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalize_st_species_code(species_code: str) -> str:
    """eBird S&T URLs expect lowercase 6-letter codes (e.g. eurrob1, not EURROB1)."""
    return species_code.strip().lower()


def species_codes_for_country(country_code: str) -> List[str]:
    """All distinct eBird species codes linked to the country via CountrySpecies."""
    from jizz.models import CountrySpecies

    cc = country_code.strip().upper()
    qs = CountrySpecies.objects.filter(country_id=cc).values_list("species__code", flat=True)
    return sorted({normalize_st_species_code(c) for c in qs if c})


def species_codes_for_selected_countries(country_codes: List[str]) -> List[str]:
    """Distinct eBird species codes on any CountrySpecies row for the given countries."""
    from jizz.models import Species

    codes = sorted({c.strip().upper() for c in country_codes if c and str(c).strip()})
    if not codes:
        return []
    qs = Species.objects.filter(countryspecies__country_id__in=codes).values_list(
        "code", flat=True
    )
    return sorted({normalize_st_species_code(c) for c in qs if c})


def species_countries_map(country_codes: List[str]) -> dict:
    """
    Map each eBird species code to sorted country codes where it appears in CountrySpecies.

    Used to download each regional_stats CSV once and parse every target country from it.
    """
    from collections import defaultdict

    from jizz.models import CountrySpecies

    codes = sorted({c.strip().upper() for c in country_codes if c and str(c).strip()})
    if not codes:
        return {}
    out: dict = defaultdict(list)
    qs = CountrySpecies.objects.filter(country_id__in=codes).values_list(
        "species__code", "country_id"
    )
    for sp_code, cc in qs:
        if sp_code:
            out[normalize_st_species_code(sp_code)].append(str(cc).strip().upper())
    return {sp: sorted(set(ccs)) for sp, ccs in out.items()}


def st_list_objects_url(species_code: str, version_year: int) -> str:
    return f"{ST_DOWNLOAD_BASE}/list-obj/{version_year}/{normalize_st_species_code(species_code)}"


def st_fetch_url() -> str:
    return f"{ST_DOWNLOAD_BASE}/fetch"


def _coerce_list_obj_payload(data: object) -> Optional[List[Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("paths", "objects", "data", "files"):
            inner = data.get(key)
            if isinstance(inner, list):
                return inner
    return None


def _normalize_list_obj_paths(paths: object) -> List[str]:
    """Coerce list-obj entries to fetchable object key strings."""
    if not isinstance(paths, list):
        return []
    out: List[str] = []
    for item in paths:
        if isinstance(item, str):
            p = item.strip()
            if p:
                out.append(p.replace("\\", "/"))
            continue
        if isinstance(item, dict):
            for key in ("objKey", "path", "key", "name", "Key"):
                raw = item.get(key)
                if isinstance(raw, str) and raw.strip():
                    out.append(raw.strip().replace("\\", "/"))
                    break
    return out


def science_downloads_page_url(species_code: str) -> str:
    """Public downloads page (same links the eBird Science UI builds)."""
    sp = normalize_st_species_code(species_code)
    return f"{SCIENCE_ST_DOWNLOADS_BASE}/en/status-and-trends/species/{sp}/downloads"


def parse_science_download_years(page_html: str) -> List[int]:
    """
    Read ``statusModelYear`` / ``trendEndYear`` from the SSR ``__NUXT__`` payload on the
    science downloads page (see StVizDownloadLink in the Science web app).
    """
    years: List[int] = []
    # trendEndYear usually matches the on-disk S&T vintage; statusModelYear can be newer.
    for pattern in (_RE_SCIENCE_TREND_END_YEAR, _RE_SCIENCE_STATUS_MODEL_YEAR):
        for match in pattern.finditer(page_html):
            year = int(match.group(1))
            if year not in years:
                years.append(year)
    return years


def fetch_science_download_years(
    session: requests.Session,
    species_code: str,
    *,
    cache: Optional[dict] = None,
) -> List[int]:
    """Fetch the science downloads page and return catalog years for this species."""
    sp = normalize_st_species_code(species_code)
    if cache is not None and sp in cache:
        return list(cache[sp])
    years: List[int] = []
    url = science_downloads_page_url(sp)
    try:
        r = session.get(url, headers=_ST_HTTP_HEADERS, timeout=60)
        r.raise_for_status()
        years = parse_science_download_years(r.text)
    except requests.RequestException as exc:
        print(
            f"  [note] {sp}: could not read science downloads page ({exc})",
            file=sys.stderr,
        )
    if cache is not None:
        cache[sp] = list(years)
    return years


def _years_to_try(version_year: int, science_years: Optional[List[int]] = None) -> List[int]:
    """Science page years first, then CLI year, then static fallbacks."""
    years: List[int] = []
    if science_years:
        for y in science_years:
            yi = int(y)
            if yi not in years:
                years.append(yi)
    primary = int(version_year)
    if primary not in years:
        years.append(primary)
    for y in sorted(_ST_CATALOG_YEARS):
        if y not in years:
            years.append(y)
    return years


def _constructed_regional_obj_keys(species_code: str, version_year: int) -> List[str]:
    """
    Same object keys as the eBird Science downloads page (web_download ZIP, then flat CSV).
    """
    sp = normalize_st_species_code(species_code)
    y = str(int(version_year))
    return [
        f"{y}/{sp}/web_download/{sp}_regional_{y}.zip",
        f"{y}/{sp}/regional_stats.csv",
    ]


def _regional_obj_key_candidates(
    species_code: str,
    version_year: int,
    paths: Optional[List[Any]],
) -> List[str]:
    """Ordered unique object keys to try for regional_stats (listing + constructed)."""
    seen: set = set()
    candidates: List[str] = []

    def add(key: Optional[str]) -> None:
        if key and key not in seen:
            seen.add(key)
            candidates.append(key)

    norm_paths = _normalize_list_obj_paths(paths) if paths else []
    add(_select_regional_obj_key(norm_paths, species_code, version_year))
    for key in _constructed_regional_obj_keys(species_code, version_year):
        add(key)
    return candidates


def list_st_objects(
    session: requests.Session,
    species_code: str,
    version_year: int,
    access_key: str,
) -> Optional[List[Any]]:
    """GET /list-obj/{year}/{species} (single attempt)."""
    sp = normalize_st_species_code(species_code)
    url = st_list_objects_url(sp, version_year)
    try:
        r = session.get(url, params={"key": access_key}, timeout=60)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("status") in (404, 500):
            return []
        payload = _coerce_list_obj_payload(data)
        if isinstance(payload, list):
            return _normalize_list_obj_paths(payload)
        print(
            f"  [skip] {sp}: list-obj did not return a path list: {str(data)[:240]}",
            file=sys.stderr,
        )
    except (requests.RequestException, ValueError, TypeError) as e:
        print(f"  [skip] {sp}: list-obj failed: {e}", file=sys.stderr)
    return None


def _select_regional_obj_key(
    paths: object, species_code: str, version_year: int
) -> Optional[str]:
    str_paths = _normalize_list_obj_paths(paths)
    if not str_paths:
        return None
    for p in str_paths:
        if p.endswith("regional_stats.csv"):
            return p

    sp = species_code.strip().lower()
    y = str(int(version_year))
    suffix = f"{sp}_regional_{y}.zip"
    for p in str_paths:
        if p.lower().endswith(suffix):
            return p

    for p in str_paths:
        pl = p.replace("\\", "/").lower()
        if "web_download" not in pl:
            continue
        if not pl.endswith(".zip"):
            continue
        if sp not in pl:
            continue
        if "regional" in pl:
            return p

    for p in str_paths:
        pl = p.lower()
        if pl.endswith(".zip") and "ebird-trends_regional" in pl:
            return p

    for p in str_paths:
        pl = p.lower()
        if pl.endswith(".zip") and "regional" in pl:
            return p

    return None


def _select_species_stats_obj_key(
    paths: object, species_code: str, version_year: int
) -> Optional[str]:
    str_paths = _normalize_list_obj_paths(paths)
    if not str_paths:
        return None
    for p in str_paths:
        if p.endswith("species_stats.csv"):
            return p

    sp = species_code.strip().lower()
    y = str(int(version_year))
    suffix = f"{sp}_species_{y}.zip"
    for p in str_paths:
        if p.lower().endswith(suffix):
            return p

    for p in str_paths:
        pl = p.replace("\\", "/").lower()
        if "web_download" not in pl:
            continue
        if not pl.endswith(".zip"):
            continue
        if sp not in pl:
            continue
        if "species" in pl and "regional" not in pl:
            return p

    for p in str_paths:
        pl = p.lower()
        if pl.endswith(".zip") and "ebird-trends" in pl and "species" in pl:
            return p

    for p in str_paths:
        pl = p.lower()
        if pl.endswith(".zip") and "species" in pl and "regional" not in pl:
            return p

    return None


def _csv_text_from_fetch_response(r: requests.Response, *, kind: str = "regional") -> str:
    raw = r.content
    ct = (r.headers.get("Content-Type") or "").lower()
    is_zip = "zip" in ct or (len(raw) >= 4 and raw[:4] == b"PK\x03\x04")
    if not is_zip:
        r.encoding = r.encoding or getattr(r, "apparent_encoding", None) or "utf-8"
        return r.text

    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("ZIP contains no .csv file")

        def sort_key_regional(n: str) -> tuple:
            nl = n.lower()
            return (
                0 if nl.endswith("regional_stats.csv") else 1,
                0 if "regional" in nl else 1,
                len(n),
            )

        def sort_key_species(n: str) -> tuple:
            nl = n.lower()
            return (
                0 if nl.endswith("species_stats.csv") else 1,
                0 if "species" in nl and "regional" not in nl else 1,
                len(n),
            )

        names.sort(key=sort_key_species if kind == "species" else sort_key_regional)
        return zf.read(names[0]).decode("utf-8", errors="replace")


def ebird_st_access_key_from_local_py() -> str:
    path = os.path.join(_repo_root(), "jizz", "settings", "local.py")
    if not os.path.isfile(path):
        return ""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return ""
    m = re.search(
        r"EBIRD_ST_ACCESS_KEY\s*=\s*os\.environ\.get\s*\(\s*['\"]EBIRD_ST_ACCESS_KEY['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*\)",
        text,
    )
    if m:
        return m.group(1).strip()
    m = re.search(r"EBIRD_ST_ACCESS_KEY\s*=\s*['\"]([^'\"]+)['\"]", text)
    return m.group(1).strip() if m else ""


def app_country_for_st_region(region_code: str) -> Optional[str]:
    """Map an eBird ST country ``region_code`` to app ``Country.pk`` (e.g. USA → US)."""
    return resolve_app_country_for_st_region(region_code)


def countries_in_regional_stats(
    df: pd.DataFrame,
    selected_countries: Optional[List[str]] = None,
) -> List[str]:
    """
    App country codes that have country-level rows in a regional_stats frame.

    When ``selected_countries`` is set, only returns codes in that list (the run scope).
    """
    if df is None or df.empty or "region_code" not in df.columns:
        return []

    sub = df.copy()
    if "region_type" in sub.columns:
        rt = sub["region_type"].astype(str).str.strip().str.lower()
        sub = sub[rt.isin(ST_PLAYABLE_REGION_TYPES)]
    if sub.empty:
        return []

    selected: Optional[set] = None
    if selected_countries is not None:
        selected = {c.strip().upper() for c in selected_countries if c}

    out: List[str] = []
    seen: set = set()
    names = sub["region_name"] if "region_name" in sub.columns else None
    present_app: set[str] = set()
    codes_list = list(sub["region_code"].astype(str).str.strip().str.upper())
    for i, raw in enumerate(codes_list):
        if not raw:
            continue
        rn = None
        if names is not None:
            val = names.iloc[i]
            if not (isinstance(val, float) and pd.isna(val)):
                rn = str(val)
        app_cc = app_code_for_st_region(raw, rn)
        if not app_cc:
            continue
        present_app.add(app_cc)
        if app_cc in seen:
            continue
        if selected is not None and app_cc not in selected:
            continue
        seen.add(app_cc)
        out.append(app_cc)

    for agg_code, members in AGGREGATE_MEMBERS.items():
        if agg_code in seen:
            continue
        if selected is not None and agg_code not in selected:
            continue
        if any(member in present_app for member in members):
            seen.add(agg_code)
            out.append(agg_code)
    return sorted(out)


def _fetch_regional_csv_text(
    session: requests.Session,
    obj_key: str,
    access_key: str,
) -> str:
    r = session.get(
        st_fetch_url(),
        params={"objKey": obj_key, "key": access_key},
        timeout=120,
    )
    r.raise_for_status()
    return _csv_text_from_fetch_response(r, kind="regional")


def download_regional_stats(
    species_code: str,
    access_key: str,
    version_year: int,
    data_dir: str,
    use_cache: bool,
    session: requests.Session,
    paths: Optional[List[Any]] = None,
    *,
    science_year_cache: Optional[dict] = None,
) -> Optional[pd.DataFrame]:
    species_code = normalize_st_species_code(species_code)
    os.makedirs(data_dir, exist_ok=True)
    cache_path = os.path.join(data_dir, f"{species_code}_regional_stats.csv")

    if use_cache and os.path.isfile(cache_path):
        try:
            return pd.read_csv(cache_path)
        except Exception:
            pass

    if not access_key:
        print(f"  [skip] {species_code}: missing cache and no access key", file=sys.stderr)
        return None

    text: Optional[str] = None
    used_year: Optional[int] = None

    if paths is not None:
        years = [version_year]
    else:
        science_years = fetch_science_download_years(
            session, species_code, cache=science_year_cache
        )
        if science_years:
            print(
                f"  [science] {species_code}: catalog year(s) "
                f"{', '.join(str(y) for y in science_years)}",
                file=sys.stderr,
            )
        years = _years_to_try(version_year, science_years)
    for year in years:
        year_paths = paths
        if year_paths is None:
            year_paths = list_st_objects(session, species_code, year, access_key)
        candidates = _regional_obj_key_candidates(species_code, year, year_paths)
        if paths is not None and not candidates:
            break

        for obj_key in candidates:
            try:
                text = _fetch_regional_csv_text(session, obj_key, access_key)
                used_year = year
                break
            except (requests.RequestException, ValueError):
                text = None
            if text is not None:
                break
        if text is not None:
            break
        paths = None

    if text is None:
        print(
            f"  [skip] {species_code}: could not fetch regional_stats "
            f"(tried years {', '.join(str(y) for y in years)})",
            file=sys.stderr,
        )
        return None

    if used_year is not None and used_year != version_year:
        print(
            f"  [note] {species_code}: using S&T year {used_year} "
            f"(requested {version_year})",
            file=sys.stderr,
        )

    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)

    try:
        return pd.read_csv(cache_path)
    except Exception as e:
        print(f"  [skip] {species_code}: parse CSV failed: {e}", file=sys.stderr)
        return None


def ensure_species_stats_csv(
    species_code: str,
    access_key: str,
    version_year: int,
    data_dir: str,
    use_cache: bool,
    session: requests.Session,
    paths: Optional[List[Any]],
) -> bool:
    species_code = normalize_st_species_code(species_code)
    os.makedirs(data_dir, exist_ok=True)
    cache_path = os.path.join(data_dir, f"{species_code}_species_stats.csv")

    if use_cache and os.path.isfile(cache_path):
        return True

    if not access_key:
        return False

    if not paths:
        paths = list_st_objects(session, species_code, version_year, access_key)
    if not paths:
        return False

    obj_key = _select_species_stats_obj_key(paths, species_code, version_year)
    if not obj_key:
        return False

    try:
        r = session.get(
            st_fetch_url(),
            params={"objKey": obj_key, "key": access_key},
            timeout=120,
        )
        r.raise_for_status()
        text = _csv_text_from_fetch_response(r, kind="species")
    except (requests.RequestException, ValueError) as e:
        print(f"  [skip] {species_code}: species_stats fetch failed: {e}", file=sys.stderr)
        return False

    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"  saved → {cache_path}", flush=True)
    return True


def _column_mean(sub: pd.DataFrame, col: str) -> Optional[float]:
    if col not in sub.columns:
        return None
    s = pd.to_numeric(sub[col], errors="coerce")
    if s.isna().all():
        return None
    return float(s.mean())


def _column_max(sub: pd.DataFrame, col: str) -> Optional[float]:
    if col not in sub.columns:
        return None
    s = pd.to_numeric(sub[col], errors="coerce")
    if s.isna().all():
        return None
    return float(s.max())


def _range_occupied_column(sub: pd.DataFrame) -> Optional[str]:
    for name in ("range_occupied_percent", "range_percent_occupied"):
        if name in sub.columns:
            return name
    return None


def _normalize_range_occupied_fraction(raw: Optional[float]) -> Optional[float]:
    """Return ``range_occupied_percent`` as a 0–1 fraction."""
    if raw is None:
        return None
    v = float(raw)
    if v > 1.5:
        return min(v, 100.0) / 100.0
    return v


def _abundance_score_unit(abundance_mean_max: float) -> float:
    """Normalized abundance score in [0, 1] for ``frequency_pct``."""
    a = max(float(abundance_mean_max), 0.0)
    return min(1.0, math.log10(1.0 + a) / _SCORE_LOG_DENOM)


def _tier_index(tier: str) -> int:
    return _FREQUENCY_ORDER.index(tier)


def _cap_tier(tier: str, ceiling: str) -> str:
    """Cap ``tier`` so it is not more common than ``ceiling``."""
    ti = _tier_index(tier)
    ci = _tier_index(ceiling)
    if ti < ci:
        return ceiling
    return tier


def _upgrade_tier_one_step(tier: str) -> str:
    i = _tier_index(tier)
    if i > 0:
        return _FREQUENCY_ORDER[i - 1]
    return tier


def _base_tier_from_abundance(abundance_mean_max: float) -> str:
    a = float(abundance_mean_max)
    if a > 5.0:
        return "abundant"
    if a > 1.0:
        return "common"
    if a > 0.2:
        return "fairly_common"
    if a > 0.05:
        return "uncommon"
    if a > 0.01:
        return "rare"
    return "very_rare"


def classify_from_abundance(
    abundance_mean_max: float,
    range_occupied_percent: Optional[float] = None,
    range_days_occupation: Optional[float] = None,
) -> Tuple[str, Optional[str]]:
    """
    Classify local commonness from peak ``abundance_mean`` with occupancy/day modifiers.

    Returns ``(frequency_tier, rarity_cap)`` where ``rarity_cap`` is set when a modifier
    forced a ceiling (for debug output).
    """
    tier = _base_tier_from_abundance(abundance_mean_max)
    rarity_cap: Optional[str] = None
    rop = _normalize_range_occupied_fraction(range_occupied_percent)
    rdo = float(range_days_occupation) if range_days_occupation is not None else None
    extremely_high = float(abundance_mean_max) > 5.0

    if rdo is not None:
        if rdo < 14:
            rarity_cap = rarity_cap or "very_rare"
            tier = _cap_tier(tier, "very_rare")
        elif rdo < 30 and not extremely_high:
            rarity_cap = rarity_cap or "rare"
            tier = _cap_tier(tier, "rare")

    if rop is not None:
        if rop < 0.01:
            rarity_cap = rarity_cap or "very_rare"
            tier = _cap_tier(tier, "very_rare")
        elif rop < 0.05:
            rarity_cap = rarity_cap or "rare"
            tier = _cap_tier(tier, "rare")

    if rop is not None and rdo is not None and rop > 0.5 and rdo >= 180:
        upgraded = _upgrade_tier_one_step(tier)
        if not extremely_high and _tier_index(upgraded) < _tier_index("common"):
            upgraded = "common"
        tier = upgraded

    return tier, rarity_cap


def parse_species_commonness(
    df: pd.DataFrame,
    country_code: str,
) -> Optional[dict]:
    if df is None or df.empty:
        return None

    codes = {c.upper() for c in scoring_region_codes(country_code)}
    rc = df["region_code"].astype(str).str.strip().str.upper()
    names = df["region_name"] if "region_name" in df.columns else None
    mapped = []
    for i, raw in enumerate(rc):
        rn = None
        if names is not None:
            val = names.iloc[i]
            if not (isinstance(val, float) and pd.isna(val)):
                rn = str(val)
        mapped.append(app_code_for_st_region(raw, rn) or "")
    mask = rc.isin(codes) | pd.Series(mapped, index=df.index).isin(codes)
    if "region_type" in df.columns:
        rt = df["region_type"].astype(str).str.strip().str.lower()
        mask &= rt.isin(ST_PLAYABLE_REGION_TYPES)
    sub = df[mask].copy()
    if sub.empty:
        return None

    if "abundance_mean" not in sub.columns:
        return None

    sub["_am"] = pd.to_numeric(sub["abundance_mean"], errors="coerce")
    sub = sub[sub["_am"].notna()]
    if sub.empty:
        return None

    peak_idx = sub["_am"].idxmax()
    peak_row = sub.loc[peak_idx]
    abundance_mean_max = float(peak_row["_am"])
    abundance_mean_avg = float(sub["_am"].mean())

    peak_season: Optional[str] = None
    if "season" in sub.columns:
        raw_season = peak_row.get("season")
        if pd.notna(raw_season):
            peak_season = str(raw_season).strip() or None

    rop_col = _range_occupied_column(sub)
    range_occupied_percent: Optional[float] = None
    if rop_col is not None:
        peak_rop = pd.to_numeric(peak_row.get(rop_col), errors="coerce")
        max_rop = _column_max(sub, rop_col)
        if pd.notna(peak_rop):
            range_occupied_percent = float(peak_rop)
        else:
            range_occupied_percent = max_rop

    range_days_occupation = _column_max(sub, "range_days_occupation")
    range_total_percent_max = _column_max(sub, "range_total_percent")
    total_pop_percent_max = _column_max(sub, "total_pop_percent")

    score = _abundance_score_unit(abundance_mean_max)
    freq_pct = score * 100.0
    abundance = math.log1p(max(abundance_mean_max, 0.0))

    occ_debug_pct = (
        occupancy_raw_to_pct(float(range_occupied_percent))
        if range_occupied_percent is not None
        else None
    )

    _, rarity_cap = classify_from_abundance(
        abundance_mean_max,
        range_occupied_percent,
        range_days_occupation,
    )

    return {
        "abundance": abundance,
        "abundance_mean_avg": abundance_mean_avg,
        "abundance_mean_max": abundance_mean_max,
        "peak_season": peak_season,
        "range_occupied_percent": range_occupied_percent,
        "range_total_percent": range_total_percent_max,
        "total_pop_percent": total_pop_percent_max,
        "range_days_occupation": range_days_occupation,
        "occupancy": occ_debug_pct,
        "score": score,
        "rarity_cap": rarity_cap,
        "frequency_pct": freq_pct,
        "commonness_basis": _COMMONNESS_BASIS,
        "debug_range_occupied_max": range_occupied_percent,
    }


def _classify_from_score_legacy(score: float) -> str:
    """Legacy score tiers (pre peak-abundance scoring)."""
    if score >= 0.72:
        return "abundant"
    if score >= 0.55:
        return "very_common"
    if score >= 0.38:
        return "common"
    if score >= 0.22:
        return "uncommon"
    if score >= 0.12:
        return "scarce"
    if score >= 0.05:
        return "rare"
    return "extremely_rare"


def classify(score: float, rarity_cap: Optional[str] = None) -> str:
    """
    Map a normalized score in [0, 1] to a frequency tier (legacy score-based path).

    Prefer ``classify_from_abundance`` for new peak-abundance scoring. If ``rarity_cap`` is
    set (from occupancy/day modifiers), it caps the label to that tier or rarer.
    """
    legacy_order = (
        "abundant",
        "very_common",
        "common",
        "uncommon",
        "scarce",
        "rare",
        "extremely_rare",
    )
    label = _classify_from_score_legacy(score)
    if rarity_cap in ("very_rare", "extremely_rare"):
        return "very_rare"
    if rarity_cap == "rare":
        rare_idx = legacy_order.index("rare")
        label_idx = legacy_order.index(label) if label in legacy_order else len(legacy_order) - 1
        if label_idx < rare_idx:
            return "rare"
        return label
    return label


def occupancy_raw_to_pct(raw: float) -> float:
    """
    eBird ST ``range_occupied_percent`` may be a 0–1 fraction or already 0–100.
    Store as percentage 0–100 for CountrySpecies.frequency_pct.
    """
    v = float(raw)
    if v > 1.5:
        return min(v, 100.0)
    return v * 100.0


def load_species_codes_from_file(path: str) -> List[str]:
    with open(path, encoding="utf-8") as f:
        return [
            normalize_st_species_code(line.split()[0])
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]


def species_codes_from_data_dir(data_dir: str) -> List[str]:
    out: List[str] = []
    for pattern, suffix in (
        ("*_regional_stats.csv", "_regional_stats.csv"),
        ("*_species_stats.csv", "_species_stats.csv"),
    ):
        for path in glob.glob(os.path.join(data_dir, pattern)):
            base = os.path.basename(path)
            code = base.replace(suffix, "")
            if code:
                out.append(normalize_st_species_code(code))
    return sorted(set(out))


def write_commonness_outputs(
    result: pd.DataFrame,
    sqlite_path: str,
    csv_path: str,
) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(sqlite_path)) or ".", exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        result.to_sql("commonness", conn, if_exists="replace", index=False)
    finally:
        conn.close()
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)) or ".", exist_ok=True)
    result.to_csv(csv_path, index=False)
