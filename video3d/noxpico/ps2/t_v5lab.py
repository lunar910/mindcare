"""Bench test of version 5 acting (no rendering): run every frame, report motion numbers, stick strips per shot."""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
tag = sys.argv[1] if len(sys.argv) > 1 else 'v5a'
sys.argv = ['x']
import bpy, numpy as np
import excerpt5 as E, motionlab as ML
t0 = time.time()
W = E.build()
W = ML.fast(W)
print('build', round(time.time() - t0, 1), 's', flush=True)
times = np.arange(0, E.T_END, 1 / 30)
t1 = time.time()
T = ML.sample(E, W, times)
print('sampled', len(times), 'frames in', round(time.time() - t1, 1), 's', flush=True)
print(ML.report(T, times, stand_from={'pico': 4.6, 'nox': 0.0}))
np.savez(HERE + f'/lab/{tag}_joints.npz', times=times, **{k.replace('.', '__'): v for k, v in T.items()})
for a, b, shot in E.SHOTS:
    ML.strip(E, W, shot, a, b, 6, f'{HERE}/lab/{tag}_{shot}.png', cols=12, tile=(150, 267))
print('strips done', round(time.time() - t0, 1), 's')
