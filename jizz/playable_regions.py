"""Playable subnational regions, aggregates, and calendar seasons.

States/provinces are ``Country`` rows (same as US-EAST). Aggregates such as
US-EAST or Argentina Patagonia are unions of eBird subnational1 codes.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

KIND_COUNTRY = "country"
KIND_SUBNATIONAL = "subnational"
KIND_AGGREGATE = "aggregate"
KIND_SPECIALTY = "specialty"
KIND_CHOICES = (
    (KIND_COUNTRY, "Country"),
    (KIND_SUBNATIONAL, "Subnational"),
    (KIND_AGGREGATE, "Aggregate"),
    (KIND_SPECIALTY, "Specialty"),
)

HEMISPHERE_NORTH = "north"
HEMISPHERE_SOUTH = "south"
HEMISPHERE_CHOICES = (
    (HEMISPHERE_NORTH, "Northern"),
    (HEMISPHERE_SOUTH, "Southern"),
)

SEASON_SPRING = "spring"
SEASON_SUMMER = "summer"
SEASON_AUTUMN = "autumn"
SEASON_WINTER = "winter"
SEASON_CHOICES = (
    (SEASON_SPRING, "Spring"),
    (SEASON_SUMMER, "Summer"),
    (SEASON_AUTUMN, "Autumn"),
    (SEASON_WINTER, "Winter"),
)

# Parents whose eBird subnational1 list should become playable quiz countries.
PROVISION_PARENTS = ("US", "CA", "AU", "MX")

# Shown at the top level of the picker in addition to countries and aggregates.
TOP_LEVEL_SUBNATIONAL = frozenset({"US-AK", "US-HI"})

SPECIALTY_PARENTS: dict[str, str] = {
    "NL-NH": "NL",
}

SOUTHERN_HEMISPHERE_ROOTS = frozenset(
    {
        "AR",
        "AU",
        "NZ",
        "ZA",
        "CL",
        "UY",
        "PY",
        "NA",
        "BW",
        "ZW",
        "MZ",
        "MG",
        "LS",
        "SZ",
        "FK",
    }
)

US_EAST = (
    "US-ND",
    "US-SD",
    "US-NE",
    "US-KS",
    "US-OK",
    "US-TX",
    "US-MN",
    "US-IA",
    "US-MO",
    "US-AR",
    "US-LA",
    "US-WI",
    "US-IL",
    "US-IN",
    "US-OH",
    "US-KY",
    "US-TN",
    "US-MS",
    "US-MI",
    "US-AL",
    "US-GA",
    "US-FL",
    "US-SC",
    "US-NC",
    "US-VA",
    "US-WV",
    "US-PA",
    "US-NY",
    "US-VT",
    "US-NH",
    "US-ME",
    "US-MA",
    "US-CT",
    "US-RI",
    "US-NJ",
    "US-DE",
    "US-MD",
    "US-DC",
)

US_WEST = (
    "US-CA",
    "US-OR",
    "US-WA",
    "US-ID",
    "US-NV",
    "US-UT",
    "US-AZ",
    "US-MT",
    "US-WY",
    "US-CO",
    "US-NM",
)

CN_SOUTH = (
    "CN-53",  # Yunnan
    "CN-51",  # Sichuan
    "CN-45",  # Guangxi
    "CN-44",  # Guangdong
    "CN-52",  # Guizhou
    "CN-46",  # Hainan
    "CN-35",  # Fujian
)

CN_EAST = (
    "CN-32",  # Jiangsu
    "CN-33",  # Zhejiang
    "CN-31",  # Shanghai
    "CN-34",  # Anhui
    "CN-36",  # Jiangxi
    "CN-42",  # Hubei
    "CN-43",  # Hunan
)

CN_NORTH = (
    "CN-11",  # Beijing
    "CN-13",  # Hebei
    "CN-37",  # Shandong
    "CN-21",  # Liaoning
    "CN-22",  # Jilin
    "CN-23",  # Heilongjiang
    "CN-15",  # Inner Mongolia
)

CN_WEST = (
    "CN-65",  # Xinjiang
    "CN-54",  # Tibet
    "CN-63",  # Qinghai
    "CN-62",  # Gansu
)

AR_NW = (
    "AR-A",  # Salta
    "AR-Y",  # Jujuy
    "AR-T",  # Tucumán
    "AR-K",  # Catamarca
)

AR_NE = (
    "AR-N",  # Misiones
    "AR-W",  # Corrientes
    "AR-P",  # Formosa
    "AR-H",  # Chaco
)

AR_PAMPAS = (
    "AR-B",  # Buenos Aires
    "AR-C",  # CABA
    "AR-S",  # Santa Fe
    "AR-X",  # Córdoba
    "AR-L",  # La Pampa
)

AR_CUYO = (
    "AR-M",  # Mendoza
    "AR-J",  # San Juan
    "AR-D",  # San Luis
)

AR_PAT = (
    "AR-Q",  # Neuquén
    "AR-R",  # Río Negro
    "AR-U",  # Chubut
    "AR-Z",  # Santa Cruz
    "AR-V",  # Tierra del Fuego
)

AGGREGATE_MEMBERS: dict[str, tuple[str, ...]] = {
    "US-EAST": US_EAST,
    "US-WEST": US_WEST,
    "CN-SOUTH": CN_SOUTH,
    "CN-EAST": CN_EAST,
    "CN-NORTH": CN_NORTH,
    "CN-WEST": CN_WEST,
    "AR-NW": AR_NW,
    "AR-NE": AR_NE,
    "AR-PAMPAS": AR_PAMPAS,
    "AR-CUYO": AR_CUYO,
    "AR-PAT": AR_PAT,
}

AGGREGATE_PARENTS: dict[str, str] = {
    "US-EAST": "US",
    "US-WEST": "US",
    "CN-SOUTH": "CN",
    "CN-EAST": "CN",
    "CN-NORTH": "CN",
    "CN-WEST": "CN",
    "AR-NW": "AR",
    "AR-NE": "AR",
    "AR-PAMPAS": "AR",
    "AR-CUYO": "AR",
    "AR-PAT": "AR",
}

AGGREGATE_NAMES: dict[str, str] = {
    "US-EAST": "United States – Eastern",
    "US-WEST": "United States – Western",
    "CN-SOUTH": "China – South & Southwest",
    "CN-EAST": "China – East & Central",
    "CN-NORTH": "China – North & Northeast",
    "CN-WEST": "China – West & Plateau",
    "AR-NW": "Argentina – Northwest",
    "AR-NE": "Argentina – Northeast",
    "AR-PAMPAS": "Argentina – Pampas",
    "AR-CUYO": "Argentina – Cuyo",
    "AR-PAT": "Argentina – Patagonia",
}

SEASON_MONTHS_NORTH: dict[str, tuple[int, ...]] = {
    SEASON_SPRING: (3, 4, 5),
    SEASON_SUMMER: (6, 7, 8),
    SEASON_AUTUMN: (9, 10, 11),
    SEASON_WINTER: (12, 1, 2),
}

SEASON_MONTHS_SOUTH: dict[str, tuple[int, ...]] = {
    SEASON_SPRING: (9, 10, 11),
    SEASON_SUMMER: (12, 1, 2),
    SEASON_AUTUMN: (3, 4, 5),
    SEASON_WINTER: (6, 7, 8),
}

# Most common → rarest (matches CountrySpecies.FREQUENCY_CHOICES).
FREQUENCY_TIER_ORDER = (
    "abundant",
    "very_common",
    "common",
    "fairly_common",
    "uncommon",
    "rare",
    "very_rare",
    "vagrant",
)
_FREQUENCY_RANK = {tier: i for i, tier in enumerate(FREQUENCY_TIER_ORDER)}


def normalize_code(code: str | None) -> str:
    return (code or "").strip().upper()


def hyphen_parent_code(code: str) -> Optional[str]:
    """ISO-style parent from a hyphenated quiz code (US-MA → US, AR-PAMPAS → AR)."""
    cc = normalize_code(code)
    if "-" not in cc:
        return None
    prefix = cc.split("-", 1)[0]
    if len(prefix) == 2 and prefix.isalpha():
        return prefix
    return None


def inferred_parent_code(code: str) -> Optional[str]:
    cc = normalize_code(code)
    if not cc:
        return None
    if cc in SPECIALTY_PARENTS:
        return SPECIALTY_PARENTS[cc]
    if cc in AGGREGATE_PARENTS:
        return AGGREGATE_PARENTS[cc]
    return hyphen_parent_code(cc)


def inferred_kind(code: str) -> str:
    cc = normalize_code(code)
    if cc in SPECIALTY_PARENTS:
        return KIND_SPECIALTY
    if cc in AGGREGATE_MEMBERS:
        return KIND_AGGREGATE
    if "-" in cc:
        return KIND_SUBNATIONAL
    return KIND_COUNTRY


def inferred_hemisphere(code: str) -> str:
    cc = normalize_code(code)
    root = inferred_parent_code(cc) or cc
    root = hyphen_parent_code(root) or root
    if root in SOUTHERN_HEMISPHERE_ROOTS:
        return HEMISPHERE_SOUTH
    return HEMISPHERE_NORTH


def members_for(code: str) -> tuple[str, ...]:
    return AGGREGATE_MEMBERS.get(normalize_code(code), ())


def scoring_region_codes(country_code: str) -> list[str]:
    """eBird ST ``region_code`` values to score for a quiz country.

    Aggregates use member subnational1 codes (not the synthetic US-EAST token).
    Ordinary countries keep the ISO / ``Country.codes`` expansion.
    """
    cc = normalize_code(country_code)
    members = AGGREGATE_MEMBERS.get(cc)
    if members:
        from jizz.country_region_codes import st_region_codes_for_app_country

        out: list[str] = []
        seen: set[str] = set()
        for member in members:
            for token in st_region_codes_for_app_country(member):
                if token not in seen:
                    seen.add(token)
                    out.append(token)
        return out
    from jizz.country_region_codes import expand_region_codes

    return expand_region_codes(cc)


def months_for_season(season: str | None, hemisphere: str | None) -> tuple[int, ...]:
    if not season:
        return ()
    key = season.strip().lower()
    hemi = (hemisphere or HEMISPHERE_NORTH).strip().lower()
    table = SEASON_MONTHS_SOUTH if hemi == HEMISPHERE_SOUTH else SEASON_MONTHS_NORTH
    return table.get(key, ())


def hemisphere_for_country(country) -> str:
    """Prefer the stored field; otherwise infer from the code."""
    stored = getattr(country, "hemisphere", None)
    if stored in (HEMISPHERE_NORTH, HEMISPHERE_SOUTH):
        return stored
    parent = getattr(country, "parent", None)
    parent_hemi = getattr(parent, "hemisphere", None) if parent is not None else None
    if parent_hemi in (HEMISPHERE_NORTH, HEMISPHERE_SOUTH):
        return parent_hemi
    code = getattr(country, "code", None) or getattr(country, "pk", "")
    return inferred_hemisphere(str(code))


def months_for_game(game) -> tuple[int, ...]:
    season = getattr(game, "season", None)
    if not season:
        return ()
    country = getattr(game, "country", None)
    hemi = hemisphere_for_country(country) if country is not None else HEMISPHERE_NORTH
    return months_for_season(season, hemi)


def best_frequency_tier(tiers: Iterable[str | None]) -> Optional[str]:
    """Most common (lowest rank) among known tiers; ignore blanks."""
    best: Optional[str] = None
    best_rank = 10**9
    for raw in tiers:
        if not raw:
            continue
        rank = _FREQUENCY_RANK.get(raw)
        if rank is None:
            continue
        if rank < best_rank:
            best_rank = rank
            best = raw
    return best


def is_top_level_picker_code(code: str, kind: str | None) -> bool:
    cc = normalize_code(code)
    k = (kind or inferred_kind(cc)).strip().lower()
    if k == KIND_SPECIALTY:
        return False
    if k in (KIND_COUNTRY, KIND_AGGREGATE):
        return True
    return cc in TOP_LEVEL_SUBNATIONAL


def us_smart_expansion() -> tuple[str, ...]:
    return ("US-EAST", "US-WEST", "US-AK", "US-HI") + US_EAST + US_WEST


def all_aggregate_codes() -> Sequence[str]:
    return tuple(AGGREGATE_MEMBERS.keys())
