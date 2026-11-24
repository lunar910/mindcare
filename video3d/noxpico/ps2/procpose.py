"""Procedural pose layers that work with Meshy rigs (whose bone tails are arbitrary): everything is computed from the
positions of the joints (bone heads) in world space, and applied by rotating pose bones about their head.

    rotate_bone_world(arm, bone, q_world)                  rotate a pose bone (and its children) by a world rotation
    two_bone_ik(arm, upper, lower, end, target, pole, w)  place the end joint (wrist) on target, elbow towards pole
    look_at(arm, bone, fwd_local, target, w, limit_deg)   turn a bone so that its forward axis points at target"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector


def _upd():
    bpy.context.view_layer.update()


def joint(arm, bone):
    return arm.matrix_world @ arm.pose.bones[bone].head


def rotate_bone_world(arm, bone, q_world):
    pb = arm.pose.bones[bone]
    Mw = arm.matrix_world @ pb.matrix                       # bone world matrix (posed)
    piv = Mw.translation.copy()
    R = q_world.to_matrix().to_4x4()
    new = Matrix.Translation(piv) @ R @ Matrix.Translation(-piv) @ Mw
    pb.matrix = arm.matrix_world.inverted() @ new
    pb.scale = (1.0, 1.0, 1.0)          # a rotation never scales a bone: drop the rounding error (it compounds otherwise)
    _upd()


def _rot_between(a, b, w=1.0):
    a, b = a.normalized(), b.normalized()
    q = a.rotation_difference(b)
    return Quaternion().slerp(q, w) if w < 1.0 else q


def two_bone_ik(arm, upper, lower, end, target, pole, w=1.0):
    if w <= 0.0:
        return
    S, E, Wr = joint(arm, upper), joint(arm, lower), joint(arm, end)
    a, b = (E - S).length, (Wr - E).length
    T = Vector(target)
    d = T - S
    L = max(min(d.length, a + b - 1e-4), abs(a - b) + 1e-4)
    dn = d.normalized()
    # elbow on the circle, towards the pole
    x = (a * a - b * b + L * L) / (2 * L)
    r = math.sqrt(max(a * a - x * x, 0.0))
    pv = Vector(pole) - S
    pv = (pv - dn * pv.dot(dn)).normalized()
    E_new = S + dn * x + pv * r
    rotate_bone_world(arm, upper, _rot_between(E - S, E_new - S, w))
    S, E, Wr = joint(arm, upper), joint(arm, lower), joint(arm, end)
    T_eff = S + dn * L
    tgt = Wr.lerp(T_eff if (T - S).length > a + b else T, w)
    rotate_bone_world(arm, lower, _rot_between(Wr - E, tgt - E, 1.0))


def look_at(arm, bone, fwd_local, target, w=1.0, limit_deg=60.0):
    if w <= 0.0:
        return
    pb = arm.pose.bones[bone]
    Mw = arm.matrix_world @ pb.matrix
    fwd = (Mw.to_3x3() @ Vector(fwd_local)).normalized()
    want = (Vector(target) - Mw.translation).normalized()
    q = fwd.rotation_difference(want)
    ang = q.angle
    if ang > math.radians(limit_deg):
        q = Quaternion(q.axis, math.radians(limit_deg))
    rotate_bone_world(arm, bone, Quaternion().slerp(q, w))
