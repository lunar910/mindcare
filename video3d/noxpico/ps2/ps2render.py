"""PS2-cutscene renderer, Blender side.   import ps2render as PR

Cycles is only used as a rasteriser here: one sample per pixel through the pixel centre, no light bounces, and only
"data" passes come out (base colour, emission, normal, world position, depth, object index).  The lighting itself is
computed afterwards in numpy (ps2shade.py), the way a PS2 game lit a scene: ambient + a few lights, no ray-traced shadows.

The scene is split in two:
  static  - the set; rendered once per shot (plus an ambient-occlusion pass, the "baked" shading of a PS2 level)
  dynamic - characters and whatever moves; rendered every frame (about a second)
and both are merged with their depth in ps2shade.
"""
import math
import os

import bpy
from mathutils import Vector

_STATE = {}


def setup(width, height, ss=2):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    c = sc.cycles
    c.device = 'CPU'
    c.samples = 1
    c.use_adaptive_sampling = False
    c.use_denoising = False
    c.max_bounces = 0
    c.diffuse_bounces = c.glossy_bounces = c.transmission_bounces = c.volume_bounces = 0
    c.transparent_max_bounces = 8
    c.pixel_filter_type = 'BOX'
    c.filter_width = 0.01                       # every sample goes through the pixel centre: stable, jaggy like a rasteriser
    c.caustics_reflective = c.caustics_refractive = False
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = width * ss, height * ss
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.threads_mode = 'AUTO'
    sc.view_settings.view_transform = 'Standard'
    vl = sc.view_layers[0]
    vl.use_pass_diffuse_color = vl.use_pass_emit = vl.use_pass_normal = True
    vl.use_pass_position = vl.use_pass_z = vl.use_pass_object_index = True
    vl.use_pass_ambient_occlusion = False
    vl.pass_alpha_threshold = 0.5
    ims = sc.render.image_settings
    if hasattr(ims, 'media_type'):
        ims.media_type = 'MULTI_LAYER_IMAGE'
    ims.file_format = 'OPEN_EXR_MULTILAYER'
    ims.color_depth = '16'
    ims.exr_codec = 'ZIPS'
    if sc.world is None:
        sc.world = bpy.data.worlds.new('w')
    sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Strength'].default_value = 0.0
    _STATE.update(w=width, h=height, ss=ss)
    return sc


def split(dynamic):
    """Declare which objects move; everything else that renders is the static set."""
    dyn = set(dynamic)
    stat = [o for o in bpy.context.scene.objects if o.type in ('MESH', 'CURVE') and o not in dyn and not o.hide_render]
    _STATE.update(dynamic=[o for o in dyn if not o.hide_render], static=stat, user_hidden={})
    return stat


def _show(which):
    for o in _STATE['static']:
        o.hide_render = which != 'static'
    for o in _STATE['dynamic']:
        o.hide_render = (which != 'dynamic') or _STATE['user_hidden'].get(o.name, False)


def hide_dynamic(ob, hidden):
    """Per-frame visibility of a dynamic object (kept across the static / dynamic switch)."""
    _STATE['user_hidden'][ob.name] = hidden


def render_static(path, ao_samples=96, ao_distance=0.9):
    """The set from the current camera: data passes (1 sample) and a converged ambient-occlusion pass."""
    sc = bpy.context.scene
    vl = sc.view_layers[0]
    _show('static')
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    if ao_samples:
        vl.use_pass_ambient_occlusion = True
        sc.world.light_settings.distance = ao_distance
        sc.cycles.samples = ao_samples
        sc.render.filepath = path.replace('.exr', '_ao.exr')
        bpy.ops.render.render(write_still=True)
        sc.cycles.samples = 1
        vl.use_pass_ambient_occlusion = False
    _show('dynamic')


def render_dynamic(path):
    _show('dynamic')
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def camera(name='cam'):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'VERTICAL'
    cd.clip_start, cd.clip_end = 0.05, 100
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def aim(cam, pos, tgt, vfov_deg, roll_deg=0.0):
    cam.location = Vector(pos)
    q = (Vector(tgt) - Vector(pos)).to_track_quat('-Z', 'Y')
    e = q.to_euler()
    cam.rotation_euler = e
    if roll_deg:
        cam.rotation_euler.rotate_axis('Z', math.radians(roll_deg))
    cam.data.angle = math.radians(vfov_deg)
    bpy.context.view_layer.update()


def cam_info(cam):
    """What the shader needs to know about the camera (world position and view direction)."""
    m = cam.matrix_world
    return dict(pos=tuple(m.translation), fwd=tuple(-m.col[2].xyz), up=tuple(m.col[1].xyz), right=tuple(m.col[0].xyz),
                vfov=cam.data.angle)
