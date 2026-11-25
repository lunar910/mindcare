"""Nox & Pico, episode 1 excerpt (Pico bursts in .. "Bon. Laisse-moi t'expliquer.") in 3D, pixel-art cel look.

    python excerpt.py OUTDIR [--fps 12] [--times 0.3,1.2,...] [--frames A:B] [--samples 24]
Writes OUTDIR/exr/fNNNN.exr; pxpost.py turns them into pixel frames."""
import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import addon_utils
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable('cycles', default_set=True)
import atelier as AT
import pxrender as PX
import rigext
import procpose as PP

S = '/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad'
RIG = S + '/meshy/models/rig'
ANIM = S + '/meshy/models/anim'
VAR = os.path.dirname(os.path.abspath(__file__)) + '/out_face/var'
FPS_SRC = 24

# ------------------------------------------------------------------ the script (seconds)
LINES = [  # id, who, start, duration, text
    ('l01', 'pico', 2.40, 4.40, "Nox ! Pourquoi ma montre fait des lumières vertes à la fin de mon run ?"),
    ('l02', 'nox', 7.20, 3.85, "Bonsoir à toi aussi, Pico. Entre, fais comme chez toi."),
    ('l02b', 'nox', 11.55, 4.60, "Tu portes cette montre depuis deux ans… et tu découvres qu'elle s'allume ?"),
    ('l02c', 'pico', 16.45, 2.20, "J'ai jamais regardé dessous, ok ?"),
    ('l02d', 'nox', 19.15, 1.95, "Bon. Laisse-moi t'expliquer."),
]
T_END = 21.6
SHOTS = [(0.0, 11.38, 'wide'), (11.38, 16.32, 'closeN'), (16.32, 18.95, 'closeP'), (18.95, T_END, 'wide')]
DOOR_OPEN = (0.55, 0.85)          # door swings open between these times
SPRINT = (0.62, 14, 48)           # starts at t, uses source frames 14..48 (the end of the sprint and the stop)
STOP = (0.22, 0.62)               # where Pico's hips stop (x, y)
NOX_MARK = (-0.72, 1.44)

# each actor: list of (t_start, action, src_frame_start, speed, loop) ; crossfade XF seconds between consecutive clips
XF = 0.35
PICO_CLIPS = [(SPRINT[0], 'sprintstop', SPRINT[1], 1.0, False), (2.00, 'breath', 100, 1.0, False), (3.10, 'talk', 0, 1.0, True),
              (7.10, 'listen', 0, 1.0, True), (16.30, 'hip', 0, 1.0, False), (18.95, 'listen', 30, 1.0, True)]
NOX_CLIPS = [(0.0, 'idle', 0, 1.0, True), (11.45, 'talkright', 0, 1.0, True), (14.55, 'shrug', 0, 1.0, False), (16.40, 'listen', 0, 1.0, True),
             (19.05, 'talkopen', 0, 1.0, True)]
# head / hands overlays (start, end, value) piecewise-linear
NOX_SOLDER = [(0.0, 1.0), (11.2, 1.0), (11.9, 0.0)]                  # hands on the bench + head down
NOX_LOOK_PICO = [(0.0, 0.0), (11.3, 0.0), (11.9, 0.85), (16.3, 0.85), (16.6, 0.5), (21.6, 0.5)]
PICO_LOOK_NOX = [(0.0, 0.0), (2.2, 0.0), (2.8, 0.55), (21.6, 0.55)]
PICO_TURN = [(0.0, -42.0), (2.1, -42.0), (2.9, -58.0), (21.6, -58.0)]  # yaw (deg)
NOX_TURN = [(0.0, 16.0), (21.6, 16.0)]


def pw(keys, t):
    """Piecewise-linear interpolation of [(t, v), ...] with smoothstep easing inside each segment."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            x = (t - t0) / max(t1 - t0, 1e-6)
            x = x * x * (3 - 2 * x)
            return v0 + (v1 - v0) * x
    return keys[-1][1]


# ------------------------------------------------------------------ actions
def channelbag(act):
    from bpy_extras import anim_utils
    return anim_utils.action_get_channelbag_for_slot(act, act.slots[0])


def load_action(path, name):
    before_obs, before_acts = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new_acts = [a for a in bpy.data.actions if a not in before_acts]
    act = new_acts[0]
    act.name = name
    act.use_fake_user = True
    for o in [o for o in bpy.data.objects if o not in before_obs]:
        bpy.data.objects.remove(o, do_unlink=True)
    cb = channelbag(act)
    curves = {}
    for fc in cb.fcurves:
        m = re.match(r'pose\.bones\["(.+)"\]\.(location|rotation_quaternion|scale)', fc.data_path)
        if m:
            curves.setdefault(m.group(1), {}).setdefault(m.group(2), {})[fc.array_index] = fc
    f0, f1 = act.frame_range
    return dict(name=name, curves=curves, f0=f0, f1=f1)


def eval_action(A, frame):
    out = {}
    for bone, ch in A['curves'].items():
        loc = Vector([ch['location'][i].evaluate(frame) if 'location' in ch and i in ch['location'] else 0.0 for i in range(3)])
        q = Quaternion([ch['rotation_quaternion'][i].evaluate(frame) if 'rotation_quaternion' in ch and i in ch['rotation_quaternion'] else (1.0 if i == 0 else 0.0) for i in range(4)])
        q.normalize()
        out[bone] = (loc, q)
    return out


def blend(pa, pb, w):
    if w <= 0:
        return pa
    if w >= 1:
        return pb
    out = {}
    for bone in set(pa) | set(pb):
        if bone not in pa:
            out[bone] = pb[bone]
            continue
        if bone not in pb:
            out[bone] = pa[bone]
            continue
        (la, qa), (lb, qb) = pa[bone], pb[bone]
        out[bone] = (la.lerp(lb, w), qa.slerp(qb, w))
    return out


def clip_pose(actions, clips, t):
    """Pose of an actor at time t from its clip list (with crossfades)."""
    def at(k, tt):
        t0, name, fs, speed, loop = clips[k]
        A = actions[name]
        fr = fs + (tt - t0) * FPS_SRC * speed
        if loop:
            span = A['f1'] - A['f0']
            fr = A['f0'] + ((fr - A['f0']) % span)
        else:
            fr = min(fr, A['f1'])
        return eval_action(A, max(fr, A['f0']))
    k = 0
    for i, c in enumerate(clips):
        if t >= c[0]:
            k = i
    pose = at(k, t)
    if k + 1 < len(clips) and t > clips[k + 1][0] - XF and t < clips[k + 1][0]:
        pass
    if k > 0 and t < clips[k][0] + XF:                                # fading in from the previous clip
        w = (t - clips[k][0]) / XF
        w = w * w * (3 - 2 * w)
        pose = blend(at(k - 1, t), pose, w)
    return pose, clips[k][1]


def apply_pose(arm, pose):
    for bone, (loc, q) in pose.items():
        pb = arm.pose.bones.get(bone)
        if pb is None:
            continue
        pb.rotation_mode = 'QUATERNION'
        pb.location = loc
        pb.rotation_quaternion = q


# ------------------------------------------------------------------ actors
class Actor:
    def __init__(self, name, glb, anims, height):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=glb)
        new = [o for o in bpy.data.objects if o not in before]
        self.arm = next(o for o in new if o.type == 'ARMATURE')
        self.mesh = next(o for o in new if o.type == 'MESH' and o.vertex_groups)
        for o in new:
            if o.type == 'MESH' and not o.vertex_groups:
                o.hide_render = True                                   # stray helper geometry
        if self.arm.animation_data:
            self.arm.animation_data.action = None
        for b in self.arm.pose.bones:
            b.location = (0, 0, 0)
            b.rotation_mode = 'QUATERNION'
            b.rotation_quaternion = (1, 0, 0, 0)
        bpy.context.view_layer.update()
        rigext.add_fingers(self.arm, self.mesh)
        PX.matte(self.mesh)
        self.root = bpy.data.objects.new(name + '_root', None)
        bpy.context.scene.collection.objects.link(self.root)
        top = self.arm.parent
        self.arm.parent = self.root
        self.name = name
        self.actions = {k: load_action(v, f'{name}_{k}') for k, v in anims.items()}
        # face texture variants
        self.tex_node = next(n for m in self.mesh.data.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE')
        self.tex_base = self.tex_node.image
        self.variants = {'closed': self.tex_base}
        for k in ('mouth_half', 'mouth_open', 'mouth_wide', 'blink'):
            p = f'{VAR}/{name}_{k}.png'
            if os.path.exists(p):
                im = bpy.data.images.load(p)
                im.colorspace_settings.name = self.tex_base.colorspace_settings.name
                self.variants[k] = im
        self.head_axis = self._head_forward_axis()
        self.track = None
        bpy.context.view_layer.update()
        hb, nb = self.arm.pose.bones['Head'], self.arm.pose.bones['neck']
        hf = self.arm.pose.bones['headfront'].head - hb.head
        front = Vector((0, -1, 0))                                     # the characters face -Y in their rest pose
        self.face_fwd = tuple(((self.arm.matrix_world @ hb.matrix).to_3x3().inverted() @ front).normalized())
        self.face_fwd_neck = tuple(((self.arm.matrix_world @ nb.matrix).to_3x3().inverted() @ front).normalized())

    def _head_forward_axis(self):
        b = self.arm.data.bones['Head']
        M = (self.arm.matrix_world @ b.matrix_local).to_3x3()
        best, ax = -2, 'TRACK_NEGATIVE_Z'
        for name, v in (('TRACK_X', (1, 0, 0)), ('TRACK_NEGATIVE_X', (-1, 0, 0)), ('TRACK_Y', (0, 1, 0)), ('TRACK_NEGATIVE_Y', (0, -1, 0)),
                        ('TRACK_Z', (0, 0, 1)), ('TRACK_NEGATIVE_Z', (0, 0, -1))):
            d = (M @ Vector(v)).normalized().dot(Vector((0, -1, 0)))
            if d > best:
                best, ax = d, name
        return ax

    def add_head_track(self, target):
        c = self.arm.pose.bones['Head'].constraints.new('DAMPED_TRACK')
        c.target = target
        c.track_axis = self.head_axis
        c.influence = 0.0
        self.track = c
        return c

    def add_hand_ik(self, side, target, pole):
        c = self.arm.pose.bones[f'{side}Hand'].constraints.new('IK')
        c.target = target
        c.pole_target = pole
        c.pole_angle = 0.0
        c.use_tail = False
        c.chain_count = 2
        c.influence = 0.0
        return c

    def hips_offset(self):
        """Hips position in the root's space (x, y)."""
        bpy.context.view_layer.update()
        p = self.root.matrix_world.inverted() @ (self.arm.matrix_world @ self.arm.pose.bones['Hips'].head)
        return Vector((p.x, p.y))

    def set_face(self, key):
        self.tex_node.image = self.variants.get(key, self.tex_base)


def empty(name, loc):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = Vector(loc)
    return e


# ------------------------------------------------------------------ mouth from text
VOW = {'aa': 'mouth_open', 'E': 'mouth_wide', 'I': 'mouth_wide', 'O': 'mouth_half', 'U': 'mouth_half'}


def mouth_track(text, t0, dur):
    import speech_fr as SP
    seq = SP.french_visemes(text)
    tot = sum(d for _, d in seq) or 1.0
    k = dur / tot
    out, t = [], t0
    for v, d in seq:
        if v != 'sil':
            shape = 'closed' if v == 'PP' else VOW.get(v, 'mouth_half')
            out.append((t, t + d * k, shape))
        t += d * k
    return out


def mouth_at(track, t):
    for a, b, s in track:
        if a <= t < b:
            return s
    return 'closed'


def blink_at(name, t):
    seed = 7 if name == 'nox' else 3
    rng = np.random.default_rng(seed)
    tt = 0.8 + rng.random() * 1.5
    while tt < 30:
        if tt <= t < tt + 0.14:
            return True
        tt += 2.6 + rng.random() * 1.8
    return False


# ------------------------------------------------------------------ build
def build():
    objs = AT.build()
    AT.place_on_bench(objs)
    L = AT.lights()
    # door hinge (handle on its left => hinge on the right edge) + lit doorway behind it
    door_empty = objs['door'][0]
    dm = objs['door'][1]
    bpy.context.view_layer.update()
    co = np.array([tuple(o.matrix_world @ v.co) for o in dm for v in o.data.vertices])
    lo, hi = co.min(0), co.max(0)
    hinge = empty('door_hinge', (hi[0] - 0.05, (lo[1] + hi[1]) / 2, 0))
    door_empty.parent = hinge
    door_empty.matrix_parent_inverse = hinge.matrix_world.inverted()
    glow = AT.mat_col('doorway', [214, 140, 74], emit=0.55)
    doorway = AT.quad('doorway', [(lo[0] + 0.07, AT.WALL_Y - 0.015, 0.0), (hi[0] - 0.07, AT.WALL_Y - 0.015, 0.0), (hi[0] - 0.07, AT.WALL_Y - 0.015, hi[2] - 0.08),
                                  (lo[0] + 0.07, AT.WALL_Y - 0.015, hi[2] - 0.08)], glow)
    pico = Actor('pico', RIG + '/pico_rigged.glb', {k: f'{ANIM}/pico_{k}.glb' for k in ('sprintstop', 'breath', 'talk', 'listen', 'hip', 'idle')}, 1.66)
    nox = Actor('nox2', RIG + '/nox2_rigged.glb', {k: f'{ANIM}/nox2_{k}.glb' for k in ('idle', 'talkright', 'shrug', 'listen', 'agree', 'talkopen')}, 1.78)
    # targets
    bench_top = AT.place_on_bench(objs)
    nox.hand_t = {s: empty(f'nox_hand_{s}', (NOX_MARK[0] + (0.2 if s == 'Left' else -0.12), NOX_MARK[1] - 0.3, bench_top + 0.04)) for s in ('Left', 'Right')}
    nox.pole_t = {s: empty(f'nox_pole_{s}', (NOX_MARK[0] + (0.75 if s == 'Left' else -0.75), NOX_MARK[1] + 0.35, 0.9)) for s in ('Left', 'Right')}
    bench_look = empty('nox_look_bench', (NOX_MARK[0] + 0.05, NOX_MARK[1] - 0.6, bench_top))
    pico_head_t = empty('pico_head_target', (0, 0, 1.5))
    nox_head_t = empty('nox_head_target', (0, 0, 1.6))
    nox.bench_look = bench_look
    bip = objs['bip'][0]
    return dict(objs=objs, L=L, hinge=hinge, doorway=doorway, pico=pico, nox=nox, pico_head_t=pico_head_t, nox_head_t=nox_head_t, bip=bip,
                bip0=bip.location.copy())


def pose_at(W, t):
    pico, nox = W['pico'], W['nox']
    # door
    k = min(max((t - DOOR_OPEN[0]) / (DOOR_OPEN[1] - DOOR_OPEN[0]), 0), 1)
    k = 1 - (1 - k) ** 3
    W['hinge'].rotation_euler = (0, 0, math.radians(-105 * k))
    W['doorway'].hide_render = k <= 0.01
    # Pico
    p_pose, p_clip = clip_pose(pico.actions, PICO_CLIPS, t)
    apply_pose(pico.arm, p_pose)
    th = math.radians(pw(PICO_TURN, t))
    pico.root.rotation_euler = (0, 0, th)
    pico.root.location = (0, 0, 0)
    bpy.context.view_layer.update()
    h = pico.hips_offset()
    R = Matrix.Rotation(th, 2)
    if t < SPRINT[0]:                                     # waiting behind the door, out of sight
        A = pico.actions['sprintstop']
        apply_pose(pico.arm, eval_action(A, SPRINT[1]))
        bpy.context.view_layer.update()
        h = pico.hips_offset()
        pico.root.location = (5, 5, -5)
    elif p_clip == 'sprintstop' and t < PICO_CLIPS[1][0]:
        A = pico.actions['sprintstop']
        h_end = Vector((0, 0))
        apply_pose(pico.arm, eval_action(A, SPRINT[2])); bpy.context.view_layer.update(); h_end = pico.hips_offset()
        apply_pose(pico.arm, p_pose)
        start = Vector(STOP) - R @ h_end
        pico.root.location = (start.x, start.y, 0)
    else:
        pico.root.location = (STOP[0] - (R @ h).x, STOP[1] - (R @ h).y, 0)
    # Nox
    n_pose, n_clip = clip_pose(nox.actions, NOX_CLIPS, t)
    apply_pose(nox.arm, n_pose)
    thn = math.radians(pw(NOX_TURN, t))
    nox.root.rotation_euler = (0, 0, thn)
    nox.root.location = (0, 0, 0)
    hn = nox.hips_offset()
    Rn = Matrix.Rotation(thn, 2)
    nox.root.location = (NOX_MARK[0] - (Rn @ hn).x, NOX_MARK[1] - (Rn @ hn).y, 0)
    bpy.context.view_layer.update()
    W['pico_head_t'].location = PP.joint(pico.arm, 'headfront')
    W['nox_head_t'].location = PP.joint(nox.arm, 'headfront')
    solder = pw(NOX_SOLDER, t)
    if solder > 0:
        right = Vector((math.cos(thn), math.sin(thn), 0.0))           # the character's right-to-left axis
        PP.rotate_bone_world(nox.arm, 'Spine01', Quaternion(right, math.radians(12 * solder)))
        PP.rotate_bone_world(nox.arm, 'Spine', Quaternion(right, math.radians(8 * solder)))
        for s_, sx in (('Left', 1), ('Right', -1)):
            base = Vector(W.setdefault('hand0_' + s_, tuple(nox.hand_t[s_].location)))
            jig = Vector((0.01 * math.sin(t * (6.0 if sx > 0 else 4.7)), 0.008 * math.sin(t * 3.3 + sx), 0.006 * abs(math.sin(t * 5.1 + sx))))
            PP.two_bone_ik(nox.arm, f'{s_}Arm', f'{s_}ForeArm', f'{s_}Hand', base + jig, nox.pole_t[s_].location, solder)
    # gaze: face direction = from the head joint towards 'headfront' (rest pose), measured per actor
    for actor, tgt, wgt in ((nox, nox.bench_look.location, 0.8 * solder), (nox, W['pico_head_t'].location, pw(NOX_LOOK_PICO, t)),
                            (pico, W['nox_head_t'].location, pw(PICO_LOOK_NOX, t))):
        if wgt > 0:
            PP.look_at(actor.arm, 'Head', actor.face_fwd, tgt, wgt, 55)
            PP.look_at(actor.arm, 'neck', actor.face_fwd_neck, tgt, 0.35 * wgt, 25)
    # hands relaxed
    for a in (pico, nox):
        for s in ('L', 'R'):
            rigext.hand_pose(a.arm, s, curl=0.35, thumb=0.25)
    # faces
    for a, who in ((pico, 'pico'), (nox, 'nox')):
        key = 'closed'
        for lid, w, t0, dur, text in LINES:
            if w == who and t0 <= t < t0 + dur:
                key = mouth_at(W.setdefault('mt_' + lid, mouth_track(text, t0, dur)), t)
        if key == 'closed' and blink_at(who, t):
            key = 'blink'
        a.set_face(key)
    # Bip floats
    W['bip'].location = W['bip0'] + Vector((0, 0, 0.025 * math.sin(t * 2.1)))
    W['bip'].rotation_euler = (0, 0, 0.15 * math.sin(t * 0.9))
    bpy.context.view_layer.update()


def shot_at(t):
    for a, b, name in SHOTS:
        if a <= t < b:
            return name
    return SHOTS[-1][2]


def _front(actor):
    """The character's facing direction (world, horizontal) and its right-hand side."""
    th = actor.root.rotation_euler.z
    f = Vector((math.sin(th), -math.cos(th), 0.0))
    return f, Vector((-f.y, f.x, 0.0))


def camera_for(W, cam, name, t):
    if name == 'wide':
        PX.aim(cam, (-0.08, -2.4, 1.32), (-0.1, 1.4, 1.06), 54)
        return
    actor = W['nox'] if name == 'closeN' else W['pico']
    face = actor.arm.matrix_world @ actor.arm.pose.bones['headfront'].head
    f, r = _front(actor)
    side = 0.32 if name == 'closeN' else -0.28                    # a little off-axis: three-quarter view
    pos = face + f * 1.3 + r * side + Vector((0, 0, 0.03))
    PX.aim(cam, pos, face + Vector((0, 0, 0.05)), 33)      # face in the middle band: the captions sit above it


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--fps', type=int, default=12)
    ap.add_argument('--times', default=None)
    ap.add_argument('--frames', default=None)
    ap.add_argument('--samples', type=int, default=24)
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    os.makedirs(a.out + '/exr', exist_ok=True)
    W = build()
    k = 1
    for o in bpy.context.scene.objects:
        if o.type in ('MESH', 'CURVE'):
            o.pass_index = k
            k += 1
    PX.setup(360, 640, samples=a.samples, supersample=2)
    cam = PX.camera()
    n = int(round(T_END * a.fps))
    if a.times:
        items = [(f'k{float(x):06.2f}', float(x)) for x in a.times.split(',')]
    else:
        f0, f1 = (1, n) if not a.frames else (int(x) for x in a.frames.split(':'))
        items = [(f'f{f:04d}', (f - 1) / a.fps) for f in range(f0, f1 + 1)]
    import time
    t_start = time.time()
    for tag, t in items:
        pose_at(W, t)
        camera_for(W, cam, shot_at(t), t)
        PX.render(os.path.abspath(f'{a.out}/exr/{tag}.exr'))
        print('frame', tag, round(t, 2), shot_at(t), round(time.time() - t_start, 1), 's', flush=True)


if __name__ == '__main__':
    main()
