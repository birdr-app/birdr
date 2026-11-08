"""Turn a trip's species into groups and units.

A unit holds 4-7 species. Large groups are split in taxonomic order, so lookalikes stay together.
Small groups are joined with their taxonomic neighbours. Within a unit the commonest birds come
first. Endemics stay in their group's unit and also get units of their own for the endemics
chapter.
"""

from __future__ import annotations

import math
from itertools import groupby

from jizz.trips.content import LANGUAGES, ScopeSpecies

MIN_UNIT = 4
MAX_UNIT = 7
ENDEMIC_UNIT = 6
FIRST_DAY_SIZE = 20


def split_evenly(items: list, max_size: int) -> list[list]:
    """Split into the fewest chunks of at most ``max_size``, as equal as possible, keeping order."""
    if not items:
        return []
    parts = math.ceil(len(items) / max_size)
    base, extra = divmod(len(items), parts)
    out, start = [], 0
    for i in range(parts):
        size = base + (1 if i < extra else 0)
        out.append(items[start : start + size])
        start += size
    return out


def _join_names(names: list[str], lang: str) -> str:
    if len(names) == 1:
        return names[0]
    joiner = {'en': ' and ', 'nl': ' en '}.get(lang, ' & ')
    return ', '.join(names[:-1]) + joiner + names[-1]


def _unit(slug: str, groups: list[list[ScopeSpecies]]) -> dict:
    species = [s for group in groups for s in group]
    species.sort(key=lambda s: s.commonness)
    title = {lang: _join_names([g[0].group_name.get(lang) or g[0].group_name['en'] for g in groups], lang) for lang in LANGUAGES}
    return {
        'slug': slug,
        'title': title,
        'groups': [g[0].group_slug for g in groups],
        'species': [s.code for s in species],
    }


def build_units(species: list[ScopeSpecies], first_day: list[str] | None = None, region: bool = False) -> dict:
    """Groups, units, the first day and the endemics units. A region pack (``region=True``) has no
    first day and no endemics chapter of its own: those belong to the country's trip."""
    by_group = []
    for _, members in groupby(sorted(species, key=lambda s: (s.group_sort, s.tax_ordering)), key=lambda s: s.group_slug):
        by_group.append(list(members))

    groups = [
        {
            'slug': members[0].group_slug,
            'name': members[0].group_name,
            'species': [s.code for s in members],
            'endemics': [s.code for s in members if s.endemic],
        }
        for members in by_group
    ]

    # Plan units: a big group splits; small groups pool with their neighbours.
    planned: list[list[list[ScopeSpecies]]] = []
    pending: list[list[ScopeSpecies]] = []

    def pending_size():
        return sum(len(g) for g in pending)

    def flush():
        if pending:
            planned.append(list(pending))
            pending.clear()

    for members in by_group:
        if len(members) >= MIN_UNIT:
            flush()
            for chunk in split_evenly(members, MAX_UNIT):
                planned.append([chunk])
            continue
        if pending_size() + len(members) > MAX_UNIT:
            flush()
        pending.append(members)
        if pending_size() >= MIN_UNIT:
            flush()
    flush()

    # A pool of one or two species joins a neighbouring unit when that stays within the limit.
    merged: list[list[list[ScopeSpecies]]] = []
    for unit in planned:
        size = sum(len(g) for g in unit)
        if size < MIN_UNIT - 1 and merged and sum(len(g) for g in merged[-1]) + size <= MAX_UNIT:
            merged[-1].extend(unit)
        else:
            merged.append(unit)
    if len(merged) > 1 and sum(len(g) for g in merged[0]) < MIN_UNIT - 1:
        if sum(len(g) for g in merged[0]) + sum(len(g) for g in merged[1]) <= MAX_UNIT:
            merged[1] = merged[0] + merged[1]
            merged.pop(0)

    units = []
    seen_slugs: dict[str, int] = {}
    for unit in merged:
        base = unit[0][0].group_slug
        seen_slugs[base] = seen_slugs.get(base, 0) + 1
        units.append(_unit(f'{base}-{seen_slugs[base]}' if seen_slugs[base] > 1 or _splits(unit, by_group) else base, unit))

    endemics = [] if region else [s for s in species if s.endemic]
    endemic_units = [
        {'slug': f'endemics-{i + 1}', 'species': [s.code for s in chunk]}
        for i, chunk in enumerate(split_evenly(endemics, ENDEMIC_UNIT))
    ]

    codes = {s.code for s in species}
    if region:
        day = []
    elif first_day:
        day = [c for c in first_day if c in codes]
    else:
        day = [s.code for s in sorted(species, key=lambda s: s.commonness)[:FIRST_DAY_SIZE]]

    return {'groups': groups, 'first_day': day, 'units': units, 'endemic_units': endemic_units}


def _splits(unit, by_group) -> bool:
    """True when this unit is one part of a group that was split."""
    if len(unit) != 1:
        return False
    slug = unit[0][0].group_slug
    full = next(len(g) for g in by_group if g[0].group_slug == slug)
    return full > len(unit[0])
