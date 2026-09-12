"""Country marketing page stats, reused from the public data section."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Q

from jizz.country_challenge_leaderboard import country_challenge_leaderboard
from jizz.games_played_stats import games_played_for_country
from jizz.marketing.slugs import compare_pair_slug
from jizz.models import Game, PlayerScore, Species
from jizz.quiz_mistake_stats import get_confusion_pair_rows, get_species_mistake_rows
from jizz.user_names import sanitize_player_name

TOP_N = 5
_MISTAKE_STATS_CACHE_TTL = 6 * 60 * 60


def _mistake_cache_key(kind: str, country_code: str | None, limit: int) -> str:
    scope = (country_code or 'all').lower()
    return f'marketing-v2-{kind}:{scope}:{limit}'


def _hiscore_qs(country):
    return (
        PlayerScore.objects.filter(game__country=country)
        .filter(Q(game__tax_order='') | Q(game__tax_order__isnull=True))
        .filter(Q(game__tax_family='') | Q(game__tax_family__isnull=True))
        .filter(Q(game__species_group='') | Q(game__species_group__isnull=True))
        .filter(Q(game__season='') | Q(game__season__isnull=True))
        .exclude(
            game__game_type__in=[
                Game.GAME_TYPE_PAIR_PRACTICE,
                Game.GAME_TYPE_SPECIES_PRACTICE,
            ]
        )
        .select_related('player', 'game')
        .order_by('-score')
    )


def _highscores(country, *, limit: int = TOP_N) -> list[dict]:
    rows = []
    for score in _hiscore_qs(country)[:limit]:
        rows.append(
            {
                'name': sanitize_player_name(score.player.name if score.player else ''),
                'score': score.score,
                'level': score.game.level if score.game else '',
                'length': score.game.length if score.game else '',
            }
        )
    return rows


def missed_birds(country_code: str | None = None, *, limit: int = TOP_N) -> list[dict]:
    cache_key = _mistake_cache_key('missed-birds', country_code, limit)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    rows = get_species_mistake_rows(country_code)
    rows.sort(
        key=lambda row: (row['wrongly_answered'], row['error_rate'] or 0.0),
        reverse=True,
    )
    species_ids = [row['species_id'] for row in rows[:limit]]
    slugs = {
        pk: slug
        for pk, slug in Species.objects.filter(pk__in=species_ids).values_list('id', 'slug')
        if slug
    }
    out = []
    for row in rows[:limit]:
        slug = slugs.get(row['species_id']) or ''
        out.append(
            {
                'species_id': row['species_id'],
                'name': row['name'],
                'name_latin': row['name_latin'],
                'wrongly_answered': row['wrongly_answered'],
                'error_rate': row['error_rate'],
                'url': f'/site/birds/{slug}/' if slug else '',
            }
        )
    cache.set(cache_key, out, _MISTAKE_STATS_CACHE_TTL)
    return out


def confusion_pairs(country_code: str | None = None, *, limit: int = TOP_N) -> list[dict]:
    cache_key = _mistake_cache_key('confusion-pairs', country_code, limit)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    rows = get_confusion_pair_rows(country_code)[:limit]
    ids = {row['low_id'] for row in rows} | {row['high_id'] for row in rows}
    slugs = dict(
        Species.objects.filter(pk__in=ids).exclude(slug='').values_list('id', 'slug')
    )
    out = []
    for row in rows:
        slug_a = slugs.get(row['low_id']) or ''
        slug_b = slugs.get(row['high_id']) or ''
        compare_url = ''
        if slug_a and slug_b:
            compare_url = f'/site/compare/{compare_pair_slug(slug_a, slug_b)}/'
        out.append(
            {
                'low_id': row['low_id'],
                'high_id': row['high_id'],
                'low_name': row['low_name'],
                'high_name': row['high_name'],
                'total_wrong': row['total_wrong'],
                'url': compare_url,
            }
        )
    cache.set(cache_key, out, _MISTAKE_STATS_CACHE_TTL)
    return out


def country_page_stats(country, *, request=None) -> dict:
    code = country.code
    played = games_played_for_country(code)
    highscores = _highscores(country)
    challenge = country_challenge_leaderboard(
        limit=TOP_N,
        country_code=code,
        request=request,
    )
    missed = missed_birds(code)
    pairs = confusion_pairs(code)
    return {
        'games_played': played['games'],
        'players_played': played['players'],
        'show_games': played['games'] > 0,
        'games_href': '/data/games-played/',
        'highscores': highscores,
        'show_highscores': bool(highscores),
        'highscores_href': f'/scores/?country={code}',
        'challenge_rows': challenge,
        'show_challenge': bool(challenge),
        'challenge_leaderboard_href': f'/data/country-challenge-leaderboard/?country={code}',
        'missed_birds': missed,
        'show_missed': bool(missed),
        'missed_href': f'/data/quiz-mistakes/species/?country={code}',
        'confusion_pairs': pairs,
        'show_pairs': bool(pairs),
        'pairs_href': f'/data/quiz-mistakes/pairs/?country={code}',
    }
