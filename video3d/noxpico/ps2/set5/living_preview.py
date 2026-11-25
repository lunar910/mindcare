"""Previews for set5.living (one Blender process, props rendered one after the other).

    ../blender-venv/bin/python set5/living_preview.py sofa,rug [yaw] [elev] [size] [samples] [suffix]
    ../blender-venv/bin/python set5/living_preview.py zone [shot] [size] [samples]      # night composite

Product shots use look5.preview (neutral floor, soft key/fill/rim); output lab/set5/living_<name><suffix>.png
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
import mat5  # noqa: E402
from set5 import living  # noqa: E402

OUT = os.path.join(ROOT, 'lab', 'set5')
EXPOSURE = float(os.environ.get('LV_EXPOSURE', '-1.5'))


def tri_count(col):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in col.all_objects:
        if o.type in ('MESH', 'CURVE'):
            ev = o.evaluated_get(dg)
            try:
                me = ev.to_mesh()
            except RuntimeError:
                continue
            me.calc_loop_triangles()
            n += len(me.loop_triangles)
            ev.to_mesh_clear()
    return n


def product(name, yaw, elev, size, samples, suffix=''):
    fn = getattr(living, 'build_' + name)

    def b():
        mat5._CACHE.clear()
        living._reset()
        P = fn()
        bpy.context.scene.view_settings.exposure = EXPOSURE
        return P
    out = os.path.join(OUT, f'living_{name}{suffix}.png')
    P = look5.preview(b, out, size=(size, size), yaw=yaw, elev=elev, samples=samples)
    bpy.context.scene.render.use_simplify = False
    print(name, 'objects', len(P.col.all_objects), 'tris', tri_count(P.col), flush=True)


ZONE_SHOTS = {
    # name: (cam pos, target, lens, w, h)
    'wide': ((3.9, 0.6, 1.55), (1.3, -2.4, 0.55), 26, 512, 288),
    'sofa': ((1.9, 0.2, 1.25), (1.45, -2.35, 0.55), 32, 512, 288),
    'low': ((0.4, -0.6, 0.75), (2.2, -2.4, 0.6), 24, 512, 288),
    'top': ((1.5, 0.8, 3.2), (1.4, -2.2, 0.2), 22, 512, 384),
}


def zone(shot='wide', scale=1.0, samples=32):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat5._CACHE.clear()
    living._reset()
    look5.setup(512, 288, samples)
    look5.world((0.008, 0.012, 0.028), 1.0)
    t = time.time()
    Z = living.living_zone()
    # stand-in room around the living zone: floor, front wall (y = -4), right wall (x = 4), part of the ceiling
    R = kit5.Prop('_room')
    R.box('floor', (9.0, 8.0, 0.04), (-0.5, 0.0, -0.02), 'concrete_floor', bevel=0)
    R.box('front_wall', (9.0, 0.1, 3.4), (-0.5, -4.05, 1.7), 'plaster_warm', bevel=0)
    R.box('right_wall', (0.1, 8.0, 3.4), (4.05, 0.0, 1.7), 'plaster_warm', bevel=0)
    R.box('left_wall', (0.1, 8.0, 3.4), (-5.05, 0.0, 1.7), 'brick_painted', bevel=0)
    R.box('ceiling', (9.0, 8.0, 0.1), (-0.5, 0.0, 3.45), 'concrete_wall', bevel=0)
    print('build', round(time.time() - t, 1), 's  tris', tri_count(Z.col), flush=True)
    # night: cool window light from +Y (big soft area), a warm pendant over the living zone
    look5.area('window', (-1.5, 3.9, 1.9), (-1.0, -2.0, 0.6), 260.0, (0.55, 0.68, 1.0), 6.0, 2.4)
    pend = bpy.data.lights.new('pendant', 'POINT')
    pend.energy = 60.0
    pend.color = (1.0, 0.72, 0.45)
    pend.shadow_soft_size = 0.05
    po = bpy.data.objects.new('pendant', pend)
    bpy.context.scene.collection.objects.link(po)
    po.location = (1.3, -1.4, 2.3)
    cam = look5.camera('cam', 26)
    pos, tgt, lens, w, h = ZONE_SHOTS[shot]
    look5.aim(cam, pos, tgt, lens)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = int(w * scale), int(h * scale)
    sc.render.filepath = os.path.join(OUT, f'living_zone_{shot}.png')
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('zone', shot, round(time.time() - t, 1), 's', flush=True)


if __name__ == '__main__':
    names = sys.argv[1].split(',')
    if names[0] == 'zone':
        shots = (sys.argv[2] if len(sys.argv) > 2 else 'wide').split(',')
        scale = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        samples = int(sys.argv[4]) if len(sys.argv) > 4 else 32
        for s in shots:
            zone(s, scale, samples)
    else:
        yaw = float(sys.argv[2]) if len(sys.argv) > 2 else -30.0
        elev = float(sys.argv[3]) if len(sys.argv) > 3 else 18.0
        size = int(sys.argv[4]) if len(sys.argv) > 4 else 448
        samples = int(sys.argv[5]) if len(sys.argv) > 5 else 24
        suffix = sys.argv[6] if len(sys.argv) > 6 else ''
        for n in names:
            t = time.time()
            product(n, yaw, elev, size, samples, suffix)
            print(n, 'total', round(time.time() - t, 1), 's', flush=True)
