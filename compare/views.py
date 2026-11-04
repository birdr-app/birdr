import re

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404

from .models import SpeciesTrait, SpeciesComparison, ComparisonRequest, CommunityComparison
from .community import can_manage, cleaned_fields, display_name_for_user
from .serializers import (
    SpeciesTraitSerializer, SpeciesComparisonSerializer,
    ComparisonRequestSerializer, CreateComparisonRequestSerializer
)
from .ai_service import AIComparisonService, ComparisonGenerationError
from .scraper import BirdsOfTheWorldScraper
from jizz.models import Species

LOGIN_REQUIRED_MESSAGE = 'Log in to generate a comparison for this pair.'

NATIVE_APP_PLATFORMS = {'ios', 'android'}
# New AI comparisons an anonymous app user may start per IP address per day.
APP_GENERATIONS_PER_IP_PER_DAY = 30


# React Native's fetch: OkHttp on Android, CFNetwork on iOS ("Motmot/123 CFNetwork/... Darwin/...").
NATIVE_APP_USER_AGENT_RE = re.compile(r'^okhttp/|\bCFNetwork/', re.I)


def _is_native_app_request(request) -> bool:
    """The iOS or Android app rather than a browser or crawler.

    Newer builds send X-Platform and X-App-Version; 1.134.0 and older send no client
    headers on this call, so the native HTTP client's user agent counts too. Browsers,
    including crawlers running the compare page's JavaScript, send Origin or Sec-Fetch
    headers on a fetch() POST and never get through.
    """
    from jizz.usage_analytics import is_crawler_user_agent

    meta = request.META
    if meta.get('HTTP_ORIGIN') or meta.get('HTTP_SEC_FETCH_SITE') or meta.get('HTTP_SEC_FETCH_MODE'):
        return False
    user_agent = meta.get('HTTP_USER_AGENT') or ''
    if is_crawler_user_agent(user_agent):
        return False
    platform = (
        meta.get('HTTP_X_PLATFORM')
        or meta.get('HTTP_X_BIRDR_PLATFORM')
        or meta.get('HTTP_X_BIRDR_DEVICE_TYPE')
        or ''
    ).strip().lower()
    version = (meta.get('HTTP_X_APP_VERSION') or meta.get('HTTP_X_BIRDR_APP_VERSION') or '').strip()
    if platform in NATIVE_APP_PLATFORMS and version:
        return True
    return bool(NATIVE_APP_USER_AGENT_RE.search(user_agent))


def _take_app_generation_slot(request) -> bool:
    """Count one anonymous app generation for this IP; False once today's cap is reached."""
    from django.core.cache import cache
    from django.utils import timezone

    from jizz.usage_analytics import get_client_ip

    key = f'compare-app-generations:{get_client_ip(request) or "unknown"}:{timezone.now():%Y-%m-%d}'
    cache.add(key, 0, 60 * 60 * 24)
    try:
        used = cache.incr(key)
    except ValueError:
        cache.set(key, 1, 60 * 60 * 24)
        used = 1
    return used <= APP_GENERATIONS_PER_IP_PER_DAY


class OptionalJWTAuthentication(JWTAuthentication):
    """JWT auth that treats a bad or expired token as anonymous instead of a 401."""

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None


class SpeciesTraitViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing species traits.
    """
    queryset = SpeciesTrait.objects.all()
    serializer_class = SpeciesTraitSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # No authentication required
    
    def get_queryset(self):
        queryset = SpeciesTrait.objects.select_related('species')
        
        # Filter by species
        species_id = self.request.query_params.get('species_id', None)
        if species_id:
            queryset = queryset.filter(species_id=species_id)
        
        # Filter by category
        category = self.request.query_params.get('category', None)
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset


def _serialized_comparison(comparison, request, generate_translation=True):
    return SpeciesComparisonSerializer(
        comparison,
        context={'request': request, 'generate_translation': generate_translation},
    ).data


class SpeciesComparisonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing species comparisons.
    """
    queryset = SpeciesComparison.objects.all()
    serializer_class = SpeciesComparisonSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # No authentication required
    
    def get_queryset(self):
        queryset = SpeciesComparison.objects.select_related('species_1', 'species_2').prefetch_related(
            'translations'
        )
        
        # Filter by species
        species_1_id = self.request.query_params.get('species_1_id', None)
        if species_1_id:
            queryset = queryset.filter(species_1_id=species_1_id)
        
        species_2_id = self.request.query_params.get('species_2_id', None)
        if species_2_id:
            queryset = queryset.filter(species_2_id=species_2_id)
        
        # Filter by comparison type
        comparison_type = self.request.query_params.get('comparison_type', None)
        if comparison_type:
            queryset = queryset.filter(comparison_type=comparison_type)
        
        return queryset

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['generate_translation'] = getattr(self, 'action', None) != 'list'
        return ctx


class ComparisonRequestView(APIView):
    """
    API endpoint for creating and retrieving comparison requests.
    Anyone may fetch a cached comparison. Generating a new one needs a login, or the
    iOS or Android app, where most players have no account.
    """
    permission_classes = [AllowAny]
    authentication_classes = [OptionalJWTAuthentication, SessionAuthentication]
    
    def post(self, request):
        """
        Create a new comparison request.
        If a comparison already exists, return it. Otherwise, generate a new one.
        """
        serializer = CreateComparisonRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        comparison_type = data['comparison_type']
        
        # Check if comparison already exists
        existing_comparison = None
        if comparison_type == 'species':
            from compare.generation import comparison_cache_is_current, find_species_comparison

            species_1 = get_object_or_404(Species, id=data['species_1_id'])
            species_2 = get_object_or_404(Species, id=data['species_2_id'])
            existing_comparison = find_species_comparison(species_1, species_2)
            if existing_comparison and not comparison_cache_is_current(existing_comparison):
                existing_comparison = None
        elif comparison_type == 'family':
            existing_comparison = SpeciesComparison.objects.filter(
                comparison_type='family',
                family_1=data['family_1'],
                family_2=data['family_2']
            ).first()
        elif comparison_type == 'order':
            existing_comparison = SpeciesComparison.objects.filter(
                comparison_type='order',
                order_1=data['order_1'],
                order_2=data['order_2']
            ).first()
        
        if existing_comparison:
            # Return existing comparison
            return Response(
                _serialized_comparison(existing_comparison, request),
                status=status.HTTP_200_OK
            )
        
        # Generating calls OpenAI, so only logged-in users and the native app may start one.
        # 403 rather than 401 so the React app does not bounce anonymous users to /.
        user = request.user if request.user.is_authenticated else None
        if user is None:
            if not _is_native_app_request(request):
                return Response(
                    {'error': LOGIN_REQUIRED_MESSAGE, 'login_required': True},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not _take_app_generation_slot(request):
                return Response(
                    {'error': 'Too many new comparisons today. Try again tomorrow.'},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        # Create new comparison request
        request_obj = ComparisonRequest.objects.create(
            comparison_type=comparison_type,
            species_1_id=data.get('species_1_id'),
            species_2_id=data.get('species_2_id'),
            family_1=data.get('family_1'),
            family_2=data.get('family_2'),
            order_1=data.get('order_1'),
            order_2=data.get('order_2'),
            requested_by=user,
            status='processing'
        )
        
        # Generate comparison asynchronously (in production, use Celery)
        try:
            comparison = self._generate_comparison(data, comparison_type)
            request_obj.comparison = comparison
            request_obj.status = 'completed'
            request_obj.save()
            
            return Response(
                _serialized_comparison(comparison, request),
                status=status.HTTP_201_CREATED
            )
        except ComparisonGenerationError as e:
            request_obj.status = 'failed'
            request_obj.error_message = str(e)
            request_obj.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            request_obj.status = 'failed'
            request_obj.error_message = str(e)
            request_obj.save()
            
            return Response(
                {'error': 'Failed to generate comparison', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _generate_comparison(self, data: dict, comparison_type: str) -> SpeciesComparison:
        """Generate a comparison using AI."""
        ai_service = AIComparisonService()

        if comparison_type == 'species':
            from compare.generation import get_or_create_species_comparison

            species_1 = get_object_or_404(Species, id=data['species_1_id'])
            species_2 = get_object_or_404(Species, id=data['species_2_id'])
            comparison = get_or_create_species_comparison(species_1, species_2)
            if comparison is None:
                raise ValueError(f'No comparison generated for {species_1.name} vs {species_2.name}')
            return comparison
        
        elif comparison_type == 'family':
            # For family comparisons, we'd need to aggregate species data
            # This is a simplified version
            comparison_data = ai_service.generate_family_comparison(
                data['family_1'], data['family_2'], [], []
            )
            
            comparison = SpeciesComparison.objects.create(
                comparison_type='family',
                family_1=data['family_1'],
                family_2=data['family_2'],
                **comparison_data
            )
            
            return comparison
        
        else:
            raise ValueError(f"Unsupported comparison type: {comparison_type}")
    
    def get(self, request):
        """List comparison requests."""
        requests = ComparisonRequest.objects.filter(
            requested_by=request.user if request.user.is_authenticated else None
        ).order_by('-requested_at')[:20]
        
        serializer = ComparisonRequestSerializer(
            requests,
            many=True,
            context={'request': request, 'generate_translation': False},
        )
        return Response(serializer.data)


class ScrapeSpeciesView(APIView):
    """
    API endpoint for scraping species data from Birds of the World.
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # No authentication required
    
    def post(self, request):
        """Scrape species data."""
        species_id = request.data.get('species_id')
        species_code = request.data.get('species_code')
        url = request.data.get('url')
        
        if not species_id and not species_code:
            return Response(
                {'error': 'Either species_id or species_code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get species
        if species_id:
            species = get_object_or_404(Species, id=species_id)
        else:
            species = get_object_or_404(Species, code=species_code)
        
        # Scrape data
        scraper = BirdsOfTheWorldScraper()
        scraped_data = scraper.scrape_species(
            species.code, 
            url=url,
            species_name=species.name,
            scientific_name=species.name_latin
        )
        
        if not scraped_data or 'traits' not in scraped_data:
            return Response(
                {'error': 'Failed to scrape data or no data found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Save traits
        created_traits = []
        for category, trait_data in scraped_data['traits'].items():
            trait, created = SpeciesTrait.objects.get_or_create(
                species=species,
                category=category,
                title=trait_data['title'],
                defaults={
                    'content': trait_data['content'],
                    'source_url': scraped_data.get('source_url'),
                    'section': trait_data.get('section')
                }
            )
            if not created:
                # Update existing trait
                trait.content = trait_data['content']
                trait.source_url = scraped_data.get('source_url')
                trait.section = trait_data.get('section')
                trait.save()
            
            created_traits.append(trait)
        
        return Response({
            'species_id': species.id,
            'species_name': species.name,
            'traits_created': len(created_traits),
            'traits': SpeciesTraitSerializer(created_traits, many=True).data
        }, status=status.HTTP_201_CREATED)


class CommunityComparisonSubmitView(APIView):
    """Create or update a community comparison for a species pair (JWT required)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            id1 = int(request.data.get('species_1_id'))
            id2 = int(request.data.get('species_2_id'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'species_1_id and species_2_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if id1 == id2:
            return Response(
                {'detail': 'Choose two different species.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        first = get_object_or_404(Species, id=id1)
        second = get_object_or_404(Species, id=id2)
        low, high = (first, second) if first.id < second.id else (second, first)
        data, any_text = cleaned_fields(request.data)
        if not any_text:
            return Response(
                {'detail': 'Write at least one section before publishing.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        community = CommunityComparison.objects.filter(
            species_low=low, species_high=high
        ).first()
        if community:
            if not can_manage(request.user, community):
                return Response(
                    {'detail': 'A community description is already published for this pair.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for field, value in data.items():
                setattr(community, field, value)
            if community.author_id == request.user.id:
                community.author_name = display_name_for_user(request.user)
            community.published = True
            community.save()
            created = False
        else:
            community = CommunityComparison.objects.create(
                species_low=low,
                species_high=high,
                author=request.user,
                author_name=display_name_for_user(request.user),
                published=True,
                **data,
            )
            created = True
        return Response(
            {'id': community.id, 'created': created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

