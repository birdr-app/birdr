"""Per-species media-review statistics without COUNT(DISTINCT) over a join."""
from __future__ import annotations

from django.core.cache import cache
from django.db import connection

from media.models import MEDIA_TYPES

STATS_CACHE_TTL = 60
_CACHE_KEY = 'media:species-review-stats:{media_type}'

# Visible media only (hide=False). Rejected items are hidden, so they drop out of
# total/approved/not_sure and are counted separately from hide=True rows.
_VISIBLE_STATS_SQL = """
SELECT
    m.species_id,
    COUNT(*)::int AS total_media,
    COUNT(r.media_id)::int AS media_with_review,
    COUNT(*) FILTER (WHERE r.has_approved)::int AS approved_media,
    COUNT(*) FILTER (WHERE r.has_not_sure)::int AS not_sure_media
FROM media_media m
LEFT JOIN (
    SELECT
        r.media_id,
        BOOL_OR(r.review_type = 'approved') AS has_approved,
        BOOL_OR(r.review_type = 'not_sure') AS has_not_sure
    FROM media_mediareview r
    INNER JOIN media_media vis
        ON vis.id = r.media_id AND vis.hide = FALSE AND vis.type = %s
    GROUP BY r.media_id
) r ON r.media_id = m.id
WHERE m.type = %s AND m.hide = FALSE
{species_clause}
GROUP BY m.species_id
"""

_HIDDEN_STATS_SQL = """
SELECT species_id, COUNT(*)::int
FROM media_media
WHERE type = %s AND hide = TRUE
{species_clause}
GROUP BY species_id
"""


def stats_cache_key(media_type: str) -> str:
    return _CACHE_KEY.format(media_type=media_type or 'image')


def invalidate_species_media_review_stats() -> None:
    cache.delete_many([stats_cache_key(media_type) for media_type, _label in MEDIA_TYPES])


def _fetch_species_media_review_stats(media_type: str, species_ids=None) -> dict[int, dict]:
    if species_ids is not None:
        species_ids = list(species_ids)
        if not species_ids:
            return {}
        visible_clause = 'AND m.species_id = ANY(%s)'
        hidden_clause = 'AND species_id = ANY(%s)'
        visible_params = [media_type, media_type, species_ids]
        hidden_params = [media_type, species_ids]
    else:
        visible_clause = ''
        hidden_clause = ''
        visible_params = [media_type, media_type]
        hidden_params = [media_type]

    with connection.cursor() as cursor:
        cursor.execute(
            _VISIBLE_STATS_SQL.format(species_clause=visible_clause),
            visible_params,
        )
        visible_rows = cursor.fetchall()
        cursor.execute(
            _HIDDEN_STATS_SQL.format(species_clause=hidden_clause),
            hidden_params,
        )
        hidden_rows = cursor.fetchall()

    stats = {
        species_id: {
            'total_media': total_media,
            'media_with_review': media_with_review,
            'approved_media': approved_media,
            'rejected_media': 0,
            'not_sure_media': not_sure_media,
        }
        for species_id, total_media, media_with_review, approved_media, not_sure_media in visible_rows
    }
    for species_id, rejected_media in hidden_rows:
        row = stats.get(species_id)
        if row is None:
            stats[species_id] = {
                'total_media': 0,
                'media_with_review': 0,
                'approved_media': 0,
                'rejected_media': rejected_media,
                'not_sure_media': 0,
            }
        else:
            row['rejected_media'] = rejected_media
    return stats


def get_species_media_review_stats(media_type: str, species_ids=None) -> dict[int, dict]:
    """Species-id -> review counts. Full-type results are cached briefly."""
    media_type = media_type or 'image'
    if species_ids is not None:
        return _fetch_species_media_review_stats(media_type, species_ids)

    key = stats_cache_key(media_type)
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = _fetch_species_media_review_stats(media_type)
    cache.set(key, data, STATS_CACHE_TTL)
    return data


def attach_review_stats(species_list, stats_by_id: dict[int, dict]):
    empty = {
        'total_media': 0,
        'media_with_review': 0,
        'approved_media': 0,
        'rejected_media': 0,
        'not_sure_media': 0,
    }
    for species in species_list:
        stats = stats_by_id.get(species.id) or empty
        species.total_media = stats['total_media']
        species.media_with_review = stats['media_with_review']
        species.approved_media = stats['approved_media']
        species.rejected_media = stats['rejected_media']
        species.not_sure_media = stats['not_sure_media']
    return species_list


def summary_from_stats(stats_by_id: dict[int, dict]) -> dict[str, int]:
    total_species = 0
    not_reviewed = 0
    fully_reviewed = 0
    reviewed = 0
    partly_reviewed = 0
    for stats in stats_by_id.values():
        total = stats['total_media']
        rejected = stats['rejected_media']
        if total <= 0 and rejected <= 0:
            continue
        total_species += 1
        with_review = stats['media_with_review']
        approved = stats['approved_media']
        if total == 0:
            fully_reviewed += 1
            reviewed += 1
            continue
        if with_review == 0:
            not_reviewed += 1
        if with_review >= total:
            fully_reviewed += 1
        if approved >= 10 or with_review >= total:
            reviewed += 1
        if 0 < with_review < total and approved < 10:
            partly_reviewed += 1
    return {
        'total_species': total_species,
        'not_reviewed': not_reviewed,
        'partly_reviewed': partly_reviewed,
        'reviewed': reviewed,
        'fully_reviewed': fully_reviewed,
    }


def species_ids_for_review_level(stats_by_id: dict[int, dict], level: str) -> list[int]:
    """Visible-media species IDs, filtered by fast/full/thorough, ordered by id."""
    ids = []
    for species_id, stats in stats_by_id.items():
        total = stats['total_media']
        if total <= 0:
            continue
        with_review = stats['media_with_review']
        if level == 'fast':
            if stats['approved_media'] >= 10 or with_review >= total:
                continue
        elif level == 'full':
            if with_review >= total:
                continue
        ids.append(species_id)
    ids.sort()
    return ids
