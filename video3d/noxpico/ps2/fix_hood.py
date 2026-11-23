"""Pico's hood lining came out of the generator with a green / red pattern.  This paints the green part of the lining
in a shaded hoodie yellow, in the texture (base + mouth/blink variants), and leaves the green of the headphones alone.

    python fix_hood.py          -> out_fix/pico_{base,mouth_half,...}.png + a before/after mask preview"""
import os, sys
import bpy, bmesh
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

S = '/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad'
VAR = S + '/np3d_prod/out_face/var'
OUT = S + '/ps2/out_fix'
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=S + '/meshy/models/rig/pico_rigged.glb')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.vertex_groups)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
if arm.animation_data:
    arm.animation_data.action = None
for b in arm.pose.bones:
    b.location = (0, 0, 0); b.rotation_mode = 'QUATERNION'; b.rotation_quaternion = (1, 0, 0, 0)
bpy.context.view_layer.update()
node = next(n for m in mesh.data.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links)
img = node.image
W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)[::-1]          # row 0 = top
base = (np.clip(px[..., :3], 0, 1) * 255 + 0.5).astype(np.uint8)
print('texture', W, H, img.colorspace_settings.name)
me = mesh.data
uvl = me.uv_layers.active.data
Mw = mesh.matrix_world
neck = arm.matrix_world @ arm.pose.bones['neck'].head
polys = me.polygons
n = len(polys)
cent = np.array([tuple(Mw @ p.center) for p in polys])
uvc = np.array([np.mean([tuple(uvl[li].uv) for li in p.loop_indices], axis=0) for p in polys])
tx = np.clip((uvc[:, 0] * W).astype(int), 0, W - 1)
ty = np.clip(((1 - uvc[:, 1]) * H).astype(int), 0, H - 1)
col = base[ty, tx].astype(np.float32) / 255
r, g, b = col[:, 0], col[:, 1], col[:, 2]
green = (g > r * 1.25) & (g > b * 1.25) & (col.max(1) > 0.22)
black = col.max(1) < 0.16
rad = np.hypot(cent[:, 0] - neck.x, cent[:, 1] - neck.y)
zone = (cent[:, 2] > neck.z - 0.03) & (cent[:, 2] < neck.z + 0.13) & (rad > 0.025) & (rad < 0.19)
cand = green & zone
# adjacency (shared edges), to drop the green discs of the headphones (they sit in black plastic)
edge_polys = {}
for p in polys:
    for ek in p.edge_keys:
        edge_polys.setdefault(ek, []).append(p.index)
nb = [[] for _ in range(n)]
for ps in edge_polys.values():
    if len(ps) == 2:
        nb[ps[0]].append(ps[1]); nb[ps[1]].append(ps[0])
# grow candidate patches, look at what borders each patch
seen = np.zeros(n, bool)
keep = np.zeros(n, bool)
info = []
for s0 in np.where(cand)[0]:
    if seen[s0]:
        continue
    stack, patch = [s0], []
    seen[s0] = True
    while stack:
        i = stack.pop(); patch.append(i)
        for j in nb[i]:
            if cand[j] and not seen[j]:
                seen[j] = True; stack.append(j)
    border = set(j for i in patch for j in nb[i] if not cand[j])
    ring2 = set(k for j in border for k in nb[j] if not cand[k]) | border
    fb = np.mean([black[j] for j in ring2]) if ring2 else 0
    c = cent[patch].mean(0)
    info.append((len(patch), fb, c))
    if fb < 0.30:
        keep[patch] = True
info.sort(key=lambda x: -x[0])
for nfaces, fb, c in info[:14]:
    print(f'patch {nfaces:5d} faces, black border {fb:.2f}, centre ({c[0]:+.3f},{c[1]:+.3f},{c[2]:.3f}) -> {"lining" if fb < 0.30 else "headphones"}')
print('polygons recoloured', int(keep.sum()), 'of', int(cand.sum()), 'green in the collar zone')
mask = Image.new('L', (W, H), 0)
d = ImageDraw.Draw(mask)
for i in np.where(keep)[0]:
    pts = [(uvl[li].uv[0] * W, (1 - uvl[li].uv[1]) * H) for li in polys[i].loop_indices]
    d.polygon(pts, fill=255)
m = ndi.binary_dilation(np.asarray(mask) > 0, iterations=3)


def paint(arr):
    a = arr.astype(np.float32) / 255
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    gr = m & (G > R * 1.15) & (G > B * 1.15)
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    ochre = np.array([0.78, 0.60, 0.10], dtype=np.float32)              # hoodie yellow in the shade of the hood
    out = a.copy()
    out[gr] = np.clip(ochre[None, :] * (0.55 + 0.9 * lum[gr][:, None]), 0, 1)
    return (out * 255 + 0.5).astype(np.uint8), int(gr.sum())


fixed, cnt = paint(base)
print('texels repainted', cnt)
Image.fromarray(fixed).save(OUT + '/pico_base.png')
for k in ('mouth_half', 'mouth_open', 'mouth_wide', 'blink'):
    v = np.asarray(Image.open(f'{VAR}/pico_{k}.png').convert('RGB'))
    if v.shape[:2] != (H, W):
        print('variant size differs', k, v.shape); continue
    Image.fromarray(paint(v)[0]).save(f'{OUT}/pico_{k}.png')
vis = np.concatenate([base, fixed], axis=1)
Image.fromarray(vis).resize((1024, 512), Image.LANCZOS).save(OUT + '/before_after_tex.png')
