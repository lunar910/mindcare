"""Blender helpers for the pixel-art cel look: passes, matte materials, cameras.  import pxrender as PX"""
import math
import os

import bpy
from mathutils import Vector


def setup(width, height, samples=32, supersample=2):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 3
    sc.cycles.diffuse_bounces = 2
    sc.cycles.glossy_bounces = 0
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
    sc.cycles.pixel_filter_type = 'BOX'
    sc.cycles.filter_width = 1.0
    sc.render.resolution_x, sc.render.resolution_y = width * supersample, height * supersample
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'Standard'
    vl = sc.view_layers[0]
    vl.use_pass_diffuse_direct = vl.use_pass_diffuse_indirect = vl.use_pass_diffuse_color = True
    vl.use_pass_emit = vl.use_pass_z = vl.use_pass_normal = vl.use_pass_object_index = True
    ims = sc.render.image_settings
    if hasattr(ims, 'media_type'):
        ims.media_type = 'MULTI_LAYER_IMAGE'          # Blender 5: multilayer EXR is a media type
        ims.file_format = 'OPEN_EXR_MULTILAYER'
    else:
        ims.file_format = 'OPEN_EXR_MULTILAYER'
    sc.render.image_settings.color_depth = '16'
    sc.render.image_settings.exr_codec = 'ZIP'
    return sc


def matte(ob, rough=1.0, nearest=False):
    """Diffuse-only look: no specular, no metal; optional nearest texture filtering."""
    for m in ob.data.materials if ob.type == 'MESH' else []:
        if not m or not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                for k in ('Metallic', 'Roughness', 'Normal'):
                    for l in list(n.inputs[k].links):
                        m.node_tree.links.remove(l)
                n.inputs['Metallic'].default_value = 0.0
                n.inputs['Roughness'].default_value = rough
                n.inputs['Specular IOR Level'].default_value = 0.0
                if 'Coat Weight' in n.inputs:
                    n.inputs['Coat Weight'].default_value = 0.0
            if n.type == 'TEX_IMAGE' and nearest:
                n.interpolation = 'Closest'


def ids(objs, start=1):
    for k, o in enumerate(objs):
        o.pass_index = start + k


def area(name, loc, tgt, energy, color=(1, 1, 1), size=1.0):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.color, ld.size = energy, color, size
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = Vector(loc)
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def point(name, loc, energy, color=(1, 1, 1), radius=0.05):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy, ld.color, ld.shadow_soft_size = energy, color, radius
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = Vector(loc)
    return o


def camera(name='cam'):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'VERTICAL'
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def aim(cam, pos, tgt, vfov_deg):
    cam.location = Vector(pos)
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.angle = math.radians(vfov_deg)


def render(path_exr):
    bpy.context.scene.render.filepath = path_exr
    bpy.ops.render.render(write_still=True)
