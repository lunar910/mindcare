"""Numbers about the motion: jumps between frames, foot sliding.   python motion_report.py OUT/motion.json"""
import json, sys
import numpy as np
rows = json.load(open(sys.argv[1]))
t = np.array([r['t'] for r in rows]); dt = t[1] - t[0]
keys = [k for k in rows[0] if k != 't']
print(f'{len(rows)} frames, dt={dt:.4f}')
for k in keys:
    p = np.array([r[k] for r in rows])
    v = np.linalg.norm(np.diff(p, axis=0), axis=1) / dt                 # m/s
    a = np.abs(np.diff(v)) / dt                                         # m/s^2
    top = np.argsort(a)[-3:][::-1]
    s = ', '.join(f'{t[i + 1]:.2f}s:{a[i]:.0f}' for i in top)
    line = f'{k:16s} vmax {v.max():5.2f} m/s at {t[v.argmax()]:5.2f}s | accel peaks m/s2: {s}'
    if 'Foot' in k:
        low = p[:-1, 2] < (np.percentile(p[:, 2], 10) + 0.015)          # foot on the ground
        hv = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1) / dt
        slide = hv[low]
        line += f' | planted {low.mean() * 100:.0f}% of the time, sliding mean {slide.mean() * 100:.1f} cm/s, max {slide.max() * 100:.0f} cm/s, total {slide.sum() * dt * 100:.0f} cm'
    print(line)
