#!/usr/bin/env python3
"""Prepares the two start images that come from the approved pictures. Nothing is generated.

    python3 prep_refs.py

    stills/pico_porte.png   pico_ref.png without transparency, trimmed to an exact 4:3 (1192x894)   -> shot 1
    stills/nox_face.png     top-centre 1000x750 crop of nox_ref.png (a 1.2x punch-in anchored at     -> shot 8, takes 4b, 8b
                            the top): the bench top, and the opened watch lying on it, leave the frame

The approved files in refs/ are not modified; they stay the reference images of the new stills.
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "stills")


def flat(path):
    """RGB copy: some upload paths mishandle the (fully opaque) alpha channel of the approved PNGs."""
    im = Image.open(path)
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (0, 0, 0))
        bg.paste(im, mask=im.split()[3])
        return bg
    return im.convert("RGB")


def main():
    os.makedirs(OUT, exist_ok=True)

    pico = flat(os.path.join(HERE, "refs", "pico_ref.png"))
    w, h = pico.size                                   # 1200 x 896 = 1.339, not 4:3
    cw, ch = 1192, 894                                 # exact 4:3
    assert w >= cw and h >= ch, pico.size
    x0, y0 = (w - cw) // 2, (h - ch) // 2
    pico.crop((x0, y0, x0 + cw, y0 + ch)).save(os.path.join(OUT, "pico_porte.png"))

    nox = flat(os.path.join(HERE, "refs", "nox_ref.png"))
    w, h = nox.size
    cw, ch = 1000, 750                                 # 1.2x punch-in, exact 4:3
    assert w >= cw and h >= ch, nox.size
    x0 = (w - cw) // 2
    nox.crop((x0, 0, x0 + cw, ch)).save(os.path.join(OUT, "nox_face.png"))

    for name in ("pico_porte.png", "nox_face.png"):
        im = Image.open(os.path.join(OUT, name))
        assert im.mode == "RGB" and im.size[0] * 3 == im.size[1] * 4, (name, im.size, im.mode)
        print("écrit : stills/%s  %dx%d  %s" % (name, im.size[0], im.size[1], im.mode))


if __name__ == "__main__":
    main()
