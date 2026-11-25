"""Checks on the rendered frames: missing frames, and jumps between consecutive frames that are not cuts.

    python check_video.py OUT_DIR"""
import os, re, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(HERE + '/excerpt2.py').read()
ns = {}
exec(re.search(r'T_END = [0-9.]+', src).group(0), ns)
exec(re.search(r'SHOTS = \[.*?\]\n', src, re.S).group(0), ns)
FPS = 30
out = sys.argv[1]
n = int(round(ns['T_END'] * FPS))
cuts = {int(round(a * FPS)) for a, b, nm in ns['SHOTS']}
missing = [f for f in range(n) if not os.path.exists(f'{out}/px/f{f:05d}.png')]
print('frames expected', n, 'missing', len(missing), missing[:10])
prev, diffs = None, []
for f in range(n):
    p = f'{out}/px/f{f:05d}.png'
    if not os.path.exists(p):
        prev = None; continue
    a = np.asarray(Image.open(p).convert('L').resize((108, 192), Image.BILINEAR), dtype=np.float32)
    if prev is not None:
        diffs.append((f, float(np.abs(a - prev).mean()), float((np.abs(a - prev) > 40).mean())))
    prev = a
d = np.array([x[1] for x in diffs])
print(f'frame-to-frame change: median {np.median(d):.2f}, 95th pct {np.percentile(d, 95):.2f}')
print('cuts:', [(f, round(v, 1)) for f, v, _ in diffs if f in cuts])
rest = sorted([x for x in diffs if x[0] not in cuts], key=lambda x: -x[1])[:12]
print('largest changes that are not cuts (frame, time, mean change, share of strongly changed pixels):')
for f, v, s in rest:
    print(f'   f{f:05d} t={f / FPS:5.2f}s  {v:5.2f}  {s * 100:4.1f}%')
