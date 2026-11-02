"""Put the app icon on a light sage ground: cut Tody out of the dark ground of tody-app-icon.png.

The ground is flood-filled from the border. Pixels in a thin band around it get a soft alpha by
their distance from the ground colour, and the dark ground is un-mixed from their colour, so the
feather tips show no dark halo. The band keeps Tody's black mask and bill opaque.

    python3 marketing/tody/light_icon.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'marketing/tody/masters/tody-app-icon.png')
DST = os.path.join(ROOT, 'marketing/tody/masters/tody-app-icon-light.png')
SAGE = (220, 236, 226)  # #DCECE2
SEED_MAX = 25       # border pixels this close to the ground start a flood fill
FLOOD_THRESH = 40   # flood fill tolerance
EDGE_BAND = 13      # px, the soft edge around the ground (MaxFilter size)
EDGE_LO, EDGE_HI = 12.0, 90.0  # colour distance from the ground for alpha 0 and 1

img = Image.open(SRC).convert('RGB')
im = np.asarray(img).astype(np.float32)
w, h = img.size
ground = np.median(np.concatenate([im[:8].reshape(-1, 3), im[:, :8].reshape(-1, 3), im[:, -8:].reshape(-1, 3)]), axis=0)
dist = np.linalg.norm(im - ground, axis=2)

FILL = (255, 0, 255)
marker = img.copy()
seeds = [(x, y) for x in range(0, w, 8) for y in (0, h - 1)] + [(x, y) for y in range(0, h, 8) for x in (0, w - 1)]
for x, y in seeds:
    if dist[y, x] < SEED_MAX and marker.getpixel((x, y)) != FILL:
        ImageDraw.floodfill(marker, (x, y), FILL, thresh=FLOOD_THRESH)
bg = np.all(np.asarray(marker) == FILL, axis=2)

band = (np.asarray(Image.fromarray(bg.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(EDGE_BAND))) > 0) & ~bg
alpha = np.ones_like(dist)
alpha[bg] = 0
alpha[band] = np.clip((dist[band] - EDGE_LO) / (EDGE_HI - EDGE_LO), 0, 1)
alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32) / 255

a = np.maximum(alpha, 0.05)[..., None]
fg = np.where(alpha[..., None] > 0.98, im, np.clip((im - (1 - a) * ground) / a, 0, 255))
out = alpha[..., None] * fg + (1 - alpha[..., None]) * np.array(SAGE, dtype=np.float32)
Image.fromarray(out.round().astype(np.uint8), 'RGB').save(DST, optimize=True)
print(os.path.relpath(DST, ROOT), img.size)
