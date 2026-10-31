"""Tody app icon, splash and notification icon for the mobile app (Expo config and native projects).

    python3 marketing/tody/install_app_icons.py
"""
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
M = os.path.join(ROOT, 'mobile')
ICON = Image.open(os.path.join(ROOT, 'marketing/tody/masters/tody-app-icon.png')).convert('RGB')
HELLO = Image.open(os.path.join(ROOT, 'marketing/tody/cutout/tody-hello.png')).convert('RGBA')
MASK_INK = (11, 24, 19)  # background of the icon artwork
MIST = (243, 248, 245)


def square_icon(size):
    return ICON.resize((size, size), Image.LANCZOS)


def adaptive_foreground(size):
    """The icon scaled into Android's safe zone on the same dark ground, so any launcher mask looks right."""
    canvas = Image.new('RGB', (size, size), MASK_INK)
    inner = int(size * 0.76)
    canvas.paste(ICON.resize((inner, inner), Image.LANCZOS), ((size - inner) // 2, (size - inner) // 2))
    return canvas


def round_icon(size):
    im = square_icon(size).convert('RGBA')
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new('RGB', (size, size), MASK_INK)
    out.paste(im, (0, 0), mask)
    return out


def splash(size, fill=0.62, opaque=True):
    art = HELLO.crop(HELLO.getbbox())
    scale = size * fill / max(art.size)
    art = art.resize((int(art.width * scale), int(art.height * scale)), Image.LANCZOS)
    canvas = Image.new('RGBA', (size, size), MIST + (255,) if opaque else (0, 0, 0, 0))
    canvas.alpha_composite(art, ((size - art.width) // 2, (size - art.height) // 2))
    return canvas.convert('RGB') if opaque else canvas


def notification(size):
    """Android wants a single-colour silhouette: white Tody on transparent."""
    art = HELLO.crop(HELLO.getbbox())
    scale = size * 0.92 / max(art.size)
    art = art.resize((max(1, int(art.width * scale)), max(1, int(art.height * scale))), Image.LANCZOS)
    alpha = art.getchannel('A').point(lambda a: 255 if a > 110 else 0)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    white = Image.new('RGBA', art.size, (255, 255, 255, 255))
    canvas.paste(white, ((size - art.width) // 2, (size - art.height) // 2), alpha)
    return canvas


def save(img, rel, **kw):
    path = os.path.join(M, rel)
    img.save(path, **kw)
    print(rel, img.size)


save(square_icon(1024), 'assets/icon.png', optimize=True)
save(square_icon(1024), 'ios/Birdr/Images.xcassets/AppIcon.appiconset/App-Icon-1024x1024@1x.png', optimize=True)
save(adaptive_foreground(1024), 'assets/adaptive-icon.png', optimize=True)
for rel in ('assets/splash-icon.png', 'assets/splash-android.png', 'assets/splash-android12.png',
            'android/app/src/main/res/drawable-nodpi/splashscreen_android12.png'):
    save(splash(1024), rel, optimize=True)
for name in ('image.png', 'image@2x.png', 'image@3x.png'):
    save(splash(1024), f'ios/Birdr/Images.xcassets/SplashScreenLegacy.imageset/{name}', optimize=True)
save(notification(96), 'assets/notification-icon.png', optimize=True)

for density, base in (('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)):
    res = f'android/app/src/main/res/mipmap-{density}'
    save(square_icon(base), f'{res}/ic_launcher.webp', quality=92)
    save(round_icon(base), f'{res}/ic_launcher_round.webp', quality=92)
    save(adaptive_foreground(int(base * 2.25)), f'{res}/ic_launcher_foreground.webp', quality=92)
    draw = f'android/app/src/main/res/drawable-{density}'
    save(splash(base * 6), f'{draw}/splashscreen_logo.png', optimize=True)
    save(notification(base // 2), f'{draw}/notification_icon.png', optimize=True)
