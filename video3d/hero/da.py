"""PS2-era 'Capcom cutscene' art direction: hand-painted skin texture, painted eyes."""
import math

import bpy
import numpy as np
from mathutils import Vector

import mh
import uvbake

TEX = 2048


def sm(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def gauss(x, s):
    return np.exp(-(x / s) ** 2)


def srgb(c):
    return np.asarray(c, dtype=np.float32) / 255.0


def mix(c, col, t):
    return c + (np.asarray(col, dtype=np.float32) - c) * np.asarray(t, dtype=np.float32)[..., None]


def vnoise(x, y, seed=0):
    xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    xf, yf = (x - xi).astype(np.float32), (y - yi).astype(np.float32)
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    k = (seed * 2654435761) & 0xFFFFFFFF

    def h(a, b):
        n = (a * 374761393 + b * 668265263 + k) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF).astype(np.float32) / 65535.0
    return (h(xi, yi) * (1 - u) + h(xi + 1, yi) * u) * (1 - v) + (h(xi, yi + 1) * (1 - u) + h(xi + 1, yi + 1) * u) * v


def fbm2(x, y, seed=0, octaves=4):
    out, amp, tot, f = 0.0, 1.0, 0.0, 1.0
    for o in range(octaves):
        out = out + amp * vnoise(x * f, y * f, seed + o * 17)
        tot += amp
        amp *= 0.5
        f *= 2.03
    return out / tot


# ---------------------------------------------------------------- per-vertex data
def weight_sum(ch, bones):
    body = ch['body']
    ids = {body.vertex_groups[b].index for b in bones if b in body.vertex_groups}
    w = np.zeros(len(body.data.vertices), dtype=np.float32)
    for v in body.data.vertices:
        for g in v.groups:
            if g.group in ids:
                w[v.index] += g.weight
    return w


def target_mask(ch, name):
    B = mh.base()
    t = B.target(name)
    m = np.zeros(len(B.v), dtype=np.float32)
    if t is not None:
        m[t[0]] = np.linalg.norm(t[1], axis=1)
    m = m[ch['used']]
    return m / (m.max() + 1e-9)


def limb_coords(co, p0, p1, lateral, fwd=(0, -1.0, 0)):
    """t along the limb (0..1), angle around it (0 = lateral side, + = forward), radial distance."""
    p0, p1 = np.asarray(p0, dtype=float), np.asarray(p1, dtype=float)
    L = np.linalg.norm(p1 - p0)
    a = (p1 - p0) / L
    lat = np.asarray(lateral, dtype=float)
    lat = lat - a * lat.dot(a)
    lat /= np.linalg.norm(lat)
    f = np.asarray(fwd, dtype=float)
    f = f - a * f.dot(a) - lat * f.dot(lat)
    f /= np.linalg.norm(f)
    d = co - p0
    t = (d @ a) / L
    r = d - np.outer(d @ a, a)
    return t.astype(np.float32), np.arctan2(r @ f, r @ lat).astype(np.float32), np.linalg.norm(r, axis=1).astype(np.float32)


def vertex_data(ch):
    """Everything the painters need, per body vertex (rest pose, object space)."""
    if 'vd' in ch:
        return ch['vd']
    B = mh.base()
    body, rig = ch['body'], ch['rig']
    me = body.data
    n = len(me.vertices)
    co = np.zeros(n * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(n, 3)
    nr = np.zeros(n * 3, dtype=np.float32)
    me.vertices.foreach_get('normal', nr)
    nr = nr.reshape(n, 3)
    V0 = mh.to_bl(B.v[ch['used']])
    J0 = mh.joint_positions(B.v)
    E0 = (mh.to_bl(J0['eye.L____head']) + mh.to_bl(J0['eye.R____head'])) / 2
    can = np.stack([V0[:, 0] - E0[0], V0[:, 2] - E0[2], -(V0[:, 1] - E0[1])], axis=1).astype(np.float32)
    hb = rig.data.bones['head']
    head_bones = [hb.name] + [b.name for b in hb.children_recursive]
    J = {k: mh.to_bl(v) for k, v in ch['J'].items()}
    vd = dict(co=co, nr=nr, can=can, J=J,
              hw=weight_sum(ch, head_bones),
              w_neck=weight_sum(ch, ['neck01', 'neck02', 'neck03']),
              w_torso=weight_sum(ch, ['spine01', 'spine02', 'spine03', 'spine04', 'spine05', 'breast.L', 'breast.R', 'clavicle.L', 'clavicle.R',
                                      'shoulder01.L', 'shoulder01.R', 'neck01', 'root', 'pelvis.L', 'pelvis.R']),
              w_arm=weight_sum(ch, [f'{b}.{s}' for s in 'LR' for b in ('upperarm01', 'upperarm02', 'lowerarm01', 'lowerarm02')]),
              w_leg=weight_sum(ch, [f'{b}.{s}' for s in 'LR' for b in ('upperleg01', 'upperleg02', 'lowerleg01', 'lowerleg02')]),
              w_foot=weight_sum(ch, [f'foot.{s}' for s in 'LR'] + [f'toe{i}-{j}.{s}' for s in 'LR' for i in range(1, 6) for j in range(1, 4)]),
              up=target_mask(ch, 'mouth/mouth-upperlip-volume-incr'), lo=target_mask(ch, 'mouth/mouth-lowerlip-volume-incr'),
              clo=np.maximum(target_mask(ch, 'expression/units/caucasian/eye-left-closure'), target_mask(ch, 'expression/units/caucasian/eye-right-closure')))
    hand_bones = [b.name for s in 'LR' for b in [rig.data.bones[f'wrist.{s}']] + list(rig.data.bones[f'wrist.{s}'].children_recursive)]
    vd['w_hand'] = weight_sum(ch, hand_bones)
    vd['w_fingers'] = weight_sum(ch, [b for b in hand_bones if b.startswith('finger')])
    vd['w_pelvis'] = weight_sum(ch, ['root', 'pelvis.L', 'pelvis.R', 'spine05'])
    # limb parameterisation
    arm_t = np.full(n, -1.0, dtype=np.float32)
    arm_a = np.zeros(n, dtype=np.float32)
    leg_t = np.full(n, -1.0, dtype=np.float32)
    leg_a = np.zeros(n, dtype=np.float32)
    for s, sx in (('L', 1), ('R', -1)):
        t, a, r = limb_coords(co, J[f'upperarm01.{s}____head'], J[f'wrist.{s}____head'], (sx, 0, 0.6))
        sel = (co[:, 0] * sx > 0.02) & (r < 0.13) & (t > -0.25) & (t < 1.2)
        arm_t[sel], arm_a[sel] = t[sel], a[sel]
        t, a, r = limb_coords(co, J[f'upperleg01.{s}____head'], J[f'foot.{s}____head'], (sx, 0, 0))
        sel = (co[:, 0] * sx > 0.0) & (t > -0.3) & (t < 1.2)
        leg_t[sel], leg_a[sel] = t[sel], a[sel]
    vd.update(arm_t=arm_t, arm_a=arm_a, leg_t=leg_t, leg_a=leg_a)
    vd['arm_cs'] = np.stack([np.cos(arm_a), np.sin(arm_a)], axis=1)
    vd['leg_cs'] = np.stack([np.cos(leg_a), np.sin(leg_a)], axis=1)
    vd['eye_c'] = [np.array(e.location[:], dtype=np.float32) for e in ch['eyes']]
    ev = np.array([v.co[:] for v in ch['eyes'][0].data.vertices])
    vd['eye_r'] = float(np.percentile(np.linalg.norm(ev, axis=1), 60))
    ch['vd'] = vd
    return vd


class Texels:
    """Per-texel access to the per-vertex data (valid texels only, as 1-D arrays)."""

    def __init__(self, ch, S=TEX):
        self.R = uvbake.raster(S)
        self.S = S
        self.valid = self.R['tri'] >= 0
        self.vids = self.R['tv'][self.R['tri'][self.valid]]
        self.b = self.R['bary'][self.valid]
        self.vd = vertex_data(ch)
        self.n = int(self.valid.sum())
        self._cache = {}

    def get(self, key):
        if key not in self._cache:
            a = np.asarray(self.vd[key], dtype=np.float32)
            if a.ndim == 1:
                self._cache[key] = (a[self.vids] * self.b).sum(axis=1)
            else:
                self._cache[key] = (a[self.vids] * self.b[:, :, None]).sum(axis=1)
        return self._cache[key]

    def image(self, rgb, alpha=None, name='tex', bleed=10, down=1):
        out = np.zeros((self.S, self.S, 3), dtype=np.float32)
        out[self.valid] = np.clip(rgb, 0, 1)
        out = uvbake.dilate(out, self.valid, bleed)
        if alpha is None:
            a = np.ones((self.S, self.S, 1), dtype=np.float32)
        else:
            a = np.zeros((self.S, self.S), dtype=np.float32)
            a[self.valid] = alpha
            a = uvbake.dilate(a[..., None], self.valid, bleed)
        arr = np.concatenate([out, a], axis=2)
        if down > 1:                      # PS2-size texture: block average
            S2 = self.S // down
            arr = arr.reshape(S2, down, S2, down, 4).mean(axis=(1, 3))
        return uvbake.to_image(name, arr)


# ---------------------------------------------------------------- skin
def paint_skin(ch, P, T=None):
    """Hand-painted style skin: baked soft light, contouring, lash lines, brows, lips."""
    T = T or Texels(ch)
    vd = T.vd
    can, pos, nr, hw = T.get('can'), T.get('co'), T.get('nr'), T.get('hw')
    nr = nr / (np.linalg.norm(nr, axis=1, keepdims=True) + 1e-9)
    cx, cy, cz = can[:, 0], can[:, 1], can[:, 2]
    ax = np.abs(cx)
    face = sm(0.05, 0.4, hw) * sm(-0.06, -0.02, cz)
    tone, shadow, deep = srgb(P['skin']), srgb(P['skin_shadow']), srgb(P['skin_deep'])
    blush, lipc, browc, lash = srgb(P['blush']), srgb(P['lip']), srgb(P['brow']), srgb(P.get('lash', [18, 14, 14]))
    seed = P.get('seed', 1)
    if P.get('base_tex'):
        # photo-based MakeHuman skin (CC0) as the base layer, graded towards the wanted tone
        import mhassets
        tex = mhassets.load_pixels(P['base_tex'])[..., :3]
        if tex.shape[0] != T.S:
            idx = (np.arange(T.S) * tex.shape[0] // T.S)
            tex = tex[idx][:, idx]
        c = tex[T.valid].astype(np.float32)
        ref = c[(hw > 0.5) & (cz > 0.0)].mean(axis=0)
        c = c * (tone / ref)[None, :]
        c = (c - tone) * P.get('tex_contrast', 1.25) + tone
    else:
        # base tone with slow variation
        c = np.tile(tone, (T.n, 1))
        c = c * (1 + (fbm2(pos[:, 0] * 30, (pos[:, 2] + pos[:, 1]) * 30, seed, 3) - 0.5)[:, None] * 0.07)
    # ---- baked soft key light + sky (painted shading, PS2 style)
    L = np.array(P.get('bake_light', (-0.35, -0.55, 0.76)), dtype=np.float32)
    L /= np.linalg.norm(L)
    lam = np.clip(nr @ L, -1, 1)
    sky = nr[:, 2] * 0.5 + 0.5
    shade = np.clip(0.35 + 0.5 * sm(-0.35, 0.85, lam) + 0.22 * sky, 0, 1.08)
    k = P.get('bake', 0.75)
    c = mix(c, shadow, k * sm(0.78, 0.45, shade))
    c = mix(c, deep, k * 0.6 * sm(0.5, 0.2, shade))
    c = c * (1 + 0.1 * k * sm(0.9, 1.05, shade))[:, None]
    # ---- face colour zones
    c = mix(c, blush, 0.22 * gauss(ax - 0.043, 0.02) * gauss(cy + 0.035, 0.022) * face)      # cheeks
    c = mix(c, blush, 0.25 * gauss(cx, 0.014) * gauss(cy + 0.04, 0.013) * face)              # nose tip
    c = mix(c, blush, 0.3 * sm(0.066, 0.08, ax) * sm(-0.065, -0.03, cy) * sm(0.02, -0.02, cy) * sm(0.02, 0.3, hw))  # ears
    # ---- ambient occlusion style shadows
    eye_d = np.minimum(np.linalg.norm(pos - vd['eye_c'][0], axis=1), np.linalg.norm(pos - vd['eye_c'][1], axis=1))
    er = vd['eye_r']
    c = mix(c, shadow, 0.42 * gauss(ax - 0.031, 0.02) * gauss(cy - 0.004, 0.013) * face)       # eye sockets
    c = mix(c, deep, 0.22 * gauss(ax - 0.02, 0.008) * gauss(cy - 0.004, 0.012) * face)         # inner corners / nose root sides
    c = mix(c, shadow, 0.45 * gauss(ax - 0.014, 0.006) * sm(-0.045, -0.03, cy) * sm(0.012, -0.004, cy) * face)  # nose flanks
    c = mix(c, deep, 0.5 * gauss(cx, 0.016) * gauss(cy + 0.0535, 0.0045) * face)               # under the nose
    c = mix(c, shadow, 0.5 * gauss(cx, 0.022) * gauss(cy + 0.0855, 0.006) * face)              # under the lower lip
    kc = P.get('contour', 1.0)
    c = mix(c, shadow, 0.55 * kc * gauss(ax - 0.05, 0.015) * gauss(cy + 0.052, 0.026) * face)   # under cheekbones
    c = mix(c, shadow, 0.4 * kc * sm(0.05, 0.07, ax) * gauss(cy - 0.03, 0.03) * face)           # temples
    c = mix(c, shadow, 0.45 * kc * sm(0.035, 0.06, ax) * sm(-0.07, -0.1, cy) * face)            # jaw sides
    c = mix(c, shadow, 0.35 * kc * gauss(cx, 0.03) * gauss(cy - 0.014, 0.006) * sm(0.012, 0.02, ax) * face)  # under the brow ridge
    c = mix(c, deep, 0.75 * sm(-0.25, -0.75, nr[:, 2]) * sm(0.02, 0.3, hw + T.get('w_neck')))  # under jaw / chin
    c = mix(c, deep, 0.9 * sm(-0.5, -0.85, nr[:, 2]) * gauss(cx, 0.02) * gauss(cy + 0.047, 0.008) * face)   # nostrils
    hi = srgb(P.get('highlight', [255, 240, 226]))
    c = mix(c, hi, 0.34 * gauss(cx, 0.005) * sm(-0.042, -0.02, cy) * sm(0.014, -0.005, cy) * face)   # nose bridge
    c = mix(c, hi, 0.26 * gauss(ax - 0.044, 0.013) * gauss(cy + 0.017, 0.008) * face)               # cheekbone tops
    c = mix(c, hi, 0.2 * gauss(ax - 0.03, 0.012) * gauss(cy - 0.026, 0.005) * face)                  # brow bone
    c = mix(c, hi, 0.2 * gauss(cx, 0.028) * gauss(cy - 0.045, 0.018) * face)                        # forehead
    c = mix(c, hi, 0.2 * gauss(cx, 0.012) * gauss(cy + 0.097, 0.008) * face)                        # chin
    c = mix(c, hi, 0.18 * gauss(cx, 0.01) * gauss(cy + 0.0595, 0.0025) * face)                      # cupid's bow edge
    # ---- lips (geometry-driven masks)
    up, lo = T.get('up'), T.get('lo')
    lips_u = sm(P.get('lip_u', (0.22, 0.4))[0], P.get('lip_u', (0.22, 0.4))[1], up)
    lips_l = sm(P.get('lip_l', (0.3, 0.5))[0], P.get('lip_l', (0.3, 0.5))[1], lo) * sm(-0.084, -0.079, cy)
    fwd = -nr[:, 1]
    ls = P.get('lip_strength', 1.0)
    c = mix(c, lipc * 0.74, lips_u * 0.9 * ls)
    c = mix(c, lipc, lips_l * 0.85 * ls)
    c = mix(c, hi, 0.2 * lips_l * gauss(cx, 0.01) * gauss(cy + 0.0745, 0.003))
    lipzone = np.maximum(lips_u, lips_l)
    c = mix(c, srgb([52, 22, 22]), 0.85 * sm(0.45, 0.05, fwd) * sm(0.2, 0.6, np.maximum(up, lo)) * gauss(cy + 0.0672, 0.004) * face)  # mouth line
    c = mix(c, deep, 0.45 * gauss(ax - 0.0265, 0.004) * gauss(cy + 0.0675, 0.004) * face)        # mouth corners
    # ---- eyebrows: tapered band with hair strokes
    b = P['brows']
    t = (ax - b['x0']) / (b['x1'] - b['x0'])
    tc = np.clip(t, 0, 1)
    yb = b['y0'] + b['rise'] * tc + b['arch'] * np.sin(np.pi * np.clip(tc * 1.1, 0, 1)) - b['drop'] * sm(0.65, 1.0, tc)
    th = b['thick'] * (1.0 - 0.72 * tc ** 1.3)
    strokes = fbm2((cy - yb) * 2600 - ax * 500, ax * 260 + (cy - yb) * 120, seed + 5, 2)
    bm = sm(th / 2 + 0.0007, th / 2 - 0.0005, np.abs(cy - yb)) * sm(-0.06, 0.05, t) * sm(1.02, 0.86, t) * sm(0.0, 0.01, cz) * face
    c = mix(c, browc, bm * (0.78 + 0.22 * sm(0.3, 0.6, strokes)))
    # ---- lash lines and lid crease (follow the real eyelid edge)
    upper = pos[:, 2] > np.where(pos[:, 0] > 0, vd['eye_c'][0][2], vd['eye_c'][1][2]) - 0.0005
    near = sm(er + 0.004, er + 0.002, eye_d) * face
    outer = sm(0.026, 0.04, ax)
    clo = T.get('clo')
    edge_up = np.maximum(sm(-0.1, -0.45, nr[:, 2]), sm(P.get('lash_clo', 0.5), 0.8, clo)) * near * upper
    edge_lo = sm(0.3, 0.65, nr[:, 2]) * near * (~upper)
    c = mix(c, shadow, 0.5 * near * upper)                                                       # soft lid shade
    c = mix(c, deep, 0.3 * gauss(eye_d - (er + 0.004), 0.004) * face)                            # smoky ring around the eye
    c = mix(c, lash, np.clip(0.95 * edge_up + 0.4 * edge_lo * (0.2 + 0.8 * outer), 0, 1))
    c = mix(c, shadow, 0.4 * gauss(eye_d - (er + 0.0085), 0.002) * upper * face)                 # lid crease
    c = mix(c, lash, 0.7 * sm(0.0012, 0.0004, np.abs((cy - 0.0005) - (ax - 0.0435) * 0.45)) * sm(0.0425, 0.045, ax) * sm(0.0505, 0.047, ax) * face)  # outer flick
    # ---- stubble
    if P.get('stubble', 0) > 0:
        tj = np.clip((0.07 - ax) / 0.045, 0, 1)
        line = -0.022 - 0.045 * tj
        bz = (np.where(ax > 0.027, sm(line + 0.004, line - 0.006, cy), sm(-0.052, -0.058, cy))) * sm(-0.08, -0.03, cz) * sm(0.1, 0.5, hw) * (1 - lipzone)
        bz = bz * sm(-0.2, -0.13, cy)
        grain = vnoise(pos[:, 0] * 2400, pos[:, 2] * 2400 + pos[:, 1] * 1700, seed + 9)
        c = mix(c, srgb(P.get('stubble_col', [70, 66, 70])), P['stubble'] * bz * (0.45 + 0.55 * grain))
    # ---- scalp under the hair: hair shadow colour
    az = np.arctan2(ax, cz + 0.095)
    hl = np.interp(az, P['hairline_az'], P['hairline_y'])
    scalp = sm(hl - 0.003, hl + 0.005, cy) * sm(0.2, 0.6, hw)
    ears = (ax > 0.066) & (cy > -0.06) & (cy < 0.012) & (cz > -0.14) & (cz < -0.06)
    scalp = scalp * (~ears)
    c = mix(c, srgb(P['scalp']), 0.92 * scalp)
    # ---- fingerless gloves painted on the hands
    if P.get('glove') is not None:
        wh, wf = T.get('w_hand'), T.get('w_fingers')
        gl = sm(0.45, 0.6, wh - wf) * sm(0.55, 0.4, wf)
        gcol = srgb(P['glove']) * (0.55 + 0.75 * shade)[:, None]
        c = mix(c, gcol, gl)
    # ---- soft overall grain
    c = c * (1 + (vnoise(pos[:, 0] * 900, pos[:, 2] * 900 + pos[:, 1] * 700, seed + 3) - 0.5)[:, None] * 0.035)
    return T.image(c, name=ch['name'] + '_skin', bleed=12, down=P.get('down', 2)), T


def skin_material(name, img, rough=0.72, spec=0.14, closest=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = 'Closest' if closest else 'Linear'
    nt.links.new(tx.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Subsurface Weight'].default_value = 0.0
    return m


def eye_material(name, iris, iris_in=None, sclera=(146, 144, 150)):
    """Painted eye: dark limbal ring, two-tone iris, pupil and a fixed catch-light."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nrm = nt.nodes.new('ShaderNodeVectorMath')
    nrm.operation = 'NORMALIZE'
    nt.links.new(tc.outputs['Object'], nrm.inputs[0])
    dot = nt.nodes.new('ShaderNodeVectorMath')
    dot.operation = 'DOT_PRODUCT'
    dot.inputs[1].default_value = (0, -1, 0)
    nt.links.new(nrm.outputs['Vector'], dot.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(dot.outputs['Value'], ramp.inputs['Fac'])
    lin = lambda c: tuple(float(x) for x in (np.where(np.asarray(c) / 255 <= 0.04045, np.asarray(c) / 255 / 12.92, ((np.asarray(c) / 255 + 0.055) / 1.055) ** 2.4))) + (1.0,)
    i_out = lin(iris)
    i_in = lin(iris_in if iris_in is not None else np.clip(np.asarray(iris) * 1.5 + 25, 0, 255))
    scl = lin(sclera)
    scl_edge = lin(np.asarray(sclera) * np.array([0.72, 0.62, 0.62]))
    stops = [(0.0, scl_edge), (0.55, scl_edge), (0.8, scl), (0.852, scl), (0.861, (0.004, 0.005, 0.008, 1)), (0.876, i_out),
             (0.935, i_in), (0.953, i_in), (0.96, (0.002, 0.002, 0.002, 1)), (1.0, (0.002, 0.002, 0.002, 1))]
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = stops[0]
    cr.elements[1].position, cr.elements[1].color = stops[-1]
    for pos, colr in stops[1:-1]:
        e = cr.elements.new(pos)
        e.color = colr
    # fixed painted catch-light (upper-left of the iris), like a baked PS2 eye texture
    d2 = Vector((0.16, -1, 0.2)).normalized()
    dot2 = nt.nodes.new('ShaderNodeVectorMath')
    dot2.operation = 'DOT_PRODUCT'
    dot2.inputs[1].default_value = d2
    nt.links.new(nrm.outputs['Vector'], dot2.inputs[0])
    gt = nt.nodes.new('ShaderNodeMath')
    gt.operation = 'GREATER_THAN'
    gt.inputs[1].default_value = math.cos(math.radians(4.2))
    nt.links.new(dot2.outputs['Value'], gt.inputs[0])
    mixn = nt.nodes.new('ShaderNodeMix')
    mixn.data_type = 'RGBA'
    nt.links.new(gt.outputs[0], mixn.inputs['Factor'])
    nt.links.new(ramp.outputs['Color'], mixn.inputs['A'])
    mixn.inputs['B'].default_value = (1, 1, 1, 1)
    nt.links.new(mixn.outputs['Result'], b.inputs['Base Color'])
    nt.links.new(gt.outputs[0], b.inputs['Emission Strength'])
    b.inputs['Emission Color'].default_value = (1, 1, 1, 1)
    b.inputs['Roughness'].default_value = 0.25
    b.inputs['Specular IOR Level'].default_value = 0.4
    return m
