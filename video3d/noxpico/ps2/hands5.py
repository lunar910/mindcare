"""Real hands for the two Meshy rigs (version 5): five fingers with three phalanges each, smaller hands, natural poses.

    import hands5
    info = hands5.add_hands(arm, mesh, size=0.9)          # once, right after cast2.Actor (rest pose, T-pose)
    ...
    # every frame, AFTER the arms are posed (Performer.pose / IK / orient_hand):
    hands5.pose_hand(arm, 'R', 'pen', t=t)                 # a preset, with a little life
    hands5.pose_hand(arm, 'L', hands5.mix('relaxed', 'palm_up_open', w), t=t)
    wf.apply(arm, t)                                       # optional wrist lag (WristFollow, see below)

add_hands(arm, mesh, size=0.9, even=True, dqs=True)
    * shrinks each hand (palm and fingers, about the centre of the wrist) by moving the vertices of the mesh AND of every
      shape key (baked: pose-bone scale is reset by procpose.rotate_bone_world, so a bone scale would not survive);
      the factor ramps in from 1 cm before the wrist joint to 3.5 cm after it, so the wrist seam stays smooth.
      size is relative to the mean length of the two hands; even=True also makes both hands the same length (the
      Meshy hands differ by 7-8 % left / right).
    * finds the fingers on the mesh: beyond the webs each finger is its own surface; cutting the hand at increasing
      distances from the wrist, the thumb separates first, then the four fingers.  Each finger's axis comes from its own
      vertices; the knuckles (MCP) are placed on that axis at anatomical distances (middle finger = 49 % of the hand
      length, knuckle arc index -2 %, ring -2.5 %, pinky -7 %), the PIP / DIP joints at real phalanx ratios, every
      joint centred in the thickness of the finger (MCP 42 % from the back of the hand).
    * bones <S>Hand<Finger><1..3>  (S = Left / Right, Finger = Thumb, Index, Middle, Ring, Pinky), parented to <S>Hand;
      roll: local Z = palm side, so a POSITIVE rotation about local X curls a finger towards the palm (thumb: towards
      the base of the ring finger, i.e. across the palm).
    * weights: soft membership between neighbouring fingers in the webs, hard membership on the free fingers, smooth
      ramps across each joint (MCP +-0.9 cm, PIP / DIP +-0.3 cm on a 19 cm hand) -> nothing tears when the fingers bend.
      The old rigext finger groups are removed (the old bones stay, unweighted, so Performer.rest_hand still works);
      the forearm's weight that Meshy spilled into the palm (10-20 % at 4-6 cm) is handed back to the hand.
    * dqs=True: a second Armature modifier with dual-quaternion skinning, mixed in on the hands only (vertex group
      'H5_dqs'), so bent fingers keep their volume instead of pinching.

pose_hand(arm, side, pose, weight=1.0, t=None, seed=None, life=1.0)
    pose: a preset name or a dict (see PRESETS and the keys below).  weight blends from what the bones hold now (rest,
    after acting.reset_pose) to the pose.  t: time in seconds -> slow per-finger life (each finger drifts on its own,
    2-3 deg, 0.15-0.4 Hz); every hand also has fixed small per-finger offsets (seeded by side), so the fingers are never
    all identical.
    Pose dict keys (degrees): 'index' / 'middle' / 'ring' / 'pinky': (MCP, PIP, DIP) flexion, + = towards the palm;
    'spread': {finger: deg} + = away from the middle finger (middle: + = towards the index);
    'thumb': (CMC, MCP, IP) flexion across the palm; 'thumb_abd': palmar abduction (+ = thumb lifts off the palm plane,
    in front of the palm); 'thumb_spread': radial abduction (+ = away from the index, in the palm plane);
    'thumb_roll': + = the pad turns to face the fingers' pads.  Missing keys come from pose.get('base', 'relaxed').

PRESETS
    relaxed       natural rest: index 16/19/14 deg per joint cascading to pinky 31/35/24, a light fan, thumb slightly
                  flexed and adducted along the index.
    pen           tripod grip of a pen / soldering iron: thumb pad and index pad pinch, middle finger under the shaft
                  (its side supports it), ring and pinky curled.  pen_frame(arm, side) gives where the shaft goes.
    palm_up_open  offering / showing: fingers almost straight with a soft cascade, opened fan, thumb out.
    loose_fist    relaxed closed hand (fingers curled, not squeezed), thumb resting on the middle phalanx of the index.
    point         index extended, the others curled, thumb on the middle finger.
    flat          hand flat on a surface: fingers straight and together, thumb along.

Wrist (overlapping action): the hand should trail the forearm a little when the arm moves, then catch up / overshoot.
    wf = hands5.WristFollow('Right', pos_fn, t_end)    # pos_fn(t) -> world position of the hand (the IK target is fine)
    ... per frame, after the arm and orient_hand:  wf.apply(arm, t, w=1.0)
    WristFollow.from_performer(P, 'Right', t_end) samples the Performer itself (poses it, so call it before rendering).
    One-frame version without memory: wrist_follow(arm, 'R', vel, acc) (vel / acc of the hand in world, m/s, m/s^2).
    install(performer, left=None, right=None, wrist=None) wraps Performer.pose_arms so that every pose(t) ends with the
    hand poses (HandTrack or None = mapped from the Performer's own finger curl) and the wrist follow.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

FINGERS = ('Index', 'Middle', 'Ring', 'Pinky')
ALL = ('Thumb',) + FINGERS
KEYS = {'Thumb': 'thumb', 'Index': 'index', 'Middle': 'middle', 'Ring': 'ring', 'Pinky': 'pinky'}
OLD = ('Fingers1', 'Fingers2', 'Thumb1', 'Thumb2')            # rigext bones: kept (Performer uses them), unweighted


def bname(S, f, k):
    return f'{S}Hand{f}{k}'


def _side(side):
    return 'Left' if side in ('L', 'Left', 'left', 'l') else 'Right'


def _smooth(x, a, b):
    x = np.clip((x - a) / np.maximum(b - a, 1e-9), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


# anatomical ratios (fractions of the hand length HL = wrist joint -> tip of the middle finger)
FINGER_LEN = {'Index': 0.445, 'Middle': 0.49, 'Ring': 0.465, 'Pinky': 0.37}        # MCP -> tip
MCP_ARC = {'Index': -0.02, 'Middle': 0.0, 'Ring': -0.025, 'Pinky': -0.07}            # knuckle line, along the hand
PHALANX = {'Index': (0.47, 0.28), 'Middle': (0.47, 0.29), 'Ring': (0.46, 0.29), 'Pinky': (0.45, 0.27)}   # MCP-PIP, PIP-DIP
THUMB = (0.235, 0.165, 0.145)                    # metacarpal, proximal, distal (+ pad) as fractions of HL


# ------------------------------------------------------------------ mesh data
def _read(mesh):
    me = mesh.data
    n = len(me.vertices)
    P = np.empty(n * 3)
    me.vertices.foreach_get('co', P)
    E = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', E)
    W = {}
    names = {g.index: g.name for g in mesh.vertex_groups}
    for v in me.vertices:
        for e in v.groups:
            if e.weight > 0.0:
                W.setdefault(names[e.group], {})[v.index] = e.weight
    return P.reshape(-1, 3), E.reshape(-1, 2), W


def _dense(W, name, n):
    a = np.zeros(n)
    d = W.get(name)
    if d:
        a[np.fromiter(d.keys(), np.int64)] = np.fromiter(d.values(), np.float64)
    return a


def _components(A, keep, members):
    """Connected components (scipy) of the sub-graph of the hand vertices kept by the boolean mask keep."""
    from scipy.sparse.csgraph import connected_components
    ii = np.where(keep)[0]
    if len(ii) == 0:
        return []
    sub = A[ii][:, ii]
    n, lab = connected_components(sub, directed=False)
    out = []
    for k in range(n):
        m = ii[lab == k]
        out.append(members[m])
    return out


# ------------------------------------------------------------------ analysis of one hand
class _Hand:
    pass


def _frame(P, idx, wrist):
    Q = P[idx] - wrist
    m = _unit(Q.mean(0))
    t0 = Q @ m
    fwd = _unit(Q[t0 > np.percentile(t0, 90)].mean(0))
    t = Q @ fwd
    sel = t > 0.15 * t.max()
    C = np.cov((Q[sel] - Q[sel].mean(0)).T)
    ev, V = np.linalg.eigh(C)
    nrm = V[:, 0] - fwd * (V[:, 0] @ fwd)
    nrm = _unit(nrm)
    if nrm[2] > 0:                       # T-pose: the palms face the floor
        nrm = -nrm
    side = _unit(np.cross(nrm, fwd))
    return fwd, nrm, side


def _analyse(P, E, share, wrist, U, S):
    """Finger segmentation and joints of one hand (arrays in armature space, U = armature units per metre)."""
    H = _Hand()
    core = np.where(share > 0.3)[0]
    fwd, nrm, side = _frame(P, core, wrist)
    Q = P[core]
    t = (Q - wrist) @ fwd
    HL = float(t.max())
    k = HL / (0.19 * U)                   # 1 for a 19 cm hand
    # graph of the core vertices
    from scipy.sparse import coo_matrix
    pos = -np.ones(len(P), np.int64)
    pos[core] = np.arange(len(core))
    ee = E[(pos[E[:, 0]] >= 0) & (pos[E[:, 1]] >= 0)]
    a, b = pos[ee[:, 0]], pos[ee[:, 1]]
    A = coo_matrix((np.ones(len(a) * 2), (np.r_[a, b], np.r_[b, a])), shape=(len(core),) * 2).tocsr()
    members = np.arange(len(core))
    step = 0.0015 * U
    minsize = 12
    cuts = np.arange(0.3 * HL, 0.97 * HL, step)
    base = _components(A, t > cuts[0], members)
    main = max(base, key=len)
    in_main = np.zeros(len(core), bool)
    in_main[main] = True
    lat = (Q - wrist) @ side
    thumb = None
    fingers = None
    seeds = None
    for c in cuts:
        comps = [x for x in _components(A, (t > c) & in_main, members) if len(x) >= minsize]
        if thumb is None:
            if len(comps) >= 2:
                big = max(comps, key=len)
                rest = [x for x in comps if x is not big]
                th = max(rest, key=lambda x: abs(lat[x].mean() - lat[big].mean()) - 0.2 * t[x].max())
                thumb = (c, th)
                tsign = 1.0 if lat[th].mean() > lat[big].mean() else -1.0
            continue
        fc = [x for x in comps if not np.intersect1d(x, thumb[1]).size]
        if len(fc) == 4:
            fingers = sorted(fc, key=lambda x: -tsign * lat[x].mean())      # index (thumb side) first
            seeds = [x[t[x] > np.percentile(t[x], 70)] for x in fingers]
            c4 = c
            break
    if thumb is None or fingers is None:
        raise RuntimeError(f'hands5: could not separate the fingers of the {S} hand (thumb {thumb is not None})')
    side_t = side * tsign                                # lateral direction towards the thumb
    # each finger's free part: the lowest cut at which its component holds no other finger's seed
    free = {}
    for i, f in enumerate(FINGERS):
        best = fingers[i]
        for c in np.arange(c4 - step, thumb[0], -step):
            comps = _components(A, (t > c) & in_main, members)
            mine = next(x for x in comps if np.intersect1d(x, seeds[i]).size)
            if any(np.intersect1d(mine, seeds[j]).size for j in range(4) if j != i) or np.intersect1d(mine, thumb[1]).size:
                break
            best = mine
        free[f] = best
    # the thumb's free part
    free['Thumb'] = thumb[1]
    H.fwd, H.nrm, H.side, H.side_t, H.HL, H.k, H.U = fwd, nrm, side, side_t, HL, k, U
    H.core, H.free, H.wrist = core, {f: core[v] for f, v in free.items()}, wrist
    # ---- joints
    Pc = P[core]

    def axis_of(vs):
        X = P[vs]
        c = X.mean(0)
        _, _, Vt = np.linalg.svd(X - c, full_matrices=False)
        d = _unit(Vt[0])
        if d @ (c - wrist) < 0:
            d = -d
        return c, d

    def centre(J, d, half_len, half_lat, ratio, pool=None, centre_lat=False):
        """Put the joint J in the middle of the local cross-section (ratio = 0 back of the hand .. 1 palm side)."""
        X = Pc if pool is None else P[pool]
        lat_d = _unit(np.cross(nrm, d))
        R = X - J
        sel = (np.abs(R @ d) < half_len) & (np.abs(R @ lat_d) < half_lat)
        if sel.sum() < 4:
            return J
        h = R[sel] @ nrm
        J = J + nrm * (h.min() + ratio * (h.max() - h.min()))
        if centre_lat:
            l = R[sel] @ lat_d
            J = J + lat_d * 0.5 * (l.min() + l.max())
        return J

    H.joints, H.radius = {}, {}
    t_tip_mid = None
    axes = {}
    for f in FINGERS:
        c, d = axis_of(H.free[f])
        s = (P[H.free[f]] - c) @ d
        axes[f] = (c, d, s.max())
    cmid, dmid, smid = axes['Middle']
    tip_mid = cmid + dmid * smid
    t_mcp_mid = (tip_mid - wrist) @ fwd - FINGER_LEN['Middle'] * HL
    for f in FINGERS:
        c, d, smax = axes[f]
        tip = c + d * smax
        tip = centre(tip - d * 0.004 * U * k, d, 0.004 * U * k, 0.012 * U * k, 0.5, H.free[f], True) + d * 0.002 * U * k
        tip = tip - d * 0.0015 * U * k                     # the bone ends just inside the pad
        t_mcp = t_mcp_mid + MCP_ARC[f] * HL
        # MCP: on the finger's axis line, at the knuckle line
        dd = d @ fwd
        s_m = ((wrist + fwd * t_mcp - c) @ fwd) / max(dd, 0.3)
        mcp = c + d * s_m
        mcp = centre(mcp, d, 0.005 * U * k, 0.008 * U * k, 0.42)
        L = np.linalg.norm(tip - mcp)
        d2 = _unit(tip - mcp)
        r1, r2 = PHALANX[f]
        pip = mcp + d2 * r1 * L
        dip = mcp + d2 * (r1 + r2) * L
        fr = H.free[f]
        s_pip = (pip - c) @ d
        pool = fr if s_pip > ((P[fr] - c) @ d).min() + 0.002 * U else None
        pip = centre(pip, d2, 0.0035 * U * k, 0.009 * U * k, 0.5, pool, pool is not None)
        dip = centre(dip, d2, 0.003 * U * k, 0.009 * U * k, 0.5, fr, True)
        H.joints[f] = [mcp, pip, dip, tip]
        rr = np.linalg.norm(np.cross(P[fr] - c, d), axis=1)
        H.radius[f] = float(np.median(rr))
    # thumb: free part axis, tip; MCP / IP on that axis; CMC by anatomy (radial, palmar, near the wrist)
    c, d, = axis_of(H.free['Thumb'])
    s = (P[H.free['Thumb']] - c) @ d
    tip = c + d * s.max()
    tip = centre(tip - d * 0.004 * U * k, d, 0.004 * U * k, 0.014 * U * k, 0.5, H.free['Thumb'], True) + d * 0.0025 * U * k
    tip = tip - d * 0.0015 * U * k
    ip = tip - d * THUMB[2] * HL
    mcp = ip - d * THUMB[1] * HL
    ip = centre(ip, d, 0.0035 * U * k, 0.01 * U * k, 0.5, H.free['Thumb'], True)
    mcp = centre(mcp, d, 0.005 * U * k, 0.012 * U * k, 0.5)
    # CMC (trapezium-metacarpal joint): base of the thenar, radial and a little palmar, ~2 cm past the wrist joint
    anchor = wrist + fwd * 0.11 * HL + side_t * 0.11 * HL
    anchor = centre(anchor, fwd, 0.006 * U * k, 0.01 * U * k, 0.58)
    Lm = np.clip(np.linalg.norm(anchor - mcp), 0.19 * HL, 0.27 * HL)
    cmc = mcp + _unit(anchor - mcp) * Lm
    H.joints['Thumb'] = [cmc, mcp, ip, tip]
    H.radius['Thumb'] = float(np.median(np.linalg.norm(np.cross(P[H.free['Thumb']] - c, d), axis=1)))
    return H


def _project(X, J, back):
    """Arc-length parameter u along the joint polyline J (first segment extended backwards by `back`) and distance r."""
    best_r = np.full(len(X), np.inf)
    best_u = np.zeros(len(X))
    cum = 0.0
    for i in range(len(J) - 1):
        a, b = J[i], J[i + 1]
        seg = b - a
        L = np.linalg.norm(seg)
        d = seg / L
        s = (X - a) @ d
        lo = -back if i == 0 else 0.0
        hi = L + (0.03 * L if i == len(J) - 2 else 0.0)
        sc = np.clip(s, lo, hi)
        r = np.linalg.norm(X - (a + np.outer(sc, d)), axis=1)
        better = r < best_r
        best_r[better] = r[better]
        best_u[better] = cum + sc[better]
        cum += L
    return best_u, best_r


def _weights(P, E, share, H, smooth_iter=4):
    """{group name: weights over H.region} and the region (vertex indices)."""
    U, k = H.U, H.k
    reg = np.where(share > 1e-5)[0]
    X = P[reg]
    sh = share[reg]
    n = len(reg)
    inf = {}
    for f in ALL:
        J = H.joints[f]
        back = 0.05 * U * k
        u, r = _project(X, J, back)
        R = H.radius[f]
        if f == 'Thumb':
            A = _smooth(u, -0.006 * U * k, 0.012 * U * k)
            L1 = np.linalg.norm(J[1] - J[0])
            rad = np.where(u < L1, 0.010 * U * k + 0.6 * R, 1.4 * R)        # thenar bulk around the metacarpal
            B = 1.0 - _smooth(r, rad, rad + 0.012 * U * k)
        else:
            A = _smooth(u, -0.009 * U * k, 0.009 * U * k)
            B = 1.0 - _smooth(r, 0.016 * U * k, 0.026 * U * k)
        inf[f] = (u, r, A * B)
    # competition between neighbouring chains (webs): inverse distance, sharp
    R4 = np.stack([1.0 / np.maximum(inf[f][1], 1e-4 * U) ** 4 for f in ALL], 1)
    M = R4 / R4.sum(1, keepdims=True)
    G = np.stack([inf[f][2] for f in ALL], 1) * M
    # free fingers: hard membership
    pos = -np.ones(len(P), np.int64)
    pos[reg] = np.arange(n)
    for i, f in enumerate(ALL):
        fr = pos[H.free[f]]
        fr = fr[fr >= 0]
        G[fr, :] = 0.0
        G[fr, i] = 1.0
    tot = G.sum(1)
    over = tot > 1.0
    G[over] /= tot[over, None]
    # smooth the memberships over the surface (no edge crosses the gap between two free fingers, so this only
    # softens the borders: web / free finger, knuckles, thenar)
    from scipy.sparse import coo_matrix, diags
    ee = E[(pos[E[:, 0]] >= 0) & (pos[E[:, 1]] >= 0)]
    a, b = pos[ee[:, 0]], pos[ee[:, 1]]
    Adj = coo_matrix((np.ones(len(a) * 2), (np.r_[a, b], np.r_[b, a])), shape=(n, n)).tocsr()
    deg = np.asarray(Adj.sum(1)).ravel()
    Nrm = diags(1.0 / np.maximum(deg, 1)) @ Adj
    has = deg > 0
    for _ in range(smooth_iter):
        Gs = Nrm @ G
        G[has] = 0.5 * G[has] + 0.5 * Gs[has]
    out = {}
    hand = 1.0 - G.sum(1)
    for i, f in enumerate(ALL):
        u = inf[f][0]
        J = H.joints[f]
        l1 = np.linalg.norm(J[1] - J[0])
        l2 = l1 + np.linalg.norm(J[2] - J[1])
        if f == 'Thumb':
            b1, b2 = 0.005 * U * k, 0.0035 * U * k
        else:
            b1, b2 = 0.0035 * U * k, 0.003 * U * k
        w2 = _smooth(u, l1 - b1, l1 + b1)
        w3 = _smooth(u, l2 - b2, l2 + b2)
        g = G[:, i]
        out[bname(H.S, f, 1)] = g * (1 - w2)
        out[bname(H.S, f, 2)] = g * w2 * (1 - w3)
        out[bname(H.S, f, 3)] = g * w3
    out[f'{H.S}Hand'] = hand
    for kname in out:
        out[kname] = out[kname] * sh
    return reg, out


# ------------------------------------------------------------------ build
def add_hands(arm, mesh, size=0.9, even=True, dqs=True, verbose=True):
    """Shrink, segment, rig and weight both hands.  Armature and mesh in their rest (T) pose.  Returns per-side info."""
    if arm.get('hands5'):
        return dict(arm['hands5'])
    bpy.context.view_layer.update()
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    to_arm = arm.matrix_world.inverted() @ mesh.matrix_world
    if not np.allclose(np.array(to_arm), np.eye(4), atol=1e-5):
        raise RuntimeError('hands5: the mesh must share the armature space (Meshy import)')
    U = 1.0 / arm.matrix_world.to_scale()[0]
    P, E, W = _read(mesh)
    n = len(P)
    sides = {}
    for S in ('Left', 'Right'):
        fam = [f'{S}Hand'] + [f'{S}{o}' for o in OLD]
        share = sum(_dense(W, g, n) for g in fam)
        fore = _dense(W, f'{S}ForeArm', n)
        wrist = np.array(tuple(arm.data.bones[f'{S}Hand'].head_local))
        core = np.where(share > 0.3)[0]
        fwd, nrm, side = _frame(P, core, wrist)
        HL = float(((P[core] - wrist) @ fwd).max())
        sides[S] = dict(share=share, fore=fore, wrist=wrist, fwd=fwd, HL=HL)
    mean = 0.5 * (sides['Left']['HL'] + sides['Right']['HL'])
    # ---- 1. shrink (numpy first; the mesh is written only once everything has been computed)
    P2 = P.copy()
    for S, d in sides.items():
        fac = size * (mean / d['HL']) if even else size
        d['factor'] = fac
        tt = (P - d['wrist']) @ d['fwd']
        near = np.linalg.norm(P - d['wrist'], axis=1) < 0.35 * U
        mask = near & ((d['share'] > 0) | (d['fore'] > 0)) & (tt > -0.012 * U)
        ring = mask & (np.abs(tt) < 0.006 * U)
        cw = P[ring].mean(0) if ring.sum() > 6 else d['wrist']          # centre of the wrist cross-section
        cw = cw - d['fwd'] * ((cw - d['wrist']) @ d['fwd'])             # ... at the level of the joint
        s = 1.0 - (1.0 - fac) * _smooth(tt, -0.01 * U, 0.035 * U)
        idx = np.where(mask)[0]
        d['idx'], d['cw'], d['s'] = idx, cw, s[idx]
        P2[idx] = cw + (P[idx] - cw) * s[idx, None]
    # the forearm's weight that Meshy spilled into the palm goes back to the hand (the palm stays rigid on a wrist bend)
    for S, d in sides.items():
        tt = (P2 - d['wrist']) @ d['fwd']
        near = np.linalg.norm(P2 - d['wrist'], axis=1) < 0.3 * U
        frac = np.where(near & (d['share'] > 0), _smooth(tt, 0.03 * U, 0.06 * U), 0.0)
        d['share2'] = d['share'] + d['fore'] * frac
        d['fore2'] = d['fore'] * (1.0 - frac)
        d['fore_idx'] = np.where((d['fore'] > 0) & (frac > 0))[0]
    # ---- 2. analysis on the shrunk hands
    Hs = {}
    for S, d in sides.items():
        H = _analyse(P2, E, d['share'], d['wrist'], U, S)
        H.S = S
        H.reg, H.W = _weights(P2, E, d['share2'], H)
        Hs[S] = H
    # ---- 3. write: vertices and every shape key
    me = mesh.data
    me.vertices.foreach_set('co', P2.ravel())
    if me.shape_keys:
        for kb in me.shape_keys.key_blocks:
            K = np.empty(n * 3)
            kb.data.foreach_get('co', K)
            K = K.reshape(-1, 3)
            for S, d in sides.items():
                i = d['idx']
                K[i] = d['cw'] + (K[i] - d['cw']) * d['s'][:, None]
            kb.data.foreach_set('co', K.ravel())
    me.update()
    # ---- 4. bones
    prev_active = bpy.context.view_layer.objects.active
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    hidden = arm.hide_get()
    arm.hide_set(False)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for S, H in Hs.items():
        d = sides[S]
        for o in OLD:                                        # rigext bones follow the shrink (directions unchanged)
            b = eb.get(f'{S}{o}')
            if b:
                for attr in ('head', 'tail'):
                    p = np.array(tuple(getattr(b, attr)))
                    tt = (p - d['wrist']) @ d['fwd']
                    s = 1.0 - (1.0 - d['factor']) * _smooth(tt, -0.01 * U, 0.035 * U)
                    setattr(b, attr, Vector(tuple(d['cw'] + (p - d['cw']) * s)))
        hand = eb[f'{S}Hand']
        ring_base = H.joints['Ring'][0] + H.nrm * 0.012 * U * H.k
        for f in ALL:
            J = H.joints[f]
            parent = hand
            for i in range(3):
                b = eb.new(bname(S, f, i + 1))
                b.head, b.tail = Vector(tuple(J[i])), Vector(tuple(J[i + 1]))
                b.parent = parent
                b.use_connect = i > 0
                b.use_deform = True
                if f == 'Thumb':
                    ref = ring_base - J[i]
                else:
                    ref = H.nrm
                y = _unit(J[i + 1] - J[i])
                z = _unit(ref - y * (ref @ y))
                b.align_roll(Vector(tuple(z)))
                parent = b
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.hide_set(hidden)
    # ---- 5. weights
    for S, H in Hs.items():
        for o in OLD:
            vg = mesh.vertex_groups.get(f'{S}{o}')
            if vg:
                mesh.vertex_groups.remove(vg)
        reg = H.reg.tolist()
        for name, w in H.W.items():
            vg = mesh.vertex_groups.get(name) or mesh.vertex_groups.new(name=name)
            hand = name.endswith('Hand')
            for i, wi in zip(reg, w.tolist()):
                if wi > 1e-4 or hand:
                    vg.add([i], wi if wi > 1e-4 else 0.0, 'REPLACE')
        d = sides[S]
        vf = mesh.vertex_groups[f'{S}ForeArm']
        for i in d['fore_idx'].tolist():
            vf.add([i], float(d['fore2'][i]), 'REPLACE')
    # ---- 6. dual-quaternion skinning on the hands only
    if dqs:
        vg = mesh.vertex_groups.get('H5_dqs') or mesh.vertex_groups.new(name='H5_dqs')
        for S, d in sides.items():
            tt = (P2 - d['wrist']) @ d['fwd']
            sel = np.where(((d['share'] > 0) | (d['fore'] > 0)) & (tt > -0.03 * U) &
                           (np.linalg.norm(P2 - d['wrist'], axis=1) < 0.35 * U))[0]
            w = _smooth(tt[sel], -0.02 * U, 0.02 * U)
            for i, wi in zip(sel.tolist(), w.tolist()):
                if wi > 0:
                    vg.add([i], wi, 'REPLACE')
        base = next((m for m in mesh.modifiers if m.type == 'ARMATURE'), None)
        md = mesh.modifiers.new('H5_hands_dqs', 'ARMATURE')
        md.object = arm
        md.use_deform_preserve_volume = True
        md.use_multi_modifier = True
        md.vertex_group = 'H5_dqs'
        md.use_vertex_groups = True
        md.use_bone_envelopes = False
        # right after the original armature modifier
        if base is not None:
            names = [m.name for m in mesh.modifiers]
            target = names.index(base.name) + 1
            if names.index(md.name) != target:
                with bpy.context.temp_override(object=mesh, active_object=mesh):
                    bpy.ops.object.modifier_move_to_index(modifier=md.name, index=target)
    # ---- 7. what pose_hand needs: local axes of each bone
    meta = {}
    for S, H in Hs.items():
        m = {'HL_m': H.HL / U, 'factor': sides[S]['factor'], 'radius_m': {f: H.radius[f] / U for f in ALL}}
        away = {'Index': H.side_t, 'Middle': H.side_t, 'Ring': -H.side_t, 'Pinky': -H.side_t}
        for f in FINGERS:
            R = arm.data.bones[bname(S, f, 1)].matrix_local.to_3x3()
            X = np.array(tuple(R.col[0]))
            m[f'spread_sign_{f}'] = 1.0 if (-X) @ away[f] > 0 else -1.0
        b1 = arm.data.bones[bname(S, 'Thumb', 1)]
        R = b1.matrix_local.to_3x3()
        Ri = R.inverted()
        Y = np.array(tuple(R.col[1]))
        X = np.array(tuple(R.col[0]))
        ax_abd = _unit(np.cross(Y, H.nrm))                     # + : the thumb lifts towards the palm side
        ax_spr = _unit(np.cross(Y, H.side_t))                  # + : the thumb moves away from the index (radially)
        m['thumb_abd_axis'] = list(Ri @ Vector(tuple(ax_abd)))
        m['thumb_spread_axis'] = list(Ri @ Vector(tuple(ax_spr)))
        # roll + : the pad (local Z) turns towards the fingers' pads (palm side and across): Z moves towards -X
        to_fingers = _unit(H.nrm * 0.5 - H.side_t)
        m['thumb_roll_sign'] = 1.0 if (-X) @ to_fingers > 0 else -1.0
        m['nrm'] = list(map(float, H.nrm))
        m['side_t'] = list(map(float, H.side_t))
        m['fwd'] = list(map(float, H.fwd))
        meta[S] = m
        if verbose:
            Jm = H.joints
            print(f'hands5 {mesh.name} {S}: factor {sides[S]["factor"]:.3f}  length {H.HL / U * 100:.1f} cm (was '
                  f'{sides[S]["HL"] / U * 100:.1f})  fingers (MCP->tip, cm) ' +
                  ' '.join(f'{f[:2]} {np.linalg.norm(Jm[f][3] - Jm[f][0]) / U * 100:.1f}' for f in ALL) +
                  f'  free verts ' + ' '.join(str(len(H.free[f])) for f in ALL), flush=True)
    arm['hands5'] = meta
    bpy.context.view_layer.objects.active = prev_active
    bpy.context.view_layer.update()
    return meta


# ------------------------------------------------------------------ poses
PRESETS = {
    'relaxed': {
        'index': (16, 19, 14), 'middle': (21, 25, 17), 'ring': (26, 30, 20), 'pinky': (31, 35, 24),
        'spread': {'index': 2, 'middle': 0, 'ring': 1, 'pinky': 4},
        'thumb': (8, 12, 14), 'thumb_abd': 6, 'thumb_spread': -8, 'thumb_roll': 10},
    'pen': {
        'index': (38, 32, 8), 'middle': (46, 52, 22), 'ring': (62, 75, 42), 'pinky': (68, 80, 48),
        'spread': {'index': -2, 'middle': -3, 'ring': -1, 'pinky': 2},
        'thumb': (22, 14, 12), 'thumb_abd': 28, 'thumb_spread': 0, 'thumb_roll': 25},
    'palm_up_open': {
        'index': (6, 8, 5), 'middle': (8, 10, 6), 'ring': (11, 13, 8), 'pinky': (14, 17, 10),
        'spread': {'index': 5, 'middle': 1, 'ring': 3, 'pinky': 9},
        'thumb': (0, 4, 6), 'thumb_abd': 18, 'thumb_spread': 10, 'thumb_roll': 5},
    'loose_fist': {
        'index': (58, 72, 38), 'middle': (64, 80, 42), 'ring': (70, 84, 45), 'pinky': (75, 86, 48),
        'spread': {'index': -2, 'middle': -1, 'ring': -1, 'pinky': 1},
        'thumb': (22, 22, 20), 'thumb_abd': 10, 'thumb_spread': -14, 'thumb_roll': 25},
    'point': {
        'index': (3, 4, 2), 'middle': (70, 88, 45), 'ring': (76, 92, 48), 'pinky': (80, 92, 50),
        'spread': {'index': 0, 'middle': -1, 'ring': -1, 'pinky': 1},
        'thumb': (28, 24, 18), 'thumb_abd': 12, 'thumb_spread': -12, 'thumb_roll': 25},
    'flat': {
        'index': (2, 2, 1), 'middle': (2, 2, 1), 'ring': (3, 3, 2), 'pinky': (3, 4, 2),
        'spread': {'index': -3, 'middle': -1, 'ring': -2, 'pinky': -4},
        'thumb': (0, 3, 3), 'thumb_abd': 0, 'thumb_spread': -10, 'thumb_roll': 0},
}
LIMITS = {'mcp': (-25.0, 95.0), 'pip': (-5.0, 110.0), 'dip': (-15.0, 90.0), 'spread': (-20.0, 25.0)}


def resolve(pose):
    """Preset name or partial dict -> full dict (missing keys from pose['base'], default 'relaxed')."""
    if isinstance(pose, str):
        return {k: (dict(v) if isinstance(v, dict) else v) for k, v in PRESETS[pose].items()}
    bn = pose.get('base', 'relaxed')
    out = dict(resolve(bn)) if bn else {}
    for k, v in pose.items():
        if k == 'base':
            continue
        if k == 'spread':
            sp = dict(out.get('spread', {}))
            sp.update(v)
            out['spread'] = sp
        else:
            out[k] = v
    return out


def mix(a, b, w):
    """Blend two poses (names or dicts): w = 0 -> a, 1 -> b."""
    A, B = resolve(a), resolve(b)
    out = {}
    for k in set(A) | set(B):
        va, vb = A.get(k, B.get(k)), B.get(k, A.get(k))
        if isinstance(va, dict):
            out[k] = {f: va.get(f, 0.0) + (vb.get(f, 0.0) - va.get(f, 0.0)) * w for f in set(va) | set(vb)}
        elif isinstance(va, (tuple, list)):
            out[k] = tuple(x + (y - x) * w for x, y in zip(va, vb))
        else:
            out[k] = va + (vb - va) * w
    return out


def _noise(t, seed, f):
    import acting as AC
    return AC.noise(t, seed, f, 2)


def _personal(S, seed):
    """Small fixed per-finger offsets (degrees) so that two hands / fingers are never identical (deterministic: the
    render workers are separate processes)."""
    rng = np.random.default_rng((11 if S == 'Left' else 29) + (0 if seed is None else int(round(float(seed) * 1000)) % 100003))
    return {f: rng.uniform(-2.5, 2.5, 4) for f in ALL}


def pose_hand(arm, side, pose='relaxed', weight=1.0, t=None, seed=None, life=1.0):
    """Set the finger bones of one hand (local rotations, quaternions).  Call every frame after the arm is posed."""
    S = _side(side)
    meta = arm['hands5'][S]
    p = resolve(pose)
    pers = _personal(S, seed)
    pb = arm.pose.bones
    sd = (0.0 if seed is None else float(seed)) + (3.1 if S == 'Left' else 7.7)
    for i, f in enumerate(ALL):
        key = KEYS[f]
        ang = list(p.get(key, (0, 0, 0)))
        off = pers[f]
        ang = [a + off[j] * min(1.0, 0.3 + abs(a) / 30.0) for j, a in enumerate(ang)]
        if t is not None and life:
            nz = _noise(t, sd + 13.0 * i, 0.17 + 0.05 * i) * 2.6 * life
            nz2 = _noise(t, sd + 13.0 * i + 5.0, 0.31 + 0.04 * i) * 1.2 * life
            ang = [ang[0] + nz, ang[1] + 0.8 * nz + nz2, ang[2] + 0.5 * nz + 0.6 * nz2]
        if f != 'Thumb':
            ang[0] = min(max(ang[0], LIMITS['mcp'][0]), LIMITS['mcp'][1])
            ang[1] = min(max(ang[1], LIMITS['pip'][0]), LIMITS['pip'][1])
            ang[2] = min(max(ang[2], LIMITS['dip'][0]), LIMITS['dip'][1])
        qs = []
        if f == 'Thumb':
            abd = p.get('thumb_abd', 0.0) + off[3]
            spr = p.get('thumb_spread', 0.0)
            roll = p.get('thumb_roll', 0.0)
            if t is not None and life:
                abd += _noise(t, sd + 71.0, 0.13) * 2.5 * life
            q1 = (Quaternion(Vector(meta['thumb_spread_axis']), math.radians(spr)) @
                  Quaternion(Vector(meta['thumb_abd_axis']), math.radians(abd)) @
                  Quaternion((1, 0, 0), math.radians(ang[0])) @
                  Quaternion((0, 1, 0), math.radians(roll * meta['thumb_roll_sign'])))
            qs = [q1, Quaternion((1, 0, 0), math.radians(ang[1])), Quaternion((1, 0, 0), math.radians(ang[2]))]
        else:
            spr = p.get('spread', {}).get(key, 0.0) + 0.4 * off[3]
            if t is not None and life:
                spr += _noise(t, sd + 41.0 + 7.0 * i, 0.11) * 1.2 * life
            spr = min(max(spr, LIMITS['spread'][0]), LIMITS['spread'][1])
            q1 = (Quaternion((0, 0, 1), math.radians(spr * meta[f'spread_sign_{f}'])) @
                  Quaternion((1, 0, 0), math.radians(ang[0])))
            qs = [q1, Quaternion((1, 0, 0), math.radians(ang[1])), Quaternion((1, 0, 0), math.radians(ang[2]))]
        for k in range(3):
            b = pb[bname(S, f, k + 1)]
            b.rotation_mode = 'QUATERNION'
            cur = b.rotation_quaternion.copy()
            b.rotation_quaternion = cur.slerp(qs[k], weight) if weight < 1.0 else qs[k]


def legacy(curl):
    """Map the old single finger curl (rigext / Performer: 0 open .. 0.32 relaxed .. 1 fist) to a pose dict."""
    c = float(curl)
    if c <= 0.32:
        return mix('palm_up_open', 'relaxed', max(c, 0.0) / 0.32)
    return mix('relaxed', 'loose_fist', min((c - 0.32) / 0.68, 1.0))


class HandTrack:
    """keys = [(t, pose), ...] (pose: name or dict); minimum-jerk cross-fade of xfade seconds starting at each key."""

    def __init__(self, keys, xfade=0.3):
        self.keys, self.xfade = sorted(keys, key=lambda k: k[0]), xfade

    def at(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return resolve(ks[0][1])
        k = max(i for i, kk in enumerate(ks) if kk[0] <= t)
        if k == 0:
            return resolve(ks[0][1])
        x = (t - ks[k][0]) / max(self.xfade, 1e-6)
        if x >= 1.0:
            return resolve(ks[k][1])
        prev = self.at(ks[k][0] - 1e-6) if k > 1 else resolve(ks[k - 1][1])
        import acting as AC
        return mix(prev, ks[k][1], AC.minjerk(x))


# ------------------------------------------------------------------ helpers for props
def bone_world(arm, name):
    return arm.matrix_world @ arm.pose.bones[name].matrix


def tip(arm, side, finger):
    """World position of a finger tip (end of its distal bone)."""
    S = _side(side)
    return arm.matrix_world @ arm.pose.bones[bname(S, finger, 3)].tail


def pad(arm, side, finger, along=0.55, depth=0.6):
    """World position on the pad of a finger's distal phalanx (palm side), depth in finger radii."""
    S = _side(side)
    b = arm.pose.bones[bname(S, finger, 3)]
    M = arm.matrix_world @ b.matrix
    r = arm['hands5'][S]['radius_m'][finger]
    p = M @ Vector((0.0, b.length * along, 0.0))
    z = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
    return p + z * r * depth


def pen_frame(arm, side):
    """World matrix of a pen / soldering iron held in the 'pen' grip: origin on the shaft at the pinch (between the thumb
    pad, the index pad and the side of the middle finger), +Y along the shaft towards its tip (away from the hand),
    +Z towards the back of the hand.  The shaft rests on the back of the web between thumb and index.  Attach the
    tool so that its grip section sits at the origin (a 13-18 mm handle fits)."""
    S = _side(side)
    pb = arm.pose.bones
    Mw = arm.matrix_world
    m = arm['hands5'][S]
    Rh = (Mw @ pb[f'{S}Hand'].matrix).to_3x3().normalized()
    R0 = arm.data.bones[f'{S}Hand'].matrix_local.to_3x3().normalized()
    Ma = Mw.to_3x3().normalized()
    palm = (Rh @ R0.inverted() @ Vector(m['nrm'])).normalized()      # world, out of the palm
    thumbw = (Rh @ R0.inverted() @ Vector(m['side_t'])).normalized()
    th = pad(arm, S, 'Thumb', 0.45, 0.9)
    ix = pad(arm, S, 'Index', 0.4, 0.9)
    mb = pb[bname(S, 'Middle', 3)]
    Mm = Mw @ mb.matrix
    mid = Mm @ Vector((0.0, mb.length * 0.3, 0.0)) + thumbw * m['radius_m']['Middle'] * 1.2
    pinch = (th + ix + mid) / 3.0
    web = (Mw @ pb[bname(S, 'Thumb', 2)].head + Mw @ pb[bname(S, 'Index', 1)].head) * 0.5
    web = web - palm * (0.55 * m['HL_m'] * 0.09) + thumbw * 0.004
    y = (pinch - web).normalized()
    up = (-palm - y * (-palm).dot(y)).normalized()
    x = y.cross(up)
    M = Matrix((x, y, up)).transposed().to_4x4()
    M.translation = pinch
    return M


# ------------------------------------------------------------------ wrist: overlapping action
def _hand_dirs(arm, S):
    pb = arm.pose.bones
    Mw = arm.matrix_world
    w = Mw @ pb[f'{S}Hand'].head
    m = Mw @ pb[bname(S, 'Middle', 1)].head
    R = (Mw @ pb[f'{S}Hand'].matrix).to_3x3().normalized()
    nrm = R @ (arm.data.bones[f'{S}Hand'].matrix_local.to_3x3().inverted() @ Vector(arm['hands5'][S]['nrm']))
    return w, (m - w).normalized(), nrm.normalized(), (m - w).length


def wrist_follow(arm, side, vel=(0, 0, 0), acc=(0, 0, 0), drag=0.035, inertia=0.010, max_deg=14.0, w=1.0):
    """One frame, no memory: tilt the hand so that the fingers trail the motion of the wrist.
    vel (m/s), acc (m/s^2): world velocity / acceleration of the hand (finite differences of your hand target:
    v = (f(t+h) - f(t-h)) / 2h, a = (f(t+h) - 2 f(t) + f(t-h)) / h^2 with h = 1/30).  The fingertips lag by
    drag * |v| + inertia * |a| metres (perpendicular to the hand), at most max_deg; deviation (side to side) is
    halved (the wrist bends more easily up / down)."""
    S = _side(side)
    w0, d, nrm, L = _hand_dirs(arm, S)
    off = -(Vector(vel) * drag + Vector(acc) * inertia)
    _tilt(arm, S, off, d, nrm, 2.0 * L, max_deg, w)          # the fingertips are about twice as far as the knuckles


def _tilt(arm, S, off, d, nrm, lever, max_deg, w):
    off = off - d * off.dot(d)
    lat = d.cross(nrm).normalized()
    off = nrm * off.dot(nrm) + lat * (0.5 * off.dot(lat))
    if off.length < 1e-6 or w <= 0:
        return
    ang = min(off.length / max(lever, 1e-3), math.radians(max_deg))
    axis = d.cross(off).normalized()
    import procpose as PP
    PP.rotate_bone_world(arm, f'{S}Hand', Quaternion(axis, ang * w))


class WristFollow:
    """The hand hangs on the wrist like a damped pendulum driven by the wrist's acceleration (overlapping action):
    when the arm starts a move the fingers trail, when it stops they carry on a little and settle.

        wf = WristFollow('Right', pos_fn, t_end)     # pos_fn(t) -> world hand position (Vector / tuple), metres
        wf.apply(arm, t, w=1.0)                     # every frame, after the arm and the hand orientation

    freq (Hz) and zeta set the spring (2.2 Hz, 0.6: a relaxed but toned wrist), gain scales the response, max_deg
    clamps it.  Pure function of t after construction (baked at `rate`)."""

    def __init__(self, side, pos_fn, t_end, rate=60.0, freq=2.2, zeta=0.6, gain=0.6, max_deg=14.0):
        self.S, self.rate, self.max_deg = _side(side), rate, max_deg
        n = int(math.ceil(t_end * rate)) + 3
        X = np.array([tuple(pos_fn(i / rate)) for i in range(n)], dtype=np.float64)
        dt = 1.0 / rate
        # light smoothing of the positions, then acceleration
        Xs = X.copy()
        Xs[1:-1] = 0.25 * X[:-2] + 0.5 * X[1:-1] + 0.25 * X[2:]
        Acc = np.zeros_like(Xs)
        Acc[1:-1] = (Xs[2:] - 2 * Xs[1:-1] + Xs[:-2]) / dt ** 2
        w0 = 2 * math.pi * freq
        x = np.zeros(3)
        v = np.zeros(3)
        out = np.zeros_like(X)
        sub = 4
        h = dt / sub
        for i in range(n):
            a_in = -gain * Acc[i]
            for _ in range(sub):                          # semi-implicit Euler
                v += (a_in - w0 * w0 * x - 2 * zeta * w0 * v) * h
                x += v * h
            out[i] = x
        import acting as AC
        self.off = AC.Baked(out, rate)

    @classmethod
    def from_performer(cls, P, side, t_end, rate=30.0, **kw):
        S = _side(side)
        arm = P.a.arm

        def fn(t):
            P.pose(t)
            return arm.matrix_world @ arm.pose.bones[f'{S}Hand'].head
        return cls(S, fn, t_end, rate=rate, **kw)

    def offset(self, t):
        return Vector(self.off.at(t))

    def apply(self, arm, t, w=1.0):
        S = self.S
        w0, d, nrm, L = _hand_dirs(arm, S)
        _tilt(arm, S, self.offset(t), d, nrm, L, self.max_deg, w)       # x = displacement of the hand's mass (MCP level)


def install(performer, left=None, right=None, wrist=None, seed=None):
    """Make performer.pose(t) end with real hand poses (and the wrist follow).
    left / right: HandTrack, a pose (name / dict), a callable t -> pose, or None (use the Performer's own finger curl,
    mapped by legacy()).  wrist: {'Left': WristFollow, 'Right': WristFollow} or None."""
    orig = performer.pose_arms
    arm = performer.a.arm

    def pose_arms(t):
        orig(t)
        for S, src in (('Left', left), ('Right', right)):
            if isinstance(src, HandTrack):
                p = src.at(t)
            elif callable(src):
                p = src(t)
            elif src is not None:
                p = src
            else:
                b = arm.pose.bones.get(f'{S}Fingers1')
                curl = (b.rotation_euler.x / math.radians(80.0)) if b is not None and b.rotation_mode == 'XYZ' else 0.32
                p = legacy(curl)
            if wrist and S in wrist:
                wrist[S].apply(arm, t)
            pose_hand(arm, S, p, t=t, seed=seed)
    performer.pose_arms = pose_arms
    return performer
