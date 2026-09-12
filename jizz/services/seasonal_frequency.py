"""Resolve year-round vs seasonal frequency for a game's CountrySpecies pool."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

from jizz.models import CountrySpecies, CountrySpeciesFrequency, Game
from jizz.playable_regions import best_frequency_tier, months_for_game


def _allowed_tiers(rarity: str) -> tuple[str, ...]:
    return Game.RARIT_FREQUENCY_TIERS.get(rarity, Game.RARIT_FREQUENCY_TIERS[Game.RARIT_REGULAR])


def _allows_unclassified(rarity: str) -> bool:
    return rarity in (Game.RARIT_REGULAR, Game.RARIT_EXCEPTIONAL)


def _tier_allowed(tier: str | None, rarity: str) -> bool:
    if not tier:
        return _allows_unclassified(rarity)
    return tier in _allowed_tiers(rarity)


def seasonal_tier_map(
    country_id: str | None,
    species_ids: Sequence[int],
    months: Iterable[int],
) -> dict[int, str | None]:
    """species_id → peak frequency tier across ``months`` (latest reference year)."""
    if not country_id or not species_ids:
        return {}
    month_set = {int(m) for m in months if 1 <= int(m) <= 12}
    if not month_set:
        return {}

    cs_rows = list(
        CountrySpecies.objects.filter(
            country_id=country_id,
            species_id__in=species_ids,
        ).values_list("id", "species_id", "frequency")
    )
    if not cs_rows:
        return {}
    cs_id_to_species = {cs_id: species_id for cs_id, species_id, _ in cs_rows}
    fallback = {species_id: frequency or None for _, species_id, frequency in cs_rows}

    grouped: dict[int, list[tuple[int, str | None, float | None]]] = defaultdict(list)
    for cs_id, month_tier, pct, year in CountrySpeciesFrequency.objects.filter(
        country_species_id__in=cs_id_to_species.keys(),
        month__in=month_set,
    ).values_list("country_species_id", "frequency", "frequency_pct", "reference_year"):
        grouped[cs_id].append((int(year or 0), month_tier, pct))

    out: dict[int, str | None] = dict(fallback)
    for cs_id, rows in grouped.items():
        species_id = cs_id_to_species.get(cs_id)
        if species_id is None:
            continue
        latest = max(year for year, _, _ in rows)
        latest_rows = [row for row in rows if row[0] == latest]
        max_pct = None
        for _, _, pct in latest_rows:
            if pct is None:
                continue
            if max_pct is None or pct > max_pct:
                max_pct = pct
        if max_pct is not None and max_pct <= 0:
            out[species_id] = "very_rare"
            continue
        tier = best_frequency_tier(tier for _, tier, _ in latest_rows)
        if tier:
            out[species_id] = tier
    return out


def filter_country_species_ids_for_game(game: Game, country_species_qs) -> list[int]:
    """Return CountrySpecies.species_id values that pass rarity (and season, if set)."""
    rarity = (
        Game.RARIT_EXCEPTIONAL
        if game.game_type == Game.GAME_TYPE_EXTREME
        else (game.rarity or Game.RARIT_REGULAR)
    )
    months = months_for_game(game)
    if not months:
        return list(
            country_species_qs.filter(Game.country_species_rarity_q(rarity)).values_list(
                "species_id", flat=True
            )
        )

    rows = list(country_species_qs.values_list("id", "species_id", "frequency"))
    if not rows:
        return []
    species_ids = [species_id for _, species_id, _ in rows]
    tier_map = seasonal_tier_map(game.country_id, species_ids, months)
    allowed: list[int] = []
    for _, species_id, year_round in rows:
        tier = tier_map.get(species_id, year_round)
        if _tier_allowed(tier, rarity):
            allowed.append(species_id)
    return allowed


def frequency_map_for_game(game: Game, species_ids: Sequence[int]) -> dict[int, str | None]:
    if not game.country_id or not species_ids:
        return {}
    months = months_for_game(game)
    if months:
        return seasonal_tier_map(game.country_id, species_ids, months)
    rows = CountrySpecies.objects.filter(
        country_id=game.country_id,
        species_id__in=species_ids,
    ).values_list("species_id", "frequency")
    return {species_id: frequency or None for species_id, frequency in rows}
