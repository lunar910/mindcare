"""Animation test bench without rendering: joint trajectories, stick-figure strips, motion numbers.   import motionlab as ML

    W = ML.fast(E.build())                      hide the heavy meshes from pose evaluation (10 ms per frame instead of 36)
    T = ML.sample(E, W, times)                  {'pico.LeftHand': (n, 3) world positions, ...} for all JOINTS of both actors
    ML.strip(E, W, shot, t0, t1, fps, out_png)  stick figures seen through the shot's camera, one tile per frame
    ML.report(T, times)                         text: foot sliding, stillness, speeds, smoothness

The scene module E must provide build(), pose_at(W, t), camera_setup(W, cam, shot) and W['pico'] / W['nox'] actors
(cast2.Actor).  Nothing here touches the renderer, so it runs in seconds and several can run at once."""
import math

import bpy
import numpy as np
from PIL import Image, ImageDraw

JOINTS = ['Hips', 'Spine02', 'Spine01', 'Spine', 'neck', 'Head', 'head_end', 'headfront',
          'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand', 'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
          'LeftUpLeg', 'LeftLeg', 'LeftFoot', 'LeftToeBase', 'RightUpLeg', 'RightLeg', 'RightFoot', 'RightToeBase',
          'LeftFingers1', 'LeftFingers2', 'LeftThumb1', 'RightFingers1', 'RightFingers2', 'RightThumb1']
SEGMENTS = [('Hips', 'Spine02'), ('Spine02', 'Spine01'), ('Spine01', 'Spine'), ('Spine', 'neck'), ('neck', 'Head'), ('Head', 'head_end'), ('Head', 'headfront'),
            ('Spine', 'LeftShoulder'), ('LeftShoulder', 'LeftArm'), ('LeftArm', 'LeftForeArm'), ('LeftForeArm', 'LeftHand'), ('LeftHand', 'LeftFingers1'),
            ('LeftFingers1', 'LeftFingers2'), ('LeftHand', 'LeftThumb1'),
            ('Spine', 'RightShoulder'), ('RightShoulder', 'RightArm'), ('RightArm', 'RightForeArm'), ('RightForeArm', 'RightHand'), ('RightHand', 'RightFingers1'),
            ('RightFingers1', 'RightFingers2'), ('RightHand', 'RightThumb1'),
            ('Hips', 'LeftUpLeg'), ('LeftUpLeg', 'LeftLeg'), ('LeftLeg', 'LeftFoot'), ('LeftFoot', 'LeftToeBase'),
            ('Hips', 'RightUpLeg'), ('RightUpLeg', 'RightLeg'), ('RightLeg', 'RightFoot'), ('RightFoot', 'RightToeBase')]
COLORS = {'pico': ((240, 190, 40), (200, 60, 50)), 'nox': ((90, 170, 230), (40, 70, 140))}    # (left side / trunk, right side)


def fast(W):
    """Pose evaluation only: the skinned meshes are not updated (they still render normally)."""
    for k in ('pico', 'nox'):
        W[k].mesh.hide_viewport = True
    try:
        import ps2render as PR
        PR._STATE.setdefault('user_hidden', {})
        PR._STATE.setdefault('static', [])
        PR._STATE.setdefault('dynamic', [])
    except Exception:
        pass
    return W


def joints_now(W):
    out = {}
    for k in ('pico', 'nox'):
        a = W[k]
        pb = a.arm.pose.bones
        M = a.arm.matrix_world
        for j in JOINTS:
            if j in pb:
                out[f'{k}.{j}'] = tuple(M @ pb[j].head)
    return out


def sample(E, W, times):
    rows = []
    for t in times:
        E.pose_at(W, float(t))
        rows.append(joints_now(W))
    keys = rows[0].keys()
    return {k: np.array([r[k] for r in rows]) for k in keys}


def _camera(E, W, shot):
    import ps2render as PR
    cam = W.get('_lab_cam')
    if cam is None:
        cam = PR.camera('labcam')
        W['_lab_cam'] = cam
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    E.camera_setup(W, cam, shot)
    bpy.context.view_layer.update()
    return cam


def _project(cam, pts):
    """World points (n, 3) -> (n, 2) in 0..1 picture coordinates (x right, y down) and depth."""
    Mi = np.array(cam.matrix_world.inverted())
    p = pts @ Mi[:3, :3].T + Mi[:3, 3]
    z = -p[:, 2]
    f = 1.0 / math.tan(cam.data.angle / 2)                      # vertical field of view (sensor_fit VERTICAL)
    aspect = 1080 / 1920
    x = p[:, 0] / np.maximum(z, 1e-6) * f / aspect * 0.5 + 0.5
    y = 0.5 - p[:, 1] / np.maximum(z, 1e-6) * f * 0.5
    return np.stack([x, y], axis=1), z


def strip(E, W, shot, t0, t1, fps, out, cols=10, tile=(180, 320), actors=('pico', 'nox'), props=True, trails=('LeftHand', 'RightHand')):
    """Stick figures through the camera of `shot`; hand trails show the path of the last 0.5 s."""
    cam = _camera(E, W, shot)
    times = np.arange(t0, t1 - 1e-6, 1.0 / fps)
    w, h = tile
    rows = (len(times) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (w + 3), rows * (h + 3)), 'white')
    hist = {}
    floor = []
    if props and 'A' in W:
        try:
            AT = W['AT']
            b = AT.BENCH
            x0, x1, y0, y1, z = b['x'] - b['width'] / 2, b['x'] + b['width'] / 2, b['y'] - b['depth'] / 2, b['y'] + b['depth'] / 2, b['top']
            floor = [np.array([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), (x0, y0, z)]),
                     np.array([(x0, y0, 0), (x0, y0, z)]), np.array([(x1, y0, 0), (x1, y0, z)]),
                     np.array([(-1.95, 2.0, 0), (1.95, 2.0, 0)]), np.array([(-1.95, 2.0, 0), (-1.95, 2.0, 2.9), (1.95, 2.0, 2.9), (1.95, 2.0, 0)])]
            xa, xb = W['A']['doorway']
            floor.append(np.array([(xa, 2.0, 0), (xa, 2.0, 2.04), (xb, 2.0, 2.04), (xb, 2.0, 0)]))
        except Exception:
            floor = []
    for i, t in enumerate(times):
        E.pose_at(W, float(t))
        J = joints_now(W)
        im = Image.new('RGB', (w, h), (244, 244, 246))
        d = ImageDraw.Draw(im)
        for poly in floor:
            q, z = _project(cam, poly)
            if (z > 0.05).all():
                d.line([(float(a) * w, float(b) * h) for a, b in q], fill=(190, 190, 200), width=1)
        for k in actors:
            cl, cr = COLORS[k]
            for a, b in SEGMENTS:
                if f'{k}.{a}' not in J or f'{k}.{b}' not in J:
                    continue
                q, z = _project(cam, np.array([J[f'{k}.{a}'], J[f'{k}.{b}']]))
                if (z <= 0.05).any():
                    continue
                col = cr if a.startswith(('Right', 'RF', 'RT')) or b.startswith(('Right', 'RF', 'RT')) else cl
                d.line([(float(q[0, 0]) * w, float(q[0, 1]) * h), (float(q[1, 0]) * w, float(q[1, 1]) * h)], fill=col, width=3 if a in ('Head',) else 2)
            hd = np.array([J[f'{k}.Head'], J[f'{k}.head_end']])
            q, z = _project(cam, hd)
            if (z > 0.05).all():
                r = max(2.0, float(np.linalg.norm((q[1] - q[0]) * np.array([w, h]))) * 0.45)
                c = (q[0] + q[1]) / 2 * np.array([w, h])
                d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=cl, width=2)
            for tj in trails:
                key = f'{k}.{tj}'
                hist.setdefault(key, []).append(J[key])
                pts = np.array(hist[key][-max(2, int(0.5 * fps)):])
                if len(pts) > 1:
                    q, z = _project(cam, pts)
                    if (z > 0.05).all():
                        d.line([(float(a) * w, float(b) * h) for a, b in q], fill=(60, 160, 90), width=1)
        d.text((3, 2), f'{t:.2f}', fill=(40, 40, 40))
        sheet.paste(im, ((i % cols) * (w + 3), (i // cols) * (h + 3)))
    sheet.save(out)
    return out


def report(T, times, stand_from=None):
    """Plain-text numbers about a sampled animation.  stand_from = {'pico': t, 'nox': t}: from when each actor stands in place."""
    t = np.asarray(times, dtype=float)
    dt = float(np.median(np.diff(t)))
    stand_from = stand_from or {'pico': 2.6, 'nox': 0.0}
    out = []
    for k in ('pico', 'nox'):
        sel = t >= stand_from.get(k, 0.0)
        for foot in ('LeftFoot', 'RightFoot'):
            p = T[f'{k}.{foot}'][sel]
            v = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1) / dt
            path = float(v.sum() * dt)
            out.append(f'{k}.{foot}: horizontal travel while standing {path * 100:.1f} cm, mean speed {v.mean() * 100:.2f} cm/s, max {v.max() * 100:.1f} cm/s, '
                       f'height range {np.ptp(p[:, 2]) * 100:.1f} cm')
        for j in ('Head', 'LeftHand', 'RightHand', 'Hips'):
            p = T[f'{k}.{j}'][sel]
            v = np.linalg.norm(np.diff(p, axis=0), axis=1) / dt
            a = np.abs(np.diff(v)) / dt
            still = float((v < 0.02).mean())
            out.append(f'{k}.{j}: speed median {np.median(v) * 100:.1f} cm/s, p90 {np.percentile(v, 90) * 100:.1f}, max {v.max() * 100:.0f}; still (<2 cm/s) {still * 100:.0f} % of the time; '
                       f'acceleration p99 {np.percentile(a, 99):.1f} m/s2')
    return '\n'.join(out)
