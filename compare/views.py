from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
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
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # No authentication required
    
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
        
        # Create new comparison request
        request_obj = ComparisonRequest.objects.create(
            comparison_type=comparison_type,
            species_1_id=data.get('species_1_id'),
            species_2_id=data.get('species_2_id'),
            family_1=data.get('family_1'),
            family_2=data.get('family_2'),
            order_1=data.get('order_1'),
            order_2=data.get('order_2'),
            requested_by=request.user if request.user.is_authenticated else None,
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

