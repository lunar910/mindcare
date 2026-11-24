"""Version 5 render look: Cycles path tracing, AgX tone mapping, OIDN denoising, soft output (no dithering).

    look5.setup(width=576, height=1024, samples=32)       # the production settings (also used for previews)
    look5.preview(build_fn, out_png, size=(768, 768))     # turntable-free product shot of a prop built at the origin

Preview from the shell (builds `module.build()` which must return a kit5.Prop):
    ../blender-venv/bin/python look5.py preview set5.bench bench.png [yaw_deg] [elev_deg]
"""
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))


def setup(width=576, height=1024, samples=32, threshold=0.04, bounces=(2, 2, 4), clamp_indirect=6.0):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    c = sc.cycles
    c.device = 'CPU'
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = threshold
    c.adaptive_min_samples = 0
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    try:
        c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
        c.denoising_prefilter = 'ACCURATE'
    except Exception:
        pass
    c.diffuse_bounces, c.glossy_bounces, c.max_bounces = bounces
    c.transmission_bounces = 4
    c.transparent_max_bounces = 8
    c.sample_clamp_indirect = clamp_indirect
    c.blur_glossy = 1.0
    c.caustics_reflective = c.caustics_refractive = False
    c.pixel_filter_type = 'BLACKMAN_HARRIS'
    c.filter_width = 1.5
    c.use_light_tree = True
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    looks = [l.identifier for l in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items]
    sc.view_settings.look = next((l for l in ('AgX - Base Contrast', 'AgX - Medium High Contrast') if l in looks), 'None')
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.image_settings.color_depth = '8'
    return sc


def world(rgb=(0.010, 0.014, 0.030), strength=1.0):
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('world')
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = tuple(rgb) + (1.0,)
    bg.inputs['Strength'].default_value = strength
    return w


def camera(name='cam', lens=35.0, sensor=36.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    cd.sensor_fit = 'HORIZONTAL'
    cd.clip_start, cd.clip_end = 0.03, 400
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def aim(cam, pos, target, lens=None, roll=0.0):
    cam.location = pos
    d = Vector(target) - Vector(pos)
    q = d.to_track_quat('-Z', 'Y')
    cam.rotation_euler = q.to_euler()
    if roll:
        cam.rotation_euler.rotate_axis('Z', math.radians(roll))
    if lens:
        cam.data.lens = lens


def dof(cam, focus_obj_or_dist, fstop=2.8):
    cam.data.dof.use_dof = True
    if isinstance(focus_obj_or_dist, (int, float)):
        cam.data.dof.focus_distance = focus_obj_or_dist
    else:
        cam.data.dof.focus_object = focus_obj_or_dist
    cam.data.dof.aperture_fstop = fstop


def area(name, pos, target, energy, color=(1.0, 0.9, 0.8), size=1.0, size_y=None):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.color = color
    if size_y:
        ld.shape = 'RECTANGLE'
        ld.size, ld.size_y = size, size_y
    else:
        ld.size = size
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = pos
    o.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    return o


def bbox(objs):
    pts = []
    for o in objs:
        if o.type in ('MESH', 'CURVE'):
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def preview(build, out, size=(768, 768), yaw=-30.0, elev=18.0, samples=48, lens=50.0):
    """Product shot of a prop on a neutral concrete floor, soft key + fill + rim, camera fitted to its bounds."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import mat5
    import kit5
    setup(size[0], size[1], samples)
    world((0.05, 0.055, 0.065), 1.0)
    P = build()
    bpy.context.view_layer.update()
    objs = [o for o in P.col.all_objects]
    lo, hi = bbox(objs)
    c = (lo + hi) / 2
    r = max((hi - lo).length / 2, 0.05)
    F = kit5.Prop('_floor')
    F.box('floor', (40, 40, 0.02), (0, 0, lo.z - 0.01), 'concrete_wall', bevel=0)
    cam = camera('pcam', lens)
    dist = r / math.tan(math.atan(18.0 / lens)) * 1.25
    a, e = math.radians(yaw), math.radians(elev)
    pos = c + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    aim(cam, pos, c)
    area('key', c + Vector((-2.0, -2.5, 3.0)) * max(r, 0.4), c, 900 * r * r + 60, (1.0, 0.93, 0.85), 2.0 * max(r, 0.3))
    area('fill', c + Vector((2.5, -1.5, 1.0)) * max(r, 0.4), c, 250 * r * r + 15, (0.85, 0.9, 1.0), 2.5 * max(r, 0.3))
    area('rim', c + Vector((0.5, 3.0, 2.5)) * max(r, 0.4), c, 500 * r * r + 30, (0.8, 0.88, 1.0), 1.5 * max(r, 0.3))
    sc = bpy.context.scene
    sc.render.filepath = out
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'preview {out} {time.time() - t:.1f} s, size {tuple(round(x, 3) for x in (hi - lo))} m', flush=True)
    return P


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    if len(sys.argv) > 1 and sys.argv[1] == 'preview':
        import importlib
        mod = importlib.import_module(sys.argv[2])
        fn = sys.argv[5] if len(sys.argv) > 5 and not sys.argv[5].lstrip('-').replace('.', '').isdigit() else 'build'
        yaw = float(sys.argv[4]) if len(sys.argv) > 4 else -30.0
        elev = float(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5].lstrip('-').replace('.', '').isdigit() else 18.0
        preview(getattr(mod, 'build'), sys.argv[3], yaw=yaw, elev=elev)
