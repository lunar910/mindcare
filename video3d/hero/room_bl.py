"""Moroccan living room at night (Cycles). Z-up, metres; camera side is -Y, back wall at +Y."""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

WALL_Y = 1.6      # back wall plane (the sofa stands against it)
SEAT_Z = 0.43     # top of the seat cushion


def lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)) + (1.0,)


def np_image(name, arr, closest=False):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True)
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1))], axis=2)
    img.pixels.foreach_set(np.flipud(arr).astype(np.float32).ravel())
    img.pack()
    img['closest'] = closest
    return img


def mat_basic(name, color, rough=0.5, metal=0.0, sheen=0.0, emission=None, estr=0.0, transmission=0.0, ior=1.45, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = lin(color) if len(color) == 3 else color
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Sheen Weight'].default_value = sheen
    b.inputs['Transmission Weight'].default_value = transmission
    b.inputs['IOR'].default_value = ior
    b.inputs['Alpha'].default_value = alpha
    if emission is not None:
        b.inputs['Emission Color'].default_value = lin(emission)
        b.inputs['Emission Strength'].default_value = estr
    return m


def mat_image(name, img, rough=0.6, sheen=0.0, sheen_tint=None, emission=0.0, bump=0.0, mapping_scale=None, box=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Closest' if img.get('closest') else 'Linear'
    if box:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (box, box, box)
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
        tex.projection = 'BOX'
        tex.projection_blend = 0.15
    elif mapping_scale:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = mapping_scale
        nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], tex.inputs['Vector'])
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Sheen Weight'].default_value = sheen
    if sheen_tint:
        b.inputs['Sheen Tint'].default_value = sheen_tint
    if emission:
        nt.links.new(tex.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = emission
    if bump:
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = 40
        bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump
        nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


def obj_from_bm(name, bm, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def cube(name, size, loc, mat, bevel=0.0, segs=3, rot=(0, 0, 0)):
    bm = bmesh.new()
    bm.loops.layers.uv.new('UVMap')
    bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = obj_from_bm(name, bm, mat)
    ob.location = loc
    ob.rotation_euler = rot
    if bevel:
        bv = ob.modifiers.new('bevel', 'BEVEL')
        bv.width = bevel
        bv.segments = segs
        bv.limit_method = 'NONE'
        ob.data.polygons.foreach_set('use_smooth', [True] * len(ob.data.polygons))
        try:
            ob.data.set_sharp_from_angle(angle=math.radians(40))
        except Exception:
            pass
    return ob


def cylinder(name, r1, r2, depth, loc, mat, segs=48, rot=(0, 0, 0), cap=True):
    bm = bmesh.new()
    bm.loops.layers.uv.new('UVMap')
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r1, radius2=r2, depth=depth, calc_uvs=True)
    ob = obj_from_bm(name, bm, mat, smooth=True)
    ob.location = loc
    ob.rotation_euler = rot
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(50))
    except Exception:
        pass
    return ob


def torus(name, R, r, loc, mat, rot=(0, 0, 0), arc=2 * math.pi, major=48, minor=12):
    verts, faces = [], []
    for i in range(major + 1):
        a = arc * i / major
        for j in range(minor):
            b = 2 * math.pi * j / minor
            verts.append(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
    for i in range(major):
        for j in range(minor):
            a0, a1 = i * minor + j, i * minor + (j + 1) % minor
            faces.append((a0, a1, a1 + minor, a0 + minor))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def lathe(name, profile, loc, mat, segs=40):
    verts, faces = [], []
    n = len(profile)
    for i in range(segs):
        a = 2 * math.pi * i / segs
        for r, z in profile:
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(segs):
        for j in range(n - 1):
            a0 = i * n + j
            b0 = ((i + 1) % segs) * n + j
            faces.append((a0, b0, b0 + 1, a0 + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(mat)
    ob.location = loc
    return ob


def plane(name, w, h, loc, rot, mat, sub=(1, 1)):
    bm = bmesh.new()
    bm.loops.layers.uv.new('UVMap')
    bmesh.ops.create_grid(bm, x_segments=sub[0], y_segments=sub[1], size=0.5, calc_uvs=True)
    bmesh.ops.scale(bm, vec=Vector((w, h, 1)), verts=bm.verts)
    ob = obj_from_bm(name, bm, mat)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


# ---------------------------------------------------------------- pixel art helpers
def diamond(a, cx, cy, r, col):
    for i in range(-r, r + 1):
        w = r - abs(i)
        y = cy + i
        if 0 <= y < a.shape[0]:
            a[y, max(0, cx - w):max(0, cx + w + 1)] = col


def star8(a, cx, cy, r, col):
    a[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1] = col
    diamond(a, cx, cy, int(round(r * 1.42)), col)


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=float) / 255.0


def make_textures():
    rng = np.random.default_rng(5)
    T = {}
    # velvet pattern
    a = np.tile(hexc('#0f5a45'), (64, 64, 1))
    a *= 1 + (rng.random((64, 64, 1)) - 0.5) * 0.12
    for i in range(64):
        a[i, i] = hexc('#0a4635')
        a[i, 63 - i] = hexc('#0a4635')
    for cx, cy in ((32, 32), (0, 0), (63, 0), (0, 63), (63, 63)):
        star8(a, cx, cy, 4, hexc('#c9a23a'))
        diamond(a, cx, cy, 2, hexc('#0f5a45'))
    for cx, cy in ((32, 0), (0, 32), (63, 32), (32, 63)):
        diamond(a, cx, cy, 2, hexc('#b8912c'))
    T['velvet'] = np_image('velvet', a, closest=True)
    # rug
    W, H = 160, 112
    a = np.tile(hexc('#7a1a1c'), (H, W, 1))
    a *= 1 + (rng.random((H, W, 1)) - 0.5) * 0.1
    cream, navy, orange = hexc('#e8d6b0'), hexc('#1f2a4a'), hexc('#c8642a')
    a[4:7, 4:W - 4] = cream; a[H - 7:H - 4, 4:W - 4] = cream; a[4:H - 4, 4:7] = cream; a[4:H - 4, W - 7:W - 4] = cream
    a[9:13, 9:W - 9] = navy; a[H - 13:H - 9, 9:W - 9] = navy; a[9:H - 9, 9:13] = navy; a[9:H - 9, W - 13:W - 9] = navy
    for cy in range(26, H - 18, 20):
        for cx in range(24, W - 18, 22):
            diamond(a, cx, cy, 8, cream); diamond(a, cx, cy, 5, orange); diamond(a, cx, cy, 1, navy)
    T['rug'] = np_image('rug', a, closest=True)
    # city at night
    W, H = 1024, 512
    a = np.zeros((H, W, 3))
    t = np.clip(np.arange(H) / 270.0, 0, 1)[:, None]
    sky = (1 - t) * hexc('#030616') + t * hexc('#1a2c55')
    a[:] = sky[:, None, :]
    for _ in range(110):
        x, y = rng.integers(0, W), rng.integers(0, 170)
        a[y, x] = 0.5 + rng.random() * 0.5
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.hypot(xx - 780, yy - 64)
    a += (np.clip(1 - d / 70, 0, 1) ** 2)[..., None] * np.array([0.25, 0.27, 0.35])
    a[d < 11] = [0.95, 0.95, 0.9]
    hill = (238 + 8 * np.sin(np.arange(W) * 0.01) + rng.random(W) * 4).astype(int)
    for x in range(W):
        a[hill[x]:, x] = hexc('#0b1328')

    def layer(base, minh, maxh, minw, maxw, color, litp, sc):
        x = -10
        while x < W:
            bw, bh = int(minw + rng.random() * (maxw - minw)), int(minh + rng.random() * (maxh - minh))
            x0, x1 = max(0, x), min(W, x + bw)
            a[max(0, base - bh):, x0:x1] = color
            cw, chh, gx, gy = int(3 * sc), int(4 * sc), int(6 * sc), int(8 * sc)
            for wy in range(base - bh + int(gy * 0.6), base - 4, gy):
                for wx in range(x + 3, x + bw - cw - 2, gx):
                    if rng.random() < litp and 0 <= wx < W - cw:
                        col = np.array([1.0, 0.75 + rng.random() * 0.15, 0.4 + rng.random() * 0.2]) if rng.random() < 0.82 else np.array([0.62, 0.72, 1.0])
                        a[wy:wy + chh, wx:wx + cw] = col * (1.6 + rng.random())
            x += bw + int(rng.random() * 6)
    layer(262, 20, 60, 30, 70, hexc('#101a33'), 0.18, 0.7)
    layer(280, 30, 120, 40, 90, hexc('#0c142a'), 0.22, 1.0)
    for _ in range(26):
        x, y = rng.integers(0, W), 284 + rng.integers(0, 8)
        dd = np.hypot(xx - x, yy - y)
        a += (np.clip(1 - dd / 10, 0, 1) ** 2)[..., None] * np.array([1.0, 0.7, 0.35]) * 0.9
    a[292:] = hexc('#070b17')
    img = bpy.data.images.new('city', W, H, alpha=True, float_buffer=True)
    img.pixels.foreach_set(np.flipud(np.concatenate([a, np.ones((H, W, 1))], 2)).astype(np.float32).ravel())
    img.pack()
    T['city'] = img
    # carved apron
    a = np.tile(hexc('#4a2a16'), (32, 32, 1))
    a[10:32, 4:28] = hexc('#7a4a26')
    yy, xx = np.mgrid[0:32, 0:32]
    a[(np.hypot(xx - 16, yy - 12) < 12) & (yy < 12)] = hexc('#7a4a26')
    a[13:32, 8:24] = hexc('#2e180b')
    a[(np.hypot(xx - 16, yy - 14) < 8) & (yy < 14)] = hexc('#2e180b')
    T['apron'] = np_image('apron', a, closest=True)
    # lantern holes
    a = np.zeros((48, 32, 3))
    for y in range(4, 46, 8):
        for x in range(3 + (y // 8) % 2 * 4, 30, 8):
            diamond(a, x, y, 2, np.array([1.0, 0.7, 0.28]))
    T['lantern'] = np_image('lantern', a, closest=True)
    # picture (sunset dunes)
    W, H = 96, 64
    a = np.zeros((H, W, 3))
    t = (np.arange(H) / H)[:, None, None]
    a[:] = (1 - t) * hexc('#f2a65a') + t * hexc('#a8452a')
    yy, xx = np.mgrid[0:H, 0:W]
    a[np.hypot(xx - 62, yy - 30) < 8] = hexc('#ffe3a3')
    a[yy > 46 - 10 * np.sin(xx / 30.0)] = hexc('#8a3a22')
    a[yy > 56 - 6 * np.sin(xx / 20.0 + 1)] = hexc('#6a2a18')
    T['picture'] = np_image('picture', a)
    # clock face
    a = np.ones((128, 128, 3)) * hexc('#f4f1e8')
    yy, xx = np.mgrid[0:128, 0:128]
    a[np.hypot(xx - 64, yy - 64) > 63] = 0.1
    for i in range(12):
        ang = i / 12 * 2 * math.pi
        cx, cy = 64 + math.sin(ang) * 52, 64 - math.cos(ang) * 52
        a[np.hypot(xx - cx, yy - cy) < 3] = 0.1

    def hand(ang, ln, wd):
        dx, dy = math.sin(ang), -math.cos(ang)
        tt = (xx - 64) * dx + (yy - 64) * dy
        dd = np.abs((xx - 64) * dy - (yy - 64) * dx)
        a[(tt > -6) & (tt < ln) & (dd < wd)] = 0.08
    hand((11 + 40 / 60) / 12 * 2 * math.pi, 32, 2.6)
    hand(40 / 60 * 2 * math.pi, 47, 1.6)
    T['clock'] = np_image('clock', a)
    return T


def build_room():
    T = make_textures()
    M = {}
    # ---------------- materials
    M['plaster'] = bpy.data.materials.new('plaster'); M['plaster'].use_nodes = True
    nt = M['plaster'].node_tree; b = nt.nodes['Principled BSDF']
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3; nz.inputs['Detail'].default_value = 8
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = lin([176, 132, 92]); ramp.color_ramp.elements[1].color = lin([214, 172, 126])
    nt.links.new(nz.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.85
    nz2 = nt.nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 60
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.15
    nt.links.new(nz2.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])

    M['tiles'] = bpy.data.materials.new('tiles'); M['tiles'].use_nodes = True
    nt = M['tiles'].node_tree; b = nt.nodes['Principled BSDF']
    br = nt.nodes.new('ShaderNodeTexBrick')
    br.inputs['Color1'].default_value = lin([214, 196, 168]); br.inputs['Color2'].default_value = lin([200, 182, 152])
    br.inputs['Mortar'].default_value = lin([110, 96, 82]); br.inputs['Scale'].default_value = 2.0
    br.inputs['Mortar Size'].default_value = 0.006; br.offset = 0.0; br.inputs['Brick Width'].default_value = 0.5; br.inputs['Row Height'].default_value = 0.5
    nt.links.new(br.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.28

    M['velvet'] = mat_image('velvet', T['velvet'], rough=0.8, sheen=1.0, sheen_tint=lin([110, 220, 180]), box=2.0)
    M['velvet_back'] = mat_image('velvet_b', T['velvet'], rough=0.8, sheen=1.0, sheen_tint=lin([110, 220, 180]), box=2.0)
    M['rug'] = mat_image('rug', T['rug'], rough=0.95, sheen=0.6)
    M['gold'] = mat_basic('gold', [212, 168, 74], rough=0.32, metal=1.0)
    M['brass'] = mat_basic('brass', [180, 140, 64], rough=0.38, metal=1.0)
    M['silver'] = mat_basic('silver', [210, 212, 216], rough=0.22, metal=1.0)
    M['frame'] = mat_basic('frame', [214, 210, 200], rough=0.45)
    M['sill'] = mat_basic('sill', [236, 232, 222], rough=0.2)
    M['curtain'] = mat_basic('curtain', [236, 222, 196], rough=0.9, sheen=0.6)
    M['glass'] = mat_basic('glass', [255, 255, 255], rough=0.02, transmission=1.0, ior=1.45)
    M['tea'] = mat_basic('tea', [170, 70, 14], rough=0.05, transmission=0.85, ior=1.33)
    M['cookie'] = mat_basic('cookie', [234, 210, 164], rough=0.8)
    M['plate'] = mat_basic('plate', [244, 241, 234], rough=0.25)
    M['carton'] = mat_basic('carton', [245, 245, 242], rough=0.55)
    M['blue'] = mat_basic('blue', [42, 111, 214], rough=0.5)
    M['dark'] = mat_basic('dark', [30, 30, 30], rough=0.4)
    M['shade'] = mat_basic('shade', [243, 226, 192], rough=0.9, emission=[255, 196, 130], estr=2.5)
    M['city'] = bpy.data.materials.new('city'); M['city'].use_nodes = True
    nt = M['city'].node_tree
    for n in list(nt.nodes):
        if n.type == 'BSDF_PRINCIPLED':
            nt.nodes.remove(n)
    tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = T['city']
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 0.45
    nt.links.new(tx.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    M['wood'] = bpy.data.materials.new('wood'); M['wood'].use_nodes = True
    nt = M['wood'].node_tree; b = nt.nodes['Principled BSDF']
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = 3; wv.inputs['Distortion'].default_value = 6; wv.inputs['Detail'].default_value = 3
    rp = nt.nodes.new('ShaderNodeValToRGB'); rp.color_ramp.elements[0].color = lin([70, 38, 20]); rp.color_ramp.elements[1].color = lin([118, 70, 38])
    nt.links.new(wv.outputs['Fac'], rp.inputs['Fac']); nt.links.new(rp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.35
    b.inputs['Coat Weight'].default_value = 0.3
    M['apron'] = mat_image('apron', T['apron'], rough=0.6, mapping_scale=(14, 1, 1))
    M['lantern'] = mat_image('lantern', T['lantern'], rough=0.4, emission=6.0)
    M['picture'] = mat_image('picture', T['picture'], rough=0.6)
    M['clock'] = mat_image('clock', T['clock'], rough=0.3)

    WY = WALL_Y
    # ---------------- floor, rug, walls, ceiling
    plane('floor', 10, 10, (0, 0, 0), (0, 0, 0), M['tiles'])
    plane('rug', 3.6, 2.4, (0, 0.2, 0.004), (0, 0, 0), M['rug'])
    X0, X1, Z0, Z1, D = -1.15, 1.15, 1.0, 2.35, 0.26

    def wall(x0, x1, z0, z1):
        plane('wall', x1 - x0, z1 - z0, ((x0 + x1) / 2, WY, (z0 + z1) / 2), (math.pi / 2, 0, 0), M['plaster'])
    wall(-4, X0, 0, 3.2); wall(X1, 4, 0, 3.2); wall(X0, X1, 0, Z0); wall(X0, X1, Z1, 3.2)
    for sx in (-1, 1):
        plane('side', 6, 3.2, (sx * 2.45, -1.4, 1.6), (math.pi / 2, 0, -sx * math.pi / 2), M['plaster'])
    plane('ceiling', 6, 7, (0, -1.4, 3.0), (math.pi, 0, 0), mat_basic('ceil', [216, 200, 176], rough=0.95))
    plane('rev_l', D, Z1 - Z0, (X0, WY + D / 2, (Z0 + Z1) / 2), (math.pi / 2, 0, math.pi / 2), M['plaster'])
    plane('rev_r', D, Z1 - Z0, (X1, WY + D / 2, (Z0 + Z1) / 2), (math.pi / 2, 0, -math.pi / 2), M['plaster'])
    plane('rev_t', X1 - X0, D, (0, WY + D / 2, Z1), (math.pi, 0, 0), M['plaster'])
    cube('sill', (X1 - X0 + 0.12, D + 0.1, 0.04), (0, WY + D / 2 - 0.05, Z0 - 0.02), M['sill'], bevel=0.01)
    fy = WY + D * 0.62
    for (sx, sz, x, z) in ((0.07, Z1 - Z0, X0 + 0.035, (Z0 + Z1) / 2), (0.07, Z1 - Z0, X1 - 0.035, (Z0 + Z1) / 2),
                           (X1 - X0, 0.07, 0, Z1 - 0.035), (X1 - X0, 0.07, 0, Z0 + 0.035), (0.06, Z1 - Z0, 0, (Z0 + Z1) / 2)):
        cube('frame', (sx, 0.07, sz), (x, fy, z), M['frame'], bevel=0.006)
    plane('city', 16, 8, (0, WY + 7.5, 1.0), (math.pi / 2, 0, 0), M['city'])
    # curtains with folds
    for sx in (-1, 1):
        ob = plane('curtain', 0.62, 1.75, (sx * 1.42, WY - 0.09, 0.9 + 0.875), (math.pi / 2, 0, 0), M['curtain'], sub=(60, 2))
        for v in ob.data.vertices:
            v.co.z += 0.035 * math.sin(v.co.x / 0.62 * math.pi * 10)
        ob.data.polygons.foreach_set('use_smooth', [True] * len(ob.data.polygons))
        sol = ob.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = 0.004
    cylinder('rod', 0.012, 0.012, 3.3, (0, WY - 0.1, 2.66), M['brass'], segs=16, rot=(0, math.pi / 2, 0))
    # ---------------- sedari
    SX, SD, SB, SC = 4.0, 0.78, 0.28, 0.15
    cube('sofa_base', (SX, SD, SB), (0, WY - SD / 2, SB / 2), M['velvet'], bevel=0.02)
    cube('sofa_seat', (SX, SD, SC), (0, WY - SD / 2, SB + SC / 2), M['velvet'], bevel=0.05, segs=5)
    for i in range(4):
        cube('cushion', (0.98, 0.18, 0.52), (-1.5 + i * 1.0, WY - 0.11, SB + SC + 0.25), M['velvet_back'], bevel=0.06, segs=5, rot=(-0.12, 0, 0))
    cylinder('cord1', 0.008, 0.008, SX, (0, WY - SD + 0.004, SB + SC - 0.006), M['gold'], segs=10, rot=(0, math.pi / 2, 0))
    cylinder('cord2', 0.008, 0.008, SX, (0, WY - SD - 0.002, SB + 0.006), M['gold'], segs=10, rot=(0, math.pi / 2, 0))
    # ---------------- table + tea set
    TX, TY, TZ = 0.0, -0.12, 0.43
    TOP = TZ + 0.0175
    cylinder('table_top', 0.5, 0.5, 0.035, (TX, TY, TZ), M['wood'], segs=64)
    torus('table_edge', 0.5, 0.017, (TX, TY, TZ), M['wood'])
    ap = cylinder('apron', 0.45, 0.45, 0.38, (TX, TY, 0.22), M['apron'], segs=48, cap=False)
    torus('table_foot', 0.45, 0.02, (TX, TY, 0.03), M['wood'])
    cylinder('tray', 0.27, 0.26, 0.012, (TX - 0.1, TY + 0.08, TOP + 0.006), M['silver'])
    torus('tray_rim', 0.27, 0.007, (TX - 0.1, TY + 0.08, TOP + 0.012), M['silver'])
    pot = [(0.0001, 0), (0.045, 0.0), (0.06, 0.012), (0.072, 0.04), (0.068, 0.07), (0.05, 0.095), (0.034, 0.11), (0.036, 0.125),
           (0.045, 0.135), (0.044, 0.14), (0.03, 0.142), (0.022, 0.155), (0.012, 0.17), (0.006, 0.185), (0.0001, 0.19)]
    px, py = TX - 0.16, TY + 0.12
    lathe('teapot', pot, (px, py, TOP + 0.012), M['silver'])
    sp = bpy.data.curves.new('spout', 'CURVE'); sp.dimensions = '3D'; sp.bevel_depth = 0.009; sp.bevel_resolution = 3
    spl = sp.splines.new('BEZIER'); spl.bezier_points.add(2)
    for i, (x, z) in enumerate(((0.055, 0.035), (0.1, 0.075), (0.135, 0.135))):
        bp_ = spl.bezier_points[i]; bp_.co = (x, 0, z); bp_.handle_left_type = bp_.handle_right_type = 'AUTO'
    so = bpy.data.objects.new('spout', sp); bpy.context.scene.collection.objects.link(so); sp.materials.append(M['silver'])
    so.location = (px, py, TOP + 0.012); so.rotation_euler = (0, 0, -0.7)
    torus('handle', 0.042, 0.007, (px + 0.045 * math.cos(-0.7 + math.pi), py + 0.045 * math.sin(-0.7 + math.pi), TOP + 0.09), M['silver'],
          rot=(math.pi / 2, 0, -0.7 + math.pi / 2), arc=math.pi * 1.1, major=24, minor=8)
    for gx, gy in ((0.02, 0.24), (0.08, 0.12), (-0.02, -0.02), (-0.2, -0.06)):
        cylinder('glass', 0.025, 0.02, 0.085, (TX + gx, TY + gy, TOP + 0.012 + 0.0425), M['glass'], segs=24, rot=(math.pi, 0, 0))
        cylinder('tea', 0.022, 0.018, 0.058, (TX + gx, TY + gy, TOP + 0.012 + 0.031), M['tea'], segs=24, rot=(math.pi, 0, 0))
        torus('band', 0.0245, 0.0022, (TX + gx, TY + gy, TOP + 0.082), M['gold'], major=24, minor=6)
    cylinder('plate', 0.1, 0.085, 0.012, (TX + 0.28, TY + 0.05, TOP + 0.006), M['plate'])
    for i in range(6):
        a = i * 1.05
        torus('cookie', 0.026, 0.009, (TX + 0.28 + math.cos(a) * 0.045, TY + 0.05 + math.sin(a) * 0.045, TOP + 0.02 + (i % 2) * 0.006),
              M['cookie'], rot=(0, 0, a), arc=math.pi * 0.95, major=12, minor=8)
    # the evidence: milk carton
    cx, cy = TX + 0.16, TY - 0.24
    cart = cube('carton', (0.07, 0.07, 0.17), (cx, cy, TOP + 0.085), M['carton'], bevel=0.002, rot=(0, 0, 0.35))
    band = cube('carton_band', (0.0705, 0.0705, 0.03), (cx, cy, TOP + 0.07), M['blue'], rot=(0, 0, 0.35))
    for s in (-1, 1):
        rf = cube('roof', (0.07, 0.0505, 0.003), (cx + s * 0.0175 * math.sin(0.35), cy - s * 0.0175 * math.cos(0.35), TOP + 0.17 + 0.0175), M['carton'], rot=(s * math.pi / 4, 0, 0.35))
    cube('fin', (0.07, 0.005, 0.02), (cx, cy, TOP + 0.17 + 0.045), M['carton'], rot=(0, 0, 0.35))
    txt = bpy.data.curves.new('lait', 'FONT'); txt.body = 'LAIT'; txt.size = 0.024; txt.align_x = 'CENTER'; txt.extrude = 0.0005
    to = bpy.data.objects.new('lait', txt); bpy.context.scene.collection.objects.link(to)
    txt.materials.append(mat_basic('white', [255, 255, 255], rough=0.5))
    n_ = Vector((-math.sin(0.35), -math.cos(0.35), 0))
    to.location = Vector((cx, cy, TOP + 0.062)) + n_ * 0.0365
    to.rotation_euler = (math.pi / 2, 0, 0.35)
    # ---------------- lamp, lantern, clock, picture
    LX, LY = -1.5, 0.86
    cylinder('lamp_base', 0.14, 0.16, 0.025, (LX, LY, 0.0125), M['brass'])
    cylinder('lamp_pole', 0.012, 0.012, 1.42, (LX, LY, 0.72), M['brass'], segs=12)
    cylinder('lamp_shade', 0.24, 0.16, 0.3, (LX, LY, 1.48), M['shade'], segs=40, cap=False)
    lx, ly = 1.8, 0.98
    cylinder('lantern', 0.1, 0.1, 0.3, (lx, ly, 0.2), M['lantern'], segs=6)
    cylinder('lantern_dome', 0.115, 0.0, 0.13, (lx, ly, 0.415), M['brass'], segs=6)
    cylinder('lantern_base', 0.11, 0.12, 0.05, (lx, ly, 0.025), M['brass'], segs=6)
    plane('clock', 0.28, 0.28, (1.85, WY - 0.034, 1.86), (math.pi / 2, 0, math.pi), M['clock'])
    torus('clock_rim', 0.145, 0.014, (1.85, WY - 0.03, 1.86), M['dark'], rot=(math.pi / 2, 0, 0))
    plane('picture', 0.42, 0.28, (-1.85, WY - 0.025, 1.95), (math.pi / 2, 0, math.pi), M['picture'])
    cube('pic_frame', (0.5, 0.03, 0.36), (-1.85, WY - 0.012, 1.95), M['gold'], bevel=0.008)
    # ---------------- lights
    L = {}

    def light(name, kind, loc, power, color, size=0.1, rot=(0, 0, 0), spot=None, shadow=0.05):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = power
        ld.color = color
        if kind == 'AREA':
            ld.size = size
        elif kind in ('POINT', 'SPOT'):
            ld.shadow_soft_size = shadow
        if spot:
            ld.spot_size, ld.spot_blend = spot
        ob = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = rot
        L[name] = ob
        return ob
    light('lamp', 'POINT', (LX, LY, 1.46), 90, (1.0, 0.66, 0.36), shadow=0.08)
    light('ceiling', 'AREA', (0.2, -0.6, 2.95), 55, (1.0, 0.8, 0.6), size=1.0)
    light('lantern', 'POINT', (lx, ly, 0.22), 14, (1.0, 0.55, 0.2), shadow=0.03)
    moon = light('moon', 'SPOT', (-0.7, WY + 3.2, 3.3), 900, (0.55, 0.66, 1.0), spot=(math.radians(32), 0.6), shadow=0.2)
    d = Vector((0, 1.15, 0.95)) - moon.location
    moon.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    tv = light('tv', 'AREA', (1.9, -1.4, 0.95), 22, (0.45, 0.58, 1.0), size=0.6)
    d = Vector((0.5, 1.1, 1.0)) - tv.location
    tv.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    w = bpy.data.worlds.new('night')
    bpy.context.scene.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.006, 0.008, 0.018, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    return dict(M=M, L=L)
