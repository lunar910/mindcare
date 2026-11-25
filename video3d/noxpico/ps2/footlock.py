"""Feet that stay where they are planted.   import footlock

    lock = footlock.FootLock(actor)
    lock.capture()                 the current pose of the actor gives the planted position and orientation of each foot
    lock.apply(w=1.0)              after the body has been posed for a frame: legs re-solved so the ankles are on their marks

A motion clip of someone standing lets the feet drift by centimetres as the hips sway (and cross-fading two clips makes
them glide).  Here the ankles are pinned in the world; the hips keep the sway of the clip, the knees follow by
two-bone IK, and the feet keep the orientation they had when they were planted.  If the hips wander further than the
legs can reach, the hips are pulled back just enough."""
import bpy
from mathutils import Vector

import acting as AC

LEGS = {'Left': ('LeftUpLeg', 'LeftLeg', 'LeftFoot'), 'Right': ('RightUpLeg', 'RightLeg', 'RightFoot')}


class FootLock:
    def __init__(self, actor, stretch=0.985):
        self.actor, self.arm = actor, actor.arm
        self.pos, self.rot, self.len = {}, {}, {}
        self.stretch = stretch                       # the leg is never straightened beyond this share of its length

    def capture(self, sides=('Left', 'Right'), floor=None):
        """Plant the feet where they are now.  floor: ankle height to use (keeps both feet level with the ground)."""
        bpy.context.view_layer.update()
        for s in sides:
            up, lo, ft = LEGS[s]
            p = AC.joint(self.arm, ft).copy()
            if floor is not None:
                p.z = floor
            self.pos[s] = p
            self.rot[s] = AC.world_rot(self.arm, ft)
            self.len[s] = (AC.joint(self.arm, up) - AC.joint(self.arm, lo)).length + (AC.joint(self.arm, lo) - AC.joint(self.arm, ft)).length
        return self

    def set(self, side, pos, rot=None):
        self.pos[side] = Vector(pos)
        if rot is not None:
            self.rot[side] = rot

    def apply(self, w=1.0, sides=('Left', 'Right')):
        if w <= 0.0 or not self.pos:
            return
        arm = self.arm
        # 1. hips within reach of both planted feet
        for _ in range(2):
            worst, move = 0.0, Vector((0, 0, 0))
            for s in sides:
                up = LEGS[s][0]
                d = self.pos[s] - AC.joint(arm, up)
                over = d.length - self.len[s] * self.stretch
                if over > worst:
                    worst, move = over, d.normalized() * over
            if worst <= 1e-5:
                break
            AC.translate(arm, 'Hips', move * w)
        # 2. legs: ankle on its mark, knee where the clip points it, foot flat as planted
        for s in sides:
            up, lo, ft = LEGS[s]
            hip, knee = AC.joint(arm, up), AC.joint(arm, lo)
            ankle = AC.joint(arm, ft)
            axis = (ankle - hip).normalized()
            bend = knee - hip
            bend = bend - axis * bend.dot(axis)                      # which way the knee points in the clip
            if bend.length < 1e-4:
                f, _, _ = AC.body_frame(self.actor)
                bend = f
            pole = hip + (self.pos[s] - hip) * 0.5 + bend.normalized() * 0.5
            AC.ik2(arm, up, lo, ft, self.pos[s], pole, w)
            AC.set_world_rot(arm, ft, self.rot[s], w)
