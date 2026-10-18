"""Capital-city timezone per country code, used for the National League day boundaries."""

from __future__ import annotations

import pytz

# Countries spanning several zones: pytz lists them in an arbitrary order,
# so pin the capital's zone explicitly.
CAPITAL_TIMEZONE_OVERRIDES: dict[str, str] = {
    'AR': 'America/Argentina/Buenos_Aires',
    'AU': 'Australia/Sydney',
    'BR': 'America/Sao_Paulo',
    'CA': 'America/Toronto',
    'CD': 'Africa/Kinshasa',
    'CL': 'America/Santiago',
    'CN': 'Asia/Shanghai',
    'EC': 'America/Guayaquil',
    'ES': 'Europe/Madrid',
    'FM': 'Pacific/Pohnpei',
    'GL': 'America/Nuuk',
    'ID': 'Asia/Jakarta',
    'KI': 'Pacific/Tarawa',
    'KZ': 'Asia/Almaty',
    'MN': 'Asia/Ulaanbaatar',
    'MX': 'America/Mexico_City',
    'MY': 'Asia/Kuala_Lumpur',
    'NZ': 'Pacific/Auckland',
    'PF': 'Pacific/Tahiti',
    'PG': 'Pacific/Port_Moresby',
    'PT': 'Europe/Lisbon',
    'RU': 'Europe/Moscow',
    'UA': 'Europe/Kyiv',
    'US': 'America/New_York',
    'UZ': 'Asia/Tashkent',
    # Regions whose own capital differs from the parent's.
    'US-CA': 'America/Los_Angeles',
    'US-WEST': 'America/Los_Angeles',
    'US-AZ': 'America/Phoenix',
    'US-CO': 'America/Denver',
    'US-TX': 'America/Chicago',
    'US-IL': 'America/Chicago',
    'US-HI': 'Pacific/Honolulu',
    'US-AK': 'America/Anchorage',
    'CA-BC': 'America/Vancouver',
    'CA-AB': 'America/Edmonton',
    'AU-WA': 'Australia/Perth',
    'AU-QLD': 'Australia/Brisbane',
}

DEFAULT_TIMEZONE = 'UTC'


def capital_timezone(code: str) -> str | None:
    """IANA zone for a country/region code, or None when unknown (caller falls back)."""
    code = (code or '').upper()
    if code in CAPITAL_TIMEZONE_OVERRIDES:
        return CAPITAL_TIMEZONE_OVERRIDES[code]
    if len(code) == 2:
        zones = pytz.country_timezones.get(code.lower())
        if zones:
            return zones[0]
    return None
