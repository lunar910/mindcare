"""Finishing of the excerpt: pixel frames + series-style captions (chunks, avatars, green keywords) + music/SFX -> MP4.

    python excerpt_post.py frames OUT_DIR            EXR -> pixel PNG (1080x1920) for every rendered frame
    python excerpt_post.py captions OUT_DIR [t...]   caption overlay test on the given times
    python excerpt_post.py video OUT_DIR             final MP4 (24 fps, audio)"""
import glob
import html
import math
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
K = '/root/.claude/skills/synced/7d4567e0-870e-4333-9b59-e44776ce31b7_361ee74e-2e40-466a-9de4-24365b8cec2d/nox-pico/template'
FONT = HERE + '/post/PixelifySans.ttf'
SRC_FPS, OUT_FPS = 12, 24


def lines():
    import importlib.util
    spec = importlib.util.spec_from_file_location('exc_cfg', HERE + '/excerpt.py')
    src = open(HERE + '/excerpt.py').read()
    m = re.search(r'LINES = \[.*?\n\]', src, re.S)
    ns = {}
    exec(m.group(0), ns)
    t_end = float(re.search(r'T_END = ([0-9.]+)', src).group(1))
    return ns['LINES'], t_end


# ---------------------------------------------------------------- captions
def chunks_from_series():
    """The caption chunks of episode 1 (captions.html): [(who, [(word, is_keyword), ...]), ...] in order."""
    s = open(K + '/compositions/captions.html').read()
    out = []
    for m in re.finditer(r'<div class="cg [a-z]+" id="cg\d+"><span class="cbox"><span class="av (nox|pico)"></span>(.*?)</span></div>', s):
        words = [(html.unescape(w), bool(kw)) for kw, w in re.findall(r'<span class="cw( kw)?" id="cw[\d-]+">(.*?)</span>', m.group(2))]
        out.append((m.group(1), words))
    return out


def avatar(who, size=70):
    s = open(K + '/compositions/captions.html').read()
    m = re.search(r'\.av\.' + who + r' \{ background-image: url\("data:image/svg\+xml;utf8,(.*?)"\); \}', s)
    svg = m.group(1).replace('%23', '#')
    im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x, y, w, h, f in re.findall(r"<rect (?:x='(\d+)' )?(?:y='(\d+)' )?width='(\d+)' height='(\d+)' fill='(#[0-9A-Fa-f]{6})'/>", svg):
        x, y = int(x or 0), int(y or 0)
        d.rectangle([x, y, x + int(w) - 1, y + int(h) - 1], fill=f)
    return im.resize((size, size), Image.NEAREST)


def norm(w):
    import unicodedata
    w = unicodedata.normalize('NFD', w.lower())
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in w if unicodedata.category(c) != 'Mn'))


def timed_chunks():
    """Caption chunks for the excerpt lines, with the start time of each chunk (word timing estimated like build.mjs)."""
    L, _ = lines()
    series = chunks_from_series()
    out = []
    k = 0
    for lid, who, t0, dur, text in L:
        words = text.split()
        est = []
        for w in words:
            d = 0.05 + 0.058 * len(re.sub(r'[^\w]', '', w))
            if re.search(r'[.,!?…]$', w):
                d += 0.18
            est.append(d)
        scale = dur / sum(est)
        starts = np.cumsum([0] + est[:-1]) * scale + t0
        # walk the series chunks until this line's words are covered
        used = 0
        target = [norm(w) for w in words if norm(w)]
        while used < len(target) and k < len(series):
            cwho, cw = series[k]
            n = len([w for w, _ in cw if norm(w)])
            if [norm(w) for w, _ in cw if norm(w)] != target[used:used + n]:
                k += 1                                    # a chunk of another line (e.g. l00): skip
                continue
            wi = [i for i, w in enumerate(words) if norm(w)][used]
            out.append(dict(who=who, words=cw, start=float(starts[wi]), line_end=t0 + dur))
            used += n
            k += 1
    for i, c in enumerate(out):
        nxt = out[i + 1]['start'] if i + 1 < len(out) else 1e9
        c['end'] = min(nxt, c['line_end'] + 0.35) if nxt - c['line_end'] > 0.05 else nxt
    return out


def draw_caption(img, chunk, font, av):
    W, H = img.size
    d = ImageDraw.Draw(img)
    sp = 0.12 * 58
    parts, widths = [], []
    for w, kw in chunk['words']:
        bb = d.textbbox((0, 0), w, font=font)
        parts.append((w, kw)); widths.append(bb[2] - bb[0])
    tw = sum(widths) + sp * 2 * len(widths)
    pad_l, pad_r, pad_t, pad_b = 18, 26, 14, 18
    bw = int(av.width + 16 + tw + pad_l + pad_r)
    bh = int(max(av.height, 67) + pad_t + pad_b)
    x0 = (W - bw) // 2
    y0 = 300
    over = Image.new('RGBA', img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    od.rectangle([x0 - 4, y0 - 4, x0 + bw + 3, y0 + bh + 3], fill=(5, 7, 16, int(0.35 * 255)))
    od.rectangle([x0, y0, x0 + bw - 1, y0 + bh - 1], fill=(5, 7, 16, int(0.62 * 255)))
    img.alpha_composite(over)
    img.alpha_composite(av, (x0 + pad_l, y0 + pad_t + 2))
    x = x0 + pad_l + av.width + 16 + sp
    for (w, kw), ww in zip(parts, widths):
        col = (61, 255, 138) if kw else (244, 246, 247)
        for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4), (4, 4), (-4, 4), (4, -4), (-4, -4)):
            d.text((x + dx, y0 + pad_t + dy - 4), w, font=font, fill=(2, 3, 4))
        d.text((x, y0 + pad_t - 4), w, font=font, fill=col)
        x += ww + 2 * sp


def caption_at(chunks, t):
    for c in chunks:
        if c['start'] <= t < c['end']:
            return c
    return None


def font58():
    f = ImageFont.truetype(FONT, 58)
    try:
        f.set_variation_by_axes([700])
    except Exception:
        pass
    return f


# ---------------------------------------------------------------- commands
def cmd_frames(out):
    import pxpost
    os.makedirs(out + '/px', exist_ok=True)
    for exr in sorted(glob.glob(out + '/exr/f*.exr')):
        png = out + '/px/' + os.path.basename(exr)[:-4] + '.png'
        if os.path.exists(png) and os.path.getmtime(png) > os.path.getmtime(exr):
            continue
        P = pxpost.read_exr(exr)
        a = pxpost.process(P, down_f=2, ref=1.0)
        im = Image.fromarray((a * 255 + 0.5).astype(np.uint8))
        im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(png)
    print('pixel frames:', len(glob.glob(out + '/px/*.png')))


def cmd_captions(out, times):
    chunks = timed_chunks()
    font, avs = font58(), {w: avatar(w) for w in ('nox', 'pico')}
    for c in chunks:
        print(round(c['start'], 2), round(c['end'], 2), c['who'], ' '.join(w for w, _ in c['words']))
    for t in times:
        src = sorted(glob.glob(out + '/px/*.png')) or sorted(glob.glob(out + '/k*.png'))
        img = Image.open(src[min(int(t * SRC_FPS), len(src) - 1)]).convert('RGBA')
        c = caption_at(chunks, t)
        if c:
            draw_caption(img, c, font, avs[c['who']])
        img.convert('RGB').save(f'{out}/cap_{t:05.2f}.png')


def cmd_video(out):
    L, t_end = lines()
    chunks = timed_chunks()
    font, avs = font58(), {w: avatar(w) for w in ('nox', 'pico')}
    src = sorted(glob.glob(out + '/px/f*.png'))
    os.makedirs(out + '/final', exist_ok=True)
    n = int(round(t_end * OUT_FPS))
    for i in range(n):
        t = i / OUT_FPS
        img = Image.open(src[min(int(t * SRC_FPS), len(src) - 1)]).convert('RGBA')
        c = caption_at(chunks, t)
        if c:
            draw_caption(img, c, font, avs[c['who']])
        img.convert('RGB').save(f'{out}/final/o{i:05d}.png')
    A = K + '/assets'
    mix = out + '/final/audio.m4a'
    # music low under everything, door slam, running steps, soldering hiss while he works, Bip's beep when the door slams
    fc = ('[0:a]volume=0.16,afade=t=in:st=0:d=0.6,afade=t=out:st={fo}:d=1.2[m];'
          '[1:a]atrim=0:1.6,adelay=550|550,volume=0.9[d];'
          '[2:a]atrim=1.0:2.6,adelay=650|650,volume=0.55[f];'
          '[3:a]atrim=0:9.8,aloop=loop=1:size=470000,atrim=0:11.4,volume=0.12,afade=t=out:st=10.6:d=0.8[s];'
          '[4:a]atrim=0:0.5,adelay=900|900,volume=0.35[b];'
          '[m][d][f][s][b]amix=inputs=5:normalize=0,atrim=0:{te}[a]').format(fo=t_end - 1.2, te=t_end)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', A + '/music/cute.mp3', '-i', A + '/sfx8/door.mp3', '-i', A + '/sfx8/footsteps.mp3',
                    '-i', A + '/sfx8/solder.mp3', '-i', A + '/sfx8/beep2.mp3', '-filter_complex', fc, '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', mix], check=True)
    raw = out + '/final/raw.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(OUT_FPS), '-i', out + '/final/o%05d.png', '-i', mix, '-c:v', 'libx264',
                    '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-shortest', raw], check=True)
    final = out + '/Nox-et-Pico-ep01-extrait-3D.mp4'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-c:v', 'copy', '-af', 'loudnorm=I=-15:TP=-1:LRA=11', '-ar', '48000', '-c:a', 'aac',
                    '-b:a', '192k', final], check=True)
    print('video:', final)


if __name__ == '__main__':
    cmd, out = sys.argv[1], sys.argv[2]
    if cmd == 'frames':
        cmd_frames(out)
    elif cmd == 'captions':
        cmd_captions(out, [float(x) for x in sys.argv[3:]])
    elif cmd == 'video':
        cmd_video(out)
