"""Bench test of version 4 acting, no rendering: numbers + stick figures through the shot cameras."""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.argv = ['x']
import bpy, numpy as np
import excerpt4 as E, motionlab as ML
t0 = time.time()
W = ML.fast(E.build())
print('build', round(time.time() - t0, 1), 's', flush=True)
times = np.arange(0, E.T_END, 1 / 30)
t1 = time.time()
T = ML.sample(E, W, times)
print('sampled', len(times), 'frames in', round(time.time() - t1, 1), 's', flush=True)
print(ML.report(T, times, stand_from={'pico': 2.1, 'nox': 0.0}))
out = HERE + '/lab'
tag = sys.argv[1] if len(sys.argv) > 1 else 'v4a'
import script4
for a, b, shot in script4.SHOTS:
    a = max(a, 0.4)
    ML.strip(E, W, shot, a, b, 6, f'{out}/{tag}_{shot}.png', cols=12, tile=(150, 267))
print('strips done', round(time.time() - t0, 1), 's')
