"""Public media-review statistics for the data site."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.core.cache import cache
from django.db.models import Count, Exists, OuterRef
from django.db.models.functions import TruncMonth
from django.utils import timezone

from jizz.data_user_stats import media_reviews_per_user_rows
from jizz.games_played_stats import default_date_range, iter_periods
from jizz.marketing.pages import MEDIA_REVIEWED_APPROVED_COUNT
from jizz.models import Country, CountrySpecies
from jizz.services.checklist import CHECKLIST_COUNTRY_SPECIES_STATUSES
from media.models import IMAGE_SOURCES, MEDIA_TYPES, Media, MediaReview
from media.review_stats import get_species_media_review_stats

_ISO2_COUNTRY = r'^[A-Za-z]{2}$'
_PAYLOAD_CACHE_KEY = 'data:media-review-stats'
_PAYLOAD_CACHE_TTL = 60


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def _label_from_choices(choices, value: str, empty: str = 'Unknown') -> str:
    raw = (value or '').strip()
    if not raw:
        return empty
    return dict(choices).get(raw, raw)


def _photo_and_reviewed_by(field: str, *, type_filter: str | None = None) -> list[dict]:
    qs = Media.objects.filter(hide=False)
    if type_filter:
        qs = qs.filter(type=type_filter)
    photos_by = dict(qs.values(field).annotate(n=Count('id')).values_list(field, 'n'))
    reviewed_by = dict(
        qs.filter(Exists(MediaReview.objects.filter(media_id=OuterRef('pk'))))
        .values(field)
        .annotate(n=Count('id'))
        .values_list(field, 'n')
    )
    return [
        {field: key, 'photos': photos, 'reviewed': reviewed_by.get(key) or 0}
        for key, photos in photos_by.items()
    ]


def visible_photo_counts_by_species() -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    """Per-species visible image counts: total, with any review, with an approved review."""
    photos: dict[int, int] = {}
    reviewed: dict[int, int] = {}
    approved: dict[int, int] = {}
    for species_id, row in get_species_media_review_stats('image').items():
        if row['total_media']:
            photos[species_id] = row['total_media']
        if row['media_with_review']:
            reviewed[species_id] = row['media_with_review']
        if row['approved_media']:
            approved[species_id] = row['approved_media']
    return photos, reviewed, approved


def review_overview(photo_stats: tuple[dict[int, int], dict[int, int], dict[int, int]] | None = None) -> dict:
    now = timezone.now()
    month_ago = now - timedelta(days=30)
    photos_by, reviewed_by, approved_by = photo_stats or visible_photo_counts_by_species()
    photos = sum(photos_by.values())
    photos_reviewed = sum(reviewed_by.values())
    type_counts = {
        row['review_type']: row['n']
        for row in MediaReview.objects.values('review_type').annotate(n=Count('id'))
    }
    approved = type_counts.get(MediaReview.APPROVED, 0)
    rejected = type_counts.get(MediaReview.REJECTED, 0)
    not_sure = type_counts.get(MediaReview.NOT_SURE, 0)
    total = approved + rejected + not_sure
    decided = approved + rejected
    species_with_photos = len(photos_by)
    species_ready = sum(
        1
        for species_id, total_photos in photos_by.items()
        if approved_by.get(species_id, 0) >= MEDIA_REVIEWED_APPROVED_COUNT
        or reviewed_by.get(species_id, 0) >= total_photos
    )
    return {
        'total_reviews': total,
        'approved': approved,
        'rejected': rejected,
        'not_sure': not_sure,
        'decided': decided,
        'approval_rate': _pct(approved, decided),
        'photos': photos,
        'photos_reviewed': photos_reviewed,
        'photos_reviewed_pct': _pct(photos_reviewed, photos),
        'species_with_photos': species_with_photos,
        'species_ready': species_ready,
        'species_ready_pct': _pct(species_ready, species_with_photos),
        'reviews_last_30_days': MediaReview.objects.filter(created__gte=month_ago).count(),
    }


def country_review_coverage_rows(
    photo_stats: tuple[dict[int, int], dict[int, int], dict[int, int]] | None = None,
) -> list[dict]:
    """Visible images of checklist species, and how many have at least one review."""
    photos_by, reviewed_by, _approved_by = photo_stats or visible_photo_counts_by_species()
    country_names = dict(
        Country.objects.filter(code__regex=_ISO2_COUNTRY).values_list('code', 'name')
    )
    if not country_names:
        return []
    pairs = (
        CountrySpecies.objects.filter(
            status__in=CHECKLIST_COUNTRY_SPECIES_STATUSES,
            country_id__in=country_names,
        )
        .values_list('country_id', 'species_id')
        .iterator(chunk_size=5000)
    )
    by_country: dict[str, dict] = {}
    for country_id, species_id in pairs:
        n_photos = photos_by.get(species_id) or 0
        if n_photos <= 0:
            continue
        bucket = by_country.get(country_id)
        if bucket is None:
            bucket = {
                'code': country_id,
                'name': country_names.get(country_id) or country_id,
                'photos': 0,
                'reviewed': 0,
                'species_with_photos': 0,
                'species_with_review': 0,
            }
            by_country[country_id] = bucket
        bucket['photos'] += n_photos
        bucket['reviewed'] += reviewed_by.get(species_id) or 0
        bucket['species_with_photos'] += 1
        if reviewed_by.get(species_id):
            bucket['species_with_review'] += 1

    out = []
    for bucket in by_country.values():
        out.append(
            {
                **bucket,
                'pct': _pct(bucket['reviewed'], bucket['photos']),
                'species_pct': _pct(bucket['species_with_review'], bucket['species_with_photos']),
            }
        )
    out.sort(
        key=lambda item: (-item['species_pct'], -item['species_with_photos'], item['name'].lower())
    )
    return out


def reviews_by_source_rows() -> list[dict]:
    out = []
    for row in _photo_and_reviewed_by('source', type_filter='image'):
        photos = row['photos']
        reviewed = row['reviewed']
        out.append(
            {
                'source': _label_from_choices(IMAGE_SOURCES, row['source']),
                'photos': photos,
                'reviewed': reviewed,
                'pct': _pct(reviewed, photos),
            }
        )
    out.sort(key=lambda item: (-item['photos'], item['source'].lower()))
    return out


def reviews_by_media_type_rows() -> list[dict]:
    out = []
    for row in _photo_and_reviewed_by('type'):
        items = row['photos']
        reviewed = row['reviewed']
        out.append(
            {
                'type': _label_from_choices(MEDIA_TYPES, row['type'] or 'image'),
                'items': items,
                'reviewed': reviewed,
                'pct': _pct(reviewed, items),
            }
        )
    out.sort(key=lambda item: (-item['items'], item['type'].lower()))
    return out


def reviews_by_month_rows() -> list[dict]:
    """Reviews per calendar month for the last 12 months, including months with none."""
    start, end = default_date_range()
    start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end, datetime.max.time()))
    aggregated: dict = {}
    for row in (
        MediaReview.objects.filter(created__gte=start_dt, created__lte=end_dt)
        .annotate(month=TruncMonth('created'))
        .values('month')
        .annotate(total=Count('id'))
    ):
        month = row['month']
        if month is None:
            continue
        key = month.date().replace(day=1) if hasattr(month, 'date') else month.replace(day=1)
        aggregated[key] = row['total']
    return [
        {
            'month': period.isoformat(),
            'total': aggregated.get(period, 0),
        }
        for period in iter_periods(start, end, 'month')
    ]


def invalidate_media_review_stats_payload() -> None:
    cache.delete(_PAYLOAD_CACHE_KEY)


def media_review_stats_payload() -> dict:
    cached = cache.get(_PAYLOAD_CACHE_KEY)
    if cached is not None:
        return cached
    photo_stats = visible_photo_counts_by_species()
    reviewers = media_reviews_per_user_rows()
    overview = review_overview(photo_stats)
    overview['reviewers'] = len(reviewers)
    payload = {
        'overview': overview,
        'reviewers': reviewers,
        'countries': country_review_coverage_rows(photo_stats),
        'sources': reviews_by_source_rows(),
        'media_types': reviews_by_media_type_rows(),
        'by_month': reviews_by_month_rows(),
    }
    cache.set(_PAYLOAD_CACHE_KEY, payload, _PAYLOAD_CACHE_TTL)
    return payload
