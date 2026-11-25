"""Pixel-art cel look from Cycles render passes (multilayer EXR written by pxrender.setup_passes).

    python pxpost.py IN.exr OUT.png [--down 2] [--up 3] [--bands default] [--outline 0.28]

albedo (DiffCol) x light (DiffDir + DiffInd) quantised into a few flat bands, + emission; 1-pixel dark outlines where depth,
object or surface direction jump; computed at the low resolution, then enlarged with nearest-neighbour (crisp pixels)."""
import sys

import numpy as np
import OpenEXR
from PIL import Image

BANDS = {  # (light luminance threshold, value the band is set to)
    'default': [(0.0, 0.40), (0.30, 0.64), (0.62, 0.90), (1.05, 1.12)],
    'soft': [(0.0, 0.50), (0.32, 0.72), (0.66, 0.94), (1.10, 1.10)],
    # light normalised by `ref` (the light level that should read as fully lit): shadow / half-tone / lit / highlight
    'cel': [(0.0, 0.46), (0.42, 0.70), (0.72, 0.93), (1.08, 1.10)],
}


def read_exr(path):
    f = OpenEXR.File(path)
    out = {}
    for part in f.parts:
        for name, ch in part.channels.items():
            out[name] = np.asarray(ch.pixels, dtype=np.float32)
    return out


ALIASES = {'DiffCol': 'Diffuse Color', 'DiffDir': 'Diffuse Direct', 'DiffInd': 'Diffuse Indirect', 'Emit': 'Emission',
           'IndexOB': 'Object Index', 'Depth': 'Depth', 'Normal': 'Normal', 'Combined': 'Combined'}


def chan(P, layer, comps='RGB'):
    """A pass as an (H, W[, C]) array, whatever the channel naming (Blender 5 packs RGB passes in one channel)."""
    names = [layer] + ([ALIASES[layer]] if layer in ALIASES else [])
    for nm in names:
        for k, v in P.items():                                   # packed: 'ViewLayer.Diffuse Color' -> (H, W, 3)
            if (k.endswith('.' + nm) or k == nm) and v.ndim == 3:
                v = v[..., :len(comps)] if len(comps) > 1 else v[..., 0]
                return v.astype(np.float32)
        res = []
        for c in comps:                                           # split: 'ViewLayer.Depth.Z', '...Normal.X'
            k = next((k for k in P if k.endswith(f'{nm}.{c}')), None)
            if k is None:
                res = None
                break
            res.append(P[k])
        if res:
            a = np.stack(res, axis=-1).astype(np.float32)
            return a[..., 0] if len(comps) == 1 else a
    return None


def down(a, f, mode='mean'):
    if f == 1:
        return a
    h, w = a.shape[:2]
    a = a[:h - h % f, :w - w % f]
    s = a.reshape(h // f, f, w // f, f, *a.shape[2:])
    if mode == 'mean':
        return s.mean(axis=(1, 3))
    if mode == 'min':
        return s.min(axis=(1, 3))
    return s[:, f // 2, :, f // 2]            # 'pick': centre sample (ids)


def blur3(a):
    p = np.pad(a, [(1, 1), (1, 1)] + [(0, 0)] * (a.ndim - 2), mode='edge')
    k = np.array([0.25, 0.5, 0.25], dtype=np.float32)
    v = sum(p[i:i + a.shape[0]] * k[i] for i in range(3))
    return sum(v[:, i:i + a.shape[1]] * k[i] for i in range(3))


def process(P, down_f=2, bands='cel', outline=0.28, sat=1.08, gamma=1.0, ref=1.0):
    col = chan(P, 'DiffCol')
    ddir, dind = chan(P, 'DiffDir'), chan(P, 'DiffInd')
    emit = chan(P, 'Emit')
    z = chan(P, 'Depth', 'Z') if chan(P, 'Depth', 'Z') is not None else chan(P, 'Z', 'R')
    nrm = chan(P, 'Normal', 'XYZ')
    idx = chan(P, 'IndexOB', 'X')
    comb = chan(P, 'Combined', 'RGB')
    col, ddir, dind = (down(a, down_f) for a in (col, ddir, dind))
    emit = down(emit, down_f) if emit is not None else 0.0
    comb = down(comb, down_f) if comb is not None else None
    z = down(z, down_f, 'min')
    nrm = down(nrm, down_f, 'pick')
    idx = down(idx, down_f, 'pick') if idx is not None else np.zeros(z.shape, np.float32)
    light = blur3(ddir + dind)
    light = light / ref
    lum = light.max(axis=-1)
    level = np.zeros_like(lum)
    for th, v in BANDS[bands]:
        level = np.where(lum >= th, v, level)
    lq = light / np.maximum(lum, 1e-4)[..., None] * level[..., None]
    lq = np.where((lum > 1e-4)[..., None], lq, 0.0)
    img = col * lq + emit
    bgmask = (idx < 0.5) & (z > 1e8)
    if comb is not None:
        img = np.where(bgmask[..., None], comb, img)
    # outlines: depth jumps (relative), object id changes, creases
    H, W = z.shape
    edge = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        zs = np.roll(z, (dy, dx), axis=(0, 1))
        ids = np.roll(idx, (dy, dx), axis=(0, 1))
        ns = np.roll(nrm, (dy, dx), axis=(0, 1))
        nearer = z < zs                                   # draw the line on the nearer side of a jump
        jump = (np.abs(zs - z) / np.maximum(z, 1e-3) > 0.045) & nearer
        other = (ids != idx) & nearer & (idx > 0.5)
        crease = ((nrm * ns).sum(axis=-1) < 0.35) & (ids == idx) & (idx > 0.5) & nearer
        edge |= jump | other | crease
    edge &= ~bgmask
    img = np.where(edge[..., None], img * outline, img)
    g = img.mean(axis=-1, keepdims=True)
    img = g + (img - g) * sat
    img = np.clip(img, 0, None) ** gamma
    # linear -> sRGB
    srgb = np.where(img <= 0.0031308, img * 12.92, 1.055 * np.power(np.clip(img, 0.0031308, None), 1 / 2.4) - 0.055)
    return np.clip(srgb, 0, 1)


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    P = read_exr(a[0])
    out = process(P, down_f=opt('--down', 2), bands=opt('--bands', 'cel'), outline=opt('--outline', 0.28), ref=opt('--ref', 1.0))
    im = Image.fromarray((out * 255 + 0.5).astype(np.uint8))
    up = opt('--up', 3)
    im.resize((im.width * up, im.height * up), Image.NEAREST).save(a[1])
    if '--keys' in a:
        print(sorted(P))
