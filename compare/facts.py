"""Upsert helpers and attribution constants for SpeciesFact."""

from __future__ import annotations

from typing import Any

from compare.models import SpeciesFact
from jizz.models import Species

AVONET_ATTRIBUTION = (
    'Tobias et al. 2022. AVONET: morphological, ecological and geographical '
    'data for all birds. Ecology Letters 25:581–597. CC BY 4.0.'
)
AVONET_LICENSE = 'CC BY 4.0'
WIKIPEDIA_LICENSE = 'CC BY-SA 4.0'
WIKIPEDIA_ATTRIBUTION = 'Wikipedia contributors (CC BY-SA)'
WIKIDATA_LICENSE = 'CC0'
WIKIDATA_ATTRIBUTION = 'Wikidata contributors (CC0)'
EBIRD_ATTRIBUTION = 'eBird relative abundance (Motmot country stats)'
BOTW_ATTRIBUTION = 'Birds of the World (temporary grounding; link for full account)'
COMMUNITY_ATTRIBUTION = 'Motmot community contributor'


def upsert_fact(
    species: Species,
    *,
    source: str,
    category: str,
    key: str,
    value_text: str = '',
    value_num: float | None = None,
    value_json: Any = None,
    source_url: str | None = None,
    license: str = '',
    attribution: str = '',
) -> SpeciesFact:
    defaults = {
        'value_text': value_text or '',
        'value_num': value_num,
        'value_json': value_json,
        'source_url': source_url,
        'license': license or '',
        'attribution': attribution or '',
    }
    fact, _created = SpeciesFact.objects.update_or_create(
        species=species,
        source=source,
        category=category,
        key=key,
        defaults=defaults,
    )
    return fact


def facts_for_species(species: Species, *, sources: list[str] | None = None) -> list[SpeciesFact]:
    qs = SpeciesFact.objects.filter(species=species)
    if sources:
        qs = qs.filter(source__in=sources)
    return list(qs)


def attributions_from_facts(facts: list[SpeciesFact]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for fact in facts:
        key = (fact.source, fact.source_url or '')
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                'source': fact.source,
                'url': fact.source_url or '',
                'attribution': fact.attribution or fact.source,
                'license': fact.license or '',
            }
        )
    return out
