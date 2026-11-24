"""Try camera variants quickly: python t_cam5.py tag 'shot|t|px,py,pz|tx,ty,tz|lens' ...  (low res, few samples)"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
args = sys.argv[1:]; sys.argv = ['x']
import bpy
from mathutils import Vector
import excerpt5 as E, look5
E.RES = (270, 480)
W = E.build()
sc = bpy.context.scene
tag = args[0]
outs = []
for i, spec in enumerate(args[1:]):
    shot, t, p, tg, lens = spec.split('|')
    t = float(t)
    E.pose_at(W, t)
    E.camera_setup(W, W['cam'], shot, t)
    E.set_shot_lights(W, shot)
    if p:
        look5.aim(W['cam'], tuple(float(x) for x in p.split(',')), tuple(float(x) for x in tg.split(',')), float(lens))
        W['cam'].data.dof.use_dof = False
    sc.cycles.samples = 6
    f = f'{HERE}/out_v5t/cam_{tag}_{i}.png'
    sc.render.filepath = f
    bpy.ops.render.render(write_still=True)
    outs.append(f)
from PIL import Image, ImageDraw
ims = [Image.open(f).convert('RGB') for f in outs]
s = Image.new('RGB', (270 * len(ims), 480))
for i, im in enumerate(ims):
    d = ImageDraw.Draw(im); d.text((4, 4), str(i), fill=(255, 255, 0))
    s.paste(im, (i * 270, 0))
s.save(f'{HERE}/out_v5t/cam_{tag}.png')
print('CAM done', len(ims))
