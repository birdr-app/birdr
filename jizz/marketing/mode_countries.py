"""Countries with National League or Survival activity, for marketing index pages."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Count, Max

from jizz.league import flag_emoji
from jizz.marketing.pages import MARKETING_QUERY_CACHE_TTL
from jizz.models import Country, Game, LeagueMembership, PlayerScore
from jizz.user_names import sanitize_player_name

_LEAGUE_CACHE = 'marketing-league-countries-v1'
_SURVIVAL_CACHE = 'marketing-survival-countries-v1'


def _country_page_by_code() -> dict[str, dict]:
    from jizz.marketing.views import _indexable_countries

    return {row['code']: row for row in _indexable_countries()}


def _enrich(rows: list[dict]) -> list[dict]:
    pages = _country_page_by_code()
    out = []
    for row in rows:
        code = row['code']
        page = pages.get(code) or {}
        out.append(
            {
                **row,
                'flag': flag_emoji(code),
                'url': page.get('url') or '',
                'slug': page.get('slug') or '',
            }
        )
    return out


def national_league_countries() -> list[dict]:
    """Countries with at least one National League member, busiest first."""
    cached = cache.get(_LEAGUE_CACHE)
    if cached is not None:
        return cached
    counts = {
        row['country_id']: row['players']
        for row in (
            LeagueMembership.objects.values('country_id')
            .annotate(players=Count('id'))
            .order_by('-players', 'country_id')
        )
    }
    if not counts:
        cache.set(_LEAGUE_CACHE, [], MARKETING_QUERY_CACHE_TTL)
        return []
    countries = Country.objects.in_bulk(list(counts))
    rows = []
    for code, players in counts.items():
        country = countries.get(code)
        if country is None:
            continue
        rows.append(
            {
                'code': code,
                'name': country.name,
                'players': players,
            }
        )
    rows = _enrich(rows)
    cache.set(_LEAGUE_CACHE, rows, MARKETING_QUERY_CACHE_TTL)
    return rows


def survival_countries() -> list[dict]:
    """Countries with Survival scores, strongest country record first."""
    cached = cache.get(_SURVIVAL_CACHE)
    if cached is not None:
        return cached
    stats = list(
        PlayerScore.objects.filter(
            game__game_type=Game.GAME_TYPE_SURVIVAL,
            streak__gt=0,
        )
        .values('game__country_id')
        .annotate(
            players=Count('player_id', distinct=True),
            best_streak=Max('streak'),
        )
        .order_by('-best_streak', '-players', 'game__country_id')
    )
    if not stats:
        cache.set(_SURVIVAL_CACHE, [], MARKETING_QUERY_CACHE_TTL)
        return []

    records: dict[str, dict] = {}
    scores = (
        PlayerScore.objects.filter(
            game__game_type=Game.GAME_TYPE_SURVIVAL,
            streak__gt=0,
            game__country_id__in=[row['game__country_id'] for row in stats],
        )
        .select_related('player', 'game')
        .order_by('game__country_id', '-streak', '-score', 'id')
    )
    for score in scores:
        code = score.game.country_id
        if code in records:
            continue
        records[code] = {
            'best_streak': score.streak,
            'record_holder': sanitize_player_name(score.player.name if score.player else ''),
        }

    countries = Country.objects.in_bulk([row['game__country_id'] for row in stats])
    rows = []
    for row in stats:
        code = row['game__country_id']
        country = countries.get(code)
        if country is None:
            continue
        record = records.get(code) or {}
        rows.append(
            {
                'code': code,
                'name': country.name,
                'players': row['players'],
                'best_streak': record.get('best_streak') or row['best_streak'] or 0,
                'record_holder': record.get('record_holder') or '',
            }
        )
    rows = _enrich(rows)
    cache.set(_SURVIVAL_CACHE, rows, MARKETING_QUERY_CACHE_TTL)
    return rows
