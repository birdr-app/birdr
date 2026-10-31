"""Assemble multi-source grounding for a species pair (open-first, BotW fallback)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from compare.collectors.wikipedia_species import ensure_wikipedia_species_facts
from compare.collectors.wikidata import ensure_wikidata_species_facts
from compare.facts import (
    BOTW_ATTRIBUTION,
    COMMUNITY_ATTRIBUTION,
    EBIRD_ATTRIBUTION,
    attributions_from_facts,
    facts_for_species,
    upsert_fact,
)
from compare.models import CommunityComparison, SpeciesFact, SpeciesTrait
from jizz.models import CountrySpecies, Species

logger = logging.getLogger(__name__)

OPEN_SOURCES = (
    SpeciesFact.SOURCE_WIKIPEDIA,
    SpeciesFact.SOURCE_WIKIDATA,
    SpeciesFact.SOURCE_AVONET,
    SpeciesFact.SOURCE_EBIRD,
    SpeciesFact.SOURCE_COMMUNITY,
)


@dataclass
class PairGrounding:
    species_1: Species
    species_2: Species
    traits_1: dict[str, Any] = field(default_factory=dict)
    traits_2: dict[str, Any] = field(default_factory=dict)
    sources_used: list[dict[str, str]] = field(default_factory=list)
    used_botw_fallback: bool = False
    measurement_table: str = ''
    community_block: str = ''
    abundance_block: str = ''

    @property
    def is_grounded(self) -> bool:
        return has_open_or_botw_grounding(self.traits_1) or has_open_or_botw_grounding(
            self.traits_2
        )


def _trait_content(section_data) -> str:
    if isinstance(section_data, dict):
        return section_data.get('content') or ''
    if isinstance(section_data, str):
        return section_data
    return ''


def has_open_or_botw_grounding(traits: dict | None) -> bool:
    """Enough to generate: ID / plumage / similar-species prose, or size numbers."""
    data = traits or {}
    for key in ('identification', 'similar_species', 'plumage', 'measurements', 'size'):
        if _trait_content(data.get(key)).strip():
            return True
    return False


def has_open_identification(facts: list[SpeciesFact]) -> bool:
    for fact in facts:
        if fact.source == SpeciesFact.SOURCE_BOTW:
            continue
        if fact.category in (
            'identification',
            'similar_species',
            'plumage',
            'measurements',
            'size',
        ):
            if (fact.value_text or '').strip() or fact.value_num is not None:
                return True
    return False


def _facts_to_traits(facts: list[SpeciesFact]) -> dict[str, Any]:
    grouped: dict[str, list[str]] = {}
    for fact in facts:
        if fact.source == SpeciesFact.SOURCE_BOTW:
            continue
        bits = []
        if fact.value_num is not None:
            bits.append(f'{fact.key}={fact.value_num}')
        elif fact.value_text:
            bits.append(f'{fact.key}: {fact.value_text}' if fact.key != 'intro' else fact.value_text)
        if not bits:
            continue
        label = f'[{fact.source}] ' + ' '.join(bits)
        grouped.setdefault(fact.category, []).append(label)
    formatted: dict[str, Any] = {}
    for category, lines in grouped.items():
        text = '\n'.join(lines)
        if text:
            formatted[category] = {
                'title': category.replace('_', ' ').title(),
                'content': text,
            }
    return formatted


def _botw_traits_dict(species: Species) -> dict[str, Any]:
    grouped: dict[str, list[str]] = {}
    for trait in SpeciesTrait.objects.filter(species=species):
        grouped.setdefault(trait.category, []).append(trait.content)
    formatted = {}
    for category, contents in grouped.items():
        text = '\n\n'.join(part for part in contents if part)
        if text:
            formatted[category] = {
                'title': category.replace('_', ' ').title(),
                'content': f'[botw] {text}',
            }
    return formatted


def _merge_traits(*parts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, list[str]] = {}
    for part in parts:
        for category, data in part.items():
            if category == 'name_latin':
                continue
            content = _trait_content(data).strip()
            if not content:
                continue
            merged.setdefault(category, []).append(content)
    out: dict[str, Any] = {}
    for category, lines in merged.items():
        out[category] = {
            'title': category.replace('_', ' ').title(),
            'content': '\n\n'.join(lines),
        }
    return out


def _ensure_open_facts(species: Species, *, fetch_remote: bool = True) -> list[SpeciesFact]:
    existing = facts_for_species(species, sources=list(OPEN_SOURCES))
    if has_open_identification(existing) or not fetch_remote:
        return facts_for_species(species)
    if fetch_remote:
        try:
            ensure_wikipedia_species_facts(species)
        except Exception:
            logger.exception('Wikipedia fetch failed for %s', species.name)
        try:
            ensure_wikidata_species_facts(species)
        except Exception:
            logger.exception('Wikidata fetch failed for %s', species.name)
    return facts_for_species(species)


def _save_botw_traits(species: Species, scraped_data: dict) -> None:
    from django.db import transaction

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


def _ensure_botw_fallback(species: Species, *, scrape: bool = True) -> dict[str, Any]:
    from compare.ai_service import has_grounding_traits

    traits = _botw_traits_dict(species)
    if has_grounding_traits(traits) or not scrape:
        return traits
    try:
        from compare.scraper import BirdsOfTheWorldScraper

        scraped = BirdsOfTheWorldScraper().scrape_species(
            species.code,
            species_name=species.name,
            scientific_name=species.name_latin,
        )
        if scraped and scraped.get('traits'):
            _save_botw_traits(species, scraped)
    except Exception:
        logger.exception('BotW fallback scrape failed for %s', species.name)
    return _botw_traits_dict(species)


def _measurement_table(facts_1: list[SpeciesFact], facts_2: list[SpeciesFact], name_1: str, name_2: str) -> str:
    # AVONET morphometrics beat Wikidata when both exist for the same key.
    _SOURCE_RANK = {
        SpeciesFact.SOURCE_AVONET: 0,
        SpeciesFact.SOURCE_WIKIDATA: 1,
    }

    def nums(facts: list[SpeciesFact]) -> dict[str, float]:
        best: dict[str, tuple[int, float]] = {}
        for f in facts:
            if f.value_num is None:
                continue
            rank = _SOURCE_RANK.get(f.source)
            if rank is None:
                continue
            # Normalize legacy Wikidata keys without units.
            key = f.key
            if key == 'body_mass':
                key = 'body_mass_g'
            elif key == 'body_length':
                key = 'body_length_mm'
            prev = best.get(key)
            if prev is None or rank < prev[0]:
                best[key] = (rank, f.value_num)
        return {key: value for key, (_rank, value) in best.items()}

    a = nums(facts_1)
    b = nums(facts_2)
    keys = sorted(set(a) | set(b))
    if not keys:
        return ''
    lines = [
        f'Measurements in grams/mm (prefer AVONET, else adult Wikidata mass):\n'
        f'| trait | {name_1} | {name_2} |'
    ]
    lines.append('|---|---|---|')
    for key in keys:
        left = a.get(key)
        right = b.get(key)
        lines.append(
            f'| {key} | {left if left is not None else "—"} | {right if right is not None else "—"} |'
        )
    return '\n'.join(lines)


def _community_block(species_a: Species, species_b: Species) -> tuple[str, list[SpeciesFact]]:
    low, high = (species_a, species_b) if species_a.id <= species_b.id else (species_b, species_a)
    row = (
        CommunityComparison.objects.filter(
            species_low=low,
            species_high=high,
            published=True,
        )
        .order_by('-updated')
        .first()
    )
    if not row:
        return '', []
    parts = []
    for label, value in (
        ('summary', row.summary),
        ('identification_tips', row.identification_tips),
        ('size', row.size_comparison),
        ('plumage', row.plumage_comparison),
        ('habitat', row.habitat_comparison),
        ('vocalization', row.vocalization_comparison),
        ('behavior', row.behavior_comparison),
    ):
        text = (value or '').strip()
        if text:
            parts.append(f'{label}: {text}')
    if not parts:
        return '', []
    block = '[community] ' + '\n'.join(parts)
    fact = upsert_fact(
        low,
        source=SpeciesFact.SOURCE_COMMUNITY,
        category='identification',
        key=f'pair_{high.id}',
        value_text=block[:8000],
        attribution=f'{COMMUNITY_ATTRIBUTION}: {row.author_name}',
    )
    return block, [fact]


def _abundance_block(
    species_a: Species,
    species_b: Species,
    country_code: str | None,
) -> tuple[str, list[SpeciesFact]]:
    if not country_code:
        return '', []
    rows = list(
        CountrySpecies.objects.filter(
            country__code=country_code,
            species_id__in=[species_a.id, species_b.id],
        ).select_related('species', 'country')
    )
    if not rows:
        return '', []
    lines = [f'Local relative abundance in {country_code} (eBird-derived Motmot stats):']
    facts: list[SpeciesFact] = []
    for row in rows:
        freq = row.frequency or 'unknown'
        pct = row.frequency_pct
        pct_bit = f', frequency_pct={pct}' if pct is not None else ''
        lines.append(f'- {row.species.name}: {freq}{pct_bit}')
        facts.append(
            upsert_fact(
                row.species,
                source=SpeciesFact.SOURCE_EBIRD,
                category='distribution',
                key=f'abundance_{country_code}',
                value_text=f'{freq}{pct_bit}',
                value_json={'frequency': freq, 'frequency_pct': pct, 'country': country_code},
                attribution=EBIRD_ATTRIBUTION,
            )
        )
    return '\n'.join(lines), facts


def build_pair_grounding(
    species_1: Species,
    species_2: Species,
    *,
    country_code: str | None = None,
    scrape_botw: bool = True,
    fetch_remote: bool = True,
) -> PairGrounding:
    """
    Open sources first; BotW scrape only when open grounding is insufficient.
    """
    facts_1 = _ensure_open_facts(species_1, fetch_remote=fetch_remote)
    facts_2 = _ensure_open_facts(species_2, fetch_remote=fetch_remote)

    open_1 = [f for f in facts_1 if f.source != SpeciesFact.SOURCE_BOTW]
    open_2 = [f for f in facts_2 if f.source != SpeciesFact.SOURCE_BOTW]
    traits_1 = _facts_to_traits(open_1)
    traits_2 = _facts_to_traits(open_2)

    community_block, community_facts = _community_block(species_1, species_2)
    abundance_block, abundance_facts = _abundance_block(species_1, species_2, country_code)

    used_botw = False
    botw_attrs: list[dict[str, str]] = []
    if not (has_open_identification(open_1) or has_open_identification(open_2) or community_block):
        used_botw = True
        botw_1 = _ensure_botw_fallback(species_1, scrape=scrape_botw)
        botw_2 = _ensure_botw_fallback(species_2, scrape=scrape_botw)
        traits_1 = _merge_traits(traits_1, botw_1)
        traits_2 = _merge_traits(traits_2, botw_2)
        # Cap BotW dump size in traits for prompt safety
        for traits in (traits_1, traits_2):
            for key in ('identification', 'similar_species'):
                content = _trait_content(traits.get(key))
                if len(content) > 6000:
                    traits[key] = {
                        'title': key.replace('_', ' ').title(),
                        'content': content[:6000] + '…',
                    }
        botw_attrs.append(
            {
                'source': SpeciesFact.SOURCE_BOTW,
                'url': '',
                'attribution': BOTW_ATTRIBUTION,
                'license': '',
            }
        )

    traits_1['name_latin'] = species_1.name_latin
    traits_2['name_latin'] = species_2.name_latin

    measurement_table = _measurement_table(
        open_1, open_2, species_1.name, species_2.name
    )

    all_facts = list(open_1) + list(open_2) + community_facts + abundance_facts
    sources = attributions_from_facts(all_facts) + botw_attrs
    # Dedupe sources by source+url
    seen: set[tuple[str, str]] = set()
    deduped = []
    for row in sources:
        key = (row.get('source', ''), row.get('url', ''))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return PairGrounding(
        species_1=species_1,
        species_2=species_2,
        traits_1=traits_1,
        traits_2=traits_2,
        sources_used=deduped,
        used_botw_fallback=used_botw,
        measurement_table=measurement_table,
        community_block=community_block,
        abundance_block=abundance_block,
    )
