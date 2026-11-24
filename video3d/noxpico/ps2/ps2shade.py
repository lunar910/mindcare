"""PS2-cutscene look, numpy side.   import ps2shade as SH

    G = SH.load(exr[, ao_exr])                    data passes of one layer (see ps2render.py)
    rgb = SH.shade(G, lights, cam)                ambient + a few lights, PS2 style (no ray-traced shadows), linear RGB
    out = SH.merge(S_rgb, S, D_rgb, D)            depth-merge the moving layer over the set
    img = SH.finish(rgb, ss, ...)                 down-sample, glow, PS2 softness and dither, sRGB, enlarge -> PIL image

Lights (dicts):
    dict(type='hemi', sky=(r,g,b), ground=(r,g,b))                         ambient that depends on the surface direction
    dict(type='dir', dir=(x,y,z), color=(r,g,b), wrap=0.3)                 dir = direction towards the light
    dict(type='point', pos=(x,y,z), color=(r,g,b), radius=1.5, wrap=0.2)   falls off as 1 / (1 + (d/radius)^2)
    dict(type='rim', color=(r,g,b), power=2.5, dir=(x,y,z))                edge light on what faces away from the camera
"""
import numpy as np
import OpenEXR
from PIL import Image

ALIASES = {'DiffCol': 'Diffuse Color', 'Emit': 'Emission', 'IndexOB': 'Object Index', 'Depth': 'Depth', 'Normal': 'Normal',
           'Combined': 'Combined', 'Position': 'Position', 'AO': 'Ambient Occlusion'}


def read_exr(path):
    f = OpenEXR.File(path)
    out = {}
    for part in f.parts:
        for name, ch in part.channels.items():
            out[name] = np.asarray(ch.pixels, dtype=np.float32)
    return out


def chan(P, layer, n=3):
    names = [layer, ALIASES.get(layer, layer)]
    for nm in names:
        for k, v in P.items():
            if (k.endswith('.' + nm) or k == nm) and v.ndim == 3:
                return v[..., :n] if n > 1 else v[..., 0]
        for comps in ('RGBA', 'XYZW', 'ZZZZ', 'VVVV'):
            ks = [next((k for k in P if k.endswith(f'{nm}.{c}')), None) for c in comps[:max(n, 1)]]
            if all(ks):
                a = np.stack([P[k] for k in ks], axis=-1)
                return a if n > 1 else a[..., 0]
    return None


def load(path, ao_path=None):
    P = read_exr(path)
    G = dict(albedo=chan(P, 'DiffCol'), emit=chan(P, 'Emit'), normal=chan(P, 'Normal'), pos=chan(P, 'Position'),
             z=chan(P, 'Depth', 1), idx=chan(P, 'IndexOB', 1))
    comb = chan(P, 'Combined', 4)
    G['mask'] = (comb[..., 3] > 0.5) if comb is not None and comb.shape[-1] == 4 else (G['idx'] > 0)
    n = G['normal']
    ln = np.linalg.norm(n, axis=-1, keepdims=True)
    G['normal'] = n / np.maximum(ln, 1e-6)
    G['z'] = np.where(G['mask'], G['z'], 1e9).astype(np.float32)
    if ao_path:
        A = read_exr(ao_path)
        ao = chan(A, 'AO')
        G['ao'] = ao.mean(-1) if ao is not None else None
    return G


def _v(x):
    return np.asarray(x, dtype=np.float32)


def shade(G, lights, cam=None, ao_strength=1.0, ao_floor=0.0):
    N, P, alb = G['normal'], G['pos'], G['albedo']
    E = np.zeros_like(alb)
    for L in lights:
        t = L['type']
        col = _v(L.get('color', (1, 1, 1)))
        if t == 'hemi':
            k = (0.5 + 0.5 * N[..., 2])[..., None]
            E += _v(L['ground']) * (1 - k) + _v(L['sky']) * k
        elif t == 'dir':
            d = _v(L['dir'])
            d = d / np.linalg.norm(d)
            w = L.get('wrap', 0.0)
            nl = np.clip(((N @ d) + w) / (1 + w), 0, 1)
            E += nl[..., None] * col
        elif t == 'point':
            v = _v(L['pos']) - P
            dist = np.linalg.norm(v, axis=-1)
            w = L.get('wrap', 0.0)
            nl = np.clip(((N * v).sum(-1) / np.maximum(dist, 1e-4) + w) / (1 + w), 0, 1)
            att = 1.0 / (1.0 + (dist / L.get('radius', 1.5)) ** 2)
            if 'cone' in L:                                        # spot: (axis, cos_inner, cos_outer)
                ax, ci, co = L['cone']
                ax = _v(ax) / np.linalg.norm(ax)
                cs = -(v @ ax) / np.maximum(dist, 1e-4)
                att = att * np.clip((cs - co) / max(ci - co, 1e-4), 0, 1)
            if 'ymin' in L:                                        # light that stays in the next room (no shadow rays here)
                att = att * (P[..., 1] > L['ymin'])
            if 'ymax' in L:
                att = att * (P[..., 1] < L['ymax'])
            if 'factor' in L:                                      # e.g. the cast shadow of this light
                att = att * L['factor']
            E += (nl * att)[..., None] * col
        elif t == 'rim' and cam is not None:
            V = _v(cam['pos']) - P
            V /= np.maximum(np.linalg.norm(V, axis=-1, keepdims=True), 1e-4)
            f = np.clip(1.0 - (N * V).sum(-1), 0, 1) ** L.get('power', 2.5)
            if 'dir' in L:
                d = _v(L['dir'])
                d = d / np.linalg.norm(d)
                f = f * np.clip((N @ d) * 0.5 + 0.5, 0, 1)
            E += f[..., None] * col
    if G.get('ao') is not None and ao_strength > 0:
        ao = np.clip(G['ao'], 0, 1)
        ao = ao_floor + (1 - ao_floor) * ao
        E *= (1 - ao_strength + ao_strength * ao)[..., None]
    return alb * E + G['emit']


def blob_shadows(G, blobs):
    """Soft dark discs under the characters, the classic PS2 drop shadow.  blobs: [(x, y, z, radius, strength), ...]
    Returns the factor to multiply the lit colour with (only upward-facing surfaces just below the blob are darkened)."""
    P, N = G['pos'], G['normal']
    f = np.ones(P.shape[:2], dtype=np.float32)
    up = np.clip((N[..., 2] - 0.6) / 0.3, 0, 1)
    for x, y, z, r, s in blobs:
        d2 = (P[..., 0] - x) ** 2 + (P[..., 1] - y) ** 2
        below = np.clip((z + 0.06 - P[..., 2]) / 0.05, 0, 1) * np.clip((P[..., 2] - (z - 0.35)) / 0.1, 0, 1)
        f *= 1.0 - s * np.exp(-d2 / (r * r)) * up * below
    return f


def merge(S_rgb, S, D_rgb, D, bias=0.006):
    """The moving layer in front of the set wherever it is nearer (with a small bias so that hands lying on a table win)."""
    m = D['mask'] & (D['z'] < S['z'] + bias)
    out = np.where(m[..., None], D_rgb, S_rgb)
    return out, m


def _box(a, f):
    if f == 1:
        return a
    h, w = a.shape[:2]
    return a.reshape(h // f, f, w // f, f, *a.shape[2:]).mean(axis=(1, 3))


def _blur(a, sigma):
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(a, sigma=(sigma, sigma, 0)) if a.ndim == 3 else gaussian_filter(a, sigma)


def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) + 0.5) / 16.0 - 0.5


def finish(rgb, ss=2, exposure=1.0, glow=0.30, glow_thresh=1.05, glow_sigma=5.0, soft=0.45, dither_bits=6, contrast=1.0,
           saturation=1.0, out_size=(1080, 1920), fog=None, vignette=0.0):
    """rgb: linear (H*ss, W*ss, 3).  Returns a PIL image at out_size."""
    a = _box(rgb.astype(np.float32), ss) * exposure
    if glow > 0:                                                   # glow of the bright parts (lamps, screens, highlights)
        lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        hi = a * np.clip((lum - glow_thresh) / 0.5, 0, 3)[..., None]
        a = a + glow * (0.6 * _blur(hi, glow_sigma) + 0.4 * _blur(hi, glow_sigma * 3))
    a = a / (1.0 + 0.18 * np.maximum(a - 0.8, 0))                 # gentle shoulder: bright areas do not clip hard
    s = srgb(a)
    if contrast != 1.0:
        s = np.clip((s - 0.5) * contrast + 0.5, 0, 1)
    if saturation != 1.0:
        g = s @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        s = np.clip(g[..., None] + (s - g[..., None]) * saturation, 0, 1)
    if vignette > 0:
        h, w = s.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r2 = ((xx - w / 2) / (w / 2)) ** 2 * 0.6 + ((yy - h / 2) / (h / 2)) ** 2 * 0.6
        s = s * (1 - vignette * np.clip(r2 - 0.25, 0, 1))[..., None]
    if soft > 0:                                                   # the slightly soft picture of the console's video output
        s = (1 - soft) * s + soft * _blur(s, 0.7)
    if dither_bits:                                                # 16-bit style frame buffer: ordered dither
        h, w = s.shape[:2]
        levels = (1 << dither_bits) - 1
        d = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w][..., None]
        s = np.clip(np.floor(s * levels + 0.5 + d * 0.9) / levels, 0, 1)
    im = Image.fromarray((s * 255 + 0.5).astype(np.uint8))
    if out_size and im.size != tuple(out_size):
        k = max(2, int(np.ceil(4 * out_size[0] / im.size[0] / 2)))          # nearest up, then area down: firm but not harsh pixels
        im = im.resize((im.size[0] * k, im.size[1] * k), Image.NEAREST).resize(tuple(out_size), Image.BOX if (im.size[0] * k) % out_size[0] == 0 else Image.BILINEAR)
    return im

# ------------------------------------------------------------------ cast shadows of the key light (shadow map)
def shadow_map(path, info):
    """Distance from the light to the first surface, for every direction seen by the light's camera."""
    P = read_exr(path)
    pos = chan(P, 'Position')
    comb = chan(P, 'Combined', 4)
    d = np.linalg.norm(pos - _v(info['pos']), axis=-1)
    return np.where(comb[..., 3] > 0.5, d, 1e9).astype(np.float32)


def shadow(G, dist_map, info, bias=0.03, soft=1.2, taps=2.0):
    """0..1 for every pixel of G: 1 = the key light reaches it.

    The depth test is averaged over a 3x3 neighbourhood of the map (taps = spacing in map pixels) and the result is
    blurred a little, which gives a soft, clean edge instead of the staircase of the map's pixels."""
    P = G['pos']
    v = P - _v(info['pos'])
    z = v @ _v(info['fwd'])
    x = (v @ _v(info['right'])) / np.maximum(z, 1e-4) / info['tan']
    y = (v @ _v(info['up'])) / np.maximum(z, 1e-4) / info['tan']
    n = info['size']
    fx = (x * 0.5 + 0.5) * n
    fy = (0.5 - y * 0.5) * n
    inside = (z > 0.05) & (np.abs(x) < 1) & (np.abs(y) < 1)
    d = np.linalg.norm(v, axis=-1) - bias
    f = np.zeros(P.shape[:2], dtype=np.float32)
    for oy in (-taps, 0.0, taps):
        for ox in (-taps, 0.0, taps):
            px = np.clip((fx + ox).astype(np.int32), 0, n - 1)
            py = np.clip((fy + oy).astype(np.int32), 0, n - 1)
            f += (d <= dist_map[py, px])
    f = np.where(inside, f / 9.0, 1.0).astype(np.float32)
    if soft > 0:
        from scipy.ndimage import gaussian_filter
        f = gaussian_filter(f, soft)
    return f
