"""Look-dev renders of eyes6 (static eyeball, shader gaze).

    ../blender-venv/bin/python t_eyes6.py front [tag]      one bare eye, front view, straight gaze
    ../blender-venv/bin/python t_eyes6.py sheet [tag]      3x3 gazes seen through a skin mask with an almond opening
    ../blender-venv/bin/python t_eyes6.py variants [tag]   brown / large iris / extreme gazes (pole check)
    ../blender-venv/bin/python t_eyes6.py check            conventions only (no render)
    ../blender-venv/bin/python t_eyes6.py anim             two tiny renders in one session: the iris must follow the gaze AND the head
"""
import sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
args = sys.argv[1:]; sys.argv = ['x']
import bpy
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
import addon_utils; addon_utils.enable('cycles', default_set=True)
import look5
import eyes6

OUT = f'{HERE}/lab/eyes6'
os.makedirs(OUT, exist_ok=True)
mode = args[0] if args else 'front'
tag = args[1] if len(args) > 1 else ''
BROWN = (0.23, 0.12, 0.06)
GREEN = (0.20, 0.42, 0.30)


def skin_mat():
    m = bpy.data.materials.get('mask_skin')
    if m:
        return m
    m = bpy.data.materials.new('mask_skin'); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (0.56, 0.33, 0.24, 1.0)
    b.inputs['Roughness'].default_value = 0.55
    b.inputs['Subsurface Weight'].default_value = 0.0
    return m


def mask(name, loc, radius=0.0245, depth=0.0148, w=0.034, h=0.014, cell=(0.040, 0.024), k=1.03, thick=0.0012):
    """Curved shell following the ellipsoid scaled by k, with an almond opening w x h, cut to a rectangular cell."""
    N, M = 128, 10
    hu, hl = h * 0.56, h * 0.44
    A, B = radius * k, depth * k

    def surf(x, z, lift=0.0):
        r2 = (x * x + z * z) / (A * A)
        y = -B * math.sqrt(max(0.0, 1.0 - r2))
        p = Vector((x, y, z))
        if lift:
            nrm = Vector((x / (A * A), y / (B * B), z / (A * A)))
            nrm = nrm.normalized() if r2 < 0.98 else Vector((0, -1, 0))
            p += nrm * lift
        return p

    inner, outer = [], []
    for i in range(N):
        th = 2 * math.pi * i / N
        x = 0.5 * w * math.cos(th)
        c = max(0.0, math.cos(math.pi * x / w))
        z = hu * c ** 0.85 if math.sin(th) >= 0 else -hl * c ** 1.15
        inner.append((x, z))
        dx, dz = math.cos(th), math.sin(th)
        s = min(0.5 * cell[0] / max(abs(dx), 1e-9), 0.5 * cell[1] / max(abs(dz), 1e-9), 0.97 * A)
        outer.append((dx * s, dz * s))
    verts, faces = [], []
    for layer in (0.0, thick):
        for j in range(M + 1):
            f = (j / M) ** 1.4
            for i in range(N):
                x = inner[i][0] + (outer[i][0] - inner[i][0]) * f
                z = inner[i][1] + (outer[i][1] - inner[i][1]) * f
                verts.append(surf(x, z, layer))
    R = (M + 1) * N
    for j in range(M):
        for i in range(N):
            a, b = j * N + i, j * N + (i + 1) % N
            c, d = b + N, a + N
            faces.append((R + a, R + b, R + c, R + d))       # outer skin (faces -Y)
            faces.append((a, d, c, b))                       # inner skin
    for i in range(N):                                       # lid margin
        a, b = i, (i + 1) % N
        faces.append((a, b, R + b, R + a))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.update()
    try:
        me.set_sharp_from_angle(angle=math.radians(50))
    except Exception as e:
        print('sharp', e)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    me.materials.append(skin_mat())
    return ob


def lights(c, dist=1.6, key=30.0, fill=5.0):      # same irradiance as the v5 cutscene key (160 W at 2.3 m)
    """Warm key upper left of the camera, dim blue fill on the right; same angular sizes as the cutscene key."""
    c = Vector(c)
    look5.area('key', c + Vector((-0.61, -0.70, 0.38)) * dist, c, key * dist * dist, (1.0, 0.85, 0.68), 0.38 * dist)
    look5.area('fill', c + Vector((0.72, -0.68, -0.10)) * dist, c, fill * dist * dist, (0.55, 0.68, 1.0), 0.6 * dist)


def ortho(width, center=(0, 0, 0)):
    cam = look5.camera('cam', 50)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = width
    look5.aim(cam, (center[0], center[1] - 0.6, center[2]), center)
    return cam


def render(name, w, h, samples=40):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.cycles.samples = samples
    sc.render.filepath = f'{OUT}/{name}{("_" + tag) if tag else ""}.png'
    t = time.time(); bpy.ops.render.render(write_still=True)
    print('RENDER', sc.render.filepath, round(time.time() - t, 1), 's', flush=True)


def check():
    E = eyes6.build('chk')
    bpy.context.view_layer.update()
    tris = sum(len(p.vertices) - 2 for p in E['eye'].data.polygons)
    ys = [v.co.y for v in E['eye'].data.vertices]
    print('tris', tris, 'verts', len(E['eye'].data.vertices), 'front pole y', min(ys), 'has pole vert',
          any(abs(v.co.x) < 1e-7 and abs(v.co.z) < 1e-7 and v.co.y < 0 for v in E['eye'].data.vertices))
    for yaw, pitch in ((0, 0), (0.35, 0), (0, 0.25), (-0.35, -0.25), (0.5, 0.5)):
        eyes6.set_gaze(E, yaw, pitch)
        bpy.context.view_layer.update()
        p = E['gaze'].matrix_world @ Vector((0, -1, 0))
        q = eyes6.iris_center(E)
        back = eyes6.shift_to_gaze(E, *eyes6.gaze_to_shift(E, yaw, pitch))
        print(f'yaw {yaw:+.2f} pitch {pitch:+.2f} -> iris centre world {tuple(round(c * 1000, 2) for c in p)} mm, '
              f'helper {tuple(round(c * 1000, 2) for c in q)} mm, roundtrip {tuple(round(c, 3) for c in back)}')
    E['root'].location = (0.1, 0.2, 1.5)
    bpy.context.view_layer.update()
    print('look_at left-up', eyes6.look_at(E, (0.6, -0.8, 1.9)), 'look_at straight', eyes6.look_at(E, (0.1, -2.0, 1.5)))


if mode == 'check':
    check()
    sys.exit(0)

look5.setup(640, 640, 40)
look5.world((0.010, 0.014, 0.030), 1.0)

if mode == 'front':
    E = eyes6.build('eye')
    lights((0, 0, 0))
    ortho(0.056)
    render('front', 640, 640, 48)

elif mode == 'sheet':
    cw, ch = 0.040, 0.024
    for r, pitch in enumerate((0.25, 0.0, -0.25)):
        for c, yaw in enumerate((-0.35, 0.0, 0.35)):
            loc = ((c - 1) * cw, 0.0, (1 - r) * ch)
            E = eyes6.build(f'eye{r}{c}')
            E['root'].location = loc
            eyes6.set_gaze(E, yaw, pitch)
            mask(f'mask{r}{c}', loc, cell=(cw, ch))
    lights((0, 0, 0))
    ortho(3 * cw)
    render('sheet', 640, 384, 40)

elif mode == 'variants':
    cw, ch = 0.052, 0.052
    cells = [  # (row, col, kwargs, gaze, masked)
        (0, 0, dict(iris_rgb=BROWN), (0.0, 0.0), False),
        (0, 1, dict(iris_rgb=GREEN, iris_radius=0.0095), (0.0, 0.0), False),
        (0, 2, dict(iris_rgb=BROWN), (0.5, 0.5), False),
        (1, 0, dict(iris_rgb=BROWN), (0.2, -0.1), True),
        (1, 1, dict(iris_rgb=GREEN, iris_radius=0.0095), (-0.35, 0.25), True),
        (1, 2, dict(iris_rgb=GREEN), (-0.5, -0.5), False),
    ]
    for r, c, kw, gz, masked in cells:
        loc = ((c - 1) * cw, 0.0, (0.5 - r) * ch)
        E = eyes6.build(f'eye{r}{c}', **kw)
        E['root'].location = loc
        eyes6.set_gaze(E, *gz)
        if masked:
            mask(f'mask{r}{c}', loc, cell=(cw, ch))
    lights((0, 0, 0))
    ortho(3 * cw)
    render('variants', 640, 427, 40)

elif mode == 'anim':
    # persistent-data session, like the production loop: pose -> render -> pose -> render
    from PIL import Image
    import numpy as np
    look5.world((0.5, 0.5, 0.5), 1.0)
    E = eyes6.build('eye')
    lights((0, 0, 0))
    W, H, width = 320, 192, 0.080
    ortho(width)
    poses = [((0.0, 0.0), (0.0, 0.0, 0.0), 0.0), ((0.35, 0.20), (0.010, 0.0, 0.004), 25.0), ((-0.30, -0.15), (-0.008, 0.0, -0.003), -15.0)]
    for i, (gz, loc, roll) in enumerate(poses):
        eyes6.set_gaze(E, *gz)
        E['root'].location = loc
        E['root'].rotation_euler = (0.0, math.radians(roll), 0.0)
        bpy.context.view_layer.update()
        exp = E['root'].matrix_world @ eyes6.iris_center(E)
        tag = f'{i}'
        render('anim', W, H, 12)
        im = np.asarray(Image.open(f'{OUT}/anim_{i}.png').convert('L'), dtype=float)
        ys, xs = np.nonzero(im < im.min() + 22)
        px = (xs.mean() - W / 2 + 0.5) * width / W
        pz = -(ys.mean() - H / 2 + 0.5) * width / W
        print(f'pose {i}: pupil seen at ({px * 1000:+.2f}, {pz * 1000:+.2f}) mm, expected ({exp.x * 1000:+.2f}, {exp.z * 1000:+.2f}) mm, '
              f'{len(xs)} px', flush=True)
