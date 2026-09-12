"""Optional app version / device type sent when starting or joining a game."""

from __future__ import annotations

from typing import Any

APP_VERSION_MAX = 32
DEVICE_TYPES = {'ios', 'android', 'web'}
DEVICE_ALIASES = {
    'ios': 'ios',
    'iphone': 'ios',
    'ipad': 'ios',
    'android': 'android',
    'web': 'web',
    'browser': 'web',
}


def normalize_app_version(value: Any) -> str:
    if value is None:
        return ''
    return str(value).strip()[:APP_VERSION_MAX]


def normalize_device_type(value: Any) -> str:
    if value is None:
        return ''
    key = str(value).strip().lower()
    return DEVICE_ALIASES.get(key, '')


def client_info_from_mapping(data: Any) -> tuple[str, str]:
    if not isinstance(data, dict):
        return '', ''
    version = normalize_app_version(data.get('app_version') or data.get('appVersion'))
    device = normalize_device_type(
        data.get('device_type') or data.get('deviceType') or data.get('platform')
    )
    return version, device


def client_info_from_request(request) -> tuple[str, str]:
    version, device = '', ''
    data = getattr(request, 'data', None)
    if data is not None:
        version, device = client_info_from_mapping(data)
    meta = getattr(request, 'META', None) or {}
    if not version:
        version = normalize_app_version(
            meta.get('HTTP_X_APP_VERSION') or meta.get('HTTP_X_BIRDR_APP_VERSION')
        )
    if not device:
        device = normalize_device_type(
            meta.get('HTTP_X_PLATFORM')
            or meta.get('HTTP_X_BIRDR_DEVICE_TYPE')
            or meta.get('HTTP_X_BIRDR_PLATFORM')
        )
    return version, device


def apply_player_score_client(player_score, app_version: str = '', device_type: str = '') -> None:
    updates = []
    if app_version and player_score.app_version != app_version:
        player_score.app_version = app_version
        updates.append('app_version')
    if device_type and player_score.device_type != device_type:
        player_score.device_type = device_type
        updates.append('device_type')
    if updates:
        player_score.save(update_fields=updates)


def record_player_score_client(
    player, game, app_version: str = '', device_type: str = ''
):
    from jizz.models import PlayerScore

    defaults: dict[str, Any] = {'score': 0}
    if app_version:
        defaults['app_version'] = app_version
    if device_type:
        defaults['device_type'] = device_type
    player_score, created = PlayerScore.objects.get_or_create(
        player=player, game=game, defaults=defaults
    )
    if not created:
        apply_player_score_client(player_score, app_version, device_type)
    return player_score


def record_player_score_client_from_request(player, game, request) -> None:
    app_version, device_type = client_info_from_request(request)
    record_player_score_client(player, game, app_version, device_type)
