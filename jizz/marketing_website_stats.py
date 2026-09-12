"""Aggregates for public marketing-site (/site/) visitor stats."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.db.models import Q
from django.utils import timezone

from jizz.games_played_stats import (
    Granularity,
    _end_period,
    _period_start,
    default_date_range,
    games_played_map_style,
    iter_periods,
    normalize_range,
    world_map_country_code,
)
from jizz.marketing.i18n import MARKETING_LOCALES, strip_locale_prefix
from jizz.marketing.pages import INTENT_PAGES
from jizz.models import Country, UsageEvent
from jizz.usage_analytics import is_crawler_user_agent

PRIVATE_PREFIXES = (
    '/site/my-edits/',
    '/site/logout/',
    '/site/feedback/',
)

_PAGE_LABELS = {
    '/site/': 'Home',
    '/site/birds/': 'Species',
    '/site/page/': 'All pages',
}


def _intent_page_labels() -> dict[str, str]:
    labels = dict(_PAGE_LABELS)
    for slug, page in INTENT_PAGES.items():
        labels[f'/site/{slug}/'] = page.get('heading') or slug
    return labels


def marketing_path_filter() -> Q:
    query = Q(path__startswith='/site/')
    for locale in MARKETING_LOCALES:
        if locale == 'en':
            continue
        query |= Q(path__startswith=f'/{locale}/site/')
    return query


def normalize_marketing_path(path: str) -> str:
    logical = strip_locale_prefix(path or '')
    if not logical.startswith('/site/'):
        if (path or '').startswith('/site/'):
            logical = path.split('?', 1)[0]
        else:
            return ''
    logical = logical.split('?', 1)[0]
    if not logical.endswith('/'):
        logical += '/'
    return logical


def is_public_marketing_path(path: str) -> bool:
    logical = normalize_marketing_path(path)
    if not logical:
        return False
    return not any(logical.startswith(prefix) for prefix in PRIVATE_PREFIXES)


def marketing_path_label(path: str) -> str:
    logical = normalize_marketing_path(path) or path
    labels = _intent_page_labels()
    if logical in labels:
        return labels[logical]
    parts = [part for part in logical.strip('/').split('/') if part]
    if len(parts) >= 3 and parts[0] == 'site' and parts[1] == 'birds':
        return f'Species · {parts[2]}'
    if len(parts) >= 3 and parts[0] == 'site' and parts[1] == 'countries':
        return f'Country · {parts[2]}'
    if len(parts) >= 3 and parts[0] == 'site' and parts[1] == 'compare':
        return f'Compare · {parts[2]}'
    if len(parts) >= 3 and parts[0] == 'site' and parts[1] == 'page':
        return f'Page · {parts[2]}'
    return logical


def _marketing_queryset(start: date, end: date):
    start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end, datetime.max.time()))
    return (
        UsageEvent.objects.filter(
            event_type='page_view',
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        )
        .filter(marketing_path_filter())
    )


def _human_queryset(qs):
    return [
        event
        for event in qs.iterator(chunk_size=500)
        if is_public_marketing_path(event.path) and not is_crawler_user_agent(event.user_agent)
    ]


def marketing_website_rows(
    events: list,
    start: date,
    end: date,
    *,
    granularity: Granularity = 'month',
) -> list[dict]:
    start, end = normalize_range(start, end, granularity=granularity)
    buckets: dict[date, dict[str, Any]] = {}
    for event in events:
        period = _period_start(timezone.localdate(event.created_at), granularity)
        bucket = buckets.setdefault(period, {'visits': 0, 'ips': set()})
        bucket['visits'] += 1
        if event.ip_address:
            bucket['ips'].add(str(event.ip_address))

    rows: list[dict] = []
    for period_start in iter_periods(start, end, granularity):
        bucket = buckets.get(period_start, {'visits': 0, 'ips': set()})
        rows.append(
            {
                'period': period_start.isoformat(),
                'period_end': _end_period(period_start, end, granularity).isoformat(),
                'visits': bucket['visits'],
                'visitors': len(bucket['ips']),
            }
        )
    return rows


def marketing_website_by_country(events: list) -> dict:
    visits: dict[str, int] = {}
    visitors: dict[str, set[str]] = {}
    unknown_visits = 0
    unknown_ips: set[str] = set()

    for event in events:
        code = (event.country_code or '').strip().upper()
        ip = str(event.ip_address) if event.ip_address else ''
        if len(code) != 2:
            unknown_visits += 1
            if ip:
                unknown_ips.add(ip)
            continue
        visits[code] = visits.get(code, 0) + 1
        visitors.setdefault(code, set())
        if ip:
            visitors[code].add(ip)

    names = {
        row.code: row.name
        for row in Country.objects.filter(code__in=visits.keys()).only('code', 'name')
    }
    by_country = [
        {
            'country_code': code,
            'country_name': names.get(code) or code,
            'visits': count,
            'visitors': len(visitors.get(code, ())),
        }
        for code, count in sorted(visits.items(), key=lambda item: (-item[1], item[0]))
    ]
    if unknown_visits:
        by_country.append(
            {
                'country_code': '',
                'country_name': 'Unknown',
                'visits': unknown_visits,
                'visitors': len(unknown_ips),
            }
        )

    country_map: dict[str, int] = {}
    for row in by_country:
        map_code = world_map_country_code(row['country_code'])
        if not map_code:
            continue
        country_map[map_code] = country_map.get(map_code, 0) + row['visits']

    return {'by_country': by_country, 'country_map': country_map}


def marketing_website_top_paths(events: list, *, limit: int = 25) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    ips: dict[str, set[str]] = {}
    for event in events:
        path = normalize_marketing_path(event.path)
        if not path:
            continue
        counts[path] = counts.get(path, 0) + 1
        ips.setdefault(path, set())
        if event.ip_address:
            ips[path].add(str(event.ip_address))

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [
        {
            'path': path,
            'label': marketing_path_label(path),
            'visits': visits,
            'visitors': len(ips.get(path, ())),
        }
        for path, visits in ranked
    ]


def marketing_website_payload(
    start: date | None = None,
    end: date | None = None,
    *,
    granularity: Granularity | None = None,
) -> dict[str, Any]:
    default_start, default_end = default_date_range()
    start = start or default_start
    end = end or default_end
    granularity = granularity or 'month'
    start, end = normalize_range(start, end, granularity=granularity)

    qs = _marketing_queryset(start, end)
    events = _human_queryset(qs)
    country_stats = marketing_website_by_country(events)
    unique_ips = {str(event.ip_address) for event in events if event.ip_address}

    return {
        'start': start.isoformat(),
        'end': end.isoformat(),
        'granularity': granularity,
        'total_visits': len(events),
        'unique_visitors': len(unique_ips),
        'country_count': len(
            [row for row in country_stats['by_country'] if row['country_code']]
        ),
        'series': marketing_website_rows(events, start, end, granularity=granularity),
        'top_paths': marketing_website_top_paths(events),
        'by_country': country_stats['by_country'],
        'country_map': country_stats['country_map'],
        'map_style': games_played_map_style(),
    }
