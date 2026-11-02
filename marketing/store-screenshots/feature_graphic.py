"""Play Store feature graphic (1024x500) per listing language, plus the 512px store icon.

    python3 marketing/store-screenshots/feature_graphic.py

Writes out/play/feature-<lang>.png and out/play/icon-512.png.
"""
from pathlib import Path

from PIL import Image, ImageDraw

from make import CANOPY_SOFT, FONTS, ROOT, WHITE, background, font, rounded, wrap

HERE = Path(__file__).resolve().parent
OUT = HERE / 'out' / 'play'
OCHRE = (200, 116, 42)
SUN = (245, 195, 59)

TAGLINES = {
    'en': 'Improve your birding skills',
    'nl': 'Word beter in vogels herkennen',
    'de': 'Verbessere deine Vogelkenntnis',
    'fr': 'Progresse en identification d’oiseaux',
    'es': 'Mejora tu identificación de aves',
    'pt-BR': 'Melhore sua identificação de aves',
}
SUBTITLE = {
    'en': 'Bird ID Quiz', 'nl': 'Vogelquiz', 'de': 'Vogel-Quiz',
    'fr': 'Quiz oiseaux', 'es': 'Quiz de aves', 'pt-BR': 'Quiz de aves',
}


def feature(lang):
    w, h = 1024, 500
    canvas = background((w, h)).convert('RGBA')
    draw = ImageDraw.Draw(canvas)

    # Phone with the home screen, running off the bottom on the right
    shot = Image.open(ROOT / 'screenshots' / 'home.png').convert('RGB')
    sw = 250
    shot = shot.resize((sw, int(shot.height * sw / shot.width)), Image.LANCZOS)
    bezel = 8
    frame = Image.new('RGBA', (sw + 2 * bezel, shot.height + 2 * bezel), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle([0, 0, frame.width - 1, frame.height - 1], radius=40, fill=(16, 32, 27, 255))
    frame.alpha_composite(rounded(shot, 32), (bezel, bezel))
    canvas.alpha_composite(frame, (w - frame.width - 150, 46))

    # Tody waving next to the phone
    tody = Image.open(ROOT / 'tody' / 'cutout' / 'tody-hello.png').convert('RGBA')
    th = 300
    tody = tody.resize((int(tody.width * th / tody.height), th), Image.LANCZOS)
    canvas.alpha_composite(tody, (w - tody.width + 10, h - th - 6))

    # Icon, wordmark, subtitle and tagline on the left
    icon = Image.open(ROOT / 'tody' / 'masters' / 'tody-app-icon-light.png').convert('RGB').resize((112, 112), Image.LANCZOS)
    canvas.alpha_composite(rounded(icon, 26), (64, 92))
    draw.text((196, 84), 'Motmot', font=font('Baloo2.ttf', 92, 800), fill=WHITE)
    draw.text((200, 176), SUBTITLE[lang], font=font('Baloo2.ttf', 40, 700), fill=SUN)
    tag_font = font('Figtree.ttf', 40, 600)
    y = 268
    for line in wrap(draw, TAGLINES[lang], tag_font, 470):
        draw.text((66, y), line, font=tag_font, fill=CANOPY_SOFT)
        y += 52
    return canvas.convert('RGB')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for lang in TAGLINES:
        feature(lang).save(OUT / f'feature-{lang}.png', optimize=True)
    icon = Image.open(ROOT / 'tody' / 'masters' / 'tody-app-icon-light.png').convert('RGB').resize((512, 512), Image.LANCZOS)
    icon.save(OUT / 'icon-512.png', optimize=True)
    print('written to', OUT)


if __name__ == '__main__':
    main()
