"""Lifetime play stats used to reveal game modes gradually (see the clients' modeVisibility)."""

from __future__ import annotations

from django.db.models import Count, F, Q

from jizz.models import PlayerScore


def completed_games_count(*, user=None, player=None) -> int:
    """Distinct games this user (all their players) or guest player finished, of any type.

    Finished = force-ended, or every question answered. Survival games have no fixed
    length, so they only count once force-ended (the run is over).
    """
    if user is not None and getattr(user, 'is_authenticated', False):
        scores = PlayerScore.objects.filter(player__user=user)
    elif player is not None:
        scores = PlayerScore.objects.filter(player=player)
    else:
        return 0
    return (
        scores.filter(game__isnull=False)
        .annotate(answered=Count('answers', distinct=True))
        .filter(Q(game__force_ended=True) | Q(game__length__gt=0, answered__gte=F('game__length')))
        .values('game_id')
        .distinct()
        .count()
    )
