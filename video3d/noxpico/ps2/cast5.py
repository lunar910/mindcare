"""Version 5 characters: Meshy's full PBR materials, tuned for a realistic night render.

    a = cast5.actor('pico')          # cast2.Actor with PBR kept, then realism(a)

realism():
  - the baked normal map makes the faces look lumpy in close-up: it is faded on the head and neck (vertex mask from the
    'Head'/'neck' skin weights) and kept at 60 % on the clothes (folds, seams);
  - a little subsurface scattering (skin, cloth) so faces do not look like painted plaster;
  - roughness raised a touch (Meshy's maps are glossy for skin), saturation +12 % (AgX desaturates)."""
import numpy as np
import bpy

import cast2

CAST = dict(pico=dict(name='picoR', rig='picoR_rigged', clips_from='pico', glasses=False),
            nox=dict(name='noxR', rig='noxR_rigged', clips_from='nox2', glasses=True))


def head_mask(mesh, name='nmask'):
    me = mesh.data
    gi = {g.name: g.index for g in mesh.vertex_groups}
    w = np.zeros(len(me.vertices))
    want = {gi.get('Head'), gi.get('neck')} - {None}
    for v in me.vertices:
        for g in v.groups:
            if g.group in want:
                w[v.index] += g.weight
    w = np.clip(w, 0, 1)
    at = me.color_attributes.get(name) or me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
    cols = np.zeros((len(w), 4), np.float32)
    cols[:, 0] = w
    cols[:, 3] = 1
    at.data.foreach_set('color', cols.ravel())
    return w


def realism(actor, body_normal=0.6, head_normal=0.15, sss=0.12, rough_add=0.08, sat=1.12):
    mesh = actor.mesh
    head_mask(mesh)
    for m in mesh.data.materials:
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        nm = next((n for n in nt.nodes if n.type == 'NORMAL_MAP'), None)
        if nm is not None:
            attr = nt.nodes.new('ShaderNodeAttribute')
            attr.attribute_name = 'nmask'
            attr.attribute_type = 'GEOMETRY'
            mr = nt.nodes.new('ShaderNodeMapRange')
            mr.inputs['To Min'].default_value = body_normal
            mr.inputs['To Max'].default_value = head_normal
            nt.links.new(attr.outputs['Fac'], mr.inputs['Value'])
            nt.links.new(mr.outputs['Result'], nm.inputs['Strength'])
        if sss:
            bsdf.inputs['Subsurface Weight'].default_value = sss
            bsdf.inputs['Subsurface Radius'].default_value = (0.010, 0.004, 0.0025)
            bsdf.inputs['Subsurface Scale'].default_value = 0.6
        if rough_add:
            lk = bsdf.inputs['Roughness'].links
            if lk:
                src = lk[0].from_socket
                add = nt.nodes.new('ShaderNodeMath')
                add.operation = 'ADD'
                add.use_clamp = True
                add.inputs[1].default_value = rough_add
                nt.links.new(src, add.inputs[0])
                nt.links.new(add.outputs[0], bsdf.inputs['Roughness'])
        if sat != 1.0:
            lk = bsdf.inputs['Base Color'].links
            if lk:
                src = lk[0].from_socket
                hsv = nt.nodes.new('ShaderNodeHueSaturation')
                hsv.inputs['Saturation'].default_value = sat
                nt.links.new(src, hsv.inputs['Color'])
                nt.links.new(hsv.outputs['Color'], bsdf.inputs['Base Color'])
    return actor


def _node(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        if k in n.inputs:
            n.inputs[k].default_value = v
        else:
            setattr(n, k, v)
    return n


def _band(nt, x, a0, a1, b0, b1):
    """1 inside [a1, b0], ramps to 0 at a0 and b1 (two Map Range nodes and a minimum)."""
    up = _node(nt, 'ShaderNodeMapRange')
    up.inputs['From Min'].default_value, up.inputs['From Max'].default_value = a0, a1
    dn = _node(nt, 'ShaderNodeMapRange')
    dn.inputs['From Min'].default_value, dn.inputs['From Max'].default_value = b0, b1
    dn.inputs['To Min'].default_value, dn.inputs['To Max'].default_value = 1.0, 0.0
    nt.links.new(x, up.inputs['Value'])
    nt.links.new(x, dn.inputs['Value'])
    m = _node(nt, 'ShaderNodeMath', operation='MINIMUM')
    nt.links.new(up.outputs['Result'], m.inputs[0])
    nt.links.new(dn.outputs['Result'], m.inputs[1])
    return m.outputs['Value']


def living_skin(actor, warm=(0.92, 0.75, 0.61), sat=1.28, sss_skin=0.28, hair_dark=False, weave=0.12):
    """v5.1 (critique: 'vinyl toys in a photo'): key the skin texels by colour (orange hue, moderate saturation, light
    value) and warm them up with more subsurface; optionally darken bluish-black hair (Nox); a fine weave bump on the
    clothes.  Works on the existing realism() node tree."""
    for m in actor.mesh.data.materials:
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
        lk = bsdf.inputs['Base Color'].links
        if not lk:
            continue
        src = lk[0].from_socket
        sep = _node(nt, 'ShaderNodeSeparateColor', mode='HSV')
        nt.links.new(src, sep.inputs['Color'])
        h, s, v = sep.outputs[0], sep.outputs[1], sep.outputs[2]
        hue_ok = _band(nt, h, 0.0, 0.02, 0.10, 0.13)
        sat_ok = _band(nt, s, 0.03, 0.08, 0.48, 0.62)
        val_ok = _band(nt, v, 0.32, 0.46, 1.0, 1.1)
        m1 = _node(nt, 'ShaderNodeMath', operation='MULTIPLY')
        nt.links.new(hue_ok, m1.inputs[0])
        nt.links.new(sat_ok, m1.inputs[1])
        skin = _node(nt, 'ShaderNodeMath', operation='MULTIPLY')
        nt.links.new(m1.outputs['Value'], skin.inputs[0])
        nt.links.new(val_ok, skin.inputs[1])
        skin = skin.outputs['Value']
        mul = _node(nt, 'ShaderNodeMix', data_type='RGBA', blend_type='MULTIPLY')
        mul.inputs['Factor'].default_value = 1.0
        nt.links.new(src, mul.inputs[6])
        mul.inputs[7].default_value = tuple(warm) + (1.0,)
        hs = _node(nt, 'ShaderNodeHueSaturation')
        hs.inputs['Saturation'].default_value = sat
        nt.links.new(mul.outputs[2], hs.inputs['Color'])
        out = _node(nt, 'ShaderNodeMix', data_type='RGBA')
        nt.links.new(skin, out.inputs['Factor'])
        nt.links.new(src, out.inputs[6])
        nt.links.new(hs.outputs['Color'], out.inputs[7])
        col = out.outputs[2]
        if hair_dark:                                  # dark slate-blue texels (Nox's hair) -> near black
            hh = _band(nt, h, 0.45, 0.52, 0.75, 0.82)
            vv = _band(nt, v, -0.1, 0.0, 0.32, 0.42)
            hm = _node(nt, 'ShaderNodeMath', operation='MULTIPLY')
            nt.links.new(hh, hm.inputs[0])
            nt.links.new(vv, hm.inputs[1])
            dk = _node(nt, 'ShaderNodeHueSaturation')
            dk.inputs['Saturation'].default_value = 0.45
            dk.inputs['Value'].default_value = 0.55
            nt.links.new(col, dk.inputs['Color'])
            o2 = _node(nt, 'ShaderNodeMix', data_type='RGBA')
            nt.links.new(hm.outputs['Value'], o2.inputs['Factor'])
            nt.links.new(col, o2.inputs[6])
            nt.links.new(dk.outputs['Color'], o2.inputs[7])
            col = o2.outputs[2]
        nt.links.new(col, bsdf.inputs['Base Color'])
        # subsurface: stronger on skin than on cloth
        ss = _node(nt, 'ShaderNodeMapRange')
        ss.inputs['To Min'].default_value, ss.inputs['To Max'].default_value = 0.04, sss_skin
        nt.links.new(skin, ss.inputs['Value'])
        nt.links.new(ss.outputs['Result'], bsdf.inputs['Subsurface Weight'])
        # a fine weave on the clothes (not on skin, not on the head)
        if weave:
            nl = bsdf.inputs['Normal'].links
            nrm = nl[0].from_socket if nl else None
            tc = _node(nt, 'ShaderNodeTexCoord')
            wv = _node(nt, 'ShaderNodeTexWave', wave_type='BANDS', bands_direction='DIAGONAL')
            wv.inputs['Scale'].default_value = 900.0
            wv.inputs['Distortion'].default_value = 1.5
            nt.links.new(tc.outputs['Object'], wv.inputs['Vector'])
            attr = _node(nt, 'ShaderNodeAttribute', attribute_name='nmask', attribute_type='GEOMETRY')
            notskin = _node(nt, 'ShaderNodeMath', operation='SUBTRACT')
            notskin.inputs[0].default_value = 1.0
            nt.links.new(skin, notskin.inputs[1])
            nothead = _node(nt, 'ShaderNodeMath', operation='SUBTRACT')
            nothead.inputs[0].default_value = 1.0
            nt.links.new(attr.outputs['Fac'], nothead.inputs[1])
            wgt = _node(nt, 'ShaderNodeMath', operation='MULTIPLY')
            nt.links.new(notskin.outputs['Value'], wgt.inputs[0])
            nt.links.new(nothead.outputs['Value'], wgt.inputs[1])
            st = _node(nt, 'ShaderNodeMath', operation='MULTIPLY')
            st.inputs[1].default_value = weave
            nt.links.new(wgt.outputs['Value'], st.inputs[0])
            bp = _node(nt, 'ShaderNodeBump')
            bp.inputs['Distance'].default_value = 0.0004
            nt.links.new(st.outputs['Value'], bp.inputs['Strength'])
            nt.links.new(wv.outputs['Fac'], bp.inputs['Height'])
            if nrm is not None:
                nt.links.new(nrm, bp.inputs['Normal'])
            nt.links.new(bp.outputs['Normal'], bsdf.inputs['Normal'])
    return actor


def actor(who, clips, hands=True):
    cast2.MATTE = False
    c = CAST[who]
    a = cast2.Actor(c['name'], c['rig'], [c['clips_from'] + ':' + k for k in clips], scale=1.0, glasses=c['glasses'])
    realism(a, body_normal=0.85)
    living_skin(a, hair_dark=(who == 'nox'))
    if hands:
        try:
            import hands5
            hands5.add_hands(a.arm, a.mesh)
            a.hands5 = True
        except Exception as e:                       # the hand module is optional (built separately)
            print('hands5 not used:', repr(e)[:200])
            a.hands5 = False
    return a
