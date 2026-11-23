"""Skin, eyes, hair and clothes for the MakeHuman characters (Cycles)."""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

import mh


def sm(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ---------------------------------------------------------------- head frame
def head_local(ch):
    """Rest-pose body vertices expressed in a head frame (metres):
    hx = right(+x), hy = up from eye line, hz = forward (towards the face)."""
    J = ch['J']
    eL, eR = mh.to_bl(J['eye.L____head']), mh.to_bl(J['eye.R____head'])
    top = mh.to_bl(J['head____tail'])
    eye = (eL + eR) / 2
    s_v = (top[2] - eye[2]) / 0.126
    s_h = (eL[0] - eR[0]) / 0.062
    co = np.array([v.co[:] for v in ch['body'].data.vertices])
    hx = (co[:, 0] - eye[0]) / s_h
    hy = (co[:, 2] - eye[2]) / s_v
    hz = (-(co[:, 1] - eye[1]) + 0.076) / s_h  # 0 = 7.6 cm behind the eye centres
    head_w = np.zeros(len(co))
    hb = ch['rig'].data.bones['head']
    names = {hb.name} | {b.name for b in hb.children_recursive}
    ids = {ch['body'].vertex_groups[n].index for n in names if n in ch['body'].vertex_groups}
    for v in ch['body'].data.vertices:
        for g in v.groups:
            if g.group in ids:
                head_w[v.index] += g.weight
    return hx, hy, hz, head_w, co


def masks(ch, style):
    hx, hy, hz, hw, co = head_local(ch)
    ax = np.abs(hx)
    az = np.arctan2(ax, hz)  # 0 front .. pi back
    ears = (ax > 0.07) & (hy > -0.05) & (hy < 0.045) & (hz > -0.04) & (hz < 0.03)
    # hairline height as a function of azimuth
    hl = np.interp(az, [0.0, 0.45, 0.85, 1.25, 1.5, 1.9, 2.4, 3.15], style['hairline'])
    scalp = sm(hl - 0.004, hl + 0.006, hy) * (hw > 0.3) * (~ears)
    # fade: length grows with height above the hairline on the sides/back, full on top
    top = sm(0.06, 0.11, hy + 0.04 * np.cos(az))
    # beard
    t = np.clip((0.072 - ax) / 0.044, 0, 1)
    cheek = -0.012 - 0.05 * t - 0.012 * np.sin(np.pi * t)
    beard_side = (ax > 0.028) & (hy < cheek)
    mous = (ax <= 0.028) & (hy < -0.053)
    lips_e = ((hx / 0.026) ** 2 + ((hy + 0.07) / 0.0125) ** 2) < 1.0
    lips = lips_e & (hz > 0.02)
    nose = (ax < 0.022) & (hy > -0.06) & (hz > 0.112)
    beard = (beard_side | mous) & (hz > -0.03) & (hy > -0.16) & (hw > 0.35) & (~lips) & (~ears) & (~nose)
    # eyebrows (one band per side)
    bx = (ax - 0.012) / 0.045
    by = 0.024 + style.get('brow_arch', 0.004) * np.sin(np.pi * np.clip(bx, 0, 1)) + style.get('brow_inner', 0.0) * (1 - np.clip(bx, 0, 1))
    brow = (bx > 0) & (bx < 1) & (np.abs(hy - by) < (0.0042 - 0.0017 * np.clip(bx, 0, 1))) & (hz > 0.03)
    return dict(hx=hx, hy=hy, hz=hz, ax=ax, az=az, hw=hw, scalp=scalp, top=top, beard=beard.astype(float),
                lips=lips.astype(float), brow=brow.astype(float), ears=ears, co=co, hl=hl)


def set_group(obj, name, w):
    vg = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
    w = np.asarray(w, dtype=float)
    for val in np.unique(np.round(w[w > 0.001], 3)):
        ids = np.where(np.abs(np.round(w, 3) - val) < 1e-9)[0].tolist()
        vg.add(ids, float(val), 'REPLACE')
    return vg


# ---------------------------------------------------------------- skin
def paint_skin(ch, M, tone, style):
    me = ch['body'].data
    n = len(me.vertices)
    rng = np.random.default_rng(style.get('seed', 1))
    base = np.tile(lin(tone), (n, 1))
    red = lin(style.get('blush', [190, 100, 85]))
    lipc = lin(style.get('lip', [150, 82, 72]))
    dark = lin(style.get('dark', [90, 55, 40]))
    hair = lin(style.get('hair', [25, 18, 14]))
    hx, hy, hz, ax = M['hx'], M['hy'], M['hz'], M['ax']
    face = (hz > 0.0) * (M['hw'] > 0.3)
    mixc = lambda c, col, t: c + (col - c) * np.asarray(t)[:, None]
    c = base
    c = mixc(c, red, 0.25 * np.exp(-(((ax - 0.04) / 0.022) ** 2 + ((hy + 0.03) / 0.02) ** 2)) * face)  # cheeks
    c = mixc(c, red, 0.25 * np.exp(-((hx / 0.012) ** 2 + ((hy + 0.035) / 0.012) ** 2)) * face)  # nose tip
    c = mixc(c, dark, 0.3 * np.exp(-(((ax - 0.031) / 0.017) ** 2 + ((hy + 0.012) / 0.008) ** 2)) * face)  # under-eye
    c = mixc(c, dark, 0.22 * np.exp(-(((ax - 0.031) / 0.02) ** 2 + ((hy - 0.012) / 0.01) ** 2)) * face)  # lid crease
    k = style.get('contour', 0.0)
    if k:
        c = mixc(c, dark, k * 0.55 * np.exp(-(((ax - 0.05) / 0.016) ** 2 + ((hy + 0.045) / 0.022) ** 2)) * face)   # under cheekbones
        c = mixc(c, dark, k * 0.45 * np.exp(-(((ax - 0.062) / 0.012) ** 2 + ((hy - 0.035) / 0.03) ** 2)) * face)   # temples
        c = mixc(c, dark, k * 0.5 * np.clip((ax - 0.045) / 0.03, 0, 1) * np.clip((-hy - 0.07) / 0.04, 0, 1) * face)  # jaw sides
        c = mixc(c, dark, k * 0.4 * np.exp(-(((ax - 0.021) / 0.01) ** 2 + ((hy - 0.004) / 0.016) ** 2)) * face)   # eye sockets (inner)
        hi = lin([255, 236, 220])
        c = mixc(c, hi, k * 0.22 * np.exp(-((hx / 0.008) ** 2 + ((hy + 0.012) / 0.03) ** 2)) * face)              # nose bridge
        c = mixc(c, hi, k * 0.18 * np.exp(-((hx / 0.03) ** 2 + ((hy - 0.07) / 0.03) ** 2)) * face)               # forehead
        c = mixc(c, hi, k * 0.2 * np.exp(-(((ax - 0.045) / 0.012) ** 2 + ((hy + 0.018) / 0.01) ** 2)) * face)     # cheekbone tops
    c = mixc(c, lipc, 0.85 * M['lips'])
    if style.get('stubble', 0) > 0:  # dark skin under the beard hair
        c = mixc(c, dark, style['stubble'] * M['beard'])
    if style.get('lashes') and ch.get('eye_centers') is not None:
        for ec in ch['eye_centers']:
            d = np.linalg.norm(M['co'] - ec, axis=1)
            up_ = (M['co'][:, 2] - ec[2])
            rim = np.clip(1 - np.abs(d - 0.0142) / 0.0016, 0, 1) * (M['co'][:, 1] < ec[1] - 0.004)
            c = mixc(c, hair, style['lashes'] * rim * np.clip(up_ / 0.002 + 0.6, 0.25, 1.0))
    c = mixc(c, hair, 0.75 * M['scalp'] * (M['hw'] > 0.5))  # dark scalp under the hair
    c = mixc(c, hair, 0.55 * M['brow'])
    c *= (1 + (rng.random((n, 1)) - 0.5) * 0.04)
    col = me.color_attributes.new('paint', 'FLOAT_COLOR', 'POINT')
    rgba = np.concatenate([np.clip(c, 0, 1), np.ones((n, 1))], axis=1).astype(np.float32)
    col.data.foreach_set('color', rgba.ravel())


def skin_material(name, sss=0.3):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    vc = nt.nodes.new('ShaderNodeVertexColor'); vc.layer_name = 'paint'
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 60; noise.inputs['Detail'].default_value = 6
    mixn = nt.nodes.new('ShaderNodeMix'); mixn.data_type = 'RGBA'; mixn.blend_type = 'OVERLAY'; mixn.inputs['Factor'].default_value = 0.12
    nt.links.new(vc.outputs['Color'], mixn.inputs['A'])
    nt.links.new(noise.outputs['Color'], mixn.inputs['B'])
    nt.links.new(mixn.outputs['Result'], b.inputs['Base Color'])
    nt.links.new(mixn.outputs['Result'], b.inputs['Subsurface Radius'])
    b.inputs['Subsurface Weight'].default_value = sss
    b.inputs['Subsurface Scale'].default_value = 0.012
    b.inputs['Roughness'].default_value = 0.46
    b.inputs['Specular IOR Level'].default_value = 0.45
    pores = nt.nodes.new('ShaderNodeTexNoise'); pores.inputs['Scale'].default_value = 900; pores.inputs['Detail'].default_value = 2
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.06; bump.inputs['Distance'].default_value = 0.0005
    nt.links.new(pores.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


def eye_material(name, iris):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    norm = nt.nodes.new('ShaderNodeVectorMath'); norm.operation = 'NORMALIZE'
    nt.links.new(tc.outputs['Object'], norm.inputs[0])
    dot = nt.nodes.new('ShaderNodeVectorMath'); dot.operation = 'DOT_PRODUCT'; dot.inputs[1].default_value = (0, -1, 0)
    nt.links.new(norm.outputs['Vector'], dot.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    nt.links.new(dot.outputs['Value'], ramp.inputs['Fac'])
    cr = ramp.color_ramp
    ic = list(lin(iris)) + [1]
    ic2 = list(np.clip(lin(iris) * 1.8, 0, 1)) + [1]
    stops = [(0.0, (0.55, 0.5, 0.48, 1)), (0.78, (0.8, 0.76, 0.72, 1)), (0.855, (0.82, 0.78, 0.74, 1)),
             (0.865, (0.02, 0.015, 0.01, 1)), (0.875, ic), (0.955, ic2), (0.966, (0.003, 0.003, 0.003, 1)), (1.0, (0.003, 0.003, 0.003, 1))]
    cr.elements[0].position, cr.elements[0].color = stops[0]
    cr.elements[1].position, cr.elements[1].color = stops[-1]
    for pos, colr in stops[1:-1]:
        e = cr.elements.new(pos); e.color = colr
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.08
    b.inputs['Coat Weight'].default_value = 1.0
    b.inputs['Coat Roughness'].default_value = 0.02
    b.inputs['Subsurface Weight'].default_value = 0.05
    return m


def hair_material(name, melanin=0.9, redness=0.3, rough=0.32):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    out = nt.nodes['Material Output']
    for nd in list(nt.nodes):
        if nd.type == 'BSDF_PRINCIPLED':
            nt.nodes.remove(nd)
    h = nt.nodes.new('ShaderNodeBsdfHairPrincipled')
    h.parametrization = 'MELANIN'
    h.inputs['Melanin'].default_value = melanin
    h.inputs['Melanin Redness'].default_value = redness
    h.inputs['Roughness'].default_value = rough
    h.inputs['Radial Roughness'].default_value = 0.4
    h.inputs['Coat'].default_value = 0.15
    h.inputs['Random Color'].default_value = 0.12
    nt.links.new(h.outputs[0], out.inputs['Surface'])
    return m


def add_hair(obj, name, mat_index, density_vg, length, count, children=30, length_vg=None, root=0.12, tip=0.03,
             align=(0, 0, 0), normal=1.0, clump=0.0, rough=0.002, rough_end=0.0, kink=None, seed=0, child_len_thr=0.0, steps=4):
    mod = obj.modifiers.new(name, 'PARTICLE_SYSTEM')
    ps = mod.particle_system
    ps.seed = seed
    st = ps.settings
    st.name = name
    st.type = 'HAIR'
    st.use_advanced_hair = True
    st.count = count
    st.emit_from = 'FACE'
    st.use_emit_random = True
    st.distribution = 'RAND'
    # strand length = 4 * |normal_factor * n + align|  (measured), so scale both together
    k = length / (4.0 * math.sqrt(normal * normal + sum(a * a for a in align)))
    st.normal_factor = normal * k
    st.object_align_factor = tuple(a * k for a in align)
    st.child_type = 'INTERPOLATED'
    st.child_percent = 2
    st.rendered_child_count = children
    st.child_radius = 0.004
    st.clump_factor = clump
    st.roughness_1 = rough
    st.roughness_1_size = 1.0
    st.roughness_endpoint = rough_end
    st.root_radius = root
    st.tip_radius = tip
    st.radius_scale = 0.001
    st.use_close_tip = True
    st.display_step = 3
    st.render_step = steps
    st.material = mat_index + 1
    if kink:
        st.kink = 'CURL'
        st.kink_amplitude = kink[0]
        st.kink_frequency = kink[1]
        st.kink_shape = kink[2] if len(kink) > 2 else 0.0
    ps.vertex_group_density = density_vg
    if length_vg:
        ps.vertex_group_length = length_vg
    return mod


# ---------------------------------------------------------------- clothes
def bone_weight_sum(ch, bones):
    body = ch['body']
    ids = {body.vertex_groups[b].index for b in bones if b in body.vertex_groups}
    w = np.zeros(len(body.data.vertices))
    for v in body.data.vertices:
        for g in v.groups:
            if g.group in ids:
                w[v.index] += g.weight
    return w


def make_shell(ch, name, keep, offset, mat, thickness=0.003, subdiv=1, smooth=0):
    """Duplicate the body, keep vertices where keep>0.5, push outward along normals."""
    body = ch['body']
    me = body.data.copy()
    me.name = name
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if me.shape_keys:
        ob.shape_key_clear()
    for vg in body.vertex_groups:
        ob.vertex_groups.new(name=vg.name)
    # copy weights
    for v in body.data.vertices:
        for g in v.groups:
            ob.vertex_groups[body.vertex_groups[g.group].name].add([v.index], g.weight, 'REPLACE')
    nrm = np.array([v.normal[:] for v in me.vertices])
    co = np.array([v.co[:] for v in me.vertices])
    off = np.broadcast_to(np.asarray(offset, dtype=float), (len(co),))
    co = co + nrm * off[:, None]
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    kill = [v for v in bm.verts if keep[v.index] <= 0.5]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bm.to_mesh(me)
    bm.free()
    for col in list(me.color_attributes):
        me.color_attributes.remove(col)
    me.materials.clear()
    if isinstance(mat, (list, tuple)):
        for mm in mat:
            me.materials.append(mm)
    else:
        me.materials.append(mat)
    ob.parent = ch['rig']
    a = ob.modifiers.new('Armature', 'ARMATURE'); a.object = ch['rig']
    if smooth:
        cs = ob.modifiers.new('Smooth', 'SMOOTH'); cs.iterations = smooth; cs.factor = 0.5
    s = ob.modifiers.new('Solid', 'SOLIDIFY'); s.thickness = thickness; s.offset = 1.0; s.use_rim = True
    if subdiv:
        sd = ob.modifiers.new('Subd', 'SUBSURF'); sd.levels = 1; sd.render_levels = subdiv
    return ob


def axis_angle_attr(ob, ch, chains, name):
    """Per-vertex angle around each limb axis (0 = lateral side), stored as a float attribute."""
    me = ob.data
    co = np.array([v.co[:] for v in me.vertices])
    out = np.full(len(co), 9.0)
    arm = ch['rig'].data
    for bones, lateral in chains:
        p0 = np.array(arm.bones[bones[0]].head_local)
        p1 = np.array(arm.bones[bones[-1]].tail_local)
        axis = (p1 - p0) / np.linalg.norm(p1 - p0)
        fwd = np.array([0, -1.0, 0])
        lat = np.asarray(lateral, dtype=float)
        lat = lat - axis * lat.dot(axis); lat /= np.linalg.norm(lat)
        f2 = fwd - axis * fwd.dot(axis) - lat * fwd.dot(lat); f2 /= np.linalg.norm(f2)
        d = co - p0
        t = d @ axis
        r = d - np.outer(t, axis)
        rl = np.linalg.norm(r, axis=1)
        sel = (t > -0.03) & (t < np.linalg.norm(p1 - p0) + 0.03) & (rl < 0.11)
        ang = np.arctan2(r @ f2, r @ lat)
        out[sel] = np.where(np.abs(ang[sel]) < np.abs(out[sel]), ang[sel], out[sel])
    at = me.attributes.new(name, 'FLOAT', 'POINT')
    at.data.foreach_set('value', out.astype(np.float32))


def fabric_material(name, color, rough=0.7, sheen=0.3, wrinkle=0.4, stripe_attr=None, stripe_color=(240, 240, 236), stripes=((0.12, 0.32),)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    base = list(lin(color)) + [1]
    b.inputs['Roughness'].default_value = rough
    b.inputs['Sheen Weight'].default_value = sheen
    b.inputs['Sheen Roughness'].default_value = 0.5
    b.inputs['Specular IOR Level'].default_value = 0.35
    col_out = None
    if stripe_attr:
        at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = stripe_attr
        ab = nt.nodes.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'
        nt.links.new(at.outputs['Fac'], ab.inputs[0])
        acc = None
        for lo, hi in stripes:
            g1 = nt.nodes.new('ShaderNodeMath'); g1.operation = 'GREATER_THAN'; g1.inputs[1].default_value = lo
            l1 = nt.nodes.new('ShaderNodeMath'); l1.operation = 'LESS_THAN'; l1.inputs[1].default_value = hi
            nt.links.new(ab.outputs[0], g1.inputs[0]); nt.links.new(ab.outputs[0], l1.inputs[0])
            mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
            nt.links.new(g1.outputs[0], mul.inputs[0]); nt.links.new(l1.outputs[0], mul.inputs[1])
            if acc is None:
                acc = mul
            else:
                mx = nt.nodes.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'
                nt.links.new(acc.outputs[0], mx.inputs[0]); nt.links.new(mul.outputs[0], mx.inputs[1]); acc = mx
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
        mix.inputs['A'].default_value = base
        mix.inputs['B'].default_value = list(lin(stripe_color)) + [1]
        nt.links.new(acc.outputs[0], mix.inputs['Factor'])
        col_out = mix.outputs['Result']
    # subtle weave/colour variation
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 25
    ov = nt.nodes.new('ShaderNodeMix'); ov.data_type = 'RGBA'; ov.blend_type = 'OVERLAY'; ov.inputs['Factor'].default_value = 0.08
    if col_out is not None:
        nt.links.new(col_out, ov.inputs['A'])
    else:
        ov.inputs['A'].default_value = base
    nt.links.new(noise.outputs['Color'], ov.inputs['B'])
    nt.links.new(ov.outputs['Result'], b.inputs['Base Color'])
    # wrinkles via bump
    wn = nt.nodes.new('ShaderNodeTexNoise'); wn.inputs['Scale'].default_value = 4; wn.inputs['Detail'].default_value = 2
    wn.inputs['Distortion'].default_value = 0.3
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = wrinkle * 0.35; bump.inputs['Distance'].default_value = 0.01
    nt.links.new(wn.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


# ---------------------------------------------------------------- stylised (DMC-like) additions
def parent_keep(ob, ch, bone):
    """Parent ob to a pose bone without moving it (works in any pose)."""
    rig = ch['rig']
    bpy.context.view_layer.update()
    pbn = rig.pose.bones[bone]
    mw = ob.matrix_world.copy()
    ob.parent = rig
    ob.parent_type = 'BONE'
    ob.parent_bone = bone
    parent_world = rig.matrix_world @ pbn.matrix @ Matrix.Translation((0, pbn.bone.length, 0))
    ob.matrix_parent_inverse = parent_world.inverted()
    ob.matrix_basis = mw


def _catmull(P, n):
    P = [P[0]] + list(P) + [P[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return out


def hair_locks(ch, M, mat, n=230, seed=7, top_len=0.06, side_len=0.03, fringe=0.12, width=0.0065, ring=6, seg=4):
    """Chunky, card-like locks (PS2 cinematic hair) as one mesh parented to the head.
    Point attribute 't' runs 0 (root) -> 1 (tip); UVs: u around the lock, v along it."""
    rng = np.random.default_rng(seed)
    me = ch['body'].data
    co = M['co']
    nrm = np.array([v.normal[:] for v in me.vertices])
    hx, hy, hz = M['hx'], M['hy'], M['hz']
    J = ch['J']
    centre = (mh.to_bl(J['head____head']) + mh.to_bl(J['head____tail'])) / 2
    cand = np.where((M['scalp'] > 0.6) & (hy > 0.035) & (M['hw'] > 0.5))[0]
    rng.shuffle(cand)
    roots = []
    for i in cand:
        if all(np.linalg.norm(co[i] - co[j]) > 0.0085 for j in roots[-400:]):
            roots.append(i)
        if len(roots) >= n:
            break
    up, fwd = np.array([0, 0, 1.0]), np.array([0, -1.0, 0])
    verts, faces, tvals, uvs = [], [], [], []
    angs = np.linspace(0, 2 * np.pi, ring, endpoint=False)
    for i in roots:
        p, nv = co[i], nrm[i]
        x_, y_, z_ = hx[i], hy[i], hz[i]
        side = abs(x_) > 0.055 and y_ < 0.085
        front = z_ > 0.045
        sx = np.array([np.sign(x_), 0, 0]) * 0.5 + np.array([0.35, 0, 0])
        if side:
            d0 = nv * 0.3 + fwd * 0.35 + up * -0.2 + sx * 0.2; L = side_len * (0.85 + 0.3 * rng.random()); bend = up * -0.8
        elif front:
            d0 = nv * 0.35 + fwd * 0.85 + up * 0.05 + sx * 0.18 * rng.random(); L = top_len * (0.95 + 0.4 * rng.random()); bend = up * -1.3 + fwd * 0.2
        else:
            d0 = nv * 0.3 + fwd * 0.75 + up * 0.35 + sx * 0.25 * rng.random(); L = top_len * (1.05 + 0.45 * rng.random()); bend = up * -0.9 + fwd * 0.3
        d0 = d0 / np.linalg.norm(d0) + (rng.random(3) - 0.5) * 0.16
        d = d0 / np.linalg.norm(d0)
        P = [p - nv * 0.003]
        for k in range(4):
            d = d + bend * 0.22 + (rng.random(3) - 0.5) * 0.05
            out_ = (P[-1] - centre) / np.linalg.norm(P[-1] - centre)
            if d.dot(out_) < 0.05:
                d = d + out_ * (0.05 - d.dot(out_))
            d /= np.linalg.norm(d)
            P.append(P[-1] + d * (L / 4))
        path = _catmull([np.asarray(q) for q in P], seg)
        m = len(path)
        wscale = width * (0.8 + 0.4 * rng.random())
        twist = (rng.random() - 0.5) * 0.8
        base = len(verts)
        for k, q in enumerate(path):
            t = k / (m - 1)
            tan = path[min(k + 1, m - 1)] - path[max(k - 1, 0)]
            tan /= np.linalg.norm(tan) + 1e-12
            out = q - centre
            out -= tan * out.dot(tan)
            out /= np.linalg.norm(out) + 1e-12
            side_v = np.cross(tan, out)
            a = twist * t
            ca, sa = math.cos(a), math.sin(a)
            side_v, out = side_v * ca + out * sa, out * ca - side_v * sa
            r = (1.0 - t ** 1.4) * (1.0 + 0.35 * math.sin(t * 3.1))
            for j, ang in enumerate(angs):
                off = side_v * math.cos(ang) * wscale * r + out * math.sin(ang) * wscale * 0.36 * r
                verts.append(q + off)
                tvals.append(t)
        for k in range(m - 1):
            for j in range(ring):
                a0 = base + k * ring + j
                a1 = base + k * ring + (j + 1) % ring
                faces.append((a0, a1, a1 + ring, a0 + ring))
        for k in range(m):
            for j in range(ring):
                uvs.append((j / ring, k / (m - 1)))
    mesh = bpy.data.meshes.new(ch['name'] + '_locks')
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    at = mesh.attributes.new('t', 'FLOAT', 'POINT')
    at.data.foreach_set('value', np.asarray(tvals, dtype=np.float32))
    uvl = mesh.uv_layers.new(name='UVMap')
    loop_uv = []
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            loop_uv.append(uvs[vi])
    uvl.data.foreach_set('uv', np.asarray(loop_uv, dtype=np.float32).ravel())
    ob = bpy.data.objects.new(ch['name'] + '_locks', mesh)
    bpy.context.scene.collection.objects.link(ob)
    mesh.materials.append(mat)
    sd = ob.modifiers.new('sub', 'SUBSURF'); sd.levels = 0; sd.render_levels = 1
    ob.matrix_world = ch['body'].matrix_world.copy()
    parent_keep(ob, ch, 'head')
    return ob


def silver_hair_material(name, root=(0.04, 0.035, 0.035), tip=(0.62, 0.64, 0.68)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeAttribute'); sep.attribute_name = 't'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.1
    ramp.color_ramp.elements[0].color = root + (1,)
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = tip + (1,)
    nt.links.new(sep.outputs['Fac'], ramp.inputs['Fac'])
    wave = nt.nodes.new('ShaderNodeTexNoise')
    wave.inputs['Scale'].default_value = 1.0
    wave.inputs['Detail'].default_value = 6
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (40, 1.5, 1)
    nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 0.85
    nt.links.new(ramp.outputs['Color'], mul.inputs['A'])
    nt.links.new(wave.outputs['Color'], mul.inputs['B'])
    nt.links.new(mp.outputs['Vector'], wave.inputs['Vector'])
    nt.links.new(mul.outputs['Result'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.26
    b.inputs['Specular IOR Level'].default_value = 0.8
    b.inputs['Anisotropic'].default_value = 0.6
    b.inputs['Coat Weight'].default_value = 0.15
    b.inputs['Sheen Weight'].default_value = 0.3
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35
    nt.links.new(wave.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m


def chain(ch, mat, drop=0.055, r=0.0017):
    """Silver chain around the neck, parented to the upper spine."""
    J = ch['J']
    c = mh.to_bl(J['neck01____head'])
    cu = bpy.data.curves.new(ch['name'] + '_chain', 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = r
    cu.bevel_resolution = 3
    sp = cu.splines.new('NURBS')
    pts = []
    for a in np.linspace(0, 2 * math.pi, 17)[:-1]:
        x = math.sin(a) * 0.072
        y = -math.cos(a) * 0.062 + 0.004
        z = c[2] + 0.012 - drop * max(0.0, math.cos(a)) ** 2
        pts.append((x, y + c[1], z, 1))
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = q
    sp.use_cyclic_u = True
    sp.order_u = 4
    ob = bpy.data.objects.new(ch['name'] + '_chain', cu)
    bpy.context.scene.collection.objects.link(ob)
    cu.materials.append(mat)
    ob.matrix_world = ch['body'].matrix_world.copy()
    parent_keep(ob, ch, 'spine01')
    return ob


def add_smirk(ch, side='L', amount=0.6, unit='mouth-corner-puller'):
    """One-sided smile: the expression unit applied to one half of the face only."""
    body = ch['body']
    race = ch.get('race_mix') or {'african': 1 / 3, 'asian': 1 / 3, 'caucasian': 1 / 3}
    D = mh.expression_deltas(race, [unit])[unit][ch['used']]
    Db = mh.to_bl(D)
    co = np.array([v.co[:] for v in body.data.vertices])
    s = 1 if side == 'L' else -1
    w = np.clip((co[:, 0] * s + 0.004) / 0.012, 0, 1)
    if body.data.shape_keys is None:
        body.shape_key_add(name='Basis', from_mix=False)
    basis = np.array([v.co[:] for v in body.data.shape_keys.key_blocks['Basis'].data])
    sk = body.shape_key_add(name='smirk', from_mix=False)
    sk.data.foreach_set('co', (basis + Db * w[:, None]).astype(np.float32).ravel())
    sk.value = amount
