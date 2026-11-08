"""Facebook group cover for Motmot Community (facebook.com/groups/birdrcommunity): 1640x856.

    python3 marketing/store-screenshots/facebook_group_cover.py

Writes out/facebook/group-cover.png and group-cover-safe-area.png. Facebook crops the
cover top and bottom on wide desktop screens and the sides on phones, so text and faces
stay inside the middle band drawn on the safe-area copy.
"""
from pathlib import Path

from PIL import Image, ImageDraw

from app_store_header import bokeh, place, tody
from make import CANOPY_SOFT, SUN, WHITE, background, font

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out' / 'facebook'
W, H = 1640, 856
SAFE = (120, 150, 1520, 706)


def cover():
    canvas = background((W, H)).convert('RGBA')
    bokeh(canvas)

    # The flock on its branch on the right, a fourth Tody flying in above it
    flock = tody('tody-flock', 470)
    place(canvas, flock, W - flock.width - 100, 262)
    flying = tody('tody-flying', 220, flip=True)
    place(canvas, flying, W - flying.width - 60, 96)

    # Wordmark and tagline on the left
    draw = ImageDraw.Draw(canvas)
    draw.text((150, 236), 'Motmot', font=font('Baloo2.ttf', 140, 800), fill=WHITE)
    draw.text((156, 392), 'Community', font=font('Baloo2.ttf', 84, 700), fill=SUN)
    draw.text((158, 520), 'Learn · Play · Identify Birds', font=font('Figtree.ttf', 40, 600), fill=CANOPY_SOFT)
    return canvas.convert('RGB')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    im = cover()
    im.save(OUT / 'group-cover.png', optimize=True)
    check = im.copy()
    ImageDraw.Draw(check).rectangle(SAFE, outline=(255, 60, 60), width=4)
    check.save(OUT / 'group-cover-safe-area.png', optimize=True)
    print('written to', OUT)


if __name__ == '__main__':
    main()
