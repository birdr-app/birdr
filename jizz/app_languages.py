"""Supported app UI languages (BCP-47). Distinct from bird-name `UserProfile.language`."""

APP_LANGUAGES = frozenset({'en', 'nl', 'es', 'fr', 'de', 'it', 'pt-BR', 'ja'})

# App UI locale -> SpeciesName.language_id (underscores, e.g. pt_BR).
SPECIES_LANGUAGE_FROM_APP = {
    'en': 'en',
    'nl': 'nl',
    'es': 'es',
    'fr': 'fr',
    'de': 'de',
    'it': 'it',
    'pt-BR': 'pt_BR',
    'ja': 'ja',
}


def normalize_app_language(value: str | None) -> str:
    """Return a supported app locale, or '' if unset/unknown."""
    raw = (value or '').strip()
    if not raw:
        return ''
    if raw in APP_LANGUAGES:
        return raw
    lower = raw.lower().replace('_', '-')
    if lower.startswith('pt'):
        return 'pt-BR'
    prefix = lower.split('-')[0]
    if prefix in APP_LANGUAGES:
        return prefix
    return ''


def species_language_from_app_language(value: str | None) -> str:
    """Map an app UI locale onto the bird-name language code."""
    code = normalize_app_language(value)
    return SPECIES_LANGUAGE_FROM_APP.get(code, 'en')
