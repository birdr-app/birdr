"""App Store product page header (iOS 27+): 3840x1646, no text, no alpha.

    python3 marketing/store-screenshots/app_store_header.py

Writes out/appstore/header-3840x1646.png and header-safe-area.png (the same with Apple's
safe area x 1097-2743, y 493-1154 drawn on, for checking). The header has no text, so one
image serves every localization. Tody is cut from the full-size masters, since the cutouts
in marketing/tody/cutout/ are only 768px.
"""
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from make import ROOT, background

sys.path.insert(0, str(ROOT / 'tody'))
from cutout import background_mask  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out' / 'appstore'
W, H = 3840, 1646
SAFE = (1097, 493, 2743, 1154)


def tody(name, height, flip=False):
    im = Image.open(ROOT / 'tody' / 'masters' / f'{name}.png').convert('RGBA')
    mask = background_mask(im).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(mask)
    im = im.crop(im.getbbox())
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im.resize((int(im.width * height / im.height), height), Image.LANCZOS)


def bokeh(canvas):
    """Soft out-of-focus leaves and light, so the ground reads as forest rather than a flat fill."""
    rng = random.Random(7)
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(46):
        r = rng.randint(60, 260)
        x, y = rng.randint(-100, W + 100), rng.randint(-100, H + 100)
        colour = rng.choice([(120, 200, 150), (170, 220, 120), (245, 195, 59), (90, 180, 200)])
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*colour, rng.randint(14, 34)))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(28)))


def shadow(im, blur=30, opacity=90):
    s = Image.new('RGBA', im.size, (0, 0, 0, 0))
    s.putalpha(im.getchannel('A').point(lambda a: a * opacity // 255))
    pad = blur * 3
    out = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    out.alpha_composite(s, (pad, pad))
    return out.filter(ImageFilter.GaussianBlur(blur)), pad


def place(canvas, im, x, y):
    s, pad = shadow(im)
    canvas.alpha_composite(s, (x - pad + 18, y - pad + 30))
    canvas.alpha_composite(im, (x, y))


def header():
    canvas = background((W, H)).convert('RGBA')
    bokeh(canvas)

    # The flock in the middle, faces inside the safe area
    flock = tody('tody-flock', 940)
    place(canvas, flock, (W - flock.width) // 2, 500)

    # Out at the edges, only on wider crops: one birding, one flying in
    birding = tody('tody-birding', 840)
    place(canvas, birding, 170, H - birding.height - 70)
    flying = tody('tody-flying', 640, flip=True)
    place(canvas, flying, W - flying.width - 260, 170)

    return canvas.convert('RGB')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    im = header()
    im.save(OUT / 'header-3840x1646.png', optimize=True)
    check = im.copy()
    ImageDraw.Draw(check).rectangle(SAFE, outline=(255, 60, 60), width=8)
    check.save(OUT / 'header-safe-area.png', optimize=True)
    print('written to', OUT)


if __name__ == '__main__':
    main()
