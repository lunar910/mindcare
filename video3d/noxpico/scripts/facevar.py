"""Mouth / blink texture variants from hand-placed features in the front face render (see facefx.capture).

    python facevar.py NAME '{"mouth": [y, x, half_width], "eyes": [[y, x, rx, ry], [y, x, rx, ry]]}'

writes out_face/var/NAME_{mouth_half,mouth_open,mouth_wide,blink}.png (full textures) and NAME_preview.png."""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facefx

name, feat = sys.argv[1], json.loads(sys.argv[2])
col = np.asarray(Image.open(f'out_face/{name}_col.png').convert('RGBA'), dtype=np.float32) / 255
uv = facefx._read_uv(f'out_face/{name}_uv.exr')
tex = np.asarray(Image.open(f'out_face/{name}_tex.png').convert('RGB'), dtype=np.float32) / 255
H, W = col.shape[:2]
a = col[..., :3]
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
my, mx, mw = feat['mouth']
# colours sampled on the face itself
cheek = np.median(a[int(my - 0.9 * mw):int(my - 0.5 * mw), int(mx - 0.4 * mw):int(mx + 0.4 * mw)].reshape(-1, 3), axis=0)
line = a[int(my - 2):int(my + 3), int(mx - 0.6 * mw):int(mx + 0.6 * mw)].reshape(-1, 3)
mline = line[np.argsort(line @ np.array([0.3, 0.59, 0.11]))[:max(3, len(line) // 6)]].mean(axis=0)
inner = np.clip(mline * 0.55 + np.array([0.12, 0.0, 0.0]), 0, 1)          # mouth interior: darker, a little redder than the line
teeth = np.array([0.96, 0.94, 0.90], dtype=np.float32)
tongue = np.clip(inner * 1.6 + np.array([0.12, 0.02, 0.02]), 0, 1)
print('cheek', (cheek * 255).round(), 'line', (mline * 255).round())
out = {}
shapes = {'half': (0.42, 0.20, 0.0), 'open': (0.50, 0.42, 0.30), 'wide': (0.68, 0.30, 0.34)}
for var, (rx, ry, tee) in shapes.items():
    view = a.copy()
    cy = my + 0.35 * mw * ry
    m = ((yy - cy) / (mw * ry)) ** 2 + ((xx - mx) / (mw * rx)) ** 2 <= 1
    view[m] = inner
    if tee:                                                       # upper teeth band, tongue at the bottom
        top = m & (yy < cy - mw * ry * (1 - 2 * tee))
        view[top] = teeth
        bot = m & (yy > cy + mw * ry * 0.35) & (np.abs(xx - mx) < mw * rx * 0.6)
        view[bot] = tongue
    edge = m & ~ndi.binary_erosion(m, iterations=1)
    view[edge] = mline * 0.8
    out['mouth_' + var] = facefx.project(view, uv, tex, mask=ndi.binary_dilation(m, iterations=3) & ~ndi.binary_dilation(m, iterations=3, mask=np.zeros_like(m)) | ndi.binary_dilation(m, iterations=3))
# blink: eyes covered with lid skin, a closed-eye lash line (gentle downward arc) at 60 % of the eye height
view = a.copy(); bm = np.zeros((H, W), bool)
for ey, ex, rx, ry in feat['eyes']:
    m = ((yy - ey) / (ry * 1.08)) ** 2 + ((xx - ex) / (rx * 1.06)) ** 2 <= 1
    lid = np.median(a[int(ey + ry * 1.15):int(ey + ry * 1.6), int(ex - rx * 0.5):int(ex + rx * 0.5)].reshape(-1, 3), axis=0)
    view[m] = lid
    shade = m & (yy < ey - 0.1 * ry)                              # upper lid a touch darker (the closed lid)
    view[shade] = lid * 0.95
    u = (xx - ex) / rx
    arc_y = ey + 0.25 * ry + 0.32 * ry * (1 - u ** 2)
    arc = (np.abs(yy - arc_y) <= max(2.0, 0.11 * ry)) & (np.abs(u) <= 1.0)
    view[arc] = np.array([0.12, 0.08, 0.09])
    flick = (np.abs(yy - (arc_y - 0.10 * ry * (np.abs(u) - 0.85) / 0.15)) <= max(1.5, 0.08 * ry)) & (np.abs(u) > 0.85) & (np.abs(u) < 1.12)
    view[flick] = np.array([0.12, 0.08, 0.09])
    bm |= m | arc | flick
out['blink'] = facefx.project(view, uv, tex, mask=ndi.binary_dilation(bm, iterations=2))
os.makedirs('out_face/var', exist_ok=True)
for k, v in out.items():
    Image.fromarray((np.clip(v, 0, 1) * 255).astype(np.uint8)).save(f'out_face/var/{name}_{k}.png')
# preview through the UV map (what the camera will see)
prev = []
ok = uv[..., 3] > 0.5
for k in ('mouth_half', 'mouth_open', 'mouth_wide', 'blink'):
    t2 = out[k]
    Ht, Wt = t2.shape[:2]
    tx = np.clip((uv[..., 0] * Wt).astype(int), 0, Wt - 1); ty = np.clip(((1 - uv[..., 1]) * Ht).astype(int), 0, Ht - 1)
    v = np.where(ok[..., None], t2[ty, tx], 0)
    cy0 = int(min(my, min(e[0] for e in feat['eyes'])) - 1.2 * mw)
    prev.append(v[max(cy0, 0):int(my + 1.4 * mw), int(mx - 3.2 * mw):int(mx + 3.2 * mw)])
hmin = min(p.shape[0] for p in prev)
Image.fromarray((np.concatenate([p[:hmin] for p in prev], axis=1) * 255).astype(np.uint8)).save(f'out_face/var/{name}_preview.png')
json.dump(feat, open(f'out_face/{name}_feat.json', 'w'))
print('ok', name)
