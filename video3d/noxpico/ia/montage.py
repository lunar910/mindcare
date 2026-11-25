#!/usr/bin/env python3
"""Montage du sketch IA « Nox & Pico ».

    python3 montage.py build edit.json      assemble les clips, sous-titre, mixe, exporte
    python3 montage.py qc clip.mp4          planche d'images + mesure de la parole d'une prise

edit.json (chemins relatifs au dossier du fichier) :
{
  "size": [960, 720], "fps": 24, "out": "sortie/extrait.mp4", "vertical": true,
  "music": {"file": "musique.mp3", "under_voice_db": -16, "start": 0.0,
            "enter_s": 0.6,            # la musique entre après ce délai
            "stop_at_shot": 11},       # et se coupe net à l'entrée de ce plan
  "shots": [
    {"n": 1, "clip": "clips/s01.mp4", "caption": "Texte affiché",
     "in": null, "out": null,          # secondes dans le clip ; null = calé sur la parole
     "lead": 0.25, "tail": 0.45,       # marge avant le premier mot / après le dernier
     "silent_s": 1.6,                  # durée gardée si le plan n'a pas de parole (à partir de "in" s'il est donné)
     "hold_start": 0.0,                # fige la première image pendant ce temps (silence avant la réplique)
     "push_in": 0.0,                   # zoom avant lent sur tout le plan (0.14 = +14 %)
     "mute": false,                    # coupe le son du clip
     "audio_from": "clips/autre.mp4",  # son pris sur une autre prise (voix hors champ)
     "hflip": false,                   # image retournée gauche-droite (prise à l'envers)
     "gain_db": 0.0},
    {"n": 6, "still": "images/deux_etabli.png", "silent_s": 1.3}   # image fixe à la place d'un clip
  ],
  "sfx": [{"file": "sfx/door.mp3", "shot": 1, "offset": 0.0, "gain_db": -6,
           "from": 4.84,               # commence à ce moment du fichier son
           "dur": 1.2,                 # durée maximale (fondu court à la fin)
           "until_shot": 3}]           # ou : s'arrête net à l'entrée de ce plan
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

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = [
    os.path.join(HERE, "polices", "Inter-SemiBold.otf"),          # police fournie avec l'outil
    "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "C:/Windows/Fonts/segoeuib.ttf",                               # Windows
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",           # Mac
    "/Library/Fonts/Arial Bold.ttf",
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
    """(début, fin, niveau moyen parlé, pauses) de la parole, ou None si le plan est muet.
    pauses = silences d'au moins 0,15 s à l'intérieur de la réplique, [(début, fin), ...]."""
    if env is None or env.size == 0:
        return None
    peak = float(np.percentile(env, 99))
    floor = float(np.percentile(env, 10))
    if peak < -50 or peak - floor < 10:
        return None
    thr = max(floor + 10.0, peak - 28.0)
    raw = env > thr

    def runs(mask):
        idx = np.flatnonzero(np.diff(np.concatenate(([0], mask.astype(np.int8), [0]))))
        return list(zip(idx[::2], idx[1::2]))
    # enlève les éclats de moins de 0,08 s, puis bouche les trous de moins de 0,35 s
    for a, b in runs(raw):
        if (b - a) * FRAME < 0.08:
            raw[a:b] = False
    on = raw.copy()
    for a, b in runs(~on):
        if a > 0 and b < on.size and (b - a) * FRAME < 0.35:
            on[a:b] = True
    r = runs(on)
    if not r or sum(b - a for a, b in r) * FRAME < 0.15:
        return None
    i0, i1 = r[0][0], r[-1][1]
    pauses = [(a * FRAME, b * FRAME) for a, b in runs(~raw[i0:i1]) if (b - a) * FRAME >= 0.15]
    pauses = [(a + i0 * FRAME, b + i0 * FRAME) for a, b in pauses]
    voiced = env[raw]
    level = 10 * np.log10(np.mean(10 ** (voiced / 10)))
    return i0 * FRAME, i1 * FRAME, float(level), pauses


def caption_windows(parts, span, offset, t0, t1):
    """Fenêtres d'affichage d'un sous-titre en plusieurs temps. Chaque partie apparaît un peu avant
    d'être dite : on change de partie dans les plus longues pauses de la réplique, sinon au prorata
    du nombre de lettres. offset = temps du film qui correspond au temps 0 du son."""
    if not span:
        step = (t1 - t0) / len(parts)
        return [(t0 + i * step, t0 + (i + 1) * step) for i in range(len(parts))]
    s0, s1 = span[0], span[1]
    cuts = []
    if len(parts) > 1:
        gaps = sorted(span[3], key=lambda g: g[0] - g[1])[: len(parts) - 1]
        if len(gaps) == len(parts) - 1:
            cuts = sorted(g[1] - 0.10 for g in gaps)          # juste avant la reprise de la parole
        else:
            n = [len(p) for p in parts]
            acc = np.cumsum(n)[:-1] / sum(n)
            cuts = [s0 + float(x) * (s1 - s0) for x in acc]
    edges = [s0 - 0.10] + cuts + [s1 + 0.25]
    return [(max(t0, offset + edges[i]), min(t1, offset + edges[i + 1])) for i in range(len(parts))]


def load_font(size):
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    raise SystemExit("aucune police trouvée")


WEAK_END = {"le", "la", "les", "l'", "un", "une", "des", "du", "de", "d'", "à", "au", "aux", "et", "ou", "mais", "que", "qu'",
            "qui", "ma", "mon", "mes", "ta", "ton", "tes", "sa", "son", "ses", "ce", "cette", "ces", "en", "dans", "sur",
            "pour", "par", "avec", "sans", "deux", "trois", "très", "plus", "ne", "n'", "je", "tu", "il", "elle", "on", "y"}


def wrap_caption(text, font, max_w, draw):
    """Une ligne si elle tient, sinon deux lignes : coupure de préférence après une ponctuation,
    jamais après un petit mot (« des », « deux »…). Garde « mot ? » ensemble."""
    t = " ".join(text.split())
    for mark in "?!:;»":
        t = t.replace(" " + mark, "\u00a0" + mark)
    t = t.replace("« ", "«\u00a0")
    words = t.split(" ")
    width = lambda x: draw.textlength(x, font=font)
    if width(t) <= max_w or len(words) == 1:
        return [t]
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wa, wb = width(a), width(b)
        cost = max(wa, wb) / max_w
        last = words[i - 1].lower()
        if last[-1] in ",;:…!?.»" or last.endswith(("\u00a0?", "\u00a0!")):
            cost -= 0.30                      # belle coupure : après une ponctuation
        elif last in WEAK_END:
            cost += 0.25                      # mauvaise coupure : après un petit mot
        if max(wa, wb) > max_w:
            cost += 2.0
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
            n = sh.get("n", k + 1)
            still = sh.get("still")
            src = rel(still or sh["clip"])
            if not os.path.exists(src):
                raise SystemExit(f"plan {n} : fichier absent ({still or sh['clip']})")
            info = None if still else probe(src)
            vdur = 1e9 if still else info["duration"]
            # d'où vient le son : du clip lui-même, d'une autre prise, ou de nulle part
            asrc = None
            if sh.get("audio_from"):
                asrc = rel(sh["audio_from"])
                if not os.path.exists(asrc):
                    raise SystemExit(f"plan {n} : son absent ({sh['audio_from']})")
            elif not still and info["audio"] and not sh.get("mute"):
                asrc = src
            span = speech_span(envelope(asrc)) if asrc else None
            lead, tail = sh.get("lead", 0.25), sh.get("tail", 0.45)
            hold = max(0.0, sh.get("hold_start", 0.0))
            if sh.get("audio_from"):
                adur = probe(asrc)["duration"]
                aa = max(0.0, span[0] - lead) if span else 0.0
                ab = min(adur, span[1] + tail) if span else min(adur, sh.get("silent_s", 1.6))
                a = sh["in"] if sh.get("in") is not None else 0.0
                d = ab - aa
            else:
                if span:
                    a, b = max(0.0, span[0] - lead), min(vdur, span[1] + tail)
                    a = sh["in"] if sh.get("in") is not None else a
                else:
                    a = sh["in"] if sh.get("in") is not None else 0.0
                    b = a + sh.get("silent_s", 1.6)
                b = sh["out"] if sh.get("out") is not None else b
                a = max(0.0, min(a, vdur - 0.2))
                b = max(a + 0.2, min(b, vdur))
                aa, d = a, b - a
            # durée arrondie à un nombre entier d'images, pour que l'image et le son restent calés
            frames = max(1, round((hold + d) * fps))
            total_d = frames / fps
            gain = sh.get("gain_db", 0.0)
            if span:
                gain += float(np.clip(VOICE_TARGET_DB - span[2], -12, 12))

            # image
            vf = [f"fps={fps}", f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}", "setsar=1"]
            if sh.get("hflip"):
                vf.append("hflip")
            vf.append(f"tpad=start_mode=clone:start_duration={hold:.3f}:stop_mode=clone:stop_duration=30")
            push = sh.get("push_in", 0.0)
            if push:
                vf += [f"scale={3 * W}:{3 * H}:flags=lanczos",
                       f"zoompan=z='1+{push:.4f}*on/{max(1, frames - 1)}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s={W}x{H}:fps={fps}"]
            vf.append("format=yuv420p")
            vseg = os.path.join(tmp, f"v{k:03d}.mkv")
            cmd = ["ffmpeg", "-v", "error", "-y"]
            cmd += ["-loop", "1", "-framerate", str(fps), "-i", src] if still else ["-i", src, "-ss", f"{a:.3f}"]
            cmd += ["-an", "-vf", ",".join(vf), "-frames:v", str(frames), "-c:v", "libx264", "-crf", "12", "-preset", "fast", vseg]
            run(cmd)
            # son
            aseg = os.path.join(tmp, f"a{k:03d}.wav")
            if asrc:
                ms = int(round(hold * 1000))
                af = (f"aresample=48000,aformat=channel_layouts=stereo,volume={gain:.2f}dB,afade=t=in:d=0.015,"
                      f"afade=t=out:st={max(0.0, d - 0.04):.3f}:d=0.04," + (f"adelay={ms}:all=1," if ms else "") + "apad")
                run(["ffmpeg", "-v", "error", "-y", "-i", asrc, "-ss", f"{aa:.3f}", "-t", f"{d:.3f}", "-vn", "-af", af,
                     "-t", f"{total_d:.3f}", "-c:a", "pcm_s16le", aseg])
            else:
                run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{total_d:.3f}",
                     "-c:a", "pcm_s16le", aseg])
            seg = os.path.join(tmp, f"seg{k:03d}.mkv")
            run(["ffmpeg", "-v", "error", "-y", "-i", vseg, "-i", aseg, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                 "-c:a", "pcm_s16le", "-t", f"{total_d:.3f}", seg])
            segs.append(seg)
            cap = sh.get("caption") or ""
            parts = [c.strip() for c in ([cap] if isinstance(cap, str) else cap) if c and c.strip()]
            if parts:
                wins = caption_windows(parts, span, t + hold - aa, t, t + total_d)
                for j, (part, (c0, c1)) in enumerate(zip(parts, wins)):
                    png = os.path.join(tmp, f"cap{k:03d}_{j}.png")
                    caption_png(part, (W, H), png)
                    caps.append((png, c0, c1))
            cap = " / ".join(parts)
            report.append({"n": n, "source": still or sh["clip"], "in": round(a, 3), "start": round(t, 3), "dur": round(total_d, 3),
                           "hold_start": hold, "speech": [round(span[0], 2), round(span[1], 2)] if span else None,
                           "sound": "autre prise" if sh.get("audio_from") else ("clip" if asrc else "muet"),
                           "gain_db": round(gain, 1), "caption": cap})
            t += total_d
        total = t
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as f:
            for s in segs:
                f.write("file '" + s.replace(os.sep, "/") + "'\n")
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
            enter = max(0.0, mus.get("enter_s", 0.0))
            stop = total
            if mus.get("stop_at_shot") is not None:
                stop = next(r["start"] for r in report if r["n"] == mus["stop_at_shot"])
                fade = f"afade=t=out:st={max(0.0, stop - enter - 0.06):.3f}:d=0.06"
            else:
                fade = f"afade=t=out:st={max(0.0, stop - enter - 1.0):.3f}:d=1.0"
            ms = int(round(enter * 1000))
            cmd += ["-stream_loop", "-1", "-ss", f"{mus.get('start', 0.0):.3f}", "-i", mfile]
            mix.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{max(0.1, stop - enter):.3f},"
                       f"volume={mgain:.2f}dB,afade=t=in:d=0.4,{fade}" + (f",adelay={ms}:all=1" if ms else "") + "[mus]")
            labels.append("[mus]")
            n_in += 1
        for j, fx in enumerate(ed.get("sfx", [])):
            at = fx.get("at")
            if at is None:
                r = next(r for r in report if r["n"] == fx["shot"])
                at = r["start"] + fx.get("offset", 0.0)
            dur = fx.get("dur")
            if fx.get("until_shot") is not None:
                end = next(r["start"] for r in report if r["n"] == fx["until_shot"]) - at
                dur = min(dur, end) if dur else end
            cmd += ["-ss", f"{max(0.0, fx.get('from', 0.0)):.3f}", "-i", rel(fx["file"])]
            ms = int(max(0.0, at) * 1000)
            cut = ""
            if dur:
                dur = max(0.05, dur)
                cut = f"atrim=0:{dur:.3f},afade=t=out:st={max(0.0, dur - 0.08):.3f}:d=0.08,"
            mix.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,{cut}volume={fx.get('gain_db', -6.0):.2f}dB,adelay={ms}:all=1[fx{j}]")
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
            sp = f"parole {r['speech'][0]:.2f}–{r['speech'][1]:.2f}" if r["speech"] else "sans parole"
            print(f"  plan {r['n']:>2}  {r['start']:6.2f} s  durée {r['dur']:.2f}  (son : {r['sound']}, {sp}, gain {r['gain_db']:+.1f} dB)  {r['caption']}")
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
        if span[3]:
            print("  pauses dans la réplique : " + ", ".join(f"{a:.2f}–{b:.2f}" for a, b in span[3]))
    else:
        print("  pas de parole détectée")
    sheet = sheet or os.path.splitext(clip)[0] + "_planche.jpg"
    tmp = tempfile.mkdtemp(prefix="planche_")
    try:
        run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-vf", "fps=3,scale=480:-2", os.path.join(tmp, "f%04d.png")])
        frames = sorted(f for f in os.listdir(tmp) if f.endswith(".png"))
        if not frames:
            raise SystemExit("aucune image extraite")
        first = Image.open(os.path.join(tmp, frames[0]))
        w, h = first.size
        cols = min(6, len(frames))
        rows = -(-len(frames) // cols)
        board = Image.new("RGB", (cols * w, rows * h), (0, 0, 0))
        font = load_font(20)
        for i, f in enumerate(frames):
            im = Image.open(os.path.join(tmp, f)).convert("RGB")
            d = ImageDraw.Draw(im)
            label = f"{i / 3:.2f} s"
            d.rectangle([0, 0, d.textlength(label, font=font) + 12, 28], fill=(0, 0, 0))
            d.text((6, 3), label, font=font, fill=(255, 255, 255))
            board.paste(im, ((i % cols) * w, (i // cols) * h))
        board.save(sheet, quality=85)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
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
