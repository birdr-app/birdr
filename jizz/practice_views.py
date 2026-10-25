"""Personal practice stats and confusion-pair drill games."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from jizz.practice_serializers import (
    StartConfusionPairPracticeSerializer,
    StartMixupPracticeSerializer,
    StartPracticeResponseSerializer,
    StartSpeciesPracticeSerializer,
    TroubleSpotsResponseSerializer,
)


class TroubleSpotsView(APIView):
    """GET — personal mistake species, confusion pairs and mixed-up flocks for the authenticated user."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = TroubleSpotsResponseSerializer.for_user(request.user, request)
        return Response(serializer.data)


class GlobalTroubleSpotsView(APIView):
    """GET — tricky birds across all players (species, pairs, mixed-up flocks)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = TroubleSpotsResponseSerializer.for_everyone(request)
        return Response(serializer.data)


class StartSpeciesPracticeView(APIView):
    """POST — start a 20-question pro drill focused on one species and kin."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StartSpeciesPracticeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        response = StartPracticeResponseSerializer(
            {
                'game': result['game'],
                'player_token': result['player'].token,
            },
            context={'request': request},
        )
        return Response(response.data, status=status.HTTP_201_CREATED)


class StartConfusionPairPracticeView(APIView):
    """POST — start a 20-question two-option drill for one confusion pair."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StartConfusionPairPracticeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        response = StartPracticeResponseSerializer(
            {
                'game': result['game'],
                'player_token': result['player'].token,
            },
            context={'request': request},
        )
        return Response(response.data, status=status.HTTP_201_CREATED)


class StartMixupPracticeView(APIView):
    """POST — start a 20-question drill within one mixed-up flock (3–6 species, all as options)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StartMixupPracticeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        response = StartPracticeResponseSerializer(
            {
                'game': result['game'],
                'player_token': result['player'].token,
            },
            context={'request': request},
        )
        return Response(response.data, status=status.HTTP_201_CREATED)
