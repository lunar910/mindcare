"""Extend a Meshy biped rig (24 bones, mitten hands) with finger bones, and give the mesh their weights.

    import rigext; rigext.add_fingers(arm, mesh)          # rest pose must be the T-pose of the rigged GLB
    rigext.hand_pose(arm, 'L', curl=0.4, thumb=0.2)         # 0 open .. 1 fist

Per hand: <S>Fingers1, <S>Fingers2 (the fused block of four fingers, two joints) and <S>Thumb1, <S>Thumb2."""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector


def _hand_verts(mesh, group, thr=0.3):
    g = mesh.vertex_groups[group].index
    idx, P = [], []
    for v in mesh.data.vertices:
        for e in v.groups:
            if e.group == g and e.weight > thr:
                idx.append(v.index)
                P.append(v.co.copy())
                break
    return np.array(idx), np.array([tuple(p) for p in P])


def add_fingers(arm, mesh, knuckle=0.47, mid=0.74):
    """Bones and weights for the finger block and the thumb of both hands (mesh in its rest pose, armature in rest)."""
    bpy.context.view_layer.update()
    Mm, Ma = mesh.matrix_world, arm.matrix_world
    to_arm = Ma.inverted() @ Mm
    info = {}
    for S in ('Left', 'Right'):
        idx, P = _hand_verts(mesh, f'{S}Hand')
        Pa = np.array([tuple(to_arm @ Vector(p)) for p in P])            # armature space
        hb = arm.data.bones[f'{S}Hand']
        wrist = np.array(tuple(hb.head_local))
        fwd = Pa.mean(axis=0) - wrist
        fwd = fwd / np.linalg.norm(fwd)
        t = (Pa - wrist) @ fwd
        tip = float(np.percentile(t, 99.5))
        # palm normal: the hand is flat, its thinnest direction (PCA)
        C = np.cov((Pa - Pa.mean(axis=0)).T)
        w_, V_ = np.linalg.eigh(C)
        nrm = V_[:, 0]
        if nrm[2] > 0:                                                     # T-pose: palm faces down
            nrm = -nrm
        side = np.cross(nrm, fwd)
        side /= np.linalg.norm(side)
        lat = (Pa - wrist) @ side
        # the thumb: the side of the hand whose lateral extent is largest at mid-length
        band = (t > 0.15 * tip) & (t < 0.6 * tip)
        thumb_sign = 1.0 if np.percentile(lat[band], 97) > -np.percentile(lat[band], 3) else -1.0
        lat_s = lat * thumb_sign
        fingers_w = np.percentile(lat_s[(t > 0.8 * tip)], [5, 95])          # lateral span of the finger block at the tips
        is_thumb = (lat_s > fingers_w[1] + 0.004 * tip / 0.18) & (t > 0.1 * tip) & (t < 0.78 * tip)
        # the thumb is one connected piece: drop stray vertices far from the main thumb cluster
        if is_thumb.sum() > 20:
            ct = np.median(Pa[is_thumb], axis=0)
            dd = np.linalg.norm(Pa - ct, axis=1)
            is_thumb &= dd < np.percentile(dd[is_thumb], 90) * 1.6
        info[S] = dict(wrist=wrist, fwd=fwd, nrm=nrm, side=side * thumb_sign, tip=tip)
        # bones
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm.data.edit_bones
        hand = eb[f'{S}Hand']
        cblock = Pa[~is_thumb & (t > knuckle * tip)].mean(axis=0) if (~is_thumb & (t > knuckle * tip)).any() else wrist + fwd * tip
        lat_c = float(((cblock - wrist) @ (side * thumb_sign)))
        base = Vector(tuple(wrist + fwd * knuckle * tip + side * thumb_sign * lat_c))
        midp = Vector(tuple(wrist + fwd * mid * tip + side * thumb_sign * lat_c))
        tipp = Vector(tuple(wrist + fwd * tip + side * thumb_sign * lat_c))
        roll_ref = Vector(tuple(nrm))
        f1 = eb.new(f'{S}Fingers1'); f1.head, f1.tail = base, midp; f1.parent = hand; f1.align_roll(roll_ref)
        f2 = eb.new(f'{S}Fingers2'); f2.head, f2.tail = midp, tipp; f2.parent = f1; f2.use_connect = True; f2.align_roll(roll_ref)
        if is_thumb.any():
            Pt, tt = Pa[is_thumb], t[is_thumb]
            th_tip = Pt[np.argmax(tt + 0.5 * ((Pt - wrist) @ (side * thumb_sign)))]
            th_base = wrist + fwd * 0.12 * tip + side * thumb_sign * 0.25 * float(np.percentile(lat_s[band], 97))
            th_mid = (th_base + th_tip) / 2
            t1 = eb.new(f'{S}Thumb1'); t1.head, t1.tail = Vector(tuple(th_base)), Vector(tuple(th_mid)); t1.parent = hand; t1.align_roll(roll_ref)
            t2 = eb.new(f'{S}Thumb2'); t2.head, t2.tail = Vector(tuple(th_mid)), Vector(tuple(th_tip)); t2.parent = t1; t2.use_connect = True; t2.align_roll(roll_ref)
        bpy.ops.object.mode_set(mode='OBJECT')
        # weights: smooth hand -> fingers1 -> fingers2 along the hand; the thumb by its own axis
        def ramp(x, a, b):
            return np.clip((x - a) / max(b - a, 1e-6), 0, 1)
        blend = 0.08 * tip
        wf1 = ramp(t, knuckle * tip - blend, knuckle * tip + blend)
        wf2 = ramp(t, mid * tip - blend, mid * tip + blend)
        W = {f'{S}Hand': 1 - wf1, f'{S}Fingers1': wf1 * (1 - wf2), f'{S}Fingers2': wf1 * wf2}
        if is_thumb.any():
            ax = th_tip - th_base
            L = np.linalg.norm(ax)
            u = ((Pa - th_base) @ (ax / L)) / L
            wt = np.where(is_thumb, ramp(u, 0.05, 0.3), 0.0)
            wt2 = np.where(is_thumb, ramp(u, 0.45, 0.65), 0.0)
            for k in list(W):
                W[k] = W[k] * (1 - wt)
            W[f'{S}Thumb1'] = wt * (1 - wt2)
            W[f'{S}Thumb2'] = wt * wt2
        # keep the share the vertex had for the hand (vertices near the wrist are shared with the forearm)
        g_hand = mesh.vertex_groups[f'{S}Hand']
        share = np.array([g_hand.weight(int(i)) for i in idx])
        for name, w in W.items():
            vg = mesh.vertex_groups.get(name) or mesh.vertex_groups.new(name=name)
            for i, wi, sh in zip(idx, w, share):
                vg.add([int(i)], float(wi * sh), 'REPLACE')
        print(S, 'hand verts', len(idx), 'thumb verts', int(is_thumb.sum()), 'tip', round(tip, 3))
    arm['finger_info'] = {S: {k: list(map(float, v)) if hasattr(v, '__len__') else float(v) for k, v in d.items()} for S, d in info.items()}
    return info


def hand_pose(arm, side, curl=0.35, thumb=0.2, spread=0.0):
    """Curl the finger block (0 open .. 1 fist) and the thumb, on the pose bones (call after the body animation is set)."""
    S = 'Left' if side in ('L', 'Left') else 'Right'
    pb = arm.pose.bones
    for name, ang in ((f'{S}Fingers1', 80 * curl), (f'{S}Fingers2', 95 * curl), (f'{S}Thumb1', 35 * thumb), (f'{S}Thumb2', 45 * thumb)):
        if name in pb:
            b = pb[name]
            b.rotation_mode = 'XYZ'
            b.rotation_euler = (math.radians(ang), 0.0, 0.0)
