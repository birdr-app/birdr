from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count
from django.db.models.functions import TruncDay
from django.utils import timezone

from jizz.api_event_labels import resolve_websocket_event_label
from jizz.client_info import normalize_app_version
from jizz.models import UsageEvent, UserProfile

_PLATFORM_CHOICES = {'web', 'ios', 'android'}
_DEVICE_CHOICES = {'desktop', 'mobile', 'tablet', 'unknown'}
_EVENT_TYPE_CHOICES = {'page_view', 'feature', 'api', 'websocket'}
_COUNTRY_RE = re.compile(r'^[A-Za-z]{2}$')
_CRAWLER_UA_RE = re.compile(
    r'googlebot|bingbot|slurp|duckduckbot|baiduspider|yandexbot|facebookexternalhit|'
    r'twitterbot|linkedinbot|applebot|semrush|ahrefs|mj12bot|dotbot|petalbot|'
    r'bytespider|gptbot|claudebot|ccbot|amazonbot|ia_archiver|pingdom|uptimerobot',
    re.I,
)


def get_client_ip(request) -> str | None:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = (request.META.get('REMOTE_ADDR') or '').strip()
    return ip or None


def request_debug_meta(request) -> dict[str, str]:
    """Stored on events so staff can see proxy headers (nginx, Cloudflare)."""
    return {
        'remote_addr': (request.META.get('REMOTE_ADDR') or '')[:45],
        'x_forwarded_for': (request.META.get('HTTP_X_FORWARDED_FOR') or '')[:500],
        'cf_ipcountry': (request.META.get('HTTP_CF_IPCOUNTRY') or '')[:10],
    }


def resolve_country_code(request, client_country: str | None = None) -> str:
    if client_country:
        code = client_country.strip().upper()[:2]
        if _COUNTRY_RE.match(code):
            return code

    cf_country = (request.META.get('HTTP_CF_IPCOUNTRY') or '').strip().upper()
    if cf_country and cf_country != 'XX' and _COUNTRY_RE.match(cf_country):
        return cf_country

    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        try:
            profile = user.profile
            code = (profile.country_id or '').strip().upper()
            if code and _COUNTRY_RE.match(code):
                return code
        except UserProfile.DoesNotExist:
            pass

    return ''


def is_crawler_user_agent(user_agent: str | None) -> bool:
    """True for common search/preview crawlers we should not count as visitors."""
    return bool(user_agent) and bool(_CRAWLER_UA_RE.search(user_agent))


_NATIVE_APP_UA_TOKENS = ('okhttp', 'dalvik', 'cfnetwork', 'darwin/')
APP_BUILD_MAX = 32
OS_VERSION_MAX = 64


def parse_device_type(user_agent: str) -> str:
    ua = (user_agent or '').lower()
    if not ua:
        return 'unknown'
    if 'ipad' in ua or 'tablet' in ua:
        return 'tablet'
    if any(
        token in ua
        for token in ('mobile', 'iphone', 'android', 'okhttp', 'dalvik')
    ):
        return 'mobile'
    return 'desktop'


def infer_platform_from_user_agent(user_agent: str) -> str:
    ua = (user_agent or '').lower()
    if any(token in ua for token in ('iphone', 'ipad', 'ios', 'cfnetwork')):
        return 'ios'
    if any(token in ua for token in ('android', 'okhttp', 'dalvik')):
        return 'android'
    return 'web'


def _header_map_get(headers: dict[str, str], *names: str) -> str:
    for name in names:
        value = (headers.get(name) or '').strip()
        if value:
            return value
    return ''


def headers_from_request(request) -> dict[str, str]:
    meta = getattr(request, 'META', None) or {}
    out: dict[str, str] = {}
    for key, value in meta.items():
        if not key.startswith('HTTP_') or not isinstance(value, str):
            continue
        header = key[5:].replace('_', '-').lower()
        out[header] = value
    return out


def headers_from_scope(scope) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in scope.get('headers') or []:
        name = key.decode('latin1', errors='replace').lower()
        out[name] = value.decode('latin1', errors='replace')
    return out


def app_identity_from_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Read optional app identity headers. Missing values become empty strings."""
    headers = headers or {}
    platform = _header_map_get(
        headers,
        'x-platform',
        'x-birdr-platform',
        'x-birdr-device-type',
    ).strip().lower()
    if platform not in _PLATFORM_CHOICES:
        platform = ''
    return {
        'app_version': normalize_app_version(
            _header_map_get(headers, 'x-app-version', 'x-birdr-app-version')
        ),
        'app_build': _header_map_get(headers, 'x-app-build', 'x-birdr-app-build')[:APP_BUILD_MAX],
        'os_version': _header_map_get(headers, 'x-os-version', 'x-birdr-os-version')[:OS_VERSION_MAX],
        'platform': platform,
    }


def app_identity_from_mapping(data: Any) -> dict[str, str]:
    """Optional identity on websocket join payloads. Missing keys are empty."""
    if not isinstance(data, dict):
        return {'app_version': '', 'app_build': '', 'os_version': '', 'platform': ''}
    platform = str(
        data.get('platform') or data.get('device_type') or data.get('deviceType') or ''
    ).strip().lower()
    if platform not in _PLATFORM_CHOICES:
        platform = ''
    return {
        'app_version': normalize_app_version(
            data.get('app_version') or data.get('appVersion')
        ),
        'app_build': str(data.get('app_build') or data.get('appBuild') or '').strip()[:APP_BUILD_MAX],
        'os_version': str(data.get('os_version') or data.get('osVersion') or '').strip()[:OS_VERSION_MAX],
        'platform': platform,
    }


def merge_app_identity(*identities: dict[str, str]) -> dict[str, str]:
    """First non-empty value wins (headers first, then payload fallback)."""
    merged = {'app_version': '', 'app_build': '', 'os_version': '', 'platform': ''}
    for identity in identities:
        for key in merged:
            if not merged[key] and identity.get(key):
                merged[key] = identity[key]
    return merged


def resolve_device_type(user_agent: str, platform: str = '') -> str:
    """Native app traffic is never Desktop, even when UA is only okhttp."""
    ua_device = parse_device_type(user_agent)
    if platform in ('ios', 'android'):
        return 'tablet' if ua_device == 'tablet' else 'mobile'
    ua = (user_agent or '').lower()
    if any(token in ua for token in _NATIVE_APP_UA_TOKENS):
        return 'tablet' if ua_device == 'tablet' else 'mobile'
    return ua_device


def infer_platform_from_request(request) -> str:
    identity = app_identity_from_headers(headers_from_request(request))
    if identity['platform'] in _PLATFORM_CHOICES:
        return identity['platform']
    user_agent = request.META.get('HTTP_USER_AGENT') or ''
    return infer_platform_from_user_agent(user_agent)


def normalize_platform(value: str | None) -> str:
    platform = (value or 'web').strip().lower()
    return platform if platform in _PLATFORM_CHOICES else 'web'


def normalize_event_type(value: str | None) -> str:
    event_type = (value or 'page_view').strip().lower()
    return event_type if event_type in _EVENT_TYPE_CHOICES else 'page_view'


def normalize_path(value: str | None) -> str:
    path = (value or '/').strip()
    if not path.startswith('/'):
        path = f'/{path}'
    return path[:500]


def record_usage_event(
    request,
    *,
    path: str,
    event_type: str = 'page_view',
    platform: str | None = None,
    session_key: str = '',
    country_code: str | None = None,
    metadata: dict | None = None,
) -> UsageEvent:
    user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:2000]
    identity = app_identity_from_headers(headers_from_request(request))
    resolved_platform = normalize_platform(
        platform or identity['platform'] or infer_platform_from_request(request)
    )
    device_type = resolve_device_type(user_agent, resolved_platform)
    user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
    merged_metadata = dict(metadata or {})
    merged_metadata['proxy'] = request_debug_meta(request)

    return UsageEvent.objects.create(
        event_type=normalize_event_type(event_type),
        path=normalize_path(path) if event_type in ('page_view', 'feature') else path[:500],
        platform=resolved_platform,
        device_type=device_type,
        country_code=resolve_country_code(request, country_code),
        ip_address=get_client_ip(request),
        user=user,
        session_key=(session_key or '')[:64],
        user_agent=user_agent,
        app_version=identity['app_version'],
        app_build=identity['app_build'],
        os_version=identity['os_version'],
        metadata=merged_metadata,
    )


def _scope_header(scope, name: str) -> str:
    wanted = name.lower().encode('latin1')
    for key, value in scope.get('headers') or []:
        if key.lower() == wanted:
            return value.decode('latin1', errors='replace')
    return ''


def _scope_client_ip(scope) -> str | None:
    client = scope.get('client')
    if client:
        return client[0]
    forwarded = _scope_header(scope, 'x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip() or None
    return None


def scope_debug_meta(scope) -> dict[str, str]:
    return {
        'remote_addr': (_scope_client_ip(scope) or '')[:45],
        'x_forwarded_for': (_scope_header(scope, 'x-forwarded-for') or '')[:500],
        'cf_ipcountry': (_scope_header(scope, 'cf-ipcountry') or '')[:10],
    }


def record_websocket_usage_event(
    scope,
    *,
    action: str,
    metadata: dict | None = None,
    app_version: str = '',
    app_build: str = '',
    os_version: str = '',
    platform: str = '',
) -> UsageEvent | None:
    label = resolve_websocket_event_label(action)
    if not label:
        return None

    headers = headers_from_scope(scope)
    user_agent = (headers.get('user-agent') or '')[:2000]
    identity = merge_app_identity(
        app_identity_from_headers(headers),
        {
            'app_version': normalize_app_version(app_version),
            'app_build': (app_build or '')[:APP_BUILD_MAX],
            'os_version': (os_version or '')[:OS_VERSION_MAX],
            'platform': platform if platform in _PLATFORM_CHOICES else '',
        },
    )
    resolved_platform = normalize_platform(
        identity['platform'] or infer_platform_from_user_agent(user_agent)
    )
    country = (headers.get('cf-ipcountry') or '').strip().upper()[:2]
    if country == 'XX':
        country = ''

    ws_metadata = {'action': action, **(metadata or {}), 'proxy': scope_debug_meta(scope)}

    return UsageEvent.objects.create(
        event_type='websocket',
        path=label[:500],
        platform=resolved_platform,
        device_type=resolve_device_type(user_agent, resolved_platform),
        country_code=country if _COUNTRY_RE.match(country or '') else '',
        ip_address=_scope_client_ip(scope),
        user=None,
        session_key='',
        user_agent=user_agent,
        app_version=identity['app_version'],
        app_build=identity['app_build'],
        os_version=identity['os_version'],
        metadata=ws_metadata,
    )


def default_date_range() -> tuple[date, date]:
    end = timezone.localdate()
    return end - timedelta(days=29), end


def parse_date_param(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return fallback


def normalize_range(start: date, end: date) -> tuple[date, date]:
    if start > end:
        start, end = end, start
    if (end - start).days > 366:
        start = end - timedelta(days=366)
    return start, end


def _filtered_queryset(
    start: date,
    end: date,
    *,
    platform: str | None = None,
    device_type: str | None = None,
    country_code: str | None = None,
    event_type: str | None = None,
    ip_address: str | None = None,
):
    start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end, datetime.max.time()))
    qs = UsageEvent.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)

    if platform in _PLATFORM_CHOICES:
        qs = qs.filter(platform=platform)
    if device_type in _DEVICE_CHOICES:
        qs = qs.filter(device_type=device_type)
    if country_code and _COUNTRY_RE.match(country_code.upper()):
        qs = qs.filter(country_code=country_code.upper())
    if event_type in _EVENT_TYPE_CHOICES:
        qs = qs.filter(event_type=event_type)
    if ip_address:
        qs = qs.filter(ip_address=ip_address.strip())
    return qs


def usage_by_ip_country(qs, *, limit: int = 50, max_api_lookups: int = 60) -> list[dict[str, Any]]:
    """Aggregate events by GeoIP country code (same lookup path as Top IP addresses)."""
    from collections import Counter

    from jizz.ip_geo import lookup_ip_locations, mmdb_available

    counter: Counter[str] = Counter()
    ip_rows = list(
        qs.exclude(ip_address__isnull=True)
        .values('ip_address')
        .annotate(events=Count('id'))
        .order_by('-events')
    )
    live_cap = None if mmdb_available() else max_api_lookups
    locations = lookup_ip_locations(
        [str(row['ip_address']).strip() for row in ip_rows],
        max_live_lookups=live_cap,
    )

    for row in ip_rows:
        ip = str(row['ip_address']).strip()
        location = locations.get(ip, {})
        code = (location.get('country_code') or '').upper()
        if code:
            counter[code] += row['events']

    return [
        {'country_code': code, 'events': count}
        for code, count in counter.most_common(limit)
    ]


def usage_stats_payload(
    start: date,
    end: date,
    *,
    platform: str | None = None,
    device_type: str | None = None,
    country_code: str | None = None,
    event_type: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    start, end = normalize_range(start, end)
    qs = _filtered_queryset(
        start,
        end,
        platform=platform,
        device_type=device_type,
        country_code=country_code,
        event_type=event_type,
        ip_address=ip_address,
    )

    daily = (
        qs.annotate(day=TruncDay('created_at'))
        .values('day')
        .annotate(events=Count('id'))
        .order_by('day')
    )
    series = [
        {'period': row['day'].date().isoformat(), 'events': row['events']}
        for row in daily
    ]

    top_paths = list(
        qs.values('path')
        .annotate(events=Count('id'))
        .order_by('-events', 'path')[:20]
    )

    by_platform = list(
        qs.values('platform')
        .annotate(events=Count('id'))
        .order_by('-events', 'platform')
    )
    by_device = list(
        qs.values('device_type')
        .annotate(events=Count('id'))
        .order_by('-events', 'device_type')
    )
    by_event_type = list(
        qs.values('event_type')
        .annotate(events=Count('id'))
        .order_by('-events', 'event_type')
    )
    by_country = usage_by_ip_country(qs)

    session_qs = qs.exclude(session_key='').values('session_key').distinct()
    unique_sessions = session_qs.count()

    country_map = {row['country_code']: row['events'] for row in by_country}

    from jizz.games_played_stats import games_played_map_style

    return {
        'start': start.isoformat(),
        'end': end.isoformat(),
        'platform': platform or '',
        'device_type': device_type or '',
        'country_code': (country_code or '').upper(),
        'event_type': event_type or '',
        'total_events': qs.count(),
        'unique_sessions': unique_sessions,
        'series': series,
        'top_paths': top_paths,
        'by_platform': by_platform,
        'by_device': by_device,
        'by_event_type': by_event_type,
        'by_country': by_country,
        'country_map': country_map,
        'map_style': games_played_map_style(),
    }


def usage_top_ips(qs, *, limit: int = 15) -> list[dict[str, Any]]:
    from jizz.ip_geo import enrich_ip_rows

    rows = list(
        qs.exclude(ip_address__isnull=True)
        .values('ip_address')
        .annotate(events=Count('id'))
        .order_by('-events', 'ip_address')[:limit]
    )
    return enrich_ip_rows(rows)
