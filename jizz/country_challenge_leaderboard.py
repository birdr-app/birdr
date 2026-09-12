from __future__ import annotations

from typing import Any

from jizz.birdr_journey_views import (
    get_journey_levels_ordered,
    get_level_steps_ordered,
    is_pending_level_celebration,
)
from jizz.models import BirdrJourney, Player
from jizz.services.species_cover import absolute_media_url
from jizz.user_names import player_name_for_user, sanitize_player_name


def journey_player_name(journey: BirdrJourney) -> str:
    if journey.player_id:
        return sanitize_player_name(journey.player.name)
    if journey.user_id:
        linked = Player.objects.filter(user_id=journey.user_id).order_by('id').first()
        if linked and linked.name.strip():
            return sanitize_player_name(linked.name.strip())
        return player_name_for_user(journey.user)
    return 'Player'


def _level_icon_url(level, request=None) -> str:
    if not level or not level.icon:
        return ''
    return absolute_media_url(level.icon.url, request)


def _level_at_index(levels, level_index):
    if level_index < 0 or level_index >= len(levels):
        return None
    return levels[level_index]


def journey_leaderboard_row(
    journey: BirdrJourney,
    *,
    levels,
    request=None,
) -> dict[str, Any]:
    level = _level_at_index(levels, journey.current_sequence)
    steps = get_level_steps_ordered(level) if level else []
    step_count = len(steps)
    champion = bool(level and level.is_champion)
    pending_celebration = is_pending_level_celebration(journey)

    if champion:
        step_number = step_count
        step_label = 'Champion'
    elif pending_celebration and step_count:
        step_number = step_count
        step_label = f'Step {step_count}'
    elif step_count:
        step_number = min(journey.current_step_sequence + 1, step_count)
        step_label = f'Step {step_number}'
    else:
        step_number = 0
        step_label = '—'

    sort_step = step_count if (champion or pending_celebration) and step_count else journey.current_step_sequence

    return {
        'player_name': journey_player_name(journey),
        'country_code': journey.country_id,
        'country_name': journey.country.name or journey.country_id,
        'level_index': journey.current_sequence,
        'level_title': level.title if level else '—',
        'level_title_nl': (level.title_nl or '') if level else '',
        'level_icon_url': _level_icon_url(level, request),
        'step_number': step_number,
        'step_total': step_count,
        'step_label': step_label,
        'is_champion': champion,
        'sort_step': sort_step,
        'updated': journey.updated.isoformat(),
    }


def country_challenge_leaderboard(
    *,
    limit: int = 100,
    country_code: str | None = None,
    request=None,
) -> list[dict[str, Any]]:
    """All-time Country Challenge progress, highest level first.

    When ``country_code`` is set, only journeys for that quiz country are included.
    """
    levels = get_journey_levels_ordered()

    journeys = BirdrJourney.objects.select_related('country', 'user', 'player').all()
    if country_code:
        journeys = journeys.filter(country_id=country_code)
    rows = [
        journey_leaderboard_row(journey, levels=levels, request=request)
        for journey in journeys
    ]
    rows.sort(
        key=lambda row: (
            -row['level_index'],
            -row['sort_step'],
            row['player_name'].lower(),
            row['country_code'],
        ),
    )
    ranked = rows[:limit]
    _assign_ranks(ranked)
    return ranked


def _score_key(row: dict[str, Any]) -> tuple:
    return (row['level_index'], row['sort_step'])


def _assign_ranks(rows: list[dict[str, Any]]) -> None:
    """Players with the same level and step share a competition rank (1, 1, 3)."""
    prev_key = None
    rank = 0
    for index, row in enumerate(rows):
        key = _score_key(row)
        if key != prev_key:
            rank = index + 1
            prev_key = key
        row['rank'] = rank
