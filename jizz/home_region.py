"""Home region: which birds a player already knows from home (drives Trip prep tailoring).

Only three regions are tailored for now. A player picks one on their profile; when they haven't,
it is inferred from their preferred country.
"""

from __future__ import annotations

REGION_NA = 'na'
REGION_EU = 'eu'
REGION_OTHER = 'other'
REGIONS = (REGION_NA, REGION_EU, REGION_OTHER)

# North America: United States, Canada and Bermuda (Mexico and the tropics are "other" for now).
NA_COUNTRIES = frozenset({'US', 'CA', 'BM', 'PM'})

# Europe, including the Atlantic islands, Iceland, Turkey's neighbours in the Caucasus excluded.
EU_COUNTRIES = frozenset({
    'AD', 'AL', 'AT', 'AX', 'BA', 'BE', 'BG', 'BY', 'CH', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FO',
    'FR', 'GB', 'GG', 'GI', 'GR', 'HR', 'HU', 'IE', 'IM', 'IS', 'IT', 'JE', 'LI', 'LT', 'LU', 'LV', 'MC',
    'MD', 'ME', 'MK', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'RS', 'RU', 'SE', 'SI', 'SK', 'SM', 'SJ', 'UA',
    'VA', 'XK',
})


def region_for_country(code: str | None) -> str:
    """NA, EU or other for a country code (a subnational code like ``US-MA`` counts as its country)."""
    country = (code or '').upper().split('-')[0]
    if country in NA_COUNTRIES:
        return REGION_NA
    if country in EU_COUNTRIES:
        return REGION_EU
    return REGION_OTHER


def effective_home_region(profile) -> str:
    """The chosen region, else inferred from the preferred country, else ``eu`` for no country at all."""
    if profile is None:
        return REGION_OTHER
    if profile.home_region in REGIONS:
        return profile.home_region
    if profile.country_id:
        return region_for_country(profile.country_id)
    return REGION_OTHER
