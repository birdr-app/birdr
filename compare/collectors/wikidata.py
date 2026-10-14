"""Fetch structured Wikidata facts (CC0) for a species."""

from __future__ import annotations

import logging
from typing import Any

import requests

from compare.facts import WIKIDATA_ATTRIBUTION, WIKIDATA_LICENSE, upsert_fact
from compare.models import SpeciesFact
from jizz.models import Species

logger = logging.getLogger(__name__)

WIKIDATA_API = 'https://www.wikidata.org/w/api.php'
WIKIDATA_SPARQL = 'https://query.wikidata.org/sparql'
USER_AGENT = 'BirdrCompareBot/1.0 (https://birdr.pro; species comparison grounding)'

# Property IDs
P_MASS = 'P2067'  # mass
P_LENGTH = 'P2043'  # length
P_IUCN = 'P141'  # IUCN conservation status
P_STATEMENT_ROLE = 'P3831'  # object of statement has role

# Units
Q_GRAM = 'Q41803'
Q_KILOGRAM = 'Q11570'
Q_MILLIMETRE = 'Q174728'
Q_CENTIMETRE = 'Q25267'
Q_METRE = 'Q11573'

# Mass statement roles (Sabine's Gull has birth 16 g + adult 185 g)
Q_BIRTH_WEIGHT = 'Q4128476'
Q_ADULT_WEIGHT = 'Q78101716'
_SKIP_MASS_ROLES = frozenset({Q_BIRTH_WEIGHT})
_PREFER_MASS_ROLES = frozenset({Q_ADULT_WEIGHT})


def _session() -> requests.Session:
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    return session


def _search_entity_id(session: requests.Session, latin: str) -> str | None:
    response = session.get(
        WIKIDATA_API,
        params={
            'action': 'wbsearchentities',
            'search': latin,
            'language': 'en',
            'type': 'item',
            'limit': 5,
            'format': 'json',
        },
        timeout=30,
    )
    response.raise_for_status()
    results = response.json().get('search') or []
    latin_l = latin.lower()
    for row in results:
        label = (row.get('label') or '').lower()
        desc = (row.get('description') or '').lower()
        if latin_l in label or 'species of' in desc or 'bird' in desc:
            return row.get('id')
    return results[0].get('id') if results else None


def _quantity_parts(claim: dict[str, Any]) -> tuple[float, str] | None:
    """Return (amount, unit_qid) from a Wikidata quantity claim."""
    try:
        mainsnak = claim['mainsnak']
        datavalue = mainsnak['datavalue']['value']
        amount = datavalue.get('amount')
        if amount is None:
            return None
        unit = str(datavalue.get('unit') or '')
        unit_qid = unit.rsplit('/', 1)[-1] if unit.startswith('http') else unit
        return float(str(amount).lstrip('+')), unit_qid
    except (KeyError, TypeError, ValueError):
        return None


def _quantity_amount(claim: dict[str, Any]) -> float | None:
    parts = _quantity_parts(claim)
    return parts[0] if parts else None


def _claim_roles(claim: dict[str, Any]) -> set[str]:
    roles: set[str] = set()
    for snak in (claim.get('qualifiers') or {}).get(P_STATEMENT_ROLE) or []:
        try:
            roles.add(snak['datavalue']['value']['id'])
        except (KeyError, TypeError):
            continue
    return roles


def _to_grams(amount: float, unit_qid: str) -> float | None:
    if unit_qid in ('', '1', Q_GRAM):
        # Unitless bird masses on Wikidata are almost always grams.
        return amount
    if unit_qid == Q_KILOGRAM:
        return amount * 1000.0
    return None


def _to_millimetres(amount: float, unit_qid: str) -> float | None:
    if unit_qid in ('', '1', Q_MILLIMETRE):
        return amount
    if unit_qid == Q_CENTIMETRE:
        return amount * 10.0
    if unit_qid == Q_METRE:
        return amount * 1000.0
    return None


def pick_adult_mass_g(claims: list[dict[str, Any]]) -> float | None:
    """
    Prefer adult-weight mass statements; never use birth weight.

    When several adult (or unqualified) masses exist (e.g. male/female), average them.
    """
    adult: list[float] = []
    unqualified: list[float] = []
    for claim in claims:
        parts = _quantity_parts(claim)
        if not parts:
            continue
        amount, unit_qid = parts
        grams = _to_grams(amount, unit_qid)
        if grams is None:
            continue
        roles = _claim_roles(claim)
        if roles & _SKIP_MASS_ROLES:
            continue
        if roles & _PREFER_MASS_ROLES:
            adult.append(grams)
        elif not roles:
            unqualified.append(grams)
        else:
            # Other roles (e.g. sex-only without adult tag): treat as usable fallback.
            unqualified.append(grams)
    chosen = adult or unqualified
    if not chosen:
        return None
    return sum(chosen) / len(chosen)


def pick_length_mm(claims: list[dict[str, Any]]) -> float | None:
    values: list[float] = []
    for claim in claims:
        parts = _quantity_parts(claim)
        if not parts:
            continue
        amount, unit_qid = parts
        mm = _to_millimetres(amount, unit_qid)
        if mm is not None:
            values.append(mm)
    if not values:
        return None
    return sum(values) / len(values)


def _entity_claims(session: requests.Session, entity_id: str) -> dict[str, Any]:
    response = session.get(
        WIKIDATA_API,
        params={
            'action': 'wbgetentities',
            'ids': entity_id,
            'props': 'claims|sitelinks',
            'format': 'json',
        },
        timeout=30,
    )
    response.raise_for_status()
    entities = response.json().get('entities') or {}
    return entities.get(entity_id) or {}


def ensure_wikidata_species_facts(species: Species) -> list[SpeciesFact]:
    latin = (species.name_latin or '').strip()
    if not latin:
        return []

    session = _session()
    try:
        entity_id = _search_entity_id(session, latin)
        if not entity_id:
            return []
        entity = _entity_claims(session, entity_id)
    except Exception:
        logger.exception('Wikidata lookup failed for %s', latin)
        return []

    claims = entity.get('claims') or {}
    url = f'https://www.wikidata.org/wiki/{entity_id}'
    saved: list[SpeciesFact] = []

    mass_g = pick_adult_mass_g(claims.get(P_MASS) or [])
    if mass_g is not None:
        saved.append(
            upsert_fact(
                species,
                source=SpeciesFact.SOURCE_WIKIDATA,
                category='measurements',
                key='body_mass_g',
                value_text=str(round(mass_g, 2)),
                value_num=mass_g,
                source_url=url,
                license=WIKIDATA_LICENSE,
                attribution=WIKIDATA_ATTRIBUTION,
            )
        )
        # Drop legacy unitless key if present from older imports.
        SpeciesFact.objects.filter(
            species=species,
            source=SpeciesFact.SOURCE_WIKIDATA,
            key='body_mass',
        ).delete()

    length_mm = pick_length_mm(claims.get(P_LENGTH) or [])
    if length_mm is not None:
        saved.append(
            upsert_fact(
                species,
                source=SpeciesFact.SOURCE_WIKIDATA,
                category='measurements',
                key='body_length_mm',
                value_text=str(round(length_mm, 2)),
                value_num=length_mm,
                source_url=url,
                license=WIKIDATA_LICENSE,
                attribution=WIKIDATA_ATTRIBUTION,
            )
        )
        SpeciesFact.objects.filter(
            species=species,
            source=SpeciesFact.SOURCE_WIKIDATA,
            key='body_length',
        ).delete()

    iucn_claims = claims.get(P_IUCN) or []
    if iucn_claims:
        try:
            status_id = iucn_claims[0]['mainsnak']['datavalue']['value']['id']
        except (KeyError, TypeError, IndexError):
            status_id = None
        if status_id:
            saved.append(
                upsert_fact(
                    species,
                    source=SpeciesFact.SOURCE_WIKIDATA,
                    category='conservation',
                    key='iucn_status',
                    value_text=status_id,
                    source_url=url,
                    license=WIKIDATA_LICENSE,
                    attribution=WIKIDATA_ATTRIBUTION,
                )
            )

    return saved
