"""Compose captioned App Store and Play Store screenshots from raw app screenshots.

    python3 marketing/store-screenshots/make.py [--only en] [--device iphone]

Raw screenshots come from marketing/screenshots/ (iPhone) and marketing/screenshots/ipad/
(iPad). Captions and Tody poses are in captions.json. Output goes to out/<device>/<lang>/.
Fonts (Baloo 2, Figtree, Noto Sans JP, all OFL) are read from fonts/, which is not committed;
download them from github.com/google/fonts.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FONTS = HERE / 'fonts'

CANOPY_DEEP = (13, 77, 51)
CANOPY_DARK = (8, 46, 31)
CANOPY_SOFT = (217, 240, 227)
SUN = (245, 195, 59)
WHITE = (255, 255, 255)

# Store sizes. Play needs the long side at most twice the short side.
DEVICES = {
    'iphone': {'size': (1320, 2868), 'source': ROOT / 'screenshots', 'radius': 64},
    'android': {'size': (1080, 1920), 'source': ROOT / 'screenshots', 'radius': 48},
    'ipad': {'size': (2064, 2752), 'source': ROOT / 'screenshots' / 'ipad', 'radius': 48},
}


def font(name, size, weight):
    f = ImageFont.truetype(str(FONTS / name), size)
    try:
        f.set_variation_by_axes([weight])
    except OSError:
        pass
    return f


def fonts_for(lang, scale):
    if lang == 'ja':
        return font('NotoSansJP.ttf', int(104 * scale), 800), font('NotoSansJP.ttf', int(50 * scale), 500)
    return font('Baloo2.ttf', int(116 * scale), 800), font('Figtree.ttf', int(54 * scale), 500)


def wrap(draw, text, fnt, max_width):
    """Wrap on spaces; Japanese has none, so it wraps per character."""
    tokens = text.split(' ') if ' ' in text else list(text)
    sep = ' ' if ' ' in text else ''
    lines, line = [], ''
    for tok in tokens:
        trial = f'{line}{sep}{tok}' if line else tok
        if draw.textlength(trial, font=fnt) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = tok
    lines.append(line)
    return lines


def background(size):
    w, h = size
    bg = Image.new('RGB', size, CANOPY_DEEP)
    # soft vertical fade to a darker green at the bottom
    fade = Image.linear_gradient('L').resize(size)
    bg.paste(Image.new('RGB', size, CANOPY_DARK), (0, 0), fade.point(lambda v: int(v * 0.75)))
    # a faint light-blue glow behind the phone
    glow = Image.new('L', size, 0)
    ImageDraw.Draw(glow).ellipse([w * 0.1, h * 0.35, w * 0.9, h * 0.95], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.12))
    bg.paste(Image.new('RGB', size, (90, 180, 200)), (0, 0), glow)
    return bg


def rounded(im, radius):
    mask = Image.new('L', im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=radius, fill=255)
    out = im.convert('RGBA')
    out.putalpha(mask)
    return out


def compose(device, shot_path, tody_path, title, subtitle, lang):
    cfg = DEVICES[device]
    w, h = cfg['size']
    scale = w / 1320 if device != 'ipad' else 1.25
    canvas = background((w, h)).convert('RGBA')
    draw = ImageDraw.Draw(canvas)
    title_font, sub_font = fonts_for(lang, scale)

    # Headline and subline, centred at the top
    max_text = w * 0.86
    y = int(h * (0.055 if device != 'android' else 0.045))
    for line in wrap(draw, title, title_font, max_text):
        tw = draw.textlength(line, font=title_font)
        draw.text(((w - tw) / 2, y), line, font=title_font, fill=WHITE)
        y += int(title_font.size * 1.08)
    y += int(18 * scale)
    for line in wrap(draw, subtitle, sub_font, w * 0.92):
        tw = draw.textlength(line, font=sub_font)
        draw.text(((w - tw) / 2, y), line, font=sub_font, fill=CANOPY_SOFT)
        y += int(sub_font.size * 1.3)
    # The phone always starts at the same height, whatever the caption length
    top = int(h * {'iphone': 0.215, 'android': 0.24, 'ipad': 0.2}[device])

    # The screenshot, framed, running off the bottom edge a little
    shot = Image.open(shot_path).convert('RGB')
    shot_w = int(w * {'iphone': 0.72, 'android': 0.62, 'ipad': 0.66}[device])
    shot = shot.resize((shot_w, int(shot.height * shot_w / shot.width)), Image.LANCZOS)
    radius = int(cfg['radius'] * shot_w / 976)
    bezel = int(14 * shot_w / 976)
    frame = Image.new('RGBA', (shot.width + 2 * bezel, shot.height + 2 * bezel), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle(
        [0, 0, frame.width - 1, frame.height - 1], radius=radius + bezel, fill=(16, 32, 27, 255)
    )
    frame.alpha_composite(rounded(shot, radius), (bezel, bezel))
    shadow = Image.new('RGBA', (frame.width + 120, frame.height + 120), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [60, 80, frame.width + 60, frame.height + 80], radius=radius + bezel, fill=(0, 0, 0, 110)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(36))
    fx = (w - frame.width) // 2
    canvas.alpha_composite(shadow, (fx - 60, top - 60))
    canvas.alpha_composite(frame, (fx, top))

    # Tody, overlapping the lower right corner of the phone
    if tody_path:
        tody = Image.open(tody_path).convert('RGBA')
        # same visual size for wide (flock) and tall poses
        target = w * (0.30 if device != 'ipad' else 0.22)
        k = target / (tody.width * tody.height) ** 0.5
        tody = tody.resize((int(tody.width * k), int(tody.height * k)), Image.LANCZOS)
        tx = w - tody.width + int(w * 0.015)
        ty = h - tody.height - int(h * 0.012)
        canvas.alpha_composite(tody, (tx, ty))

    return canvas.convert('RGB')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', help='one language, e.g. en')
    parser.add_argument('--device', choices=DEVICES, action='append')
    args = parser.parse_args()
    spec = json.loads((HERE / 'captions.json').read_text(encoding='utf-8'))
    langs = [args.only] if args.only else list(spec['captions'])
    for device in args.device or list(DEVICES):
        src = DEVICES[device]['source']
        for lang in langs:
            out = HERE / 'out' / device / lang
            out.mkdir(parents=True, exist_ok=True)
            for i, key in enumerate(spec['order'], 1):
                shot = src / f'{key}.png'
                if not shot.exists():
                    print(f'skip {device}/{key}: no {shot}')
                    continue
                title, subtitle = spec['captions'][lang][key]
                tody = ROOT / 'tody' / 'cutout' / f"{spec['tody'][key]}.png"
                img = compose(device, shot, tody, title, subtitle, lang)
                path = out / f'{i:02d}-{key}.png'
                img.save(path, optimize=True)
            print(f'{device}/{lang}: done')


if __name__ == '__main__':
    main()
