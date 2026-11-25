"""PS2-era 'Capcom cutscene' art direction: hand-painted skin texture, painted eyes.

Skin: the MakeHuman photo skin is only the base layer. On top of it everything is painted per texel with numpy:
baked soft light with real occlusion (per-vertex ray casting), colour zones, contouring, eyebrows drawn hair by hair,
lash lines that follow the real eyelid rims, lips, the dark mouth cavity.  Two textures come out of the same painter:
the 1024 px body atlas and a denser patch for the front of the face (FACE_WIN, 512 x 608 px), blended in the material.
Eyes: a small painted eye texture projected along the eye axis, plus a head-fixed shadow under the upper lid."""
import math
import os

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import mh
import uvbake

TEX = 2048
# front of the face in the body UV atlas (u0, v0, u1, v1); the UV layout is the same for every morph
FACE_WIN = (0.7435, 0.335, 0.9935, 0.6319)
FACE_RASTER = (1024, 1216)          # painted at this size (the density of a 4096 atlas), stored at half
# labels of the UV islands (per texel / per triangle)
ISL_BODY, ISL_HEAD, ISL_SOCK_L, ISL_SOCK_R, ISL_MOUTH = 0, 1, 2, 3, 4


def sm(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def gauss(x, s):
    return np.exp(-(x / s) ** 2)


def srgb(c):
    return np.asarray(c, dtype=np.float32) / 255.0


def mix(c, col, t):
    return c + (np.asarray(col, dtype=np.float32) - c) * np.asarray(t, dtype=np.float32)[..., None]


def vnoise(x, y, seed=0):
    xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    xf, yf = (x - xi).astype(np.float32), (y - yi).astype(np.float32)
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    k = (seed * 2654435761) & 0xFFFFFFFF

    def h(a, b):
        n = (a * 374761393 + b * 668265263 + k) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF).astype(np.float32) / 65535.0
    return (h(xi, yi) * (1 - u) + h(xi + 1, yi) * u) * (1 - v) + (h(xi, yi + 1) * (1 - u) + h(xi + 1, yi + 1) * u) * v


def fbm2(x, y, seed=0, octaves=4):
    out, amp, tot, f = 0.0, 1.0, 0.0, 1.0
    for o in range(octaves):
        out = out + amp * vnoise(x * f, y * f, seed + o * 17)
        tot += amp
        amp *= 0.5
        f *= 2.03
    return out / tot


def lin(c):
    """sRGB 0..255 -> linear RGBA tuple for node sockets."""
    a = np.asarray(c, dtype=np.float64) / 255
    return tuple(float(x) for x in np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)) + (1.0,)


# ---------------------------------------------------------------- base-mesh topology (feature lines)
_TOPO = None


def _order_loop(edges):
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    start = edges[0][0]
    loop, prev, cur = [start], None, start
    for _ in range(len(edges) + 2):
        nxt = [n for n in adj[cur] if n != prev]
        if not nxt or nxt[0] == start:
            break
        loop.append(nxt[0])
        prev, cur = cur, nxt[0]
    return loop


def _split_loop(loop, i0, i1):
    """Two chains from loop[i0] to loop[i1] (both directions around the closed loop)."""
    n = len(loop)
    a = [loop[(i0 + k) % n] for k in range(((i1 - i0) % n) + 1)]
    b = [loop[(i0 - k) % n] for k in range(((i0 - i1) % n) + 1)]
    return a, b


def topology():
    """Feature lines of the base mesh, found from its UV islands (identical for every morph): the eye-opening rims and the
    lip contact line are the seams between the head island and the eye-socket / mouth-cavity islands.
    Returns dict(tri_label [per uvbake.body_tris triangle], chains {name: body-local vertex ids}, can [unmorphed canonical coords])."""
    global _TOPO
    if _TOPO is not None:
        return _TOPO
    B = mh.base()
    faces = [f for f in B.faces if f[2] == 'body']
    used = np.array(sorted({i for f in faces for i in f[0]}))
    remap = -np.ones(len(B.v), dtype=np.int64)
    remap[used] = np.arange(len(used))
    par = list(range(len(B.vt)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for vi, ti, _ in faces:
        r0 = find(ti[0])
        for t in ti[1:]:
            r = find(t)
            if r != r0:
                par[r] = r0
    root = [find(f[1][0]) for f in faces]
    V0 = mh.to_bl(B.v[used])
    J0 = mh.joint_positions(B.v)
    E0 = (mh.to_bl(J0['eye.L____head']) + mh.to_bl(J0['eye.R____head'])) / 2
    can = np.stack([V0[:, 0] - E0[0], V0[:, 2] - E0[2], -(V0[:, 1] - E0[1])], axis=1)
    front = np.where((np.abs(can[:, 0]) < 0.004) & (can[:, 1] > -0.05) & (can[:, 1] < -0.03))[0]
    tip = int(front[np.argmax(can[front, 2])])
    edge_isl, head_root = {}, None
    for k, (vi, ti, _) in enumerate(faces):
        loc = [int(remap[i]) for i in vi]
        if head_root is None and tip in loc:
            head_root = root[k]
        for a, b in zip(loc, loc[1:] + loc[:1]):
            edge_isl.setdefault((min(a, b), max(a, b)), set()).add(root[k])
    seams = {}
    for e, s in edge_isl.items():
        if head_root in s and len(s) > 1:
            for r in s:
                if r != head_root:
                    seams.setdefault(r, []).append(e)
    label = {head_root: ISL_HEAD}
    chains = {}
    for r, edges in seams.items():
        ids = np.unique(np.array(edges))
        c = can[ids].mean(axis=0)
        loop = _order_loop(edges)
        lc = can[loop]
        if abs(c[1]) < 0.015 and 0.015 < abs(c[0]) < 0.05:
            side = 'L' if c[0] > 0 else 'R'
            label[r] = ISL_SOCK_L if side == 'L' else ISL_SOCK_R
            a, b = _split_loop(loop, int(np.argmin(np.abs(lc[:, 0]))), int(np.argmax(np.abs(lc[:, 0]))))
            up, lo = (a, b) if can[a][:, 1].mean() > can[b][:, 1].mean() else (b, a)
            chains[f'lid_{side}_up'], chains[f'lid_{side}_lo'] = np.array(up), np.array(lo)      # inner corner -> outer corner
        elif abs(c[0]) < 0.01 and -0.085 < c[1] < -0.05:
            label[r] = ISL_MOUTH
            a, b = _split_loop(loop, int(np.argmin(lc[:, 0])), int(np.argmax(lc[:, 0])))
            t = B.target('expression/units/caucasian/mouth-open')
            dy = np.zeros(len(B.v))
            if t is not None:
                dy[t[0]] = t[1][:, 1]
            dy = dy[used]
            up, lo = (a, b) if dy[a].mean() > dy[b].mean() else (b, a)
            chains['lip_up'], chains['lip_lo'] = np.array(up), np.array(lo)                       # right corner -> left corner
    tri_label = []
    for k, (vi, ti, _) in enumerate(faces):
        tri_label.extend([label.get(root[k], ISL_BODY)] * (2 if len(vi) == 4 else 1))
    # edge-loop distance from the eyelid rims over the skin (0 = rim seam, 1-2 = the lid's shelf, 3 = its visible edge, then outwards)
    adj = {}
    for k, (vi, ti, _) in enumerate(faces):
        if root[k] != head_root:
            continue
        loc = [int(remap[i]) for i in vi]
        for a, b in zip(loc, loc[1:] + loc[:1]):
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    rings = {}
    for part in ('up', 'lo'):
        depth = np.full(len(used), 99.0, dtype=np.float32)
        cur = [int(i) for side in 'LR' for i in chains.get(f'lid_{side}_{part}', [])]
        depth[cur] = 0
        for d in range(1, 14):
            nxt = []
            for i in cur:
                for j in adj.get(i, ()):
                    if depth[j] > d:
                        depth[j] = d
                        nxt.append(j)
            cur = nxt
        rings[part] = depth
    _TOPO = dict(tri_label=np.array(tri_label, dtype=np.int8), chains=chains, can=can, ring_up=rings['up'], ring_lo=rings['lo'])
    return _TOPO


def poly_dist(P, Q):
    """Distance from points P (n,3) to the polyline Q (m,3). Returns (distance, s) with s = arc position (0..1) of the nearest point."""
    P = np.asarray(P, dtype=np.float32)
    Q = np.asarray(Q, dtype=np.float32)
    seg = Q[1:] - Q[:-1]
    L = np.linalg.norm(seg, axis=1)
    cum = np.concatenate([[0.0], np.cumsum(L)])
    best = np.full(len(P), 1e9, dtype=np.float32)
    bs = np.zeros(len(P), dtype=np.float32)
    for i in range(len(seg)):
        d = P - Q[i]
        t = np.clip((d @ seg[i]) / (L[i] ** 2 + 1e-12), 0, 1)
        dist = np.linalg.norm(d - t[:, None] * seg[i], axis=1)
        m = dist < best
        best[m] = dist[m]
        bs[m] = cum[i] + t[m] * L[i]
    return best, bs / max(float(cum[-1]), 1e-9)


# ---------------------------------------------------------------- per-vertex data
def weight_sum(ch, bones):
    body = ch['body']
    ids = {body.vertex_groups[b].index for b in bones if b in body.vertex_groups}
    w = np.zeros(len(body.data.vertices), dtype=np.float32)
    for v in body.data.vertices:
        for g in v.groups:
            if g.group in ids:
                w[v.index] += g.weight
    return w


def target_mask(ch, name):
    B = mh.base()
    t = B.target(name)
    m = np.zeros(len(B.v), dtype=np.float32)
    if t is not None:
        m[t[0]] = np.linalg.norm(t[1], axis=1)
    m = m[ch['used']]
    return m / (m.max() + 1e-9)


def limb_coords(co, p0, p1, lateral, fwd=(0, -1.0, 0)):
    """t along the limb (0..1), angle around it (0 = lateral side, + = forward), radial distance."""
    p0, p1 = np.asarray(p0, dtype=float), np.asarray(p1, dtype=float)
    L = np.linalg.norm(p1 - p0)
    a = (p1 - p0) / L
    lat = np.asarray(lateral, dtype=float)
    lat = lat - a * lat.dot(a)
    lat /= np.linalg.norm(lat)
    f = np.asarray(fwd, dtype=float)
    f = f - a * f.dot(a) - lat * f.dot(lat)
    f /= np.linalg.norm(f)
    d = co - p0
    t = (d @ a) / L
    r = d - np.outer(d @ a, a)
    return t.astype(np.float32), np.arctan2(r @ f, r @ lat).astype(np.float32), np.linalg.norm(r, axis=1).astype(np.float32)


SKY_DIR = (-0.22, -0.48, 0.85)      # painted soft light: from above and in front, slightly from the character's right


def _sphere_dirs(n=128):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = np.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], axis=1)


def bake_light(me, co, nr, sel, sky_dir=SKY_DIR, reach=0.25):
    """Per-vertex baked light of the rest mesh, by ray casting against the body itself.
    ao: cosine-weighted openness (0 = buried, 1 = free); sky: light received from a soft dome centred on sky_dir, with shadows.
    Vertices outside sel get the unoccluded values."""
    D = _sphere_dirs(128)
    Lv = np.asarray(sky_dir, dtype=np.float64)
    Lv /= np.linalg.norm(Lv)
    wl = np.clip(D @ Lv, 0, None)
    norm = float((wl * wl).sum())
    nd = np.clip(nr.astype(np.float64) @ D.T, 0, None)                 # (N, D)
    ao = np.ones(len(co), dtype=np.float32)
    sky = (nd @ wl / norm).astype(np.float32)
    polys = [tuple(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons([Vector(c) for c in co.astype(np.float64)], polys)
    Dv = [Vector(d) for d in D]
    for i in np.where(sel)[0]:
        o = Vector(co[i].astype(np.float64) + nr[i].astype(np.float64) * 0.0009)
        w = nd[i]
        tot = a_acc = s_acc = 0.0
        for j in np.where(w > 0.08)[0]:
            wj = w[j]
            tot += wj
            hit = bvh.ray_cast(o, Dv[j], reach)
            if hit[0] is None:
                a_acc += wj
                s_acc += wj * wl[j]
            else:
                dist = hit[3]
                if dist > 0.035:                                        # far hits occlude the ambient part less
                    a_acc += wj * min(1.0, (dist - 0.035) / 0.07)
                if dist > 0.11:
                    s_acc += wj * wl[j] * (dist - 0.11) / (reach - 0.11)
        if tot > 0:
            ao[i] = a_acc / tot
            sky[i] = s_acc / norm
    # one smoothing pass over the mesh edges (ray noise)
    ed = np.array([e.vertices[:] for e in me.edges], dtype=np.int64)
    for arr in (ao, sky):
        acc = arr.astype(np.float64).copy()
        cnt = np.ones(len(arr))
        np.add.at(acc, ed[:, 0], arr[ed[:, 1]])
        np.add.at(acc, ed[:, 1], arr[ed[:, 0]])
        np.add.at(cnt, ed[:, 0], 1)
        np.add.at(cnt, ed[:, 1], 1)
        arr[:] = np.where(sel, 0.5 * arr + 0.5 * acc / cnt, arr)
    return ao, sky


def vertex_data(ch):
    """Everything the painters need, per body vertex (rest pose, object space)."""
    if 'vd' in ch:
        return ch['vd']
    B = mh.base()
    body, rig = ch['body'], ch['rig']
    me = body.data
    n = len(me.vertices)
    co = np.zeros(n * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    nr = np.zeros(n * 3, dtype=np.float32)
    me.vertices.foreach_get('normal', nr)
    nr = nr.reshape(n, 3)
    V0 = mh.to_bl(B.v[ch['used']])
    J0 = mh.joint_positions(B.v)
    E0 = (mh.to_bl(J0['eye.L____head']) + mh.to_bl(J0['eye.R____head'])) / 2
    can = np.stack([V0[:, 0] - E0[0], V0[:, 2] - E0[2], -(V0[:, 1] - E0[1])], axis=1).astype(np.float32)
    hb = rig.data.bones['head']
    head_bones = [hb.name] + [b.name for b in hb.children_recursive]
    J = {k: mh.to_bl(v) for k, v in ch['J'].items()}
    vd = dict(co=co, nr=nr, can=can, J=J,
              hw=weight_sum(ch, head_bones),
              w_neck=weight_sum(ch, ['neck01', 'neck02', 'neck03']),
              w_torso=weight_sum(ch, ['spine01', 'spine02', 'spine03', 'spine04', 'spine05', 'breast.L', 'breast.R', 'clavicle.L', 'clavicle.R',
                                      'shoulder01.L', 'shoulder01.R', 'neck01', 'root', 'pelvis.L', 'pelvis.R']),
              w_arm=weight_sum(ch, [f'{b}.{s}' for s in 'LR' for b in ('upperarm01', 'upperarm02', 'lowerarm01', 'lowerarm02')]),
              w_leg=weight_sum(ch, [f'{b}.{s}' for s in 'LR' for b in ('upperleg01', 'upperleg02', 'lowerleg01', 'lowerleg02')]),
              w_foot=weight_sum(ch, [f'foot.{s}' for s in 'LR'] + [f'toe{i}-{j}.{s}' for s in 'LR' for i in range(1, 6) for j in range(1, 4)]),
              up=target_mask(ch, 'mouth/mouth-upperlip-volume-incr'), lo=target_mask(ch, 'mouth/mouth-lowerlip-volume-incr'),
              clo=np.maximum(target_mask(ch, 'expression/units/caucasian/eye-left-closure'), target_mask(ch, 'expression/units/caucasian/eye-right-closure')))
    hand_bones = [b.name for s in 'LR' for b in [rig.data.bones[f'wrist.{s}']] + list(rig.data.bones[f'wrist.{s}'].children_recursive)]
    vd['w_hand'] = weight_sum(ch, hand_bones)
    vd['w_fingers'] = weight_sum(ch, [b for b in hand_bones if b.startswith('finger')])
    vd['w_pelvis'] = weight_sum(ch, ['root', 'pelvis.L', 'pelvis.R', 'spine05'])
    # limb parameterisation
    arm_t = np.full(n, -1.0, dtype=np.float32)
    arm_a = np.zeros(n, dtype=np.float32)
    leg_t = np.full(n, -1.0, dtype=np.float32)
    leg_a = np.zeros(n, dtype=np.float32)
    for s, sx in (('L', 1), ('R', -1)):
        t, a, r = limb_coords(co, J[f'upperarm01.{s}____head'], J[f'wrist.{s}____head'], (sx, 0, 0.6))
        sel = (co[:, 0] * sx > 0.02) & (r < 0.13) & (t > -0.25) & (t < 1.2)
        arm_t[sel], arm_a[sel] = t[sel], a[sel]
        t, a, r = limb_coords(co, J[f'upperleg01.{s}____head'], J[f'foot.{s}____head'], (sx, 0, 0))
        sel = (co[:, 0] * sx > 0.0) & (t > -0.3) & (t < 1.2)
        leg_t[sel], leg_a[sel] = t[sel], a[sel]
    vd.update(arm_t=arm_t, arm_a=arm_a, leg_t=leg_t, leg_a=leg_a)
    vd['arm_cs'] = np.stack([np.cos(arm_a), np.sin(arm_a)], axis=1)
    vd['leg_cs'] = np.stack([np.cos(leg_a), np.sin(leg_a)], axis=1)
    vd['eye_c'] = [np.array(e.location[:], dtype=np.float32) for e in ch['eyes']]
    ev = np.array([v.co[:] for v in ch['eyes'][0].data.vertices])
    vd['eye_r'] = float(np.percentile(np.linalg.norm(ev, axis=1), 60))
    # feature lines (rest-pose polylines) and baked light
    topo = topology()
    vd['chains'] = {k: co[ids].astype(np.float32) for k, ids in topo['chains'].items()}
    vd['ring_up'], vd['ring_lo'] = topo['ring_up'], topo['ring_lo']
    lit = (vd['hw'] + vd['w_neck'] + vd['w_hand'] > 0.02) | (co[:, 2] > J['neck01____head'][2] - 0.14)
    vd['ao'], vd['sky'] = bake_light(me, co, nr, lit)
    ch['vd'] = vd
    return vd


# ---------------------------------------------------------------- texel access
_WIN_CACHE = {}


def raster_window(win, size):
    """Like uvbake.raster, for a sub-rectangle of UV space at its own resolution (in memory: only a few thousand triangles)."""
    key = (tuple(win), tuple(size))
    if key in _WIN_CACHE:
        return _WIN_CACHE[key]
    tv, tuv, used = uvbake.body_tris()
    u0, v0, u1, v1 = win
    W, H = size
    P = np.empty_like(tuv)
    P[..., 0] = (tuv[..., 0] - u0) / (u1 - u0) * W
    P[..., 1] = (tuv[..., 1] - v0) / (v1 - v0) * H
    lo, hi = P.min(axis=1), P.max(axis=1)
    tri = -np.ones((H, W), dtype=np.int32)
    bary = np.zeros((H, W, 3), dtype=np.float32)
    for t in np.where((hi[:, 0] > -1) & (lo[:, 0] < W + 1) & (hi[:, 1] > -1) & (lo[:, 1] < H + 1))[0]:
        (x0, y0), (x1, y1), (x2, y2) = P[t]
        minx, maxx = max(int(np.floor(lo[t, 0] - 0.5)), 0), min(int(np.ceil(hi[t, 0] + 0.5)), W - 1)
        miny, maxy = max(int(np.floor(lo[t, 1] - 0.5)), 0), min(int(np.ceil(hi[t, 1] + 0.5)), H - 1)
        if maxx < minx or maxy < miny:
            continue
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        X, Y = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
        l0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
        l1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
        l2 = 1 - l0 - l1
        inside = np.minimum(np.minimum(l0, l1), l2)
        sub_t = tri[miny:maxy + 1, minx:maxx + 1]
        sub_b = bary[miny:maxy + 1, minx:maxx + 1]
        prev = np.where(sub_t >= 0, sub_b.min(axis=2), -1.0)
        w = (inside >= -0.02) & (inside > prev)
        sub_t[w] = t
        sub_b[w, 0], sub_b[w, 1], sub_b[w, 2] = l0[w], l1[w], l2[w]
    _WIN_CACHE[key] = dict(tri=tri, bary=bary, tv=tv, S=max(W, H))
    return _WIN_CACHE[key]


class Texels:
    """Per-texel access to the per-vertex data (valid texels only, as 1-D arrays).
    Default: the whole body atlas at S x S.  With window=(u0, v0, u1, v1) and size=(W, H): only that part of UV space."""

    def __init__(self, ch, S=TEX, window=None, size=None):
        if window is None:
            self.R = uvbake.raster(S)
            self.W = self.H = S
            self.window = (0.0, 0.0, 1.0, 1.0)
        else:
            self.W, self.H = size
            self.R = raster_window(window, size)
            self.window = tuple(window)
        self.S = S
        self.valid = self.R['tri'] >= 0
        self.tri = self.R['tri'][self.valid]
        self.vids = self.R['tv'][self.tri]
        self.b = self.R['bary'][self.valid]
        self.vd = vertex_data(ch)
        self.n = int(self.valid.sum())
        self._cache = {}

    def get(self, key):
        if key not in self._cache:
            a = np.asarray(self.vd[key], dtype=np.float32)
            if a.ndim == 1:
                self._cache[key] = (a[self.vids] * self.b).sum(axis=1)
            else:
                self._cache[key] = (a[self.vids] * self.b[:, :, None]).sum(axis=1)
        return self._cache[key]

    def island(self):
        """UV island label per texel (ISL_*)."""
        if '_island' not in self._cache:
            self._cache['_island'] = topology()['tri_label'][self.tri]
        return self._cache['_island']

    def uv(self):
        """Atlas UV of every valid texel."""
        if '_uv' not in self._cache:
            ys, xs = np.nonzero(self.valid)
            u0, v0, u1, v1 = self.window
            self._cache['_uv'] = np.stack([u0 + (xs + 0.5) / self.W * (u1 - u0), v0 + (ys + 0.5) / self.H * (v1 - v0)], axis=1).astype(np.float32)
        return self._cache['_uv']

    def sample(self, tex):
        """Bilinear lookup of an atlas-space image (h, w, c), row 0 = v 0, at every valid texel."""
        h, w = tex.shape[:2]
        uv = self.uv()
        x = np.clip(uv[:, 0] * w - 0.5, 0, w - 1.001)
        y = np.clip(uv[:, 1] * h - 0.5, 0, h - 1.001)
        xi, yi = x.astype(np.int64), y.astype(np.int64)
        fx, fy = (x - xi)[:, None], (y - yi)[:, None]
        return ((tex[yi, xi] * (1 - fx) + tex[yi, xi + 1] * fx) * (1 - fy) + (tex[yi + 1, xi] * (1 - fx) + tex[yi + 1, xi + 1] * fx) * fy).astype(np.float32)

    def image(self, rgb, alpha=None, name='tex', bleed=10, down=1):
        out = np.zeros((self.H, self.W, 3), dtype=np.float32)
        out[self.valid] = np.clip(rgb, 0, 1)
        out = uvbake.dilate(out, self.valid, bleed)
        if alpha is None:
            a = np.ones((self.H, self.W, 1), dtype=np.float32)
        else:
            a = np.zeros((self.H, self.W), dtype=np.float32)
            a[self.valid] = alpha
            a = uvbake.dilate(a[..., None], self.valid, bleed)
        arr = np.concatenate([out, a], axis=2)
        if down > 1:                      # PS2-size texture: block average
            arr = arr.reshape(self.H // down, down, self.W // down, down, 4).mean(axis=(1, 3))
        return uvbake.to_image(name, arr)


# ---------------------------------------------------------------- painted strokes (eyebrow hairs)
def draw_strokes(shape, strokes):
    """Soft tapered polylines drawn into an ink map (H, W), values 0..1.  strokes: (points (k,2) in pixels, w_root, w_tip, opacity)."""
    H, W = shape
    ink = np.zeros(shape, dtype=np.float32)
    for pts, w0, w1, a in strokes:
        pts = np.asarray(pts, dtype=np.float32)
        pad = max(w0, w1) + 2
        x0, x1 = max(int(pts[:, 0].min() - pad), 0), min(int(pts[:, 0].max() + pad) + 1, W)
        y0, y1 = max(int(pts[:, 1].min() - pad), 0), min(int(pts[:, 1].max() + pad) + 1, H)
        if x1 <= x0 or y1 <= y0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        best = np.full(xx.shape, 1e9, dtype=np.float32)
        bt = np.zeros(xx.shape, dtype=np.float32)
        ns = len(pts) - 1
        for i in range(ns):
            p, d = pts[i], pts[i + 1] - pts[i]
            t = np.clip(((xx - p[0]) * d[0] + (yy - p[1]) * d[1]) / (d @ d + 1e-9), 0, 1)
            dist = np.hypot(xx - p[0] - t * d[0], yy - p[1] - t * d[1])
            m = dist < best
            best = np.where(m, dist, best)
            bt = np.where(m, (i + t) / ns, bt)
        cov = np.clip(w0 + (w1 - w0) * bt - best + 0.5, 0, 1) * a
        sub = ink[y0:y1, x0:x1]
        sub[:] = 1 - (1 - sub) * (1 - cov)
    return ink


def _blur(a, r):
    if r <= 0:
        return a
    k = np.exp(-(np.arange(-3 * r, 3 * r + 1) / r) ** 2 / 2).astype(np.float32)
    k /= k.sum()
    a = np.apply_along_axis(lambda m: np.convolve(m, k, mode='same'), 0, a)
    return np.apply_along_axis(lambda m: np.convolve(m, k, mode='same'), 1, a)


BROW_PX = 0.0001                    # the brow is drawn at 0.1 mm per pixel, then looked up per texel
BROW_BOX = (0.0, 0.068, -0.002, 0.036)


def brow_axis(b, n=200):
    """Centre line of the brow, resampled: points (n,2) in (ax, cy), unit tangents, half thickness."""
    line = np.asarray(b['line'], dtype=np.float64)
    seg = np.linalg.norm(np.diff(line, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    # smooth the polyline (two passes of corner cutting, then arc-length resampling)
    pts = line
    for _ in range(3):
        q = np.empty((2 * len(pts) - 2, 2))
        q[0::2] = 0.75 * pts[:-1] + 0.25 * pts[1:]
        q[1::2] = 0.25 * pts[:-1] + 0.75 * pts[1:]
        pts = np.vstack([pts[:1], q, pts[-1:]])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    C = np.stack([np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])], axis=1)
    Tn = np.gradient(C, axis=0)
    Tn /= np.linalg.norm(Tn, axis=1, keepdims=True)
    th = np.asarray(b['thick'], dtype=np.float64)
    half = np.interp(C[:, 0], th[:, 0], th[:, 1]) / 2
    return C, Tn, half


def brow_map(b, seed):
    """One eyebrow as an ink map in the canonical (|cx|, cy) plane: a soft core plus individual hair strokes (direction field:
    upright at the nose end, sweeping outwards, upper and lower hairs converging on the ridge, flat along the tail)."""
    x0, x1, y0, y1 = BROW_BOX
    W, H = int(round((x1 - x0) / BROW_PX)), int(round((y1 - y0) / BROW_PX))
    C, Tn, half = brow_axis(b)
    Nn = np.stack([-Tn[:, 1], Tn[:, 0]], axis=1)                      # towards the forehead
    n = len(C)
    rng = np.random.default_rng(seed)
    px = lambda p: np.stack([(p[..., 0] - x0) / BROW_PX, (p[..., 1] - y0) / BROW_PX], axis=-1)
    strokes = []
    for _ in range(int(b.get('hairs', 300))):
        s = rng.beta(1.05, 1.25)                                       # a little denser towards the nose
        k = min(int(s * (n - 1)), n - 1)
        nn = float(np.clip(rng.normal(0, 0.55), -1.0, 1.0))
        root = C[k] + Nn[k] * nn * half[k] * 0.92
        base = np.interp(s, [0.0, 0.1, 0.28, 0.6, 1.0], [80, 62, 30, 12, 2])            # hair angle to the brow axis (degrees)
        conv = np.interp(s, [0.0, 0.2, 0.5, 1.0], [6, 16, 24, 14])                      # converge on the ridge line
        ang = math.radians(base - conv * nn + rng.normal(0, 7))
        ln = np.interp(s, [0, 0.3, 0.7, 1.0], [0.0050, 0.0052, 0.0042, 0.0028]) * rng.uniform(0.7, 1.2) * b.get('hair_len', 1.0)
        bend = math.radians(rng.uniform(8, 22))
        pts = [root]
        for q in range(3):
            a = ang - bend * q / 2
            d = Tn[k] * math.cos(a) + Nn[k] * math.sin(a)
            pts.append(pts[-1] + d * ln / 3)
        w = rng.uniform(0.00022, 0.00034) / BROW_PX * b.get('hair_w', 1.0)
        strokes.append((px(np.array(pts)), w, w * 0.3, rng.uniform(0.7, 1.0)))
    ink = draw_strokes((H, W), strokes)
    # soft core: inside the outline, fading at the edges and at both ends
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    P = np.stack([x0 + (xx + 0.5) * BROW_PX, y0 + (yy + 0.5) * BROW_PX], axis=-1).reshape(-1, 2)
    P = P.astype(np.float32)
    best = np.full(len(P), 1e9, dtype=np.float32)
    j = np.zeros(len(P), dtype=np.int64)
    for k in range(0, n, 3):
        d2 = (P[:, 0] - C[k, 0]) ** 2 + (P[:, 1] - C[k, 1]) ** 2
        m = d2 < best
        best[m] = d2[m]
        j[m] = k
    dn = ((P - C[j]) * Nn[j]).sum(axis=1)
    dt = ((P - C[j]) * Tn[j]).sum(axis=1)
    core = sm(1.0, 0.45, np.abs(dn) / np.maximum(half[j], 1e-5)) * sm(0.0012, 0.0, np.abs(dt) - 0.0002)
    core = core.reshape(H, W) * sm(0.0, 0.07, (j / (n - 1)).reshape(H, W) + 0.02)
    out = np.clip(b.get('core', 0.6) * core + ink * b.get('ink', 0.95), 0, 1)
    return _blur(out, 1.0)


def brow_lookup(maps, cx, cy):
    """Ink of the eyebrows at canonical positions (left brow where cx > 0)."""
    x0, x1, y0, y1 = BROW_BOX
    out = np.zeros(len(cx), dtype=np.float32)
    for side, m in ((1, maps[0]), (-1, maps[1])):
        H, W = m.shape
        fx = (cx * side - x0) / BROW_PX - 0.5
        fy = (cy - y0) / BROW_PX - 0.5
        ok = (fx > 0) & (fx < W - 1.01) & (fy > 0) & (fy < H - 1.01)
        xi, yi = fx[ok].astype(np.int64), fy[ok].astype(np.int64)
        tx, ty = fx[ok] - xi, fy[ok] - yi
        out[ok] = (m[yi, xi] * (1 - tx) + m[yi, xi + 1] * tx) * (1 - ty) + (m[yi + 1, xi] * (1 - tx) + m[yi + 1, xi + 1] * tx) * ty
    return out


# ---------------------------------------------------------------- skin
_TEXCACHE = {}


def _photo(path):
    if path not in _TEXCACHE:
        import mhassets
        _TEXCACHE[path] = mhassets.load_pixels(path)[..., :3].copy()
    return _TEXCACHE[path]


def skin_colors(ch, P, T):
    """The painter: one sRGB colour per valid texel of T (body atlas or face patch)."""
    vd = T.vd
    can, pos, nr, hw = T.get('can'), T.get('co'), T.get('nr'), T.get('hw')
    nr = nr / (np.linalg.norm(nr, axis=1, keepdims=True) + 1e-9)
    cx, cy, cz = can[:, 0], can[:, 1], can[:, 2]
    ax = np.abs(cx)
    isl = T.island()
    skin_isl = (isl == ISL_HEAD)
    face = sm(0.05, 0.4, hw) * sm(-0.06, -0.02, cz) * skin_isl
    tone, shadow, deep = srgb(P['skin']), srgb(P['skin_shadow']), srgb(P['skin_deep'])
    blush, lipc, browc, lash = srgb(P['blush']), srgb(P['lip']), srgb(P['brow']), srgb(P.get('lash', [18, 14, 14]))
    hi = srgb(P.get('highlight', [255, 240, 226]))
    cool = srgb(P.get('cool', [150, 128, 150]))
    seed = P.get('seed', 1)
    lipraw = np.zeros(T.n, dtype=np.float32)
    if P.get('base_tex'):
        # photo-based MakeHuman skin (CC0) as the base layer, graded towards the wanted tone
        tex = _photo(P['base_tex'])
        c = T.sample(tex)
        if '_skin_ref' not in ch:
            m = (isl == ISL_HEAD) & (hw > 0.5) & (cz > -0.03) & (((np.abs(ax - 0.042) < 0.016) & (cy > -0.05) & (cy < -0.018)) | ((ax < 0.035) & (cy > 0.03) & (cy < 0.052)))
            ch['_skin_ref'] = c[m].mean(axis=0)
        ref = ch['_skin_ref']
        lipraw = sm(0.70, 0.60, c[:, 1] / np.maximum(c[:, 0], 1e-3))        # the photo's own lip painting (redder than skin)
        c = c * (tone / ref)[None, :]
        c = (c - tone) * P.get('tex_contrast', 1.15) + tone
    else:
        c = np.tile(tone, (T.n, 1))
        c = c * (1 + (fbm2(pos[:, 0] * 30, (pos[:, 2] + pos[:, 1]) * 30, seed, 3) - 0.5)[:, None] * 0.07)
    # ---- colour zones: warm cheeks / nose / ears / chin, yellower forehead, cooler eye sockets and jaw
    kz = P.get('zones', 1.0)
    c = mix(c, blush, kz * 0.26 * gauss(ax - 0.046, 0.022) * gauss(cy + 0.034, 0.02) * face)             # cheeks
    c = mix(c, blush, kz * 0.24 * gauss(cx, 0.013) * gauss(cy + 0.041, 0.012) * face)                    # nose tip and wings
    c = mix(c, blush, kz * 0.12 * gauss(cx, 0.02) * gauss(cy + 0.098, 0.012) * face)                     # chin
    c = mix(c, blush, kz * 0.34 * sm(0.066, 0.08, ax) * sm(-0.065, -0.03, cy) * sm(0.02, -0.02, cy) * sm(0.02, 0.3, hw) * skin_isl)   # ears
    c = c * (1 + kz * np.array([0.0, 0.012, -0.03], dtype=np.float32) * (gauss(cx, 0.05) * gauss(cy - 0.045, 0.025) * face)[:, None])   # forehead
    c = mix(c, cool, kz * 0.16 * gauss(ax - 0.031, 0.017) * gauss(cy - 0.006, 0.011) * face)             # eye sockets
    c = mix(c, cool, kz * 0.08 * sm(0.035, 0.062, ax) * sm(-0.045, -0.085, cy) * face)                   # jaw sides
    # ---- baked soft light (painted shading, PS2 style): dome light with real occlusion + ambient openness
    ao, sky = T.get('ao'), T.get('sky')
    k = P.get('bake', 0.8)
    s = np.clip(P.get('ambient', 0.3) * ao + (1 - P.get('ambient', 0.3)) * np.clip(sky, 0, 1.2) ** 0.85 * (0.4 + 0.6 * ao), 0, 1.1)
    c = c * (1 + ((shadow / tone)[None, :] - 1) * (k * sm(0.74, 0.40, s))[:, None])
    c = c * (1 + ((deep / shadow)[None, :] - 1) * (k * sm(0.40, 0.10, s))[:, None])
    c = c * (1 + 0.07 * k * sm(0.82, 1.0, s))[:, None]
    # ---- painted contour and occlusion accents
    eye_d = np.minimum(np.linalg.norm(pos - vd['eye_c'][0], axis=1), np.linalg.norm(pos - vd['eye_c'][1], axis=1))
    er = vd['eye_r']
    kc = P.get('contour', 1.0)
    c = mix(c, shadow, kc * 0.36 * gauss(ax - 0.030, 0.016) * gauss(cy - 0.0075, 0.0055) * face)         # upper lid, under the brow ridge
    c = mix(c, deep, kc * 0.24 * gauss(ax - 0.0185, 0.006) * gauss(cy - 0.003, 0.009) * face)            # inner corners / nose root sides
    c = mix(c, shadow, kc * 0.16 * gauss(ax - 0.045, 0.006) * gauss(cy - 0.001, 0.006) * face)           # outer corners
    c = mix(c, shadow, kc * 0.40 * gauss(ax - 0.0135, 0.005) * sm(-0.046, -0.03, cy) * sm(0.012, -0.004, cy) * face)   # nose flanks
    c = mix(c, shadow, kc * 0.30 * gauss(ax - 0.0175, 0.004) * gauss(cy + 0.043, 0.006) * face)          # wing crease
    c = mix(c, deep, kc * 0.35 * gauss(cx, 0.014) * gauss(cy + 0.0525, 0.0035) * face)                   # under the nose
    c = mix(c, shadow, kc * 0.38 * gauss(cx, 0.02) * gauss(cy + 0.0865, 0.005) * face)                   # under the lower lip
    c = mix(c, shadow, kc * 0.50 * gauss(ax - 0.052, 0.014) * gauss(cy + 0.055, 0.024) * sm(0.03, 0.045, ax) * face)   # under the cheekbones
    c = mix(c, shadow, kc * 0.32 * sm(0.052, 0.072, ax) * gauss(cy - 0.03, 0.03) * face)                 # temples
    c = mix(c, shadow, kc * 0.36 * sm(0.036, 0.06, ax) * sm(-0.072, -0.1, cy) * face)                    # jaw sides
    c = mix(c, deep, 0.9 * sm(-0.45, -0.85, nr[:, 2]) * gauss(ax - 0.0085, 0.006) * gauss(cy + 0.0445, 0.006) * face)   # nostrils
    c = mix(c, shadow, kc * 0.16 * gauss(cx, 0.003) * sm(-0.0595, -0.0575, cy) * sm(-0.05, -0.053, cy) * face)         # philtrum groove
    kh = P.get('lights', 1.0)
    c = mix(c, hi, kh * 0.32 * gauss(cx, 0.0045) * sm(-0.04, -0.02, cy) * sm(0.016, -0.004, cy) * face)   # nose bridge
    c = mix(c, hi, kh * 0.26 * gauss(cx, 0.006) * gauss(cy + 0.0385, 0.005) * face)                      # nose tip
    c = mix(c, hi, kh * 0.25 * gauss(ax - 0.045, 0.013) * gauss(cy + 0.016, 0.0075) * face)              # cheekbone tops
    c = mix(c, hi, kh * 0.20 * gauss(ax - 0.031, 0.012) * gauss(cy - 0.0255, 0.005) * face)              # brow bone
    c = mix(c, hi, kh * 0.18 * gauss(cx, 0.026) * gauss(cy - 0.044, 0.016) * face)                       # forehead
    c = mix(c, hi, kh * 0.20 * gauss(cx, 0.011) * gauss(cy + 0.098, 0.007) * face)                       # chin
    c = mix(c, hi, kh * 0.20 * gauss(ax - 0.0048, 0.0018) * sm(-0.0595, -0.0575, cy) * sm(-0.051, -0.054, cy) * face)  # philtrum ridges
    c = mix(c, hi, kh * 0.14 * gauss(ax - 0.031, 0.008) * gauss(cy + 0.0085, 0.002) * face)              # lower lid ridge
    # ---- lips
    up, lo = T.get('up'), T.get('lo')
    mzone = sm(0.036, 0.03, ax) * sm(-0.092, -0.086, cy) * sm(-0.05, -0.054, cy) * skin_isl
    lipm = sm(0.2, 0.62, lipraw) * mzone if P.get('base_tex') else np.maximum(sm(0.22, 0.4, up), sm(0.3, 0.5, lo) * sm(-0.084, -0.079, cy)) * skin_isl
    is_up = up > lo
    ls = P.get('lip_strength', 1.0)
    d_lip = np.full(T.n, 1.0, dtype=np.float32)
    s_lip = np.zeros(T.n, dtype=np.float32)
    mi = np.where((ax < 0.045) & (cy < -0.045) & (cy > -0.095) & (cz > -0.04) & (hw > 0.3))[0]
    if 'lip_up' in vd['chains'] and len(mi):
        d1, s1 = poly_dist(pos[mi], vd['chains']['lip_up'])
        d2, s2 = poly_dist(pos[mi], vd['chains']['lip_lo'])
        d_lip[mi] = np.minimum(d1, d2)
        s_lip[mi] = np.where(d1 < d2, s1, s2)
    crease = vnoise(cx * 2600, cy * 260, seed + 31) - 0.5
    lipm = sm(0.1, 0.72, lipraw) * mzone if P.get('base_tex') else lipm
    c = np.where((lipm > 0.01)[:, None], np.minimum(c, tone[None, :] * 1.03), c)                         # no photo speculars on the lips
    lip_lo = lipc * ((0.86 + 0.14 * sm(0.0, 0.004, d_lip)) * (1 + 0.09 * crease))[:, None]
    lip_up = lipc * np.asarray(P.get('lip_upper', [0.9, 0.84, 0.84]), dtype=np.float32) * ((0.72 + 0.24 * sm(0.0004, 0.0062, d_lip)) * (1 + 0.07 * crease))[:, None]
    c = np.where(is_up[:, None], c + (lip_up - c) * (lipm * ls)[:, None], c + (lip_lo - c) * (lipm * ls)[:, None])
    c = mix(c, hi, 0.26 * lipm * (~is_up) * gauss(cx, 0.0085) * gauss(d_lip - 0.0048, 0.0022))            # lower lip light
    c = mix(c, hi, kh * 0.20 * gauss(cx, 0.012) * gauss(cy + 0.0577, 0.0016) * (1 - lipm) * face)        # cupid's bow edge
    mline = srgb(P.get('mouth_line', [50, 22, 22]))
    wline = 0.0002 + 0.0002 * np.sin(np.pi * np.clip(s_lip, 0, 1))                                        # thinner at the corners
    c = mix(c, mline, 0.9 * sm(wline + 0.0003, wline, d_lip) * skin_isl)
    if 'lip_up' in vd['chains']:
        for corner in (vd['chains']['lip_up'][0], vd['chains']['lip_up'][-1]):                            # mouth corners
            dc = np.linalg.norm(pos - corner, axis=1)
            c = mix(c, deep, 0.5 * gauss(dc, 0.002) * skin_isl)
    # ---- eyebrows: hair strokes drawn in the canonical frame
    b = P['brows']
    if '_brow_maps' not in ch or ch.get('_brow_key') != repr(b):
        ch['_brow_maps'] = (brow_map(b, seed + 5), brow_map(b, seed + 6))
        ch['_brow_key'] = repr(b)
    bi = np.where((ax < BROW_BOX[1]) & (cy > BROW_BOX[2]) & (cy < BROW_BOX[3]) & (cz > -0.035) & skin_isl & (hw > 0.3))[0]
    if len(bi):
        ink = brow_lookup(ch['_brow_maps'], cx[bi], cy[bi])
        c[bi] = mix(c[bi], browc * 1.6, 0.35 * sm(0.0, 0.5, ink))            # soft shadow under the hairs
        c[bi] = mix(c[bi], browc, np.clip(ink * 1.15, 0, 1))
    # ---- eyes: lash lines, waterline and tear duct follow the edge loops of the real eyelid rims
    lashw = P.get('lash_w', 1.0)
    ru, rl = T.get('ring_up'), T.get('ring_lo')
    ei = np.where((np.minimum(ru, rl) < 11.0) & skin_isl)[0]
    if len(ei):
        ce, r_u, r_l, axe, cye = c[ei], ru[ei], rl[ei], ax[ei], cy[ei]
        se = np.clip((axe - 0.0205) / 0.023, 0, 1)                         # 0 = inner corner, 1 = outer corner
        upper = r_u <= r_l
        lower = ~upper
        # smoky upper lid, darker towards the outer corner; lid crease
        ce = mix(ce, shadow, P.get('lid_smoke', 0.3) * sm(9.5, 4.0, r_u) * upper * (0.55 + 0.45 * sm(0.25, 0.9, se)))
        ccy = P.get('crease', 0.0093) - 0.0052 * ((axe - 0.0315) / 0.0125) ** 2
        ce = mix(ce, deep, 0.3 * gauss(cye - ccy, 0.00065) * upper * sm(0.03, 0.22, se) * sm(1.0, 0.8, se))
        # upper lash line: the whole shelf of the lid plus a band above its edge, thicker towards the outer third
        tk = 3.0 + (0.45 + 1.0 * sm(0.12, 0.8, se)) * lashw
        ce = mix(ce, lash, sm(tk + 0.4, tk - 0.1, r_u) * upper * sm(0.0, 0.07, se + 0.02))
        # the wing: the lash line runs on a little past the outer corner
        wl_ = P.get('wing', 0.0034)
        if wl_ > 0:
            A_, d_ = np.array([0.0434, 0.0006]), np.array([0.9, 0.44]) * wl_
            tt = np.clip(((axe - A_[0]) * d_[0] + (cye - A_[1]) * d_[1]) / (d_ @ d_), 0, 1)
            dw = np.hypot(axe - A_[0] - tt * d_[0], cye - A_[1] - tt * d_[1])
            ww = 0.00075 * (1 - tt) * lashw
            ce = mix(ce, lash, sm(ww + 0.0003, ww - 0.0001, dw) * (ww > 2e-5) * (r_u > 2.5))
        # lower lid: wet rim on the shelf, thin lash line on the outer two thirds, soft shade under it
        ce = mix(ce, srgb(P.get('lid_rim', [208, 142, 130])), 0.85 * sm(3.0, 2.3, r_l) * lower)
        ce = mix(ce, lash * 1.6 + 0.03, 0.6 * sm(2.5, 3.0, r_l) * sm(4.1, 3.4, r_l) * lower * sm(0.18, 0.6, se) * min(lashw, 1.5))
        ce = mix(ce, shadow, 0.2 * sm(3.2, 4.0, r_l) * sm(8.0, 5.0, r_l) * lower * sm(0.1, 0.5, se))
        # tear duct
        ce = mix(ce, srgb(P.get('caruncle', [200, 118, 112])), 0.8 * sm(0.0216, 0.0202, axe) * sm(4.4, 3.2, np.minimum(r_u, r_l)))
        c[ei] = ce
    sock = (isl == ISL_SOCK_L) | (isl == ISL_SOCK_R)
    if sock.any():
        c = np.where(sock[:, None], (deep * 0.55)[None, :], c)
    # ---- stubble: faint cool shadow with grain
    lipzone = lipm
    if P.get('stubble', 0) > 0:
        tj = np.clip((0.07 - ax) / 0.045, 0, 1)
        line = -0.022 - 0.045 * tj
        bz = (np.where(ax > 0.027, sm(line + 0.004, line - 0.006, cy), sm(-0.052, -0.058, cy))) * sm(-0.08, -0.03, cz) * sm(0.1, 0.5, hw) * (1 - lipzone) * skin_isl
        bz = bz * sm(-0.2, -0.13, cy)
        grain = vnoise(pos[:, 0] * 2400, pos[:, 2] * 2400 + pos[:, 1] * 1700, seed + 9)
        c = mix(c, srgb(P.get('stubble_col', [96, 88, 96])), P['stubble'] * bz * (0.45 + 0.55 * grain))
    # ---- mouth cavity
    mouth = isl == ISL_MOUTH
    if mouth.any():
        dark = srgb(P.get('mouth_inside', [52, 16, 18]))
        inner = lipc * np.array([0.82, 0.7, 0.72], dtype=np.float32)
        c = np.where(mouth[:, None], dark[None, :] * (0.3 + 0.7 * sm(0.02, 0.004, d_lip))[:, None] + (inner - dark)[None, :] * sm(0.0055, 0.0012, d_lip)[:, None], c)
    # ---- scalp under the hair: hair shadow colour
    az = np.arctan2(ax, cz + 0.095)
    hl = np.interp(az, P['hairline_az'], P['hairline_y'])
    scalp = sm(hl - 0.003, hl + 0.005, cy) * sm(0.2, 0.6, hw) * skin_isl
    ears = (ax > 0.066) & (cy > -0.06) & (cy < 0.012) & (cz > -0.14) & (cz < -0.06)
    scalp = scalp * (~ears)
    c = mix(c, srgb(P['scalp']), 0.92 * scalp)
    # ---- fingerless gloves painted on the hands
    if P.get('glove') is not None:
        wh, wf = T.get('w_hand'), T.get('w_fingers')
        gl = sm(0.45, 0.6, wh - wf) * sm(0.55, 0.4, wf)
        gcol = srgb(P['glove']) * (0.55 + 0.75 * np.clip(s, 0, 1))[:, None]
        c = mix(c, gcol, gl)
    # ---- skin grain (pores), a little stronger on the face patch scale
    g = (vnoise(pos[:, 0] * 900, pos[:, 2] * 900 + pos[:, 1] * 700, seed + 3) - 0.5) * 0.035
    g = g + (vnoise(pos[:, 0] * 2600 + pos[:, 1] * 900, pos[:, 2] * 2600 - pos[:, 1] * 1300, seed + 4) - 0.5) * P.get('grain', 0.04) * face
    c = c * (1 + g)[:, None]
    return c


def paint_skin(ch, P, T=None):
    """Hand-painted style skin for the whole body atlas. Returns (image, Texels)."""
    T = T or Texels(ch)
    return T.image(skin_colors(ch, P, T), name=ch['name'] + '_skin', bleed=12, down=P.get('down', 2)), T


def paint_face(ch, P):
    """The same painting at a higher texel density, for the front of the face only. Returns (image, Texels)."""
    T = Texels(ch, window=FACE_WIN, size=FACE_RASTER)
    return T.image(skin_colors(ch, P, T), name=ch['name'] + '_face', bleed=8, down=2), T


def skin_material(name, img, rough=0.72, spec=0.14, closest=False, face_img=None, face_win=FACE_WIN, fade=0.03):
    """Skin material. With face_img the denser face patch replaces the atlas inside face_win (soft border)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = 'Closest' if closest else 'Linear'
    out = tx.outputs['Color']
    if face_img is not None:
        u0, v0, u1, v1 = face_win
        uvn = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (1 / (u1 - u0), 1 / (v1 - v0), 1)
        mp.inputs['Location'].default_value = (-u0 / (u1 - u0), -v0 / (v1 - v0), 0)
        nt.links.new(uvn.outputs['UV'], mp.inputs['Vector'])
        fx = nt.nodes.new('ShaderNodeTexImage')
        fx.image = face_img
        fx.interpolation = 'Closest' if closest else 'Linear'
        fx.extension = 'EXTEND'
        nt.links.new(mp.outputs['Vector'], fx.inputs['Vector'])
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(mp.outputs['Vector'], sep.inputs[0])

        def edge(sock):                        # 0 at the borders of the patch, 1 inside
            a = nt.nodes.new('ShaderNodeMath')
            a.operation = 'SUBTRACT'
            a.inputs[1].default_value = 0.5
            nt.links.new(sock, a.inputs[0])
            ab = nt.nodes.new('ShaderNodeMath')
            ab.operation = 'ABSOLUTE'
            nt.links.new(a.outputs[0], ab.inputs[0])
            mr = nt.nodes.new('ShaderNodeMapRange')
            mr.interpolation_type = 'SMOOTHSTEP'
            mr.inputs['From Min'].default_value = 0.5
            mr.inputs['From Max'].default_value = 0.5 - fade
            mr.inputs['To Min'].default_value = 0.0
            mr.inputs['To Max'].default_value = 1.0
            nt.links.new(ab.outputs[0], mr.inputs['Value'])
            return mr.outputs['Result']
        mul = nt.nodes.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        nt.links.new(edge(sep.outputs['X']), mul.inputs[0])
        nt.links.new(edge(sep.outputs['Y']), mul.inputs[1])
        mixn = nt.nodes.new('ShaderNodeMix')
        mixn.data_type = 'RGBA'
        nt.links.new(mul.outputs[0], mixn.inputs['Factor'])
        nt.links.new(tx.outputs['Color'], mixn.inputs['A'])
        nt.links.new(fx.outputs['Color'], mixn.inputs['B'])
        out = mixn.outputs['Result']
    nt.links.new(out, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Subsurface Weight'].default_value = 0.0
    return m


# ---------------------------------------------------------------- eyes
EYE_RANGE = 0.8                     # the eye texture covers direction components -0.8..0.8 around the eye axis


def eye_texture(name, E, size=128, ss=4):
    """Painted eye, seen along its axis: sclera, limbal ring, iris fibres, pupil, baked lid shade and catch-lights.
    x = towards the character's left, y = up; the alpha channel holds the catch-light mask."""
    S = size * ss
    y, x = np.mgrid[0:S, 0:S].astype(np.float32)
    dx = ((x + 0.5) / S * 2 - 1) * EYE_RANGE
    dz = ((y + 0.5) / S * 2 - 1) * EYE_RANGE
    r = np.hypot(dx, dz)
    ang = np.arctan2(dz, dx)
    ri = math.sin(math.radians(E.get('iris_deg', 25.0)))
    q = r / ri
    seed = E.get('seed', 7)
    scl, edge = srgb(E.get('sclera', [226, 220, 214])), srgb(E.get('sclera_edge', [150, 122, 118]))
    c = mix(np.tile(scl, (S, S, 1)), edge, sm(0.42, 0.8, r))
    c = mix(c, srgb([196, 150, 146]), 0.3 * sm(0.3, 0.75, np.abs(dx)) * fbm2(dx * 9, dz * 14, seed, 3))       # faint veins towards the corners
    i_out, i_in, limb = srgb(E['iris']), srgb(E['iris_in']), srgb(E.get('limbus', [14, 20, 30]))
    au = ang / (2 * np.pi) + 0.5
    fib = fbm2(au * 46, q * 1.6, seed + 1, 3) * 0.6 + vnoise(au * 110, q * 3.0, seed + 2) * 0.4               # radial fibres
    fib2 = vnoise(au * 23, q * 0.8, seed + 3)
    ic = mix(np.tile(i_in, (S, S, 1)), i_out, sm(0.38, 0.92, q + 0.12 * (fib2 - 0.5)))
    ic = ic * (0.72 + 0.56 * fib)[..., None]
    pup = E.get('pupil', 0.36)
    ic = mix(ic, srgb(E.get('collarette', [176, 170, 150])), 0.45 * gauss(q - (pup + 0.12), 0.09) * (0.4 + 0.6 * fib))   # lighter ring round the pupil
    ic = mix(ic, limb, sm(0.78, 0.99, q) * 0.92)                                                            # limbal ring
    ic = ic * (1 - E.get('lid_shade', 0.55) * sm(-0.25, 0.85, dz / ri))[..., None]                           # upper half in the lid's shade
    glow = E.get('glow_k', 0.35) * gauss(dz / ri + 0.5, 0.3) * gauss(dx / ri - 0.12, 0.6) * sm(0.97, 0.7, q) * sm(pup, pup + 0.2, q)
    ic = ic + srgb(E.get('glow', [150, 190, 215]))[None, None, :] * glow[..., None]                          # soft light in the lower iris
    ic = mix(ic, np.array([0.012, 0.012, 0.016], dtype=np.float32), sm(pup + 0.035, pup - 0.02, q))          # pupil
    c = mix(c, limb, 0.55 * gauss(q - 1.0, 0.07) * (q > 1.0))                                                # soft dark halo outside the limbus
    c = mix(c, ic, sm(1.02, 0.97, q))
    hl = np.zeros((S, S), dtype=np.float32)
    for hx, hz, rx, rz, a in E.get('catch', [(-0.30, 0.36, 0.17, 0.13, 1.0), (0.34, -0.40, 0.07, 0.06, 0.55)]):
        d = np.hypot((dx / ri - hx) / rx, (dz / ri - hz) / rz)
        hl = np.maximum(hl, a * sm(1.0, 0.75, d))
    c = mix(c, np.array([1.0, 1.0, 1.0], dtype=np.float32), hl)
    arr = np.concatenate([np.clip(c, 0, 1), hl[..., None]], axis=2)
    arr = arr.reshape(size, ss, size, ss, 4).mean(axis=(1, 3))
    img = uvbake.to_image(name, arr)
    img.alpha_mode = 'CHANNEL_PACKED'       # alpha is a separate mask here: without this Cycles premultiplies and the eye turns black
    return img


def eye_material(name, iris, iris_in=None, sclera=(226, 220, 214), E=None, centre=(0.0, 0.0, 0.0), ref=None, ipd=0.062):
    """Painted eye. The texture is looked up by the direction from the eyeball centre (object space, `centre` = offset of the
    sphere centre from the object origin), so it turns with the eye.  `ref` (an object fixed to the head, at the midpoint
    between the eyes) adds what does not turn with the eye: the shadow of the upper lid and of the socket corners."""
    E = dict(E or {})
    E.setdefault('iris', list(iris))
    E.setdefault('iris_in', list(iris_in if iris_in is not None else np.clip(np.asarray(iris) * 1.5 + 25, 0, 255)))
    E.setdefault('sclera', list(sclera))
    img = eye_texture(name + '_tex', E, size=E.get('tex', 128))
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    N = nt.nodes.new

    def math_(op, a, bval=None, cval=None, clamp=False):
        n = N('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        for k, v in enumerate((a, bval, cval)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = v
            else:
                nt.links.new(v, n.inputs[k])
        return n.outputs[0]
    tc = N('ShaderNodeTexCoord')
    sub = N('ShaderNodeVectorMath')
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = tuple(centre)
    nt.links.new(tc.outputs['Object'], sub.inputs[0])
    nrm = N('ShaderNodeVectorMath')
    nrm.operation = 'NORMALIZE'
    nt.links.new(sub.outputs['Vector'], nrm.inputs[0])
    sep = N('ShaderNodeSeparateXYZ')
    nt.links.new(nrm.outputs['Vector'], sep.inputs[0])
    comb = N('ShaderNodeCombineXYZ')
    nt.links.new(math_('MULTIPLY_ADD', sep.outputs['X'], 0.5 / EYE_RANGE, 0.5), comb.inputs['X'])
    nt.links.new(math_('MULTIPLY_ADD', sep.outputs['Z'], 0.5 / EYE_RANGE, 0.5), comb.inputs['Y'])
    tx = N('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = 'Linear'
    tx.extension = 'EXTEND'
    nt.links.new(comb.outputs[0], tx.inputs['Vector'])
    col = tx.outputs['Color']
    if ref is not None:
        tr = N('ShaderNodeTexCoord')
        tr.object = ref
        sp = N('ShaderNodeSeparateXYZ')
        nt.links.new(tr.outputs['Object'], sp.inputs[0])
        lx = math_('SUBTRACT', math_('ABSOLUTE', sp.outputs['X']), ipd / 2)
        # shadow under the upper lid
        top = N('ShaderNodeMapRange')
        top.interpolation_type = 'SMOOTHSTEP'
        top.inputs['From Min'].default_value = E.get('lid_z0', 0.0002)
        top.inputs['From Max'].default_value = E.get('lid_z1', 0.0052)
        top.inputs['To Min'].default_value = 1.0
        top.inputs['To Max'].default_value = E.get('lid_dark', 0.38)
        nt.links.new(sp.outputs['Z'], top.inputs['Value'])
        # corners and lower rim of the socket
        ex = math_('POWER', math_('DIVIDE', math_('ABSOLUTE', lx), E.get('socket_x', 0.0125)), 2.0)
        ez = math_('POWER', math_('DIVIDE', math_('ABSOLUTE', sp.outputs['Z']), E.get('socket_z', 0.0065)), 2.0)
        vig = N('ShaderNodeMapRange')
        vig.interpolation_type = 'SMOOTHSTEP'
        vig.inputs['From Min'].default_value = 0.35
        vig.inputs['From Max'].default_value = 1.15
        vig.inputs['To Min'].default_value = 1.0
        vig.inputs['To Max'].default_value = E.get('socket_dark', 0.5)
        nt.links.new(math_('ADD', ex, ez), vig.inputs['Value'])
        shade = math_('MULTIPLY', top.outputs['Result'], vig.outputs['Result'])
        mul = N('ShaderNodeMix')
        mul.data_type = 'RGBA'
        mul.blend_type = 'MULTIPLY'
        mul.inputs[0].default_value = 1.0                 # ShaderNodeMix sockets by index: Factor 0, colour A 6, B 7, Result 2
        nt.links.new(col, mul.inputs[6])                  # (by name, 'A' / 'B' / 'Result' are the unused FLOAT sockets: black eyes)
        gray = N('ShaderNodeCombineColor')
        for k in range(3):
            nt.links.new(shade, gray.inputs[k])
        nt.links.new(gray.outputs[0], mul.inputs[7])
        col = mul.outputs[2]
    nt.links.new(col, b.inputs['Base Color'])
    nt.links.new(math_('MULTIPLY', tx.outputs['Alpha'], E.get('catch_emit', 0.9)), b.inputs['Emission Strength'])
    b.inputs['Emission Color'].default_value = (1, 1, 1, 1)
    b.inputs['Roughness'].default_value = E.get('rough', 0.32)
    b.inputs['Specular IOR Level'].default_value = E.get('spec', 0.3)
    return m
