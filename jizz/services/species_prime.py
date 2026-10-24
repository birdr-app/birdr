"""Load media and translated names for many species at once.

``SpeciesDetailSerializer`` reads ``species.images/videos/sounds`` and a translated
name for every species it renders, which costs up to seven queries per species. For
payloads that embed whole games (every answer has two species) that adds up to
hundreds of queries. ``prime_species`` fills per-instance caches that
``Species._eligible_media`` and ``_species_name_for_language`` use instead, with the
same selection rules, in two queries.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from django.db.models import Exists, OuterRef

MEDIA_TYPES = ('image', 'video', 'audio')


def prime_species(species: Iterable, languages: Iterable[str | None] = ()) -> None:
    from jizz.models import SpeciesName
    from media.models import Media, MediaReview

    by_id: dict[int, list] = defaultdict(list)
    for item in species:
        if item is not None:
            by_id[item.id].append(item)
    if not by_id:
        return

    media = (
        Media.objects.filter(species_id__in=by_id, type__in=MEDIA_TYPES)
        .annotate(
            _approved=Exists(MediaReview.objects.filter(media=OuterRef('pk'), review_type='approved')),
            _rejected=Exists(MediaReview.objects.filter(
                media=OuterRef('pk'), review_type__in=MediaReview.REJECTING_TYPES,
            )),
        )
        .order_by('id')
    )
    grouped: dict[tuple[int, str], list] = defaultdict(list)
    for item in media:
        grouped[(item.species_id, item.type)].append(item)

    for species_id, instances in by_id.items():
        cache = {}
        for media_type in MEDIA_TYPES:
            rows = grouped.get((species_id, media_type), [])
            approved = [m for m in rows if m._approved]
            cache[media_type] = approved if approved else [m for m in rows if not m._rejected]
        for instance in instances:
            instance._eligible_media_cache = cache

    langs = {lang for lang in languages if lang and lang != 'la'}
    if langs:
        names = defaultdict(dict)
        for row in SpeciesName.objects.filter(species_id__in=by_id, language_id__in=langs):
            names[row.species_id][row.language_id] = row.name
        for species_id, instances in by_id.items():
            for instance in instances:
                instance._name_by_language = {lang: names[species_id].get(lang) for lang in langs}
