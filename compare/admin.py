from django.contrib import admin
from .models import CommunityComparison, ComparisonTranslation, SpeciesTrait, SpeciesComparison, ComparisonRequest


class ComparisonTranslationInline(admin.TabularInline):
    model = ComparisonTranslation
    extra = 0
    can_delete = True
    readonly_fields = ['language', 'source_hash', 'updated']
    fields = ['language', 'source_hash', 'updated']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SpeciesTrait)
class SpeciesTraitAdmin(admin.ModelAdmin):
    list_display = ['species', 'category', 'title', 'is_verified', 'extracted_at']
    list_filter = ['category', 'is_verified', 'extracted_at']
    search_fields = ['species__name', 'species__name_latin', 'title', 'content']
    readonly_fields = ['extracted_at', 'updated_at']
    raw_id_fields = ['species']


@admin.register(SpeciesComparison)
class SpeciesComparisonAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'comparison_type', 'ai_model', 'is_verified', 'generated_at']
    list_filter = ['comparison_type', 'is_verified', 'ai_model', 'generated_at']
    search_fields = ['species_1__name', 'species_2__name', 'family_1', 'family_2', 'order_1', 'order_2']
    readonly_fields = ['generated_at', 'updated_at']
    raw_id_fields = ['species_1', 'species_2']
    inlines = [ComparisonTranslationInline]


@admin.register(CommunityComparison)
class CommunityComparisonAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'author_name', 'published', 'updated']
    list_filter = ['published', 'updated']
    search_fields = [
        'species_low__name',
        'species_high__name',
        'author_name',
        'summary',
    ]
    raw_id_fields = ['species_low', 'species_high', 'author']
    readonly_fields = ['created', 'updated']


@admin.register(ComparisonRequest)
class ComparisonRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'comparison_type', 'status', 'requested_at', 'completed_at']
    list_filter = ['status', 'comparison_type', 'requested_at']
    readonly_fields = ['requested_at', 'completed_at']
    raw_id_fields = ['comparison', 'requested_by']

