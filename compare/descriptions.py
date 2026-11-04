"""AI field-guide descriptions of single species, focused on telling them from lookalikes.

The model names other species only as [[<species id>|<English name>]] tokens. Translations
keep the tokens, and rendering swaps each one for the official local name linked to that
bird's page, so bird names are never translated literally.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from functools import lru_cache
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import close_old_connections
from django.db.models import Q

from compare.ai_service import (
    _TRAIT_CHAR_LIMITS,
    _TRAIT_ORDER,
    ComparisonGenerationError,
    NO_GROUNDING_MESSAGE,
    _clip,
    _friendly_openai_error,
    _is_quota_error,
    _trait_content,
    comparison_model_name,
    completion_token_kwargs,
    sampling_kwargs,
)
from compare.grounding import build_species_grounding
from compare.models import SpeciesComparison, SpeciesDescription, SpeciesDescriptionTranslation
from jizz.models import Species
from jizz.update_i18n import LOCALE_NAMES

logger = logging.getLogger(__name__)

PROMPT_VERSION = 'sd-v1'
MAX_SIMILAR = 12
TOKEN_RE = re.compile(r'\[\[(\d+)\|([^\[\]|]+)\]\]')

SYSTEM_PROMPT = (
    'You are a field-guide editor for Motmot, a bird identification app. You write the '
    'identification text for one species: what to look and listen for, and above all how to '
    'tell it from the species it is most easily confused with. Be precise and practical; '
    'prefer diagnostic, observable marks over life history. Base the text on the notes and '
    'paraphrase them in your own words. Do not invent measurements, songs or field marks. '
    'For lookalikes the notes do not cover, only state well-established differences and skip '
    'the lookalike when unsure. Name birds only with the [[id|name]] tokens you are given, '
    'copied exactly. Reply with a JSON object only.'
)


def description_model_name() -> str:
    return (getattr(settings, 'SPECIES_DESCRIPTION_AI_MODEL', None) or comparison_model_name()).strip()


def description_is_current(description: SpeciesDescription | None) -> bool:
    if description is None:
        return False
    return (
        description.ai_prompt_version == PROMPT_VERSION
        and description.ai_model == description_model_name()
    )


def species_token(species: Species) -> str:
    name = (species.name or species.name_latin or '').replace('[', '').replace(']', '').replace('|', ' ')
    return f'[[{species.id}|{name}]]'


@lru_cache(maxsize=1)
def _species_name_index() -> tuple[re.Pattern | None, dict[str, int]]:
    """One pattern matching every English species name, for spotting lookalikes in notes."""
    by_name: dict[str, int] = {}
    for pk, name in Species.objects.exclude(name='').values_list('id', 'name'):
        by_name.setdefault(name.casefold(), pk)
    if not by_name:
        return None, {}
    names = sorted(by_name, key=len, reverse=True)
    pattern = re.compile(r'(?<![\w-])(' + '|'.join(re.escape(n) for n in names) + r')(?![\w-])', re.I)
    return pattern, by_name


def _mentioned_species_ids(text: str) -> list[int]:
    pattern, by_name = _species_name_index()
    if pattern is None or not text:
        return []
    ids = []
    for match in pattern.finditer(text):
        pk = by_name.get(match.group(1).casefold())
        if pk and pk not in ids:
            ids.append(pk)
    return ids


def similar_candidates(species: Species, notes: str = '') -> list[tuple[Species, str]]:
    """Likely lookalikes, most relevant first: quiz mix-ups, comparisons, notes, same genus."""
    from jizz.quiz_mistake_stats import get_confused_partners_for_species

    reasons: dict[int, str] = {}

    def add(pk: int | None, reason: str) -> None:
        if pk and pk != species.id and pk not in reasons:
            reasons[pk] = reason

    for row in get_confused_partners_for_species(species.id, limit=8):
        add(row.get('species_id'), 'often mixed up with it in Motmot quizzes')
    pairs = SpeciesComparison.objects.filter(
        Q(species_1=species) | Q(species_2=species),
        comparison_type='species',
    ).values_list('species_1_id', 'species_2_id')
    for a, b in pairs:
        add(b if a == species.id else a, 'has a Motmot comparison with it')
    for pk in _mentioned_species_ids(notes):
        add(pk, 'named in the notes')
    genus = (species.name_latin or '').split(' ')[0]
    if genus:
        same_genus = (
            Species.objects.filter(name_latin__startswith=f'{genus} ')
            .exclude(id=species.id)
            .values_list('id', flat=True)[:MAX_SIMILAR]
        )
        for pk in same_genus:
            add(pk, 'same genus')
    ids = list(reasons)[:MAX_SIMILAR]
    by_id = Species.objects.in_bulk(ids)
    return [(by_id[pk], reasons[pk]) for pk in ids if pk in by_id]


def _notes_block(traits: dict[str, Any]) -> str:
    parts = []
    for key in _TRAIT_ORDER:
        content = _trait_content(traits.get(key)).strip()
        if content:
            parts.append(f'### {key.replace("_", " ").title()}\n{_clip(content, _TRAIT_CHAR_LIMITS.get(key, 1500))}')
    return '\n\n'.join(parts)


def build_prompt(species: Species, notes: str, candidates: list[tuple[Species, str]]) -> str:
    family = species.taxonomic_family
    family_line = f'Family: {family.name_en or family.name_latin} ({family.name_latin})\n' if family else ''
    if candidates:
        lookalikes = '\n'.join(
            f'- {species_token(other)} ({other.name_latin}): {reason}'
            for other, reason in candidates
        )
    else:
        lookalikes = '- (none)'
    return (
        f'Species: {species.name} ({species.name_latin})\n'
        f'{family_line}'
        f'Write this species itself as {species_token(species)}.\n\n'
        'Possible lookalikes. Write each exactly as its token; never write a bird name '
        f'without its token, and do not name birds that are not listed:\n{lookalikes}\n\n'
        f'Notes:\n{notes}\n\n'
        'Return JSON with these keys:\n'
        '- "summary": one or two sentences, at most 160 characters, with the marks that '
        'identify it at a glance. Use only the token of this species itself.\n'
        '- "identification": Markdown, 120 to 250 words in 2 to 4 short paragraphs. Start with '
        'the most distinctive features. Cover shape and size, plumage (say which sex, age and '
        'season when the notes do), flight, and voice, behaviour or habitat only where they '
        'help identification.\n'
        '- "similar_species": Markdown bullet list, one bullet per lookalike you can separate '
        'with confidence, most confusable first, in the form "- **[[id|name]]**: the decisive '
        'differences". At most 6 bullets. Empty string when there are none.\n'
    )


def _chat_json(model: str, system: str, prompt: str, *, max_tokens: int, temperature: float) -> dict:
    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        raise ComparisonGenerationError('Descriptions cannot be generated because the AI service is not configured.')
    from openai import OpenAI

    try:
        response = OpenAI(api_key=api_key, timeout=120.0).chat.completions.create(
            model=model,
            messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            **sampling_kwargs(model, temperature=temperature),
            **completion_token_kwargs(model, max_tokens),
        )
    except Exception as exc:
        logger.exception('OpenAI species description request failed (model=%s)', model)
        raise ComparisonGenerationError(_friendly_openai_error(exc)) from exc
    try:
        data = json.loads(response.choices[0].message.content or '')
    except ValueError as exc:
        raise ComparisonGenerationError('The model did not return valid JSON.') from exc
    return data if isinstance(data, dict) else {}


def _clean_tokens(text: str, allowed: set[int]) -> str:
    """Unlisted species ids lose their link but keep the name."""
    return TOKEN_RE.sub(lambda m: m.group(0) if int(m.group(1)) in allowed else m.group(2), text)


def generate_species_description(
    species: Species,
    *,
    force: bool = False,
    scrape: bool = True,
) -> SpeciesDescription:
    existing = SpeciesDescription.objects.filter(species=species).first()
    if existing and not force and description_is_current(existing):
        return existing
    grounding = build_species_grounding(species, scrape_botw=scrape, fetch_remote=scrape)
    if not grounding.is_grounded:
        raise ComparisonGenerationError(NO_GROUNDING_MESSAGE)
    notes = _notes_block(grounding.traits)
    candidates = similar_candidates(species, notes)
    model = description_model_name()
    data = _chat_json(
        model,
        SYSTEM_PROMPT,
        build_prompt(species, notes, candidates),
        max_tokens=2500,
        temperature=0.3,
    )
    allowed = {species.id, *(other.id for other, _ in candidates)}
    fields = {key: _clean_tokens(str(data.get(key) or '').strip(), allowed) for key in SpeciesDescription.TEXT_FIELDS}
    if not fields['summary'] or not fields['identification']:
        raise ComparisonGenerationError(f'No description generated for {species.name}')
    description, _ = SpeciesDescription.objects.update_or_create(
        species=species,
        defaults={
            **fields,
            'ai_model': model,
            'ai_prompt_version': PROMPT_VERSION,
            'sources_used': grounding.sources_used,
        },
    )
    return description


def english_fields(description: SpeciesDescription) -> dict[str, str]:
    return {key: getattr(description, key) or '' for key in SpeciesDescription.TEXT_FIELDS}


def source_hash(fields: dict[str, str]) -> str:
    blob = json.dumps(fields, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()[:32]


def _tokens(text: str) -> list[str]:
    return sorted(m.group(1) for m in TOKEN_RE.finditer(text or ''))


def translate_description(description: SpeciesDescription, language: str) -> SpeciesDescriptionTranslation | None:
    """Translate into one language, unless a translation of this exact text exists."""
    english = english_fields(description)
    digest = source_hash(english)
    row = description.translations.filter(language=language).first()
    if row and row.source_hash == digest:
        return row
    model = getattr(settings, 'COMPARISON_TRANSLATION_MODEL', None) or 'gpt-4o-mini'
    source = {key: value for key, value in english.items() if value.strip()}
    prompt = (
        f'Translate this Motmot bird identification text from English into '
        f'{LOCALE_NAMES.get(language, language)}. Return a JSON object with the same keys.\n'
        'Keep markdown syntax unchanged. Copy every [[id|name]] token exactly as it is, '
        'English name included: it is replaced by the official local bird name later. '
        'Keep scientific names and the name Motmot unchanged.\n\n'
        f'{json.dumps(source, ensure_ascii=False)}'
    )
    data = _chat_json(
        model,
        'You translate bird identification texts. Reply with JSON only, using the keys of the source object.',
        prompt,
        max_tokens=4000,
        temperature=0.2,
    )
    translated = {}
    for key, value in source.items():
        text = str(data.get(key) or '').strip()
        # A lost or altered token would drop a link or a name, so keep English instead.
        translated[key] = text if text and _tokens(text) == _tokens(value) else value
    row, _ = SpeciesDescriptionTranslation.objects.update_or_create(
        description=description,
        language=language,
        defaults={'source_hash': digest, 'fields': translated},
    )
    return row


def localized_fields(description: SpeciesDescription, language: str) -> dict[str, str]:
    """Stored translation when it matches the current English text, else English."""
    english = english_fields(description)
    if language == 'en':
        return english
    row = description.translations.filter(language=language).first()
    if row is None or row.source_hash != source_hash(english):
        return english
    return {key: row.fields.get(key) or english[key] for key in english}


def _markdown_escape(text: str) -> str:
    return re.sub(r'([\\\[\]*_`])', r'\\\1', text)


def render_tokens(text: str, locale: str, *, self_id: int | None = None, links: bool = True) -> str:
    """Swap tokens for local names; with links, as markdown links to public bird pages."""
    from jizz.marketing.i18n import localize_path
    from jizz.marketing.local_names import species_display_names
    from jizz.marketing.pages import public_species_ids

    ids = {int(m.group(1)) for m in TOKEN_RE.finditer(text or '')}
    if not ids:
        return text or ''
    names = species_display_names(ids, locale)
    slugs = dict(Species.objects.filter(id__in=ids).values_list('id', 'slug'))
    public = set(public_species_ids()) if links else set()

    def replace(match: re.Match) -> str:
        pk = int(match.group(1))
        name = names.get(pk) or match.group(2)
        if not links:
            return name
        if pk != self_id and pk in public and slugs.get(pk):
            url = localize_path(f'/site/birds/{slugs[pk]}/', locale)
            return f'[{_markdown_escape(name)}]({url})'
        return _markdown_escape(name)

    return TOKEN_RE.sub(replace, text)


def description_context(species: Species, locale: str) -> dict:
    """The text in this locale for the species page, with lookalikes linked by local name."""
    from jizz.marketing.html import markdown_to_safe_html

    description = SpeciesDescription.objects.filter(species=species).first()
    if description is None:
        return {}
    fields = localized_fields(description, locale)

    def html(text: str) -> str:
        return markdown_to_safe_html(render_tokens(text, locale, self_id=species.id))

    return {
        'ai_summary': render_tokens(fields['summary'], locale, links=False),
        'ai_identification_html': html(fields['identification']),
        'ai_similar_html': html(_with_comparison_links(fields['similar_species'], species, locale)),
    }


_LOOKALIKE_BULLET_RE = re.compile(r'^(\s*[-*]\s+\*\*\[\[(\d+)\|[^\]]+\]\]\*\*.*?)\s*$')


def _compared_species(species: Species, ids: set[int]) -> dict[int, str]:
    """Lookalike id -> compare page path, for pairs with a written comparison."""
    from compare.models import CommunityComparison
    from jizz.marketing.slugs import compare_pair_slug

    others: set[int] = set()
    ai_pairs = (
        SpeciesComparison.objects.filter(comparison_type='species')
        .filter(
            Q(species_1=species, species_2_id__in=ids) | Q(species_2=species, species_1_id__in=ids)
        )
        .exclude(Q(summary='') | Q(summary__isnull=True))
        .values_list('species_1_id', 'species_2_id')
    )
    community_pairs = CommunityComparison.objects.filter(published=True).filter(
        Q(species_low=species, species_high_id__in=ids) | Q(species_high=species, species_low_id__in=ids)
    ).values_list('species_low_id', 'species_high_id')
    for a, b in [*ai_pairs, *community_pairs]:
        others.add(b if a == species.id else a)
    slugs = dict(Species.objects.filter(id__in=others | {species.id}).values_list('id', 'slug'))
    paths = {}
    for other in others:
        if not slugs.get(other) or not species.slug:
            continue
        low, high = (species.id, other) if species.id < other else (other, species.id)
        paths[other] = f'/site/compare/{compare_pair_slug(slugs[low], slugs[high])}/'
    return paths


def _with_comparison_links(markdown: str, species: Species, locale: str) -> str:
    """End each lookalike bullet with a link to its comparison page, when one is written."""
    from jizz.marketing.i18n import localize_path, translate

    matches = [_LOOKALIKE_BULLET_RE.match(line) for line in (markdown or '').splitlines()]
    ids = {int(m.group(2)) for m in matches if m}
    paths = _compared_species(species, ids) if ids else {}
    if not paths:
        return markdown
    label = _markdown_escape(translate('How to tell them apart', locale))
    lines = []
    for line, match in zip(markdown.splitlines(), matches):
        path = paths.get(int(match.group(2))) if match else None
        if path:
            line = f'{match.group(1)} → [{label}]({localize_path(path, locale)})'
        lines.append(line)
    return '\n'.join(lines)


# On-demand generation from the species page: a background job, polled by the page.
LOCK_TIMEOUT = 60 * 10
ERROR_TIMEOUT = 60 * 10
UNAVAILABLE_TIMEOUT = 60 * 60 * 24 * 7
HOURLY_LIMIT = 20


def _lock_key(species_id: int) -> str:
    return f'species-description-lock:{species_id}'


def _error_key(species_id: int) -> str:
    return f'species-description-error:{species_id}'


def generation_unavailable(species_id: int) -> bool:
    """True when a recent attempt found no source notes for this species."""
    return cache.get(_error_key(species_id)) == 'unavailable'


def generation_status(species: Species) -> dict:
    if cache.get(_lock_key(species.id)):
        return {'pending': True}
    if SpeciesDescription.objects.filter(species=species).exists():
        return {'ready': True}
    error = cache.get(_error_key(species.id))
    if error:
        return {'error': error}
    return {'missing': True}


def take_generation_slot(user) -> bool:
    """Count one AI generation for this user; False once the hourly limit is reached."""
    if user.is_staff:
        return True
    key = f'ai-generations:{user.pk}:{int(time.time() // 3600)}'
    cache.add(key, 0, 3600)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 3600)
        count = 1
    return count <= HOURLY_LIMIT


def start_generation(species: Species, language: str) -> dict:
    """Start writing the text unless someone else already is."""
    if not cache.add(_lock_key(species.id), True, LOCK_TIMEOUT):
        return {'pending': True}
    cache.delete(_error_key(species.id))
    _run_in_background(_generation_job, species.id, language)
    return {'pending': True}


def _run_in_background(func, *args) -> None:
    def run():
        try:
            func(*args)
        finally:
            close_old_connections()

    threading.Thread(target=run, daemon=True).start()


def _generation_job(species_id: int, language: str) -> None:
    description = None
    try:
        description = generate_species_description(Species.objects.get(pk=species_id))
        # The visitor's language first, so the reloaded page is in their language.
        if language != 'en':
            translate_description(description, language)
    except ComparisonGenerationError as exc:
        if description is None:
            if str(exc) == NO_GROUNDING_MESSAGE:
                error, timeout = 'unavailable', UNAVAILABLE_TIMEOUT
            else:
                error, timeout = ('quota' if _is_quota_error(exc) else 'failed'), ERROR_TIMEOUT
            cache.set(_error_key(species_id), error, timeout)
    except Exception:
        logger.exception('Species description job failed for species %s', species_id)
        cache.set(_error_key(species_id), 'failed', ERROR_TIMEOUT)
    finally:
        cache.delete(_lock_key(species_id))
    if description is None:
        return
    for other in LOCALE_NAMES:
        if other == language:
            continue
        try:
            translate_description(description, other)
        except ComparisonGenerationError:
            logger.warning('Stopped translating the %s description', description.species)
            return
