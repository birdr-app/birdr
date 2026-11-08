"""Trip prep API.

GET  /api/trips/                      countries on offer (region packs hang off their country's trip)
GET  /api/trips/<cc>/?lang=           everything the screens show (public, cached)
GET  /api/trips/<cc>/progress/        the player's known species and groups (JWT user or player token)
POST /api/trips/<cc>/answers/         store a unit quiz as a trip_prep game
"""

from django.core.cache import cache
from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from jizz.trips.api import (
    players_for_request,
    record_answers,
    trip_language,
    trip_payload,
    trip_progress,
    trip_summary,
)
from jizz.trips.content import TRIPS, is_region

CACHE_SECONDS = 10 * 60
MAX_ANSWERS = 60


def _country(code: str) -> str:
    code = code.upper()
    if code not in TRIPS:
        raise Http404
    return code


class TripListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        lang = (request.query_params.get('lang') or 'en').lower()[:2]
        return Response([trip_summary(code, trip_language(code, lang)) for code in TRIPS if not is_region(code)])


class TripDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, country):
        country = _country(country)
        lang = trip_language(country, request.query_params.get('lang'))
        key = f'trip:{country}:{lang}'
        payload = cache.get(key)
        if payload is None:
            payload = trip_payload(country, lang)
            cache.set(key, payload, CACHE_SECONDS)
        return Response(payload)


class TripProgressView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, country):
        country = _country(country)
        return Response(trip_progress(country, players_for_request(request)))


class TripAnswersView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, country):
        country = _country(country)
        players = players_for_request(request)
        if not players:
            return Response({'detail': 'Sign in or play a game first, so your answers can be saved.'}, status=401)
        answers = request.data.get('answers')
        if not isinstance(answers, list) or not answers or len(answers) > MAX_ANSWERS:
            return Response({'detail': f'Send 1 to {MAX_ANSWERS} answers.'}, status=400)
        cleaned = []
        for row in answers:
            try:
                cleaned.append({
                    'species_id': int(row['species_id']),
                    'answer_id': int(row['answer_id']),
                    'media_id': int(row['media_id']) if row.get('media_id') else None,
                })
            except (KeyError, TypeError, ValueError):
                return Response({'detail': 'Each answer needs species_id and answer_id.'}, status=400)
        player = max(players, key=lambda p: p.created)
        game_id = record_answers(country, player, cleaned)
        return Response({'game_id': game_id, **trip_progress(country, players)}, status=201)
