"""Animation clips of Meshy rigs, sampled into arrays so that they can be smoothed, looped and blended cleanly.

    C = load_clip(glb, name)          30 samples per second (the rate Meshy keys them at)
    P = C.sample(t)                   pose at t seconds (clamped)          P = (loc[nb, 3], quat[nb, 4])
    P = C.sample_loop(t, xf=0.6)      endless loop whose seam is cross-faded over xf seconds (no jump when it restarts)
    P = blend(Pa, Pb, w)              w = 0 -> Pa, 1 -> Pb
    apply(arm, C.bones, P)

Why arrays: the v1 evaluator read the f-curves frame by frame, looped clips by jumping from their last frame to their
first (a visible pop) and could not smooth the small jitter that generated clips contain."""
import math
import re

import bpy
import numpy as np
from mathutils import Quaternion, Vector

RATE = 30.0


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)             # smootherstep: zero velocity and acceleration at both ends


def blend(a, b, w):
    if w <= 0.0:
        return a
    if w >= 1.0:
        return b
    la, qa = a
    lb, qb = b
    s = np.sign((qa * qb).sum(-1, keepdims=True))
    s[s == 0] = 1.0
    q = qa * (1 - w) + qb * s * w
    q /= np.maximum(np.linalg.norm(q, axis=-1, keepdims=True), 1e-9)
    return la * (1 - w) + lb * w, q


class Clip:
    def __init__(self, name, bones, loc, quat):
        self.name, self.bones, self.loc, self.quat = name, bones, loc, quat
        self.n = loc.shape[0]
        self.dur = (self.n - 1) / RATE

    def sample(self, t):
        x = min(max(t * RATE, 0.0), self.n - 1.0)
        i = int(math.floor(x))
        j = min(i + 1, self.n - 1)
        f = x - i
        if f < 1e-6:
            return self.loc[i].copy(), self.quat[i].copy()
        return blend((self.loc[i], self.quat[i]), (self.loc[j], self.quat[j]), f)

    def sample_loop(self, t, xf=0.6):
        xf = min(xf, self.dur * 0.4)
        period = self.dur - xf
        u = t % period
        p = self.sample(u)
        if u < xf:                                         # the end of the clip fades into its beginning
            p = blend(self.sample(u + period), p, ease(u / xf))
        return p

    def jitter(self):
        """RMS of the second difference of the rotations, in degrees per sample^2 (how shaky the clip is)."""
        d2 = self.quat[2:] - 2 * self.quat[1:-1] + self.quat[:-2]
        return float(np.degrees(2 * np.sqrt((d2 ** 2).sum(-1)).mean()))


def _channelbag(act):
    from bpy_extras import anim_utils
    return anim_utils.action_get_channelbag_for_slot(act, act.slots[0])


def load_clip(path, name, smooth=1.0, scene_fps=24.0):
    """smooth: sigma of a gaussian over time, in samples (1/30 s); 0 = raw."""
    before_obs, before_acts = set(bpy.data.objects), set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    act = [a for a in bpy.data.actions if a not in before_acts][0]
    curves = {}
    for fc in _channelbag(act).fcurves:
        m = re.match(r'pose\.bones\["(.+)"\]\.(location|rotation_quaternion)', fc.data_path)
        if m:
            curves.setdefault(m.group(1), {}).setdefault(m.group(2), {})[fc.array_index] = fc
    f0, f1 = act.frame_range
    step = scene_fps / RATE
    n = int(round((f1 - f0) / step)) + 1
    bones = sorted(curves)
    loc = np.zeros((n, len(bones), 3), dtype=np.float64)
    quat = np.zeros((n, len(bones), 4), dtype=np.float64)
    quat[..., 0] = 1.0
    for bi, b in enumerate(bones):
        ch = curves[b]
        for k in range(n):
            fr = f0 + k * step
            if 'location' in ch:
                for i, fc in ch['location'].items():
                    loc[k, bi, i] = fc.evaluate(fr)
            if 'rotation_quaternion' in ch:
                for i, fc in ch['rotation_quaternion'].items():
                    quat[k, bi, i] = fc.evaluate(fr)
    for o in [o for o in bpy.data.objects if o not in before_obs]:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.actions.remove(act)
    quat /= np.maximum(np.linalg.norm(quat, axis=-1, keepdims=True), 1e-9)
    for k in range(1, n):                                  # keep each bone's quaternion on the same hemisphere over time
        flip = (quat[k] * quat[k - 1]).sum(-1) < 0
        quat[k][flip] *= -1
    raw = Clip(name, bones, loc.copy(), quat.copy())
    if smooth and n > 4:
        from scipy.ndimage import gaussian_filter1d
        quat = gaussian_filter1d(quat, sigma=smooth, axis=0, mode='nearest')
        quat /= np.maximum(np.linalg.norm(quat, axis=-1, keepdims=True), 1e-9)
        loc = gaussian_filter1d(loc, sigma=smooth, axis=0, mode='nearest')
    c = Clip(name, bones, loc, quat)
    c.jitter_raw = raw.jitter()
    return c


def apply(arm, bones, pose):
    loc, quat = pose
    pbs = arm.pose.bones
    for i, b in enumerate(bones):
        pb = pbs.get(b)
        if pb is None:
            continue
        pb.rotation_mode = 'QUATERNION'
        pb.location = loc[i]
        pb.rotation_quaternion = quat[i]


class Track:
    """A sequence of clips on one actor: [(t_start, clip_name, offset_s, loop, xf_in[, speed]), ...]; pose(t) cross-fades them.

    shifts[k] is added to the Hips translation of segment k: it re-bases every clip so that the feet stand on the
    actor's origin.  Without it each clip carries its own offset (metres, for a run) and turning or cross-fading the
    actor swings it around that offset."""

    def __init__(self, clips, segs):
        self.clips, self.segs = clips, segs
        self.shifts = [np.zeros(3) for _ in segs]
        self.hips = next(iter(clips.values())).bones.index('Hips')

    def seg_pose(self, k, t):
        t0, name, off, loop = self.segs[k][:4]
        speed = self.segs[k][5] if len(self.segs[k]) > 5 else 1.0
        c = self.clips[name]
        tt = off + (t - t0) * speed
        loc, quat = c.sample_loop(tt) if loop else c.sample(tt)
        loc = loc.copy()
        loc[self.hips] += self.shifts[k]
        return loc, quat

    def index(self, t):
        k = 0
        for i, s in enumerate(self.segs):
            if t >= s[0]:
                k = i
        return k

    def pose(self, t):
        """Returns (pose, k, w): the blended pose, the current segment and how far it has faded in (1 = fully)."""
        k = self.index(t)
        p = self.seg_pose(k, t)
        xf = self.segs[k][4]
        w = 1.0
        if k > 0 and xf > 0 and t < self.segs[k][0] + xf:
            w = ease((t - self.segs[k][0]) / xf)
            p = blend(self.seg_pose(k - 1, t), p, w)
        return p, k, w
