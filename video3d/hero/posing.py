"""Pose / behaviour pass: pose presets applied to the rig. Entry points: apply(ch, name), gaze(ch, target).

Rig: MakeHuman default skeleton (163 bones). Useful bones: root, spine05..spine01 (pelvis -> chest), neck01..03, head, jaw,
eye.L/R, clavicle.L/R, shoulder01.L/R, upperarm01/02.L/R, lowerarm01/02.L/R, wrist.L/R, metacarpal1-4, finger1-5-1..3.L/R
(finger1 = thumb), upperleg01/02.L/R, lowerleg01/02.L/R, foot.L/R, toe*. The character faces -Y; its left side is +X.
Low-level helpers live in mh.py: pb, aim, rot, rotate_arm_space, pose_limb (2-bone IK), curl_fingers."""
import bpy
from mathutils import Vector

import cfg_pose as CP
import mh


def pose_seated(ch, P):
    """P: dict with hip (world), knee spread, feet, arms, spine lean, head yaw/pitch, gaze target."""
    rig = ch['rig']
    pb = lambda n: rig.pose.bones[n]
    # legs
    for s, sx in (('L', 1), ('R', -1)):
        hip = pb(f'upperleg01.{s}').head.copy()
        ankle = hip + Vector((sx * P['feet_spread'][s], -P['feet_fwd'], -P['shin_drop']))
        pole = hip + Vector((sx * 0.3, -1, 0.6))
        mh.pose_limb(ch, [f'upperleg01.{s}', f'upperleg02.{s}'], [f'lowerleg01.{s}', f'lowerleg02.{s}'], ankle, pole)
        mh.aim(pb(f'foot.{s}'), Vector((sx * P.get('toe_out', 0.15), -1, -0.42)))
    # spine lean (positive = forward)
    for n, k in (('spine05', 0.35), ('spine04', 0.25), ('spine03', 0.2), ('spine02', 0.2)):
        mh.rot(pb(n), (1, 0, 0), P['lean'] * k)
    for n, k in (('spine04', 0.3), ('spine03', 0.35), ('spine02', 0.35)):
        mh.rot(pb(n), (0, 0, 1), P.get('twist', 0) * k)
    if P.get('shrug'):
        for s, sx in (('L', 1), ('R', -1)):
            mh.rot(pb(f'clavicle.{s}'), (0, 1, 0), -sx * P['shrug'])
    # place the rig so the hips sit on the seat
    bpy.context.view_layer.update()
    hipL = pb('upperleg01.L').head
    hipR = pb('upperleg01.R').head
    mid = (hipL + hipR) / 2
    rig.location = Vector(P['hip']) - mid
    bpy.context.view_layer.update()
    # arms (targets in world space)
    for s, sx in (('L', 1), ('R', -1)):
        a = P['arms'][s]
        sh_w = rig.matrix_world @ pb(f'upperarm01.{s}').head
        if a['mode'] == 'knee':
            knee = rig.matrix_world @ pb(f'lowerleg01.{s}').head
            wrist = knee + Vector((-sx * 0.01, 0.085, 0.075))
            hand_dir = Vector((0, -1, -0.65))
        else:
            wrist = Vector(a['wrist'])
            hand_dir = Vector(a['hand_dir'])
        pole = sh_w + Vector(a['pole'])
        inv = rig.matrix_world.inverted()
        mh.pose_limb(ch, [f'upperarm01.{s}', f'upperarm02.{s}'], [f'lowerarm01.{s}', f'lowerarm02.{s}'], inv @ wrist, inv @ pole)
        mh.aim(pb(f'wrist.{s}'), hand_dir)
        if a.get('wrist_roll'):
            mh.rot(pb(f'wrist.{s}'), hand_dir, a['wrist_roll'])
        mh.curl_fingers(ch, s, a.get('curl', 0.8), a.get('thumb', 0.6))
    # neck & head
    for n, k in (('neck01', 0.2), ('neck02', 0.3), ('head', 0.5)):
        mh.rot(pb(n), (0, 0, 1), P['head_yaw'] * k)
    for n, k in (('neck02', 0.4), ('head', 0.6)):
        right = (rig.matrix_world.to_3x3() @ (pb(n).matrix.to_3x3() @ Vector((1, 0, 0)))).normalized()
        mh.rot(pb(n), right, P['head_pitch'] * k)
    if P.get('head_roll'):
        fwd = (pb('head').matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
        mh.rot(pb('head'), fwd, P['head_roll'])
    # eyes look at a world point
    if P.get('gaze'):
        for s in 'LR':
            e = pb(f'eye.{s}')
            eh = rig.matrix_world @ e.head
            mh.aim(e, rig.matrix_world.inverted().to_3x3() @ (Vector(P['gaze']) - eh))
    bpy.context.view_layer.update()


def gaze(ch, target):
    """Aim both eyes at a world-space point."""
    rig = ch['rig']
    for s in 'LR':
        e = rig.pose.bones[f'eye.{s}']
        e.rotation_mode = 'QUATERNION'
        e.rotation_quaternion = (1, 0, 0, 0)
        bpy.context.view_layer.update()
        eh = rig.matrix_world @ e.head
        mh.aim(e, rig.matrix_world.inverted().to_3x3() @ (Vector(target) - eh))
    bpy.context.view_layer.update()


def apply(ch, name='seated'):
    """Put the character in a named pose preset from cfg_pose.POSES."""
    pose_seated(ch, dict(CP.POSES[name]))
