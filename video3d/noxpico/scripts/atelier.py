"""Nox's workshop (episode 1 layout), built from the Meshy props + a simple room shell with pixel-art textures.

    import atelier; A = atelier.build()     -> dict(objects=..., lights=..., marks=...)
World: Z up, metres; the camera side is -Y; back wall at y = WALL_Y."""
import math
import os

import bpy
import numpy as np
from mathutils import Vector

S = '/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad'
PROPS = S + '/meshy/models/props'
FLAT = S + '/meshy/np/props'
WALL_Y, HALF_W, DEPTH, CEIL = 2.0, 1.85, -2.6, 2.7

# where the characters stand and walk (used by the shots)
MARKS = dict(nox=(-0.72, 1.55), door=(1.3, 1.95), pico_stop=(0.45, 0.95), pico_close=(0.35, 0.95))


def lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def img_from_array(name, arr):
    """arr: (H, W, 3|4) sRGB 0..1, row 0 = top."""
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1))], axis=2)
    im = bpy.data.images.new(name, w, h, alpha=True)
    im.pixels.foreach_set(arr[::-1].astype(np.float32).ravel())
    im.pack()
    return im


def img_load(path):
    im = bpy.data.images.load(path)
    im.pack()
    return im


def mat_tex(name, img, scale=(1, 1), emit=0.0, alpha=False, rough=1.0, coords='UV'):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = 'Closest'
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale[0], scale[1], 1)
    nt.links.new(tc.outputs[coords], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], tx.inputs['Vector'])
    nt.links.new(tx.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = 0.0
    if emit:
        nt.links.new(tx.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = emit
    if alpha:
        nt.links.new(tx.outputs['Alpha'], b.inputs['Alpha'])
    return m


def mat_col(name, rgb, emit=0.0, rough=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = tuple(lin(rgb)) + (1,)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = 0.0
    if emit:
        b.inputs['Emission Color'].default_value = tuple(lin(rgb)) + (1,)
        b.inputs['Emission Strength'].default_value = emit
    return m


def quad(name, corners, mat, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c in corners], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name='UVMap')
    for li, t in zip(me.polygons[0].loop_indices, uv):
        uvl.data[li].uv = t
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def box(name, c, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=c)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    ob.data.materials.append(mat)
    return ob


# ---------------------------------------------------------------- pixel-art textures
def tex_wallpaper(rng):
    W, H = 64, 64
    a = np.zeros((H, W, 3))
    base = np.array([30, 36, 70]) / 255
    a[:] = base
    for x in range(W):
        k = x % 16
        if k in (0, 1):
            a[:, x] = np.array([22, 27, 54]) / 255
        elif k in (7, 8):
            a[:, x] = np.array([38, 45, 86]) / 255
    a *= (0.96 + 0.08 * rng.random((H, W, 1)))
    return np.clip(a, 0, 1)


def tex_floor(rng):
    W, H = 64, 64
    a = np.zeros((H, W, 3))
    cols = [np.array([96, 60, 36]), np.array([84, 52, 31]), np.array([104, 66, 40]), np.array([78, 48, 28])]
    for p in range(4):
        y0 = p * 16
        c = cols[p] / 255
        a[y0:y0 + 16] = c
        a[y0] = c * 0.55
        a[y0 + 1] = c * 1.12
        off = int(rng.integers(0, 64))
        a[y0:y0 + 16, off % 64] = c * 0.6
        for _ in range(6):
            gy, gx = y0 + int(rng.integers(3, 14)), int(rng.integers(0, 60))
            a[gy, gx:gx + int(rng.integers(3, 9))] = c * 0.86
    a *= (0.97 + 0.06 * rng.random((H, W, 1)))
    return np.clip(a, 0, 1)


def tex_curtain():
    W, H = 32, 64
    a = np.zeros((H, W, 3))
    for x in range(W):
        f = 0.75 + 0.25 * math.sin(x / W * 2 * math.pi * 3)
        a[:, x] = np.array([52, 36, 78]) / 255 * f
    a[-3:] *= 0.7
    return a


# ---------------------------------------------------------------- props
def prop(name, size, loc, rot_z=0.0, axis=2, pass_index=None):
    """Import a Meshy prop, scale it so that its dimension along `axis` equals size, put its base on loc."""
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(PROPS, name + '.glb'))
    new = [o for o in bpy.context.scene.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    root = next((o for o in new if o.parent is None), meshes[0])
    bpy.context.view_layer.update()
    co = np.array([tuple(o.matrix_world @ v.co) for o in meshes for v in o.data.vertices])
    lo, hi = co.min(0), co.max(0)
    k = size / (hi[axis] - lo[axis])
    centre = (lo + hi) / 2
    empty = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(empty)
    for o in new:
        if o.parent is None:
            o.parent = empty
    empty.scale = (k, k, k)
    # base centre of the prop -> origin of the empty, then move
    for o in new:
        if o.parent is empty:
            o.location = Vector(tuple(o.location)) - Vector((centre[0], centre[1], lo[2]))
    empty.location = Vector(loc)
    empty.rotation_euler = (0, 0, rot_z)
    for o in meshes:
        for m in o.data.materials:
            if m and m.node_tree:
                for n in m.node_tree.nodes:
                    if n.type == 'BSDF_PRINCIPLED':
                        n.inputs['Roughness'].default_value = 1.0
                        n.inputs['Specular IOR Level'].default_value = 0.0
                        n.inputs['Metallic'].default_value = 0.0
    return empty, meshes


def decal(name, png, centre, width, normal='-Y', emit=0.0, flat_floor=False):
    from PIL import Image
    im = Image.open(png)
    w, h = im.size
    hgt = width * h / w
    img = img_load(png)
    m = mat_tex(name + '_m', img, alpha=True, emit=emit)
    cx, cy, cz = centre
    if flat_floor:
        c = [(cx - width / 2, cy - hgt / 2, cz), (cx + width / 2, cy - hgt / 2, cz), (cx + width / 2, cy + hgt / 2, cz), (cx - width / 2, cy + hgt / 2, cz)]
    else:
        c = [(cx - width / 2, cy, cz - hgt / 2), (cx + width / 2, cy, cz - hgt / 2), (cx + width / 2, cy, cz + hgt / 2), (cx - width / 2, cy, cz + hgt / 2)]
    return quad(name, c, m)


def garland(x0, x1, z, y, sag=0.12, n=22):
    wire = mat_col('wire', [20, 24, 30])
    bulbs = [mat_col('bulb_g', [80, 255, 140], emit=6.0), mat_col('bulb_w', [255, 196, 110], emit=6.0)]
    obs = []
    pts = []
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t
        seg = (t * 4) % 1.0                              # four festoons
        zz = z - sag * 4 * seg * (1 - seg)
        pts.append((x, y, zz))
    cu = bpy.data.curves.new('garland', 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.004
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1)
    ob = bpy.data.objects.new('garland', cu)
    ob.data.materials.append(wire)
    bpy.context.scene.collection.objects.link(ob)
    obs.append(ob)
    for i, q in enumerate(pts[1:-1]):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.022, segments=8, ring_count=6, location=(q[0], q[1] - 0.01, q[2] - 0.03))
        b = bpy.context.active_object
        b.data.materials.append(bulbs[i % 2])
        obs.append(b)
    return obs


def build(rng_seed=3):
    rng = np.random.default_rng(rng_seed)
    sc = bpy.context.scene
    objs = {}
    wall = mat_tex('wallpaper', img_from_array('wallpaper', tex_wallpaper(rng)), scale=(9, 4.8))
    floor = mat_tex('floor', img_from_array('floor', tex_floor(rng)), scale=(5, 4.5))
    objs['floor'] = quad('floor', [(-HALF_W, DEPTH, 0), (HALF_W, DEPTH, 0), (HALF_W, WALL_Y, 0), (-HALF_W, WALL_Y, 0)], floor)
    objs['back'] = quad('wall_back', [(-HALF_W, WALL_Y, 0), (HALF_W, WALL_Y, 0), (HALF_W, WALL_Y, CEIL), (-HALF_W, WALL_Y, CEIL)], wall)
    objs['left'] = quad('wall_left', [(-HALF_W, DEPTH, 0), (-HALF_W, WALL_Y, 0), (-HALF_W, WALL_Y, CEIL), (-HALF_W, DEPTH, CEIL)], wall)
    objs['right'] = quad('wall_right', [(HALF_W, WALL_Y, 0), (HALF_W, DEPTH, 0), (HALF_W, DEPTH, CEIL), (HALF_W, WALL_Y, CEIL)], wall)
    objs['ceil'] = quad('ceiling', [(-HALF_W, DEPTH, CEIL), (-HALF_W, WALL_Y, CEIL), (HALF_W, WALL_Y, CEIL), (HALF_W, DEPTH, CEIL)], mat_col('ceil', [18, 20, 36]))
    base = mat_col('baseboard', [24, 20, 30])
    box('baseboard', (0, WALL_Y - 0.01, 0.05), (2 * HALF_W, 0.02, 0.1), base)
    # window with the night city behind it
    wx, wz0, wz1, ww = 0.4, 1.2, 2.25, 0.95
    wood = mat_col('window_wood', [58, 40, 34])
    for nm, c, s in (('win_l', (wx - ww / 2, WALL_Y - 0.03, (wz0 + wz1) / 2), (0.06, 0.08, wz1 - wz0 + 0.06)),
                     ('win_r', (wx + ww / 2, WALL_Y - 0.03, (wz0 + wz1) / 2), (0.06, 0.08, wz1 - wz0 + 0.06)),
                     ('win_t', (wx, WALL_Y - 0.03, wz1), (ww + 0.06, 0.08, 0.06)), ('win_b', (wx, WALL_Y - 0.05, wz0), (ww + 0.16, 0.14, 0.06)),
                     ('win_mv', (wx, WALL_Y - 0.03, (wz0 + wz1) / 2), (0.035, 0.05, wz1 - wz0)), ('win_mh', (wx, WALL_Y - 0.03, (wz0 + wz1) / 2 + 0.1), (ww, 0.05, 0.035))):
        box(nm, c, s, wood)
    night = mat_tex('night', img_load(FLAT + '/night.png'), emit=1.0)
    objs['night'] = quad('night', [(wx - ww / 2, WALL_Y + 0.02, wz0), (wx + ww / 2, WALL_Y + 0.02, wz0), (wx + ww / 2, WALL_Y + 0.02, wz1), (wx - ww / 2, WALL_Y + 0.02, wz1)], night,
                         uv=((0.18, 0.0), (0.82, 0.0), (0.82, 1.0), (0.18, 1.0)))
    curt = mat_tex('curtain', img_from_array('curtain', tex_curtain()), scale=(1, 1))
    for s_ in (-1, 1):
        x0 = wx + s_ * (ww / 2 + 0.05)
        x1 = wx + s_ * (ww / 2 - 0.22)
        quad(f'curtain_{s_}', [(min(x0, x1), WALL_Y - 0.09, wz0 - 0.15), (max(x0, x1), WALL_Y - 0.09, wz0 - 0.15), (max(x0, x1), WALL_Y - 0.09, wz1 + 0.12), (min(x0, x1), WALL_Y - 0.09, wz1 + 0.12)], curt)
    box('curtain_rod', (wx, WALL_Y - 0.1, wz1 + 0.14), (ww + 0.7, 0.02, 0.02), mat_col('rod', [150, 150, 160]))
    # furniture and props (Meshy)
    objs['bookshelf'] = prop('bookshelf', 1.75, (-1.36, WALL_Y - 0.17, 0))
    objs['workbench'] = prop('workbench', 1.25, (-0.72, 0.98, 0), axis=0)
    objs['workbench'][0].scale.z *= 1.28                      # standing-height workbench (top at about 0.88 m)
    objs['door'] = prop('door', 2.05, (1.32, WALL_Y - 0.03, 0))
    objs['plant'] = prop('plant', 0.95, (1.62, 1.35, 0))
    objs['ukulele'] = prop('ukulele', 0.5, (0.98, WALL_Y - 0.05, 1.25))
    objs['stool'] = prop('stool', 0.5, (-1.55, 0.75, 0))
    objs['mug'] = prop('mug', 0.1, (-0.38, 0.93, 0.0), axis=2)
    objs['sneakers'] = prop('sneakers', 0.28, (0.98, 1.62, 0), rot_z=0.35, axis=0)
    objs['bip'] = prop('bip', 0.24, (-1.36, WALL_Y - 0.25, 1.76))
    # flat wall pieces
    decal('pegboard', FLAT + '/pegboard_alpha.png', (-0.42, WALL_Y - 0.02, 1.62), 0.7)
    decal('clock', FLAT + '/clock_alpha.png', (-0.42, WALL_Y - 0.02, 2.33), 0.3, emit=0.6)
    decal('rug', FLAT + '/rug_alpha.png', (0.3, 0.45, 0.004), 1.5, flat_floor=True)
    garland(-HALF_W + 0.1, HALF_W - 0.1, CEIL - 0.08, WALL_Y - 0.05)
    return objs


def place_on_bench(objs):
    """Put the mug on the workbench top (the bench height is measured)."""
    wb = objs['workbench'][1]
    bpy.context.view_layer.update()
    co = np.array([tuple(o.matrix_world @ v.co) for o in wb for v in o.data.vertices])
    top = float(np.percentile(co[:, 2], 80))
    objs['mug'][0].location.z = top
    return top


def lights(strength=1.0):
    from pxrender import area, point
    L = {}
    w = bpy.data.worlds.new('night_world')
    bpy.context.scene.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.025, 0.06, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    L['ceiling'] = area('ceiling', (-0.1, 0.6, CEIL - 0.05), (-0.1, 0.6, 0), 150 * strength, (1.0, 0.86, 0.7), 1.4)
    L['moon'] = area('moon', (0.4, WALL_Y + 0.6, 1.8), (0.2, 0.0, 0.8), 110 * strength, (0.55, 0.65, 1.0), 0.9)
    L['door'] = area('door_spill', (1.32, WALL_Y - 0.25, 2.1), (0.9, 0.6, 0.0), 70 * strength, (1.0, 0.72, 0.42), 0.6)
    L['scope'] = point('scope_glow', (-0.95, 1.05, 1.05), 10 * strength, (0.35, 1.0, 0.55), 0.05)
    L['fill'] = area('fill', (0.0, -2.0, 1.6), (0.0, 1.0, 1.0), 50 * strength, (0.75, 0.8, 1.0), 2.5)
    return L
