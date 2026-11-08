"""Trip prep content: which species a trip covers, and the JSON files that hold its texts.

Layout under ``jizz/trips/data/``:

- ``species/<ebird-code>.json``: ``look_for`` lines, shared by every country.
- ``groups/<group-slug>.json``: ``about`` and ``false_friend`` texts, shared by every country.
- ``<cc>/scope.json``: hand-made changes to the species list (``add``, ``drop``), ``first_day``,
  ``group_overrides`` and regional specialities.
- ``<cc>/units.json``: groups, units and the endemics units, written by ``trip_prep_units``.
- ``<cc>/texts.json``: ``here`` texts for groups and species, and the endemics chapter.
- ``lookalikes/<here>__<home>.json``: how to tell a local bird from a lookalike at home (for a
  European birder), shared by every country that lists the pair in ``scope.json``'s ``lookalikes``.

Texts are ``{"en": ..., "nl": ...}`` objects, like the courses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / 'data'
LOOKALIKES_DIR = DATA_DIR / 'lookalikes'

# Countries with Trip prep content, and the languages their texts exist in.
TRIPS: dict[str, dict] = {
    'LK': {'name': {'en': 'Sri Lanka', 'nl': 'Sri Lanka'}, 'languages': ('en', 'nl')},
    'SC': {'name': {'en': 'Seychelles', 'nl': 'Seychellen'}, 'languages': ('en', 'nl')},
    'UG': {'name': {'en': 'Uganda', 'nl': 'Oeganda'}, 'languages': ('en', 'nl')},
}

LANGUAGES = ('en', 'nl')

# Frequencies that count as "regular": the cut used for the main percentage.
REGULAR_FREQUENCIES = ('abundant', 'very_common', 'common', 'fairly_common', 'uncommon')
FREQUENCY_RANK = {name: rank for rank, name in enumerate(REGULAR_FREQUENCIES + ('rare', 'very_rare', 'vagrant'))}


@dataclass
class ScopeSpecies:
    species_id: int
    code: str
    name: str
    name_nl: str
    latin: str
    status: str
    frequency: str
    frequency_pct: float | None
    tax_ordering: float
    group_slug: str
    group_sort: int
    group_name: dict = field(default_factory=dict)

    @property
    def endemic(self) -> bool:
        return self.status == 'endemic'

    @property
    def commonness(self) -> tuple:
        """Sort key, commonest first. Endemics carry the fallback frequency 'rare', so they rank
        as 'uncommon' here."""
        freq = 'uncommon' if self.endemic and self.frequency not in REGULAR_FREQUENCIES else self.frequency
        return (FREQUENCY_RANK.get(freq, 99), -(self.frequency_pct or 0))


def country_dir(country: str) -> Path:
    return DATA_DIR / country.lower()


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_scope(country: str) -> dict:
    scope = read_json(country_dir(country) / 'scope.json', {}) or {}
    scope.setdefault('add', [])
    scope.setdefault('drop', [])
    scope.setdefault('first_day', [])
    scope.setdefault('group_overrides', {})
    scope.setdefault('regional_specialities', [])
    scope.setdefault('lookalikes', [])
    return scope


def lookalike_path(here: str, home: str) -> Path:
    return LOOKALIKES_DIR / f'{here}__{home}.json'


def home_codes(scope: dict, in_scope) -> list[str]:
    """Lookalike home birds that aren't in the trip itself: they need their own photos."""
    out = []
    for pair in scope.get('lookalikes', []):
        if pair['home'] not in in_scope and pair['home'] not in out:
            out.append(pair['home'])
    return out


def scope_species(country: str) -> list[ScopeSpecies]:
    """The species a trip to ``country`` covers, in taxonomic order.

    Native, endemic and introduced species from ``CountrySpecies``, regular ones only (abundant to
    uncommon) plus every endemic, then ``scope.json``'s ``add`` and ``drop`` (eBird codes).
    Species without an eBird group take the group of another species in their family.
    """
    from django.db.models import Q

    from jizz.models import CountrySpecies, Species

    scope = load_scope(country)
    regular = Q(status__in=('native', 'introduced'), frequency__in=REGULAR_FREQUENCIES) | Q(status='endemic')
    rows = list(
        CountrySpecies.objects.filter(country_id=country.upper())
        .filter(regular | Q(species__code__in=scope['add']))
        .exclude(species__code__in=scope['drop'])
        .select_related('species', 'species__species_group')
    )

    family_group = {}
    family_ids = {cs.species.taxonomic_family_id for cs in rows if cs.species.species_group_id is None}
    if family_ids:
        for sp in Species.objects.filter(taxonomic_family_id__in=family_ids, species_group__isnull=False).select_related(
            'species_group'
        ):
            family_group.setdefault(sp.taxonomic_family_id, sp.species_group)

    groups_by_slug = {}
    out = []
    for cs in rows:
        sp = cs.species
        group = sp.species_group or family_group.get(sp.taxonomic_family_id)
        override = scope['group_overrides'].get(sp.code)
        if override:
            from jizz.models import SpeciesGroup

            group = groups_by_slug.get(override) or SpeciesGroup.objects.get(slug=override)
        if group is None:
            raise ValueError(f'No species group for {sp.code} ({sp.name}); add one to group_overrides')
        groups_by_slug[group.slug] = group
        out.append(
            ScopeSpecies(
                species_id=sp.id,
                code=sp.code,
                name=sp.name,
                name_nl=sp.name_nl or sp.name,
                latin=sp.name_latin,
                status=cs.status,
                frequency=cs.frequency or '',
                frequency_pct=cs.frequency_pct,
                tax_ordering=sp.tax_ordering or 0,
                group_slug=group.slug,
                group_sort=group.sort_order,
                group_name={'en': group.name_en, 'nl': group.name_nl},
            )
        )
    out.sort(key=lambda s: s.tax_ordering)
    return out
