"""Face texture variants for lip-sync and blinks, PS2-style (texture swaps): finds the face in the texture through an
orthographic front render that stores the UV of every pixel, paints mouth / eye variants in that view and writes them
back into copies of the texture.

    blender: facefx.capture(mesh, out_prefix, size=1024)      -> <out>_col.png, <out>_uv.exr, <out>_meta.json
    python : facefx.variants(prefix, texture_png, out_dir)      -> mouth_closed/half/open, blink PNGs"""
import json
import math
import os

import numpy as np


def capture(mesh, out, size=1024, face_width=None):
    import bpy
    from mathutils import Vector
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    me = ev.to_mesh()
    co = np.array([tuple(mesh.matrix_world @ v.co) for v in me.vertices])
    ev.to_mesh_clear()
    lo, hi = co.min(0), co.max(0)
    H = hi[2] - lo[2]
    cx = (lo[0] + hi[0]) / 2
    far = co[np.abs(co[:, 0] - cx) > 0.28 * H]
    zmin = float(np.median(far[:, 2])) + 0.075 * H if len(far) > 50 else lo[2] + 0.7 * H
    cand = co[(np.abs(co[:, 0] - cx) < 0.03 * H) & (co[:, 2] > zmin)]
    nose = cand[np.argmin(cand[:, 1])]
    fw = face_width or 0.15 * (nose[2] - lo[2]) / 0.87 * 1.0
    centre = Vector((float(cx), float(nose[1]), float(nose[2]) + 0.0 * fw))
    # materials: texture as emission (colour pass), UV as emission (uv pass)
    tex_nodes = []
    for m in mesh.data.materials:
        nt = m.node_tree
        tx = next((n for n in nt.nodes if n.type == 'TEX_IMAGE'), None)
        out_n = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        em = nt.nodes.new('ShaderNodeEmission')
        uvn = nt.nodes.new('ShaderNodeTexCoord')
        em2 = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(uvn.outputs['UV'], em2.inputs['Color'])
        if tx is not None:
            nt.links.new(tx.outputs['Color'], em.inputs['Color'])
            tex_nodes.append(tx.image)
        tex_nodes and None
        m['_em'], m['_em2'] = em.name, em2.name
    cd = bpy.data.cameras.new('facecam'); cd.type = 'ORTHO'; cd.ortho_scale = fw * 1.6
    cam = bpy.data.objects.new('facecam', cd); sc.collection.objects.link(cam); sc.camera = cam
    cam.location = centre + Vector((0, -1.0, 0.0))
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 1; sc.cycles.pixel_filter_type = 'BOX'; sc.cycles.filter_width = 0.01
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.view_settings.view_transform = 'Standard'
    hide = [o for o in sc.objects if o.type == 'MESH' and o != mesh]
    for o in hide:
        o.hide_render = True
    ims = sc.render.image_settings
    for which, fmt in (('_em', 'PNG'), ('_em2', 'EXR')):
        for m in mesh.data.materials:
            nt = m.node_tree
            out_n = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
            nt.links.new(nt.nodes[m[which]].outputs[0], out_n.inputs['Surface'])
        if fmt == 'PNG':
            if hasattr(ims, 'media_type'):
                ims.media_type = 'IMAGE'
            ims.file_format = 'PNG'; ims.color_mode = 'RGBA'
            sc.render.filepath = out + '_col.png'
        else:
            if hasattr(ims, 'media_type'):
                ims.media_type = 'IMAGE'
            ims.file_format = 'OPEN_EXR'; ims.color_depth = '32'; ims.color_mode = 'RGBA'
            sc.render.filepath = out + '_uv.exr'
        sc.render.film_transparent = True
        bpy.ops.render.render(write_still=True)
    for o in hide:
        o.hide_render = False
    meta = dict(nose=[float(x) for x in nose], centre=list(centre), ortho=fw * 1.6, size=size,
                textures=[img.filepath or img.name for img in tex_nodes])
    json.dump(meta, open(out + '_meta.json', 'w'))
    return meta


# ------------------------------------------------------------------------------------------------ 2D side
def _read_uv(path):
    import OpenEXR
    f = OpenEXR.File(path)
    P = {}
    for part in f.parts:
        for k, c in part.channels.items():
            P[k] = np.asarray(c.pixels, dtype=np.float32)
    rgba = next(v for k, v in P.items() if v.ndim == 3)
    return rgba


def _ellipse(h, w, cy, cx, ry, rx):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 <= 1.0


def features(col):
    """Find the mouth line and the two eyes in the front face render (RGBA float 0..1). Coordinates in pixels (y, x)."""
    a = col[..., :3]
    al = col[..., 3] > 0.5
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    h, w = lum.shape
    skin = np.median(a[al & (lum > np.percentile(lum[al], 40))], axis=0)
    dark = al & (lum < 0.45 * (skin @ np.array([0.299, 0.587, 0.114])))
    # the face occupies the centre; eyes: dark blobs in the upper middle band, mouth: dark row in the lower band
    from scipy import ndimage as ndi
    lab, n = ndi.label(dark)
    blobs = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(ys) < 12:
            continue
        blobs.append(dict(y=ys.mean(), x=xs.mean(), n=len(ys), y0=ys.min(), y1=ys.max(), x0=xs.min(), x1=xs.max()))
    return skin, blobs, dark


def project(col_view, uv, tex, mask=None):
    """Write the pixels of col_view (H, W, 3, 0..1) into the texture (Ht, Wt, 3) through the UV render; mask: pixels to write."""
    out = tex.copy()
    Ht, Wt = tex.shape[:2]
    ok = uv[..., 3] > 0.5 if uv.shape[-1] == 4 else np.ones(uv.shape[:2], bool)
    if mask is not None:
        ok &= mask
    u, v = uv[..., 0][ok], uv[..., 1][ok]
    tx = np.clip((u * Wt).astype(int), 0, Wt - 1)
    ty = np.clip(((1 - v) * Ht).astype(int), 0, Ht - 1)
    out[ty, tx] = col_view[ok]
    return out
