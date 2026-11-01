"""Write Tody image sets for the web and mobile apps, plus the Tody logo and icons.

    python3 marketing/tody/install_app_images.py
"""
import glob
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CUT = os.path.join(ROOT, 'marketing/tody/cutout')
ICON = os.path.join(ROOT, 'marketing/tody/masters/tody-app-icon.png')
HEAD = os.path.join(ROOT, 'marketing/tody/masters/tody-head.png')
SURFACE = (250, 247, 242, 255)

MOODS = {
    'success': 'correct', 'failed': 'wrong', 'stressed': 'stressed', 'waiting': 'thinking',
    'maintenance': 'sleeping', 'start-game': 'birding', 'flock-invite': 'flock',
    'leaderboard': 'champion', 'survival': 'stressed', 'no-image': 'no-image',
    **{f'level{i}': f'level{i}' for i in range(8)},
}


def fit(src, size, pad=0.04):
    """Tody centred in a transparent canvas of the original size, resting on the bottom edge."""
    w, h = size
    art = Image.open(src).convert('RGBA')
    art = art.crop(art.getbbox())
    box_w, box_h = int(w * (1 - 2 * pad)), int(h * (1 - pad))
    scale = min(box_w / art.width, box_h / art.height)
    art = art.resize((max(1, int(art.width * scale)), max(1, int(art.height * scale))), Image.LANCZOS)
    canvas = Image.new('RGBA', size)
    canvas.alpha_composite(art, ((w - art.width) // 2, h - art.height - int(h * pad / 2)))
    return canvas


def silhouette(img):
    """Locked level: a soft grey shape, like the old shaded level image."""
    alpha = img.getchannel('A').filter(ImageFilter.GaussianBlur(radius=max(2, img.width // 60)))
    out = Image.new('RGBA', img.size, (110, 125, 118, 0))
    out.putalpha(alpha.point(lambda a: int(a * 0.55)))
    return out


def icon(size, shape='square'):
    """square/circle: the app icon on dark green; head: Tody without background; head-surface: on the site's mist."""
    if shape.startswith('head'):
        im = Image.open(HEAD).convert('RGBA').resize((size, size), Image.LANCZOS)
        if shape == 'head-surface':
            bg = Image.new('RGBA', (size, size), SURFACE)
            bg.alpha_composite(im)
            im = bg
        return im
    im = Image.open(ICON).convert('RGBA').resize((size, size), Image.LANCZOS)
    if shape == 'circle':
        mask = Image.new('L', (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        im.putalpha(mask)
    return im


def write_tody_set(folders, dest):
    """Tody versions of every mood and level file found in the reference folders, at the first size found."""
    sizes = {}
    for folder in folders:
        for path in sorted(glob.glob(os.path.join(ROOT, folder, 'birdr-*.png'))):
            sizes.setdefault(os.path.basename(path), Image.open(path).size)
    os.makedirs(os.path.join(ROOT, dest), exist_ok=True)
    for name, size in sorted(sizes.items()):
        key = name[len('birdr-'):-4]
        if key == 'level1-shaded':
            img = silhouette(fit(os.path.join(CUT, 'tody-level1.png'), size))
        elif key in MOODS:
            img = fit(os.path.join(CUT, f'tody-{MOODS[key]}.png'), size)
        else:
            continue
        out = os.path.join(ROOT, dest, name)
        img.save(out, optimize=True)
        print('mood', os.path.relpath(out, ROOT), size)


# Bertie ("classic") and the notebook set ("stylish") stay untouched; Tody gets his own folder.
write_tody_set(('app/public/images', 'app/public/images/stylish'), 'app/public/images/tody')
write_tody_set(('mobile/assets', 'mobile/assets/stylish'), 'mobile/assets/tody')

for rel, shape in (
    ('app/public/images/birdr-logo.png', 'circle'),
    ('app/public/images/badge.png', 'circle'),
    ('app/public/images/logo.png', 'square'),
    ('app/public/images/birdr-icon.png', 'square'),
    ('app/public/logo192.png', 'head'),
    ('app/public/logo512.png', 'head'),
    ('app/public/apple-touch-icon.png', 'head-surface'),
    ('app/public/favicon-32x32.png', 'head'),
    ('app/public/favicon-16x16.png', 'head'),
    ('app/public/android-chrome-192x192.png', 'head'),
    ('app/public/android-chrome-512x512.png', 'head'),
    ('app/public/mstile-150x150.png', 'head'),
    ('app/public/images/motmot/tody-icon-64.png', 'head'),
    ('app/public/images/motmot/tody-icon-128.png', 'head'),
    ('app/public/images/motmot/tody-icon-256.png', 'head'),
    ('mobile/assets/birdr-512.png', 'square'),
):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        continue
    w, h = Image.open(path).size
    size = min(w, h, 1024)
    icon(size, shape).save(path, optimize=True)
    print('icon', rel, (size, size))

ico = os.path.join(ROOT, 'app/public/favicon.ico')
if os.path.exists(ico):
    icon(64, 'head').save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print('icon app/public/favicon.ico')

# Tody with binoculars for the marketing site's menu bar, cut at the chest where the bar's edge is
art = Image.open(os.path.join(CUT, 'tody-birding.png')).convert('RGBA')
art = art.crop(art.getbbox())
art = art.crop((0, 0, art.width, int(art.height * 0.68)))
art = art.crop(art.getbbox())
art = art.resize((round(art.width * 200 / art.height), 200), Image.LANCZOS)
out = os.path.join(ROOT, 'app/public/images/motmot/tody-header-binoculars.webp')
art.save(out, quality=88, method=6)
print('header', os.path.relpath(out, ROOT), art.size)
