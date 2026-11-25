"""Test bench of glasses6: 2D drawing, statistics, and close-up renders on a stand-in head.

    ../blender-venv/bin/python t_glasses6.py design                 # lab/glasses6/design.png (the 2D drawing, no render)
    ../blender-venv/bin/python t_glasses6.py render front q side    # lab/glasses6/<view>.png
    options: res=640x400 spp=16 tag=_a veil=0.12 reflect=0.04 flat=1 head=0
"""
import sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
args = sys.argv[1:]; sys.argv = ['x']
OUT = os.path.join(HERE, 'lab', 'glasses6'); os.makedirs(OUT, exist_ok=True)
opt = dict(a.split('=', 1) for a in args if '=' in a)
words = [a for a in args if '=' not in a]
import bpy, numpy as np
bpy.ops.wm.read_factory_settings(use_empty=True)
import addon_utils; addon_utils.enable('cycles', default_set=True)
import glasses6, look5


def plot_design(path, scale=9000):
    from PIL import Image, ImageDraw
    D = glasses6.design()
    W, H = int(0.150 * scale), int(0.062 * scale)
    im = Image.new('RGB', (W, H), (245, 245, 242)); dr = ImageDraw.Draw(im)
    def px(p): return (W / 2 + p[0] * scale, H * 0.42 - p[1] * scale)
    mir = np.array([-1.0, 1.0])
    dr.polygon([px(p) for p in D['outer']], fill=(70, 78, 76))
    for hole in (D['hole'], D['hole'] * mir):
        dr.polygon([px(p) for p in hole], fill=(225, 235, 245))
    for P, col in ((D['outer'], (255, 80, 60)), (D['hole'], (40, 90, 255))):
        for p in P:
            x, y = px(p); dr.ellipse((x - 2, y - 2, x + 2, y + 2), fill=col)
    for p in (D['hinge'], D['centre'], (0, 0)):
        x, y = px(p); dr.line((x - 9, y, x + 9, y), fill=(0, 160, 0), width=2); dr.line((x, y - 9, x, y + 9), fill=(0, 160, 0), width=2)
    for mm in range(-70, 71, 10):                                           # 10 mm ruler
        x, y = px((mm / 1000, -0.034)); dr.line((x, y, x, y + (14 if mm % 50 == 0 else 7)), fill=(0, 0, 0), width=1)
    im.save(path)
    print('design ->', path, 'bridge z', D['bridge_z'], 'centre', D['centre'], 'hinge', D['hinge'], 'x_end', D['x_end'],
          'top', D['outer'][:, 1].max(), 'bottom', D['outer'][:, 1].min())


def simple_mat(name, rgb, rough=0.5, **kw):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = tuple(rgb) + (1,); b.inputs['Roughness'].default_value = rough
    for k, v in kw.items(): b.inputs[k].default_value = v
    return m


def ellipsoid(name, c, r, mat, seg=64, rings=32):
    import bmesh
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    for v in bm.verts: v.co = (v.co.x * r[0], v.co.y * r[1], v.co.z * r[2])
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); ob.location = c
    return ob


def disc(name, c, r, mat):
    me = bpy.data.meshes.new(name)
    a = np.arange(32) * 2 * math.pi / 32
    me.from_pydata([(r * math.cos(t), 0, r * math.sin(t)) for t in a], [], [tuple(range(32))])
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); ob.location = c
    return ob


def stand_in(G):
    """Ellipsoid head 0.15 x 0.19 x 0.22 m, eyeballs with dark irises 12 mm behind the lenses, a nose and two ears."""
    skin = simple_mat('skin', (0.62, 0.36, 0.27), 0.5)
    white = simple_mat('sclera', (0.75, 0.73, 0.70), 0.25)
    iris = simple_mat('iris', (0.03, 0.07, 0.05), 0.3)
    pupil = simple_mat('pupil', (0.002, 0.002, 0.002), 0.3)
    (xr, zl), (xl, _) = G['lens_centres']
    ez = zl + 0.002
    y_cornea = G['lens_y'] + 0.012
    ellipsoid('head', (0, 0.1045, ez - 0.004), (0.075, 0.095, 0.11), skin)
    ellipsoid('nose', (0, 0.016, ez - 0.022), (0.0095, 0.024, 0.022), skin, 32, 16)
    for x in (xr, xl):
        ellipsoid('eye', (x, y_cornea + 0.012, ez), (0.012, 0.012, 0.012), white, 32, 16)
        disc('iris', (x, y_cornea - 0.00005, ez), 0.0058, iris)
        disc('pupil', (x, y_cornea - 0.00015, ez), 0.0022, pupil)
    for (x, y, z) in G['ear_points']:
        ellipsoid('ear', (x * 0.985, y + 0.012, z - 0.0325), (0.005, 0.017, 0.030), skin, 32, 16)


def render(views, res, spp, tag):
    sc = look5.setup(res[0], res[1], spp)
    look5.world((0.020, 0.030, 0.060), 1.0)
    G = glasses6.build('nox.glasses', wrap_radius=0.0 if opt.get('flat') else 0.36)
    kw = {k: float(opt[k]) for k in ('veil', 'rough', 'veil_follow', 'veil_slant', 'edge_dark', 'edge_haze') if k in opt}
    glasses6.set_lens(G, reflect=float(opt.get('reflect', 0.04)), **kw)
    print('TRIANGLES', G['triangles'], {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in G['objects']})
    for k in ('lens_centres', 'lens_y', 'hinges', 'temple_tips', 'ear_points', 'pad_centres', 'size', 'bridge_z', 'front_top_z', 'front_bottom_z'):
        print(k, G[k])
    for o in G['objects']:
        bb = np.array([list(v.co) for v in o.data.vertices]); print(o.name, 'bbox', bb.min(0).round(4), bb.max(0).round(4))
    if opt.get('head', '1') != '0':
        stand_in(G)
    tz = G['lens_centres'][0][1] + 0.004
    look5.area('key', (-0.75, -0.85, 0.50), (0, 0.02, tz), 42, (1.0, 0.85, 0.68), 0.45)
    look5.area('fill', (0.85, -0.95, -0.05), (0, 0.02, tz), 9, (0.55, 0.68, 1.0), 0.8)
    look5.area('rim', (0.25, 0.95, 0.50), (0, 0.05, tz), 30, (0.5, 0.65, 1.0), 0.5)
    cam = look5.camera('cam', 150)
    shots = {'front': ((0.0, -0.80, tz), (0.0, 0.0, tz), 150),
             'q': ((0.50, -0.62, tz + 0.10), (0.012, 0.012, tz), 150),
             'q2': ((-0.50, -0.62, tz + 0.03), (-0.012, 0.012, tz), 150),
             'side': ((0.85, 0.045, tz + 0.03), (0.07, 0.050, tz - 0.002), 150),
             'low': ((0.10, -0.75, tz - 0.22), (0.0, 0.0, tz), 150),
             'macro': ((0.20, -0.33, tz + 0.06), (0.045, 0.0, tz + 0.004), 150),
             'back': ((0.25, 0.42, tz + 0.10), (0.02, 0.02, tz), 110),
             'hinge': ((0.035, 0.085, 0.030), (0.064, 0.012, 0.002), 150),
             'top': ((0.0, -0.05, 0.75), (0.0, 0.055, 0.0), 120)}
    for v in views:
        pos, target, lens = shots[v]
        look5.aim(cam, pos, target, lens)
        sc.render.filepath = os.path.join(OUT, f'{v}{tag}.png')
        t = time.time(); bpy.ops.render.render(write_still=True); print('RENDER', v, round(time.time() - t, 1), 's', flush=True)


if words and words[0] == 'design':
    plot_design(os.path.join(OUT, 'design.png'))
elif words and words[0] == 'stats':
    G = glasses6.build('nox.glasses')
    print('TRIANGLES', G['triangles'], {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in G['objects']})
    for k in ('lens_centres', 'lens_y', 'hinges', 'temple_tips', 'ear_points', 'pad_centres', 'size', 'bridge_z', 'front_top_z', 'front_bottom_z'):
        print(k, G[k])
    for o in G['objects']:
        bb = np.array([list(v.co) for v in o.data.vertices]); print(o.name, 'bbox', bb.min(0).round(4), bb.max(0).round(4), len(o.data.vertices), 'verts')
else:
    w, h = (int(x) for x in opt.get('res', '640x400').split('x'))
    render(words[1:] or ['front', 'q', 'side'], (w, h), int(opt.get('spp', 16)), opt.get('tag', ''))
