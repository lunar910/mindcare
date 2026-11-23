"""Loader for MakeHuman assets (.mhclo clothes / hair / shoes fitted to a morphed body, .mhmat materials).

The assets come from the official MakeHuman asset packs (CC0 unless noted). They are data only:
files are parsed as text / images, nothing from the packs is executed."""
import json
import os

import bpy
import numpy as np

import mh
import uvbake

ASSETS = os.path.join(mh.SP, 'mh-assets')
EXTRA = os.path.join(mh.SP, 'mh-extra')


def find(kind, name):
    """Locate an asset folder, e.g. find('clothes', 'male_casualsuit05')."""
    for root in [ASSETS] + sorted(os.path.join(EXTRA, d) for d in os.listdir(EXTRA)) if os.path.isdir(EXTRA) else [ASSETS]:
        p = os.path.join(root, kind, name)
        if os.path.isdir(p):
            return p
    raise FileNotFoundError(f'{kind}/{name}')


def parse_mhclo(path):
    folder = os.path.dirname(path)
    info = dict(scales={}, obj=None, material=None, weights_file=None, name=os.path.basename(folder), folder=folder)
    refs, wts, offs, delete = [], [], [], []
    mode = None
    with open(path, encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            t = line.split()
            if not t or t[0].startswith('#'):
                continue
            k = t[0]
            if k == 'verts':
                mode = 'verts'
                continue
            if k == 'delete_verts':
                mode = 'delete'
                continue
            if k in ('x_scale', 'y_scale', 'z_scale'):
                info['scales']['xyz'.index(k[0])] = (int(t[1]), int(t[2]), float(t[3]))
                continue
            if k == 'obj_file':
                info['obj'] = os.path.join(folder, t[1])
                continue
            if k == 'material':
                info['material'] = os.path.join(folder, t[1])
                continue
            if k == 'vertexboneweights_file':
                info['weights_file'] = os.path.join(folder, t[1])
                continue
            if k[0].isalpha():
                mode = None
                continue
            if mode == 'verts':
                if len(t) == 1:
                    refs.append((int(t[0]), 0, 1)); wts.append((1.0, 0.0, 0.0)); offs.append((0.0, 0.0, 0.0))
                else:
                    refs.append((int(t[0]), int(t[1]), int(t[2])))
                    wts.append((float(t[3]), float(t[4]), float(t[5])))
                    offs.append(tuple(float(x) for x in t[6:9]) if len(t) >= 9 else (0.0, 0.0, 0.0))
            elif mode == 'delete':
                i = 0
                while i < len(t):
                    if i + 2 < len(t) and t[i + 1] == '-':
                        delete.extend(range(int(t[i]), int(t[i + 2]) + 1))
                        i += 3
                    else:
                        delete.append(int(t[i]))
                        i += 1
    info.update(refs=np.array(refs, dtype=np.int64), w=np.array(wts, dtype=np.float64), off=np.array(offs, dtype=np.float64),
                delete=np.array(sorted(set(delete)), dtype=np.int64))
    return info


def parse_obj(path):
    nv, vt, faces = 0, [], []
    with open(path, encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            if line.startswith('v '):
                nv += 1
            elif line.startswith('vt '):
                vt.append([float(x) for x in line.split()[1:3]])
            elif line.startswith('f '):
                vi, ti = [], []
                for tok in line.split()[1:]:
                    p = tok.split('/')
                    vi.append(int(p[0]) - 1)
                    ti.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                faces.append((vi, ti))
    return nv, np.array(vt, dtype=np.float32), faces


def parse_mhmat(path):
    out = {}
    folder = os.path.dirname(path)
    with open(path, encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            t = line.split()
            if len(t) >= 2 and t[0].endswith('Texture'):
                out[t[0]] = os.path.join(folder, t[1])
            elif len(t) >= 4 and t[0] in ('diffuseColor', 'specularColor'):
                out[t[0]] = [float(x) for x in t[1:4]]
    return out


def fit(info, V):
    """Clothing vertices for a morphed base mesh V (MakeHuman coordinates)."""
    S = np.ones(3)
    for n, (a, b, den) in info['scales'].items():
        S[n] = abs(V[a][n] - V[b][n]) / den
    r, w = info['refs'], info['w']
    return V[r[:, 0]] * w[:, 0:1] + V[r[:, 1]] * w[:, 1:2] + V[r[:, 2]] * w[:, 2:3] + info['off'] * S


_WB = None


def base_weights():
    """Dense (n_base_verts, n_bones) weight matrix of the default rig."""
    global _WB
    if _WB is None:
        B = mh.base()
        names = list(B.weights.keys())
        W = np.zeros((len(B.v), len(names)), dtype=np.float32)
        for j, n in enumerate(names):
            a = np.array(B.weights[n], dtype=np.float64)
            if len(a):
                W[a[:, 0].astype(np.int64), j] = a[:, 1]
        _WB = (names, W)
    return _WB


def load_pixels(path):
    """Image file -> float array (H, W, 4), row 0 at the bottom (same convention as uvbake)."""
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.zeros(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(axis=-1), rgb.min(axis=-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rc, gc, bc = (mx - r) / np.where(m, d, 1), (mx - g) / np.where(m, d, 1), (mx - b) / np.where(m, d, 1)
    h = np.where(mx == r, bc - gc, np.where(mx == g, 2.0 + rc - bc, 4.0 + gc - rc))
    h = (h / 6.0) % 1.0
    h = np.where(m, h, 0.0)
    s = np.where(mx > 1e-6, d / np.where(mx > 1e-6, mx, 1), 0.0)
    return h, s, mx


def downsample(a, down):
    if down <= 1:
        return a
    h, w = a.shape[0] // down * down, a.shape[1] // down * down
    return a[:h, :w].reshape(h // down, down, w // down, down, a.shape[2]).mean(axis=(1, 3))


def texture_material(name, arr, rough=0.8, spec=0.12, closest=True, alpha=False, normal=None, normal_strength=0.6):
    img = uvbake.to_image(name, arr)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = 'Closest' if closest else 'Linear'
    nt.links.new(tx.outputs['Color'], b.inputs['Base Color'])
    if alpha:
        gt = nt.nodes.new('ShaderNodeMath')
        gt.operation = 'GREATER_THAN'
        gt.inputs[1].default_value = 0.4
        nt.links.new(tx.outputs['Alpha'], gt.inputs[0])
        nt.links.new(gt.outputs[0], b.inputs['Alpha'])
    if normal is not None:
        nimg = uvbake.to_image(name + '_n', normal, srgb=False)
        ntx = nt.nodes.new('ShaderNodeTexImage')
        ntx.image = nimg
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(ntx.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    return m


def add_proxy(ch, kind, name, recolor=None, down=4, rough=0.8, spec=0.12, closest=True, use_normal=True, ao=0.8, subdiv=0, hide_body=True,
              offset=0.0):
    """Fit an asset to the character, skin it to the rig and give it a (PS2-sized) material.
    recolor: callable(rgb, alpha) -> rgb working on the full-size diffuse texture."""
    folder = find(kind, name)
    mhclo = [f for f in os.listdir(folder) if f.endswith('.mhclo')][0]
    info = parse_mhclo(os.path.join(folder, mhclo))
    nv, vt, faces = parse_obj(info['obj'])
    assert nv == len(info['refs']), (name, nv, len(info['refs']))
    co = mh.to_bl(fit(info, ch['V']))
    me = bpy.data.meshes.new(f"{ch['name']}_{name}")
    me.from_pydata(co.tolist(), [], [f[0] for f in faces])
    uvl = me.uv_layers.new(name='UVMap')
    luv = [vt[ti] if ti >= 0 else (0.0, 0.0) for f in faces for ti in f[1]]
    uvl.data.foreach_set('uv', np.asarray(luv, dtype=np.float32).ravel())
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    if offset:
        nr = np.zeros(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get('normal', nr)
        me.vertices.foreach_set('co', (co + nr.reshape(-1, 3) * offset).astype(np.float32).ravel())
    ob = bpy.data.objects.new(me.name, me)
    bpy.context.scene.collection.objects.link(ob)
    # skin weights: custom file, else transferred from the body through the fitting references
    if info['weights_file'] and os.path.exists(info['weights_file']):
        wj = json.load(open(info['weights_file']))['weights']
        for bone, pairs in wj.items():
            if bone not in ch['rig'].data.bones:
                continue
            vg = ob.vertex_groups.new(name=bone)
            for vi, w in pairs:
                vg.add([int(vi)], float(w), 'REPLACE')
    else:
        names, W = base_weights()
        r, w = info['refs'], info['w'].astype(np.float32)
        Wp = W[r[:, 0]] * w[:, 0:1] + W[r[:, 1]] * w[:, 1:2] + W[r[:, 2]] * w[:, 2:3]
        Wp[Wp < 0.01] = 0
        Wp /= np.maximum(Wp.sum(axis=1, keepdims=True), 1e-6)
        for j in np.where(Wp.any(axis=0))[0]:
            vg = ob.vertex_groups.new(name=names[j])
            idx = np.where(Wp[:, j] > 0)[0]
            for i in idx:
                vg.add([int(i)], float(Wp[i, j]), 'REPLACE')
    ob.parent = ch['rig']
    a = ob.modifiers.new('Armature', 'ARMATURE')
    a.object = ch['rig']
    if subdiv:
        sd = ob.modifiers.new('Subd', 'SUBSURF')
        sd.levels = 0
        sd.render_levels = subdiv
    # material
    mat = parse_mhmat(info['material']) if info['material'] and os.path.exists(info['material']) else {}
    arr = None
    if 'diffuseTexture' in mat and os.path.exists(mat['diffuseTexture']):
        arr = load_pixels(mat['diffuseTexture'])
        rgb, alpha = arr[..., :3].copy(), arr[..., 3]
        if recolor is not None:
            rgb = recolor(rgb, alpha)
        if ao and 'aomapTexture' in mat and os.path.exists(mat['aomapTexture']):
            aoimg = load_pixels(mat['aomapTexture'])[..., 0]
            if aoimg.shape == alpha.shape:
                rgb = rgb * (1 - ao + ao * aoimg)[..., None]
        arr = downsample(np.concatenate([np.clip(rgb, 0, 1), alpha[..., None]], axis=2), down)
    nrm = None
    if use_normal and 'normalmapTexture' in mat and os.path.exists(mat['normalmapTexture']):
        nrm = downsample(load_pixels(mat['normalmapTexture']), max(1, down // 2))
    if arr is None:
        arr = np.ones((4, 4, 4), dtype=np.float32) * np.array(mat.get('diffuseColor', [0.5, 0.5, 0.5]) + [1.0], dtype=np.float32)
    has_alpha = bool((arr[..., 3] < 0.4).any())
    me.materials.append(texture_material(f"{ch['name']}_{name}", arr, rough=rough, spec=spec, closest=closest, alpha=has_alpha, normal=nrm))
    if hide_body and len(info['delete']):
        ch.setdefault('hidden_base', set()).update(int(i) for i in info['delete'])
    ch.setdefault('proxies', {})[name] = ob
    return ob


def apply_body_mask(ch, extra_hidden=None):
    """Hide the body vertices that the fitted clothes declare as covered."""
    body = ch['body']
    hidden = np.zeros(len(mh.base().v), dtype=bool)
    if ch.get('hidden_base'):
        hidden[np.array(sorted(ch['hidden_base']))] = True
    vis = ~hidden[ch['used']]
    if extra_hidden is not None:
        vis &= ~extra_hidden
    vg = body.vertex_groups.get('visible') or body.vertex_groups.new(name='visible')
    vg.add([int(i) for i in np.where(vis)[0]], 1.0, 'REPLACE')
    for m in list(body.modifiers):
        if m.type == 'MASK':
            body.modifiers.remove(m)
    mk = body.modifiers.new('Mask', 'MASK')
    mk.vertex_group = 'visible'
    return vis
