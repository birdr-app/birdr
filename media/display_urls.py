"""Rewrite stored media URLs to a display-sized derivative before serving clients.

Wikimedia originals become a standard Commons thumb. iNaturalist `original`
photos become `medium` (typically 500px) so quiz clients do not download
1024px `large` or multi-megapixel camera files.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from django.conf import settings

from media.wikimedia_urls import wikimedia_display_url, wikimedia_video_playback_url

# Largest first. Only rewrite down, never up (a stored medium stays medium).
INATURALIST_SIZE_RANK = ('original', 'large', 'medium', 'small', 'thumb', 'square')
_INAT_PATH_RE = re.compile(
    r'(?i)^(/photos/\d+/)(original|large|medium|small|thumb|square)(\.(?:jpe?g|png|gif|webp))$'
)


def _inaturalist_host(host: str) -> bool:
    h = (host or '').lower()
    return 'inaturalist' in h or 'inaturalist-open-data' in h


def inaturalist_display_url(url: str | None, size: str | None = None) -> str | None:
    """Rewrite iNaturalist photo URLs to `size` (default: medium). Non-iNat URLs unchanged."""
    if not url:
        return url
    if size is None:
        size = (getattr(settings, 'MEDIA_INATURALIST_DISPLAY_SIZE', None) or 'medium').lower()
    else:
        size = size.lower()
    if size not in INATURALIST_SIZE_RANK:
        size = 'medium'

    parsed = urlparse(url)
    if not _inaturalist_host(parsed.netloc):
        return url
    match = _INAT_PATH_RE.match(parsed.path or '')
    if not match:
        return url

    prefix, current, ext = match.groups()
    current = current.lower()
    target_idx = INATURALIST_SIZE_RANK.index(size)
    current_idx = INATURALIST_SIZE_RANK.index(current)
    if current_idx >= target_idx:
        return url

    new_path = f'{prefix}{size}{ext}'
    return urlunparse((parsed.scheme, parsed.netloc, new_path, parsed.params, parsed.query, parsed.fragment))


def media_display_url(url: str | None) -> str | None:
    """Client URL for quiz/API/marketing (Wikimedia thumb, iNat medium, Commons 480p video).

    Xeno-Canto audio is not rewritten here: /download cannot be turned into an
    MP3 without the XC sono hash. Playback URLs are stored on Media.url
    (scraper + ``backfill_xeno_canto_mp3_urls``).
    """
    return wikimedia_video_playback_url(inaturalist_display_url(wikimedia_display_url(url)))
