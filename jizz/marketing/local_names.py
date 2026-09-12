"""Proper names for marketing pages.

Species names come from ``SpeciesName`` (eBird/IOC vernaculars), never from the
marketing copy catalog. Country names on English pages are ``Country.name`` from
the database; other locales use official ISO region labels (same source as the
apps), not catalog/machine translation of the English string.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from jizz.marketing.i18n import DEFAULT_LOCALE, get_locale, is_marketing_locale
from jizz.models import Species, SpeciesName

# Marketing locale -> SpeciesName.language_id (underscores, e.g. pt_BR).
SPECIES_NAME_LANGUAGE = {
    'en': 'en',
    'nl': 'nl',
    'es': 'es',
    'fr': 'fr',
    'de': 'de',
    'it': 'it',
    'pt-BR': 'pt_BR',
    'ja': 'ja',
}

_DATA = Path(__file__).resolve().parent / 'data' / 'country_names.json'


def _locale(locale: str | None) -> str:
    if is_marketing_locale(locale):
        return locale
    return get_locale()


def species_name_language_id(locale: str | None = None) -> str:
    return SPECIES_NAME_LANGUAGE.get(_locale(locale), 'en')


@lru_cache(maxsize=1)
def _country_name_maps() -> dict[str, dict[str, str]]:
    if not _DATA.exists():
        return {}
    return json.loads(_DATA.read_text(encoding='utf-8'))


def country_code_of(country) -> str:
    if country is None:
        return ''
    if isinstance(country, str):
        return country.strip()
    if isinstance(country, dict):
        return str(country.get('code') or '').strip()
    return str(getattr(country, 'code', '') or '').strip()


def country_fallback_name(country) -> str:
    if country is None:
        return ''
    if isinstance(country, str):
        return country
    if isinstance(country, dict):
        return str(country.get('name') or '')
    return str(getattr(country, 'name', '') or '')


def country_display_name(country, locale: str | None = None) -> str:
    """Local country label. English uses the database name; never catalog lookup."""
    loc = _locale(locale)
    fallback = country_fallback_name(country)
    code = country_code_of(country)
    if loc == DEFAULT_LOCALE or not code or '-' in code:
        return fallback
    mapped = _country_name_maps().get(loc, {}).get(code.upper())
    return mapped or fallback


def species_display_names(species_ids: Iterable[int], locale: str | None = None) -> dict[int, str]:
    """Map species id -> vernacular from SpeciesName, else Species.name."""
    ids = [int(pk) for pk in species_ids if pk]
    if not ids:
        return {}
    loc = _locale(locale)
    lang = species_name_language_id(loc)
    species_map = Species.objects.in_bulk(ids)
    translated = {}
    if lang != 'en':
        translated = dict(
            SpeciesName.objects.filter(
                species_id__in=ids,
                language_id=lang,
            ).values_list('species_id', 'name')
        )
    out: dict[int, str] = {}
    for sid in ids:
        sp = species_map.get(sid)
        if sid in translated and translated[sid]:
            out[sid] = translated[sid]
        elif loc == 'nl' and sp is not None and sp.name_nl:
            out[sid] = sp.name_nl
        elif sp is not None:
            out[sid] = sp.name
        else:
            out[sid] = ''
    return out


def species_display_name(species, locale: str | None = None) -> str:
    if species is None:
        return ''
    if isinstance(species, dict):
        sid = species.get('id') or species.get('species_id')
        if sid:
            names = species_display_names([sid], locale)
            return names.get(int(sid), species.get('name') or '')
        return species.get('name') or ''
    sid = getattr(species, 'id', None)
    if sid:
        names = species_display_names([sid], locale)
        if sid in names and names[sid]:
            return names[sid]
    return getattr(species, 'name', '') or ''


def _as_species_id(value) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def overlay_species_names(rows: list[dict], locale: str | None, fields: dict[str, str]) -> list[dict]:
    """Copy rows, replacing name fields from SpeciesName using id fields.

    ``fields`` maps display key -> id key, e.g. ``{'name': 'species_id'}``.
    """
    ids = []
    for row in rows:
        for id_key in fields.values():
            sid = _as_species_id(row.get(id_key))
            if sid:
                ids.append(sid)
    names = species_display_names(ids, locale)
    out = []
    for row in rows:
        item = dict(row)
        for name_key, id_key in fields.items():
            sid = _as_species_id(item.get(id_key))
            if sid in names and names[sid]:
                item[name_key] = names[sid]
        out.append(item)
    return out


def stamp_species_display_names(species_list: list, locale: str | None = None) -> list:
    names = species_display_names(
        [getattr(species, 'id', None) for species in species_list],
        locale,
    )
    for species in species_list:
        sid = getattr(species, 'id', None)
        species.display_name = names.get(sid) or getattr(species, 'name', '') or ''
    return species_list


def localize_country_rows(rows: list[dict], locale: str | None = None) -> list[dict]:
    loc = _locale(locale)
    out = []
    for row in rows:
        item = dict(row)
        item['name'] = country_display_name(item, loc)
        out.append(item)
    out.sort(key=lambda r: (r.get('name') or '').casefold())
    return out


def localize_family_rows(rows: list[dict], locale: str | None = None) -> list[dict]:
    loc = _locale(locale)
    out = []
    for row in rows:
        item = dict(row)
        item['display_name'] = taxonomy_display_name(
            item.get('name_en') or '',
            item.get('name_nl') or '',
            loc,
        )
        out.append(item)
    out.sort(key=lambda r: (r.get('display_name') or '').casefold())
    return out


def taxonomy_display_name(name_en: str, name_nl: str, locale: str | None = None) -> str:
    loc = _locale(locale)
    if loc == 'nl' and name_nl:
        return name_nl
    return name_en or name_nl or ''
