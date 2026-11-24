"""Version 6 faces: the heads rebuilt from separate parts (what a game character has, and the generated models lack).

    R = face6.build(mesh, arm, name, glasses=False)

Before: one fused skin with the eyes painted on it (on the lenses for Nox) and a slit for a mouth; every expression
stretched that skin, so the whole face deformed when a character spoke.
Now:
  - the skull, nose, cheeks and forehead never move;
  - real eyeballs sit behind eye openings cut in the skin (eyes6.py); the iris slides, the lids are separate shells that
    turn over the eyeball (a blink does not stretch anything);
  - real teeth and a tongue (teeth6.py): the upper teeth are fixed to the skull, the lower ones and the tongue turn with
    the jaw, about the jaw hinge in front of the ears;
  - the lips are a clean patch of regular mesh around the mouth line, with thickness, and their own small shape keys;
  - Nox's glasses block (frame, lenses and the eyes painted on them) is erased from his skin: the mesh is faired where
    it was, the skin colour is filled in, and real glasses with transparent lenses are put on (glasses6.py).

Everything is found from the front view of the head (face6prep.py) and the 478 face landmarks (faceprep.py)."""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from scipy import ndimage as ndi
from scipy import sparse
from scipy.sparse.linalg import splu

import f6img

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE + '/out_face6'
FRONT = np.array([0.0, -1.0, 0.0])


def _smooth(x, a, b):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------------------------------ mesh <-> numpy

def bm_world(bm, Mw):
    M = np.array(Mw)
    co = np.array([v.co[:] for v in bm.verts])
    return co @ M[:3, :3].T + M[:3, 3]


def set_world(bm, Mw, idx, W):
    Minv = np.array(Mw.inverted())
    loc = W @ Minv[:3, :3].T + Minv[:3, 3]
    bm.verts.ensure_lookup_table()
    for i, p in zip(idx, loc):
        bm.verts[i].co = p


def texture_colours(bm, image):
    """Colour of the model's own texture at every vertex (sRGB, one of its UV corners)."""
    w, h = image.size
    px = np.empty(w * h * 4, np.float32)
    image.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)[..., :3]
    uvl = bm.loops.layers.uv.active
    out = np.zeros((len(bm.verts), 3), np.float32)
    for v in bm.verts:
        if v.link_loops:
            u = v.link_loops[0][uvl].uv
            out[v.index] = px[int(np.clip(u.y * h, 0, h - 1)), int(np.clip(u.x * w, 0, w - 1))]
    return out


def adjacency(bm):
    n = len(bm.verts)
    a = np.array([(e.verts[0].index, e.verts[1].index) for e in bm.edges])
    A = sparse.coo_matrix((np.ones(len(a) * 2), (np.r_[a[:, 0], a[:, 1]], np.r_[a[:, 1], a[:, 0]])), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    return A


def fair(A, W, unknown, order=2, values=None):
    """Positions of the `unknown` vertices that make the surface as smooth as possible given all the others
    (order 1: membrane, each vertex the mean of its neighbours; order 2: thin plate, keeps the slope at the border).
    `values`: fair these per-vertex values instead of the positions (colours)."""
    n = A.shape[0]
    X = (W if values is None else values).astype(np.float64).copy()
    deg = np.asarray(A.sum(1)).ravel()
    Lm = sparse.diags(1.0 / np.maximum(deg, 1)) @ A - sparse.identity(n)       # umbrella operator
    U = np.nonzero(unknown)[0]
    if order == 1:
        rows = U
        M = Lm[rows]
    else:
        near = np.asarray((A @ unknown.astype(float))).ravel() > 0
        rows = np.nonzero(unknown | near)[0]
        M = Lm[rows]
    known = np.ones(n, bool)
    known[U] = False
    K = np.nonzero(known)[0]
    Au = M[:, U].tocsc()
    b = -(M[:, K] @ X[K])
    lhs = (Au.T @ Au).tocsc()
    lu = splu(lhs)
    X[U] = np.column_stack([lu.solve(Au.T @ b[:, c]) for c in range(X.shape[1])])
    return X


# ------------------------------------------------------------------------------------------------ Nox's glasses block

def erase_glasses(bm, Mw, F, tex_col, grow_mm=3.0):
    """Flatten the fused glasses (frame, lenses, arms along the temples) into the skin.  Returns per-vertex arrays:
    `gl` (was part of the glasses), `front` (seen from the front: gets the repainted front picture), `fill` (colour to
    use elsewhere: skin/hair colours diffused from around)."""
    G = np.load(f'{OUT}/{F.name}_G.npy')
    Gd = ndi.binary_dilation(G, iterations=int(grow_mm * 1e-3 * F.ppm))
    V = bm_world(bm, Mw)
    n = len(V)
    p = F.px(V)
    xi = np.clip(p[:, 0].round().astype(int), 0, F.S - 1)
    yi = np.clip(p[:, 1].round().astype(int), 0, F.S - 1)
    inimg = (p[:, 0] >= 0) & (p[:, 0] < F.S) & (p[:, 1] >= 0) & (p[:, 1] < F.S)
    yvis = np.where(F.mask[yi, xi], F.pos[yi, xi, 1], 1e9)
    hair_px = ndi.binary_dilation(F.hair_like(), iterations=2)
    visible = inimg & (np.abs(V[:, 1] - yvis) < 0.002)
    gl = inimg & Gd[yi, xi] & (V[:, 1] < yvis + 0.012) & ~(visible & hair_px[yi, xi])
    # the arms: grey vertices connected to the frame, along the temples (not seen from the front)
    A = adjacency(bm)
    hue, sat, val = f6img.hsv(tex_col)
    # frame and lens texels are grey or pale and unsaturated (the skin is more saturated and redder)
    grey = (val > 0.22) & (hue < 0.45) & ((sat < 0.17) | ((hue > 0.095) & (sat < 0.26)))
    L = F.L
    zlo, zhi = V[gl, 2].min() - 0.006, V[gl, 2].max() + 0.006
    ear_y = max(L[234][1], L[454][1]) + 0.03
    x_out = abs(L[33][0] - L[168][0])                                 # the arms start beyond the outer corners of the eyes
    cand = grey & (V[:, 2] > zlo) & (V[:, 2] < zhi) & (V[:, 1] < ear_y) & (np.abs(V[:, 0] - L[168][0]) > x_out)
    arms = np.zeros(n, bool)
    seed = gl.copy()
    for _ in range(45):
        nxt = (np.asarray(A @ (seed | arms).astype(float)).ravel() > 0) & cand & ~gl & ~arms
        if not nxt.any():
            break
        arms |= nxt
    hairv = (hue > 0.50) & (hue < 0.75) & (val < 0.50)                # the model's own hair: dark saturated blue
    skin_set = (gl | arms) & ~hairv
    # the skirt where the block meets the skin: two rings, but never onto a hair lock (their pale highlights are not
    # 'hair-coloured': they are recognised by the hair pixels around them in the front view)
    hair_near = ndi.binary_dilation(F.hair_like(), iterations=int(0.0018 * F.ppm))
    on_lock = inimg & hair_near[yi, xi] & (V[:, 1] < yvis + 0.004)
    skinv = ~hairv & ~on_lock & (V[:, 2] > zlo - 0.006) & (V[:, 2] < zhi + 0.006)
    for _ in range(2):
        skin_set = skin_set | ((np.asarray(A @ skin_set.astype(float)).ravel() > 0) & skinv)
    # Hair tips were fused onto the frame.  Cutting them loose leaves holes on both sides; leaving them where they are
    # pulls the faired skin up into creases.  So the ends of those locks (the part over the glasses) come down with
    # the frame and rest on the skin, keeping their own colour.
    Gh = ndi.binary_dilation(G, iterations=int(0.006 * F.ppm))
    hair_tip = hairv & inimg & Gh[yi, xi] & (V[:, 1] < yvis + 0.012)
    hair_tip |= hairv & (np.asarray(A @ skin_set.astype(float)).ravel() > 0)
    unknown = skin_set | hair_tip
    Wn = fair(A, V, unknown, order=2)
    set_world(bm, Mw, np.nonzero(unknown)[0], Wn[unknown])
    keep = sparse.diags((~hairv).astype(float))                       # colours: hair never bleeds into the skin
    Af = (keep @ A @ keep).tocsr()
    Af.eliminate_zeros()
    fillable = skin_set & (np.asarray(Af.sum(1)).ravel() > 0)
    fill = fair(Af, None, fillable, order=1, values=tex_col)
    hsel = hairv & ~hair_tip & (val < 0.45) & (V[:, 2] > L[152][2])        # real hair: dark, on the head (not the jacket)
    hair_colour = np.median(tex_col[hsel], 0) if hsel.any() else None
    # the arms along the temples ran over skin, then over hair: where they were, the hairline is continued smoothly
    # (a 0..1 "hair" value diffused from the vertices around), skin colour on one side, hair colour on the other
    side_set = skin_set & ~(gl & visible)
    if side_set.any() and hair_colour is not None:
        lab = fair(A, None, side_set | hair_tip, order=1, values=hairv.astype(np.float64)[:, None])[:, 0]
        wgt = _smooth(lab, 0.35, 0.65)[:, None]
        mixed = fill * (1 - wgt) + hair_colour[None, :] * wgt
        fill[side_set] = mixed[side_set]
    print('  glasses: footprint %d, arms %d, skirt+all %d, hair tips %d, z %.3f..%.3f (frame %.3f..%.3f)' % (gl.sum(), arms.sum(), skin_set.sum(), hair_tip.sum(), V[skin_set, 2].min(), V[skin_set, 2].max(), zlo, zhi))
    return dict(gl=skin_set, arms=arms, front=gl & visible & ~hairv, fill=np.clip(fill, 0, 1), V=Wn, hairv=hairv, hair_tip=hair_tip, hair_colour=hair_colour)


# ------------------------------------------------------------------------------------------------ clean patches

class Surface:
    """The head as it is now, for depth queries along the front direction."""

    def __init__(self, bm, Mw):
        bm.verts.index_update()
        V = bm_world(bm, Mw)
        bm.faces.ensure_lookup_table()
        self.bvh = BVHTree.FromPolygons([tuple(p) for p in V], [[v.index for v in f.verts] for f in bm.faces])

    def depth(self, x, z, default=None):
        hit = self.bvh.ray_cast(Vector((x, -5.0, z)), Vector((0, 1, 0)))
        if hit[0] is None:
            return default
        return hit[0].y

    def depths(self, pts):
        out = np.empty(len(pts))
        for i, (x, z) in enumerate(pts):
            d = self.depth(float(x), float(z))
            out[i] = np.nan if d is None else d
        if np.isnan(out).any():
            good = ~np.isnan(out)
            out[~good] = out[good].mean() if good.any() else 0.0
        return out


def closed_spline(P, n):
    """n points evenly spaced along a smooth closed curve through the 2D points P (periodic Catmull-Rom)."""
    P = np.asarray(P, float)
    m = len(P)
    dense = []
    for i in range(m):
        p0, p1, p2, p3 = P[i - 1], P[i], P[(i + 1) % m], P[(i + 2) % m]
        for t in np.linspace(0, 1, 12, endpoint=False):
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    dense = np.array(dense)
    seg = np.linalg.norm(np.roll(dense, -1, 0) - dense, axis=1)
    s = np.r_[0, np.cumsum(seg)]
    u = np.linspace(0, s[-1], n, endpoint=False)
    d2 = np.vstack([dense, dense[:1]])
    return np.column_stack([np.interp(u, s, d2[:, 0]), np.interp(u, s, d2[:, 1])])


def poly_area(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def offset_closed(P, d):
    """Offset a closed 2D polygon outwards by d (d may be an array, one value per point)."""
    P = np.asarray(P, float)
    t = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    nrm = np.column_stack([t[:, 1], -t[:, 0]])
    if poly_area(P) < 0:
        nrm = -nrm
    return P + nrm * np.asarray(d, float).reshape(-1, 1) if np.ndim(d) else P + nrm * d


def inside_poly(pts, poly):
    pts = np.asarray(pts, float)
    ins = np.zeros(len(pts), bool)
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        cond = (a[1] > pts[:, 1]) != (b[1] > pts[:, 1])
        xi = (b[0] - a[0]) * (pts[:, 1] - a[1]) / (b[1] - a[1] + 1e-15) + a[0]
        ins ^= cond & (pts[:, 0] < xi)
    return ins


def dist_to_closed(pts, poly):
    """Distance of 2D points to a closed polyline, and the parameter (index + fraction) of the nearest point."""
    pts = np.asarray(pts, float)
    best = np.full(len(pts), 1e9)
    par = np.zeros(len(pts))
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ab = b - a
        t = np.clip(((pts - a) @ ab) / (ab @ ab + 1e-15), 0, 1)
        d = np.linalg.norm(pts - (a + t[:, None] * ab), axis=1)
        m = d < best
        best[m] = d[m]
        par[m] = i + t[m]
    return best, par


def convex_hull(P):
    P = sorted(map(tuple, P))
    def half(pts):
        h = []
        for p in pts:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h
    lo, up = half(P), half(P[::-1])
    return np.array(lo[:-1] + up[:-1])


def cut_region(bm, Mw, poly, surf, layer=0.008, keep=None):
    """Cut the skin along a convex polygon of the front view and remove what is inside it (front layer only).
    Returns the closed loop of boundary vertices left around the hole (BMVerts, counter-clockwise in the x-z plane)."""
    from mathutils import Vector as Vx
    Minv = Mw.inverted()
    N3 = Minv.to_3x3().inverted().transposed()
    poly = np.asarray(poly, float)
    if poly_area(poly) < 0:
        poly = poly[::-1]
    lo, hi = poly.min(0) - 0.004, poly.max(0) + 0.004

    def near_faces():
        out = []
        for f in bm.faces:
            c = Mw @ f.calc_center_median()
            if lo[0] < c.x < hi[0] and lo[1] < c.z < hi[1]:
                ys = surf.depth(c.x, c.z)
                if ys is not None and c.y < ys + 0.03:
                    out.append(f)
        return out
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        nrm = Vx((-(b[1] - a[1]), 0.0, (b[0] - a[0])))           # points to the inside for a counter-clockwise polygon
        faces = near_faces()
        geom = set(faces)
        for f in faces:
            geom.update(f.edges)
            geom.update(f.verts)
        bmesh.ops.bisect_plane(bm, geom=list(geom), dist=1e-6, plane_co=Minv @ Vx((a[0], 0.0, a[1])), plane_no=(N3 @ nrm).normalized(),
                               clear_inner=False, clear_outer=False)
    kill = []
    for f in near_faces():
        c = Mw @ f.calc_center_median()
        if inside_poly(np.array([[c.x, c.z]]), poly)[0]:
            ys = surf.depth(c.x, c.z)
            if ys is not None and abs(c.y - ys) < layer and not (keep is not None and keep(c.x, c.z)):
                kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    be = [e for e in bm.edges if e.is_boundary]
    be = [e for e in be if all(lo[0] - 0.002 < (Mw @ v.co).x < hi[0] + 0.002 and lo[1] - 0.002 < (Mw @ v.co).z < hi[1] + 0.002 for v in e.verts)]
    nxt = {}
    for e in be:
        for v in e.verts:
            nxt.setdefault(v, []).append(e)
    left = set(be)
    loops = []
    while left:
        e = left.pop()
        v0, v = e.verts
        loop = [v0, v]
        while v is not v0:
            cand = [x for x in nxt[v] if x in left]
            if not cand:
                break
            e = cand[0]
            left.discard(e)
            v = e.other_vert(v)
            loop.append(v)
        if loop[-1] is loop[0] and len(loop) > 3:
            loops.append(loop[:-1])
    if not loops:
        raise RuntimeError('cut_region: no closed boundary found')
    loop = max(loops, key=len)
    for other in loops:
        if other is not loop and len(other) <= 24:
            try:
                bm.faces.new(other)
            except ValueError:
                pass
    P = np.array([[(Mw @ v.co).x, (Mw @ v.co).z] for v in loop])
    if poly_area(P) < 0:
        loop = loop[::-1]
    return loop, len(loops)


def fill_patch(bm, Mw, loop, points, constraints, holes, depth_of, head_group):
    """Triangulate the inside of a boundary loop with the given 2D interior points and constraint polylines
    (lists of indices into `points`; closed=True polylines listed in `holes` are left open).  New vertices get their
    depth from depth_of(xz array).  Returns (list of new BMVerts in the order of `points`, list of new faces)."""
    from mathutils.geometry import delaunay_2d_cdt
    Minv = Mw.inverted()
    dl = bm.verts.layers.deform.verify()
    LP = np.array([[(Mw @ v.co).x, (Mw @ v.co).z] for v in loop])
    nL = len(loop)
    points = np.asarray(points, float)
    allp = np.vstack([LP, points])
    edges = [(i, (i + 1) % nL) for i in range(nL)]
    for idx, closed in constraints:
        idx = [nL + i for i in idx]
        edges += list(zip(idx[:-1], idx[1:]))
        if closed:
            edges.append((idx[-1], idx[0]))
    sc = 1000.0                                                     # CDT in millimetres (its epsilon is absolute)
    res = delaunay_2d_cdt([Vector((p[0] * sc, p[1] * sc)) for p in allp], edges, [], 0, 1e-4, True)
    ov, _, of, orig_v = res[0], res[1], res[2], res[3]
    depth = depth_of(points)
    newv = [None] * len(points)
    out_bv = []
    for k, co in enumerate(ov):
        src = orig_v[k]
        if src and min(src) < nL:
            out_bv.append(loop[min(src)])
            continue
        if src:
            j = min(src) - nL
            w = Vector((points[j][0], depth[j], points[j][1]))
        else:                                                       # a point added by the triangulation (crossing)
            x, z = co.x / sc, co.y / sc
            w = Vector((x, float(depth_of(np.array([[x, z]]))[0]), z))
            j = None
        nv = bm.verts.new(Minv @ w)
        nv[dl][head_group] = 1.0
        if j is not None:
            newv[j] = nv
            for jj in src:
                if jj - nL != j and jj >= nL:
                    newv[jj - nL] = nv
        out_bv.append(nv)
    hole_polys = [points[idx] for idx in holes]
    faces = []
    for tri in of:
        c = np.mean([[ov[i].x / sc, ov[i].y / sc] for i in tri], 0)[None, :]
        if not inside_poly(c, LP)[0] or any(inside_poly(c, h)[0] for h in hole_polys):
            continue
        vs = [out_bv[i] for i in tri]
        if len(set(vs)) < 3:
            continue
        try:
            f = bm.faces.new(vs)
        except ValueError:
            continue
        f.smooth = True
        faces.append(f)
    # all faces must face the front (-Y)
    for f in faces:
        f.normal_update()
        if (Mw.to_3x3() @ f.normal).y > 0:
            f.normal_flip()
    return newv, faces


# ------------------------------------------------------------------------------------------------ eyes

EYE_RING = {'R': [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
            'L': [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]}
IRIS = {'R': 468, 'L': 473}
IRIS_RING = {'R': [469, 470, 471, 472], 'L': [474, 475, 476, 477]}
N_RING = 44
# Nox's eyes were painted on his flat lenses, wider than his face allows: its sides turn back right at their outer corners
EYE_SHRINK = {'noxR': 0.84}
RIM = 1.030                    # the skin around the opening lies on the eyeball surface scaled by this
LID = 1.014                    # the lid shells


class EyeGeo:
    """Where an eye is: the opening outline (front view), the ellipsoid of the eyeball, the surface the lids follow."""

    def __init__(self, F, side, surf, grow=0.0004, recess=0.0010, radius_k=0.72, depth_k=0.60):
        L = F.L
        ring = L[EYE_RING[side]][:, [0, 2]]
        iris_c = L[IRIS[side]][[0, 2]].copy()
        shrink = EYE_SHRINK.get(F.name, 1.0)
        if shrink != 1.0:                                             # narrower eyes, the inner corners stay where they are
            inner = ring[np.argmax(ring[:, 0])] if side == 'R' else ring[np.argmin(ring[:, 0])]
            ring = inner + (ring - inner) * shrink
            iris_c = inner + (iris_c - inner) * shrink
        O = closed_spline(ring, N_RING)
        if poly_area(O) < 0:
            O = O[::-1]
        O = offset_closed(O, grow)
        k = int(np.argmin(O[:, 0]))                                   # start at the corner with the smallest x
        self.O = np.roll(O, -k, 0)
        self.side = side
        self.w = float(np.ptp(O[:, 0]))
        self.h = float(np.ptp(O[:, 1]))
        self.c = np.array([(O[:, 0].min() + O[:, 0].max()) / 2, (O[:, 1].min() + O[:, 1].max()) / 2])
        self.iris_c = iris_c
        self.iris_r = float(np.mean(np.linalg.norm(L[IRIS_RING[side]][:, [0, 2]] - L[IRIS[side]][[0, 2]], axis=1))) * (0.5 + 0.5 * shrink)
        ys = surf.depths(np.vstack([self.c, self.O[::4]]))
        self.y0 = float(np.median(ys))
        self.R = radius_k * self.w
        self.D = depth_k * self.R
        self.cy = self.y0 + recess + self.D
        self.centre = np.array([self.c[0], self.cy, self.c[1]])

    def fit(self, surf, margin, radius_ks=(0.72, 0.68, 0.64, 0.60), recesses=(0.0010, 0.0018, 0.0026, 0.0034, 0.0042, 0.0050), depth_k=0.60):
        """Size and depth of the eyeball: as large and as little sunk as possible while the skin around the eye patch
        stays in front of it (what little is left behind is pushed onto the eyeball by cut_eye)."""
        ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)
        best = None
        for rk in radius_ks:
            R = rk * self.w
            rad = np.linspace(0.3, 1.0, 10) * R
            xz = np.array([[self.c[0] + r * np.cos(a), self.c[1] + r * np.sin(a)] for r in rad for a in ang])
            d, _ = dist_to_closed(xz, self.O)
            far = (d >= 0.8 * margin) & ~inside_poly(xz, self.O)
            ys = surf.depths(xz[far]) if far.any() else np.zeros(0)
            for rec in recesses:
                self.R, self.D = R, depth_k * R
                self.cy = self.y0 + rec + self.D
                viol = float(np.clip(ys - self.sphere_y(xz[far], RIM), 0.0, None).max()) if far.any() else 0.0
                cost = rec * 1000 + 40.0 * (radius_ks[0] - rk) + 0.6 * viol * 1000
                if best is None or cost < best[0]:
                    best = (cost, rk, rec, viol)
        self.set_fit(best[1], best[2], depth_k)
        return (best[1], best[2], round(best[3] * 1000, 1))

    def set_fit(self, rk, rec, depth_k=0.60):
        self.R = rk * self.w
        self.D = depth_k * self.R
        self.cy = self.y0 + rec + self.D
        self.centre = np.array([self.c[0], self.cy, self.c[1]])
        self.fitted = (rk, rec)

    def sphere_y(self, xz, k=1.0):
        """Depth (y) of the front of the eyeball surface scaled by k, above the points xz."""
        xz = np.asarray(xz, float)
        r2 = ((xz[:, 0] - self.c[0]) ** 2 + (xz[:, 1] - self.c[1]) ** 2) / (k * self.R) ** 2
        return self.cy - k * self.D * np.sqrt(np.clip(1.0 - r2, 0.02, 1.0))

    def unit(self, xz, k=1.0):
        """Points of the front view -> points on the unit sphere of the eye's holder (x, y, z), radius k."""
        xz = np.asarray(xz, float)
        x = (xz[:, 0] - self.c[0]) / self.R
        z = (xz[:, 1] - self.c[1]) / self.R
        y = -np.sqrt(np.clip(k * k - x * x - z * z, 0.0, None))
        return np.column_stack([x, y, z])

    def upper_lower(self, n=41):
        """The opening as two curves z(x): upper rim and lower rim, sampled at n abscissas between the corners."""
        O = self.O
        i1 = int(np.argmax(O[:, 0]))
        a, b = O[:i1 + 1], np.vstack([O[i1:], O[:1]])                 # the two chains between the corners
        xs = np.linspace(O[0, 0], O[i1, 0], n)
        za = np.interp(xs, a[:, 0], a[:, 1])
        zb = np.interp(xs, b[::-1, 0], b[::-1, 1])
        return xs, np.maximum(za, zb), np.minimum(za, zb)


def cut_eye(bm, Mw, F, geo, surf, head_group, margin_k=0.30, uv_override=None):
    """Open the skin over one eye: a clean ring of mesh around the opening, hugging the eyeball, with a lid margin."""
    O = geo.O
    m = margin_k * geo.w
    if not hasattr(geo, 'fitted'):
        geo.fitted = geo.fit(surf, m)
    outer = offset_closed(O, m)
    # on a narrow face the skin turns back steeply just outside the eye: the patch stops where it is 11 mm behind the eye
    ys_o = surf.depths(outer)
    for i in range(len(outer)):
        if ys_o[i] - geo.y0 > 0.011:
            lo_t, hi_t = 0.0, 1.0
            for _ in range(7):
                mid = (lo_t + hi_t) / 2
                q = O[i] + (outer[i] - O[i]) * mid
                d = surf.depth(float(q[0]), float(q[1]))
                if d is None or d - geo.y0 > 0.011:
                    hi_t = mid
                else:
                    lo_t = mid
            outer[i] = O[i] + (outer[i] - O[i]) * max(lo_t, 0.25)
    poly = convex_hull(outer[::2])
    hair = F.raised() & ~F.skin_like()

    def keep(x, z):
        p = F.px(np.array([x, 0.0, z]))
        return bool(hair[int(np.clip(p[1], 0, F.S - 1)), int(np.clip(p[0], 0, F.S - 1))])
    loop, nloops = cut_region(bm, Mw, poly, surf, keep=keep)
    LP = np.array([[(Mw @ v.co).x, (Mw @ v.co).z] for v in loop])
    offs = [0.0, 0.0007, 0.0016, 0.0028, 0.0043, 0.0061, 0.0082]
    offs = [d for d in offs if d < m - 0.0018]
    rings = [offset_closed(O, d) for d in offs]
    pts = np.vstack(rings)
    keep = np.ones(len(pts), bool)
    keep[N_RING:] = inside_poly(pts[N_RING:], LP) & (dist_to_closed(pts[N_RING:], LP)[0] > 0.0012)
    idx_map = np.cumsum(keep) - 1
    pts = pts[keep]
    band = 0.80 * m

    def depth_of(xz):
        d, _ = dist_to_closed(xz, O)
        w = 1.0 - _smooth(d, 0.0, band)
        ys = surf.depths(xz)
        hug = geo.sphere_y(xz, RIM)
        return np.minimum(ys * (1 - w) + hug * w, np.where(d < band, hug, 1e9))     # never behind the eyeball
    newv, faces = fill_patch(bm, Mw, loop, pts, [(list(range(N_RING)), True)], [list(range(N_RING))], depth_of, head_group)
    rim = newv[:N_RING]
    # the lid margin: a strip going from the rim back to the eyeball
    Minv = Mw.inverted()
    dl = bm.verts.layers.deform.verify()
    inner2d = offset_closed(O, -0.0007)
    iy = geo.sphere_y(inner2d, 1.004)
    inner = []
    for j in range(N_RING):
        nv = bm.verts.new(Minv @ Vector((inner2d[j][0], iy[j], inner2d[j][1])))
        nv[dl][head_group] = 1.0
        inner.append(nv)
        if uv_override is not None:
            uv_override[nv] = offset_closed(O, 0.0004)[j]             # coloured like the skin just outside the rim
    for j in range(N_RING):
        a, b = rim[j], rim[(j + 1) % N_RING]
        c, d = inner[(j + 1) % N_RING], inner[j]
        try:
            f = bm.faces.new((b, a, d, c))
            f.smooth = True
            faces.append(f)
        except ValueError:
            pass
    geo.pushed = 0
    return dict(rim=rim, inner=inner, faces=faces, new=[v for v in newv if v is not None] + inner + list(loop), nloops=nloops, margin=m)


# ------------------------------------------------------------------------------------------------ colours

def ensure_layers(bm):
    """Create the custom layers used by write_layers.  Call it right after making the BMesh: creating a layer
    invalidates every vertex reference and layer handle taken before."""
    if bm.loops.layers.uv.get('uvfront') is None:
        bm.loops.layers.uv.new('uvfront')
    for nm in ('fmask', 'amask'):
        if bm.verts.layers.float.get(nm) is None:
            bm.verts.layers.float.new(nm)
    if bm.verts.layers.float_color.get('fillcol') is None:
        bm.verts.layers.float_color.new('fillcol')
    for nm in ('lipside', 'anchor', 'hairflag'):
        if bm.verts.layers.int.get(nm) is None:
            bm.verts.layers.int.new(nm)
    bm.verts.layers.deform.verify()


def mark_erased(bm, Mw, F, R):
    """Right after erase_glasses (before any cut changes the vertex numbering): the erased skin takes the repainted
    front picture where it faces the front and is not under a hair lock, a plain diffused colour elsewhere."""
    fm, am = bm.verts.layers.float['fmask'], bm.verts.layers.float['amask']
    fc = bm.verts.layers.float_color['fillcol']
    hf = bm.verts.layers.int['hairflag']
    bm.verts.ensure_lookup_table()
    for i in np.nonzero(R['hairv'])[0]:
        bm.verts[i][hf] = 1
    bm.normal_update()
    hair = F.raised() & ~F.skin_like()
    hair = ndi.binary_dilation(hair, iterations=3)
    N3 = Mw.to_3x3()
    bm.verts.ensure_lookup_table()
    nf = na = 0
    for i in np.nonzero(R['gl'])[0]:
        v = bm.verts[i]
        w = Mw @ v.co
        p = F.px(np.array([w.x, 0.0, w.z]))
        xi, yi = int(round(p[0])), int(round(p[1]))
        inside = 0 <= xi < F.S and 0 <= yi < F.S and F.mask[yi, xi]
        facing = (N3 @ v.normal).normalized().y < -0.40
        v[hf] = 2                                                      # erased skin (relaxed once more after the cuts)
        if inside and facing and not hair[yi, xi]:
            v[fm] = 1.0
            nf += 1
        else:
            v[am] = 1.0
            c = R['fill'][i]
            v[fc] = (float(c[0]), float(c[1]), float(c[2]), 1.0)
            na += 1
    # the ends of the hair locks that came down with the frame: one plain hair colour (their texels were a mix)
    hc = R.get('hair_colour')
    if hc is not None:
        tips = {bm.verts[i] for i in np.nonzero(R['hair_tip'])[0]}
        ring = {e.other_vert(v) for v in tips for e in v.link_edges if R['hairv'][e.other_vert(v).index]}
        for v in tips | ring:
            v[am] = 1.0
            v[fc] = (float(hc[0]), float(hc[1]), float(hc[2]), 1.0)
    return nf, na


def write_front(bm, Mw, F, front_verts, uv_override=None):
    """'fmask' = 1 on the given vertices (the rebuilt patches); planar 'uvfront' UVs on every face corner."""
    uvl = bm.loops.layers.uv['uvfront']
    fm = bm.verts.layers.float['fmask']
    S = F.S
    bm.verts.index_update()
    for v in front_verts:
        if v.is_valid:
            v[fm] = 1.0
    uv_override = {v.index: xz for v, xz in (uv_override or {}).items() if v.is_valid}
    for f in bm.faces:
        for lp in f.loops:
            v = lp.vert
            if v.index in uv_override:
                x, z = uv_override[v.index]
            else:
                w = Mw @ v.co
                x, z = w.x, w.z
            p = F.px(np.array([x, 0.0, z]))
            lp[uvl].uv = (p[0] / S, 1.0 - p[1] / S)


def hook_material(mesh, front_png, with_fill=False):
    """Base colour = the model's texture, replaced by the front picture where 'fmask' says so (and by the plain fill
    colour where 'amask' says so); the old normal map is switched off there."""
    img = bpy.data.images.load(front_png)
    for m in mesh.data.materials:
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        lk = bsdf.inputs['Base Color'].links
        if not lk:
            continue
        src = lk[0].from_socket
        uvn = nt.nodes.new('ShaderNodeUVMap')
        uvn.uv_map = 'uvfront'
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = img
        tex.extension = 'EXTEND'
        nt.links.new(uvn.outputs['UV'], tex.inputs['Vector'])
        col = src
        if with_fill:
            am = nt.nodes.new('ShaderNodeAttribute')
            am.attribute_name = 'amask'
            fcn = nt.nodes.new('ShaderNodeAttribute')
            fcn.attribute_name = 'fillcol'
            g = nt.nodes.new('ShaderNodeGamma')                      # the fill colours were sampled as sRGB values
            g.inputs['Gamma'].default_value = 2.2
            nt.links.new(fcn.outputs['Color'], g.inputs['Color'])
            mx = nt.nodes.new('ShaderNodeMix')
            mx.data_type = 'RGBA'
            nt.links.new(am.outputs['Fac'], mx.inputs['Factor'])
            nt.links.new(col, mx.inputs[6])
            nt.links.new(g.outputs['Color'], mx.inputs[7])
            col = mx.outputs[2]
        fm = nt.nodes.new('ShaderNodeAttribute')
        fm.attribute_name = 'fmask'
        mx2 = nt.nodes.new('ShaderNodeMix')
        mx2.data_type = 'RGBA'
        mx2.name = 'front_mix'
        nt.links.new(fm.outputs['Fac'], mx2.inputs['Factor'])
        nt.links.new(col, mx2.inputs[6])
        nt.links.new(tex.outputs['Color'], mx2.inputs[7])
        nt.links.new(mx2.outputs[2], bsdf.inputs['Base Color'])
        nm = next((n for n in nt.nodes if n.type == 'NORMAL_MAP'), None)
        if nm is not None:                                           # no old relief on rebuilt skin
            inv = nt.nodes.new('ShaderNodeMath')
            inv.operation = 'SUBTRACT'
            inv.inputs[0].default_value = 1.0
            mxa = nt.nodes.new('ShaderNodeMath')
            mxa.operation = 'MAXIMUM'
            nt.links.new(fm.outputs['Fac'], mxa.inputs[0])
            if with_fill:
                nt.links.new(am.outputs['Fac'], mxa.inputs[1])
            else:
                mxa.inputs[1].default_value = 0.0
            nt.links.new(mxa.outputs[0], inv.inputs[1])
            inv.name = 'keep_normal'
            old = nm.inputs['Strength'].links
            if old:
                mul = nt.nodes.new('ShaderNodeMath')
                mul.operation = 'MULTIPLY'
                nt.links.new(old[0].from_socket, mul.inputs[0])
                nt.links.new(inv.outputs[0], mul.inputs[1])
                nt.links.new(mul.outputs[0], nm.inputs['Strength'])
            else:
                s0 = nm.inputs['Strength'].default_value
                mul = nt.nodes.new('ShaderNodeMath')
                mul.operation = 'MULTIPLY'
                mul.inputs[0].default_value = s0
                nt.links.new(inv.outputs[0], mul.inputs[1])
                nt.links.new(mul.outputs[0], nm.inputs['Strength'])
    return img


# ------------------------------------------------------------------------------------------------ eyelids

def _srgb_to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lid_colours(F, geo, tex_rgb=None):
    """Skin colour of the upper lid (a little above the lash line) and colour of the lash line, from the front picture."""
    rgb = F.rgb if tex_rgb is None else tex_rgb
    xs, zu, zl = geo.upper_lower(21)
    mid = slice(5, 16)
    def sample(dz0, dz1):
        cols = []
        for x, z in zip(xs[mid], zu[mid]):
            for dz in np.linspace(dz0, dz1, 6):
                p = F.px(np.array([x, 0.0, z + dz]))
                cols.append(rgb[int(np.clip(p[1], 0, F.S - 1)), int(np.clip(p[0], 0, F.S - 1))])
        return np.array(cols)
    skin = np.median(sample(0.0032, 0.0052), 0)
    near = sample(0.0002, 0.0018)
    lash = near[np.argsort(near.sum(1))[:max(3, len(near) // 5)]].mean(0)
    under = []
    for x, z in zip(xs[mid], zl[mid]):
        p = F.px(np.array([x, 0.0, z - 0.004]))
        under.append(rgb[int(np.clip(p[1], 0, F.S - 1)), int(np.clip(p[0], 0, F.S - 1))])
    return skin, lash, np.median(np.array(under), 0)


def _lid_material(name, skin, lash, lash_width=0.07):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'lid'
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uv.outputs['UV'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, (*_srgb_to_lin(lash), 1)
    e[1].position, e[1].color = lash_width * 2.2, (*_srgb_to_lin(skin), 1)
    k = ramp.color_ramp.elements.new(lash_width)
    k.color = (*_srgb_to_lin(lash * 0.6 + skin * 0.4), 1)
    nt.links.new(sep.outputs['X'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.5
    b.inputs['Subsurface Weight'].default_value = 0.2
    b.inputs['Subsurface Radius'].default_value = (0.010, 0.004, 0.0025)
    b.inputs['Subsurface Scale'].default_value = 0.6
    return m


def build_lids(name, geo, holder, F, skin_material, collection=None, nx=28, nrow=14):
    """The two eyelids of one eye: shells lying on the eyeball, turning about the axis through the eye corners.
    They are children of the eyeball's holder (unit-sphere space), so they stay on the flattened eyeball when they turn.
    They wear the SKIN's own material: their 'uvfront' UVs point at the skin just above (below) the eye opening in the
    front picture, and at the painted lash line for their edge, so a closed lid has the colour and shading of the skin
    around it and carries its lash line down with it.
    Returns dict(upper=pivot, lower=pivot, up_open, low_rest, low_span, objects): set_lids() drives them."""
    col = collection or bpy.context.scene.collection
    xs, zu, zl = geo.upper_lower(nx)
    pad = 0.0012
    xs_w = np.r_[xs[0] - pad, xs, xs[-1] + pad]
    zu = np.r_[zu[0], zu, zu[-1]]
    zl = np.r_[zl[0], zl, zl[-1]]
    xn = np.clip((xs_w - geo.c[0]) / geo.R, -0.975, 0.975)             # never past the edge of the eyeball
    cth = np.sqrt(np.clip(1.0 - xn ** 2, 1e-4, None))
    au = np.arcsin(np.clip((zu - geo.c[1]) / geo.R / cth, -0.99, 0.99))
    al = np.arcsin(np.clip((zl - geo.c[1]) / geo.R / cth, -0.99, 0.99))
    ac = al + 0.05 * (au - al)                                        # where the lids meet when the eye is shut
    up_open = float(np.max(au - ac)) + 0.05                           # turn that hides the upper lid under the skin
    kk = geo.w / 0.030
    out = dict(objects=[], up_open=up_open, low_rest=-0.05, low_span=float(np.max(au - al)))
    S = F.S

    def uv_of(x, z):
        p = F.px(np.array([x, 0.0, z]))
        return (p[0] / S, 1.0 - p[1] / S)

    def shell(tag, edge, sign, span, rad_lid, z_rim, d_skin, d_lash):
        verts, uvs, faces = [], [], []
        rows = [(-1, 1.003)] + [(j, rad_lid) for j in range(nrow + 1)]   # first row: the lid margin, down on the eyeball
        for j, rad in rows:
            a = edge + sign * (max(j, 0) / nrow) * span
            for i in range(len(xn)):
                verts.append((xn[i] * rad, -cth[i] * math.cos(a[i]) * rad, cth[i] * math.sin(a[i]) * rad))
                xi = float(np.clip(xs_w[i], xs[1], xs[-2]))
                zr = float(np.interp(xi, xs_w, z_rim))
                dz = d_lash if j <= 0 else d_skin + 0.00012 * j
                uvs.append(uv_of(xi, zr + sign * dz))
        n = len(xn)
        for r in range(len(rows) - 1):
            for i in range(n - 1):
                q = (r * n + i, r * n + i + 1, (r + 1) * n + i + 1, (r + 1) * n + i)
                faces.append(q if sign > 0 else q[::-1])
        me = bpy.data.meshes.new(f'{name}.{tag}')
        me.from_pydata(verts, [], faces)
        uvl = me.uv_layers.new(name='uvfront')
        for lp in me.loops:
            uvl.data[lp.index].uv = uvs[lp.vertex_index]
        for nm in ('fmask',):
            at = me.attributes.new(nm, 'FLOAT', 'POINT')
            at.data.foreach_set('value', np.ones(len(verts), np.float32))
        nmk = me.color_attributes.new('nmask', 'FLOAT_COLOR', 'POINT')
        nmk.data.foreach_set('color', np.ones(len(verts) * 4, np.float32))
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(skin_material)
        ob = bpy.data.objects.new(f'{name}.{tag}', me)
        piv = bpy.data.objects.new(f'{name}.{tag}.pivot', None)
        col.objects.link(ob)
        col.objects.link(piv)
        piv.parent = holder
        piv.rotation_mode = 'XYZ'
        ob.parent = piv
        out['objects'].append(ob)
        return piv
    out['upper'] = shell('lidU', ac, +1.0, up_open + 0.14, 1.024, zu, 0.0042 * kk, 0.0005 * kk)
    out['lower'] = shell('lidL', al, -1.0, 0.27, 1.016, zl, 0.0035 * kk, 0.0003 * kk)
    set_lids(out, 0.0, 0.0)
    return out


def set_lids(lids, upper, lower=0.0):
    """upper: 0 = fully open (hidden under the skin), 1 = shut.  lower: 0 = at rest (hidden), 1 = raised by 35 % of the
    eye opening (squint, smile, the last part of a blink)."""
    lids['upper'].rotation_euler.x = -lids['up_open'] * (1.0 - min(max(upper, 0.0), 1.0))
    lids['lower'].rotation_euler.x = -(lids['low_rest'] + 0.35 * lids['low_span'] * min(max(lower, 0.0), 1.0))


# ------------------------------------------------------------------------------------------------ mouth

LIP_IN_U = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
LIP_IN_L = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]
LIP_OUT_U = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
LIP_OUT_L = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
N_LIP = 37


def _resample_open(P, n):
    P = np.asarray(P, float)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    u = np.linspace(0, s[-1], n)
    return np.column_stack([np.interp(u, s, P[:, 0]), np.interp(u, s, P[:, 1])])


class MouthGeo:
    """The mouth in the front view: the line between the lips (snapped to the painted crease), the outline of the
    lips, the jaw hinge."""

    def __init__(self, F, surf, tex_rgb=None):
        L = F.L
        rgb = F.rgb if tex_rgb is None else tex_rgb
        cR, cL = L[61][[0, 2]], L[291][[0, 2]]
        mid = (L[LIP_IN_U][:, [0, 2]] + L[LIP_IN_L][:, [0, 2]]) / 2
        mid[0], mid[-1] = cR, cL
        line = _resample_open(mid, N_LIP)
        # snap to the darkest row of the picture near the line (the painted crease), then smooth
        lum = rgb.mean(-1)
        dz = np.linspace(-0.0022, 0.0022, 23)
        off = np.zeros(N_LIP)
        for i in range(1, N_LIP - 1):
            vals = []
            for d in dz:
                p = F.px(np.array([line[i, 0], 0.0, line[i, 1] + d]))
                vals.append(lum[int(np.clip(p[1], 0, F.S - 1)), int(np.clip(p[0], 0, F.S - 1))])
            vals = ndi.gaussian_filter1d(np.array(vals), 1.0)
            off[i] = dz[int(np.argmin(vals))]
        off = ndi.gaussian_filter1d(off, 2.0)
        off[0] = off[-1] = 0.0
        line[:, 1] += off * np.sin(np.linspace(0, np.pi, N_LIP)) ** 0.5
        self.line = line
        self.xs = line[:, 0]
        self.out_u = self._curve(L[LIP_OUT_U][:, [0, 2]], +1)
        self.out_l = self._curve(L[LIP_OUT_L][:, [0, 2]], -1)
        self.cR, self.cL = line[0], line[-1]
        self.w = float(cL[0] - cR[0])
        self.xm = float((cL[0] + cR[0]) / 2)
        self.io = float(np.linalg.norm(L[468] - L[473]))
        self.hu = float(np.max(self.out_u - line[:, 1]))              # height of the upper lip (red part)
        self.hl = float(np.max(line[:, 1] - self.out_l))
        c = N_LIP // 2
        self.y_lip = float(surf.depth(line[c, 0], line[c, 1] + 0.4 * self.hu))
        self.y_line = float(surf.depth(line[c, 0], line[c, 1]))
        chin = L[152]
        hinge = (L[234] + L[454]) / 2
        self.chin = chin
        self.hinge = np.array([self.xm, max(hinge[1], chin[1] + 0.6 * self.io), hinge[2] - 0.05 * self.io])
        self.nose_z = float(L[2][2])                                  # base of the nose
        self.jaw_x = float(max(abs(L[172][0] - self.xm), abs(L[397][0] - self.xm)))

    def _curve(self, P, sign):
        """Outer lip contour as z at the abscissas of the lip line (pinched onto the line at the corners)."""
        z = np.interp(self.xs, P[:, 0], P[:, 1])
        z[0], z[-1] = self.line[0, 1], self.line[-1, 1]
        return np.maximum(z, self.line[:, 1]) if sign > 0 else np.minimum(z, self.line[:, 1])

    def line_z(self, x):
        """Height of the line between the lips at abscissa x, continued flat beyond the corners."""
        return np.interp(x, self.xs, self.line[:, 1])


def cut_mouth(bm, Mw, F, geo, surf, head_group, uv_override, margin=0.0075):
    """Rebuild the lips as two clean patches (upper, lower) that meet along the line between the lips without being
    joined there, each with an inner face going back into the mouth."""
    Minv = Mw.inverted()
    dl = bm.verts.layers.deform.verify()
    side_l = bm.verts.layers.int['lipside']
    line, xs = geo.line, geo.xs
    outline = np.vstack([np.column_stack([xs, geo.out_u]), np.column_stack([xs, geo.out_l])[-2:0:-1]])
    if poly_area(outline) < 0:
        outline = outline[::-1]
    poly = convex_hull(offset_closed(outline, margin)[::2])
    top = geo.nose_z - 0.0025                                        # stay under the nose (its underside cannot be
    poly[:, 1] = np.minimum(poly[:, 1], top)                         # rebuilt from a front view)
    poly = convex_hull(poly)
    loop, nloops = cut_region(bm, Mw, poly, surf)
    LP = np.array([[(Mw @ v.co).x, (Mw @ v.co).z] for v in loop])
    nL = len(loop)

    def new_vert(x, z, y=None, side=0):
        if y is None:
            y = surf.depth(float(x), float(z))
        v = bm.verts.new(Minv @ Vector((float(x), float(y), float(z))))
        v[dl][head_group] = 1.0
        v[side_l] = side
        return v
    # the cut continues from each corner to the border of the patch (shared by both halves)
    iR = int(np.argmin(np.hypot(LP[:, 0] - (line[0, 0] - 2 * margin), LP[:, 1] - line[0, 1])))
    iL = int(np.argmin(np.hypot(LP[:, 0] - (line[-1, 0] + 2 * margin), LP[:, 1] - line[-1, 1])))
    cornR = new_vert(*line[0])
    cornL = new_vert(*line[-1])

    def ext(c2d, lv):
        p1 = np.array([(Mw @ lv.co).x, (Mw @ lv.co).z])
        n = max(1, int(np.linalg.norm(p1 - c2d) / 0.0018))
        return [new_vert(*(c2d + (p1 - c2d) * k / (n + 1))) for k in range(1, n + 1)]
    extR, extL = ext(line[0], loop[iR]), ext(line[-1], loop[iL])
    ydep = surf.depths(line[1:-1])
    up = [new_vert(line[i][0], line[i][1], ydep[i - 1], +1) for i in range(1, N_LIP - 1)]      # R -> L
    lo = [new_vert(line[i][0], line[i][1], ydep[i - 1], -1) for i in range(1, N_LIP - 1)]

    def arc(i0, i1):                                                  # loop vertices i0 .. i1 going counter-clockwise
        out, i = [], i0
        while True:
            out.append(loop[i])
            if i == i1:
                break
            i = (i + 1) % nL
        return out
    # the loop is counter-clockwise (x-z plane): from the left side (iL) over the top to the right side (iR)
    loop_u = arc(iL, iR) + extR[::-1] + [cornR] + up + [cornL] + extL
    loop_l = arc(iR, iL) + extL[::-1] + [cornL] + lo[::-1] + [cornR] + extR
    fr = [0.22, 0.48, 0.76, 1.0, 1.32, 1.75, 2.3, 3.0]
    faces, new, rows = [], [cornR, cornL] + extR + extL + up + lo, {}
    for sgn, lp, outz, tag in ((+1, loop_u, geo.out_u, 'u'), (-1, loop_l, geo.out_l, 'l')):
        P2 = np.array([[(Mw @ v.co).x, (Mw @ v.co).z] for v in lp])
        if poly_area(P2) < 0:
            lp, P2 = lp[::-1], P2[::-1]
        h = np.abs(outz - line[:, 1])
        hmin = 0.35 * h.max()
        pts = []
        for f in fr:
            for i in range(1, N_LIP - 1):
                hh = max(h[i], hmin * math.sin(math.pi * i / (N_LIP - 1)) ** 0.5)
                pts.append((line[i, 0], line[i, 1] + sgn * f * hh))
        pts = np.array(pts)
        ok = inside_poly(pts, P2) & (dist_to_closed(pts, P2)[0] > 0.0011)
        pts = pts[ok]
        nv, fs = fill_patch(bm, Mw, lp, pts, [], [], surf.depths, head_group)
        faces += fs
        new += [v for v in nv if v is not None]
        rows[tag] = nv
    for v in new:
        if v.is_valid and v[side_l] == 0:
            pass
    # inner faces of the lips: each lip edge goes back into the mouth and curls behind the lip
    inner = {}
    c = len(up) // 2
    for sgn, chain, tag in ((+1, up, 'u'), (-1, lo, 'l')):
        kk = geo.io / 0.062
        prof = [(0.0010 * kk, -0.0003 * kk), (0.0024 * kk, 0.0006 * kk), (0.0032 * kk, 0.0026 * kk), (0.0035 * kk, 0.0058 * kk), (0.0036 * kk, 0.0100 * kk)]   # (back, away from the opening): the inside of the lip lies on the teeth
        prev = chain
        strips = []
        for k, (back, away) in enumerate(prof):
            row = []
            for i, v in enumerate(chain):
                w = Mw @ v.co
                t = math.sin(math.pi * (i + 1) / (len(chain) + 1)) ** 0.6           # thinner towards the corners
                pz = w.z + sgn * away * t
                py = w.y + back * (0.35 + 0.65 * t)
                ys = surf.depth(w.x, pz)
                if ys is not None and k >= 2:                                       # never through the skin of the lip
                    py = max(py, ys + 0.0028 * kk)
                nv = bm.verts.new(Minv @ Vector((w.x, py, pz)))
                nv[dl][head_group] = 1.0
                nv[side_l] = sgn * 2                                               # 2 = inner face (anchored to its edge)
                uv_override[nv] = (w.x, w.z + sgn * (0.0010 + 0.0004 * k))
                row.append(nv)
            for i in range(len(chain) - 1):
                q = (prev[i], prev[i + 1], row[i + 1], row[i]) if sgn > 0 else (prev[i + 1], prev[i], row[i], row[i + 1])
                try:
                    f = bm.faces.new(q)
                    f.smooth = True
                    faces.append(f)
                except ValueError:
                    pass
            # close the strip onto the corners
            for corner, a, b in ((cornR, prev[0], row[0]), (cornL, row[-1], prev[-1])):
                try:
                    f = bm.faces.new((corner, a, b) if sgn < 0 else (corner, b, a))
                    f.smooth = True
                    faces.append(f)
                except ValueError:
                    pass
            strips.append(row)
            prev = row
        inner[tag] = strips
        new += [v for r in strips for v in r]
    # the inside of the mouth: a dark sock from the back of the lips, widening behind them to hold the teeth
    kk = geo.io / 0.062
    ring = inner['u'][-1] + [cornL] + inner['l'][-1][::-1] + [cornR]
    sides = [1] * len(inner['u'][-1]) + [0] + [-1] * len(inner['l'][-1]) + [0]
    P0 = [Mw @ v.co for v in ring]
    ctr = Vector((geo.xm, geo.y_line, float(geo.line_z(geo.xm))))
    sock_faces = []
    prev = ring
    for back, sx, sz in ((0.004, 1.12, 1.25), (0.012, 1.30, 1.9), (0.026, 1.38, 2.3), (0.044, 1.25, 2.1)):
        row = []
        for v, p0, sd in zip(ring, P0, sides):
            w = Vector((ctr.x + (p0.x - ctr.x) * sx, max(p0.y, geo.y_line + 0.003 * kk) + back * kk, ctr.z + (p0.z - ctr.z) * sz))
            ys = surf.depth(w.x, w.z)
            if ys is not None:
                w.y = max(w.y, ys + 0.004 * kk)
            nv = bm.verts.new(Minv @ w)
            nv[dl][head_group] = 1.0
            nv[side_l] = sd * 3 if sd else 3 if p0.z > ctr.z else -3
            if sd == 0:
                nv[side_l] = 4                                                      # behind a corner: half and half
            row.append(nv)
        m = len(ring)
        for i in range(m):
            try:
                f = bm.faces.new((prev[i], prev[(i + 1) % m], row[(i + 1) % m], row[i]))
                f.smooth = True
                sock_faces.append(f)
            except ValueError:
                pass
        prev = row
    try:
        sock_faces.append(bm.faces.new(prev))
    except ValueError:
        pass
    return dict(up=up, lo=lo, corners=(cornR, cornL), inner=inner, new=new + list(loop), faces=faces, sock=sock_faces, nloops=nloops)



# ------------------------------------------------------------------------------------------------ shape keys

OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132,
        93, 234, 127, 162, 21, 54, 103, 67, 109]
BROW = {'R': [70, 63, 105, 66, 107], 'L': [300, 293, 334, 296, 336]}          # outer -> inner
CORNER = {'R': 61, 'L': 291}
CHEEK = {'R': 205, 'L': 425}
LIP_TINT = {'picoR': (0.84, 0.64, 0.66), 'noxR': (0.92, 0.78, 0.78)}
JAW_DEG = 10.0                 # jawOpen = 1 turns the jaw by this much about its hinge
LIP_DOWN = 0.0060              # lipLowerDown = 1: the lower lip goes down by this much (metres, for an eye distance of 62 mm)
LIP_UP = 0.0036


def _field(V, controls, io):
    """Sum of gaussian-weighted displacements; controls = [(point, disp, sigma in eye distances), ...] (front view)."""
    D = np.zeros_like(V)
    W = np.zeros(len(V))
    for p, d, s in controls:
        r2 = (V[:, 0] - p[0]) ** 2 + (V[:, 2] - p[2]) ** 2
        w = np.exp(-r2 / (2 * (s * io) ** 2))
        D += w[:, None] * np.asarray(d)[None, :]
        W += w
    return D / np.maximum(W, 1.0)[:, None]


def build_keys(mesh, F, mouth, eyes):
    """Shape keys of the skin: jaw, lips, mouth corners, eyebrows.  The eyes have none: lids and eyeballs are parts.
    Every key leaves the skull alone: the displacement fields are local and masked to the face skin."""
    me = mesh.data
    L, io = F.L, mouth.io
    k = io / 0.062                                                    # this head against a real one
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    M = np.array(mesh.matrix_world)
    V = co @ M[:3, :3].T + M[:3, 3]
    side = np.zeros(n, np.int32)
    me.attributes['lipside'].data.foreach_get('value', side)
    fm = np.zeros(n, np.float32)
    me.attributes['fmask'].data.foreach_get('value', fm)
    A = V.copy()
    inner = (np.abs(side) == 2) | (np.abs(side) == 3)
    A[inner, 0] = np.clip(V[inner, 0], mouth.xs[1], mouth.xs[-2])
    A[inner, 2] = mouth.line_z(A[inner, 0]) + np.sign(side[inner]) * 0.0003
    A[inner, 1] = mouth.y_line
    corner_back = side == 4
    A[corner_back, 0] = np.where(V[corner_back, 0] > mouth.xm, mouth.xs[-1], mouth.xs[0])
    A[corner_back, 2] = mouth.line_z(A[corner_back, 0])
    A[corner_back, 1] = mouth.y_line
    # the face skin: inside the outline of the face and close to the surface seen from the front
    oval = L[OVAL][:, [0, 2]]
    c = oval.mean(0)
    q = c + (A[:, [0, 2]] - c) / 1.12
    p = F.px(A)
    xi = np.clip(p[:, 0].round().astype(int), 0, F.S - 1)
    yi = np.clip(p[:, 1].round().astype(int), 0, F.S - 1)
    yfront = np.where(F.mask[yi, xi], F.pos[yi, xi, 1], -1e9)
    skin = inside_poly(q, oval) * (1.0 - _smooth(A[:, 1] - yfront, 0.02, 0.045))
    skin = np.where((fm > 0.5) | (side != 0), 1.0, skin)
    Minv3 = np.linalg.inv(M[:3, :3])
    if me.shape_keys is None:
        mesh.shape_key_add(name='Basis')
    keys, reach = {}, {}

    def add(key, D):
        D = D * skin[:, None]
        sk = mesh.shape_key_add(name=key, from_mix=False)
        sk.data.foreach_set('co', (co + D @ Minv3.T).ravel())
        sk.value = 0.0
        keys[key] = sk
        reach[key] = float(np.linalg.norm(D, axis=1).max())

    up, right, fwd = np.array([0, 0, 1.0]), np.array([1.0, 0, 0]), np.array([0, -1.0, 0])
    xm, hw = mouth.xm, mouth.w / 2
    s = np.clip((A[:, 0] - xm) / hw, -1.5, 1.5)
    zline = mouth.line_z(A[:, 0])
    sdist = A[:, 2] - zline                                           # > 0 above the line between the lips
    between = np.abs(s) < 1.0
    is_low = np.where((side != 0) & (side != 4), side < 0, sdist < 0)
    # ---- jaw: a rotation about the hinge for what hangs from the lower jaw
    latd = np.maximum(0.0, np.abs(A[:, 0] - xm) - 0.85 * hw)
    wd = 0.004 + 1.1 * latd
    ramp = _smooth(-sdist, -wd, wd)
    hard = np.where(between, is_low.astype(float), ramp)
    u = _smooth(np.abs(A[:, 0] - xm), 0.80 * hw, 1.10 * hw)
    below = (1 - u) * hard + u * ramp
    lat = 1.0 - _smooth(np.abs(A[:, 0] - xm) / mouth.jaw_x, 0.70, 1.05)
    chin = mouth.chin
    neck = _smooth(A[:, 2], chin[2] - 0.55 * io, chin[2] - 0.12 * io)
    cR, cL = L[61], L[291]
    dcorner = np.minimum(np.linalg.norm(A[:, [0, 2]] - cR[[0, 2]], axis=1), np.linalg.norm(A[:, [0, 2]] - cL[[0, 2]], axis=1))
    wj = below * lat * neck * (1.0 - 0.90 * np.exp(-(dcorner / (0.15 * io)) ** 2))
    th = math.radians(JAW_DEG)
    Rx = np.array([[1, 0, 0], [0, math.cos(th), -math.sin(th)], [0, math.sin(th), math.cos(th)]])
    rel = V - mouth.hinge
    add('jawOpen', (rel @ Rx.T - rel) * wj[:, None])
    # ---- lips
    gt = np.clip(1.0 - s ** 2, 0.0, 1.0)
    dzl = np.where(is_low, np.maximum(zline - A[:, 2], 0.0), 1e9)
    gl = (1.0 - _smooth(dzl, mouth.hl, mouth.hl + 0.011 * k)) * (np.abs(s) < 1.0)
    add('lipLowerDown', (gt ** 0.8 * gl)[:, None] * (-up * LIP_DOWN * k + fwd * 0.0012 * k))
    dzu = np.where(~is_low, np.maximum(A[:, 2] - zline, 0.0), 1e9)
    zroom = max(mouth.nose_z - float(zline.mean()) - 0.001, mouth.hu + 0.003)
    gu = (1.0 - _smooth(dzu, mouth.hu * 0.9, zroom)) * (np.abs(s) < 1.0)
    add('lipUpperUp', (gt ** 0.6 * gu)[:, None] * (up * LIP_UP * k + fwd * 0.0006 * k))
    lipu = (1.0 - _smooth(dzu, 0.0, mouth.hu * 1.1)) * (np.abs(s) < 1.0)
    lipl = (1.0 - _smooth(dzl, 0.0, mouth.hl * 1.1)) * (np.abs(s) < 1.0)
    add('lipsPress', (gt ** 0.5 * lipu)[:, None] * (-up * 0.0011 * k - fwd * 0.0016 * k) + (gt ** 0.5 * lipl)[:, None] * (up * 0.0011 * k - fwd * 0.0016 * k))
    lip_c_u, lip_c_l = L[0], L[17]
    add('mouthNarrow', _field(A, [(cR, right * 0.20 * io + fwd * 0.050 * io, 0.17), (cL, -right * 0.20 * io + fwd * 0.050 * io, 0.17),
                                  (lip_c_u, fwd * 0.078 * io, 0.19), (lip_c_l, fwd * 0.078 * io, 0.19)], io))
    add('mouthWide', _field(A, [(cR, -right * 0.09 * io - fwd * 0.02 * io, 0.15), (cL, right * 0.09 * io - fwd * 0.02 * io, 0.15)], io))
    for sd, sx in (('R', -1.0), ('L', 1.0)):
        cc, ch = L[CORNER[sd]], L[CHEEK[sd]]
        add(f'smile_{sd}', _field(A, [(cc, up * 0.12 * io + right * sx * 0.07 * io - fwd * 0.03 * io, 0.16), (ch, up * 0.05 * io, 0.22)], io))
        add(f'frown_{sd}', _field(A, [(cc, -up * 0.10 * io - right * sx * 0.02 * io, 0.15)], io))
        # ---- eyebrows: the band above the eye; nothing moves at the rim of the eye opening
        b = L[BROW[sd]]
        g = eyes[sd]
        d_rim, _ = dist_to_closed(A[:, [0, 2]], g.O)
        att = (_smooth(d_rim, 0.0060 * k, 0.0130 * k) * (A[:, 2] > g.c[1] - 0.2 * g.h))[:, None]   # the lids and the lash line stay put
        add(f'browUp_{sd}', att * _field(A, [(b[0], up * 0.09 * io, 0.19), (b[2], up * 0.15 * io, 0.19), (b[4], up * 0.14 * io, 0.19)], io))
        add(f'browDown_{sd}', att * _field(A, [(b[0], up * 0.015 * io, 0.17), (b[2], -up * 0.06 * io, 0.17),
                                               (b[4], -up * 0.11 * io - right * sx * 0.045 * io, 0.17)], io))
        add(f'browSad_{sd}', att * _field(A, [(b[0], -up * 0.045 * io, 0.17), (b[2], up * 0.035 * io, 0.17), (b[4], up * 0.13 * io, 0.17)], io))
    me.update()
    return keys, reach


# ------------------------------------------------------------------------------------------------ assembly

def trim_eyeball(eye_ob, geo, keep=0.0014):
    """Keep only the part of the eyeball that can be seen through the eye opening (the eyeball never turns: the iris
    slides on it).  What is left cannot come out through the skin of a narrow face, at the temple or under the eye."""
    me = eye_ob.data
    bmx = bmesh.new()
    bmx.from_mesh(me)
    poly = offset_closed(geo.O, keep)
    P = np.array([[v.co.x + geo.c[0], v.co.z + geo.c[1]] for v in bmx.verts])
    ins = inside_poly(P, poly)
    front = np.array([v.co.y < 0.0 for v in bmx.verts])
    kill = [f for f in bmx.faces if not any(ins[v.index] and front[v.index] for v in f.verts)]
    bmesh.ops.delete(bmx, geom=kill, context='FACES')
    bmx.to_mesh(me)
    bmx.free()
    me.update()


def _tone_teeth(T, value=0.60, warm=(1.0, 0.95, 0.84)):
    """Teeth as they look inside a mouth: ivory and in the shade of the lips, never the brightest thing of the face."""
    done = set()
    for ob in T['objects']:
        for m in ob.data.materials:
            if m is None or m.name in done or 'enamel' not in m.name:
                continue
            done.add(m.name)
            nt = m.node_tree
            b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
            if any(n.name == 'tone' for n in nt.nodes):
                continue
            lk = b.inputs['Base Color'].links
            if lk:
                mx = nt.nodes.new('ShaderNodeMix')
                mx.name = 'tone'
                mx.data_type = 'RGBA'
                mx.blend_type = 'MULTIPLY'
                mx.inputs['Factor'].default_value = 1.0
                mx.inputs[7].default_value = (value * warm[0], value * warm[1], value * warm[2], 1.0)
                nt.links.new(lk[0].from_socket, mx.inputs[6])
                nt.links.new(mx.outputs[2], b.inputs['Base Color'])
            b.inputs['Coat Weight'].default_value = 0.25


def _mouth_bag(name, mouth, col):
    """A dark shell behind the lips: whatever is seen between the teeth and the cheeks is the dark of the mouth,
    never the inside of the head."""
    import bmesh as _bm
    me = bpy.data.meshes.new(name)
    b = _bm.new()
    _bm.ops.create_uvsphere(b, u_segments=24, v_segments=12, radius=1.0)
    k = mouth.io / 0.062
    for v in list(b.verts):
        if v.co.y < -0.05:
            b.verts.remove(v)
    for v in b.verts:
        v.co.x *= 0.56 * mouth.w
        v.co.y *= 0.045 * k
        v.co.z *= 0.026 * k
    b.to_mesh(me)
    b.free()
    for p in me.polygons:
        p.use_smooth = True
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = (0.030, 0.006, 0.007, 1)
    bs.inputs['Roughness'].default_value = 0.8
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.location = (mouth.xm, mouth.y_line + 0.0045 * k, float(mouth.line_z(mouth.xm)) - 0.004 * k)
    return ob


def build(mesh, arm, name, collection=None, teeth=True):
    """Rebuild the face of a rigged character (rest pose, character at the origin facing -Y).  Returns a dict used by
    apply(): the skin keys, the eyes with their lids, the teeth and the jaw pivot, all following the Head bone."""
    import eyes6
    F = f6img.Front(name, HERE)
    me = mesh.data
    Mw = mesh.matrix_world.copy()
    col = collection or bpy.context.scene.collection
    bm = bmesh.new()
    bm.from_mesh(me)
    ensure_layers(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.verts.index_update()
    bm.verts.ensure_lookup_table()
    hg = mesh.vertex_groups['Head'].index
    erased = None
    gpath = f'{OUT}/{name}_G.npy'
    if os.path.exists(gpath):
        node = next(n for m in me.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links)
        erased = erase_glasses(bm, Mw, F, texture_colours(bm, node.image))
        mark_erased(bm, Mw, F, erased)
    surf = Surface(bm, Mw)
    uvo, front, eyes = {}, [], {}
    fits = {}
    for sd in 'RL':
        eyes[sd] = EyeGeo(F, sd, surf)
        fits[sd] = eyes[sd].fit(surf, 0.30 * eyes[sd].w)
    rk, rec = min(f[0] for f in fits.values()), max(f[1] for f in fits.values())     # the same eyeball on both sides
    for sd in 'RL':
        eyes[sd].set_fit(rk, rec)
        r = cut_eye(bm, Mw, F, eyes[sd], surf, hg, uv_override=uvo)
        front += r['new']
    print('  eyes: radius %.2f x width, set %.1f mm back' % (rk, rec * 1000))
    front_png = f'{OUT}/{name}_front_tex.png'
    tex_rgb = F.rgb
    if erased is not None:
        tex_rgb = f6img.repaint_front(F, np.load(gpath), [eyes[sd].O for sd in 'RL'])
    if erased is not None:                                            # the eyebrows are redrawn in the front picture
        bmask = f6img.brow_region(F, grow_mm=5.0) & ~ndi.binary_dilation(F.raised() & ~F.skin_like(), iterations=3)
        N3 = Mw.to_3x3()
        bm.normal_update()
        hfl = bm.verts.layers.int['hairflag']
        for v in bm.verts:
            w = Mw @ v.co
            pp = F.px(np.array([w.x, 0.0, w.z]))
            xi, yi = int(round(pp[0])), int(round(pp[1]))
            if 0 <= xi < F.S and 0 <= yi < F.S and bmask[yi, xi] and abs(w.y - F.pos[yi, xi, 1]) < 0.0025 and (N3 @ v.normal).y < -0.3 and not v[hfl]:
                front.append(v)
    if erased is not None:                                            # a last relaxation of the erased skin and its edge
        hfl = bm.verts.layers.int['hairflag']
        core = {v for v in bm.verts if v[hfl] == 2}
        near = {e.other_vert(v) for v in core for e in v.link_edges if e.other_vert(v)[hfl] == 0}
        near |= {e.other_vert(v) for v in near for e in v.link_edges if e.other_vert(v)[hfl] == 0}
        keep_fixed = set(front)                                       # the new eye patches keep their shape
        mov = [v for v in (core | near) if v not in keep_fixed and v.is_valid and not v.is_boundary]
        for _ in range(6):
            bmesh.ops.smooth_vert(bm, verts=mov, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    surf = Surface(bm, Mw)
    mouth = MouthGeo(F, surf)
    from PIL import Image as _Image
    tex_rgb = f6img.tint_lips(tex_rgb, F, mouth.xs, mouth.line[:, 1], mouth.out_u, mouth.out_l, mul=LIP_TINT.get(name, (0.90, 0.76, 0.77)))
    _Image.fromarray((np.clip(tex_rgb, 0, 1) * 255 + 0.5).astype(np.uint8)).save(front_png)
    rm = cut_mouth(bm, Mw, F, mouth, surf, hg, uvo)
    front += rm['new']
    n_mat = len(me.materials)
    for f in rm['sock']:
        if f.is_valid:
            f.material_index = n_mat
    write_front(bm, Mw, F, front, uvo)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    if 'custom_normal' in me.attributes:
        me.attributes.remove(me.attributes['custom_normal'])
    for p in me.polygons:
        p.use_smooth = True
    me.update()
    hook_material(mesh, front_png, with_fill=erased is not None)
    dark = bpy.data.materials.new(f'{name}.mouth_in')
    dark.use_nodes = True
    bs = dark.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = (0.10, 0.022, 0.020, 1)      # dark red-brown flesh, not a black void
    bs.inputs['Roughness'].default_value = 0.6
    me.materials.append(dark)
    keys, reach = build_keys(mesh, F, mouth, eyes)
    # ---- the parts: they follow the Head bone through one anchor that is the identity in the rest pose
    anchor = bpy.data.objects.new(f'{name}.head_anchor', None)
    col.objects.link(anchor)
    anchor.parent = arm
    anchor.parent_type = 'BONE'
    anchor.parent_bone = 'Head'
    bpy.context.view_layer.update()
    anchor.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    focus = bpy.data.objects.new(f'{name}.focus', None)               # between the eyes: what a close-up focuses on
    col.objects.link(focus)
    focus.parent = anchor
    focus.location = ((eyes['R'].centre + eyes['L'].centre) / 2) - np.array([0.0, (eyes['R'].D + eyes['L'].D) / 2, 0.0])
    R = dict(name=name, mesh=mesh, keys=keys, reach=reach, F=F, mouth=mouth, eyes=eyes, anchor=anchor, parts={}, objects=[], lid_rest=0.22, focus=focus)
    for sd in 'RL':
        g = eyes[sd]
        p = F.px(np.array([g.iris_c[0], 0.0, g.iris_c[1] - 0.55 * g.iris_r]))
        colr = F.rgb[int(p[1]), int(p[0])]
        E = eyes6.build(f'{name}.eye{sd}', radius=g.R, depth=g.D, iris_radius=g.iris_r, iris_rgb=eyes6.srgb(*[float(c) for c in colr]), collection=col)
        nd = E['material'].node_tree.nodes
        if 'sclera_rgb' in nd:                                       # the white of an eye is greyer than lit skin
            nd['sclera_rgb'].outputs[0].default_value = (0.42, 0.385, 0.345, 1.0)
        eyes6.set_look(E, lid_shade=0.65)
        trim_eyeball(E['eye'], g)
        E['root'].parent = anchor
        E['root'].location = g.centre
        E['rest_shift'] = (float(g.iris_c[0] - g.c[0]), float(g.iris_c[1] - g.c[1]))
        E['lids'] = build_lids(f'{name}.eye{sd}', g, E['holder'], F, me.materials[0], collection=col)
        R['parts']['eye' + sd] = E
        R['objects'] += [E['eye']] + E['lids']['objects']
    if teeth:
        import teeth6
        k = mouth.io / 0.062
        T = teeth6.build(name, arch_width=0.80 * mouth.w, collection=col, cavity=True)
        zl = float(mouth.line_z(mouth.xm))
        # at rest the lips meet 0.7 mm above the edge of the upper incisors: when they part, a sliver of the upper
        # teeth shows under the upper lip and the rest of the opening is the dark of the mouth (as in the reference)
        up_pos = Vector((mouth.xm, mouth.y_line + 0.0068 * k, zl - 0.0007 * k))
        T['upper'].parent = anchor
        T['upper'].location = up_pos
        jaw = bpy.data.objects.new(f'{name}.jaw', None)
        col.objects.link(jaw)
        jaw.parent = anchor
        jaw.location = mouth.hinge
        jaw.rotation_mode = 'XYZ'
        T['lower'].parent = jaw
        # the lower teeth stay 2.4 mm under the edge of the lower lip (they show only when that lip is pulled down)
        low_pos = Vector((mouth.xm, up_pos.y + T['bite'][1], zl - 0.0024 * k))
        T['lower'].location = low_pos - Vector(mouth.hinge)
        _tone_teeth(T)
        R['parts']['teeth'] = T
        R['parts']['jaw'] = jaw
        R['objects'] += list(T['objects'])
    if erased is not None:
        import glasses6
        gR, gL = eyes['R'], eyes['L']
        ex = (abs(gR.c[0]) + abs(gL.c[0])) / 2
        xmid = (gR.c[0] + gL.c[0]) / 2
        pupil_z = (gR.iris_c[1] + gL.iris_c[1]) / 2
        cornea_y = ((gR.cy - gR.D) + (gL.cy - gL.D)) / 2
        lens_w = min(1.55 * (gR.w + gL.w) / 2 / EYE_SHRINK.get(name, 1.0), 2 * ex - 0.017)       # the bridge needs 17 mm
        bridge = 2 * ex - lens_w
        ear_y = (F.L[234][1] + F.L[454][1]) / 2
        half = ex + lens_w / 2 + 0.0032 + 0.004
        root_z = pupil_z + 0.0098                                    # the brows stay visible above the frame
        y_nose = surf.depth(float(xmid), float(root_z - 0.004)) or cornea_y
        root_y = min(cornea_y - 0.0125, y_nose - 0.0048)
        G = glasses6.build(f'{name}.glasses', lens_w=lens_w, lens_h=0.70 * lens_w, bridge=bridge, temple_len=max(0.09, ear_y - root_y + 0.012),
                           face_half_width=half, head_half_width=half + 0.004, collection=col, rim=0.0027)
        glasses6.set_lens(G, reflect=0.004, veil=0.0, edge_haze=0.06, edge_dark=0.20)        # clear glass: the eyes must read
        glasses6.set_frame(G, rgb=(34, 38, 42), coat=0.3)                       # dark smoke grey: it frames the eyes like a brow line
        print('  glasses: lens %.1f x %.1f mm, bridge %.1f, cornea-lens %.1f mm, nose clearance %.1f mm' % (
            lens_w * 1000, 0.70 * lens_w * 1000, bridge * 1000, (cornea_y - root_y) * 1000, (y_nose - root_y) * 1000))
        G['root'].parent = anchor
        G['root'].location = (xmid, root_y, root_z)
        R['parts']['glasses'] = G
        R['objects'] += list(G['objects'])
    apply(R, {})
    return R


def apply(R, values):
    """Set the whole face from one dict of values in 0..1 (missing = 0):
       skin keys   jawOpen, lipLowerDown, lipUpperUp, lipsPress, mouthNarrow, mouthWide, smile_L/R, frown_L/R,
                   browUp_L/R, browDown_L/R, browSad_L/R
       eyes        eyeClosed_L/R (blink), eyeSquint_L/R, eyeWide_L/R, eyeLookLeft/Right/Up/Down_L/R (1 = 28 degrees)
       tongue      tongueUp, tongueOut
    Names without a side are applied to both sides."""
    import eyes6
    v = {}
    for key, x in values.items():
        if key.endswith(('_L', '_R')) or key in ('jawOpen', 'lipLowerDown', 'lipUpperUp', 'lipsPress', 'mouthNarrow', 'mouthWide', 'tongueUp', 'tongueOut'):
            v[key] = x
        else:
            v.setdefault(key + '_L', x)
            v.setdefault(key + '_R', x)
    if 'lipsUp' in values:                                            # old name
        v['lipUpperUp'] = max(v.get('lipUpperUp', 0.0), values['lipsUp'])
    for key, sk in R['keys'].items():
        sk.value = float(min(max(v.get(key, 0.0), 0.0), 1.0))
    jaw = R['parts'].get('jaw')
    if jaw is not None:
        jaw.rotation_euler.x = math.radians(JAW_DEG) * float(min(max(v.get('jawOpen', 0.0), 0.0), 1.0))
        T = R['parts']['teeth']
        kb = T['tongue'].data.shape_keys.key_blocks if T['tongue'].data.shape_keys else None
        if kb is not None:
            kb['up'].value = float(min(max(v.get('tongueUp', 0.0), 0.0), 1.1))
            kb['out'].value = float(min(max(v.get('tongueOut', 0.0), 0.0), 1.0))
    rest = R['lid_rest']
    for sd in 'RL':
        E = R['parts']['eye' + sd]
        g = R['eyes'][sd]
        look_x = v.get(f'eyeLookLeft_{sd}', 0.0) - v.get(f'eyeLookRight_{sd}', 0.0)
        look_z = v.get(f'eyeLookUp_{sd}', 0.0) - v.get(f'eyeLookDown_{sd}', 0.0)
        # 1 = 28 degrees of a real eye: the iris travels 12 mm x sin(angle) on a real eyeball; scaled to this eye
        ks = g.w / 0.030
        dx = E['rest_shift'][0] + 0.012 * ks * math.sin(math.radians(28.0) * look_x)
        dz = E['rest_shift'][1] + 0.012 * ks * math.sin(math.radians(28.0) * look_z) * 0.8
        eyes6.set_gaze(E, *eyes6.shift_to_gaze(E, dx, dz))
        closed = min(max(v.get(f'eyeClosed_{sd}', 0.0), 0.0), 1.0)
        squint = v.get(f'eyeSquint_{sd}', 0.0)
        wide = v.get(f'eyeWide_{sd}', 0.0)
        angry = max(v.get(f'browDown_{sd}', 0.0), 0.0)
        upper = rest * (1.0 - 0.8 * wide) + 0.22 * squint + 0.14 * angry - 0.45 * look_z * (1.0 if look_z < 0 else 0.35)
        upper = min(max(upper, 0.0), 0.9)
        upper = upper + (1.0 - upper) * closed
        lower = min(0.55 * squint + 0.20 * angry + 0.22 * closed, 0.22 + 0.5 * (1.0 - closed))
        set_lids(E['lids'], upper, lower)


def match_skin(R, **_):
    """Kept for callers: the lids now wear the skin's own material, there is nothing to match."""
    return R
