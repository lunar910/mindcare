"""Seated acting for version 5: Nox on his swivel stool at the workbench.

The clips are standing clips, so sitting is built on top of them each frame:
  1. the upper body comes from the clip (posture, breathing, gaze, gestures as usual);
  2. the pelvis is moved onto the seat (hip joints ~9 cm above the cushion, a little in front of the column) and tilted
     back a few degrees, as a real seated pelvis is;
  3. the legs are solved with two-bone IK: thighs about level, shins about vertical, feet flat on the floor (their
     standing world orientation is kept), knees a little apart;
  4. the trunk leans forward FROM THE HIPS with a fairly straight back (lean_keys): leaning over work is a hinge at the
     hips, not a hunched upper back.
The stool swivels: heading_keys turn the whole body about the seat pivot; the feet lift a little while it turns.

    P = seat5.SeatedPerformer(actor, base, pivot=(x, y), seat_z=0.52, heading=..., heading_keys=[(t, rad)],
                              lean_keys=[(t, deg)], gaze=..., gestures=..., accents=..., life=..., extra=...)
"""
import math

import bpy
from mathutils import Quaternion, Vector

import acting as AC
import perform as PF
import procpose as PP


class SeatedPerformer(PF.Performer):
    def __init__(self, actor, base, pivot, seat_z, heading, lean_keys=None, hip_fwd=0.035, hip_up=0.095,
                 pelvis_tilt=7.0, foot_fwd=0.36, knee_out=0.06, foot_out=0.045, ankle_z=None, swivel_lift=0.05,
                 seat_offset_keys=None, **kw):
        kw.setdefault('lock_from', 1e9)
        super().__init__(actor, base, tuple(pivot), heading, **kw)
        self.pivot = Vector((pivot[0], pivot[1], 0.0))
        self.seat_z = seat_z
        self.lean_keys = lean_keys or [(0.0, 0.0)]
        self.hip_fwd, self.hip_up, self.pelvis_tilt = hip_fwd, hip_up, pelvis_tilt
        self.foot_fwd, self.knee_out, self.foot_out = foot_fwd, knee_out, foot_out
        self.ankle_z = ankle_z
        self.swivel_lift = swivel_lift
        self.seat_offset_keys = seat_offset_keys        # [(t, (fwd, side))]: sliding forward on the seat to work, etc.
        self._foot_rest = None

    # the heading speed (rad/s) tells when the stool is turning
    def _turning(self, t):
        if not self.heading_keys:
            return 0.0
        dt = 1 / 60
        return abs(AC.curve(self.heading_keys, t + dt) - AC.curve(self.heading_keys, t - dt)) / (2 * dt)

    def prepare(self, t_end):
        if self.gaze:
            self.gaze.prepare(t_end)
        self.base.calibrate(self.mark)
        self.locked = False
        # the feet's standing orientation in the body frame (flat on the floor, pointing forward)
        a, arm = self.a, self.a.arm
        AC.reset_pose(arm)
        a.pose(self.base.sample(0.0), self.base.bones)
        a.place(self.mark, 0.0)
        bpy.context.view_layer.update()
        self._foot_rest = {s: AC.world_rot(arm, f'{s}Foot').copy() for s in ('Left', 'Right')}
        self._ankle_rest = min(AC.joint(arm, 'LeftFoot').z, AC.joint(arm, 'RightFoot').z)

    def sit(self, t):
        a, arm = self.a, self.a.arm
        f, r, u = AC.body_frame(a)
        # 2. pelvis onto the seat
        hl, hr = AC.joint(arm, 'LeftUpLeg'), AC.joint(arm, 'RightUpLeg')
        mid = (hl + hr) / 2
        fwd, side = (0.0, 0.0)
        if self.seat_offset_keys:
            fwd, side = AC.curve(self.seat_offset_keys, t)
        want = self.pivot + f * (self.hip_fwd + fwd) + r * side + Vector((0, 0, self.seat_z + self.hip_up))
        AC.translate(arm, 'Hips', want - mid)
        PP.rotate_bone_world(arm, 'Hips', Quaternion(r, math.radians(self.pelvis_tilt)))     # posterior tilt
        # counter the tilt in the lower spine so the trunk stays upright, then lean from the hips
        lean = AC.curve(self.lean_keys, t)
        PP.rotate_bone_world(arm, 'Spine02', Quaternion(r, math.radians(-self.pelvis_tilt - 0.65 * lean)))
        PP.rotate_bone_world(arm, 'Spine01', Quaternion(r, math.radians(-0.25 * lean)))
        PP.rotate_bone_world(arm, 'Spine', Quaternion(r, math.radians(-0.10 * lean)))
        bpy.context.view_layer.update()
        # 3. legs: feet flat on the floor in front of the knees, a little apart
        turn = self._turning(t)
        lift = self.swivel_lift * min(1.0, turn / 2.5)
        ankle = (self.ankle_z if self.ankle_z is not None else self._ankle_rest) + lift
        q_head = Quaternion((0, 0, 1), a.heading)
        for s, sgn in (('Left', -1.0), ('Right', 1.0)):
            hip = AC.joint(arm, f'{s}UpLeg')
            out = r * sgn
            foot = Vector((hip.x, hip.y, 0.0)) + f * self.foot_fwd + out * self.foot_out
            foot.z = ankle
            pole = hip + f * 0.9 + out * self.knee_out * 4 + u * 0.25
            AC.ik2(arm, f'{s}UpLeg', f'{s}Leg', f'{s}Foot', foot, pole)
            R = q_head.to_matrix() @ self._foot_rest[s]
            AC.set_world_rot(arm, f'{s}Foot', R)
        bpy.context.view_layer.update()

    def pose_body(self, t, lock=True):
        a = self.a
        arm = a.arm
        AC.reset_pose(arm)
        a.pose(self.base.sample(t), self.base.bones)
        a.place((self.pivot.x, self.pivot.y), self.heading_at(t))
        bpy.context.view_layer.update()
        self.sit(t)
        f, r, u = AC.body_frame(a)
        L = self.life
        if self.hips_yaw:
            PP.rotate_bone_world(arm, 'Spine02', Quaternion(u, math.radians(AC.curve(self.hips_yaw, t))))
        b, deg = L.breath(t)
        PP.rotate_bone_world(arm, 'Spine01', Quaternion(r, math.radians(-0.6 * deg * b)))
        PP.rotate_bone_world(arm, 'Spine', Quaternion(r, math.radians(-0.4 * deg * b)))
        lift = L.lift(t)
        for s, sx in (('Left', -1), ('Right', 1)):
            PP.rotate_bone_world(arm, f'{s}Shoulder', Quaternion(f, math.radians(sx * (0.5 * deg * max(b, 0.0) + 3.6 * lift))))
        if lift:
            PP.rotate_bone_world(arm, 'Spine01', Quaternion(r, math.radians(-0.8 * lift)))
        if self.extra:
            self.extra(self, t, 'body')
