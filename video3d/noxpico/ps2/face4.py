"""Faces of version 4: lip-sync, blinks and expressions with the timings measured on the reference video.

    F = FaceTrack(E, who, perf, base=[...], events=[...], blinks=[...], amp=1.0)
    F.values(t)        -> {shape key: value} for facemorph (expressions + speech + blink); the eyes come from perf.eyes(t)

Targets (study/reports/face-data.md):
  - mouth: opens and closes in about 70 ms (2 frames at 30 fps); lips really closed (>= 100 ms) on m / b / p and at
    commas and full stops; no 1-frame shape; the jaw drops (lip gap 7-10 % of the face height, more on stressed words);
    mouth corners neutral while speaking
  - blinks: on every head turn of 15 deg or more, closed at the turn's peak speed (held longer for 30 deg or more);
    otherwise sparse (about one per 4 s); close in 3-4 frames, reopen in 5-7
  - brows: still during calm speech; a quick raise of both brows (about 0.17 s up, held, 0.3 s down) on a stressed word
"""
import math

import numpy as np

import acting as AC

RATE = 120.0
VIS = {
    'aa': {'jawOpen': 1.0},
    'E': {'jawOpen': 0.55, 'mouthWide': 0.45},
    'I': {'jawOpen': 0.30, 'mouthWide': 0.75, 'lipsUp': 0.25},
    'O': {'jawOpen': 0.62, 'mouthNarrow': 0.85},
    'U': {'jawOpen': 0.32, 'mouthNarrow': 1.0},
    'PP': {},
    'FF': {'jawOpen': 0.12, 'lipsUp': 0.35},
    'DD': {'jawOpen': 0.32, 'mouthWide': 0.15},
    'nn': {'jawOpen': 0.28, 'mouthWide': 0.1},
    'SS': {'jawOpen': 0.18, 'mouthWide': 0.35},
    'kk': {'jawOpen': 0.36},
    'RR': {'jawOpen': 0.34, 'mouthNarrow': 0.25},
    'CH': {'jawOpen': 0.22, 'mouthNarrow': 0.6},
    'TH': {'jawOpen': 0.25},
    'sil': {},
}
MOUTH_KEYS = ('jawOpen', 'mouthWide', 'mouthNarrow', 'lipsUp')


def line_segments(E, lid, min_close=0.10, min_vis=0.067):
    """[(t0, t1, viseme)] for a line, phrase by phrase; closures (PP, commas, full stops) last at least min_close,
    nothing is shorter than min_vis (2 frames)."""
    import speech_fr as SP
    import script4
    out = []
    for text, p0, p1 in script4.PHRASES[lid]:
        seq = list(SP.french_visemes(text))
        while seq and seq[-1][0] == 'sil':                   # the phrase ends when its last sound ends
            seq.pop()
        segs = [[v, d] for v, d in seq]
        tot = sum(d for _, d in segs)
        k = (p1 - p0) / tot
        for sg in segs:
            sg[1] *= k
            need = min_close if sg[0] in ('PP', 'sil') else min_vis
            if sg[1] < need:
                sg[1] = need
        extra = sum(d for _, d in segs) - (p1 - p0)
        if extra > 0:
            flex = [sg for sg in segs if sg[0] in ('aa', 'E', 'I', 'O', 'U')]
            tf = sum(sg[1] for sg in flex)
            for sg in flex:
                sg[1] -= extra * sg[1] / tf
        t = p0
        for v, d in segs:
            out.append((t, t + d, v))
            t += d
    return out


def stressed_vowels(E, lid, words):
    """Times of the loudest vowel of each word given (the head nods and brow raises land on them)."""
    import chore4
    segs = line_segments(E, lid)
    out = []
    for w in words:
        ws = chore4.word(E, lid, w)
        we = next(e for ww, s, e in chore4.word_times(E, lid) if abs(s - ws) < 1e-6)
        best = None
        for t0, t1, v in segs:
            if t1 > ws and t0 < we and v in VIS and VIS[v].get('jawOpen', 0) >= 0.5:
                c = (t0 + t1) / 2
                if best is None or VIS[v]['jawOpen'] > best[1]:
                    best = (c, VIS[v]['jawOpen'])
        out.append(best[0] if best else (ws + we) / 2)
    return out


class FaceTrack:
    def __init__(self, E, who, perf, base, events=(), blinks=(), amp=1.0, t_end=None, stress=()):
        """base: [(t, expression dict)] held expressions, minimum-jerk transitions between keys (0.25 s before a key
        to the key); events: [(t_peak, expression dict, rise, hold, fall)] quick accents on top; blinks: extra blink
        times; stress: [(line_id, [words])] whose vowels open wider."""
        self.E, self.who, self.perf, self.base, self.events, self.amp = E, who, perf, base, list(events), amp
        self.t_end = t_end or E.T_END
        self.stress_t = []
        for lid, words in stress:
            self.stress_t += stressed_vowels(E, lid, words)
        self._bake_mouth()
        self._blinks(list(blinks))

    # ---- speech
    def _bake_mouth(self):
        n = int(math.ceil(self.t_end * RATE)) + 1
        tgt = np.zeros((n, len(MOUTH_KEYS)))
        talk = np.zeros(n)
        for l in self.E.LINES:
            if l[1] != self.who:
                continue
            for t0, t1, v in line_segments(self.E, l[0]):
                t0, t1 = t0 - 0.06, t1 - 0.06               # the mouth moves about 2 frames before the sound
                i0, i1 = max(int(round(t0 * RATE)), 0), int(round(t1 * RATE))
                vals = VIS.get(v, {})
                boost = 1.0
                for ts in self.stress_t:
                    if t0 - 0.02 <= ts <= t1 + 0.02:
                        boost = 1.3
                for j, key in enumerate(MOUTH_KEYS):
                    x = vals.get(key, 0.0) * (self.amp if key == 'jawOpen' else 1.0)
                    if key == 'jawOpen':
                        x *= boost
                    tgt[i0:i1, j] = min(x, 1.0)
                talk[i0:i1] = 1.0
        # 10-90 % in about 70 ms: a critically damped follower with a 15 ms half-life
        self.mouth = AC.Baked(AC.spring_follow(tgt, RATE, 0.0145).clip(0, 1), RATE)
        self.talk = AC.Baked(AC.spring_follow(talk[:, None], RATE, 0.08)[:, 0], RATE)

    # ---- blinks
    def _blinks(self, extra):
        items = []
        if self.perf is not None and self.perf.gaze is not None and hasattr(self.perf.gaze, 'head_segs'):
            for t_peak, deg, d in self.perf.gaze.turns(15.0):
                hold = 0.22 if deg >= 30 else 0.04
                close = 0.12
                items.append((t_peak - close - hold / 2, close, hold, 0.20))
        for t in extra:
            items.append((t, 0.12, 0.03, 0.20))
        items.sort()
        kept = []
        for it in items:                                 # never two blinks closer than 0.6 s
            if not kept or it[0] - kept[-1][0] > 0.6:
                kept.append(it)
        self.blink_items = kept

    def blink(self, t):
        return max([AC.bump(t, t0, c, h, o) for t0, c, h, o in self.blink_items] + [0.0])

    # ---- expressions
    def _base(self, t):
        """Held expressions; key (t, expr[, change]) is reached at t after a change of `change` seconds (0.25 by
        default; 0.07 = a 2-frame snap, as the reference's emotional switches)."""
        keys = self.base
        if t <= keys[0][0]:
            return dict(keys[0][1])
        for k0, k1 in zip(keys, keys[1:]):
            t0, e0 = k0[0], k0[1]
            t1, e1 = k1[0], k1[1]
            ch = k1[2] if len(k1) > 2 else 0.25
            if t < t1:
                ts = max(t0, t1 - ch)
                if t < ts:
                    return dict(e0)
                x = AC.snappy((t - ts) / (t1 - ts)) if ch <= 0.1 else AC.minjerk((t - ts) / (t1 - ts))
                return {k: e0.get(k, 0.0) * (1 - x) + e1.get(k, 0.0) * x for k in set(e0) | set(e1)}
        return dict(keys[-1][1])

    def values(self, t):
        import facemorph
        vals = facemorph.expand(self._base(t))
        for tp, ex, rise, hold, fall in self.events:
            w = AC.bump(t, tp - rise, rise, hold, fall)
            if w > 0:
                for k, v in facemorph.expand(ex).items():
                    vals[k] = vals.get(k, 0.0) + v * w
        talk = self.talk.at(t)
        if talk > 0:                                     # neutral mouth corners while speaking
            for k in ('smile_L', 'smile_R', 'frown_L', 'frown_R'):
                if k in vals:
                    vals[k] *= 1.0 - 0.7 * talk
        m = self.mouth.at(t)
        for j, k in enumerate(MOUTH_KEYS):
            vals[k] = min(1.0, vals.get(k, 0.0) + float(m[j]))
        b = self.blink(t)
        if b > 0:
            for k in ('eyeClosed_L', 'eyeClosed_R'):
                vals[k] = max(vals.get(k, 0.0), b)
            for k in ('eyeWide_L', 'eyeWide_R', 'eyeSquint_L', 'eyeSquint_R'):
                if k in vals:
                    vals[k] *= 1 - b
        return vals
