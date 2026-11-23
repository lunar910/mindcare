"""PS2-style hair: a painted base shell plus chunky polygon 'cards', generated from a declarative style.

Entry point: build(ch). The cut is chosen with cfg_hair.STYLE and described by cfg_hair.STYLES[STYLE] (pure data):

    whorl      crown point the hair radiates from, dict(theta, phi) in degrees
    volume     thickness of the hair mass over the skull, dict(theta=[deg...], thick=[m...], edge_min, edge_ramp)
    shell      the base shell that closes the scalp (painted, alpha-toothed along the hairline)
    halo       painted highlight ring baked into the vertex colours
    groups     list of lock groups; each group is a dict of lock parameters (see LOCK_DEFAULTS) plus one of
                 locks=[{...}, ...]                 explicit locks (per-lock overrides)
                 ring=dict(phi=(a, b), n=k)         k locks spread over an azimuth range
               and optionally mirror=True (duplicate on the other side), jitter={param: sigma}, alt={param: (f0, f1, ...)}.

Angles: phi = azimuth in degrees (0 front, +90 the character's left, 180 back), theta = polar angle from straight up.
A lock is a path that hugs the skull from its root to its release direction (phi, theta), then hangs free for `length`
metres (or until its tip reaches the height `tip`, metres above the eye line). Any parameter may be a table
[(a0, v0), (a1, v1), ...] interpolated over |phi|. theta may be ('hl', d): d degrees past the hairline at that azimuth.
"""
import math
import zlib

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

import da
import look
import uvbake

TILE_W, TILE_H = 16, 64          # one painted lock: 16 x 64 texels
LOCK_TILES = 7                   # lock variants in the atlas
ATLAS_TILES = LOCK_TILES + 1     # + 1 tile for the base shell -> 128 x 64 texture
BASE_TILE = LOCK_TILES
UP = np.array([0.0, 0.0, 1.0])

LOCK_DEFAULTS = dict(
    phi=0.0, theta=('hl', 0.0),      # release direction
    root_phi=None, root_theta=None,  # root direction (None = the whorl)
    root_f=0.1,                      # the card starts at this fraction of the root -> release arc
    swirl=0.0,                       # sideways bow of the hugging part (radians at mid arc, + = towards larger phi)
    length=0.06, tip=None,           # free length in metres, or tip height (metres above the eye line, canonical)
    width=0.026, point=0.05, taper_pow=1.5, grow=0.03,
    lift0=0.002, lift=0.006,         # height above the hair volume at the root / at the release
    bump=0.003, bump_at=0.5,         # extra lift along the hugging part
    rise=0.0,                        # lifts the lock off the head when it leaves the scalp
    flick=0.0,                       # outward kick of the tip
    bend=(0.0, 0.0),                 # sideways drift at the start / end of the free part (+ = towards larger phi)
    grav=1.0, t_blend=0.5,           # how strongly / how early gravity takes over
    hug=0.0, off=(0.008, 0.012),     # pull towards the body, wanted distance at the start / end of the free part
    clear=0.005,                     # minimum distance to the body
    twist=0.0, tilt=0.08, arch=0.2, round=0.3,  # card cross-section (tilt: each card lies over its neighbour like a shingle)
    shade=1.0, layer=1, tex=None, seg=0.011,
    wisps=0, wisp_len=0.82, wisp_width=0.5,   # thinner companion cards that split off near the tip
)
JITTER_DEFAULTS = dict(phi=1.2, theta=1.0, length=0.08, tip=0.003, width=0.08, shade=0.06, lift=0.0008, root_f=0.03, flick=0.05)
RELATIVE_JITTER = ('length', 'width', 'shade')
MIRROR_SIGN = ('phi', 'root_phi', 'twist')


# ---------------------------------------------------------------- small helpers
def u_dir(theta, phi):
    t, p = math.radians(theta), math.radians(phi)
    return np.array([math.sin(t) * math.sin(p), -math.sin(t) * math.cos(p), math.cos(t)])


def slerp(a, b, t):
    d = float(np.clip(a.dot(b), -1, 1))
    om = math.acos(d)
    if om < 1e-5:
        return a.copy()
    return (math.sin((1 - t) * om) * a + math.sin(t * om) * b) / math.sin(om)


def _unit(v):
    return v / (np.linalg.norm(v) + 1e-12)


def _wrap(phi):
    return ((phi + 180.0) % 360.0) - 180.0


def head_frame(ch):
    vd = da.vertex_data(ch)
    J = vd['J']
    E = (J['eye.L____head'] + J['eye.R____head']) / 2
    s = (J['head____tail'][2] - E[2]) / 0.112
    C = E + np.array([0, 0.091 * s, 0.017 * s])
    return E, C, s


# ---------------------------------------------------------------- strand texture
def _ramp(val, light, mid, dark):
    light, mid, dark = (np.asarray(c, dtype=np.float32) for c in (light, mid, dark))
    val = np.clip(val, 0, 1)[..., None]
    lo = dark + (mid - dark) * np.clip(val / 0.5, 0, 1)
    return lo + (light - mid) * np.clip((val - 0.5) / 0.5, 0, 1)


def paint_tile(seed, light, mid, dark, kind='lock', ss=8):
    """One hand-painted lock, u across (0..1), v from root (row 0) to tip. Returns (TILE_H, TILE_W, 4).
    Strands of uneven width (1 to 4 texels) in a few tones, dark gaps that open and close between them, a zig-zag sheen
    that starts and stops strand by strand, shadowed roots and one shadowed edge (the painted light comes from u = 1).
    Painted large, then box-filtered down to PS2 size."""
    rng = np.random.default_rng(seed)
    W, H = TILE_W * ss, TILE_H * ss
    v, u = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = (u + 0.5) / W, (v + 0.5) / H
    vv = (np.arange(H, dtype=np.float32) + 0.5) / H
    widths = []
    while sum(widths) < TILE_W:
        widths.append(int(rng.choice([1, 2, 2, 3, 3, 4])))
    widths[-1] -= sum(widths) - TILE_W
    if widths[-1] <= 0:
        widths.pop()
    widths = [w for w in widths if w > 0]
    widths[-1] += TILE_W - sum(widths)
    ns = len(widths)
    b0 = np.cumsum(widths)[:-1] / TILE_W
    B = []
    for i in range(ns - 1):
        wander = (da.vnoise(vv * float(rng.uniform(1.5, 3.0)), vv * 0 + i * 7.3, seed + 11 + i) - 0.5) * 0.1
        B.append(b0[i] + wander + float(rng.uniform(-0.05, 0.05)) * (vv - 0.5))
    B = np.sort(np.clip(np.stack(B, axis=0), 0.03, 0.97), axis=0)
    edges = np.concatenate([np.zeros((1, H), dtype=np.float32), B, np.ones((1, H), dtype=np.float32)], axis=0)
    idx = (u[None] > B[:, :, None]).sum(axis=0)
    rows = np.arange(H)[:, None]
    left, right = edges[idx, rows], edges[idx + 1, rows]
    r_in = (u - left) / np.maximum(right - left, 1e-3)
    levels = np.array([0.4, 0.54, 0.66, 0.78])
    tone = np.zeros(ns)
    k = int(rng.integers(0, 4))
    for i in range(ns):
        k = int(rng.choice([j for j in range(4) if j != k], p=None))
        tone[i] = levels[k] + float(rng.uniform(-0.03, 0.03))
    val = tone[idx].astype(np.float32) + 0.07 * (r_in - 0.5)                # each strand is lit from the u = 1 side
    for i in range(ns - 1):                                                  # dark gaps between some strands
        if rng.uniform() < 0.3:
            continue
        mode = int(rng.integers(0, 4))
        v0, v1 = ((-0.3, float(rng.uniform(0.35, 0.8))), (float(rng.uniform(0.2, 0.55)), 1.4), (-0.3, 1.4),
                  (float(rng.uniform(0.1, 0.3)), float(rng.uniform(0.6, 0.9))))[mode]
        t = np.clip((vv - v0) / (v1 - v0), 0, 1)
        gw = float(rng.uniform(0.024, 0.036)) * np.maximum(np.sin(np.pi * t), 0.0) ** 0.5 + 1e-4
        d = np.abs(u - B[i][:, None]) / gw[:, None]
        val = val - float(rng.uniform(0.3, 0.5)) * np.clip(1.6 - d, 0, 1) * ((vv > v0) & (vv < v1))[:, None]
    fine = da.fbm2(u * 6.0, v * 1.5, seed + 6, 2)
    val = val + 0.06 * (fine - 0.5)
    if kind == 'lock':
        h0 = 0.27 + rng.normal(0, 0.035, ns)                                 # sheen: starts and stops strand by strand
        h1 = h0 + rng.uniform(0.1, 0.24, ns)
        hg = np.where(tone > 0.6, rng.uniform(0.2, 0.32, ns), rng.uniform(0.06, 0.16, ns)) * (rng.uniform(0, 1, ns) > 0.2)
        band = da.sm(h0[idx] - 0.03, h0[idx] + 0.02, v) * da.sm(h1[idx] + 0.06, h1[idx] - 0.02, v)
        val = val + hg[idx] * band
        l0 = 0.66 + rng.normal(0, 0.04, ns)
        val = val + (0.4 * hg[idx]) * da.sm(l0[idx] - 0.03, l0[idx] + 0.02, v) * da.sm(l0[idx] + 0.16, l0[idx] + 0.08, v)
        r0 = rng.uniform(0.07, 0.17, ns)                                     # roots in shadow, jagged
        val = val * (0.5 + 0.5 * da.sm(r0[idx] * 0.3, r0[idx], v))
        val = val * (1.0 - 0.12 * da.sm(0.82, 1.0, v))
        val = val * (1.0 - 0.3 * da.sm(0.2, 0.0, u) ** 1.2) * (1.0 - 0.1 * da.sm(0.9, 1.0, u))
    else:
        val = 0.5 + (val - 0.6) * 0.8
    col = _ramp(val, light, mid, dark)
    col = col.reshape(TILE_H, ss, TILE_W, ss, 3).mean(axis=(1, 3))
    alpha = np.ones((TILE_H, TILE_W), dtype=np.float32)
    if kind == 'base':                                                       # ragged roots along the hairline (v -> 1)
        depth = np.clip(np.round(1.6 + 1.4 * np.sin(np.arange(TILE_W) * 1.7 + rng.uniform(0, 6)) + rng.normal(0, 0.9, TILE_W)), 0, 4).astype(int)
        for c in range(TILE_W):
            if depth[c]:
                alpha[TILE_H - depth[c]:, c] = 0.0
    return np.concatenate([col, alpha[..., None]], axis=2).astype(np.float32)


def atlas_pixels(light, mid, dark, seed=3):
    tiles = [paint_tile(seed * 101 + k, light, mid, dark, 'lock') for k in range(LOCK_TILES)]
    tiles.append(paint_tile(seed * 101 + 77, light, mid, dark, 'base'))
    return np.concatenate(tiles, axis=1)


def strand_atlas(name, light, mid, dark, seed=3):
    return uvbake.to_image(name, atlas_pixels(light, mid, dark, seed))


def hair_material(name, img, rough=0.72, spec=0.1, emit=0.0, closest=True):
    """Matte painted hair: texture x per-vertex 'shade', alpha-tested."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.extension = 'EXTEND'
    tx.interpolation = 'Closest' if closest else 'Linear'
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'shade'
    mul = nt.nodes.new('ShaderNodeMix')
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    nt.links.new(tx.outputs['Color'], mul.inputs['A'])
    nt.links.new(at.outputs['Color'], mul.inputs['B'])
    nt.links.new(mul.outputs['Result'], b.inputs['Base Color'])
    gt = nt.nodes.new('ShaderNodeMath')
    gt.operation = 'GREATER_THAN'
    gt.inputs[1].default_value = 0.5
    nt.links.new(tx.outputs['Alpha'], gt.inputs[0])
    nt.links.new(gt.outputs[0], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    if emit > 0:                      # a little self-illumination keeps the painted tones readable in any light
        nt.links.new(mul.outputs['Result'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = emit
    return m


# ---------------------------------------------------------------- head sampler
class Head:
    """Rest-pose head: scalp ray casts, hairline test, distance queries against the body and the clothes."""

    def __init__(self, ch, hairline, style):
        vd = da.vertex_data(ch)
        body = ch['body']
        self.co = vd['co'].astype(np.float64)
        self.can = vd['can'].astype(np.float64)
        self.hw = np.asarray(vd['hw'], dtype=np.float64)
        self.polys = [tuple(p.vertices) for p in body.data.polygons]
        self.vecs = [Vector(c) for c in self.co]
        self.bvh = BVHTree.FromPolygons(self.vecs, self.polys)
        self.E, self.C, self.s = head_frame(ch)
        self.Cv = Vector(self.C)
        top = Vector(self.C + np.array([0, 0, 0.3]))
        pr = self.bvh.find_nearest(top)
        self.sign = 1.0 if (top - pr[0]).dot(pr[1]) > 0 else -1.0
        self.hl_az, self.hl_y = np.asarray(hairline[0], dtype=float), np.asarray(hairline[1], dtype=float)
        self.cloth = []
        inv = body.matrix_world.inverted()
        for name, ob in (ch.get('proxies') or {}).items():
            M = inv @ ob.matrix_world
            pts = [M @ v.co for v in ob.data.vertices]
            if min((p - self.Cv).length for p in pts) > 0.4:
                continue
            self.cloth.append(BVHTree.FromPolygons(pts, [tuple(p.vertices) for p in ob.data.polygons]))
        self.vol = dict(theta=[0, 180], thick=[0.006, 0.006], edge_min=0.0015, edge_ramp=0.03)
        self.vol.update(style.get('volume') or {})
        wh = style.get('whorl') or dict(theta=16, phi=180)
        self.whorl = (wh['theta'], wh['phi'])
        g = np.asarray(style.get('gravity', (0.0, 0.0, -1.0)), dtype=float)
        self.gdir = g / np.linalg.norm(g)
        self._hl = self._hairline_table()

    def cast(self, d):
        """Ray from the head centre: (point, outward normal, canonical coords, head weight) or None."""
        hit = self.bvh.ray_cast(self.Cv, Vector(d), 0.45)
        if hit[0] is None:
            return None
        p, n = np.array(hit[0]), np.array(hit[1])
        if n.dot(d) < 0:
            n = -n
        vids = self.polys[hit[2]]
        w = poly_3d_calc([self.vecs[i] for i in vids], hit[0])
        can = sum(wi * self.can[i] for wi, i in zip(w, vids))
        hw = sum(wi * self.hw[i] for wi, i in zip(w, vids))
        return p, n, can, hw

    def inside(self, hit):
        """Signed height above the hairline (metres, canonical frame); negative outside the scalp."""
        if hit is None:
            return -1.0
        can, hw = hit[2], hit[3]
        ax = abs(can[0])
        az = math.atan2(ax, can[2] + 0.095)
        g = can[1] - float(np.interp(az, self.hl_az, self.hl_y))
        if ax > 0.066 and -0.06 < can[1] < 0.012 and -0.14 < can[2] < -0.06:      # ears (same box as the skin painter)
            g = min(g, -0.004)
        if hw < 0.4:
            g = min(g, -0.004)
        return g

    def _edge(self, dir_at, a0, a1, step, edge=0.0):
        """First angle in [a0, a1] where the scalp ends along a family of directions dir_at(angle)."""
        last, a = a0, a0
        while a <= a1:
            if self.inside(self.cast(dir_at(a))) < edge:
                lo, hi = last, a
                for _ in range(9):
                    mid = (lo + hi) / 2
                    if self.inside(self.cast(dir_at(mid))) < edge:
                        hi = mid
                    else:
                        lo = mid
                return (lo + hi) / 2
            last, a = a, a + step
        return a1

    def _hairline_table(self):
        phis = np.arange(-180.0, 180.0, 4.0)
        return phis, np.array([self._edge(lambda t, p=p: u_dir(t, p), 20.0, 170.0, 2.5) for p in phis])

    def theta_hl(self, phi):
        """Polar angle of the hairline at an azimuth."""
        phis, th = self._hl
        return float(np.interp(_wrap(phi), np.append(phis, 180.0), np.append(th, th[0])))

    def volume(self, d, hit):
        th = math.degrees(math.acos(max(-1.0, min(1.0, float(d[2])))))
        base = float(np.interp(th, self.vol['theta'], self.vol['thick']))
        k = float(da.sm(0.0, self.vol['edge_ramp'], self.inside(hit)))
        return max(self.vol['edge_min'], base * k) * self.s

    def signed(self, p, maxd=0.08):
        """Nearest body point: (location, direction away from the body, signed distance) or None."""
        r = self.bvh.find_nearest(Vector(p), maxd)
        if r[0] is None:
            return None
        loc = np.array(r[0])
        dv = p - loc
        dist = float(np.linalg.norm(dv))
        if dist < 1e-5:
            return loc, np.array(r[1]) * self.sign, 0.0
        # inside test: nothing between the head centre and the point (face normals are unreliable around the ears)
        dc = Vector(p) - self.Cv
        sg = -1.0 if self.bvh.ray_cast(self.Cv, dc.normalized(), dc.length)[0] is None else 1.0
        return loc, dv / dist * sg, dist * sg

    def push_out(self, p, clear):
        q = self.signed(p, 0.06)
        if q is not None and q[2] < clear:
            p = q[0] + q[1] * clear
        return p

    def cloth_push(self, p, clear):
        for bv in self.cloth:
            r = bv.find_nearest(Vector(p), clear * 4)
            if r[0] is None:
                continue
            loc, n = np.array(r[0]), np.array(r[1])
            axis = np.array([0.0, self.C[1] + 0.015, loc[2]])
            if n.dot(loc - axis) < 0:
                n = -n
            sd = float((p - loc).dot(n))
            if sd < clear:
                p = p + n * (clear - sd)
        return p

    def cloth_dist(self, p, maxd=0.1):
        best = maxd
        for bv in self.cloth:
            r = bv.find_nearest(Vector(p), maxd)
            if r[0] is not None:
                best = min(best, r[3])
        return best


# ---------------------------------------------------------------- style -> locks
def _table(x, a):
    if isinstance(x, (list, tuple)) and len(x) and isinstance(x[0], (list, tuple)):
        xs, ys = zip(*x)
        return float(np.interp(a, xs, ys))
    return x


def _theta(H, spec, phi):
    if isinstance(spec, (list, tuple)) and len(spec) == 2 and spec[0] == 'hl':
        return H.theta_hl(phi) + spec[1]
    return float(spec)


def expand(style, H, seed=0):
    """Declarative style -> list of fully resolved lock dicts."""
    locks = []
    for g in style['groups']:
        rng = np.random.default_rng([seed, zlib.crc32(g['name'].encode())])
        base = dict(LOCK_DEFAULTS)
        base.update({k: v for k, v in g.items() if k not in ('name', 'locks', 'ring', 'mirror', 'jitter', 'alt')})
        items = [dict(it) for it in g.get('locks', [])]
        if 'ring' in g:
            a, b, n = g['ring']['phi'][0], g['ring']['phi'][1], g['ring']['n']
            var = g['ring'].get('var', 'phi')
            closed = abs(abs(b - a) - 360.0) < 1e-6
            for i in range(n):
                f = i / n if closed else (i / (n - 1) if n > 1 else 0.5)
                items.append({var: a + (b - a) * f})
        for i, it in enumerate(items):
            it['_i'] = i
        if g.get('mirror'):
            mir = []
            for it in items:
                m = dict(it)
                for k in MIRROR_SIGN:
                    if m.get(k) is not None:
                        m[k] = -m[k]
                if 'bend' in m:
                    m['bend'] = (-m['bend'][0], -m['bend'][1])
                m['_mir'] = True
                mir.append(m)
            items += mir
        jit = dict(JITTER_DEFAULTS)
        jit.update(g.get('jitter') or {})
        for it in items:
            L = dict(base)
            L.update(it)
            key = L['root_phi'] if (g.get('ring', {}).get('var') == 'root_phi') else L['phi']
            a = abs(_wrap(key))
            sgn = -1.0 if _wrap(key) < 0 else 1.0
            for k in list(L):
                L[k] = _table(L[k], a)
            if g.get('ring', {}).get('var') == 'root_phi':       # tables give |release phi| from |root phi|
                L['phi'] = sgn * abs(L['phi']) if 'phi' not in it else L['phi']
            if L.get('_mir') and 'bend' not in it:
                L['bend'] = (-L['bend'][0], -L['bend'][1])
                if 'twist' not in it:
                    L['twist'] = -L['twist']
            for k, fs in (g.get('alt') or {}).items():
                L[k] = L[k] * fs[L['_i'] % len(fs)] if L[k] is not None else None
            for k, sg in jit.items():
                if sg and L.get(k) is not None and not isinstance(L[k], (tuple, list)):
                    L[k] = L[k] * float(1 + rng.normal(0, sg)) if k in RELATIVE_JITTER else L[k] + float(rng.normal(0, sg))
            L['root_f'] = float(np.clip(L['root_f'], 0.0, 0.95))
            L['theta_abs'] = _theta(H, L['theta'], L['phi'])
            if L['root_phi'] is None:
                L['root_theta_abs'], L['root_phi_abs'] = H.whorl
            else:
                L['root_phi_abs'] = L['root_phi']
                L['root_theta_abs'] = _theta(H, L['root_theta'], L['root_phi'])
            L['group'] = g['name']
            L['tile'] = int(L['tex']) if L['tex'] is not None else int(rng.integers(0, LOCK_TILES))
            L['flip'] = (_wrap(L['phi'] - style.get('light_phi', -35.0)) < 0) != (rng.uniform() < 0.12)   # lit edge towards the painted light
            L['wisp_rng'] = [float(x) for x in rng.uniform(0, 1, 8)]
            locks.append(L)
    return locks


# ---------------------------------------------------------------- lock paths
def make_path(H, L, length=None):
    """Guide polyline of one lock (points, outward normals, number of hugging points) or None."""
    dA = u_dir(L['root_theta_abs'], L['root_phi_abs'])
    dB = u_dir(L['theta_abs'], L['phi'])
    om = math.degrees(math.acos(float(np.clip(dA.dot(dB), -1, 1))))
    n_hug = max(3, int(math.ceil(om * (1 - L['root_f']) / 7.0)) + 1)
    perp = _unit(np.cross(dA, dB)) if om > 1e-3 else np.zeros(3)
    pts, nrm = [], []
    for i in range(n_hug):
        fl = i / (n_hug - 1)
        f = L['root_f'] + (1 - L['root_f']) * fl
        d = slerp(dA, dB, f)
        if L['swirl']:
            d = _unit(d + perp * L['swirl'] * math.sin(math.pi * f))
        hit = H.cast(d)
        if hit is None:
            continue
        n = _unit(hit[1] * 0.5 + d * 0.5)
        lift = (L['lift0'] + (L['lift'] - L['lift0']) * float(da.sm(0.0, 0.75, fl))
                + L['bump'] * math.exp(-((fl - L['bump_at']) / 0.28) ** 2) + 0.0012 * L['layer'])
        pts.append(hit[0] + n * (H.volume(d, hit) + lift * H.s))
        nrm.append(n)
    if len(pts) < 2:
        return None
    n_hug = len(pts)
    length = (L['length'] if length is None else length) * H.s
    T0 = _unit(_unit(pts[-1] - pts[-2]) + nrm[-1] * L['rise'])
    n_free = max(3, int(round(length / 0.008)))
    step = length / n_free
    p, out = pts[-1].copy(), nrm[-1]
    for k in range(1, n_free + 1):
        w = k / n_free
        g = float(da.sm(0.0, L['t_blend'], w)) * L['grav']
        rad = _unit(np.array([p[0] - H.C[0], p[1] - H.C[1], 0.0]))
        tau = np.array([-rad[1], rad[0], 0.0])
        d = (T0 * (1 - g) + H.gdir * g + out * (L['flick'] * float(da.sm(0.4, 1.0, w)))
             + tau * (L['bend'][0] + (L['bend'][1] - L['bend'][0]) * w))
        p = p + _unit(d) * step
        q = H.signed(p, 0.08)
        if q is not None:
            loc, nn, sd = q
            tgt = (L['off'][0] + (L['off'][1] - L['off'][0]) * w ** 1.5) * H.s
            if sd < L['clear']:
                p = loc + nn * L['clear']
            elif L['hug'] > 0 and sd > tgt:
                p = p - nn * (sd - tgt) * L['hug']
            out = _unit(nn * 0.6 + rad * 0.4)
        else:
            out = _unit(rad * 0.85 + UP * 0.15)
        p = H.cloth_push(p, L['clear'] + 0.003)
        pts.append(p.copy())
        nrm.append(out)
    for _ in range(2):                       # relax the kinks left by the collisions
        for i in range(n_hug, len(pts) - 1):
            pts[i] = 0.25 * pts[i - 1] + 0.5 * pts[i] + 0.25 * pts[i + 1]
    for i in range(n_hug, len(pts)):
        pts[i] = H.cloth_push(H.push_out(pts[i], L['clear']), L['clear'] + 0.003)
    return pts, nrm, n_hug


def solve_path(H, L):
    """make_path, with the free length solved so that the tip ends at the wanted height when L['tip'] is given."""
    if L.get('tip') is None:
        return make_path(H, L)
    zt = H.E[2] + L['tip'] * H.s
    lo, hi = 0.006, 0.32
    for _ in range(12):
        mid = (lo + hi) / 2
        r = make_path(H, L, mid)
        if r is None:
            return None
        if r[0][-1][2] > zt:
            lo = mid
        else:
            hi = mid
    L['length'] = (lo + hi) / 2
    return make_path(H, L)


def _resample(P, N, rows):
    P, N = np.asarray(P), np.asarray(N)
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0.0, s[-1], rows)
    Pr = np.stack([np.interp(t, s, P[:, k]) for k in range(3)], axis=1)
    Nr = np.stack([np.interp(t, s, N[:, k]) for k in range(3)], axis=1)
    return Pr, Nr / (np.linalg.norm(Nr, axis=1, keepdims=True) + 1e-12), float(s[-1])


class _Buf:
    def __init__(self):
        self.verts, self.faces, self.uvs, self.shade, self.normals = [], [], [], [], []


def _frames(Pr, Nr):
    m = len(Pr)
    T, Nn, Bn = [], [], []
    for i in range(m):
        t = _unit(Pr[min(i + 1, m - 1)] - Pr[max(i - 1, 0)])
        n = _unit(Nr[i] - t * Nr[i].dot(t))
        T.append(t)
        Nn.append(n)
        Bn.append(np.cross(t, n))
    return np.array(T), np.array(Nn), np.array(Bn)


def emit_card(buf, Pr, Nr, L, s, width, shade_fn, tile, flip):
    """Append one tapered card (3 vertices across) following the centre line Pr."""
    m = len(Pr)
    seg = np.linalg.norm(np.diff(Pr, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(arc[-1])
    v = arc / (total + 1e-9)
    point = min(L['point'] * s, 0.8 * total)
    v0 = 1.0 - point / total
    g_end = float(np.clip(L['grow'] * s / total, 0.04, 0.4))
    T, Nn, Bn = _frames(Pr, Nr)
    base = len(buf.verts)
    us = (0.04, 0.5, 0.96) if not flip else (0.96, 0.5, 0.04)
    for i in range(m):
        n, b = Nn[i], Bn[i]
        a = L['twist'] * float(v[i]) - L['tilt']
        if a:
            n, b = n * math.cos(a) + b * math.sin(a), b * math.cos(a) - n * math.sin(a)
        grow = 0.3 + 0.7 * float(da.sm(0.0, g_end, v[i]))
        tp = float(np.clip((v[i] - v0) / (1.0 - v0), 0, 1))
        hw = max(width * s / 2 * grow * (1.0 - tp ** L['taper_pow']), 0.0004)
        buf.verts += [Pr[i] - b * hw, Pr[i] + n * (L['arch'] * hw), Pr[i] + b * hw]
        buf.normals += [_unit(n - b * L['round']), n, _unit(n + b * L['round'])]
        buf.uvs += [((tile + uu) / ATLAS_TILES, float(v[i])) for uu in us]
        sh = shade_fn(Pr[i], n, float(v[i]))
        buf.shade += [sh, sh, sh]
    for i in range(m - 1):
        a = base + i * 3
        buf.faces.append((a, a + 1, a + 4, a + 3))
        buf.faces.append((a + 1, a + 2, a + 5, a + 4))


def _halo(style, H):
    hp = style.get('halo')
    if not hp:
        return lambda p, n: 0.0
    axis = u_dir(hp['dir'][0], hp['dir'][1])
    a0, wd, gain = hp['angle'], hp['width'], hp['gain']

    def f(p, n):
        r = _unit(p - H.C) * 0.6 + n * 0.4
        ang = math.degrees(math.acos(float(np.clip(_unit(r).dot(axis), -1, 1))))
        return gain * math.exp(-((ang - a0) / wd) ** 2)
    return f


def build_cards(ch, H, locks, mat, style):
    buf = _Buf()
    halo = _halo(style, H)
    report = []
    for L in locks:
        r = solve_path(H, L)
        if r is None:
            print('hair: lock skipped', L['group'], round(L['phi'], 1))
            continue
        pts, nrm, n_hug = r
        seg_total = float(np.sum(np.linalg.norm(np.diff(np.asarray(pts), axis=0), axis=1)))
        rows = int(np.clip(round(seg_total / (L['seg'] * H.s)), 6, 30)) + 1
        Pr, Nr, total = _resample(pts, nrm, rows)
        sh0 = L['shade']
        v_first = len(buf.verts)
        shade_fn = lambda p, n, v, sh0=sh0: sh0 * (1.0 + halo(p, n))
        emit_card(buf, Pr, Nr, L, H.s, L['width'], shade_fn, L['tile'], L['flip'])
        report.append(dict(group=L['group'], phi=L['phi'], tip=np.array(pts[-1]), root=np.array(pts[0]), rel=np.array(pts[n_hug - 1]),
                           total=total, free=L['length'], v0=v_first))
        for k in range(int(L['wisps'])):          # thinner cards that leave the lock near its tip: a clumped, split end
            rr = L['wisp_rng']
            side = 1.0 if (k % 2 == 0) != L['flip'] else -1.0
            frac = L['wisp_len'] * (0.9 + 0.2 * rr[k % 8])
            Pw, Nw, _ = _resample(pts, nrm, rows)
            T, Nn, Bn = _frames(Pw, Nw)
            vv = np.linspace(0.0, 1.0, rows)
            lat = (0.2 + 0.55 * da.sm(0.25, 0.95, vv)) * L['width'] * H.s * side
            Pw = Pw + Bn * lat[:, None] - Nn * 0.0012
            keep = max(4, int(round(rows * frac)))
            Lw = dict(L)
            Lw['point'] = L['point'] * 0.8
            emit_card(buf, Pw[:keep], Nw[:keep], Lw, H.s, L['width'] * L['wisp_width'],
                      lambda p, n, v, sh0=sh0: sh0 * 0.93 * (1.0 + halo(p, n)), (L['tile'] + 1 + k) % LOCK_TILES, not L['flip'])
        report[-1]['v1'] = len(buf.verts)
    ob = _mesh_object(ch, ch['name'] + '_hair', buf, mat)
    return ob, report


def _mesh_object(ch, name, buf, mat, loop_uvs=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(float(x) for x in v) for v in buf.verts], [], buf.faces)
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    uvl = mesh.uv_layers.new(name='UVMap')
    if loop_uvs is None:
        li = np.zeros(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get('vertex_index', li)
        uvl.data.foreach_set('uv', np.asarray(buf.uvs, dtype=np.float32)[li].ravel())
    else:
        uvl.data.foreach_set('uv', np.asarray(loop_uvs, dtype=np.float32).ravel())
    ca = mesh.color_attributes.new('shade', 'FLOAT_COLOR', 'POINT')
    sh = np.asarray(buf.shade, dtype=np.float32)
    ca.data.foreach_set('color', np.stack([sh, sh, sh, np.ones_like(sh)], axis=1).ravel())
    if buf.normals:
        mesh.normals_split_custom_set_from_vertices([tuple(float(x) for x in n) for n in buf.normals])
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    mesh.materials.append(mat)
    ob.matrix_world = ch['body'].matrix_world.copy()
    look.parent_keep(ob, ch, 'head')
    return ob


# ---------------------------------------------------------------- base shell
SHELL_DEFAULTS = dict(strips=24, rows=13, edge=-0.002, shade=0.8, tile_len=0.21, edge_shade=0.8, edge_width=0.03)


def build_shell(ch, H, style, mat):
    """Painted shell over the whole scalp: strips radiating from the whorl down to the hairline. It gives the hair its
    volume, closes every gap between the cards and ends in ragged alpha roots exactly on the painted hairline."""
    sp = dict(SHELL_DEFAULTS)
    sp.update(style.get('shell') or {})
    halo = _halo(style, H)
    pole = u_dir(*H.whorl)
    ref = np.array([0.0, -1.0, 0.0])
    e1 = _unit(ref - pole * ref.dot(pole))
    e2 = np.cross(pole, e1)
    N, M = sp['strips'] * 2, sp['rows']
    b0 = math.radians(5.0)
    buf = _Buf()
    cols, dists = [], []
    for j in range(N):
        al = 2 * math.pi * j / N
        side = math.cos(al) * e1 + math.sin(al) * e2
        dir_at = lambda bdeg, side=side: math.cos(math.radians(bdeg)) * pole + math.sin(math.radians(bdeg)) * side
        b_end = math.radians(H._edge(dir_at, 5.0, 165.0, 2.5, sp['edge']))
        col = []
        for i in range(M):
            b = b0 + (b_end - b0) * (i / (M - 1)) ** 0.85
            d = math.cos(b) * pole + math.sin(b) * side
            hit = H.cast(d)
            if hit is None:
                col.append(col[-1].copy())
                continue
            n = _unit(hit[1] * 0.5 + d * 0.5)
            col.append(hit[0] + n * H.volume(d, hit))
        col = np.array(col)
        seg = np.linalg.norm(np.diff(col, axis=0), axis=1)
        dist = seg.sum() - np.concatenate([[0.0], np.cumsum(seg)])      # distance to the hairline end
        cols.append(col)
        dists.append(dist)
    hit = H.cast(pole)
    centre = hit[0] + _unit(hit[1] * 0.5 + pole * 0.5) * H.volume(pole, hit)
    buf.verts.append(centre)
    for j in range(N):
        buf.verts += list(cols[j])
    vid = lambda j, i: 1 + (j % N) * M + i
    T = sp['tile_len'] * H.s
    loop_uvs = []

    def uv(j_strip_u, dist):
        return ((BASE_TILE + 0.03 + 0.94 * j_strip_u) / ATLAS_TILES, max(0.0, 1.0 - dist / T))
    d_pole = float(np.mean([d[0] for d in dists])) + b0 * 0.1
    for j in range(N):
        k = j // 2                      # strip index: two columns per strip, mirrored every other strip
        ua, ub = (0.0, 0.5) if j % 2 == 0 else (0.5, 1.0)
        if k % 2:
            ua, ub = 1.0 - ua, 1.0 - ub
        jn = (j + 1) % N
        buf.faces.append((0, vid(j, 0), vid(jn, 0)))
        loop_uvs += [uv((ua + ub) / 2, d_pole), uv(ua, dists[j][0]), uv(ub, dists[jn][0])]
        for i in range(M - 1):
            buf.faces.append((vid(j, i), vid(j, i + 1), vid(jn, i + 1), vid(jn, i)))
            loop_uvs += [uv(ua, dists[j][i]), uv(ua, dists[j][i + 1]), uv(ub, dists[jn][i + 1]), uv(ub, dists[jn][i])]
    allv = np.array(buf.verts)
    dall = np.concatenate([[d_pole]] + dists)
    for p, dd in zip(allv, dall):
        n = _unit(p - H.C)
        edge = sp['edge_shade'] + (1 - sp['edge_shade']) * float(da.sm(0.0, sp['edge_width'], dd))
        buf.shade.append(sp['shade'] * edge * (1.0 + halo(p, n)))
    ob = _mesh_object(ch, ch['name'] + '_cap', buf, mat, loop_uvs=loop_uvs)
    # make sure the shell faces outwards
    me = ob.data
    c = np.mean(allv, axis=0)
    p0 = me.polygons[len(me.polygons) // 2]
    if (np.array(p0.center) - H.C).dot(np.array(p0.normal)) < 0:
        me.flip_normals()
    return ob


# ---------------------------------------------------------------- entry point
def build(ch):
    """Hair pass entry point: painted base shell + polygon cards for the style chosen in cfg_hair."""
    import cfg_hair as CH
    style = CH.STYLES[CH.STYLE]
    H = Head(ch, (CH.HAIRLINE_AZ, CH.HAIRLINE_Y), style)
    img = strand_atlas(ch['name'] + '_strands', CH.HAIR_LIGHT, CH.HAIR_MID, CH.HAIR_DARK, seed=CH.TEX_SEED)
    mat = hair_material(ch['name'] + '_hair', img, rough=CH.ROUGH, spec=CH.SPEC, emit=CH.EMIT)
    locks = expand(style, H, seed=style.get('seed', CH.STYLE_SEED))
    cards, report = build_cards(ch, H, locks, mat, style)
    shell = build_shell(ch, H, style, mat)
    ch['hair'] = dict(objects=[cards, shell], report=report, head=H, style=CH.STYLE)
    return [cards, shell]
