"""Public App Store / Google Play ratings for marketing pages."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from django.core.cache import cache

from jizz.store_version import BUNDLE_ID

_CACHE_KEY = 'marketing-store-ratings-v1'
_CACHE_TTL_SECONDS = 3600
_FETCH_TIMEOUT = 4
# A single outlier should not look like the public store score.
_MIN_PUBLIC_RATINGS = 5
_ITUNES_LOOKUP_URL = f'https://itunes.apple.com/lookup?bundleId={BUNDLE_ID}'
_PLAY_STORE_URL = (
    f'https://play.google.com/store/apps/details?id={BUNDLE_ID}&hl=en&gl=US'
)
_DS5_RE = re.compile(
    r"AF_initDataCallback\(\{key:\s*'ds:5'.*?data:(.*?), sideChannel:",
    re.S,
)
_PLAY_HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Birdr/1.0)'}


def write_review_url(app_store_url: str) -> str:
    """App Store URL that opens the write-review sheet when possible."""
    url = (app_store_url or '').strip()
    if not url:
        return ''
    if 'action=write-review' in url:
        return url
    joiner = '&' if '?' in url else '?'
    return f'{url}{joiner}action=write-review'


def get_store_ratings() -> dict[str, dict | None]:
    """Cached iOS/Android scores. Missing stores are ``None``."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return _public_ratings(cached)
    data = _public_ratings({
        'ios': _fetch_itunes_rating(),
        'android': _fetch_play_rating(),
    })
    cache.set(_CACHE_KEY, data, _CACHE_TTL_SECONDS)
    return data


def _public_ratings(data: dict) -> dict[str, dict | None]:
    return {
        'ios': _ensure_public(data.get('ios') if isinstance(data, dict) else None),
        'android': _ensure_public(data.get('android') if isinstance(data, dict) else None),
    }


def _ensure_public(row) -> dict | None:
    if not isinstance(row, dict):
        return None
    try:
        return rating_dict(row['score'], row['count'])
    except (KeyError, TypeError, ValueError):
        return None


def clear_store_ratings_cache() -> None:
    """Testing helper."""
    cache.delete(_CACHE_KEY)


def store_review_context() -> dict:
    ratings = get_store_ratings()
    return {
        'app_store_rating': ratings.get('ios'),
        'play_store_rating': ratings.get('android'),
    }


def rating_dict(score: float, count: int) -> dict | None:
    if count < _MIN_PUBLIC_RATINGS or not (0 < float(score) <= 5):
        return None
    value = round(float(score), 1)
    return {
        'score': value,
        'count': int(count),
        'score_label': f'{value:.1f}',
        'star_percent': int(round(value / 5 * 100)),
    }


def _fetch_itunes_rating() -> dict | None:
    try:
        with urllib.request.urlopen(_ITUNES_LOOKUP_URL, timeout=_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    results = data.get('results') or []
    if not results:
        return None
    row = results[0]
    score = row.get('averageUserRating')
    count = row.get('userRatingCount')
    try:
        return rating_dict(float(score), int(count))
    except (TypeError, ValueError):
        return None


def _fetch_play_rating() -> dict | None:
    req = urllib.request.Request(_PLAY_STORE_URL, headers=_PLAY_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except (OSError, urllib.error.URLError):
        return None
    return play_rating_from_html(html)


def play_rating_from_html(html: str) -> dict | None:
    match = _DS5_RE.search(html or '')
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    details = _nested(payload, (1, 2))
    if not isinstance(details, list):
        return None
    block = _nested(details, (51,))
    parsed = _rating_from_play_block(block)
    if parsed:
        return parsed
    for index, item in enumerate(details):
        if index == 51:
            continue
        parsed = _rating_from_play_block(item)
        if parsed:
            return parsed
    return None


def _rating_from_play_block(block) -> dict | None:
    score = _nested(block, (0, 1))
    count = _nested(block, (2, 1))
    try:
        return rating_dict(float(score), int(count))
    except (TypeError, ValueError):
        return None


def _nested(obj, path):
    cur = obj
    for key in path:
        if not isinstance(cur, (list, tuple)) or key < 0 or key >= len(cur):
            return None
        cur = cur[key]
    return cur
