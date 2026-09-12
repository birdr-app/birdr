"""Helpers for the public species index page."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Count, Q

from compare.models import SpeciesComparison
from jizz.marketing.pages import (
    MARKETING_QUERY_CACHE_TTL,
    public_species_ids,
)
from jizz.marketing.slugs import compare_pair_slug
from jizz.models import Species, TaxonomicFamily
from jizz.marketing.local_names import species_name_language_id

SEARCH_MIN = 2
SEARCH_LIMIT = 40
FAMILY_LIMIT = 80


def search_public_species(
    query: str,
    *,
    family_latin: str = '',
    limit: int = SEARCH_LIMIT,
    locale: str | None = None,
):
    qs = Species.objects.filter(pk__in=public_species_ids())
    if family_latin:
        qs = qs.filter(taxonomic_family__name_latin=family_latin)
    q = (query or '').strip()
    if q:
        name_filter = (
            Q(name__icontains=q)
            | Q(name_latin__icontains=q)
            | Q(name_nl__icontains=q)
            | Q(code__icontains=q)
        )
        lang = species_name_language_id(locale)
        if lang and lang != 'en':
            name_filter |= Q(speciesname__language_id=lang, speciesname__name__icontains=q)
        qs = qs.filter(name_filter).distinct()
    return list(
        qs.order_by('name').only('id', 'name', 'name_latin', 'name_nl', 'slug', 'code')[:limit]
    )


def public_families() -> list[dict]:
    cached = cache.get('marketing-public-families-v2')
    if cached is not None:
        return cached
    rows = list(
        TaxonomicFamily.objects.filter(species__pk__in=public_species_ids())
        .annotate(species_n=Count('species', distinct=True))
        .filter(species_n__gt=0)
        .order_by('name_en')
        .values('name_en', 'name_nl', 'name_latin', 'species_n')
    )
    cache.set('marketing-public-families-v2', rows, MARKETING_QUERY_CACHE_TTL)
    return rows


def featured_comparisons(*, limit: int = 6) -> list[dict]:
    cache_key = f'marketing-featured-comparisons:{limit}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    rows = _featured_comparisons(limit=limit)
    cache.set(cache_key, rows, MARKETING_QUERY_CACHE_TTL)
    return rows


def _featured_comparisons(*, limit: int = 6) -> list[dict]:
    rows = []
    qs = (
        SpeciesComparison.objects.filter(comparison_type='species')
        .exclude(summary='')
        .select_related('species_1', 'species_2')
        .order_by('-id')
    )
    for comparison in qs:
        left = comparison.species_1
        right = comparison.species_2
        if not left or not right or not left.slug or not right.slug:
            continue
        rows.append(
            {
                'left_id': left.id,
                'right_id': right.id,
                'left_name': left.name,
                'right_name': right.name,
                'summary': comparison.summary,
                'url': f'/site/compare/{compare_pair_slug(left.slug, right.slug)}/',
            }
        )
        if len(rows) >= limit:
            break
    return rows
