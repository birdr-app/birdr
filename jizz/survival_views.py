"""Survival mode: Pro-level images game that lasts until the first wrong answer."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from jizz.authentication import PlayerTokenAuthentication
from jizz.game_question_selection import candidate_species_ids
from jizz.models import Answer, Country, Game, Player, PlayerScore
from jizz.practice_serializers import get_or_create_player_for_user
from jizz.serializers import GameSerializer
from jizz.services.checklist import localized_species_names
from media.display_urls import media_display_url

SURVIVAL_SPEED_SECONDS = 15
SURVIVAL_LEADERBOARD_SIZE = 100


def survival_scores(country):
    """Finished-or-running survival scores for one country (streak > 0 only)."""
    return PlayerScore.objects.filter(
        game__game_type=Game.GAME_TYPE_SURVIVAL,
        game__country=country,
        streak__gt=0,
    )


def best_per_player(qs):
    """Each player's best run, ranked by streak, ties broken by speed points."""
    best = (
        qs.annotate(
            player_rank=Window(
                expression=RowNumber(),
                partition_by=[F('player_id')],
                order_by=[F('streak').desc(), F('score').desc(), F('id').asc()],
            )
        )
        .filter(player_rank=1)
        .select_related('player', 'game')
    )
    return sorted(best, key=lambda ps: (-ps.streak, -ps.score, ps.id))


def record_payload(player_score):
    if player_score is None:
        return None
    return {
        'streak': player_score.streak,
        'score': player_score.score,
        'name': player_score.player.name,
    }


def country_record(country, exclude_game=None):
    qs = survival_scores(country)
    if exclude_game is not None:
        qs = qs.exclude(game=exclude_game)
    return qs.select_related('player').order_by('-streak', '-score', 'id').first()


def personal_best(country, player, exclude_game=None):
    qs = survival_scores(country).filter(player=player)
    if exclude_game is not None:
        qs = qs.exclude(game=exclude_game)
    best = qs.order_by('-streak').values_list('streak', flat=True).first()
    return best or 0


def shown_media(question):
    """The photo the player actually saw for this question (locked, else the play rotation)."""
    if question.media_id:
        return question.media
    from jizz.question_play import active_play_media, fetch_eligible_media_for_species

    shown = active_play_media(fetch_eligible_media_for_species(question.species_id, 'image'), question.number or 0)
    return shown[0] if shown else None


def missed_payload_for(wrong: Answer, game: Game, names: dict[int, str]) -> dict:
    """The bird that ended the run: correct species, the player's answer and the photo shown."""
    species = wrong.question.species
    # Timeouts are stored as a wrong option; detect them by the elapsed time.
    timed_out = bool(game.speed_seconds) and (
        wrong.created - wrong.question.created >= timedelta(seconds=game.speed_seconds)
    )
    media = shown_media(wrong.question)
    return {
        'species': {
            'id': species.id,
            'name': species.name,
            'name_translated': names.get(species.id, species.name),
            'name_latin': species.name_latin,
        },
        'answer': None if timed_out else {
            'id': wrong.answer.id,
            'name': wrong.answer.name,
            'name_translated': names.get(wrong.answer.id, wrong.answer.name),
        },
        'timed_out': timed_out,
        'image': {
            'url': media_display_url(media.url),
            'contributor': media.contributor or '',
        } if media is not None and media.url else None,
    }


class SurvivalPlayerMixin:
    """Resolve the player from `Bearer <player token>` (guests) or a JWT (logged in)."""

    authentication_classes = [PlayerTokenAuthentication, JWTAuthentication]
    permission_classes = [AllowAny]

    def get_player(self, request, required=True):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            return get_or_create_player_for_user(user)
        token = request.auth
        if token:
            player = Player.objects.filter(token=str(token)).first()
            if player:
                return player
        if required:
            raise AuthenticationFailed('Player token or login required.')
        return None


def get_country(code):
    code = (code or '').strip()
    if not code:
        raise ValidationError({'country': 'This field is required.'})
    country = Country.objects.filter(code__iexact=code).first()
    if country is None:
        raise ValidationError({'country': 'Unknown country.'})
    return country


class StartSurvivalSerializer(serializers.Serializer):
    country = serializers.CharField()
    language = serializers.CharField(required=False, allow_blank=True, default='en')


class SurvivalStartView(SurvivalPlayerMixin, APIView):
    """POST — start a new survival run for a country."""

    def post(self, request):
        serializer = StartSurvivalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        player = self.get_player(request)
        country = get_country(serializer.validated_data['country'])
        language = serializer.validated_data['language'] or player.language or 'en'

        game = Game(
            country=country,
            language=language,
            level='advanced',
            rarity=Game.RARIT_EXCEPTIONAL,
            media='images',
            length=0,
            multiplayer=False,
            speed_seconds=SURVIVAL_SPEED_SECONDS,
            game_type=Game.GAME_TYPE_SURVIVAL,
            host=player,
        )
        if len(candidate_species_ids(game)) < 2:
            raise ValidationError({'country': 'Not enough species with images for this country.'})
        game.save()
        PlayerScore.objects.get_or_create(player=player, game=game, defaults={'score': 0})
        from jizz.client_info import record_player_score_client_from_request

        record_player_score_client_from_request(player, game, request)
        game.add_question()

        return Response(
            {
                'game': GameSerializer(game, context={'request': request}).data,
                'player_token': player.token,
                'country_record': record_payload(country_record(country, exclude_game=game)),
                'personal_best': personal_best(country, player, exclude_game=game),
            },
            status=status.HTTP_201_CREATED,
        )


class SurvivalRecordView(SurvivalPlayerMixin, APIView):
    """GET ?country=XX — the country record and the caller's personal best."""

    def get(self, request):
        country = get_country(request.query_params.get('country'))
        player = self.get_player(request, required=False)
        return Response(
            {
                'country_record': record_payload(country_record(country)),
                'personal_best': personal_best(country, player) if player else 0,
            }
        )


class SurvivalResultView(SurvivalPlayerMixin, APIView):
    """GET — outcome of a survival run, compared with records set before it."""

    def get(self, request, token):
        game = get_object_or_404(
            Game.objects.select_related('country'),
            token=token,
            game_type=Game.GAME_TYPE_SURVIVAL,
        )
        player = self.get_player(request)
        player_score = get_object_or_404(PlayerScore, game=game, player=player)
        country = game.country

        previous_record = country_record(country, exclude_game=game)
        previous_best = personal_best(country, player, exclude_game=game)
        streak = player_score.streak
        is_country_record = streak > 0 and (
            previous_record is None
            or (streak, player_score.score) > (previous_record.streak, previous_record.score)
        )

        rank = None
        if streak > 0:
            for position, row in enumerate(best_per_player(survival_scores(country)), start=1):
                if row.player_id == player.id:
                    rank = position
                    break

        return Response(
            {
                'streak': streak,
                'score': player_score.score,
                'rank': rank,
                'ended': game.ended,
                'country': {'code': country.code, 'name': country.name},
                'previous_country_record': record_payload(previous_record),
                'previous_personal_best': previous_best,
                'is_country_record': is_country_record,
                'is_personal_best': streak > previous_best,
                'missed': self.missed_payload(game, player_score),
            }
        )

    def missed_payload(self, game, player_score):
        wrong = (
            Answer.objects.filter(player_score=player_score, correct=False)
            .select_related('question__species', 'question__media', 'answer')
            .first()
        )
        if wrong is None:
            return None
        names = localized_species_names(
            {wrong.question.species_id: wrong.question.species, wrong.answer_id: wrong.answer}, game.language,
        )
        return missed_payload_for(wrong, game, names)


class SurvivalScoresView(SurvivalPlayerMixin, APIView):
    """GET ?country=XX — best survival run per player for a country."""

    def get(self, request):
        country = get_country(request.query_params.get('country'))
        me = self.get_player(request, required=False)
        rows = best_per_player(survival_scores(country))[:SURVIVAL_LEADERBOARD_SIZE]
        missed = self.missed_by_score(rows, request.query_params.get('language') or 'en')
        return Response(
            {
                'country': {'code': country.code, 'name': country.name},
                'results': [
                    {
                        'id': row.id,
                        'ranking': position,
                        'name': row.player.name,
                        'streak': row.streak,
                        'score': row.score,
                        'created': row.game.created if row.game_id else None,
                        'is_mine': me is not None and row.player_id == me.id,
                        'missed': missed.get(row.id),
                    }
                    for position, row in enumerate(rows, start=1)
                ],
            }
        )

    @staticmethod
    def missed_by_score(rows, language: str) -> dict[int, dict]:
        """The bird each listed run ended on, in the viewer's species language."""
        wrong_answers = {}
        for answer in (
            Answer.objects.filter(player_score_id__in=[row.id for row in rows], correct=False)
            .select_related('question__species', 'question__media', 'question__game', 'answer')
            .order_by('created')
        ):
            wrong_answers.setdefault(answer.player_score_id, answer)
        species = {}
        for answer in wrong_answers.values():
            species[answer.question.species_id] = answer.question.species
            species[answer.answer_id] = answer.answer
        names = localized_species_names(species, language)
        return {
            score_id: missed_payload_for(answer, answer.question.game, names)
            for score_id, answer in wrong_answers.items()
        }
