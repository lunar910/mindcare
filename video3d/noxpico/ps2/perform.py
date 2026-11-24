"""The acting layer of version 4: a character holds a natural pose and only makes small, motivated movements.

    P = Performer(actor, base=BaseTrack(...), gaze=Gaze(...), gestures=[...], accents=[...], life=Life(...), lock=True)
    P.prepare(t_end)                 bake everything that needs memory (lags, springs) once
    P.pose(t)                        set the armature for time t (pure: frames can be evaluated in any order)
    P.eyes(t)                        eye shape-key values for the face at time t (call after pose)

Layers, in the order they are applied every frame:
  1. base     a motion clip window (calm part of an idle / listen clip), slowed down, with long minimum-jerk cross-fades
  2. life     breathing (chest, shoulders), slow weight shift (hips), tiny head drift: alive but never restless
  3. feet     planted feet are locked to the floor (footlock.py)
  4. torso    the chest turns a little towards what the character looks at (lags behind the head)
  5. gaze     eyes jump to the target (fast, minimum-jerk), the head follows with a critically damped lag
  6. accents  small nods / head tilts on stressed words
  7. arms     authored gestures: hand targets in the character's own frame, minimum-jerk between key poses, IK
  8. hands    hand orientation and finger curl per gesture key
All amplitudes are in degrees / metres; all times in seconds."""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import acting as AC
import anim2
import footlock
import procpose as PP
import rigext


# ------------------------------------------------------------------ 1. base body motion
class BaseTrack:
    """[(t_start, clip, clip_time_start, speed, xfade)]: each segment plays its clip from clip_time_start at `speed`
    (0.5 = half speed), looping with a long seam blend when it runs out; segments cross-fade over xfade seconds with a
    minimum-jerk weight.  freeze=True on a segment holds its first frame (a still pose)."""

    def __init__(self, actor, segs, hips_rebase=True):
        self.actor, self.segs = actor, segs
        self.clips = actor.clips
        self.bones = next(iter(self.clips.values())).bones
        self.hi = self.bones.index('Hips')
        self.shift = [np.zeros(3) for _ in segs]
        self.rebase = hips_rebase

    def _seg(self, k, t):
        s = self.segs[k]
        t0, clip, c0, speed = s[0], s[1], s[2], s[3]
        mode = s[5] if len(s) > 5 else 'loop'
        c = self.clips[clip]
        tt = max(c0 + (t - t0) * speed, 0.0)
        if mode == 'loop':                         # always the looping sampler: it is continuous everywhere
            loc, quat = c.sample_loop(tt, xf=min(1.2, c.dur * 0.3))
        else:                                      # 'clamp': play once and hold the last frame
            loc, quat = c.sample(tt)
        loc = loc.copy()
        loc[self.hi] += self.shift[k]
        return loc, quat

    def index(self, t):
        k = 0
        for i, s in enumerate(self.segs):
            if t >= s[0]:
                k = i
        return k

    def sample(self, t):
        k = self.index(t)
        p = self._seg(k, t)
        xf = self.segs[k][4]
        if k > 0 and xf > 0 and t < self.segs[k][0] + xf:
            w = AC.minjerk((t - self.segs[k][0]) / xf)
            p = anim2.blend(self._seg(k - 1, t), p, w)
        return p

    def calibrate(self, mark_xy):
        """Re-base each segment so that the feet stand on the actor's origin (average over the segment)."""
        a = self.actor
        for k, s in enumerate(self.segs):
            if not self.rebase or s[1] == 'sprintstop':
                continue
            t1 = self.segs[k + 1][0] if k + 1 < len(self.segs) else s[0] + 4.0
            acc, n = Vector((0, 0)), 7
            for i in range(n):
                tt = s[0] + (t1 - s[0]) * i / (n - 1)
                loc, quat = self._seg(k, tt)
                loc = loc.copy()
                loc[self.hi] -= self.shift[k]
                a.pose((loc, quat), self.bones)
                acc += a.feet_local()
            self.shift[k] = a.hips_shift(acc / n)


# ------------------------------------------------------------------ 2. life
class Life:
    def __init__(self, seed=1.0, breath_rate=0.26, breath_deg=0.7, sway_cm=0.9, sway_rate=0.11, head_deg=0.6,
                 pant=None, events=()):
        """pant = (t_start, t_end, rate_hz, deg): heavier, faster breathing that settles (after a sprint)."""
        self.seed, self.rate, self.deg, self.sway, self.sway_rate, self.head = seed, breath_rate, breath_deg, sway_cm, sway_rate, head_deg
        self.pant = pant
        self.events = list(events)               # [(t0, rise, hold, fall, shoulder_cm)] one visible breath / sigh each

    def lift(self, t):
        """Shoulder lift in cm of the breath events at t (an exhale is a negative lift)."""
        return sum(cm * AC.bump(t, t0, r, h, f) for t0, r, h, f, cm in self.events)

    def breath(self, t):
        """(-1..1 phase signal, amplitude in degrees)."""
        rate, deg = self.rate, self.deg
        if self.pant and t < self.pant[1]:
            k = 1.0 - AC.minjerk((t - self.pant[0]) / max(self.pant[1] - self.pant[0], 1e-3)) if t > self.pant[0] else 1.0
            rate = self.rate + (self.pant[2] - self.rate) * k
            deg = self.deg + (self.pant[3] - self.deg) * k
        # integrate the varying rate so that the phase stays continuous
        ph = self._phase(t)
        return math.sin(ph), deg

    def _phase(self, t):
        if not self.pant:
            return 2 * math.pi * self.rate * t + self.seed
        n = max(1, int(t * 60))
        dt = t / n
        ph = self.seed
        for i in range(n):
            tt = (i + 0.5) * dt
            if tt < self.pant[1]:
                k = 1.0 - AC.minjerk((tt - self.pant[0]) / max(self.pant[1] - self.pant[0], 1e-3)) if tt > self.pant[0] else 1.0
                r = self.rate + (self.pant[2] - self.rate) * k
            else:
                r = self.rate
            ph += 2 * math.pi * r * dt
        return ph


# ------------------------------------------------------------------ 5. gaze
class Gaze:
    """Where a character looks, and how the eyes, the head and the chest get there.

    keys: [(t, target, _, head_share=1.0)]: from time t look at `target` (Vector or callable t -> Vector).
      head_share < 1: a glance: the eyes go all the way, the head only that share of the way.
    Timing measured on the reference video (study/reports/face-data.md):
      - eyes: a saccade, 25 ms + 2.4 ms per degree, minimum jerk (they arrive first)
      - head: starts head_delay after the eyes; one-way minimum-jerk turn, 15 deg in 0.30 s, 30 deg in 0.68 s
        (peak about 80-90 deg/s), then it holds
      - chest: starts later, takes longer, turns only `chest` of the way
    origin: roughly where the head is (to measure the angles)."""

    def __init__(self, keys, origin, head_delay=0.05, chest=0.22, chest_delay=0.14, head_weight=0.9, limit=70.0, speed=1.0,
                 **_):
        self.keys = keys
        self.speed = speed                       # < 1: a quicker, more excitable character
        self.origin_keys = origin if isinstance(origin, list) else [(0.0, tuple(origin))]
        self.head_delay, self.chest, self.chest_delay, self.hw = head_delay, chest, chest_delay, head_weight
        self.limit = limit
        self.rate = 60.0

    def _val(self, i, t):
        g = self.keys[i][1]
        return Vector(g(t) if callable(g) else g)

    def _share(self, i):
        return self.keys[i][3] if len(self.keys[i]) > 3 else 1.0

    def origin(self, t):
        return Vector(AC.curve(self.origin_keys, t))

    def angle(self, p, q, t=0.0):
        o = self.origin(t)
        a, b = Vector(p) - o, Vector(q) - o
        if a.length < 1e-6 or b.length < 1e-6:
            return 0.0
        return math.degrees(a.angle(b))

    @staticmethod
    def head_duration(deg):
        """Total time of a head turn with the 'snappy' profile: 30 deg settles in about 0.6 s (half of it done in
        0.17 s), like the reference; bigger turns grow more slowly (the body helps)."""
        if deg <= 30.0:
            return max(0.20, 0.27 + 0.022 * (deg - 15.0))
        return min(1.1, 0.60 + 0.006 * (deg - 30.0))

    @staticmethod
    def eye_duration(deg):
        return min(0.16, 0.025 + 0.0024 * deg)

    def _build(self, kind):
        """Segments [(t_start, dur, p_from, key_index)] for 'eyes', 'head' or 'chest'."""
        segs = []

        def at(t):
            if not segs:
                return self._val(0, t)
            for (t0, d, pf, k) in reversed(segs):
                if t >= t0:
                    pt = self._goal(kind, k, t)
                    ease = AC.minjerk if kind == 'eyes' else AC.snappy
                    return pt if t >= t0 + d else self._interp(pf, pt, ease((t - t0) / d), t)
            return segs[0][2]
        for k, key in enumerate(self.keys):
            t = key[0]
            if kind == 'eyes':
                t0 = t
            elif kind == 'head':
                t0 = t + self.head_delay
            else:
                t0 = t + self.chest_delay
            if kind != 'eyes' and segs:                    # never start a head / chest move while the last one is still fast
                p0, pd = segs[-1][0], segs[-1][1]
                t0 = max(t0, p0 + 0.85 * pd)
            pf = at(t0)
            pt = self._goal(kind, k, t0)
            deg = self.angle(pf, pt, t0)
            if kind == 'eyes':
                d = self.eye_duration(deg)
            elif kind == 'head':
                d = self.head_duration(deg) * self.speed
            else:
                d = self.head_duration(deg) * self.speed * 1.4
            segs.append((t0, max(d, 1.0 / 60), pf, k))
        return segs, at

    def _interp(self, pf, pt, w, t):
        """Between two aim points, turning at an even angular pace as seen from the head (a straight line between a
        near and a far point would sweep most of the angle at the start)."""
        o = self.origin(t)
        a, b = Vector(pf) - o, Vector(pt) - o
        if a.length < 1e-6 or b.length < 1e-6 or a.normalized().dot(b.normalized()) > 0.99999:
            return Vector(pf).lerp(Vector(pt), w)
        d = a.normalized().slerp(b.normalized(), w)
        return o + d * (a.length * (1 - w) + b.length * w)

    def _goal(self, kind, k, t):
        """Where the eyes / head / chest aim for key k.  A glance (share < 1) turns the head only that share of the ANGLE
        from the last fully followed target, seen from the head."""
        p = self._val(k, t)
        if kind != 'eyes' and self._share(k) < 1.0:
            j = k
            while j > 0 and self._share(j) < 1.0:
                j -= 1
            o = self.origin(t)
            a, b = self._val(j, t) - o, p - o
            q = a.normalized().slerp(b.normalized(), self._share(k)) if a.length > 1e-6 and b.length > 1e-6 else b.normalized()
            p = o + q * b.length
        return p

    def prepare(self, t_end):
        n = int(math.ceil(t_end * self.rate)) + 1
        out = {}
        for kind in ('eyes', 'head', 'chest'):
            segs, at = self._build(kind)
            out[kind] = AC.Baked(np.array([tuple(at(i / self.rate)) for i in range(n)]), self.rate)
            if kind == 'head':
                self.head_segs = segs
        self.eyes_b, self.head_b, self.chest_b = out['eyes'], out['head'], out['chest']

    def turns(self, min_deg=15.0):
        """[(t_peak_speed, degrees, duration)] of the head turns of at least min_deg (blinks go there)."""
        out = []
        for (t0, d, pf, k) in self.head_segs[1:]:
            deg = self.angle(pf, self._goal('head', k, t0), t0)
            if deg >= min_deg:
                out.append((t0 + d / 2, deg, d))
        return out

    def eye_target(self, t):
        return Vector(self.eyes_b.at(t))

    def head_target(self, t):
        return Vector(self.head_b.at(t))

    def chest_target(self, t):
        return Vector(self.chest_b.at(t))


# ------------------------------------------------------------------ 7-8. gestures
class Gesture:
    """One arm movement: keys = [(t, hand_offset, palm, fingers_dir, curl), ...] in the character's own frame:
        hand_offset = (right, forward, up) metres from the chest joint ('Spine'); right = the character's right
        palm / fingers_dir = (right, forward, up) directions or None (keep the forearm's own wrist)
        curl = finger curl 0..1 (0.35 relaxed)
    weight goes 0 -> 1 over the first key interval (from the base pose) and 1 -> 0 over the last one.
    elbow = (right, forward, up) pole direction for the elbow (default: out and back)."""

    def __init__(self, side, keys, elbow=None, ease_in=None, ease_out=None):
        self.side, self.keys = side, keys
        sx = 1.0 if side == 'Right' else -1.0
        self.elbow = elbow or (0.7 * sx, -0.55, -0.45)
        self.t0, self.t1 = keys[0][0], keys[-1][0]
        self.ease_in = ease_in if ease_in is not None else (keys[1][0] - keys[0][0])
        self.ease_out = ease_out if ease_out is not None else (keys[-1][0] - keys[-2][0])

    def weight(self, t):
        if t <= self.t0 or t >= self.t1:
            return 0.0
        if t < self.t0 + self.ease_in:
            return AC.snappy((t - self.t0) / self.ease_in)
        if t > self.t1 - self.ease_out:
            return 1.0 - AC.minjerk((t - (self.t1 - self.ease_out)) / self.ease_out)
        return 1.0

    def at(self, t):
        """(hand offset, palm, fingers, curl) at t, minimum-jerk between keys (the first and last keys are reached
        through the weight, so the inner keys are interpolated)."""
        ks = self.keys
        inner = ks[1:-1] if len(ks) > 2 else ks
        if t <= inner[0][0]:
            k = inner[0]
            return Vector(k[1]), k[2], k[3], k[4]
        for a, b in zip(inner, inner[1:]):
            if t <= b[0]:
                x = AC.snappy((t - a[0]) / max(b[0] - a[0], 1e-6))
                pal = None if a[2] is None or b[2] is None else Vector(a[2]).lerp(Vector(b[2]), x)
                fin = None if a[3] is None or b[3] is None else Vector(a[3]).lerp(Vector(b[3]), x)
                return Vector(a[1]).lerp(Vector(b[1]), x), pal, fin, a[4] + (b[4] - a[4]) * x
        k = inner[-1]
        return Vector(k[1]), k[2], k[3], k[4]


# ------------------------------------------------------------------ the performer
class Performer:
    def __init__(self, actor, base, mark, heading, gaze=None, gestures=(), accents=(), life=None, lock_from=0.0,
                 heading_keys=None, extra=None, relax_curl=0.32, gaze_weight=None, hips_yaw=None, spine_yaw=None):
        self.a, self.base, self.mark, self.heading = actor, base, mark, heading
        self.gaze, self.gestures, self.accents = gaze, list(gestures), list(accents)
        self.life = life or Life()
        self.lock_from = lock_from
        self.heading_keys = heading_keys
        self.extra = extra                      # callable(performer, t): scene-specific layer (Nox's hands on the bench)
        self.relax_curl = relax_curl
        self.gaze_weight = gaze_weight          # [(t, w)] or None (= 1)
        self.hips_yaw, self.spine_yaw = hips_yaw, spine_yaw      # [(t, degrees)]: turning the body towards someone, feet planted
        self.lock = footlock.FootLock(actor)
        self.locked = False
        arm = actor.arm
        hb = arm.data.bones['Head']
        Mh = (arm.matrix_world.to_3x3().normalized() @ hb.matrix_local.to_3x3()).normalized()
        f_l = Vector(actor.face_fwd).normalized()
        u_l = Mh.inverted() @ Vector((0.0, 0.0, 1.0))
        u_l = (u_l - f_l * u_l.dot(f_l)).normalized()
        self.head_basis = Matrix((f_l, u_l, f_l.cross(u_l))).transposed()     # columns: forward, up, side (bone space)
        self.rest_hand = {}
        for s in ('Left', 'Right'):                            # rest frame of each hand, in armature space
            b = arm.data.bones[f'{s}Hand']
            R = b.matrix_local.to_3x3().normalized()
            h = b.head_local
            f = arm.data.bones[f'{s}Fingers2'].head_local - h
            th = arm.data.bones[f'{s}Thumb1'].head_local - h if f'{s}Thumb1' in arm.data.bones else Vector((0, -1, 0))
            f.normalize()
            th = (th - f * th.dot(f)).normalized()
            palm = f.cross(th) if s == 'Left' else th.cross(f)
            self.rest_hand[s] = (R, f, palm.normalized())

    # ---- helpers
    def frame(self, t):
        return AC.body_frame(self.a)

    def heading_at(self, t):
        if self.heading_keys:
            return AC.curve(self.heading_keys, t)
        return self.heading

    def chest(self):
        return AC.joint(self.a.arm, 'Spine')

    def to_world(self, off):
        f, r, u = AC.body_frame(self.a)
        return r * off[0] + f * off[1] + u * off[2]

    def prepare(self, t_end):
        if self.gaze:
            self.gaze.prepare(t_end)
        self.base.calibrate(self.mark)
        # plant the feet once, from the calmest moment after lock_from
        self.pose_body(self.lock_from + 0.5, lock=False)
        self.lock.capture(floor=None)
        floor = min(self.lock.pos['Left'].z, self.lock.pos['Right'].z)
        for s in ('Left', 'Right'):
            self.lock.pos[s].z = floor
        self.locked = True

    # ---- layers 1-3
    def pose_body(self, t, lock=True):
        a = self.a
        arm = a.arm
        AC.reset_pose(arm)                         # each frame starts from rest: nothing carries over from the last one
        a.pose(self.base.sample(t), self.base.bones)
        a.place(self.mark, self.heading_at(t))
        bpy.context.view_layer.update()
        f, r, u = AC.body_frame(a)
        L = self.life
        # weight shift: hips drift sideways and a little forward / back, very slowly
        dx = L.sway * 0.01 * AC.noise(t, L.seed, L.sway_rate, 2)
        dy = L.sway * 0.004 * AC.noise(t, L.seed + 5, L.sway_rate * 0.8, 2)
        AC.translate(arm, 'Hips', r * dx + f * dy)
        PP.rotate_bone_world(arm, 'Hips', Quaternion(f, math.radians(-dx / 0.01 * 0.45)))     # the pelvis tilts with the weight
        if self.hips_yaw:
            PP.rotate_bone_world(arm, 'Hips', Quaternion(u, math.radians(AC.curve(self.hips_yaw, t))))
        if lock and self.locked and t >= self.lock_from:
            w = 1.0 if self.lock_from <= 0.0 else AC.minjerk((t - self.lock_from) / 0.4)
            self.lock.apply(w)
        # breathing: chest rises, shoulders lift a hair
        b, deg = L.breath(t)
        PP.rotate_bone_world(arm, 'Spine01', Quaternion(r, math.radians(-0.6 * deg * b)))
        PP.rotate_bone_world(arm, 'Spine', Quaternion(r, math.radians(-0.4 * deg * b)))
        lift = L.lift(t)                          # one visible breath: shoulders up (and the chest a little back)
        for s, sx in (('Left', -1), ('Right', 1)):
            PP.rotate_bone_world(arm, f'{s}Shoulder', Quaternion(f, math.radians(sx * (0.5 * deg * max(b, 0.0) + 3.6 * lift))))
        if lift:
            PP.rotate_bone_world(arm, 'Spine01', Quaternion(r, math.radians(-0.8 * lift)))
        if self.extra:
            self.extra(self, t, 'body')

    # ---- layers 4-6
    def pose_head(self, t):
        a, arm = self.a, self.a.arm
        f, r, u = AC.body_frame(a)
        nod_t = sum(acc[2] * AC.bump(t, acc[0], acc[3] if len(acc) > 3 else 0.10, 0.0, acc[4] if len(acc) > 4 else 0.25)
                    for acc in self.accents if acc[1] == 'nod')
        lean_t = 0.0                               # (t0, 'lean', degrees, rise, hold, fall): the chest leans in (head push)
        for acc in self.accents:
            if acc[1] == 'lean':
                t0_, _, deg, rise, hold, fall = acc
                if t >= t0_:
                    if t < t0_ + rise:
                        w = AC.snappy((t - t0_) / rise)
                    elif t < t0_ + rise + hold:
                        w = 1.0
                    else:
                        w = 1.0 - AC.minjerk((t - t0_ - rise - hold) / fall)
                    lean_t += deg * max(w, 0.0)
        left_axis = Vector((math.cos(a.heading), math.sin(a.heading), 0.0))
        if nod_t or lean_t:                        # head and chest start together; the chest moves about a third as much
            PP.rotate_bone_world(arm, 'Spine', Quaternion(left_axis, math.radians(0.3 * nod_t + 0.5 * lean_t)))
            if lean_t:
                PP.rotate_bone_world(arm, 'Spine01', Quaternion(left_axis, math.radians(0.5 * lean_t)))
        if self.spine_yaw:
            y = math.radians(AC.curve(self.spine_yaw, t))
            PP.rotate_bone_world(arm, 'Spine02', Quaternion(u, y * 0.45))
            PP.rotate_bone_world(arm, 'Spine01', Quaternion(u, y * 0.55))
        if self.extra:
            self.extra(self, t, 'torso')
        gw = AC.curve(self.gaze_weight, t) if self.gaze_weight else 1.0
        if self.gaze and gw > 0:
            g = self.gaze
            ct = g.chest_target(t)
            ch = AC.joint(arm, 'Spine')
            want = ct - ch
            want.z = 0
            if want.length > 1e-4:
                ang = math.atan2(want.cross(f).z * -1, want.dot(f))
                ang = max(-math.radians(40), min(math.radians(40), ang))
                PP.rotate_bone_world(arm, 'Spine01', Quaternion(u, ang * g.chest * 0.55 * gw))
                PP.rotate_bone_world(arm, 'Spine', Quaternion(u, ang * g.chest * 0.45 * gw))
            ht = g.head_target(t)
            PP.look_at(arm, 'neck', a.face_fwd_neck, ht, 0.35 * g.hw * gw, 30)
            # the head is stabilised in the room (as a real head is, by reflex): it points at the target, upright,
            # whatever the chest does underneath (breathing, weight shift, leaning)
            d = (ht - AC.joint(arm, 'Head')).normalized()
            up = Vector((0.0, 0.0, 1.0))
            up = (up - d * up.dot(d)).normalized()
            Bw = Matrix((d, up, d.cross(up))).transposed()
            AC.set_world_rot(arm, 'Head', (Bw @ self.head_basis.transposed()).normalized(), g.hw * gw)
        # accents (nods, tilts) and a little drift
        L = self.life
        nod = sum(acc[2] * AC.bump(t, acc[0], acc[3] if len(acc) > 3 else 0.10, 0.0, acc[4] if len(acc) > 4 else 0.25)
                  for acc in self.accents if acc[1] == 'nod')
        tilt = sum(acc[2] * AC.bump(t, acc[0], 0.22, acc[3] if len(acc) > 3 else 0.6, 0.35) for acc in self.accents if acc[1] == 'tilt')
        up = sum(acc[2] * AC.bump(t, acc[0], 0.16, acc[3] if len(acc) > 3 else 0.3, 0.3) for acc in self.accents if acc[1] == 'up')
        # one-way poses: (t0, 'pitch' | 'roll', degrees, rise, hold, fall) - snap there, hold, ease back
        for acc in self.accents:
            if acc[1] in ('pitch', 'roll'):
                t0_, _, deg, rise, hold, fall = acc
                if t < t0_:
                    continue
                if t < t0_ + rise:
                    w = AC.snappy((t - t0_) / rise)
                elif t < t0_ + rise + hold:
                    w = 1.0
                else:
                    w = 1.0 - AC.minjerk((t - t0_ - rise - hold) / fall)
                if acc[1] == 'pitch':
                    nod += deg * max(w, 0.0)
                else:
                    tilt += deg * max(w, 0.0)
        drift_y = L.head * AC.noise(t, L.seed + 11, 0.23, 3)
        drift_p = L.head * 0.7 * AC.noise(t, L.seed + 23, 0.19, 3)
        f, r, u = AC.body_frame(a)
        hf = (AC.joint(arm, 'headfront') - AC.joint(arm, 'Head')).normalized()
        side = hf.cross(u).normalized()
        if nod or up or drift_p:
            PP.rotate_bone_world(arm, 'Head', Quaternion(side, math.radians(-(nod - up + drift_p))))
        if tilt:
            PP.rotate_bone_world(arm, 'Head', Quaternion(hf, math.radians(tilt)))
        if drift_y:
            PP.rotate_bone_world(arm, 'Head', Quaternion(u, math.radians(drift_y)))

    # ---- layers 7-8
    def pose_arms(self, t):
        a, arm = self.a, self.a.arm
        if self.extra:
            self.extra(self, t, 'arms')
        curls = {'Left': self.relax_curl, 'Right': self.relax_curl}
        for g in self.gestures:
            w = g.weight(t)
            if w <= 0:
                continue
            off, palm, fing, curl = g.at(t)
            s = g.side
            tgt = self.chest() + self.to_world(off)
            pole = AC.joint(arm, f'{s}Arm') + self.to_world(Vector(g.elbow))
            AC.ik2(arm, f'{s}Arm', f'{s}ForeArm', f'{s}Hand', tgt, pole, w)
            if palm is not None and fing is not None:
                self.orient_hand(s, self.to_world(palm), self.to_world(fing), w)
            curls[s] = curls[s] * (1 - w) + curl * w
        for s, S in (('Left', 'L'), ('Right', 'R')):
            rigext.hand_pose(arm, S, curl=curls[s], thumb=0.25 + 0.3 * curls[s])

    def orient_hand(self, side, palm_w, fing_w, w=1.0):
        """Turn the hand so that its fingers point along fing_w and its palm faces palm_w (world directions)."""
        R0, f0, p0 = self.rest_hand[side]
        Ma = self.a.arm.matrix_world.to_3x3().normalized()
        Mi = Ma.inverted()
        f1 = (Mi @ Vector(fing_w)).normalized()
        p1 = Mi @ Vector(palm_w)
        p1 = (p1 - f1 * p1.dot(f1)).normalized()
        B0 = Matrix((f0, p0, f0.cross(p0))).transposed()
        B1 = Matrix((f1, p1, f1.cross(p1))).transposed()
        AC.set_world_rot(self.a.arm, f'{side}Hand', (Ma @ (B1 @ B0.inverted() @ R0)).normalized(), w)

    # ---- everything
    def pose(self, t):
        self.pose_body(t)
        self.pose_head(t)
        self.pose_arms(t)
        bpy.context.view_layer.update()

    def eyes(self, t, deg_per_unit=28.0):
        """Eye shape keys so that the painted eyes look at the gaze target from where the head is pointing now."""
        if not self.gaze:
            return {}
        a, arm = self.a, self.a.arm
        hb = arm.pose.bones['Head']
        M = (arm.matrix_world @ hb.matrix).to_3x3().normalized()
        fwd = (M @ Vector(a.face_fwd)).normalized()
        u = Vector((0, 0, 1))
        rgt = fwd.cross(u).normalized()                     # the character's right, seen from behind
        up = rgt.cross(fwd).normalized()
        eye_c = AC.joint(arm, 'headfront') + up * 0.02
        d = (self.gaze.eye_target(t) - eye_c).normalized()
        yaw = math.degrees(math.atan2(d.dot(rgt), d.dot(fwd)))       # + = to the character's right
        pitch = math.degrees(math.atan2(d.dot(up), d.dot(fwd)))
        k = 1.0 / deg_per_unit
        out = {}
        if yaw > 0:
            out['eyeLookRight_L'] = out['eyeLookRight_R'] = min(1.0, yaw * k)
        else:
            out['eyeLookLeft_L'] = out['eyeLookLeft_R'] = min(1.0, -yaw * k)
        if pitch > 0:
            out['eyeLookUp_L'] = out['eyeLookUp_R'] = min(1.0, pitch * k * 1.2)
        else:
            out['eyeLookDown_L'] = out['eyeLookDown_R'] = min(1.0, -pitch * k * 1.1)
        return out
