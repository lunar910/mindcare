"""Hero assembly: builds the character from the four passes (face, outfit, hair, pose) and offers render helpers.

    ch = herolib.build_character()          # rest pose (A-pose), rig at the origin
    herolib.pose(ch, 'seated')              # optional: seated in the living room
ch keys: name, body (mesh object), rig (armature), eyes [L, R], V (morphed base verts, MakeHuman coords),
         used / remap (base <-> body vertex ids), J (joints), proxies {asset name: object}, texels (da.Texels)."""
import math
import os

import bpy
import numpy as np
from mathutils import Vector

import cfg_body as CB
import cfg_face as CF
import face
import hairda
import mh
import outfit
import posing

WARM = (1.0, 0.8, 0.62)


def reset():
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable('cycles', default_set=True)


def expression_units():
    """All MakeHuman expression units (34: eye-left-closure, mouth-open, eyebrows-left-up, ...). Each becomes a shape key
    on the body mesh (value 0 by default), so expressions, blinks and mouth shapes can be driven later."""
    names = mh.base().npz.files
    pre = 'targets/expression/units/caucasian/'
    return sorted(n[len(pre):-len('.index')] for n in names if n.startswith(pre) and n.endswith('.index'))


def build_character(name='H', hair=True, clothes=True):
    details = dict(CB.BODY_DETAILS)
    details.update(CF.FACE_DETAILS)
    ch = mh.build(name, CB.MACRO, details=details, expr_units=expression_units(), race_mix=CB.MACRO['races'])
    ch['race_mix'] = CB.MACRO['races']
    bpy.context.view_layer.update()
    face.build(ch)
    if clothes:
        outfit.build(ch)
    if hair:
        hairda.build(ch)
    bpy.context.view_layer.update()
    return ch


def pose(ch, name='seated'):
    posing.apply(ch, name)
    bpy.context.view_layer.update()


def setup_cycles(width, height, samples=32):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 5
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.pixel_filter_type = 'BOX'
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.view_settings.view_transform = 'Standard'
    return sc


def camera():
    sc = bpy.context.scene
    cd = bpy.data.cameras.new('cam')
    cd.sensor_fit = 'VERTICAL'
    cam = bpy.data.objects.new('cam', cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def aim_camera(cam, pos, target, fov_deg):
    cam.location = Vector(pos)
    cam.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.angle = math.radians(fov_deg)


def area(name, loc, target, power, color=(1, 1, 1), size=0.8):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.color, ld.size = power, color, size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(loc)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return ob


def eyes_mid(ch):
    bpy.context.view_layer.update()
    return (ch['eyes'][0].matrix_world.translation + ch['eyes'][1].matrix_world.translation) / 2


def bone_world(ch, bone, tail=False):
    bpy.context.view_layer.update()
    p = ch['rig'].pose.bones[bone]
    return ch['rig'].matrix_world @ (p.tail if tail else p.head)


def studio_world(strength=0.6):
    sc = bpy.context.scene
    w = bpy.data.worlds.new('studio')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.32, 0.34, 0.4, 1)
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = strength


def room_lighting(R):
    """Kept for old scripts: the room lighting now lives in stage.py."""
    import stage
    stage.room_lighting(R)


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
