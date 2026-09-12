"""API views for Birdr Flocks (Phase 1)."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from jizz.daily_challenge_views import _get_or_create_player_for_user
from jizz.flock_challenge import (
    CLUB_MIX_LENGTH,
    InsufficientChallengeContent,
    clone_challenge_into_game,
    generate_club_mix_snapshot,
    generate_invite_code,
    link_attempt_questions,
    persist_challenge_snapshot,
    unique_flock_slug,
)
from jizz.models import (
    Answer,
    Country,
    Flock,
    FlockChallenge,
    FlockChallengeAttempt,
    FlockInvite,
    FlockMembership,
    PlayerScore,
)
from jizz.services.species_cover import absolute_media_url
from jizz.user_names import player_name_for_user
from jizz.notifications import send_push_to_user


def _public_token(nbytes: int = 8) -> str:
    return secrets.token_urlsafe(nbytes)[:nbytes * 2][:16]


def _result_token() -> str:
    return secrets.token_urlsafe(12)[:24]


def _absolute_url(request, path: str) -> str:
    """Public absolute URL (invite/share); prefers SITE_URL and forces https in prod."""
    return absolute_media_url(path, request)


def _notify_flock_challenge(flock: Flock, challenge: FlockChallenge, exclude_user_id: int | None = None):
    """Push members to play a newly started flock challenge."""
    memberships = (
        FlockMembership.objects.filter(flock=flock)
        .exclude(user_id=exclude_user_id)
        .select_related('user')
    )
    title = f'Birdr: {flock.name}'
    body = f'New challenge ready — play {challenge.title} now!'
    data = {
        'type': 'flock_challenge',
        'flock_slug': flock.slug,
        'challenge_id': challenge.id,
    }
    for membership in memberships:
        try:
            send_push_to_user(membership.user, title, body, data=data)
        except Exception:
            pass


def _active_invite(flock: Flock) -> FlockInvite | None:
    return flock.invites.filter(is_active=True).order_by('-created_at').first()


def _ensure_owner_membership(flock: Flock, user) -> None:
    FlockMembership.objects.get_or_create(
        flock=flock,
        user=user,
        defaults={'role': FlockMembership.ROLE_OWNER},
    )


def _require_admin(flock: Flock, user) -> None:
    if not flock.is_admin(user):
        raise PermissionDenied('Only flock admins can perform this action.')


def _require_member(flock: Flock, user) -> None:
    if not flock.is_member(user):
        raise PermissionDenied('Flock membership required.')


def _admin_user_ids(flock: Flock) -> set[int]:
    ids = set(
        flock.memberships.filter(
            role__in=(FlockMembership.ROLE_OWNER, FlockMembership.ROLE_ADMIN)
        ).values_list('user_id', flat=True)
    )
    if flock.owner_id:
        ids.add(flock.owner_id)
    return ids


def _can_leave_flock(flock: Flock, user) -> bool:
    """Members can leave; admins (incl. owner) only if another admin remains."""
    if not user or not flock.is_member(user):
        return False
    if flock.is_admin(user):
        return bool(_admin_user_ids(flock) - {user.id})
    return True


def _pick_successor_admin(flock: Flock, excluding_user_id: int) -> FlockMembership | None:
    other_ids = _admin_user_ids(flock) - {excluding_user_id}
    if not other_ids:
        return None
    return (
        FlockMembership.objects.filter(
            flock=flock,
            user_id__in=other_ids,
            role=FlockMembership.ROLE_ADMIN,
        )
        .order_by('joined_at', 'id')
        .first()
        or FlockMembership.objects.filter(flock=flock, user_id__in=other_ids)
        .order_by('joined_at', 'id')
        .first()
    )


def _display_name(user) -> str:
    return player_name_for_user(user)


def _logo_url(flock: Flock, request) -> str | None:
    if not flock.logo:
        return None
    return absolute_media_url(flock.logo.url, request)


def _published_challenges(flock: Flock) -> list[FlockChallenge]:
    return list(
        flock.challenges.exclude(status=FlockChallenge.STATUS_DRAFT).order_by(
            'starts_at', 'id'
        )
    )


def _published_challenge_count(flock: Flock) -> int:
    return flock.challenges.exclude(status=FlockChallenge.STATUS_DRAFT).count()


def _flock_history_path(flock: Flock) -> str | None:
    if _published_challenge_count(flock) < 2:
        return None
    latest = (
        flock.challenges.exclude(status=FlockChallenge.STATUS_DRAFT)
        .order_by('-starts_at', '-id')
        .first()
    )
    if not latest:
        return None
    return f'/flocks/c/{latest.public_token}/history/'


def _challenge_week_label(challenge: FlockChallenge) -> str:
    local = timezone.localtime(challenge.starts_at)
    return local.strftime('%d %b').lstrip('0')


def _flock_progress_payload(flock: Flock) -> dict:
    """Line-chart data: x = challenges, y = correct answers / rank per player."""
    challenges = _published_challenges(flock)
    n = len(challenges)
    labels = [_challenge_week_label(c) for c in challenges]
    max_correct = max((c.length for c in challenges), default=25)
    players: dict[int, dict] = {}
    max_rank = 1
    for idx, challenge in enumerate(challenges):
        rows = _leaderboard_rows(challenge)
        max_rank = max(max_rank, len(rows) or 1)
        for rank, attempt in enumerate(rows, start=1):
            entry = players.setdefault(
                attempt.user_id,
                {
                    'user_id': attempt.user_id,
                    'display_name': _display_name(attempt.user),
                    'correct': [None] * n,
                    'rank': [None] * n,
                },
            )
            entry['correct'][idx] = attempt.correct_count
            entry['rank'][idx] = rank
    series = sorted(
        players.values(),
        key=lambda p: (
            next((r for r in reversed(p['rank']) if r is not None), 999),
            p['display_name'].lower(),
        ),
    )
    max_cumulative = 0
    for player in series:
        running = 0
        started = False
        cumulative = []
        for correct in player['correct']:
            if correct is not None:
                started = True
                running += correct
                cumulative.append(running)
            elif started:
                cumulative.append(running)
            else:
                cumulative.append(None)
        player['cumulative'] = cumulative
        if running > max_cumulative:
            max_cumulative = running
    return {
        'labels': labels,
        'max_correct': max_correct,
        'max_rank': max_rank,
        'max_cumulative': max_cumulative,
        'players': series,
        'challenge_count': n,
    }


def _challenge_status(challenge: FlockChallenge) -> str:
    now_ts = timezone.now()
    if challenge.status == FlockChallenge.STATUS_ENDED or now_ts > challenge.ends_at:
        return 'ended'
    if challenge.status == FlockChallenge.STATUS_ACTIVE and challenge.starts_at <= now_ts:
        return 'active'
    return challenge.status


def _serialize_flock(flock: Flock, request, *, include_invite: bool = False) -> dict:
    user = getattr(request, 'user', None)
    active = (
        flock.challenges.filter(status=FlockChallenge.STATUS_ACTIVE)
        .filter(ends_at__gte=timezone.now())
        .order_by('-starts_at')
        .first()
    )
    data = {
        'id': flock.id,
        'name': flock.name,
        'slug': flock.slug,
        'default_country': {
            'code': flock.default_country_id,
            'name': flock.default_country.name,
        },
        'is_private': flock.is_private,
        'logo_url': _logo_url(flock, request),
        'member_count': flock.member_count(),
        'is_admin': bool(user and flock.is_admin(user)),
        'is_owner': bool(user and flock.owner_id == getattr(user, 'id', None)),
        'is_member': bool(user and flock.is_member(user)),
        'can_leave': bool(user and _can_leave_flock(flock, user)),
        'active_challenge': _serialize_challenge_summary(active, request) if active else None,
        'challenge_count': _published_challenge_count(flock),
        'history_path': _flock_history_path(flock),
    }
    if include_invite and user and flock.is_member(user):
        invite = _active_invite(flock)
        data['invite'] = _serialize_invite(invite, request, flock) if invite else None
    return data


def _serialize_invite(invite: FlockInvite, request, flock: Flock) -> dict:
    path = f'/join/flock/{invite.token}/'
    absolute = _absolute_url(request, path) if request else path
    return {
        'code': invite.code,
        'token': invite.token,
        'is_active': invite.is_active,
        'invite_url': absolute,
        'deep_link': f'birdr://join/flock/{invite.token}',
        'share_message': (
            f'Join {flock.name} on Birdr! Play our weekly bird identification challenge '
            f'and see how you compare with other members. Can you recognise this week’s '
            f'{CLUB_MIX_LENGTH} birds? {absolute}'
        ),
    }


def _serialize_challenge_summary(challenge: FlockChallenge, request) -> dict:
    share_path = f'/flocks/c/{challenge.public_token}/'
    share_url = _absolute_url(request, share_path) if request else share_path
    data = {
        'id': challenge.id,
        'title': challenge.title,
        'length': challenge.length,
        'preset': challenge.preset,
        'status': _challenge_status(challenge),
        'starts_at': challenge.starts_at.isoformat(),
        'ends_at': challenge.ends_at.isoformat(),
        'country': {'code': challenge.country_id, 'name': challenge.country.name},
        'public_token': challenge.public_token,
        'share_url': share_url,
        'participant_count': challenge.attempts.filter(
            is_ranked=True, completed_at__isnull=False
        ).count(),
        'my_completed': False,
        'my_rank': None,
        'my_rank_label': None,
    }
    user = getattr(request, 'user', None) if request else None
    if user and getattr(user, 'is_authenticated', False):
        mine = (
            FlockChallengeAttempt.objects.filter(
                challenge=challenge,
                user=user,
                is_ranked=True,
                completed_at__isnull=False,
            )
            .only('id')
            .first()
        )
        if mine:
            board = _build_leaderboard_payload(challenge, user)
            me = board.get('me')
            total = board.get('total_participants') or 0
            data['my_completed'] = True
            data['my_rank'] = me['rank'] if me else None
            if me:
                data['my_rank_label'] = f"#{me['rank']} of {total}"
    return data


def _attempt_stats(attempt: FlockChallengeAttempt) -> None:
    ps = PlayerScore.objects.filter(game=attempt.game, player=attempt.player).first()
    correct = Answer.objects.filter(
        player_score=ps, correct=True
    ).count() if ps else 0
    attempt.correct_count = correct
    attempt.birdr_score = ps.score if ps else 0


def _leaderboard_rows(challenge: FlockChallenge) -> list[FlockChallengeAttempt]:
    return list(
        FlockChallengeAttempt.objects.filter(
            challenge=challenge,
            is_ranked=True,
            completed_at__isnull=False,
        )
        .select_related('user', 'player')
        .order_by('-correct_count', '-birdr_score', 'completed_at', 'id')
    )


def _serialize_leaderboard_entry(attempt: FlockChallengeAttempt, rank: int) -> dict:
    return {
        'rank': rank,
        'display_name': _display_name(attempt.user),
        'correct_count': attempt.correct_count,
        'length': attempt.challenge.length,
        'score_label': f'{attempt.correct_count}/{attempt.challenge.length}',
        'birdr_score': attempt.birdr_score,
        'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
        'result_token': attempt.result_token,
        'user_id': attempt.user_id,
    }


def _build_leaderboard_payload(challenge: FlockChallenge, user) -> dict:
    rows = _leaderboard_rows(challenge)
    total = len(rows)
    top = [
        _serialize_leaderboard_entry(a, i)
        for i, a in enumerate(rows[:10], start=1)
    ]
    me = None
    neighbours = []
    if user and user.is_authenticated:
        my_index = next((i for i, a in enumerate(rows) if a.user_id == user.id), None)
        if my_index is not None:
            me = _serialize_leaderboard_entry(rows[my_index], my_index + 1)
            if my_index >= 10:
                start = max(0, my_index - 1)
                end = min(total, my_index + 2)
                neighbours = [
                    _serialize_leaderboard_entry(rows[i], i + 1)
                    for i in range(start, end)
                ]
    return {
        'top': top,
        'total_participants': total,
        'me': me,
        'neighbours': neighbours,
    }


class FlockListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        flocks = (
            Flock.objects.filter(
                Q(owner=request.user) | Q(memberships__user=request.user)
            )
            .select_related('default_country')
            .distinct()
            .order_by('name')
        )
        return Response([_serialize_flock(f, request) for f in flocks])

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        country_code = (request.data.get('country_code') or '').strip().upper()
        if not name:
            raise ValidationError({'name': 'Required.'})
        if not country_code:
            raise ValidationError({'country_code': 'Required.'})
        country = get_object_or_404(Country, pk=country_code)
        slug = unique_flock_slug(name)
        with transaction.atomic():
            flock = Flock.objects.create(
                name=name[:120],
                slug=slug,
                owner=request.user,
                default_country=country,
                is_private=True,
            )
            _ensure_owner_membership(flock, request.user)
            code = generate_invite_code()
            while FlockInvite.objects.filter(code=code, is_active=True).exists():
                code = generate_invite_code()
            FlockInvite.objects.create(
                flock=flock,
                code=code,
                token=_public_token(12),
                created_by=request.user,
            )
        flock = Flock.objects.select_related('default_country').get(pk=flock.pk)
        return Response(
            _serialize_flock(flock, request, include_invite=True),
            status=status.HTTP_201_CREATED,
        )


class FlockDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        flock = get_object_or_404(
            Flock.objects.select_related('default_country'), slug=slug
        )
        if flock.is_private and not flock.is_member(request.user):
            raise NotFound()
        return Response(_serialize_flock(flock, request, include_invite=True))

    def patch(self, request, slug):
        flock = get_object_or_404(Flock, slug=slug)
        _require_admin(flock, request.user)
        if 'name' in request.data:
            name = (request.data.get('name') or '').strip()
            if not name:
                raise ValidationError({'name': 'Required.'})
            flock.name = name[:120]
        if 'country_code' in request.data:
            code = (request.data.get('country_code') or '').strip().upper()
            flock.default_country = get_object_or_404(Country, pk=code)
        # Flocks are invite-only; ignore any is_private client field.
        flock.is_private = True
        if 'logo' in request.data:
            logo = request.data.get('logo')
            if logo in (None, '', 'null'):
                if flock.logo:
                    flock.logo.delete(save=False)
                flock.logo = None
            else:
                if flock.logo:
                    flock.logo.delete(save=False)
                flock.logo = logo
        flock.save()
        return Response(_serialize_flock(flock, request, include_invite=True))


class FlockProgressView(APIView):
    """Weekly score/rank/cumulative series for flock members."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        flock = get_object_or_404(
            Flock.objects.select_related('default_country'), slug=slug
        )
        _require_member(flock, request.user)
        chart = _flock_progress_payload(flock)
        return Response({
            'flock_name': flock.name,
            'flock_slug': flock.slug,
            'logo_url': _logo_url(flock, request),
            **chart,
        })


class FlockMembersView(APIView):
    """List flock members (display names + roles). Members only."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        flock = get_object_or_404(Flock, slug=slug)
        _require_member(flock, request.user)
        memberships = (
            FlockMembership.objects.filter(flock=flock)
            .select_related('user')
            .order_by('joined_at', 'id')
        )
        members = [
            {
                'user_id': m.user_id,
                'display_name': _display_name(m.user),
                'role': m.role,
                'joined_at': m.joined_at.isoformat() if m.joined_at else None,
            }
            for m in memberships
        ]
        return Response({
            'flock_name': flock.name,
            'flock_slug': flock.slug,
            'member_count': len(members),
            'members': members,
            'is_admin': flock.is_admin(request.user),
            'is_owner': flock.owner_id == request.user.id,
            'viewer_user_id': request.user.id,
            'can_leave': _can_leave_flock(flock, request.user),
        })


class FlockLeaveView(APIView):
    """Leave a flock. Admins (incl. owner) only if another admin remains."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        flock = get_object_or_404(Flock, slug=slug)
        _require_member(flock, request.user)
        if flock.is_admin(request.user) and not (_admin_user_ids(flock) - {request.user.id}):
            raise ValidationError(
                {
                    'detail': (
                        'You are the only admin. Make someone else an admin before leaving.'
                    )
                }
            )
        with transaction.atomic():
            if flock.owner_id == request.user.id:
                successor = _pick_successor_admin(flock, request.user.id)
                if not successor:
                    raise ValidationError(
                        {
                            'detail': (
                                'You are the only admin. Make someone else an admin '
                                'before leaving.'
                            )
                        }
                    )
                flock.owner = successor.user
                flock.save(update_fields=['owner', 'updated'])
                successor.role = FlockMembership.ROLE_OWNER
                successor.save(update_fields=['role'])
            deleted, _ = FlockMembership.objects.filter(
                flock=flock, user=request.user
            ).delete()
        if not deleted:
            raise PermissionDenied('Flock membership required.')
        return Response({'left': True, 'flock_slug': flock.slug})


class FlockMemberDetailView(APIView):
    """Update member role or remove a member (admin/owner only)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug, user_id: int):
        flock = get_object_or_404(Flock, slug=slug)
        _require_admin(flock, request.user)
        role = (request.data.get('role') or '').strip().lower()
        if role not in (FlockMembership.ROLE_ADMIN, FlockMembership.ROLE_MEMBER):
            raise ValidationError({'role': 'Must be "admin" or "member".'})
        if user_id == flock.owner_id:
            raise ValidationError({'detail': 'Cannot change the flock owner role.'})
        membership = FlockMembership.objects.filter(flock=flock, user_id=user_id).first()
        if not membership:
            raise NotFound('Member not found.')
        if membership.role == FlockMembership.ROLE_OWNER:
            raise ValidationError({'detail': 'Cannot change the flock owner role.'})
        if (
            membership.role == FlockMembership.ROLE_ADMIN
            and role == FlockMembership.ROLE_MEMBER
            and not (_admin_user_ids(flock) - {user_id})
        ):
            raise ValidationError(
                {'detail': 'Cannot demote the only remaining admin.'}
            )
        membership.role = role
        membership.save(update_fields=['role'])
        return Response({
            'user_id': membership.user_id,
            'display_name': _display_name(membership.user),
            'role': membership.role,
            'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
        })

    def delete(self, request, slug, user_id: int):
        flock = get_object_or_404(Flock, slug=slug)
        _require_admin(flock, request.user)
        if user_id == request.user.id:
            raise ValidationError({'detail': 'Use leave to remove yourself from the flock.'})
        if user_id == flock.owner_id:
            raise ValidationError({'detail': 'Cannot remove the flock owner.'})
        membership = FlockMembership.objects.filter(flock=flock, user_id=user_id).first()
        if not membership:
            raise NotFound('Member not found.')
        if membership.role == FlockMembership.ROLE_OWNER:
            raise ValidationError({'detail': 'Cannot remove the flock owner.'})
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FlockInviteRotateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        flock = get_object_or_404(Flock, slug=slug)
        _require_admin(flock, request.user)
        with transaction.atomic():
            flock.invites.filter(is_active=True).update(
                is_active=False, revoked_at=timezone.now()
            )
            code = generate_invite_code()
            while FlockInvite.objects.filter(code=code, is_active=True).exists():
                code = generate_invite_code()
            invite = FlockInvite.objects.create(
                flock=flock,
                code=code,
                token=_public_token(12),
                created_by=request.user,
            )
        return Response(_serialize_invite(invite, request, flock))


class FlockInvitePreviewView(APIView):
    """Public invite landing payload (no membership required)."""

    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]

    def get(self, request, token):
        invite = (
            FlockInvite.objects.select_related('flock', 'flock__default_country')
            .filter(token=token)
            .first()
        )
        if not invite:
            return Response({'error': 'invalid_invite'}, status=status.HTTP_404_NOT_FOUND)
        if not invite.is_active:
            return Response({'error': 'revoked_invite'}, status=status.HTTP_410_GONE)
        flock = invite.flock
        active = (
            flock.challenges.filter(status=FlockChallenge.STATUS_ACTIVE)
            .filter(ends_at__gte=timezone.now())
            .order_by('-starts_at')
            .first()
        )
        user = request.user if request.user.is_authenticated else None
        return Response({
            'flock': {
                'id': flock.id,
                'name': flock.name,
                'slug': flock.slug,
                'logo_url': _logo_url(flock, request),
                'default_country': {
                    'code': flock.default_country_id,
                    'name': flock.default_country.name,
                },
                'member_count': flock.member_count(),
                'is_private': flock.is_private,
                'is_member': bool(user and flock.is_member(user)),
            },
            'invite': {
                'code': invite.code,
                'token': invite.token,
            },
            'active_challenge': _serialize_challenge_summary(active, request) if active else None,
            'requires_auth_to_join': True,
        })


class FlockInviteJoinView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        code = (request.data.get('code') or '').strip().upper()
        invite = None
        if token:
            invite = FlockInvite.objects.select_related('flock').filter(token=token).first()
        elif code:
            invite = (
                FlockInvite.objects.select_related('flock')
                .filter(code=code, is_active=True)
                .first()
            )
        else:
            raise ValidationError({'token': 'token or code required'})
        if not invite:
            return Response({'error': 'invalid_invite'}, status=status.HTTP_404_NOT_FOUND)
        if not invite.is_active:
            return Response({'error': 'revoked_invite'}, status=status.HTTP_410_GONE)
        flock = invite.flock
        membership, created = FlockMembership.objects.get_or_create(
            flock=flock,
            user=request.user,
            defaults={'role': FlockMembership.ROLE_MEMBER},
        )
        return Response({
            'joined': created,
            'already_member': not created,
            'flock': _serialize_flock(flock, request),
            'membership_role': membership.role,
        })


class FlockChallengeCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        flock = get_object_or_404(
            Flock.objects.select_related('default_country'), slug=slug
        )
        _require_admin(flock, request.user)
        active = (
            flock.challenges.filter(status=FlockChallenge.STATUS_ACTIVE)
            .filter(ends_at__gte=timezone.now())
            .exists()
        )
        if active:
            return Response(
                {'error': 'challenge_already_active'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        title = (request.data.get('title') or f'{flock.name} Challenge').strip()[:160]
        days = int(request.data.get('duration_days') or 7)
        days = max(1, min(days, 30))
        country_code = (request.data.get('country_code') or flock.default_country_id).upper()
        country = get_object_or_404(Country, pk=country_code)
        host = _get_or_create_player_for_user(request.user)
        starts = timezone.now()
        ends = starts + timedelta(days=days)

        try:
            snapshot = generate_club_mix_snapshot(country=country, host=host)
        except InsufficientChallengeContent as exc:
            return Response(
                {
                    'error': 'insufficient_content',
                    'detail': str(exc),
                    'needed': exc.needed,
                    'available': exc.available,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        with transaction.atomic():
            challenge = FlockChallenge.objects.create(
                flock=flock,
                title=title,
                country=country,
                length=CLUB_MIX_LENGTH,
                preset=FlockChallenge.PRESET_CLUB_MIX,
                status=FlockChallenge.STATUS_ACTIVE,
                starts_at=starts,
                ends_at=ends,
                created_by=request.user,
                public_token=_public_token(8),
            )
            persist_challenge_snapshot(challenge, snapshot)

        _notify_flock_challenge(flock, challenge, exclude_user_id=request.user.id)

        return Response(
            {
                **_serialize_challenge_summary(challenge, request),
                'item_count': challenge.items.count(),
            },
            status=status.HTTP_201_CREATED,
        )


class FlockChallengeDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, challenge_id):
        flock = get_object_or_404(Flock, slug=slug)
        if flock.is_private and not flock.is_member(request.user):
            raise NotFound()
        challenge = get_object_or_404(FlockChallenge, pk=challenge_id, flock=flock)
        my_ranked = (
            FlockChallengeAttempt.objects.filter(
                challenge=challenge,
                user=request.user,
                is_ranked=True,
                completed_at__isnull=False,
            )
            .order_by('-completed_at')
            .first()
        )
        in_progress = (
            FlockChallengeAttempt.objects.filter(
                challenge=challenge,
                user=request.user,
                completed_at__isnull=True,
            )
            .select_related('player', 'game')
            .order_by('-created_at')
            .first()
        )
        my_player = _get_or_create_player_for_user(request.user)
        return Response({
            'challenge': _serialize_challenge_summary(challenge, request),
            'leaderboard': _build_leaderboard_payload(challenge, request.user),
            'my_ranked_attempt': (
                {
                    'correct_count': my_ranked.correct_count,
                    'birdr_score': my_ranked.birdr_score,
                    'result_token': my_ranked.result_token,
                    'completed_at': my_ranked.completed_at.isoformat(),
                }
                if my_ranked
                else None
            ),
            'in_progress_game_token': in_progress.game.token if in_progress else None,
            'my_player_token': (
                in_progress.player.token if in_progress and in_progress.player_id else my_player.token
            ),
            'can_play_ranked': my_ranked is None and in_progress is None,
            'can_practice': False,
        })


class FlockChallengeStartView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, challenge_id):
        flock = get_object_or_404(Flock, slug=slug)
        _require_member(flock, request.user)
        challenge = get_object_or_404(FlockChallenge, pk=challenge_id, flock=flock)
        if _challenge_status(challenge) != 'active':
            return Response(
                {'error': 'challenge_not_active'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.data.get('practice'):
            return Response(
                {'error': 'practice_not_allowed'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        player = _get_or_create_player_for_user(request.user)
        has_ranked_completed = FlockChallengeAttempt.objects.filter(
            challenge=challenge,
            user=request.user,
            is_ranked=True,
            completed_at__isnull=False,
        ).exists()
        if has_ranked_completed:
            return Response(
                {'error': 'already_completed'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        in_progress = FlockChallengeAttempt.objects.filter(
            challenge=challenge,
            user=request.user,
            completed_at__isnull=True,
        ).select_related('game', 'player').order_by('-created_at').first()
        if in_progress:
            return Response(
                {
                    'attempt_id': in_progress.id,
                    'game_token': in_progress.game.token,
                    'player_token': in_progress.player.token if in_progress.player_id else player.token,
                    'is_ranked': in_progress.is_ranked,
                    'is_practice': False,
                    'label': 'Ranked',
                    'length': challenge.length,
                },
                status=status.HTTP_200_OK,
            )

        try:
            with transaction.atomic():
                game = clone_challenge_into_game(
                    challenge=challenge,
                    host=player,
                    language=getattr(player, 'language', 'en') or 'en',
                )
                from jizz.client_info import record_player_score_client_from_request

                record_player_score_client_from_request(player, game, request)
                attempt = FlockChallengeAttempt.objects.create(
                    challenge=challenge,
                    user=request.user,
                    player=player,
                    game=game,
                    is_ranked=True,
                    is_practice=False,
                    result_token=_result_token(),
                )
                link_attempt_questions(attempt, game)
        except InsufficientChallengeContent as exc:
            return Response(
                {'error': 'insufficient_content', 'detail': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            {
                'attempt_id': attempt.id,
                'game_token': game.token,
                'player_token': player.token,
                'is_ranked': True,
                'is_practice': False,
                'label': 'Ranked',
                'length': challenge.length,
            },
            status=status.HTTP_201_CREATED,
        )


class FlockChallengeCompleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, challenge_id):
        flock = get_object_or_404(Flock, slug=slug)
        _require_member(flock, request.user)
        challenge = get_object_or_404(FlockChallenge, pk=challenge_id, flock=flock)
        game_token = (request.data.get('game_token') or '').strip()
        attempt = get_object_or_404(
            FlockChallengeAttempt.objects.select_related('game', 'player'),
            challenge=challenge,
            user=request.user,
            game__token=game_token,
        )
        with transaction.atomic():
            attempt = (
                FlockChallengeAttempt.objects.select_for_update()
                .select_related('game', 'player', 'challenge')
                .get(pk=attempt.pk)
            )
            if attempt.completed_at:
                return Response(self._result_payload(attempt, request))

            answered = Answer.objects.filter(
                player_score__player=attempt.player,
                player_score__game=attempt.game,
            ).count()
            if answered < attempt.challenge.length:
                return Response(
                    {
                        'error': 'incomplete',
                        'answered': answered,
                        'length': attempt.challenge.length,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            _attempt_stats(attempt)
            existing_ranked = (
                FlockChallengeAttempt.objects.select_for_update()
                .filter(
                    challenge=challenge,
                    user=request.user,
                    is_ranked=True,
                    completed_at__isnull=False,
                )
                .exclude(pk=attempt.pk)
                .first()
            )
            if existing_ranked:
                return Response(
                    {'error': 'already_completed'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            attempt.is_ranked = True
            attempt.is_practice = False
            attempt.completed_at = timezone.now()
            try:
                attempt.save()
            except IntegrityError:
                return Response(
                    {'error': 'already_completed'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not attempt.game.force_ended:
                attempt.game.force_ended = True
                attempt.game.save(update_fields=['force_ended'])

        return Response(self._result_payload(attempt, request))

    def _result_payload(self, attempt: FlockChallengeAttempt, request) -> dict:
        board = _build_leaderboard_payload(attempt.challenge, request.user)
        me = board.get('me')
        flock = attempt.challenge.flock
        result_path = f'/flocks/results/{attempt.result_token}/'
        result_url = _absolute_url(request, result_path)
        rank_label = f"#{me['rank']} of {board['total_participants']}" if me else None
        return {
            'attempt_id': attempt.id,
            'is_ranked': attempt.is_ranked,
            'is_practice': attempt.is_practice,
            'correct_count': attempt.correct_count,
            'length': attempt.challenge.length,
            'score_label': f'{attempt.correct_count}/{attempt.challenge.length}',
            'birdr_score': attempt.birdr_score,
            'rank': me['rank'] if me else None,
            'rank_label': rank_label,
            'total_participants': board['total_participants'],
            'result_token': attempt.result_token,
            'result_url': result_url,
            'share_message': (
                f"I scored {attempt.correct_count}/{attempt.challenge.length}"
                + (f" and ranked {rank_label}" if rank_label else '')
                + f" in the {flock.name} Birdr Challenge. Can you beat me? {result_url}"
            ),
            'flock_name': flock.name,
            'flock_slug': flock.slug,
            'challenge_title': attempt.challenge.title,
            'challenge_id': attempt.challenge_id,
            'leaderboard': board,
        }


class FlockChallengeLeaderboardView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, challenge_id):
        flock = get_object_or_404(Flock, slug=slug)
        if flock.is_private and not flock.is_member(request.user):
            raise NotFound()
        challenge = get_object_or_404(FlockChallenge, pk=challenge_id, flock=flock)
        return Response(_build_leaderboard_payload(challenge, request.user))


class FlockPublicResultView(APIView):
    """Public-safe ranked result for sharing (no answers / emails)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, result_token):
        attempt = (
            FlockChallengeAttempt.objects.select_related(
                'challenge', 'challenge__flock', 'challenge__country', 'user'
            )
            .filter(result_token=result_token, completed_at__isnull=False)
            .first()
        )
        if not attempt:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        rows = _leaderboard_rows(attempt.challenge)
        rank = next(
            (i for i, a in enumerate(rows, start=1) if a.id == attempt.id),
            None,
        )
        flock = attempt.challenge.flock
        return Response({
            'flock_name': flock.name,
            'flock_slug': flock.slug,
            'logo_url': _logo_url(flock, request),
            'challenge_title': attempt.challenge.title,
            'challenge_id': attempt.challenge_id,
            'display_name': _display_name(attempt.user),
            'correct_count': attempt.correct_count,
            'length': attempt.challenge.length,
            'score_label': f'{attempt.correct_count}/{attempt.challenge.length}',
            'birdr_score': attempt.birdr_score,
            'rank': rank,
            'total_participants': len(rows),
            'rank_label': f'#{rank} of {len(rows)}' if rank else None,
            'is_ranked': attempt.is_ranked,
            'country': {
                'code': attempt.challenge.country_id,
                'name': attempt.challenge.country.name,
            },
        })


def flock_result_page(request, result_token: str):
    """HTML share page with Open Graph tags (no private data)."""
    attempt = (
        FlockChallengeAttempt.objects.select_related(
            'challenge', 'challenge__flock', 'user'
        )
        .filter(result_token=result_token, completed_at__isnull=False)
        .first()
    )
    if not attempt:
        return render(request, 'jizz/flock_result.html', {'missing': True}, status=404)
    rows = _leaderboard_rows(attempt.challenge)
    rank = next((i for i, a in enumerate(rows, start=1) if a.id == attempt.id), None)
    flock = attempt.challenge.flock
    score_label = f'{attempt.correct_count}/{attempt.challenge.length}'
    rank_label = f'#{rank} of {len(rows)}' if rank else ''
    description = (
        f'{_display_name(attempt.user)} scored {score_label}'
        + (f' ({rank_label})' if rank_label else '')
        + f' in the {flock.name} Birdr Challenge. Can you beat them?'
    )
    absolute = _absolute_url(request, request.path)
    return render(
        request,
        'jizz/flock_result.html',
        {
            'missing': False,
            'flock_name': flock.name,
            'challenge_title': attempt.challenge.title,
            'score_label': score_label,
            'rank_label': rank_label,
            'display_name': _display_name(attempt.user),
            'description': description,
            'canonical_url': absolute,
            'og_image': _absolute_url(request, f'/flocks/results/{result_token}/og.png'),
            'join_url': _share_join_url(request, flock),
            'start_url': '/start/',
            'app_store_url': getattr(settings, 'APP_STORE_URL', ''),
            'play_store_url': getattr(settings, 'PLAY_STORE_URL', ''),
        },
    )


def flock_result_og_image(request, result_token: str):
    """Generated 1200×630 PNG for a shared flock challenge result."""
    from jizz.flock_share import render_flock_result_og_image

    attempt = (
        FlockChallengeAttempt.objects.select_related(
            'challenge', 'challenge__flock', 'user'
        )
        .filter(result_token=result_token, completed_at__isnull=False)
        .first()
    )
    if not attempt:
        return HttpResponse(status=404)
    rows = _leaderboard_rows(attempt.challenge)
    rank = next((i for i, a in enumerate(rows, start=1) if a.id == attempt.id), None)
    score_label = f'{attempt.correct_count}/{attempt.challenge.length}'
    rank_label = f'#{rank} of {len(rows)}' if rank else ''
    png = render_flock_result_og_image(
        flock=attempt.challenge.flock,
        display_name=_display_name(attempt.user),
        score_label=score_label,
        rank_label=rank_label,
    )
    response = HttpResponse(png, content_type='image/png')
    response['Cache-Control'] = 'public, max-age=600'
    return response


def _challenge_by_public_token(public_token: str) -> FlockChallenge | None:
    return (
        FlockChallenge.objects.select_related('flock', 'country', 'flock__default_country')
        .filter(public_token=public_token)
        .first()
    )


def _share_top_entries(challenge: FlockChallenge, limit: int = 5) -> list[dict]:
    rows = _leaderboard_rows(challenge)
    return [
        _serialize_leaderboard_entry(a, i)
        for i, a in enumerate(rows[:limit], start=1)
    ]


def _share_join_url(request, flock: Flock) -> str | None:
    invite = _active_invite(flock)
    if not invite:
        return None
    return _absolute_url(request, f'/join/flock/{invite.token}/')


def flock_challenge_share_page(request, public_token: str):
    """Public HTML landing + Open Graph for WhatsApp/Signal share previews."""
    challenge = _challenge_by_public_token(public_token)
    if not challenge:
        return render(
            request,
            'jizz/flock_challenge_share.html',
            {'missing': True},
            status=404,
        )
    flock = challenge.flock
    rows = _leaderboard_rows(challenge)
    participant_count = len(rows)
    show_all = request.GET.get('all') in ('1', 'true', 'yes')
    displayed = rows if show_all else rows[:5]
    top = [
        _serialize_leaderboard_entry(a, i)
        for i, a in enumerate(displayed, start=1)
    ]
    join_url = _share_join_url(request, flock)
    canonical = _absolute_url(request, f'/flocks/c/{challenge.public_token}/')
    og_image = _absolute_url(request, f'/flocks/c/{challenge.public_token}/og.png')
    status_label = _challenge_status(challenge)
    description = (
        f'{flock.name} flock challenge on Birdr. '
        + (
            f'Top score {top[0]["score_label"]} by {top[0]["display_name"]}. '
            if top
            else 'No scores yet — be the first. '
        )
        + 'Join and play before time runs out.'
    )
    return render(
        request,
        'jizz/flock_challenge_share.html',
        {
            'missing': False,
            'flock_name': flock.name,
            'logo_url': _logo_url(flock, request),
            'status_label': status_label,
            'ends_at': challenge.ends_at,
            'ends_at_iso': challenge.ends_at.isoformat(),
            'top': top,
            'show_all': show_all,
            'has_more': participant_count > 5,
            'participant_count': participant_count,
            'join_url': join_url,
            'description': description,
            'canonical_url': canonical,
            'og_image': og_image,
            'og_title': f'{flock.name} leaderboard · Birdr',
            'has_history': _published_challenge_count(flock) > 1,
            'history_path': f'/flocks/c/{challenge.public_token}/history/',
        },
    )


def flock_challenge_history_page(request, public_token: str):
    """Public chart of correct answers and ranks across weekly challenges."""
    challenge = _challenge_by_public_token(public_token)
    if not challenge:
        return render(
            request,
            'jizz/flock_challenge_history.html',
            {'missing': True},
            status=404,
        )
    flock = challenge.flock
    chart = _flock_progress_payload(flock)
    share_path = f'/flocks/c/{challenge.public_token}/'
    join_url = _share_join_url(request, flock)
    canonical = _absolute_url(request, f'{share_path}history/')
    return render(
        request,
        'jizz/flock_challenge_history.html',
        {
            'missing': False,
            'flock_name': flock.name,
            'logo_url': _logo_url(flock, request),
            'chart_json': chart,
            'has_history': chart['challenge_count'] > 1,
            'share_path': share_path,
            'join_url': join_url,
            'canonical_url': canonical,
            'og_title': f'{flock.name} weekly scores · Birdr',
            'description': (
                f'{flock.name} weekly challenge scores on Birdr. '
                f'{chart["challenge_count"]} week'
                f'{"s" if chart["challenge_count"] != 1 else ""} of club mix quizzes.'
            ),
        },
    )


def flock_challenge_og_image(request, public_token: str):
    """Generated 1200×630 PNG for messenger link previews."""
    from jizz.flock_share import render_challenge_og_image

    challenge = _challenge_by_public_token(public_token)
    if not challenge:
        return HttpResponse(status=404)
    top = _share_top_entries(challenge, 5)
    participant_count = len(_leaderboard_rows(challenge))
    png = render_challenge_og_image(
        flock=challenge.flock,
        challenge=challenge,
        top_entries=top,
        participant_count=participant_count,
    )
    response = HttpResponse(png, content_type='image/png')
    response['Cache-Control'] = 'public, max-age=600'
    return response

