"""App Store in-app event images for the National League.

    python3 marketing/app-store-events/make_league.py

Writes league-card-1920x1080.png and league-details-1080x1920.png next to this file.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'store-screenshots'))
from make import font, rounded, wrap  # noqa: E402

ROOT = HERE.parent
BROWN = (92, 56, 20)
OCHRE = (200, 116, 42)
DARK = (16, 32, 27)


def gradient(size):
    w, h = size
    top, bottom = (246, 238, 222), (214, 186, 136)
    im = Image.new('RGB', size)
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return im.convert('RGBA')


def phone(width, crop_ratio=1.9, angle=0):
    shot = Image.open(ROOT / 'screenshots' / 'league.png').convert('RGB')
    shot = shot.crop((0, 0, shot.width, int(shot.width * crop_ratio)))
    shot = shot.resize((width, int(shot.height * width / shot.width)), Image.LANCZOS)
    bezel = max(10, width // 28)
    frame = Image.new('RGBA', (shot.width + 2 * bezel, shot.height + 2 * bezel), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle([0, 0, frame.width - 1, frame.height - 1], radius=width // 7, fill=DARK + (255,))
    frame.alpha_composite(rounded(shot, width // 8).convert('RGBA'), (bezel, bezel))
    if angle:
        frame = frame.rotate(angle, resample=Image.BICUBIC, expand=True)
    shadow = Image.new('RGBA', (frame.width + 120, frame.height + 120), (0, 0, 0, 0))
    shadow.paste((60, 35, 10, 110), (60, 70), frame.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    shadow.alpha_composite(frame, (60, 60))
    return shadow


def tody(height):
    im = Image.open(ROOT / 'tody' / 'cutout' / 'tody-champion.png').convert('RGBA')
    return im.resize((int(im.width * height / im.height), height), Image.LANCZOS)


def text_block(canvas, xy, lines, fnt, fill, max_w, gap=1.15):
    d = ImageDraw.Draw(canvas)
    x, y = xy
    for para in lines:
        for ln in wrap(d, para, fnt, max_w):
            d.text((x, y), ln, font=fnt, fill=fill)
            y += int(fnt.size * gap)
    return y


def card():
    c = gradient((1920, 1080))
    p = phone(420, angle=-6)
    c.alpha_composite(p, (1240, 40))
    t = tody(700)
    c.alpha_composite(t, (780, 1080 - t.height + 20))
    d = ImageDraw.Draw(c)
    d.text((110, 130), 'National League', font=font('Baloo2.ttf', 140, 800), fill=BROWN)
    d.text((114, 290), 'Win the week', font=font('Baloo2.ttf', 96, 800), fill=OCHRE)
    text_block(c, (114, 480), ['One daily quiz.', 'Your whole country.', 'Same birds for everyone.'], font('Figtree.ttf', 58, 600), BROWN, 700)
    return c.convert('RGB')


def details():
    c = gradient((1080, 1920))
    t = tody(640)
    c.alpha_composite(t, ((1080 - t.width) // 2, 40))
    p = phone(560, crop_ratio=1.14)
    c.alpha_composite(p, ((1080 - p.width) // 2, 620))
    d = ImageDraw.Draw(c)
    d.text((540, 1640), 'National League', font=font('Baloo2.ttf', 110, 800), fill=BROWN, anchor='mm')
    d.text((540, 1765), 'One quiz a day. Win the week.', font=font('Figtree.ttf', 52, 700), fill=OCHRE, anchor='mm')
    return c.convert('RGB')


if __name__ == '__main__':
    card().save(HERE / 'league-card-1920x1080.png')
    details().save(HERE / 'league-details-1080x1920.png')
