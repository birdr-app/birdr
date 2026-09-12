"""Map eBird Status & Trends admin-1 rows onto app ``Country.pk`` values.

ST ``regional_stats.csv`` uses ``region_type=state`` (not eBird ``subnational1``).
Region codes are mixed:

- US / Canada / Mexico: ISO 3166-2 with an alpha-3 prefix (``USA-MA``, ``CAN-ON``)
- China / Australia / Argentina: opaque numeric ids (``CHN-1178``, ``AUS-006``,
  ``ARG-1295``) plus an English ``region_name``

The app stores alpha-2 quiz codes (``US-MA``, ``CN-35``, ``AU-NSW``, ``AR-B``).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Optional

from jizz.country_region_codes import (
    alpha2_for_alpha3,
    resolve_app_country_for_st_region,
)

ST_PLAYABLE_REGION_TYPES = frozenset({"country", "state", "province", "subnational1"})

# English names as they appear in ST CSVs (folded) → app Country.pk.
ST_ADMIN1_NAMES: dict[str, dict[str, str]] = {
    "CN": {
        "beijing": "CN-11",
        "tianjin": "CN-12",
        "hebei": "CN-13",
        "shanxi": "CN-14",
        "inner mongol": "CN-15",
        "inner mongolia": "CN-15",
        "nei mongol": "CN-15",
        "liaoning": "CN-21",
        "jilin": "CN-22",
        "heilongjiang": "CN-23",
        "shanghai": "CN-31",
        "jiangsu": "CN-32",
        "zhejiang": "CN-33",
        "anhui": "CN-34",
        "fujian": "CN-35",
        "jiangxi": "CN-36",
        "shandong": "CN-37",
        "henan": "CN-41",
        "hubei": "CN-42",
        "hunan": "CN-43",
        "guangdong": "CN-44",
        "guangxi": "CN-45",
        "hainan": "CN-46",
        "chongqing": "CN-50",
        "sichuan": "CN-51",
        "guizhou": "CN-52",
        "yunnan": "CN-53",
        "xizang": "CN-54",
        "tibet": "CN-54",
        "shaanxi": "CN-61",
        "gansu": "CN-62",
        "qinghai": "CN-63",
        "ningxia": "CN-64",
        "xinjiang": "CN-65",
    },
    "AR": {
        "salta": "AR-A",
        "buenos aires": "AR-B",
        "ciudad de buenos aires": "AR-C",
        "caba": "AR-C",
        "san luis": "AR-D",
        "entre rios": "AR-E",
        "la rioja": "AR-F",
        "santiago del estero": "AR-G",
        "chaco": "AR-H",
        "san juan": "AR-J",
        "catamarca": "AR-K",
        "la pampa": "AR-L",
        "mendoza": "AR-M",
        "misiones": "AR-N",
        "formosa": "AR-P",
        "neuquen": "AR-Q",
        "rio negro": "AR-R",
        "santa fe": "AR-S",
        "tucuman": "AR-T",
        "chubut": "AR-U",
        "tierra del fuego": "AR-V",
        "corrientes": "AR-W",
        "cordoba": "AR-X",
        "jujuy": "AR-Y",
        "santa cruz": "AR-Z",
    },
    "AU": {
        "new south wales": "AU-NSW",
        "queensland": "AU-QLD",
        "south australia": "AU-SA",
        "tasmania": "AU-TAS",
        "victoria": "AU-VIC",
        "western australia": "AU-WA",
        "northern territory": "AU-NT",
        "australian capital territory": "AU-ACT",
    },
    "CA": {
        "alberta": "CA-AB",
        "british columbia": "CA-BC",
        "manitoba": "CA-MB",
        "new brunswick": "CA-NB",
        "newfoundland and labrador": "CA-NL",
        "nova scotia": "CA-NS",
        "northwest territories": "CA-NT",
        "nunavut": "CA-NU",
        "ontario": "CA-ON",
        "prince edward island": "CA-PE",
        "quebec": "CA-QC",
        "saskatchewan": "CA-SK",
        "yukon": "CA-YT",
        "yukon territory": "CA-YT",
    },
}


def fold_region_name(name: str | None) -> str:
    raw = unicodedata.normalize("NFKD", name or "")
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.replace("'", "").replace("’", "")
    raw = re.sub(r"[^a-zA-Z0-9]+", " ", raw).lower().strip()
    return " ".join(raw.split())


def _parent_from_st_code(region_code: str) -> str | None:
    prefix = region_code.split("-", 1)[0]
    if len(prefix) == 3:
        return alpha2_for_alpha3(prefix) or prefix
    if len(prefix) == 2:
        return prefix
    return None


def _is_opaque_suffix(code: str) -> bool:
    if "-" not in code:
        return False
    return code.split("-", 1)[1].isdigit()


@lru_cache(maxsize=1)
def _db_admin1_name_map() -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    try:
        from jizz.models import Country

        rows = list(Country.objects.exclude(parent_id=None).only("code", "name", "parent_id"))
    except Exception:
        return out
    for country in rows:
        parent = str(country.parent_id or "").strip().upper()
        if not parent:
            continue
        app = str(country.code).strip().upper()
        for key in (fold_region_name(country.name),):
            if not key:
                continue
            out.setdefault((parent, key), app)
            if " " in key:
                tail = key.split()[-1]
                if tail not in {"island", "territory", "province", "state"}:
                    out.setdefault((parent, tail), app)
            # "United States - Alaska" → "alaska"
            if "-" in (country.name or ""):
                tail_name = fold_region_name(country.name.split("-")[-1])
                if tail_name:
                    out.setdefault((parent, tail_name), app)
    return out


def lookup_admin1_name(region_code: str, region_name: str | None) -> Optional[str]:
    folded = fold_region_name(region_name)
    if not folded:
        return None
    parent = _parent_from_st_code(region_code.strip().upper())
    if not parent:
        return None
    hit = ST_ADMIN1_NAMES.get(parent, {}).get(folded)
    if hit:
        return hit
    return _db_admin1_name_map().get((parent, folded))


def app_code_for_st_region(
    region_code: str | None,
    region_name: str | None = None,
) -> Optional[str]:
    """Map one ST CSV row (code + optional English name) to an app country code."""
    rc = (region_code or "").strip().upper()
    if not rc or rc in {"NAN", "NONE"}:
        return None
    name_hit = lookup_admin1_name(rc, region_name) if region_name else None
    if _is_opaque_suffix(rc):
        return name_hit
    mapped = resolve_app_country_for_st_region(rc)
    if mapped and not _is_opaque_suffix(mapped):
        return mapped
    return name_hit or mapped
