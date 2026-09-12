"""Localize AI species comparisons into the selected app language, with a durable cache."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from django.conf import settings
from django.core.cache import cache

from compare.models import ComparisonTranslation, SpeciesComparison
from jizz.app_languages import APP_LANGUAGES, normalize_app_language
from jizz.update_i18n import (
    DEFAULT_LANGUAGE,
    LOCALE_NAMES,
    QUOTA_CACHE_KEY,
    QUOTA_CACHE_TIMEOUT,
    _is_quota_error,
)

logger = logging.getLogger(__name__)

CACHE_PREFIX = 'compare-i18n-v2'
CACHE_TIMEOUT = 60 * 60 * 24 * 30

TRANSLATABLE_FIELDS = (
    'summary',
    'detailed_comparison',
    'size_comparison',
    'plumage_comparison',
    'behavior_comparison',
    'habitat_comparison',
    'vocalization_comparison',
    'identification_tips',
)
TRANSLATABLE_FIELD_SET = frozenset(TRANSLATABLE_FIELDS)


class LocalizedComparison:
    """Read overlay of translated markdown fields on a SpeciesComparison."""

    __slots__ = ('_obj', '_fields')

    def __init__(self, obj: SpeciesComparison, fields: dict[str, str]):
        object.__setattr__(self, '_obj', obj)
        object.__setattr__(self, '_fields', fields)

    def __getattr__(self, name):
        fields = object.__getattribute__(self, '_fields')
        if name in TRANSLATABLE_FIELD_SET:
            return fields.get(name) or ''
        return getattr(object.__getattribute__(self, '_obj'), name)


def source_fields(comparison: SpeciesComparison) -> dict[str, str]:
    return {field: (getattr(comparison, field, None) or '') for field in TRANSLATABLE_FIELDS}


def source_hash(fields: dict[str, str], glossary: list[dict[str, str]] | None = None) -> str:
    blob = json.dumps(
        {'fields': fields, 'names': glossary or []},
        ensure_ascii=False,
        sort_keys=True,
    ).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()[:32]


def species_name_glossary(
    comparison: SpeciesComparison,
    language: str,
    fields: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Official English → localized common names for species in this comparison."""
    from jizz.marketing.local_names import species_display_names

    species_list = _glossary_species(comparison, fields)
    if not species_list:
        return []
    localized = species_display_names([sp.id for sp in species_list], language)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for sp in species_list:
        english = (sp.name or '').strip()
        if not english:
            continue
        key = english.casefold()
        if key in seen:
            continue
        seen.add(key)
        local = (localized.get(sp.id) or english).strip() or english
        rows.append({
            'en': english,
            'name': local,
            'latin': (sp.name_latin or '').strip(),
        })
    rows.sort(key=lambda row: row['en'].casefold())
    return rows


def apply_species_names(text: str, glossary: list[dict[str, str]]) -> str:
    """Swap English common names for the official vernaculars."""
    if not text or not glossary:
        return text
    items = sorted(glossary, key=lambda row: len(row.get('en') or ''), reverse=True)
    out = text
    for row in items:
        english = (row.get('en') or '').strip()
        local = (row.get('name') or '').strip()
        if not english or not local or english.casefold() == local.casefold():
            continue
        for variant in _english_name_variants(english):
            pattern = re.compile(rf'(?<![A-Za-z]){re.escape(variant)}(?![A-Za-z])', re.I)
            out = pattern.sub(local, out)
    return out


_COMPOUND_NAME_SUFFIXES = (
    'lark', 'finch', 'warbler', 'thrush', 'pipit', 'wren', 'creeper',
    'shrike', 'sparrow', 'hawk', 'eagle', 'owl', 'duck', 'goose', 'gull',
    'tern', 'plover', 'sandpiper', 'woodpecker', 'flycatcher', 'bunting',
)


def _english_name_variants(name: str) -> list[str]:
    raw = (name or '').strip()
    if not raw:
        return []
    variants = [raw]
    collapsed = re.sub(r'[\s\-]+', '', raw)
    if collapsed and collapsed.casefold() != raw.casefold():
        variants.append(collapsed)
    spaced = re.sub(r'[\s\-]+', ' ', raw)
    if spaced and spaced.casefold() not in {item.casefold() for item in variants}:
        variants.append(spaced)
    lower = collapsed.casefold()
    for suffix in _COMPOUND_NAME_SUFFIXES:
        if lower.endswith(suffix) and len(collapsed) > len(suffix) + 2:
            head = collapsed[: len(collapsed) - len(suffix)]
            tail = collapsed[len(collapsed) - len(suffix):]
            split = f'{head} {tail}'
            if split.casefold() not in {item.casefold() for item in variants}:
                variants.append(split)
            hyphen = f'{head}-{tail}'
            if hyphen.casefold() not in {item.casefold() for item in variants}:
                variants.append(hyphen)
    variants.sort(key=len, reverse=True)
    return variants


def _glossary_species(comparison: SpeciesComparison, fields: dict[str, str] | None):
    from jizz.models import Species

    found = []
    seen: set[int] = set()

    def add(species):
        if species is None:
            return
        sid = getattr(species, 'id', None)
        if not sid or sid in seen:
            return
        seen.add(sid)
        found.append(species)

    add(getattr(comparison, 'species_1', None))
    add(getattr(comparison, 'species_2', None))
    blob = ' '.join((fields or source_fields(comparison)).values())
    blob_l = blob.casefold()
    family_ids = {
        getattr(sp, 'taxonomic_family_id', None)
        for sp in found
        if getattr(sp, 'taxonomic_family_id', None)
    }
    if not blob_l or not family_ids:
        return found
    extras = (
        Species.objects.filter(taxonomic_family_id__in=family_ids)
        .exclude(id__in=seen)
        .only('id', 'name', 'name_latin', 'name_nl')
    )
    for species in extras:
        english = (species.name or '').strip()
        if english and english.casefold() in blob_l:
            add(species)
    return found


def _apply_glossary(fields: dict[str, str], glossary: list[dict[str, str]]) -> dict[str, str]:
    if not glossary:
        return fields
    return {key: apply_species_names(value, glossary) for key, value in fields.items()}


def _glossary_prompt(glossary: list[dict[str, str]]) -> str:
    if not glossary:
        return (
            'Do not invent translations of English bird common names. '
            'Keep English common names and Latin names unchanged.\n'
        )
    lines = [
        'Use these official common names exactly. Do not invent a word-for-word translation of an English bird name:',
    ]
    for row in glossary:
        english = row.get('en') or ''
        local = row.get('name') or english
        latin = row.get('latin') or ''
        if latin:
            lines.append(f'- {english} ({latin}) → {local}')
        else:
            lines.append(f'- {english} → {local}')
    lines.append(
        'Inflect the official name for grammar if needed, but do not substitute a different name.'
    )
    return '\n'.join(lines) + '\n'


def localized_fields(
    comparison: SpeciesComparison,
    language: str,
    *,
    generate: bool = True,
) -> dict[str, str]:
    english = source_fields(comparison)
    lang = normalize_app_language(language) or DEFAULT_LANGUAGE
    glossary = species_name_glossary(comparison, lang, english) if lang != DEFAULT_LANGUAGE else []
    digest = source_hash(english, glossary)

    memo_attr = f'_i18n_{lang}_{digest}'
    memo = getattr(comparison, memo_attr, None)
    if isinstance(memo, dict):
        return memo

    if lang == DEFAULT_LANGUAGE:
        setattr(comparison, memo_attr, english)
        return english

    mem_key = _cache_key(comparison.pk, lang, digest)
    cached = cache.get(mem_key)
    if isinstance(cached, dict):
        payload = _apply_glossary(cached, glossary)
        setattr(comparison, memo_attr, payload)
        return payload

    row = _cached_row(comparison, lang)
    if row is not None and row.source_hash == digest and isinstance(row.fields, dict):
        payload = _apply_glossary(_merged_fields(english, row.fields), glossary)
        cache.set(mem_key, payload, timeout=CACHE_TIMEOUT)
        setattr(comparison, memo_attr, payload)
        return payload

    if not generate or not any(english.values()):
        setattr(comparison, memo_attr, english)
        return english

    translated = _translate_with_openai(english, lang, glossary=glossary)
    if translated is None:
        setattr(comparison, memo_attr, english)
        return english

    payload = _apply_glossary(_merged_fields(english, translated), glossary)
    _store_translation(comparison, lang, digest, payload)
    cache.set(mem_key, payload, timeout=CACHE_TIMEOUT)
    setattr(comparison, memo_attr, payload)
    return payload


def localize_comparison(
    comparison: SpeciesComparison | None,
    language: str,
    *,
    generate: bool = True,
) -> SpeciesComparison | LocalizedComparison | None:
    if comparison is None:
        return None
    lang = normalize_app_language(language) or DEFAULT_LANGUAGE
    if lang == DEFAULT_LANGUAGE:
        return comparison
    return LocalizedComparison(comparison, localized_fields(comparison, lang, generate=generate))


def _merged_fields(english: dict[str, str], translated: dict[str, Any]) -> dict[str, str]:
    out = dict(english)
    for field in TRANSLATABLE_FIELDS:
        text = str(translated.get(field) or '').strip()
        if text:
            out[field] = text
    return out


def _cached_row(comparison: SpeciesComparison, language: str) -> ComparisonTranslation | None:
    prefetch = getattr(comparison, '_prefetched_objects_cache', None)
    if prefetch and 'translations' in prefetch:
        for row in comparison.translations.all():
            if row.language == language:
                return row
        return None
    if not comparison.pk:
        return None
    return comparison.translations.filter(language=language).first()


def _store_translation(
    comparison: SpeciesComparison,
    language: str,
    digest: str,
    payload: dict[str, str],
) -> None:
    if not comparison.pk:
        return
    ComparisonTranslation.objects.update_or_create(
        comparison=comparison,
        language=language,
        defaults={
            'source_hash': digest,
            'fields': payload,
        },
    )


def _cache_key(comparison_id: Any, language: str, digest: str) -> str:
    return f'{CACHE_PREFIX}:{comparison_id}:{language}:{digest}'


def _translate_with_openai(
    fields: dict[str, str],
    language: str,
    *,
    glossary: list[dict[str, str]] | None = None,
) -> dict[str, str] | None:
    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        logger.debug('Comparison translation skipped: OPENAI_API_KEY not set')
        return None
    if language not in APP_LANGUAGES or language == DEFAULT_LANGUAGE:
        return None
    if cache.get(QUOTA_CACHE_KEY):
        logger.debug('Comparison translation skipped: OpenAI quota exhausted')
        return None
    language_name = LOCALE_NAMES.get(language, language)
    model = getattr(settings, 'COMPARISON_TRANSLATION_MODEL', None) or 'gpt-4o-mini'
    source = {key: value for key, value in fields.items() if value.strip()}
    if not source:
        return None
    name_block = _glossary_prompt(glossary or [])
    prompt = (
        f'Translate this Birdr species comparison from English into {language_name}.\n'
        'Return a JSON object with the same keys.\n'
        'Keep markdown syntax, headings, lists and emphasis unchanged; translate visible text only.\n'
        'Keep scientific (Latin) bird names unchanged. Keep the name Birdr untranslated.\n'
        f'{name_block}\n'
        f'{json.dumps(source, ensure_ascii=False)}'
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
                        'You translate Birdr species comparisons. Reply with JSON only, '
                        'using the same keys as the source object. '
                        'Use only the official common bird names supplied in the prompt; '
                        'never invent a literal translation of an English bird name.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.2,
            max_tokens=8000,
            response_format={'type': 'json_object'},
        )
        raw = (response.choices[0].message.content or '').strip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        out: dict[str, str] = {}
        translated_any = False
        for key, value in source.items():
            text = str(data.get(key) or '').strip()
            if text:
                out[key] = text
                translated_any = True
            else:
                out[key] = value
        if not translated_any:
            return None
        return out
    except Exception as exc:
        if _is_quota_error(exc):
            logger.warning('Comparison translation skipped: OpenAI out of credits')
            cache.set(QUOTA_CACHE_KEY, True, timeout=QUOTA_CACHE_TIMEOUT)
        else:
            logger.exception('Comparison translation failed (language=%s model=%s)', language, model)
        return None
