"""Finishing of the 3D excerpt: series-style captions (chunks, avatars, green keywords) + music and sound effects -> MP4.

    python post2.py captions OUT_DIR t1 t2 ...     caption overlay test on rendered frames (writes OUT_DIR/cap_*.png)
    python post2.py video OUT_DIR [name.mp4]       final MP4, 30 fps, from OUT_DIR/px/fNNNNN.png

Sound: the series' music bed, the door banging open and Pico's running steps.  No voices yet (they are generated last in
the series' pipeline).  The level is normalised in two passes so that nothing pumps."""
import glob
import html
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
K = '/root/.claude/skills/synced/7d4567e0-870e-4333-9b59-e44776ce31b7_361ee74e-2e40-466a-9de4-24365b8cec2d/nox-pico/template'
FONT = HERE + '/PixelifySans.ttf'
FPS = 30
LUFS = -17.0


def lines():
    src = open(HERE + '/excerpt2.py').read()
    ns = {}
    exec(re.search(r'LINES = \[.*?\n\]', src, re.S).group(0), ns)
    return ns['LINES'], float(re.search(r'T_END = ([0-9.]+)', src).group(1))


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
        used = 0
        target = [norm(w) for w in words if norm(w)]
        while used < len(target) and k < len(series):
            cwho, cw = series[k]
            n = len([w for w, _ in cw if norm(w)])
            if [norm(w) for w, _ in cw if norm(w)] != target[used:used + n]:
                k += 1                                    # a chunk of another line: skip
                continue
            wi = [i for i, w in enumerate(words) if norm(w)][used]
            out.append(dict(who=who, words=cw, start=float(starts[wi]), line_end=t0 + dur))
            used += n
            k += 1
    for i, c in enumerate(out):
        nxt = out[i + 1]['start'] if i + 1 < len(out) else 1e9
        c['end'] = min(nxt, c['line_end'] + 0.12) if nxt - c['line_end'] > 0.05 else nxt   # a caption never outlives its shot
    return out


def draw_caption(img, chunk, font, av, y0=300):
    W, H = img.size
    d = ImageDraw.Draw(img)
    sp = 0.12 * 58
    parts, widths = [], []
    for w, kw in chunk['words']:
        bb = d.textbbox((0, 0), w, font=font)
        parts.append((w, kw))
        widths.append(bb[2] - bb[0])
    tw = sum(widths) + sp * 2 * len(widths)
    pad_l, pad_r, pad_t, pad_b = 18, 26, 14, 18
    bw = int(av.width + 16 + tw + pad_l + pad_r)
    bh = int(max(av.height, 67) + pad_t + pad_b)
    x0 = (W - bw) // 2
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
def cmd_captions(out, times):
    chunks = timed_chunks()
    font, avs = font58(), {w: avatar(w) for w in ('nox', 'pico')}
    for c in chunks:
        print(round(c['start'], 2), round(c['end'], 2), c['who'], ' '.join(w for w, _ in c['words']))
    for t in times:
        f = int(round(t * FPS))
        img = Image.open(f'{out}/px/f{f:05d}.png').convert('RGBA')
        c = caption_at(chunks, t)
        if c:
            draw_caption(img, c, font, avs[c['who']])
        img.convert('RGB').save(f'{out}/cap_{t:05.2f}.png')


def mix_audio(path, t_end):
    A = K + '/assets'
    # music bed (as in the series, a bit more present since there are no voices), the door flung open, running steps
    fc = ('[0:a]atrim=0.9:{m1},asetpts=PTS-STARTPTS,volume=1.0,afade=t=in:st=0:d=0.4,afade=t=out:st={fo}:d=1.2[m];'
          '[1:a]atrim=4.30:5.60,asetpts=PTS-STARTPTS,afade=t=out:st=1.0:d=0.3,adelay=300|300,volume=0.30[d];'
          '[2:a]atrim=2.45:3.85,asetpts=PTS-STARTPTS,afade=t=out:st=1.05:d=0.35,adelay=620|620,volume=0.34[f];'
          '[m][d][f]amix=inputs=3:normalize=0,atrim=0:{te}[a]').format(m1=0.9 + t_end, fo=t_end - 1.2, te=t_end)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', A + '/music/cute.mp3', '-i', A + '/sfx8/door.mp3', '-i', A + '/sfx8/footsteps.mp3',
                    '-filter_complex', fc, '-map', '[a]', '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', path], check=True)
    # two-pass loudness: measure, then one fixed gain; a limiter only catches the few peaks above -1 dBFS
    def measure(f):
        probe = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'ebur128=peak=true:framelog=quiet', '-f', 'null', '-'],
                               capture_output=True, text=True).stderr
        return float(re.findall(r'I:\s+(-?[0-9.]+) LUFS', probe)[-1]), max(float(x) for x in re.findall(r'Peak:\s+(-?[0-9.]+) dBFS', probe))
    I, peak = measure(path)
    gain = LUFS - I
    out = path.replace('.wav', '_n.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', path, '-af', f'volume={gain:.2f}dB,alimiter=limit=0.89:attack=5:release=60:level=disabled',
                    '-ar', '48000', '-c:a', 'pcm_s16le', out], check=True)
    I2, peak2 = measure(out)
    print(f'audio: {I:.1f} LUFS, peak {peak:.1f} dBFS -> gain {gain:+.1f} dB -> {I2:.1f} LUFS, peak {peak2:.1f} dBFS')
    return out


def cmd_video(out, name='Nox-et-Pico-ep01-extrait-3D-v2.mp4'):
    L, t_end = lines()
    chunks = timed_chunks()
    font, avs = font58(), {w: avatar(w) for w in ('nox', 'pico')}
    n = int(round(t_end * FPS))
    wav = mix_audio(out + '/audio.wav', t_end)
    final = f'{out}/{name}'
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1080x1920', '-r', str(FPS), '-i', '-',
                           '-i', wav, '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                           '-shortest', '-movflags', '+faststart', final], stdin=subprocess.PIPE)
    last = None
    for f in range(n):
        p = f'{out}/px/f{f:05d}.png'
        if os.path.exists(p):
            last = p
        img = Image.open(last).convert('RGBA')
        if img.size != (1080, 1920):
            img = img.resize((1080, 1920), Image.NEAREST)
        c = caption_at(chunks, f / FPS)
        if c:
            draw_caption(img, c, font, avs[c['who']])
        ff.stdin.write(img.convert('RGB').tobytes())
    ff.stdin.close()
    ff.wait()
    print('video:', final, os.path.getsize(final))


if __name__ == '__main__':
    cmd, out = sys.argv[1], sys.argv[2]
    if cmd == 'captions':
        cmd_captions(out, [float(x) for x in sys.argv[3:]])
    elif cmd == 'video':
        cmd_video(out, *sys.argv[3:4])
