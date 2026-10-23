"""API for shared games (create, share link, play, leaderboard, finish, question stats).

Guests and logged-in players use the same endpoints: the Authorization header carries a
player token (``Bearer``/``Token``) like the normal game endpoints, or a JWT. Only logged-in
players can create a shared game, so the owner can find and finish it from any device.
"""

from __future__ import annotations

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from jizz.client_info import record_player_score_client_from_request
from jizz.daily_challenge_views import _get_or_create_player_for_user
from jizz.models import Game, Player, SharedGame, SharedGameAttempt
from jizz.serializers import GameSerializer
from jizz.services.species_cover import absolute_media_url
from jizz.shared_game import (
    MAX_DURATION_HOURS,
    MAX_LENGTH,
    SHAREABLE_GAME_TYPES,
    SharedGameContentError,
    attempt_for,
    create_shared_game,
    leaderboard,
    question_stats,
    start_attempt,
)
from jizz.user_names import player_name_for_user


def _request_player(request) -> Player | None:
    """The player behind the request: a player token in the header, else the JWT user's player."""
    header = request.headers.get('Authorization') or ''
    parts = header.split()
    if len(parts) == 2 and parts[0] in ('Bearer', 'Token'):
        player = Player.objects.filter(token=parts[1]).select_related('user').first()
        if player:
            return player
    if request.user and request.user.is_authenticated:
        return _get_or_create_player_for_user(request.user)
    return None


def _owner_user(player: Player | None):
    return player.user if player and player.user_id else None


def _share_url(shared_game: SharedGame, request) -> str:
    return absolute_media_url(f'/join/s/{shared_game.token}/', request)


def _attempt_payload(attempt: SharedGameAttempt | None) -> dict | None:
    if attempt is None:
        return None
    return {
        'game_token': attempt.game.token,
        'completed': attempt.completed_at is not None,
        'is_ranked': attempt.is_ranked,
        'score': attempt.score,
        'correct_count': attempt.correct_count,
        'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
    }


def shared_game_payload(shared_game: SharedGame, request, player: Player | None) -> dict:
    shared_game.refresh_status()
    template = shared_game.template_game
    mine = attempt_for(shared_game, player) if player else None
    is_owner = bool(player and player.user_id and player.user_id == shared_game.owner_id)
    country = template.country
    return {
        'token': shared_game.token,
        'share_url': _share_url(shared_game, request),
        'owner_name': player_name_for_user(shared_game.owner),
        'is_owner': is_owner,
        'status': shared_game.status,
        'is_open': shared_game.is_open,
        'created': shared_game.created.isoformat(),
        'ends_at': shared_game.ends_at.isoformat() if shared_game.ends_at else None,
        'closes_at': shared_game.closes_at.isoformat(),
        'finished_at': shared_game.finished_at.isoformat() if shared_game.finished_at else None,
        'game': {
            'country': {'code': country.code, 'name': country.name} if country else None,
            **{
                key: getattr(template, key)
                for key in (
                    'level', 'length', 'media', 'rarity', 'game_type', 'speed_seconds',
                    'tax_order', 'tax_family', 'species_group', 'season', 'include_escapes',
                )
            },
        },
        'my_attempt': _attempt_payload(mine),
        'can_play': shared_game.is_open and (mine is None or mine.completed_at is None),
        'can_finish': is_owner and shared_game.is_open,
        'leaderboard': leaderboard(shared_game, player),
    }


class SharedGameListCreateView(APIView):
    """GET: shared games you own or played. POST: create one from normal game settings."""

    permission_classes = [AllowAny]

    def get(self, request):
        player = _request_player(request)
        if player is None:
            return Response({'error': 'not_authenticated'}, status=status.HTTP_401_UNAUTHORIZED)
        owned = SharedGame.objects.none()
        if player.user_id:
            owned = SharedGame.objects.filter(owner_id=player.user_id)
            played = SharedGame.objects.filter(attempts__user_id=player.user_id)
        else:
            played = SharedGame.objects.filter(attempts__player=player)
        games = (owned | played).distinct().select_related('template_game__country', 'owner')[:50]
        return Response([shared_game_payload(sg, request, player) for sg in games])

    def post(self, request):
        player = _request_player(request)
        owner = _owner_user(player)
        if owner is None:
            return Response({'error': 'login_required'}, status=status.HTTP_401_UNAUTHORIZED)

        duration_hours = request.data.get('duration_hours')
        if duration_hours in ('', None):
            duration_hours = None
        else:
            try:
                duration_hours = int(duration_hours)
            except (TypeError, ValueError):
                duration_hours = 0
            if not 1 <= duration_hours <= MAX_DURATION_HOURS:
                return Response(
                    {'error': 'invalid_duration', 'max_hours': MAX_DURATION_HOURS},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        data = {key: value for key, value in request.data.items() if key != 'duration_hours'}
        serializer = GameSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        game_type = serializer.validated_data.get('game_type', Game.GAME_TYPE_STANDARD)
        if game_type not in SHAREABLE_GAME_TYPES:
            return Response({'error': 'game_type_not_shareable'}, status=status.HTTP_400_BAD_REQUEST)
        length = serializer.validated_data.get('length') or 0
        if not 1 <= length <= MAX_LENGTH:
            return Response(
                {'error': 'invalid_length', 'max_length': MAX_LENGTH},
                status=status.HTTP_400_BAD_REQUEST,
            )

        template = serializer.save(host=player, multiplayer=False)
        try:
            shared_game = create_shared_game(
                owner=owner, template=template, duration_hours=duration_hours
            )
        except SharedGameContentError as exc:
            template.delete()
            return Response(
                {'error': 'insufficient_content', 'detail': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(
            shared_game_payload(shared_game, request, player),
            status=status.HTTP_201_CREATED,
        )


class SharedGameDetailView(APIView):
    """Public: anyone with the link sees the settings, status and leaderboard."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        shared_game = get_object_or_404(
            SharedGame.objects.select_related('template_game__country', 'owner'), token=token
        )
        return Response(shared_game_payload(shared_game, request, _request_player(request)))


class SharedGamePlayView(APIView):
    """Start (or resume) your attempt; returns the game token to play with the normal game API."""

    permission_classes = [AllowAny]

    def post(self, request, token):
        shared_game = get_object_or_404(SharedGame, token=token)
        player = _request_player(request)
        if player is None:
            return Response({'error': 'player_required'}, status=status.HTTP_401_UNAUTHORIZED)
        shared_game.refresh_status()
        existing = attempt_for(shared_game, player)
        if existing and existing.completed_at:
            return Response({'error': 'already_played'}, status=status.HTTP_400_BAD_REQUEST)
        if not shared_game.is_open:
            return Response({'error': 'finished'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            attempt, created = start_attempt(shared_game, player)
        except IntegrityError:
            # A parallel request (double tap) started it first.
            attempt, created = attempt_for(shared_game, player), False
        record_player_score_client_from_request(attempt.player, attempt.game, request)
        return Response(
            {
                'game_token': attempt.game.token,
                'player_token': attempt.player.token,
                'length': attempt.game.length,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class SharedGameFinishView(APIView):
    """Owner closes the game now; the leaderboard is final and question stats open up."""

    permission_classes = [AllowAny]

    def post(self, request, token):
        shared_game = get_object_or_404(SharedGame, token=token)
        player = _request_player(request)
        if _owner_user(player) is None or player.user_id != shared_game.owner_id:
            return Response({'error': 'not_owner'}, status=status.HTTP_403_FORBIDDEN)
        shared_game.finish()
        return Response(shared_game_payload(shared_game, request, player))


class SharedGameStatsView(APIView):
    """Right/wrong per question; only once finished, so open games don't leak answers."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        shared_game = get_object_or_404(SharedGame, token=token)
        shared_game.refresh_status()
        if shared_game.status != SharedGame.STATUS_FINISHED:
            return Response({'error': 'not_finished'}, status=status.HTTP_403_FORBIDDEN)
        player = _request_player(request)
        language = request.query_params.get('language') or (player.language if player else 'en')
        return Response(
            {
                'participants': leaderboard(shared_game)['total_participants'],
                'questions': question_stats(shared_game, language),
            }
        )
