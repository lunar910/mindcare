"""Version 6 faces, step 1: a high-resolution front view of each head (rest pose).   python face6prep.py NAME RIG.glb

Writes out_face6/NAME_albedo.png (sRGB base colour, orthographic, the character faces the camera), NAME_pos.npy (world
position of every pixel), NAME_normal.npy, NAME_mask.npy and NAME_meta.json (centre, scale, size: the same framing as
out_face2, so the landmarks found there are valid here).  The face parts of version 6 (eye openings, lids, lips, the
skin under Nox's glasses) are rebuilt from these pictures as clean patches: see face6.py."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = HERE + '/out_face6'
SIZE = 2048


def capture(mesh, arm, name, size=SIZE):
    import bpy
    import numpy as np
    from mathutils import Vector
    from PIL import Image
    import ps2render as PR
    import ps2shade as SH
    os.makedirs(OUT, exist_ok=True)
    meta = json.load(open(f'{HERE}/out_face2/{name}_landmarks.json'))['meta']
    centre, scale = Vector(meta['centre']), meta['scale']
    PR.setup(size, size, ss=1)
    PR.split([mesh])
    for o in bpy.data.objects:
        if o.type == 'MESH' and o is not mesh:
            o.hide_render = True
    cam = PR.camera('facecam6')
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = scale
    cam.location = centre + Vector((0, -1.5, 0))
    cam.rotation_euler = (1.5707963, 0, 0)
    bpy.context.view_layer.update()
    exr = f'{OUT}/{name}_front.exr'
    PR.render_dynamic(exr)
    G = SH.load(exr)
    os.remove(exr)
    col = SH.srgb(G['albedo'])
    Image.fromarray((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8)).save(f'{OUT}/{name}_albedo.png')
    np.save(f'{OUT}/{name}_pos.npy', G['pos'].astype(np.float32))
    np.save(f'{OUT}/{name}_normal.npy', G['normal'].astype(np.float16))
    np.save(f'{OUT}/{name}_mask.npy', G['mask'])
    json.dump(dict(centre=tuple(centre), scale=scale, size=size), open(f'{OUT}/{name}_meta.json', 'w'))
    return G


if __name__ == '__main__':
    import bpy
    import addon_utils
    name, glb = sys.argv[1], sys.argv[2]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable('cycles', default_set=True)
    import cast2
    import faceprep
    arm, mesh = faceprep.load_rig(glb)
    cast2.matte(mesh)
    fix = f'{HERE}/out_fix/{name}_base.png'
    if os.path.exists(fix):
        node = next(n for m in mesh.data.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links)
        cs = node.image.colorspace_settings.name
        node.image = bpy.data.images.load(fix)
        node.image.colorspace_settings.name = cs
        print('repainted base texture used')
    capture(mesh, arm, name)
    print('captured', name)
