"""Preview of set5.city: a camera inside the loft looking through a stand-in black window frame (y = 4.0).

    ../blender-venv/bin/python set5/city_preview.py [shots] [scale] [samples]
    shots: comma list of a24,a50,w24,out,down,left,hill,church,mast,bench,sky (default a24,a50)
    scale: 1.0 = 288x512 portrait / 512x288 landscape (1.5 = 432x768 / 768x432 for final checks)
    a24/a50/w24: from (-1.5, -1, 1.5) inside the room through the stand-in frame; bench: over Nox's shoulder;
    left: from the right of the room looking left; out/down/hill/church/mast/sky: from just outside the glazing
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

import kit5  # noqa: E402
import look5  # noqa: E402
from set5 import city  # noqa: E402

OUT = os.path.join(ROOT, 'lab', 'set5')


def frame(col):
    """Black stand-in for the steel glazing: wall around x -5..2 / z 0.70..3.15, mullions every 1 m, transoms."""
    F = kit5.Prop('_frame', col)
    blk = bpy.data.materials.new('_black')
    blk.use_nodes = True
    bs = blk.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = (0.004, 0.004, 0.004, 1)
    bs.inputs['Roughness'].default_value = 0.9
    t = 0.10
    F.box('below', (30, t, 10.7), (-1.5, 4.0, 0.70 - 5.35), blk, bevel=0)
    F.box('above', (30, t, 8.0), (-1.5, 4.0, 3.15 + 4.0), blk, bevel=0)
    F.box('left', (10, t, 3.0), (-5.0 - 5.0, 4.0, 1.9), blk, bevel=0)
    F.box('right', (10, t, 3.0), (2.0 + 5.0, 4.0, 1.9), blk, bevel=0)
    for k in range(8):
        x = -5.0 + k * 1.0
        F.box(f'mull{k}', (0.06 if 0 < k < 7 else 0.10, 0.12, 2.5), (x, 4.0, 1.925), blk, bevel=0)
    for z in (1.55, 2.35):
        F.box(f'tr{z}', (7.0, 0.12, 0.05), (-1.5, 4.0, z), blk, bevel=0)
    F.box('sill', (7.2, 0.35, 0.08), (-1.5, 3.9, 0.68), blk, bevel=0)
    return F


SHOTS = {
    # name: (pos, target, lens, portrait, with frame)
    'a24': ((-1.5, -1.0, 1.5), (-1.5, 10.0, 1.5), 24, True, True),
    'a50': ((-1.5, -1.0, 1.5), (-1.5, 10.0, 1.5), 50, True, True),
    'w24': ((-1.5, -1.0, 1.5), (-1.5, 10.0, 1.5), 24, False, True),
    'out': ((-1.5, 4.2, 1.6), (-1.5, 100.0, -2.0), 24, False, False),
    'down': ((-1.5, 4.2, 1.6), (-1.5, 40.0, -14.0), 24, False, False),
    'left': ((1.5, -1.5, 1.5), (-20.0, 30.0, 0.0), 35, False, True),
    'hill': ((-1.5, 4.2, 1.6), (-1.5, 300.0, -4.0), 50, False, False),
    'church': ((-1.5, 4.2, 1.6), (-96.0, 311.0, 52.0), 135, False, False),
    'mast': ((-1.5, 4.2, 1.6), (79.0, 324.0, 55.0), 100, False, False),
    'sky': ((-1.5, 4.2, 1.6), (-1.5, 100.0, 15.0), 24, False, False),
    'bench': ((-3.1, 1.2, 1.25), (-3.6, 30.0, 0.5), 35, False, True),
}


def main():
    shots = (sys.argv[1] if len(sys.argv) > 1 else 'a24,a50').split(',')
    scale = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    samples = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    bpy.ops.wm.read_factory_settings(use_empty=True)
    look5.setup(288, 512, samples)
    look5.world((0.0, 0.0, 0.0), 0.0)
    t = time.time()
    P = city.build()
    F = frame(None)
    print(f'build {time.time() - t:.1f} s', flush=True)
    tris = sum(len(o.data.loop_triangles) if o.type == 'MESH' and (o.data.calc_loop_triangles() or True) else 0
               for o in P.col.objects)
    print('city triangles', tris, 'objects', len(P.col.objects), 'beacons', len(P.beacons), flush=True)
    cam = look5.camera('cam', 24)
    sc = bpy.context.scene
    for s in shots:
        pos, tgt, lens, portrait, with_frame = SHOTS[s]
        for o in F.col.objects:
            o.hide_render = not with_frame
        look5.aim(cam, pos, tgt, lens)
        w, h = (288, 512) if portrait else (512, 288)
        sc.render.resolution_x, sc.render.resolution_y = int(w * scale), int(h * scale)
        sc.render.filepath = os.path.join(OUT, f'city_{s}.png')
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f'{s}: {time.time() - t:.1f} s -> {sc.render.filepath}', flush=True)


if __name__ == '__main__':
    main()
