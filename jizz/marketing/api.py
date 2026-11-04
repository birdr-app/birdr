"""API for the marketing website."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from compare.descriptions import generation_status, start_generation, take_generation_slot
from compare.views import OptionalJWTAuthentication
from jizz.marketing.i18n import is_marketing_locale
from jizz.models import Species


class SpeciesDescriptionView(APIView):
    """Status of a species' AI text (GET), or start writing it (POST, logged-in users only)."""

    authentication_classes = [OptionalJWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        # The page polls this until the text is ready, so no cache may keep an old status.
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    def get(self, request, species_id: int):
        species = get_object_or_404(Species, pk=species_id)
        return Response(generation_status(species))

    def post(self, request, species_id: int):
        species = get_object_or_404(Species, pk=species_id)
        state = generation_status(species)
        if state.get('ready') or state.get('pending') or state.get('error') == 'unavailable':
            return Response(state)
        # Writing calls OpenAI, so it is for logged-in users only, and rationed per hour.
        # 403 rather than 401, like comparisons, so the React app does not log anyone out.
        if not request.user.is_authenticated:
            return Response({'login_required': True}, status=status.HTTP_403_FORBIDDEN)
        if not take_generation_slot(request.user):
            return Response({'rate_limited': True}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        language = request.data.get('language') or 'en'
        if not is_marketing_locale(language):
            language = 'en'
        return Response(start_generation(species, language), status=status.HTTP_202_ACCEPTED)
