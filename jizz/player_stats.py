"""Aggregate play stats used to reveal game modes and the Member stats modal."""

from __future__ import annotations

from django.db.models import Count, F, Q

from jizz.country_challenge_leaderboard import journey_leaderboard_row
from jizz.birdr_journey_views import get_journey_levels_ordered
from jizz.models import (
    Answer,
    BirdrJourney,
    FlockMembership,
    Game,
    LeagueAttempt,
    LeagueMembership,
    PlayerScore,
)
from jizz import league as league_mod


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


def _user_scores(user):
    return PlayerScore.objects.filter(player__user=user)


def member_stats_for_user(user, *, request=None) -> dict:
    """Stats payload for the authenticated Member stats modal."""
    scores = _user_scores(user)
    correct_answers = Answer.objects.filter(
        player_score__player__user=user,
        correct=True,
    ).count()
    species_identified = (
        Answer.objects.filter(
            player_score__player__user=user,
            correct=True,
        )
        .values('question__species_id')
        .distinct()
        .count()
    )

    levels = get_journey_levels_ordered()
    journeys = list(
        BirdrJourney.objects.filter(user=user).select_related('country', 'user', 'player')
    )
    # Guest players linked to this account may also have journeys.
    journeys += list(
        BirdrJourney.objects.filter(player__user=user)
        .exclude(pk__in=[j.pk for j in journeys])
        .select_related('country', 'user', 'player')
    )
    country_challenges = []
    for journey in journeys:
        row = journey_leaderboard_row(journey, levels=levels, request=request)
        country_challenges.append(
            {
                'country_code': row['country_code'],
                'country_name': row['country_name'],
                'level_title': row['level_title'],
                'level_icon_url': row['level_icon_url'],
                'step_label': row['step_label'],
                'step_number': row['step_number'],
                'step_total': row['step_total'],
                'is_champion': row['is_champion'],
                'level_index': row['level_index'],
            }
        )
    country_challenges.sort(
        key=lambda row: (-row['level_index'], -row['step_number'], row['country_name'].lower())
    )

    survival_qs = scores.filter(
        game__game_type=Game.GAME_TYPE_SURVIVAL,
        streak__gt=0,
    ).select_related('game__country', 'player')
    best_survival = survival_qs.order_by('-streak', '-score', 'id').first()
    survival_by_country = {}
    for score in survival_qs.order_by('game__country_id', '-streak', '-score', 'id'):
        code = score.game.country_id if score.game_id else None
        if not code or code in survival_by_country:
            continue
        country = score.game.country
        survival_by_country[code] = {
            'country_code': code,
            'country_name': country.name if country else code,
            'streak': score.streak,
        }
    survival_records = sorted(
        survival_by_country.values(),
        key=lambda row: (-row['streak'], row['country_name'].lower()),
    )

    memberships = list(
        LeagueMembership.objects.filter(user=user).select_related('country')
        .order_by(F('last_played_date').desc(nulls_last=True), '-joined_at')
    )
    caps_total = league_mod.caps_for(user)
    league_rows = []
    for membership in memberships:
        caps = league_mod.caps_for(user, membership.country)
        league_rows.append(
            {
                'country_code': membership.country_id,
                'country_name': membership.country.name,
                'flag': league_mod.flag_emoji(membership.country_id),
                'daily_wins': caps['daily_wins'],
                'week_champions': caps['week_champion'],
            }
        )
    league_quizzes = LeagueAttempt.objects.filter(
        user=user,
        completed_at__isnull=False,
    ).count()

    best_score = (
        scores.filter(game__isnull=False)
        .exclude(
            game__game_type__in=[
                Game.GAME_TYPE_SURVIVAL,
                Game.GAME_TYPE_LEAGUE,
                Game.GAME_TYPE_PAIR_PRACTICE,
                Game.GAME_TYPE_SPECIES_PRACTICE,
            ]
        )
        .select_related('game__country')
        .order_by('-score', 'id')
        .first()
    )
    best_score_payload = None
    if best_score and best_score.game_id:
        country = best_score.game.country
        best_score_payload = {
            'score': best_score.score,
            'country_code': best_score.game.country_id or '',
            'country_name': country.name if country else '',
            'level': best_score.game.level or '',
            'length': best_score.game.length or 0,
        }

    return {
        'member_since': user.date_joined.isoformat(),
        'games_played': completed_games_count(user=user),
        'correct_answers': correct_answers,
        'species_identified': species_identified,
        'country_challenges': country_challenges,
        'survival': {
            'best_streak': best_survival.streak if best_survival else 0,
            'best_country_code': (
                best_survival.game.country_id if best_survival and best_survival.game_id else ''
            ),
            'best_country_name': (
                best_survival.game.country.name
                if best_survival and best_survival.game_id and best_survival.game.country
                else ''
            ),
            'countries_played': len(survival_records),
            'records': survival_records[:8],
        },
        'national_league': {
            'memberships': len(memberships),
            'daily_wins': caps_total['daily_wins'],
            'week_champions': caps_total['week_champion'],
            'quizzes_played': league_quizzes,
            'leagues': league_rows,
        },
        'flocks_joined': FlockMembership.objects.filter(user=user).count(),
        'best_score': best_score_payload,
    }
