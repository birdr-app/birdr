from rest_framework import serializers
from .models import SpeciesTrait, SpeciesComparison, ComparisonRequest
from jizz.update_i18n import resolve_request_language
import markdown


class SpeciesTraitSerializer(serializers.ModelSerializer):
    species_name = serializers.CharField(source='species.name', read_only=True)
    species_latin = serializers.CharField(source='species.name_latin', read_only=True)
    
    class Meta:
        model = SpeciesTrait
        fields = [
            'id', 'species', 'species_name', 'species_latin', 'category', 'title',
            'content', 'source_url', 'section', 'extracted_at', 'updated_at', 'is_verified'
        ]
        read_only_fields = ['extracted_at', 'updated_at']


class SpeciesComparisonSerializer(serializers.ModelSerializer):
    species_1_name = serializers.CharField(source='species_1.name', read_only=True)
    species_1_latin = serializers.CharField(source='species_1.name_latin', read_only=True)
    species_1_code = serializers.CharField(source='species_1.code', read_only=True)
    species_1_slug = serializers.SerializerMethodField()
    species_2_name = serializers.CharField(source='species_2.name', read_only=True)
    species_2_latin = serializers.CharField(source='species_2.name_latin', read_only=True)
    species_2_code = serializers.CharField(source='species_2.code', read_only=True)
    species_2_slug = serializers.SerializerMethodField()
    
    # HTML versions of markdown fields
    summary_html = serializers.SerializerMethodField()
    detailed_comparison_html = serializers.SerializerMethodField()
    size_comparison_html = serializers.SerializerMethodField()
    plumage_comparison_html = serializers.SerializerMethodField()
    behavior_comparison_html = serializers.SerializerMethodField()
    habitat_comparison_html = serializers.SerializerMethodField()
    vocalization_comparison_html = serializers.SerializerMethodField()
    identification_tips_html = serializers.SerializerMethodField()
    
    def _markdown_to_html(self, markdown_text):
        """Convert markdown to HTML."""
        if not markdown_text:
            return None
        # Convert markdown to HTML with extensions for better formatting
        # 'extra' adds features like tables, fenced code blocks, etc.
        # 'nl2br' converts newlines to <br> tags
        html = markdown.markdown(
            markdown_text,
            extensions=['extra', 'nl2br']
        )
        return html
    
    def get_summary_html(self, obj):
        return self._markdown_to_html(obj.summary)
    
    def get_detailed_comparison_html(self, obj):
        return self._markdown_to_html(obj.detailed_comparison)
    
    def get_size_comparison_html(self, obj):
        return self._markdown_to_html(obj.size_comparison)
    
    def get_plumage_comparison_html(self, obj):
        return self._markdown_to_html(obj.plumage_comparison)
    
    def get_behavior_comparison_html(self, obj):
        return self._markdown_to_html(obj.behavior_comparison)
    
    def get_habitat_comparison_html(self, obj):
        return self._markdown_to_html(obj.habitat_comparison)
    
    def get_vocalization_comparison_html(self, obj):
        return self._markdown_to_html(obj.vocalization_comparison)
    
    def get_identification_tips_html(self, obj):
        return self._markdown_to_html(obj.identification_tips)

    def get_species_1_slug(self, obj):
        return getattr(obj.species_1, 'slug', None) if getattr(obj, 'species_1_id', None) else None

    def get_species_2_slug(self, obj):
        return getattr(obj.species_2, 'slug', None) if getattr(obj, 'species_2_id', None) else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        language = resolve_request_language(request) if request is not None else 'en'
        generate = self.context.get('generate_translation', True)
        if language == 'en':
            return data
        from compare.i18n import TRANSLATABLE_FIELDS, localized_fields

        fields = localized_fields(instance, language, generate=generate)
        for key in TRANSLATABLE_FIELDS:
            value = fields.get(key) or ''
            data[key] = value or None
            html_key = f'{key}_html'
            if html_key in data:
                data[html_key] = self._markdown_to_html(value)
        return data
    
    class Meta:
        model = SpeciesComparison
        fields = [
            'id', 'comparison_type', 'species_1', 'species_1_name', 'species_1_latin', 'species_1_code',
            'species_1_slug',
            'species_2', 'species_2_name', 'species_2_latin', 'species_2_code', 'species_2_slug',
            'family_1', 'family_2',
            'order_1', 'order_2', 'summary', 'summary_html', 'detailed_comparison', 'detailed_comparison_html',
            'size_comparison', 'size_comparison_html', 'plumage_comparison', 'plumage_comparison_html',
            'behavior_comparison', 'behavior_comparison_html', 'habitat_comparison', 'habitat_comparison_html',
            'vocalization_comparison', 'vocalization_comparison_html', 'identification_tips', 'identification_tips_html',
            'generated_at', 'updated_at', 'ai_model', 'is_verified', 'quality_score'
        ]
        read_only_fields = ['generated_at', 'updated_at']


class ComparisonRequestSerializer(serializers.ModelSerializer):
    comparison = SpeciesComparisonSerializer(read_only=True)
    
    class Meta:
        model = ComparisonRequest
        fields = [
            'id', 'comparison', 'comparison_type', 'species_1_id', 'species_2_id',
            'family_1', 'family_2', 'order_1', 'order_2', 'status', 'error_message',
            'requested_at', 'completed_at', 'requested_by'
        ]
        read_only_fields = ['requested_at', 'completed_at', 'requested_by']


class CreateComparisonRequestSerializer(serializers.Serializer):
    """Serializer for creating a new comparison request."""
    comparison_type = serializers.ChoiceField(choices=SpeciesComparison.COMPARISON_TYPE_CHOICES)
    species_1_id = serializers.IntegerField(required=False, allow_null=True)
    species_2_id = serializers.IntegerField(required=False, allow_null=True)
    family_1 = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    family_2 = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    order_1 = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    order_2 = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    
    def validate(self, data):
        """Validate that appropriate fields are provided based on comparison_type."""
        comparison_type = data.get('comparison_type')
        
        if comparison_type == 'species':
            if not data.get('species_1_id') or not data.get('species_2_id'):
                raise serializers.ValidationError(
                    "species_1_id and species_2_id are required for species comparisons"
                )
        elif comparison_type == 'family':
            if not data.get('family_1') or not data.get('family_2'):
                raise serializers.ValidationError(
                    "family_1 and family_2 are required for family comparisons"
                )
        elif comparison_type == 'order':
            if not data.get('order_1') or not data.get('order_2'):
                raise serializers.ValidationError(
                    "order_1 and order_2 are required for order comparisons"
                )
        
        return data

