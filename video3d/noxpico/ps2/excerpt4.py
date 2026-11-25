"""Nox & Pico, episode 1 excerpt in 3D, version 4: human acting (held natural poses, gaze, authored gestures, planted feet).

    python excerpt4.py statics OUT [--ao 64] [--shots wide,medP]   the set (+ ambient occlusion) from each shot's camera, once
    python excerpt4.py frames  OUT [--frames A:B]                  OUT/px/fNNNNN.png  (1080x1920, no captions)
    python excerpt4.py stills  OUT --times 1.2,4.0 [--ao 16]       quick stills, statics rendered on the fly
    python excerpt4.py motion  OUT                                 numbers about the motion (speeds, jumps) for every frame

Frame f (from 0) is the time f / 30 s.  Each shot has a fixed camera; within a shot only the characters, the door and
Bip are rendered for each frame and merged with the set by depth (see ps2render.py / ps2shade.py)."""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
import addon_utils
import numpy as np
from mathutils import Matrix, Quaternion, Vector

FPS = 30
# who plays: the realistic models; their clips were made for the first models' rigs and are re-targeted (anim2.retarget)
CAST = dict(pico=dict(name='picoR', rig='picoR_rigged', clips_from='pico', scale=1.0),
            nox=dict(name='noxR', rig='noxR_rigged', clips_from='nox2', scale=1.0))
RES = (432, 768)             # internal picture: about the pixel count of a PS2 frame, upright
SS = 2                       # geometry is drawn at twice that and averaged (soft edges, as on the console's video output)
OUT_SIZE = (1080, 1920)

# ------------------------------------------------------------------ the script (seconds)
from script4 import LINES, PHRASES, SHOTS, T_END          # lines split into phrases, shots cut on the words
DOOR_OPEN = (0.50, 0.88)          # the door swings open between these times
DOOR_ANGLE = 104.0
SPRINT_T0, SPRINT_OFF = 0.62, 0.583   # Pico's run starts at SPRINT_T0, from SPRINT_OFF seconds into the clip (its last strides + the stop)
PICO_FACE = math.radians(-60.0)       # where she faces once stopped: three-quarters towards Nox, open to the camera
NOX_FACE = math.radians(10.0)

# what their faces do: (time, expression) keys, eased from one to the next; names are in facemorph.EXPR, a dict gives raw
# shape-key values.  The mouth shapes of speech and the blinks are added on top.
FACE = {
    'pico': [(0.0, {'browUp': 0.5, 'eyeWide': 0.5}), (2.0, {'browUp': 0.5, 'eyeWide': 0.5}), (2.5, {'browUp': 0.8, 'eyeWide': 0.7}),
             (3.2, {'browSad': 0.5, 'browUp': 0.3, 'eyeWide': 0.3}), (4.3, {'browUp': 0.6, 'eyeWide': 0.75}), (5.6, {'browSad': 0.6, 'eyeWide': 0.3}),
             (7.0, {'browSad': 0.4}), (8.2, {'browDown': 0.25}), (11.5, {'browDown': 0.3}), (13.0, {'browDown': 0.55, 'frown': 0.45}),
             (16.2, {'browDown': 0.6, 'frown': 0.5}), (16.5, {'browDown': 0.75, 'eyeSquint': 0.3, 'frown': 0.3}),
             (18.1, {'browDown_R': 0.6, 'browUp_L': 0.7, 'frown': 0.2}), (19.2, {'browDown': 0.2}), (20.4, {'smile': 0.25}), (21.6, {'smile': 0.25})],
    'nox': [(0.0, {'eyeSquint': 0.3, 'browDown': 0.2}), (7.0, {'eyeSquint': 0.3, 'browDown': 0.2}), (7.4, {'eyeSquint': 0.45}),
            (8.7, {'eyeSquint': 0.45}), (9.0, {'eyeSquint': 0.3, 'browUp_L': 0.8, 'browDown_R': 0.3}), (9.6, {'eyeSquint': 0.3, 'browUp_L': 0.8, 'browDown_R': 0.3}),
            (10.1, {'eyeSquint': 0.45}), (11.3, {'eyeSquint': 0.4}), (11.8, 'doubt'), (13.6, 'doubt'),
            (14.3, {'browUp': 0.6, 'eyeWide': 0.4, 'smile_L': 0.5}), (16.0, {'browUp_L': 0.6, 'smile_L': 0.6, 'eyeSquint': 0.2}), (16.6, 'smug'),
            (18.9, 'smug'), (19.3, {'browUp': 0.35, 'smile': 0.45}), (21.6, {'browUp': 0.2, 'smile': 0.6})],
}
MOUTH = {'aa': {'jawOpen': 0.75}, 'E': {'jawOpen': 0.42, 'mouthWide': 0.6}, 'I': {'jawOpen': 0.24, 'mouthWide': 0.8, 'lipsUp': 0.3},
         'O': {'jawOpen': 0.5, 'mouthNarrow': 0.8}, 'U': {'jawOpen': 0.28, 'mouthNarrow': 1.0}, 'PP': {}, 'sil': {}}
MOUTH_OTHER = {'jawOpen': 0.2}


def pw(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            x = (t - t0) / max(t1 - t0, 1e-6)
            x = x * x * (3 - 2 * x)
            return v0 + (v1 - v0) * x
    return keys[-1][1]


def shot_at(t):
    for a, b, name in SHOTS:
        if a <= t < b:
            return name
    return SHOTS[-1][2]


def shot_range(name):
    return next((a, b) for a, b, n in SHOTS if n == name)


# ------------------------------------------------------------------ lights (see ps2shade.shade)
# Night in the workshop: a dim, cool room and one warm key light from the front left that casts real shadows
# (shadow map, see ps2render.shadow_setup).  Faces stay bright against a darker set, as in a game cutscene.
KEY = dict(type='point', pos=(-1.45, -0.75, 2.45), color=(1.75, 1.48, 1.16), radius=3.4, wrap=0.12)
KEY_TARGET = (-0.05, 1.45, 0.95)
KEY_FOV = 104.0
KEY_ON_SET = 0.5          # the set receives only part of the key light: characters are lit apart from the decor, as on the console


def lights():
    return [
        dict(type='hemi', sky=(0.19, 0.23, 0.36), ground=(0.12, 0.115, 0.15)),
        dict(type='dir', dir=(0.25, -1.0, 0.35), color=(0.09, 0.10, 0.14), wrap=0.5),                     # faint fill from the camera side
        dict(type='dir', dir=(0.15, 1.0, 0.55), color=(0.16, 0.24, 0.46), wrap=0.0),                      # moonlight from the window
        dict(type='point', pos=(-0.16, -0.60, 2.40), color=(0.55, 0.46, 0.35), radius=2.8, wrap=0.3),    # the hanging lamp (decor3)
        dict(type='point', pos=(1.80, 2.46, 1.97), color=(1.1, 0.82, 0.52), radius=0.5, wrap=0.6, ymin=2.0),  # wall lamp in the corridor
        dict(type='point', pos=(-1.12, 1.02, 1.22), color=(0.20, 0.80, 0.42), radius=0.5, wrap=0.4),     # glow of the oscilloscope
        dict(type='point', pos=(1.0, 2.62, 2.35), color=(1.5, 1.1, 0.74), radius=1.3, wrap=0.5, ymin=2.0),  # the lamp of the corridor
    ]


DOOR_LIGHT = dict(type='point', pos=(1.0, 1.75, 1.55), color=(1.7, 1.1, 0.58), radius=1.25, wrap=0.35)
RIM = dict(type='rim', color=(0.30, 0.40, 0.66), power=2.6, dir=(0.2, 1.0, 0.5))
FINISH = dict(exposure=1.0, glow=0.38, soft=0.40, dither_bits=6, saturation=1.05, contrast=1.04)


# ------------------------------------------------------------------ build
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable('cycles', default_set=True)
    import atelier2 as AT
    import cast2
    import anim2
    A = AT.build()
    import decor3
    decor3.dress(A)
    import chore4
    pico = cast2.Actor(CAST['pico']['name'], CAST['pico']['rig'], [CAST['pico']['clips_from'] + ':' + k for k in chore4.PICO_CLIPS],
                       scale=CAST['pico']['scale'])
    nox = cast2.Actor(CAST['nox']['name'], CAST['nox']['rig'], [CAST['nox']['clips_from'] + ':' + k for k in chore4.NOX_CLIPS],
                      scale=CAST['nox']['scale'], glasses=True)
    W = dict(A=A, AT=AT, pico=pico, nox=nox, hinge=A['door_hinge'])
    W['perf'] = chore4.performers(W, sys.modules[__name__])
    bip = A['objs']['bip'][0]
    W['bip'], W['bip0'] = bip, bip.location.copy()
    W['dynamic'] = [pico.mesh, nox.mesh] + list(A['door_meshes']) + list(A['objs']['bip'][1])
    W['mouth'] = {}
    return W


# ------------------------------------------------------------------ mouth and eyes
VOW = {'aa': 'mouth_open', 'E': 'mouth_wide', 'I': 'mouth_wide', 'O': 'mouth_half', 'U': 'mouth_half'}


def mouth_track(text, t0, dur):
    """[(start, end, viseme), ...] for a line, spread over its duration."""
    import speech_fr as SP
    seq = SP.french_visemes(text)
    tot = sum(d for _, d in seq) or 1.0
    k = dur / tot
    out, t = [], t0
    for v, d in seq:
        if v != 'sil':
            out.append((t, t + d * k, v))
        t += d * k
    return out


def viseme_at(track, t):
    for a, b, v in track:
        if a <= t < b:
            return v
    return 'sil'


BLINK_EXTRA = {'pico': [], 'nox': []}         # filled by chore4: blinks that go with big gaze shifts


def blink_times(name):
    rng = np.random.default_rng(7 if name == 'nox' else 3)
    out, tt = [], 0.8 + rng.random() * 1.5
    while tt < 30:
        out.append(tt)
        tt += 2.6 + rng.random() * 1.8
    extra = BLINK_EXTRA.get(name, [])
    out = [x for x in out if all(abs(x - e) > 0.9 for e in extra)] + list(extra)
    return sorted(out)


def blink_at(name, t, close=0.075, hold=0.03, opening=0.17):
    """0..1: how closed the eyes are: a fast close, a short hold, a slower opening."""
    import acting as AC
    for tb in blink_times(name):
        if tb <= t < tb + close + hold + opening:
            return AC.bump(t, tb, close, hold, opening)
    return 0.0


def _expr_values(e):
    import facemorph
    return facemorph.expand(facemorph.EXPR[e] if isinstance(e, str) else e)


def face_at(W, who, t):
    """All shape-key values of one face at time t: expression track + speech + blink."""
    keys = FACE[who]
    vals = {}
    if t <= keys[0][0]:
        vals = dict(_expr_values(keys[0][1]))
    else:
        for (t0, e0), (t1, e1) in zip(keys, keys[1:]):
            if t <= t1:
                x = (t - t0) / max(t1 - t0, 1e-6)
                x = x * x * (3 - 2 * x)
                a, b = _expr_values(e0), _expr_values(e1)
                vals = {k: a.get(k, 0.0) * (1 - x) + b.get(k, 0.0) * x for k in set(a) | set(b)}
                break
        else:
            vals = dict(_expr_values(keys[-1][1]))
    # speech: the mouth shape is averaged over a short window so that it glides from one sound to the next
    mouth = {}
    for dt, wgt in ((-0.05, 0.25), (0.0, 0.5), (0.05, 0.25)):
        for lid, w_, t0, dur, text in LINES:
            if w_ == who and t0 <= t + dt < t0 + dur:
                if lid not in W['mouth']:
                    W['mouth'][lid] = mouth_track(text, t0, dur)
                v = viseme_at(W['mouth'][lid], t + dt)
                for k, x in MOUTH.get(v, MOUTH_OTHER).items():
                    mouth[k] = mouth.get(k, 0.0) + wgt * x
    for k, x in mouth.items():
        vals[k] = min(1.0, vals.get(k, 0.0) + x)
    if mouth.get('jawOpen', 0) > 0.05:                                     # a talking mouth is not held in a pout
        for k in ('frown_L', 'frown_R'):
            vals[k] = vals.get(k, 0.0) * 0.5
    b = blink_at(who, t)
    if b > 0:
        for k in ('eyeClosed_L', 'eyeClosed_R'):
            vals[k] = max(vals.get(k, 0.0), b)
        for k in ('eyeWide_L', 'eyeWide_R'):
            vals[k] = vals.get(k, 0.0) * (1 - b)
    return vals


# ------------------------------------------------------------------ one instant
def _lerp_angle(a, b, w):
    d = (b - a + math.pi) % (2 * math.pi) - math.pi
    return a + d * w


def door_k(t):
    k = min(max((t - DOOR_OPEN[0]) / (DOOR_OPEN[1] - DOOR_OPEN[0]), 0), 1)
    k = 1 - (1 - k) ** 3                                                # flung open, then it settles
    bounce = 0.035 * math.exp(-(t - DOOR_OPEN[1]) * 5.0) * math.sin((t - DOOR_OPEN[1]) * 14.0) if t > DOOR_OPEN[1] else 0.0
    return k - bounce


def pose_at(W, t):
    import ps2render as PR
    pico, nox = W['pico'], W['nox']
    W['hinge'].rotation_euler = (0, 0, math.radians(DOOR_ANGLE * door_k(t)))
    PR.hide_dynamic(pico.mesh, t < SPRINT_T0)
    W['perf']['pico'].pose(max(t, SPRINT_T0))
    W['perf']['nox'].pose(t)
    # ---- faces: expressions, speech and blinks drive the shape keys (older models without them swap textures)
    for a, who in ((pico, 'pico'), (nox, 'nox')):
        if a.face is not None:
            vals = W['face'][who].values(t)
            vals.update(W['perf'][who].eyes(t))
            a.express(vals)
            continue
        key = 'closed'
        for lid, w_, t0, dur, text in LINES:
            if w_ == who and t0 <= t < t0 + dur:
                if lid not in W['mouth']:
                    W['mouth'][lid] = mouth_track(text, t0, dur)
                key = VOW.get(viseme_at(W['mouth'][lid], t), 'closed' if viseme_at(W['mouth'][lid], t) in ('PP', 'sil') else 'mouth_half')
        if key == 'closed' and blink_at(who, t) > 0.5:
            key = 'blink'
        a.set_face(key)
    # ---- Bip hovers; it starts when the door bangs, looks at Pico, then goes back to watching Nox work
    look = pw([(0.0, 0.0), (0.55, 0.0), (0.95, 1.0), (3.4, 1.0), (4.6, 0.0), (21.6, 0.0)], t)
    jump = 0.06 * math.exp(-max(t - 0.55, 0) * 4.0) * (1 if t > 0.55 else 0)
    W['bip'].location = W['bip0'] + Vector((0, 0, 0.022 * math.sin(t * 2.1) + jump))
    W['bip'].rotation_euler = (0, 0, math.radians(-25 + 75 * look) + 0.10 * math.sin(t * 0.9))
    bpy.context.view_layer.update()


def frame_meta(W, t):
    pico, nox = W['pico'], W['nox']
    blobs = []
    for a in (pico, nox):
        if a is pico and t < SPRINT_T0:
            continue
        feet = [a.joint('LeftFoot'), a.joint('RightFoot')]
        for f in feet:
            lift = max(0.0, f.z - 0.16 * a.scale)                           # a lifted foot casts a fainter, wider shadow
            blobs.append((f.x, f.y - 0.03, 0.0, 0.12 + lift * 0.5, 0.22 * max(0.25, 1 - lift * 4)))
        c = (feet[0] + feet[1]) / 2
        blobs.append((c.x, c.y, 0.0, 0.30, 0.12))
    return dict(blobs=blobs, door=max(0.0, min(1.0, door_k(t))))


# ------------------------------------------------------------------ cameras: one fixed camera per shot
def camera_setup(W, cam, name):
    import ps2render as PR
    if name == 'wide':
        PR.aim(cam, (-0.16, -4.05, 1.62), (-0.16, 1.5, 1.36), 38)
    elif name == 'two':
        PR.aim(cam, (-0.18, -3.75, 1.50), (-0.15, 1.5, 1.30), 37)
    elif name == 'medN':
        PR.aim(cam, (0.18, -1.30, 1.50), (-0.76, 1.42, 1.24), 28)
    else:
        # the face shots keep the framing they had in version 3 (fixed numbers: the set behind them is rendered once)
        FIXED = {'medP': ((-1.15, -0.8, 1.46), (-0.56431, 0.00995, 1.42918), 28.0), 'closeN': ((0.74, 0.02, 1.44377), (0.05045, 0.7442, 1.4513), 22.0), 'closeP': ((-1.0, -0.28, 1.40458), (-0.35055, 0.48032, 1.41578), 22.0)}
        pos, tgt, vfov = FIXED[name]
        PR.aim(cam, pos, tgt, vfov)
    return PR.cam_info(cam)


# ------------------------------------------------------------------ rendering
class Renderer:
    def __init__(self, W, out, ao=64):
        import ps2render as PR
        import ps2shade as SH
        self.W, self.out, self.ao, self.PR, self.SH = W, out, ao, PR, SH
        os.makedirs(out + '/static', exist_ok=True)
        os.makedirs(out + '/px', exist_ok=True)
        os.makedirs(out + '/tmp', exist_ok=True)
        PR.setup(RES[0], RES[1], ss=SS)
        PR.split(W['dynamic'])
        self.cam = PR.camera()
        self.cur = None
        self.tmp = f'{out}/tmp/d{os.getpid()}.exr'
        self.tmp_sh = f'{out}/tmp/s{os.getpid()}.exr'
        # the key light's shadow map of the set: the same for every shot
        self.sh = PR.shadow_setup(KEY['pos'], KEY_TARGET, KEY_FOV, 1024)
        bpy.context.scene.camera = self.cam
        self.sh_static = f'{out}/static/shadow_static.exr'
        self.smap_static = None

    def static_shadow(self):
        if self.smap_static is None:
            if not os.path.exists(self.sh_static):
                pose_at(self.W, 0.0)
                self.PR.render_shadow(self.sh_static, 'static')
            self.smap_static = self.SH.shadow_map(self.sh_static, self.sh)
        return self.smap_static

    def static_paths(self, shot):
        return f'{self.out}/static/{shot}.exr', f'{self.out}/static/{shot}_ao.exr', f'{self.out}/static/{shot}.json'

    def make_static(self, shot):
        exr, ao, js = self.static_paths(shot)
        info = camera_setup(self.W, self.cam, shot)
        self.PR.render_static(exr, ao_samples=self.ao)
        json.dump(info, open(js, 'w'))

    def use_shot(self, shot):
        if self.cur == shot:
            return
        exr, ao, js = self.static_paths(shot)
        if not (os.path.exists(exr) and os.path.exists(js)):
            self.make_static(shot)
        else:
            camera_setup(self.W, self.cam, shot)
        SH = self.SH
        self.cam_info = json.load(open(js))
        S = SH.load(exr, ao if os.path.exists(ao) else None)
        self.S = S
        self.S_base = SH.shade(S, lights(), self.cam_info, ao_strength=0.9)
        bare = dict(S, emit=np.zeros_like(S['emit']))
        f_ss = SH.shadow(S, self.static_shadow(), self.sh, bias=0.035, soft=3.0)          # the set shadowing itself
        self.S_key = SH.shade(bare, [dict(KEY, factor=f_ss)], self.cam_info, ao_strength=0.35) * KEY_ON_SET
        self.S_door = SH.shade(dict(bare, ao=None), [DOOR_LIGHT], self.cam_info)
        self.cur = shot

    def frame(self, t, path, shot=None):
        SH = self.SH
        shot = shot or shot_at(t)
        self.use_shot(shot)
        pose_at(self.W, t)
        meta = frame_meta(self.W, t)
        self.PR.render_shadow(self.tmp_sh, 'dynamic')                                   # the characters seen from the key light
        smap_dyn = SH.shadow_map(self.tmp_sh, self.sh)
        self.PR.render_dynamic(self.tmp)
        D = SH.load(self.tmp)
        f_dyn = SH.shadow(self.S, smap_dyn, self.sh, bias=0.04, soft=3.5)                # their shadows on the set
        s_rgb = self.S_base + self.S_key * f_dyn[..., None] + meta['door'] * self.S_door
        s_rgb = s_rgb * SH.blob_shadows(self.S, meta['blobs'])[..., None]
        f_set = SH.shadow(D, self.static_shadow(), self.sh, bias=0.05, soft=2.5)        # the set's shadows on them (no self-shadowing)
        L = lights() + [dict(KEY, factor=f_set), dict(DOOR_LIGHT, color=tuple(c * meta['door'] for c in DOOR_LIGHT['color'])), RIM]
        d_rgb = SH.shade(D, L, self.cam_info)
        rgb, _ = SH.merge(s_rgb, self.S, d_rgb, D)
        im = SH.finish(rgb, ss=SS, out_size=OUT_SIZE, **FINISH)
        im.save(path)
        return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('out')
    ap.add_argument('--frames', default=None)
    ap.add_argument('--times', default=None)
    ap.add_argument('--shots', default=None)
    ap.add_argument('--ao', type=int, default=64)
    ap.add_argument('--res', default=None, help='internal resolution WxH (previews), default 432x768')
    ap.add_argument('--ss', type=int, default=None, help='supersampling (previews), default 2')
    ap.add_argument('--step', type=int, default=1, help='render every n-th frame (previews)')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    global RES, SS
    if a.res:
        RES = tuple(int(x) for x in a.res.split('x'))
    if a.ss:
        SS = a.ss
    global OUT_SIZE
    if a.res:
        OUT_SIZE = None                                               # previews stay at their internal size
    W = build()
    R = Renderer(W, a.out, ao=a.ao)
    t_start = time.time()
    if a.cmd == 'statics':
        R.static_shadow()                                                 # the key light's shadow map of the set
        for name in (a.shots.split(',') if a.shots else [s[2] for s in SHOTS]):
            R.make_static(name)
            print(f'static {name} {time.time() - t_start:.0f} s', flush=True)
    elif a.cmd == 'stills':
        for x in a.times.split(','):
            shot = None
            if ':' in x:
                x, shot = x.split(':')
            t = float(x)
            R.frame(t, f'{a.out}/px/t{t:06.2f}{"_" + shot if shot else ""}.png', shot)
            print(f'still {t} {shot or shot_at(t)} {time.time() - t_start:.0f} s', flush=True)
    elif a.cmd == 'frames':
        n = int(round(T_END * FPS))
        f0, f1 = (0, n - 1) if not a.frames else (int(x) for x in a.frames.split(':'))
        for f in range(f0, f1 + 1, a.step):
            R.frame(f / FPS, f'{a.out}/px/f{f:05d}.png')
            if f % 10 == 0:
                print(f'frame {f} {shot_at(f / FPS)} {time.time() - t_start:.0f} s', flush=True)
    elif a.cmd == 'motion':
        rows = []
        for f in range(int(round(T_END * FPS))):
            t = f / FPS
            pose_at(W, t)
            row = dict(t=t)
            for nm in ('pico', 'nox'):
                A_ = W[nm]
                for b in ('Hips', 'Head', 'LeftHand', 'RightHand', 'LeftFoot', 'RightFoot'):
                    row[f'{nm}.{b}'] = tuple(A_.joint(b))
            rows.append(row)
        json.dump(rows, open(a.out + '/motion.json', 'w'))
        print('motion rows', len(rows))


if __name__ == '__main__':
    main()
