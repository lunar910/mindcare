#!/usr/bin/env python3
"""Montage du sketch IA « Nox & Pico ».

    python3 montage.py build edit.json      assemble les clips, sous-titre, mixe, exporte
    python3 montage.py qc clip.mp4          planche d'images + mesure de la parole d'une prise

edit.json (chemins relatifs au dossier du fichier) :
{
  "size": [960, 720], "fps": 24, "out": "sortie/extrait.mp4", "vertical": true,
  "music": {"file": "musique.mp3", "under_voice_db": -16, "start": 0.0},
  "shots": [
    {"n": 1, "clip": "clips/s01.mp4", "caption": "Texte affiché",
     "in": null, "out": null,          # secondes dans le clip ; null = calé sur la parole
     "lead": 0.25, "tail": 0.45,       # marge avant le premier mot / après le dernier
     "silent_s": 1.6,                  # durée gardée si le plan n'a pas de parole
     "gain_db": 0.0}
  ],
  "sfx": [{"file": "sfx/door.mp3", "shot": 1, "offset": 0.0, "gain_db": -6}]
}
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = [
    "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
SR = 16000            # analyse de la parole
FRAME = 0.02          # pas d'analyse, en secondes
VOICE_TARGET_DB = -20.0   # niveau visé pour les passages parlés de chaque plan
LOUDNESS_I = -15.0        # niveau final (règle de la série)


def run(cmd, capture=False):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode("utf-8", "replace")[-2000:] + "\n")
        raise SystemExit("commande en échec : " + " ".join(cmd[:6]) + " …")
    return p.stdout if capture else None


def probe(path):
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], capture=True)
    j = json.loads(out)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    if v is None:
        raise SystemExit(f"pas d'image dans {path}")
    num, den = (v.get("avg_frame_rate") or "24/1").split("/")
    fps = float(num) / float(den) if float(den) else 24.0
    dur = float(j["format"].get("duration") or v.get("duration") or 0)
    return {"duration": dur, "width": int(v["width"]), "height": int(v["height"]), "fps": fps, "audio": a is not None}


def envelope(path, voice_band=True):
    """Niveau (dB) de la piste son par tranches de 20 ms ; None s'il n'y a pas de son."""
    af = "highpass=f=150,lowpass=f=4000," if voice_band else ""
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-af", af + f"aresample={SR}", "-ac", "1",
                        "-f", "f32le", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    x = np.frombuffer(p.stdout, dtype=np.float32)
    n = int(SR * FRAME)
    if p.returncode != 0 or x.size < n * 3:
        return None
    x = x[: x.size // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((x.astype(np.float64) ** 2).mean(axis=1)) + 1e-9)


def speech_span(env):
    """(début, fin, niveau moyen parlé) de la parole, ou None si le plan est muet."""
    if env is None or env.size == 0:
        return None
    peak = float(np.percentile(env, 99))
    floor = float(np.percentile(env, 10))
    if peak < -50 or peak - floor < 10:
        return None
    thr = max(floor + 10.0, peak - 28.0)
    on = env > thr
    # bouche les trous de moins de 0,35 s, enlève les éclats de moins de 0,08 s
    def runs(mask):
        idx = np.flatnonzero(np.diff(np.concatenate(([0], mask.astype(np.int8), [0]))))
        return list(zip(idx[::2], idx[1::2]))
    for a, b in runs(~on):
        if a > 0 and b < on.size and (b - a) * FRAME < 0.35:
            on[a:b] = True
    for a, b in runs(on):
        if (b - a) * FRAME < 0.08:
            on[a:b] = False
    r = runs(on)
    if not r or sum(b - a for a, b in r) * FRAME < 0.15:
        return None
    voiced = env[on]
    level = 10 * np.log10(np.mean(10 ** (voiced / 10)))
    return r[0][0] * FRAME, r[-1][1] * FRAME, float(level)


def load_font(size):
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    raise SystemExit("aucune police trouvée")


def wrap_caption(text, font, max_w, draw):
    """Une ligne si elle tient, sinon deux lignes équilibrées. Garde « mot ? » ensemble."""
    t = " ".join(text.split())
    for mark in "?!:;»":
        t = t.replace(" " + mark, " " + mark)
    t = t.replace("« ", "« ")
    words = t.split(" ")
    width = lambda s: draw.textlength(s, font=font)
    if width(t) <= max_w or len(words) == 1:
        return [t]
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        cost = max(width(a), width(b))
        if best is None or cost < best[0]:
            best = (cost, [a, b])
    return best[1]


def caption_png(text, size, path):
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fs = round(H * 0.050)
    while True:
        font = load_font(fs)
        lines = wrap_caption(text, font, W * 0.88, draw)
        if max(draw.textlength(l, font=font) for l in lines) <= W * 0.90 or fs <= round(H * 0.034):
            break
        fs -= 1
    stroke = max(2, round(fs * 0.10))
    lh = round(fs * 1.22)
    y0 = round(H * 0.945) - lh * len(lines)
    # ombre douce puis texte blanc cerné de noir, comme la référence
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for i, l in enumerate(lines):
        x = (W - sd.textlength(l, font=font)) / 2
        sd.text((x, y0 + i * lh + round(fs * 0.06)), l, font=font, fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(fs * 0.10)))
    for i, l in enumerate(lines):
        x = (W - draw.textlength(l, font=font)) / 2
        draw.text((x, y0 + i * lh), l, font=font, fill=(255, 255, 255, 255), stroke_width=stroke, stroke_fill=(12, 12, 12, 255))
    img.save(path)


def build(edit_path):
    edit_path = os.path.abspath(edit_path)
    base = os.path.dirname(edit_path)
    ed = json.load(open(edit_path, encoding="utf-8"))
    rel = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
    W, H = ed.get("size", [960, 720])
    fps = ed.get("fps", 24)
    out = rel(ed.get("out", "sortie/extrait.mp4"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="montage_")
    report, segs, caps, t = [], [], [], 0.0
    try:
        for k, sh in enumerate(ed["shots"]):
            clip = rel(sh["clip"])
            if not os.path.exists(clip):
                raise SystemExit(f"plan {sh.get('n', k + 1)} : fichier absent ({sh['clip']})")
            info = probe(clip)
            dur = info["duration"]
            span = speech_span(envelope(clip)) if info["audio"] else None
            lead, tail = sh.get("lead", 0.25), sh.get("tail", 0.45)
            if span:
                a = max(0.0, span[0] - lead)
                b = min(dur, span[1] + tail)
            else:
                a = 0.0
                b = min(dur, sh.get("silent_s", 1.6))
            a = sh["in"] if sh.get("in") is not None else a
            b = sh["out"] if sh.get("out") is not None else b
            a = max(0.0, min(a, dur - 0.2))
            b = max(a + 0.2, min(b, dur))
            # durée arrondie à un nombre entier d'images, pour que l'image et le son restent calés
            frames = max(1, round((b - a) * fps))
            d = frames / fps
            gain = sh.get("gain_db", 0.0)
            if span:
                gain += float(np.clip(VOICE_TARGET_DB - span[2], -12, 12))
            seg = os.path.join(tmp, f"seg{k:03d}.mkv")
            vf = f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p"
            af = (f"aresample=48000,aformat=channel_layouts=stereo,volume={gain:.2f}dB,"
                  f"afade=t=in:d=0.015,afade=t=out:st={max(0.0, d - 0.04):.3f}:d=0.04,apad")
            cmd = ["ffmpeg", "-v", "error", "-y", "-i", clip]
            if not info["audio"]:
                cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
            cmd += ["-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-map", "0:v:0", "-map", "0:a:0" if info["audio"] else "1:a:0",
                    "-vf", vf, "-af", af, "-frames:v", str(frames), "-c:v", "libx264", "-crf", "12", "-preset", "fast",
                    "-c:a", "pcm_s16le", "-shortest", seg]
            run(cmd)
            segs.append(seg)
            cap = (sh.get("caption") or "").strip()
            if cap:
                if span:
                    c0 = max(t, t + (span[0] - a) - 0.10)
                    c1 = min(t + d, t + (span[1] - a) + 0.25)
                else:
                    c0, c1 = t, t + d
                png = os.path.join(tmp, f"cap{k:03d}.png")
                caption_png(cap, (W, H), png)
                caps.append((png, c0, c1))
            report.append({"n": sh.get("n", k + 1), "clip": sh["clip"], "in": round(a, 3), "out": round(a + d, 3),
                           "start": round(t, 3), "dur": round(d, 3), "speech": [round(span[0], 2), round(span[1], 2)] if span else None,
                           "gain_db": round(gain, 1), "caption": cap})
            t += d
        total = t
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as f:
            for s in segs:
                f.write(f"file '{s}'\n")
        body = os.path.join(tmp, "body.mkv")
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", body])

        cmd = ["ffmpeg", "-v", "error", "-y", "-i", body]
        for png, _, _ in caps:
            cmd += ["-i", png]
        fc, last = [], "0:v"
        for i, (_, c0, c1) in enumerate(caps):
            fc.append(f"[{last}][{i + 1}:v]overlay=0:0:enable='between(t,{c0:.3f},{c1:.3f})'[v{i}]")
            last = f"v{i}"
        n_in = 1 + len(caps)
        mix = ["[0:a]anull[voice]"]
        labels = ["[voice]"]
        mus = ed.get("music")
        if mus and mus.get("file"):
            mfile = rel(mus["file"])
            menv = envelope(mfile, voice_band=False)
            mlevel = 10 * np.log10(np.mean(10 ** (menv / 10))) if menv is not None else -20.0
            mgain = VOICE_TARGET_DB + mus.get("under_voice_db", -16.0) - mlevel
            cmd += ["-stream_loop", "-1", "-ss", f"{mus.get('start', 0.0):.3f}", "-i", mfile]
            mix.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},volume={mgain:.2f}dB,"
                       f"afade=t=in:d=0.4,afade=t=out:st={max(0.0, total - 1.0):.3f}:d=1.0[mus]")
            labels.append("[mus]")
            n_in += 1
        for j, fx in enumerate(ed.get("sfx", [])):
            at = fx.get("at")
            if at is None:
                r = next(r for r in report if r["n"] == fx["shot"])
                at = r["start"] + fx.get("offset", 0.0)
            cmd += ["-i", rel(fx["file"])]
            ms = int(max(0.0, at) * 1000)
            mix.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,volume={fx.get('gain_db', -6.0):.2f}dB,adelay={ms}|{ms}[fx{j}]")
            labels.append(f"[fx{j}]")
            n_in += 1
        mix.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,"
                   f"loudnorm=I={LOUDNESS_I}:TP=-1.5:LRA=11,aresample=48000[aout]")
        fc += mix
        cmd += ["-filter_complex", ";".join(fc), "-map", f"[{last}]" if caps else "0:v", "-map", "[aout]",
                "-t", f"{total:.3f}", "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
                "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
        run(cmd)
        outs = [out]
        if ed.get("vertical", True):
            vout = os.path.splitext(out)[0] + "_vertical.mp4"
            h = round(1080 * H / W / 2) * 2
            run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", f"scale=1080:{h}:flags=lanczos,pad=1080:1920:0:(1920-{h})/2:black",
                 "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", vout])
            outs.append(vout)
        json.dump({"total_s": round(total, 3), "shots": report, "outputs": outs}, open(os.path.splitext(out)[0] + "_rapport.json", "w"),
                  ensure_ascii=False, indent=1)
        print(f"durée totale : {total:.2f} s — {len(report)} plans")
        for r in report:
            sp = f"parole {r['speech'][0]:.2f}–{r['speech'][1]:.2f}" if r["speech"] else "muet"
            print(f"  plan {r['n']:>2}  {r['start']:6.2f} s  durée {r['dur']:.2f}  (clip {r['in']:.2f}–{r['out']:.2f}, {sp}, gain {r['gain_db']:+.1f} dB)  {r['caption']}")
        for o in outs:
            print("écrit :", o)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def qc(clip, sheet=None):
    info = probe(clip)
    span = speech_span(envelope(clip)) if info["audio"] else None
    print(f"{os.path.basename(clip)} : {info['width']}x{info['height']}, {info['fps']:.2f} i/s, {info['duration']:.2f} s, son : {'oui' if info['audio'] else 'non'}")
    if span:
        print(f"  parole de {span[0]:.2f} à {span[1]:.2f} s (niveau {span[2]:.1f} dB) ; silence avant {span[0]:.2f} s, après {info['duration'] - span[1]:.2f} s")
    else:
        print("  pas de parole détectée")
    sheet = sheet or os.path.splitext(clip)[0] + "_planche.jpg"
    n = max(1, int(info["duration"] * 3))
    cols = min(6, n)
    rows = -(-n // cols)
    run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-vf",
         f"fps=3,scale=480:-2,drawtext=text='%{{pts\\:hms}}':fontcolor=white:fontsize=20:box=1:boxcolor=black@0.6:x=6:y=6,tile={cols}x{rows}",
         "-frames:v", "1", "-q:v", "3", sheet])
    print("  planche :", sheet)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("edit")
    q = sub.add_parser("qc")
    q.add_argument("clip")
    q.add_argument("-o", "--sheet")
    a = ap.parse_args()
    build(a.edit) if a.cmd == "build" else qc(a.clip, a.sheet)
