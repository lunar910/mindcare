"""Nox's workshop, version 2: everything at real scale, flat pieces drawn front-on, a real doorway.   import atelier2 as AT

    A = AT.build()   -> dict(objs=..., door_hinge=..., door_meshes=[...], bench_top=..., marks=...)

World: Z up, metres.  The camera side is -Y, the back wall is at y = WALL_Y.  Sizes that matter:
    door leaf 0.9 x 2.04 m, window sill at 1.0 m, workbench top at 0.96 m (hip height of Nox, who stands at it),
    bookcase 1.5 m, pegboard 0.84 x 0.62 m with 15-30 cm tools, wall clock 0.30 m, round rug 1.5 m."""
import math
import os

import bpy
import numpy as np
from mathutils import Vector

import tex2

S = '/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad'
PROPS = S + '/meshy/models/props'
FLAT = S + '/meshy/np/props'
WALL_Y, HALF_W, FRONT, CEIL = 2.0, 1.95, -3.4, 2.9
DOOR_X1, DOOR_H = 1.46, 2.04                 # hinge side of the doorway (the leaf width is measured on the model)
BENCH = dict(x=-0.78, y=1.06, top=0.96, width=1.12, depth=0.62)
MARKS = dict(nox=(-0.78, 1.58), pico=(0.50, 1.50), door=(1.05, 2.47))


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


def img_from_pil(name, pil):
    return img_from_array(name, np.asarray(pil.convert('RGBA')).astype(np.float32) / 255.0)


def mat_tex(name, img, emit=0.0, alpha=False, interp='Linear', emit_img=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = interp
    nt.links.new(tx.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 1.0
    b.inputs['Specular IOR Level'].default_value = 0.0
    if emit:
        if emit_img is not None:
            te = nt.nodes.new('ShaderNodeTexImage')
            te.image = emit_img
            te.interpolation = interp
            nt.links.new(te.outputs['Color'], b.inputs['Emission Color'])
        else:
            nt.links.new(tx.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = emit
    if alpha:
        nt.links.new(tx.outputs['Alpha'], b.inputs['Alpha'])
    return m


def mat_col(name, rgb, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = tuple(lin(rgb)) + (1,)
    b.inputs['Roughness'].default_value = 1.0
    b.inputs['Specular IOR Level'].default_value = 0.0
    if emit:
        b.inputs['Emission Color'].default_value = tuple(lin(rgb)) + (1,)
        b.inputs['Emission Strength'].default_value = emit
    return m


def quad(name, corners, mat, uv=((0, 0), (1, 0), (1, 1), (0, 1)), tile=None):
    """tile=(tw, th): UVs follow the world size of the quad so that a pattern keeps the same scale on every wall piece."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c in corners], [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name='UVMap')
    if tile:
        c = [Vector(p) for p in corners]
        ex, ey = (c[1] - c[0]), (c[3] - c[0])
        ux, uy = ex.normalized(), ey.normalized()
        o = Vector((0, 0, 0))
        uv = [((p - o).dot(ux) / tile[0], (p - o).dot(uy) / tile[1]) for p in c]
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


# ---------------------------------------------------------------- textures of the shell
def tex_wallpaper(rng):
    W, H = 64, 64
    a = np.zeros((H, W, 3))
    a[:] = np.array([58, 70, 124]) / 255
    for x in range(W):
        k = x % 16
        if k in (0, 1):
            a[:, x] = np.array([47, 57, 104]) / 255
        elif k in (7, 8):
            a[:, x] = np.array([68, 81, 140]) / 255
    a *= (0.97 + 0.06 * rng.random((H, W, 1)))
    return np.clip(a, 0, 1)


def tex_floor(rng):
    W, H = 64, 64
    a = np.zeros((H, W, 3))
    cols = [np.array([150, 98, 60]), np.array([136, 88, 54]), np.array([160, 106, 66]), np.array([128, 82, 50])]
    for p in range(4):
        y0 = p * 16
        c = cols[p] / 255
        a[y0:y0 + 16] = c
        a[y0] = c * 0.6
        a[y0 + 1] = c * 1.10
        off = int(rng.integers(0, 64))
        a[y0:y0 + 16, off % 64] = c * 0.65
        for _ in range(6):
            gy, gx = y0 + int(rng.integers(3, 14)), int(rng.integers(0, 60))
            a[gy, gx:gx + int(rng.integers(3, 9))] = c * 0.88
    a *= (0.97 + 0.06 * rng.random((H, W, 1)))
    return np.clip(a, 0, 1)


def tex_curtain():
    W, H = 32, 64
    a = np.zeros((H, W, 3))
    for x in range(W):
        f = 0.78 + 0.22 * math.sin(x / W * 2 * math.pi * 3)
        a[:, x] = np.array([92, 62, 132]) / 255 * f
    a[-3:] *= 0.75
    return a


# ---------------------------------------------------------------- Meshy props
def prop(name, size, loc, rot_z=0.0, axis=2):
    """Import a Meshy prop, scale it so that its dimension along `axis` equals size, put its base centre on loc."""
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(PROPS, name + '.glb'))
    new = [o for o in bpy.context.scene.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    bpy.context.view_layer.update()
    co = np.array([tuple(o.matrix_world @ v.co) for o in meshes for v in o.data.vertices])
    lo, hi = co.min(0), co.max(0)
    k = size / (hi[axis] - lo[axis])
    centre = (lo + hi) / 2
    # bake the placement into the mesh data: metres, base centre at the origin of one clean object
    for o in meshes:
        M = o.matrix_world.copy()
        o.data.transform(M)
        o.parent = None
        o.matrix_world.identity()
        for v in o.data.vertices:
            v.co = (Vector(v.co) - Vector((centre[0], centre[1], lo[2]))) * k
        o.data.update()
    for o in new:
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    empty = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(empty)
    for o in meshes:
        o.parent = empty
        for m in o.data.materials:
            if m and m.node_tree:
                for n in m.node_tree.nodes:
                    if n.type == 'BSDF_PRINCIPLED':
                        for inp in ('Metallic', 'Roughness', 'Normal'):
                            for l in list(n.inputs[inp].links):
                                m.node_tree.links.remove(l)
                        n.inputs['Roughness'].default_value = 1.0
                        n.inputs['Specular IOR Level'].default_value = 0.0
                        n.inputs['Metallic'].default_value = 0.0
    empty.location = Vector(loc)
    empty.rotation_euler = (0, 0, rot_z)
    bpy.context.view_layer.update()
    return empty, meshes


def prop_size(meshes):
    bpy.context.view_layer.update()
    co = np.array([tuple(o.matrix_world @ v.co) for o in meshes for v in o.data.vertices])
    return co.min(0), co.max(0)


def stretch_legs(meshes, top_now, top_target):
    """Make a table taller by lengthening only what is under the table top (what stands on it keeps its proportions)."""
    cut = top_now - 0.09
    s = (top_target - (top_now - cut)) / cut
    for o in meshes:
        for v in o.data.vertices:
            z = v.co.z
            v.co.z = z * s if z <= cut else z + (top_target - top_now)
        o.data.update()


def flat(name, pil_size, centre, mat_kw=None, normal='-Y', thick=0.0, frame=None):
    """A flat piece on a wall (picture, board, clock).  pil_size = (PIL image, (width_m, height_m))."""
    pil, (w, h) = pil_size
    img = img_from_pil(name + '_img', pil)
    m = mat_tex(name + '_m', img, alpha=True, interp='Closest', **(mat_kw or {}))
    cx, cy, cz = centre
    if normal == '-Y':
        c = [(cx - w / 2, cy, cz - h / 2), (cx + w / 2, cy, cz - h / 2), (cx + w / 2, cy, cz + h / 2), (cx - w / 2, cy, cz + h / 2)]
    elif normal == '+X':                                   # on the left wall, facing the room
        c = [(cx, cy + w / 2, cz - h / 2), (cx, cy - w / 2, cz - h / 2), (cx, cy - w / 2, cz + h / 2), (cx, cy + w / 2, cz + h / 2)]
    elif normal == '-X':                                   # on the right wall
        c = [(cx, cy - w / 2, cz - h / 2), (cx, cy + w / 2, cz - h / 2), (cx, cy + w / 2, cz + h / 2), (cx, cy - w / 2, cz + h / 2)]
    else:                                                  # '+Z': lying on the floor
        c = [(cx - w / 2, cy - h / 2, cz), (cx + w / 2, cy - h / 2, cz), (cx + w / 2, cy + h / 2, cz), (cx - w / 2, cy + h / 2, cz)]
    return quad(name, c, m)


def garland(x0, x1, z, y, sag=0.10, n=26, festoons=4):
    wire = mat_col('wire', [30, 34, 44])
    bulbs = [mat_col('bulb_g', [80, 255, 140], emit=5.0), mat_col('bulb_w', [255, 196, 110], emit=5.0)]
    pts = []
    for i in range(n + 1):
        t = i / n
        seg = (t * festoons) % 1.0
        pts.append((x0 + (x1 - x0) * t, y, z - sag * 4 * seg * (1 - seg)))
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
    obs = [ob]
    for i, q in enumerate(pts[1:-1]):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.02, segments=8, ring_count=6, location=(q[0], q[1] - 0.01, q[2] - 0.03))
        b = bpy.context.active_object
        b.name = f'bulb_{i}'
        b.data.materials.append(bulbs[i % 2])
        obs.append(b)
    return obs


def build(rng_seed=3):
    rng = np.random.default_rng(rng_seed)
    objs = {}
    wall = mat_tex('wallpaper', img_from_array('wallpaper', tex_wallpaper(rng)))
    floor = mat_tex('floor', img_from_array('floor', tex_floor(rng)))
    WT, FT = (0.42, 0.42), (0.90, 0.56)                        # size of one wallpaper tile / one floor tile (4 planks), metres

    # the door first: its measured width gives the doorway
    door, dm = prop('door', DOOR_H, (0, 0, 0))
    lo, hi = prop_size(dm)
    dw, dth = hi[0] - lo[0], hi[1] - lo[1]
    x1 = DOOR_X1
    x0 = x1 - dw
    hinge = bpy.data.objects.new('door_hinge', None)
    bpy.context.scene.collection.objects.link(hinge)
    hinge.location = (x1, WALL_Y - dth / 2 - 0.01, 0)
    door.parent = hinge
    door.location = (-dw / 2, 0, 0)                            # leaf from the hinge towards -X
    objs['door'] = (door, dm)

    # shell: floor, back wall with the doorway, side walls, ceiling
    objs['floor'] = quad('floor', [(-HALF_W, FRONT, 0), (HALF_W, FRONT, 0), (HALF_W, WALL_Y, 0), (-HALF_W, WALL_Y, 0)], floor, tile=FT)
    for nm, (a, b, z0, z1) in dict(wall_bl=(-HALF_W, x0, 0, CEIL), wall_bt=(x0, x1, DOOR_H, CEIL), wall_br=(x1, HALF_W, 0, CEIL)).items():
        quad(nm, [(a, WALL_Y, z0), (b, WALL_Y, z0), (b, WALL_Y, z1), (a, WALL_Y, z1)], wall, tile=WT)
    quad('wall_left', [(-HALF_W, FRONT, 0), (-HALF_W, WALL_Y, 0), (-HALF_W, WALL_Y, CEIL), (-HALF_W, FRONT, CEIL)], wall, tile=WT)
    quad('wall_right', [(HALF_W, WALL_Y, 0), (HALF_W, FRONT, 0), (HALF_W, FRONT, CEIL), (HALF_W, WALL_Y, CEIL)], wall, tile=WT)
    quad('ceiling', [(-HALF_W, FRONT, CEIL), (-HALF_W, WALL_Y, CEIL), (HALF_W, WALL_Y, CEIL), (HALF_W, FRONT, CEIL)], mat_col('ceil', [44, 50, 84]))
    wood_d = mat_col('wood_dark', [70, 46, 34])
    box('baseboard_l', ((-HALF_W + x0) / 2, WALL_Y - 0.01, 0.05), (x0 + HALF_W, 0.02, 0.10), wood_d)
    box('baseboard_r', ((x1 + HALF_W) / 2, WALL_Y - 0.01, 0.05), (HALF_W - x1, 0.02, 0.10), wood_d)
    box('baseboard_left', (-HALF_W + 0.01, (FRONT + WALL_Y) / 2, 0.05), (0.02, WALL_Y - FRONT, 0.10), wood_d)
    box('baseboard_right', (HALF_W - 0.01, (FRONT + WALL_Y) / 2, 0.05), (0.02, WALL_Y - FRONT, 0.10), wood_d)
    # door frame + the corridor behind (lit, seen when the door opens)
    jamb = mat_col('door_frame', [84, 54, 38])
    box('jamb_l', (x0 - 0.035, WALL_Y - 0.02, DOOR_H / 2), (0.07, 0.10, DOOR_H), jamb)
    box('jamb_r', (x1 + 0.035, WALL_Y - 0.02, DOOR_H / 2), (0.07, 0.10, DOOR_H), jamb)
    box('jamb_t', ((x0 + x1) / 2, WALL_Y - 0.02, DOOR_H + 0.035), (dw + 0.14, 0.10, 0.07), jamb)
    cwp, _ = tex2.corridor_wall(picture=True, width=dw + 1.0, height=CEIL)
    cws, _ = tex2.corridor_wall(picture=False, width=1.3, height=CEIL)
    cw = mat_tex('corridor_wall', img_from_pil('corridor_wall_i', cwp), interp='Closest')
    cs = mat_tex('corridor_side', img_from_pil('corridor_side_i', cws), interp='Closest')
    cf = mat_col('corridor_floor', [150, 100, 64])
    yb = WALL_Y + 1.3
    quad('corr_back', [(x0 - 0.5, yb, 0), (x1 + 0.5, yb, 0), (x1 + 0.5, yb, CEIL), (x0 - 0.5, yb, CEIL)], cw)
    quad('corr_floor', [(x0 - 0.5, WALL_Y, 0), (x1 + 0.5, WALL_Y, 0), (x1 + 0.5, yb, 0), (x0 - 0.5, yb, 0)], cf)
    quad('corr_l', [(x0 - 0.5, yb, 0), (x0 - 0.5, WALL_Y + 0.001, 0), (x0 - 0.5, WALL_Y + 0.001, CEIL), (x0 - 0.5, yb, CEIL)], cs)
    quad('corr_r', [(x1 + 0.5, WALL_Y + 0.001, 0), (x1 + 0.5, yb, 0), (x1 + 0.5, yb, CEIL), (x1 + 0.5, WALL_Y + 0.001, CEIL)], cs)
    quad('corr_ceil', [(x0 - 0.5, WALL_Y, CEIL), (x0 - 0.5, yb, CEIL), (x1 + 0.5, yb, CEIL), (x1 + 0.5, WALL_Y, CEIL)], mat_col('corr_ceil_m', [200, 180, 160]))
    # back side of the room's wall, seen from the corridor through the doorway
    wb_ = mat_col('wall_backside', [200, 150, 116])
    quad('wall_back_in_l', [(x0, WALL_Y + 0.002, 0), (x0 - 0.5, WALL_Y + 0.002, 0), (x0 - 0.5, WALL_Y + 0.002, CEIL), (x0, WALL_Y + 0.002, CEIL)], wb_)
    quad('wall_back_in_r', [(x1 + 0.5, WALL_Y + 0.002, 0), (x1, WALL_Y + 0.002, 0), (x1, WALL_Y + 0.002, CEIL), (x1 + 0.5, WALL_Y + 0.002, CEIL)], wb_)

    # window with the night city behind it
    wx, wz0, wz1, ww = 0.0, 1.0, 2.06, 0.78
    wood = mat_col('window_wood', [92, 62, 48])
    for nm, c, s in (('win_l', (wx - ww / 2, WALL_Y - 0.03, (wz0 + wz1) / 2), (0.06, 0.08, wz1 - wz0 + 0.06)),
                     ('win_r', (wx + ww / 2, WALL_Y - 0.03, (wz0 + wz1) / 2), (0.06, 0.08, wz1 - wz0 + 0.06)),
                     ('win_t', (wx, WALL_Y - 0.03, wz1), (ww + 0.06, 0.08, 0.06)), ('win_b', (wx, WALL_Y - 0.06, wz0), (ww + 0.16, 0.16, 0.05)),
                     ('win_mv', (wx, WALL_Y - 0.03, (wz0 + wz1) / 2), (0.035, 0.05, wz1 - wz0)), ('win_mh', (wx, WALL_Y - 0.03, (wz0 + wz1) / 2 + 0.1), (ww, 0.05, 0.035))):
        box(nm, c, s, wood)
    night_img = bpy.data.images.load(FLAT + '/night.png')
    night_img.pack()
    night = mat_tex('night', night_img, emit=1.0)
    quad('night', [(wx - ww / 2, WALL_Y - 0.005, wz0), (wx + ww / 2, WALL_Y - 0.005, wz0), (wx + ww / 2, WALL_Y - 0.005, wz1), (wx - ww / 2, WALL_Y - 0.005, wz1)], night,
         uv=((0.22, 0.0), (0.72, 0.0), (0.72, 1.0), (0.22, 1.0)))
    curt = mat_tex('curtain', img_from_array('curtain', tex_curtain()))
    for s_ in (-1, 1):
        xa = wx + s_ * (ww / 2 + 0.07)
        xb = wx + s_ * (ww / 2 - 0.16)
        quad(f'curtain_{s_}', [(min(xa, xb), WALL_Y - 0.09, wz0 - 0.18), (max(xa, xb), WALL_Y - 0.09, wz0 - 0.18), (max(xa, xb), WALL_Y - 0.09, wz1 + 0.12),
                               (min(xa, xb), WALL_Y - 0.09, wz1 + 0.12)], curt)
    box('curtain_rod', (wx, WALL_Y - 0.1, wz1 + 0.14), (ww + 0.30, 0.02, 0.02), mat_col('rod', [170, 170, 184]))

    # furniture (Meshy props), each one at a checked real size
    bx, by = BENCH['x'], BENCH['y']
    wb, wbm = prop('workbench', 1.25, (bx, by, 0), axis=0)
    co = np.concatenate([np.array([tuple(v.co) for v in o.data.vertices]) for o in wbm])
    top0 = float(np.percentile(co[:, 2], 80))
    stretch_legs(wbm, top0, BENCH['top'])
    lo, hi = prop_size(wbm)
    wb.scale = (BENCH['width'] / (hi[0] - lo[0]), BENCH['depth'] / (hi[1] - lo[1]), 1.0)
    objs['workbench'] = (wb, wbm)
    objs['bookshelf'] = prop('bookshelf', 1.50, (-HALF_W + 0.16, 1.30, 0), rot_z=math.radians(90))
    objs['plant'] = prop('plant', 0.95, (1.70, 0.72, 0))
    objs['stool'] = prop('stool', 0.50, (-1.58, 0.95, 0))
    objs['mug'] = prop('mug', 0.095, (bx + 0.40, by - 0.12, BENCH['top']), rot_z=0.6)
    objs['sneakers'] = prop('sneakers', 0.28, (-0.02, 1.80, 0), rot_z=0.25, axis=0)
    objs['ukulele'] = prop('ukulele', 0.53, (HALF_W - 0.03, 1.15, 1.25), rot_z=math.radians(-90))
    objs['bip'] = prop('bip', 0.22, (-0.36, 1.66, 2.36))

    # flat pieces, drawn front-on at real scale
    yw = WALL_Y - 0.012
    flat('pegboard', tex2.pegboard(), (-0.92, yw, 1.62))
    ck, sz = tex2.clock()
    cimg = img_from_pil('clock_img', ck)
    cm = mat_tex('clock_m', cimg, alpha=True, interp='Closest', emit=1.6, emit_img=img_from_pil('clock_glow', tex2.clock_glow()))
    ccx, ccz = -1.17, 2.30
    quad('clock', [(ccx - sz[0] / 2, yw, ccz - sz[1] / 2), (ccx + sz[0] / 2, yw, ccz - sz[1] / 2), (ccx + sz[0] / 2, yw, ccz + sz[1] / 2),
                   (ccx - sz[0] / 2, yw, ccz + sz[1] / 2)], cm)
    flat('poster_blueprint', tex2.poster_blueprint(), (-0.74, yw, 2.30))
    flat('poster_heart', tex2.poster_heart(), (0.03, yw, 2.44))
    flat('whiteboard', tex2.whiteboard(), (HALF_W - 0.012, 0.25, 1.55), normal='-X')
    flat('rug', tex2.rug(), (-0.12, 1.02, 0.004), normal='+Z')
    objs['garland'] = garland(-HALF_W + 0.1, HALF_W - 0.1, CEIL - 0.13, WALL_Y - 0.05, sag=0.07)
    bpy.context.view_layer.update()
    return dict(objs=objs, door_hinge=hinge, door_meshes=dm, doorway=(x0, x1), bench_top=BENCH['top'], marks=MARKS)
