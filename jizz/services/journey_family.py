from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Q

from jizz.models import Country, CountrySpecies, Game, JourneyStep, Species, TaxonomicFamily
from media.models import Media

_MEDIA_TYPE = {
    'images': 'image',
    'video': 'video',
    'audio': 'audio',
}


def family_step_index(step: JourneyStep, level_steps) -> int:
    """0-based index among family-type steps in the same level."""
    index = 0
    for current in level_steps:
        if current.id == step.id:
            return index
        if current.step_type == 'family':
            index += 1
    return index


def _country_statuses_for_step(step: JourneyStep) -> list[str]:
    return ['native', 'endemic', 'rare']


def eligible_species_ids_for_step(country: Country, step: JourneyStep) -> list[int]:
    """Species IDs eligible for a journey step (same rules as game question selection)."""
    media_type = _MEDIA_TYPE.get(step.media, 'image')
    statuses = _country_statuses_for_step(step)

    country_species = CountrySpecies.objects.filter(
        country_id=country.pk,
        status__in=statuses,
    ).filter(Game.country_species_rarity_q(step.rarity))

    species_qs = Species.objects.filter(
        id__in=country_species.values('species_id'),
    ).filter(
        Exists(
            Media.objects.filter(
                species_id=OuterRef('pk'),
                type=media_type,
                hide=False,
            )
        )
    )
    return list(species_qs.values_list('id', flat=True))


def families_ranked_for_step(country: Country, step: JourneyStep):
    """Families ordered by eligible species count (desc), then Latin name."""
    eligible_ids = eligible_species_ids_for_step(country, step)
    if not eligible_ids:
        return TaxonomicFamily.objects.none()

    return (
        TaxonomicFamily.objects.annotate(
            species_count=Count(
                'species',
                filter=Q(species__id__in=eligible_ids),
                distinct=True,
            ),
        )
        .filter(species_count__gt=0)
        .order_by('-species_count', 'name_latin')
    )


def resolve_family_for_step(
    step: JourneyStep,
    country: Country,
    level_steps=None,
) -> TaxonomicFamily | None:
    if step.step_type != 'family':
        return None
    if level_steps is None:
        level_steps = list(step.journey_level.steps.order_by('sequence'))
    ranked = list(families_ranked_for_step(country, step))
    index = family_step_index(step, level_steps)
    if index >= len(ranked):
        return None
    return ranked[index]


def family_by_latin(name_latin: str | None) -> TaxonomicFamily | None:
    if not name_latin:
        return None
    return TaxonomicFamily.objects.filter(name_latin=name_latin).first()


def family_display_fields(family: TaxonomicFamily, language: str = 'en') -> dict[str, str]:
    use_nl = (language or 'en').startswith('nl')
    name = family.name_nl if use_nl and family.name_nl else family.name_en
    description = family.description_nl if use_nl and family.description_nl else family.description_en
    return {
        'name_latin': family.name_latin,
        'name': name or family.name_en or family.name_latin,
        'description': description or '',
    }
