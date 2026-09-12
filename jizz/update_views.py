from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Value
from django.db.models.fields import BooleanField
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from jizz.models import Player, Update, UpdateThumbsUp
from jizz.serializers import UpdateDetailSerializer, UpdateListSerializer
from jizz.update_emails import mark_email_opened, TRANSPARENT_GIF
from jizz.views import UpdatePagination


def _player_from_request(request):
    token = request.query_params.get('player_token', '').strip()
    if not token:
        return None
    return Player.objects.filter(token=token).first()


def _annotate_updates(qs, user, player):
    qs = qs.annotate(thumbs_up_count=Count('thumbs_ups', distinct=True))
    if user:
        return qs.annotate(
            user_has_thumbs_up=Exists(
                UpdateThumbsUp.objects.filter(update_id=OuterRef('pk'), user=user)
            ),
        )
    if player:
        return qs.annotate(
            user_has_thumbs_up=Exists(
                UpdateThumbsUp.objects.filter(update_id=OuterRef('pk'), player=player)
            ),
        )
    return qs.annotate(user_has_thumbs_up=Value(False, output_field=BooleanField()))


class UpdateListView(ListAPIView):
    serializer_class = UpdateListSerializer
    pagination_class = UpdatePagination

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        player = _player_from_request(self.request)
        qs = Update.objects.filter(published=True).select_related('user').prefetch_related(
            'reactions__player',
            'translations',
        ).order_by('-created')
        return _annotate_updates(qs, user, player)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['player'] = _player_from_request(self.request)
        return ctx


class UpdateDetailView(RetrieveAPIView):
    serializer_class = UpdateDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user = self.request.user if self.request.user.is_authenticated else None
        player = _player_from_request(self.request)
        qs = Update.objects.filter(published=True).select_related('user').prefetch_related(
            'reactions__player',
            'translations',
        )
        return _annotate_updates(qs, user, player)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['player'] = _player_from_request(self.request)
        return ctx


class UpdateThumbsUpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        update = get_object_or_404(Update, pk=pk, published=True)
        player_token = (request.data.get('player_token') or '').strip()
        user = request.user if request.user.is_authenticated else None
        player = Player.objects.filter(token=player_token).first() if player_token else None

        if not user and not player:
            return Response(
                {'detail': 'Authentication or player_token required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lookup = {'update': update}
        if user:
            lookup['user'] = user
        else:
            lookup['player'] = player

        _, created = UpdateThumbsUp.objects.get_or_create(**lookup)
        count = update.thumbs_ups.count()
        return Response({'thumbs_up_count': count, 'user_has_thumbs_up': True}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, pk):
        update = get_object_or_404(Update, pk=pk, published=True)
        player_token = (request.data.get('player_token') or request.query_params.get('player_token') or '').strip()
        user = request.user if request.user.is_authenticated else None
        player = Player.objects.filter(token=player_token).first() if player_token else None

        qs = UpdateThumbsUp.objects.filter(update=update)
        if user:
            qs.filter(user=user).delete()
        elif player:
            qs.filter(player=player).delete()
        else:
            return Response({'detail': 'Authentication or player_token required'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'thumbs_up_count': update.thumbs_ups.count(), 'user_has_thumbs_up': False})


class UpdateEmailOpenTrackingView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        mark_email_opened(token)
        return HttpResponse(TRANSPARENT_GIF, content_type='image/gif')
