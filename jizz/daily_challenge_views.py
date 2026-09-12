"""
Views for Friends, Daily Challenge, and Device Tokens (push).
All require IsAuthenticated unless noted.
"""
from django.utils.timezone import now
from django.utils import timezone
from django.db import models
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from datetime import timedelta
import html2text
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import NotFound, ValidationError
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from jizz.notifications import send_push_to_user
from jizz.models import (
    Country,
    Game,
    Player,
    PlayerScore,
    Friendship,
    DailyChallenge,
    DailyChallengeParticipant,
    DailyChallengeInvite,
    DailyChallengeRound,
    DeviceToken,
)
from jizz.serializers import (
    FriendshipSerializer,
    FriendshipRequestSerializer,
    UserMinimalSerializer,
    DailyChallengeSerializer,
    DailyChallengeCreateSerializer,
    DailyChallengeInviteSerializer,
    DailyChallengeRoundSerializer,
    DeviceTokenSerializer,
)

User = get_user_model()


def _send_daily_challenge_invite_email(request, invite):
    """Send invite email with accept link (join/challenge/<token>)."""
    base_url = request.build_absolute_uri('/').rstrip('/')
    if 'localhost' in base_url or '127.0.0.1' in base_url:
        base_url = getattr(settings, 'DAILY_CHALLENGE_BASE_URL', 'https://birdr.pro')
    accept_url = f"{base_url}/join/challenge/{invite.invite_token}"
    inviter_username = invite.challenge.creator.get_username()
    try:
        html_content = render_to_string('emails/daily_challenge_invite.html', {
            'accept_url': accept_url,
            'inviter_username': inviter_username,
        })
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        text_content = h.handle(html_content)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@birdr.pro')
        msg = EmailMultiAlternatives(
            subject='You\'re invited to a Daily Challenge on Birdr',
            body=text_content,
            from_email=from_email,
            to=[invite.email],
        )
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
    except Exception:
        pass


def _ensure_friends(inviter, invitee):
    """When an invitation is accepted, make inviter and invitee friends (accepted)."""
    if inviter.id == invitee.id:
        return
    for from_u, to_u in [(inviter, invitee), (invitee, inviter)]:
        friendship, created = Friendship.objects.get_or_create(
            from_user=from_u,
            to_user=to_u,
            defaults={'status': 'accepted'},
        )
        if not created and friendship.status != 'accepted':
            friendship.status = 'accepted'
            friendship.save(update_fields=['status'])


class FriendsListView(APIView):
    """GET /api/friends/ – list accepted friends."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Friends: where I'm from_user or to_user and status=accepted
        sent = Friendship.objects.filter(from_user=user, status='accepted').values_list('to_user_id', flat=True)
        received = Friendship.objects.filter(to_user=user, status='accepted').values_list('from_user_id', flat=True)
        friend_ids = list(sent) + list(received)
        friends = User.objects.filter(id__in=friend_ids).distinct()
        serializer = UserMinimalSerializer(friends, many=True)
        return Response(serializer.data)


class FriendRequestsListView(APIView):
    """GET /api/friends/requests/ – pending requests received (and optionally sent)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        received = Friendship.objects.filter(to_user=user, status='pending').select_related('from_user')
        sent = Friendship.objects.filter(from_user=user, status='pending').select_related('to_user')
        return Response({
            'received': FriendshipSerializer(received, many=True).data,
            'sent': FriendshipSerializer(sent, many=True).data,
        })


class FriendRequestView(APIView):
    """POST /api/friends/request/ – send friend request (body: user_id or username)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FriendshipRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        target = None
        if serializer.validated_data.get('user_id'):
            target = get_object_or_404(User, id=serializer.validated_data['user_id'])
        else:
            target = get_object_or_404(User, username=serializer.validated_data['username'])
        if target.id == user.id:
            return Response({'error': 'Cannot add yourself'}, status=status.HTTP_400_BAD_REQUEST)
        # Avoid duplicate: already friends or pending
        if Friendship.objects.filter(from_user=user, to_user=target).exists():
            return Response({'error': 'Request already sent'}, status=status.HTTP_400_BAD_REQUEST)
        if Friendship.objects.filter(from_user=target, to_user=user).exists():
            existing = Friendship.objects.get(from_user=target, to_user=user)
            if existing.status == 'accepted':
                return Response({'error': 'Already friends'}, status=status.HTTP_400_BAD_REQUEST)
            if existing.status == 'pending':
                return Response({'error': 'They already sent you a request'}, status=status.HTTP_400_BAD_REQUEST)
        Friendship.objects.create(from_user=user, to_user=target, status='pending')
        return Response({'status': 'pending'}, status=status.HTTP_201_CREATED)


class FriendAcceptView(APIView):
    """POST /api/friends/accept/<id>/ – accept a friend request (id = Friendship id)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        friendship = get_object_or_404(Friendship, id=pk, to_user=request.user, status='pending')
        friendship.status = 'accepted'
        friendship.save(update_fields=['status'])
        return Response(FriendshipSerializer(friendship).data)


class FriendDeclineView(APIView):
    """POST /api/friends/decline/<id>/."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        friendship = get_object_or_404(Friendship, id=pk, to_user=request.user, status='pending')
        friendship.status = 'declined'
        friendship.save(update_fields=['status'])
        return Response({'status': 'declined'})


# --- Daily Challenge ---


class DailyChallengeCreateView(APIView):
    """POST /api/daily-challenges/ – create challenge. GET – list my challenges."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List my challenges (created or participating)."""
        user = request.user
        challenges = DailyChallenge.objects.filter(
            models.Q(creator=user) | models.Q(participants__user=user)
        ).distinct().prefetch_related(
            'participants', 'participants__user', 'rounds', 'country'
        ).order_by('-created')
        return Response(DailyChallengeSerializer(challenges, many=True).data)

    def post(self, request):
        """Create new challenge."""
        serializer = DailyChallengeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        country = get_object_or_404(Country, code=serializer.validated_data['country'])
        challenge = DailyChallenge.objects.create(
            creator=request.user,
            country=country,
            media=serializer.validated_data['media'],
            length=serializer.validated_data['length'],
            duration_days=serializer.validated_data.get('duration_days', 7),
            level=serializer.validated_data.get('level', 'advanced'),
            status='pending_accept',
        )
        # Creator is first participant, accepted
        DailyChallengeParticipant.objects.create(
            challenge=challenge,
            user=request.user,
            invited_by=None,
            status='accepted',
            accepted_at=now(),
        )
        return Response(
            DailyChallengeSerializer(challenge).data,
            status=status.HTTP_201_CREATED,
        )


class DailyChallengeListView(APIView):
    """GET /api/daily-challenges/ – my challenges (created or participating). Kept for backwards compat; use CreateView.get instead."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        challenges = DailyChallenge.objects.filter(
            models.Q(creator=user) | models.Q(participants__user=user)
        ).distinct().prefetch_related(
            'participants', 'participants__user', 'rounds', 'country'
        ).order_by('-created')
        return Response(DailyChallengeSerializer(challenges, many=True).data)


class DailyChallengeDetailView(APIView):
    """GET /api/daily-challenges/<id>/ – detail (must be creator or participant)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        challenge = DailyChallenge.objects.filter(pk=pk).prefetch_related(
            'participants', 'participants__user', 'rounds', 'rounds__game', 'country'
        ).first()
        if not challenge:
            raise NotFound()
        if challenge.creator_id != request.user.id and not challenge.participants.filter(user=request.user).exists():
            raise NotFound()
        return Response(DailyChallengeSerializer(challenge).data)


class DailyChallengeInviteView(APIView):
    """POST /api/daily-challenges/<id>/invite/ – add opponents (friend_user_ids, emails)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        challenge = get_object_or_404(DailyChallenge, id=pk, creator=request.user)
        if challenge.status not in ('draft', 'pending_accept'):
            return Response({'error': 'Challenge already started'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = DailyChallengeInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for uid in serializer.validated_data.get('friend_user_ids', []):
            try:
                target = User.objects.get(id=uid)
            except User.DoesNotExist:
                continue
            if target.id == request.user.id:
                continue
            _, created = DailyChallengeParticipant.objects.get_or_create(
                challenge=challenge,
                user=target,
                defaults={'invited_by': request.user, 'status': 'invited'},
            )
        for email in serializer.validated_data.get('emails', []):
            email = (email or '').strip().lower()
            if not email:
                continue
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user:
                DailyChallengeParticipant.objects.get_or_create(
                    challenge=challenge,
                    user=existing_user,
                    defaults={'invited_by': request.user, 'status': 'invited'},
                )
                from jizz.user_names import player_name_for_user

                inviter_name = player_name_for_user(request.user, fallback='Someone')
                send_push_to_user(
                    existing_user,
                    'Daily Challenge invite',
                    f'{inviter_name} invited you to a Daily Challenge',
                    {'challenge_id': challenge.id, 'type': 'daily_challenge_invite'},
                )
            else:
                invite, created = DailyChallengeInvite.objects.get_or_create(
                    challenge=challenge,
                    email=email,
                    defaults={'status': 'pending'},
                )
                if created and invite.email:
                    _send_daily_challenge_invite_email(request, invite)
        challenge.refresh_from_db()
        return Response(DailyChallengeSerializer(challenge).data)


class DailyChallengeAcceptByIdView(APIView):
    """POST /api/daily-challenges/<id>/accept/ – accept invite (authenticated)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        participant = get_object_or_404(
            DailyChallengeParticipant,
            challenge_id=pk,
            user=request.user,
            status='invited',
        )
        participant.status = 'accepted'
        participant.accepted_at = now()
        participant.save(update_fields=['status', 'accepted_at'])
        _ensure_friends(participant.challenge.creator, request.user)
        return Response(DailyChallengeSerializer(participant.challenge).data)


class DailyChallengeDeclineView(APIView):
    """POST /api/daily-challenges/<id>/decline/."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        participant = get_object_or_404(
            DailyChallengeParticipant,
            challenge_id=pk,
            user=request.user,
            status='invited',
        )
        participant.status = 'declined'
        participant.save(update_fields=['status'])
        return Response({'status': 'declined'})


def _get_or_create_player_for_user(user):
    """Get or create a Player linked to this user (for daily challenge games)."""
    player = Player.objects.filter(user=user).first()
    if player:
        return player
    from jizz.user_names import player_name_for_user

    name = player_name_for_user(user)
    return Player.objects.create(user=user, name=name, language='en')


class DailyChallengeStartView(APIView):
    """POST /api/daily-challenges/<id>/start/ – creator starts challenge; create round 1 + game."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        challenge = get_object_or_404(DailyChallenge, id=pk, creator=request.user)
        if challenge.status not in ('draft', 'pending_accept'):
            return Response({'error': 'Challenge already started'}, status=status.HTTP_400_BAD_REQUEST)
        accepted = list(challenge.participants.filter(status='accepted').select_related('user'))
        if not accepted:
            return Response({'error': 'No accepted participants'}, status=status.HTTP_400_BAD_REQUEST)

        creator_player = _get_or_create_player_for_user(request.user)
        game = Game.objects.create(
            country=challenge.country,
            language='en',
            level=challenge.level,
            length=challenge.length,
            media=challenge.media,
            multiplayer=True,
            host=creator_player,
            rarity=Game.RARIT_REGULAR,
            include_escapes=False,
        )
        for p in accepted:
            pl = _get_or_create_player_for_user(p.user)
            PlayerScore.objects.get_or_create(player=pl, game=game, defaults={'score': 0})
        from jizz.client_info import record_player_score_client_from_request

        record_player_score_client_from_request(creator_player, game, request)

        started = now()
        closes_at = started + timedelta(hours=24)
        round1 = DailyChallengeRound.objects.create(
            challenge=challenge,
            day_number=1,
            game=game,
            opens_at=started,
            closes_at=closes_at,
            status='active',
        )
        challenge.started_at = started
        challenge.status = 'active'
        challenge.save(update_fields=['started_at', 'status'])

        # Create placeholder rounds for remaining days (game=None until that day)
        for day in range(2, challenge.duration_days + 1):
            day_start = started + timedelta(days=day - 1)
            day_end = day_start + timedelta(hours=24)
            DailyChallengeRound.objects.get_or_create(
                challenge=challenge,
                day_number=day,
                defaults={'opens_at': day_start, 'closes_at': day_end, 'status': 'pending'},
            )

        challenge.refresh_from_db()
        return Response(DailyChallengeSerializer(challenge).data)


class DailyChallengeRoundView(APIView):
    """GET /api/daily-challenges/<id>/rounds/<day>/ – get round + game token for that day."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, day):
        challenge = get_object_or_404(DailyChallenge, id=pk)
        if challenge.creator_id != request.user.id and not challenge.participants.filter(user=request.user, status='accepted').exists():
            raise NotFound()
        round_obj = get_object_or_404(DailyChallengeRound, challenge_id=pk, day_number=day)
        return Response(DailyChallengeRoundSerializer(round_obj, context={'request': request}).data)


class DailyChallengeAcceptByTokenView(APIView):
    """GET /api/daily-challenges/accept/<token>/ – resolve invite by token (for deep link). Returns challenge info."""
    permission_classes = []
    authentication_classes = []

    def get(self, request, token):
        invite = DailyChallengeInvite.objects.filter(invite_token=token, status='pending').select_related('challenge').first()
        if not invite:
            return Response({'error': 'Invalid or expired invite'}, status=status.HTTP_404_NOT_FOUND)
        if invite.expires_at and timezone.now() > invite.expires_at:
            return Response({'error': 'Invite expired'}, status=status.HTTP_410_GONE)
        return Response({
            'type': 'email_invite',
            'challenge_id': invite.challenge_id,
            'invite_token': token,
            'accept_url': f'/api/daily-challenges/{invite.challenge_id}/accept-by-token/',
        })


class DailyChallengeAcceptByTokenPostView(APIView):
    """POST /api/daily-challenges/accept-by-token/ – body: invite_token. Authenticated: create participant, mark invite accepted."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('invite_token')
        if not token:
            return Response({'error': 'invite_token required'}, status=status.HTTP_400_BAD_REQUEST)
        invite = DailyChallengeInvite.objects.filter(invite_token=token, status='pending').select_related('challenge').first()
        if not invite:
            return Response({'error': 'Invalid or expired invite'}, status=status.HTTP_404_NOT_FOUND)
        if invite.expires_at and timezone.now() > invite.expires_at:
            return Response({'error': 'Invite expired'}, status=status.HTTP_410_GONE)
        participant, created = DailyChallengeParticipant.objects.get_or_create(
            challenge=invite.challenge,
            user=request.user,
            defaults={'invited_by_id': invite.challenge.creator_id, 'status': 'accepted', 'accepted_at': now()},
        )
        if not created:
            if participant.status == 'invited':
                participant.status = 'accepted'
                participant.accepted_at = now()
                participant.save(update_fields=['status', 'accepted_at'])
        invite.status = 'accepted'
        invite.save(update_fields=['status'])
        _ensure_friends(invite.challenge.creator, request.user)
        return Response(DailyChallengeSerializer(invite.challenge).data)


# --- Device tokens (push) ---


class DeviceTokenCreateView(APIView):
    """POST /api/device-tokens/ – register push token (idempotent)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        platform = serializer.validated_data['platform']
        obj, _ = DeviceToken.objects.update_or_create(
            user=request.user,
            token=token,
            defaults={'platform': platform},
        )
        return Response(DeviceTokenSerializer(obj).data, status=status.HTTP_201_CREATED)


class DeviceTokenDeleteView(APIView):
    """DELETE /api/device-tokens/<id>/ or by token."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk=None):
        if pk:
            DeviceToken.objects.filter(id=pk, user=request.user).delete()
        else:
            token = request.data.get('token') or request.query_params.get('token')
            if token:
                DeviceToken.objects.filter(token=token, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
