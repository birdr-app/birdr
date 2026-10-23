"""Resolve CountrySpecies.frequency for a species in a game's country scope."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from jizz.models import Game


def country_codes_for_game(game: Game) -> list[str]:
    """App country PKs to check for frequency (game country + ``Country.codes`` aliases)."""
    if not game or not game.country_id:
        return []
    codes: list[str] = [game.country_id]
    country = getattr(game, 'country', None)
    if country is None:
        from jizz.models import Country

        country = Country.objects.filter(pk=game.country_id).first()
    if country and country.codes:
        for part in country.codes.split(','):
            part = part.strip()
            if part and part not in codes:
                codes.append(part)
    return codes


def species_frequency_for_game(game: Game, species_id: int) -> Optional[str]:
    from jizz.models import CountrySpecies

    from jizz.request_memo import memo

    primed = (memo() or {}).get('species_frequency', {}).get(game.country_id, {})
    if species_id in primed:
        return primed[species_id]
    for country_code in country_codes_for_game(game):
        freq = (
            CountrySpecies.objects.filter(
                country_id=country_code,
                species_id=species_id,
            )
            .values_list('frequency', flat=True)
            .first()
        )
        if freq:
            return freq
    return None
