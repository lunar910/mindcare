"""Body / outfit pass: clothes, shoes, accessories and the mask hiding the covered skin. Entry point: build(ch)."""
import numpy as np

import cfg_body as CB
import look
import mhassets as A
import room_bl


def box_blur(a, r):
    c = np.cumsum(np.cumsum(np.pad(a, ((r + 1, r), (r + 1, r)), mode='edge'), axis=0), axis=1)
    n = 2 * r + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / (n * n)


def recolor_suit(rgb, alpha):
    """male_casualsuit05 texture: field jacket -> dark red, striped shirt -> black, blue jeans -> washed black."""
    h, s, v = A.rgb_to_hsv(rgb)
    lum = rgb.mean(axis=-1)
    blue = (h > 0.5) & (h < 0.72) & (s > 0.16) & (v > 0.05)
    jeans = (box_blur(blue.astype(np.float32), 24) > 0.2) & (v > 0.035)
    red = ((h < 0.07) | (h > 0.9)) & (s > 0.35) & (v > 0.12)
    shirt_zone = (box_blur(red.astype(np.float32), 14) > 0.05) & (~jeans)
    jacket = (~jeans) & (~shirt_zone) & (v > 0.035)
    shirt = shirt_zone & (v > 0.02)
    out = rgb.copy()
    jl = lum / max(float(lum[jacket].mean()), 1e-3)
    out[jacket] = np.array(CB.SUIT['jacket'], dtype=np.float32) / 255 * (jl[jacket, None] ** 1.15)
    dl = lum / max(float(lum[jeans].mean()), 1e-3)
    out[jeans] = np.array(CB.SUIT['jeans'], dtype=np.float32) / 255 * (dl[jeans, None] ** 1.1)
    out[shirt] = np.array(CB.SUIT['shirt'], dtype=np.float32) / 255 * (0.55 + 1.5 * lum[shirt, None])
    return np.clip(out, 0, 1)


def build(ch):
    A.add_proxy(ch, 'clothes', CB.SUIT['asset'], recolor=recolor_suit, down=CB.TEXDOWN, rough=0.7, spec=0.16, use_normal=True)
    A.add_proxy(ch, 'clothes', CB.SUIT['shoes'], down=CB.TEXDOWN, rough=0.75, spec=0.12)
    A.apply_body_mask(ch)
    if CB.CHAIN:
        look.chain(ch, room_bl.mat_basic('chain', [215, 218, 224], rough=0.2, metal=1.0), drop=0.07, r=0.0016)
