"""National League: one shared daily quiz per country, Monday–Sunday standings, caps.

Days follow the country's capital timezone (``Country.league_timezone``).
Everything here is idempotent so the 15-minute ``league_tick`` cron can be
missed or run twice without side effects.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from jizz.flock_challenge import InsufficientChallengeContent, generate_club_mix_snapshot
from jizz.models import (
    Answer,
    Country,
    Game,
    LeagueAttempt,
    LeagueDay,
    LeagueDayItem,
    LeagueMembership,
    LeagueNotificationLog,
    LeagueWeekResult,
    Player,
    PlayerScore,
)
from jizz.user_names import player_name_for_user, sanitize_player_name

logger = logging.getLogger(__name__)

WEEKDAY_LENGTH = 10
WEEKEND_LENGTH = 20

# (level, rarity, media, count) in play order: easy → hard, photos only.
LEAGUE_WEEKDAY_SLOTS = [
    ('beginner', Game.RARIT_FAMILIAR, 'images', 3),
    ('advanced', Game.RARIT_REGULAR, 'images', 4),
    ('advanced', Game.RARIT_EXCEPTIONAL, 'images', 3),
]
LEAGUE_WEEKEND_SLOTS = [
    ('beginner', Game.RARIT_FAMILIAR, 'images', 5),
    ('advanced', Game.RARIT_REGULAR, 'images', 8),
    ('advanced', Game.RARIT_EXCEPTIONAL, 'images', 7),
]

TOP_SIZE = 10


# --- Time helpers -----------------------------------------------------------

def league_tz(country: Country) -> ZoneInfo:
    try:
        return ZoneInfo(country.league_timezone)
    except Exception:
        return ZoneInfo('UTC')


def league_local_now(country: Country, at: datetime | None = None) -> datetime:
    return (at or timezone.now()).astimezone(league_tz(country))


def league_today(country: Country, at: datetime | None = None) -> date:
    return league_local_now(country, at).date()


def week_start_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def length_for(day: date) -> int:
    return WEEKEND_LENGTH if day.weekday() >= 5 else WEEKDAY_LENGTH


def slots_for(day: date):
    return LEAGUE_WEEKEND_SLOTS if day.weekday() >= 5 else LEAGUE_WEEKDAY_SLOTS


def closes_at(country: Country, day: date) -> datetime:
    """Capital-local midnight at the end of ``day``."""
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=league_tz(country))


# --- Days and attempts -------------------------------------------------------

def get_or_create_league_day(country: Country, day: date) -> LeagueDay:
    """The shared quiz for a country/date, generated on first use."""
    existing = LeagueDay.objects.filter(country=country, date=day).first()
    if existing and existing.items.exists():
        return existing

    # Generate outside the lock (slow); the unique (country, date) row decides the winner.
    snapshot = generate_club_mix_snapshot(country=country, host=None, slots=slots_for(day))
    try:
        with transaction.atomic():
            league_day, _ = LeagueDay.objects.select_for_update().get_or_create(
                country=country, date=day, defaults={'length': len(snapshot)},
            )
            if not league_day.items.exists():
                LeagueDayItem.objects.bulk_create([
                    LeagueDayItem(
                        day=league_day,
                        sequence=item.sequence,
                        species_id=item.species_id,
                        media_id=item.media_id,
                        media_type=item.media_type,
                        level=item.level,
                        rarity=item.rarity,
                        option_species_ids=item.option_species_ids,
                    )
                    for item in snapshot
                ])
    except IntegrityError:
        league_day = LeagueDay.objects.get(country=country, date=day)
    return league_day


def player_for_user(user) -> Player:
    player = Player.objects.filter(user=user).order_by('id').first()
    if player:
        return player
    return Player.objects.create(user=user, name=player_name_for_user(user))


def display_name(user, player: Player | None = None) -> str:
    if player and (player.name or '').strip():
        return sanitize_player_name(player.name)
    return player_name_for_user(user)


@transaction.atomic
def clone_day_into_game(league_day: LeagueDay, host: Player, language: str = 'en') -> Game:
    from jizz.pregenerated_game import PregeneratedItem, fill_pregenerated_game

    items = list(league_day.items.order_by('sequence'))
    if len(items) != league_day.length:
        raise InsufficientChallengeContent(
            'League day snapshot is incomplete.', needed=league_day.length, available=len(items),
        )
    game = Game.objects.create(
        country=league_day.country,
        level='advanced',
        length=league_day.length,
        media='images',
        rarity=Game.RARIT_REGULAR,
        include_escapes=False,
        multiplayer=False,
        host=host,
        language=language or 'en',
        game_type=Game.GAME_TYPE_LEAGUE,
        questions_pregenerated=True,
    )
    pregenerated = []
    for item in items:
        option_ids = list(item.option_species_ids or [])
        random.shuffle(option_ids)  # same birds for everyone, own button order
        pregenerated.append(PregeneratedItem(
            sequence=item.sequence,
            species_id=item.species_id,
            media_id=item.media_id,
            option_species_ids=option_ids,
        ))
    fill_pregenerated_game(game, pregenerated)
    PlayerScore.objects.get_or_create(player=host, game=game, defaults={'score': 0})
    return game


def start_attempt(league_day: LeagueDay, user, request=None) -> tuple[LeagueAttempt, bool]:
    """Return (attempt, created). Resumes an in-progress attempt."""
    existing = LeagueAttempt.objects.filter(day=league_day, user=user).select_related('game', 'player').first()
    if existing:
        return existing, False
    player = player_for_user(user)
    try:
        with transaction.atomic():
            game = clone_day_into_game(league_day, player, language=player.language or 'en')
            attempt = LeagueAttempt.objects.create(day=league_day, user=user, player=player, game=game)
    except IntegrityError:
        return LeagueAttempt.objects.select_related('game', 'player').get(day=league_day, user=user), False
    if request is not None:
        from jizz.client_info import record_player_score_client_from_request

        record_player_score_client_from_request(player, game, request)
    return attempt, True


def answered_count(attempt: LeagueAttempt) -> int:
    return Answer.objects.filter(player_score__player=attempt.player, player_score__game=attempt.game).count()


def refresh_attempt_stats(attempt: LeagueAttempt) -> None:
    ps = PlayerScore.objects.filter(game=attempt.game, player=attempt.player).first()
    attempt.correct_count = Answer.objects.filter(player_score=ps, correct=True).count() if ps else 0
    attempt.score = (ps.score or 0) if ps else 0


def finish_attempt(attempt: LeagueAttempt, at: datetime | None = None) -> None:
    refresh_attempt_stats(attempt)
    attempt.completed_at = at or timezone.now()
    attempt.save(update_fields=['correct_count', 'score', 'completed_at'])
    if not attempt.game.force_ended:
        attempt.game.force_ended = True
        attempt.game.save(update_fields=['force_ended'])
    LeagueMembership.objects.filter(user=attempt.user, country=attempt.day.country).update(
        last_played_date=attempt.day.date,
        reminder_mode=LeagueMembership.REMINDERS_NORMAL,
    )


# --- Standings ---------------------------------------------------------------

@dataclass
class StandingRow:
    user_id: int
    name: str
    score: int
    correct: int = 0
    days_played: int = 0
    rank: int = 0


def day_standings(league_day: LeagueDay) -> list[StandingRow]:
    attempts = (
        LeagueAttempt.objects.filter(day=league_day, completed_at__isnull=False)
        .select_related('user', 'player')
        .order_by('-score', '-correct_count', 'completed_at', 'id')
    )
    rows = [
        StandingRow(user_id=a.user_id, name=display_name(a.user, a.player), score=a.score,
                    correct=a.correct_count, days_played=1)
        for a in attempts
    ]
    for i, row in enumerate(rows, start=1):
        row.rank = i
    return rows


def week_standings(country: Country, week_start: date, *, exclude_attempt_id: int | None = None) -> list[StandingRow]:
    attempts = LeagueAttempt.objects.filter(
        day__country=country,
        day__date__gte=week_start,
        day__date__lt=week_start + timedelta(days=7),
        completed_at__isnull=False,
    )
    if exclude_attempt_id:
        attempts = attempts.exclude(pk=exclude_attempt_id)
    totals = (
        attempts.values('user_id')
        .annotate(total=Sum('score'), correct=Sum('correct_count'), days=Count('id'), last=Max('completed_at'))
        .order_by('-total', '-days', 'last', 'user_id')
    )
    totals = list(totals)
    players = {}
    for p in Player.objects.filter(user_id__in=[t['user_id'] for t in totals]).select_related('user').order_by('id'):
        players.setdefault(p.user_id, p)
    rows = []
    for i, t in enumerate(totals, start=1):
        player = players.get(t['user_id'])
        rows.append(StandingRow(
            user_id=t['user_id'],
            name=display_name(player.user if player else None, player),
            score=t['total'] or 0,
            correct=t['correct'] or 0,
            days_played=t['days'],
            rank=i,
        ))
    return rows


def rank_of(rows: list[StandingRow], user_id) -> int | None:
    for row in rows:
        if row.user_id == user_id:
            return row.rank
    return None


def caps_for(user, country: Country | None = None) -> dict:
    days = LeagueDay.objects.filter(winner=user)
    weeks = LeagueWeekResult.objects.filter(user=user, is_champion=True)
    if country is not None:
        days = days.filter(country=country)
        weeks = weeks.filter(country=country)
    return {'week_champion': weeks.count(), 'daily_wins': days.count()}


def caps_by_user(user_ids, country: Country) -> dict[int, dict]:
    wins = dict(
        LeagueDay.objects.filter(country=country, winner_id__in=user_ids)
        .values('winner_id').annotate(n=Count('id')).values_list('winner_id', 'n')
    )
    champs = dict(
        LeagueWeekResult.objects.filter(country=country, user_id__in=user_ids, is_champion=True)
        .values('user_id').annotate(n=Count('id')).values_list('user_id', 'n')
    )
    return {uid: {'week_champion': champs.get(uid, 0), 'daily_wins': wins.get(uid, 0)} for uid in user_ids}


def caps_standings(country: Country) -> list[dict]:
    wins = dict(
        LeagueDay.objects.filter(country=country, winner__isnull=False)
        .values('winner_id').annotate(n=Count('id')).values_list('winner_id', 'n')
    )
    champs = dict(
        LeagueWeekResult.objects.filter(country=country, is_champion=True)
        .values('user_id').annotate(n=Count('id')).values_list('user_id', 'n')
    )
    user_ids = set(wins) | set(champs)
    players = {}
    for p in Player.objects.filter(user_id__in=user_ids).select_related('user').order_by('id'):
        players.setdefault(p.user_id, p)
    rows = sorted(
        user_ids,
        key=lambda uid: (-champs.get(uid, 0), -wins.get(uid, 0), uid),
    )
    out = []
    for i, uid in enumerate(rows, start=1):
        player = players.get(uid)
        out.append({
            'rank': i,
            'user_id': uid,
            'name': display_name(player.user if player else None, player),
            'week_champion': champs.get(uid, 0),
            'daily_wins': wins.get(uid, 0),
        })
    return out


# --- Closing days and weeks ---------------------------------------------------

def close_day(league_day: LeagueDay) -> None:
    """Finalise unfinished attempts with the answers they have, then crown the daily winner."""
    if league_day.closed_at:
        return
    close_time = closes_at(league_day.country, league_day.date)
    for attempt in LeagueAttempt.objects.filter(day=league_day, completed_at__isnull=True).select_related('game', 'day__country'):
        if answered_count(attempt) > 0:
            finish_attempt(attempt, at=close_time)
    rows = day_standings(league_day)
    with transaction.atomic():
        league_day.winner_id = rows[0].user_id if rows else None
        league_day.closed_at = timezone.now()
        league_day.save(update_fields=['winner', 'closed_at'])
        if rows:
            LeagueNotificationLog.objects.get_or_create(
                user_id=rows[0].user_id, country=league_day.country, date=league_day.date,
                kind=LeagueNotificationLog.KIND_DAILY_WIN,
            )


def close_week(country: Country, week_start: date) -> None:
    if LeagueWeekResult.objects.filter(country=country, week_start=week_start).exists():
        return
    rows = week_standings(country, week_start)
    if not rows:
        return
    with transaction.atomic():
        LeagueWeekResult.objects.bulk_create([
            LeagueWeekResult(
                country=country, week_start=week_start, user_id=row.user_id,
                total_score=row.score, days_played=row.days_played, rank=row.rank,
                is_champion=row.rank == 1,
            )
            for row in rows
        ], ignore_conflicts=True)
        LeagueNotificationLog.objects.get_or_create(
            user_id=rows[0].user_id, country=country, date=week_start,
            kind=LeagueNotificationLog.KIND_WEEK_CHAMPION,
        )


def pending_celebrations(user, country: Country) -> list[dict]:
    logs = LeagueNotificationLog.objects.filter(
        user=user, country=country, kind__in=LeagueNotificationLog.CELEBRATION_KINDS, seen_at__isnull=True,
    ).order_by('date')
    out = []
    for log in logs:
        if log.kind == LeagueNotificationLog.KIND_DAILY_WIN:
            out.append({'kind': log.kind, 'date': log.date.isoformat()})
        else:
            out.append({'kind': log.kind, 'week_start': log.date.isoformat(), 'rank': 1})
    return out


def mark_celebrations_seen(user, country: Country) -> None:
    LeagueNotificationLog.objects.filter(
        user=user, country=country, kind__in=LeagueNotificationLog.CELEBRATION_KINDS, seen_at__isnull=True,
    ).update(seen_at=timezone.now())


# --- Reminders ---------------------------------------------------------------

REMINDER_KINDS = (
    LeagueNotificationLog.KIND_REMINDER_18,
    LeagueNotificationLog.KIND_REMINDER_20,
    LeagueNotificationLog.KIND_FINAL_DAY,
    LeagueNotificationLog.KIND_WEEKLY_RECAP,
    LeagueNotificationLog.KIND_FRESH_START,
)
MAX_PUSHES_PER_DAY = 2
WINDOW_MINUTES = 30


def reminder_mode_for(membership: LeagueMembership, today: date) -> str:
    """Back off when someone stops playing: 3 missed days → evening only, 7 → paused."""
    reference = membership.last_played_date or timezone.localdate(membership.joined_at)
    missed = (today - reference).days - (1 if membership.last_played_date else 0)
    if missed >= 7:
        return LeagueMembership.REMINDERS_PAUSED
    if missed >= 3:
        return LeagueMembership.REMINDERS_EVENING_ONLY
    return LeagueMembership.REMINDERS_NORMAL


def flag_emoji(code: str) -> str:
    code = (code or '').upper()[:2]
    if len(code) == 2 and code.isalpha():
        return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code)
    return '🐦'


def _user_language(user) -> str:
    profile = getattr(user, 'profile', None)
    lang = (getattr(profile, 'app_language', '') or getattr(profile, 'language', '') or 'en').lower()
    return 'nl' if lang.startswith('nl') else 'en'


MESSAGES = {
    'en': {
        'title': '{flag} Birdr League',
        LeagueNotificationLog.KIND_REMINDER_18: "Today's {length} birds are waiting. Can you climb the {country} table?",
        LeagueNotificationLog.KIND_REMINDER_20: '4 hours left for today\'s quiz! 🐦',
        LeagueNotificationLog.KIND_FINAL_DAY: 'Final day! You\'re #{rank}, {gap} pts behind #{target}.',
        'final_day_lead': 'Final day! You lead the {country} league. Hold on! 🏆',
        LeagueNotificationLog.KIND_WEEKLY_RECAP: 'You finished #{rank} in {country}. Week champion: {champion} 🏆',
        'weekly_recap_champion': 'You are the {country} week champion! 🏆',
        LeagueNotificationLog.KIND_FRESH_START: 'New week, fresh start. Today\'s birds are ready!',
        LeagueNotificationLog.KIND_INVITE: 'The {country} National League has started: one short bird quiz a day. Join in!',
    },
    'nl': {
        'title': '{flag} Birdr League',
        LeagueNotificationLog.KIND_REMINDER_18: 'De {length} vogels van vandaag wachten op je. Klim jij op in {country}?',
        LeagueNotificationLog.KIND_REMINDER_20: 'Nog 4 uur voor de quiz van vandaag! 🐦',
        LeagueNotificationLog.KIND_FINAL_DAY: 'Laatste dag! Je staat #{rank}, {gap} punten achter #{target}.',
        'final_day_lead': 'Laatste dag! Je staat bovenaan in {country}. Volhouden! 🏆',
        LeagueNotificationLog.KIND_WEEKLY_RECAP: 'Je eindigde #{rank} in {country}. Weekkampioen: {champion} 🏆',
        'weekly_recap_champion': 'Jij bent weekkampioen van {country}! 🏆',
        LeagueNotificationLog.KIND_FRESH_START: 'Nieuwe week, nieuwe kansen. De vogels van vandaag staan klaar!',
        LeagueNotificationLog.KIND_INVITE: 'De nationale Birdr League voor {country} is begonnen: elke dag een korte vogelquiz. Doe mee!',
    },
}


def _send(user, country: Country, kind: str, body_key: str, **fmt) -> bool:
    from jizz.notifications import send_push_to_user

    lang = _user_language(user)
    messages = MESSAGES[lang]
    values = {'country': country.name, 'flag': flag_emoji(country.code), **fmt}
    title = messages['title'].format(**values)
    body = messages[body_key].format(**values)
    try:
        send_push_to_user(user, title, body, data={'type': 'league', 'country_code': country.code, 'kind': kind})
    except Exception:
        logger.exception('League push %s failed for user %s', kind, user.pk)
        return False
    return True


def _claim(user, country: Country, day: date, kind: str) -> bool:
    """Record a notification; False when it was already sent (or the daily budget is used)."""
    if kind in REMINDER_KINDS:
        sent_today = LeagueNotificationLog.objects.filter(
            user=user, country=country, date=day, kind__in=REMINDER_KINDS,
        ).count()
        if sent_today >= MAX_PUSHES_PER_DAY:
            return False
    _, created = LeagueNotificationLog.objects.get_or_create(user=user, country=country, date=day, kind=kind)
    return created


def _in_window(local: datetime, hour: int) -> bool:
    start = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    return start <= local < start + timedelta(minutes=WINDOW_MINUTES)


def send_due_notifications(country: Country, local: datetime) -> int:
    today = local.date()
    weekday = today.weekday()
    sent = 0
    members = list(
        LeagueMembership.objects.filter(country=country, reminders_enabled=True).select_related('user', 'user__profile')
    )
    if not members:
        return 0
    played_today = set(
        LeagueAttempt.objects.filter(day__country=country, day__date=today, completed_at__isnull=False)
        .values_list('user_id', flat=True)
    )

    for membership in members:
        mode = reminder_mode_for(membership, today)
        if mode != membership.reminder_mode:
            membership.reminder_mode = mode
            membership.save(update_fields=['reminder_mode'])

    # Monday 09:00: last week's recap, or a single "fresh start" for paused members.
    if weekday == 0 and _in_window(local, 9):
        last_week = week_start_for(today) - timedelta(days=7)
        rows = week_standings(country, last_week)
        champion = rows[0].name if rows else ''
        for membership in members:
            user = membership.user
            rank = rank_of(rows, user.id)
            if rank is not None:
                if _claim(user, country, today, LeagueNotificationLog.KIND_WEEKLY_RECAP):
                    key = 'weekly_recap_champion' if rank == 1 else LeagueNotificationLog.KIND_WEEKLY_RECAP
                    sent += _send(user, country, LeagueNotificationLog.KIND_WEEKLY_RECAP, key, rank=rank, champion=champion)
            elif membership.reminder_mode == LeagueMembership.REMINDERS_PAUSED:
                if _claim(user, country, today, LeagueNotificationLog.KIND_FRESH_START):
                    sent += _send(user, country, LeagueNotificationLog.KIND_FRESH_START, LeagueNotificationLog.KIND_FRESH_START)

    for hour, kind in ((18, LeagueNotificationLog.KIND_REMINDER_18), (20, LeagueNotificationLog.KIND_REMINDER_20)):
        if not _in_window(local, hour):
            continue
        week_rows = week_standings(country, week_start_for(today)) if weekday == 6 and hour == 18 else []
        for membership in members:
            user = membership.user
            if user.id in played_today:
                continue
            if membership.reminder_mode == LeagueMembership.REMINDERS_PAUSED:
                continue
            if kind == LeagueNotificationLog.KIND_REMINDER_18:
                if membership.reminder_mode != LeagueMembership.REMINDERS_NORMAL:
                    continue
                # A morning recap already used one push today: save the other for "4 hours left".
                if weekday == 0 and LeagueNotificationLog.objects.filter(
                    user=user, country=country, date=today,
                    kind__in=(LeagueNotificationLog.KIND_WEEKLY_RECAP, LeagueNotificationLog.KIND_FRESH_START),
                ).exists():
                    continue
            rank = rank_of(week_rows, user.id) if week_rows else None
            if rank is not None:
                # Sunday evening: the final-day push replaces the plain 18:00 reminder.
                if not _claim(user, country, today, LeagueNotificationLog.KIND_FINAL_DAY):
                    continue
                if rank == 1:
                    sent += _send(user, country, LeagueNotificationLog.KIND_FINAL_DAY, 'final_day_lead')
                else:
                    target = week_rows[rank - 2]
                    gap = target.score - week_rows[rank - 1].score
                    sent += _send(user, country, LeagueNotificationLog.KIND_FINAL_DAY,
                                  LeagueNotificationLog.KIND_FINAL_DAY, rank=rank, gap=gap, target=target.rank)
                continue
            if _claim(user, country, today, kind):
                sent += _send(user, country, kind, kind, length=length_for(today))
    return sent


# --- Tick ----------------------------------------------------------------------

def league_countries():
    return Country.objects.filter(
        Q(league_memberships__isnull=False) | Q(league_days__isnull=False)
    ).distinct()


def tick(at: datetime | None = None) -> dict:
    """Close finished days/weeks and send due notifications for every league country."""
    summary = {'closed_days': 0, 'closed_weeks': 0, 'notifications': 0}
    for country in league_countries():
        local = league_local_now(country, at)
        today = local.date()
        for league_day in LeagueDay.objects.filter(country=country, date__lt=today, closed_at__isnull=True):
            close_day(league_day)
            summary['closed_days'] += 1
        last_week = week_start_for(today) - timedelta(days=7)
        if not LeagueWeekResult.objects.filter(country=country, week_start=last_week).exists():
            if LeagueAttempt.objects.filter(
                day__country=country, day__date__gte=last_week, day__date__lt=week_start_for(today),
                completed_at__isnull=False,
            ).exists():
                close_week(country, last_week)
                summary['closed_weeks'] += 1
        summary['notifications'] += send_due_notifications(country, local)
    return summary
