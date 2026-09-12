"""Wikimedia Commons thumbnail URL helpers.

Uses Wikimedia production $wgThumbnailSteps — arbitrary widths often 400.
https://www.mediawiki.org/wiki/Common_thumbnail_sizes
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

from django.conf import settings

# https://w.wiki/GHai
WIKIMEDIA_THUMB_STEPS = (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840)


def is_wikimedia_upload(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return 'upload.wikimedia.org' in host or host.endswith('.wikimedia.org')


def wikimedia_snap_step(requested: int) -> int:
    """Smallest standard step >= requested (Wikimedia rejects arbitrary widths)."""
    r = max(1, min(int(requested), WIKIMEDIA_THUMB_STEPS[-1]))
    for s in WIKIMEDIA_THUMB_STEPS:
        if s >= r:
            return s
    return WIKIMEDIA_THUMB_STEPS[-1]


def wikimedia_candidate_steps(requested: int) -> list[int]:
    """Primary snapped width, then smaller standard steps (for 400/404 fallbacks)."""
    primary = wikimedia_snap_step(requested)
    idx = WIKIMEDIA_THUMB_STEPS.index(primary)
    return [primary] + list(reversed(WIKIMEDIA_THUMB_STEPS[:idx]))


def wikimedia_commons_thumb_url(url: str, step_px: int) -> str:
    """
    Build a Commons thumbnail URL using a Wikimedia $wgThumbnailSteps width only.

    Accepts direct file URLs or existing /thumb/.../OLDpx-... URLs (rewrites width).
    """
    parsed = urlparse(url)
    path = parsed.path or ''
    step_px = int(step_px)

    # Existing thumb: .../thumb/X/XY/Orig.ext/Wpx-Orig.ext
    m_thumb = re.match(
        r'^(/wikipedia/commons/thumb/[0-9a-f]/[0-9a-f]{2}/)([^/]+)/(\d+)px-(.+)$',
        path,
        re.IGNORECASE,
    )
    if m_thumb:
        base, orig, _old_w, _suffix = m_thumb.groups()
        thumb_path = f'{base}{orig}/{step_px}px-{orig}'
        return urlunparse((parsed.scheme, parsed.netloc, thumb_path, '', '', ''))

    # Direct file: /wikipedia/commons/{1hex}/{2hex}/filename.ext
    m = re.match(
        r'^(/wikipedia/commons/)([0-9a-f])(/[0-9a-f]{2}/)([^/]+\.(?:jpe?g|png|webp|gif))$',
        path,
        re.IGNORECASE,
    )
    if not m:
        return url
    prefix, c1, mid, filename = m.groups()
    thumb_path = f'{prefix}thumb/{c1}{mid}{filename}/{step_px}px-{filename}'
    return urlunparse((parsed.scheme, parsed.netloc, thumb_path, '', '', ''))


def wikimedia_display_url(url: str | None, width_px: int | None = None) -> str | None:
    """
    Rewrite Wikimedia image URLs to a standard display thumbnail (default 960px).

    Non-Wikimedia URLs and unrecognized paths are returned unchanged.
    """
    if not url:
        return url
    if not is_wikimedia_upload(url):
        return url
    if width_px is None:
        width_px = int(getattr(settings, 'MEDIA_WIKIMEDIA_DISPLAY_WIDTH_PX', 960) or 960)
    step = wikimedia_snap_step(width_px)
    return wikimedia_commons_thumb_url(url, step)


# Commons TimedMediaHandler derivatives (no MP4/H.264 on Wikimedia).
# iOS: 144p MJPEG QuickTime is the profile that usually succeeds; 360p MPEG-4 often errors.
WIKIMEDIA_VIDEO_WEBM_PROFILE = '480p.vp9.webm'
WIKIMEDIA_VIDEO_IOS_PROFILE = '144p.mjpeg.mov'
_VIDEO_EXT_RE = r'webm|ogv|ogg|mpg|mpeg|avi|mov|mp4'
_COMMONS_VIDEO_DIRECT_RE = re.compile(
    rf'^(/wikipedia/commons/)([0-9a-f])/([0-9a-f]{{2}})/([^/]+\.(?:{_VIDEO_EXT_RE}))$',
    re.I,
)
_COMMONS_VIDEO_TRANSCODED_RE = re.compile(
    r'^(/wikipedia/commons/transcoded/)([0-9a-f])/([0-9a-f]{2})/([^/]+)/([^/]+)$',
    re.I,
)


def _commons_video_parts(url: str | None) -> tuple[str, str, str, str, str] | None:
    """Return (scheme, netloc, h1, h2, filename) for a Commons video file URL."""
    if not url or not is_wikimedia_upload(url):
        return None
    parsed = urlparse(url)
    path = parsed.path or ''
    match = _COMMONS_VIDEO_DIRECT_RE.match(path)
    if match:
        _prefix, h1, h2, filename = match.groups()
        return parsed.scheme or 'https', parsed.netloc, h1, h2, filename
    match = _COMMONS_VIDEO_TRANSCODED_RE.match(path)
    if not match:
        return None
    _prefix, h1, h2, filename, last = match.groups()
    if not last.lower().startswith(filename.lower() + '.'):
        return None
    return parsed.scheme or 'https', parsed.netloc, h1, h2, filename


def wikimedia_video_original_url(url: str | None) -> str | None:
    parts = _commons_video_parts(url)
    if not parts:
        return url
    scheme, netloc, h1, h2, filename = parts
    path = f'/wikipedia/commons/{h1}/{h2}/{filename}'
    return urlunparse((scheme, netloc, path, '', '', ''))


def wikimedia_video_transcode_url(url: str | None, profile: str) -> str | None:
    """Deterministic Commons transcode path. Does not check that the derivative exists."""
    parts = _commons_video_parts(url)
    if not parts:
        return url
    scheme, netloc, h1, h2, filename = parts
    path = f'/wikipedia/commons/transcoded/{h1}/{h2}/{filename}/{filename}.{profile}'
    return urlunparse((scheme, netloc, path, '', '', ''))


def wikimedia_video_playback_url(url: str | None) -> str | None:
    """Smaller VP9 WebM for Android/desktop. iOS clients swap to the .mov profile."""
    if not _commons_video_parts(url):
        return url
    return wikimedia_video_transcode_url(url, WIKIMEDIA_VIDEO_WEBM_PROFILE)


def wikimedia_video_ios_url(url: str | None) -> str | None:
    if not _commons_video_parts(url):
        return url
    return wikimedia_video_transcode_url(url, WIKIMEDIA_VIDEO_IOS_PROFILE)
