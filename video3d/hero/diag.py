"""Diagnostic and final renders of the hero.

    python diag.py OUTDIR view [view ...]

Studio views (neutral grey studio, character in rest A-pose, no room; fast):
    face_front face_q face_side face_low eye mouth      head close-ups (640x640)
    hair_front hair_q hair_side hair_back hair_top      head from further away (640x640)
    body_front body_q body_side body_back               full body (540x720)
    torso_front torso_back hand_l hand_r feet           close-ups
Room views (seated in the living room with the final warm lighting; 640x480 like the final video frames):
    room_close room_portrait room_medium room_wide room_side room_top room_low
Do not mix studio and room views in one run.

Environment variables: SAMPLES (default 32), SCALE (resolution multiplier, default 1), POSE (pose preset, default 'seated'),
NOHAIR=1, NOCLOTHES=1, SAVE_BLEND=1 (writes OUTDIR/scene.blend)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector

import herolib

OUT = sys.argv[1]
VIEWS = sys.argv[2:]
SAMPLES = int(os.environ.get('SAMPLES', 32))
SCALE = float(os.environ.get('SCALE', 1))
room_mode = all(v.startswith('room_') for v in VIEWS)
assert room_mode or not any(v.startswith('room_') for v in VIEWS), 'do not mix studio and room views'
t0 = time.time()
herolib.reset()
os.makedirs(OUT, exist_ok=True)
R = None
if room_mode:
    import room_bl
    R = room_bl.build_room()
ch = herolib.build_character(hair=not os.environ.get('NOHAIR'), clothes=not os.environ.get('NOCLOTHES'))
print('character built', round(time.time() - t0, 1), 's')
cam = herolib.camera()
V = Vector


def size(w, h):
    herolib.setup_cycles(int(w * SCALE), int(h * SCALE), SAMPLES)


if room_mode:
    herolib.pose(ch, os.environ.get('POSE', 'seated'))
    import posing
    herolib.room_lighting(R)
    e0 = herolib.eyes_mid(ch)
    herolib.area('rim', e0 + V((0.9, 0.9, 0.5)), e0, 30, (0.5, 0.62, 1.0), 0.5)
    size(640, 480)
    for v in VIEWS:
        e = herolib.eyes_mid(ch)
        hips = herolib.bone_world(ch, 'spine05')
        gaze_cam = True
        if v == 'room_close':
            pos, tgt, fov, key = e + V((-0.3, -0.66, -0.015)), e + V((0.005, 0.03, -0.022)), 20, (e + V((-0.8, -0.5, 0.3)), e, 12, 0.8)
        elif v == 'room_portrait':
            pos, tgt, fov, key = e + V((-0.42, -0.86, 0.03)), e + V((0.0, 0.03, -0.035)), 22, (e + V((-0.8, -0.55, 0.35)), e, 12, 0.8)
        elif v == 'room_medium':
            pos, tgt, fov, key = V((-0.45, -0.75, 1.1)), V((0.03, 1.15, 0.9)), 38, (V((-1.0, -0.3, 1.6)), V((0, 1.1, 1.0)), 55, 1.0)
        elif v == 'room_wide':
            pos, tgt, fov, key = V((0.0, -2.05, 1.06)), V((0.0, 1.0, 0.9)), 38, (V((-1.0, -0.6, 2.0)), V((0, 1.1, 0.9)), 110, 1.2)
        elif v == 'room_side':
            pos, tgt, fov, key = hips + V((-2.4, -0.25, 0.35)), hips + V((0, -0.15, 0.2)), 34, (hips + V((-1.5, -1.5, 1.5)), hips, 160, 1.2)
            gaze_cam = False
        elif v == 'room_top':
            pos, tgt, fov, key = hips + V((0.0, -0.5, 2.3)), hips + V((0, -0.2, 0.0)), 40, (hips + V((-1.0, -1.0, 2.0)), hips, 160, 1.2)
            gaze_cam = False
        elif v == 'room_low':
            pos, tgt, fov, key = V((0.5, -1.6, 0.35)), hips + V((0, -0.2, 0.05)), 40, (V((-1.0, -0.6, 1.6)), hips, 110, 1.2)
            gaze_cam = False
        else:
            raise SystemExit('unknown view ' + v)
        k = herolib.area('key', key[0], key[1], key[2], herolib.WARM, key[3])
        if gaze_cam:
            posing.gaze(ch, pos)
        herolib.aim_camera(cam, pos, tgt, fov)
        herolib.render(os.path.join(OUT, v + '.png'))
        bpy.data.objects.remove(k)
        print('rendered', v, round(time.time() - t0, 1), 's')
else:
    herolib.studio_world()
    co = [ch['body'].matrix_world @ v.co for v in ch['body'].data.vertices]
    zmin, zmax = min(c.z for c in co), max(c.z for c in co)
    mid = V((0, 0, (zmin + zmax) / 2))
    e = herolib.eyes_mid(ch)
    herolib.area('rim', e + V((0.7, 0.6, 0.3)), e, 18, (0.6, 0.72, 1.0), 0.5)
    key = None
    for v in VIEWS:
        if key:
            bpy.data.objects.remove(key)
        if v.startswith(('face_', 'eye', 'mouth', 'hair_')):
            key = herolib.area('key', e + V((-0.5, -0.9, 0.45)), e, 15, (1.0, 0.93, 0.85), 0.8)
            size(640, 640)
            far = 1.25 if v.startswith('hair_') else 1.05
            fov = 16.0
            table = {
                'face_front': ((0, -far, 0.0), (0, 0, -0.02)), 'face_q': ((-0.57 * far, -0.82 * far, 0.02), (0, 0, -0.02)),
                'face_side': ((-far, 0.05, 0.0), (0, 0.05, -0.02)), 'face_low': ((-0.3, -0.9, -0.5), (0, 0, -0.03)),
                'eye': ((-0.1, -1.05, 0.0), (0, 0, 0.0)), 'mouth': ((-0.08, -1.05, -0.06), (0, 0, -0.065)),
                'hair_front': ((0, -far, 0.0), (0, 0.02, 0.0)), 'hair_q': ((-0.57 * far, -0.82 * far, 0.03), (0, 0.02, 0.0)),
                'hair_side': ((-far, 0.08, 0.0), (0, 0.08, 0.0)), 'hair_back': ((0.4 * far, 0.96 * far, 0.08), (0, 0.06, 0.0)),
                'hair_top': ((0.0, -0.6 * far, 0.85 * far), (0, 0.05, 0.02)),
            }
            if v not in table:
                raise SystemExit('unknown view ' + v)
            off, toff = table[v]
            if v in ('eye', 'mouth'):
                fov = 6.8
            herolib.aim_camera(cam, e + V(off), e + V(toff), fov)
        elif v.startswith('body_'):
            key = herolib.area('key', mid + V((-1.5, -2.5, 1.2)), mid, 300, (1, 0.95, 0.9), 1.5)
            size(540, 720)
            off = {'body_front': (0.0, -4.6, 0.1), 'body_q': (-2.8, -3.6, 0.3), 'body_side': (-4.6, 0.0, 0.1), 'body_back': (0.6, 4.6, 0.1)}[v]
            if v == 'body_back':
                bpy.data.objects.remove(key)
                key = herolib.area('key', mid + V((1.5, 2.5, 1.2)), mid, 300, (1, 0.95, 0.9), 1.5)
            herolib.aim_camera(cam, mid + V(off), mid, 26)
        elif v in ('torso_front', 'torso_back'):
            c = herolib.bone_world(ch, 'spine02')
            s = -1 if v == 'torso_front' else 1
            key = herolib.area('key', c + V((-1.0 * -s, 1.8 * s, 0.8)), c, 150, (1, 0.95, 0.9), 1.2)
            size(640, 640)
            herolib.aim_camera(cam, c + V((0.25 * s, 2.3 * s, 0.1)), c + V((0, 0, 0.02)), 22)
        elif v in ('hand_l', 'hand_r'):
            sd = 'L' if v == 'hand_l' else 'R'
            c = herolib.bone_world(ch, f'wrist.{sd}', tail=True)
            key = herolib.area('key', c + V((0, -0.8, 0.6)), c, 25, (1, 0.95, 0.9), 0.6)
            size(640, 640)
            herolib.aim_camera(cam, c + V((0.05, -0.75, 0.45)), c, 14)
        elif v == 'feet':
            c = (herolib.bone_world(ch, 'foot.L') + herolib.bone_world(ch, 'foot.R')) / 2
            key = herolib.area('key', c + V((-0.8, -1.2, 1.0)), c, 80, (1, 0.95, 0.9), 0.8)
            size(640, 480)
            herolib.aim_camera(cam, c + V((-0.7, -1.3, 0.45)), c + V((0, -0.05, -0.02)), 22)
        else:
            raise SystemExit('unknown view ' + v)
        herolib.render(os.path.join(OUT, v + '.png'))
        print('rendered', v, round(time.time() - t0, 1), 's')
if os.environ.get('SAVE_BLEND'):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene.blend'), compress=True)
print('done', round(time.time() - t0, 1), 's')
