"""Add one photo from Wikimedia Commons to a species, with its author and licence."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

import requests

from media.mirror import commons_file_title
from media.models import Media
from media.utils import normalize_contributor, parse_copyright

COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'Motmot/1.0 (https://motmot.club; media import)'
PHOTO_MIME = {'image/jpeg', 'image/png', 'image/webp'}


class CommonsImportError(Exception):
    """The link is not a usable Commons photo; the message says why, for the person who pasted it."""


def commons_title(link: str) -> str:
    """`File:Name.jpg` from a Commons page link, an upload.wikimedia.org link or the title itself."""
    link = (link or '').strip()
    if link.startswith('File:'):
        return link
    parsed = urlparse(link)
    host = (parsed.netloc or '').lower()
    if host.endswith('upload.wikimedia.org'):
        title = commons_file_title(link)
        if title:
            return title
    if host.endswith('wikimedia.org') or host.endswith('wikipedia.org'):
        match = re.search(r'/wiki/((?:File|Bestand|Datei|Fichier):.+)$', parsed.path)
        if match:
            name = unquote(match.group(1)).split(':', 1)[1]
            return 'File:' + name.replace('_', ' ')
        match = re.match(r'/media/(?:File|Bestand|Datei|Fichier):(.+)$', parsed.fragment)
        if match:
            return 'File:' + unquote(match.group(1)).replace('_', ' ')
    raise CommonsImportError('Dit is geen link naar een bestand op Wikimedia Commons.')


def fetch_commons_file(title: str) -> dict:
    """Image URL, page link, author and licence of a Commons file."""
    try:
        response = requests.get(
            COMMONS_API,
            params={
                'action': 'query',
                'format': 'json',
                'titles': title,
                'prop': 'imageinfo',
                'iiprop': 'url|mime|extmetadata',
            },
            headers={'User-Agent': USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        pages = response.json().get('query', {}).get('pages', {})
    except (requests.RequestException, ValueError) as exc:
        raise CommonsImportError('Wikimedia Commons is nu niet bereikbaar. Probeer het zo nog eens.') from exc
    page = next(iter(pages.values()), {}) if pages else {}
    info = (page.get('imageinfo') or [None])[0]
    if 'missing' in page or not info:
        raise CommonsImportError('Dit bestand bestaat niet op Wikimedia Commons.')
    if info.get('mime') not in PHOTO_MIME:
        raise CommonsImportError('Dit bestand is geen foto (alleen JPEG, PNG of WebP).')
    meta = info.get('extmetadata', {})
    licence = (meta.get('LicenseShortName', {}).get('value') or meta.get('License', {}).get('value') or '').strip()
    author = meta.get('Artist', {}).get('value') or meta.get('Author', {}).get('value') or ''
    return {
        'url': info['url'],
        'link': info.get('descriptionurl') or f"https://commons.wikimedia.org/wiki/{page.get('title', title).replace(' ', '_')}",
        'contributor': normalize_contributor(author),
        'copyright_text': f'License: {licence}' if licence else '',
    }


def add_commons_photo(species, link: str) -> tuple[Media, bool]:
    """Create the Media row for a Commons photo of `species`, or return the one that exists."""
    info = fetch_commons_file(commons_title(link))
    existing = Media.objects.filter(species=species, type='image').filter(
        link=info['link']
    ).first() or Media.objects.filter(species=species, type='image', url=info['url']).first()
    if existing:
        if existing.hide:
            existing.hide = False
            existing.save(update_fields=['hide'])
        return existing, False
    standardized, non_commercial = parse_copyright(info['copyright_text'])
    media = Media.objects.create(
        species=species,
        type='image',
        source='wikimedia',
        url=info['url'],
        link=info['link'],
        contributor=info['contributor'],
        copyright_text=info['copyright_text'],
        copyright_standardized=standardized,
        non_commercial_only=non_commercial,
    )
    return media, True
