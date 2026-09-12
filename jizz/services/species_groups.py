"""eBird species groups (shorebirds, wood-warblers, …) as a SpeciesGroup table.

Groups partition the taxonomy: each species belongs to at most one group.
Assignment uses Species.tax_ordering against eBird taxonOrderBounds.

English, Dutch, Spanish, French, German and Brazilian Portuguese names come
from the eBird sppgroup API. Italian and Japanese are not localized there, so
those names are translated with OpenAI when filling groups.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from django.conf import settings
from django.core.cache import cache
from django.utils.text import slugify

from jizz.app_languages import normalize_app_language
from jizz.services.taxonomy_texts import fetch_ebird_sppgroups
from jizz.update_i18n import LOCALE_NAMES, QUOTA_CACHE_KEY, QUOTA_CACHE_TIMEOUT, _is_quota_error

logger = logging.getLogger(__name__)

# App-language field suffix -> eBird groupNameLocale.
GROUP_NAME_EBIRD_LOCALES: dict[str, str] = {
    'en': 'en',
    'nl': 'nl',
    'es': 'es',
    'fr': 'fr',
    'de': 'de',
    'it': 'it',
    'pt_br': 'pt_BR',
    'ja': 'ja',
}

GROUP_NAME_FIELDS: tuple[str, ...] = tuple(
    f'name_{suffix}' for suffix in GROUP_NAME_EBIRD_LOCALES
)

APP_LOCALE_TO_NAME_FIELD: dict[str, str] = {
    'en': 'name_en',
    'nl': 'name_nl',
    'es': 'name_es',
    'fr': 'name_fr',
    'de': 'name_de',
    'it': 'name_it',
    'pt-BR': 'name_pt_br',
    'ja': 'name_ja',
}

# eBird returns English for these groupNameLocale values.
OPENAI_GROUP_NAME_SUFFIXES = frozenset({'it', 'ja'})
TRANSLATE_BATCH = 50
GROUP_NAMES_PATH = Path(__file__).resolve().parent.parent / 'data' / 'species_group_names.json'


def unique_slug(name: str, used: set[str]) -> str:
    base = slugify(name) or 'group'
    slug = base
    n = 2
    while slug in used:
        slug = f'{base}-{n}'
        n += 1
    used.add(slug)
    return slug


def sppgroup_intervals(
    groups: list[dict[str, Any]],
    *,
    key: str = 'groupName',
) -> list[tuple[float, float, float, Any]]:
    """Return (low, high, width, key_value) intervals for taxonOrder matching."""
    intervals: list[tuple[float, float, float, Any]] = []
    for group in groups:
        value = group.get(key)
        for bound in group.get('taxonOrderBounds') or []:
            if len(bound) != 2:
                continue
            low, high = bound
            intervals.append((float(low), float(high), float(high) - float(low), value))
    return intervals


def match_group(
    taxon_order: float | None,
    intervals: list[tuple[float, float, float, Any]],
) -> Any | None:
    """Return the narrowest group whose bounds contain taxon_order."""
    if taxon_order is None:
        return None
    matches = [
        (width, value)
        for low, high, width, value in intervals
        if low <= taxon_order <= high
    ]
    if not matches:
        return None
    return min(matches)[1]


def _names_by_group_order(groups: list[dict[str, Any]]) -> dict[int, str]:
    names: dict[int, str] = {}
    for group in groups:
        order = group.get('groupOrder')
        name = (group.get('groupName') or '').strip()
        if order is None or not name:
            continue
        names[int(order)] = name
    return names


def rows_from_sppgroups(
    en_groups: list[dict[str, Any]],
    nl_groups: list[dict[str, Any]] | None = None,
    locale_groups: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    """Build SpeciesGroup field dicts from eBird sppgroup payloads.

    ``locale_groups`` maps field suffix (``nl``, ``es``, ``pt_br``, …) to that
    locale's eBird payload. ``nl_groups`` is kept for existing callers.
    """
    lookups: dict[str, dict[int, str]] = {}
    merged = dict(locale_groups or {})
    if nl_groups is not None:
        merged.setdefault('nl', nl_groups)
    for suffix, groups in merged.items():
        lookups[suffix] = _names_by_group_order(groups)

    used_slugs: set[str] = set()
    rows: list[dict[str, Any]] = []
    for group in sorted(en_groups, key=lambda g: g.get('groupOrder') or 0):
        name_en = (group.get('groupName') or '').strip()
        if not name_en:
            continue
        sort_order = int(group.get('groupOrder') or 0)
        row: dict[str, Any] = {
            'slug': unique_slug(name_en, used_slugs),
            'ebird_name': name_en,
            'name_en': name_en,
            'sort_order': sort_order,
            'taxon_order_bounds': group.get('taxonOrderBounds') or [],
        }
        for suffix in GROUP_NAME_EBIRD_LOCALES:
            if suffix == 'en':
                continue
            row[f'name_{suffix}'] = lookups.get(suffix, {}).get(sort_order) or name_en
        rows.append(row)
    return rows


def apply_missing_translations(
    rows: list[dict[str, Any]],
    *,
    translate_names=None,
) -> list[str]:
    """Translate locales eBird leaves in English. Returns suffixes that were filled."""
    translate = translate_names or translate_group_names
    filled: list[str] = []
    for suffix in GROUP_NAME_EBIRD_LOCALES:
        if suffix not in OPENAI_GROUP_NAME_SUFFIXES:
            continue
        field = f'name_{suffix}'
        missing = [
            row for row in rows
            if (row.get('name_en') or '').strip()
            and (row.get(field) or '').strip() in ('', (row.get('name_en') or '').strip())
        ]
        if not missing:
            continue
        app_locale = 'pt-BR' if suffix == 'pt_br' else suffix
        mapping = translate([row['name_en'] for row in missing], app_locale) or {}
        changed = False
        for row in missing:
            translated = (mapping.get(row['name_en']) or '').strip()
            if translated:
                row[field] = translated
                changed = True
        if changed:
            filled.append(suffix)
    return filled


def group_name_for_locale(group: Any, locale: str | None = None) -> str:
    """Localized group name, falling back to English."""
    code = normalize_app_language(locale) or 'en'
    field = APP_LOCALE_TO_NAME_FIELD.get(code, 'name_en')
    if isinstance(group, dict):
        value = group.get(field) or group.get('name_en') or ''
    else:
        value = getattr(group, field, None) or getattr(group, 'name_en', None) or ''
    return str(value).strip()


def load_bundled_group_names(path: Path | None = None) -> dict[str, dict[str, str]]:
    catalog_path = path or GROUP_NAMES_PATH
    if not catalog_path.exists():
        return {}
    try:
        data = json.loads(catalog_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        logger.warning('Could not read species group name catalog at %s', catalog_path)
        return {}
    return data if isinstance(data, dict) else {}


def overlay_bundled_names(
    rows: list[dict[str, Any]],
    catalog: dict[str, dict[str, str]] | None = None,
) -> None:
    """Fill empty/English names from the committed catalog (used for it/ja)."""
    data = load_bundled_group_names() if catalog is None else catalog
    if not data:
        return
    for row in rows:
        extra = data.get(row.get('ebird_name') or '') or data.get(row.get('slug') or '') or {}
        english = (row.get('name_en') or '').strip()
        for field in GROUP_NAME_FIELDS:
            if field == 'name_en':
                continue
            bundled = (extra.get(field) or '').strip()
            current = (row.get(field) or '').strip()
            if bundled and (not current or current == english):
                row[field] = bundled


def catalog_from_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get('ebird_name') or row.get('slug')
        if not key:
            continue
        catalog[key] = {
            field: (row.get(field) or '')
            for field in GROUP_NAME_FIELDS
            if field != 'name_en'
        }
    return catalog


def fetch_species_group_rows(*, translate_missing: bool = True) -> list[dict[str, Any]]:
    en_groups = fetch_ebird_sppgroups(locale='en')
    locale_groups: dict[str, list[dict[str, Any]]] = {}
    for suffix, ebird_locale in GROUP_NAME_EBIRD_LOCALES.items():
        if suffix == 'en':
            continue
        try:
            locale_groups[suffix] = fetch_ebird_sppgroups(locale=ebird_locale)
        except Exception:
            logger.warning('Failed to fetch eBird species groups for locale %s', ebird_locale)
            locale_groups[suffix] = []
    rows = rows_from_sppgroups(en_groups, locale_groups=locale_groups)
    overlay_bundled_names(rows)
    if translate_missing:
        apply_missing_translations(rows)
    return rows


def taxon_order_by_species_code(ebird_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Map eBird speciesCode -> taxonOrder for species rows."""
    result: dict[str, float] = {}
    for row in ebird_rows:
        if row.get('category') != 'species':
            continue
        code = (row.get('speciesCode') or '').strip()
        taxon_order = row.get('taxonOrder')
        if code and taxon_order is not None:
            result[code] = float(taxon_order)
    return result


def assign_species_group_ids(
    *,
    taxon_orders: Iterable[tuple[int, float | None]],
    intervals: list[tuple[float, float, float, int]],
) -> dict[int | None, list[int]]:
    """Map species_group_id (or None) -> species ids from tax_ordering."""
    by_group: dict[int | None, list[int]] = defaultdict(list)
    for species_id, tax_ordering in taxon_orders:
        group_id = match_group(tax_ordering, intervals)
        by_group[group_id].append(species_id)
    return dict(by_group)


def translate_group_names(english_names: list[str], language: str) -> dict[str, str]:
    """Translate eBird group names into an app language. Empty dict if skipped."""
    language = normalize_app_language(language)
    if not language or language == 'en':
        return {}
    unique_names = list(dict.fromkeys(name for name in english_names if name))
    mapping: dict[str, str] = {}
    for start in range(0, len(unique_names), TRANSLATE_BATCH):
        chunk = unique_names[start:start + TRANSLATE_BATCH]
        part = _translate_group_names_with_openai(chunk, language)
        if not part:
            continue
        mapping.update(part)
    return mapping


def _translate_group_names_with_openai(names: list[str], language: str) -> dict[str, str] | None:
    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        logger.debug('Species-group translation skipped: OPENAI_API_KEY not set')
        return None
    if cache.get(QUOTA_CACHE_KEY):
        logger.debug('Species-group translation skipped: OpenAI quota exhausted')
        return None
    language_name = LOCALE_NAMES.get(language, language)
    model = getattr(settings, 'UPDATE_TRANSLATION_MODEL', None) or 'gpt-4o-mini'
    prompt = (
        f'Translate these eBird/Clements bird species-group names into {language_name}.\n'
        'They are birder category labels (for example Shorebirds, Wood-Warblers, '
        'Tyrant Flycatchers), not full sentences.\n'
        'Return a JSON object mapping each exact English name to its translation.\n'
        'Keep hyphenation and ampersands where they still read naturally.\n'
        'Do not invent extra words. Keep internationally used names such as Kiwis '
        'only if that is the usual name in the target language.\n'
        'Never copy the English string when a normal translation exists. '
        'For Japanese, write names in Japanese script (kanji and katakana), '
        'not Latin letters.\n\n'
        f'{json.dumps(names, ensure_ascii=False)}'
    )
    try:
        from openai import OpenAI
    except ImportError:
        logger.exception('openai package is not installed')
        return None
    try:
        client = OpenAI(api_key=api_key, timeout=60.0)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You translate eBird species-group names for the Birdr app. '
                        'Reply with JSON only: {"English name": "translated name", ...}.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
            response_format={'type': 'json_object'},
        )
        raw = (response.choices[0].message.content or '').strip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        out: dict[str, str] = {}
        for name in names:
            translated = str(data.get(name) or '').strip()
            if translated:
                out[name] = translated
        return out or None
    except Exception as exc:
        if _is_quota_error(exc):
            logger.warning('Species-group translation skipped: OpenAI out of credits')
            cache.set(QUOTA_CACHE_KEY, True, timeout=QUOTA_CACHE_TIMEOUT)
        else:
            logger.exception(
                'Species-group translation failed (language=%s model=%s)', language, model
            )
        return None
