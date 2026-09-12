"""
Sync rematch logic for multiplayer games. Used by the WebSocket consumer.
Testable without async/WebSocket.
"""
from jizz.models import Game, Player


def create_rematch_game(game_token: str, player_token: str) -> tuple:
    """
    Create a new game with the same specs as the given game (rematch).
    Caller must be the host of the existing game.
    Returns (new_game, player).
    Raises ValueError if player is not the host.
    Raises Game.DoesNotExist or Player.DoesNotExist if not found.
    """
    player = Player.objects.get(token=player_token)
    old_game = Game.objects.get(token=game_token)
    if old_game.host_id != player.id:
        raise ValueError("Only the host can start a rematch")
    new_game = Game.objects.create(
        country=old_game.country,
        level=old_game.level,
        length=old_game.length,
        media=old_game.media,
        host=player,
        multiplayer=old_game.multiplayer,
        rarity=old_game.rarity,
        include_escapes=old_game.include_escapes,
        dificult_species=old_game.dificult_species,
        game_type=old_game.game_type,
        speed_seconds=old_game.speed_seconds,
        tax_order=old_game.tax_order or "",
        tax_family=old_game.tax_family or "",
        species_group=old_game.species_group or "",
        season=old_game.season or "",
        language=old_game.language or "en",
        repeat=old_game.repeat,
    )
    return new_game, player
