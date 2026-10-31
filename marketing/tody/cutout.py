"""Remove the plain white background, with a soft edge.

The background is flood-filled from the border. White background caught inside the art (between
the legs, inside a trophy handle, under a tripod) is removed too: it is near-pure white, while
Tody's white feathers and eye highlights are slightly darker. Shadowed background between the legs
is a little darker as well, so the lower part of the image gets a lower threshold.

    python3 marketing/tody/cutout.py marketing/tody/masters marketing/tody/cutout
"""
import sys, glob, os
from collections import deque
from PIL import Image, ImageFilter

HOLE_MIN_PIXELS = 150
HOLE_MIN_BRIGHTNESS = 252.8          # anywhere in the image
HOLE_MIN_BRIGHTNESS_LOW = 251.5      # in the lower part, where shadows sit
LOW_PART = 0.6                       # below 60% of the image height


def flood(px, w, h, seeds, accept, mark):
    q = deque(seeds)
    while q:
        x, y = q.popleft(); i = y * w + x
        if mark[i] or not accept(px[x, y]): continue
        mark[i] = 1
        if x > 0: q.append((x - 1, y))
        if x < w - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < h - 1: q.append((x, y + 1))


def whiteish(p, t=232): return p[0] > t and p[1] > t and p[2] > t
def pure_white(p): return min(p[:3]) >= 243 and max(p[:3]) - min(p[:3]) <= 10


def background_mask(im):
    w, h = im.size; px = im.load()
    bg = bytearray(w * h)
    border = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    flood(px, w, h, border, whiteish, bg)

    # Enclosed near-white areas: decide per area whether it is trapped background.
    seen = bytearray(bg)
    holes = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i] or not pure_white(px[x, y]): continue
            q = deque([(x, y)]); seen[i] = 1; pts = []
            while q:
                cx, cy = q.popleft(); pts.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        if not seen[j] and pure_white(px[nx, ny]): seen[j] = 1; q.append((nx, ny))
            if len(pts) < HOLE_MIN_PIXELS: continue
            brightness = sum(sum(px[p][:3]) for p in pts) / (3 * len(pts))
            centre_y = sum(p[1] for p in pts) / len(pts)
            low = centre_y > h * LOW_PART
            if brightness >= HOLE_MIN_BRIGHTNESS or (low and brightness >= HOLE_MIN_BRIGHTNESS_LOW):
                holes.extend(pts)
    if holes:
        flood(px, w, h, holes, whiteish, bg)  # grow into the soft fringe around each hole
    return Image.frombytes('L', (w, h), bytes(0 if b else 255 for b in bg))


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    for f in sorted(glob.glob(src + '/*.png')):
        if os.path.basename(f) == 'tody-app-icon.png':
            continue  # square artwork on a dark ground, not a cut-out
        im = Image.open(f).convert('RGBA')
        mask = background_mask(im)
        mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
        im.putalpha(mask)
        im = im.crop(im.getbbox())
        # pad to a square-ish canvas with a little air, then 768px max
        m = 24; c = Image.new('RGBA', (im.width + 2 * m, im.height + 2 * m)); c.paste(im, (m, m))
        c.thumbnail((768, 768), Image.LANCZOS)
        c.save(os.path.join(dst, os.path.basename(f)), optimize=True)
        print(os.path.basename(f), c.size, os.path.getsize(os.path.join(dst, os.path.basename(f))) // 1024, 'KB')
