"""Flock challenge lifecycle: start, auto-renew, last-day reminders and results pushes.

``tick()`` runs hourly from the ``flock_tick`` command. It is idempotent: every push is
recorded in FlockNotificationLog and every closed challenge gets ``results_sent_at``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from jizz import flock_views
from jizz.flock_challenge import CLUB_MIX_LENGTH, InsufficientChallengeContent, persist_challenge_snapshot
from jizz.models import (
    Flock,
    FlockChallenge,
    FlockChallengeAttempt,
    FlockMembership,
    FlockNotificationLog,
)

logger = logging.getLogger(__name__)

LAST_DAY = timedelta(hours=24)
# Challenges that ended longer ago than this are closed silently (no stale results push).
RESULTS_GRACE = timedelta(hours=48)


def challenge_days(challenge: FlockChallenge) -> int:
    days = round((challenge.ends_at - challenge.starts_at) / timedelta(days=1))
    return max(1, min(days, 30))


def start_challenge(
    flock: Flock,
    *,
    created_by,
    country,
    title: str,
    days: int,
    notify: bool = True,
    exclude_user_id: int | None = None,
) -> FlockChallenge:
    """Create and snapshot a new active challenge. Raises InsufficientChallengeContent."""
    host = flock_views._get_or_create_player_for_user(created_by)
    snapshot = flock_views.generate_club_mix_snapshot(country=country, host=host)
    starts = timezone.now()
    with transaction.atomic():
        challenge = FlockChallenge.objects.create(
            flock=flock,
            title=title[:160],
            country=country,
            length=CLUB_MIX_LENGTH,
            preset=FlockChallenge.PRESET_CLUB_MIX,
            status=FlockChallenge.STATUS_ACTIVE,
            starts_at=starts,
            ends_at=starts + timedelta(days=days),
            created_by=created_by,
            public_token=flock_views._public_token(8),
        )
        persist_challenge_snapshot(challenge, snapshot)
    if notify:
        flock_views._notify_flock_challenge(flock, challenge, exclude_user_id=exclude_user_id)
    return challenge


# --- Messages ------------------------------------------------------------------

def _lang(user) -> str:
    profile = getattr(user, 'profile', None)
    lang = (getattr(profile, 'app_language', '') or getattr(profile, 'language', '') or 'en').lower()
    return 'nl' if lang.startswith('nl') else 'en'


MESSAGES = {
    'en': {
        'title': 'Motmot: {flock}',
        'last_day': "1 day left to play this week's challenge, {challenge}. Tap to play!",
        'won': "🏆 You won last week's challenge with {score}! ({players} played)",
        'ranked': "Last week's challenge: {winner} won with {wscore}. You finished #{rank} of {players} ({score}).",
        'missed': "Last week's challenge: {winner} won with {wscore}. {players} birders played.",
        'missed_one': "Last week's challenge: {winner} won with {wscore}.",
        'nobody': "Last week's challenge has ended.",
        'renewed': ' New challenge is live, play now!',
    },
    'nl': {
        'title': 'Motmot: {flock}',
        'last_day': 'Nog 1 dag om de challenge van deze week te spelen: {challenge}. Tik om te spelen!',
        'won': '🏆 Je hebt de challenge van vorige week gewonnen met {score}! ({players} spelers)',
        'ranked': 'Challenge van vorige week: {winner} won met {wscore}. Jij werd #{rank} van {players} ({score}).',
        'missed': 'Challenge van vorige week: {winner} won met {wscore}. {players} vogelaars speelden mee.',
        'missed_one': 'Challenge van vorige week: {winner} won met {wscore}.',
        'nobody': 'De challenge van vorige week is afgelopen.',
        'renewed': ' Er staat een nieuwe challenge klaar, speel nu!',
    },
}


def _claim(user, challenge: FlockChallenge, kind: str) -> bool:
    try:
        _, created = FlockNotificationLog.objects.get_or_create(user=user, challenge=challenge, kind=kind)
    except IntegrityError:
        return False
    return created


def _push(user, title: str, body: str, data: dict) -> int:
    try:
        flock_views.send_push_to_user(user, title, body, data=data)
    except Exception:
        logger.exception('Flock push failed for user %s', user.pk)
        return 0
    return 1


def _members(flock: Flock):
    return (
        FlockMembership.objects.filter(flock=flock, notifications_enabled=True)
        .select_related('user', 'user__profile')
    )


def _score(row) -> str:
    return f'{row.correct_count}/{row.challenge.length}'


def results_body(lang: str, user_id: int, rows: list[FlockChallengeAttempt], renewed: bool) -> str:
    msg = MESSAGES[lang]
    if not rows:
        body = msg['nobody']
    else:
        winner = rows[0]
        mine = next((i for i, row in enumerate(rows, start=1) if row.user_id == user_id), None)
        if mine == 1:
            body = msg['won'].format(score=_score(winner), players=len(rows))
        elif mine:
            body = msg['ranked'].format(
                winner=flock_views._display_name(winner.user), wscore=_score(winner),
                rank=mine, players=len(rows), score=_score(rows[mine - 1]),
            )
        else:
            body = msg['missed' if len(rows) > 1 else 'missed_one'].format(
                winner=flock_views._display_name(winner.user), wscore=_score(winner), players=len(rows),
            )
    return body + (msg['renewed'] if renewed else '')


# --- Tick ------------------------------------------------------------------------

def send_last_day_reminders(now: datetime) -> int:
    sent = 0
    challenges = FlockChallenge.objects.filter(
        status=FlockChallenge.STATUS_ACTIVE,
        starts_at__lte=now,
        ends_at__gt=now,
        ends_at__lte=now + LAST_DAY,
    ).select_related('flock')
    for challenge in challenges:
        played = set(
            FlockChallengeAttempt.objects.filter(
                challenge=challenge, is_ranked=True, completed_at__isnull=False,
            ).values_list('user_id', flat=True)
        )
        data = {'type': 'flock_challenge', 'flock_slug': challenge.flock.slug, 'challenge_id': challenge.id}
        for membership in _members(challenge.flock):
            user = membership.user
            if user.id in played or not _claim(user, challenge, FlockNotificationLog.KIND_LAST_DAY):
                continue
            msg = MESSAGES[_lang(user)]
            sent += _push(
                user,
                msg['title'].format(flock=challenge.flock.name),
                msg['last_day'].format(challenge=challenge.title),
                data,
            )
    return sent


def close_ended_challenges(now: datetime) -> list[FlockChallenge]:
    """Mark ended challenges as ENDED; return those recent enough for a results push."""
    recent = []
    ended = FlockChallenge.objects.filter(
        status=FlockChallenge.STATUS_ACTIVE, ends_at__lte=now, results_sent_at__isnull=True,
    ).values_list('pk', flat=True)
    for pk in list(ended):
        with transaction.atomic():
            challenge = FlockChallenge.objects.select_for_update().select_related('flock').get(pk=pk)
            if challenge.results_sent_at:
                continue
            challenge.status = FlockChallenge.STATUS_ENDED
            challenge.results_sent_at = now
            challenge.save(update_fields=['status', 'results_sent_at'])
        if challenge.ends_at >= now - RESULTS_GRACE:
            recent.append(challenge)
    return recent


def renew_challenges(now: datetime) -> dict[int, FlockChallenge]:
    """For auto-renew flocks without an open challenge, start one like the latest."""
    renewed: dict[int, FlockChallenge] = {}
    for flock in Flock.objects.filter(auto_renew_challenges=True).select_related('owner'):
        if flock.challenges.filter(status=FlockChallenge.STATUS_ACTIVE, ends_at__gt=now).exists():
            continue
        latest = flock.challenges.select_related('country', 'created_by').order_by('-starts_at').first()
        if latest is None or latest.ends_at > now:
            continue
        try:
            renewed[flock.id] = start_challenge(
                flock,
                created_by=latest.created_by or flock.owner,
                country=latest.country,
                title=latest.title,
                days=challenge_days(latest),
                notify=False,  # announced together with the results
            )
        except InsufficientChallengeContent as exc:
            logger.warning('Flock %s: could not auto-renew challenge: %s', flock.slug, exc)
    return renewed


def send_results(challenges: list[FlockChallenge], renewed: dict[int, FlockChallenge]) -> int:
    sent = 0
    for challenge in challenges:
        rows = flock_views._leaderboard_rows(challenge)
        new = renewed.get(challenge.flock_id)
        data = {
            'type': 'flock_challenge',
            'flock_slug': challenge.flock.slug,
            'challenge_id': (new or challenge).id,
        }
        for membership in _members(challenge.flock):
            user = membership.user
            if not _claim(user, challenge, FlockNotificationLog.KIND_RESULTS):
                continue
            lang = _lang(user)
            sent += _push(
                user,
                MESSAGES[lang]['title'].format(flock=challenge.flock.name),
                results_body(lang, user.id, rows, renewed=new is not None),
                data,
            )
    # A renewal whose old challenge was too old for a results push still gets announced.
    announced = {c.flock_id for c in challenges}
    for flock_id, new in renewed.items():
        if flock_id not in announced:
            flock_views._notify_flock_challenge(new.flock, new)
    return sent


def tick(now: datetime | None = None) -> dict:
    now = now or timezone.now()
    reminders = send_last_day_reminders(now)
    closed = close_ended_challenges(now)
    renewed = renew_challenges(now)
    results = send_results(closed, renewed)
    return {'reminders': reminders, 'closed': len(closed), 'renewed': len(renewed), 'results': results}
