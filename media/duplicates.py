"""Find and hide media rows that point at the same file for the same species.

The January 2026 scrape stored many iNaturalist photos twice: once from the
iNaturalist scraper and once from GBIF (whose occurrence links differ, so the
per-source link check let both through). Games then showed the same photo
twice, and flagging one copy brought the other one back as "a new picture".

Each group of copies keeps one row; the others get ``duplicate_of`` and are
hidden. If any copy was rejected, every visible copy is hidden under it.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction

from media.models import Media, MediaReview


@dataclass
class DuplicateReport:
    groups: int = 0
    to_hide: int = 0
    hidden_under_rejected: int = 0
    by_source: dict = field(default_factory=lambda: defaultdict(int))
    samples: list = field(default_factory=list)
    # media id -> id of the row it duplicates
    assignments: dict = field(default_factory=dict)


def image_url_exists(species, url: str | None, media_type: str = 'image') -> bool:
    """True when this species already has a row for this file, from any source."""
    if not url:
        return False
    return Media.objects.filter(species=species, type=media_type, url=url).exists()


def _keeper(rows, reviews_by_media):
    """Row to keep: approved first, then most reviewed, then oldest."""
    def rank(row):
        reviews = reviews_by_media.get(row['id'], [])
        approved = any(r == MediaReview.APPROVED for r in reviews)
        return (not approved, -len(reviews), row['id'])
    return min(rows, key=rank)


def scan(samples: int = 5) -> DuplicateReport:
    groups = defaultdict(list)
    rows = (
        Media.objects.exclude(url__isnull=True).exclude(url='')
        .values('id', 'species_id', 'type', 'url', 'source', 'hide', 'duplicate_of_id')
        .order_by()
        .iterator(chunk_size=10000)
    )
    for row in rows:
        groups[(row['species_id'], row['type'], row['url'])].append(row)
    groups = {key: members for key, members in groups.items() if len(members) > 1}

    ids = [row['id'] for members in groups.values() for row in members]
    reviews_by_media = defaultdict(list)
    for start in range(0, len(ids), 10000):
        for media_id, review_type in MediaReview.objects.filter(
            media_id__in=ids[start:start + 10000]
        ).values_list('media_id', 'review_type'):
            reviews_by_media[media_id].append(review_type)

    report = DuplicateReport()
    for members in groups.values():
        rejected = [
            row for row in members
            if any(r in MediaReview.REJECTING_TYPES for r in reviews_by_media.get(row['id'], []))
        ]
        keeper = min(rejected, key=lambda row: row['id']) if rejected else _keeper(members, reviews_by_media)
        changed = [
            row for row in members
            if row['id'] != keeper['id'] and row['id'] not in {r['id'] for r in rejected}
            and (row['duplicate_of_id'] is None or not row['hide'])
        ]
        if not changed:
            continue
        report.groups += 1
        for row in changed:
            report.assignments[row['id']] = keeper['id']
            report.to_hide += 1
            report.by_source[row['source'] or '-'] += 1
            if rejected:
                report.hidden_under_rejected += 1
        if len(report.samples) < samples:
            report.samples.append((keeper['id'], [row['id'] for row in changed], keeper['url']))
    return report


def apply(report: DuplicateReport, batch_size: int = 1000) -> int:
    """Hide the duplicates found by ``scan``. Returns the number of rows updated."""
    from jizz.data_review_stats import invalidate_media_review_stats_payload
    from media.review_stats import invalidate_species_media_review_stats

    items = list(report.assignments.items())
    updated = 0
    for start in range(0, len(items), batch_size):
        batch = [
            Media(id=media_id, duplicate_of_id=keeper_id, hide=True)
            for media_id, keeper_id in items[start:start + batch_size]
        ]
        with transaction.atomic():
            updated += Media.objects.bulk_update(batch, ['duplicate_of', 'hide'])
    invalidate_species_media_review_stats()
    invalidate_media_review_stats_payload()
    return updated
