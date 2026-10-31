"""Remove the plain white background by flood-filling from the border, with a soft edge."""
import sys, glob, os
from collections import deque
from PIL import Image, ImageFilter

src, dst = sys.argv[1], sys.argv[2]
for f in sorted(glob.glob(src + '/*.png')):
    im = Image.open(f).convert('RGBA'); w, h = im.size; px = im.load()
    def whiteish(p, t=232): return p[0] > t and p[1] > t and p[2] > t
    bg = bytearray(w * h); q = deque()
    for x in range(w):
        for y in (0, h - 1): q.append((x, y))
    for y in range(h):
        for x in (0, w - 1): q.append((x, y))
    while q:
        x, y = q.popleft(); i = y * w + x
        if bg[i] or not whiteish(px[x, y]): continue
        bg[i] = 1
        if x > 0: q.append((x - 1, y))
        if x < w - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < h - 1: q.append((x, y + 1))
    mask = Image.frombytes('L', (w, h), bytes(0 if b else 255 for b in bg))
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(mask)
    im = im.crop(im.getbbox())
    # pad to a square-ish canvas with a little air, then 768px max
    m = 24; c = Image.new('RGBA', (im.width + 2 * m, im.height + 2 * m)); c.paste(im, (m, m))
    c.thumbnail((768, 768), Image.LANCZOS)
    c.save(os.path.join(dst, os.path.basename(f)), optimize=True)
    print(os.path.basename(f), c.size, os.path.getsize(os.path.join(dst, os.path.basename(f))) // 1024, 'KB')
