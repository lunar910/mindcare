"""Face pass: skin textures, eyes, eyelashes, teeth and tongue, expression.

Entry points:
    build(ch)                                       called by herolib.build_character
    set_expression(ch, name_or_dict, strength=1.0)  apply a preset from cfg_face.EXPRESSIONS (or a dict of units) on top of the resting face
    expression_names()                              the preset names

Everything attached to the face (lashes, teeth, tongue) is a MakeHuman asset fitted on the morphed base mesh. Each gets the same
expression shape keys as the body (refitted on V + the unit's delta) and a driver per key that copies the body's value, so setting
body.data.shape_keys.key_blocks['mouth-open'].value (or calling set_expression) moves the attachments too. They are also skinned
to the rig (jaw, tongue and eyelid bones)."""
import os

import bpy
import numpy as np
from mathutils import Vector

import cfg_body as CB
import cfg_face as CF
import cfg_hair as CH
import da
import look
import mh
import mhassets as A

HALF_KEYS = {'smirk-left': ('mouth-corner-puller', 'L'), 'smirk-right': ('mouth-corner-puller', 'R')}


# ---------------------------------------------------------------- expression data
def unit_names(ch):
    return [k.name for k in ch['body'].data.shape_keys.key_blocks if k.name != 'Basis']


def unit_deltas(ch):
    """{shape key name: delta on the full base mesh (MakeHuman coordinates)} for the 34 expression units and the one-sided keys."""
    if '_unit_deltas' in ch:
        return ch['_unit_deltas']
    race = ch.get('race_mix') or CB.MACRO['races']
    names = [n for n in unit_names(ch) if n not in HALF_KEYS and not n.startswith('smirk')]
    D = mh.expression_deltas(race, names)
    x = mh.to_bl(ch['V'])[:, 0]
    for key, (unit, side) in HALF_KEYS.items():
        s = 1.0 if side == 'L' else -1.0
        w = np.clip((x * s + 0.004) / 0.012, 0, 1)
        D[key] = mh.expression_deltas(race, [unit])[unit] * w[:, None]
    ch['_unit_deltas'] = D
    return D


def _add_half_keys(ch):
    """One-sided mouth corner pull (a smirk) as shape keys of the body."""
    body = ch['body']
    D = unit_deltas(ch)
    kb = body.data.shape_keys.key_blocks
    n = len(body.data.vertices)
    basis = np.zeros(n * 3, dtype=np.float32)
    kb['Basis'].data.foreach_get('co', basis)
    for key in HALF_KEYS:
        if key in kb:
            continue
        sk = body.shape_key_add(name=key, from_mix=False)
        sk.data.foreach_set('co', (basis.reshape(n, 3) + mh.to_bl(D[key][ch['used']])).astype(np.float32).ravel())
        sk.value = 0.0


def _fit(info, V, S):
    r, w = info['refs'], info['w']
    return V[r[:, 0]] * w[:, 0:1] + V[r[:, 1]] * w[:, 1:2] + V[r[:, 2]] * w[:, 2:3] + info['off'] * S


def follow_expressions(ch, ob, info, min_move=2e-5):
    """Give a fitted asset the body's expression shape keys (refit on V + delta) and drive them from the body's values."""
    V = ch['V']
    S = np.ones(3)
    for k, (a, b, den) in info['scales'].items():
        S[k] = abs(V[a][k] - V[b][k]) / den
    base = _fit(info, V, S)
    n = len(ob.data.vertices)
    rest = np.zeros(n * 3, dtype=np.float32)
    ob.data.vertices.foreach_get('co', rest)
    rest = rest.reshape(n, 3)
    body_keys = ch['body'].data.shape_keys
    added = []
    for name, D in unit_deltas(ch).items():
        d = mh.to_bl(_fit(info, V + D, S) - base)
        if np.abs(d).max() < min_move:
            continue
        if ob.data.shape_keys is None:
            ob.shape_key_add(name='Basis', from_mix=False)
        sk = ob.shape_key_add(name=name, from_mix=False)
        sk.data.foreach_set('co', (rest + d).astype(np.float32).ravel())
        sk.value = 0.0
        fc = ob.data.shape_keys.driver_add(f'key_blocks["{name}"].value')
        fc.driver.type = 'AVERAGE'
        var = fc.driver.variables.new()
        var.name = 'v'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'KEY'
        var.targets[0].id = body_keys
        var.targets[0].data_path = f'key_blocks["{name}"].value'
        added.append(name)
    return added


# ---------------------------------------------------------------- attachments
def _asset(ch, kind, name, **kw):
    """Fit a MakeHuman asset with the shared loader, then make it follow the expressions."""
    ob = A.add_proxy(ch, kind, name, hide_body=False, use_normal=False, **kw)
    folder = A.find(kind, name)
    info = A.parse_mhclo(os.path.join(folder, [f for f in os.listdir(folder) if f.endswith('.mhclo')][0]))
    ob['expression_keys'] = follow_expressions(ch, ob, info)
    return ob, info


def lash_material(name, tex_path, color, down=4, strength=1.0):
    """Eyelash cards: flat dark colour, soft alpha from the (downsampled) MakeHuman lash texture."""
    arr = A.downsample(A.load_pixels(tex_path), down)
    arr[..., :3] = np.asarray(color, dtype=np.float32) / 255
    arr[..., 3] = np.clip(arr[..., 3] * strength, 0, 1)
    img = da.uvbake.to_image(name, arr)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    tx.interpolation = 'Linear'
    tx.extension = 'CLIP'
    b.inputs['Base Color'].default_value = da.lin(color)
    nt.links.new(tx.outputs['Alpha'], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.6
    b.inputs['Specular IOR Level'].default_value = 0.05
    return m


def build_lashes(ch):
    L = CF.LASHES
    if not L or not L.get('asset'):
        return None
    ob, info = _asset(ch, 'eyelashes', L['asset'])
    folder = A.find('eyelashes', L['asset'])
    tex = [f for f in os.listdir(folder) if f.endswith('.png')][0]
    ob.data.materials.clear()
    ob.data.materials.append(lash_material(ch['name'] + '_lashes', os.path.join(folder, tex), L.get('color', [16, 12, 12]), L.get('down', 4), L.get('strength', 1.0)))
    ob.visible_shadow = False
    return ob


def build_mouth(ch):
    """Teeth and tongue, so the mouth has an interior when it opens."""
    M = CF.MOUTH
    out = {}
    if M.get('teeth'):
        tint = np.asarray(M.get('teeth_tint', [1.0, 0.97, 0.9]), dtype=np.float32)
        gum = np.asarray(M.get('gum_tint', [0.8, 0.6, 0.62]), dtype=np.float32)

        def recolor(rgb, alpha):
            sat = rgb.max(axis=-1) - rgb.min(axis=-1)
            is_gum = da.sm(0.12, 0.3, sat)[..., None]                    # gums are saturated, enamel is not
            return rgb * (tint * (1 - is_gum) + gum * is_gum)
        out['teeth'], _ = _asset(ch, 'teeth', M['teeth'], recolor=recolor, down=M.get('teeth_down', 8), rough=0.42, spec=0.25, closest=False)
    if M.get('tongue'):
        tt = np.asarray(M.get('tongue_tint', [0.82, 0.62, 0.64]), dtype=np.float32)
        out['tongue'], _ = _asset(ch, 'tongue', M['tongue'], recolor=lambda rgb, alpha: rgb * tt, down=M.get('tongue_down', 8), rough=0.5, spec=0.2, closest=False)
    return out


# ---------------------------------------------------------------- eyes
def eye_sphere(ob):
    """Centre (object space) and radius of the eyeball: least-squares sphere through the sclera (cornea bulge and iris left out)."""
    P = np.array([v.co[:] for v in ob.data.vertices], dtype=np.float64)
    c = P.mean(axis=0)
    r = 0.012
    for _ in range(3):
        d = P - c
        dist = np.linalg.norm(d, axis=1)
        off_axis = np.degrees(np.arccos(np.clip(-d[:, 1] / np.maximum(dist, 1e-9), -1, 1)))
        Q = P[(off_axis > 38) & (dist > 0.6 * r)]
        Aa = np.c_[2 * Q, np.ones(len(Q))]
        x = np.linalg.lstsq(Aa, (Q ** 2).sum(axis=1), rcond=None)[0]
        c = x[:3]
        r = float(np.sqrt(x[3] + c @ c))
    return c, r


def build_eyes(ch):
    E = dict(CF.EYE)
    cs = [eye_sphere(e) for e in ch['eyes']]
    r = float(np.mean([c[1] for c in cs]))
    centre = np.mean([c[0] * np.array([s, 1, 1]) for c, s in zip(cs, (1, -1))], axis=0)      # mirror the right eye's offset
    centre[0] = 0.0
    wc = [np.array(e.matrix_world.translation) + c[0] for e, c in zip(ch['eyes'], cs)]
    mid = (wc[0] + wc[1]) / 2
    ref = bpy.data.objects.new(ch['name'] + '_eyeref', None)
    bpy.context.scene.collection.objects.link(ref)
    ref.empty_display_size = 0.01
    ref.matrix_world.translation = Vector(mid)
    look.parent_keep(ref, ch, 'head')
    for k, f in (('socket_x', 1.0), ('socket_z', 0.55), ('lid_z0', 0.02), ('lid_z1', 0.42)):
        E[k] = E.get(k + '_r', f) * r
    em = da.eye_material(ch['name'] + '_eye', CF.IRIS, CF.IRIS_IN, E=E, centre=tuple(centre), ref=ref, ipd=float(abs(wc[0][0] - wc[1][0])))
    for e in ch['eyes']:
        e.data.materials.clear()
        e.data.materials.append(em)
    ch['eye_ref'], ch['eye_radius'], ch['eye_centre'] = ref, r, centre
    return em


# ---------------------------------------------------------------- expression
def expression_names():
    return sorted(CF.EXPRESSIONS)


def resting_expression():
    rest = dict(CF.EXPR)
    for side, amount in CF.SMIRK.items():
        rest['smirk-left' if side == 'L' else 'smirk-right'] = amount
    return rest


def set_expression(ch, expr='neutral', strength=1.0):
    """Apply an expression on top of the resting face.
    expr: a preset name from cfg_face.EXPRESSIONS, or a dict {unit: value}. Units are the body's shape keys (the 34 MakeHuman
    expression units plus 'smirk-left' / 'smirk-right'). The optional entry 'rest' (0..1, default 1) says how much of the
    resting expression survives at full strength.  strength 0 gives the resting face, 1 the full expression (blend for animation).
    Lashes, teeth and tongue follow through their drivers."""
    if isinstance(expr, str):
        if expr not in CF.EXPRESSIONS:
            raise KeyError(f'unknown expression {expr!r}; presets: {expression_names()}')
        expr = CF.EXPRESSIONS[expr]
    expr = dict(expr)
    keep = float(expr.pop('rest', 1.0))
    rest = ch.get('rest_expr') or resting_expression()
    kb = ch['body'].data.shape_keys.key_blocks
    unknown = [k for k in expr if k not in kb]
    if unknown:
        raise KeyError(f'unknown expression units {unknown}')
    for k in kb:
        if k.name == 'Basis':
            continue
        v = rest.get(k.name, 0.0) * (1 - strength * (1 - keep)) + strength * expr.get(k.name, 0.0)
        k.value = float(min(max(v, 0.0), 1.0))
    ch['expression'] = (expr, strength)
    bpy.context.view_layer.update()


# ---------------------------------------------------------------- build
def build(ch):
    body = ch['body']
    P = dict(CF.SKIN)
    P.update(hairline_az=CH.HAIRLINE_AZ, hairline_y=CH.HAIRLINE_Y, scalp=CH.SCALP_PAINT, glove=CB.PAINT_GLOVES)
    T = da.Texels(ch)
    skin_img, _ = da.paint_skin(ch, P, T)
    face_img, Tf = da.paint_face(ch, P) if P.get('face_patch', True) else (None, None)
    body.data.materials.append(da.skin_material(ch['name'] + '_skin', skin_img, rough=P.get('rough', 0.8), spec=P.get('spec', 0.08), face_img=face_img))
    build_eyes(ch)
    _add_half_keys(ch)
    ch['lashes'] = build_lashes(ch)
    ch['mouth'] = build_mouth(ch)
    ch['rest_expr'] = resting_expression()
    set_expression(ch, {}, 0.0)
    ch['texels'] = T
    ch['face_texels'] = Tf
