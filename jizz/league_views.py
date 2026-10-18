"""National League API: today's quiz, week standings, caps, membership."""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from jizz import league
from jizz.flock_challenge import InsufficientChallengeContent
from jizz.models import Country, LeagueAttempt, LeagueDay, LeagueMembership
from jizz.serializers import GameSerializer


def _country(code: str) -> Country:
    return get_object_or_404(Country, code__iexact=code)


def _country_payload(country: Country) -> dict:
    return {'code': country.code, 'name': country.name, 'flag': league.flag_emoji(country.code)}


def _membership_payload(membership: LeagueMembership | None) -> dict | None:
    if membership is None:
        return None
    return {
        'country': _country_payload(membership.country),
        'reminders_enabled': membership.reminders_enabled,
        'reminder_mode': membership.reminder_mode,
        'joined_at': membership.joined_at.isoformat(),
    }


def _row(row: league.StandingRow, me_id, caps: dict) -> dict:
    return {
        'rank': row.rank,
        'name': row.name,
        'score': row.score,
        'correct': row.correct,
        'days_played': row.days_played,
        'is_me': row.user_id == me_id,
        'caps': caps.get(row.user_id, {'week_champion': 0, 'daily_wins': 0}),
    }


def _board(rows: list[league.StandingRow], country: Country, me_id) -> tuple[list[dict], list[dict]]:
    """Top 10 plus the rows around me when I'm further down."""
    top = rows[:league.TOP_SIZE]
    around = []
    my_rank = league.rank_of(rows, me_id) if me_id else None
    if my_rank and my_rank > league.TOP_SIZE:
        around = rows[my_rank - 2: my_rank + 1]
    caps = league.caps_by_user([r.user_id for r in top + around], country)
    return [_row(r, me_id, caps) for r in top], [_row(r, me_id, caps) for r in around]


class LeagueOverviewView(APIView):
    """GET — my leagues, suggested league (favourite country) and caps."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({'memberships': [], 'suggested': [], 'caps': []})
        memberships = list(LeagueMembership.objects.filter(user=user).select_related('country'))
        member_codes = {m.country_id for m in memberships}
        suggested = []
        profile = getattr(user, 'profile', None)
        if profile and profile.country_id and profile.country_id not in member_codes:
            suggested.append(_country_payload(profile.country))
        caps = []
        for membership in memberships:
            caps.append({'country_code': membership.country_id, **league.caps_for(user, membership.country)})
        return Response({
            'memberships': [_membership_payload(m) for m in memberships],
            'suggested': suggested,
            'caps': caps,
        })


class LeagueCountryView(APIView):
    """GET — today's quiz card and this week's standings for a country."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, code):
        country = _country(code)
        user = request.user if request.user.is_authenticated else None
        me_id = user.id if user else None
        local_now = league.league_local_now(country)
        today = local_now.date()
        week_start = league.week_start_for(today)

        league_day = LeagueDay.objects.filter(country=country, date=today).first()
        attempt = None
        if league_day and user:
            attempt = LeagueAttempt.objects.filter(day=league_day, user=user).first()
        today_rows = league.day_standings(league_day) if league_day else []
        my_result = None
        if attempt and attempt.completed_at:
            my_result = {
                'score': attempt.score,
                'correct': attempt.correct_count,
                'length': league_day.length,
                'rank': league.rank_of(today_rows, me_id),
            }

        week_rows = league.week_standings(country, week_start)
        top, around = _board(week_rows, country, me_id)
        my_week_row = next((r for r in week_rows if r.user_id == me_id), None)

        played_by_date = {}
        if user:
            for a in LeagueAttempt.objects.filter(
                user=user, day__country=country, day__date__gte=week_start,
                day__date__lt=week_start + timedelta(days=7), completed_at__isnull=False,
            ).select_related('day'):
                played_by_date[a.day.date] = a.score
        days = []
        for offset in range(7):
            d = week_start + timedelta(days=offset)
            days.append({
                'date': d.isoformat(),
                'length': league.length_for(d),
                'played': d in played_by_date,
                'score': played_by_date.get(d),
                'is_today': d == today,
                'is_future': d > today,
            })

        membership = None
        if user:
            membership = LeagueMembership.objects.filter(user=user, country=country).select_related('country').first()

        return Response({
            'country': _country_payload(country),
            'timezone': country.league_timezone,
            'today': {
                'date': today.isoformat(),
                'length': league.length_for(today),
                'closes_at': league.closes_at(country, today).isoformat(),
                'played': bool(attempt and attempt.completed_at),
                'in_progress': bool(attempt and not attempt.completed_at),
                'players_count': len(today_rows),
                'my_result': my_result,
            },
            'week': {
                'start': week_start.isoformat(),
                'end': (week_start + timedelta(days=6)).isoformat(),
                'days': days,
                'my_rank': my_week_row.rank if my_week_row else None,
                'my_total': my_week_row.score if my_week_row else 0,
                'players_count': len(week_rows),
                'top': top,
                'around_me': around,
            },
            'membership': _membership_payload(membership),
            'caps': league.caps_for(user, country) if user else {'week_champion': 0, 'daily_wins': 0},
            'celebrations': league.pending_celebrations(user, country) if user else [],
        })


class LeagueJoinView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        country = _country(code)
        membership, created = LeagueMembership.objects.get_or_create(user=request.user, country=country)
        if not created and not membership.reminders_enabled:
            membership.reminders_enabled = True
            membership.save(update_fields=['reminders_enabled'])
        return Response(
            _membership_payload(membership),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LeagueLeaveView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        LeagueMembership.objects.filter(user=request.user, country=_country(code)).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeagueMembershipView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, code):
        membership = get_object_or_404(LeagueMembership, user=request.user, country=_country(code))
        if 'reminders_enabled' in request.data:
            membership.reminders_enabled = bool(request.data.get('reminders_enabled'))
            membership.save(update_fields=['reminders_enabled'])
        return Response(_membership_payload(membership))


class LeagueCelebrationsSeenView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        league.mark_celebrations_seen(request.user, _country(code))
        return Response(status=status.HTTP_204_NO_CONTENT)


class LeagueStartView(APIView):
    """POST — start (or resume) today's quiz."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        country = _country(code)
        today = league.league_today(country)
        try:
            league_day = league.get_or_create_league_day(country, today)
            attempt, created = league.start_attempt(league_day, request.user, request=request)
        except InsufficientChallengeContent as exc:
            return Response(
                {'error': 'insufficient_content', 'detail': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if attempt.completed_at:
            return Response({'error': 'already_played'}, status=status.HTTP_400_BAD_REQUEST)
        # Playing implies joining: reminders and standings follow the people who play.
        LeagueMembership.objects.get_or_create(user=request.user, country=country)
        return Response(
            {
                'game': GameSerializer(attempt.game, context={'request': request}).data,
                'player_token': attempt.player.token,
                'attempt_id': attempt.id,
                'length': league_day.length,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LeagueCompleteView(APIView):
    """POST — finish today's quiz; returns the result and celebration flags."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(
            LeagueAttempt.objects.select_related('day__country', 'game', 'player'),
            pk=attempt_id, user=request.user,
        )
        country = attempt.day.country
        week_start = league.week_start_for(attempt.day.date)
        previous_week_rows = league.week_standings(country, week_start, exclude_attempt_id=attempt.id)
        week_rank_previous = league.rank_of(previous_week_rows, request.user.id)
        previous_leader = previous_week_rows[0].user_id if previous_week_rows else None

        if not attempt.completed_at:
            answered = league.answered_count(attempt)
            if answered < attempt.day.length:
                return Response(
                    {'error': 'incomplete', 'answered': answered, 'length': attempt.day.length},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if attempt.day.closed_at:
                return Response({'error': 'day_closed'}, status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                attempt = LeagueAttempt.objects.select_for_update().select_related(
                    'day__country', 'game', 'player',
                ).get(pk=attempt.pk)
                if not attempt.completed_at:
                    league.finish_attempt(attempt)

        today_rows = league.day_standings(attempt.day)
        week_rows = league.week_standings(country, week_start)
        week_rank = league.rank_of(week_rows, request.user.id)
        my_week = next((r for r in week_rows if r.user_id == request.user.id), None)
        rank_today = league.rank_of(today_rows, request.user.id)
        change = None
        if week_rank_previous and week_rank:
            change = week_rank_previous - week_rank
        took_lead = week_rank == 1 and previous_leader not in (None, request.user.id)
        flag = league.flag_emoji(country.code)
        share = (
            f'{flag} I scored {attempt.correct_count}/{attempt.day.length} in today\'s {country.name} '
            f'Birdr League'
            + (f' and I\'m #{week_rank} this week' if week_rank else '')
            + '. Can you beat me? https://birdr.pro/league/' + country.code
        )
        return Response({
            'attempt_id': attempt.id,
            'country': _country_payload(country),
            'score': attempt.score,
            'correct': attempt.correct_count,
            'length': attempt.day.length,
            'rank_today': rank_today,
            'players_today': len(today_rows),
            'week_rank': week_rank,
            'week_rank_previous': week_rank_previous,
            'week_rank_change': change,
            'week_total': my_week.score if my_week else attempt.score,
            'week_days_played': my_week.days_played if my_week else 1,
            'took_lead': took_lead,
            'perfect': attempt.correct_count == attempt.day.length,
            'share_message': share,
        })


class LeagueLeaderboardView(APIView):
    """GET ?period=today|week|last_week|caps."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, code):
        country = _country(code)
        period = request.query_params.get('period', 'week')
        me_id = request.user.id if request.user.is_authenticated else None
        today = league.league_today(country)

        if period == 'caps':
            rows = league.caps_standings(country)[:100]
            for row in rows:
                row['is_me'] = row.pop('user_id') == me_id
            return Response({'period': period, 'rows': rows})

        if period == 'today':
            league_day = LeagueDay.objects.filter(country=country, date=today).first()
            standings = league.day_standings(league_day) if league_day else []
        elif period == 'last_week':
            standings = league.week_standings(country, league.week_start_for(today) - timedelta(days=7))
        else:
            period = 'week'
            standings = league.week_standings(country, league.week_start_for(today))
        standings = standings[:100]
        caps = league.caps_by_user([r.user_id for r in standings], country)
        return Response({'period': period, 'rows': [_row(r, me_id, caps) for r in standings]})
