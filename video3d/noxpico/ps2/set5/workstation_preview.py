"""Previews for set5.workstation (one render per process; the CPU is shared).

    ../blender-venv/bin/python set5/workstation_preview.py prop  bench|stool|iron  out.png yaw elev [size] [samples]
    ../blender-venv/bin/python set5/workstation_preview.py comp  nox|wide|win|close|winP  out.png [w] [h] [samples]
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import kit5  # noqa: E402
import look5  # noqa: E402
import mat5  # noqa: E402
from set5 import workstation as ws  # noqa: E402


def tri_count(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in objs:
        if o.type in ('MESH', 'CURVE'):
            e = o.evaluated_get(dg)
            try:
                me = e.to_mesh()
            except Exception:
                continue
            if me:
                me.calc_loop_triangles()
                n += len(me.loop_triangles)
                e.to_mesh_clear()
    return n


def prop(which, out, yaw, elev, size=512, samples=24):
    fn = {'bench': ws.build_bench, 'stool': ws.build_stool, 'iron': ws.build_iron}[which]
    P = look5.preview(fn, out, size=(size, size), yaw=yaw, elev=elev, samples=samples)
    print('triangles', tri_count(P.col.all_objects), flush=True)


VIEWS = {
    # name: (camera pos, target, lens)  -- bench-local coordinates
    'nox': ((0.62, -1.62, 1.40), (-0.08, 0.02, 0.93), 28),
    'wide': ((0.25, -3.0, 1.62), (-0.05, 0.05, 0.78), 24),
    'win': ((0.20, 0.385, 1.16), (0.02, -0.85, 1.02), 30),
    'winP': ((0.14, 0.43, 1.22), (0.05, -0.70, 1.12), 40),
    'winW': ((0.25, 0.43, 1.30), (0.0, -0.80, 0.95), 24),
    'close': ((0.30, -0.42, 1.10), ws.BOARD, 45),
    'right': ((1.25, -0.95, 1.35), (0.75, 0.0, 0.85), 30),
    'stand': ((0.05, -0.62, 1.02), (0.42, -0.16, 0.86), 35),
    'left': ((-0.55, -1.1, 1.35), (-0.95, 0.15, 0.95), 30),
}


def environment():
    E = kit5.Prop('_env')
    E.box('floor', (9, 7, 0.02), (0, -2.0, -0.01), 'concrete_floor', bevel=0)
    E.box('upstand', (7.0, 0.20, 0.70), (0, 0.55, 0.35), 'concrete_wall', bevel=0.004)
    E.box('sill', (7.0, 0.26, 0.05), (0, 0.53, 0.705), 'concrete_wall', bevel=0.004)
    night = mat5.emissive('_night', (40, 62, 110), 0.25, (5, 7, 12))
    E.plane('glass', (7.0, 2.45), (0, 0.62, 0.70 + 1.225), night, rot=(90, 0, 0))
    for k in range(8):
        E.box('mullion', (0.06, 0.12, 2.45), (-3.5 + k * 1.0 + 0.35, 0.56, 0.70 + 1.225), 'steel_black', bevel=0.003)
    for z in (1.55, 2.35, 3.15):
        E.box('transom', (7.0, 0.12, 0.05), (0, 0.56, z), 'steel_black', bevel=0.003)
    return E


def comp(view, out, w=512, h=384, samples=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    look5.setup(w, h, samples)
    look5.world((0.010, 0.014, 0.030), 1.0)
    t = time.time()
    B, S, I, C = ws.build_all()
    environment()
    if view.startswith('win'):
        D = kit5.Prop('_dummy')
        skin = mat5.matte('_skin', (190, 150, 130), 0.6)
        cloth = mat5.fabric('_cloth', (40, 90, 60))
        D.sphere('head', 0.105, (0.05, -0.70, 1.24), skin, scale=(0.85, 1.0, 1.15))
        D.box('torso', (0.40, 0.22, 0.56), (0.05, -0.80, 0.86), cloth, rot=(-12, 0, 0), bevel=0.06, segments=3)
        for sx in (-1, 1):
            D.box('thigh', (0.15, 0.42, 0.15), (0.05 + sx * 0.10, -0.62, 0.60), cloth, bevel=0.05, segments=3)
            D.box('forearm', (0.08, 0.30, 0.08), (0.05 + sx * 0.16, -0.40, 0.86), skin, rot=(10, 0, -sx * 15), bevel=0.03, segments=3)
    print(f'build {time.time() - t:.1f} s', flush=True)
    look5.area('window', (0, 0.9, 1.9), (0, -1.0, 0.9), 120, (0.42, 0.56, 1.0), 6.0, 2.4)
    for x in (-0.85, 0.55):
        ld = bpy.data.lights.new('pend', 'POINT')
        ld.energy, ld.color, ld.shadow_soft_size = 35, (1.0, 0.78, 0.52), 0.05
        o = bpy.data.objects.new('pend', ld)
        bpy.context.scene.collection.objects.link(o)
        o.location = (x, -0.25, 2.1)
    pos, tgt, lens = VIEWS[view]
    cam = look5.camera('cam', lens)
    look5.aim(cam, pos, tgt)
    sc = bpy.context.scene
    sc.render.filepath = out
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'{view}: {time.time() - t:.1f} s -> {out}', flush=True)
    print('bench triangles', tri_count(B.col.all_objects), 'stool', tri_count(S.col.all_objects), 'iron',
          tri_count(I.col.all_objects), flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'prop':
        prop(a[1], a[2], float(a[3]), float(a[4]), *(int(x) for x in a[5:7]))
    else:
        comp(a[1], a[2], *(int(x) for x in a[3:6]))
