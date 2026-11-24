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


def actor(who, clips, hands=True):
    cast2.MATTE = False
    c = CAST[who]
    a = cast2.Actor(c['name'], c['rig'], [c['clips_from'] + ':' + k for k in clips], scale=1.0, glasses=c['glasses'])
    realism(a)
    if hands:
        try:
            import hands5
            hands5.add_hands(a.arm, a.mesh)
            a.hands5 = True
        except Exception as e:                       # the hand module is optional (built separately)
            print('hands5 not used:', repr(e)[:200])
            a.hands5 = False
    return a
