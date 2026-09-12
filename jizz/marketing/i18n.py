"""Marketing-site locales — same UI languages as the Birdr app."""

from __future__ import annotations

import re
from contextvars import ContextVar
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

from jizz.app_languages import APP_LANGUAGES, normalize_app_language

DEFAULT_LOCALE = 'en'
MARKETING_LOCALES = ('en', 'nl', 'es', 'fr', 'de', 'it', 'pt-BR', 'ja')
LOCALE_LABELS = {
    'en': 'English',
    'nl': 'Nederlands',
    'es': 'Español',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
    'pt-BR': 'Português (Brasil)',
    'ja': '日本語',
}
OG_LOCALES = {
    'en': 'en_US',
    'nl': 'nl_NL',
    'es': 'es_ES',
    'fr': 'fr_FR',
    'de': 'de_DE',
    'it': 'it_IT',
    'pt-BR': 'pt_BR',
    'ja': 'ja_JP',
}
STORE_BADGE = {
    'en': ('en-us', 'en_us', 'en'),
    'nl': ('nl-nl', 'nl_nl', 'nl'),
    'es': ('es-es', 'es_es', 'es'),
    'fr': ('fr-fr', 'fr_fr', 'fr'),
    'de': ('de-de', 'de_de', 'de'),
    'it': ('it-it', 'it_it', 'it'),
    'pt-BR': ('pt-br', 'pt_br', 'pt_br'),
    'ja': ('ja-jp', 'ja_jp', 'ja'),
}
HTML_LANG = {
    'en': 'en',
    'nl': 'nl',
    'es': 'es',
    'fr': 'fr',
    'de': 'de',
    'it': 'it',
    'pt-BR': 'pt-BR',
    'ja': 'ja',
}

assert frozenset(MARKETING_LOCALES) == APP_LANGUAGES

_LOCALE_ALT = '|'.join(re.escape(code) for code in MARKETING_LOCALES if code != DEFAULT_LOCALE)
LOCALE_PATH_RE = re.compile(rf'^/(?P<locale>{_LOCALE_ALT})(?P<rest>/site(?:/.*)?)?$')
EN_PREFIX_RE = re.compile(r'^/en(?P<rest>/site(?:/.*)?)?$')

_SKIP_TRANSLATE_KEYS = frozenset({
    'cta_href',
    'src',
    'width',
    'height',
    'show_countries',
})

_current_locale: ContextVar[str] = ContextVar('marketing_locale', default=DEFAULT_LOCALE)


def is_marketing_locale(value: str | None) -> bool:
    return bool(value) and value in MARKETING_LOCALES


def get_locale() -> str:
    return _current_locale.get()


def set_locale(locale: str):
    code = locale if is_marketing_locale(locale) else DEFAULT_LOCALE
    return _current_locale.set(code)


def reset_locale(token) -> None:
    _current_locale.reset(token)


def parse_locale_prefix(path: str) -> tuple[str, str | None]:
    """Return (locale, remainder_or_None). remainder is the /site/... path to route."""
    raw = path or ''
    en_match = EN_PREFIX_RE.match(raw)
    if en_match:
        return DEFAULT_LOCALE, en_match.group('rest') or '/site/'
    match = LOCALE_PATH_RE.match(raw)
    if not match:
        return DEFAULT_LOCALE, None
    rest = match.group('rest') or '/site/'
    return match.group('locale'), rest


def localize_path(path: str, locale: str | None = None) -> str:
    """Prefix a /site/... path with the locale, except English (unprefixed)."""
    loc = locale if is_marketing_locale(locale) else get_locale()
    value = path or ''
    if not value.startswith('/site/'):
        return value
    stripped = strip_locale_prefix(value)
    if loc == DEFAULT_LOCALE:
        return stripped
    return f'/{loc}{stripped}'


def strip_locale_prefix(path: str) -> str:
    raw = path or ''
    en_match = EN_PREFIX_RE.match(raw)
    if en_match:
        return en_match.group('rest') or '/site/'
    match = LOCALE_PATH_RE.match(raw)
    if match:
        return match.group('rest') or '/site/'
    return raw


def alternate_paths(path: str) -> list[dict[str, str]]:
    logical = strip_locale_prefix(path) or '/site/'
    if not logical.startswith('/site/'):
        logical = '/site/'
    current = get_locale()
    rows = []
    for code in MARKETING_LOCALES:
        href = localize_path(logical, code)
        rows.append({
            'code': code,
            'hreflang': code,
            'label': LOCALE_LABELS[code],
            'url': href,
            'current': code == current,
        })
    return rows


def store_badge_urls(locale: str | None = None) -> tuple[str, str]:
    loc = locale if is_marketing_locale(locale) else get_locale()
    apple, play_intl, play_code = STORE_BADGE.get(loc, STORE_BADGE['en'])
    apple_url = (
        'https://tools.applemediaservices.com/api/badges/download-on-the-app-store/'
        f'black/{apple}?size=250x83'
    )
    play_url = (
        'https://play.google.com/intl/'
        f'{play_intl}/badges/static/images/badges/{play_code}_badge_web_generic.png'
    )
    return apple_url, play_url


@lru_cache(maxsize=1)
def _catalogs() -> dict[str, dict[str, str]]:
    from jizz.marketing.catalogs import CATALOGS
    return CATALOGS


def lookup(message: str, locale: str | None = None) -> str:
    if not message:
        return message
    loc = locale if is_marketing_locale(locale) else get_locale()
    if loc == DEFAULT_LOCALE:
        return message
    return _catalogs().get(loc, {}).get(message, message)


def is_catalog_message(message: str) -> bool:
    """True when ``message`` is marketing UI copy, not a proper name."""
    if not message:
        return False
    return any(message in locale_map for locale_map in _catalogs().values())


def translate_nav_label(message: str, locale: str | None = None) -> str:
    """Translate breadcrumbs that are UI strings; leave species/country names alone."""
    if is_catalog_message(message):
        return translate(message, locale)
    return message


def translate(message: str, locale: str | None = None, **kwargs) -> str:
    text = lookup(message, locale)
    has_html = '<' in text
    if kwargs:
        values = (
            {key: conditional_escape(value) for key, value in kwargs.items()}
            if has_html
            else kwargs
        )
        try:
            text = text.format(**values)
        except (KeyError, IndexError, ValueError):
            pass
    if has_html:
        return mark_safe(text)
    return text


def translate_copy(obj: Any, locale: str | None = None) -> Any:
    """Recursively translate strings; leave URLs, numbers and known keys alone."""
    loc = locale if is_marketing_locale(locale) else get_locale()
    if isinstance(obj, str):
        if obj.startswith('/') or obj.startswith('http'):
            return localize_path(obj, loc) if obj.startswith('/site/') else obj
        return lookup(obj, loc)
    if isinstance(obj, tuple):
        return tuple(translate_copy(item, loc) for item in obj)
    if isinstance(obj, list):
        return [translate_copy(item, loc) for item in obj]
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if key in _SKIP_TRANSLATE_KEYS:
                out[key] = value
            else:
                out[key] = translate_copy(value, loc)
        return out
    return obj


def html_lang(locale: str | None = None) -> str:
    loc = locale if is_marketing_locale(locale) else get_locale()
    return HTML_LANG.get(loc, 'en')


def og_locale(locale: str | None = None) -> str:
    loc = locale if is_marketing_locale(locale) else get_locale()
    return OG_LOCALES.get(loc, 'en_US')


def js_messages(locale: str | None = None) -> dict[str, str]:
    loc = locale if is_marketing_locale(locale) else get_locale()
    keys = (
        'Log in',
        'Register',
        'Forgot password',
        "Don't have an account?",
        'Already have an account?',
        'Password must be at least 8 characters.',
        'Authentication failed. Please try again.',
        'Failed to send password reset email',
        'If an account with this email exists, a password reset link has been sent.',
        'Account',
        'Images',
        'Videos',
        'Sounds',
        'No images available',
        'No videos available',
        'No sounds available',
        'Loading…',
        'Could not load media. Try again later.',
        'Media',
        'Video',
        'Could not generate the comparison.',
        'A handbook comparison is not available yet.',
        'Updated {date}',
        '{left} vs {right}',
    )
    return {key: lookup(key, loc) for key in keys}


def locale_from_request(request) -> str:
    code = getattr(request, 'marketing_locale', None)
    if is_marketing_locale(code):
        return code
    return DEFAULT_LOCALE


def login_next_path(request, fallback: str) -> str:
    path = getattr(request, 'path', '') or fallback
    return quote(path)


def normalize_marketing_locale(value: str | None) -> str:
    return normalize_app_language(value) or DEFAULT_LOCALE
