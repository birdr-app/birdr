"""Localize Birdr updates into the selected app language, with a durable cache."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from django.conf import settings
from django.core.cache import cache

from jizz.app_languages import APP_LANGUAGES, normalize_app_language
from jizz.models import Update, UpdateTranslation, UserProfile

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = 'en'
CACHE_PREFIX = 'update-i18n-v1'
CACHE_TIMEOUT = 60 * 60 * 24 * 30
QUOTA_CACHE_KEY = 'update-i18n-quota-exhausted'
QUOTA_CACHE_TIMEOUT = 60 * 10

LOCALE_NAMES = {
    'nl': 'Dutch',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt-BR': 'Brazilian Portuguese',
    'ja': 'Japanese',
}


def resolve_app_language(*, user=None, accept_language: str = '', requested: str = '') -> str:
    """Pick a supported app UI language from query, profile.app_language, then Accept-Language.

    Bird-name `UserProfile.language` is ignored: it is not the app UI locale.
    """
    candidates: list[str] = [requested]
    if user is not None and getattr(user, 'is_authenticated', False):
        try:
            profile = user.profile
            candidates.append(getattr(profile, 'app_language', '') or '')
        except UserProfile.DoesNotExist:
            pass
    candidates.extend(_accept_language_tags(accept_language))
    for raw in candidates:
        code = normalize_app_language(raw)
        if code:
            return code
    return DEFAULT_LANGUAGE


def resolve_language(user, accept_language: str = '') -> str:
    """Language for update emails and API when no explicit query param is given."""
    return resolve_app_language(user=user, accept_language=accept_language)


def resolve_request_language(request) -> str:
    if request is None:
        return DEFAULT_LANGUAGE
    params = getattr(request, 'query_params', None)
    if params is None:
        params = getattr(request, 'GET', {})
    requested = (params.get('app_language') or params.get('language') or '').strip()
    user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
    accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '') if hasattr(request, 'META') else ''
    return resolve_app_language(user=user, accept_language=accept, requested=requested)


def localized_title(update: Update, language: str) -> str:
    return localized_copy(update, language)['title']


def localized_body(update: Update, language: str) -> str:
    """Return a Quill JSON string for the localized body."""
    html = localized_copy(update, language)['html']
    return json.dumps({'delta': '', 'html': html})


def localized_copy(update: Update, language: str) -> dict[str, str]:
    lang = normalize_app_language(language) or DEFAULT_LANGUAGE
    title_en = (update.title_en or '').strip()
    html_en = _english_html(update)
    digest = source_hash(title_en, html_en)
    english = {'title': title_en or update.title_en, 'html': html_en}

    memo_attr = f'_i18n_{lang}_{digest}'
    memo = getattr(update, memo_attr, None)
    if isinstance(memo, dict):
        return memo

    if lang == DEFAULT_LANGUAGE:
        setattr(update, memo_attr, english)
        return english

    if lang == 'nl':
        editorial = _editorial_dutch(update)
        if editorial:
            setattr(update, memo_attr, editorial)
            return editorial

    mem_key = _cache_key(update.pk, lang, digest)
    cached = cache.get(mem_key)
    if isinstance(cached, dict) and cached.get('title') is not None:
        setattr(update, memo_attr, cached)
        return cached

    row = _cached_row(update, lang)
    if row is not None and row.source_hash == digest and row.title:
        payload = {'title': row.title, 'html': row.body_html or ''}
        cache.set(mem_key, payload, timeout=CACHE_TIMEOUT)
        setattr(update, memo_attr, payload)
        return payload

    translated = _translate_with_openai(title_en, html_en, lang)
    if translated is None:
        # Credits / API failure: show English, never Dutch editorial, and do not cache.
        setattr(update, memo_attr, english)
        return english

    title, html = translated
    payload = {'title': title[:200], 'html': html}
    _store_translation(update, lang, digest, payload)
    cache.set(mem_key, payload, timeout=CACHE_TIMEOUT)
    setattr(update, memo_attr, payload)
    return payload


def source_hash(title: str, html: str) -> str:
    blob = f'{title}\n{html}'.encode('utf-8')
    return hashlib.sha256(blob).hexdigest()[:32]


def _english_html(update: Update) -> str:
    from jizz.update_emails import quill_value_to_html

    return quill_value_to_html(update.body_en)


def _editorial_dutch(update: Update) -> dict[str, str] | None:
    from jizz.update_emails import quill_value_to_html

    title = (update.title_nl or '').strip()
    html = quill_value_to_html(update.body_nl)
    if title and html:
        return {'title': title, 'html': html}
    return None


def _cached_row(update: Update, language: str) -> UpdateTranslation | None:
    prefetch = getattr(update, '_prefetched_objects_cache', None)
    if prefetch and 'translations' in prefetch:
        for row in update.translations.all():
            if row.language == language:
                return row
        return None
    if not update.pk:
        return None
    return update.translations.filter(language=language).first()


def _store_translation(update: Update, language: str, digest: str, payload: dict[str, str]) -> None:
    if not update.pk:
        return
    UpdateTranslation.objects.update_or_create(
        update=update,
        language=language,
        defaults={
            'source_hash': digest,
            'title': payload['title'],
            'body_html': payload['html'],
        },
    )


def _cache_key(update_id: Any, language: str, digest: str) -> str:
    return f'{CACHE_PREFIX}:{update_id}:{language}:{digest}'


def _accept_language_tags(header: str) -> list[str]:
    if not header:
        return []
    parts: list[tuple[float, str]] = []
    for item in header.split(','):
        raw = item.strip()
        if not raw:
            continue
        tag, _, rest = raw.partition(';')
        q = 1.0
        match = re.search(r'q\s*=\s*([0-9.]+)', rest, re.I)
        if match:
            try:
                q = float(match.group(1))
            except ValueError:
                q = 0.0
        parts.append((q, tag.strip()))
    parts.sort(key=lambda row: row[0], reverse=True)
    return [tag for _, tag in parts]


def _is_quota_error(exc: BaseException) -> bool:
    parts = [str(exc)]
    cause = getattr(exc, '__cause__', None)
    if cause is not None:
        parts.append(str(cause))
    text = ' '.join(parts).lower()
    return any(
        token in text
        for token in (
            'insufficient_quota',
            'credit_balance_exhausted',
            'no credits remaining',
            'exceeded your current quota',
            'out of credits',
        )
    )


def _translate_with_openai(title: str, html: str, language: str) -> tuple[str, str] | None:
    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        logger.debug('Update translation skipped: OPENAI_API_KEY not set')
        return None
    if language not in APP_LANGUAGES or language == DEFAULT_LANGUAGE:
        return None
    if cache.get(QUOTA_CACHE_KEY):
        logger.debug('Update translation skipped: OpenAI quota exhausted')
        return None
    language_name = LOCALE_NAMES.get(language, language)
    model = getattr(settings, 'UPDATE_TRANSLATION_MODEL', None) or 'gpt-4o-mini'
    prompt = (
        f'Translate this Birdr product update into {language_name}.\n'
        'Return a JSON object with keys "title" and "html".\n'
        'Keep HTML tags, attributes and URLs unchanged; translate visible text only.\n'
        'Keep the name Birdr untranslated. Keep scientific bird names in Latin.\n\n'
        f'Title:\n{title}\n\n'
        f'HTML:\n{html}'
    )
    try:
        from openai import OpenAI
    except ImportError:
        logger.exception('openai package is not installed')
        return None
    try:
        client = OpenAI(api_key=api_key, timeout=45.0)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You translate Birdr app updates. Reply with JSON only: '
                        '{"title": "...", "html": "..."}.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.2,
            max_tokens=2500,
            response_format={'type': 'json_object'},
        )
        raw = (response.choices[0].message.content or '').strip()
        data = json.loads(raw)
        out_title = str(data.get('title') or '').strip()
        out_html = str(data.get('html') or '').strip()
        if not out_title:
            return None
        return out_title, out_html or html
    except Exception as exc:
        if _is_quota_error(exc):
            logger.warning('Update translation skipped: OpenAI out of credits')
            cache.set(QUOTA_CACHE_KEY, True, timeout=QUOTA_CACHE_TIMEOUT)
        else:
            logger.exception('Update translation failed (language=%s model=%s)', language, model)
        return None
