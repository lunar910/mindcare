"""UV-space texture painting helpers for the MakeHuman body mesh.

The UV layout is the same for every morph, so the texel -> (triangle, barycentric) map is
computed once and cached. Any per-vertex attribute can then be looked up per texel."""
import os

import bpy
import numpy as np

import mh

CACHE = os.path.join(mh.SP, 'cache')


def body_tris():
    """Triangles of the body mesh: vertex ids (body-local) and UVs per corner."""
    B = mh.base()
    faces = [f for f in B.faces if f[2] == 'body']
    used = sorted({i for f in faces for i in f[0]})
    remap = -np.ones(len(B.v), dtype=np.int64)
    remap[np.array(used)] = np.arange(len(used))
    tv, tuv = [], []
    for vi, ti, _ in faces:
        for a, b, c in ((0, 1, 2), (0, 2, 3)) if len(vi) == 4 else ((0, 1, 2),):
            tv.append((remap[vi[a]], remap[vi[b]], remap[vi[c]]))
            tuv.append((B.vt[ti[a]], B.vt[ti[b]], B.vt[ti[c]]))
    return np.array(tv, dtype=np.int64), np.array(tuv, dtype=np.float64), np.array(used)


def raster(S=2048):
    """Returns dict(tri=[S,S] int32 (-1 = empty), bary=[S,S,3] float32, tv=[T,3]). Row 0 is v=0."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f'raster_{S}.npz')
    tv, tuv, used = body_tris()
    if os.path.exists(path):
        z = np.load(path)
        return dict(tri=z['tri'], bary=z['bary'], tv=tv, S=S)
    tri = -np.ones((S, S), dtype=np.int32)
    bary = np.zeros((S, S, 3), dtype=np.float32)
    P = tuv * S  # pixel units
    for t in range(len(tv)):
        (x0, y0), (x1, y1), (x2, y2) = P[t]
        minx, maxx = int(np.floor(min(x0, x1, x2) - 0.5)), int(np.ceil(max(x0, x1, x2) + 0.5))
        miny, maxy = int(np.floor(min(y0, y1, y2) - 0.5)), int(np.ceil(max(y0, y1, y2) + 0.5))
        minx, miny, maxx, maxy = max(minx, 0), max(miny, 0), min(maxx, S - 1), min(maxy, S - 1)
        if maxx < minx or maxy < miny:
            continue
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        xs = np.arange(minx, maxx + 1) + 0.5
        ys = np.arange(miny, maxy + 1) + 0.5
        X, Y = np.meshgrid(xs, ys)
        l0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
        l1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
        l2 = 1 - l0 - l1
        eps = -0.02
        m = (l0 >= eps) & (l1 >= eps) & (l2 >= eps)
        if not m.any():
            continue
        sub_t = tri[miny:maxy + 1, minx:maxx + 1]
        sub_b = bary[miny:maxy + 1, minx:maxx + 1]
        # keep the best-covered triangle when several touch a texel
        inside = np.minimum(np.minimum(l0, l1), l2)
        prev = np.where(sub_t >= 0, sub_b.min(axis=2), -1.0)
        w = m & (inside > prev)
        sub_t[w] = t
        sub_b[w, 0], sub_b[w, 1], sub_b[w, 2] = l0[w], l1[w], l2[w]
    np.savez_compressed(path, tri=tri, bary=bary)
    return dict(tri=tri, bary=bary, tv=tv, S=S)


def texel(R, attr):
    """Interpolate a per-vertex attribute (N,) or (N,k) to texels -> (S,S) or (S,S,k) float32 (0 where empty)."""
    attr = np.asarray(attr, dtype=np.float32)
    valid = R['tri'] >= 0
    t = R['tri'][valid]
    vids = R['tv'][t]                     # (M,3)
    b = R['bary'][valid]                  # (M,3)
    if attr.ndim == 1:
        out = np.zeros(R['tri'].shape, dtype=np.float32)
        out[valid] = (attr[vids] * b).sum(axis=1)
    else:
        out = np.zeros(R['tri'].shape + (attr.shape[1],), dtype=np.float32)
        out[valid] = (attr[vids] * b[:, :, None]).sum(axis=1)
    return out


def dilate(img, valid, n=12):
    """Bleed painted texels into empty ones (avoids dark seams)."""
    img = img.copy()
    valid = valid.copy()
    for _ in range(n):
        acc = np.zeros_like(img)
        cnt = np.zeros(valid.shape, dtype=np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            sv = np.roll(np.roll(valid, dy, 0), dx, 1)
            si = np.roll(np.roll(img, dy, 0), dx, 1)
            acc += si * sv[..., None]
            cnt += sv
        new = (~valid) & (cnt > 0)
        img[new] = acc[new] / cnt[new][:, None]
        valid = valid | new
    return img


def to_image(name, arr, srgb=True):
    """arr: (S,S,3|4) float in display space (sRGB if srgb), row 0 = v 0."""
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), dtype=arr.dtype)], axis=2)
    img = bpy.data.images.new(name, w, h, alpha=True)
    if not srgb:
        img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.pack()
    return img


def fbm(shape, seed=0, octaves=5, base=4, stretch=(1.0, 1.0)):
    """Smooth tileable-ish value noise in [0,1] at texture resolution."""
    rng = np.random.default_rng(seed)
    H, W = shape
    out = np.zeros(shape, dtype=np.float32)
    amp, tot = 1.0, 0.0
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    for o in range(octaves):
        gy = max(2, int(base * (2 ** o) * stretch[0]))
        gx = max(2, int(base * (2 ** o) * stretch[1]))
        g = rng.random((gy + 1, gx + 1)).astype(np.float32)
        fy, fx = yy * gy / H, xx * gx / W
        iy, ix = np.minimum(fy.astype(int), gy - 1), np.minimum(fx.astype(int), gx - 1)
        ty, tx = fy - iy, fx - ix
        ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
        v = (g[iy, ix] * (1 - tx) + g[iy, ix + 1] * tx) * (1 - ty) + (g[iy + 1, ix] * (1 - tx) + g[iy + 1, ix + 1] * tx) * ty
        out += v * amp
        tot += amp
        amp *= 0.5
    return out / tot
