"""Image-space helpers for the version 6 faces (no bpy): colour classes, harmonic inpainting, glasses footprint."""
import json
import math

import numpy as np
from scipy import ndimage as ndi
from scipy import sparse
from scipy.sparse.linalg import spsolve


def hsv(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    return hue, (mx - mn) / np.maximum(mx, 1e-6), mx


def inpaint(values, hole, valid=None):
    """Harmonic (membrane) fill of `values` (H, W[, C]) inside `hole` from the pixels around it.  `valid`: pixels that
    may be used as sources (default: everything outside the hole); other pixels outside the hole are ignored (treated
    as part of the hole but not returned)."""
    v = values if values.ndim == 3 else values[..., None]
    H, W, C = v.shape
    unknown = hole.copy() if valid is None else (hole | ~valid)
    sl = ndi.find_objects(ndi.binary_dilation(hole, iterations=2).astype(int))[0]
    # work on the bounding box of the hole, grown until every unknown component touches a known pixel
    y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
    pad = 24
    y0, y1, x0, x1 = max(y0 - pad, 0), min(y1 + pad, H), max(x0 - pad, 0), min(x1 + pad, W)
    u = unknown[y0:y1, x0:x1]
    vv = v[y0:y1, x0:x1].astype(np.float64)
    h, w = u.shape
    idx = -np.ones((h, w), int)
    idx[u] = np.arange(u.sum())
    n = int(u.sum())
    rows, cols, dat = [], [], []
    rhs = np.zeros((n, C))
    diag = np.zeros(n)
    ys, xs = np.nonzero(u)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        yy, xx = ys + dy, xs + dx
        ok = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
        i = idx[ys[ok], xs[ok]]
        j = idx[yy[ok], xx[ok]]
        diag_add = np.zeros(n)
        np.add.at(diag_add, i, 1.0)
        diag += diag_add
        inner = j >= 0
        rows.append(i[inner]); cols.append(j[inner]); dat.append(-np.ones(inner.sum()))
        np.add.at(rhs, i[~inner], vv[yy[ok][~inner], xx[ok][~inner]])
    rows.append(np.arange(n)); cols.append(np.arange(n)); dat.append(np.maximum(diag, 1e-9))
    A = sparse.csr_matrix((np.concatenate(dat), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
    sol = np.column_stack([spsolve(A, rhs[:, c]) for c in range(C)])
    out = v.astype(np.float64).copy()
    box = out[y0:y1, x0:x1]
    hb = hole[y0:y1, x0:x1]
    full = vv.copy()
    full[u] = sol
    box[hb] = full[hb]
    return out if values.ndim == 3 else out[..., 0]


class Front:
    """The front view of a head: albedo, world positions, landmarks, pixel <-> world."""

    def __init__(self, name, here='.'):
        from PIL import Image
        self.name = name
        O = f'{here}/out_face6'
        self.meta = json.load(open(f'{O}/{name}_meta.json'))
        self.S = self.meta['size']
        self.rgb = np.asarray(Image.open(f'{O}/{name}_albedo.png').convert('RGB'), np.float32) / 255
        self.pos = np.load(f'{O}/{name}_pos.npy')
        self.mask = np.load(f'{O}/{name}_mask.npy')
        self.L = np.array(json.load(open(f'{here}/out_face2/{name}_landmarks.json'))['points'])
        self.ppm = self.S / self.meta['scale']                       # pixels per metre
        self.hue, self.sat, self.val = hsv(self.rgb)

    def px(self, p):
        p = np.asarray(p, float)
        m = self.meta
        return np.stack([(p[..., 0] - m['centre'][0]) * self.ppm + self.S / 2, self.S / 2 - (p[..., 2] - m['centre'][2]) * self.ppm], -1)

    def world_xz(self, xy):
        xy = np.asarray(xy, float)
        m = self.meta
        return np.stack([(xy[..., 0] - self.S / 2) / self.ppm + m['centre'][0], (self.S / 2 - xy[..., 1]) / self.ppm + m['centre'][2]], -1)

    def raised(self, mm=1.5, size_mm=9.0):
        """Pixels whose surface stands out in front of the skin around it (hair locks hanging over the face)."""
        if not hasattr(self, '_relief'):
            k = 4
            y = self.pos[::k, ::k, 1].astype(np.float32).copy()
            m = self.mask[::k, ::k]
            y[~m] = np.nan
            fill = np.where(m, y, np.nanmax(y))
            n = max(3, int(size_mm * 1e-3 * self.ppm / k) | 1)
            med = ndi.median_filter(fill, size=n)
            rel = (med - fill) * 1000.0
            self._relief = np.kron(rel, np.ones((k, k), np.float32))[:self.S, :self.S]
        return self.mask & (self._relief > mm)

    def skin_like(self):
        return self.mask & (self.sat > 0.16) & (self.val > 0.62) & ((self.hue < 0.12) | (self.hue > 0.95))

    def hair_like(self):
        return self.mask & (self.val < 0.50) & (self.hue > 0.50) & (self.hue < 0.75)


def glasses_footprint(F, relief_mm=0.5):
    """Pixels of the glasses block in the front view: the two rims with their lenses (grey, found by colour) and the
    bridge between them (skin-coloured on this model: found by its relief over a membrane from forehead to nose)."""
    L = F.L
    e0 = F.px(L[33])
    skin = F.skin_like()
    band = np.zeros_like(F.mask)
    band[int(e0[1] - 0.038 * F.ppm):int(e0[1] + 0.046 * F.ppm), :] = True
    grey = ndi.binary_opening(F.mask & band & ~skin & (F.val > 0.28), iterations=2)
    lab, n = ndi.label(grey)
    sizes = ndi.sum(grey, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1][:2]
    G0 = np.zeros_like(grey)
    cols = []
    r0 = int(e0[1])                                                   # the row of the eyes: inner edges of the two rims
    for k in order:
        c = ndi.binary_fill_holes(ndi.binary_closing(lab == k + 1, iterations=5))
        G0 |= c
        xs = np.nonzero(c[r0 - 10:r0 + 10].any(0))[0]
        cols.append((xs.min(), xs.max()))
    cols.sort()
    rows = np.nonzero(G0.any(1))[0]
    box = np.zeros_like(G0)
    box[rows.min():rows.max(), cols[0][1] - 8:cols[1][0] + 8] = True
    hair = ndi.binary_dilation(F.hair_like(), iterations=3)
    y = F.pos[..., 1].astype(np.float64)
    fit = inpaint(y, box, valid=F.mask & ~hair & ~ndi.binary_dilation(G0, iterations=4))
    bridge = box & ((fit - y) * 1000.0 > relief_mm) & ~hair
    G = ndi.binary_fill_holes(ndi.binary_closing(G0 | bridge, iterations=3))
    return G


BROW_UP = {'R': [70, 63, 105, 66, 107], 'L': [300, 293, 334, 296, 336]}          # outer -> inner
BROW_LOW = {'R': [46, 53, 52, 65, 55], 'L': [276, 283, 282, 295, 285]}


def brow_polys(F, thick=1.0):
    """The two eyebrows as pixel polygons (from the landmarks), a little fuller than the model's."""
    out = []
    for s in 'RL':
        up = F.px(F.L[BROW_UP[s]])
        lo = F.px(F.L[BROW_LOW[s]])
        mid = (up + lo) / 2
        half = (lo - up) / 2 * thick
        taper = np.array([0.35, 0.85, 1.0, 1.0, 0.8])[:, None]                # thin tail outside, full towards the nose
        out.append(np.vstack([mid - half * taper, (mid + half * taper)[::-1]]))
    return out


def brow_region(F, grow_mm=5.0):
    from PIL import Image, ImageDraw
    im = Image.new('L', (F.S, F.S), 0)
    d = ImageDraw.Draw(im)
    for P in brow_polys(F, 1.3):
        d.polygon([tuple(p) for p in P], fill=255)
    return ndi.binary_dilation(np.asarray(im) > 0, iterations=int(grow_mm * 1e-3 * F.ppm))


def repaint_front(F, G, eye_outlines, grow_mm=1.4, lash=(34, 24, 22), out=None):
    """The front picture with the glasses block painted out (skin colours diffused in from around it), and a little
    drawing around the new eye openings: upper lash line, a soft crease above it, a light lower lash line.
    eye_outlines: list of (N, 2) world x-z polygons (counter-clockwise, starting at the corner with the smallest x)."""
    from PIL import Image, ImageDraw, ImageFilter
    hole = ndi.binary_dilation(G, iterations=int(grow_mm * 1e-3 * F.ppm))
    # the old eyebrows (cut by the frame, crossed by hair) are painted out too and redrawn whole
    hairp = ndi.binary_dilation(F.raised() & ~F.skin_like(), iterations=3)
    breg = brow_region(F, 5.0) & ~hairp
    dark_warm = F.mask & (F.val < 0.62) & ~F.skin_like() & ((F.hue < 0.2) | (F.hue > 0.9))
    brow_col = np.median(F.rgb[breg & dark_warm & (F.val < 0.4)], 0) if (breg & dark_warm & (F.val < 0.4)).sum() > 50 else np.array([0.22, 0.16, 0.13])
    hole = hole | ndi.binary_dilation(breg & dark_warm, iterations=3)
    src = F.skin_like() & ~ndi.binary_dilation(hole, iterations=3)
    k = 4                                                            # solve at quarter resolution: the fill is smooth anyway
    small = F.rgb[::k, ::k]
    hs = ndi.binary_dilation(hole[::k, ::k], iterations=1)
    filled = inpaint(small, hs, valid=src[::k, ::k] & ~hs)
    up = np.stack([ndi.zoom(filled[..., c], k, order=1)[:F.S, :F.S] for c in range(3)], -1)
    soft = ndi.gaussian_filter(hole.astype(np.float32), 2.0)[..., None]
    img = F.rgb * (1 - soft) + up * soft
    base = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
    ss = 2
    big = base.resize((F.S * ss, F.S * ss), Image.LANCZOS)
    crease = Image.new('L', big.size, 0)
    lashu = Image.new('L', big.size, 0)
    lashl = Image.new('L', big.size, 0)
    dc, du, dl = ImageDraw.Draw(crease), ImageDraw.Draw(lashu), ImageDraw.Draw(lashl)
    mm = F.ppm * 1e-3 * ss
    for O in eye_outlines:
        i1 = int(np.argmax(O[:, 0]))
        a, b = O[:i1 + 1], np.vstack([O[i1:], O[:1]])
        upper, lower = (a, b) if a[:, 1].mean() > b[:, 1].mean() else (b, a)
        pu = [tuple(F.px(np.array([p[0], 0, p[1] + 0.0005])) * ss) for p in upper]
        pl = [tuple(F.px(np.array([p[0], 0, p[1] - 0.0004])) * ss) for p in lower]
        w = float(np.ptp(O[:, 0]))
        pc = [tuple(F.px(np.array([p[0], 0, p[1] + 0.0030 + 0.0022 * math.sin(math.pi * (p[0] - O[:, 0].min()) / w)])) * ss) for p in upper]
        du.line(pu, fill=255, width=max(2, int(1.25 * mm)), joint='curve')
        dl.line(pl, fill=255, width=max(1, int(0.5 * mm)), joint='curve')
        dc.line(pc[2:-2], fill=255, width=max(2, int(0.9 * mm)), joint='curve')
    lashu = lashu.filter(ImageFilter.GaussianBlur(0.22 * mm))
    lashl = lashl.filter(ImageFilter.GaussianBlur(0.35 * mm))
    crease = crease.filter(ImageFilter.GaussianBlur(0.9 * mm))
    arr = np.asarray(big, np.float32) / 255
    lu = np.asarray(lashu, np.float32)[..., None] / 255
    ll = np.asarray(lashl, np.float32)[..., None] / 255 * 0.40
    cr = np.asarray(crease, np.float32)[..., None] / 255 * 0.22
    lash_c = np.array(lash, np.float32) / 255
    arr = arr * (1 - cr) + arr * np.array([0.62, 0.50, 0.46], np.float32) * cr
    arr = arr * (1 - ll) + lash_c * 1.6 * ll
    arr = arr * (1 - lu) + lash_c * lu
    # eyebrows: a soft-edged shape with a few darker and lighter hair strokes along it
    rng = np.random.default_rng(7)
    bl = Image.new('L', big.size, 0)
    st = Image.new('L', big.size, 0)
    db, ds = ImageDraw.Draw(bl), ImageDraw.Draw(st)
    for P in brow_polys(F, 1.0):
        P2 = P * ss
        db.polygon([tuple(p) for p in P2], fill=255)
        n = len(P2) // 2
        upc, loc = P2[:n], P2[n:][::-1]
        for _ in range(140):
            u = rng.uniform(0.02, 0.95)
            i = min(int(u * (n - 1)), n - 2)
            f = u * (n - 1) - i
            a = upc[i] * (1 - f) + upc[i + 1] * f
            b = loc[i] * (1 - f) + loc[i + 1] * f
            v = rng.uniform(0.1, 0.9)
            p0 = a * (1 - v) + b * v
            dirv = (upc[min(i + 1, n - 1)] - upc[i])
            dirv = dirv / max(np.linalg.norm(dirv), 1e-6)
            L_ = rng.uniform(1.2, 2.6) * mm
            p1 = p0 - dirv * L_ + np.array([0, -rng.uniform(0.2, 0.7) * mm])
            ds.line([tuple(p0), tuple(p1)], fill=int(rng.uniform(90, 255)), width=max(1, int(0.22 * mm)))
    bl = bl.filter(ImageFilter.GaussianBlur(0.45 * mm))
    st = st.filter(ImageFilter.GaussianBlur(0.12 * mm))
    ba = np.asarray(bl, np.float32)[..., None] / 255
    sa = np.asarray(st, np.float32)[..., None] / 255 * ba
    bc = np.asarray(brow_col, np.float32)
    bc = bc * 0.62
    arr = arr * (1 - 0.92 * ba) + bc * 0.92 * ba
    arr = arr * (1 - 0.45 * sa) + bc * 0.5 * 0.45 * sa
    hp = np.kron(hairp, np.ones((ss, ss), bool))[..., None]                    # hair locks over the brows stay as they are
    arr = np.where(hp, np.asarray(big, np.float32) / 255, arr)
    res = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)).resize((F.S, F.S), Image.LANCZOS)
    if out:
        res.save(out)
    return np.asarray(res, np.float32) / 255


def tint_lips(rgb, F, xs, line_z, out_u, out_l, mul=(0.84, 0.66, 0.68), soft_mm=0.7):
    """Give the lips their own colour in the front picture (they were almost the colour of the skin): a soft-edged
    multiply over the red part of the lips, given as the mouth line and the two outer contours z(x)."""
    from PIL import Image, ImageDraw, ImageFilter
    S = F.S
    pu = [tuple(F.px(np.array([x, 0.0, z]))) for x, z in zip(xs, out_u)]
    pl = [tuple(F.px(np.array([x, 0.0, z]))) for x, z in zip(xs, out_l)]
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).polygon(pu + pl[::-1], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(soft_mm * 1e-3 * F.ppm))
    a = (np.asarray(m, np.float32) / 255)[..., None]
    return rgb * (1 - a) + rgb * np.asarray(mul, np.float32) * a
