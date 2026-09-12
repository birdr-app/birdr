from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Case, When, Value, Prefetch, F, Q
from django.db.models.aggregates import Count
from django.db.models.functions import RowNumber
from django.db.models.expressions import Window
from django.http import Http404, HttpResponse
from django.views.generic import DetailView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from jizz.authentication import PlayerTokenAuthentication
from rest_framework_social_oauth2.views import ConvertTokenView
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import login
import logging

logger = logging.getLogger(__name__)
from social_django.views import complete as social_complete
from rest_framework import status
from rest_framework.exceptions import NotFound, APIException
from rest_framework import generics
from django.shortcuts import get_object_or_404
from .models import Game, Language, Page
from .serializers import (
    GameSerializer,
    GameLanguageSerializer,
    FamilyListSerializer,
    OrderListSerializer,
    SpeciesGroupListSerializer,
    LanguageSerializer,
    PageSerializer,
    PageListSerializer,
)

from jizz.models import (
    Answer,
    QuestionMediaReady,
    Country,
    CountrySpecies,
    SpeciesName,
    Feedback,
    FlagQuestion,
    Game,
    Player,
    PlayerScore,
    Question,
    Species,
    TaxonomicOrder,
    TaxonomicFamily,
    SpeciesGroup,
    MIN_TAX_FILTER_SPECIES,
    Update,
    Reaction,
    UserProfile,
    Friendship,
    DailyChallenge,
    DailyChallengeParticipant,
    DailyChallengeInvite,
    DailyChallengeRound,
    DeviceToken,
)
from media.models import Media, MediaReview, FlagMedia
from jizz.serializers import (
    AnswerSerializer,
    CountrySerializer,
    FeedbackSerializer,
    MediaSerializer,
    ReviewMediaSerializer,
    FirstAssertionReviewSerializer,
    MediaReviewBriefSerializer,
    FlagMediaSerializer,
    FlagQuestionSerializer,
    GameSerializer,
    PlayerScoreListSerializer,
    PlayerScoreSerializer,
    SpeciesReviewStatsSerializer,
    SpeciesWithMediaReviewSerializer,
    PlayerSerializer,
    QuestionSerializer,
    QuestionPlaySerializer,
    SpeciesCoverSerializer,
    SpeciesDetailSerializer,
    SpeciesListSerializer,
    SpeciesSlugSerializer,
    UpdateSerializer,
    ReactionSerializer,
)

User = get_user_model()


class GetPlayerMixin:

    def get_token_from_header(self, request):
        auth_header = request.headers.get("Authorization", None)

        if not auth_header:
            raise AuthenticationFailed("Authorization header is missing")
        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            raise AuthenticationFailed("Invalid Authorization header format")

        return token

    def get_user_from_token(self, token):
        try:
            return Player.objects.get(token=token)
        except Exception as e:
            raise AuthenticationFailed("Invalid token or user does not exist")

    def get_player_from_token(self, request):
        token = self.get_token_from_header(self.request)
        return self.get_user_from_token(token)

    def get_player_from_request(self, request):
        token = self.get_token_from_header(self.request)
        player = self.get_user_from_token(token)
        return player


class CountryDetailView(DetailView):
    model = Country

    def get_context_data(self, **kwargs):
        context = super(CountryDetailView, self).get_context_data(**kwargs)
        if self.object.species.count() == 0:
            raise NotImplemented("Country is missing species.")
        context["species"] = self.object.species.order_by("?").first().species
        return context


class CountryViewSet(viewsets.ModelViewSet):
    serializer_class = CountrySerializer
    queryset = Country.objects.exclude(countryspecies__isnull=True).all()
    pagination_class = None
    permission_classes = [AllowAny]
    authentication_classes = []

    queryset = (
        Country.objects.annotate(
            custom_order=Case(
                When(code="world", then=Value(0)),
                default=Value(1),
            )
        )
        .exclude(countryspecies__isnull=True)
        .order_by("custom_order", "name")
    )


SPECIES_LIST_CACHE_TTL = 3600


class SpeciesListView(ListAPIView):
    serializer_class = SpeciesListSerializer
    queryset = Species.objects.select_related('taxonomic_order', 'taxonomic_family')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["countryspecies__country"]
    permission_classes = [AllowAny]
    authentication_classes = []  # No authentication required for public species data
    pagination_class = None  # Disable pagination - we need all species for the combobox

    def get_queryset(self):
        qs = super().get_queryset()
        language = (self.request.query_params.get('language') or '').strip()
        lang = language.lower().split('-')[0].split('_')[0] if language else ''
        if language and lang != 'la':
            qs = qs.prefetch_related(
                Prefetch(
                    'speciesname_set',
                    queryset=SpeciesName.objects.filter(language_id=language),
                    to_attr='_translated_names',
                )
            )
        return qs

    def list(self, request, *args, **kwargs):
        country = (request.query_params.get("countryspecies__country") or "").strip()
        if not country:
            return Response(
                {"detail": "countryspecies__country is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        language = (request.query_params.get("language") or "").strip()
        cache_key = f"jizz:species_list:{country}:{language}"
        cached = cache.get(cache_key)
        if cached is not None:
            response = Response(cached)
            response["Cache-Control"] = "public, max-age=3600"
            return response
        queryset = self.filter_queryset(self.get_queryset()).distinct()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        cache.set(cache_key, data, SPECIES_LIST_CACHE_TTL)
        response = Response(data)
        response["Cache-Control"] = "public, max-age=3600"
        return response


class SpeciesDetailView(RetrieveAPIView):
    serializer_class = SpeciesDetailSerializer
    queryset = Species.objects.all()
    permission_classes = [AllowAny]
    authentication_classes = []  # No authentication required for public species data


class SpeciesBySlugView(RetrieveAPIView):
    """Public species lookup by marketing slug for practice start pages."""

    serializer_class = SpeciesSlugSerializer
    queryset = Species.objects.all()
    lookup_field = 'slug'
    permission_classes = [AllowAny]
    authentication_classes = []


class SpeciesCoverView(RetrieveAPIView):
    """Cover / field-guide illustration; may call OpenAI to generate on first request."""

    serializer_class = SpeciesCoverSerializer
    queryset = Species.objects.prefetch_related('illustration')
    permission_classes = [AllowAny]
    authentication_classes = []

    def retrieve(self, request, *args, **kwargs):
        from jizz.services.species_illustration import ensure_species_illustration

        instance = self.get_object()
        ensure_species_illustration(instance)
        instance.refresh_from_db()
        serializer = self.get_serializer(instance, context=self.get_serializer_context())
        return Response(serializer.data)


class LanguageListView(ListAPIView):
    serializer_class = LanguageSerializer
    queryset = Language.objects.all()
    pagination_class = None

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        data = [
            row
            for row in self.get_serializer(queryset, many=True).data
            if row.get('code') != 'la'
        ]
        data.sort(key=lambda row: (row.get('name') or '').lower())
        return Response([{'code': 'la', 'name': 'Scientific (Latin)'}, *data])


class PageListView(ListAPIView):
    """List help pages (show=True only)."""
    serializer_class = PageListSerializer
    queryset = Page.objects.filter(show=True).order_by('title')
    pagination_class = None
    permission_classes = [AllowAny]
    authentication_classes = []


class PageDetailView(RetrieveAPIView):
    """Retrieve a help page by slug."""
    serializer_class = PageSerializer
    queryset = Page.objects.filter(show=True)
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'
    permission_classes = [AllowAny]
    authentication_classes = []


class FamilyListView(ListAPIView):
    serializer_class = FamilyListSerializer
    pagination_class = None

    def get_queryset(self):
        country_id = self.request.query_params.get("country", None)
        queryset = TaxonomicFamily.objects.all()

        if country_id:
            queryset = queryset.filter(
                species__countryspecies__country_id=country_id,
                species__countryspecies__status__in=["native", "endemic", "rare"],
            )

        return (
            queryset.annotate(count=Count('species', distinct=True))
            .filter(count__gte=MIN_TAX_FILTER_SPECIES)
            .order_by('name_latin')
        )

class OrderListView(ListAPIView):
    serializer_class = OrderListSerializer
    pagination_class = None

    def get_queryset(self):
        country_id = self.request.query_params.get("country", None)
        queryset = TaxonomicOrder.objects.all()
        if country_id:
            queryset = queryset.filter(
                species__countryspecies__country_id=country_id,
                species__countryspecies__status__in=["native", "endemic", "rare"],
            )
        return (
            queryset.annotate(count=Count('species', distinct=True))
            .filter(count__gte=MIN_TAX_FILTER_SPECIES)
            .order_by('name_latin')
        )


class SpeciesGroupListView(ListAPIView):
    serializer_class = SpeciesGroupListSerializer
    pagination_class = None

    def get_queryset(self):
        country_id = self.request.query_params.get("country", None)
        queryset = SpeciesGroup.objects.all()
        if country_id:
            queryset = queryset.filter(
                species__countryspecies__country_id=country_id,
                species__countryspecies__status__in=["native", "endemic", "rare"],
            )
        return (
            queryset.annotate(count=Count('species', distinct=True))
            .filter(count__gte=MIN_TAX_FILTER_SPECIES)
            .order_by('sort_order', 'name_en')
        )


class PlayerCreateView(CreateAPIView):
    serializer_class = PlayerSerializer
    queryset = Player.objects.all()
    permission_classes = [AllowAny]  # Allow anonymous users to create players

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def perform_create(self, serializer):
        ip = self.get_client_ip(self.request)
        # If the request is authenticated (e.g. Bearer token), the new player is linked to that user.
        # No need to call /api/player/link/ later — link is only for linking an *existing* anonymous player.
        user = self.request.user if (self.request.user and self.request.user.is_authenticated) else None
        return serializer.save(ip=ip, user=user)


class PlayerView(RetrieveUpdateAPIView):
    serializer_class = PlayerSerializer
    queryset = Player.objects.all()
    lookup_field = "token"


class PlayerStatsView(RetrieveAPIView):
    serializer_class = PlayerSerializer
    queryset = Player.objects.all()
    lookup_field = "token"


class PlayerLinkView(APIView):
    """
    Link an existing player (by player token) to the currently authenticated user.
    Call after login so anonymous player/game data is associated with the account.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        player_token = (request.data or {}).get("player_token") or (request.data or {}).get("token")
        if not player_token or not isinstance(player_token, str):
            import logging
            logging.getLogger(__name__).warning("PlayerLinkView: missing or invalid player_token")
            return Response(
                {"error": "Missing player_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        player_token = player_token.strip()
        if not player_token:
            return Response(
                {"error": "Missing player_token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            player = Player.objects.get(token=player_token.strip())
        except Player.DoesNotExist:
            return Response(
                {"error": "Player not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if player.user_id is not None and player.user_id != request.user.id:
            return Response(
                {"error": "Player already linked to another account"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        player.user = request.user
        player.save(update_fields=["user"])
        return Response({"ok": True, "player_id": player.id})
    serializer_class = FlagQuestionSerializer
    queryset = FlagQuestion.objects.all()


class MediaPagination(PageNumberPagination):
    """Custom pagination for media list with 50 items per page."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class SpeciesReviewPagination(PageNumberPagination):
    """Paginate by species (default 3 per page) for media-review."""
    page_size = 3
    page_size_query_param = 'page_size'
    max_page_size = 20


class MediaListView(ListAPIView):
    """List media for review. level=fast|full|thorough. fast: species not fully reviewed and <10 approved; full: species not fully reviewed; thorough: all media with review_status."""
    serializer_class = MediaSerializer
    pagination_class = MediaPagination

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['level'] = self.request.query_params.get('level', 'fast')
        return context

    def get_queryset(self):
        from jizz.models import CountrySpecies

        level = self.request.query_params.get('level', 'fast')
        media_type = self.request.query_params.get('type', 'image')
        country_code = self.request.query_params.get('country')
        species_id_param = self.request.query_params.get('species')

        # Base filters (type, country, species)
        queryset = Media.objects.filter(hide=False, type=media_type)
        if country_code:
            country_species_ids = CountrySpecies.objects.exclude(
                status__in=['introduced', 'extirpated', 'uncertain', 'unknown']
            ).filter(country__code=country_code).values_list('species_id', flat=True)
            queryset = queryset.filter(species_id__in=country_species_ids)
        if species_id_param:
            try:
                queryset = queryset.filter(species_id=int(species_id_param))
            except (ValueError, TypeError):
                pass

        if level == 'thorough':
            # All media (including reviewed) with review counts annotated
            queryset = queryset.annotate(
                _approved_count=Count('reviews', filter=Q(reviews__review_type='approved')),
                _rejected_count=Count('reviews', filter=Q(reviews__review_type='rejected')),
                _not_sure_count=Count('reviews', filter=Q(reviews__review_type='not_sure')),
            )
            return queryset.order_by('species__id', '-created')
        else:
            # fast or full: only unreviewed media
            reviewed_media_ids = MediaReview.objects.values_list('media_id', flat=True).distinct()
            queryset = queryset.exclude(id__in=reviewed_media_ids)

            if level == 'fast':
                # Restrict to species that have < 10 approved media (and at least one unreviewed)
                unreviewed_species_ids = list(
                    queryset.values_list('species_id', flat=True).distinct()
                )
                if not unreviewed_species_ids:
                    return Media.objects.none().order_by('species__id', '-created')
                species_under_10 = list(
                    Species.objects.filter(id__in=unreviewed_species_ids)
                    .filter(media__type=media_type)
                    .annotate(
                        approved_count=Count(
                            'media',
                            filter=Q(media__type=media_type, media__reviews__review_type='approved'),
                            distinct=True,
                        ),
                    )
                    .filter(approved_count__lt=10)
                    .values_list('id', flat=True)
                )
                queryset = queryset.filter(species_id__in=species_under_10)
            # full: no extra filter

        return queryset.order_by('species__id', '-created')


class ReviewMediaView(ListCreateAPIView):
    """View for reviewing media items (positive or negative). Accepts player_token in body or authenticated user."""
    permission_classes = [AllowAny]
    serializer_class = ReviewMediaSerializer
    queryset = MediaReview.objects.all()


class FirstAssertionReviewView(CreateAPIView):
    """First assertion for image media only: approved or rejected. Same auth as ReviewMediaView."""

    permission_classes = [AllowAny]
    serializer_class = FirstAssertionReviewSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        out = MediaReviewBriefSerializer(review, context={'request': request})
        return Response(out.data, status=status.HTTP_201_CREATED)


class FlagMediaView(ListCreateAPIView):
    """View for flagging media items."""
    serializer_class = FlagMediaSerializer
    queryset = FlagMedia.objects.all()


class SpeciesReviewStatsView(APIView):
    """List species with media review counts; optional country filter. Returns summary counts (fully/partly/not reviewed)."""
    permission_classes = [AllowAny]

    def get(self, request):
        country_code = request.query_params.get('country')
        media_type = request.query_params.get('type', 'image')

        qs = (
            Species.objects
            .filter(media__type=media_type)
            .distinct()
            .annotate(
                total_media=Count('media', filter=Q(media__type=media_type), distinct=True),
                media_with_review=Count(
                    'media',
                    filter=Q(media__type=media_type, media__reviews__id__isnull=False),
                    distinct=True,
                ),
                approved_media=Count(
                    'media',
                    filter=Q(media__type=media_type, media__reviews__review_type='approved'),
                    distinct=True,
                ),
                rejected_media=Count(
                    'media',
                    filter=Q(media__type=media_type, media__reviews__review_type='rejected'),
                    distinct=True,
                ),
                not_sure_media=Count(
                    'media',
                    filter=Q(media__type=media_type, media__reviews__review_type='not_sure'),
                    distinct=True,
                ),
            )
            .filter(total_media__gt=0)
            .order_by('id')
        )
        if country_code:
            qs = qs.filter(
                countryspecies__country__code=country_code.upper(),
                countryspecies__status__in=['native', 'endemic', 'rare'],
            ).distinct()

        species_list = list(qs)
        total_species = len(species_list)
        not_reviewed = sum(1 for s in species_list if s.media_with_review == 0)
        fully_reviewed = sum(1 for s in species_list if s.media_with_review >= s.total_media)
        # reviewed = at least 10 approved, or fully reviewed
        reviewed = sum(
            1 for s in species_list
            if s.approved_media >= 10 or s.media_with_review >= s.total_media
        )
        # partly_reviewed = has some reviews but < 10 approved and not fully reviewed
        partly_reviewed = sum(
            1 for s in species_list
            if 0 < s.media_with_review < s.total_media and s.approved_media < 10
        )

        serializer = SpeciesReviewStatsSerializer(
            species_list,
            many=True,
            context={'request': request},
        )
        return Response({
            'summary': {
                'total_species': total_species,
                'not_reviewed': not_reviewed,
                'partly_reviewed': partly_reviewed,
                'reviewed': reviewed,
                'fully_reviewed': fully_reviewed,
            },
            'species': serializer.data,
        })


class MediaReviewSpeciesListView(APIView):
    """List species for media review with all media embedded. Paginated by species (default 3 per page).
    Filter: country, type, level (fast=species with <10 approved), optional species id.
    """
    permission_classes = [AllowAny]
    pagination_class = SpeciesReviewPagination

    def get(self, request):
        from jizz.models import CountrySpecies

        level = request.query_params.get('level', 'fast')
        media_type = request.query_params.get('type', 'image')
        country_code = request.query_params.get('country')
        species_id_param = request.query_params.get('species')

        qs = (
            Species.objects
            .filter(media__type=media_type)
            .distinct()
            .annotate(
                total_media=Count('media', filter=Q(media__type=media_type), distinct=True),
                media_with_review=Count(
                    'media',
                    filter=Q(media__type=media_type, media__reviews__id__isnull=False),
                    distinct=True,
                ),
                approved_media=Count(
                    'media',
                    filter=Q(media__type=media_type, media__reviews__review_type='approved'),
                    distinct=True,
                ),
                rejected_media=Count(
                    'media',
                    filter=Q(media__type=media_type, media__reviews__review_type='rejected'),
                    distinct=True,
                ),
                not_sure_media=Count(
                    'media',
                    filter=Q(media__type=media_type, media__reviews__review_type='not_sure'),
                    distinct=True,
                ),
            )
            .filter(total_media__gt=0)
            .order_by('id')
        )
        if country_code:
            country_species_ids = CountrySpecies.objects.exclude(
                status__in=['introduced', 'extirpated', 'uncertain', 'unknown']
            ).filter(country__code=country_code.upper()).values_list('species_id', flat=True)
            qs = qs.filter(id__in=country_species_ids)
        if species_id_param:
            try:
                qs = qs.filter(id=int(species_id_param))
            except (ValueError, TypeError):
                pass

        if level == 'fast':
            qs = qs.filter(approved_media__lt=10, media_with_review__lt=F('total_media'))
        elif level == 'full':
            qs = qs.filter(media_with_review__lt=F('total_media'))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is None:
            return paginator.get_paginated_response([])

        species_ids = [s.id for s in page]
        media_qs = (
            Media.objects
            .filter(species_id__in=species_ids, type=media_type, hide=False)
            .prefetch_related('reviews')
            .select_related('first_assertion_prediction')
            .order_by('species_id', '-created')
        )
        media_by_species = {}
        for m in media_qs:
            media_by_species.setdefault(m.species_id, []).append(m)

        results = []
        for s in page:
            media_list = media_by_species.get(s.id, [])
            unreviewed = s.total_media - s.media_with_review
            results.append({
                'species': s,
                'total_media': s.total_media,
                'unreviewed': unreviewed,
                'approved': s.approved_media,
                'rejected': s.rejected_media,
                'not_sure': s.not_sure_media,
                'media': media_list,
            })
        serializer = SpeciesWithMediaReviewSerializer(
            results, many=True, context={'request': request}
        )
        return paginator.get_paginated_response(serializer.data)


class GameListView(ListCreateAPIView, GetPlayerMixin):
    serializer_class = GameSerializer
    queryset = Game.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["country"]

    def perform_create(self, serializer):
        player = self.get_player_from_request(self.request)
        game = serializer.save(host=player)
        from jizz.client_info import record_player_score_client_from_request

        record_player_score_client_from_request(player, game, self.request)


class GameDetailView(RetrieveUpdateAPIView):
    serializer_class = GameSerializer
    queryset = Game.objects.all()
    lookup_field = "token"
    permission_classes = [AllowAny]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return GameLanguageSerializer
        return GameSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = GameLanguageSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(GameSerializer(instance, context=self.get_serializer_context()).data)


class NoSpeciesForGame(APIException):
    status_code = 422
    default_detail = 'No species available for this country and game settings.'
    default_code = 'no_species'


class QuestionView(RetrieveAPIView):
    serializer_class = QuestionPlaySerializer
    queryset = Question.objects.all()
    permission_classes = [AllowAny]

    def get_object(self):
        game = Game.objects.get(token=self.kwargs["token"])
        if game.ended:
            raise NotFound("Game has ended")
        # Ensure we see latest state (e.g. after a previous request marked question done)
        game.refresh_from_db()
        try:
            if not game.question:
                if game.multiplayer and not game.questions.exists():
                    raise NotFound("Game has not started")
                game.add_question()
        except ValueError:
            raise NoSpeciesForGame(
                detail=(
                    f'No birds available for {game.country_id} with these step settings. '
                    'In admin, set rarity to Regular, clear taxonomic order, '
                    'or enable include escapes.'
                )
            )
        from jizz.question_play import build_play_serializer_context, load_question_for_play

        question = load_question_for_play(game.question.id)
        self._play_serializer_context = build_play_serializer_context(question)
        return question

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        extra = getattr(self, '_play_serializer_context', None)
        if extra:
            ctx.update(extra)
        return ctx


def _stop_game_if_jokers_exhausted(game):
    """End Birdr Journey games after a wrong answer uses the last joker."""
    from jizz.models import BirdrJourneyGame

    for link in BirdrJourneyGame.objects.filter(game=game).select_related('journey_step'):
        if link.remaining_jokers < 0:
            if not game.force_ended:
                game.force_ended = True
                game.save(update_fields=['force_ended'])
            return True
    return False


class AnswerView(CreateAPIView):
    serializer_class = AnswerSerializer
    queryset = Answer.objects.all()
    permission_classes = [AllowAny]
    # Player token before JWT: guests send Bearer <player.token>; JWT would reject that UUID as invalid.
    # Logged-in clients send a JWT; PlayerToken misses, then JWT authenticates for checklist_added.
    authentication_classes = [PlayerTokenAuthentication, JWTAuthentication]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['include_media_link'] = True
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        data = dict(serializer.data)
        if serializer.instance is not None:
            data['checklist_added'] = bool(
                getattr(serializer.instance, 'checklist_added', False)
            )
            data['checklist_missed'] = bool(
                getattr(serializer.instance, 'checklist_missed', False)
            )
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        answer = serializer.save()
        answer.question.done = True
        answer.question.save()
        game = answer.question.game
        if not answer.correct and _stop_game_if_jokers_exhausted(game):
            return
        game.add_question()


class AnswerDetail(RetrieveAPIView):
    serializer_class = AnswerSerializer
    queryset = Answer.objects.all()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['include_media_link'] = True
        return ctx

    def get_object(self):
        return self.queryset.filter(
            player_score__player__token=self.kwargs["token"], question=self.kwargs["question"]
        ).first()


class QuestionMediaReadyView(APIView):
    """POST when client has finished loading primary media; server records time for score calculation."""

    permission_classes = [AllowAny]

    def post(self, request, pk):
        from django.utils import timezone

        player_token = request.data.get('player_token')
        if not player_token:
            return Response({'error': 'player_token required'}, status=400)
        question = get_object_or_404(Question, pk=pk)
        player = get_object_or_404(Player, token=player_token)
        if not PlayerScore.objects.filter(player=player, game=question.game).exists():
            return Response({'error': 'Player is not in this game'}, status=403)
        ts = timezone.now()
        QuestionMediaReady.objects.update_or_create(
            player=player,
            question=question,
            defaults={'ready_at': ts},
        )
        return Response({'ok': True, 'ready_at': ts.isoformat()})


class QuestionNextMediaView(APIView):
    """POST after flagging media: advance to next eligible image/video/sound for this question."""

    permission_classes = [AllowAny]

    def post(self, request, pk):
        from jizz.question_play import (
            advance_question_media_after_exclusion,
            load_question_for_play,
            serialize_question_for_play,
        )

        player_token = request.data.get('player_token')
        if not player_token:
            return Response({'error': 'player_token required'}, status=400)
        question = get_object_or_404(Question, pk=pk)
        player = get_object_or_404(Player, token=player_token)
        if not PlayerScore.objects.filter(player=player, game=question.game).exists():
            return Response({'error': 'Player is not in this game'}, status=403)

        excluded = request.data.get('excluded_media_id')
        if excluded is not None:
            try:
                excluded = int(excluded)
            except (TypeError, ValueError):
                return Response({'error': 'invalid excluded_media_id'}, status=400)

        updated = advance_question_media_after_exclusion(question, excluded)
        if not updated:
            return Response({'error': 'no_alternate_media'}, status=409)

        loaded = load_question_for_play(updated.id)
        data = serialize_question_for_play(loaded)
        # After rotation, return only the new active clip (index 0), not the full list.
        return Response(
            {
                'number': data['number'],
                'images': data['images'][:1],
                'videos': data['videos'][:1],
                'sounds': data['sounds'][:1],
            }
        )


class QuestionDetailView(RetrieveUpdateAPIView):
    serializer_class = QuestionSerializer
    queryset = Question.objects.all()


class PlayerScorePagination(PageNumberPagination):
    page_size = 100


class PlayerScoreListView(ListAPIView):
    serializer_class = PlayerScoreListSerializer
    pagination_class = PlayerScorePagination

    filterset_fields = ["game__media", "game__length", "game__level", "game__country", "game__rarity"]
    filter_backends = [DjangoFilterBackend, OrderingFilter]

    ordering = ["-score"]

    def get_queryset(self):
        return (
            PlayerScore.objects
            .filter(Q(game__tax_order='') | Q(game__tax_order__isnull=True))
            .filter(Q(game__tax_family='') | Q(game__tax_family__isnull=True))
            .filter(Q(game__species_group='') | Q(game__species_group__isnull=True))
            .exclude(game__game_type__in=[
                Game.GAME_TYPE_PAIR_PRACTICE,
                Game.GAME_TYPE_SPECIES_PRACTICE,
            ])
            .select_related("player", "game", "game__country")
            .annotate(
                score_rank=Window(
                    expression=RowNumber(),
                    order_by=F("score").desc(),
                )
            )
        )


class FeedbackListView(ListCreateAPIView):
    serializer_class = FeedbackSerializer
    queryset = Feedback.objects.select_related('user', 'player').all()
    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]


class UpdatePagination(PageNumberPagination):
    page_size = 10


class CustomConvertTokenView(ConvertTokenView):

    def post(self, request, *args, **kwargs):
        # Call the original ConvertTokenView to get the OAuth2 token
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Get the user from the OAuth2 access token
            user = request.user

            # Generate a JWT token
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "expires_in": 3600,  # Customize expiry
                }
            )
        return response


class GoogleLoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response({"error": "Missing token"}, status=400)

        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests

            # Primary: Web client ID (same as app's GOOGLE_WEB_CLIENT_ID). Optional: extra IDs (e.g. iOS) to accept.
            primary_key = (
                getattr(settings, "SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", None) or ""
            ).strip()
            extra_ids = getattr(settings, "SOCIAL_AUTH_GOOGLE_OAUTH2_ADDITIONAL_AUDIENCE", None) or []
            if isinstance(extra_ids, str):
                extra_ids = [e.strip() for e in extra_ids.split(",") if e.strip()]
            allowed_client_ids = [primary_key] + [a for a in extra_ids if a and a != primary_key]

            if not primary_key or primary_key.startswith("<") or "your-" in primary_key.lower():
                logger.warning(
                    "Google login: SOCIAL_AUTH_GOOGLE_OAUTH2_KEY not set or placeholder. "
                    "Set it to your Google Cloud Web application client ID (same as app's GOOGLE_WEB_CLIENT_ID)."
                )
                return Response(
                    {"error": "Invalid token", "message": "Server Google client ID not configured"},
                    status=400,
                )

            idinfo = None
            for cid in allowed_client_ids:
                if not cid:
                    continue
                try:
                    idinfo = id_token.verify_oauth2_token(
                        token, google_requests.Request(), cid
                    )
                    break
                except ValueError:
                    continue
            if idinfo is None:
                logger.warning(
                    "Google login: token verification failed for all client IDs. "
                    "Ensure SOCIAL_AUTH_GOOGLE_OAUTH2_KEY matches the app Web client ID."
                )
                return Response(
                    {"error": "Invalid token", "message": "Token verification failed (wrong client ID or expired)"},
                    status=400,
                )
            if idinfo.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
                raise ValueError("Wrong issuer")

            email = idinfo.get("email")
            if not email:
                raise ValueError("No email in token")

            def _username_from_google(idinfo, email, exclude_user_id=None):
                from jizz.user_names import username_from_oauth

                full = (idinfo.get("name") or "").strip()
                given = (idinfo.get("given_name") or "").strip()
                family = (idinfo.get("family_name") or "").strip()
                return username_from_oauth(
                    first_name=given,
                    last_name=family,
                    full_name=full,
                    email=email,
                    exclude_user_id=exclude_user_id,
                )

            def _username_needs_oauth_fix(user, email):
                username = (user.username or "").strip()
                if not username:
                    return True
                if username.lower() == (email or "").lower():
                    return True
                return '@' in username

            users = User.objects.filter(email__iexact=email).order_by("id")
            if users.count() == 0:
                username = _username_from_google(idinfo, email)
                user = User.objects.create_user(username=username, email=email)
                if idinfo.get("given_name"):
                    user.first_name = idinfo.get("given_name", "")[:150]
                if idinfo.get("family_name"):
                    user.last_name = idinfo.get("family_name", "")[:150]
                user.save()
                created = True
            elif users.count() == 1:
                user = users.get()
                created = False
                if _username_needs_oauth_fix(user, email):
                    user.username = _username_from_google(idinfo, email, exclude_user_id=user.pk)
                    if idinfo.get("given_name"):
                        user.first_name = idinfo.get("given_name", "")[:150]
                    if idinfo.get("family_name"):
                        user.last_name = idinfo.get("family_name", "")[:150]
                    user.save()
            else:
                # Multiple users with same email (e.g. legacy data): use the first by id
                logger.warning(
                    "Google login: multiple users with email %s (ids %s). Using first.",
                    email,
                    list(users.values_list("id", flat=True)),
                )
                user = users.first()
                created = False
                if _username_needs_oauth_fix(user, email):
                    user.username = _username_from_google(idinfo, email, exclude_user_id=user.pk)
                    if idinfo.get("given_name"):
                        user.first_name = idinfo.get("given_name", "")[:150]
                    if idinfo.get("family_name"):
                        user.last_name = idinfo.get("family_name", "")[:150]
                    user.save()

            # Get or create profile and save Google avatar if user doesn't have one yet
            profile, _ = UserProfile.objects.get_or_create(
                user=user, defaults={}
            )
            picture_url = idinfo.get("picture")
            if picture_url and not profile.avatar:
                try:
                    import requests
                    from django.core.files.base import ContentFile
                    from urllib.parse import urlparse
                    import os

                    response = requests.get(picture_url, timeout=10)
                    if response.status_code == 200:
                        parsed_url = urlparse(picture_url)
                        ext = os.path.splitext(parsed_url.path)[1] or ".jpg"
                        filename = f"avatar_{user.id}{ext}"
                        profile.avatar.save(
                            filename,
                            ContentFile(response.content),
                            save=True,
                        )
                except Exception as e:
                    logger.warning("Failed to save Google avatar for user %s: %s", user.id, e)

            refresh = RefreshToken.for_user(user)
            return Response(
                {"refresh": str(refresh), "access": str(refresh.access_token)}
            )

        except ValueError as e:
            logger.warning("Google login invalid token: %s", e)
            return Response({"error": "Invalid token"}, status=400)
        except Exception as e:
            logger.exception("Google login error: %s", e)
            return Response({"error": "Invalid token"}, status=400)

    def dispatch(self, request, *args, **kwargs):
        """Catch any uncaught exception so we always log 500s to console."""
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            logger.exception("GoogleLoginView 500: %s", e)
            raise


def _validate_apple_identity_token(identity_token):
    """
    Verify Apple Sign In identity_token (JWT) using Apple's public keys.
    Returns decoded payload with sub, email (optional), email_verified.

    Accepts both:
    - Web/Services ID (SOCIAL_AUTH_APPLE_ID_CLIENT) for browser OAuth
    - Native bundle ID (SOCIAL_AUTH_APPLE_ID_BUNDLE_ID or pro.birdr.app) for iOS app
    """
    import jwt
    import requests
    from django.conf import settings

    client_id = getattr(
        settings, "SOCIAL_AUTH_APPLE_ID_CLIENT", None
    ) or getattr(settings, "SOCIAL_AUTH_APPLE_ID_SERVICES_ID", None)
    if not client_id:
        raise ValueError("SOCIAL_AUTH_APPLE_ID_CLIENT not configured")

    # Native iOS sends bundle ID as audience; web sends Services ID. Accept both.
    allowed_audiences = [client_id]
    bundle_id = getattr(settings, "SOCIAL_AUTH_APPLE_ID_BUNDLE_ID", None) or "pro.birdr.app"
    if bundle_id and bundle_id not in allowed_audiences:
        allowed_audiences.append(bundle_id)

    unverified = jwt.get_unverified_header(identity_token)
    kid = unverified.get("kid")
    if not kid:
        raise ValueError("Token header missing kid")

    resp = requests.get("https://appleid.apple.com/auth/keys", timeout=10)
    resp.raise_for_status()
    keys = resp.json().get("keys", [])
    jwk = next((k for k in keys if k.get("kid") == kid), None)
    if not jwk:
        raise ValueError("Apple key not found for kid")

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
    payload = jwt.decode(
        identity_token,
        public_key,
        algorithms=["RS256"],
        issuer="https://appleid.apple.com",
        audience=allowed_audiences,
    )
    return payload


class AppleLoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        identity_token = request.data.get("identity_token") or request.data.get("token")
        user_data = request.data.get("user")  # Optional: { "name": { "firstName", "lastName" }, "email" } on first sign-in

        if not identity_token:
            return Response({"error": "identity_token required"}, status=400)

        try:
            payload = _validate_apple_identity_token(identity_token)
        except Exception as e:
            return Response({"error": "Invalid token"}, status=400)

        sub = payload.get("sub")
        email = payload.get("email")
        if not email and isinstance(user_data, dict):
            ed = user_data.get("email")
            email = ed if isinstance(ed, str) and ed.strip() else None
        if not sub:
            return Response({"error": "Invalid token"}, status=400)

        # Optional name from native client (only sent on first sign-in)
        name_obj = (user_data or {}).get("name") if isinstance(user_data, dict) else None
        first_name = ""
        last_name = ""
        if isinstance(name_obj, dict):
            first_name = (name_obj.get("firstName") or "").strip() if name_obj.get("firstName") is not None else ""
            last_name = (name_obj.get("lastName") or "").strip() if name_obj.get("lastName") is not None else ""
            # Never store the literal string "null"
            if first_name == "null":
                first_name = ""
            if last_name == "null":
                last_name = ""

        from social_django.models import UserSocialAuth
        from jizz.user_names import username_from_oauth

        def _username_from_apple(exclude_user_id=None):
            return username_from_oauth(
                first_name=first_name,
                last_name=last_name,
                email=email or '',
                exclude_user_id=exclude_user_id,
            )

        def _username_needs_oauth_fix(user, user_email):
            username = (user.username or '').strip()
            if not username:
                return True
            if user_email and username.lower() == user_email.lower():
                return True
            return '@' in username

        social = UserSocialAuth.objects.filter(provider="apple-id", uid=sub).first()
        if social:
            user = social.user
            # Update name/email from client if we have them and user doesn't
            if first_name or last_name:
                if first_name and not user.first_name:
                    user.first_name = first_name
                if last_name and not user.last_name:
                    user.last_name = last_name
                user.save(update_fields=["first_name", "last_name"])
            if email and not (user.email or "").strip():
                user.email = email
                user.save(update_fields=["email"])
            if _username_needs_oauth_fix(user, email or user.email):
                user.username = _username_from_apple(exclude_user_id=user.pk)
                user.save(update_fields=["username"])
        else:
            # First-time Apple sign-in: create or link user
            if email:
                username = _username_from_apple()
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                    },
                )
                if not created and (first_name or last_name):
                    if first_name and not user.first_name:
                        user.first_name = first_name
                    if last_name and not user.last_name:
                        user.last_name = last_name
                    user.save(update_fields=["first_name", "last_name"])
                if not created and _username_needs_oauth_fix(user, email):
                    user.username = _username_from_apple(exclude_user_id=user.pk)
                    user.save(update_fields=["username"])
            else:
                # Apple may hide email; use sub as unique username (never "null")
                username = f"apple_{sub}"
                if len(username) > 150:
                    username = username[:150]
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1
                user = User.objects.create(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                )

            UserSocialAuth.objects.get_or_create(
                provider="apple-id",
                uid=sub,
                defaults={"user": user, "extra_data": {}},
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {"refresh": str(refresh), "access": str(refresh.access_token)}
        )


class OAuthCompleteView(APIView):
    """
    Custom OAuth completion view that generates JWT tokens and redirects to frontend
    This intercepts the OAuth callback and adds JWT tokens to the redirect URL
    """
    def get(self, request, backend):
        from django.conf import settings
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        # Get the redirect URI from session (stored during OAuth initiation) or request or use default
        redirect_uri = request.session.get('social_auth_redirect_uri') or request.GET.get('redirect_uri') or settings.SOCIAL_AUTH_LOGIN_REDIRECT_URL
        # Apple: we stored the app callback (birdr://) separately; redirect user there with tokens
        if request.session.get('social_auth_app_callback'):
            redirect_uri = request.session['social_auth_app_callback']
        
        # Call the social_django complete view to finish OAuth
        # This will authenticate the user and create/update the social auth association
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"OAuthCompleteView called for backend: {backend}")
            logger.info(f"Before social_complete: user authenticated={request.user.is_authenticated}")
            
            response = social_complete(request, backend)
            
            user_after = request.user if request.user.is_authenticated else None
            logger.info(f"After social_complete: user authenticated={request.user.is_authenticated}, user_id={user_after.id if user_after else None}")
            
        except Exception as e:
            logger.error(f"OAuth completion failed: {e}", exc_info=True)
            # If OAuth completion failed, redirect with error
            if 'social_auth_app_callback' in request.session:
                del request.session['social_auth_app_callback']
            parsed = urlparse(redirect_uri)
            query_params = parse_qs(parsed.query)
            query_params['error'] = ['authentication_failed']
            new_query = urlencode(query_params, doseq=True)
            new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
            if parsed.scheme and parsed.scheme not in ('http', 'https'):
                return HttpResponse(status=302, headers={'Location': new_url})
            return redirect(new_url)
        
        # If OAuth was successful, the user should now be authenticated
        if request.user.is_authenticated:
            logger.info(f"OAuth successful for user: {request.user.username} (ID: {request.user.id}, email: {getattr(request.user, 'email', 'N/A')})")
            
            # Get or create user profile
            from .models import UserProfile
            profile, profile_created = UserProfile.objects.get_or_create(user=request.user)
            logger.info(f"UserProfile {'created' if profile_created else 'retrieved'} for user {request.user.id}")
            
            # Get social auth data - try multiple sources
            extra_data = None
            social_user = None
            
            # First, try to get from session (social_django stores it there during OAuth)
            if 'social_auth' in request.session:
                social_auth_data = request.session.get('social_auth', {})
                if isinstance(social_auth_data, dict):
                    extra_data = social_auth_data.get('user_details', {})
                    logger.info(f"Found user data in session: {list(extra_data.keys()) if extra_data else 'None'}")
            
            # Also try to get from UserSocialAuth model (might be saved by now)
            try:
                from social_django.models import UserSocialAuth
                # Refresh from database - might have been created by social_complete
                social_user = UserSocialAuth.objects.filter(user=request.user, provider=backend).first()
                if social_user and social_user.extra_data:
                    extra_data = social_user.extra_data
                    logger.info(f"Found user data in UserSocialAuth: {list(extra_data.keys()) if extra_data else 'None'}")
            except Exception as e:
                logger.warning(f"Error accessing UserSocialAuth: {e}")
            
            # Only fetch user details from Google API when this is Google OAuth (not Apple)
            if backend == 'google-oauth2' and social_user and social_user.extra_data and 'access_token' in social_user.extra_data:
                access_token = social_user.extra_data.get('access_token')
                if access_token and not extra_data.get('name') and not extra_data.get('picture'):
                    try:
                        import requests
                        google_user_info_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
                        headers = {'Authorization': f'Bearer {access_token}'}
                        response = requests.get(google_user_info_url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            google_data = response.json()
                            extra_data.update(google_data)
                            social_user.extra_data.update(google_data)
                            social_user.save()
                    except Exception as e:
                        logger.warning(f"Error fetching user details from Google API: {e}")
            
            # Update user profile from social data (Google or Apple extra_data)
            if extra_data:
                logger.info(f"Updating user profile with {backend} data: {list(extra_data.keys())}")
                
                # Update first_name and last_name first
                updated = False
                if 'given_name' in extra_data and extra_data.get('given_name'):
                    request.user.first_name = extra_data.get('given_name', '')
                    updated = True
                if 'family_name' in extra_data and extra_data.get('family_name'):
                    request.user.last_name = extra_data.get('family_name', '')
                    updated = True
                if 'name' in extra_data and extra_data.get('name') and not request.user.first_name:
                    # If we have full name but no first_name, try to split it
                    full_name = extra_data.get('name', '').split(' ', 1)
                    if len(full_name) > 0:
                        request.user.first_name = full_name[0]
                        updated = True
                    if len(full_name) > 1:
                        request.user.last_name = full_name[1]
                        updated = True
                
                # Set username to full name (first_name + last_name) with spaces allowed
                # Build full name from first_name and last_name
                full_name_parts = []
                if request.user.first_name:
                    full_name_parts.append(request.user.first_name.strip())
                if request.user.last_name:
                    full_name_parts.append(request.user.last_name.strip())
                
                # Fallback: if we don't have first_name/last_name but have the full name, use it
                if not full_name_parts and 'name' in extra_data and extra_data.get('name'):
                    full_name = extra_data.get('name', '').strip()
                    if full_name:
                        full_name_parts = [full_name]
                
                if full_name_parts:
                    from jizz.user_names import make_unique_username, sanitize_username

                    expected_username = sanitize_username(' '.join(full_name_parts))
                    current_username = request.user.username
                    should_update = (
                        current_username == request.user.email or
                        '@' in current_username or
                        current_username != expected_username
                    )

                    if should_update:
                        username = make_unique_username(
                            expected_username,
                            exclude_user_id=request.user.pk,
                        )
                        request.user.username = username
                        updated = True
                        logger.info(
                            "Updated username from '%s' to '%s' (from full name: %s)",
                            current_username,
                            username,
                            expected_username,
                        )
                
                if updated:
                    request.user.save()
                    logger.info(f"Updated user name: {request.user.first_name} {request.user.last_name}, username: {request.user.username}")
                
                # Download and save avatar if available and user doesn't have one yet
                if 'picture' in extra_data and extra_data['picture'] and not profile.avatar:
                    try:
                        import requests
                        from django.core.files.base import ContentFile
                        from django.core.files.storage import default_storage
                        import os
                        from urllib.parse import urlparse
                        
                        avatar_url = extra_data['picture']
                        response = requests.get(avatar_url, timeout=10)
                        if response.status_code == 200:
                            parsed_url = urlparse(avatar_url)
                            ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
                            filename = f"avatar_{request.user.id}{ext}"
                            
                            profile.avatar.save(
                                filename,
                                ContentFile(response.content),
                                save=True
                            )
                    except Exception as e:
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to download avatar for user {request.user.id}: {e}")
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(request.user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            # Clear the redirect URI from session
            if 'social_auth_redirect_uri' in request.session:
                del request.session['social_auth_redirect_uri']
            if 'social_auth_app_callback' in request.session:
                del request.session['social_auth_app_callback']
            
            # Redirect to frontend with tokens in URL
            parsed = urlparse(redirect_uri)
            query_params = parse_qs(parsed.query)
            query_params['access_token'] = [access_token]
            query_params['refresh_token'] = [refresh_token]
            new_query = urlencode(query_params, doseq=True)
            new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

            # Django's redirect() disallows non-http(s) schemes; use 302 + Location for app deep link (e.g. birdr://)
            if parsed.scheme and parsed.scheme not in ('http', 'https'):
                return HttpResponse(status=302, headers={'Location': new_url})
            return redirect(new_url)
        
        # If authentication failed, redirect with error
        parsed = urlparse(redirect_uri)
        query_params = parse_qs(parsed.query)
        query_params['error'] = ['authentication_failed']
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        
        # Django's redirect() disallows non-http(s) schemes; use 302 + Location for app deep link (e.g. birdr://)
        if parsed.scheme and parsed.scheme not in ('http', 'https'):
            return HttpResponse(status=302, headers={'Location': new_url})
        return redirect(new_url)


class ReactionView(CreateAPIView):
    serializer_class = ReactionSerializer
    queryset = Reaction.objects.all()


class RegisterView(APIView):
    """
    User registration endpoint
    Creates a new user and returns JWT tokens
    """
    def post(self, request):
        from .serializers import UserRegistrationSerializer
        from .models import UserProfile

        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                # Create user profile
                UserProfile.objects.get_or_create(user=user)
                
                # Send welcome email
                frontend_url = request.data.get('frontend_url', request.build_absolute_uri('/').rstrip('/'))
                if 'localhost' in frontend_url or '127.0.0.1' in frontend_url:
                    frontend_url = 'http://localhost:3000'
                from jizz.notifications import send_welcome_email
                send_welcome_email(user, site_url=frontend_url)
                
                refresh = RefreshToken.for_user(user)
                return Response({
                    "access": str(refresh.access_token),
                    "refresh": str(refresh)
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                # Handle duplicate username/email errors
                if 'username' in str(e).lower() or 'unique' in str(e).lower():
                    return Response(
                        {"error": "Username already exists. Please choose a different username."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                elif 'email' in str(e).lower():
                    return Response(
                        {"error": "Email already exists. Please use a different email or login."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return Response(
                    {"error": "Registration failed. Please try again."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Format validation errors for frontend
        error_messages = []
        for field, errors in serializer.errors.items():
            if isinstance(errors, list):
                error_messages.extend([f"{field}: {error}" for error in errors])
            else:
                error_messages.append(f"{field}: {errors}")
        
        return Response(
            {"error": "; ".join(error_messages) if error_messages else "Invalid registration data"},
            status=status.HTTP_400_BAD_REQUEST
        )


def _set_no_cache_headers(response):
    """Per-user data must not be stored by browsers or intermediaries."""
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


class UserGamesView(ListAPIView):
    """
    Get paginated list of games played by the authenticated user
    """
    from rest_framework.permissions import IsAuthenticated
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from .serializers import UserGameSerializer
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = UserGameSerializer
    pagination_class = PageNumberPagination

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return _set_no_cache_headers(response)
    
    def get_queryset(self):
        user_players = Player.objects.filter(user=self.request.user)
        user_player_scores = PlayerScore.objects.filter(player__in=user_players)
        games = Game.objects.filter(
            questions__answers__player_score__in=user_player_scores
        ).distinct().select_related(
            'country'
        ).prefetch_related(
            'questions'
        ).order_by('-created')
        
        return games
    
    def get_serializer_context(self):
        """Add request to serializer context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class UserGameDetailView(RetrieveAPIView):
    """
    Get game details with all questions and user's answers
    """
    from rest_framework.permissions import IsAuthenticated
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from .serializers import GameDetailWithAnswersSerializer
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = GameDetailWithAnswersSerializer
    lookup_field = "token"

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return _set_no_cache_headers(response)
    
    def get_queryset(self):
        user_players = Player.objects.filter(user=self.request.user)
        user_player_scores = PlayerScore.objects.filter(player__in=user_players)
        game =  Game.objects.filter(
            questions__answers__player_score__in=user_player_scores
        ).distinct().prefetch_related(
            Prefetch(
                'questions',
                queryset=Question.objects.order_by('sequence').select_related('species').prefetch_related(
                    'species__media',
                    Prefetch(
                        'media_ready',
                        queryset=QuestionMediaReady.objects.select_related('player'),
                    ),
                    Prefetch(
                        'answers',
                        queryset=Answer.objects.filter(
                            player_score__in=user_player_scores
                        ).select_related('answer', 'player_score', 'player_score__player', 'player_score__player__user').prefetch_related(
                            'answer__media'
                        )
                    )
                )
            )
        )
        return game
    
    def get_serializer_context(self):
        """Add request to serializer context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class GameDetailWithAnswersByPlayerTokenView(RetrieveAPIView):
    """
    Same JSON as GET /api/my-games/<token>/ for guests: ?player_token=<player token>.
    Player must have a score row for this game (same secret as WebSocket join_game).
    """

    from .serializers import GameDetailWithAnswersSerializer

    permission_classes = [AllowAny]
    serializer_class = GameDetailWithAnswersSerializer
    lookup_field = "token"

    def retrieve(self, request, *args, **kwargs):
        if not (request.query_params.get("player_token") or "").strip():
            return Response(
                {"detail": "player_token query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = super().retrieve(request, *args, **kwargs)
        return _set_no_cache_headers(response)

    def get_queryset(self):
        player_token = (self.request.query_params.get("player_token") or "").strip()
        self._detail_player_for_context = None
        if not player_token:
            return Game.objects.none()
        player = Player.objects.filter(token=player_token).first()
        if not player:
            return Game.objects.none()

        self._detail_player_for_context = player
        user_player_scores = PlayerScore.objects.filter(player=player)
        return (
            Game.objects.filter(
                token=self.kwargs["token"],
                questions__answers__player_score__in=user_player_scores,
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "questions",
                    queryset=Question.objects.order_by("sequence")
                    .select_related("species")
                    .prefetch_related(
                        "species__media",
                        Prefetch(
                            "media_ready",
                            queryset=QuestionMediaReady.objects.select_related("player"),
                        ),
                        Prefetch(
                            "answers",
                            queryset=Answer.objects.filter(
                                player_score__in=user_player_scores
                            )
                            .select_related(
                                "answer",
                                "player_score",
                                "player_score__player",
                            )
                            .prefetch_related("answer__media"),
                        ),
                    ),
                )
            )
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        player = getattr(self, "_detail_player_for_context", None)
        if player is not None:
            context["detail_player"] = player
        return context


class ProfileView(APIView):
    """
    Get and update user profile
    """
    from rest_framework.permissions import IsAuthenticated
    from rest_framework_simplejwt.authentication import JWTAuthentication
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from .serializers import UserProfileSerializer
        from .models import UserProfile
        
        # The IsAuthenticated permission will handle authentication
        # If we reach here, the user is authenticated
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)
    
    def put(self, request):
        from .serializers import UserProfileUpdateSerializer
        from .models import UserProfile
        
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Handle avatar removal (empty string means remove)
        data = request.data.copy()
        if 'avatar' in data and data['avatar'] == '':
            data['avatar'] = None
        
        serializer = UserProfileUpdateSerializer(profile, data=data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            # Refresh profile from database
            profile.refresh_from_db()
            # Return updated profile
            from .serializers import UserProfileSerializer
            profile_serializer = UserProfileSerializer(profile, context={'request': request})
            return Response(profile_serializer.data)
        
        # Format validation errors
        error_messages = []
        for field, errors in serializer.errors.items():
            if isinstance(errors, list):
                error_messages.extend([f"{field}: {error}" for error in errors])
            else:
                error_messages.append(f"{field}: {errors}")
        
        return Response(
            {"error": "; ".join(error_messages) if error_messages else "Invalid profile data"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request):
        """
        Delete the authenticated user's account.
        Unlinks all players (and their scores/games) from the user so that data is kept;
        then deletes the user and related profile/social data.
        """
        from .models import Player

        # Unlink all players from this user so player/scores/games are preserved
        Player.objects.filter(user=request.user).update(user=None)
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    """
    Request password reset - sends email with reset link
    """
    def post(self, request):
        from .serializers import PasswordResetRequestSerializer
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.conf import settings
        import html2text
        
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                # Generate token
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Create reset URL
                frontend_url = request.data.get('frontend_url', 'http://localhost:3000')
                reset_url = f"{frontend_url}/reset-password/{uid}/{token}/"
                
                # Send HTML email
                try:
                    subject = 'Reset Your Birdr Password'
                    
                    # Render HTML template
                    html_content = render_to_string('emails/password_reset.html', {
                        'reset_url': reset_url,
                        'user_email': email,
                        'username': user.username,
                    })
                    
                    # Convert HTML to plain text automatically
                    h = html2text.HTML2Text()
                    h.ignore_links = False
                    h.body_width = 0  # Don't wrap lines
                    text_content = h.handle(html_content)
                    
                    # Create email message
                    email_message = EmailMultiAlternatives(
                        subject=subject,
                        body=text_content,
                        from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'info@birdr.pro',
                        to=[email],
                    )
                    email_message.attach_alternative(html_content, "text/html")
                    email_message.send()
                except Exception as e:
                    # If email sending fails, still return success for security (don't reveal if email exists)
                    pass
                
                # Always return success to prevent email enumeration
                return Response({
                    "message": "If an account with this email exists, a password reset link has been sent."
                }, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                # Don't reveal if user exists
                return Response({
                    "message": "If an account with this email exists, a password reset link has been sent."
                }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    """
    Confirm password reset with token and set new password
    """
    def post(self, request):
        from .serializers import PasswordResetConfirmSerializer
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_decode
        from django.utils.encoding import force_str
        
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            uid = serializer.validated_data['uid']
            token = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']
            
            try:
                # Decode user ID
                user_id = force_str(urlsafe_base64_decode(uid))
                user = User.objects.get(pk=user_id)
                
                # Verify token
                if default_token_generator.check_token(user, token):
                    # Set new password
                    user.set_password(new_password)
                    user.save()
                    return Response({
                        "message": "Password has been reset successfully."
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "error": "Invalid or expired reset token."
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (TypeError, ValueError, OverflowError, User.DoesNotExist):
                return Response({
                    "error": "Invalid reset link."
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
