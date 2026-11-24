"""Shared maths and bone helpers for the acting layers (version 4 of the animation).   import acting as AC

Everything is a pure function of time: a frame can be evaluated on its own, in any order (three render workers start
at different frames).  What needs memory (springs, lags) is baked once over the whole timeline with bake().

Timing:   minjerk(x)                 0..1 -> 0..1, the velocity profile of real reaching movements (bell shaped)
          bump(t, t0, rise, hold, fall)        0 -> 1 -> hold -> 0 with minimum-jerk flanks
          curve(keys, t)             [(t, value), ...] scalars, tuples or Vectors, minimum-jerk between keys
          noise(t, seed, f, octaves) smooth 1/f-like value noise in -1..1, deterministic
          bake(fn, t_end, rate)      sample a function of time; Baked.at(t) reads it back (linear)
          spring_follow(x, rate, halflife)     critically damped follower of a sampled signal (for lag and settle)
Bones (Meshy rigs have arbitrary bone tails, so everything goes through joint positions and world rotations):
          joint(arm, bone)                           world position of the joint at the head of a bone
          rotate(arm, bone, q_world)                 rotate a bone and its children about its joint
          translate(arm, bone, delta_world)          move a bone (the hips) in world space
          aim(arm, bone, child, direction, w)        swing a bone so that bone->child points along direction
          world_rot(arm, bone) / set_world_rot(arm, bone, R)   3x3 world orientation of a bone
          ik2(arm, upper, lower, end, target, pole, w)  two-bone IK on joint positions (arms and legs)
          yaw_pitch(arm, bone, yaw, pitch, roll, frame)  rotate a bone by angles about the character's own axes
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import procpose as PP


# ------------------------------------------------------------------ timing
def minjerk(x):
    x = min(max(float(x), 0.0), 1.0)
    return x * x * x * (10.0 - 15.0 * x + 6.0 * x * x)


def snappy(x, p=0.6):
    """0..1 -> 0..1 with zero speed at both ends but the peak speed early (about 30 % of the way through): the fast
    start and long settle of the reference's turns and strokes (50 % done in ~0.3 of the time)."""
    x = min(max(float(x), 0.0), 1.0)
    return minjerk(x ** p)


def bump(t, t0, rise, hold, fall):
    if t <= t0 or t >= t0 + rise + hold + fall:
        return 0.0
    if t < t0 + rise:
        return minjerk((t - t0) / rise)
    if t < t0 + rise + hold:
        return 1.0
    return 1.0 - minjerk((t - t0 - rise - hold) / fall)


def _lerp(a, b, w):
    if isinstance(a, (int, float)):
        return a + (b - a) * w
    if isinstance(a, Vector):
        return a.lerp(Vector(b), w)
    return type(a)(x + (y - x) * w for x, y in zip(a, b))


def curve(keys, t, ease=minjerk):
    """Piecewise interpolation of [(time, value), ...]; values are numbers, tuples or Vectors."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return _lerp(v0, v1, ease((t - t0) / max(t1 - t0, 1e-9)))
    return keys[-1][1]


def _hash(i, seed):
    x = math.sin(i * 127.1 + seed * 311.7) * 43758.5453
    return (x - math.floor(x)) * 2.0 - 1.0


def noise(t, seed=0.0, f=1.0, octaves=3):
    """Smooth pseudo-random signal in about -1..1; f = base frequency in Hz; each octave is twice as fast, half as big."""
    out, amp, tot = 0.0, 1.0, 0.0
    for o in range(octaves):
        x = t * f * (2 ** o)
        i = math.floor(x)
        u = x - i
        u = u * u * u * (u * (u * 6 - 15) + 10)
        out += amp * (_hash(i, seed + 17.0 * o) * (1 - u) + _hash(i + 1, seed + 17.0 * o) * u)
        tot += amp
        amp *= 0.5
    return out / tot


class Baked:
    def __init__(self, values, rate):
        self.v, self.rate = np.asarray(values, dtype=np.float64), rate

    def at(self, t):
        x = min(max(t * self.rate, 0.0), len(self.v) - 1.0)
        i = int(x)
        j = min(i + 1, len(self.v) - 1)
        return self.v[i] * (1 - (x - i)) + self.v[j] * (x - i)


def bake(fn, t_end, rate=60.0):
    n = int(math.ceil(t_end * rate)) + 1
    return Baked([fn(k / rate) for k in range(n)], rate)


def spring_follow(x, rate, halflife):
    """Critically damped spring following the samples x (n, ...) -> same shape.  halflife in seconds (0.05-0.3)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.empty_like(x)
    v = np.zeros_like(x[0])
    p = x[0].copy()
    d = 2.0 * 0.69314718 / max(halflife, 1e-5)              # damping from half-life (critically damped)
    dt = 1.0 / rate
    e = math.exp(-0.5 * d * dt)
    for k in range(len(x)):
        j0 = p - x[k]
        j1 = v + j0 * (0.5 * d)
        p = e * (j0 + j1 * dt) + x[k]
        v = e * (v - j1 * (0.5 * d) * dt)
        y[k] = p
    return y


# ------------------------------------------------------------------ bones
def joint(arm, bone):
    return arm.matrix_world @ arm.pose.bones[bone].head


def rotate(arm, bone, q_world):
    PP.rotate_bone_world(arm, bone, q_world)


def translate(arm, bone, delta):
    pb = arm.pose.bones[bone]
    Mw = arm.matrix_world @ pb.matrix
    Mw.translation = Mw.translation + Vector(delta)
    pb.matrix = arm.matrix_world.inverted() @ Mw
    pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def reset_pose(arm, keep=()):
    """Every pose bone back to rest (location, rotation, scale), except the names in keep: run before posing a frame so
    that nothing from the previous frame survives."""
    for pb in arm.pose.bones:
        pb.scale = (1.0, 1.0, 1.0)
        if pb.name in keep:
            continue
        pb.location = (0.0, 0.0, 0.0)
        if pb.rotation_mode == 'QUATERNION':
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        else:
            pb.rotation_euler = (0.0, 0.0, 0.0)


def world_rot(arm, bone):
    return (arm.matrix_world @ arm.pose.bones[bone].matrix).to_3x3().normalized()


def set_world_rot(arm, bone, R, w=1.0):
    """Give a bone the world orientation R (3x3), fully or by a fraction w."""
    cur = world_rot(arm, bone)
    q = (R @ cur.inverted()).to_quaternion()
    if w < 1.0:
        q = Quaternion().slerp(q, w)
    PP.rotate_bone_world(arm, bone, q)


def aim(arm, bone, child, direction, w=1.0):
    a = (joint(arm, child) - joint(arm, bone)).normalized()
    b = Vector(direction).normalized()
    q = a.rotation_difference(b)
    if w < 1.0:
        q = Quaternion().slerp(q, w)
    PP.rotate_bone_world(arm, bone, q)


def ik2(arm, upper, lower, end, target, pole, w=1.0):
    PP.two_bone_ik(arm, upper, lower, end, target, pole, w)


def body_frame(actor):
    """(forward, right, up) of the character in the world: forward is where it faces, right is its own right hand side."""
    th = actor.heading
    f = Vector((math.sin(th), -math.cos(th), 0.0))
    return f, Vector((-f.y, f.x, 0.0)) * -1.0, Vector((0.0, 0.0, 1.0))


def yaw_pitch(arm, bone, yaw=0.0, pitch=0.0, roll=0.0, frame=None):
    """Rotate a bone by angles in degrees about the character's axes: yaw to its left (+), pitch down (+, a nod), roll to its right shoulder (+)."""
    f, r, u = frame
    if yaw:
        PP.rotate_bone_world(arm, bone, Quaternion(u, math.radians(yaw)))
    if pitch:
        PP.rotate_bone_world(arm, bone, Quaternion(r, math.radians(-pitch)))
    if roll:
        PP.rotate_bone_world(arm, bone, Quaternion(f, math.radians(roll)))
