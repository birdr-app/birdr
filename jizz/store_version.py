"""Fetch public store release labels (bird codenames) for soft-update prompts."""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request

BUNDLE_ID = 'pro.birdr.app'
_CACHE_TTL_SECONDS = 3600
_PLAY_STORE_URL = (
    f'https://play.google.com/store/apps/details?id={BUNDLE_ID}&hl=en'
)
_ITUNES_LOOKUP_URL = f'https://itunes.apple.com/lookup?bundleId={BUNDLE_ID}'
_PLAY_RELEASE_LABEL_RE = re.compile(r'"141":\[\[\["([^"]+)"\]\]')
_FETCH_TIMEOUT = 5
_cache: dict[str, object] = {'expires': 0.0, 'ios': None, 'android': None}
_refresh_lock = threading.Lock()
_refresh_thread: threading.Thread | None = None


def _fetch_itunes_release_label() -> str | None:
    try:
        with urllib.request.urlopen(_ITUNES_LOOKUP_URL, timeout=_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    results = data.get('results') or []
    if not results:
        return None
    version = results[0].get('version')
    if not isinstance(version, str):
        return None
    label = version.strip()
    return label or None


def _fetch_play_release_label() -> str | None:
    req = urllib.request.Request(
        _PLAY_STORE_URL,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; Birdr/1.0)'},
    )
    try:
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except (OSError, urllib.error.URLError):
        return None
    match = _PLAY_RELEASE_LABEL_RE.search(html)
    if not match:
        return None
    label = match.group(1).strip()
    return label or None


def _refresh() -> None:
    global _refresh_thread
    try:
        ios = _fetch_itunes_release_label()
        android = _fetch_play_release_label()
        # Keep the last known label when a store is unreachable.
        if ios is not None:
            _cache['ios'] = ios
        if android is not None:
            _cache['android'] = android
        _cache['expires'] = time.time() + _CACHE_TTL_SECONDS
    finally:
        with _refresh_lock:
            _refresh_thread = None


def get_store_release_labels() -> dict[str, str | None]:
    """Return cached iOS/Android store release labels without blocking the request.

    The store lookups can take tens of seconds from the server, so an expired cache
    is refreshed in a background thread (one at a time) and callers get the last
    known labels, or None before the first fetch has finished.
    """
    global _refresh_thread
    if time.time() >= float(_cache.get('expires') or 0):
        with _refresh_lock:
            if _refresh_thread is None:
                _refresh_thread = threading.Thread(
                    target=_refresh, name='store-release-labels', daemon=True
                )
                _refresh_thread.start()
    return {
        'ios': _cache.get('ios'),  # type: ignore[dict-item]
        'android': _cache.get('android'),  # type: ignore[dict-item]
    }


def wait_for_store_release_label_refresh(timeout: float | None = None) -> None:
    """Testing helper: block until a running background refresh has finished."""
    thread = _refresh_thread
    if thread is not None:
        thread.join(timeout)


def clear_store_release_label_cache() -> None:
    """Testing helper."""
    _cache['expires'] = 0.0
    _cache['ios'] = None
    _cache['android'] = None
