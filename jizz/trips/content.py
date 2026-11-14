"""Trip prep content: which species a trip covers, and the JSON files that hold its texts.

Layout under ``jizz/trips/data/``:

- ``species/<ebird-code>.json``: ``look_for`` lines, shared by every country.
- ``groups/<group-slug>.json``: ``about`` and ``false_friend`` texts, shared by every country.
- ``<cc>/scope.json``: hand-made changes to the species list (``add``, ``drop``), ``first_day``,
  ``group_overrides`` and regional specialities.
- ``<cc>-<region>/``: a region pack, the same files as a country (see ``is_region``). Its species
  are hand-picked in ``scope.json`` (``"manual": true``) and never repeat the country's own.
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
    'CR': {'name': {'en': 'Costa Rica', 'nl': 'Costa Rica'}, 'languages': ('en', 'nl')},
    'MA': {'name': {'en': 'Morocco', 'nl': 'Marokko'}, 'languages': ('en', 'nl')},
    'DO': {'name': {'en': 'Dominican Republic', 'nl': 'Dominicaanse Republiek'}, 'languages': ('en', 'nl')},
    'NZ': {'name': {'en': 'New Zealand', 'nl': 'Nieuw-Zeeland'}, 'languages': ('en', 'nl')},
    'AU': {'name': {'en': 'Australia', 'nl': 'Australië'}, 'languages': ('en', 'nl')},
    'AU-WETTROPICS': {
        'name': {'en': 'Wet Tropics and Cape York', 'nl': 'Wet Tropics en Kaap York'},
        'languages': ('en', 'nl'),
        'parent': 'AU',
    },
    'AU-TOPEND': {
        'name': {'en': 'Top End and Kimberley', 'nl': 'Top End en Kimberley'},
        'languages': ('en', 'nl'),
        'parent': 'AU',
    },
    'AU-REDCENTRE': {
        'name': {'en': 'Red Centre and outback', 'nl': 'Rode Centrum en outback'},
        'languages': ('en', 'nl'),
        'parent': 'AU',
    },
    'AU-SOUTHWEST': {
        'name': {'en': 'South-west', 'nl': 'Zuidwest'},
        'languages': ('en', 'nl'),
        'parent': 'AU',
    },
    'AU-TASMANIA': {
        'name': {'en': 'Tasmania', 'nl': 'Tasmanië'},
        'languages': ('en', 'nl'),
        'parent': 'AU',
    },
    'AU-SOUTHEAST': {
        'name': {'en': 'South-east heath and mallee', 'nl': 'Zuidoost: heide en mallee'},
        'languages': ('en', 'nl'),
        'parent': 'AU',
    },
    'ES': {'name': {'en': 'Spain', 'nl': 'Spanje'}, 'languages': ('en', 'nl')},
    'ES-CANARIES': {
        'name': {'en': 'Canary Islands', 'nl': 'Canarische Eilanden'},
        'languages': ('en', 'nl'),
        'parent': 'ES',
    },
    'TH': {'name': {'en': 'Thailand', 'nl': 'Thailand'}, 'languages': ('en', 'nl')},
    'ZA': {'name': {'en': 'South Africa', 'nl': 'Zuid-Afrika'}, 'languages': ('en', 'nl')},
    'KH': {'name': {'en': 'Cambodia', 'nl': 'Cambodja'}, 'languages': ('en', 'nl')},
    'CO': {'name': {'en': 'Colombia', 'nl': 'Colombia'}, 'languages': ('en', 'nl')},
    'CO-CARIBBEAN': {
        'name': {'en': 'Caribbean coast and Santa Marta', 'nl': 'Caribische kust en Santa Marta'},
        'languages': ('en', 'nl'),
        'parent': 'CO',
    },
    'CO-CHOCO': {
        'name': {'en': 'Chocó and the Western Andes', 'nl': 'Chocó en de Westelijke Andes'},
        'languages': ('en', 'nl'),
        'parent': 'CO',
    },
    'CO-ANDES': {
        'name': {'en': 'Central and Eastern Andes', 'nl': 'Centrale en Oostelijke Andes'},
        'languages': ('en', 'nl'),
        'parent': 'CO',
    },
    'CO-AMAZON': {
        'name': {'en': 'Amazon', 'nl': 'Amazone'},
        'languages': ('en', 'nl'),
        'parent': 'CO',
    },
    'CO-LLANOS': {
        'name': {'en': 'Llanos', 'nl': 'Llanos'},
        'languages': ('en', 'nl'),
        'parent': 'CO',
    },
    'CR-CARIBBEAN': {
        'name': {'en': 'Caribbean lowlands', 'nl': 'Caribisch laagland'},
        'languages': ('en', 'nl'),
        'parent': 'CR',
    },
    'CR-HIGHLANDS': {
        'name': {'en': 'Highlands', 'nl': 'Hooglanden'},
        'languages': ('en', 'nl'),
        'parent': 'CR',
    },
    'CR-SOUTHPACIFIC': {
        'name': {'en': 'South Pacific', 'nl': 'Zuid-Pacific'},
        'languages': ('en', 'nl'),
        'parent': 'CR',
    },
    'CR-NORTHPACIFIC': {
        'name': {'en': 'North Pacific', 'nl': 'Noord-Pacific'},
        'languages': ('en', 'nl'),
        'parent': 'CR',
    },
    'BALTICS': {
        'name': {'en': 'Baltics', 'nl': 'Baltische staten'},
        'languages': ('en', 'nl'),
        'countries': ['EE', 'LV', 'LT'],
    },
}

LANGUAGES = ('en', 'nl')


def db_country(trip: str) -> str:
    """The country behind a trip id: ``CR`` for ``CR`` and for the region pack ``CR-CARIBBEAN``."""
    return trip.upper().split('-')[0]


def trip_countries(trip: str) -> list[str]:
    """The countries whose birds a trip covers: one, except for a trip that spans several
    (``BALTICS`` lists ``countries`` in ``TRIPS``)."""
    return list(TRIPS.get(trip.upper(), {}).get('countries') or [db_country(trip)])


def is_region(trip: str) -> bool:
    """A region pack: extra birds for one part of a country, on top of the country's own trip."""
    return '-' in trip


def parent_trip(trip: str) -> str | None:
    return db_country(trip) if is_region(trip) else None


def region_ids(country: str) -> list[str]:
    """The published region packs of a country, in the order of ``TRIPS``."""
    return [code for code, meta in TRIPS.items() if meta.get('parent') == country]

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
    # A region pack lists its species by hand: the country's frequency cut doesn't apply.
    scope.setdefault('manual', is_region(country))
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


def parent_codes(trip: str) -> list[str]:
    """The species of the country trip behind a region pack (from its units.json)."""
    parent = parent_trip(trip)
    units = read_json(country_dir(parent) / 'units.json') if parent else None
    return [c for g in (units or {}).get('groups', []) for c in g['species']]


def scope_species(country: str) -> list[ScopeSpecies]:
    """The species a trip to ``country`` covers, in taxonomic order.

    Native, endemic and introduced species from ``CountrySpecies``, regular ones only (abundant to
    uncommon) plus every endemic, then ``scope.json``'s ``add`` and ``drop`` (eBird codes).
    A region pack (``CR-CARIBBEAN``) takes only its ``add`` list, minus the birds the country's own
    trip already has. Species without an eBird group take the group of another species in their
    family.
    """
    from django.db.models import Q

    from jizz.models import CountrySpecies, Species

    scope = load_scope(country)
    if scope['manual']:
        wanted = Q(species__code__in=scope['add'])
        own = set(parent_codes(country))
        rows = list(
            CountrySpecies.objects.filter(country_id__in=trip_countries(country))
            .filter(wanted)
            .exclude(species__code__in=list(scope['drop']) + sorted(own))
            .select_related('species', 'species__species_group')
        )
    else:
        regular = Q(status__in=('native', 'introduced'), frequency__in=REGULAR_FREQUENCIES) | Q(status='endemic')
        rows = list(
            CountrySpecies.objects.filter(country_id__in=trip_countries(country))
            .filter(regular | Q(species__code__in=scope['add']))
            .exclude(species__code__in=scope['drop'])
            .select_related('species', 'species__species_group')
        )

    # A trip over several countries: a bird on more than one list counts once, at its commonest.
    best: dict[int, object] = {}
    for cs in rows:
        cur = best.get(cs.species_id)
        if cur is None or (FREQUENCY_RANK.get(cs.frequency, 99), -(cs.frequency_pct or 0)) < (
            FREQUENCY_RANK.get(cur.frequency, 99),
            -(cur.frequency_pct or 0),
        ):
            best[cs.species_id] = cs
    rows = list(best.values())

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
