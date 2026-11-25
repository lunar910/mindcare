"""Real facial expressions on a Meshy character (which comes without any face rig).   import facemorph

    keys = facemorph.build(mesh, arm, name)      needs out_face2/NAME_landmarks.json and NAME_pos.npy (see faceprep.py)

From the 478 face landmarks placed on the model, this:
  1. welds and refines the mesh of the face (the generated mesh is far too coarse there),
  2. cuts the lips apart along the mouth line and adds the inside of the mouth and two rows of teeth,
  3. creates shape keys: eyebrows (up / down / sad, each side), eyes (wide / squint / closed, each side), mouth (smile,
     frown, narrow, wide, each side where it makes sense) and the jaw (a rotation about the jaw hinge).
Eyes and brows are painted on the texture, so moving the surface moves them: a closed eye is the painted eye squeezed
into a line.  All keys are ordinary Blender shape keys: values between 0 and 1, they can be mixed and animated."""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE + '/out_face2'
OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132,
        93, 234, 127, 162, 21, 54, 103, 67, 109]
BROW = {'R': [70, 63, 105, 66, 107], 'L': [300, 293, 334, 296, 336]}          # outer -> inner
BROW_LOW = {'R': [46, 53, 52, 65, 55], 'L': [276, 283, 282, 295, 285]}        # lower edge of the eyebrows
EYE_UP = {'R': [160, 159, 158], 'L': [385, 386, 387]}
EYE_LO = {'R': [144, 145, 153], 'L': [373, 374, 380]}
EYE_CORN = {'R': [33, 133], 'L': [263, 362]}                                    # outer, inner
IRIS = {'R': 468, 'L': 473}
CORNER = {'R': 61, 'L': 291}
CHEEK = {'R': 205, 'L': 425}
EYE_RING = {'R': [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],        # outline of the eye opening
            'L': [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]}


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Face:
    """Landmarks, sizes and the 'is this vertex part of the face skin' test."""

    def __init__(self, name):
        d = json.load(open(f'{OUT}/{name}_landmarks.json'))
        self.L = np.array(d['points'])
        self.meta = d['meta']
        self.pos = np.load(f'{OUT}/{name}_pos.npy')
        self.mask = np.load(f'{OUT}/{name}_mask.npy')
        L = self.L
        self.io = float(np.linalg.norm(L[468] - L[473]))                        # distance between the eyes: the unit of all sizes
        self.mouth_w = float(abs(L[291][0] - L[61][0]))
        self.xm = float((L[291][0] + L[61][0]) / 2)
        self.seam_mid = (L[13] + L[14]) / 2
        self.oval = L[OVAL][:, [0, 2]]
        self.oval_c = self.oval.mean(0)

    def front_depth(self, V):
        """Depth (y) of the visible surface in front of each vertex, from the front picture."""
        m = self.meta
        px = np.clip(((V[:, 0] - m['centre'][0]) / m['scale'] * m['size'] + m['size'] / 2).round().astype(int), 0, m['size'] - 1)
        py = np.clip((m['size'] / 2 - (V[:, 2] - m['centre'][2]) / m['scale'] * m['size']).round().astype(int), 0, m['size'] - 1)
        y = self.pos[py, px, 1]
        return np.where(self.mask[py, px], y, -1e9)

    def skin(self, V, margin=0.0):
        """0..1: inside the face outline (grown by margin x eye distance) and close to the visible front surface."""
        p = V[:, [0, 2]]
        c = self.oval_c
        q = c + (p - c) / (1.0 + margin)                                       # test a shrunk point = grow the outline
        inside = np.zeros(len(q), bool)                                        # even-odd ray casting
        poly = self.oval
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            cond = (a[1] > q[:, 1]) != (b[1] > q[:, 1])
            xi = (b[0] - a[0]) * (q[:, 1] - a[1]) / (b[1] - a[1] + 1e-12) + a[0]
            inside ^= cond & (q[:, 0] < xi)
        depth = V[:, 1] - self.front_depth(V)
        return inside * (1.0 - _smooth(depth, 0.02, 0.045))


def _weld_and_refine(bm, Mw, face, cuts=2):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    for _ in range(cuts):
        bm.verts.ensure_lookup_table()
        V = np.array([tuple(Mw @ v.co) for v in bm.verts])
        inr = face.skin(V, margin=0.25) > 0.5
        edges = [e for e in bm.edges if inr[e.verts[0].index] and inr[e.verts[1].index]]
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True, smooth=0.0)
        bm.verts.index_update()
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.verts.index_update()
    bm.normal_update()


def _cut_mouth(bm, Mw, face, head_group):
    """Split the lips along the mouth line; add mouth interior and teeth.  Returns dict of vertex index lists + anchors."""
    L = face.L
    Minv = Mw.inverted()
    cR, cL, mid = Vector(L[61]), Vector(L[291]), Vector(face.seam_mid)
    n = (cL - cR).cross(mid - cR)
    if n.z < 0:
        n = -n
    n.normalize()                                                          # points up: above the plane = upper lip
    co_l = Minv @ cR
    no_l = (Minv.to_3x3().inverted().transposed() @ n).normalized()
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    V = np.array([tuple(Mw @ v.co) for v in bm.verts])
    skin = face.skin(V, margin=0.1)
    hw = face.mouth_w / 2
    near = (np.abs(V[:, 0] - face.xm) < hw * 1.15) & (np.abs((V - np.array(cR)) @ np.array(n)) < 0.30 * face.io) & (skin > 0.5)
    faces = [f for f in bm.faces if all(near[v.index] for v in f.verts)]
    geom = set(faces)
    for f in faces:
        geom.update(f.edges)
        geom.update(f.verts)
    res = bmesh.ops.bisect_plane(bm, geom=list(geom), dist=1e-5, plane_co=co_l, plane_no=no_l, clear_inner=False, clear_outer=False)
    cut = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
    inner = 0.93 * hw
    cut = [e for e in cut if all(abs((Mw @ v.co).x - face.xm) < inner for v in e.verts)]
    seam_pos = sorted({tuple(round(c, 5) for c in (Mw @ v.co)) for e in cut for v in e.verts})
    bmesh.ops.split_edges(bm, edges=cut)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    # which copies belong to the upper lip, which to the lower
    upper, lower = {}, {}
    seam_set = set(seam_pos)
    for v in bm.verts:
        w = Mw @ v.co
        key = tuple(round(c, 5) for c in w)
        if key not in seam_set or not v.link_faces:
            continue
        side = sum(((Mw @ f.calc_center_median()) - cR).dot(n) for f in v.link_faces) / len(v.link_faces)
        (upper if side > 0 else lower).setdefault(key, v)
    keys = sorted(set(upper) & set(lower), key=lambda k: k[0])
    if len(keys) < 4:
        raise RuntimeError(f'mouth cut failed: only {len(keys)} seam points')
    up = [upper[k] for k in keys]
    lo = [lower[k] for k in keys]
    dl = bm.verts.layers.deform.verify()
    # NB: element references are kept until the end; indices are only valid once nothing is created any more
    # (bmesh re-uses freed slots, so a new vertex can take an index in the middle and shift all the others)
    info = dict(bag_u=[], bag_l=[], teeth_u=[], teeth_l=[], anchors={})
    depth = 0.42 * face.io
    back = Vector((0, 1, 0))

    def new_vert(world, anchor_vert, kind):
        nv = bm.verts.new(Minv @ world)
        nv[dl][head_group] = 1.0
        info[kind].append(nv)
        info['anchors'][nv] = (anchor_vert, kind)
        return nv
    ub = [new_vert((Mw @ v.co) + back * depth + n * 0.10 * face.io, v, 'bag_u') for v in up]
    lb = [new_vert((Mw @ v.co) + back * depth - n * 0.10 * face.io, v, 'bag_l') for v in lo]
    f_in = []
    for i in range(len(up) - 1):
        f_in.append(bm.faces.new((up[i], up[i + 1], ub[i + 1], ub[i])))                  # roof
        f_in.append(bm.faces.new((lo[i + 1], lo[i], lb[i], lb[i + 1])))                  # floor
        f_in.append(bm.faces.new((ub[i], ub[i + 1], lb[i + 1], lb[i])))                  # back wall
    f_in.append(bm.faces.new((up[0], ub[0], lb[0], lo[0])))
    f_in.append(bm.faces.new((up[-1], lo[-1], lb[-1], ub[-1])))
    # the slit runs one edge further on each side, to a vertex shared by both lips: close those two small triangles
    for end, a, b in ((seam_pos[0], up[0], lo[0]), (seam_pos[-1], lo[-1], up[-1])):
        if end in keys:
            continue
        ev = upper.get(end) or lower.get(end)
        if ev is not None and ev is not a and ev is not b:
            try:
                f_in.append(bm.faces.new((ev, a, b)))
            except ValueError:
                pass
    # teeth: two curved strips just behind the lips, over the middle of the mouth
    f_tu, f_tl = [], []
    xs = [(Mw @ v.co).x for v in up]
    sel = [i for i, x in enumerate(xs) if abs(x - face.xm) < 0.80 * hw]
    th = 0.028 * face.io                                                   # how far the upper teeth show under the lip line
    tu_top = [new_vert((Mw @ up[i].co) + back * 0.05 * face.io + n * 0.06 * face.io, up[i], 'teeth_u') for i in sel]
    tu_bot = [new_vert((Mw @ up[i].co) + back * 0.05 * face.io - n * th, up[i], 'teeth_u') for i in sel]
    tl_top = [new_vert((Mw @ lo[i].co) + back * 0.09 * face.io - n * 0.03 * face.io, lo[i], 'teeth_l') for i in sel]   # lower teeth stay behind the lip
    tl_bot = [new_vert((Mw @ lo[i].co) + back * 0.09 * face.io - n * 0.10 * face.io, lo[i], 'teeth_l') for i in sel]
    for i in range(len(sel) - 1):
        f_tu.append(bm.faces.new((tu_top[i], tu_top[i + 1], tu_bot[i + 1], tu_bot[i])))
        f_tl.append(bm.faces.new((tl_top[i], tl_top[i + 1], tl_bot[i + 1], tl_bot[i])))
    bm.verts.index_update()
    bm.faces.index_update()
    info['upper'] = [v.index for v in up]
    info['lower'] = [v.index for v in lo]
    for k in ('bag_u', 'bag_l', 'teeth_u', 'teeth_l'):
        info[k] = [v.index for v in info[k]]
    info['anchors'] = {nv.index: (av.index, kind) for nv, (av, kind) in info['anchors'].items()}
    info['faces'] = dict(inside=[f.index for f in f_in], teeth=[f.index for f in f_tu + f_tl])
    info['plane'] = (np.array(cR), np.array(n))
    return info


def _flat_material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = 1.0
    b.inputs['Specular IOR Level'].default_value = 0.0
    return m


def _field(V, controls, io):
    """Sum of gaussian-weighted displacements; controls = [(point, disp, sigma in eye distances), ...] (front-view distance)."""
    D = np.zeros_like(V)
    W = np.zeros(len(V))
    for p, d, s in controls:
        r2 = (V[:, 0] - p[0]) ** 2 + (V[:, 2] - p[2]) ** 2
        w = np.exp(-r2 / (2 * (s * io) ** 2))
        D += w[:, None] * np.asarray(d)[None, :]
        W += w
    return D / np.maximum(W, 1.0)[:, None]


def build(mesh, arm, name, refine=2, glasses=False):
    face = Face(name)
    L, io = face.L, face.io
    me = mesh.data
    Mw = mesh.matrix_world.copy()
    head_group = mesh.vertex_groups['Head'].index
    bm = bmesh.new()
    bm.from_mesh(me)
    _weld_and_refine(bm, Mw, face, cuts=refine)
    info = _cut_mouth(bm, Mw, face, head_group)
    n_mat = len(me.materials)
    me.materials.append(_flat_material(name + '_mouth_in', (0.055, 0.012, 0.014)))
    me.materials.append(_flat_material(name + '_teeth', (0.80, 0.78, 0.72)))
    bm.faces.ensure_lookup_table()
    for i in info['faces']['inside']:
        bm.faces[i].material_index = n_mat
        bm.faces[i].smooth = True
    for i in info['faces']['teeth']:
        bm.faces[i].material_index = n_mat + 1
        bm.faces[i].smooth = True
    bm.to_mesh(me)
    bm.free()
    if 'custom_normal' in me.attributes:                                   # imported split normals no longer match the mesh
        me.attributes.remove(me.attributes['custom_normal'])
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    M = np.array(Mw)
    V = co @ M[:3, :3].T + M[:3, 3]                                        # world, rest pose
    A = V.copy()                                                           # where each vertex "is" for the fields
    for vi, (ai, kind) in info['anchors'].items():
        A[vi] = V[ai]
    skin = face.skin(A, margin=0.12)
    special = np.zeros(n, bool)
    special[list(info['anchors'])] = True
    skin[special] = 1.0
    Minv3 = np.linalg.inv(M[:3, :3])
    if me.shape_keys is None:
        mesh.shape_key_add(name='Basis')
    keys = {}

    def add(key, D):
        D = D * skin[:, None]
        sk = mesh.shape_key_add(name=key, from_mix=False)
        new = co + D @ Minv3.T
        sk.data.foreach_set('co', new.ravel())
        sk.value = 0.0
        keys[key] = sk
        return float(np.abs(D).max())

    up, right = np.array([0, 0, 1.0]), np.array([1.0, 0, 0])
    for s, sx in (('R', -1.0), ('L', 1.0)):
        b = L[BROW[s]]
        # with glasses the frame sits right under the eyebrows: the brow moves, what is under its lower edge does not
        low = float(L[BROW_LOW[s]][:, 2].mean())
        att = (_smooth(A[:, 2], low - 0.10 * io, low + 0.01 * io) if glasses else np.ones(len(A)))[:, None]
        add(f'browUp_{s}', att * _field(A, [(b[0], up * 0.10 * io, 0.20), (b[2], up * 0.17 * io, 0.20), (b[4], up * 0.16 * io, 0.20)], io))
        add(f'browDown_{s}', att * _field(A, [(b[0], up * 0.02 * io, 0.18), (b[2], -up * (0.045 if glasses else 0.07) * io, 0.18),
                                              (b[4], -up * (0.09 if glasses else 0.13) * io - right * sx * 0.05 * io, 0.18)], io))
        add(f'browSad_{s}', att * _field(A, [(b[0], -up * 0.05 * io, 0.18), (b[2], up * 0.04 * io, 0.18), (b[4], up * 0.15 * io, 0.18)], io))
        eu, el, ec = L[EYE_UP[s]], L[EYE_LO[s]], L[EYE_CORN[s]]
        ce = (ec[0] + ec[1]) / 2
        eh = max(float(np.linalg.norm(eu[1] - el[1])), 0.12 * io)             # eye opening
        ew = abs(ec[0][0] - ec[1][0])
        r2 = ((A[:, 0] - ce[0]) / (0.62 * ew)) ** 2 + ((A[:, 2] - ce[2]) / (0.95 * eh)) ** 2
        line_z = ce[2] - 0.12 * eh
        if glasses:
            # behind glasses the eye is painted on the lens: stretch or squeeze it inside the lens, never move the frame
            w = 1.0 - _smooth(r2, 0.45, 1.05)
            for key, k in ((f'eyeWide_{s}', 0.20), (f'eyeSquint_{s}', -0.40)):
                D = np.zeros_like(A)
                D[:, 2] = (A[:, 2] - line_z) * k * w
                add(key, D)
        else:
            add(f'eyeWide_{s}', _field(A, [(p, up * 0.30 * eh, 0.13) for p in eu] + [(p, -up * 0.12 * eh, 0.13) for p in el], io))
            add(f'eyeSquint_{s}', _field(A, [(p, -up * 0.30 * eh, 0.13) for p in eu] + [(p, up * 0.22 * eh, 0.13) for p in el], io))
            w = 1.0 - _smooth(r2, 0.55, 1.6)
        # closed: everything between the lids goes to the lid line (a little under the middle of the eye)
        D = np.zeros_like(A)
        D[:, 2] = (line_z - A[:, 2]) * 0.92 * w
        add(f'eyeClosed_{s}', D)
        # gaze: the painted iris slides inside the eye opening; the lids (the outline) do not move
        ring = L[EYE_RING[s]][:, [0, 2]]
        q = A[:, [0, 2]]
        ins = np.zeros(len(q), bool)
        dist = np.full(len(q), 1e9)
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            cond = (a[1] > q[:, 1]) != (b[1] > q[:, 1])
            xi = (b[0] - a[0]) * (q[:, 1] - a[1]) / (b[1] - a[1] + 1e-12) + a[0]
            ins ^= cond & (q[:, 0] < xi)
            ab = b - a
            tt = np.clip(((q - a) @ ab) / (ab @ ab + 1e-12), 0, 1)
            dist = np.minimum(dist, np.linalg.norm(q - (a + tt[:, None] * ab), axis=1))
        wg = np.where(ins, _smooth(dist, 0.0, 0.42 * eh), 0.0)[:, None]
        add(f'eyeLookLeft_{s}', wg * right * (0.24 * ew))                      # towards the character's own left (+x)
        add(f'eyeLookRight_{s}', wg * right * (-0.24 * ew))
        add(f'eyeLookUp_{s}', wg * up * (0.30 * eh))
        add(f'eyeLookDown_{s}', wg * up * (-0.34 * eh))
        c, ch = L[CORNER[s]], L[CHEEK[s]]
        add(f'smile_{s}', _field(A, [(c, up * 0.13 * io + right * sx * 0.08 * io + np.array([0, 0.03 * io, 0]), 0.17),
                                     (ch, up * 0.06 * io, 0.24)], io))
        add(f'frown_{s}', _field(A, [(c, -up * 0.11 * io - right * sx * 0.02 * io, 0.16)], io))
    cR, cL = L[61], L[291]
    add('mouthNarrow', _field(A, [(cR, right * 0.14 * io, 0.15), (cL, -right * 0.14 * io, 0.15),
                                  (L[0], np.array([0, -0.04 * io, 0]), 0.14), (L[17], np.array([0, -0.04 * io, 0]), 0.14)], io))
    add('mouthWide', _field(A, [(cR, -right * 0.10 * io, 0.15), (cL, right * 0.10 * io, 0.15)], io))
    add('lipsUp', _field(A, [(L[0], up * 0.07 * io, 0.16)], io) * 1.0)       # upper lip lifted (shows the teeth)
    # jaw: rotation about the hinge (in front of the ears), for everything under the mouth line
    p0, pn = info['plane']
    sdist = (A - p0) @ pn
    # which side of the mouth line a vertex belongs to is read from the faces it is part of: after the cut every face
    # near the mouth is entirely above or entirely below the line, and the vertices on the line exist once per lip
    npoly = len(me.polygons)
    pcen = np.empty(npoly * 3)
    me.polygons.foreach_get('center', pcen)
    pcen = pcen.reshape(npoly, 3) @ M[:3, :3].T + M[:3, 3]
    pmat = np.empty(npoly, dtype=np.int32)
    me.polygons.foreach_get('material_index', pmat)
    ltot = np.empty(npoly, dtype=np.int32)
    me.polygons.foreach_get('loop_total', ltot)
    lvert = np.empty(len(me.loops), dtype=np.int32)
    me.loops.foreach_get('vertex_index', lvert)
    lpoly = np.repeat(np.arange(npoly), ltot)
    keep = pmat[lpoly] < n_mat                                              # skin faces only (not the mouth interior)
    psd = (pcen - p0) @ pn
    smin = np.full(n, 1e9)
    smax = np.full(n, -1e9)
    np.minimum.at(smin, lvert[keep], psd[lpoly[keep]])
    np.maximum.at(smax, lvert[keep], psd[lpoly[keep]])
    # Beyond the corners of the mouth nothing is cut: there the cheek has to stretch between the fixed upper face and
    # the moving jaw, so the change-over across the mouth line gets wider and wider (a narrow one makes a crease).
    hw = face.mouth_w * 0.5
    latd = np.maximum(0.0, np.abs(A[:, 0] - face.xm) - 0.85 * hw)
    wd = 0.004 + 1.1 * latd
    ramp = _smooth(-sdist, -wd, wd)
    hard = ramp.copy()
    cutzone = (np.abs(A[:, 0] - face.xm) < hw * 1.12) & (np.abs(sdist) < 0.28 * io)
    hard[cutzone & (smax <= 1e-5)] = 1.0                                    # all its faces are under the line: lower lip
    hard[cutzone & (smin >= -1e-5)] = 0.0                                   # all above: upper lip
    hard[info['lower']] = 1.0
    hard[info['upper']] = 0.0
    u = _smooth(np.abs(A[:, 0] - face.xm), 0.78 * hw, 1.10 * hw)            # 0 between the lips, 1 past the corners
    below = (1 - u) * hard + u * ramp
    for vi, (ai, kind) in info['anchors'].items():
        below[vi] = 1.0 if kind in ('bag_l', 'teeth_l') else 0.0
    xj = max(abs(L[172][0] - face.xm), abs(L[397][0] - face.xm))
    lat = 1.0 - _smooth(np.abs(A[:, 0] - face.xm) / xj, 0.70, 1.05)
    chin = L[152]
    neck = _smooth(A[:, 2], chin[2] - 0.55 * io, chin[2] - 0.12 * io)
    hinge = (L[234] + L[454]) / 2
    hinge = np.array([face.xm, max(hinge[1], chin[1] + 0.6 * io), hinge[2] - 0.05 * io])
    dcorner = np.minimum(np.linalg.norm(A[:, [0, 2]] - cR[[0, 2]], axis=1), np.linalg.norm(A[:, [0, 2]] - cL[[0, 2]], axis=1))
    wj = below * lat * neck * (1.0 - 0.75 * np.exp(-(dcorner / (0.10 * io)) ** 2))
    th = math.radians(15.0)
    Rx = np.array([[1, 0, 0], [0, math.cos(th), -math.sin(th)], [0, math.sin(th), math.cos(th)]])   # chin goes down and back
    rel = V - hinge
    add('jawOpen', (rel @ Rx.T - rel) * wj[:, None])
    me.update()
    return keys, info, face


EXPR = {  # ready-made faces: {shape key (without side): value}; '_L' / '_R' are filled for both sides unless given
    'neutral': {},
    'surprised': {'browUp': 0.9, 'eyeWide': 0.9, 'jawOpen': 0.35},
    'angry': {'browDown': 0.95, 'eyeSquint': 0.35, 'frown': 0.5},
    'annoyed': {'browDown': 0.6, 'eyeSquint': 0.5, 'frown': 0.3},
    'sad': {'browSad': 0.9, 'frown': 0.6},
    'happy': {'smile': 0.85, 'eyeSquint': 0.25, 'browUp': 0.15},
    'smug': {'smile_L': 0.7, 'smile_R': 0.15, 'eyeSquint': 0.3, 'browUp_L': 0.5},
    'doubt': {'browUp_L': 0.85, 'browDown_R': 0.6, 'eyeSquint_R': 0.3, 'frown': 0.2},
    'pout': {'browDown': 0.45, 'frown': 0.7, 'mouthNarrow': 0.5},
}


def expand(expr):
    """{'browUp': .5, 'smile_L': 1} -> per-side shape key values."""
    out = {}
    for k, v in expr.items():
        if k.endswith(('_L', '_R')) or k in ('jawOpen', 'mouthNarrow', 'mouthWide', 'lipsUp', 'lipLowerDown', 'lipUpperUp', 'lipsPress', 'tongueUp', 'tongueOut'):
            out[k] = v
        else:
            out.setdefault(k + '_L', v)
            out.setdefault(k + '_R', v)
    return out


def apply(mesh, values):
    kb = mesh.data.shape_keys.key_blocks
    for k in kb:
        if k.name != 'Basis':
            k.value = float(min(max(values.get(k.name, 0.0), 0.0), 1.0))
