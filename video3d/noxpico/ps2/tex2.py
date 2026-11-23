"""Flat textures of Nox's workshop, drawn front-on and at real scale (PIL).   import tex2

Every function returns an RGBA PIL image together with its real size in metres, so that what is drawn on it keeps the
right proportions next to the characters (a 20 cm spanner is drawn 20 cm long)."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = (26, 18, 22, 255)            # outline colour


def _shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3]) + (255,)


# ------------------------------------------------------------------ pegboard (0.84 x 0.62 m, 5 px per cm)
def pegboard(ppcm=5):
    Wm, Hm = 0.84, 0.62
    W, H = int(Wm * 100 * ppcm), int(Hm * 100 * ppcm)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fr = int(2.6 * ppcm)                                                   # wooden frame
    d.rectangle([0, 0, W - 1, H - 1], fill=(104, 66, 40, 255), outline=OUT)
    d.rectangle([2, 2, W - 3, int(fr * 0.45)], fill=(128, 84, 52, 255))
    d.rectangle([fr, fr, W - 1 - fr, H - 1 - fr], fill=(196, 170, 124, 255), outline=(70, 44, 28, 255))
    for y in range(fr + int(1.6 * ppcm), H - fr - 2, int(2.5 * ppcm)):       # the holes, every 2.5 cm
        for x in range(fr + int(1.6 * ppcm), W - fr - 2, int(2.5 * ppcm)):
            d.rectangle([x, y, x + 1, y + 1], fill=(120, 98, 68, 255))
    d.rectangle([fr + 1, fr + 1, W - 2 - fr, fr + 3], fill=(150, 126, 90, 255))  # shadow under the frame

    def cm(v):
        return int(round(v * ppcm))

    def spanner(cx, top, length, col=(170, 176, 188, 255)):
        x, y, L = cm(cx), cm(top), cm(length)
        w = max(3, cm(1.3))
        d.rectangle([x - w // 2 + 3, y + 3, x + w // 2 + 3, y + L + 3], fill=(150, 126, 90, 255))       # drop shadow
        d.rectangle([x - w // 2, y + cm(2.0), x + w // 2, y + L - cm(2.0)], fill=col, outline=OUT)
        for yy, r in ((y + cm(1.5), cm(1.9)), (y + L - cm(1.3), cm(1.5))):
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=col, outline=OUT)
        d.rectangle([x - cm(0.55), y - 1, x + cm(0.55), y + cm(1.5)], fill=(196, 170, 124, 255))        # open jaw (top)
        d.ellipse([x - cm(0.6), y + L - cm(1.9), x + cm(0.6), y + L - cm(0.7)], fill=(196, 170, 124, 255), outline=OUT)  # ring (bottom)
        d.line([x - 1, y + cm(3), x - 1, y + L - cm(3)], fill=_shade(col, 1.18), width=1)
        d.ellipse([x - 2, y - cm(1.4) - 2, x + 2, y - cm(1.4) + 2], fill=(60, 60, 66, 255))              # hook

    def screwdriver(cx, top, length, handle):
        x, y, L = cm(cx), cm(top), cm(length)
        hl = int(L * 0.42)
        hw = cm(2.4)
        d.rectangle([x - hw // 2 + 3, y + 3, x + hw // 2 + 3, y + hl + 3], fill=(150, 126, 90, 255))
        d.rounded_rectangle([x - hw // 2, y, x + hw // 2, y + hl], radius=cm(0.8), fill=handle, outline=OUT)
        d.line([x - hw // 4, y + 3, x - hw // 4, y + hl - 3], fill=_shade(handle, 1.25), width=2)
        d.rectangle([x - 2, y + hl, x + 1, y + L], fill=(176, 182, 194, 255), outline=OUT)
        d.rectangle([x - 3, y + L - cm(0.8), x + 2, y + L], fill=(120, 126, 138, 255), outline=OUT)
        d.ellipse([x - 2, y - cm(0.9) - 2, x + 2, y - cm(0.9) + 2], fill=(60, 60, 66, 255))

    def hammer(cx, top, length):
        x, y, L = cm(cx), cm(top), cm(length)
        hw = cm(2.2)
        d.rectangle([x - hw // 2 + 3, y + cm(3) + 3, x + hw // 2 + 3, y + L + 3], fill=(150, 126, 90, 255))
        d.rectangle([x - hw // 2, y + cm(3.2), x + hw // 2, y + L], fill=(158, 104, 58, 255), outline=OUT)
        d.line([x - hw // 4, y + cm(4), x - hw // 4, y + L - 3], fill=(186, 128, 76, 255), width=2)
        d.rectangle([x - cm(5.2), y, x + cm(4.2), y + cm(3.4)], fill=(96, 100, 112, 255), outline=OUT)   # head
        d.rectangle([x - cm(5.2), y, x - cm(3.6), y + cm(3.4)], fill=(132, 136, 148, 255), outline=OUT)  # striking face
        d.polygon([(x + cm(4.2), y), (x + cm(6.6), y + cm(1.0)), (x + cm(4.2), y + cm(1.6))], fill=(96, 100, 112, 255), outline=OUT)  # claw

    def pliers(cx, top, length, col=(196, 52, 48, 255)):
        x, y, L = cm(cx), cm(top), cm(length)
        jl = int(L * 0.36)
        d.polygon([(x - cm(1.1), y + 3), (x + cm(1.1), y + 3), (x + cm(0.7), y + jl), (x - cm(0.7), y + jl)], fill=(150, 126, 90, 255))
        d.polygon([(x - cm(0.9), y), (x - 1, y), (x - 1, y + jl), (x - cm(0.8), y + jl)], fill=(170, 176, 188, 255), outline=OUT)
        d.polygon([(x + cm(0.9), y), (x + 1, y), (x + 1, y + jl), (x + cm(0.8), y + jl)], fill=(170, 176, 188, 255), outline=OUT)
        d.ellipse([x - cm(0.9), y + jl - cm(0.9), x + cm(0.9), y + jl + cm(0.9)], fill=(120, 126, 138, 255), outline=OUT)
        for s in (-1, 1):
            d.line([x + s * cm(0.5), y + jl + cm(0.6), x + s * cm(1.9), y + L], fill=OUT, width=cm(1.3) + 2)
            d.line([x + s * cm(0.5), y + jl + cm(0.6), x + s * cm(1.9), y + L], fill=col, width=cm(1.3))

    def saw(cx, top, length):
        x, y, L = cm(cx), cm(top), cm(length)
        d.polygon([(x, y + 3), (x + L + 3, y + cm(2) + 3), (x + L + 3, y + cm(6) + 3), (x, y + cm(9) + 3)], fill=(150, 126, 90, 255))
        d.polygon([(x + cm(8), y + cm(0.5)), (x + L, y + cm(2.6)), (x + L, y + cm(5.2)), (x + cm(8), y + cm(8.5))], fill=(188, 194, 204, 255), outline=OUT)
        for k in range(cm(8) + 3, L - 2, 5):
            d.line([x + k, y + cm(8.5) - (k - cm(8)) * (cm(3.3)) // max(1, L - cm(8)), x + k + 2, y + cm(8.5) - (k - cm(8)) * (cm(3.3)) // max(1, L - cm(8)) + 3], fill=OUT)
        d.rounded_rectangle([x, y, x + cm(9), y + cm(9)], radius=cm(1.5), fill=(158, 104, 58, 255), outline=OUT)
        d.rounded_rectangle([x + cm(2.4), y + cm(2.4), x + cm(6.2), y + cm(6.6)], radius=cm(1.2), fill=(196, 170, 124, 255), outline=OUT)

    def tape(cx, cy, r):
        x, y, R = cm(cx), cm(cy), cm(r)
        d.ellipse([x - R + 3, y - R + 3, x + R + 3, y + R + 3], fill=(150, 126, 90, 255))
        d.ellipse([x - R, y - R, x + R, y + R], fill=(54, 58, 70, 255), outline=OUT)
        d.ellipse([x - R // 2, y - R // 2, x + R // 2, y + R // 2], fill=(196, 170, 124, 255), outline=OUT)

    # layout, in centimetres from the top-left corner of the board
    spanner(9, 8, 22)
    spanner(15.5, 8, 18)
    spanner(21.5, 8, 15, col=(190, 196, 206, 255))
    hammer(34, 7, 29)
    screwdriver(46, 7.5, 21, (226, 178, 48, 255))
    screwdriver(52.5, 7.5, 19, (58, 110, 190, 255))
    screwdriver(59, 7.5, 17, (62, 170, 96, 255))
    pliers(68, 7, 18)
    pliers(75.5, 7.5, 16, col=(60, 150, 96, 255))
    saw(8, 41, 36)
    tape(53, 46, 4.2)
    tape(63.5, 46, 3.4)
    d.rectangle([cm(69), cm(40), cm(78), cm(52)], fill=(236, 232, 214, 255), outline=OUT)             # a pinned note
    for k in range(4):
        d.line([cm(70), cm(42.5 + 2.2 * k), cm(77 - (k % 2) * 2), cm(42.5 + 2.2 * k)], fill=(120, 126, 150, 255), width=1)
    d.ellipse([cm(73) - 3, cm(40.6) - 3, cm(73) + 3, cm(40.6) + 3], fill=(220, 60, 60, 255), outline=OUT)
    return im, (Wm, Hm)


# ------------------------------------------------------------------ round wall clock with a green display (0.30 m)
SEG = {'0': 'abcdef', '1': 'bc', '2': 'abged', '3': 'abgcd', '4': 'fgbc', '5': 'afgcd', '6': 'afgcde', '7': 'abc', '8': 'abcdefg', '9': 'abcdfg'}


def _digit(d, x, y, w, h, ch, col):
    t = max(2, w // 5)
    segs = dict(a=[x + t, y, x + w - t, y + t], b=[x + w - t, y + t, x + w, y + h // 2 - 1], c=[x + w - t, y + h // 2 + 1, x + w, y + h - t],
                d=[x + t, y + h - t, x + w - t, y + h], e=[x, y + h // 2 + 1, x + t, y + h - t], f=[x, y + t, x + t, y + h // 2 - 1],
                g=[x + t, y + h // 2 - t // 2, x + w - t, y + h // 2 + t // 2])
    for s in SEG.get(ch, ''):
        d.rectangle(segs[s], fill=col)


def clock(text='21:47', px=160):
    im = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, px - 1, px - 1], fill=(70, 78, 92, 255), outline=OUT)
    d.ellipse([6, 6, px - 7, px - 7], fill=(150, 160, 172, 255), outline=OUT)
    d.ellipse([13, 13, px - 14, px - 14], fill=(12, 26, 22, 255), outline=OUT)
    for k in range(12):                                                    # hour dots
        a = k / 12 * 2 * math.pi
        x, y = px / 2 + math.sin(a) * (px / 2 - 21), px / 2 - math.cos(a) * (px / 2 - 21)
        d.rectangle([x - 1, y - 1, x + 1, y + 1], fill=(60, 220, 130, 255))
    w, h = int(px * 0.13), int(px * 0.26)
    x = int(px / 2 - (4 * w + 3 * 6 + 8) / 2)
    y = int(px / 2 - h / 2)
    col = (90, 255, 150, 255)
    for ch in text:
        if ch == ':':
            d.rectangle([x, y + h // 3 - 2, x + 3, y + h // 3 + 1], fill=col)
            d.rectangle([x, y + 2 * h // 3 - 2, x + 3, y + 2 * h // 3 + 1], fill=col)
            x += 8
        else:
            _digit(d, x, y, w, h, ch, col)
            x += w + 6
    return im, (0.30, 0.30)


def clock_glow(px=160):
    """Emission mask of the clock (only the green parts light up)."""
    im, _ = clock(px=px)
    a = np.asarray(im).astype(np.float32) / 255
    g = (a[..., 1] > 0.8) & (a[..., 0] < 0.5)
    out = np.zeros_like(a)
    out[g] = (0.25, 1.0, 0.5, 1.0)
    out[..., 3] = 1.0
    return Image.fromarray((out * 255).astype(np.uint8))


# ------------------------------------------------------------------ round rug seen from above (1.5 m)
def rug(px=256):
    im = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = px / 2
    for r, col in ((0.495, (62, 44, 84, 255)), (0.47, (86, 62, 116, 255)), (0.40, (74, 54, 102, 255)), (0.31, (68, 200, 128, 255)),
                   (0.285, (86, 62, 116, 255)), (0.12, (98, 72, 130, 255))):
        R = r * px
        d.ellipse([c - R, c - R, c + R, c + R], fill=col)
    rng = np.random.default_rng(4)
    a = np.asarray(im).astype(np.float32)
    n = 1 + (rng.random((px, px, 1)) - 0.5) * 0.10                        # woven grain
    a[..., :3] = np.clip(a[..., :3] * n, 0, 255)
    return Image.fromarray(a.astype(np.uint8)), (1.5, 1.5)


# ------------------------------------------------------------------ the corridor seen through the open door
def corridor_wall(picture=True, px_per_m=64, width=1.9, height=2.9):
    """Hallway wall: salmon paint above a wooden wainscot, a small framed picture (drawn front-on, real size)."""
    W, H = int(width * px_per_m), int(height * px_per_m)
    im = Image.new('RGBA', (W, H), (214, 150, 112, 255))
    d = ImageDraw.Draw(im)
    wy = H - int(0.95 * px_per_m)                                          # wainscot: the lowest 95 cm
    d.rectangle([0, wy, W, H], fill=(124, 82, 56, 255))
    for x in range(0, W, int(0.24 * px_per_m)):
        d.line([x, wy + 3, x, H], fill=(98, 64, 44, 255), width=1)
    d.rectangle([0, wy - 3, W, wy + 1], fill=(150, 102, 70, 255))
    d.rectangle([0, H - int(0.10 * px_per_m), W, H], fill=(88, 56, 40, 255))
    if picture:
        cx, cy, pw_, ph = int(W * 0.56), H - int(1.62 * px_per_m), int(0.36 * px_per_m), int(0.46 * px_per_m)
        d.rectangle([cx - pw_ // 2, cy - ph // 2, cx + pw_ // 2, cy + ph // 2], fill=(92, 60, 42, 255), outline=OUT)
        d.rectangle([cx - pw_ // 2 + 3, cy - ph // 2 + 3, cx + pw_ // 2 - 3, cy + ph // 2 - 3], fill=(150, 190, 206, 255))
        d.polygon([(cx - pw_ // 2 + 3, cy + ph // 2 - 3), (cx - 2, cy), (cx + 5, cy + ph // 2 - 3)], fill=(84, 132, 108, 255))
        d.polygon([(cx - 3, cy + ph // 2 - 3), (cx + 6, cy + 4), (cx + pw_ // 2 - 3, cy + ph // 2 - 3)], fill=(64, 112, 96, 255))
        d.ellipse([cx + 2, cy - ph // 2 + 6, cx + 8, cy - ph // 2 + 12], fill=(250, 232, 170, 255))
    return im, (width, height)


# ------------------------------------------------------------------ small posters / notes on the wall
def poster_heart(px=96):
    im = Image.new('RGBA', (px, int(px * 1.2)), (232, 226, 210, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.size[0] - 1, im.size[1] - 1], outline=OUT)
    s = px // 12
    heart = ["0110110", "1111111", "1111111", "0111110", "0011100", "0001000"]
    ox, oy = (px - 7 * s) // 2, int(px * 0.35)
    for j, row in enumerate(heart):
        for i, ch in enumerate(row):
            if ch == '1':
                d.rectangle([ox + i * s, oy + j * s, ox + (i + 1) * s - 1, oy + (j + 1) * s - 1], fill=(214, 60, 70, 255))
    return im, (0.30, 0.36)


def poster_blueprint(px=128):
    im = Image.new('RGBA', (px, int(px * 0.8)), (40, 84, 150, 255))
    d = ImageDraw.Draw(im)
    W, H = im.size
    d.rectangle([0, 0, W - 1, H - 1], outline=(200, 216, 240, 255))
    for y in range(8, H - 4, 10):
        d.line([4, y, W - 5, y], fill=(64, 110, 178, 255))
    d.rectangle([W // 2 - 4, H // 4, W // 2 + 4, H * 3 // 4], fill=(222, 232, 246, 255))               # a little rocket
    d.polygon([(W // 2 - 4, H // 4), (W // 2, H // 4 - 12), (W // 2 + 4, H // 4)], fill=(222, 232, 246, 255))
    d.polygon([(W // 2 - 4, H * 3 // 4), (W // 2 - 12, H * 3 // 4 + 6), (W // 2 - 4, H * 3 // 4 - 8)], fill=(222, 232, 246, 255))
    d.polygon([(W // 2 + 4, H * 3 // 4), (W // 2 + 12, H * 3 // 4 + 6), (W // 2 + 4, H * 3 // 4 - 8)], fill=(222, 232, 246, 255))
    return im, (0.42, 0.34)


def whiteboard(px=160):
    im = Image.new('RGBA', (px, int(px * 0.7)), (236, 238, 240, 255))
    d = ImageDraw.Draw(im)
    W, H = im.size
    d.rectangle([0, 0, W - 1, H - 1], outline=(120, 126, 140, 255), width=3)
    rng = np.random.default_rng(2)
    y = 12
    for k in range(7):
        col = [(214, 70, 70, 255), (60, 110, 190, 255), (60, 60, 70, 255), (62, 160, 96, 255)][k % 4]
        x = 10 + int(rng.integers(0, 14))
        while x < W - 30:
            L = int(rng.integers(8, 30))
            d.line([x, y, min(x + L, W - 12), y], fill=col, width=2)
            x += L + int(rng.integers(5, 12))
        y += 13
    d.rectangle([W - 40, H - 34, W - 30, H - 12], fill=(62, 160, 96, 255))
    d.rectangle([W - 26, H - 26, W - 16, H - 12], fill=(62, 160, 96, 255))
    return im, (0.60, 0.42)
