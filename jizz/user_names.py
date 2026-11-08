"""Helpers to keep usernames and player names free of email addresses."""

from __future__ import annotations

from django.contrib.auth import get_user_model


def strip_email_local_part(value: str) -> str:
    """Return the part before @, or the whole string if there is no @."""
    if not value:
        return ''
    value = value.strip()
    if '@' in value:
        value = value.split('@', 1)[0]
    return value.strip()


def sanitize_username(value: str, fallback: str = 'user') -> str:
    cleaned = strip_email_local_part(value)
    if not cleaned:
        cleaned = fallback
    return cleaned[:150]


def sanitize_player_name(value: str, fallback: str = 'Player') -> str:
    cleaned = strip_email_local_part(value)
    if not cleaned:
        cleaned = fallback
    return cleaned[:255]


def make_unique_username(base: str, *, exclude_user_id=None) -> str:
    User = get_user_model()
    base = sanitize_username(base) or 'user'
    username = base[:150]
    counter = 1
    use_space_suffix = ' ' in base
    while True:
        qs = User.objects.filter(username=username)
        if exclude_user_id is not None:
            qs = qs.exclude(pk=exclude_user_id)
        if not qs.exists():
            return username
        suffix = f' {counter}' if use_space_suffix else f'_{counter}'
        username = (base[: 150 - len(suffix)] + suffix).strip()
        counter += 1


def username_from_oauth(
    *,
    first_name: str = '',
    last_name: str = '',
    full_name: str = '',
    email: str = '',
    exclude_user_id=None,
) -> str:
    """Build a display username for Google/Apple sign-in."""
    full = (full_name or '').strip()
    if not full:
        parts = [(first_name or '').strip(), (last_name or '').strip()]
        full = ' '.join(part for part in parts if part).strip()
    if full:
        base = sanitize_username(full, fallback='')
    elif email:
        base = sanitize_username(email.split('@', 1)[0], fallback='user')
    else:
        base = 'user'
    return make_unique_username(base, exclude_user_id=exclude_user_id)


def player_name_for_user(user, fallback: str = 'Player') -> str:
    """The name other players see. The username is what the profile page and
    both apps call the player name, so it wins over first + last name."""
    if not user:
        return fallback
    username = sanitize_player_name((getattr(user, 'username', None) or '').strip(), fallback='')
    if username:
        return username
    full = user.get_full_name().strip()
    if full:
        return sanitize_player_name(full)
    email = (getattr(user, 'email', None) or '').strip()
    if email:
        return sanitize_player_name(email)
    return fallback


def sync_player_names(user, name: str | None = None) -> int:
    """Rename every Player linked to ``user`` so past games, league rows and
    leaderboards show the new player name. Returns the number of rows changed."""
    from jizz.models import Player

    if not user or not getattr(user, 'pk', None):
        return 0
    new_name = sanitize_player_name(name if name is not None else user.username)
    return Player.objects.filter(user=user).exclude(name=new_name).update(name=new_name)
