"""Step-by-step look at the version 6 face surgery.   python t_face6.py NAME STEP [clay|tex]"""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
args = sys.argv[1:]; sys.argv = ['x']
import bpy, bmesh, numpy as np
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
import addon_utils; addon_utils.enable('cycles', default_set=True)
import faceprep, look5, f6img, face6
name, step = args[0], args[1]; mode = args[2] if len(args) > 2 else 'clay'
arm, mesh = faceprep.load_rig(f'{HERE}/../meshy/models/rig/{name}_rigged.glb')
F = f6img.Front(name, HERE)
me = mesh.data; Mw = mesh.matrix_world.copy()
t = time.time()
if step == 'glasses':
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.verts.index_update(); bm.verts.ensure_lookup_table()
    node = next(n for m in me.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links)
    tc = face6.texture_colours(bm, node.image)
    R = face6.erase_glasses(bm, Mw, F, tc)
    print('glasses verts', int(R['gl'].sum()), 'arms', int(R['arms'].sum()), 'front', int(R['front'].sum()), 'time', round(time.time() - t, 1))
    bm.to_mesh(me); bm.free()
    if 'custom_normal' in me.attributes: me.attributes.remove(me.attributes['custom_normal'])
    for p in me.polygons: p.use_smooth = True
    at = me.color_attributes.new('dbg', 'FLOAT_COLOR', 'POINT')
    cols = np.ones((len(me.vertices), 4), np.float32); cols[:, :3] = 0.6
    cols[R['gl'], :3] = (0.9, 0.55, 0.4); cols[R['arms'], :3] = (0.3, 0.5, 0.9); cols[R['hairv'], :3] = (0.2, 0.2, 0.26); cols[R['hair_tip'], :3] = (0.5, 0.2, 0.6)
    print('hair tips brought down', int(R['hair_tip'].sum()))
    at.data.foreach_set('color', cols.ravel())
if step == 'eyes':
    import eyes6
    bm = bmesh.new(); bm.from_mesh(me)
    face6.ensure_layers(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.verts.index_update(); bm.verts.ensure_lookup_table()
    R = None
    if name == 'noxR':
        node = next(n for m in me.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links)
        R = face6.erase_glasses(bm, Mw, F, face6.texture_colours(bm, node.image))
        print('erased: front / filled verts', face6.mark_erased(bm, Mw, F, R))
    surf = face6.Surface(bm, Mw)
    hg = mesh.vertex_groups['Head'].index
    uvo = {}; front = []; geos = {}
    for s in 'RL':
        g = face6.EyeGeo(F, s, surf); geos[s] = g
        r = face6.cut_eye(bm, Mw, F, g, surf, hg, uv_override=uvo)
        front += r['new']
        print(s, 'eye w %.1f h %.1f mm, R %.1f D %.1f, iris r %.1f, loops %d, new verts %d faces %d' % (g.w*1000, g.h*1000, g.R*1000, g.D*1000, g.iris_r*1000, r['nloops'], len(r['new']), len(r['faces'])), 'fit', g.fitted)
    face6.write_front(bm, Mw, F, front, uvo)
    bm.to_mesh(me); bm.free()
    if 'custom_normal' in me.attributes: me.attributes.remove(me.attributes['custom_normal'])
    for p in me.polygons: p.use_smooth = True
    front_png = f'{HERE}/out_face6/{name}_albedo.png'; tex_rgb = None
    if R is not None:
        front_png = f'{HERE}/out_face6/{name}_front_tex.png'
        tex_rgb = f6img.repaint_front(F, np.load(f'{HERE}/out_face6/{name}_G.npy'), [geos[s].O for s in 'RL'], out=front_png)
    face6.hook_material(mesh, front_png, with_fill=R is not None)
    for s in 'RL':
        g = geos[s]
        col = F.rgb[int(F.px(np.array([g.iris_c[0], 0, g.iris_c[1] - 0.55 * g.iris_r]))[1]), int(F.px(np.array([g.iris_c[0] + 0.0 * g.iris_r, 0, g.iris_c[1]]))[0])]
        E = eyes6.build(f'{name}.eye{s}', radius=g.R, depth=g.D, iris_radius=g.iris_r, iris_rgb=eyes6.srgb(*[float(c) for c in col]))
        E['root'].location = g.centre
        eyes6.set_gaze(E, *eyes6.shift_to_gaze(E, g.iris_c[0] - g.c[0], g.iris_c[1] - g.c[1]))
        LD = face6.build_lids(f'{name}.eye{s}', g, E['holder'], F, tex_rgb)
        lidv = [float(x) for x in os.environ.get('LIDS', '0.15,0').split(',')]
        face6.set_lids(LD, *lidv)
        print(s, 'iris colour', np.round(col, 2))
    at = me.color_attributes.new('dbg', 'FLOAT_COLOR', 'POINT')
    cols = np.ones((len(me.vertices), 4), np.float32); cols[:, :3] = 0.6
    at.data.foreach_set('color', cols.ravel())
    print('time', round(time.time() - t, 1))
    uvl = me.uv_layers['uvfront']; fm = me.attributes['fmask']
    fmv = np.array([d.value for d in fm.data])
    li = [l.index for l in me.loops if fmv[l.vertex_index] > 0.5][:5]
    print('uv layers', [u.name for u in me.uv_layers], 'active', me.uv_layers.active.name, 'fmask sum', fmv.sum(), 'domain', fm.domain, fm.data_type)
    for i in li: print(' loop', i, 'uv', tuple(round(x, 3) for x in uvl.data[i].uv), 'vert', tuple(round(x, 3) for x in (Mw @ me.vertices[me.loops[i].vertex_index].co)))
    print('mat slots', len(me.materials), 'poly mat idx range', min(p.material_index for p in me.polygons), max(p.material_index for p in me.polygons))
if step == 'full':
    R = face6.build(mesh, arm, name)
    print('keys reach (mm):', {k: round(v * 1000, 1) for k, v in R['reach'].items()})
    print('eyes', {s: (round(g.R * 1000, 1), g.fitted) for s, g in R['eyes'].items()}, 'mouth w %.1f hu %.1f hl %.1f' % (R['mouth'].w * 1000, R['mouth'].hu * 1000, R['mouth'].hl * 1000))
    EX = json.loads(os.environ.get('EXPR', '{}'))
    face6.apply(R, EX)
    if os.environ.get('NOGLASSES') and 'glasses' in R['parts']:
        for o in R['parts']['glasses']['objects']: o.hide_render = True
    print('time', round(time.time() - t, 1))
    if os.environ.get('SHEET'):
        import look5 as LK
        from PIL import Image as PI, ImageDraw as PD
        SH = json.load(open(os.environ['SHEET']))
        sc = LK.setup(480, 480, 40)
        LK.world((0.05, 0.06, 0.09), 1.0)
        Lm = F.L
        tgt = Vector((Lm[1][0], Lm[1][1], Lm[1][2] - 0.012)) if os.environ.get('SHEETVIEW', 'face') == 'face' else Vector(((Lm[61][0] + Lm[291][0]) / 2, Lm[13][1], Lm[13][2] + 0.004))
        lens = 105 if os.environ.get('SHEETVIEW', 'face') == 'face' else 190
        LK.area('key', tuple(tgt + Vector((-0.5, -0.9, 0.5))), tuple(tgt), 60, (1.0, 0.86, 0.72), 0.6)
        LK.area('fill', tuple(tgt + Vector((0.7, -0.8, 0.0))), tuple(tgt), 12, (0.55, 0.68, 1.0), 1.0)
        import cast5
        class _A: pass
        a = _A(); a.mesh = mesh
        cast5.realism(a, body_normal=0.85); cast5.living_skin(a, hair_dark=(name == 'noxR'))
        cams = []
        for off, tg in (((0.05, -0.62, 0.02), 'f'), ((0.36, -0.50, 0.0), 'q')):
            cam = LK.camera('sheet' + tg, lens); LK.aim(cam, tuple(tgt + Vector(off)), tuple(tgt)); cams.append(cam)
        tiles = []
        for label, ex in SH:
            face6.apply(R, ex)
            row = []
            for cam in cams:
                sc.camera = cam; sc.render.filepath = f'{HERE}/lab/head6/_sheet.png'
                bpy.ops.render.render(write_still=True)
                im = PI.open(sc.render.filepath).convert('RGB'); PD.Draw(im).text((8, 6), label, fill=(255, 255, 0)); row.append(im)
            tiles.append(row)
        W = 480 * 2; n = len(tiles); ncol = int(os.environ.get('SHEETCOLS', 3))
        sheet = PI.new('RGB', (W * ncol, 480 * ((n + ncol - 1) // ncol)))
        for i, row in enumerate(tiles):
            for j, im in enumerate(row): sheet.paste(im, ((i % ncol) * W + j * 480, (i // ncol) * 480))
        outp = f'{HERE}/lab/head6/{name}_sheet{os.environ.get("TAG", "")}.jpg'
        sheet.save(outp, quality=90); print('sheet', outp)
        sys.exit(0)
sc = look5.setup(640, 640, 48)
look5.world((0.25, 0.25, 0.27), 1.0)
L = F.L; c = Vector((L[468] + L[473]) / 2)
if mode == 'clay':
    clay = bpy.data.materials.new('clay'); clay.use_nodes = True
    nt = clay.node_tree; b = nt.nodes['Principled BSDF']; b.inputs['Roughness'].default_value = 0.6
    a = nt.nodes.new('ShaderNodeAttribute'); a.attribute_name = 'dbg'; nt.links.new(a.outputs['Color'], b.inputs['Base Color'])
    if 'dbg' not in mesh.data.color_attributes:
        at = mesh.data.color_attributes.new('dbg', 'FLOAT_COLOR', 'POINT')
        cols = np.ones((len(mesh.data.vertices), 4), np.float32); cols[:, :3] = 0.6
        if 'fmask' in mesh.data.attributes:
            nv = len(mesh.data.vertices)
            fmv = np.zeros(nv, np.float32); mesh.data.attributes['fmask'].data.foreach_get('value', fmv)
            amv = np.zeros(nv, np.float32); mesh.data.attributes['amask'].data.foreach_get('value', amv)
            hfv = np.zeros(nv, np.int32); mesh.data.attributes['hairflag'].data.foreach_get('value', hfv)
            cols[hfv > 0, :3] = (0.15, 0.2, 0.6); cols[fmv > 0.5, :3] = (0.2, 0.7, 0.2); cols[amv > 0.5, :3] = (0.8, 0.15, 0.1)
            print('fmask', int((fmv > 0.5).sum()), 'amask', int((amv > 0.5).sum()), 'hair', int((hfv > 0).sum()), 'hair&amask', int(((hfv > 0) & (amv > 0.5)).sum()), 'hair&fmask', int(((hfv > 0) & (fmv > 0.5)).sum()))
        at.data.foreach_set('color', cols.ravel())
    mesh.data.materials.clear(); mesh.data.materials.append(clay)
else:
    import cast2; cast2.matte(mesh)
    if os.environ.get('FLAT'):
        for m in mesh.data.materials:
            nt = m.node_tree; b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
            src = b.inputs['Base Color'].links[0].from_socket
            em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(src, em.inputs['Color'])
            outn = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'); nt.links.new(em.outputs[0], outn.inputs['Surface'])
look5.area('key', tuple(c + Vector((-0.5, -0.9, 0.5))), tuple(c), 25, (1, 1, 1), 0.5)
out = f'{HERE}/lab/head6'
from PIL import Image
ims = []
for dx, dy, tag in ((0, -0.55, 'front'), (0.39, -0.39, 'q'), (0.55, 0.0, 'side')):
    cam = look5.camera(f'cam_{tag}', 85)
    look5.aim(cam, tuple(c + Vector((dx, dy, 0.0))), tuple(c - Vector((0, 0, 0.02))))
    sc.camera = cam
    sc.render.filepath = f'{out}/_{name}_{step}_{tag}.png'
    bpy.ops.render.render(write_still=True)
    ims.append(Image.open(sc.render.filepath).convert('RGB'))
s = Image.new('RGB', (1920, 640))
for i, im in enumerate(ims): s.paste(im, (i * 640, 0))
s.save(f'{out}/{name}_{step}_{mode}{os.environ.get("TAG", "")}.jpg', quality=92)
if os.environ.get('ZOOM'):
    z = os.environ['ZOOM']
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    tgt = c + Vector((0.0, 0, 0.004))
    lens = 200
    if z == 'mouth':
        tgt = Vector(((L[61][0] + L[291][0]) / 2, L[13][1], L[13][2] - 0.004)); lens = 230
    if z == 'face':
        tgt = Vector((L[1][0], L[1][1], L[1][2] + 0.01)); lens = 105; sc.render.resolution_x, sc.render.resolution_y = 960, 960
    views = [((0.06, -0.6, 0.0), '')] if z != 'mouth' else [((0.0, -0.6, 0.0), ''), ((0.33, -0.5, -0.05), 'q')]
    zi = []
    for off, tg in views:
        cam = look5.camera('cam_zoom' + tg, lens)
        look5.aim(cam, tuple(tgt + Vector(off)), tuple(tgt))
        sc.camera = cam
        sc.render.filepath = f'{out}/_{name}_{step}_{mode}_zoom{tg}.png'
        bpy.ops.render.render(write_still=True)
        zi.append(Image.open(sc.render.filepath).convert('RGB'))
    zs = Image.new('RGB', (zi[0].width * len(zi), zi[0].height))
    for i, im in enumerate(zi): zs.paste(im, (i * zi[0].width, 0))
    zs.save(f'{out}/{name}_{step}_{mode}_zoom{os.environ.get("TAG", "")}.jpg', quality=92)
