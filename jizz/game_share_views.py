"""Public HTML + JSON + OG image for shareable game results."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from jizz.game_share import game_is_shareable, game_share_payload
from jizz.models import Game
from jizz.services.species_cover import absolute_media_url


def _absolute_url(request, path: str) -> str:
    return absolute_media_url(path, request)


def _png_response(png: bytes, *, max_age: int = 600) -> HttpResponse:
    response = HttpResponse(png, content_type='image/png')
    response['Cache-Control'] = f'public, max-age={max_age}'
    return response


def _shareable_game(token: str) -> Game | None:
    game = (
        Game.objects.select_related('country', 'host')
        .filter(token=token)
        .first()
    )
    if not game_is_shareable(game):
        return None
    return game


def _store_urls() -> tuple[str, str]:
    return (
        getattr(settings, 'APP_STORE_URL', 'https://apps.apple.com/us/app/motmot-bird-id-quiz/id6745144189'),
        getattr(settings, 'PLAY_STORE_URL', 'https://play.google.com/store/apps/details?id=pro.birdr.app'),
    )


def _page_context(request, game: Game | None) -> dict:
    app_store_url, play_store_url = _store_urls()
    if game is None:
        return {
            'missing': True,
            'app_store_url': app_store_url,
            'play_store_url': play_store_url,
        }
    share_path = f'/g/{game.token}/'
    payload = game_share_payload(
        game,
        share_url=_absolute_url(request, share_path),
        og_image=_absolute_url(request, f'/g/{game.token}/og.png'),
    )
    return {
        'missing': False,
        'app_store_url': app_store_url,
        'play_store_url': play_store_url,
        **payload,
        'canonical_url': payload['share_url'],
    }


def game_result_share_page(request, token: str):
    """HTML landing + Open Graph tags for a finished game."""
    game = _shareable_game(token)
    status = 404 if game is None else 200
    return render(request, 'jizz/game_result_share.html', _page_context(request, game), status=status)


def game_result_og_image(request, token: str):
    """Generated 1200×630 PNG for messenger / social link previews."""
    from jizz.flock_share import render_game_result_og_image

    game = _shareable_game(token)
    if game is None:
        return HttpResponse(status=404)
    payload = game_share_payload(game, share_url='', og_image='')
    png = render_game_result_og_image(
        country_name=payload['country']['name'],
        subtitle=payload['subtitle'],
        players=payload['players'],
    )
    return _png_response(png)


class GamePublicShareView(APIView):
    """Public-safe finished-game result (no answers / emails / tokens)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        game = _shareable_game(token)
        if game is None:
            return Response({'error': 'not_found'}, status=404)
        payload = game_share_payload(
            game,
            share_url=_absolute_url(request, f'/g/{game.token}/'),
            og_image=_absolute_url(request, f'/g/{game.token}/og.png'),
        )
        return Response(payload)
