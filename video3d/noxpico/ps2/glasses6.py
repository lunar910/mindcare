"""Version 6 glasses (Nox): real, separate glasses - thin acetate front, transparent lenses, hinged temples, nose pads.

    import glasses6
    G = glasses6.build('nox.glasses')                 # dict, see build()
    G['root'].parent = head_object_or_bone_proxy      # origin of root = centre of the bridge, on the FRONT plane
    glasses6.set_lens(G, reflect=0.04, tint=(0.96, 0.98, 1.0))
    glasses6.set_frame(G, rgb=(70, 78, 76))

Convention (same as the cast): metres, the character faces -Y, +Z up, +X = the character's LEFT.
    root     empty.  Origin = centre of the bridge (x = 0, mid-height of the bridge bar), y = 0 = front plane of the frame at
             the bridge.  The front is tangent to the XZ plane there and faces -Y; the temples go back towards +Y.
             By default the front has a gentle face-form bend (cylinder of radius wrap_radius = 0.36 m about a vertical axis:
             the end pieces sit 6.5 mm behind the bridge); build(..., wrap_radius=0) gives a dead flat front in the XZ plane.
    frame    mesh: the front cut from one 4 mm plate (two rims + keyhole bridge + end pieces), rounded edges, 4 steel pins.
    lenses   mesh: two 1.6 mm lenses sitting in the middle of the rim depth.
    temples  mesh: two arms (butt against the back of the end pieces, splay out to clear the head, bend down behind the
             ear) + the two barrel hinges.
    pads     mesh: two silicone nose pads on short steel arms.
All four meshes are children of root with an identity transform (their vertices are in root space), carry analytic custom
normals (no modifier, no subdivision needed) and can be joined or re-parented freely.

No refraction anywhere: the lens is Transparent + Glossy mixed by a Schlick Fresnel, it casts no shadow, and it carries a
light-linked 'veil' (a soft window-shaped band of faint diffuse haze in the upper part of the lens) so that it still reads
as glass when the scene offers nothing bright to reflect.  See set_lens().
"""
import math
import warnings

import bpy
import numpy as np
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

FRAME_SRGB = (70, 78, 76)
LENS_TINT = (0.96, 0.98, 1.0)
_DESIGNS = {}


def _lin(c):
    """sRGB 0-255 -> linear 0-1."""
    return tuple((x / 255.0 / 12.92) if x / 255.0 <= 0.04045 else ((x / 255.0 + 0.055) / 1.055) ** 2.4 for x in c[:3])


# ======================================================================================================== 2D design
def _lens_outline(w, h, tilt_deg):
    """Dense closed outline (counter-clockwise, K x 2) of the LEFT lens opening in lens-local (u, v): +u = temple side,
    +v = up, centred on its bounding box which is exactly w x h.  A 'wayfarer-rectangular' rounded rectangle: nearly
    straight top, fuller bottom, bottom corners pulled in (more on the nose side), outer end tilted up."""
    a, b = 0.5 * w, 0.5 * h
    ti, to = 0.068 * w, 0.030 * w
    C = np.array([(-a, b), (a, b), (a - to, -b), (-a + ti, -b)])           # top-nose, top-temple, bottom-temple, bottom-nose
    bow = (0.012 * w, 0.020 * h, 0.034 * w, 0.020 * h)                     # outward sagitta of the top, temple, bottom, nose edge
    rad = (0.26 * h, 0.24 * h, 0.30 * h, 0.33 * h)                         # corner radii (mean 28 % of the height)

    def edge(i, s):
        A, B = C[i], C[(i + 1) % 4]
        d = B - A
        n = np.array([-d[1], d[0]]) / np.linalg.norm(d)                    # clockwise loop: left of travel = outside
        s = np.atleast_1d(np.asarray(s, float))[:, None]
        return A + s * d + 4 * bow[i] * s * (1 - s) * n, d + 4 * bow[i] * (1 - 2 * s) * n

    length = [np.linalg.norm(C[(i + 1) % 4] - C[i]) for i in range(4)]
    trim = []
    for i in range(4):
        e0 = (C[i] - C[i - 1]) / length[i - 1]
        e1 = (C[(i + 1) % 4] - C[i]) / length[i]
        phi = math.acos(float(np.clip(e0 @ e1, -1, 1)))
        trim.append(rad[i] * math.tan(phi / 2))
    pts = []
    for i in range(4):
        j = (i + 1) % 4
        s0, s1 = trim[i] / length[i], 1 - trim[j] / length[i]
        pts.append(edge(i, np.linspace(s0, s1, 90, endpoint=False))[0])
        P0, T0 = edge(i, s1)
        P3, T3 = edge(j, trim[j] / length[j])
        P0, P3 = P0[0], P3[0]
        T0, T3 = T0[0] / np.linalg.norm(T0[0]), T3[0] / np.linalg.norm(T3[0])
        phi = math.acos(float(np.clip(T0 @ T3, -1, 1)))
        r = np.linalg.norm(P3 - P0) / (2 * math.sin(phi / 2))
        k = 4.0 / 3.0 * math.tan(phi / 4) * r
        t = np.linspace(0, 1, 110, endpoint=False)[:, None]
        pts.append((1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * (P0 + T0 * k) + 3 * (1 - t) * t * t * (P3 - T3 * k) + t ** 3 * P3)
    P = np.vstack(pts)[::-1]                                               # counter-clockwise
    c, s = math.cos(math.radians(tilt_deg)), math.sin(math.radians(tilt_deg))
    P = P @ np.array([[c, s], [-s, c]])                                    # rotate by +tilt: the temple end goes up
    lo, hi = P.min(0), P.max(0)
    return (P - 0.5 * (lo + hi)) * (np.array([w, h]) / (hi - lo))


def _uniform(P, ds, closed):
    """Resample a polyline at a constant spacing ~ds.  Closed: n points, the first is not repeated."""
    Q = np.vstack([P, P[:1]]) if closed else np.asarray(P)
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    keep = np.concatenate([[True], seg > 1e-9])
    Q = Q[keep]
    L = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    n = max(16, int(round(L[-1] / ds)))
    t = np.linspace(0.0, L[-1], n, endpoint=not closed)
    return np.stack([np.interp(t, L, Q[:, 0]), np.interp(t, L, Q[:, 1])], 1)


def _adaptive(Q, closed, n, rho, ext=None, k=4):
    """Pick n points on the fine uniform polyline Q, denser where it curves (density ~ 1 + rho * curvature), and their
    unit normals on the RIGHT of the direction of travel (= outwards for a counter-clockwise loop).
    Open polylines keep both end points and need ext = (k points before, k points after) for the end tangents."""
    M = len(Q)
    Qe = np.vstack([Q[-k:], Q, Q[:k]]) if closed else np.vstack([ext[0], Q, ext[1]])
    ds = float(np.linalg.norm(Q[1] - Q[0]))
    T = Qe[2 * k:] - Qe[:-2 * k]
    T /= np.linalg.norm(T, axis=1)[:, None]
    ang = np.unwrap(np.arctan2(T[:, 1], T[:, 0]))
    kap = np.abs(np.gradient(ang)) / ds
    pad = np.concatenate([kap[-k:], kap, kap[:k]]) if closed else np.concatenate([kap[k:0:-1], kap, kap[-2:-k - 2:-1]])
    kap = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode='valid')
    wgt = 1.0 + rho * np.minimum(kap, 600.0)
    if closed:
        cum = np.concatenate([[0.0], np.cumsum(wgt)])
        f = np.interp(np.linspace(0.0, cum[-1], n, endpoint=False), cum, np.arange(M + 1))
    else:
        cum = np.concatenate([[0.0], np.cumsum(0.5 * (wgt[1:] + wgt[:-1]))])
        f = np.interp(np.linspace(0.0, cum[-1], n), cum, np.arange(M))
    i0 = np.floor(f).astype(int)
    fr = (f - i0)[:, None]
    i0 = i0 % M if closed else np.minimum(i0, M - 1)
    i1 = (i0 + 1) % M if closed else np.minimum(i0 + 1, M - 1)
    P = Q[i0] * (1 - fr) + Q[i1] * fr
    Tn = T[i0] * (1 - fr) + T[i1] * fr
    Tn /= np.linalg.norm(Tn, axis=1)[:, None]
    return P, np.stack([Tn[:, 1], -Tn[:, 0]], 1)


def _smin(a, b, k):
    """Polynomial smooth minimum: union of two distance fields with a fillet of size ~k in the concave junctions."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def _sd_box(P, c, half, r):
    q = np.abs(P - c) - (np.asarray(half) - r)
    return np.linalg.norm(np.maximum(q, 0.0), axis=1) + np.minimum(np.maximum(q[:, 0], q[:, 1]), 0.0) - r


class _Front:
    """The 2D outline of the front plate (in the XZ plane, before the wrap): the outer silhouette is the zero set of a
    signed distance field = smooth union of (both lens outlines grown by the rim width) + bridge bar + end-piece wings."""

    def __init__(self, lens_w, lens_h, bridge, hw, rim, tilt_deg):
        self.lens_w, self.lens_h, self.bridge, self.hw, self.rim = lens_w, lens_h, bridge, hw, rim
        self.L = _lens_outline(lens_w, lens_h, tilt_deg)
        self.c = np.array([0.5 * bridge + 0.5 * lens_w, 0.0])                # left lens centre (z = 0 for now)
        L = self.L
        self._A, self._D = L, np.roll(L, -1, 0) - L
        self._DD = (self._D ** 2).sum(1)
        self._pa, self._pr = np.arctan2(L[:, 1], L[:, 0]), np.hypot(L[:, 0], L[:, 1])
        self._rmin = float(self._pr.min())
        t = math.radians(tilt_deg)
        self.eu, self.ev = np.array([math.cos(t), math.sin(t)]), np.array([-math.sin(t), math.cos(t)])
        self.Rt = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])   # row vectors: p @ Rt = into the tilted frame
        # bridge bar: a little below the top line of the rims, the arch under it is the 'keyhole'
        self.t = t
        self.cap = float((L @ self.Rt)[:, 1].max()) + rim                   # the straight brow line (in the tilted lens frame)
        self.drop = 0.0010                                                  # saddle: the bridge top sits this much under it
        self.bar_h = 0.0054
        top = float(self._top(np.zeros(1))[0])
        self.bar_c = np.array([0.0, top + 0.003 - 0.5 * (self.bar_h + 0.003)])
        self.bar_half = (0.5 * bridge + rim, 0.5 * (self.bar_h + 0.003))
        self.kb = 0.0052
        # end-piece wing: its top continues the top line of the rim (straight brow bar), in the tilted lens frame
        v_top = float((L @ self.Rt)[:, 1].max())
        self.wing_h = 0.0066
        vmid = v_top + rim - 0.0002 - 0.5 * self.wing_h
        self.ext = 0.0015                                                   # the wing passes the hinge line by this much
        u1 = (hw + self.ext - self.c[0] + vmid * math.sin(t)) / math.cos(t)
        u0 = -0.30 * lens_w                                                 # the bar starts above the lens: one straight brow line
        self.wing_c = np.array([0.5 * (u0 + u1), vmid])
        self.wing_half = (0.5 * (u1 - u0), 0.5 * self.wing_h)
        self.kw = 0.0028
        self.hinge = self.c + self.eu * (u1 - self.ext) + self.ev * vmid    # centre of the wing on the hinge line
        self.x_end = float(self.c[0] + self.eu[0] * u1 + self.ev[0] * vmid)

    def _lens_sd(self, P):
        """Signed distance to the left lens outline, P in lens-local coordinates (exact to the dense polyline)."""
        out = np.full(len(P), -0.004)
        rr, aa = np.hypot(P[:, 0], P[:, 1]), np.arctan2(P[:, 1], P[:, 0])
        near = np.nonzero(rr > self._rmin - 0.004)[0]
        for i in range(0, len(near), 512):
            idx = near[i:i + 512]
            p = P[idx, None, :]
            t = np.clip(((p - self._A) * self._D).sum(2) / self._DD, 0.0, 1.0)
            q = self._A + t[..., None] * self._D
            out[idx] = np.sqrt(((p - q) ** 2).sum(2).min(1))
        inside = rr[near] < np.interp(aa[near], self._pa, self._pr, period=2 * math.pi)
        out[near] = np.where(inside, -out[near], out[near])
        return out

    def sd(self, P):
        Q = np.array(P, float)
        Q[:, 0] = np.abs(Q[:, 0])
        d = self._lens_sd(Q - self.c) - self.rim
        d = _smin(d, _sd_box(Q, self.bar_c, self.bar_half, 0.0015), self.kb)
        Qt = (Q - self.c) @ self.Rt
        d = _smin(d, _sd_box(Qt, self.wing_c, self.wing_half, 0.0022), self.kw)
        return np.maximum(d, Q[:, 1] - self._top(Q[:, 0]))

    def _top(self, x):
        """Top line of the front at |x|: the two straight brow lines (rising towards the temples) joined over the bridge
        by a shallow smooth saddle."""
        xs = np.sqrt(x * x + 0.003 ** 2)
        brow = (self.cap + math.sin(self.t) * (xs - self.c[0])) / math.cos(self.t)
        w = np.clip((np.abs(x) - 0.002) / 0.011, 0.0, 1.0)
        return brow - self.drop * (1.0 - w * w * (3 - 2 * w))

    def half_silhouette(self, cell=0.00025):
        """Marching squares on x >= 0: the outer contour from the apex of the arch (x = 0, under the bridge) round the
        left rim and the wing to the top of the bridge (x = 0).  Dense polyline, then snapped onto the zero set."""
        nx = int(math.ceil((self.x_end + 0.003) / cell))
        z0 = -0.5 * self.lens_h - self.rim - 0.004
        nz = int(math.ceil((self.lens_h + 2 * self.rim + 0.010) / cell))
        xs, zs = np.arange(nx + 1) * cell, z0 + np.arange(nz + 1) * cell
        X, Z = np.meshgrid(xs, zs, indexing='ij')
        F = self.sd(np.stack([X.ravel(), Z.ravel()], 1)).reshape(X.shape)
        ins = (F < 0).astype(int)
        code = ins[:-1, :-1] + 2 * ins[1:, :-1] + 4 * ins[1:, 1:] + 8 * ins[:-1, 1:]
        pts, adj = {}, {}

        def cross(key):
            if key not in pts:
                kind, i, j = key
                fa, fb = F[i, j], (F[i + 1, j] if kind == 0 else F[i, j + 1])
                t = fa / (fa - fb)
                pts[key] = (xs[i] + t * cell, zs[j]) if kind == 0 else (xs[i], zs[j] + t * cell)
            return key

        for i, j in zip(*np.nonzero((code > 0) & (code < 15))):
            i, j = int(i), int(j)
            B, R, T, Lf = (0, i, j), (1, i + 1, j), (0, i, j + 1), (1, i, j)
            for a, b in {1: [(Lf, B)], 2: [(B, R)], 3: [(Lf, R)], 4: [(R, T)], 5: [(Lf, T), (B, R)], 6: [(B, T)], 7: [(Lf, T)],
                         8: [(T, Lf)], 9: [(T, B)], 10: [(Lf, B), (R, T)], 11: [(T, R)], 12: [(R, Lf)], 13: [(R, B)],
                         14: [(B, Lf)]}[int(code[i, j])]:
                adj.setdefault(cross(a), []).append(cross(b))
                adj.setdefault(b, []).append(a)
        ends = sorted((k for k, v in adj.items() if len(v) == 1), key=lambda k: pts[k][1])
        if len(ends) != 2 or any(k[0] != 1 or k[1] != 0 for k in ends):
            raise RuntimeError('glasses6: the front silhouette does not close on the mid-plane (check the proportions)')
        chain, prev = [ends[0]], None
        while chain[-1] != ends[1]:
            nxt = [k for k in adj[chain[-1]] if k != prev]
            prev = chain[-1]
            chain.append(nxt[0])
        H = np.array([pts[k] for k in chain])
        e = 2e-5
        for _ in range(3):
            f = self.sd(H)
            gx = (self.sd(H + (e, 0)) - self.sd(H - (e, 0))) / (2 * e)
            gz = (self.sd(H + (0, e)) - self.sd(H - (0, e))) / (2 * e)
            g2 = np.maximum(gx * gx + gz * gz, 1e-12)
            H[1:-1] -= (np.stack([gx, gz], 1) * (f / g2)[:, None])[1:-1]
            for m in (0, -1):
                H[m, 1] -= f[m] / gz[m]
        H[0, 0] = H[-1, 0] = 0.0
        return H


def design(lens_w=0.047, lens_h=0.034, bridge=0.017, face_half_width=0.068, rim=0.0032, tilt_deg=1.8, n_half=152, n_hole=96,
           n_lens=64):
    """The 2D drawing of the front in root space (x, z), before the wrap.  Returns a dict of arrays:
    outer / outer_n (full silhouette, counter-clockwise, unit normals pointing out of the material), hole / hole_n (left
    lens opening, normals pointing out of the lens = into the rim), lens / lens_n (the same outline with fewer points, for
    the lens mesh), centre (left lens centre), hinge (centre of the left end piece on the hinge line), eu / ev (the
    tilted axes of the left lens) and the z extent of the bridge on the mid-plane."""
    key = (lens_w, lens_h, bridge, face_half_width, rim, tilt_deg, n_half, n_hole, n_lens)
    if key in _DESIGNS:
        return {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in _DESIGNS[key].items()}
    F = _Front(lens_w, lens_h, bridge, face_half_width, rim, tilt_deg)
    H = F.half_silhouette()
    mid = 0.5 * (H[0, 1] + H[-1, 1])                                       # mid-height of the bridge -> z = 0
    shift = np.array([0.0, -mid])
    Q = _uniform(H, 1e-4, False)
    mir = np.array([-1.0, 1.0])
    P, N = _adaptive(Q, False, n_half, 0.006, ext=(Q[4:0:-1] * mir, Q[-2:-6:-1] * mir))
    P[0, 0] = P[-1, 0] = 0.0
    N[0], N[-1] = (0.0, -1.0), (0.0, 1.0)
    outer = np.vstack([P, P[-2:0:-1] * mir]) + shift
    outer_n = np.vstack([N, N[-2:0:-1] * mir])
    Lq = _uniform(F.L, 1e-4, True)
    hole, hole_n = _adaptive(Lq, True, n_hole, 0.006)
    lens, lens_n = _adaptive(Lq, True, n_lens, 0.004)
    c = F.c + shift
    D = {'outer': outer, 'outer_n': outer_n, 'hole': hole + c, 'hole_n': hole_n, 'lens': lens + c, 'lens_n': lens_n,
         'centre': c, 'hinge': F.hinge + shift, 'eu': F.eu, 'ev': F.ev, 'bridge_z': (float(H[0, 1] - mid), float(H[-1, 1] - mid)),
         'x_end': F.x_end}
    _DESIGNS[key] = D
    return {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in D.items()}


# ======================================================================================================== mesh kit
class _Geo:
    """Vertex / normal / face accumulator (one mesh object)."""

    def __init__(self):
        self.V, self.N, self.F, self.M, self.count = [], [], [], [], 0

    def verts(self, V, N):
        V = np.asarray(V, float).reshape(-1, 3)
        N = np.asarray(N, float).reshape(-1, 3)
        base = self.count
        self.V.append(V)
        self.N.append(N)
        self.count += len(V)
        return base

    def face(self, idx, mat=0):
        self.F.append(tuple(int(i) for i in idx))
        self.M.append(mat)

    def grid(self, rows, close=True, mat=0):
        """Quads between consecutive rows of vertex indices (each row a sequence of the same length)."""
        for r0, r1 in zip(rows, rows[1:]):
            n = len(r0)
            for i in range(n if close else n - 1):
                j = (i + 1) % n
                self.face((r0[i], r0[j], r1[j], r1[i]), mat)

    def arrays(self):
        V, N = np.vstack(self.V), np.vstack(self.N)
        self.V, self.N = [V], [N]
        return V, N

    def wrap(self, R):
        """Bend everything added so far round a vertical cylinder of radius R (shear along Y: y += sag(x))."""
        if not R:
            return
        V, N = self.arrays()
        s = np.sqrt(R * R - V[:, 0] ** 2)
        V[:, 1] += R - s
        N[:, 0] -= V[:, 0] / s * N[:, 1]

    def add_mirrored(self, other):
        """Append a copy of another _Geo mirrored in x (the winding is repaired when the object is made)."""
        V, N = other.arrays()
        base = self.verts(V * (-1, 1, 1), N * (-1, 1, 1))
        for f, m in zip(other.F, other.M):
            self.face([base + i for i in f], m)

    def add(self, other):
        V, N = other.arrays()
        base = self.verts(V, N)
        for f, m in zip(other.F, other.M):
            self.face([base + i for i in f], m)

    def triangles(self):
        return sum(len(f) - 2 for f in self.F)


def _make_object(name, G, mats, collection, parent, attrs=None):
    V, N = G.arrays()
    N = N / np.maximum(np.linalg.norm(N, axis=1), 1e-12)[:, None]
    faces = []
    for f in G.F:                                                          # wind every face to agree with its vertex normals
        p = V[list(f)]
        nrm = np.cross(p - np.roll(p, 1, 0), np.roll(p, -1, 0) - p).sum(0)
        faces.append(f if nrm @ N[list(f)].sum(0) >= 0 else f[::-1])
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], faces)
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set('material_index', G.M)
    me.polygons.foreach_set('use_smooth', [True] * len(faces))
    for an, values in (attrs or {}).items():
        at = me.attributes.new(an, 'FLOAT', 'POINT')
        at.data.foreach_set('value', np.asarray(values, np.float32))
    me.normals_split_custom_set_from_vertices(N.tolist())
    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.parent = parent
    return ob


def _sag(x, R):
    return (R - math.sqrt(R * R - x * x)) if R else 0.0


def _slope(x, R):
    return (x / math.sqrt(R * R - x * x)) if R else 0.0


def _keys(s, keys):
    """Smooth piecewise interpolation through (position, value) keys."""
    if s <= keys[0][0]:
        return keys[0][1]
    for (s0, v0), (s1, v1) in zip(keys, keys[1:]):
        if s <= s1:
            t = (s - s0) / (s1 - s0)
            return v0 + (v1 - v0) * t * t * (3 - 2 * t)
    return keys[-1][1]


def _rrect(a, b, rc, seg=3):
    """Rounded rectangle section, half sizes a x b: rows of (x, y, nx, ny), counter-clockwise, 4 * (seg + 1) points."""
    out = []
    for q, (sx, sy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        for k in range(seg + 1):
            ph = (q + k / seg) * 0.5 * math.pi
            out.append((sx * (a - rc) + rc * math.cos(ph), sy * (b - rc) + rc * math.sin(ph), math.cos(ph), math.sin(ph)))
    return np.array(out)


def _barrel(G, x, y, z0, z1, r, c, seg=14, mat=0):
    """Small cylinder along Z with chamfered edges and flat caps (hard edges: every band has its own vertices)."""
    a = np.arange(seg) * 2 * math.pi / seg
    ca, sa = np.cos(a), np.sin(a)
    k = math.sqrt(0.5)

    def ring(rr, zz, nr, nz):
        V = np.stack([x + rr * ca, y + rr * sa, np.full(seg, zz)], 1)
        return G.verts(V, np.stack([nr * ca, nr * sa, np.full(seg, nz)], 1)) + np.arange(seg)

    G.face(ring(r - c, z0, 0.0, -1.0), mat)
    G.grid([ring(r - c, z0, k, -k), ring(r, z0 + c, k, -k)], True, mat)
    G.grid([ring(r, z0 + c, 1.0, 0.0), ring(r, z1 - c, 1.0, 0.0)], True, mat)
    G.grid([ring(r, z1 - c, k, k), ring(r - c, z1, k, k)], True, mat)
    G.face(ring(r - c, z1, 0.0, 1.0), mat)


def _box(G, c, half, axes, mat=0):
    """Box with flat faces; axes = three unit vectors (rows)."""
    c, axes = np.asarray(c, float), np.asarray(axes, float)
    for k in range(3):
        for sgn in (-1.0, 1.0):
            u, v = axes[(k + 1) % 3] * half[(k + 1) % 3], axes[(k + 2) % 3] * half[(k + 2) % 3]
            o = c + sgn * axes[k] * half[k]
            b = G.verts([o - u - v, o + u - v, o + u + v, o - u + v], [sgn * axes[k]] * 4)
            G.face((b, b + 1, b + 2, b + 3), mat)


def _dome(G, c, axis, r, h, seg=10, mat=0):
    """A pin head: a shallow dome of radius r and height h on the plane through c with normal axis."""
    c, axis = np.asarray(c, float), np.asarray(axis, float) / np.linalg.norm(axis)
    e1 = np.cross(axis, (0.0, 0.0, 1.0))
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    a = np.arange(seg) * 2 * math.pi / seg
    rad = np.cos(a)[:, None] * e1 + np.sin(a)[:, None] * e2
    r0 = G.verts(c + r * rad, 0.8 * rad + 0.6 * axis) + np.arange(seg)
    r1 = G.verts(c + 0.62 * r * rad + 0.78 * h * axis, 0.3 * rad + 0.95 * axis) + np.arange(seg)
    p = G.verts([c + h * axis], [axis])
    G.grid([r0, r1], True, mat)
    for i in range(seg):
        G.face((r1[i], r1[(i + 1) % seg], p), mat)


def _tube(G, path, radius, seg=8, mat=0):
    """Round wire through the points of path (k x 3), open ends."""
    path = np.asarray(path, float)
    T = np.gradient(path, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    a = np.arange(seg) * 2 * math.pi / seg
    rows = []
    for p, t in zip(path, T):
        e1 = np.cross(t, (0.0, 0.0, 1.0))
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(t, e1)
        rad = np.cos(a)[:, None] * e1 + np.sin(a)[:, None] * e2
        rows.append(G.verts(p + radius * rad, rad) + np.arange(seg))
    G.grid(rows, True, mat)


def _bezier(p0, p1, p2, p3, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3


# ======================================================================================================== the parts
def _build_front(G, D, depth, r_out, r_hole, arc=3):
    """The front plate: every outline is swept through a rounded profile (front edge arc, wall, back edge arc) and the
    flat front / back faces are triangulated between the inset outlines."""
    mir = np.array([-1.0, 1.0])
    loops = [(D['outer'], D['outer_n'], r_out), (D['hole'], -D['hole_n'], r_hole),
             (D['hole'][::-1] * mir, -D['hole_n'][::-1] * mir, r_hole)]
    front, back = [], []
    for P, N, (rf, rb) in loops:
        n = len(P)
        rows = []
        for face_sign, r, y0 in ((-1.0, rf, 0.0), (1.0, rb, depth)):
            for j in range(arc + 1):
                th = 0.5 * math.pi * (j / arc if face_sign < 0 else 1 - j / arc)
                xz = P - r * (1 - math.sin(th)) * N
                y = y0 - face_sign * r * (1 - math.cos(th))
                V = np.stack([xz[:, 0], np.full(n, y), xz[:, 1]], 1)
                Nn = np.stack([N[:, 0] * math.sin(th), np.full(n, face_sign * math.cos(th)), N[:, 1] * math.sin(th)], 1)
                rows.append(G.verts(V, Nn) + np.arange(n))
        G.grid(rows, True, 0)
        front.append((rows[0], P - rf * N))
        back.append((rows[-1], P - rb * N))
    for cap in (front, back):
        ids = np.concatenate([r for r, _ in cap])
        tris = tessellate_polygon([[Vector((float(x), float(z), 0.0)) for x, z in xz] for _, xz in cap])
        for t in tris:
            G.face(ids[list(t)], 0)
    return len(tris)


def _build_lens(D, depth, thick, r_geo, r_front, r_back):
    """LEFT lens (flat design space, before the wrap) -> (_Geo, rim attribute).  A 1.6 mm meniscus sitting in the middle of
    the rim depth, its edge 0.6 mm inside the rim.  The geometry is almost flat (radius r_geo, so the edge stays in the
    groove); the SHADING normals are those of a real lens (front radius r_front, back radius r_back) so reflections curve."""
    G = _Geo()
    P, N, c = D['lens'], D['lens_n'], D['centre']
    n = len(P)
    q_edge = P + 0.0006 * N - c
    r2 = (q_edge ** 2).sum(1)
    c0 = (r2.max() + r2.min()) / (4 * r_geo)
    inner = P - 0.0013 * N - c
    rings = [(P + 0.0004 * N - c, 1.0), (P - c, 1.0), (P - 0.0005 * N - c, 0.35), (inner, 0.0), (0.75 * inner, 0.0),
             (0.5 * inner, 0.0), (0.25 * inner, 0.0)]
    attr = []
    for sgn, rs in ((-1.0, r_front), (1.0, r_back)):
        y_mid = 0.5 * depth + sgn * 0.5 * thick

        def surf(q):
            y = y_mid - c0 + (q ** 2).sum(1) / (2 * r_geo)
            V = np.stack([q[:, 0] + c[0], y, q[:, 1] + c[1]], 1)
            Nn = np.stack([-sgn * q[:, 0] / rs, np.full(len(q), sgn), -sgn * q[:, 1] / rs], 1)
            return V, Nn

        V, _ = surf(q_edge)
        V[:, 1] -= sgn * 0.0002
        rows = [G.verts(V, np.stack([N[:, 0], np.full(n, 0.3 * sgn), N[:, 1]], 1)) + np.arange(n)]
        attr += [1.0] * n
        for q, a in rings:
            rows.append(G.verts(*surf(q)) + np.arange(n))
            attr += [a] * n
        G.grid(rows, True, 0)
        p = G.verts(*surf(np.zeros((1, 2))))
        attr.append(0.0)
        for i in range(n):
            G.face((rows[-1][i], rows[-1][(i + 1) % n], p), 0)
        if sgn < 0:
            edge_f = rows[0]
        else:
            G.grid([edge_f, rows[0]], True, 0)
    return G, attr, c0


def _build_temple(hw, y0, zh, back_n, ear, tip, h0, bend_deg=38.0):
    """LEFT temple -> (_Geo, tip position).  Rounded-rectangle section swept from the back of the end piece (first section
    lying in the plane of that face, normal back_n) straight to the ear point, then bending down to the tip."""
    G = _Geo()
    P0, E, T = np.array([hw, y0, zh]), np.asarray(ear, float), np.asarray(tip, float)
    d0 = (E - P0) / np.linalg.norm(E - P0)
    a = math.radians(bend_deg)
    d1 = np.array([-0.12, math.cos(a), -math.sin(a)])
    d1 /= np.linalg.norm(d1)
    dist = np.linalg.norm(T - E)
    path = np.vstack([P0 + np.linspace(0, 1, 60, endpoint=False)[:, None] * (E - P0),
                      _bezier(E, E + d0 * 0.42 * dist, T - d1 * 0.36 * dist, T, 80)])
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    L = float(cum[-1])
    tan = np.gradient(path, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    hk = [(0.0, h0), (0.030, 0.0044), (L - 0.036, 0.0044), (L - 0.012, 0.0054), (L, 0.0054)]
    tk = [(0.0, 0.0029), (0.028, 0.0023), (L, 0.0024)]
    r_tip = 0.5 * hk[-1][1]
    stations = [0.0, 0.0006, 0.0015, 0.003, 0.005, 0.008] + list(np.arange(0.012, L - r_tip - 0.002, 0.0034)) + [L - r_tip]
    zup = np.array([0.0, 0.0, 1.0])

    def frame(s):
        p = np.array([np.interp(s, cum, path[:, k]) for k in range(3)])
        t = np.array([np.interp(s, cum, tan[:, k]) for k in range(3)])
        t /= np.linalg.norm(t)
        w = min(1.0, s / 0.008)
        w = w * w * (3 - 2 * w)
        d = (1 - w) * np.asarray(back_n) + w * t
        d /= np.linalg.norm(d)
        sv = np.cross(d, zup)
        sv /= np.linalg.norm(sv)
        return p, t, d, sv, np.cross(sv, d)

    rows = []
    for s in stations:
        p, t, d, sv, hv = frame(s)
        a_, b_ = 0.5 * _keys(s, tk), 0.5 * _keys(s, hk)
        S = _rrect(a_, b_, 0.86 * a_)
        V = p + S[:, 0:1] * sv + S[:, 1:2] * hv
        Nn = S[:, 2:3] * sv + S[:, 3:4] * hv
        if s == 0.0:
            b = G.verts(V, np.tile(-d, (len(S), 1)))
            G.face(b + np.arange(len(S)), 0)                                # butt cap (hidden against the end piece)
        rows.append(G.verts(V, Nn) + np.arange(len(S)))
    p, t, d, sv, hv = frame(L - r_tip)
    a_, b_ = 0.5 * _keys(L, tk), 0.5 * _keys(L, hk)
    for k in range(1, 5):
        al = k / 5 * 0.5 * math.pi
        S = _rrect(a_ * math.cos(al), b_ * math.cos(al), 0.86 * a_ * math.cos(al))
        V = p + t * r_tip * math.sin(al) + S[:, 0:1] * sv + S[:, 1:2] * hv
        Nn = math.cos(al) * (S[:, 2:3] * sv + S[:, 3:4] * hv) + math.sin(al) * t
        rows.append(G.verts(V, Nn) + np.arange(len(S)))
    G.grid(rows, True, 0)
    pole = G.verts([p + t * r_tip], [t])
    for i in range(len(S)):
        G.face((rows[-1][i], rows[-1][(i + 1) % len(S)], pole), 0)
    # two pin heads on the outer face, just behind the hinge
    p, t, d, sv, hv = frame(0.0048)
    for dz in (-0.0015, 0.0015):
        _dome(G, p + sv * (0.5 * _keys(0.0048, tk) - 0.00003) + hv * dz, sv, 0.00062, 0.00013, mat=1)
    return G, path[-1]


def _build_hinge(G, hw, y_back, zh, back_n, tdir, thick):
    """LEFT hinge (steel): three stacked knuckles in the inside corner between end piece and temple, a screw head, and
    the two leaves (one on the back of the end piece, one on the inner face of the temple)."""
    bn, td = np.asarray(back_n, float), np.asarray(tdir, float)
    along = np.array([bn[1], -bn[0], 0.0])                                  # along the back face of the end piece, towards +x
    side = np.array([td[1], -td[0], 0.0])
    side /= np.linalg.norm(side)                                           # across the temple, outwards
    tup = np.cross(side, td)
    P = np.array([hw, y_back, zh])
    xk = hw - 0.5 * thick - 0.0009
    yk = y_back + (xk - hw) * along[1] / along[0] + 0.0007
    for z0, z1 in ((-0.0026, -0.0009), (-0.0008, 0.0008), (0.0009, 0.0026)):
        _barrel(G, xk, yk, zh + z0, zh + z1, 0.00118, 0.00016, mat=1)
    _barrel(G, xk, yk, zh + 0.0026, zh + 0.00285, 0.00085, 0.0001, seg=10, mat=1)
    _box(G, P - along * 0.0050 + bn * 0.0001, (0.0026, 0.00028, 0.0017), (along, bn, (0.0, 0.0, 1.0)), mat=1)
    _box(G, P + td * 0.0046 - side * (0.5 * thick - 0.00002), (0.00028, 0.0030, 0.0017), (side, td, tup), mat=1)
    return (xk, yk, zh)


def _build_pad(D, depth, bridge, wrap, rim, splay_deg=30.0, frontal_deg=18.0):
    """LEFT nose pad (material 0, clear silicone) on its steel arm (material 1) -> (_Geo, pad centre)."""
    G = _Geo()
    c = D['centre']
    pc = np.array([0.5 * bridge - 0.0018, depth + 0.0055, c[1] + 0.0035])
    sp, fa = math.radians(splay_deg), math.radians(frontal_deg)
    Rz = np.array([[math.cos(-sp), -math.sin(-sp), 0], [math.sin(-sp), math.cos(-sp), 0], [0, 0, 1]])
    Ry = np.array([[math.cos(-fa), 0, math.sin(-fa)], [0, 1, 0], [-math.sin(-fa), 0, math.cos(-fa)]])
    R = Ry @ Rz                                                             # local x = thickness (contact face at -x), y = width, z = height
    tx, wy, hz = 0.0011, 0.0034, 0.0062
    rings, segs = 9, 16
    rows = []
    for i in range(1, rings):
        lat = -0.5 * math.pi + math.pi * i / rings
        lon = np.arange(segs) * 2 * math.pi / segs
        sx, sy, sz = math.cos(lat) * np.cos(lon), math.cos(lat) * np.sin(lon), np.full(segs, math.sin(lat))
        loc = np.stack([tx * np.sign(sx) * np.abs(sx) ** 0.75, wy * (1 - 0.16 * sz) * sy, hz * sz], 1)
        nrm = np.stack([sx / tx, sy / wy, sz / hz], 1)
        rows.append(G.verts(pc + loc @ R.T, nrm @ R.T) + np.arange(segs))
    G.grid(rows, True, 0)
    for row, sz in ((rows[0], -1.0), (rows[-1], 1.0)):
        p = G.verts([pc + R @ np.array([0.0, 0.0, hz * sz])], [R @ np.array([0.0, 0.0, sz])])
        for i in range(segs):
            G.face((row[i], row[(i + 1) % segs], p), 0)
    # arm: from the back of the rim (nose side, a little above the pad centre) to the outer face of the pad
    P, N = D['hole'], D['hole_n']
    nose = np.nonzero(N[:, 0] < -0.6)[0]
    k = nose[np.argmin(np.abs(P[nose, 1] - (pc[2] + 0.0040)))]
    a_xz = P[k] + 0.5 * rim * N[k]
    A = np.array([a_xz[0], _sag(a_xz[0], wrap) + depth - 0.0004, a_xz[1]])
    n_out = R @ np.array([1.0, 0.0, 0.0])
    B = pc + n_out * (tx - 0.0002)
    _tube(G, _bezier(A, A + (0.0, 0.0034, 0.0), B + n_out * 0.0028, B, 12), 0.00042, mat=1)
    _box(G, pc + n_out * tx, (0.00045, 0.0011, 0.0019), (R[:, 0], R[:, 1], R[:, 2]), mat=1)
    return G, pc


# ======================================================================================================== materials
def _new_material(name):
    m = bpy.data.materials.new(name)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        m.use_nodes = True
    m.node_tree.nodes.clear()
    if hasattr(m, 'use_transparent_shadow'):
        m.use_transparent_shadow = True
    return m, m.node_tree


def _node(nt, kind, name=None, **props):
    n = nt.nodes.new(kind)
    if name:
        n.name = n.label = name
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _value(nt, name, v):
    n = _node(nt, 'ShaderNodeValue', name)
    n.outputs[0].default_value = v
    return n.outputs[0]


def _rgb(nt, name, c):
    n = _node(nt, 'ShaderNodeRGB', name)
    n.outputs[0].default_value = (c[0], c[1], c[2], 1.0)
    return n.outputs[0]


def _math(nt, op, *args, clamp=False):
    n = _node(nt, 'ShaderNodeMath', operation=op, use_clamp=clamp)
    for sock, a in zip(n.inputs, args):
        if isinstance(a, (int, float)):
            sock.default_value = a
        else:
            nt.links.new(a, sock)
    return n.outputs[0]


def _mix_shader(nt, fac, a, b):
    n = _node(nt, 'ShaderNodeMixShader')
    if isinstance(fac, (int, float)):
        n.inputs[0].default_value = fac
    else:
        nt.links.new(fac, n.inputs[0])
    nt.links.new(a, n.inputs[1])
    nt.links.new(b, n.inputs[2])
    return n.outputs[0]


def _shadow_through(nt, shader, colour_socket_or_rgb):
    """Shadow rays see a (coloured) Transparent BSDF instead of the surface: a translucent or absent shadow, no refraction."""
    tr = _node(nt, 'ShaderNodeBsdfTransparent')
    if isinstance(colour_socket_or_rgb, tuple):
        tr.inputs['Color'].default_value = tuple(colour_socket_or_rgb) + (1.0,)
    else:
        nt.links.new(colour_socket_or_rgb, tr.inputs['Color'])
    lp = _node(nt, 'ShaderNodeLightPath')
    out = _node(nt, 'ShaderNodeOutputMaterial')
    nt.links.new(_mix_shader(nt, lp.outputs['Is Shadow Ray'], shader, tr.outputs[0]), out.inputs['Surface'])


def acetate_material(name, rgb=FRAME_SRGB, rough=0.25, coat=0.5):
    """Smoke-grey translucent acetate WITHOUT transmission: a dark glossy Principled with a clear coat, lighter towards the
    silhouette (thin material lets light through), a little diffuse back-lighting and a grey, not black, shadow."""
    m, nt = _new_material(name)
    base = _rgb(nt, 'frame_rgb', _lin(rgb))
    edge = _rgb(nt, 'edge_rgb', _lin(tuple(min(255, c * 1.75 + 14) for c in rgb)))
    lw = _node(nt, 'ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    fac = _math(nt, 'MULTIPLY', _math(nt, 'POWER', lw.outputs['Facing'], 1.6), 0.6, clamp=True)
    mix = _node(nt, 'ShaderNodeMix', data_type='RGBA')
    nt.links.new(fac, mix.inputs[0])
    nt.links.new(base, mix.inputs[6])
    nt.links.new(edge, mix.inputs[7])
    b = _node(nt, 'ShaderNodeBsdfPrincipled', 'acetate')
    nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['IOR'].default_value = 1.49
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = 0.05
    tl = _node(nt, 'ShaderNodeBsdfTranslucent')
    nt.links.new(edge, tl.inputs['Color'])
    surf = _mix_shader(nt, _value(nt, 'translucency', 0.10), b.outputs[0], tl.outputs[0])
    _shadow_through(nt, surf, _rgb(nt, 'shadow_rgb', (0.42, 0.47, 0.45)))
    return m


def lens_material(name, reflect=0.04, tint=LENS_TINT):
    """Glass without refraction, see set_lens() for the parameters (all are named Value / RGB nodes)."""
    m, nt = _new_material(name)
    geo = _node(nt, 'ShaderNodeNewGeometry')
    lw = _node(nt, 'ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    f0 = _value(nt, 'reflect', reflect)
    fres = _math(nt, 'MULTIPLY_ADD', _math(nt, 'POWER', lw.outputs['Facing'], 5.0), _math(nt, 'SUBTRACT', 1.0, f0), f0)
    back = _value(nt, 'back_reflect', 0.25)                                 # the inner surface seen through the lens reflects less
    fres = _math(nt, 'MULTIPLY', fres, _math(nt, 'MULTIPLY_ADD', geo.outputs['Backfacing'], _math(nt, 'SUBTRACT', back, 1.0), 1.0),
                 clamp=True)
    rim = _node(nt, 'ShaderNodeAttribute', attribute_name='rim')
    tmix = _node(nt, 'ShaderNodeMix', data_type='RGBA')
    rim_fac = rim.outputs[2]                                               # 'Factor'
    nt.links.new(_math(nt, 'MULTIPLY', rim_fac, _value(nt, 'edge_dark', 0.35)), tmix.inputs[0])
    nt.links.new(_rgb(nt, 'tint', [math.sqrt(c) for c in tint]), tmix.inputs[6])
    nt.links.new(_rgb(nt, 'edge_rgb', (0.62, 0.68, 0.68)), tmix.inputs[7])
    tr = _node(nt, 'ShaderNodeBsdfTransparent')
    nt.links.new(tmix.outputs[2], tr.inputs['Color'])
    gl = _node(nt, 'ShaderNodeBsdfGlossy')
    gl.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    nt.links.new(_value(nt, 'rough', 0.10), gl.inputs['Roughness'])
    surf = _mix_shader(nt, fres, tr.outputs[0], gl.outputs[0])
    # veil: a soft band of faint diffuse haze placed by the lens normal (a little by the view direction), in LENS space
    nl = _node(nt, 'ShaderNodeVectorTransform', vector_type='NORMAL', convert_from='WORLD', convert_to='OBJECT')
    il = _node(nt, 'ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='WORLD', convert_to='OBJECT')
    nt.links.new(geo.outputs['Normal'], nl.inputs['Vector'])
    nt.links.new(geo.outputs['Incoming'], il.inputs['Vector'])
    sn, si = _node(nt, 'ShaderNodeSeparateXYZ'), _node(nt, 'ShaderNodeSeparateXYZ')
    for src, dst in ((nl, sn), (il, si)):                                   # unit vectors whatever the scale of the object
        nrm = _node(nt, 'ShaderNodeVectorMath', operation='NORMALIZE')
        nt.links.new(src.outputs['Vector'], nrm.inputs[0])
        nt.links.new(nrm.outputs['Vector'], dst.inputs['Vector'])
    follow = _math(nt, 'MULTIPLY', _value(nt, 'veil_follow', 0.25), -1.0)
    qz = _math(nt, 'MULTIPLY_ADD', si.outputs['Z'], follow, _math(nt, 'MULTIPLY', sn.outputs['Z'], 2.0))
    qx = _math(nt, 'MULTIPLY_ADD', si.outputs['X'], follow, _math(nt, 'MULTIPLY', sn.outputs['X'], 2.0))
    q = _math(nt, 'MULTIPLY_ADD', qx, _value(nt, 'veil_slant', -0.12), qz)
    soft = _value(nt, 'veil_soft', 0.035)
    band = None
    for nm, v, lo, hi in (('veil_low', 0.155, 0.0, 1.0), ('veil_high', 0.235, 1.0, 0.0)):
        p = _value(nt, nm, v)
        mr = _node(nt, 'ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        nt.links.new(q, mr.inputs['Value'])
        nt.links.new(_math(nt, 'SUBTRACT', p, soft), mr.inputs['From Min'])
        nt.links.new(_math(nt, 'ADD', p, soft), mr.inputs['From Max'])
        mr.inputs['To Min'].default_value, mr.inputs['To Max'].default_value = lo, hi
        band = mr.outputs['Result'] if band is None else _math(nt, 'MULTIPLY', band, mr.outputs['Result'])
    veil = _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', band, _math(nt, 'LESS_THAN', sn.outputs['Y'], 0.0)), _value(nt, 'veil', 0.18))
    veil = _math(nt, 'MAXIMUM', veil, _math(nt, 'MULTIPLY', rim_fac, _value(nt, 'edge_haze', 0.22)))   # ground edge of the lens
    veil = _math(nt, 'MULTIPLY', veil, _math(nt, 'SUBTRACT', 1.0, geo.outputs['Backfacing']), clamp=True)
    df = _node(nt, 'ShaderNodeBsdfDiffuse')
    nt.links.new(_rgb(nt, 'veil_rgb', (0.9, 0.95, 1.0)), df.inputs['Color'])
    surf = _mix_shader(nt, veil, surf, df.outputs[0])
    _shadow_through(nt, surf, (1.0, 1.0, 1.0))
    return m


def steel_material(name):
    m, nt = _new_material(name)
    b = _node(nt, 'ShaderNodeBsdfPrincipled', 'steel')
    b.inputs['Base Color'].default_value = (0.58, 0.59, 0.61, 1.0)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.32
    out = _node(nt, 'ShaderNodeOutputMaterial')
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    return m


def pad_material(name):
    """Clear silicone without transmission: light grey, glossy, see-through in the middle (alpha), a faint shadow."""
    m, nt = _new_material(name)
    lw = _node(nt, 'ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    b = _node(nt, 'ShaderNodeBsdfPrincipled', 'pad')
    b.inputs['Base Color'].default_value = tuple(_lin((206, 210, 208))) + (1.0,)
    b.inputs['Roughness'].default_value = 0.14
    b.inputs['Coat Weight'].default_value = 0.3
    nt.links.new(_math(nt, 'MULTIPLY_ADD', _math(nt, 'POWER', lw.outputs['Facing'], 1.3), 0.55, _value(nt, 'pad_alpha', 0.42),
                       clamp=True), b.inputs['Alpha'])
    _shadow_through(nt, b.outputs[0], (0.8, 0.82, 0.82))
    return m


def _set(mat, name, v):
    n = mat.node_tree.nodes[name]
    if n.bl_idname == 'ShaderNodeRGB':
        n.outputs[0].default_value = (v[0], v[1], v[2], 1.0)
    else:
        n.outputs[0].default_value = v


def set_lens(parts, reflect=0.04, tint=LENS_TINT, rough=None, veil=None, veil_band=None, veil_rgb=None, veil_follow=None,
             veil_slant=None, edge_dark=None, edge_haze=None, back_reflect=None):
    """Lens look.  parts = the dict returned by build() (or a lens material).
    reflect      mirror reflectance facing the surface (0.04 = bare glass, 0.01 = coated); Schlick, rises to 1 at grazing.
    tint         LINEAR rgb transmitted through the whole lens (both surfaces together).
    rough        roughness of the reflection (default 0.10: soft-edged reflections of the lamps).
    veil         0..1 strength of the soft window band of diffuse haze (default 0.18; 0 = none).  It is lit by the scene
                 lights like any diffuse surface, so it is noise-free and darkens with the scene.
    veil_band    (low, high): band limits in 'reflection slope' units = 2 * height above the lens centre / 0.13 m
                 (default (0.155, 0.235) = from 10 to 15 mm above the centre for a camera at eye level; the edges are
                 softened over +-veil_soft = 0.035, node 'veil_soft').
    veil_follow  how much the band slides with the view direction (0 = painted on the lens, 1 = a true reflection; 0.25).
    veil_slant   slope of the band (default -0.12: it rises towards the character's left).
    edge_dark    0..1 darkening of the outer 1.3 mm of the lens (the thick edge of a real lens; default 0.35)
    edge_haze    0..1 diffuse haze on the same border (the ground edge of the glass catching the light; default 0.22).
    back_reflect reflectance factor of a surface seen from inside the glass (default 0.25)."""
    m = parts['materials']['lens'] if isinstance(parts, dict) else parts
    _set(m, 'reflect', reflect)
    _set(m, 'tint', [math.sqrt(max(c, 0.0)) for c in tint])
    for nm, v in (('rough', rough), ('veil', veil), ('veil_rgb', veil_rgb), ('veil_follow', veil_follow),
                  ('veil_slant', veil_slant), ('edge_dark', edge_dark), ('edge_haze', edge_haze), ('back_reflect', back_reflect)):
        if v is not None:
            _set(m, nm, v)
    if veil_band is not None:
        _set(m, 'veil_low', veil_band[0])
        _set(m, 'veil_high', veil_band[1])
    return m


def set_frame(parts, rgb=FRAME_SRGB, rough=None, coat=None, translucency=None, shadow_rgb=None):
    """Acetate look: rgb = sRGB 0-255 base colour (the lighter edge colour follows), roughness, coat weight, weight of the
    diffuse back-lighting, LINEAR rgb let through per surface by the shadow (two surfaces per crossing)."""
    m = parts['materials']['frame'] if isinstance(parts, dict) else parts
    _set(m, 'frame_rgb', _lin(rgb))
    _set(m, 'edge_rgb', _lin(tuple(min(255, c * 1.75 + 14) for c in rgb)))
    b = m.node_tree.nodes['acetate']
    if rough is not None:
        b.inputs['Roughness'].default_value = rough
    if coat is not None:
        b.inputs['Coat Weight'].default_value = coat
    if translucency is not None:
        _set(m, 'translucency', translucency)
    if shadow_rgb is not None:
        _set(m, 'shadow_rgb', shadow_rgb)
    return m


# ======================================================================================================== build
def build(name, lens_w=0.047, lens_h=0.034, bridge=0.017, temple_len=0.115, face_half_width=0.068, collection=None,
          rim=0.0032, depth=0.0040, wrap_radius=0.36, head_half_width=0.075, tilt_deg=1.8, ear_drop=0.017,
          temple_pitch_deg=0.0):
    """Build the glasses at the origin.  Returns a dict:
        'root'      empty (see the module doc for the origin / axes)
        'frame', 'lenses', 'temples', 'pads'   the four meshes; 'objects' = the same four in a list
        'lens_centres'  [(x, z) of the RIGHT-eye lens centre (x < 0), (x, z) of the LEFT] in root space
        'lens_y'        y of the middle of the lens glass at a lens centre (root space)
        'rim_thickness', 'frame_depth', 'lens_thickness', 'wrap_radius'
        'hinges'        [(x, y, z) right, left] hinge axes (vertical) ; 'temple_tips' [(x, y, z) right, left]
        'ear_points'    [(x, y, z) right, left] centre line of the temple where the downward bend starts
        'pad_centres'   [(x, y, z) right, left]
        'size'          (width, height of the front, depth front to temple tip)
        'bridge_z'      (z of the arch under the bridge, z of the top of the bridge) on the mid-plane; 'front_top_z',
                        'front_bottom_z' = z extent of the whole front ; 'design' = the 2D drawing (see design())
        'materials'     {'frame', 'lens', 'steel', 'pad'} ; 'triangles' total triangle count
    lens_w x lens_h = opening of each rim, bridge = distance between the two openings, face_half_width = x of the hinge
    line (the end pieces pass it by 1.5 mm), temple_len = y of the temple tips, head_half_width = half width of the head
    the temples must clear above the ears, wrap_radius = radius of the gentle face-form bend of the front (0 = flat),
    tilt_deg = upward tilt of the temple end of each lens, ear_drop = how far the tips drop behind the ear,
    temple_pitch_deg = slope of the temples (positive = they run DOWN towards the ears; the front does not move), to reach
    ears that are lower / higher than the hinges or to keep the temples level when root is tilted forward."""
    col = collection or bpy.context.scene.collection
    root = bpy.data.objects.new(name, None)
    root.empty_display_size = 0.02
    col.objects.link(root)
    D = design(lens_w, lens_h, bridge, face_half_width, rim, tilt_deg)
    mats = {'frame': acetate_material(name + '.acetate'), 'lens': lens_material(name + '.lens'),
            'steel': steel_material(name + '.steel'), 'pad': pad_material(name + '.pad')}
    R = wrap_radius or 0.0
    hx, hz = float(D['hinge'][0]), float(D['hinge'][1])

    # ---- front
    G = _Geo()
    _build_front(G, D, depth, (0.0010, 0.0008), (0.0006, 0.0006))
    G.wrap(R)
    for sx in (-1.0, 1.0):
        for dv in (-0.0015, 0.0015):
            q = D['hinge'] - D['eu'] * 0.0032 + D['ev'] * dv
            x = sx * float(q[0])
            _dome(G, (x, _sag(x, R) + 0.00003, float(q[1])), (_slope(x, R), -1.0, 0.0), 0.00062, 0.00013, mat=1)
    frame = _make_object(name + '.frame', G, [mats['frame'], mats['steel']], col, root)
    tris = G.triangles()

    # ---- lenses
    thick = 0.0016
    GL, attr, c0 = _build_lens(D, depth, thick, 0.30, 0.13, 0.09)
    G = _Geo()
    G.add(GL)
    G.add_mirrored(GL)
    G.wrap(R)
    lenses = _make_object(name + '.lenses', G, [mats['lens']], col, root, {'rim': attr + attr})
    tris += G.triangles()
    cx, cz = float(D['centre'][0]), float(D['centre'][1])
    lens_y = 0.5 * depth - c0 + _sag(cx, R)

    # ---- temples + hinges
    sl = _slope(hx, R)
    back_n = np.array([-sl, 1.0, 0.0]) / math.hypot(sl, 1.0)
    y_back = _sag(hx, R) + depth
    h0 = 0.0064
    xe = max(hx + 0.004, head_half_width + 0.0030)
    ye = temple_len - 0.030
    tp = math.tan(math.radians(temple_pitch_deg))
    ear = (xe, ye, hz - (ye - y_back) * tp)
    tip = (xe - 0.005, temple_len, hz - ear_drop - (temple_len - y_back) * tp)
    GT, tip_pos = _build_temple(hx, y_back + 0.00005, hz, back_n, ear, tip, h0)
    tdir = np.array([xe - hx, ye - y_back, ear[2] - hz])
    tdir /= np.linalg.norm(tdir)
    hinge = _build_hinge(GT, hx, y_back, hz, back_n, tdir, 0.0029)
    G = _Geo()
    G.add(GT)
    G.add_mirrored(GT)
    temples = _make_object(name + '.temples', G, [mats['frame'], mats['steel']], col, root)
    tris += G.triangles()

    # ---- nose pads
    GP, pc = _build_pad(D, depth, bridge, R, rim)
    G = _Geo()
    G.add(GP)
    G.add_mirrored(GP)
    pads = _make_object(name + '.pads', G, [mats['pad'], mats['steel']], col, root)
    tris += G.triangles()

    def both(p):
        return [(-float(p[0]), float(p[1]), float(p[2])), (float(p[0]), float(p[1]), float(p[2]))]

    width = 2 * float(np.abs(D['outer'][:, 0]).max())
    height = float(D['outer'][:, 1].max() - D['outer'][:, 1].min())
    return {'root': root, 'frame': frame, 'lenses': lenses, 'temples': temples, 'pads': pads,
            'objects': [frame, lenses, temples, pads],
            'lens_centres': [(-cx, cz), (cx, cz)], 'lens_y': lens_y,
            'rim_thickness': rim, 'frame_depth': depth, 'lens_thickness': thick, 'wrap_radius': R,
            'hinges': both(hinge), 'temple_tips': both(tip_pos), 'ear_points': both(ear), 'pad_centres': both(pc),
            'size': (width, height, float(tip_pos[1])), 'bridge_z': D['bridge_z'], 'front_top_z': float(D['outer'][:, 1].max()),
            'front_bottom_z': float(D['outer'][:, 1].min()), 'materials': mats, 'triangles': tris, 'design': D}
