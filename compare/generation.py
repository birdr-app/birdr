"""
Load or generate cached species-vs-species comparisons.
"""
from __future__ import annotations

import logging

from django.db import transaction

from compare.ai_service import (
    AIComparisonService,
    ComparisonGenerationError,
    HANDBOOK_MODEL,
    NO_GROUNDING_MESSAGE,
    comparison_model_name,
    comparison_prompt_version,
    has_grounding_traits,
)
from compare.models import SpeciesComparison, SpeciesTrait
from jizz.models import Species

logger = logging.getLogger(__name__)


def canonical_species_pair(species_a: Species, species_b: Species) -> tuple[Species, Species]:
    if species_a.id <= species_b.id:
        return species_a, species_b
    return species_b, species_a


def find_species_comparison(species_a: Species, species_b: Species) -> SpeciesComparison | None:
    return (
        SpeciesComparison.objects.filter(
            comparison_type='species',
            species_1=species_a,
            species_2=species_b,
        ).first()
        or SpeciesComparison.objects.filter(
            comparison_type='species',
            species_1=species_b,
            species_2=species_a,
        ).first()
    )


def comparison_cache_is_current(comparison: SpeciesComparison | None) -> bool:
    """True when the cached row was built with the current model and prompt.

    Handbook extracts (``botw-extract``) are leftovers from a previous credit
    failure — never treat them as current so generation can retry.
    """
    if comparison is None:
        return False
    stored_model = (comparison.ai_model or '').strip()
    stored_prompt = (comparison.ai_prompt_version or '').strip()
    if stored_prompt != comparison_prompt_version():
        return False
    if stored_model == HANDBOOK_MODEL:
        return False
    return stored_model == comparison_model_name()


def traits_dict_for_species(species: Species) -> dict:
    grouped: dict[str, list[str]] = {}
    for trait in SpeciesTrait.objects.filter(species=species):
        grouped.setdefault(trait.category, []).append(trait.content)
    formatted = {}
    for category, contents in grouped.items():
        text = '\n\n'.join(part for part in contents if part)
        if text:
            formatted[category] = {
                'title': category.replace('_', ' ').title(),
                'content': text,
            }
    family = getattr(species, 'taxonomic_family', None)
    order = getattr(species, 'taxonomic_order', None)
    taxonomy_bits = []
    if family:
        taxonomy_bits.append(
            f'{family.name_en or family.name_latin} ({family.name_latin})'
            if getattr(family, 'name_latin', None)
            else (family.name_en or family.name_latin or '')
        )
    if order:
        taxonomy_bits.append(order.name_en or order.name_latin or '')
    taxonomy = '; '.join(bit for bit in taxonomy_bits if bit)
    if taxonomy:
        formatted['taxonomy'] = taxonomy
    return formatted


def _save_scraped_traits(species: Species, scraped_data: dict) -> None:
    traits = (scraped_data or {}).get('traits') or {}
    source_url = scraped_data.get('source_url')
    with transaction.atomic():
        for category, trait_data in traits.items():
            trait, created = SpeciesTrait.objects.get_or_create(
                species=species,
                category=category,
                title=trait_data['title'],
                defaults={
                    'content': trait_data['content'],
                    'source_url': source_url,
                    'section': trait_data.get('section'),
                },
            )
            if not created:
                trait.content = trait_data['content']
                trait.source_url = source_url
                trait.section = trait_data.get('section')
                trait.save(update_fields=['content', 'source_url', 'section', 'updated_at'])


def ensure_species_traits(species: Species, *, scrape: bool = True) -> dict:
    traits = traits_dict_for_species(species)
    if has_grounding_traits(traits):
        return traits
    if not scrape:
        logger.info(
            'Species %s has no identification/similar_species notes (scrape skipped)',
            species.name,
        )
        return traits
    try:
        from compare.scraper import BirdsOfTheWorldScraper

        scraped = BirdsOfTheWorldScraper().scrape_species(
            species.code,
            species_name=species.name,
            scientific_name=species.name_latin,
        )
        if scraped and scraped.get('traits'):
            _save_scraped_traits(species, scraped)
        else:
            logger.warning('BotW scrape for %s returned no traits', species.name)
    except Exception:
        logger.exception('Failed to scrape Birds of the World traits for %s', species.name)
    refreshed = traits_dict_for_species(species)
    if has_grounding_traits(refreshed):
        logger.info('Scraped grounding traits for %s', species.name)
    else:
        logger.warning(
            'BotW scrape for %s left identification/similar_species empty',
            species.name,
        )
    return refreshed


def get_or_create_species_comparison(
    species_a: Species,
    species_b: Species,
    *,
    force: bool = False,
    scrape: bool = True,
) -> SpeciesComparison | None:
    """
    Return a cached species comparison, generating one if needed.

    Pairs are stored with the lower species id as species_1.
    """
    if species_a.id == species_b.id:
        return None

    low, high = canonical_species_pair(species_a, species_b)
    existing = find_species_comparison(low, high)
    if existing and not force and comparison_cache_is_current(existing):
        return existing

    traits_1 = ensure_species_traits(low, scrape=scrape)
    traits_2 = ensure_species_traits(high, scrape=scrape)
    if not has_grounding_traits(traits_1) and not has_grounding_traits(traits_2):
        logger.warning(
            'Refusing ungrounded comparison for %s vs %s (no identification/similar_species)',
            low.name,
            high.name,
        )
        raise ComparisonGenerationError(NO_GROUNDING_MESSAGE)

    traits_1['name_latin'] = low.name_latin
    traits_2['name_latin'] = high.name_latin

    service = AIComparisonService()
    comparison_data = service.generate_species_comparison(
        traits_1,
        traits_2,
        low.name,
        high.name,
        low.name_latin,
        high.name_latin,
    )
    if not comparison_data.get('summary'):
        logger.warning('No comparison generated for %s vs %s', low.name, high.name)
        raise ComparisonGenerationError(
            f'No comparison generated for {low.name} vs {high.name}'
        )

    defaults = {
        **comparison_data,
        'ai_model': service.model or comparison_model_name(),
        'ai_prompt_version': service.prompt_version or comparison_prompt_version(),
    }
    comparison, _created = SpeciesComparison.objects.update_or_create(
        comparison_type='species',
        species_1=low,
        species_2=high,
        defaults=defaults,
    )
    if existing and existing.id != comparison.id:
        existing.delete()
    return comparison
