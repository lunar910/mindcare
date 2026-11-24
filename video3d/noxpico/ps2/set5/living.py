"""Version 5 set: the LIVED-IN props of Nox's loft (living zone, storage, kitchenette, Pico's traces, Bip, wall pieces).

Every builder returns a kit5.Prop built at the origin, standing on Z = 0, FRONT facing -Y (wall pieces: their back is
at +Y, ready to be hung on a wall), real dimensions in metres:

    build_sofa()             3-seat fabric sofa, 2.20 x 0.92 x 0.88, seat top 0.46 (throw blanket, 2 loose cushions)
    build_coffee_table()     1.10 x 0.60 x 0.42 walnut + black steel, magazines, closed laptop, controller, mug
    build_rug()              2.60 (x) x 1.80 (y), low pile, muted geometric pattern, fringes on the short ends
    build_floor_lamp()       tripod lamp 1.66 m, linen drum shade with a real warm POINT light inside (P.parts['bulb'])
    build_plant_big()        1.6 m monstera in a concrete pot (alpha-cut leaves on bent grids, stems, moss pole)
    build_plant_small()      pothos + two succulents in small pots (a ~0.45 m cluster)
    build_shelving()         2.0 x 1.2 x 0.45 black steel shelving, 5 shelves (P.shelf_z = shelf top heights)
    build_shelving_filled(seed)   the same full of labelled boxes, books, a 3D printer, robot parts, spools, ...
    build_pegboard()         1.1 x 0.8 board with tools; hung with its bottom edge at z0 (default 1.0)
    build_drawer_cabinet()   0.6 m steel drawer cabinet + parts organiser on top
    build_kitchenette()      1.8 m counter (0.9 high) + small fridge on its right + wall shelf with jars
    build_basketball(), build_skateboard(lean=True), build_gym_bag(), build_bip(), build_print(), build_radiator()

    living_zone(collection=None) -> Prop   sofa, table, rug, lamp, plant in WORLD coordinates of the loft (SPEC)

Practical lights: build_floor_lamp -> P.parts['bulb'] (POINT, warm), build_bip -> P.parts['eye_glow'] (tiny green),
build_kitchenette -> P.parts['machine_led'] (tiny orange).  Materials are cached per name ('lv_*').
Textures (rug, leaves, covers, labels, print, stickers) are generated with PIL into lab/set5/tex/ on first use.
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector
from mathutils import noise as mnoise

import kit5
import mat5

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEX = os.path.join(ROOT, 'lab', 'set5', 'tex')
FONTS = {
    'sans': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    'sansb': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    'serif': '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
    'serifb': '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
    'mono': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    'monob': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
    'inter': '/usr/share/fonts/opentype/inter/Inter-Bold.otf',
    'interb': '/usr/share/fonts/opentype/inter/Inter-Black.otf',
    'interl': '/usr/share/fonts/opentype/inter/Inter-Regular.otf',
    'cond': '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
}
TEXVER = 'v1'
D = math.degrees

_MATS = {}
_IMGS = {}


def _reset():
    """Forget cached materials/images (call after bpy.ops.wm.read_factory_settings)."""
    _MATS.clear()
    _IMGS.clear()


def _alive(x):
    try:
        x.name
        return True
    except ReferenceError:
        return False


def mat(key, fn):
    """A cached custom material: fn(name) -> bpy material, built once per scene."""
    m = _MATS.get(key)
    if m is None or not _alive(m) or m.name not in bpy.data.materials:
        m = fn('lv_' + key)
        _MATS[key] = m
    return m


def image(fname, gen):
    """Load lab/set5/tex/<fname>, generating it with gen(path) first if missing."""
    path = os.path.join(TEX, fname)
    if not os.path.exists(path):
        os.makedirs(TEX, exist_ok=True)
        gen(path)
    im = _IMGS.get(fname)
    if im is None or not _alive(im) or im.name not in bpy.data.images:
        im = bpy.data.images.load(path, check_existing=True)
        _IMGS[fname] = im
    return im


def font(key, size):
    from PIL import ImageFont
    return ImageFont.truetype(FONTS[key], size)


def lin(c):
    return mat5.lin(c)


# ------------------------------------------------------------------ material helpers
def img_mat(name, img, rough=0.5, coord='UV', alpha=False, coat=0.0, coat_rough=0.05, sheen=0.0, spec=0.4,
            edge_rgb=None, metal=0.0, bump=0.0, bump_scale=200.0, sss=0.0, translucent=0.0, closest=False):
    """Image-textured Principled.  coord='Generated' maps the bounding box (a box's top face) to the image.
    edge_rgb: colour for faces not pointing +Z (object space) - magazine edges, label sides."""
    T = mat5._NT(name)
    tc = T.node('ShaderNodeTexCoord')
    tx = T.node('ShaderNodeTexImage')
    tx.image = img
    tx.extension = 'EXTEND'
    if closest:
        tx.interpolation = 'Closest'
    T.link(tc.outputs[coord], tx.inputs['Vector'])
    col = tx.outputs['Color']
    if edge_rgb is not None:
        sep = T.node('ShaderNodeSeparateXYZ')
        T.link(tc.outputs['Normal'], sep.inputs['Vector'])
        col = T.mix(T.maprange(sep.outputs['Z'], 0.6, 0.7, 0.0, 1.0), edge_rgb, col)
    T.set(base=col, rough=rough, spec=spec)
    if metal:
        T.set(metal=metal)
    if alpha:
        T.link(tx.outputs['Alpha'], T.bsdf.inputs['Alpha'])
    if coat:
        T.set(coat=coat, coat_rough=coat_rough)
    if sheen:
        T.set(sheen=sheen)
    if sss:
        T.set(sss=sss)
    if bump:
        n = T.noise(T.coord(1.0), bump_scale, 3.0, 0.6)
        T.set(normal=T.bump(n.outputs['Fac'], bump, 0.0005))
    if translucent:
        tr = T.node('ShaderNodeBsdfTranslucent')
        T.link(col, tr.inputs['Color'])
        mx = T.node('ShaderNodeMixShader')
        mx.inputs['Fac'].default_value = translucent
        T.link(T.bsdf.outputs['BSDF'], mx.inputs[1])
        T.link(tr.outputs['BSDF'], mx.inputs[2])
        if alpha:   # keep the cut-out: mix the result with transparency
            tp = T.node('ShaderNodeBsdfTransparent')
            mx2 = T.node('ShaderNodeMixShader')
            T.link(tx.outputs['Alpha'], mx2.inputs['Fac'])
            T.link(tp.outputs['BSDF'], mx2.inputs[1])
            T.link(mx.outputs['Shader'], mx2.inputs[2])
            T.link(mx2.outputs['Shader'], T.out.inputs['Surface'])
        else:
            T.link(mx.outputs['Shader'], T.out.inputs['Surface'])
    return T.m


def attr_mat(name, attr='Col', rough=0.6, var=0.08, spec=0.4, sheen=0.0, coat=0.0, bump=0.02, scale=40.0):
    """Base colour from a per-face colour attribute (many parts with different colours in one mesh)."""
    T = mat5._NT(name)
    a = T.node('ShaderNodeAttribute')
    a.attribute_name = attr
    n = T.noise(T.coord(1.0), scale, 3.0, 0.6)
    shade = T.maprange(n.outputs['Fac'], 0.3, 0.7, 1.0 - var, 1.0 + var)
    mul = T.node('ShaderNodeMix')
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    T.link(a.outputs['Color'], mul.inputs[6])
    cm = T.node('ShaderNodeCombineColor')
    for s in ('Red', 'Green', 'Blue'):
        T.link(shade, cm.inputs[s])
    T.link(cm.outputs['Color'], mul.inputs[7])
    T.set(base=mul.outputs[2], rough=rough, spec=spec, normal=T.bump(n.outputs['Fac'], bump, 0.0005))
    if sheen:
        T.set(sheen=sheen)
    if coat:
        T.set(coat=coat, coat_rough=0.1)
    return T.m


def translucent_fabric(name, rgb, trans_rgb=None, fac=0.55, rough=0.9):
    """Lamp-shade linen: diffuse cloth mixed with diffuse transmission so a bulb inside makes it glow."""
    T = mat5._NT(name)
    v = T.coord(1.0)
    w = T.node('ShaderNodeTexWave')
    w.inputs['Scale'].default_value = 260.0
    w.inputs['Distortion'].default_value = 1.0
    T.link(v, w.inputs['Vector'])
    mott = T.noise(v, 18.0, 4.0, 0.6)
    col = T.ramp(mott.outputs['Fac'], [(0.3, tuple(x * 0.94 for x in rgb)), (0.7, rgb)])
    T.set(base=col, rough=rough, sheen=0.3, spec=0.25, normal=T.bump(w.outputs['Fac'], 0.06, 0.0005))
    tr = T.node('ShaderNodeBsdfTranslucent')
    tr.inputs['Color'].default_value = tuple(lin(trans_rgb or rgb)) + (1.0,)
    mx = T.node('ShaderNodeMixShader')
    mx.inputs['Fac'].default_value = fac
    T.link(T.bsdf.outputs['BSDF'], mx.inputs[1])
    T.link(tr.outputs['BSDF'], mx.inputs[2])
    T.link(mx.outputs['Shader'], T.out.inputs['Surface'])
    return T.m


def wood2(name, rgb=(98, 66, 44), rings=95.0, tilt=3.0, y0=0.06, z0=-0.22, contrast=0.55, rough=0.45, varnish=0.0,
          seed=0.0, axis='X'):
    """Flat-sawn board: growth rings of a log whose axis lies a little below the board and slightly tilted, so the
    face shows cathedral arches + straight grain, noise-distorted; fine pores streaked along the grain; tone drift."""
    T = mat5._NT(name)
    tc = T.node('ShaderNodeTexCoord')
    mp = T.node('ShaderNodeMapping')
    if axis == 'Y':
        mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(90))
    elif axis == 'Z':
        mp.inputs['Rotation'].default_value = (0.0, math.radians(-90), 0.0)
    T.link(tc.outputs['Object'], mp.inputs['Vector'])
    p = mp.outputs['Vector']
    sep = T.node('ShaderNodeSeparateXYZ')
    T.link(p, sep.inputs['Vector'])
    rnd = random.Random(int(seed * 1000) + 7)
    # distortion field stretched along the grain (x)
    dm = T.node('ShaderNodeMapping')
    dm.inputs['Scale'].default_value = (0.6, 9.0, 9.0)
    dm.inputs['Location'].default_value = (seed * 3.1, seed * 1.7, seed * 2.3)
    T.link(p, dm.inputs['Vector'])
    dn = T.noise(dm.outputs['Vector'], 1.0, 5.0, 0.6)

    def mth(op, a, b=None, v=None):
        n = T.node('ShaderNodeMath', operation=op)
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                T.link(x, n.inputs[i])
        return n.outputs['Value']
    yy = mth('ADD', sep.outputs['Y'], -(y0 + rnd.uniform(-0.05, 0.05)))
    zz = mth('ADD', sep.outputs['Z'], -(z0 + rnd.uniform(-0.05, 0.05)))
    zz = mth('ADD', zz, mth('MULTIPLY', sep.outputs['X'], math.tan(math.radians(tilt + rnd.uniform(-1, 1)))))
    r = mth('SQRT', mth('ADD', mth('MULTIPLY', yy, yy), mth('MULTIPLY', zz, zz)))
    r = mth('ADD', r, mth('MULTIPLY', mth('ADD', dn.outputs['Fac'], -0.5), 0.012))
    ring = mth('FRACT', mth('MULTIPLY', r, rings))
    late = mth('POWER', ring, 3.0)                        # the dark late-wood band at the end of each ring
    pm = T.node('ShaderNodeMapping')
    pm.inputs['Scale'].default_value = (4.0, 260.0, 260.0)
    T.link(p, pm.inputs['Vector'])
    pores = T.noise(pm.outputs['Vector'], 1.0, 3.0, 0.7)
    tone = T.noise(T.coord((0.8, 3.0, 3.0), seed=seed), 1.0, 3.0, 0.5)
    f = mth('ADD', mth('MULTIPLY', late, contrast), mth('MULTIPLY', pores.outputs['Fac'], 0.35))
    f = mth('ADD', f, mth('MULTIPLY', tone.outputs['Fac'], 0.3))
    darkc = tuple(x * 0.62 for x in rgb)
    lightc = tuple(min(255, x * 1.18) for x in rgb)
    col = T.ramp(f, [(0.15, lightc), (0.45, rgb), (0.85, darkc)])
    T.set(base=col, rough=T.maprange(f, 0.2, 0.8, rough - 0.06, rough + 0.08),
          normal=T.bump(mth('ADD', pores.outputs['Fac'], mth('MULTIPLY', late, 0.3)), 0.08, 0.0008), spec=0.5)
    if varnish:
        T.set(coat=varnish, coat_rough=0.18)
    return T.m


def boards(P, name, size, loc, m_fn, n, axis='X', bevel=0.0008, seed=0, rot=(0, 0, 0)):
    """A glued panel: n boards side by side (across the grain), each with its own figure."""
    w = size[1] if axis == 'X' else size[0]
    obs = []
    for k in range(n):
        c = -w / 2 + w * (k + 0.5) / n
        if axis == 'X':
            sz, off = (size[0], w / n, size[2]), (0, c, 0)
        else:
            sz, off = (w / n, size[1], size[2]), (c, 0, 0)
        o = Vector(off)
        o.rotate(Euler(tuple(math.radians(a) for a in rot)))
        obs.append(P.box(f'{name}', sz, tuple(Vector(loc) + o), m_fn(k), rot=rot, bevel=bevel))
    return obs


# ------------------------------------------------------------------ geometry helpers
def mk(P, name, verts, faces, loc=(0, 0, 0), rot=(0, 0, 0), m=None, bevel=0.0, smooth=True, subsurf=0, uvs=None,
       solidify=0.0, sharp=True, parent=None, cols=None):
    """Object from raw verts/faces (+ optional per-vertex UVs, per-face colours 'Col', solidify, subdivision)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    if uvs is not None:
        uvl = me.uv_layers.new(name='UVMap')
        for lp in me.loops:
            uvl.data[lp.index].uv = uvs[lp.vertex_index]
    if cols is not None:
        ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'CORNER')
        for p in me.polygons:
            c = cols[p.index]
            for li in p.loop_indices:
                ca.data[li].color = (c[0], c[1], c[2], 1.0)
    ob = P._add(name, me, loc, rot, m, bevel, smooth=smooth, parent=parent)
    if subsurf or not sharp:
        a = me.attributes.get('sharp_edge')
        if a is not None:
            me.attributes.remove(a)
    if solidify:
        s = ob.modifiers.new('solid', 'SOLIDIFY')
        s.thickness = solidify
        s.offset = 0.0
        s.use_even_offset = True
    if subsurf:
        s = ob.modifiers.new('sub', 'SUBSURF')
        s.levels = 1
        s.render_levels = subsurf
    return ob


def rot_to(d):
    """Euler (degrees) turning local +Z onto direction d."""
    q = Vector(d).normalized().to_track_quat('Z', 'Y')
    return tuple(D(a) for a in q.to_euler())


def rod(P, name, a, b, r, m, r2=None, verts=16, bevel=0.0, parent=None):
    """A cylinder from point a to point b (local prop coordinates)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    return P.cyl(name, r, d.length, tuple((a + b) / 2), m, rot=rot_to(d), verts=verts, bevel=bevel, r2=r2, parent=parent)


def spline(points, per=6, closed=False):
    """Catmull-Rom resampling of a polyline (2D or 3D tuples) -> list of Vectors."""
    pts = [Vector(p) for p in points]
    if closed:
        ext = [pts[-1]] + pts + [pts[0], pts[1]]
    else:
        ext = [pts[0] + (pts[0] - pts[1])] + pts + [pts[-1] + (pts[-1] - pts[-2])]
    out = []
    nseg = len(pts) if closed else len(pts) - 1
    for i in range(nseg):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(pts[-1].copy())
    return out


def lathe_geo(prof, segs=32, a0=0.0):
    """Revolve a profile [(r, z), ...] around Z.  r == 0 makes a pole.  Profile going UP on the outside gives
    outward normals; continue it over the rim and DOWN the inside for a hollow vessel."""
    verts, faces, rings = [], [], []
    for r, z in prof:
        if r < 1e-7:
            rings.append([len(verts)])
            verts.append((0.0, 0.0, z))
        else:
            ring = []
            for i in range(segs):
                a = a0 + 2 * math.pi * i / segs
                ring.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    for A, B in zip(rings, rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        for i in range(segs):
            j = (i + 1) % segs
            if len(A) == 1:
                faces.append((A[0], B[j], B[i]))
            elif len(B) == 1:
                faces.append((A[i], A[j], B[0]))
            else:
                faces.append((A[i], A[j], B[j], B[i]))
    return verts, faces


def lathe(P, name, prof, loc, m, segs=32, rot=(0, 0, 0), bevel=0.0, subsurf=0, parent=None):
    v, f = lathe_geo(prof, segs)
    return mk(P, name, v, f, loc, rot, m, bevel=bevel, subsurf=subsurf, parent=parent)


def _axis(half, r, n):
    """Normalised lattice coordinates along one axis: an extra loop r metres from each end (subsurf rounding)."""
    if r <= 0 or n < 2:
        return [-1 + 2 * i / max(1, n - 1) for i in range(max(2, n))]
    e = min(0.45, r / half)
    inner = [-1 + e + (2 - 2 * e) * i / (n - 1) for i in range(n)]
    return [-1.0] + inner + [1.0]


def _lattice(xs, ys, zs):
    """Closed quad surface of the box xs x ys x zs (normalised coordinates), outward normals."""
    I, J, K = len(xs) - 1, len(ys) - 1, len(zs) - 1
    idx, verts, faces = {}, [], []

    def v(i, j, k):
        key = (i, j, k)
        if key not in idx:
            idx[key] = len(verts)
            verts.append((xs[i], ys[j], zs[k]))
        return idx[key]
    for i in range(I):
        for j in range(J):
            faces.append((v(i, j, 0), v(i, j + 1, 0), v(i + 1, j + 1, 0), v(i + 1, j, 0)))
            faces.append((v(i, j, K), v(i + 1, j, K), v(i + 1, j + 1, K), v(i, j + 1, K)))
    for i in range(I):
        for k in range(K):
            faces.append((v(i, 0, k), v(i + 1, 0, k), v(i + 1, 0, k + 1), v(i, 0, k + 1)))
            faces.append((v(i, J, k), v(i, J, k + 1), v(i + 1, J, k + 1), v(i + 1, J, k)))
    for j in range(J):
        for k in range(K):
            faces.append((v(0, j, k), v(0, j, k + 1), v(0, j + 1, k + 1), v(0, j + 1, k)))
            faces.append((v(I, j, k), v(I, j + 1, k), v(I, j + 1, k + 1), v(I, j, k + 1)))
    return verts, faces


def soft_geo(size, r=0.03, n=(6, 6, 3), bulge=(0.0, 0.0, 0.0), bulge6=None, dent=None, wobble=0.0, wscale=4.0,
             seed=0, slump=0.0, sag=0.0, taper=0.0):
    """Upholstery / cushion / bag body: a lattice box, rounded by subsurf, puffed out (bulge, metres, per axis or per
    side bulge6=(x-, x+, y-, y+, z-, z+)), dented on top (dent=(x, y, depth m, radius) normalised), wobbled with noise,
    slump: the top edge falls forward (-Y, metres), sag: the middle of the top sinks (metres), taper: top narrower."""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    xs, ys, zs = _axis(hx, r, n[0]), _axis(hy, r, n[1]), _axis(hz, r, n[2])
    verts, faces = _lattice(xs, ys, zs)
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    b6 = bulge6 or (bulge[0], bulge[0], bulge[1], bulge[1], bulge[2], bulge[2])
    out = []
    for x, y, z in verts:
        cx, cy, cz = max(0.0, 1 - x * x), max(0.0, 1 - y * y), max(0.0, 1 - z * z)
        X = x * hx * (1 - taper * (z + 1) / 2)
        Y = y * hy * (1 - taper * (z + 1) / 2)
        Z = z * hz
        X += (b6[0] if x < 0 else b6[1]) * x * cy * cz
        Y += (b6[2] if y < 0 else b6[3]) * y * cx * cz
        Z += (b6[4] if z < 0 else b6[5]) * z * cx * cy
        if dent and z > 0:
            dx, dy, depth, rad = dent
            Z -= depth * z * math.exp(-((x - dx) ** 2 + (y - dy) ** 2) / (rad * rad))
        if sag and z > 0:
            Z -= sag * z * cx
        if slump:
            Y -= slump * max(0.0, z) ** 2 * (0.6 + 0.4 * cx)
        if wobble:
            dvec = Vector((x, y, z))
            if dvec.length > 1e-6:
                dvec.normalize()
            w = mnoise.noise(Vector((X * wscale, Y * wscale, Z * wscale)) + off)
            X, Y, Z = X + dvec.x * w * wobble, Y + dvec.y * w * wobble, Z + dvec.z * w * wobble
        out.append((X, Y, Z))
    soft_geo.norm = verts
    return out, faces


def _crease(me, norm, sides, value):
    """Crease the perimeter edges of the given lattice sides ('z+', 'y-', ...) -> tailored welted seams."""
    ax = {'x': 0, 'y': 1, 'z': 2}
    a = me.attributes.get('crease_edge') or me.attributes.new('crease_edge', 'FLOAT', 'EDGE')
    for e in me.edges:
        p, q = norm[e.vertices[0]], norm[e.vertices[1]]
        for sd in sides:
            k, sg = ax[sd[0]], (1.0 if sd[1] == '+' else -1.0)
            if p[k] != sg or q[k] != sg:
                continue
            for o in (0, 1, 2):
                if o != k and abs(p[o]) == 1.0 and p[o] == q[o]:
                    a.data[e.index].value = value
                    break


def soft_box(P, name, size, loc, m, rot=(0, 0, 0), level=2, parent=None, crease=None, crease_val=0.75, **kw):
    v, f = soft_geo(size, **kw)
    norm = soft_geo.norm
    ob = mk(P, name, v, f, loc, rot, m, subsurf=level, parent=parent)
    if crease:
        _crease(ob.data, norm, crease, crease_val)
    return ob


def pillow_geo(w, h, t, nx=10, ny=10, seed=0, wobble=0.004, waist=0.07, ear=0.55):
    """Throw pillow: two domed grids sewn along the edge; thick centre, thin seam, slightly pulled-in sides."""
    rnd = random.Random(seed)
    off = Vector((rnd.uniform(-50, 50), rnd.uniform(-50, 50), rnd.uniform(-50, 50)))
    verts, faces = [], []
    idx = {}

    def pos(i, j, side):
        x, y = -1 + 2 * i / nx, -1 + 2 * j / ny
        edge = i in (0, nx) or j in (0, ny)
        fx = max(0.0, 1 - abs(x) ** 2.4) ** ear
        fy = max(0.0, 1 - abs(y) ** 2.4) ** ear
        Z = 0.0 if edge else side * (t / 2) * fx * fy
        X = x * w / 2 * (1 - waist * (1 - y * y))
        Y = y * h / 2 * (1 - waist * (1 - x * x))
        p = Vector((X, Y, Z))
        p.z += mnoise.noise(p * 6 + off) * wobble * (0 if edge else 1)
        p.x += mnoise.noise(p * 5 + off + Vector((3, 0, 0))) * wobble * 0.6
        return tuple(p)

    def v(i, j, side):
        edge = i in (0, nx) or j in (0, ny)
        key = (i, j, 0 if edge else side)
        if key not in idx:
            idx[key] = len(verts)
            verts.append(pos(i, j, side))
        return idx[key]
    for i in range(nx):
        for j in range(ny):
            faces.append((v(i, j, 1), v(i + 1, j, 1), v(i + 1, j + 1, 1), v(i, j + 1, 1)))
            faces.append((v(i, j, -1), v(i, j + 1, -1), v(i + 1, j + 1, -1), v(i + 1, j, -1)))
    return verts, faces


class MB:
    """Merge builder: many primitives -> ONE mesh object (with an optional per-face colour 'Col')."""

    def __init__(self):
        self.bm = bmesh.new()
        self.cols = {}
        self.colour = None

    def _place(self, verts, loc, rot):
        m = Matrix.LocRotScale(Vector(loc), Euler(tuple(math.radians(a) for a in rot)), None)
        bmesh.ops.transform(self.bm, matrix=m, verts=verts)
        if self.colour is not None:
            for f in {f for v in verts for f in v.link_faces}:
                self.cols[f] = self.colour

    def box(self, size, loc, rot=(0, 0, 0), col=None):
        self.colour = col
        g = bmesh.ops.create_cube(self.bm, size=1.0)
        bmesh.ops.scale(self.bm, vec=Vector(size), verts=g['verts'])
        self._place(g['verts'], loc, rot)

    def cyl(self, r, h, loc, rot=(0, 0, 0), segs=16, r2=None, col=None, cap=True):
        self.colour = col
        g = bmesh.ops.create_cone(self.bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r,
                                  radius2=r if r2 is None else r2, depth=h)
        self._place(g['verts'], loc, rot)

    def rod(self, a, b, r, segs=8, col=None, r2=None):
        a, b = Vector(a), Vector(b)
        d = b - a
        self.cyl(r, d.length, tuple((a + b) / 2), rot_to(d), segs, r2=r2, col=col)

    def sphere(self, r, loc, scale=(1, 1, 1), rot=(0, 0, 0), segs=12, rings=8, col=None):
        self.colour = col
        g = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=r)
        bmesh.ops.scale(self.bm, vec=Vector(scale), verts=g['verts'])
        self._place(g['verts'], loc, rot)

    def geo(self, verts, faces, loc=(0, 0, 0), rot=(0, 0, 0), col=None):
        self.colour = col
        vs = [self.bm.verts.new(v) for v in verts]
        for f in faces:
            try:
                self.bm.faces.new([vs[i] for i in f])
            except ValueError:
                pass
        self._place(vs, loc, rot)

    def finish(self, P, name, m, bevel=0.0, smooth=True, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, sharp=True):
        me = bpy.data.meshes.new(name)
        if self.cols:
            lay = self.bm.loops.layers.float_color.new('Col')
            for f, c in self.cols.items():
                if f.is_valid and c is not None:
                    for lp in f.loops:
                        lp[lay] = (c[0], c[1], c[2], 1.0)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        ob = P._add(name, me, loc, rot, m, bevel, smooth=smooth, parent=parent)
        if not sharp:
            a = me.attributes.get('sharp_edge')
            if a is not None:
                me.attributes.remove(a)
        return ob


def srgb(c):
    """sRGB 0-255 -> linear tuple (for colour attributes)."""
    return lin(c)


class Batch:
    """Leaf cards and other UV-mapped bits merged into one mesh."""

    def __init__(self):
        self.v, self.f, self.uv = [], [], []

    def grid(self, fn, nu, nv, uvfn):
        base = len(self.v)
        for i in range(nu + 1):
            for j in range(nv + 1):
                u, w = i / nu, j / nv
                self.v.append(tuple(fn(u, w)))
                self.uv.append(uvfn(u, w))
        for i in range(nu):
            for j in range(nv):
                a = base + i * (nv + 1) + j
                self.f.append((a, a + nv + 1, a + nv + 2, a + 1))

    def finish(self, P, name, m, subsurf=0, solidify=0.0):
        return mk(P, name, self.v, self.f, m=m, uvs=self.uv, subsurf=subsurf, solidify=solidify, sharp=False)


# ------------------------------------------------------------------ PIL helpers
def _np_noise(w, h, cell, seed, octaves=3):
    """Smooth value noise 0..1 (numpy, PIL bicubic upscale), size h x w."""
    import numpy as np
    from PIL import Image
    rs = np.random.RandomState(seed)
    acc = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = max(2, int(cell / (2 ** o)))
        sw, sh = max(2, w // c + 2), max(2, h // c + 2)
        small = (rs.rand(sh, sw) * 255).astype(np.uint8)
        big = Image.fromarray(small, 'L').resize((sw * c, sh * c), Image.BICUBIC)
        acc += amp * (np.asarray(big, np.float32)[:h, :w] / 255.0)
        tot += amp
        amp *= 0.5
    return acc / tot


# ================================================================== SOFA
def _sofa_fabric(n):
    return mat5.fabric(n, (50, 58, 70), rough=0.95, weave=380.0, sheen=0.22, seed=1.0)


def build_sofa(collection=None, seed=3):
    """3-seat sofa, dark grey-blue woven fabric: base, track arms, back, 3 seat + 3 back cushions (each sat in a bit
    differently), walnut legs, a wool throw over the left arm, two loose cushions."""
    P = kit5.Prop('sofa', collection)
    rnd = kit5.rng(seed)
    fab = mat('sofa_fabric', _sofa_fabric)
    # legs (tapered walnut, black glides)
    for x in (-1.0, 1.0, 0.0):
        for y in (-0.37, 0.37):
            if x == 0.0 and y < 0:
                continue
            P.cyl('leg', 0.015, 0.095, (x, y, 0.0525), 'wood_walnut', r2=0.022, verts=24, bevel=0.002)
            P.cyl('glide', 0.014, 0.006, (x, y, 0.003), 'plastic_black', verts=16, bevel=0.001)
    # upholstered frame
    soft_box(P, 'base', (1.86, 0.86, 0.21), (0, 0.02, 0.205), fab, r=0.025, n=(8, 4, 3), bulge=(0.0, 0.006, 0.0),
             wobble=0.002, seed=1)
    for sx in (-1, 1):
        soft_box(P, 'arm', (0.18, 0.92, 0.53), (sx * 1.01, 0.0, 0.10 + 0.265), fab, r=0.045, n=(3, 7, 5),
                 bulge6=(0.012, 0.012, 0.014, 0.01, 0.0, 0.016), wobble=0.003, seed=2 + sx,
                 crease=('y-',), crease_val=0.6)
    soft_box(P, 'back', (2.20, 0.20, 0.58), (0, 0.36, 0.39), fab, r=0.045, n=(12, 3, 4),
             bulge=(0.0, 0.012, 0.012), wobble=0.003, seed=5)
    # seat cushions: same size, each used differently
    dents = [(-0.15, -0.25, 0.030, 0.62), (0.05, -0.1, 0.018, 0.7), (0.25, -0.3, 0.036, 0.55)]
    for k, x in enumerate((-0.613, 0.0, 0.613)):
        soft_box(P, 'seat', (0.605, 0.66, 0.15), (x + rnd.uniform(-0.006, 0.006), -0.115 + rnd.uniform(-0.012, 0.004), 0.378),
                 fab, rot=(rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8), rnd.uniform(-1.4, 1.4)), r=0.05, n=(6, 6, 3),
                 bulge6=(0.008, 0.008, 0.014, 0.006, 0.0, 0.03), dent=dents[k], wobble=0.005, seed=10 + k,
                 crease=('z+', 'z-'), crease_val=0.8)
    # back cushions leaning on the back, a little slumped, not quite aligned
    for k, x in enumerate((-0.61, 0.0, 0.61)):
        soft_box(P, 'back_cushion', (0.60, 0.21, 0.45), (x + rnd.uniform(-0.01, 0.01), 0.235 + rnd.uniform(-0.01, 0.015), 0.672),
                 fab, rot=(-12 + rnd.uniform(-3, 2.5), rnd.uniform(-1.5, 1.5), rnd.uniform(-2, 2)), r=0.07, n=(6, 3, 6),
                 bulge6=(0.01, 0.01, 0.035, 0.012, 0.005, 0.02), wobble=0.007, slump=rnd.uniform(0.01, 0.03),
                 seed=20 + k, crease=('y-', 'y+'), crease_val=0.7)
    # loose cushions
    vel = mat('cushion_velvet', lambda n: mat5.fabric(n, (118, 54, 36), rough=0.72, weave=900.0, sheen=0.35, seed=2.0))
    lin_ = mat('cushion_linen', lambda n: mat5.fabric(n, (106, 114, 94), rough=0.95, weave=300.0, sheen=0.15, seed=3.0))
    v, f = pillow_geo(0.46, 0.46, 0.16, seed=31)
    mk(P, 'cushion_a', v, f, (0.80, 0.08, 0.66), (70, 8, -14), vel, subsurf=2)
    v, f = pillow_geo(0.44, 0.44, 0.15, seed=32, waist=0.09)
    mk(P, 'cushion_b', v, f, (-0.70, 0.0, 0.62), (62, -18, 24), lin_, subsurf=2)
    _throw_blanket(P, rnd)
    return P


def _throw_blanket(P, rnd):
    """Wool throw folded over the left arm: a cross-section path (x, z) swept along y with folds, solidified."""
    path2d = [(-0.50, 0.492), (-0.66, 0.490), (-0.80, 0.486), (-0.885, 0.49), (-0.912, 0.53), (-0.913, 0.59),
              (-0.925, 0.640), (-0.958, 0.664), (-1.01, 0.671), (-1.065, 0.664), (-1.106, 0.638), (-1.125, 0.585),
              (-1.130, 0.48), (-1.128, 0.38), (-1.124, 0.29)]
    pts = spline([(x, 0.0, z) for x, z in path2d], per=4)
    L = [0.0]
    for a, b in zip(pts, pts[1:]):
        L.append(L[-1] + (b - a).length)
    total = L[-1]
    ny = 26
    y0, y1 = -0.43, 0.07
    verts, faces, uvs = [], [], []
    ph = [rnd.uniform(0, 6.28) for _ in range(4)]
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        t = (b - a).normalized()
        nrm = Vector((t.z, 0.0, -t.x))
        if nrm.z < -0.2 or (abs(nrm.z) <= 0.2 and nrm.x > 0 and p.x < -1.0):
            nrm = -nrm
        u = L[i] / total
        hang = max(0.0, (u - 0.78) / 0.22)          # the free end hanging down the outer side
        seatfree = max(0.0, (0.12 - u) / 0.12)       # the free end lying on the seat
        amp = 0.003 + 0.018 * hang + 0.012 * seatfree
        for j in range(ny + 1):
            w = j / ny
            y = y0 + (y1 - y0) * w
            fold = amp * (math.sin(y * 34 + ph[0] + u * 2.0) * 0.7 + math.sin(y * 71 + ph[1]) * 0.3)
            # corners of the hanging end drop lower and flare; the seat end curls a little
            drop = hang * 0.035 * (abs(w - 0.5) * 2) ** 2
            q = p + nrm * fold + Vector((0.0, y, 0.0)) - Vector((0, 0, drop))
            if hang:
                q.x -= hang * 0.012 * (abs(w - 0.5) * 2)
            verts.append(tuple(q))
            uvs.append((L[i], y - y0))
    for i in range(len(pts) - 1):
        for j in range(ny):
            a = i * (ny + 1) + j
            faces.append((a, a + 1, a + ny + 2, a + ny + 1))

    def bl(n):
        T = mat5._NT(n)
        tc = T.node('ShaderNodeTexCoord')
        sep = T.node('ShaderNodeSeparateXYZ')
        T.link(tc.outputs['UV'], sep.inputs['Vector'])
        base, stripe = (160, 118, 52), (206, 192, 164)
        r = T.ramp(sep.outputs['X'], [(0.0, base), (0.05, stripe), (0.075, base), (0.095, stripe), (0.105, base),
                                      (total - 0.11, stripe), (total - 0.10, base), (total - 0.08, stripe), (total - 0.055, base)])
        r.node.color_ramp.interpolation = 'CONSTANT'
        rib = T.node('ShaderNodeTexWave')
        rib.inputs['Scale'].default_value = 9.0
        rib.inputs['Distortion'].default_value = 0.6
        rib.inputs['Detail'].default_value = 1.0
        cmb = T.node('ShaderNodeCombineXYZ')
        T.link(sep.outputs['Y'], cmb.inputs['X'])
        T.link(sep.outputs['X'], cmb.inputs['Y'])
        T.link(cmb.outputs['Vector'], rib.inputs['Vector'])
        mott = T.noise(T.coord(1.0), 9.0, 4.0, 0.6)
        col = T.mix(T.maprange(mott.outputs['Fac'], 0.3, 0.7, 0.0, 0.15), r, (110, 80, 40))
        return T.set(base=col, rough=0.95, sheen=0.3, spec=0.25, normal=T.bump(rib.outputs['Fac'], 0.35, 0.002))
    mk(P, 'throw', verts, faces, m=mat('throw_wool', bl), uvs=uvs, solidify=0.009, subsurf=1, sharp=False)


# ================================================================== COFFEE TABLE (+ small objects)
def _mag_cover(path, title, kind, seed):
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np
    W, H = 420, 560
    rnd = random.Random(seed)
    if kind == 'tech':
        bg = (18, 34, 40)
    elif kind == 'sport':
        bg = (214, 206, 190)
    else:
        bg = (30, 30, 36)
    im = Image.new('RGB', (W, H), bg)
    d = ImageDraw.Draw(im)
    if kind == 'tech':      # a circuit board photo-ish: traces, pads, a chip
        for _ in range(60):
            x, y = rnd.randint(0, W), rnd.randint(150, H)
            l = rnd.randint(20, 140)
            if rnd.random() < 0.5:
                d.line([(x, y), (x + l, y), (x + l + 20, y + 20)], fill=(70, 160, 120), width=3)
            else:
                d.line([(x, y), (x, y + l)], fill=(60, 140, 110), width=3)
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(200, 170, 90))
        d.rectangle([140, 300, 290, 430], fill=(16, 16, 18), outline=(120, 120, 120), width=2)
        for k in range(10):
            d.rectangle([150 + k * 14, 290, 156 + k * 14, 300], fill=(190, 190, 190))
            d.rectangle([150 + k * 14, 430, 156 + k * 14, 440], fill=(190, 190, 190))
        d.text((24, 22), title, font=font('interb', 64), fill=(120, 230, 160))
        d.text((26, 98), 'Capteurs, moteurs & micro-contrôleurs', font=font('interl', 17), fill=(220, 230, 225))
        d.rectangle([24, 480, 250, 530], fill=(230, 90, 50))
        d.text((34, 488), 'SPÉCIAL ROBOTS', font=font('inter', 26), fill=(255, 245, 235))
        d.text((360, 26), 'N°42', font=font('inter', 20), fill=(200, 220, 210))
    elif kind == 'sport':   # a basketball player silhouette on a warm court
        d.rectangle([0, 360, W, H], fill=(176, 124, 80))
        for k in range(6):
            d.line([(0, 380 + k * 34), (W, 372 + k * 34)], fill=(160, 110, 70), width=2)
        d.ellipse([230, 140, 330, 240], fill=(206, 104, 44))
        d.arc([230, 140, 330, 240], 0, 360, fill=(40, 30, 26), width=3)
        d.line([(280, 140), (280, 240)], fill=(40, 30, 26), width=3)
        d.polygon([(120, 520), (150, 330), (190, 260), (240, 240), (230, 300), (200, 360), (190, 520)], fill=(36, 40, 60))
        d.ellipse([170, 200, 214, 248], fill=(70, 50, 40))
        d.text((22, 18), title, font=font('interb', 86), fill=(200, 60, 40))
        d.text((24, 118), 'Les meneuses de la saison', font=font('inter', 20), fill=(40, 40, 46))
        d.text((24, 500), '+ 30 exercices de tir', font=font('inter', 24), fill=(255, 250, 240))
    else:                   # space/science
        a = (np.asarray(im).astype(np.float32))
        for _ in range(250):
            x, y = rnd.randint(0, W - 1), rnd.randint(0, H - 1)
            d.point((x, y), fill=(230, 230, 240))
        d.ellipse([90, 210, 330, 450], fill=(170, 120, 80))
        d.ellipse([60, 300, 360, 360], outline=(220, 200, 160), width=4)
        d.text((22, 20), title, font=font('interb', 70), fill=(240, 236, 226))
        d.text((24, 108), 'Comment marche un drone ?', font=font('interl', 22), fill=(200, 200, 210))
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    im.save(path)


def build_magazine(P, name, size, loc, rot, title, kind, seed):
    img = image(f'lv_mag_{kind}_{TEXVER}.png', lambda p: _mag_cover(p, title, kind, seed))
    m = mat(f'mag_{kind}', lambda n: img_mat(n, img, rough=0.35, coord='Generated', edge_rgb=(226, 222, 212),
                                             coat=0.3, coat_rough=0.2))
    return P.box(name, size, loc, m, rot=rot, bevel=0.0006)


def _sticker_sheet(path):
    from PIL import Image, ImageDraw
    S = 512
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # 0: green robot face (top-left quadrant)
    d.ellipse([16, 16, 240, 240], fill=(40, 44, 48, 255), outline=(255, 255, 255, 255), width=10)
    d.rounded_rectangle([60, 80, 196, 180], 18, fill=(120, 230, 150, 255))
    d.ellipse([84, 104, 116, 136], fill=(30, 30, 34, 255))
    d.ellipse([140, 104, 172, 136], fill=(30, 30, 34, 255))
    d.line([(128, 80), (128, 50)], fill=(120, 230, 150, 255), width=8)
    d.ellipse([118, 36, 138, 56], fill=(230, 90, 50, 255))
    # 1: orange bolt (top-right)
    d.regular_polygon((384, 128, 112), 6, fill=(232, 120, 40, 255), outline=(255, 255, 255, 255), width=8)
    d.polygon([(394, 50), (340, 140), (380, 140), (368, 210), (428, 112), (388, 112)], fill=(30, 30, 30, 255))
    # 2: white label "HELLO WORLD" (bottom)
    d.rounded_rectangle([20, 300, 492, 420], 20, fill=(240, 240, 236, 255), outline=(30, 30, 30, 255), width=6)
    d.text((48, 330), 'HELLO, WORLD', font=font('monob', 52), fill=(30, 30, 34, 255))
    im.save(path)


def build_laptop(P, loc, heading):
    """Closed 14-inch laptop, aluminium, with three stickers on the lid (nested prop)."""
    L = kit5.Prop('laptop', P.col)
    alu = mat('laptop_alu', lambda n: mat5.metal(n, (118, 120, 126), 0.34, brushed=False, seed=4.0))
    L.box('base', (0.312, 0.218, 0.009), (0, 0, 0.0055), alu, bevel=0.003)
    L.box('lid', (0.312, 0.218, 0.0065), (0, 0.0, 0.0143), alu, bevel=0.0028)
    L.box('seam', (0.304, 0.21, 0.0012), (0, 0.0, 0.0105), 'plastic_black', bevel=0.0)
    L.box('hinge', (0.24, 0.012, 0.012), (0, 0.105, 0.010), 'plastic_black', bevel=0.004)
    for x in (-0.13, 0.13):
        for y in (-0.085, 0.085):
            L.cyl('foot', 0.007, 0.0016, (x, y, 0.0008), 'rubber_black', verts=12, bevel=0)
    img = image(f'lv_stickers_{TEXVER}.png', _sticker_sheet)
    sm = mat('stickers', lambda n: img_mat(n, img, rough=0.45, alpha=True, coat=0.4))
    # three stickers: uv windows into the sheet
    for name, (u0, v0, u1, v1), size, pos, rz in (
            ('st_robot', (0.0, 0.5, 0.5, 1.0), (0.055, 0.055), (-0.08, 0.04), 8),
            ('st_bolt', (0.5, 0.5, 1.0, 1.0), (0.05, 0.05), (0.07, -0.05), -14),
            ('st_hello', (0.0, 0.15, 1.0, 0.45), (0.10, 0.03), (0.06, 0.06), 4)):
        ob = L.plane(name, size, (pos[0], pos[1], 0.0179), sm, rot=(0, 0, rz))
        uv = ob.data.uv_layers[0]
        for i, c in enumerate(((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
            uv.data[i].uv = c
    P.add(L, loc, heading)
    return L


def _controller_outline():
    def inside(x, y):
        if abs(x) <= 0.050 and -0.018 <= y <= 0.040:
            cx, cy = max(0, abs(x) - 0.038), max(0, y - 0.028)
            return cx * cx + cy * cy <= 0.012 ** 2 or abs(x) <= 0.038 or y <= 0.028
        for sx in (-1, 1):
            a = math.radians(-22 * sx)
            dx, dy = x - sx * 0.050, y + 0.022
            rx = dx * math.cos(a) + dy * math.sin(a)
            ry = -dx * math.sin(a) + dy * math.cos(a)
            if (rx / 0.026) ** 2 + (ry / 0.046) ** 2 <= 1:
                return True
        return False
    pts = []
    c = Vector((0, 0.008))
    for k in range(120):
        a = 2 * math.pi * k / 120
        d = Vector((math.cos(a), math.sin(a)))
        r = 0.12
        while r > 0 and not inside(c.x + d.x * r, c.y + d.y * r):
            r -= 0.0004
        pts.append(c + d * r)
    sm = []
    for i in range(len(pts)):
        sm.append((pts[i - 1] + pts[i] * 2 + pts[(i + 1) % len(pts)]) / 4)
    return sm


def build_controller(P, loc, heading):
    """Generic wireless game controller (no brand), matte dark grey, lying on its back."""
    C = kit5.Prop('controller', P.col)
    body = mat('ctrl_body', lambda n: mat5.plastic(n, (34, 35, 38), 0.55, seed=5.0))
    outline = _controller_outline()
    n = len(outline)
    bm = bmesh.new()
    lo = [bm.verts.new((p.x, p.y, 0.004)) for p in outline]
    face = bm.faces.new(lo)
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, 0.026), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('ctrl')
    bm.to_mesh(me)
    bm.free()
    ob = C._add('body', me, (0, 0, 0), (0, 0, 0), body, 0.0085, segments=3)
    # parts on top (z top = 0.030)
    for sx in (-1, 1):
        C.cyl('stick_base', 0.0125, 0.004, (sx * 0.021, -0.010, 0.032), 'plastic_black', verts=24, bevel=0.001)
        C.cyl('stick', 0.004, 0.010, (sx * 0.021, -0.010, 0.037), 'plastic_black', verts=12, bevel=0)
        C.cyl('stick_cap', 0.0105, 0.004, (sx * 0.021, -0.010, 0.043), 'rubber_black', verts=24, bevel=0.0012)
        C.box('bumper', (0.034, 0.010, 0.012), (sx * 0.044, 0.041, 0.022), body, rot=(0, 0, -sx * 8), bevel=0.003)
    C.box('dpad1', (0.022, 0.0075, 0.004), (-0.046, 0.014, 0.031), 'plastic_black', bevel=0.0012)
    C.box('dpad2', (0.0075, 0.022, 0.004), (-0.046, 0.014, 0.031), 'plastic_black', bevel=0.0012)
    for dx, dy, c in ((0.0, 0.010, (120, 160, 120)), (0.0, -0.010, (150, 150, 150)), (-0.010, 0, (140, 140, 150)), (0.010, 0, (160, 120, 110))):
        mm = mat(f'ctrl_btn_{c[0]}', lambda nm, c=c: mat5.plastic(nm, tuple(x * 0.5 for x in c), 0.3))
        C.cyl('btn', 0.0042, 0.004, (0.046 + dx, 0.014 + dy, 0.031), mm, verts=16, bevel=0.001)
    C.cyl('home', 0.0045, 0.002, (0.0, 0.016, 0.030), 'plastic_grey', verts=16, bevel=0.0006)
    C.box('touch', (0.030, 0.016, 0.002), (0.0, 0.030, 0.030), 'plastic_black', bevel=0.0008)
    P.add(C, loc, heading)
    return C


def build_mug(P, name, loc, heading=0.0, glaze=(36, 52, 64), coffee=True, r=0.041, h=0.095, parent_prop=None):
    """Ceramic mug (lathe) with a handle and black coffee."""
    G = kit5.Prop(name, P.col)
    gm = mat(f'mug_{glaze}', lambda n: mat5.ceramic(n, glaze, 0.2))
    prof = [(0.0, 0.0), (r - 0.006, 0.0), (r - 0.002, 0.002), (r - 0.001, 0.008), (r, h - 0.004), (r - 0.001, h),
            (r - 0.004, h), (r - 0.005, h - 0.006), (r - 0.0055, 0.012), (r - 0.012, 0.008), (0.0, 0.008)]
    lathe(G, 'body', prof, (0, 0, 0), gm, segs=32)
    G.tube('handle', [(r - 0.002, 0, h * 0.78), (r + 0.016, 0, h * 0.76), (r + 0.022, 0, h * 0.5),
                      (r + 0.015, 0, h * 0.26), (r - 0.002, 0, h * 0.24)], 0.0055, gm, resolution=8)
    G.parts['handle'].data.bevel_resolution = 4
    if coffee:
        cm = mat('coffee', lambda n: mat5.ceramic(n, (22, 12, 6), 0.05))
        G.cyl('coffee', r - 0.0056, 0.002, (0, 0, h * 0.72), cm, verts=32, bevel=0)
    P.add(G, loc, heading)
    return G


def build_coffee_table(collection=None, seed=5):
    """Walnut slab top on a black steel tube frame with a lower wooden shelf; magazines, closed laptop, controller,
    a mug of black coffee on a cork coaster, books on the shelf."""
    P = kit5.Prop('coffee_table', collection)
    rnd = kit5.rng(seed)
    walnut = lambda k: mat(f'walnut_{k}', lambda n: wood2(n, (84, 56, 38), rings=70.0, rough=0.4, varnish=0.3, seed=k + 1.0))
    oak = lambda k: mat(f'oak_{k}', lambda n: wood2(n, (150, 112, 76), rings=55.0, rough=0.55, seed=k + 11.0))
    boards(P, 'top', (1.10, 0.60, 0.032), (0, 0, 0.404), walnut, 4, bevel=0.0012)
    s = 0.025
    xs, ys = 0.50, 0.255
    for x in (-xs, xs):
        for y in (-ys, ys):
            P.box('leg', (s, s, 0.385), (x, y, 0.1975), 'steel_black', bevel=0.002)
            P.cyl('glide', 0.010, 0.006, (x, y, 0.003), 'plastic_black', verts=12, bevel=0.001)
    for z in (0.374, 0.105):
        for y in (-ys, ys):
            P.box('rail_x', (2 * xs - s, s * 0.8, s), (0, y, z), 'steel_black', bevel=0.002)
        for x in (-xs, xs):
            P.box('rail_y', (s * 0.8, 2 * ys - s, s), (x, 0, z), 'steel_black', bevel=0.002)
    boards(P, 'shelf', (0.99, 0.50, 0.018), (0, 0, 0.1265), oak, 3, bevel=0.0015)
    # objects on top (top surface z = 0.420)
    zt = 0.420
    build_magazine(P, 'mag1', (0.21, 0.28, 0.004), (-0.33, -0.04, zt + 0.002), (0, 0, 7), 'CIRCUITS', 'tech', 1)
    build_magazine(P, 'mag2', (0.21, 0.28, 0.0035), (-0.30, -0.06, zt + 0.0058), (0, 0, -6), 'DRIBBLE', 'sport', 2)
    build_magazine(P, 'mag3', (0.20, 0.27, 0.003), (-0.17, 0.12, zt + 0.0015), (0, 0, 31), 'ORBITE', 'space', 3)
    build_laptop(P, (0.13, 0.06, zt), 9)
    build_controller(P, (0.38, -0.17, zt), -28)
    P.cyl('coaster', 0.048, 0.004, (0.41, 0.15, zt + 0.002), mat('cork', lambda n: mat5.matte(n, (150, 112, 72), 0.9, 0.15, 0.25, 60.0)), verts=32, bevel=0.001)
    build_mug(P, 'mug', (0.41, 0.15, zt + 0.004), 130, glaze=(34, 50, 62))
    # a phone face down, a pen
    P.box('phone', (0.072, 0.150, 0.008), (0.02, -0.19, zt + 0.004), 'plastic_black', rot=(0, 0, 76), bevel=0.003)
    rod(P, 'pen', (-0.12, -0.20, zt + 0.005), (0.0, -0.235, zt + 0.005), 0.0045, 'plastic_blue', verts=12)
    # books on the lower shelf
    B = MB()
    zb = 0.1355
    for k, (w, d, h, c, rz) in enumerate(((0.24, 0.17, 0.030, (120, 46, 40), 4), (0.22, 0.16, 0.022, (40, 62, 80), -3),
                                          (0.26, 0.19, 0.034, (200, 190, 166), 9))):
        B.box((w, d, h), (-0.25, 0.02, zb + h / 2), (0, 0, rz), col=srgb(c))
        zb += h
    B.box((0.30, 0.22, 0.05), (0.22, 0.03, 0.1355 + 0.025), (0, 0, -5), col=srgb((60, 64, 58)))
    B.finish(P, 'books', mat('book_covers', lambda n: attr_mat(n, rough=0.55)), bevel=0.002)
    return P


# ================================================================== RUG
def _rug_tex(path, W=1300, H=900, seed=7):
    """Faded kilim-style rug: dark binding, cream and rust borders, indigo-grey field with a diamond lattice and a
    hooked central medallion; worn patches, abrash bands and pile speckle."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(seed)
    field = (78, 86, 100)
    rust = (146, 84, 64)
    cream = (196, 184, 160)
    dark = (42, 42, 48)
    ochre = (168, 132, 82)
    im = Image.new('RGB', (W, H), field)
    d = ImageDraw.Draw(im)
    px = W / 2.6                      # pixels per metre

    def rect(m, c):
        d.rectangle([m, m, W - 1 - m, H - 1 - m], fill=c)
    b = int(0.025 * px)
    rect(0, dark)
    rect(b, cream)
    rect(b + int(0.03 * px), rust)
    inner = b + int(0.03 * px) + int(0.11 * px)
    rect(inner, cream)
    rect(inner + int(0.015 * px), dark)
    rect(inner + int(0.025 * px), field)
    # border motif: small cream diamonds along the rust band
    mid = b + int(0.03 * px) + int(0.055 * px)
    step = int(0.12 * px)
    s = int(0.035 * px)
    for x in range(mid, W - mid, step):
        for y in (mid, H - 1 - mid):
            d.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=cream)
            d.polygon([(x, y - s // 2), (x + s // 2, y), (x, y + s // 2), (x - s // 2, y)], fill=dark)
    for y in range(mid + step // 2, H - mid, step):
        for x in (mid, W - 1 - mid):
            d.polygon([(x, y - s), (x + s, y), (x, y + s), (x - s, y)], fill=cream)
            d.polygon([(x, y - s // 2), (x + s // 2, y), (x, y + s // 2), (x - s // 2, y)], fill=dark)
    # field: diamond lattice
    f0 = inner + int(0.025 * px)
    cell = int(0.30 * px)
    for i in range(-2, W // cell + 3):
        for j in range(-2, H // cell + 3):
            cx, cy = f0 + i * cell + (cell // 2 if j % 2 else 0), f0 + j * cell // 2 * 1
            if not (f0 + 8 < cx < W - f0 - 8 and f0 + 8 < cy < H - f0 - 8):
                continue
            r = cell // 2 - 6
            d.polygon([(cx, cy - r // 2), (cx + r, cy), (cx, cy + r // 2), (cx - r, cy)], outline=rust, width=4)
            d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=cream)
    # central medallion (hooked diamond)
    cx, cy = W // 2, H // 2
    for r, c in ((int(0.55 * px), dark), (int(0.50 * px), rust), (int(0.40 * px), cream), (int(0.34 * px), field),
                 (int(0.22 * px), ochre), (int(0.15 * px), dark), (int(0.08 * px), cream)):
        d.polygon([(cx, cy - r * 0.62), (cx + r, cy), (cx, cy + r * 0.62), (cx - r, cy)], fill=c)
    for sx in (-1, 1):
        for k in range(3):
            x = cx + sx * int((0.62 + 0.13 * k) * px)
            r = int(0.06 * px)
            d.polygon([(x, cy - r), (x + r, cy), (x, cy + r), (x - r, cy)], fill=rust if k % 2 == 0 else cream)
    # clear the field edge so the lattice never touches the inner border
    d.rectangle([inner + int(0.015 * px), inner + int(0.015 * px), W - 1 - inner - int(0.015 * px), inner + int(0.025 * px)], fill=dark)
    d.rectangle([inner + int(0.015 * px), H - 1 - inner - int(0.025 * px), W - 1 - inner - int(0.015 * px), H - 1 - inner - int(0.015 * px)], fill=dark)
    a = np.asarray(im).astype(np.float32) / 255.0
    # abrash: horizontal-ish bands of slightly different dye lots (along the weave = x)
    rs = np.random.RandomState(seed)
    bands = np.repeat(rs.rand(W // 18 + 1), 18)[:W]
    bands = np.convolve(bands, np.ones(25) / 25, 'same')
    a *= (0.94 + 0.10 * bands)[None, :, None]
    worn = _np_noise(W, H, 160, seed + 1, 4)
    a = a * (0.86 + 0.22 * worn[..., None])
    fade = np.clip((worn - 0.62) * 3.0, 0, 1)[..., None]
    a = a * (1 - 0.25 * fade) + 0.25 * fade * np.array([0.62, 0.58, 0.52])
    speck = rs.rand(H, W)
    a *= (0.93 + 0.10 * speck)[..., None]
    a = np.clip(a, 0, 1)
    out = Image.fromarray((a * 255).astype(np.uint8), 'RGB').filter(ImageFilter.GaussianBlur(0.8))
    out.save(path)


def build_rug(collection=None, size=(2.6, 1.8), seed=7):
    """Low-pile rug: a gently uneven slab (one corner a little lifted), bound edge, cotton fringes on the short ends."""
    P = kit5.Prop('rug', collection)
    rnd = kit5.rng(seed)
    W, H = size
    img = image(f'lv_rug_{TEXVER}.png', _rug_tex)

    def rm(n):
        T = mat5._NT(n)
        tc = T.node('ShaderNodeTexCoord')
        tx = T.node('ShaderNodeTexImage')
        tx.image = img
        tx.extension = 'EXTEND'
        T.link(tc.outputs['UV'], tx.inputs['Vector'])
        v = T.coord(1.0)
        pile = T.noise(v, 900.0, 2.0, 0.6)
        tuft = T.noise(v, 140.0, 3.0, 0.6)
        h = T.mix(0.5, pile.outputs['Color'], tuft.outputs['Color'])
        bw = T.node('ShaderNodeRGBToBW')
        T.link(h, bw.inputs['Color'])
        col = T.mix(T.maprange(bw.outputs['Val'], 0.3, 0.7, 0.0, 0.18), tx.outputs['Color'], (20, 18, 18), 'MULTIPLY')
        return T.set(base=col, rough=0.96, sheen=1.0, spec=0.2, normal=T.bump(bw.outputs['Val'], 0.5, 0.0015))
    m = mat('rug', rm)
    nx, ny = 52, 36
    t = 0.009
    verts, faces, uvs = [], [], []
    for i in range(nx + 1):
        for j in range(ny + 1):
            u, v = i / nx, j / ny
            x, y = (u - 0.5) * W, (v - 0.5) * H
            z = t / 2 + 0.0015 * mnoise.noise(Vector((x * 1.3, y * 1.3, 0.5)))
            # one corner (front-right) curls up a little, a soft ripple near the back-left
            dc = math.hypot(x - W / 2, y + H / 2)
            z += 0.016 * max(0.0, 1 - dc / 0.32) ** 2
            z += 0.004 * math.exp(-((x + 0.7) ** 2 / 0.05 + (y - 0.45) ** 2 / 0.5))
            verts.append((x, y, z))
            uvs.append((u, v))
    for i in range(nx):
        for j in range(ny):
            a = i * (ny + 1) + j
            faces.append((a, a + ny + 1, a + ny + 2, a + 1))
    ob = mk(P, 'pile', verts, faces, m=m, uvs=uvs, solidify=t, sharp=False)
    ob.modifiers['solid'].use_rim = True
    # fringes: short cotton strands on the two short ends
    F = MB()
    for sx in (-1, 1):
        y = -H / 2 + 0.03
        while y < H / 2 - 0.03:
            L = 0.055 + rnd.uniform(-0.008, 0.01)
            a = rnd.uniform(-9, 9)
            dx = sx * L / 2
            F.box((L, 0.0042, 0.0025), (sx * W / 2 + dx * math.cos(math.radians(a)) - sx * 0.004, y + dx * math.sin(math.radians(a)) * sx,
                                        0.0015), (0, 0, a))
            y += 0.0115 + rnd.uniform(-0.002, 0.002)
    F.finish(P, 'fringe', mat('rug_fringe', lambda n: mat5.fabric(n, (204, 194, 172), 0.95, 300.0, 0.6)))
    return P


# ================================================================== FLOOR LAMP
def build_floor_lamp(collection=None, on=True, power=170.0):
    """Tripod floor lamp: three oiled-oak legs, brass hub and stem, linen drum shade (0.46 x 0.30) glowing from a
    warm bulb inside (POINT light 'bulb'), fabric cable with a foot switch running off to the back."""
    P = kit5.Prop('floor_lamp', collection)
    oak = mat('lamp_oak', lambda n: mat5.wood(n, (150, 108, 70), 'Z', ring_scale=40.0, rough=0.5, seed=9.0))
    brass = mat('brass_aged', lambda n: mat5.metal(n, (176, 140, 84), 0.36, brushed=False, seed=2.0))
    hub = Vector((0.0, 0.0, 1.20))
    for k, a in enumerate((-90, 30, 150)):
        ar = math.radians(a)
        foot = Vector((0.32 * math.cos(ar), 0.32 * math.sin(ar), 0.012))
        topp = hub + Vector((0.018 * math.cos(ar), 0.018 * math.sin(ar), 0.0))
        rod(P, 'leg', foot, topp, 0.011, oak, r2=0.016, verts=20, bevel=0.0015)
        P.cyl('tip', 0.0115, 0.012, tuple(foot - Vector((0, 0, 0.006))), 'rubber_black', rot=rot_to(topp - foot), verts=16, bevel=0.001)
    P.cyl('hub', 0.024, 0.07, (0, 0, 1.205), brass, verts=24, bevel=0.002)
    P.cyl('stem', 0.0075, 0.20, (0, 0, 1.33), brass, verts=16, bevel=0.0)
    P.cyl('socket', 0.019, 0.05, (0, 0, 1.445), 'plastic_black', verts=24, bevel=0.002)
    P.cyl('socket_ring', 0.024, 0.006, (0, 0, 1.468), brass, verts=24, bevel=0.001)
    bulb_m = mat('bulb_warm', lambda n: mat5.emissive(n, (255, 190, 120), 9.0, (240, 230, 210)))
    P.sphere('bulb_glass', 0.032, (0, 0, 1.505), bulb_m, segments=24, rings=12)
    zb, zt, R = 1.36, 1.66, 0.23
    shade = mat('shade_linen', lambda n: translucent_fabric(n, (226, 214, 190), (255, 214, 160), 0.55))
    v, f = lathe_geo([(R, zb), (R, (zb + zt) / 2), (R, zt)], 48)
    mk(P, 'shade', v, f, m=shade, sharp=False)
    for z in (zb, zt):
        P.torus('shade_ring', R, 0.0028, (0, 0, z), brass)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        rod(P, 'spider', (0.022 * math.cos(a), 0.022 * math.sin(a), 1.468), (R * math.cos(a), R * math.sin(a), 1.47), 0.0018, brass, verts=8)
    if on:
        P.light('bulb', 'POINT', (0, 0, 1.505), power, color=(1.0, 0.74, 0.47), size=0.03)
    # cable down the back leg, across the floor, foot switch
    a = math.radians(150)
    foot = Vector((0.32 * math.cos(a), 0.32 * math.sin(a), 0.0))
    d = (hub - foot)
    side = Vector((-math.sin(a), math.cos(a), 0)) * 0.016
    cab = [tuple(hub + Vector((0, 0, -0.03)) + side), tuple(foot + d * 0.6 + side), tuple(foot + d * 0.25 + side),
           tuple(foot + d * 0.04 + side + Vector((0, 0, 0.004))), (foot.x - 0.08, foot.y + 0.10, 0.005),
           (foot.x - 0.12, foot.y + 0.35, 0.005), (foot.x - 0.05, foot.y + 0.62, 0.005), (foot.x + 0.10, foot.y + 0.80, 0.005)]
    P.tube('cable', cab, 0.0032, mat('cable_fabric', lambda n: mat5.fabric(n, (40, 40, 42), 0.8, 900.0, 0.4)), resolution=10)
    P.box('switch', (0.035, 0.07, 0.018), (foot.x - 0.11, foot.y + 0.22, 0.009), 'plastic_black', rot=(0, 0, 12), bevel=0.006, segments=3)
    return P


# ================================================================== PLANTS
def _leaf_outline_monstera(S):
    cx = S / 2
    top = [(0.0, 0.105), (0.05, 0.065), (0.12, 0.022), (0.20, 0.006), (0.28, 0.012), (0.35, 0.038), (0.41, 0.08)]
    marg = [(0.12, 0.45), (0.2, 0.48), (0.3, 0.49), (0.42, 0.475), (0.55, 0.445), (0.68, 0.385), (0.8, 0.30),
            (0.9, 0.18), (0.965, 0.07), (0.995, 0.0)]
    left = [(cx - h * S, t * S) for h, t in top] + [(cx - h * S, t * S) for t, h in marg]
    right = [(cx + h * S, t * S) for t, h in reversed(marg)] + [(cx + h * S, t * S) for h, t in reversed(top)]
    return left + right


def _hw(t):
    marg = [(0.08, 0.40), (0.12, 0.45), (0.2, 0.48), (0.3, 0.49), (0.42, 0.475), (0.55, 0.445), (0.68, 0.385), (0.8, 0.30),
            (0.9, 0.18), (0.965, 0.07), (1.0, 0.0)]
    for (t0, h0), (t1, h1) in zip(marg, marg[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            return h0 + (h1 - h0) * k
    return 0.0


def _monstera_tex(path, seed=1, slits=7, holes=True):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(seed)
    S = 1024
    cx = S / 2
    mask = Image.new('L', (S, S), 0)
    md = ImageDraw.Draw(mask)
    md.polygon(_leaf_outline_monstera(S), fill=255)
    col = Image.new('RGB', (S, S), (34, 70, 36))
    cd = ImageDraw.Draw(col)
    # lateral veins: from the midrib at t0 to the margin at t1
    veins = []
    for side in (-1, 1):
        n = slits + 1
        for k in range(n):
            t0 = 0.12 + 0.70 * k / (n - 1) + rnd.uniform(-0.015, 0.015)
            t1 = min(0.97, t0 + 0.10 + 0.06 * t0)
            veins.append((side, t0, t1))
    for side, t0, t1 in veins:
        x1 = cx + side * _hw(t1) * S * 0.98
        xm = cx + side * _hw(t1) * S * 0.45
        cd.line([(cx, t0 * S), (xm, (t0 + (t1 - t0) * 0.62) * S), (x1, t1 * S)], fill=(62, 102, 56), width=7)
    cd.line([(cx, 0.10 * S), (cx, 0.99 * S)], fill=(104, 136, 80), width=16)
    cd.line([(cx, 0.6 * S), (cx, 0.99 * S)], fill=(96, 128, 74), width=9)
    # fenestrations: slits from the margin between two veins, holes near the midrib
    for side in (-1, 1):
        vs = sorted([v for v in veins if v[0] == side], key=lambda v: v[1])
        for a, b in zip(vs, vs[1:]):
            t0 = (a[1] + b[1]) / 2
            t1 = (a[2] + b[2]) / 2
            if slits and rnd.random() < 0.92:
                depth = rnd.uniform(0.38, 0.62)
                xm = cx + side * _hw(t1) * S * (1.08)
                ym = t1 * S + 0.01 * S
                xi = cx + side * _hw(t1) * S * (1 - depth)
                yi = (t1 - (t1 - t0) * depth * 0.75) * S
                w0, w1 = rnd.uniform(0.008, 0.013) * S, 0.020 * S
                dx, dy = xm - xi, ym - yi
                ln = math.hypot(dx, dy)
                nx_, ny_ = -dy / ln, dx / ln
                md.polygon([(xi + nx_ * w0, yi + ny_ * w0), (xm + nx_ * w1, ym + ny_ * w1),
                            (xm - nx_ * w1, ym - ny_ * w1), (xi - nx_ * w0, yi - ny_ * w0)], fill=0)
                md.ellipse([xi - w0, yi - w0, xi + w0, yi + w0], fill=0)
            if holes and 0.25 < t0 < 0.75 and rnd.random() < 0.7:
                xh = cx + side * _hw(t0) * S * rnd.uniform(0.18, 0.26)
                yh = (t0 + 0.04) * S
                rx, ry = 0.012 * S, 0.035 * S
                hole = Image.new('L', (S, S), 0)
                hd = ImageDraw.Draw(hole)
                hd.ellipse([xh - rx, yh - ry, xh + rx, yh + ry], fill=255)
                hole = hole.rotate(side * 35, center=(xh, yh))
                mask.paste(0, (0, 0), hole)
    a = np.asarray(col).astype(np.float32)
    nz = _np_noise(S, S, 90, seed, 4)
    a *= (0.85 + 0.3 * nz)[..., None]
    yy = np.linspace(0, 1, S)[:, None]
    a *= (0.92 + 0.1 * yy)[..., None]
    col = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    out = col.convert('RGBA')
    out.putalpha(mask)
    out = out.resize((512, 512), Image.LANCZOS)
    out.save(path)


def _pothos_tex(path, seed=4):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(seed)
    S = 512
    cx = S / 2
    pts = []
    for k in range(64):
        t = k / 63                                   # 0 = sinus (top) .. 1 = tip (bottom)
        y = (0.10 + 0.88 * t) * S
        w = math.sin(math.pi * min(1.0, t * 1.15) ** 0.75) * (1 - 0.35 * t) * 0.46 * S
        if t < 0.15:
            y -= (0.15 - t) / 0.15 * 0.08 * S
            w = max(w, 0.30 * S * t / 0.15)
        pts.append((cx - w, y))
    left = [(cx, 0.16 * S)] + pts
    right = [(2 * cx - x, y) for x, y in reversed(pts)]
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).polygon(left + right, fill=255)
    col = Image.new('RGB', (S, S), (46, 96, 40))
    d = ImageDraw.Draw(col)
    for _ in range(26):                              # golden variegation streaks along the veins
        side = rnd.choice((-1, 1))
        t0 = rnd.uniform(0.15, 0.8)
        x0, y0 = cx + side * rnd.uniform(0, 0.05) * S, t0 * S
        x1, y1 = cx + side * rnd.uniform(0.15, 0.42) * S, (t0 + rnd.uniform(0.05, 0.2)) * S
        d.line([(x0, y0), (x1, y1)], fill=(200, 190, 110), width=rnd.randint(3, 10))
    d.line([(cx, 0.15 * S), (cx, 0.97 * S)], fill=(120, 150, 80), width=6)
    col = col.filter(ImageFilter.GaussianBlur(2.0))
    a = np.asarray(col).astype(np.float32) * (0.85 + 0.3 * _np_noise(S, S, 60, seed, 3))[..., None]
    col = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert('RGBA')
    col.putalpha(mask.filter(ImageFilter.GaussianBlur(1.0)))
    col.save(path)


def _leaf_mat(key, img, rough=0.38):
    def fn(n):
        return img_mat(n, img, rough=rough, alpha=True, spec=0.5, sss=0.0, translucent=0.18)
    return mat(key, fn)


def leaf_card(B, T, f, s, L, W, curl=0.15, fold=0.18, wave=0.03, attach=0.10, phase=0.0, nu=7, nv=6):
    """Add a leaf card to Batch B: petiole tip T, blade direction f, side s (unit vectors), length L, width W."""
    f, s = Vector(f).normalized(), Vector(s).normalized()
    nrm = f.cross(s).normalized()
    A = Vector(T) - f * attach * L

    def pos(u, w):
        v = 2 * w - 1
        p = A + f * (u * L) + s * (v * W / 2)
        p += nrm * (fold * abs(v) ** 1.5 * W / 2 - curl * L * max(0.0, u - attach) ** 2)
        p += nrm * wave * W * math.sin(7 * u + phase + 3 * v) * abs(v) ** 3
        p -= f * 0.06 * L * abs(v) ** 2 * u          # margins sweep back a little
        return p
    B.grid(pos, nu, nv, lambda u, w: (w, 1 - u))


def _stem_mat():
    return mat('stem_green', lambda n: mat5.plant(n, (78, 104, 52), 0.5, seed=4.0))


def build_plant_big(collection=None, seed=11, height=1.6):
    """Monstera deliciosa (~1.6 m) in a 0.42 m concrete pot: 12 split leaves on curving petioles, a coir moss pole
    with twine ties, aerial roots, bark mulch."""
    P = kit5.Prop('plant_big', collection)
    rnd = kit5.rng(seed)
    pot_m = mat('pot_concrete', lambda n: mat5.concrete(n, (150, 147, 140), 0.8, seed=3.0))
    rim, zt = 0.21, 0.40
    prof = [(0.0, 0.0), (0.165, 0.0), (0.172, 0.006), (0.205, zt - 0.02), (rim, zt - 0.004), (rim - 0.004, zt),
            (rim - 0.016, zt), (rim - 0.02, zt - 0.006), (rim - 0.026, 0.25), (0.0, 0.25)]
    lathe(P, 'pot', prof, (0, 0, 0), pot_m, segs=40)
    soil_z = zt - 0.045
    P.cyl('soil', rim - 0.021, 0.02, (0, 0, soil_z - 0.01), 'soil', verts=40, bevel=0)
    bark = MB()
    for _ in range(70):
        a, r = rnd.uniform(0, 6.283), math.sqrt(rnd.random()) * (rim - 0.035)
        bark.box((rnd.uniform(0.012, 0.03), rnd.uniform(0.008, 0.02), 0.005), (r * math.cos(a), r * math.sin(a), soil_z + 0.002),
                 (rnd.uniform(-15, 15), rnd.uniform(-15, 15), rnd.uniform(0, 180)))
    bark.finish(P, 'bark', mat('bark_chips', lambda n: mat5.wood(n, (96, 60, 38), 'X', ring_scale=200.0, rough=0.85)), bevel=0.001)
    # coir moss pole
    coir = mat('coir', lambda n: mat5.leather(n, (98, 70, 46), rough=0.95))
    pole_h = height * 0.80
    P.cyl('pole', 0.028, pole_h - soil_z + 0.1, (0.01, 0.02, (pole_h + soil_z - 0.1) / 2), coir, verts=20, bevel=0.004)
    stem_m = _stem_mat()
    big = image(f'lv_monstera_a_{TEXVER}.png', lambda p: _monstera_tex(p, 1, 7, True))
    small = image(f'lv_monstera_b_{TEXVER}.png', lambda p: _monstera_tex(p, 2, 4, False))
    Bb, Bs = Batch(), Batch()
    n = 15
    for k in range(n):
        az = k * 2.39996 + rnd.uniform(-0.25, 0.25)
        tall = k / (n - 1)                                   # 0 = low outer leaves, 1 = tall leaves on the pole
        H = soil_z + 0.30 + tall * (height - 0.07 - soil_z - 0.30) + rnd.uniform(-0.05, 0.04)
        reach = 0.62 - 0.40 * tall + rnd.uniform(-0.06, 0.06)
        base = Vector((0.05 * math.cos(az * 3), 0.05 * math.sin(az * 3), soil_z))
        radial = Vector((math.cos(az), math.sin(az), 0.0))
        tip = Vector((radial.x * reach, radial.y * reach, H))
        if tall > 0.5:                                       # tall stems climb along the pole first
            p1 = Vector((0.01, 0.02, soil_z)) + radial * 0.04 + Vector((0, 0, 0.62 * (H - soil_z)))
            p0 = Vector((0.01, 0.02, soil_z)) + radial * 0.035 + Vector((0, 0, 0.3 * (H - soil_z)))
        else:
            p0 = base + radial * 0.03 + Vector((0, 0, 0.2 * (H - soil_z)))
            p1 = base + radial * 0.12 * reach / 0.5 + Vector((0, 0, 0.62 * (H - soil_z)))
        p2 = tip - radial * 0.18 * reach + Vector((0, 0, 0.01))
        pts = [tuple(base), tuple(p0), tuple(p1), tuple(p2), tuple(tip)]
        P.tube('petiole', pts, 0.0075 + 0.004 * (1 - tall), stem_m, resolution=8)
        L = 0.40 + 0.20 * (1 - abs(tall - 0.4) * 1.4) + rnd.uniform(-0.05, 0.05)
        pitch = math.radians(rnd.uniform(22, 48))
        f = Vector((radial.x * math.cos(pitch), radial.y * math.cos(pitch), -math.sin(pitch)))
        s = Vector((-radial.y, radial.x, 0.0))
        roll = math.radians(rnd.uniform(-28, 28))
        s = (s * math.cos(roll) + f.cross(s) * math.sin(roll)).normalized()
        B = Bb if L > 0.42 else Bs
        leaf_card(B, tip, f, s, L, L * 0.92, curl=rnd.uniform(0.12, 0.28), fold=rnd.uniform(0.12, 0.28),
                  wave=0.025, phase=rnd.uniform(0, 6))
        if tall > 0.5 and k % 2:
            P.torus('twine', 0.036, 0.0018, (0.01, 0.02, p1.z * 0.85 + soil_z * 0.15), mat('twine', lambda n: mat5.fabric(n, (170, 150, 110), 0.9, 600.0, 0.2)))
    Bb.finish(P, 'leaves_big', _leaf_mat('monstera_a', big))
    Bs.finish(P, 'leaves_small', _leaf_mat('monstera_b', small))
    # aerial roots
    root_m = mat('aerial_root', lambda n: mat5.matte(n, (96, 72, 50), 0.8, 0.12))
    for k in range(3):
        az = rnd.uniform(0, 6.28)
        r0 = Vector((0.05 * math.cos(az), 0.05 * math.sin(az), soil_z + rnd.uniform(0.25, 0.45)))
        r1 = Vector((0.14 * math.cos(az), 0.14 * math.sin(az), soil_z + 0.12))
        P.tube('root', [tuple(r0), tuple((r0 + r1) / 2 + Vector((0, 0, 0.02))), tuple(r1), (r1.x * 1.05, r1.y * 1.05, soil_z - 0.01)], 0.003, root_m, resolution=6)
    return P


# ================================================================== SMALL PLANTS
def _mth(T, op, a, b=None):
    n = T.node('ShaderNodeMath', operation=op)
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            T.link(x, n.inputs[i])
    return n.outputs['Value']


def pot(P, name, r, h, m, loc, wall=0.006, flare=0.14, soil=True):
    """Flower pot (lathe): tapered, thick rim, soil disc near the top."""
    rb = r * (1 - flare)
    x, y, z = loc
    prof = [(0.0, 0.0), (rb - 0.004, 0.0), (rb, 0.004), (r - 0.002, h - 0.004), (r, h - 0.001), (r - 0.002, h),
            (r - wall, h), (r - wall - 0.001, h - 0.008), (rb - wall + 0.004, h * 0.55), (0.0, h * 0.55)]
    lathe(P, name, prof, loc, m, segs=28)
    if soil:
        P.cyl(name + '_soil', r - wall - 0.003, 0.004, (x, y, z + h * 0.86), 'soil', verts=28, bevel=0)
    return z + h * 0.88


def _pothos(P, origin, rnd, vines=6, hang=0.0, edge_y=-0.12, spread=0.32, pot_h=0.12, pot_r=0.07, size=1.0):
    """Golden pothos growing from a pot whose base is at origin: a crown of leaves + vines trailing on the surface or,
    with hang > 0, falling over a front edge at y = origin.y + edge_y down to about -hang."""
    img = image(f'lv_pothos_{TEXVER}.png', _pothos_tex)
    lm = _leaf_mat('pothos', img, 0.42)
    stem = mat('pothos_stem', lambda n: mat5.plant(n, (96, 124, 62), 0.5, seed=2.0))
    B = Batch()
    O = Vector(origin)
    up = Vector((0, 0, 1))
    soil = O + Vector((0, 0, pot_h * 0.88))
    for k in range(8):
        az = k * 2.4 + rnd.uniform(-0.3, 0.3)
        rad = Vector((math.cos(az), math.sin(az), 0.0))
        T = soil + rad * rnd.uniform(0.01, 0.045) + Vector((0, 0, rnd.uniform(0.04, 0.10) * size))
        p = math.radians(rnd.uniform(5, 35))
        f = (rad * math.cos(p) - up * math.sin(p)).normalized()
        s = up.cross(f).normalized()
        L = rnd.uniform(0.07, 0.095) * size
        leaf_card(B, T, f, s, L, L * 0.72, curl=0.12, fold=0.2, wave=0.0, attach=0.14, nu=4, nv=4)
        P.tube('pstem', [tuple(soil + rad * 0.005), tuple(soil + rad * 0.01 + Vector((0, 0, (T.z - soil.z) * 0.6))), tuple(T)],
               0.0018, stem, resolution=4)
    for v in range(vines):
        if hang:
            az = math.radians(-90 + rnd.uniform(-70, 70))
        else:
            az = v * 2 * math.pi / vines + rnd.uniform(-0.4, 0.4)
        rad = Vector((math.cos(az), math.sin(az), 0.0))
        side = up.cross(rad)
        pts = [soil + rad * 0.015, soil + rad * (pot_r * 0.8) + Vector((0, 0, 0.03)),
               O + rad * (pot_r + 0.012) + Vector((0, 0, pot_h + 0.005))]
        L1 = rnd.uniform(0.6, 1.0)
        if hang and rad.y < -0.2:
            # down the pot side, along the shelf to the edge, over it and down
            pts.append(O + rad * (pot_r + 0.022) + Vector((0, 0, pot_h * 0.45)))
            t = (edge_y) / rad.y if rad.y < -0.01 else 0.1
            e = O + rad * max(pot_r + 0.04, t) + Vector((0, 0, 0.006))
            pts.append(O + rad * (pot_r + 0.03) + Vector((0, 0, 0.006)))
            pts.append(e)
            sway = side * rnd.uniform(-0.05, 0.05)
            pts.append(e + Vector((0, -0.012, -0.03)))
            pts.append(e + Vector((0, -0.02, -hang * 0.45 * L1)) + sway * 0.5)
            pts.append(e + Vector((0, -0.015, -hang * L1)) + sway)
        else:
            pts.append(O + rad * (pot_r + 0.025) + Vector((0, 0, pot_h * 0.4)))
            pts.append(O + rad * (pot_r + 0.04) + Vector((0, 0, 0.006)))
            R1 = pot_r + spread * L1
            pts.append(O + rad * (pot_r + 0.04 + (R1 - pot_r) * 0.5) + side * rnd.uniform(-0.05, 0.05) + Vector((0, 0, 0.006)))
            pts.append(O + rad * R1 + side * rnd.uniform(-0.08, 0.08) + Vector((0, 0, 0.006)))
        path = spline([tuple(p) for p in pts], per=6)
        P.tube('vine', [tuple(p) for p in path[::3]] + [tuple(path[-1])], 0.0021, stem, resolution=3)
        acc, sgn = 0.0, 1
        for i in range(4, len(path) - 1):
            acc += (path[i] - path[i - 1]).length
            if acc < 0.045:
                continue
            acc = 0.0
            sgn = -sgn
            t = (path[i + 1] - path[i - 1]).normalized()
            frac = i / len(path)
            L = (0.075 - 0.035 * frac) * size * rnd.uniform(0.85, 1.1)
            hanging = t.z < -0.6
            if hanging:
                ref = Vector((0, -1, 0))
                side_v = ref.cross(t).normalized() * sgn
                f = (side_v * 0.6 + t * 0.55 + ref * 0.3).normalized()
                s = ref.cross(f).normalized()
            else:
                side_v = up.cross(t).normalized() * sgn
                f = (side_v * 0.75 + t * 0.35 + up * 0.35).normalized()
                s = up.cross(f).normalized()
            leaf_card(B, path[i] + side_v * 0.006, f, s, L, L * 0.72, curl=0.15, fold=0.18, wave=0.0, attach=0.14,
                      nu=4, nv=4, phase=rnd.uniform(0, 6))
    B.finish(P, 'pothos_leaves', lm)


def _echeveria(P, name, loc, rnd, r=0.055, n=28, rgb=(122, 150, 140)):
    """Rosette succulent: thick pointed leaves on a golden-angle spiral, outer ones flat, inner ones upright."""
    m = mat(f'succ_{rgb}', lambda nm: mat5.plant(nm, rgb, 0.45, seed=5.0))
    B = MB()
    for k in range(n):
        t = k / (n - 1)
        az = k * 137.5 + rnd.uniform(-5, 5)
        L = r * (1.0 - 0.6 * t)
        W = L * 0.42
        Th = L * 0.22
        verts, faces = [], []
        nu, nv = 7, 8
        for i in range(nu + 1):
            u = i / nu
            for j in range(nv):
                a = 2 * math.pi * j / nv
                wid = W * math.sin(math.pi * min(1.0, u * 0.95 + 0.05)) ** 0.7 * (1 - 0.35 * u)
                th = Th * (1 - 0.6 * u) * (0.3 if math.sin(a) > 0 else 1.0)
                verts.append((wid * math.cos(a), u * L, th * math.sin(a) + 0.12 * L * u * u))
        for i in range(nu):
            for j in range(nv):
                a0, a1 = i * nv + j, i * nv + (j + 1) % nv
                faces.append((a0, a1, a1 + nv, a0 + nv))
        verts.append((0, L * 1.02, 0.12 * L))
        tip = len(verts) - 1
        for j in range(nv):
            faces.append((nu * nv + j, nu * nv + (j + 1) % nv, tip))
        pitch = 8 + 70 * t ** 1.3
        B.geo(verts, faces, loc=(loc[0], loc[1], loc[2] + 0.004 + 0.01 * t), rot=(pitch, 0, az - 90))
    B.finish(P, name, m, sharp=False)


def _cactus(P, name, loc, R=0.032, h=0.11, ribs=9, rgb=(62, 98, 66)):
    m = mat('cactus', lambda n: mat5.plant(n, rgb, 0.6, seed=7.0))
    segs, rings = 54, 18
    verts, faces = [], []
    for i in range(rings + 1):
        t = i / rings
        z = t * h
        rr = R * (0.88 + 0.12 * min(1.0, t * 4))
        if z > h - R:
            k = (z - (h - R)) / R
            rr *= math.sqrt(max(0.0, 1 - k * k))
        for j in range(segs):
            a = 2 * math.pi * j / segs
            rib = 1 + 0.10 * math.cos(ribs * a)
            verts.append((loc[0] + rr * rib * math.cos(a), loc[1] + rr * rib * math.sin(a), loc[2] + z))
    for i in range(rings):
        for j in range(segs):
            a0, a1 = i * segs + j, i * segs + (j + 1) % segs
            faces.append((a0, a1, a1 + segs, a0 + segs))
    verts.append((loc[0], loc[1], loc[2] + h))
    top = len(verts) - 1
    for j in range(segs):
        faces.append((rings * segs + j, rings * segs + (j + 1) % segs, top))
    mk(P, name, verts, faces, m=m, sharp=False)


def build_plant_small(collection=None, seed=4):
    """A cluster of small plants (~0.5 m wide): golden pothos in a white glazed pot trailing on the surface, an
    echeveria in terracotta, a ribbed cactus in a concrete pot with pebbles."""
    P = kit5.Prop('plant_small', collection)
    rnd = kit5.rng(seed)
    white = mat('pot_white', lambda n: mat5.ceramic(n, (226, 222, 212), 0.25))
    terra = mat('terracotta', lambda n: mat5.matte(n, (164, 92, 64), 0.85, 0.12, 0.05, 20.0))
    conc = mat('pot_concrete_s', lambda n: mat5.concrete(n, (156, 152, 146), 0.8, seed=5.0))
    pot(P, 'pot_pothos', 0.07, 0.12, white, (0.0, 0.05, 0.0))
    _pothos(P, (0.0, 0.05, 0.0), rnd, vines=5, spread=0.22)
    zs = pot(P, 'pot_echeveria', 0.052, 0.065, terra, (-0.17, -0.07, 0.0))
    _echeveria(P, 'echeveria', (-0.17, -0.07, zs), rnd)
    zc = pot(P, 'pot_cactus', 0.045, 0.07, conc, (0.15, -0.08, 0.0), soil=False)
    P.cyl('pebbles', 0.038, 0.004, (0.15, -0.08, zc - 0.004), mat('pebbles', lambda n: mat5.matte(n, (190, 184, 172), 0.8, 0.2, 0.6, 150.0)), verts=24, bevel=0)
    _cactus(P, 'cactus', (0.15, -0.08, zc - 0.004))
    return P


# ================================================================== SHELVING
SHELF_W, SHELF_D, SHELF_H = 1.2, 0.45, 2.0
SHELF_Z = (0.10, 0.55, 1.00, 1.45, 1.90)


def _slotted_black(name):
    """Black powder-coated angle steel with a row of keyhole slots on each flange (object coords of an upright)."""
    T = mat5._NT(name)
    tc = T.node('ShaderNodeTexCoord')
    sep = T.node('ShaderNodeSeparateXYZ')
    T.link(tc.outputs['Object'], sep.inputs['Vector'])
    fz = _mth(T, 'FRACT', _mth(T, 'DIVIDE', sep.outputs['Z'], 0.032))
    mz = _mth(T, 'MULTIPLY', T.maprange(fz, 0.18, 0.2, 0.0, 1.0), T.maprange(fz, 0.62, 0.64, 1.0, 0.0))
    mx = T.maprange(_mth(T, 'ABSOLUTE', _mth(T, 'SUBTRACT', sep.outputs['X'], 0.022)), 0.0035, 0.0042, 1.0, 0.0)
    my = T.maprange(_mth(T, 'ABSOLUTE', _mth(T, 'SUBTRACT', sep.outputs['Y'], 0.022)), 0.0035, 0.0042, 1.0, 0.0)
    slot = _mth(T, 'MULTIPLY', mz, _mth(T, 'MAXIMUM', mx, my))
    n = T.noise(T.coord(1.0), 9.0, 6.0, 0.65)
    worn = T.maprange(n.outputs['Fac'], 0.70, 0.73, 0.0, 1.0)
    col = T.mix(worn, (28, 30, 32), (140, 140, 142))
    col = T.mix(slot, col, (3, 3, 3))
    T.set(base=col, metal=_mth(T, 'MULTIPLY', worn, _mth(T, 'SUBTRACT', 1.0, slot)),
          rough=T.maprange(slot, 0.0, 1.0, 0.42, 0.95),
          normal=T.bump(_mth(T, 'ADD', slot, _mth(T, 'MULTIPLY', T.noise(T.coord(1.0), 120.0, 2.0, 0.5).outputs['Fac'], 0.05)), 0.4, 0.002),
          spec=0.5)
    return T.m


def profile_hole(P, name, outer, inner, depth, loc, m, bevel=0.002, rot=(0, 0, 0)):
    """Extrude an XZ outline with one hole (inner loop) along Y: saw handles, wrench rings, brackets."""
    bm = bmesh.new()
    edges = []
    for loop in (outer, inner):
        vs = [bm.verts.new((x, 0.0, z)) for x, z in loop]
        for i in range(len(vs)):
            edges.append(bm.edges.new((vs[i], vs[(i + 1) % len(vs)])))
    res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    faces = [f for f in res['geom'] if isinstance(f, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, vec=(0, -depth / 2, 0), verts=bm.verts[:])
    ext = bmesh.ops.extrude_face_region(bm, geom=faces)
    bmesh.ops.translate(bm, vec=(0, depth, 0), verts=[v for v in ext['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=bm.verts[:], edges=bm.edges[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return P._add(name, me, loc, rot, m, bevel, segments=2)


def extrude_xy(outline, z0, z1):
    n = len(outline)
    verts = [(x, y, z0) for x, y in outline] + [(x, y, z1) for x, y in outline]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return verts, faces


def build_shelving(collection=None, name='shelving'):
    """Black steel boltless shelving 2.0 x 1.2 x 0.45: slotted angle uprights, 5 steel decks on step beams, X braces
    on the sides and back, bolts, plastic feet.  P.shelf_z = top of each deck (relative to the prop)."""
    P = kit5.Prop(name, collection)
    W, Dp, H = SHELF_W, SHELF_D, SHELF_H
    up_m = mat('slotted_black', _slotted_black)
    t, a = 0.0022, 0.040
    L = [(0, 0), (a, 0), (a, t), (t, t), (t, a), (0, a)]
    v, f = extrude_xy(L, 0.0, H)
    for (sx, sy), rz in (((-1, -1), 0), ((1, -1), 90), ((1, 1), 180), ((-1, 1), -90)):
        mk(P, 'upright', v, f, (sx * W / 2, sy * Dp / 2, 0.0), (0, 0, rz), up_m, bevel=0.0008)
    deck = mat('deck_black', lambda n: mat5.painted_metal(n, (34, 35, 37), 0.5, 0.08, seed=3.0))
    bolts = MB()
    for z in SHELF_Z:
        P.box('deck', (W - 0.006, Dp - 0.008, 0.010), (0, 0, z - 0.005), deck, bevel=0.0015)
        for sy in (-1, 1):
            P.box('beam', (W - 0.006, 0.020, 0.045), (0, sy * (Dp / 2 - 0.012), z - 0.0225), 'steel_black', bevel=0.002)
            for sx in (-1, 1):
                for dz in (-0.012, -0.033):
                    bolts.cyl(0.0048, 0.004, (sx * (W / 2 - 0.022), sy * (Dp / 2 + 0.002), z + dz), (90, 0, 0), segs=6)
        for sx in (-1, 1):
            P.box('side_beam', (0.018, Dp - 0.05, 0.03), (sx * (W / 2 - 0.011), 0, z - 0.015), 'steel_black', bevel=0.002)
    # X braces: sides (two per side) and the back
    br = MB()
    for sx in (-1, 1):
        x = sx * (W / 2 + 0.0035)
        for z0, z1 in ((SHELF_Z[0], SHELF_Z[2]), (SHELF_Z[2], SHELF_Z[4])):
            for y0, y1 in ((-Dp / 2 + 0.025, Dp / 2 - 0.025), (Dp / 2 - 0.025, -Dp / 2 + 0.025)):
                dy, dz = y1 - y0, (z1 - 0.05) - (z0 - 0.0)
                br.box((0.003, math.hypot(dy, dz), 0.02), (x, (y0 + y1) / 2, (z0 + z1 - 0.05) / 2), (D(math.atan2(dz, dy)), 0, 0))
    y = Dp / 2 + 0.0035
    for x0, x1 in ((-W / 2 + 0.03, W / 2 - 0.03), (W / 2 - 0.03, -W / 2 + 0.03)):
        dx, dz = x1 - x0, SHELF_Z[4] - SHELF_Z[0] - 0.06
        br.box((math.hypot(dx, dz), 0.003, 0.02), ((x0 + x1) / 2, y, (SHELF_Z[0] + SHELF_Z[4]) / 2), (0, -D(math.atan2(dz, dx)), 0))
    br.finish(P, 'braces', 'steel_black', bevel=0.0008)
    bolts.finish(P, 'bolts', 'steel_bare', bevel=0.0)
    feet = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            feet.box((0.046, 0.046, 0.012), (sx * (W / 2 - 0.019), sy * (Dp / 2 - 0.019), 0.006))
    feet.finish(P, 'feet', 'rubber_black', bevel=0.002)
    P.shelf_z = SHELF_Z
    return P


# ------------------------------------------------------------------ shelf contents
LABELS = ['RÉSISTANCES', 'CONDENSATEURS', 'CAPTEURS', 'MOTEURS', 'SERVOS', 'VIS & ÉCROUS', 'CÂBLES USB', 'LED',
          'BATTERIES', 'CONNECTEURS', 'PROTOS', "RÉCUP'", 'CARTES', 'ROUES']
CARTONS = ['PIÈCES ROBOT', 'NE PAS JETER', 'ÉLECTRONIQUE', 'DIVERS', 'BIP v1', 'CÂBLES', 'IMPRIMANTE 3D']


def _slug(t):
    import unicodedata
    s = unicodedata.normalize('NFD', t)
    return ''.join(c for c in s if c.isalnum()).lower()[:16]


def _label_tex(path, text, kind='card', seed=0):
    from PIL import Image, ImageDraw
    rnd = random.Random(seed)
    if kind == 'card':                       # printed white label
        im = Image.new('RGBA', (512, 160), (238, 236, 228, 255))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 511, 159], outline=(200, 196, 186, 255), width=4)
        f = font('cond', 72)
        while d.textlength(text, font=f) > 470:
            f = font('cond', f.size - 4)
        w = d.textlength(text, font=f)
        d.text(((512 - w) / 2, 80 - f.size * 0.6), text, font=f, fill=(24, 24, 26, 255))
    else:                                    # marker on cardboard (transparent)
        im = Image.new('RGBA', (512, 200), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        f = font('sansb', 70)
        while d.textlength(text, font=f) > 480:
            f = font('sansb', f.size - 4)
        d.text((16, 60), text, font=f, fill=(20, 20, 24, 235))
        d.line([(16, 150), (16 + d.textlength(text, font=f) * 0.9, 156)], fill=(20, 20, 24, 200), width=6)
        im = im.rotate(rnd.uniform(-4, 4), resample=Image.BICUBIC)
    im.save(path)


def _label_mat(text, kind='card'):
    img = image(f'lv_lab_{kind}_{_slug(text)}_{TEXVER}.png', lambda p: _label_tex(p, text, kind, len(text)))
    return mat(f'label_{kind}_{_slug(text)}', lambda n: img_mat(n, img, rough=0.7 if kind == 'card' else 0.85,
                                                              alpha=(kind != 'card')))


def _front_label(P, name, text, size, loc, kind='card', parent=None):
    return P.plane(name, size, loc, _label_mat(text, kind), rot=(90, 0, 0), parent=parent)


STORAGE_COLOURS = [(44, 46, 50), (96, 100, 104), (58, 74, 96), (200, 198, 190), (70, 84, 74)]


def item_storage_box(col, rnd, w=None, d=None, h=None, label=None, colour=None):
    w = w or rnd.choice((0.30, 0.36, 0.40))
    d = d or rnd.choice((0.30, 0.34, 0.38))
    h = h or rnd.choice((0.16, 0.20, 0.24))
    label = label or rnd.choice(LABELS)
    colour = colour or rnd.choice(STORAGE_COLOURS)

    def build():
        B = kit5.Prop('storage_box', col)
        pm = mat(f'box_plastic_{colour}', lambda n: mat5.plastic(n, colour, 0.5, seed=colour[0] / 10.0))
        B.box('body', (w - 0.012, d - 0.012, h - 0.028), (0, 0, (h - 0.028) / 2), pm, bevel=0.008, segments=3)
        B.box('lid', (w, d, 0.03), (0, 0, h - 0.015), pm, bevel=0.007, segments=3)
        for k in (-1, 1):
            B.box('lid_rib', (w * 0.7, 0.012, 0.004), (0, k * d * 0.22, h + 0.001), pm, bevel=0.0015)
            B.box('grip', (0.008, d * 0.4, 0.03), (k * (w / 2 - 0.005), 0, h - 0.05), 'plastic_black', bevel=0.003)
        lw = min(0.16, w * 0.55)
        _front_label(B, 'label', label, (lw, lw * 0.31), (rnd.uniform(-0.03, 0.03), -(d - 0.012) / 2 - 0.0012, h * 0.55))
        return B
    return w, d, build


def item_carton(col, rnd, w=None, d=None, h=None, text=None):
    w = w or rnd.choice((0.32, 0.40, 0.45))
    d = d or rnd.choice((0.30, 0.36))
    h = h or rnd.choice((0.22, 0.28, 0.32))
    text = text or rnd.choice(CARTONS)

    def build():
        B = kit5.Prop('carton', col)
        cb = mat('cardboard_b', lambda n: mat5.matte(n, (160, 120, 78), 0.88, 0.14, 0.08, 4.0, seed=rnd.random()))
        sq = rnd.uniform(-0.01, 0.01)
        soft_box(B, 'box', (w, d, h), (0, 0, h / 2), cb, r=0.004, n=(3, 3, 3), bulge=(0.004, 0.004, -0.006 + sq),
                 wobble=0.002, seed=rnd.randint(0, 99), level=1)
        tape = mat('tape', lambda n: mat5.plastic(n, (176, 146, 96), 0.25))
        B.box('tape', (0.05, d + 0.004, 0.0012), (0, 0, h - 0.004 + sq), tape, bevel=0)
        B.box('tape_f', (0.05, 0.0012, 0.06), (0, -d / 2 - 0.002, h - 0.032), tape, bevel=0)
        B.box('flap_seam', (0.002, d - 0.01, 0.0015), (0, 0, h - 0.0028 + sq), 'plastic_black', bevel=0)
        _front_label(B, 'marker', text, (w * 0.8, w * 0.8 * 0.39), (0.0, -d / 2 - 0.0035, h * 0.45), kind='marker')
        return B
    return w, d, build


BOOK_COLOURS = [(120, 44, 38), (40, 60, 82), (200, 190, 168), (52, 70, 52), (30, 30, 34), (170, 120, 60), (90, 40, 60),
                (220, 216, 206), (60, 90, 110), (150, 60, 40), (110, 110, 104)]


def item_books(col, rnd, n=None, lying=False):
    n = n or rnd.randint(7, 14)
    specs = [(rnd.uniform(0.018, 0.045), rnd.uniform(0.15, 0.22), rnd.uniform(0.20, 0.30), rnd.choice(BOOK_COLOURS)) for _ in range(n)]
    w = sum(s[0] for s in specs) + (0.06 if not lying else 0.0)
    d = max(s[1] for s in specs)
    if lying:
        w = max(s[2] for s in specs)

    def build():
        B = kit5.Prop('books', col)
        M = MB()
        if lying:
            z = 0.0
            for t, dd, hh, c in specs[:5]:
                M.box((hh, dd, t), (rnd.uniform(-0.01, 0.01), 0, z + t / 2), (0, 0, rnd.uniform(-6, 6)), col=srgb(c))
                M.box((hh - 0.004, 0.003, t * 0.5), (0, -dd / 2 - 0.0006, z + t / 2), (0, 0, 0), col=srgb((228, 224, 210)))
                z += t
        else:
            x = -w / 2
            for i, (t, dd, hh, c) in enumerate(specs):
                lean = 0.0
                if i == len(specs) - 1:
                    lean = rnd.uniform(12, 22)       # the last one leans on its neighbour
                cx = x + t / 2 + (math.sin(math.radians(lean)) * hh / 2 if lean else 0)
                M.box((t, dd, hh), (cx, dd / 2 - d / 2, hh / 2 * math.cos(math.radians(lean)) + t / 2 * math.sin(math.radians(lean))),
                      (0, lean, 0), col=srgb(c))
                # spine band (title block)
                band = tuple(min(255, int(v * 1.6 + 30)) for v in c)
                M.box((t * 0.9, 0.002, hh * 0.12), (cx, -d / 2 + 0.0002 + (d - dd), hh * 0.62), (0, lean, 0), col=srgb(band))
                x += t + 0.0015
        M.finish(B, 'books', mat('book_covers', lambda nm: attr_mat(nm, rough=0.55)), bevel=0.0015)
        return B
    return w, d, build


def item_spools(col, rnd):
    w, d = 0.26, 0.20

    def build():
        B = kit5.Prop('spools', col)
        cols = [(170, 40, 30), (24, 24, 26), (40, 80, 160), (200, 170, 40), (40, 130, 70), (200, 200, 196)]
        rnd.shuffle(cols)
        M = MB()
        wires = []
        x = -0.09
        for k in range(3):
            r = rnd.uniform(0.035, 0.05)
            hh = rnd.uniform(0.035, 0.05)
            y = rnd.uniform(-0.03, 0.03)
            M.cyl(r, 0.003, (x, y, 0.0015), segs=24)
            M.cyl(r, 0.003, (x, y, hh - 0.0015), segs=24)
            wires.append((r * 0.82, hh - 0.006, (x, y, hh / 2), cols[k]))
            x += 2 * r + 0.01
        # a spool standing on its edge at the back
        r = 0.055
        M.cyl(r, 0.003, (0.0, 0.05, r), (0, 90, 0), segs=24)
        M.cyl(r, 0.003, (0.045, 0.05, r), (0, 90, 0), segs=24)
        M.finish(B, 'flanges', 'plastic_black', bevel=0.0006)
        W = MB()
        for rr, hh, loc, c in wires:
            W.cyl(rr, hh, loc, segs=24, col=srgb(c))
        W.cyl(r * 0.8, 0.042, (0.0225, 0.05, r), (0, 90, 0), segs=24, col=srgb(cols[3]))
        wm = mat('wire_wind', lambda nm: attr_mat(nm, rough=0.3, var=0.15, bump=0.4, scale=900.0, coat=0.3))
        W.finish(B, 'windings', wm, bevel=0.0015)
        # a loose coil of wire
        B.torus('coil', 0.045, 0.003, (0.08, -0.05, 0.003), mat('wire_red', lambda nm: mat5.plastic(nm, (160, 36, 28), 0.3)))
        B.torus('coil2', 0.040, 0.003, (0.083, -0.048, 0.009), mat('wire_red', lambda nm: mat5.plastic(nm, (160, 36, 28), 0.3)))
        return B
    return w, d, build


def item_filament(col, rnd):
    w, d = 0.075, 0.21

    def build():
        B = kit5.Prop('filament', col)
        c = rnd.choice(((214, 110, 40), (40, 150, 140), (226, 226, 220), (40, 40, 44)))
        r, t = 0.10, 0.068
        M = MB()
        for sx in (-1, 1):
            M.cyl(r, 0.003, (sx * (t / 2 - 0.0015), 0, r), (0, 90, 0), segs=40)
        M.cyl(0.028, t, (0, 0, r), (0, 90, 0), segs=24)
        M.finish(B, 'reel', mat('reel_black', lambda nm: mat5.plastic(nm, (30, 30, 32), 0.3)), bevel=0.0006)
        fm = mat(f'filament_{c}', lambda nm: attr_mat(nm, rough=0.25, var=0.1, bump=0.3, scale=600.0, coat=0.4))
        F = MB()
        F.cyl(r * 0.86, t - 0.008, (0, 0, r), (0, 90, 0), segs=40, col=srgb(c))
        F.finish(B, 'filament', fm, bevel=0.002)
        return B
    return w, d, build


def item_printer(col, rnd):
    w, d = 0.42, 0.40

    def build():
        B = kit5.Prop('printer3d', col)
        alu = 'aluminium'
        blk = mat('printer_black', lambda nm: mat5.painted_metal(nm, (26, 27, 29), 0.45, 0.05, seed=4.0))
        B.box('base', (0.40, 0.36, 0.05), (0, 0, 0.025), blk, bevel=0.004)
        B.box('y_rail', (0.04, 0.34, 0.02), (0, 0, 0.06), blk, bevel=0.002)
        by = rnd.uniform(-0.06, 0.06)
        B.box('bed', (0.235, 0.235, 0.004), (0, by, 0.085), alu, bevel=0.001)
        B.box('pei', (0.225, 0.225, 0.0012), (0, by, 0.0876), mat('pei', lambda nm: mat5.matte(nm, (40, 38, 34), 0.6, 0.1, 0.2, 300.0)), bevel=0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                B.cyl('bed_knob', 0.007, 0.012, (sx * 0.105, by + sy * 0.105, 0.072), 'plastic_yellow', verts=12, bevel=0.001)
            B.box('z_post', (0.02, 0.04, 0.30), (sx * 0.18, 0.05, 0.05 + 0.15), mat('extrusion', lambda nm: mat5.metal(nm, (38, 40, 42), 0.4)), bevel=0.0015)
            B.cyl('lead_screw', 0.004, 0.27, (sx * 0.155, 0.05, 0.19), 'steel_bare', verts=8, bevel=0)
            B.box('z_motor', (0.042, 0.042, 0.04), (sx * 0.155, 0.05, 0.07), 'plastic_black', bevel=0.003)
        B.box('top_bar', (0.38, 0.02, 0.02), (0, 0.05, 0.36), mat('extrusion', lambda nm: mat5.metal(nm, (38, 40, 42), 0.4)), bevel=0.0015)
        zg = rnd.uniform(0.13, 0.2)
        B.box('x_gantry', (0.36, 0.02, 0.02), (0, 0.03, zg), mat('extrusion', lambda nm: mat5.metal(nm, (38, 40, 42), 0.4)), bevel=0.0015)
        hx = rnd.uniform(-0.08, 0.08)
        B.box('head', (0.055, 0.045, 0.07), (hx, 0.005, zg - 0.005), blk, bevel=0.004)
        B.cyl('fan', 0.017, 0.004, (hx, -0.018, zg - 0.002), 'plastic_black', rot=(90, 0, 0), verts=20, bevel=0.0008)
        B.cyl('nozzle', 0.004, 0.012, (hx, 0.0, zg - 0.046), 'brass', r2=0.0015, verts=8, bevel=0)
        # print on the bed: a little gear
        gear = []
        for k in range(48):
            a = 2 * math.pi * k / 48
            rr = 0.03 if (k // 2) % 2 == 0 else 0.026
            gear.append((rr * math.cos(a), rr * math.sin(a)))
        v, f = extrude_xy(gear, 0.0, 0.009)
        mk(B, 'print', v, f, (hx * 0.3, by, 0.0882), (0, 0, 0), mat('pla_orange', lambda nm: mat5.plastic(nm, (214, 110, 40), 0.35)), bevel=0.0006)
        # control box + screen
        B.box('ctrl', (0.10, 0.03, 0.06), (0.14, -0.175, 0.045), blk, rot=(-15, 0, 0), bevel=0.003)
        B.plane('lcd', (0.07, 0.035), (0.14, -0.1915, 0.048), mat('lcd', lambda nm: mat5.emissive(nm, (90, 150, 220), 1.2)), rot=(75, 0, 0))
        B.cyl('knob', 0.008, 0.008, (0.175, -0.19, 0.032), 'plastic_grey', rot=(75, 0, 0), verts=16, bevel=0.001)
        B.tube('ribbon', [(hx + 0.02, 0.03, zg + 0.03), (0.12, 0.06, zg + 0.10), (0.18, 0.07, 0.30)], 0.003, 'plastic_black', resolution=6)
        return B
    return w, d, build


def item_robot_arm(col, rnd):
    w, d = 0.18, 0.18

    def build():
        B = kit5.Prop('robot_arm', col)
        alu = 'aluminium'
        B.cyl('base', 0.07, 0.03, (0, 0, 0.015), 'plastic_black', verts=32, bevel=0.003)
        B.cyl('turntable', 0.055, 0.018, (0, 0, 0.039), 'plastic_white', verts=32, bevel=0.002)
        a1 = math.radians(rnd.uniform(15, 35))
        a2 = math.radians(rnd.uniform(70, 110))
        shoulder = Vector((0, 0, 0.075))
        B.box('servo_s', (0.04, 0.02, 0.04), tuple(shoulder), 'plastic_black', bevel=0.002)
        elbow = shoulder + Vector((0, math.sin(a1), math.cos(a1))) * 0.12
        for sx in (-1, 1):
            rod(B, 'upper', shoulder + Vector((sx * 0.024, 0, 0)), elbow + Vector((sx * 0.024, 0, 0)), 0.006, alu, verts=12)
        B.box('servo_e', (0.04, 0.02, 0.04), tuple(elbow), 'plastic_black', bevel=0.002)
        wrist = elbow + Vector((0, math.sin(a1 + a2), math.cos(a1 + a2))) * 0.10
        for sx in (-1, 1):
            rod(B, 'fore', elbow + Vector((sx * 0.024, 0, 0)), wrist + Vector((sx * 0.024, 0, 0)), 0.005, alu, verts=12)
        B.box('servo_w', (0.035, 0.035, 0.02), tuple(wrist), 'plastic_black', bevel=0.002)
        g = (wrist - elbow).normalized()
        for sx in (-1, 1):
            rod(B, 'finger', wrist + Vector((sx * 0.012, 0, 0)), wrist + g * 0.05 + Vector((sx * 0.008, 0, 0)), 0.004, alu, verts=8)
        for p in (shoulder, elbow):
            B.cyl('horn', 0.011, 0.004, tuple(p + Vector((0.026, 0, 0))), 'plastic_white', rot=(0, 90, 0), verts=16, bevel=0.0008)
        B.tube('wires', [tuple(shoulder + Vector((-0.02, 0.01, -0.03))), tuple((shoulder + elbow) / 2 + Vector((-0.03, 0.02, 0))),
                         tuple(elbow + Vector((-0.02, 0.0, 0.0)))], 0.002, 'plastic_red', resolution=6)
        return B
    return w, d, build


def item_robot_chassis(col, rnd):
    w, d = 0.20, 0.17

    def build():
        B = kit5.Prop('robot_chassis', col)
        acr = mat('acrylic', lambda nm: mat5.plastic(nm, (40, 44, 52), 0.15))
        B.box('plate', (0.17, 0.14, 0.004), (0, 0, 0.045), acr, bevel=0.002)
        B.box('plate2', (0.15, 0.12, 0.004), (0, 0.005, 0.085), acr, bevel=0.002)
        for x, y in ((-0.07, -0.06), (0.07, -0.06), (-0.07, 0.06), (0.07, 0.06)):
            B.cyl('standoff', 0.003, 0.04, (x, y, 0.065), 'brass', verts=6, bevel=0)
        for sx in (-1, 1):
            B.cyl('tyre', 0.033, 0.026, (sx * 0.1, -0.02, 0.033), 'rubber_black', rot=(0, 90, 0), verts=28, bevel=0.003)
            B.cyl('hub', 0.02, 0.028, (sx * 0.1, -0.02, 0.033), 'plastic_yellow', rot=(0, 90, 0), verts=20, bevel=0.001)
            B.box('motor', (0.06, 0.022, 0.018), (sx * 0.05, -0.02, 0.033), 'plastic_yellow', bevel=0.002)
        B.sphere('caster', 0.01, (0, 0.05, 0.01), 'steel_bare', segments=12, rings=8)
        B.box('battery', (0.07, 0.03, 0.02), (0, 0.03, 0.058), 'plastic_black', bevel=0.002)
        B.box('pcb', (0.07, 0.05, 0.0016), (0, 0.0, 0.0882), 'pcb_green', bevel=0)
        B.box('chip', (0.016, 0.016, 0.003), (0.01, 0.005, 0.0905), 'plastic_black', bevel=0.0004)
        B.box('sonar_pcb', (0.045, 0.002, 0.02), (0, -0.068, 0.06), 'plastic_blue', bevel=0)
        for sx in (-1, 1):
            B.cyl('sonar', 0.008, 0.012, (sx * 0.013, -0.075, 0.06), 'aluminium', rot=(90, 0, 0), verts=16, bevel=0.0008)
        return B
    return w, d, build


def item_helmet(col, rnd):
    w, d = 0.26, 0.28

    def build():
        B = kit5.Prop('helmet', col)
        c = rnd.choice(((92, 104, 78), (220, 218, 210), (40, 42, 46), (150, 54, 40)))
        shell = mat(f'helmet_{c}', lambda nm: mat5.plastic(nm, c, 0.55, seed=3.0))
        prof = []
        for k in range(13):
            a = math.radians(90 * k / 12)
            prof.append((0.115 * math.cos(a) + 0.0001, 0.02 + 0.135 * math.sin(a)))
        prof = prof[:-1] + [(0.0, 0.155)]
        inner = [(0.103, 0.022), (0.0, 0.03)]
        v, f = lathe_geo([(0.112, 0.0), (0.115, 0.012)] + prof[1:] if False else [(0.0, 0.0)] + [(0.100, 0.0), (0.112, 0.004)] + prof, 36)
        ob = mk(B, 'shell', v, f, (0, 0, 0.0), (0, 0, 0), shell)
        ob.scale = (1.0, 1.18, 1.0)
        B.torus('rim', 0.108, 0.008, (0, 0, 0.012), 'rubber_black').scale = (1.0, 1.18, 1.0)
        for k in range(5):
            B.box('vent', (0.016, 0.05, 0.03), (-0.05 + 0.025 * k, -0.06 + 0.01 * abs(k - 2), 0.135 - 0.008 * abs(k - 2)), 'plastic_black',
                  rot=(-28, (k - 2) * 14, 0), bevel=0.006)
        for sx in (-1, 1):
            B.tube('strap', [(sx * 0.105, 0.0, 0.03), (sx * 0.11, -0.02, 0.0), (sx * 0.08, -0.12, 0.003), (sx * 0.02, -0.16, 0.003)], 0.004, 'plastic_black', resolution=6)
        B.box('buckle', (0.03, 0.02, 0.008), (0.0, -0.165, 0.004), 'plastic_grey', bevel=0.002)
        return B
    return w, d, build


def item_toolbox(col, rnd):
    w, d = 0.42, 0.20

    def build():
        B = kit5.Prop('toolbox', col)
        c = rnd.choice(((150, 40, 32), (60, 64, 68), (40, 70, 110)))
        pm = mat(f'toolbox_{c}', lambda nm: mat5.painted_metal(nm, c, 0.4, 0.3, seed=2.0))
        B.box('body', (0.42, 0.20, 0.14), (0, 0, 0.07), pm, bevel=0.004)
        B.box('lid', (0.425, 0.205, 0.045), (0, 0, 0.16), pm, bevel=0.006, segments=3)
        B.box('handle_base', (0.20, 0.03, 0.01), (0, 0, 0.188), 'steel_black', bevel=0.003)
        B.tube('handle', [(-0.08, 0, 0.19), (-0.07, 0, 0.215), (0.07, 0, 0.215), (0.08, 0, 0.19)], 0.006, 'plastic_black', resolution=6)
        for sx in (-1, 1):
            B.box('latch', (0.03, 0.006, 0.04), (sx * 0.15, -0.103, 0.135), 'steel_bare', bevel=0.002)
        return B
    return w, d, build


def item_bins_row(col, rnd, n=None):
    n = n or rnd.randint(3, 5)
    w = n * 0.105
    d = 0.17

    def build():
        B = kit5.Prop('bins', col)
        bcol = rnd.choice(((40, 80, 150), (150, 40, 34), (210, 170, 40), (60, 62, 66)))
        pm = mat(f'bin_{bcol}', lambda nm: mat5.plastic(nm, bcol, 0.45))
        # side outline (y, z): high back, scooped front
        prof = [(-0.085, 0.0), (0.085, 0.0), (0.085, 0.075), (-0.05, 0.075), (-0.085, 0.045)]
        for k in range(n):
            x = -w / 2 + 0.0525 + k * 0.105
            v, f = extrude_xy([(z, y) for y, z in prof], -0.05, 0.05)
            # extrude_xy works in XY; rotate so the outline lies in YZ
            ob = mk(B, 'bin', [(zz, yy, xx) for (xx, yy, zz) in v], [tuple(reversed(ff)) for ff in f], (x, 0, 0), (0, 0, 0), pm,
                    bevel=0.0015)
            B.box('contents', (0.09, 0.05, 0.012), (x, -0.045, 0.045), mat('bin_parts', lambda nm: mat5.metal(nm, (150, 140, 120), 0.4)),
                  rot=(-40, 0, 0), bevel=0.003)
            _front_label(B, 'lab', rnd.choice(LABELS), (0.06, 0.018), (x, -0.074, 0.062), parent=None)
        return B
    return w, d, build


def item_jars(col, rnd):
    w, d = 0.20, 0.10

    def build():
        B = kit5.Prop('jars', col)
        for k in range(3):
            x = -0.065 + k * 0.065
            r, h = 0.028, rnd.uniform(0.07, 0.11)
            jar(B, f'jar{k}', (x, 0, 0), r, h, rnd.choice(('screws', 'beans', 'parts')), lid='metal')
        return B
    return w, d, build


def jar(P, name, loc, r, h, content='beans', lid='cork', fill=None):
    """Glass jar (lathe, thick glass), contents, lid."""
    gl = mat('jar_glass', lambda n: mat5.glass(n, (236, 240, 238), 0.04))
    x, y, z = loc
    prof = [(0.0, 0.0), (r - 0.004, 0.0), (r, 0.004), (r, h - 0.012), (r - 0.004, h - 0.006), (r - 0.004, h),
            (r - 0.0065, h), (r - 0.0065, h - 0.008), (r - 0.0025, h - 0.012), (r - 0.0025, 0.005), (0.0, 0.004)]
    lathe(P, name, prof, loc, gl, segs=28)
    fill = fill if fill is not None else random.Random(hash(name) & 0xffff).uniform(0.4, 0.85)
    cm = {'beans': lambda n: mat5.leather(n, (60, 34, 20), 0.35),
          'pasta': lambda n: mat5.matte(n, (220, 186, 120), 0.6, 0.1, 0.8, 60.0),
          'sugar': lambda n: mat5.matte(n, (236, 234, 228), 0.7, 0.03, 0.4, 300.0),
          'tea': lambda n: mat5.matte(n, (70, 74, 40), 0.8, 0.2, 0.8, 120.0),
          'screws': lambda n: mat5.metal(n, (170, 170, 168), 0.4, brushed=False),
          'parts': lambda n: mat5.leather(n, (120, 100, 70), 0.5)}[content]
    ch = (h - 0.015) * fill
    P.cyl(name + '_fill', r - 0.0035, ch, (x, y, z + 0.004 + ch / 2), mat('jar_' + content, cm), verts=24, bevel=0.002)
    if lid == 'cork':
        P.cyl(name + '_lid', r - 0.0052, 0.016, (x, y, z + h + 0.002), mat('cork', lambda n: mat5.matte(n, (150, 112, 72), 0.9, 0.15, 0.25, 60.0)), r2=r - 0.0040, verts=24, bevel=0.0015)
    else:
        P.cyl(name + '_lid', r + 0.0006, 0.012, (x, y, z + h + 0.002), 'aluminium', verts=24, bevel=0.0015)


def item_pothos(col, rnd, hang=0.35):
    w, d = 0.16, 0.16

    def build():
        B = kit5.Prop('pothos', col)
        pot(B, 'pot', 0.065, 0.11, mat('pot_white', lambda n: mat5.ceramic(n, (226, 222, 212), 0.25)), (0, 0, 0))
        _pothos(B, (0, 0, 0), rnd, vines=6, hang=hang, edge_y=-0.12, pot_h=0.11, pot_r=0.065, size=0.95)
        return B
    return w, d, build


def item_multimeter(col, rnd):
    w, d = 0.10, 0.06

    def build():
        B = kit5.Prop('multimeter', col)
        B.box('holster', (0.095, 0.05, 0.19), (0, 0, 0.095), mat('holster', lambda nm: mat5.rubber(nm, (196, 150, 40), 0.7)), rot=(-8, 0, 0), bevel=0.008, segments=3)
        B.box('face', (0.075, 0.004, 0.16), (0, -0.026, 0.098), 'plastic_black', rot=(-8, 0, 0), bevel=0.002)
        B.box('display', (0.06, 0.002, 0.035), (0, -0.0285, 0.15), mat('lcd_off', lambda nm: mat5.plastic(nm, (120, 130, 118), 0.15)), rot=(-8, 0, 0), bevel=0)
        B.cyl('dial', 0.022, 0.008, (0, -0.03, 0.08), 'plastic_grey', rot=(82, 0, 0), verts=24, bevel=0.002)
        return B
    return w, d, build


def item_box_stack(col, rnd, hmax=0.36):
    """Two (or three) labelled storage boxes stacked."""
    w = rnd.choice((0.30, 0.36))
    d = rnd.choice((0.30, 0.34))
    hs = [rnd.choice((0.12, 0.16)), rnd.choice((0.12, 0.16))]
    if sum(hs) + 0.12 <= hmax and rnd.random() < 0.4:
        hs.append(0.12)
    subs = [item_storage_box(col, rnd, w=w, d=d, h=h) for h in hs]

    def build():
        B = kit5.Prop('box_stack', col)
        z = 0.0
        for (ww, dd, bf), h in zip(subs, hs):
            it = bf()
            B.add(it, (rnd.uniform(-0.008, 0.008), rnd.uniform(-0.008, 0.008), z), rnd.uniform(-2.5, 2.5))
            _relink(it, B)
            z += h + 0.002
        return B
    return w, d, build


def item_carton_stack(col, rnd):
    w, d = rnd.choice((0.40, 0.45)), 0.36
    a = item_carton(col, rnd, w=w, d=d, h=0.30)
    b = item_carton(col, rnd, w=w - 0.06, d=d - 0.04, h=0.22)

    def build():
        B = kit5.Prop('carton_stack', col)
        it = a[2]()
        B.add(it, (0, 0, 0), rnd.uniform(-2, 2))
        _relink(it, B)
        it = b[2]()
        B.add(it, (rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.01), 0.302), rnd.uniform(-6, 6))
        _relink(it, B)
        return B
    return w, d, build


def item_small(col, rnd):
    """Small front-row clutter: tape rolls, a pen mug, component boxes, a cable coil, a dev board."""
    kind = rnd.choice(('tape', 'penmug', 'compboxes', 'coil', 'board', 'tape', 'compboxes'))
    w, d = 0.10, 0.09

    def build():
        B = kit5.Prop('small_' + kind, col)
        if kind == 'tape':
            c = rnd.choice(((40, 40, 44), (200, 60, 40), (220, 190, 60), (60, 110, 170)))
            tm = mat(f'tape_{c}', lambda nm: mat5.plastic(nm, c, 0.3))
            prof = [(0.025, 0.0), (0.048, 0.0), (0.048, 0.019), (0.025, 0.019), (0.025, 0.0)]
            lathe(B, 'tape', [(0.0245, 0.0), (0.047, 0.0), (0.048, 0.001), (0.048, 0.018), (0.047, 0.019), (0.0245, 0.019),
                              (0.0245, 0.0)], (0, 0, 0), tm, segs=32)
            if rnd.random() < 0.5:
                lathe(B, 'tape2', [(0.02, 0.0), (0.038, 0.0), (0.038, 0.015), (0.02, 0.015), (0.02, 0.0)], (0.004, 0.0, 0.019),
                      mat('tape_alu', lambda nm: mat5.metal(nm, (190, 190, 192), 0.3)), segs=28)
        elif kind == 'penmug':
            build_mug(B, 'pens', (0, 0, 0), rnd.uniform(0, 360), glaze=rnd.choice(((200, 196, 186), (40, 40, 44), (150, 70, 50))), coffee=False)
            for k in range(5):
                a = rnd.uniform(0, 6.28)
                tip = Vector((0.022 * math.cos(a), 0.022 * math.sin(a), 0.165))
                rod(B, 'pen', (0.01 * math.cos(a), 0.01 * math.sin(a), 0.012), tip, 0.0042,
                    rnd.choice(('plastic_blue', 'plastic_black', 'plastic_red', 'plastic_yellow', 'aluminium')), verts=8)
        elif kind == 'compboxes':
            M = MB()
            z = 0.0
            for k in range(rnd.randint(2, 4)):
                h = rnd.uniform(0.02, 0.045)
                c = rnd.choice(((230, 228, 220), (200, 60, 40), (40, 90, 150), (30, 30, 34), (220, 180, 60)))
                M.box((rnd.uniform(0.07, 0.10), rnd.uniform(0.05, 0.08), h), (rnd.uniform(-0.005, 0.005), 0, z + h / 2), (0, 0, rnd.uniform(-8, 8)), col=srgb(c))
                z += h
            M.finish(B, 'boxes', mat('comp_boxes', lambda nm: attr_mat(nm, rough=0.5)), bevel=0.0015)
        elif kind == 'coil':
            c = rnd.choice(((24, 24, 26), (200, 200, 196), (160, 36, 28)))
            cm = mat(f'cable_{c}', lambda nm: mat5.plastic(nm, c, 0.4))
            for k in range(4):
                B.torus('coil', 0.04 + rnd.uniform(-0.004, 0.004), 0.0028, (rnd.uniform(-0.004, 0.004), rnd.uniform(-0.004, 0.004), 0.003 + 0.0055 * k), cm)
        else:
            B.box('pcb', (0.069, 0.053, 0.0016), (0, 0, 0.012), 'pcb_green', bevel=0)
            for x, y in ((-0.03, -0.022), (0.03, -0.022), (-0.03, 0.022), (0.03, 0.022)):
                B.cyl('spacer', 0.003, 0.011, (x, y, 0.0055), 'brass', verts=6, bevel=0)
            B.box('chip', (0.016, 0.016, 0.003), (0.008, 0.0, 0.0144), 'plastic_black', bevel=0.0004)
            B.box('header', (0.05, 0.0025, 0.008), (0.0, 0.024, 0.017), 'plastic_black', bevel=0)
            B.box('usb', (0.012, 0.009, 0.005), (-0.03, 0.0, 0.0153), 'aluminium', bevel=0.0006)
        return B
    return w, d, build


def _shelf_levels(rnd):
    """Main items per deck (bottom -> top) and the fillers that close the gaps."""
    main = [
        [item_carton(None, rnd, w=0.42, h=0.30), item_toolbox(None, rnd), item_box_stack(None, rnd)],
        [item_printer(None, rnd), item_filament(None, rnd), item_box_stack(None, rnd)],
        [item_books(None, rnd, n=rnd.randint(10, 15)), item_robot_arm(None, rnd), item_bins_row(None, rnd), item_multimeter(None, rnd)],
        [item_storage_box(None, rnd, h=0.20), item_spools(None, rnd), item_robot_chassis(None, rnd), item_jars(None, rnd)],
        [item_helmet(None, rnd), item_carton_stack(None, rnd), item_pothos(None, rnd), item_books(None, rnd, lying=True)],
    ]
    fillers = [lambda: item_books(None, rnd, n=rnd.randint(4, 8)), lambda: item_jars(None, rnd),
               lambda: item_books(None, rnd, n=rnd.randint(5, 9)), lambda: item_spools(None, rnd),
               lambda: item_storage_box(None, rnd, w=0.25, d=0.30, h=0.12),
               lambda: item_carton(None, rnd, w=0.25, d=0.30, h=0.18), lambda: item_filament(None, rnd),
               lambda: item_books(None, rnd, lying=True)]
    return main, fillers


def build_shelving_filled(seed=1, collection=None):
    """build_shelving() + contents packed on each deck (varied per seed: order, colours, labels, swaps), gaps closed
    with fillers (books, jars, spools, small boxes) so each deck is ~90 % full."""
    P = build_shelving(collection, name=f'shelving_filled_{seed}')
    rnd = kit5.rng(seed)
    levels, fillers = _shelf_levels(rnd)
    if seed % 2:
        levels[1], levels[3] = levels[3], levels[1]
    if seed % 3 == 2:
        levels[0], levels[2] = levels[2], levels[0]
    W, Dp = SHELF_W, SHELF_D
    for li, z in enumerate(SHELF_Z):
        items = levels[li][:]
        rnd.shuffle(items)
        x = -W / 2 + 0.03 + rnd.uniform(0.0, 0.02)
        tries = 0
        while items or tries < 8:
            if items:
                w, d, build = items.pop(0)
            else:
                tries += 1
                w, d, build = rnd.choice(fillers)()
            if x + w > W / 2 - 0.02:
                continue
            item = build()
            heading = rnd.uniform(-4, 4)
            if item.name.startswith(('helmet', 'robot', 'spools', 'multimeter')):
                heading = rnd.uniform(-30, 30)
            yb = Dp / 2 - 0.03 - d / 2 - rnd.uniform(0.0, 0.035)
            if item.name.startswith('pothos'):
                yb = -Dp / 2 + 0.115
            yb = max(-Dp / 2 + d / 2 + 0.005, yb)
            P.add(item, (x + w / 2, yb, z), heading)
            _relink(item, P)
            free = (yb - d / 2) - (-Dp / 2)
            if free > 0.13 and rnd.random() < 0.75 and not item.name.startswith('pothos'):
                sw, sd, sb = item_small(None, rnd)
                sm = sb()
                P.add(sm, (x + w / 2 + rnd.uniform(-w / 2 + sw / 2, w / 2 - sw / 2) if w > sw else x + w / 2,
                           -Dp / 2 + 0.012 + sd / 2 + rnd.uniform(0, free - sd - 0.03), z), rnd.uniform(-40, 40))
                _relink(sm, P)
            x += w + rnd.uniform(0.012, 0.04)
    return P


def _relink(item, P):
    """Nested item collections live under the parent prop's collection."""
    sc = bpy.context.scene.collection
    if item.col.name in sc.children:
        sc.children.unlink(item.col)
        P.col.children.link(item.col)


# ================================================================== PEGBOARD
def _pegboard_mat(name, rgb=(150, 114, 78), pitch=0.0254, hole=0.0032):
    """Hardboard pegboard: fibrous tan board, a 1-inch grid of dark holes (object X/Z)."""
    T = mat5._NT(name)
    tc = T.node('ShaderNodeTexCoord')
    sep = T.node('ShaderNodeSeparateXYZ')
    T.link(tc.outputs['Object'], sep.inputs['Vector'])

    def cell(c):
        f = _mth(T, 'FRACT', _mth(T, 'ADD', _mth(T, 'DIVIDE', c, pitch), 0.5))
        return _mth(T, 'MULTIPLY', _mth(T, 'SUBTRACT', f, 0.5), pitch)
    dx, dz = cell(sep.outputs['X']), cell(sep.outputs['Z'])
    dist = _mth(T, 'SQRT', _mth(T, 'ADD', _mth(T, 'MULTIPLY', dx, dx), _mth(T, 'MULTIPLY', dz, dz)))
    holem = T.maprange(dist, hole - 0.0005, hole, 1.0, 0.0)
    fib = T.noise(T.coord((40.0, 40.0, 40.0)), 6.0, 6.0, 0.7)
    blot = T.noise(T.coord(1.0), 3.0, 4.0, 0.6)
    col = T.ramp(_mth(T, 'ADD', _mth(T, 'MULTIPLY', fib.outputs['Fac'], 0.5), _mth(T, 'MULTIPLY', blot.outputs['Fac'], 0.5)),
                 [(0.3, tuple(x * 0.82 for x in rgb)), (0.7, tuple(min(255, x * 1.08) for x in rgb))])
    col = T.mix(holem, col, (8, 7, 6))
    return T.set(base=col, rough=T.maprange(holem, 0.0, 1.0, 0.7, 1.0), spec=0.35,
                 normal=T.bump(_mth(T, 'ADD', _mth(T, 'MULTIPLY', holem, -1.0), _mth(T, 'MULTIPLY', fib.outputs['Fac'], 0.1)), 0.6, 0.002))


def _hook(P, x, z, y0, length=0.05, up=0.012, name='hook'):
    """Wire peg hook: out of a hole, forward, tip turned up."""
    P.tube(name, [(x, y0 + 0.004, z), (x, y0 - 0.006, z - 0.002), (x, y0 - length * 0.7, z - 0.002), (x, y0 - length, z + up)],
           0.0021, 'steel_bare', resolution=5)


def _pliers(P, cx, ztop, y, grip, jaw=0.055, handle=0.13, spread=0.022, cutters=False, name='pliers'):
    """Pliers / side cutters hanging jaws-up in the board plane (x, z) at depth y."""
    piv = Vector((cx, y, ztop - jaw))
    steel = 'steel_bare'
    for sx in (-1, 1):
        tip = piv + Vector((sx * (0.002 if not cutters else 0.004), 0, jaw))
        base = piv + Vector((sx * 0.009, 0, 0.004))
        rod(P, name + '_jaw', base, tip, 0.0055, steel, r2=0.0022 if not cutters else 0.003, verts=10)
        a = piv + Vector((sx * 0.007, 0, -0.012))
        e = piv + Vector((sx * spread, 0, -handle))
        rod(P, name + '_arm', piv, a, 0.0045, steel, verts=8)
        rod(P, name + '_grip', a, e, 0.0058, grip, r2=0.0075, verts=12, bevel=0.0)
        P.sphere(name + '_end', 0.0075, tuple(e), grip, segments=12, rings=6)
    P.cyl(name + '_pivot', 0.0085, 0.013, tuple(piv), steel, rot=(90, 0, 0), verts=16, bevel=0.0012)
    P.cyl(name + '_rivet', 0.004, 0.015, tuple(piv), 'chrome', rot=(90, 0, 0), verts=10, bevel=0.0006)


def _screwdriver(P, x, ztop, y, colour, length, name='screwdriver', phillips=False):
    hm = mat(f'sd_handle_{colour}', lambda n: mat5.plastic(n, colour, 0.22, seed=colour[1] / 20.0))
    P.cyl(name + '_handle', 0.0125, 0.09, (x, y, ztop - 0.045), hm, r2=0.0105, verts=12, bevel=0.003)
    P.cyl(name + '_cap', 0.0105, 0.006, (x, y, ztop + 0.002), 'plastic_black', verts=16, bevel=0.002)
    P.cyl(name + '_ferrule', 0.007, 0.012, (x, y, ztop - 0.096), 'chrome', r2=0.0095, verts=12, bevel=0.001)
    P.cyl(name + '_shaft', 0.0032, length, (x, y, ztop - 0.10 - length / 2), 'chrome', verts=10, bevel=0)
    P.box(name + '_tip', (0.006 if not phillips else 0.005, 0.0018 if not phillips else 0.005, 0.012), (x, y, ztop - 0.10 - length - 0.004), 'chrome', bevel=0.0005)


def _wire_coil(P, cx, ztop, y, R, turns, m, name='coil'):
    pts = []
    n = int(turns * 14)
    for k in range(n + 1):
        t = 2 * math.pi * k / 14
        pts.append((cx + R * math.sin(t) * (1 + 0.04 * math.sin(3 * t)), y - 0.004 * t / (2 * math.pi) * 1.4,
                    ztop - R + R * math.cos(t) * 1.06))
    P.tube(name, pts, 0.0022, m, resolution=3)


def build_pegboard(collection=None, z0=1.0):
    """1.1 x 0.8 m hardboard pegboard on battens (back at y = 0 = the wall), bottom edge at z0, with: a handsaw, a
    claw hammer, five screwdrivers in a rack, pliers, side cutters, two coils of wire, a spirit level, a tape measure
    and the wire hooks they hang on."""
    P = kit5.Prop('pegboard', collection)
    W, H = 1.1, 0.8
    yb = -0.0225
    yf = yb - 0.0025
    P.box('board', (W, 0.005, H), (0, yb, z0 + H / 2), mat('pegboard', _pegboard_mat), bevel=0.0012)
    pine = mat('batten', lambda n: wood2(n, (176, 136, 94), rings=60.0, rough=0.7, seed=3.0))
    for z in (z0 + 0.03, z0 + H - 0.03):
        P.box('batten', (W - 0.04, 0.02, 0.04), (0, -0.01, z), pine, bevel=0.002)
    scr = MB()
    for x in (-W / 2 + 0.03, 0.0, W / 2 - 0.03):
        for z in (z0 + 0.03, z0 + H - 0.03):
            scr.cyl(0.0045, 0.0015, (x, yf - 0.0006, z), (90, 0, 0), segs=12)
    scr.finish(P, 'screws', 'steel_bare')
    yt = yf - 0.022                       # tool plane
    # -- handsaw along the bottom (handle on the right)
    teeth = []
    L, h0, h1 = 0.42, 0.11, 0.065
    n = 84
    for k in range(n + 1):
        x = -L * k / n
        teeth.append((x, -0.004 if k % 2 else 0.0))
    outline = [(0.0, h0)] + [(-L, h1 - 0.012)] + [(-L - 0.01, h1 - 0.02)] + list(reversed(teeth))[1:] + [(0.012, 0.0), (0.012, h0)]
    outline = [(0.0, 0.0)] + teeth[1:] + [(-L - 0.006, 0.004), (-L, h1)] + [(0.0, h0)]
    sx0, sz0 = 0.02, z0 + 0.10
    P.profile('saw_blade', [(sx0 + x, z) for x, z in outline], 0.0009, (0, yt - 0.006, sz0 - 0.0), mat('saw_steel', lambda nm: mat5.metal(nm, (176, 178, 180), 0.22, seed=6.0)), bevel=0.0)
    outer = spline([(-0.008, 0.112), (0.05, 0.135), (0.112, 0.128), (0.138, 0.07), (0.118, -0.002), (0.05, -0.008), (-0.008, 0.0)], per=4, closed=True)
    inner = spline([(0.03, 0.085), (0.07, 0.098), (0.098, 0.08), (0.092, 0.03), (0.06, 0.022), (0.035, 0.045)], per=4, closed=True)
    profile_hole(P, 'saw_handle', [(p.x, p.y) for p in outer], [(p.x, p.y) for p in inner], 0.024, (sx0, yt - 0.006, sz0),
                 mat('saw_handle', lambda nm: wood2(nm, (132, 80, 48), rings=80.0, rough=0.4, varnish=0.5, seed=8.0)), bevel=0.006)
    for k in range(3):
        P.cyl('saw_screw', 0.005, 0.03, (sx0 + 0.012 + 0.012 * k, yt - 0.006, sz0 + 0.035 + 0.02 * (k % 2)), 'brass', rot=(90, 0, 0), verts=12, bevel=0.0008)
    _hook(P, sx0 + 0.07, sz0 + 0.115, yf, 0.03)
    _hook(P, sx0 - 0.30, sz0 + 0.085, yf, 0.03)
    # -- hammer (head up) on two pegs
    hx, hz = 0.40, z0 + 0.64
    oak = mat('hammer_handle', lambda nm: wood2(nm, (176, 130, 84), rings=60.0, rough=0.45, varnish=0.3, seed=4.0, axis='Z'))
    P.cyl('hammer_handle', 0.0135, 0.30, (hx, yt, hz - 0.15), oak, r2=0.012, verts=16, bevel=0.002)
    P.box('hammer_head', (0.07, 0.026, 0.028), (hx - 0.005, yt, hz + 0.012), 'steel_grey', bevel=0.004)
    P.cyl('hammer_face', 0.0145, 0.03, (hx + 0.042, yt, hz + 0.012), 'steel_bare', rot=(0, 90, 0), verts=20, bevel=0.002)
    P.box('hammer_claw', (0.06, 0.022, 0.012), (hx - 0.058, yt, hz + 0.0), 'steel_grey', rot=(0, -28, 0), bevel=0.003)
    for dx in (-0.03, 0.03):
        _hook(P, hx + dx, hz - 0.004, yf, yf - yt + 0.03, 0.006)
    # -- screwdriver rack
    rx0, rz = -0.47, z0 + 0.62
    P.box('sd_rack', (0.27, 0.05, 0.012), (rx0 + 0.13, yf - 0.025, rz), 'steel_black', bevel=0.002)
    for k, (c, ln) in enumerate((((176, 30, 26), 0.15), ((214, 170, 30), 0.12), ((30, 30, 34), 0.10), ((176, 30, 26), 0.075),
                                 ((40, 90, 160), 0.13))):
        _screwdriver(P, rx0 + 0.02 + k * 0.052, rz + 0.098, yf - 0.03, c, ln, f'sd{k}', phillips=bool(k % 2))
    # -- pliers and cutters
    _pliers(P, -0.10, z0 + 0.60, yt, mat('grip_red', lambda nm: mat5.rubber(nm, (150, 34, 28), 0.6)), name='pliers')
    _hook(P, -0.10, z0 + 0.53, yf, 0.03)
    _pliers(P, 0.02, z0 + 0.58, yt, mat('grip_yellow', lambda nm: mat5.rubber(nm, (200, 160, 30), 0.6)), jaw=0.032, handle=0.11, spread=0.026, cutters=True, name='cutters')
    _hook(P, 0.02, z0 + 0.535, yf, 0.03)
    # -- wire coils
    _hook(P, 0.20, z0 + 0.60, yf, 0.07, 0.015)
    _wire_coil(P, 0.20, z0 + 0.603, yt - 0.01, 0.055, 3.2, mat('wire_red', lambda nm: mat5.plastic(nm, (160, 36, 28), 0.3)), 'coil_red')
    _wire_coil(P, 0.20, z0 + 0.603, yt - 0.03, 0.048, 2.6, mat('wire_black', lambda nm: mat5.plastic(nm, (26, 26, 28), 0.35)), 'coil_black')
    # -- spirit level along the top
    lx, lz = 0.05, z0 + 0.735
    P.box('level', (0.60, 0.024, 0.055), (lx, yf - 0.02, lz), mat('level_alu', lambda nm: mat5.metal(nm, (196, 198, 202), 0.3)), bevel=0.002)
    for sx in (-1, 1):
        P.box('level_cap', (0.02, 0.026, 0.057), (lx + sx * 0.29, yf - 0.02, lz), 'rubber_black', bevel=0.003)
    for dx in (-0.12, 0.0):
        P.box('vial', (0.04, 0.026, 0.014), (lx + dx, yf - 0.02, lz), mat('vial', lambda nm: mat5.emissive(nm, (170, 220, 60), 0.4, (150, 200, 50))), bevel=0.003)
    for dx in (-0.2, 0.2):
        _hook(P, lx + dx, lz - 0.03, yf, 0.035, 0.006)
    # -- combination wrenches (spanners), ring end up
    for k, (ln, rr) in enumerate(((0.20, 0.016), (0.18, 0.0145), (0.16, 0.013), (0.14, 0.0115))):
        wx, wz = 0.27 + k * 0.045, z0 + 0.47
        ring = [(rr * math.cos(2 * math.pi * i / 20), rr * math.sin(2 * math.pi * i / 20)) for i in range(20)]
        hole = [(rr * 0.55 * math.cos(2 * math.pi * i / 12 + 0.26), rr * 0.55 * math.sin(2 * math.pi * i / 12 + 0.26)) for i in range(12)]
        profile_hole(P, 'wrench_ring', ring, hole, 0.006, (wx, yt + 0.008, wz), 'chrome', bevel=0.0015)
        P.box('wrench_shank', (rr * 0.85, 0.005, ln - 2.2 * rr), (wx, yt + 0.008, wz - ln / 2), 'chrome', bevel=0.0015)
        jaw = [(-rr * 1.1, 0.0), (rr * 1.1, 0.0), (rr * 1.25, -rr * 1.4), (rr * 0.45, -rr * 1.4), (rr * 0.45, -rr * 0.5),
               (-rr * 0.45, -rr * 0.5), (-rr * 0.45, -rr * 1.4), (-rr * 1.25, -rr * 1.4)]
        P.profile('wrench_jaw', [(x, z) for x, z in jaw], 0.006, (wx, yt + 0.008, wz - ln + 0.012), 'chrome', bevel=0.0012)
        _hook(P, wx, wz + rr * 0.1, yf, 0.03, 0.004)
    # -- F clamp
    fx, fz = 0.31, z0 + 0.08
    P.box('clamp_bar', (0.016, 0.008, 0.22), (fx, yt, fz + 0.11), 'steel_bare', bevel=0.001)
    P.box('clamp_jaw_fixed', (0.075, 0.016, 0.02), (fx + 0.034, yt, fz + 0.21), 'steel_grey', bevel=0.003)
    P.box('clamp_jaw_slide', (0.075, 0.016, 0.02), (fx + 0.034, yt, fz + 0.06), 'steel_grey', bevel=0.003)
    P.cyl('clamp_screw', 0.004, 0.05, (fx + 0.06, yt, fz + 0.035), 'steel_bare', verts=10, bevel=0)
    P.cyl('clamp_grip', 0.011, 0.07, (fx + 0.06, yt, fz - 0.02), mat('hammer_handle', lambda nm: wood2(nm, (176, 130, 84), rings=60.0, rough=0.45, varnish=0.3, seed=4.0, axis='Z')), r2=0.009, verts=14, bevel=0.002)
    _hook(P, fx + 0.034, fz + 0.198, yf, 0.03, 0.004)
    # -- tape measure
    P.box('tape_measure', (0.068, 0.036, 0.066), (0.46, yt, z0 + 0.25), mat('tm_yellow', lambda nm: mat5.plastic(nm, (210, 170, 30), 0.4)), bevel=0.012, segments=3)
    P.box('tape_measure_side', (0.05, 0.038, 0.05), (0.46, yt, z0 + 0.25), 'rubber_black', bevel=0.01, segments=3)
    P.box('tape_end', (0.02, 0.016, 0.004), (0.46 + 0.033, yt, z0 + 0.22), 'chrome', bevel=0.0005)
    _hook(P, 0.46, z0 + 0.29, yf, 0.035)
    # -- a bent wire bin with markers
    P.box('cup', (0.10, 0.05, 0.07), (-0.36, yf - 0.026, z0 + 0.36), 'steel_black', bevel=0.003)
    for k in range(4):
        P.cyl('marker', 0.0065, 0.13, (-0.39 + 0.02 * k, yf - 0.026 + (0.008 if k % 2 else -0.008), z0 + 0.40), rnd_marker(k), verts=10, bevel=0.0015)
    return P


def rnd_marker(k):
    return ('plastic_black', 'plastic_red', 'plastic_blue', 'plastic_black')[k % 4]


# ================================================================== DRAWER CABINET
def build_drawer_cabinet(collection=None, seed=2):
    """0.6 m steel drawer cabinet (0.46 x 0.42): five drawers with bar pulls and label holders, the second one pulled
    out showing a parts tray; on top a small plastic parts organiser, a solder reel and a multimeter."""
    P = kit5.Prop('drawer_cabinet', collection)
    rnd = kit5.rng(seed)
    W, Dp, H = 0.46, 0.42, 0.60
    body = mat('cabinet_steel', lambda n: mat5.painted_metal(n, (74, 88, 100), 0.42, 0.18, seed=6.0))
    P.box('plinth', (W - 0.02, Dp - 0.04, 0.04), (0, 0.01, 0.02), 'steel_black', bevel=0.002)
    P.box('carcass', (W, Dp, H - 0.04), (0, 0, 0.04 + (H - 0.04) / 2), body, bevel=0.003)
    hs = (0.075, 0.075, 0.10, 0.12, 0.16)
    labels = ('RÉSIST.', 'CONDOS', 'VIS', 'CÂBLES', 'OUTILS')
    z = H - 0.012
    yf = -Dp / 2
    for k, h in enumerate(hs):
        zc = z - h / 2
        opn = 0.16 if k == 1 else 0.0
        y = yf - 0.009 - opn
        P.box('front', (W - 0.016, 0.018, h - 0.006), (0, y, zc), body, bevel=0.002)
        P.box('pull', (0.30, 0.022, 0.012), (0, y - 0.017, zc + h / 2 - 0.022), 'aluminium', bevel=0.003)
        P.box('pull_lip', (0.30, 0.004, 0.02), (0, y - 0.027, zc + h / 2 - 0.03), 'aluminium', bevel=0.001)
        P.box('label_holder', (0.07, 0.003, 0.028), (0.0, y - 0.0105, zc - 0.01), 'chrome', bevel=0.0008)
        _front_label(P, 'label', labels[k], (0.062, 0.020), (0.0, y - 0.0125, zc - 0.01))
        if opn:
            # drawer box: bottom, sides, back; a tray of compartments inside
            dd = Dp - 0.04
            yc = y + 0.009 + dd / 2
            P.box('d_bottom', (W - 0.05, dd, 0.004), (0, yc, zc - h / 2 + 0.008), body, bevel=0.001)
            for sx in (-1, 1):
                P.box('d_side', (0.004, dd, h - 0.02), (sx * (W / 2 - 0.027), yc, zc - 0.002), body, bevel=0.001)
            P.box('d_back', (W - 0.05, 0.004, h - 0.02), (0, yc + dd / 2, zc - 0.002), body, bevel=0.001)
            M = MB()
            cols = [(200, 160, 60), (150, 40, 30), (40, 90, 150), (230, 228, 220), (30, 30, 34), (60, 130, 70)]
            for i in range(4):
                for j in range(3):
                    cx = -0.15 + i * 0.1
                    cy = y + 0.04 + j * 0.06
                    M.box((0.095, 0.002, 0.03), (cx, cy - 0.03, zc - h / 2 + 0.025), col=srgb((70, 72, 76)))
                    if rnd.random() < 0.85:
                        c = rnd.choice(cols)
                        for q in range(rnd.randint(3, 7)):
                            M.cyl(0.003, 0.012, (cx + rnd.uniform(-0.035, 0.035), cy + rnd.uniform(-0.02, 0.02), zc - h / 2 + 0.013),
                                  (90, 0, rnd.uniform(0, 180)), segs=6, col=srgb(c))
            M.finish(P, 'parts', mat('parts_mix', lambda nm: attr_mat(nm, rough=0.4)), bevel=0.0)
        z -= h + 0.0
    # parts organiser on top
    zt = H
    org = mat('organiser', lambda n: mat5.plastic(n, (90, 94, 98), 0.45))
    P.box('org_body', (0.30, 0.15, 0.20), (-0.06, 0.04, zt + 0.10), org, bevel=0.004)
    dr = mat('org_drawer', lambda n: mat5.plastic(n, (200, 204, 206), 0.25))
    for i in range(4):
        for j in range(4):
            x = -0.06 - 0.105 + i * 0.07
            zz = zt + 0.03 + j * 0.046
            P.box('org_front', (0.064, 0.006, 0.04), (x, 0.04 - 0.077, zz), dr, bevel=0.0015)
            P.box('org_pull', (0.02, 0.006, 0.004), (x, 0.04 - 0.082, zz - 0.012), dr, bevel=0.001)
            _front_label(P, 'org_label', rnd.choice(('LED', 'R 10k', 'R 220', 'C 100n', 'M3', 'M2', 'DIODES', 'NPN')), (0.03, 0.009),
                         (x, 0.04 - 0.0805, zz + 0.006))
    # solder reel + multimeter
    lathe(P, 'solder_reel', [(0.008, 0.0), (0.03, 0.0), (0.03, 0.003), (0.022, 0.004), (0.022, 0.026), (0.03, 0.027),
                             (0.03, 0.030), (0.008, 0.030), (0.008, 0.0)], (0.15, -0.08, zt), 'plastic_black', segs=28)
    P.cyl('solder', 0.0215, 0.022, (0.15, -0.08, zt + 0.015), mat('solder', lambda n: mat5.metal(n, (190, 192, 196), 0.3)), verts=28, bevel=0.002)
    P.tube('solder_end', [(0.15 + 0.02, -0.08, zt + 0.02), (0.2, -0.1, zt + 0.003), (0.21, -0.15, zt + 0.001)], 0.0008,
           mat('solder', lambda n: mat5.metal(n, (190, 192, 196), 0.3)), resolution=6)
    mm = item_multimeter(P.col, rnd)[2]()
    P.add(mm, (0.16, 0.08, zt), -18)
    _relink(mm, P)
    return P


# ================================================================== KITCHENETTE
def _notes_tex(path):
    """Three papers for the fridge door: a shopping list, a marker drawing of Bip, a month calendar."""
    from PIL import Image, ImageDraw, ImageFilter
    S = 1024
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # shopping list (left half, lined paper)
    d.rectangle([10, 10, 500, 700], fill=(240, 236, 222, 255))
    for k in range(14):
        d.line([(20, 90 + 44 * k), (490, 90 + 44 * k)], fill=(150, 180, 210, 255), width=2)
    d.line([(70, 10), (70, 700)], fill=(220, 120, 120, 255), width=2)
    f = ImageFont_safe('/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf', 34)
    for k, t in enumerate(('café (grains !)', 'lait', 'piles AA x8', 'étain 0,8 mm', 'pâtes', 'citrons', 'ballon -> Pico ?')):
        d.text((85, 50 + 44 * k), t, font=f, fill=(30, 40, 90, 255))
    # marker drawing of a little drone (right top)
    d.rectangle([524, 10, 1014, 480], fill=(246, 244, 238, 255))
    d.ellipse([680, 160, 860, 300], outline=(20, 20, 20, 255), width=8)
    d.ellipse([740, 205, 800, 255], outline=(30, 140, 70, 255), width=8)
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cx, cy = 770 + sx * 150, 230 + sy * 110
        d.line([(770 + sx * 70, 230 + sy * 40), (cx, cy)], fill=(20, 20, 20, 255), width=6)
        d.ellipse([cx - 45, cy - 18, cx + 45, cy + 18], outline=(20, 20, 20, 255), width=6)
    d.text((560, 400), 'BIP  v2', font=ImageFont_safe(FONTS['sansb'], 48), fill=(200, 60, 40, 255))
    # calendar (right bottom)
    d.rectangle([524, 500, 1014, 1014], fill=(236, 236, 232, 255))
    d.text((560, 515), 'NOVEMBRE', font=ImageFont_safe(FONTS['sansb'], 50), fill=(30, 30, 30, 255))
    for i in range(7):
        for j in range(5):
            x0, y0 = 540 + i * 66, 600 + j * 80
            d.rectangle([x0, y0, x0 + 62, y0 + 76], outline=(120, 120, 120, 255), width=2)
            n = j * 7 + i - 2
            if 1 <= n <= 30:
                d.text((x0 + 6, y0 + 4), str(n), font=ImageFont_safe(FONTS['sans'], 20), fill=(60, 60, 60, 255))
    d.ellipse([540 + 4 * 66 + 8, 600 + 3 * 80 + 20, 540 + 4 * 66 + 58, 600 + 3 * 80 + 70], outline=(210, 40, 40, 255), width=5)
    im.filter(ImageFilter.GaussianBlur(0.5)).save(path)


def ImageFont_safe(path, size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype(FONTS['sans'], size)


def _uv_window(ob, u0, v0, u1, v1):
    uv = ob.data.uv_layers[0]
    for i, c in enumerate(((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
        uv.data[i].uv = c


def _fridge(P, x0, H=1.25, Wd=0.55, Dp=0.60):
    """Small fridge-freezer (off-white), door papers held by magnets, a fruit bowl on top."""
    cx = x0 + Wd / 2
    yb = 0.31 - Dp / 2
    white = mat('fridge_white', lambda n: mat5.matte(n, (220, 218, 210), 0.35, 0.03, 0.02, 3.0))
    P.box('fridge_body', (Wd, Dp - 0.04, H - 0.06), (cx, yb + 0.02, 0.06 + (H - 0.06) / 2), white, bevel=0.012, segments=3)
    P.box('fridge_kick', (Wd - 0.04, 0.02, 0.06), (cx, yb - Dp / 2 + 0.06, 0.03), 'plastic_black', bevel=0.002)
    yf = yb - Dp / 2 + 0.02
    for z0, z1 in ((0.07, 0.84), (0.846, H - 0.005)):
        P.box('fridge_door', (Wd - 0.006, 0.04, z1 - z0 - 0.004), (cx, yf - 0.018, (z0 + z1) / 2), white, bevel=0.014, segments=3)
    P.box('fridge_handle', (0.022, 0.03, 0.30), (x0 + 0.04, yf - 0.05, 0.62), 'aluminium', bevel=0.006)
    P.box('freezer_handle', (0.022, 0.03, 0.18), (x0 + 0.04, yf - 0.05, 0.96), 'aluminium', bevel=0.006)
    img = image(f'lv_notes_{TEXVER}.png', _notes_tex)
    nm = mat('fridge_notes', lambda n: img_mat(n, img, rough=0.8, alpha=True))
    yd = yf - 0.039
    for name, win, size, pos, rz in (('list', (0.0, 0.31, 0.49, 0.99), (0.15, 0.21), (cx + 0.06, 0.95), 3),
                                    ('drawing', (0.51, 0.53, 0.99, 0.99), (0.17, 0.16), (cx + 0.08, 0.58), -4),
                                    ('calendar', (0.51, 0.0, 0.99, 0.51), (0.15, 0.16), (cx + 0.10, 0.36), 1)):
        ob = P.plane('note_' + name, size, (pos[0], yd, pos[1]), nm, rot=(90, rz, 0))
        _uv_window(ob, *win)
    for k, (dx, dz, c) in enumerate(((0.06, 1.05, 'plastic_red'), (0.08, 0.655, 'plastic_yellow'), (0.10, 0.435, 'plastic_blue'), (-0.12, 0.70, 'plastic_red'))):
        P.cyl('magnet', 0.011, 0.008, (cx + dx, yd - 0.004, dz), c, rot=(90, 0, 0), verts=16, bevel=0.002)
    # fruit bowl on top
    lathe(P, 'bowl', [(0.0, 0.0), (0.05, 0.0), (0.11, 0.05), (0.118, 0.07), (0.112, 0.07), (0.10, 0.052), (0.045, 0.008), (0.0, 0.008)],
          (cx - 0.05, yb + 0.03, H), mat('bowl_ceramic', lambda n: mat5.ceramic(n, (196, 120, 70), 0.25)), segs=32)
    om = mat('orange', lambda n: mat5.leather(n, (226, 120, 30), 0.45))
    for k, (dx, dy, dz) in enumerate(((-0.03, 0.0, 0.048), (0.035, 0.02, 0.05), (0.0, -0.035, 0.05), (0.01, 0.005, 0.10))):
        P.sphere('orange', 0.036, (cx - 0.05 + dx, yb + 0.03 + dy, H + dz), om, segments=20, rings=10)
    P.box('cereal', (0.19, 0.07, 0.28), (cx + 0.14, yb + 0.06, H + 0.14), mat('cereal', lambda n: mat5.matte(n, (190, 150, 60), 0.6, 0.1)), rot=(0, 0, -8), bevel=0.002)


def _espresso(P, x, y, z):
    """Black boxy espresso machine: stainless front, group head, portafilter, gauge, steam wand, drip tray, cups."""
    blk = mat('espresso_black', lambda n: mat5.painted_metal(n, (22, 22, 24), 0.35, 0.04, seed=9.0))
    ss = mat('stainless', lambda n: mat5.metal(n, (188, 190, 194), 0.25, seed=3.0))
    W, Dp, H = 0.30, 0.38, 0.36
    for dx in (-0.12, 0.12):
        for dy in (-0.15, 0.15):
            P.cyl('esp_foot', 0.012, 0.012, (x + dx, y + dy, z + 0.006), 'rubber_black', verts=12, bevel=0.002)
    zb = z + 0.012
    P.box('esp_body', (W, Dp, H), (x, y, zb + H / 2), blk, bevel=0.006, segments=3)
    yf = y - Dp / 2
    P.box('esp_front', (W - 0.01, 0.006, H * 0.42), (x, yf - 0.003, zb + H * 0.76), ss, bevel=0.002)
    # group head + portafilter
    P.box('esp_brew_block', (0.11, 0.07, 0.05), (x, yf - 0.035, zb + 0.235), ss, bevel=0.01, segments=3)
    P.cyl('esp_group', 0.036, 0.035, (x, yf - 0.05, zb + 0.195), 'chrome', verts=32, bevel=0.003)
    P.cyl('esp_basket', 0.037, 0.025, (x, yf - 0.05, zb + 0.165), 'chrome', verts=32, bevel=0.003)
    rod(P, 'esp_pf_neck', (x + 0.02, yf - 0.08, zb + 0.163), (x + 0.07, yf - 0.13, zb + 0.158), 0.009, 'chrome', verts=12)
    rod(P, 'esp_pf_handle', (x + 0.07, yf - 0.13, zb + 0.158), (x + 0.12, yf - 0.20, zb + 0.15), 0.014, 'plastic_black', r2=0.016, verts=16)
    for dx in (-0.008, 0.008):
        P.cyl('esp_spout', 0.004, 0.012, (x + dx, yf - 0.05, zb + 0.147), 'chrome', verts=8, bevel=0)
    # drip tray with grille
    P.box('esp_tray', (0.26, 0.14, 0.03), (x, yf - 0.05, zb + 0.015), ss, bevel=0.003)
    G = MB()
    for k in range(11):
        G.box((0.004, 0.12, 0.003), (x - 0.11 + k * 0.022, yf - 0.05, zb + 0.031))
    G.finish(P, 'esp_grille', 'chrome', bevel=0.0)
    P.cyl('esp_cup', 0.028, 0.06, (x, yf - 0.05, zb + 0.064), mat('cup_white', lambda n: mat5.ceramic(n, (232, 230, 224), 0.15)), r2=0.032, verts=28, bevel=0.003)
    # gauge
    P.cyl('esp_gauge_bezel', 0.03, 0.012, (x, yf - 0.009, zb + 0.30), 'chrome', rot=(90, 0, 0), verts=32, bevel=0.002)
    P.cyl('esp_gauge_face', 0.025, 0.002, (x, yf - 0.0155, zb + 0.30), 'paper_white', rot=(90, 0, 0), verts=32, bevel=0)
    P.box('esp_needle', (0.002, 0.001, 0.018), (x + 0.004, yf - 0.017, zb + 0.304), 'plastic_red', rot=(0, -30, 0), bevel=0)
    # buttons + power LED
    for k, dx in enumerate((-0.10, -0.075, 0.075, 0.10)):
        P.cyl('esp_button', 0.008, 0.006, (x + dx, yf - 0.008, zb + 0.30), 'plastic_black', rot=(90, 0, 0), verts=16, bevel=0.0015)
    P.sphere('esp_led', 0.003, (x + 0.12, yf - 0.007, zb + 0.33), mat('led_orange', lambda n: mat5.emissive(n, (255, 140, 40), 25.0)), segments=10, rings=6)
    P.light('machine_led', 'POINT', (x + 0.12, yf - 0.012, zb + 0.33), 0.05, color=(1.0, 0.55, 0.2), size=0.003)
    # steam wand + knob
    P.cyl('esp_knob', 0.016, 0.03, (x + 0.13, yf + 0.02, zb + H + 0.015), 'plastic_black', verts=20, bevel=0.003)
    P.tube('esp_wand', [(x + 0.135, yf - 0.005, zb + 0.24), (x + 0.15, yf - 0.03, zb + 0.20), (x + 0.155, yf - 0.04, zb + 0.10),
                        (x + 0.15, yf - 0.05, zb + 0.06)], 0.0045, 'chrome', resolution=8)
    # cup rail on top + two cups
    P.tube('esp_rail', [(x - 0.13, y - 0.16, zb + H + 0.01), (x - 0.13, y + 0.16, zb + H + 0.01), (x + 0.10, y + 0.16, zb + H + 0.01),
                        (x + 0.10, y - 0.16, zb + H + 0.01)], 0.004, 'chrome', resolution=6)
    for k, (dx, dy) in enumerate(((-0.06, 0.05), (0.02, -0.02))):
        P.cyl('esp_topcup', 0.028, 0.055, (x + dx, y + dy, zb + H + 0.0285), mat('cup_white', lambda n: mat5.ceramic(n, (232, 230, 224), 0.15)), r2=0.032, verts=28, bevel=0.003)


def _grinder(P, x, y, z):
    body = mat('grinder_black', lambda n: mat5.plastic(n, (28, 28, 30), 0.5))
    P.box('grinder_body', (0.12, 0.18, 0.20), (x, y, z + 0.10), body, bevel=0.02, segments=3)
    P.box('grinder_band', (0.122, 0.182, 0.03), (x, y, z + 0.175), 'aluminium', bevel=0.012, segments=3)
    smoke = mat('smoke_plastic', lambda n: mat5.glass(n, (150, 140, 130), 0.08))
    lathe(P, 'grinder_hopper', [(0.022, 0.0), (0.032, 0.0), (0.058, 0.11), (0.060, 0.115), (0.055, 0.115), (0.053, 0.11), (0.028, 0.005), (0.022, 0.005)],
          (x, y + 0.02, z + 0.20), smoke, segs=28)
    P.cyl('grinder_beans', 0.045, 0.06, (x, y + 0.02, z + 0.245), mat('jar_beans', lambda n: mat5.leather(n, (60, 34, 20), 0.35)), r2=0.024 + 0.0, verts=24, bevel=0.002)
    P.cyl('grinder_lid', 0.062, 0.012, (x, y + 0.02, z + 0.322), 'plastic_black', verts=28, bevel=0.003)
    P.cyl('grinder_cup', 0.03, 0.05, (x, y - 0.11, z + 0.025), 'aluminium', verts=24, bevel=0.002)
    P.box('grinder_chute', (0.03, 0.03, 0.02), (x, y - 0.1, z + 0.095), body, bevel=0.005)


def _kettle(P, x, y, z):
    km = mat('kettle_black', lambda n: mat5.painted_metal(n, (30, 30, 32), 0.5, 0.05, seed=2.0))
    P.cyl('kettle_base', 0.08, 0.02, (x, y, z + 0.01), 'plastic_black', verts=32, bevel=0.004)
    prof = [(0.0, 0.0), (0.07, 0.0), (0.077, 0.012), (0.078, 0.05), (0.068, 0.11), (0.05, 0.135), (0.046, 0.14), (0.0, 0.14)]
    lathe(P, 'kettle_body', prof, (x, y, z + 0.02), km, segs=32)
    P.cyl('kettle_lid', 0.046, 0.008, (x, y, z + 0.164), km, verts=28, bevel=0.002)
    P.sphere('kettle_knob', 0.012, (x, y, z + 0.175), 'wood_walnut', scale=(1, 1, 0.7))
    P.tube('kettle_handle', [(x, y + 0.072, z + 0.12), (x, y + 0.11, z + 0.16), (x, y + 0.13, z + 0.10), (x, y + 0.10, z + 0.05), (x, y + 0.075, z + 0.05)],
           0.008, km, resolution=8)
    P.tube('kettle_spout', [(x, y - 0.07, z + 0.04), (x, y - 0.11, z + 0.08), (x, y - 0.12, z + 0.17), (x, y - 0.15, z + 0.20), (x, y - 0.20, z + 0.19)],
           0.0055, km, resolution=10)


def _towel_mat(n):
    T = mat5._NT(n)
    v = T.coord(1.0)
    sep = T.node('ShaderNodeSeparateXYZ')
    T.link(v, sep.inputs['Vector'])
    bx = T.maprange(_mth(T, 'SINE', _mth(T, 'MULTIPLY', sep.outputs['X'], 140.0)), 0.6, 0.7, 0.0, 1.0)
    bz = T.maprange(_mth(T, 'SINE', _mth(T, 'MULTIPLY', sep.outputs['Z'], 140.0)), 0.6, 0.7, 0.0, 1.0)
    col = T.mix(_mth(T, 'MAXIMUM', bx, bz), (214, 206, 190), (150, 50, 40))
    w = T.node('ShaderNodeTexWave')
    w.inputs['Scale'].default_value = 500.0
    T.link(v, w.inputs['Vector'])
    return T.set(base=col, rough=0.95, sheen=0.4, spec=0.25, normal=T.bump(w.outputs['Fac'], 0.1, 0.0005))


def build_kitchenette(collection=None, fridge=True):
    """1.8 m kitchenette (front -Y, back against a wall at y = +0.31): painted cabinets (drawers, sink doors, door)
    with black bar pulls, glued oak worktop at 0.92 with an inset steel sink and a black tap, espresso machine,
    grinder, gooseneck kettle, mugs, a tea towel; an oak wall shelf (1.53 m) with jars, plates and hanging mugs;
    fridge (0.55 x 0.60 x 1.25) on the right, x 0.92..1.47 (fridge=False to leave it out)."""
    P = kit5.Prop('kitchenette', collection)
    rnd = kit5.rng(8)
    W = 1.8
    yb = 0.31
    body = mat('cab_carcass', lambda n: mat5.matte(n, (60, 72, 66), 0.6, 0.04, 0.02))
    front = mat('cab_front', lambda n: mat5.matte(n, (64, 78, 70), 0.55, 0.05, 0.02, seed=2.0))
    P.box('plinth', (W - 0.01, 0.50, 0.10), (0, yb - 0.27, 0.05), mat('plinth', lambda n: mat5.matte(n, (34, 36, 36), 0.7)), bevel=0.002)
    P.box('carcass', (W, 0.56, 0.78), (0, yb - 0.28, 0.10 + 0.39), body, bevel=0.002)
    yd = yb - 0.56 - 0.0095
    pull = mat('pull_black', lambda n: mat5.painted_metal(n, (20, 20, 22), 0.3, 0.05))
    # left: three drawers
    z = 0.88
    for k, h in enumerate((0.17, 0.27, 0.334)):
        P.box('drawer', (0.596, 0.019, h - 0.004), (-0.6, yd, z - h / 2), front, bevel=0.0025)
        zc = z - 0.05 if k else z - h / 2
        rod(P, 'pull', (-0.72, yd - 0.032, zc), (-0.48, yd - 0.032, zc), 0.0065, pull, verts=12)
        for dx in (-0.11, 0.11):
            P.cyl('standoff', 0.004, 0.025, (-0.6 + dx, yd - 0.021, zc), pull, rot=(90, 0, 0), verts=8, bevel=0)
        z -= h
    # middle: two sink doors; right: one door
    for cx, w, hx in ((-0.1495, 0.297, 0.12), (0.1495, 0.297, -0.12), (0.6, 0.596, -0.26)):
        P.box('door', (w - 0.004, 0.019, 0.774), (cx, yd, 0.10 + 0.387), front, bevel=0.0025)
        rod(P, 'pull', (cx + hx, yd - 0.032, 0.62), (cx + hx, yd - 0.032, 0.82), 0.0065, pull, verts=12)
        for dz in (0.65, 0.79):
            P.cyl('standoff', 0.004, 0.025, (cx + hx, yd - 0.021, dz), pull, rot=(90, 0, 0), verts=8, bevel=0)
    # worktop (glued oak) around the sink cut-out, x -0.25..0.25, y -0.21..0.21 (relative to worktop centre)
    oak = lambda k: mat(f'worktop_{k}', lambda n: wood2(n, (164, 120, 80), rings=60.0, rough=0.5, varnish=0.25, seed=20.0 + k))
    yc, zt = yb - 0.31, 0.90
    sx0, sx1, sy0, sy1 = -0.25, 0.25, yc - 0.20, yc + 0.20
    P.box('worktop_l', (0.66, 0.62, 0.04), (-0.58, yc, zt), oak(0), bevel=0.003)
    P.box('worktop_r', (0.66, 0.62, 0.04), (0.58, yc, zt), oak(1), bevel=0.003)
    P.box('worktop_f', (0.50, sy0 - (yc - 0.31), 0.04), (0.0, (yc - 0.31 + sy0) / 2, zt), oak(2), bevel=0.003)
    P.box('worktop_b', (0.50, yc + 0.31 - sy1, 0.04), (0.0, (yc + 0.31 + sy1) / 2, zt), oak(3), bevel=0.003)
    zw = zt + 0.02
    P.box('upstand', (W, 0.012, 0.08), (0, yb - 0.006, zw + 0.04), oak(4), bevel=0.002)
    # sink: rim frame + open bowl (inward normals)
    ss = mat('stainless', lambda n: mat5.metal(n, (188, 190, 194), 0.25, seed=3.0))
    for (sx, sy, cxx, cyy) in ((0.52, 0.03, 0.0, sy0 - 0.005), (0.52, 0.03, 0.0, sy1 + 0.005), (0.03, 0.43, sx0 - 0.005, yc), (0.03, 0.43, sx1 + 0.005, yc)):
        P.box('sink_rim', (sx, sy, 0.004), (cxx, cyy, zw + 0.002), ss, bevel=0.0015)
    bx0, bx1, by0, by1, bz = sx0 + 0.01, sx1 - 0.01, sy0 + 0.01, sy1 - 0.01, zw - 0.18
    v = [(bx0, by0, zw), (bx1, by0, zw), (bx1, by1, zw), (bx0, by1, zw), (bx0, by0, bz), (bx1, by0, bz), (bx1, by1, bz), (bx0, by1, bz)]
    f = [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mk(P, 'sink_bowl', v, f, m=ss, bevel=0.02)
    P.cyl('sink_drain', 0.035, 0.004, (0.0, yc + 0.06, bz + 0.002), 'chrome', verts=24, bevel=0.001)
    P.cyl('sink_drain_hole', 0.024, 0.005, (0.0, yc + 0.06, bz + 0.003), 'rubber_black', verts=24, bevel=0)
    # tap (matte black, gooseneck)
    tx, ty = 0.0, sy1 + 0.035
    P.cyl('tap_base', 0.025, 0.03, (tx, ty, zw + 0.015), pull, verts=24, bevel=0.003)
    P.cyl('tap_column', 0.016, 0.20, (tx, ty, zw + 0.13), pull, verts=20, bevel=0.002)
    P.tube('tap_spout', [(tx, ty, zw + 0.225), (tx, ty - 0.03, zw + 0.30), (tx, ty - 0.12, zw + 0.30), (tx, ty - 0.17, zw + 0.24), (tx, ty - 0.175, zw + 0.20)],
           0.011, pull, resolution=10)
    P.box('tap_lever', (0.012, 0.012, 0.07), (tx + 0.028, ty, zw + 0.12), pull, rot=(0, 25, 0), bevel=0.004)
    # appliances and things on the worktop
    _espresso(P, -0.60, yc + 0.07, zw)
    _grinder(P, -0.32, yc + 0.12, zw)
    _kettle(P, 0.45, yc + 0.10, zw)
    build_mug(P, 'mug_a', (-0.33, yc - 0.15, zw), 200, glaze=(222, 218, 208))
    build_mug(P, 'mug_b', (0.30, yc - 0.12, zw), 40, glaze=(30, 30, 32), coffee=False)
    P.box('soap', (0.06, 0.045, 0.17), (0.29, sy1 + 0.04, zw + 0.085), mat('soap', lambda n: mat5.glass(n, (150, 200, 150), 0.1)), bevel=0.012, segments=3)
    P.cyl('soap_pump', 0.012, 0.04, (0.29, sy1 + 0.04, zw + 0.19), 'plastic_white', verts=12, bevel=0.002)
    P.box('sponge', (0.09, 0.06, 0.03), (0.30, sy1 - 0.02, zw + 0.015), mat('sponge', lambda n: mat5.matte(n, (210, 180, 50), 0.95, 0.1, 0.3, 200.0)), rot=(0, 0, 15), bevel=0.006)
    P.box('board', (0.42, 0.018, 0.30), (0.62, yb - 0.04, zw + 0.15), oak(5), rot=(-10, 0, 3), bevel=0.006, segments=3)
    # tea towel over the top drawer's pull
    tw = mat('towel', _towel_mat)
    soft_box(P, 'towel', (0.24, 0.008, 0.40), (-0.66, yd - 0.04, 0.88 - 0.05 - 0.19), tw, rot=(4, 0, 2), r=0.003, n=(6, 2, 8),
             bulge=(0.0, 0.004, 0.0), wobble=0.008, wscale=12.0, seed=4)
    soft_box(P, 'towel_back', (0.24, 0.008, 0.07), (-0.66, yd - 0.025, 0.88 - 0.05 - 0.02), tw, rot=(-10, 0, 2), r=0.003, n=(6, 2, 3),
             wobble=0.004, wscale=12.0, seed=5)
    # wall shelf with brackets, jars, plates, coffee bag, hanging mugs
    zs = 1.50
    shelf_y = yb - 0.11
    P.box('wall_shelf', (1.2, 0.22, 0.03), (-0.1, shelf_y, zs + 0.015), oak(6), bevel=0.003)
    for bx in (-0.55, 0.35):
        P.profile('bracket', [(0.0, 0.0), (0.0, -0.004), (-0.004, -0.004), (-0.004, -0.18), (-0.0, -0.18), (0.0, -0.004)], 0.03,
                  (bx, yb, zs), 'steel_black', rot=(0, 0, 90), bevel=0.0)
        P.box('bracket_arm', (0.03, 0.19, 0.004), (bx, yb - 0.095, zs - 0.002), 'steel_black', bevel=0.0008)
        rod(P, 'bracket_brace', (bx, yb - 0.004, zs - 0.15), (bx, yb - 0.15, zs - 0.004), 0.004, 'steel_black', verts=8)
    zj = zs + 0.03
    for k, (c, r, h) in enumerate((('beans', 0.045, 0.16), ('pasta', 0.045, 0.20), ('sugar', 0.04, 0.12), ('tea', 0.035, 0.11), ('beans', 0.035, 0.09))):
        jar(P, f'kjar{k}', (-0.62 + k * 0.105, shelf_y + 0.02, zj), r, h, c, lid='cork' if k % 2 == 0 else 'metal', fill=0.55 + 0.08 * k)
    for k in range(4):
        lathe(P, 'plate', [(0.0, 0.0), (0.07, 0.0), (0.12, 0.018), (0.122, 0.022), (0.118, 0.022), (0.068, 0.006), (0.0, 0.006)],
              (0.06, shelf_y, zj + 0.012 + k * 0.0145), mat('cup_white', lambda n: mat5.ceramic(n, (232, 230, 224), 0.15)), segs=40)
    bag = mat('kraft', lambda n: mat5.matte(n, (160, 120, 80), 0.85, 0.12, 0.2, 20.0))
    soft_box(P, 'coffee_bag', (0.11, 0.07, 0.20), (0.27, shelf_y + 0.01, zj + 0.10), bag, rot=(0, 0, -10), r=0.01, n=(4, 3, 5),
             bulge=(0.006, 0.012, 0.0), taper=0.25, wobble=0.004, seed=6)
    _front_label(P, 'bag_label', 'CAFÉ', (0.07, 0.022), (0.27 - 0.006, shelf_y + 0.01 - 0.048, zj + 0.10))
    zp = zj + 0.004
    pp = mat('pot_white', lambda n: mat5.ceramic(n, (226, 222, 212), 0.25))
    zz = pot(P, 'shelf_pot', 0.045, 0.07, pp, (0.42, shelf_y, zj))
    _echeveria(P, 'shelf_succulent', (0.42, shelf_y, zz), rnd, r=0.045, n=22, rgb=(110, 140, 120))
    for k, hx in enumerate((-0.35, -0.22, -0.09)):
        P.tube('cup_hook', [(hx, shelf_y - 0.06, zs), (hx, shelf_y - 0.06, zs - 0.03), (hx, shelf_y - 0.075, zs - 0.035), (hx, shelf_y - 0.085, zs - 0.026)],
               0.0018, 'brass', resolution=4)
        g = build_mug(P, f'hang_mug{k}', (hx, shelf_y - 0.085 - 0.06, zs - 0.03 - 0.115), 90, glaze=((40, 60, 80), (196, 120, 70), (220, 216, 206))[k], coffee=False)
        g.root.rotation_euler = (0.0, math.radians(-8), math.radians(-90))
    if fridge:
        _fridge(P, W / 2 + 0.02)
    return P


# ================================================================== LIVING ZONE (composite, world coordinates)
def living_zone(collection=None):
    """Sofa, coffee table, rug, floor lamp and the big plant placed as in SPEC (world coordinates of the loft):
    sofa centred (1.5, -2.3) facing +Y, table at (1.5, -1.3), rug under both, lamp at the sofa's right end (the
    sitter's right, +X), the monstera at the left end near the front wall."""
    Z = kit5.Prop('living_zone', collection)
    rug = build_rug(Z.col)
    Z.add(rug, (1.5, -1.75, 0.0), 0)
    sofa = build_sofa(Z.col)
    Z.add(sofa, (1.5, -2.35, 0.0), 180)
    table = build_coffee_table(Z.col)
    Z.add(table, (1.5, -1.30, 0.0), 180)
    lamp = build_floor_lamp(Z.col)
    Z.add(lamp, (2.95, -2.55, 0.0), 180)
    plant = build_plant_big(Z.col)
    Z.add(plant, (0.05, -3.35, 0.0), 0)
    Z.items = {'rug': rug, 'sofa': sofa, 'coffee_table': table, 'floor_lamp': lamp, 'plant_big': plant}
    return Z
