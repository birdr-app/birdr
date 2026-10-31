"""Public-safe game result payloads for share pages and Open Graph cards."""

from __future__ import annotations

from django.db.models import Count, Q

from jizz.models import Game, PlayerScore

PRIVATE_GAME_TYPES = {
    Game.GAME_TYPE_PAIR_PRACTICE,
    Game.GAME_TYPE_SPECIES_PRACTICE,
    Game.GAME_TYPE_MIXUP_PRACTICE,
}

MEDIA_LABELS = {
    'images': 'Pictures',
    'audio': 'Sounds',
    'video': 'Videos',
}


def game_is_shareable(game: Game | None) -> bool:
    if game is None:
        return False
    if game.game_type in PRIVATE_GAME_TYPES:
        return False
    return bool(game.ended)


def _level_label(level: str | None) -> str:
    if not level:
        return ''
    return level.replace('_', ' ').title()


def _media_label(media: str | None) -> str:
    if not media:
        return ''
    return MEDIA_LABELS.get(media, media.replace('_', ' ').title())


def game_share_subtitle(game: Game) -> str:
    parts = [
        _level_label(game.level),
        _media_label(game.media),
        f'{game.length} birds' if game.length else '',
    ]
    return ' · '.join(part for part in parts if part)


def game_share_players(game: Game) -> list[dict]:
    rows = list(
        PlayerScore.objects.filter(game=game)
        .select_related('player')
        .annotate(correct_count=Count('answers', filter=Q(answers__correct=True)))
        .order_by('-score', 'id')
    )
    players = []
    for rank, row in enumerate(rows, start=1):
        correct = int(getattr(row, 'correct_count', 0) or 0)
        length = game.length or 0
        players.append(
            {
                'rank': rank,
                'name': (row.player.name if row.player else None) or 'Player',
                'score': row.score,
                'score_label': f'{row.score} pts',
                'correct_count': correct,
                'correct_label': f'{correct}/{length} correct' if length else '',
            }
        )
    return players


def game_share_payload(game: Game, *, share_url: str, og_image: str) -> dict:
    players = game_share_players(game)
    country_name = game.country.name if game.country else 'Motmot quiz'
    subtitle = game_share_subtitle(game)
    winner = players[0] if players else None
    if winner and len(players) == 1:
        description = (
            f'{winner["name"]} scored {winner["score_label"]} in a Motmot quiz '
            f'({country_name}). Can you beat them?'
        )
    elif winner:
        description = (
            f'{winner["name"]} won with {winner["score_label"]} in a Motmot quiz '
            f'({country_name}). Can you beat them?'
        )
    else:
        description = f'A Motmot quiz result from {country_name}. Can you beat this score?'
    og_title = (
        f'{winner["score_label"]} — {country_name}'
        if winner
        else f'Motmot quiz — {country_name}'
    )
    return {
        'token': game.token,
        'country': {
            'code': game.country_id or '',
            'name': country_name,
        },
        'level': game.level,
        'level_label': _level_label(game.level),
        'media': game.media,
        'media_label': _media_label(game.media),
        'length': game.length,
        'subtitle': subtitle,
        'players': players,
        'share_url': share_url,
        'og_image': og_image,
        'og_title': og_title,
        'description': description,
    }
