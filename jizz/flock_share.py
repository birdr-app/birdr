"""Generate Open Graph share cards for flock challenge leaderboards."""

from __future__ import annotations

import io
from datetime import timedelta
from pathlib import Path
from typing import Sequence

from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont


OG_WIDTH = 1200
OG_HEIGHT = 630

# Motmot primary / birdr palette (app/src/theme.ts)
BIRDR_50 = '#f5ede0'
BIRDR_100 = '#e8d4b8'
BIRDR_200 = '#d4b88a'
BIRDR_500 = '#8b6419'
BIRDR_600 = '#6d4e14'
BIRDR_800 = '#31220a'


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
            ]
        )
    else:
        candidates.extend(
            [
                '/System/Library/Fonts/Supplemental/Arial.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            ]
        )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _art_path(*filenames: str) -> Path | None:
    # settings.BASE_DIR is the inner `jizz/` package directory.
    package_dir = Path(settings.BASE_DIR)
    project_root = package_dir.parent
    directories = [
        project_root / 'app' / 'public' / 'images',
        project_root / 'mobile' / 'assets',
        project_root / 'mobile' / 'public' / 'images',
        package_dir / 'static' / 'images',
        project_root / 'static' / 'images',
    ]
    for directory in directories:
        for name in filenames:
            path = directory / name
            if path.is_file():
                return path
    return None


def _load_art(
    filenames: Sequence[str],
    max_size: tuple[int, int] = (280, 280),
) -> Image.Image | None:
    path = _art_path(*filenames)
    if not path:
        return None
    try:
        art = Image.open(path).convert('RGBA')
        art.thumbnail(max_size, Image.Resampling.LANCZOS)
        return art
    except Exception:
        return None


def _load_leaderboard_art(max_size: tuple[int, int] = (280, 280)) -> Image.Image | None:
    return _load_art(('birdr-leaderboard.png',), max_size)


def _paste_rgba(img: Image.Image, overlay: Image.Image, xy: tuple[int, int]) -> Image.Image:
    base = img.convert('RGBA')
    base.paste(overlay, xy, overlay)
    return base.convert('RGB')


def _truncate(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    text = text or ''
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    ellipsis = '…'
    while text and draw.textbbox((0, 0), text + ellipsis, font=font)[2] > max_width:
        text = text[:-1]
    return (text + ellipsis) if text else ellipsis


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def _load_logo(flock) -> Image.Image | None:
    if not flock.logo:
        return None
    try:
        img = Image.open(flock.logo.path).convert('RGBA')
        img.thumbnail((120, 120), Image.Resampling.LANCZOS)
        return img
    except Exception:
        return None


def _countdown_label(ends_at) -> str:
    now = timezone.now()
    if ends_at is None or ends_at <= now:
        return 'Ended'
    remaining = ends_at - now
    if remaining > timedelta(days=1):
        days = remaining.days
        hours = remaining.seconds // 3600
        return f'{days}d {hours:02d}h left'
    total_sec = int(remaining.total_seconds())
    hours = total_sec // 3600
    mins = (total_sec % 3600) // 60
    return f'{hours:02d}:{mins:02d} left'


def render_challenge_og_image(
    *,
    flock,
    challenge,
    top_entries: Sequence[dict],
    participant_count: int,
) -> bytes:
    """Return PNG bytes for a 1200×630 flock challenge leaderboard card."""
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), BIRDR_50)
    draw = ImageDraw.Draw(img)

    # Soft brand panels
    draw.rectangle((0, 0, OG_WIDTH, 210), fill=BIRDR_100)
    draw.rounded_rectangle((48, 248, OG_WIDTH - 48, 540), radius=24, fill='#ffffff')
    draw.rounded_rectangle(
        (48, 248, OG_WIDTH - 48, 540),
        radius=24,
        outline=BIRDR_200,
        width=3,
    )

    brand = _font(28, bold=True)
    title = _font(50, bold=True)
    countdown_font = _font(64, bold=True)
    subtitle = _font(30)
    row_font = _font(32, bold=True)
    meta = _font(26)

    draw.text((56, 28), 'BIRDR', fill=BIRDR_500, font=brand)

    art = _load_leaderboard_art((220, 220))
    logo = _load_logo(flock)
    text_x = 56
    header_y = 78

    if art:
        ax = OG_WIDTH - art.width - 56
        ay = max(24, (210 - art.height) // 2)
        base = img.convert('RGBA')
        base.paste(art, (ax, ay), art)
        img = base.convert('RGB')
        draw = ImageDraw.Draw(img)

    if logo:
        lx, ly = 56, header_y
        plate = Image.new('RGBA', (logo.width + 16, logo.height + 16), (255, 255, 255, 240))
        base = img.convert('RGBA')
        base.paste(plate, (lx - 8, ly - 8), plate)
        base.paste(logo, (lx, ly), logo)
        img = base.convert('RGB')
        draw = ImageDraw.Draw(img)
        text_x = lx + logo.width + 24

    name = (flock.name or 'Flock')[:36]
    draw.text((text_x, header_y + 18), name, fill=BIRDR_800, font=title)

    countdown = _countdown_label(getattr(challenge, 'ends_at', None))
    bbox = draw.textbbox((0, 0), countdown, font=countdown_font)
    cw = bbox[2] - bbox[0]
    # Keep countdown clear of the art on the right
    max_right = OG_WIDTH - (art.width + 80 if art else 56)
    cx = min(max(56, (OG_WIDTH - cw) // 2), max(56, max_right - cw))
    draw.text((cx, 155), countdown, fill=BIRDR_500, font=countdown_font)

    y = 278
    if top_entries:
        for entry in top_entries[:5]:
            rank = entry.get('rank', '')
            display = (entry.get('display_name') or 'Player')[:28]
            score = entry.get('score_label') or ''
            left = f'#{rank}  {display}'
            draw.text((80, y), left, fill=BIRDR_800, font=row_font)
            bbox = draw.textbbox((0, 0), score, font=row_font)
            sw = bbox[2] - bbox[0]
            draw.text((OG_WIDTH - 80 - sw, y), score, fill=BIRDR_500, font=row_font)
            y += 42
    else:
        draw.text(
            (80, y + 40),
            'No scores yet — be the first to play!',
            fill=BIRDR_600,
            font=subtitle,
        )

    footer = 'Join the challenge on Motmot'
    if participant_count:
        footer = f'{participant_count} played · {footer}'
    draw.text((56, OG_HEIGHT - 62), footer, fill=BIRDR_600, font=meta)

    return _png_bytes(img)


def render_flock_result_og_image(
    *,
    flock,
    display_name: str,
    score_label: str,
    rank_label: str = '',
) -> bytes:
    """Return PNG bytes for a 1200×630 flock challenge result card."""
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), BIRDR_50)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, OG_WIDTH, 210), fill=BIRDR_100)
    draw.rounded_rectangle((48, 248, OG_WIDTH - 48, 540), radius=24, fill='#ffffff')
    draw.rounded_rectangle(
        (48, 248, OG_WIDTH - 48, 540),
        radius=24,
        outline=BIRDR_200,
        width=3,
    )

    brand = _font(28, bold=True)
    title = _font(50, bold=True)
    name_font = _font(36, bold=True)
    score_font = _font(92, bold=True)
    rank_font = _font(36, bold=True)
    meta = _font(26)

    draw.text((56, 28), 'BIRDR', fill=BIRDR_500, font=brand)

    art = _load_art(('birdr-leaderboard.png', 'birdr-success.png'), (220, 220))
    if art:
        ax = OG_WIDTH - art.width - 56
        ay = max(24, (210 - art.height) // 2)
        img = _paste_rgba(img, art, (ax, ay))
        draw = ImageDraw.Draw(img)

    flock_logo = _load_logo(flock)
    text_x = 56
    if flock_logo:
        lx, ly = 56, 78
        plate = Image.new(
            'RGBA',
            (flock_logo.width + 16, flock_logo.height + 16),
            (255, 255, 255, 240),
        )
        img = _paste_rgba(img, plate, (lx - 8, ly - 8))
        img = _paste_rgba(img, flock_logo, (lx, ly))
        draw = ImageDraw.Draw(img)
        text_x = lx + flock_logo.width + 24

    max_title = OG_WIDTH - text_x - (art.width + 80 if art else 56)
    draw.text(
        (text_x, 96),
        _truncate(draw, (flock.name if flock else None) or 'Flock', title, max_title),
        fill=BIRDR_800,
        font=title,
    )

    player = _truncate(draw, display_name or 'Player', name_font, OG_WIDTH - 160)
    draw.text((80, 278), player, fill=BIRDR_800, font=name_font)
    draw.text((80, 330), score_label or '', fill=BIRDR_500, font=score_font)
    if rank_label:
        draw.text((80, 440), rank_label, fill=BIRDR_800, font=rank_font)

    draw.text((56, OG_HEIGHT - 62), 'Can you beat this score on Motmot?', fill=BIRDR_600, font=meta)
    return _png_bytes(img)


def render_game_result_og_image(
    *,
    country_name: str,
    subtitle: str,
    players: Sequence[dict],
) -> bytes:
    """Return PNG bytes for a 1200×630 public game result card."""
    img = Image.new('RGB', (OG_WIDTH, OG_HEIGHT), BIRDR_50)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, OG_WIDTH, 210), fill=BIRDR_100)
    draw.rounded_rectangle((48, 248, OG_WIDTH - 48, 540), radius=24, fill='#ffffff')
    draw.rounded_rectangle(
        (48, 248, OG_WIDTH - 48, 540),
        radius=24,
        outline=BIRDR_200,
        width=3,
    )

    brand = _font(28, bold=True)
    title = _font(50, bold=True)
    subtitle_font = _font(28)
    row_font = _font(32, bold=True)
    meta = _font(26)
    hero_score = _font(92, bold=True)
    hero_name = _font(36, bold=True)

    draw.text((56, 28), 'BIRDR', fill=BIRDR_500, font=brand)

    art = _load_art(('birdr-success.png', 'birdr-leaderboard.png'), (220, 220))
    if art:
        ax = OG_WIDTH - art.width - 56
        ay = max(24, (210 - art.height) // 2)
        img = _paste_rgba(img, art, (ax, ay))
        draw = ImageDraw.Draw(img)

    max_title = OG_WIDTH - (art.width + 140 if art else 112)
    draw.text(
        (56, 86),
        _truncate(draw, country_name or 'Motmot quiz', title, max_title),
        fill=BIRDR_800,
        font=title,
    )
    draw.text(
        (56, 148),
        _truncate(draw, subtitle or '', subtitle_font, max_title),
        fill=BIRDR_600,
        font=subtitle_font,
    )

    entries = list(players)[:5]
    if len(entries) == 1:
        entry = entries[0]
        name = _truncate(draw, entry.get('name') or 'Player', hero_name, OG_WIDTH - 160)
        score = entry.get('score_label') or ''
        draw.text((80, 286), name, fill=BIRDR_800, font=hero_name)
        draw.text((80, 338), score, fill=BIRDR_500, font=hero_score)
        extra = entry.get('correct_label') or ''
        if extra:
            draw.text((80, 450), extra, fill=BIRDR_600, font=row_font)
    elif entries:
        y = 278
        for entry in entries:
            rank = entry.get('rank', '')
            display = _truncate(draw, entry.get('name') or 'Player', row_font, 640)
            left = f'#{rank}  {display}'
            draw.text((80, y), left, fill=BIRDR_800, font=row_font)
            score = entry.get('score_label') or ''
            bbox = draw.textbbox((0, 0), score, font=row_font)
            sw = bbox[2] - bbox[0]
            draw.text((OG_WIDTH - 80 - sw, y), score, fill=BIRDR_500, font=row_font)
            y += 42
    else:
        draw.text((80, 330), 'No scores yet', fill=BIRDR_600, font=row_font)

    draw.text((56, OG_HEIGHT - 62), 'Play on birdr.pro', fill=BIRDR_600, font=meta)
    return _png_bytes(img)
