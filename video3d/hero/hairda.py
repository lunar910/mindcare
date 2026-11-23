"""PS2-style hair: a scalp cap plus chunky polygon 'cards' with a painted strand texture."""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import da
import look
import mh
import uvbake


def u_dir(theta, phi):
    t, p = math.radians(theta), math.radians(phi)
    return np.array([math.sin(t) * math.sin(p), -math.sin(t) * math.cos(p), math.cos(t)])


def slerp(a, b, t):
    d = float(np.clip(a.dot(b), -1, 1))
    om = math.acos(d)
    if om < 1e-5:
        return a.copy()
    return (math.sin((1 - t) * om) * a + math.sin(t * om) * b) / math.sin(om)


def head_frame(ch):
    vd = da.vertex_data(ch)
    J = vd['J']
    E = (J['eye.L____head'] + J['eye.R____head']) / 2
    s = (J['head____tail'][2] - E[2]) / 0.112
    C = E + np.array([0, 0.091 * s, 0.017 * s])
    return E, C, s


def strand_texture(name, light, dark, seed=3, W=128, H=512, down=1):
    """u across the lock, v from root (0) to tip (1). Painted streaks, root shadow, soft sheen band, split tips."""
    rng = np.random.default_rng(seed)
    v, u = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = (u + 0.5) / W, (v + 0.5) / H
    streak = da.fbm2(u * 22 + da.vnoise(v * 3, u * 2, seed) * 1.2, v * 2.2, seed + 1, 3)
    fine = da.vnoise(u * 70, v * 5, seed + 2)
    val = 0.56 + 0.5 * (streak - 0.5) * 2 + 0.2 * (fine - 0.5)
    val = val * (0.52 + 0.48 * da.sm(0.0, 0.2, v))                         # darker at the root
    val = val + 0.2 * da.gauss(v - 0.36, 0.11) + 0.08 * da.gauss(v - 0.7, 0.08)  # painted sheen
    val = val * (1 - 0.55 * (np.abs(u - 0.5) * 2) ** 2.2)                   # lock edges fall into shadow
    val = val * (1 - 0.25 * da.sm(0.8, 1.0, v))
    val = np.clip(val, 0, 1)
    col = np.asarray(dark, dtype=np.float32) + (np.asarray(light, dtype=np.float32) - np.asarray(dark, dtype=np.float32)) * val[..., None]
    teeth = np.abs(((u * 3.0 + da.vnoise(u * 6, v * 0 + 1, seed + 5) * 0.6) % 1.0) - 0.5) * 2    # 0 at tooth centre
    tip = 0.8 + 0.2 * (1 - teeth) ** 0.7
    alpha = (v < tip).astype(np.float32)
    arr = np.concatenate([col, alpha[..., None]], axis=2)
    if down > 1:
        arr = arr.reshape(H // down, down, W // down, down, 4).mean(axis=(1, 3))
    return uvbake.to_image(name, arr)


def hair_material(name, img, rough=0.6, spec=0.18, closest=True):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.extension = 'EXTEND'
    tx.interpolation = 'Closest' if closest else 'Linear'
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'shade'
    mul = nt.nodes.new('ShaderNodeMix')
    mul.data_type = 'RGBA'
    mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    nt.links.new(tx.outputs['Color'], mul.inputs['A'])
    nt.links.new(at.outputs['Color'], mul.inputs['B'])
    nt.links.new(mul.outputs['Result'], b.inputs['Base Color'])
    gt = nt.nodes.new('ShaderNodeMath')
    gt.operation = 'GREATER_THAN'
    gt.inputs[1].default_value = 0.5
    nt.links.new(tx.outputs['Alpha'], gt.inputs[0])
    nt.links.new(gt.outputs[0], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    return m


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


def curtain_style(seed=4):
    """Layered, jaw-length cut that falls over the forehead (cards as dicts)."""
    rng = np.random.default_rng(seed)
    cards = []

    def rel_theta(phi):
        a = abs(((phi + 180) % 360) - 180)
        return float(np.interp(a, [0, 30, 60, 90, 130, 180], [63, 66, 76, 90, 98, 103]))

    def add(phi, length, width, layer, root_f, lift_rel, flick=0.0, theta=None, bump=0.004, shade=1.0, t_blend=0.55):
        cards.append(dict(phi=phi + float(rng.normal(0, 1.5)), theta=theta if theta is not None else rel_theta(phi) + float(rng.normal(0, 1.5)),
                          length=length * float(1 + rng.normal(0, 0.11)), width=width, layer=layer, root_f=root_f,
                          lift_rel=lift_rel + float(rng.normal(0, 0.0012)), flick=flick, bump=bump,
                          shade=shade * float(1 + rng.normal(0, 0.09)), t_blend=t_blend))
    # --- outer layer: fringe (explicit, keeps the eyes readable)
    fringe = [(-5, 0.082, 0.017, -0.1), (7, 0.07, 0.016, -0.05), (-15, 0.046, 0.019, 0.1), (17, 0.05, 0.019, 0.05),
              (-26, 0.058, 0.021, 0.1), (28, 0.092, 0.022, -0.2), (-37, 0.104, 0.024, -0.25), (40, 0.112, 0.025, -0.25),
              (-50, 0.125, 0.026, -0.3), (53, 0.13, 0.026, -0.3), (-64, 0.135, 0.028, -0.3), (67, 0.138, 0.028, -0.3),
              (-79, 0.135, 0.029, -0.25), (82, 0.135, 0.029, -0.25)]
    for phi, ln, w, fl in fringe:
        add(phi, ln, w, 0, float(rng.uniform(0.12, 0.26)), 0.017, fl, bump=0.008)
    for phi in (-22, -11, 0, 12, 23):      # short under-fringe: closes the hairline
        add(phi, 0.034, 0.03, 1, 0.5, 0.008, 0.0, shade=0.82, bump=0.002)
    # --- outer layer: sides and back
    for phi in np.arange(95, 266, 12.5):
        a = abs(((phi + 180) % 360) - 180)
        ln = float(np.interp(a, [90, 130, 180], [0.108, 0.1, 0.092]))
        add(float(phi), ln, 0.031, 0, float(rng.uniform(0.12, 0.26)), 0.017, float(rng.choice([-0.3, -0.15, 0.2, 0.35])), bump=0.008)
    # --- under layer: fills the gaps, a little shorter and darker
    for phi in np.arange(-84, 270, 12.5):
        a = abs(((phi + 180) % 360) - 180)
        if a < 24:
            continue
        ln = float(np.interp(a, [24, 45, 90, 180], [0.08, 0.1, 0.1, 0.09]))
        add(float(phi) + 6, ln, 0.032, 1, float(rng.uniform(0.5, 0.62)), 0.006, -0.2, shade=0.8, bump=0.001)
    # --- short layered tufts on top (volume and a messy silhouette)
    for i in range(18):
        phi = float(rng.uniform(-180, 180))
        add(phi, float(rng.uniform(0.03, 0.055)), 0.024, 2, float(rng.uniform(0.05, 0.3)), 0.021, float(rng.uniform(0.2, 0.6)),
            theta=float(rng.uniform(30, 60)), bump=0.008, shade=1.06, t_blend=1.6)
    return cards


def build_hair(ch, cards, mat, seed=11, clearance=0.0045, cap_mat=None, hairline=None):
    """Create the card mesh (rest pose) and parent it to the head bone."""
    rng = np.random.default_rng(seed)
    vd = da.vertex_data(ch)
    me = ch['body'].data
    co = vd['co'].astype(np.float64)
    polys = [list(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons([Vector(c) for c in co], polys)
    E, C, s = head_frame(ch)
    Cv = Vector(C)
    # orientation of mesh normals (should be outward)
    probe = bvh.find_nearest(Vector(C + np.array([0, 0, 0.3])))
    sign = 1.0 if (Vector(C + np.array([0, 0, 0.3])) - probe[0]).dot(probe[1]) > 0 else -1.0
    crown = u_dir(9, 180)
    G = np.array([0, 0, -1.0])
    verts, faces, uvs, shade = [], [], [], []
    for cd in cards:
        urel = u_dir(cd['theta'], cd['phi'])
        n_hug = 7
        pts, nrms = [], []
        for i in range(n_hug):
            sh = i / (n_hug - 1)
            d = slerp(crown, urel, cd['root_f'] + (1 - cd['root_f']) * sh)
            hit = bvh.ray_cast(Cv, Vector(d), 0.4)
            if hit[0] is None:
                continue
            p, n = np.array(hit[0]), np.array(hit[1])
            if n.dot(d) < 0:
                n = -n
            n = n * 0.5 + d * 0.5
            n /= np.linalg.norm(n)
            lift = 0.003 + (cd['lift_rel'] - 0.003) * float(da.sm(0.0, 0.75, sh)) + cd['bump'] * math.sin(math.pi * sh) + cd['layer'] * 0.0 + 0.0015 * (2 - cd['layer'])
            pts.append(p + n * lift * s)
            nrms.append(n)
        if len(pts) < 3:
            continue
        T0 = pts[-1] - pts[-2]
        T0 /= np.linalg.norm(T0)
        n_hang = 7
        step = cd['length'] * s / n_hang
        p = pts[-1].copy()
        for k in range(1, n_hang + 1):
            w = k / n_hang
            g = float(da.sm(0.0, cd['t_blend'], w))
            radial = np.array([p[0] - C[0], p[1] - C[1], 0.0])
            radial /= np.linalg.norm(radial) + 1e-9
            fl = cd['flick'] * float(da.sm(0.45, 1.0, w))
            d = T0 * (1 - g) + G * g + radial * fl
            d /= np.linalg.norm(d)
            p = p + d * step
            near = bvh.find_nearest(Vector(p), 0.06)
            if near[0] is not None:
                loc, nn = np.array(near[0]), np.array(near[1]) * sign
                sd = (p - loc).dot(nn)
                if sd < clearance:
                    p = loc + nn * clearance
            pts.append(p.copy())
            nrms.append(radial * 0.85 + np.array([0, 0, 0.15]))
        path = _catmull(pts, 3)
        nrm_s = _catmull(nrms, 3)
        m = len(path)
        seg = np.array([np.linalg.norm(path[i + 1] - path[i]) for i in range(m - 1)])
        arc = np.concatenate([[0], np.cumsum(seg)]) / (seg.sum() + 1e-9)
        hug_frac = arc[(n_hug - 1) * 3]
        base = len(verts)
        W2 = cd['width'] * s / 2
        for i in range(m):
            v = float(arc[i])
            t = path[min(i + 1, m - 1)] - path[max(i - 1, 0)]
            t /= np.linalg.norm(t) + 1e-12
            n = nrm_s[i] - t * nrm_s[i].dot(t)
            n /= np.linalg.norm(n) + 1e-12
            bvec = np.cross(t, n)
            grow = 0.32 + 0.68 * float(da.sm(0.0, max(hug_frac * 0.9, 0.05), v))
            taper = 1.0 - float(np.clip((v - 0.46) / 0.54, 0, 1)) ** 1.5
            hw = W2 * grow * taper
            ridge = hw * 0.34
            verts.append(path[i] - bvec * hw)
            verts.append(path[i] + n * ridge)
            verts.append(path[i] + bvec * hw)
            uvs.extend([(0.0, v), (0.5, v), (1.0, v)])
            shade.extend([cd['shade']] * 3)
        for i in range(m - 1):
            a = base + i * 3
            faces.append((a, a + 1, a + 4, a + 3))
            faces.append((a + 1, a + 2, a + 5, a + 4))
    mesh = bpy.data.meshes.new(ch['name'] + '_hair')
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    uvl = mesh.uv_layers.new(name='UVMap')
    li = np.zeros(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', li)
    uvl.data.foreach_set('uv', np.asarray(uvs, dtype=np.float32)[li].ravel())
    ca = mesh.color_attributes.new('shade', 'FLOAT_COLOR', 'POINT')
    sh = np.asarray(shade, dtype=np.float32)
    ca.data.foreach_set('color', np.stack([sh, sh, sh, np.ones_like(sh)], axis=1).ravel())
    ob = bpy.data.objects.new(ch['name'] + '_hair', mesh)
    bpy.context.scene.collection.objects.link(ob)
    mesh.materials.append(mat)
    ob.matrix_world = ch['body'].matrix_world.copy()
    look.parent_keep(ob, ch, 'head')
    out = [ob]
    if cap_mat is not None:
        out.append(build_cap(ch, cap_mat, hairline))
    return out


def build_cap(ch, mat, hairline, offset=0.004):
    """Thin shell over the scalp so no skin shows between the cards."""
    vd = da.vertex_data(ch)
    can, hw = vd['can'], vd['hw']
    ax = np.abs(can[:, 0])
    az = np.arctan2(ax, can[:, 2] + 0.095)
    hl = np.interp(az, hairline[0], hairline[1])
    ears = (ax > 0.066) & (can[:, 1] > -0.06) & (can[:, 1] < 0.012) & (can[:, 2] > -0.14) & (can[:, 2] < -0.06)
    keep = (can[:, 1] > hl + 0.004) & (hw > 0.5) & (~ears)
    body = ch['body']
    me = body.data.copy()
    me.name = ch['name'] + '_cap'
    ob = bpy.data.objects.new(me.name, me)
    bpy.context.scene.collection.objects.link(ob)
    if me.shape_keys:
        ob.shape_key_clear()
    co = vd['co'] + vd['nr'] * offset
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep[v.index]], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    for colattr in list(me.color_attributes):
        me.color_attributes.remove(colattr)
    me.materials.clear()
    me.materials.append(mat)
    ob.matrix_world = body.matrix_world.copy()
    look.parent_keep(ob, ch, 'head')
    return ob


def build(ch):
    """Hair pass entry point: cards + scalp cap from cfg_hair."""
    import cfg_hair as CH
    import room_bl
    tex = strand_texture(ch['name'] + '_strands', CH.HAIR_LIGHT, CH.HAIR_DARK, down=CH.TEX_DOWN)
    cap = room_bl.mat_basic(ch['name'] + '_cap', CH.CAP_COLOR, rough=0.6)
    return build_hair(ch, curtain_style(seed=CH.STYLE_SEED), hair_material(ch['name'] + '_hair', tex), cap_mat=cap,
                      hairline=(CH.HAIRLINE_AZ, CH.HAIRLINE_Y))
