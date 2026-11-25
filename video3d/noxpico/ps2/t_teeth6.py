"""Test of teeth6 (teeth, gums, tongue).

    ../blender-venv/bin/python t_teeth6.py check            # no render: sizes, triangle count, tongue/teeth overlaps
    ../blender-venv/bin/python t_teeth6.py sheet [tag]      # open 12 mm / 10 deg, front + 3/4; below: behind the 'lips'
    ../blender-venv/bin/python t_teeth6.py tongue [tag]     # tongue rest / 'up' / 'out' from above; through the teeth; bite
    ../blender-venv/bin/python t_teeth6.py open  [tag]      # mouth open 12 mm / 10 deg, front + 3/4 view
    ../blender-venv/bin/python t_teeth6.py mask  [tag]      # the same behind a dark elliptical 'lips' opening 45 x 14 mm
    ../blender-venv/bin/python t_teeth6.py mask1 [tag]      # one mouth behind the lips, at about the on-screen size
    ../blender-venv/bin/python t_teeth6.py close [tag]      # one mouth, front, closer (detail of the crowns)
    ../blender-venv/bin/python t_teeth6.py bite  [tag]      # jaw closed, front + side
Renders go to lab/teeth6/."""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
args = sys.argv[1:]
sys.argv = ['x']
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

bpy.ops.wm.read_factory_settings(use_empty=True)
import addon_utils
addon_utils.enable('cycles', default_set=True)
import look5
import teeth6

OUT = f'{HERE}/lab/teeth6'
os.makedirs(OUT, exist_ok=True)
mode = args[0] if args else 'check'
tag = args[1] if len(args) > 1 else 'a'
W = 0.046


def mouth(name, loc, yaw, open_m=0.012, rot=10.0, keys=None, pitch=0.0):
    """One set of teeth under a rig empty placed at loc, turned yaw degrees about Z (and pitched about X)."""
    rig = bpy.data.objects.new(name + '.rig', None)
    bpy.context.scene.collection.objects.link(rig)
    rig.location = loc
    rig.rotation_euler = (math.radians(pitch), 0, math.radians(yaw))
    T = teeth6.build(name, W)
    T['upper'].parent = rig
    T['lower'].parent = rig
    teeth6.set_jaw(T, open_m, rot)
    for k in ('up', 'out'):
        T['tongue'].data.shape_keys.key_blocks[k].value = (keys or {}).get(k, 0.0)
    T['rig'] = rig
    return T


def lips(rig, z, size=(0.045, 0.014), y=-0.006):
    """A dark matte sheet with an elliptical opening, 6 mm in front of the teeth."""
    n = 64
    verts, faces = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        verts.append((0.5 * size[0] * math.cos(a), y, z + 0.5 * size[1] * math.sin(a)))
        verts.append((0.031 * math.cos(a), y, z + 0.0255 * math.sin(a)))
    for i in range(n):
        j = (i + 1) % n
        faces.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    me = bpy.data.meshes.new('lips')
    me.from_pydata(verts, [], faces)
    m = bpy.data.materials.new('lips')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.035, 0.014, 0.013, 1)
    b.inputs['Roughness'].default_value = 0.6
    me.materials.append(m)
    ob = bpy.data.objects.new('lips', me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = rig
    return ob


def lights(c):
    c = Vector(c)
    look5.world((0.006, 0.008, 0.014), 1.0)
    look5.area('key', c + Vector((-0.22, -0.50, 0.30)), c, 7.0, (1.0, 0.86, 0.70), 0.25)
    look5.area('fill', c + Vector((0.40, -0.40, -0.05)), c, 1.2, (0.55, 0.68, 1.0), 0.40)


def tri_count(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for o in objs:
        me = o.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
    return n


def world_bvh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    M = ob.matrix_world
    return BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])


def render(name, w, h, samples=48):
    sc = bpy.context.scene
    sc.render.filepath = f'{OUT}/{name}.png'
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('RENDER', name, round(time.time() - t, 1), 's', flush=True)


if mode == 'check':
    T = mouth('nox', (0, 0, 0), 0)
    bpy.context.view_layer.update()
    print('scale', round(T['scale'], 4), 'bite (mm)', [round(x * 1000, 2) for x in T['bite']])
    print('dims (mm)', {k: ([round(x * 1000, 1) for x in v] if isinstance(v, list) else round(v * 1000, 2))
                        for k, v in T['dims'].items()})
    for o in T['objects']:
        print(' ', o.name, 'tris', tri_count([o]), 'bbox (mm)',
              [round(x * 1000, 1) for x in (min(c[0] for c in o.bound_box), max(c[0] for c in o.bound_box),
                                            min(c[1] for c in o.bound_box), max(c[1] for c in o.bound_box),
                                            min(c[2] for c in o.bound_box), max(c[2] for c in o.bound_box))])
    print('TOTAL tris', tri_count(T['objects']))
    kb = T['tongue'].data.shape_keys.key_blocks
    # tongue against the lower teeth for every key, against the upper teeth for a few jaw openings
    for label, vals, open_m, rot in (('rest', {}, 0.012, 10.0), ('up.5', {'up': 0.5}, 0.005, 3.0),
                                     ('up1', {'up': 1.0}, 0.005, 3.0), ('up1 open12', {'up': 1.0}, 0.012, 10.0),
                                     ('out.5', {'out': 0.5}, 0.007, 4.0), ('out1', {'out': 1.0}, 0.007, 4.0),
                                     ('out1 open12', {'out': 1.0}, 0.012, 10.0), ('rest closed', {}, 0.0, 0.0),
                                     ('rest open3', {}, 0.003, 1.0),
                                     ('out1 closed (sanity: must collide)', {'out': 1.0}, 0.0, 0.0)):
        for k in ('up', 'out'):
            kb[k].value = vals.get(k, 0.0)
        teeth6.set_jaw(T, open_m, rot)
        bpy.context.view_layer.update()
        tb = world_bvh(T['tongue'])
        lo = len(tb.overlap(world_bvh(T['lower_teeth'])))
        up = len(tb.overlap(world_bvh(T['upper_teeth'])))
        dg = bpy.context.evaluated_depsgraph_get()
        me = T['tongue'].evaluated_get(dg).to_mesh()
        co = np.array([T['tongue'].matrix_world @ v.co for v in me.vertices]) * 1000
        tip = co[co[:, 1].argmin()]
        print(f'  {label:14s} tongue x lower teeth: {lo:4d} pairs, x upper teeth: {up:4d} pairs; '
              f'front-most point (mm, upper space) {np.round(tip, 1)}; width {np.ptp(co[:, 0]):.1f}')
    # closed bite: do the arches collide?
    teeth6.set_jaw(T, 0.0, 0.0)
    bpy.context.view_layer.update()
    print('closed bite: upper teeth x lower teeth', len(world_bvh(T['upper_teeth']).overlap(world_bvh(T['lower_teeth']))),
          'pairs')
    sys.exit(0)

if mode in ('open', 'mask'):
    A = mouth('nox', (-0.040, 0, 0), 0)
    B = mouth('nox', (0.030, 0.01, 0), -38)
    if mode == 'mask':
        lips(A['rig'], -0.0042)
        lips(B['rig'], -0.0042)
    sc = look5.setup(640, 384, 48)
    lights((0, 0, -0.004))
    cam = look5.camera('cam', 78)
    look5.aim(cam, (0.0, -0.37, 0.012), (0.0, 0.0, -0.003))
    render(f'{mode}_{tag}', 640, 384)
elif mode == 'sheet':               # top: mouth open 12 mm / 10 deg, front and 3/4; bottom: the same behind the lips
    for z, masked in ((0.031, False), (-0.033, True)):
        A = mouth('nox', (-0.040, 0, z), 0)
        B = mouth('nox', (0.032, 0.01, z), -38)
        if masked:
            lips(A['rig'], -0.0042)
            lips(B['rig'], -0.0042)
    sc = look5.setup(640, 480, 48)
    lights((0, 0, -0.002))
    cam = look5.camera('cam', 78)
    look5.aim(cam, (0.0, -0.37, 0.008), (0.0, 0.0, -0.003))
    render(f'sheet_{tag}', 640, 480)
elif mode == 'tongue':
    # top row: lower jaw alone seen from above (rest, 'up', 'out'); bottom row, from slightly below: 'up' with the
    # jaw open 5 mm, 'out' with the jaw open 8 mm, and the closed bite
    for x, keys in ((-0.062, {}), (0.0, {'up': 1.0}), (0.062, {'out': 1.0})):
        A = mouth('nox', (x, 0.0, 0.026), -20, open_m=0.0, rot=0.0, keys=keys, pitch=52)
        for o in (A['upper_teeth'], A['upper_gum']):
            o.hide_render = True
    mouth('nox', (-0.064, 0.0, -0.034), -28, open_m=0.005, rot=3.0, keys={'up': 1.0}, pitch=-10)
    mouth('nox', (0.0, 0.0, -0.034), -28, open_m=0.008, rot=5.0, keys={'out': 1.0}, pitch=-10)
    mouth('nox', (0.064, 0.0, -0.034), -28, open_m=0.0, rot=0.0, pitch=-4)
    sc = look5.setup(640, 400, 48)
    lights((0, 0, 0.0))
    cam = look5.camera('cam', 85)
    look5.aim(cam, (0.0, -0.46, 0.0), (0.0, 0.0, 0.0))
    render(f'tongue_{tag}', 640, 400)
elif mode == 'mask1':               # one mouth behind the lips opening, at about the final on-screen size
    A = mouth('nox', (0, 0, 0), 0)
    lips(A['rig'], -0.0042)
    sc = look5.setup(640, 384, 48)
    lights((0, 0, -0.004))
    cam = look5.camera('cam', 85)
    look5.aim(cam, (0.0, -0.19, 0.004), (0.0, 0.0, -0.0042))
    render(f'mask1_{tag}', 640, 384)
elif mode == 'close':
    A = mouth('nox', (0, 0, 0), 0, open_m=0.010, rot=8.0)
    sc = look5.setup(640, 448, 48)
    lights((0, 0, -0.004))
    cam = look5.camera('cam', 85)
    look5.aim(cam, (0.0, -0.21, 0.006), (0.0, 0.0, -0.003))
    render(f'close_{tag}', 640, 448)
elif mode == 'bite':
    A = mouth('nox', (-0.036, 0, 0), 0, open_m=0.0, rot=0.0)
    B = mouth('nox', (0.036, 0.025, 0), -80, open_m=0.0, rot=0.0)
    sc = look5.setup(640, 384, 48)
    lights((0, 0, 0.002))
    cam = look5.camera('cam', 85)
    look5.aim(cam, (0.0, -0.37, 0.004), (0.0, 0.0, 0.002))
    render(f'bite_{tag}', 640, 384)
