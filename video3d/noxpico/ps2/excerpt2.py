"""Nox & Pico, episode 1 excerpt in 3D, PS2-cutscene look, 30 frames per second.

    python excerpt2.py statics OUT [--ao 64] [--shots wide,medP]   the set (+ ambient occlusion) from each shot's camera, once
    python excerpt2.py frames  OUT [--frames A:B]                  OUT/px/fNNNNN.png  (1080x1920, no captions)
    python excerpt2.py stills  OUT --times 1.2,4.0 [--ao 16]       quick stills, statics rendered on the fly
    python excerpt2.py motion  OUT                                 numbers about the motion (speeds, jumps) for every frame

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
RES = (432, 768)             # internal picture: about the pixel count of a PS2 frame, upright
SS = 2                       # geometry is drawn at twice that and averaged (soft edges, as on the console's video output)
OUT_SIZE = (1080, 1920)

# ------------------------------------------------------------------ the script (seconds)
LINES = [  # id, who, start, duration, text
    ('l01', 'pico', 2.40, 4.40, "Nox ! Pourquoi ma montre fait des lumières vertes à la fin de mon run ?"),
    ('l02', 'nox', 7.20, 3.85, "Bonsoir à toi aussi, Pico. Entre, fais comme chez toi."),
    ('l02b', 'nox', 11.55, 4.60, "Tu portes cette montre depuis deux ans… et tu découvres qu'elle s'allume ?"),
    ('l02c', 'pico', 16.45, 2.20, "J'ai jamais regardé dessous, ok ?"),
    ('l02d', 'nox', 19.15, 1.95, "Bon. Laisse-moi t'expliquer."),
]
T_END = 21.6
SHOTS = [(0.0, 3.05, 'wide'), (3.05, 7.05, 'medP'), (7.05, 11.45, 'medN'), (11.45, 16.30, 'closeN'), (16.30, 18.95, 'closeP'),
         (18.95, T_END, 'two')]
DOOR_OPEN = (0.50, 0.88)          # the door swings open between these times
DOOR_ANGLE = 104.0
SPRINT_T0, SPRINT_OFF = 0.62, 0.583   # Pico's run starts at SPRINT_T0, from SPRINT_OFF seconds into the clip (its last strides + the stop)
PICO_FACE = math.radians(-60.0)       # where she faces once stopped: three-quarters towards Nox, open to the camera
NOX_FACE = math.radians(10.0)
NOX_TWIST = [(0.0, 0.0), (10.95, 0.0), (11.75, 26.0), (21.6, 26.0)]    # he turns his chest to her once he stops working (degrees); his feet stay put

# clip tracks: (t_start, clip, offset_s, loop, crossfade_in_s)
PICO_SEGS = [(SPRINT_T0, 'sprintstop', SPRINT_OFF, False, 0.0), (2.02, 'talkleft', 0.0, False, 0.55),
             (7.10, 'listen', 0.0, False, 0.7), (15.50, 'hip', 0.0, False, 0.6, 0.85)]
# Pico changes pose while the camera is on Nox, so that she does not slide at the start of her close-up; the last clip
# plays a little slower (x0.85) and so lasts to the end of the excerpt
NOX_SEGS = [(0.0, 'idle', 0.0, True, 0.0), (11.40, 'talkright', 0.0, False, 0.6), (14.55, 'shrug', 0.0, False, 0.5),
            (16.40, 'listen', 0.0, False, 0.6), (18.40, 'talkopen', 0.0, False, 0.55)]   # changes while the camera is on Pico
# overlays: piecewise curves (time, value), eased
NOX_SOLDER = [(0.0, 1.0), (10.85, 1.0), (11.50, 0.0)]                  # hands on the bench, leaning over his work
NOX_LOOK_PICO = [(0.0, 0.0), (8.50, 0.0), (8.95, 0.6), (9.55, 0.6), (10.05, 0.0),      # a glance over his glasses on "Pico. Entre"
                 (10.95, 0.0), (11.55, 0.85), (16.3, 0.85), (16.7, 0.6), (21.6, 0.6)]
PICO_LOOK_NOX = [(0.0, 0.0), (2.0, 0.0), (2.7, 0.6), (21.6, 0.6)]


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
def lights(door_k=0.0):
    base = [
        dict(type='hemi', sky=(0.50, 0.53, 0.66), ground=(0.33, 0.30, 0.31)),
        dict(type='point', pos=(-0.25, 0.85, 2.55), color=(1.45, 1.24, 0.98), radius=2.6, wrap=0.3),       # ceiling lamp, warm
        dict(type='dir', dir=(0.2, -1.0, 0.45), color=(0.32, 0.33, 0.38), wrap=0.5),                      # soft fill from the camera side
        dict(type='dir', dir=(0.15, 1.0, 0.55), color=(0.14, 0.20, 0.38), wrap=0.0),                      # moonlight from the window
        dict(type='point', pos=(-1.12, 1.02, 1.22), color=(0.16, 0.62, 0.34), radius=0.45, wrap=0.4),     # glow of the oscilloscope
        dict(type='point', pos=(1.0, 2.62, 2.35), color=(2.3, 1.75, 1.2), radius=1.3, wrap=0.5, ymin=2.0),  # the lamp of the corridor
    ]
    return base


DOOR_LIGHT = dict(type='point', pos=(1.0, 1.75, 1.55), color=(1.5, 0.98, 0.52), radius=1.15, wrap=0.35)
RIM = dict(type='rim', color=(0.26, 0.34, 0.56), power=3.0, dir=(0.2, 1.0, 0.5))
FINISH = dict(exposure=1.0, glow=0.30, soft=0.40, dither_bits=6, saturation=1.06, contrast=1.03)


# ------------------------------------------------------------------ build
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable('cycles', default_set=True)
    import atelier2 as AT
    import cast2
    import anim2
    A = AT.build()
    pico = cast2.Actor('pico', 'pico_rigged', ('sprintstop', 'talkleft', 'talk', 'listen', 'hip', 'idle'), scale=1.07)
    nox = cast2.Actor('nox2', 'nox2_rigged', ('idle', 'talkright', 'shrug', 'listen', 'agree', 'talkopen'), scale=1.0, glasses=True)
    W = dict(A=A, AT=AT, pico=pico, nox=nox, hinge=A['door_hinge'])
    W['pico_track'] = anim2.Track(pico.clips, PICO_SEGS)
    W['nox_track'] = anim2.Track(nox.clips, NOX_SEGS)
    mark_p, mark_n = A['marks']['pico'], A['marks']['nox']
    assert all(c.bones == pico.clips['talk'].bones for c in pico.clips.values()) and all(c.bones == nox.clips['idle'].bones for c in nox.clips.values())
    # every clip is re-based so that the feet stand on the actor's origin: the actor then simply stays on its mark
    tp, tn = W['pico_track'], W['nox_track']
    c = pico.clips['sprintstop']
    pico.pose(c.sample(SPRINT_OFF), c.bones)
    a0 = pico.feet_local()
    pico.pose(c.sample(c.dur), c.bones)
    a1 = pico.feet_local()
    travel = a1 - a0                                                      # in her own frame
    want = (Vector(mark_p) - Vector(A['marks']['door'])).normalized()
    run_heading = math.atan2(want.x, -want.y) - math.atan2(travel.x, -travel.y)
    W['run_len'] = travel.length
    W['pico_heading'] = [(0.0, run_heading), (1.85, run_heading), (2.75, PICO_FACE), (T_END, PICO_FACE)]
    tp.shifts[0] = pico.hips_shift(a1)                                    # the run ends on the mark
    for tr, actor, segs in ((tp, pico, PICO_SEGS), (tn, nox, NOX_SEGS)):
        for i, seg in enumerate(segs):
            t0, clip, off, loop = seg[:4]
            speed = seg[5] if len(seg) > 5 else 1.0
            if tr is tp and i == 0:
                continue
            t1 = segs[i + 1][0] if i + 1 < len(segs) else T_END
            tr.shifts[i] = actor.hips_shift(actor.anchor(clip, off, min(off + (t1 - t0) * speed, actor.clips[clip].dur), loop=loop))
    # Nox's hands on the bench: as far over his work as his arms reach at every moment of his idle sway
    top = A['bench_top']
    nox.place(mark_n, NOX_FACE)
    W['hand_t'], W['pole_t'] = {}, {}
    samples = []
    for i in range(12):
        nox.pose(tn.seg_pose(0, i * 0.3))
        bpy.context.view_layer.update()
        _lean(nox, 1.0)
        samples.append({s_: (nox.joint(f'{s_}Arm').copy(), (nox.joint(f'{s_}Arm') - nox.joint(f'{s_}ForeArm')).length + (nox.joint(f'{s_}ForeArm') - nox.joint(f'{s_}Hand')).length) for s_ in ('Left', 'Right')})
    for s_, sx in (('Left', 1), ('Right', -1)):
        sh = sum((smp[s_][0] for smp in samples), Vector((0, 0, 0))) / len(samples)
        reach = min(smp[s_][1] for smp in samples)
        tgt = Vector((sh.x + sx * 0.03, mark_n[1] - 0.40, top + 0.06))
        for _ in range(60):                                               # pull the target back until it is always within reach
            if max((tgt - smp[s_][0]).length for smp in samples) <= 0.94 * reach:
                break
            tgt.y += 0.006
        W['hand_t'][s_] = tgt
        W['pole_t'][s_] = Vector((mark_n[0] + sx * 0.75, mark_n[1] + 0.3, 0.95))
    W['bench_look'] = Vector((mark_n[0] + 0.03, W['hand_t']['Left'].y - 0.06, top))
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


def blink_times(name):
    rng = np.random.default_rng(7 if name == 'nox' else 3)
    out, tt = [], 0.8 + rng.random() * 1.5
    while tt < 30:
        out.append(tt)
        tt += 2.6 + rng.random() * 1.8
    return out


def blink_at(name, t, dur=0.16):
    """0..1: how closed the eyes are (a quick close, a slightly slower opening)."""
    for tb in blink_times(name):
        if tb <= t < tb + dur:
            x = (t - tb) / dur
            return min(x / 0.35, (1 - x) / 0.65, 1.0) if x < 0.35 else max(0.0, (1 - x) / 0.65)
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


def _lean(nox, k):
    """Nox bends over his bench (k = 0..1)."""
    import procpose as PP
    axis = Vector((math.cos(nox.heading), math.sin(nox.heading), 0.0))
    PP.rotate_bone_world(nox.arm, 'Spine01', Quaternion(axis, math.radians(12 * k)))
    PP.rotate_bone_world(nox.arm, 'Spine', Quaternion(axis, math.radians(9 * k)))


def pose_at(W, t):
    import procpose as PP
    import rigext
    import ps2render as PR
    pico, nox = W['pico'], W['nox']
    marks = W['A']['marks']
    W['hinge'].rotation_euler = (0, 0, math.radians(DOOR_ANGLE * door_k(t)))
    # ---- Pico: on her mark, the clips bring her there
    PR.hide_dynamic(pico.mesh, t < SPRINT_T0)
    pose, k, w = W['pico_track'].pose(max(t, SPRINT_T0))
    pico.pose(pose)
    pico.place(marks['pico'], pw(W['pico_heading'], t))
    # ---- Nox: behind his bench
    pose, k, w = W['nox_track'].pose(t)
    solder = pw(NOX_SOLDER, t)
    if solder > 0:
        # while he works he stays over his bench: the idle clip (which turns round to look about now and then) is
        # reduced to a faint sway around one calm pose, and his head follows his hands
        import anim2
        pose = anim2.blend(pose, W['nox_track'].seg_pose(0, 0.2), 0.85 * solder)
        loc, quat = pose
        quat = quat.copy()
        bones = W['nox_track'].clips['idle'].bones
        a = 0.9 * solder
        for b in ('Head', 'neck'):
            i = bones.index(b)
            q = quat[i] * (1 - a) + np.array([1.0 if quat[i][0] >= 0 else -1.0, 0.0, 0.0, 0.0]) * a
            quat[i] = q / np.linalg.norm(q)
        pose = (loc, quat)
    nox.pose(pose)
    nox.place(marks['nox'], NOX_FACE)
    bpy.context.view_layer.update()
    twist = math.radians(pw(NOX_TWIST, t))
    if twist:
        up = Vector((0, 0, 1))
        PP.rotate_bone_world(nox.arm, 'Spine02', Quaternion(up, twist * 0.5))
        PP.rotate_bone_world(nox.arm, 'Spine01', Quaternion(up, twist * 0.5))
    if solder > 0:
        _lean(nox, solder)
        for s_, sx in (('Left', 1), ('Right', -1)):
            jig = Vector((0.006 * math.sin(t * (5.3 if sx > 0 else 4.1)), 0.004 * math.sin(t * 3.1 + sx), 0.004 * (0.5 + 0.5 * math.sin(t * 4.6 + sx))))
            PP.two_bone_ik(nox.arm, f'{s_}Arm', f'{s_}ForeArm', f'{s_}Hand', W['hand_t'][s_] + jig, W['pole_t'][s_], solder)
    # ---- where they look
    p_head, n_head = pico.face_point(), nox.face_point()
    for actor, tgt, wgt in ((nox, W['bench_look'], 0.6 * solder), (nox, p_head, pw(NOX_LOOK_PICO, t)), (pico, n_head, pw(PICO_LOOK_NOX, t))):
        if wgt > 0:
            PP.look_at(actor.arm, 'Head', actor.face_fwd, tgt, wgt, 50)
            PP.look_at(actor.arm, 'neck', actor.face_fwd_neck, tgt, 0.35 * wgt, 22)
    for a in (pico, nox):
        for s in ('L', 'R'):
            rigext.hand_pose(a.arm, s, curl=0.35, thumb=0.25)
    # ---- faces: expressions, speech and blinks drive the shape keys (older models without them swap textures)
    for a, who in ((pico, 'pico'), (nox, 'nox')):
        if a.face is not None:
            a.express(face_at(W, who, t))
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
            blobs.append((f.x, f.y - 0.03, 0.0, 0.13 + lift * 0.5, 0.42 * max(0.25, 1 - lift * 4)))
        c = (feet[0] + feet[1]) / 2
        blobs.append((c.x, c.y, 0.0, 0.33, 0.30))
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
    else:                                                                # shots on one face: framed on the average head position
        actor = W['nox'] if name == 'closeN' else W['pico']
        t0, t1 = shot_range(name)
        face, n, ts = Vector((0, 0, 0)), 0, t0 + 0.3
        while ts < t1 - 0.05:
            pose_at(W, ts)
            face += actor.face_point()
            n += 1
            ts += 0.25
        face /= n
        # shot / reverse shot: Nox is filmed from Pico's side and Pico from Nox's side, so both show their face
        if name == 'closeN':
            PR.aim(cam, (0.74, 0.02, face.z + 0.03), face + Vector((0, 0, 0.045)), 22)
        elif name == 'closeP':
            PR.aim(cam, (-1.00, -0.28, face.z + 0.02), face + Vector((0, 0, 0.045)), 22)
        else:                                                            # medP: same side as her close-up, from further back
            PR.aim(cam, (-1.15, -0.80, 1.46), face + Vector((0.06, 0, 0.02)), 28)       # her eyes stay under the caption box
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
        unit = dict(DOOR_LIGHT)
        self.S_door = S['albedo'] * SH.shade(dict(S, albedo=np.ones_like(S['albedo']), emit=np.zeros_like(S['emit']), ao=None), [unit], self.cam_info)
        self.cur = shot

    def frame(self, t, path, shot=None):
        SH = self.SH
        shot = shot or shot_at(t)
        self.use_shot(shot)
        pose_at(self.W, t)
        meta = frame_meta(self.W, t)
        self.PR.render_dynamic(self.tmp)
        D = SH.load(self.tmp)
        s_rgb = self.S_base + meta['door'] * self.S_door
        s_rgb = s_rgb * SH.blob_shadows(self.S, meta['blobs'])[..., None]
        L = lights() + [dict(DOOR_LIGHT, color=tuple(c * meta['door'] for c in DOOR_LIGHT['color'])), RIM]
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
