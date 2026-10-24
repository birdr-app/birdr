"""
Cover image for species UI: AI illustration when ready, else first eligible photo.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

from jizz.models import SpeciesIllustration
from jizz.services.species_illustration import get_illustration_status
from media.models import Media
from media.display_urls import media_object_display_url

if TYPE_CHECKING:
    from jizz.models import Species


def absolute_media_url(url: str, request=None) -> str:
    """Turn a FileField .url (often /media/...) into an absolute HTTPS URL for clients."""
    if not url:
        return url

    site = (getattr(settings, 'SITE_URL', None) or '').rstrip('/')
    force_https = (not getattr(settings, 'DEBUG', True)) or site.startswith('https://')

    def _upgrade(u: str) -> str:
        if force_https and u.startswith('http://'):
            return 'https://' + u[7:]
        return u

    if url.startswith('http://') or url.startswith('https://'):
        return _upgrade(url)

    if site and url.startswith('/'):
        return _upgrade(site + url)

    if request:
        return _upgrade(request.build_absolute_uri(url))

    if url.startswith('/'):
        fallback = (site or 'https://birdr.pro').rstrip('/')
        return _upgrade(fallback + url)
    return url


def _absolute_url(url: str, request) -> str:
    return absolute_media_url(url, request)


def _stored_illustration_url(species: Species, request) -> str | None:
    if get_illustration_status(species) != 'ready':
        return None
    try:
        ill = species.illustration
    except SpeciesIllustration.DoesNotExist:
        return None
    if not ill.image:
        return None
    return _absolute_url(ill.image.url, request)


def _first_eligible_image_url(species: Species, request) -> str | None:
    base = Media.objects.filter(species=species, type='image', hide=False)
    approved = (
        base.filter(reviews__review_type='approved')
        .distinct()
        .order_by('id')
        .first()
    )
    media = approved
    if not media:
        media = base.exclude(reviews__review_type='rejected').order_by('id').first()
    if not media or not media.url:
        return None
    return media_object_display_url(media)


def species_cover_url(species: Species, request=None) -> str | None:
    """Illustration URL if ready, otherwise the first eligible species photo."""
    url = _stored_illustration_url(species, request)
    if url:
        return url
    return _first_eligible_image_url(species, request)


def species_cover_urls_bulk(species_ids: list[int], request=None) -> dict[int, str | None]:
    if not species_ids:
        return {}

    urls: dict[int, str | None] = {}
    rows = SpeciesIllustration.objects.filter(
        species_id__in=species_ids,
        status=SpeciesIllustration.STATUS_READY,
    ).exclude(image='')
    for ill in rows:
        if ill.image:
            urls[ill.species_id] = _absolute_url(ill.image.url, request)

    missing = [sid for sid in species_ids if sid not in urls]
    if not missing:
        return urls

    approved = (
        Media.objects.filter(
            species_id__in=missing,
            type='image',
            hide=False,
            reviews__review_type='approved',
        )
        .distinct()
        .order_by('species_id', 'id')
    )
    for media in approved:
        if media.species_id not in urls and media.url:
            urls[media.species_id] = media_object_display_url(media)

    still_missing = [sid for sid in missing if sid not in urls]
    if still_missing:
        fallback = (
            Media.objects.filter(species_id__in=still_missing, type='image', hide=False)
            .exclude(reviews__review_type='rejected')
            .order_by('species_id', 'id')
        )
        for media in fallback:
            if media.species_id not in urls and media.url:
                urls[media.species_id] = media_object_display_url(media)

    return urls
