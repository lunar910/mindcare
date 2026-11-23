"""Find the face of a rigged Meshy character: 478 landmarks placed on the 3D model.   python faceprep.py NAME RIG.glb

A front, orthographic picture of the head (rest pose) is rendered with the world position of every pixel; MediaPipe's
face landmarker finds the eyes, eyebrows, lips and face outline in the picture; each landmark is then read back as a
point of the model.  Writes out_face2/NAME_front.png, NAME_landmarks.json (metres, rest pose, character facing -Y) and a
preview with the points drawn."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
S = '/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad'
MPY = S + '/mpenv/bin/python'
OUT = HERE + '/out_face2'
SIZE = 900


def capture(mesh, arm, name, tex_image=None):
    """Front ortho render of the head in the current (rest) pose.  Returns (png path, pos array, meta)."""
    import bpy
    import numpy as np
    from mathutils import Vector
    from PIL import Image
    import ps2render as PR
    import ps2shade as SH
    os.makedirs(OUT, exist_ok=True)
    bpy.context.view_layer.update()
    head = arm.matrix_world @ arm.pose.bones['Head'].head
    top = arm.matrix_world @ arm.pose.bones['head_end'].head
    front = arm.matrix_world @ arm.pose.bones['headfront'].head
    hh = (top - head).length                                         # skull height above the head joint
    centre = Vector((head.x, front.y, head.z + 0.42 * hh))
    scale = 1.55 * hh                                                # the picture covers this many metres
    PR.setup(SIZE, SIZE, ss=1)
    PR.split([mesh])
    for o in bpy.data.objects:
        if o.type == 'MESH' and o is not mesh:
            o.hide_render = True
    cam = PR.camera('facecam')
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
    rgba = np.concatenate([col, G['mask'][..., None].astype(np.float32)], axis=-1)
    png = f'{OUT}/{name}_front.png'
    Image.fromarray((rgba * 255 + 0.5).astype(np.uint8)).save(png)
    np.save(f'{OUT}/{name}_pos.npy', G['pos'].astype(np.float32))
    np.save(f'{OUT}/{name}_mask.npy', G['mask'])
    meta = dict(centre=tuple(centre), scale=scale, size=SIZE)
    return png, G['pos'], G['mask'], meta


def landmarks3d(name, png, pos, mask, meta):
    import numpy as np
    from scipy import ndimage as ndi
    js = f'{OUT}/{name}_lm2d.json'
    r = subprocess.run([MPY, HERE + '/landmarks.py', png, js, f'{OUT}/{name}_lm_preview.png'], capture_output=True, text=True)
    if not os.path.exists(js):
        raise RuntimeError('no face found: ' + r.stdout[-200:] + r.stderr[-300:])
    p2 = np.array(json.load(open(js)))
    # nearest pixel that belongs to the model, for points that fall just outside it
    idx = ndi.distance_transform_edt(~mask, return_distances=False, return_indices=True)
    out = []
    for x, y, z in p2:
        xi, yi = int(np.clip(round(x), 0, SIZE - 1)), int(np.clip(round(y), 0, SIZE - 1))
        yy, xx = idx[0][yi, xi], idx[1][yi, xi]
        P = pos[yy, xx]
        # x and z come from the picture itself (exact), the depth y from the surface under the point
        wx = meta['centre'][0] + (x - SIZE / 2) / SIZE * meta['scale']
        wz = meta['centre'][2] - (y - SIZE / 2) / SIZE * meta['scale']
        out.append((float(wx), float(P[1]), float(wz)))
    json.dump(dict(points=out, meta=meta), open(f'{OUT}/{name}_landmarks.json', 'w'))
    return np.array(out)


def load_rig(glb):
    import bpy
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == 'ARMATURE')
    mesh = next(o for o in new if o.type == 'MESH' and o.vertex_groups)
    for o in new:
        if o.type == 'MESH' and o is not mesh:
            o.hide_render = True
    if arm.animation_data:
        arm.animation_data.action = None
    for b in arm.pose.bones:
        b.location = (0, 0, 0)
        b.rotation_mode = 'QUATERNION'
        b.rotation_quaternion = (1, 0, 0, 0)
    bpy.context.view_layer.update()
    return arm, mesh


if __name__ == '__main__':
    import bpy
    import addon_utils
    name, glb = sys.argv[1], sys.argv[2]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable('cycles', default_set=True)
    import cast2
    arm, mesh = load_rig(glb)
    cast2.matte(mesh)
    if len(sys.argv) > 3 and os.path.exists(sys.argv[3]):               # optional repainted base texture
        node = next(n for m in mesh.data.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links)
        cs = node.image.colorspace_settings.name
        node.image = bpy.data.images.load(sys.argv[3])
        node.image.colorspace_settings.name = cs
    png, pos, mask, meta = capture(mesh, arm, name)
    pts = landmarks3d(name, png, pos, mask, meta)
    io = float(((pts[468] - pts[473]) ** 2).sum() ** 0.5)
    print(f'{name}: {len(pts)} landmarks, eye distance {io * 100:.1f} cm, mouth width {abs(pts[61][0] - pts[291][0]) * 100:.1f} cm, '
          f'nose ({pts[1][0]:+.3f},{pts[1][1]:+.3f},{pts[1][2]:.3f})')
