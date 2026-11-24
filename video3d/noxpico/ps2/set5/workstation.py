"""Nox's electronics workstation (version 5 set): workbench with everything on it, swivel stool, soldering iron.

All props are built at the origin, standing on Z = 0, FRONT facing -Y (the side where Nox sits).  In the room the
bench goes at world (-3.15, 3.55, 0) heading 0 and the stool at world (-3.10, 2.70, 0): bench-local = world - (-3.15, 3.55).

    import workstation as ws                      # (from set5 import workstation as ws)
    B = ws.build_bench()                          # kit5.Prop, 2.90 x 0.80 m, top at 0.78, front edge y = -0.40
    S = ws.build_stool()                          # S.parts['pivot']: empty at the column top (z 0.43); seat = its children
    I = ws.build_iron()                           # origin = grip point, +Y = toward the tip; I.parts['cable_end']
    ws.rest_iron(B, I)                            # parent the iron to the stand (B.parts['iron_rest'])
    C = ws.build_iron_cable(ws.iron_cable_points(B, I), follow=I.parts['cable_end'])   # optional, follows the iron

Useful bench parts (all objects, bench-local unless parented deeper):
    'iron_rest'    empty in the iron stand: an iron whose root sits on it rests in the spiral
    'iron_socket'  empty at the soldering-station socket (cable start)
    'board'        empty at the PCB centre (board top surface, tilted 30 deg toward Nox) - look/hand target
    'lamp_light'   the desk lamp SPOT light (warm, aimed at the board), 'lamp_bulb' its emissive bulb
    'monitor_glow' the monitor's area light (cool), 'monitor_screen', 'scope_screen' emissive screens
    'mug'          the coffee mug sub-prop root (Nox's black coffee)
Constants: TOP (0.78), SEAT (0.52), NOX_SEAT (stool position in bench coords), BOARD (board centre in bench coords).
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import kit5  # noqa: E402
import mat5  # noqa: E402

try:
    from set5 import workstation_tex as wtex  # noqa: E402
except ImportError:  # pragma: no cover
    import workstation_tex as wtex  # noqa: E402

TOP = 0.78                      # bench top surface
TH = 0.045                      # top thickness
SEAT = 0.52                     # stool seat height
NOX_SEAT = (0.05, -0.85)        # stool position in bench coords (world -3.10, 2.70)
BOARD = (0.05, -0.105, 0.885)   # PCB centre in bench coords (world -3.10, 3.445)
WORLD_LOC = (-3.15, 3.55, 0.0)  # where the assembler puts the bench


# ------------------------------------------------------------------ small helpers
def V(*a):
    return Vector(a[0] if len(a) == 1 else a)


def deg(e):
    return tuple(math.degrees(a) for a in e)


def rot_to(d, up='Y'):
    """Euler (degrees) turning local +Z onto direction d."""
    return deg(Vector(d).normalized().to_track_quat('Z', up).to_euler())


def xf(loc, heading, p):
    """Point p of a sub-prop placed at loc with heading (deg) -> parent coordinates."""
    c, s = math.cos(math.radians(heading)), math.sin(math.radians(heading))
    return Vector((loc[0] + c * p[0] - s * p[1], loc[1] + s * p[0] + c * p[1], loc[2] + p[2]))


def empty(P, name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, size=0.03):
    ob = bpy.data.objects.new(f'{P.name}.{name}', None)
    ob.empty_display_size = size
    P.col.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = Euler(tuple(math.radians(a) for a in rot))
    ob.parent = parent or P.root
    P.parts[name] = ob
    return ob


def rod(P, name, a, b, r, mat, verts=16, bevel=0.0, r2=None, parent=None):
    a, b = Vector(a), Vector(b)
    d = b - a
    return P.cyl(name, r, d.length, tuple((a + b) / 2), mat, rot=rot_to(d), verts=verts, bevel=bevel, r2=r2, parent=parent)


def bar(P, name, a, b, w, h, mat, bevel=0.002, parent=None, up='Y'):
    a, b = Vector(a), Vector(b)
    d = b - a
    return P.box(name, (w, h, d.length), tuple((a + b) / 2), mat, rot=rot_to(d, up), bevel=bevel, parent=parent)


def lathe(P, name, prof, loc, mat, rot=(0, 0, 0), segs=32, bevel=0.0, parent=None, smooth=True):
    """Revolve a profile [(r, z), ...] around local Z (r = 0 points become poles)."""
    verts, faces, rings = [], [], []
    for r, z in prof:
        if r < 1e-7:
            rings.append([len(verts)])
            verts.append((0.0, 0.0, z))
        else:
            ring = []
            for j in range(segs):
                a = 2 * math.pi * j / segs
                ring.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    for A, B in zip(rings[:-1], rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        for j in range(segs):
            k = (j + 1) % segs
            if len(A) == 1:
                faces.append((A[0], B[k], B[j]))
            elif len(B) == 1:
                faces.append((A[j], A[k], B[0]))
            else:
                faces.append((A[j], A[k], B[k], B[j]))
    return P.mesh(name, verts, faces, loc, mat, rot, bevel, smooth, parent)


def taper_bar(P, name, a, b, w0, h0, w1, h1, mat, bevel=0.003, parent=None):
    """A bar whose section shrinks from (w0, h0) at a to (w1, h1) at b (horizontal-ish, up = +Z)."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    side = d.cross(Vector((0, 0, 1))).normalized()
    up = side.cross(d).normalized()
    vs = []
    for p, w, h in ((a, w0, h0), (b, w1, h1)):
        for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vs.append(tuple(p + side * sx * w / 2 + up * sz * h / 2))
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return P.mesh(name, vs, faces, (0, 0, 0), mat, (0, 0, 0), bevel, True, parent)


def helix(c0, c1, r0, r1, turns, n_per=12, phase=0.0):
    c0, c1 = Vector(c0), Vector(c1)
    ax = c1 - c0
    L = ax.length
    ax.normalize()
    u = ax.orthogonal().normalized()
    v = ax.cross(u)
    N = max(2, int(turns * n_per))
    pts = []
    for i in range(N + 1):
        t = i / N
        a = phase + 2 * math.pi * turns * t
        r = r0 + (r1 - r0) * t
        pts.append(tuple(c0 + ax * (L * t) + (u * math.cos(a) + v * math.sin(a)) * r))
    return pts


def set_uv(ob, u0, v0, u1, v1):
    uv = ob.data.uv_layers[0]
    for i, c in enumerate(((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
        uv.data[i].uv = c


def grid(P, name, w, h, nx, ny, zf, loc, mat, rot=(0, 0, 0), uv=(0, 0, 1, 1), parent=None):
    """A w x h sheet in local XY subdivided nx x ny, height z = zf(u, v) (u, v in 0..1), with UVs (page, cloth)."""
    verts, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            verts.append(((u - 0.5) * w, (v - 0.5) * h, zf(u, v)))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    ob = P.mesh(name, verts, faces, loc, mat, rot, 0.0, True, parent)
    lay = ob.data.uv_layers.new(name='UVMap')
    for poly in ob.data.polygons:
        for li in poly.loop_indices:
            vi = ob.data.loops[li].vertex_index
            i, j = vi % (nx + 1), vi // (nx + 1)
            lay.data[li].uv = (uv[0] + (uv[2] - uv[0]) * i / nx, uv[1] + (uv[3] - uv[1]) * j / ny)
    return ob


def cable(P, name, pts, r, mat, res=8, parent=None):
    ob = P.tube(name, pts, r, mat, resolution=res, parent=parent)
    ob.data.bevel_resolution = 2
    return ob


# ------------------------------------------------------------------ materials (cached per Blender session)
_MC = {}


def _butcher(name):
    """Butcher-block top: 57 mm strips along X, each with its own tone and grain, thin glue lines, oiled, a few
    solder burns and darker grime near the front edge where the forearms rest."""
    T = mat5._NT(name)
    tc = T.node('ShaderNodeTexCoord')
    obj = tc.outputs['Object']
    sep = T.node('ShaderNodeSeparateXYZ')
    T.link(obj, sep.inputs['Vector'])
    m = T.node('ShaderNodeMath', operation='MULTIPLY')
    T.link(sep.outputs['Y'], m.inputs[0])
    m.inputs[1].default_value = 17.5
    fl = T.node('ShaderNodeMath', operation='FLOOR')
    T.link(m.outputs[0], fl.inputs[0])
    wn = T.node('ShaderNodeTexWhiteNoise')
    wn.noise_dimensions = '1D'
    T.link(fl.outputs[0], wn.inputs['W'])
    r = wn.outputs['Value']
    sc = T.node('ShaderNodeVectorMath', operation='SCALE')
    sc.inputs[0].default_value = (37.0, 11.0, 23.0)
    T.link(r, sc.inputs['Scale'])
    vm = T.node('ShaderNodeVectorMath', operation='MULTIPLY')
    T.link(obj, vm.inputs[0])
    vm.inputs[1].default_value = (0.10, 1.0, 1.0)
    va = T.node('ShaderNodeVectorMath', operation='ADD')
    T.link(vm.outputs[0], va.inputs[0])
    T.link(sc.outputs[0], va.inputs[1])
    v = va.outputs[0]
    w = T.node('ShaderNodeTexWave')
    w.wave_type = 'RINGS'
    w.rings_direction = 'X'
    w.inputs['Scale'].default_value = 55.0
    w.inputs['Distortion'].default_value = 6.0
    w.inputs['Detail'].default_value = 4.0
    w.inputs['Detail Scale'].default_value = 0.6
    T.link(v, w.inputs['Vector'])
    n = T.noise(v, 5.0, 6.0, 0.6)
    fac = T.mix(0.55, w.outputs['Color'], n.outputs['Color'])
    bw = T.node('ShaderNodeRGBToBW')
    T.link(fac, bw.inputs['Color'])
    base = (146, 112, 80)
    col = T.ramp(bw.outputs['Val'], [(0.15, tuple(x * 0.84 for x in base)), (0.5, base), (0.85, (166, 128, 92))])
    tint = T.ramp(r, [(0.0, (180, 166, 156)), (0.45, (228, 218, 206)), (1.0, (255, 250, 238))])
    col = T.mix(1.0, col, tint, 'MULTIPLY')
    # glue lines between strips
    pp = T.node('ShaderNodeMath', operation='PINGPONG')
    T.link(m.outputs[0], pp.inputs[0])
    pp.inputs[1].default_value = 0.5
    line = T.maprange(pp.outputs[0], 0.0, 0.035, 0.55, 0.0)
    col = T.mix(line, col, (52, 34, 22))
    # grime toward the front edge (forearms) - object Y from -0.40 (front) to -0.28
    gn = T.noise(T.coord(1.0, seed=3.0), 9.0, 5.0, 0.6)
    edge = T.maprange(sep.outputs['Y'], -0.40, -0.27, 0.55, 0.0)
    gm = T.node('ShaderNodeMath', operation='MULTIPLY')
    T.link(edge, gm.inputs[0])
    T.link(gn.outputs['Fac'], gm.inputs[1])
    col = T.mix(gm.outputs[0], col, (70, 50, 34))
    # solder burns: small dark spots
    bn = T.noise(T.coord(1.0, seed=7.0), 22.0, 2.0, 0.5, 0.3)
    burn = T.maprange(bn.outputs['Fac'], 0.715, 0.75, 0.0, 0.9)
    big = T.noise(T.coord(1.0, seed=11.0), 2.5, 2.0, 0.5)
    bmask = T.maprange(big.outputs['Fac'], 0.52, 0.6, 0.0, 1.0)
    bm = T.node('ShaderNodeMath', operation='MULTIPLY')
    T.link(burn, bm.inputs[0])
    T.link(bmask, bm.inputs[1])
    col = T.mix(bm.outputs[0], col, (24, 16, 10))
    rough = T.maprange(bw.outputs['Val'], 0.2, 0.9, 0.56, 0.42)
    ra = T.node('ShaderNodeMath', operation='ADD')
    T.link(rough, ra.inputs[0])
    T.link(bm.outputs[0], ra.inputs[1])
    kp = T.coord((8.0, 300.0, 300.0), seed=1.0)
    pores = T.noise(kp, 1.0, 2.0, 0.5)
    h = T.node('ShaderNodeMath', operation='SUBTRACT')
    T.link(pores.outputs['Fac'], h.inputs[0])
    T.link(line, h.inputs[1])
    T.set(base=col, rough=ra.outputs[0], normal=T.bump(h.outputs[0], 0.18, 0.001), spec=0.5)
    return T.m


def _img(name, file, rough=0.5, emit=0.0, spec=0.5, coat=0.0, closest=False):
    T = mat5._NT(name)
    tx = T.node('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(file, check_existing=True)
    if closest:
        tx.interpolation = 'Closest'
    T.link(tx.outputs['Color'], T.bsdf.inputs['Base Color'])
    if emit:
        T.link(tx.outputs['Color'], T.bsdf.inputs['Emission Color'])
        T.set(emit=emit)
    T.set(rough=rough, spec=spec)
    if coat:
        T.set(coat=coat, coat_rough=0.05)
    return T.m


def _screen(name, file, strength):
    img = bpy.data.images.load(file, check_existing=True)
    return mat5.screen(name, img, strength)


def _coffee(name):
    T = mat5._NT(name)
    return T.set(base=(16, 9, 5), rough=0.04, spec=0.5, coat=0.3, coat_rough=0.02)


def _wool(name):
    """Brass wire wool: brass, very rough and fibrous (voronoi/noise bump)."""
    T = mat5._NT(name)
    v = T.coord(1.0)
    n = T.noise(v, 900.0, 2.0, 0.6, 3.0)
    n2 = T.noise(v, 60.0, 3.0, 0.6, 6.0)
    col = T.ramp(n2.outputs['Fac'], [(0.3, (120, 84, 36)), (0.7, (214, 170, 90))])
    return T.set(base=col, metal=1.0, rough=0.42, normal=T.bump(n.outputs['Fac'], 0.9, 0.002))


def _frosted(name, tint=(232, 236, 240), rough=0.28):
    T = mat5._NT(name)
    return T.set(base=tint, rough=rough, transmission=1.0, ior=1.46, spec=0.5)


def _foam(name, rgb=(40, 44, 50)):
    T = mat5._NT(name)
    v = T.coord(1.0)
    n = T.noise(v, 700.0, 2.0, 0.6)
    return T.set(base=rgb, rough=0.9, normal=T.bump(n.outputs['Fac'], 0.4, 0.0006), spec=0.3)


_MAKERS = {
    'butcher': _butcher,
    'esd': lambda n: mat5.matte(n, (36, 62, 70), 0.74, 0.05, 0.02, 9.0, 2.0),
    'case_dark': lambda n: mat5.plastic(n, (46, 48, 52), 0.42),
    'case_light': lambda n: mat5.painted_metal(n, (168, 170, 166), 0.42, 0.05, 2.0),
    'case_station': lambda n: mat5.painted_metal(n, (58, 60, 64), 0.38, 0.12, 4.0),
    'bezel': lambda n: mat5.plastic(n, (16, 16, 18), 0.32),
    'panel_black': lambda n: mat5.plastic(n, (24, 25, 27), 0.5),
    'knob': lambda n: mat5.plastic(n, (30, 30, 33), 0.38),
    'btn_grey': lambda n: mat5.plastic(n, (110, 112, 114), 0.5),
    'alu_dark': lambda n: mat5.metal(n, (74, 76, 80), 0.36),
    'holster': lambda n: mat5.plastic(n, (196, 150, 38), 0.68),
    'cable_black': lambda n: mat5.plastic(n, (18, 18, 20), 0.5),
    'cable_grey': lambda n: mat5.plastic(n, (84, 86, 90), 0.5),
    'cable_red': lambda n: mat5.plastic(n, (150, 26, 22), 0.42),
    'cable_white': lambda n: mat5.plastic(n, (214, 214, 208), 0.45),
    'chip': lambda n: mat5.plastic(n, (20, 20, 22), 0.62),
    'pin': lambda n: mat5.metal(n, (206, 206, 200), 0.24, brushed=False),
    'gold': lambda n: mat5.metal(n, (226, 184, 96), 0.22, brushed=False),
    'elec_cap': lambda n: mat5.plastic(n, (28, 40, 96), 0.38),
    'res_body': lambda n: mat5.plastic(n, (206, 176, 128), 0.5),
    'cer_cap': lambda n: mat5.plastic(n, (206, 146, 40), 0.42),
    'led_red': lambda n: mat5.plastic(n, (190, 24, 24), 0.18),
    'led_grn': lambda n: mat5.plastic(n, (30, 170, 60), 0.18),
    'term_blue': lambda n: mat5.plastic(n, (44, 92, 160), 0.42),
    'coffee': _coffee,
    'wool': _wool,
    'drawer': lambda n: _frosted(n),
    'org_frame': lambda n: mat5.plastic(n, (78, 84, 92), 0.5),
    'lamp_metal': lambda n: mat5.painted_metal(n, (34, 36, 38), 0.38, 0.12, 5.0),
    'lamp_inner': lambda n: mat5.matte(n, (232, 228, 218), 0.55, 0.03),
    'spring': lambda n: mat5.metal(n, (184, 186, 190), 0.22, brushed=False),
    'iron_handle': lambda n: mat5.plastic(n, (40, 42, 46), 0.42),
    'iron_grip': lambda n: _foam(n, (46, 54, 64)),
    'iron_tip': lambda n: mat5.metal(n, (112, 110, 108), 0.32, brushed=False),
    'sleeve': lambda n: mat5.metal(n, (168, 160, 150), 0.26),
    'strip_white': lambda n: mat5.plastic(n, (206, 205, 198), 0.46),
    'switch_lit': lambda n: mat5.emissive(n, (255, 70, 30), 2.5, (150, 24, 12)),
    'crate': lambda n: mat5.plastic(n, (82, 86, 90), 0.55),
    'toolbox': lambda n: mat5.painted_metal(n, (118, 44, 38), 0.42, 0.25, 6.0),
    'tape': lambda n: mat5.plastic(n, (196, 156, 96), 0.28),
    'foam_black': lambda n: _foam(n, (24, 24, 26)),
    'esd_bag': lambda n: mat5.metal(n, (150, 150, 156), 0.3, brushed=False),
    'cover': lambda n: mat5.matte(n, (42, 50, 64), 0.7, 0.06),
    'cover_red': lambda n: mat5.matte(n, (120, 40, 34), 0.65, 0.08),
    'cover_grey': lambda n: mat5.matte(n, (60, 66, 72), 0.7, 0.06),
    'pages': lambda n: mat5.matte(n, (226, 220, 204), 0.9, 0.04, 0.05, 40.0),
    'pen': lambda n: mat5.plastic(n, (30, 46, 110), 0.3),
    'seat': lambda n: mat5.leather(n, (40, 40, 44), 0.45, 1.0),
    'base_black': lambda n: mat5.plastic(n, (24, 24, 26), 0.32),
    'wheel': lambda n: mat5.plastic(n, (30, 30, 32), 0.3),
    'cast_black': lambda n: mat5.painted_metal(n, (30, 30, 32), 0.55, 0.18, 9.0),
    'solder': lambda n: mat5.metal(n, (176, 178, 182), 0.38),
    'spool_red': lambda n: mat5.plastic(n, (150, 34, 28), 0.4),
    'grip_red': lambda n: mat5.plastic(n, (160, 36, 30), 0.55),
    'grip_blue': lambda n: mat5.plastic(n, (40, 74, 140), 0.55),
    'grip_yellow': lambda n: mat5.plastic(n, (200, 160, 40), 0.5),
    'wire_red': lambda n: mat5.plastic(n, (180, 30, 24), 0.4),
    'wire_blue': lambda n: mat5.plastic(n, (30, 70, 170), 0.4),
    'wire_yel': lambda n: mat5.plastic(n, (210, 170, 30), 0.4),
    'led_glow_green': lambda n: mat5.emissive(n, (60, 255, 120), 6.0),
    'led_glow_white': lambda n: mat5.emissive(n, (200, 220, 255), 5.0),
    'led_glow_red': lambda n: mat5.emissive(n, (255, 50, 30), 5.0),
    'drawer_front': lambda n: mat5.painted_metal(n, (44, 46, 50), 0.4, 0.2, 3.0),
    'plywood': lambda n: mat5.wood(n, (176, 140, 96), 'X', ring_scale=4.0, dark=0.78, seed=4.0),
    'label_paper': lambda n: mat5.paper(n, (230, 228, 220)),
    'scalpel': lambda n: mat5.metal(n, (200, 202, 206), 0.15, brushed=False),
}
_IMGS = {
    'img_pcb': lambda n: _img(n, wtex.pcb(), 0.3, spec=0.5, coat=0.4),
    'img_notebook': lambda n: _img(n, wtex.notebook(), 0.9, spec=0.3),
    'img_labels': lambda n: _img(n, wtex.labels(), 0.85, spec=0.3),
    'img_meter': lambda n: _img(n, wtex.meter(), 0.55),
    'img_stpanel': lambda n: _img(n, wtex.panel_station(), 0.45),
    'scr_monitor': lambda n: _screen(n, wtex.monitor(), 1.4),
    'scr_scope': lambda n: _screen(n, wtex.scope(), 1.6),
    'scr_station': lambda n: _screen(n, wtex.station(), 2.2),
    'scr_psu_v': lambda n: _screen(n, wtex.psu(), 2.0),
    'scr_psu_a': lambda n: _screen(n, wtex.path('psu_a'), 2.0),
    'scr_meter': lambda n: _img(n, wtex.meter(), 0.5, emit=0.0),
}


def M(key):
    m = _MC.get(key)
    if m is not None:
        try:
            if m.name in bpy.data.materials:
                return m
        except ReferenceError:
            pass
    if key in _MAKERS:
        m = _MAKERS[key](f'ws_{key}')
    elif key in _IMGS:
        os.makedirs(wtex.TEX, exist_ok=True)
        m = _IMGS[key](f'ws_{key}')
    else:
        m = mat5.get(key)
    _MC[key] = m
    return m


# ------------------------------------------------------------------ sub-assemblies (each at its own origin)
def _monitor(col):
    P = kit5.Prop('ws_monitor', col)
    P.box('base', (0.25, 0.19, 0.012), (0, 0.03, 0.006), M('alu_dark'), bevel=0.005, segments=3)
    P.box('base_pad', (0.23, 0.17, 0.002), (0, 0.03, 0.0008), M('rubber_black'), bevel=0.0)
    P.box('neck', (0.052, 0.026, 0.31), (0, 0.054, 0.165), M('alu_dark'), bevel=0.006, segments=3)
    P.box('neck_slot', (0.03, 0.004, 0.06), (0, 0.068, 0.10), M('bezel'), bevel=0.002)
    pw, ph, zc = 0.614, 0.362, 0.325
    zb = zc - 0.168 - 0.018
    P.box('panel', (pw, 0.014, ph), (0, 0.0, zb + ph / 2), M('bezel'), bevel=0.003)
    P.box('chin', (pw - 0.004, 0.002, 0.016), (0, -0.0075, zb + 0.009), M('case_dark'), bevel=0.0008)
    P.box('back', (0.44, 0.03, 0.27), (0, 0.022, zb + ph / 2 - 0.01), M('case_dark'), bevel=0.012, segments=3)
    P.box('vesa', (0.11, 0.008, 0.11), (0, 0.04, zb + ph / 2 - 0.01), M('alu_dark'), bevel=0.003)
    for sx in (-1, 1):
        P.box('vent', (0.12, 0.004, 0.006), (sx * 0.14, 0.036, zb + ph - 0.06), M('bezel'), bevel=0.001)
    s = P.plane('screen', (0.597, 0.336), (0, -0.0072, zc), M('scr_monitor'), rot=(90, 0, 0))
    P.box('led', (0.004, 0.001, 0.0015), (0.27, -0.0088, zb + 0.008), M('led_glow_white'), bevel=0)
    L = P.light('glow', 'AREA', (0, -0.04, zc), 2.0, (0.72, 0.83, 1.0), 0.6, rot=(-90, 0, 0))
    L.data.shape = 'RECTANGLE'
    L.data.size, L.data.size_y = 0.58, 0.32
    try:
        L.data.spread = math.radians(120)
    except Exception:
        pass
    empty(P, 'cable_out', (0.05, 0.03, zb + 0.06))
    P.screen = s
    return P


def _knob(P, name, r, h, loc, rot, mat=None, cap='alu_dark', parent=None):
    prof = [(0, 0), (r, 0), (r, h * 0.15), (r * 0.96, h * 0.8), (r * 0.86, h), (0, h)]
    k = lathe(P, name, prof, loc, mat or M('knob'), rot, segs=24, parent=parent)
    return k


def _psu(col):
    P = kit5.Prop('ws_psu', col)
    W, D, H = 0.26, 0.26, 0.12
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.cyl('foot', 0.009, 0.006, (sx * 0.10, sy * 0.10, 0.003), M('rubber_black'), verts=16)
    P.box('case', (W, D, H), (0, 0, 0.006 + H / 2), M('case_light'), bevel=0.004)
    yf = -D / 2 - 0.003
    P.box('front', (W - 0.008, 0.006, H - 0.008), (0, -D / 2 - 0.001, 0.006 + H / 2), M('panel_black'), bevel=0.0015)
    z0 = 0.006
    for x, key in ((-0.055, 'scr_psu_v'), (0.04, 'scr_psu_a')):
        P.box('dwin', (0.07, 0.003, 0.028), (x, yf - 0.0005, z0 + 0.088), M('bezel'), bevel=0.001)
        P.plane('disp', (0.062, 0.0207), (x, yf - 0.0021, z0 + 0.088), M(key), rot=(90, 0, 0))
        for dx in (-0.016, 0.016):
            _knob(P, 'knob', 0.0105, 0.014, (x + dx, yf, z0 + 0.045), (90, 0, 0))
    for i, (key, z) in enumerate((('grip_red', 0.075), ('knob', 0.050), ('led_grn', 0.025))):
        x = 0.105
        lathe(P, 'post', [(0, 0), (0.0068, 0), (0.0068, 0.012), (0.0055, 0.014), (0.0055, 0.02), (0, 0.02)],
              (x, yf, z0 + z), M(key), (90, 0, 0), segs=16)
        P.cyl('post_hole', 0.002, 0.002, (x, yf - 0.0205, z0 + z), M('chip'), rot=(90, 0, 0), verts=12, bevel=0)
    P.box('power', (0.016, 0.008, 0.012), (-0.105, yf - 0.002, z0 + 0.02), M('btn_grey'), bevel=0.002)
    for sx in (-1, 1):
        for k in range(7):
            P.box('vent', (0.002, 0.004, 0.06), (sx * (W / 2 + 0.0005), -0.06 + k * 0.016, z0 + H / 2), M('bezel'), bevel=0)
    return P


def _scope(col):
    P = kit5.Prop('ws_scope', col)
    W, D, H = 0.32, 0.12, 0.155
    zf = 0.008
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.cyl('foot', 0.01, zf, (sx * 0.13, sy * 0.05, zf / 2), M('rubber_black'), verts=16)
    P.box('body', (W, D, H), (0, 0, zf + H / 2), M('case_dark'), bevel=0.008, segments=3)
    P.box('rear', (0.27, 0.05, 0.125), (0, D / 2 + 0.022, zf + 0.07), M('case_dark'), bevel=0.01, segments=3)
    P.box('front', (W - 0.006, 0.008, H - 0.006), (0, -D / 2 - 0.002, zf + H / 2), M('panel_black'), bevel=0.003)
    yf = -D / 2 - 0.006
    sx0, sz0 = -0.065, zf + 0.092
    P.box('scr_bezel', (0.172, 0.004, 0.104), (sx0, yf - 0.001, sz0), M('bezel'), bevel=0.002)
    s = P.plane('screen', (0.158, 0.0948), (sx0, yf - 0.0032, sz0), M('scr_scope'), rot=(90, 0, 0))
    for i in range(6):
        P.box('softkey', (0.016, 0.006, 0.007), (-0.14 + i * 0.026, yf - 0.002, zf + 0.026), M('btn_grey'), bevel=0.0015)
    P.cyl('pwr', 0.006, 0.006, (-0.145, yf - 0.002, zf + 0.012), M('btn_grey'), rot=(90, 0, 0), verts=16)
    # control area
    for (x, z, r) in ((0.045, 0.13, 0.0085), (0.08, 0.13, 0.0085), (0.12, 0.13, 0.0085), (0.06, 0.088, 0.011),
                      (0.105, 0.088, 0.011), (0.045, 0.052, 0.008), (0.13, 0.052, 0.008)):
        _knob(P, 'knob', r, 0.012, (x, yf, zf + z), (90, 0, 0))
    for i in range(4):
        key = 'led_glow_green' if i == 1 else 'btn_grey'
        P.box('btn', (0.011, 0.005, 0.0075), (0.142, yf - 0.0015, zf + 0.142 - i * 0.017), M(key), bevel=0.0015)
        P.box('btn', (0.011, 0.005, 0.0075), (0.02, yf - 0.0015, zf + 0.142 - i * 0.017), M('btn_grey'), bevel=0.0015)
    for i, x in enumerate((0.04, 0.07, 0.10, 0.13)):
        z = zf + 0.022
        lathe(P, 'bnc', [(0, 0), (0.0062, 0), (0.0062, 0.006), (0.0048, 0.007), (0.0048, 0.016), (0.002, 0.016), (0.002, 0.012), (0, 0.012)],
              (x, yf, z), M('chrome'), (90, 0, 0), segs=20)
        P.cyl('bnc_pin', 0.0012, 0.004, (x - 0.0052, yf - 0.012, z), M('chrome'), rot=(0, 90, 0), verts=8, bevel=0)
        ring = M('led_glow_green') if i == 0 else M('btn_grey')
        P.cyl('bnc_ring', 0.0078, 0.001, (x, yf - 0.0003, z), ring, rot=(90, 0, 0), verts=24, bevel=0)
    # back: fan grille + IEC inlet
    yb = D / 2 + 0.047
    P.cyl('fan', 0.032, 0.002, (0.06, yb, zf + 0.075), M('bezel'), rot=(90, 0, 0), verts=32, bevel=0)
    for rr in (0.012, 0.021, 0.03):
        P.torus('grille', rr, 0.0012, (0.06, yb + 0.001, zf + 0.075), M('chrome'), rot=(90, 0, 0))
    P.box('iec', (0.03, 0.006, 0.022), (-0.07, yb, zf + 0.04), M('bezel'), bevel=0.002)
    # carry handle folded on top
    for sx in (-1, 1):
        P.box('hdl_side', (0.012, 0.03, 0.012), (sx * 0.15, 0.0, zf + H + 0.004), M('case_dark'), bevel=0.003)
    rod(P, 'hdl', (-0.15, -0.012, zf + H + 0.009), (0.15, -0.012, zf + H + 0.009), 0.006, M('case_dark'), verts=12)
    empty(P, 'ch1', (0.04, yf - 0.016, zf + 0.022))
    P.screen = s
    return P


def _station(col):
    P = kit5.Prop('ws_station', col)
    W, D, H = 0.15, 0.17, 0.095
    zf = 0.006
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.cyl('foot', 0.008, zf, (sx * 0.06, sy * 0.07, zf / 2), M('rubber_black'), verts=16)
    P.box('case', (W, D, H), (0, 0, zf + H / 2), M('case_station'), bevel=0.004)
    yf = -D / 2 - 0.0015
    P.box('front', (W - 0.004, 0.004, H - 0.004), (0, -D / 2 - 0.0005, zf + H / 2), M('panel_black'), bevel=0.001)
    P.plane('print', (0.140, 0.0933), (0, yf - 0.0008, zf + H / 2), M('img_stpanel'), rot=(90, 0, 0))
    P.box('dwin', (0.068, 0.003, 0.032), (-0.022, yf - 0.002, zf + 0.062), M('bezel'), bevel=0.001)
    P.plane('display', (0.060, 0.0262), (-0.022, yf - 0.0036, zf + 0.062), M('scr_station'), rot=(90, 0, 0))
    _knob(P, 'knob', 0.013, 0.016, (0.045, yf - 0.001, zf + 0.062), (90, 0, 0))
    P.box('knob_mark', (0.0015, 0.002, 0.008), (0.045, yf - 0.0175, zf + 0.068), M('pin'), bevel=0)
    P.box('switch', (0.014, 0.006, 0.02), (-0.045, yf - 0.002, zf + 0.022), M('switch_lit'), bevel=0.0015, rot=(-8, 0, 0))
    lathe(P, 'socket', [(0, 0), (0.0095, 0), (0.0095, 0.004), (0.008, 0.006), (0.006, 0.006), (0.006, 0.002), (0, 0.002)],
          (0.045, yf, zf + 0.022), M('chrome'), (90, 0, 0), segs=24)
    P.cyl('socket_in', 0.0058, 0.002, (0.045, yf - 0.0035, zf + 0.022), M('bezel'), rot=(90, 0, 0), verts=24, bevel=0)
    for sx in (-1, 1):
        for k in range(6):
            P.box('vent', (0.002, 0.008, 0.05), (sx * (W / 2 + 0.0005), -0.03 + k * 0.015, zf + H / 2 + 0.005), M('bezel'), bevel=0)
    P.box('iec', (0.028, 0.004, 0.02), (0.03, D / 2 + 0.001, zf + 0.03), M('bezel'), bevel=0.002)
    empty(P, 'socket_pt', (0.045, yf - 0.012, zf + 0.022))
    empty(P, 'back_pt', (0.03, D / 2 + 0.006, zf + 0.03))
    return P


def _stand(col):
    """Iron stand: cast base, brass-wool cup, spiral holder at 45 deg (tip down/back, handle up/front)."""
    P = kit5.Prop('ws_stand', col)
    P.box('base', (0.10, 0.15, 0.018), (0, -0.015, 0.009), M('cast_black'), bevel=0.006, segments=3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.cyl('foot', 0.006, 0.002, (sx * 0.04, -0.015 + sy * 0.06, 0.0005), M('rubber_black'), verts=12, bevel=0)
    # cup with brass wool, front-left
    cx, cy = -0.027, -0.058
    lathe(P, 'cup', [(0, 0.018), (0.024, 0.018), (0.026, 0.02), (0.027, 0.044), (0.0255, 0.046), (0.024, 0.044),
                     (0.023, 0.022), (0, 0.022)], (cx, cy, 0), M('chrome'), segs=28)
    P.sphere('wool', 0.022, (cx, cy, 0.044), M('wool'), scale=(1.0, 1.0, 0.7), segments=20, rings=12)
    rnd = random.Random(4)
    for k in range(5):
        a = rnd.uniform(0, 6.28)
        c = Vector((cx + math.cos(a) * 0.012, cy + math.sin(a) * 0.012, 0.05 + rnd.uniform(-0.004, 0.004)))
        P.tube(f'wool_curl{k}', helix(c, c + Vector((rnd.uniform(-0.01, 0.01), rnd.uniform(-0.01, 0.01), 0.004)),
                                      0.004, 0.003, 2.0, 8, a), 0.0005, M('wool'))
    # spiral holder.  Rest point R = where the iron's grip point sits; d = toward the tip (down and back)
    d = Vector((0, math.cos(math.radians(45)), -math.sin(math.radians(45))))
    R = Vector((0.0, -0.048, 0.137))
    n = Vector((0, 0.7071, 0.7071))
    c0, c1 = R + d * 0.030, R + d * 0.124
    P.tube('spiral', helix(c0, c1, 0.021, 0.0105, 7.5, 14), 0.0012, M('chrome'), resolution=4)
    P.torus('ring_top', 0.021, 0.0018, tuple(c0), M('chrome'), rot=rot_to(d))
    P.torus('ring_bot', 0.0105, 0.0016, tuple(c1), M('chrome'), rot=rot_to(d))
    mid = R + d * 0.08
    bot = mid - n * 0.0165
    P.cyl('post', 0.005, bot.z - 0.018 + 0.004, (0, bot.y, (bot.z + 0.018) / 2 + 0.002), M('cast_black'), verts=16)
    P.box('clip', (0.012, 0.03, 0.004), tuple(bot - n * 0.002), M('cast_black'), rot=deg(Euler((math.radians(-45), 0, 0))), bevel=0.001)
    rest = empty(P, 'iron_rest', tuple(R), (-45, 0, 0))
    return P


def _pcb_parts(P, par):
    """Components on the PCB (parented to the board empty `par`; board top at z = 0.0008, 100 x 70 mm)."""
    BW, BH = 0.100, 0.070
    P.box('pcb', (BW, BH, 0.0016), (0, 0, 0), M('pcb_green'), bevel=0.0003, parent=par)
    P.plane('pcb_top', (BW - 0.0006, BH - 0.0006), (0, 0, 0.00082), M('img_pcb'), parent=par)
    z = 0.0008
    rnd = random.Random(12)
    for name, (u, v, kind) in wtex.PCB_PARTS.items():
        x, y = (u - 0.5) * BW, (v - 0.5) * BH
        if kind == 'dip16':
            P.box('U1', (0.0196, 0.0064, 0.0034), (x, y, z + 0.0008 + 0.0017), M('chip'), bevel=0.0004, parent=par)
            P.cyl('U1_dot', 0.0006, 0.0002, (x - 0.008, y, z + 0.0043), M('btn_grey'), verts=8, bevel=0, parent=par)
            for i in range(8):
                for s in (-1, 1):
                    P.box('pin', (0.0005, 0.0016, 0.0028), (x - 0.0089 + i * 0.00254, y + s * 0.0039, z + 0.0016), M('pin'), bevel=0, parent=par)
        elif kind == 'soic8':
            P.box('U2', (0.005, 0.0040, 0.0015), (x, y, z + 0.00075), M('chip'), bevel=0.0002, parent=par)
            for i in range(4):
                for s in (-1, 1):
                    P.box('pin', (0.0004, 0.0012, 0.0004), (x - 0.0019 + i * 0.00127, y + s * 0.0025, z + 0.0002), M('pin'), bevel=0, parent=par)
        elif kind == 'to220':
            P.box('Q1', (0.010, 0.0045, 0.009), (x, y, z + 0.0048), M('chip'), bevel=0.0004, parent=par)
            P.box('Q1_tab', (0.010, 0.0012, 0.0062), (x, y + 0.0028, z + 0.0124), M('pin'), bevel=0.0002, parent=par)
            P.cyl('Q1_hole', 0.0016, 0.0014, (x, y + 0.0028, z + 0.0128), M('chip'), rot=(90, 0, 0), verts=12, bevel=0, parent=par)
        elif kind.startswith('elec'):
            r, h = (0.004, 0.011) if kind == 'elec8' else (0.003, 0.0075)
            lathe(P, name, [(0, 0), (r, 0), (r, h - 0.0006), (r * 0.9, h), (0, h - 0.0001)], (x, y, z), M('elec_cap'), parent=par, segs=20)
            P.cyl(name + 'top', r * 0.86, 0.0002, (x, y, z + h), M('aluminium'), verts=20, bevel=0, parent=par)
            P.box(name + 'stripe', (0.0012, 0.0004, h * 0.8), (x - r * 0.98, y, z + h * 0.5), M('btn_grey'), bevel=0, parent=par)
            continue
        elif kind == 'res':
            P.cyl(name, 0.00115, 0.0064, (x, y, z + 0.0014), M('res_body'), rot=(0, 90, 0), verts=12, bevel=0.0003, parent=par)
            for k, c in enumerate(('wire_red', 'cable_red', 'chip', 'gold')):
                P.cyl(name + 'band', 0.00122, 0.0005, (x - 0.002 + k * 0.0011, y, z + 0.0014), M(c), rot=(0, 90, 0), verts=12, bevel=0, parent=par)
            for s in (-1, 1):
                rod(P, name + 'leg', (x + s * 0.0032, y, z + 0.0014), (x + s * 0.0055, y, z + 0.0014), 0.0003, M('pin'), verts=6, parent=par)
                rod(P, name + 'leg', (x + s * 0.0055, y, z + 0.0014), (x + s * 0.0055, y, z - 0.0005), 0.0003, M('pin'), verts=6, parent=par)
            continue
        elif kind == 'cer':
            P.sphere(name, 0.0022, (x, y, z + 0.0035), M('cer_cap'), scale=(1.0, 0.55, 1.0), segments=12, rings=8, parent=par)
            continue
        elif kind == 'led':
            P.cyl(name, 0.0015, 0.004, (x, y, z + 0.002), M('led_red'), verts=16, bevel=0.0002, parent=par)
            P.sphere(name + 'dome', 0.0015, (x, y, z + 0.004), M('led_red'), segments=12, rings=8, parent=par)
            continue
        elif kind == 'term2':
            P.box('J1', (0.0076, 0.010, 0.010), (x, y, z + 0.005), M('term_blue'), bevel=0.0006, parent=par)
            for s in (-1, 1):
                P.cyl('J1_screw', 0.0014, 0.0006, (x, y + s * 0.0025, z + 0.0102), M('chrome'), verts=12, bevel=0, parent=par)
                P.box('J1_slot', (0.0024, 0.0004, 0.0002), (x, y + s * 0.0025, z + 0.0106), M('chip'), bevel=0, parent=par)
            continue
        elif kind == 'hdr8':
            P.box('J2', (0.0203, 0.0025, 0.0025), (x, y, z + 0.00125), M('chip'), bevel=0.0002, parent=par)
            for i in range(8):
                P.box('J2_pin', (0.00064, 0.00064, 0.0085), (x - 0.0089 + i * 0.00254, y, z + 0.0038), M('gold'), bevel=0, parent=par)
            continue
        elif kind == 'xtal':
            P.box('Y1', (0.011, 0.0045, 0.0035), (x, y, z + 0.00175), M('chrome'), bevel=0.0015, segments=3, parent=par)
            continue


def _hands(col):
    """Helping hands: cast base, post, two arms with crocodile clips holding the PCB (tilted 30 deg toward -Y),
    a magnifier on a third arm.  Board centre = (0, -0.125, 0.105) in this prop."""
    P = kit5.Prop('ws_hands', col)
    bx = -0.065                      # base and post offset to Nox's left: keeps the reverse shot on his face clear
    P.box('base', (0.15, 0.085, 0.02), (bx, 0.01, 0.01), M('cast_black'), bevel=0.005, segments=3)
    for sx in (-1, 1):
        for sy in (-1, 1):
            P.cyl('foot', 0.006, 0.002, (bx + sx * 0.06, 0.01 + sy * 0.03, 0.0005), M('rubber_black'), verts=12, bevel=0)
    top = Vector((bx, 0.012, 0.15))
    rod(P, 'post', (bx, 0.012, 0.02), top, 0.0045, M('chrome'), verts=16)
    P.cyl('post_nut', 0.008, 0.008, (bx, 0.012, 0.024), M('chrome'), verts=6, bevel=0.0008)
    P.sphere('ball', 0.009, tuple(top), M('chrome'), segments=16, rings=10)
    bc = Vector((0, -0.125, 0.105))
    tilt = 30.0
    par = empty(P, 'board', tuple(bc), (tilt, 0, 0), size=0.02)
    _pcb_parts(P, par)
    rt = Euler((math.radians(tilt), 0, 0)).to_matrix()
    rod(P, 'crossbar', top + Vector((-0.07, 0, 0)), top + Vector((0.11, 0, 0)), 0.0032, M('chrome'), verts=12)
    for s in (-1, 1):
        jaw = bc + rt @ Vector((s * 0.055, 0, 0))
        rear = bc + rt @ Vector((s * 0.084, 0.0, 0.0))
        knuckle = top + Vector((0.11 if s > 0 else -0.07, 0, 0))
        P.sphere('ball', 0.0065, tuple(knuckle), M('chrome'), segments=14, rings=8)
        P.cyl('wing', 0.007, 0.004, tuple(knuckle + Vector((s * 0.008, 0, 0))), M('base_black'), rot=(0, 90, 0), verts=12)
        mid = (knuckle + rear) / 2 + Vector((s * 0.012, 0, 0.012))
        rod(P, 'arm', knuckle, mid, 0.0028, M('chrome'), verts=12)
        P.sphere('elbow', 0.005, tuple(mid), M('chrome'), segments=14, rings=8)
        rod(P, 'arm', mid, rear, 0.0028, M('chrome'), verts=12)
        P.sphere('joint', 0.0048, tuple(rear), M('chrome'), segments=14, rings=8)
        dj = (jaw - rear).normalized()
        for k in (-1, 1):  # two jaws of the crocodile clip pinching the board edge
            off = rt @ Vector((0, 0, k * 0.0022))
            bar(P, 'clip', rear + dj * 0.004 + off * 0.6, jaw + off * 0.3, 0.006, 0.0016, M('steel_bare'), bevel=0.0004)
        P.box('clip_spring', (0.004, 0.007, 0.007), tuple(rear + dj * 0.008), M('spring'), bevel=0.001)
    # magnifier between Nox's eyes and the board
    eye_dir = Vector((0, -0.88, 0.47)).normalized()
    lc = bc + eye_dir * 0.115 + Vector((-0.01, 0, 0.02))
    P.torus('lens_ring', 0.038, 0.0032, tuple(lc), M('bezel'), rot=rot_to(eye_dir))
    lathe(P, 'lens', [(0, -0.0038), (0.018, -0.003), (0.03, -0.0018), (0.0375, -0.0007), (0.0375, 0.0007), (0.03, 0.0018),
                      (0.018, 0.003), (0, 0.0038)], tuple(lc), M('glass_clear'), rot_to(eye_dir), segs=40)
    up_in_plane = eye_dir.cross(Vector((1, 0, 0))).normalized()
    if up_in_plane.z < 0:
        up_in_plane = -up_in_plane
    rim = lc + up_in_plane * 0.0415
    P.box('lens_lug', (0.01, 0.008, 0.012), tuple(rim), M('bezel'), rot=rot_to(eye_dir), bevel=0.002)
    mid = Vector((-0.045, -0.06, 0.24))
    rod(P, 'mag_arm', top + Vector((0, 0, 0.005)), mid, 0.0028, M('chrome'), verts=12)
    P.sphere('mag_joint', 0.0055, tuple(mid), M('chrome'), segments=14, rings=8)
    rod(P, 'mag_arm', mid, rim, 0.0028, M('chrome'), verts=12)
    return P


def _lamp_ik(S, J, L1, L2):
    h = Vector((J.x - S.x, J.y - S.y, 0))
    dh = h.length
    hd = h.normalized()
    dv = J.z - S.z
    d = min(math.hypot(dh, dv), L1 + L2 - 1e-4)
    a1 = math.atan2(dv, dh) + math.acos(max(-1, min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
    return S + hd * (math.cos(a1) * L1) + Vector((0, 0, math.sin(a1) * L1)), hd


def _lamp(col, head, target, energy=70.0):
    """Clamp-on architect lamp.  Origin = the clamp on the bench back edge (top surface level).  head = shade apex,
    target = point the shade aims at (both in this prop's coordinates)."""
    P = kit5.Prop('ws_lamp', col)
    mt = M('lamp_metal')
    P.box('clamp_top', (0.05, 0.062, 0.012), (0, 0.009, 0.006), mt, bevel=0.003)
    P.box('clamp_spine', (0.05, 0.014, 0.106), (0, 0.047, -0.035), mt, bevel=0.003)
    P.box('clamp_jaw', (0.05, 0.046, 0.012), (0, 0.024, -0.082), mt, bevel=0.003)
    P.cyl('screw', 0.004, 0.05, (0, 0.022, -0.075), M('steel_bare'), verts=12)
    P.cyl('pad', 0.010, 0.004, (0, 0.022, -0.047), M('rubber_black'), verts=16)
    rod(P, 'tbar', (-0.025, 0.022, -0.098), (0.025, 0.022, -0.098), 0.0035, M('steel_bare'), verts=10)
    for sx in (-1, 1):
        P.sphere('tbar_ball', 0.006, (sx * 0.026, 0.022, -0.098), M('base_black'), segments=12, rings=8)
    P.cyl('post', 0.009, 0.075, (0, 0, 0.012 + 0.0375), mt, verts=20)
    P.cyl('collar', 0.013, 0.014, (0, 0, 0.087), mt, verts=24, bevel=0.002)
    S = Vector((0, 0, 0.098))
    Nk = Vector(head)
    a = (Vector(target) - Nk).normalized()
    side0 = a.cross(Vector((0, 0, 1))).normalized()
    J = Nk - a * 0.02 + Vector((0, 0, 0.032))
    L1, L2 = 0.47, 0.47
    E, hd = _lamp_ik(S, J, L1, L2)
    sv = Vector((-hd.y, hd.x, 0))
    P.box('yoke', (0.024, 0.03, 0.03), tuple(S), mt, rot=(0, 0, math.degrees(math.atan2(hd.y, hd.x)) + 90), bevel=0.004)
    for s in (-1, 1):
        rod(P, 'arm_lo', S + sv * s * 0.013, E + sv * s * 0.013, 0.0042, mt, verts=12)
        rod(P, 'arm_up', E + sv * s * 0.011, J + sv * s * 0.011, 0.0038, mt, verts=12)
    for p, r in ((S, 0.011), (E, 0.009), (J, 0.008)):
        rod(P, 'knuckle', p - sv * 0.02, p + sv * 0.02, r, mt, verts=16, bevel=0.001)
        rod(P, 'knob', p + sv * 0.02, p + sv * 0.028, r * 1.15, M('base_black'), verts=16, bevel=0.001)
    # springs along the lower arm (outside the rods) and one on the upper arm
    du = (E - S).normalized()
    nrm = du.cross(sv).normalized()
    for s in (-1, 1):
        a0 = S + du * 0.03 + sv * s * 0.026 + nrm * 0.012
        a1 = S + du * 0.20 + sv * s * 0.026 + nrm * 0.012
        P.tube('spring', helix(a0, a1, 0.0048, 0.0048, 26, 8), 0.0007, M('spring'), resolution=3)
        rod(P, 'spring_hook', a0, S + sv * s * 0.02, 0.0007, M('spring'), verts=6)
        rod(P, 'spring_hook', a1, S + du * 0.21 + sv * s * 0.013, 0.0007, M('spring'), verts=6)
    du2 = (J - E).normalized()
    b0 = E + du2 * 0.03 + sv * 0.024
    b1 = E + du2 * 0.16 + sv * 0.024
    P.tube('spring_up', helix(b0, b1, 0.004, 0.004, 20, 8), 0.0006, M('spring'), resolution=3)
    # head: neck bracket, conical shade (black outside, white inside), bulb, real spot light
    rod(P, 'head_bracket', J, Nk + a * 0.005, 0.005, mt, verts=12)
    rt = rot_to(a)
    shell = [(0, -0.004), (0.017, -0.004), (0.018, 0.0), (0.018, 0.03), (0.074, 0.128), (0.077, 0.131)]
    lathe(P, 'shade', shell, tuple(Nk), mt, rt, segs=36)
    inner = [(0.0745, 0.129), (0.0168, 0.031), (0.0165, 0.002), (0, 0.002)]
    lathe(P, 'shade_in', inner, tuple(Nk), M('lamp_inner'), rt, segs=36)
    P.torus('rim', 0.0755, 0.0022, tuple(Nk + a * 0.130), mt, rot=rt)
    P.sphere('vent_cap', 0.019, tuple(Nk - a * 0.002), mt, scale=(1, 1, 1), segments=20, rings=10)
    bulb = P.sphere('bulb', 0.024, tuple(Nk + a * 0.056), M('lamp_warm'), segments=24, rings=12)
    bulb.visible_shadow = False
    lt = P.light('light', 'SPOT', tuple(Nk + a * 0.088), energy, (1.0, 0.80, 0.58), 0.025,
                 rot=deg(a.to_track_quat('-Z', 'Y').to_euler()), spot_deg=85)
    lt.data.spot_blend = 0.55
    # cable: head -> along the upper arm -> elbow -> lower arm -> post -> down the back of the clamp
    cpts = [Nk - a * 0.01 + Vector((0, 0, 0.012)), J + sv * 0.02 + Vector((0, 0, 0.012))]
    for t in (0.35, 0.7):
        cpts.append(J + (E - J) * t - sv * 0.018 + Vector((0, 0, 0.006)))
    cpts.append(E - sv * 0.022 + Vector((0, 0, 0.015)))
    for t in (0.3, 0.65):
        cpts.append(E + (S - E) * t - sv * 0.02)
    cpts += [S + Vector((0, 0.016, -0.02)), Vector((0, 0.016, 0.03)), Vector((0, 0.03, 0.01)), Vector((0, 0.058, -0.02)),
             Vector((0.005, 0.06, -0.10))]
    cable(P, 'cable', [tuple(p) for p in cpts], 0.0022, M('cable_black'))
    empty(P, 'cable_end', (0.005, 0.06, -0.10))
    P.bulb, P.spot = bulb, lt
    return P


def _meter(col):
    """Multimeter lying flat, face up, LCD toward +Y.  Probes plugged in at the -Y end."""
    P = kit5.Prop('ws_meter', col)
    P.box('holster', (0.092, 0.185, 0.044), (0, 0, 0.022), M('holster'), bevel=0.01, segments=3)
    P.box('face', (0.076, 0.165, 0.004), (0, 0, 0.0435), M('case_dark'), bevel=0.0015)
    P.plane('face_print', (0.074, 0.148), (0, 0.001, 0.0458), M('img_meter'))
    P.box('lcd_glass', (0.058, 0.026, 0.0008), (0, 0.0465, 0.0462), M('glass_clear'), bevel=0)
    _knob(P, 'dial', 0.022, 0.009, (0, -0.012, 0.0458), (0, 0, 0), mat=M('base_black'))
    P.box('dial_bar', (0.009, 0.040, 0.008), (0, -0.012, 0.0545), M('base_black'), rot=(0, 0, 35), bevel=0.003)
    P.box('dial_mark', (0.0015, 0.012, 0.0008), (-0.0085, -0.0001, 0.0586), M('cable_white'), rot=(0, 0, 35), bevel=0)
    jacks = []
    for i, x in enumerate((-0.027, -0.009, 0.009, 0.027)):
        c = 'grip_red' if i == 3 else ('base_black' if i == 2 else 'knob')
        lathe(P, 'jack', [(0, -0.003), (0.0055, -0.003), (0.0055, 0.0), (0.0035, 0.0), (0.0035, -0.002), (0, -0.002)],
              (x, -0.068, 0.0473), M(c), segs=16)
        jacks.append(Vector((x, -0.068, 0.0473)))
    P.jacks = jacks
    P.box('kick', (0.07, 0.10, 0.003), (0, 0.02, 0.0015), M('holster'), bevel=0.001)
    return P


def _probe(P, name, tip, d, grip, parent=None):
    """A test probe lying on the bench: plastic body along d, finger guard, needle at tip."""
    d = Vector(d).normalized()
    tip = Vector(tip)
    lathe_rot = rot_to(-d)
    base = tip - d * 0.0
    lathe(P, name, [(0, 0), (0.0045, 0.0), (0.0048, 0.075), (0.007, 0.078), (0.007, 0.083), (0.0035, 0.088),
                    (0.0025, 0.105), (0, 0.106)], tuple(tip - d * 0.125), M(grip), rot_to(d), segs=16, parent=parent)
    rod(P, name + '_needle', tip - d * 0.020, tip, 0.0008, M('steel_bare'), verts=8, r2=0.0003, parent=parent)
    return tip - d * 0.125


def _mug(col):
    P = kit5.Prop('ws_mug', col)
    prof = [(0, 0.003), (0.033, 0.003), (0.0355, 0.0), (0.0395, 0.002), (0.0405, 0.012), (0.041, 0.088),
            (0.0405, 0.0945), (0.0385, 0.096), (0.0368, 0.0945), (0.0364, 0.088), (0.0362, 0.014), (0.03, 0.0105), (0, 0.0098)]
    lathe(P, 'mug', prof, (0, 0, 0), M('ceramic_black'), segs=40)
    P.tube('handle', [(0.039, 0, 0.078), (0.056, 0, 0.081), (0.067, 0, 0.06), (0.063, 0, 0.034), (0.039, 0, 0.026)],
           0.0058, M('ceramic_black'), resolution=10)
    P.cyl('coffee', 0.0362, 0.0012, (0, 0, 0.056), M('coffee'), verts=40, bevel=0)
    P.torus('coffee_ring', 0.0364, 0.0007, (0, 0, 0.0585), M('coffee'))
    return P


def _notebook(col):
    """Open spiral notebook (A5 spread) with sketches, a pen lying on it."""
    P = kit5.Prop('ws_notebook', col)
    P.box('cover', (0.304, 0.214, 0.0018), (0, 0, 0.0009), M('cover'), bevel=0.0006)
    for s, uv in ((-1, (0.0, 0.0, 0.5, 1.0)), (1, (0.5, 0.0, 1.0, 1.0))):
        def zf(u, v, s=s):
            t = (1 - u) if s < 0 else u          # 0 at the spine, 1 at the outer edge
            return 0.0055 * math.sin(math.pi * min(1, t * 1.15 + 0.05)) ** 0.6 * (1 - 0.25 * t) - 0.0045 * (1 - t) ** 6
        grid(P, 'page', 0.148, 0.208, 14, 4, zf, (s * 0.0755, 0, 0.0018), M('img_notebook'), uv=uv)
        P.box('stack', (0.146, 0.206, 0.003), (s * 0.0755, 0, 0.0033), M('pages'), bevel=0.0008)
    for k in range(17):
        y = -0.096 + k * 0.012
        P.torus('coil', 0.0055, 0.0007, (0, y, 0.0042), M('steel_bare'), rot=(90, 0, 0))
    # pen across the right page
    d = Vector((math.cos(math.radians(70)), math.sin(math.radians(70)), 0))
    c = Vector((0.085, -0.01, 0.0105))
    lathe(P, 'pen', [(0, 0), (0.0012, 0.002), (0.003, 0.016), (0.0045, 0.022), (0.0045, 0.128), (0.004, 0.134), (0, 0.135)],
          tuple(c - d * 0.07), M('pen'), rot_to(d), segs=16)
    P.box('pen_clip', (0.0016, 0.045, 0.0012), tuple(c + d * 0.035 + Vector((0, 0, 0.0048))), M('chrome'),
          rot=(0, 0, math.degrees(math.atan2(d.y, d.x)) - 90), bevel=0.0004)
    return P


def _spool(col):
    """Solder spool on a small dispenser (axis along X), wire end coming out toward -Y."""
    P = kit5.Prop('ws_spool', col)
    P.box('base', (0.075, 0.055, 0.008), (0, 0, 0.004), M('cast_black'), bevel=0.003)
    for sx in (-1, 1):
        P.box('cheek', (0.004, 0.02, 0.04), (sx * 0.026, 0, 0.026), M('cast_black'), bevel=0.0015)
    rod(P, 'axle', (-0.03, 0, 0.04), (0.03, 0, 0.04), 0.003, M('steel_bare'), verts=12)
    for sx in (-1, 1):
        P.cyl('flange', 0.027, 0.0025, (sx * 0.0175, 0, 0.04), M('spool_red'), rot=(0, 90, 0), verts=32, bevel=0.0008)
    P.cyl('wound', 0.0205, 0.0325, (0, 0, 0.04), M('solder'), rot=(0, 90, 0), verts=32, bevel=0.0015)
    for k in range(9):
        P.torus('turn', 0.0207, 0.0009, (-0.0145 + k * 0.0036, 0, 0.04), M('solder'), rot=(0, 90, 0))
    pts = [(0.004, -0.019, 0.032), (0.006, -0.032, 0.018), (0.004, -0.05, 0.006), (-0.01, -0.075, 0.002), (-0.03, -0.09, 0.0025)]
    P.tube('wire', pts, 0.0005, M('solder'), resolution=8)
    return P


def _strip(col):
    """French power strip (5 sockets facing up) along X; plugs in 1, 2, 4; lit switch at +X."""
    P = kit5.Prop('ws_strip', col)
    L = 0.33
    P.box('body', (L, 0.054, 0.038), (0, 0, 0.019), M('strip_white'), bevel=0.008, segments=3)
    socks = []
    for i in range(5):
        x = -0.13 + i * 0.056
        socks.append(x)
        lathe(P, 'socket', [(0, 0.032), (0.0185, 0.032), (0.0195, 0.0385), (0.0205, 0.0388), (0.0, 0.0388)],
              (x, 0, 0), M('strip_white'), segs=28)
        P.cyl('sock_in', 0.0182, 0.0005, (x, 0, 0.0324), M('cable_grey'), verts=28, bevel=0)
        for s in (-1, 1):
            P.cyl('hole', 0.0025, 0.0004, (x + s * 0.0095, 0, 0.0328), M('chip'), verts=10, bevel=0)
        P.cyl('earth', 0.0024, 0.006, (x, 0.0125, 0.035), M('chrome'), verts=10, bevel=0)
    P.box('switch', (0.022, 0.03, 0.008), (0.152, 0, 0.040), M('switch_lit'), bevel=0.003)
    plugs = []
    for i, colr in ((0, 'cable_black'), (1, 'cable_black'), (3, 'cable_white')):
        x = socks[i]
        body = M('strip_white') if colr == 'cable_white' else M('base_black')
        lathe(P, 'plug', [(0, 0.032), (0.0175, 0.032), (0.0185, 0.036), (0.019, 0.058), (0.0165, 0.064), (0, 0.065)],
              (x, 0, 0.0), body, segs=24)
        for k in range(5):
            P.torus('grip', 0.0188, 0.0011, (x, 0, 0.04 + k * 0.004), body)
        P.cyl('relief', 0.0055, 0.016, (x, 0.019, 0.05), body, rot=(-90, 0, 0), verts=16, r2=0.0035)
        plugs.append((Vector((x, 0.027, 0.05)), colr))
    P.plugs = plugs
    P.cord_start = Vector((L / 2 + 0.002, 0.0, 0.016))
    P.cyl('cord_relief', 0.006, 0.016, (L / 2 + 0.006, 0, 0.016), M('strip_white'), rot=(0, 90, 0), verts=16, r2=0.004)
    return P


def _organiser(col):
    """Small-parts cabinet, 4 x 6 translucent drawers, handwritten labels; two drawers pulled out."""
    P = kit5.Prop('ws_organiser', col)
    W, D, H = 0.30, 0.15, 0.245
    t = 0.004
    fr = M('org_frame')
    P.box('back', (W, t, H), (0, D / 2 - t / 2, H / 2), fr, bevel=0.0015)
    for sx in (-1, 1):
        P.box('side', (t, D, H), (sx * (W / 2 - t / 2), 0, H / 2), fr, bevel=0.0015)
    P.box('top', (W, D, t), (0, 0, H - t / 2), fr, bevel=0.0015)
    P.box('bottom', (W, D, t), (0, 0, t / 2), fr, bevel=0.0015)
    cols, rows = 4, 6
    cw = (W - 2 * t) / cols
    rh = (H - 2 * t) / rows
    for r in range(1, rows):
        P.box('shelf', (W - 2 * t, D - t, 0.002), (0, -t / 2, t + r * rh), fr, bevel=0)
    for c in range(1, cols):
        P.box('divider', (0.002, D - t, H - 2 * t), (-W / 2 + t + c * cw, -t / 2, H / 2), fr, bevel=0)
    P.box('inside', (W - 2 * t, 0.002, H - 2 * t), (0, D / 2 - t - 0.002, H / 2), M('chip'), bevel=0)
    rnd = random.Random(21)
    content = ['res_body', 'chip', 'led_red', 'pin', 'elec_cap', 'cer_cap', 'led_grn', 'cable_red', 'wire_blue', 'gold']
    pulled = {(1, 3): 0.055, (2, 1): 0.03}
    for r in range(rows):
        for c in range(cols):
            i = (rows - 1 - r) * cols + c
            x = -W / 2 + t + (c + 0.5) * cw
            z = t + (r + 0.5) * rh
            out = pulled.get((c, r), rnd.uniform(0.0, 0.004))
            yf = -D / 2 + 0.002 - out
            P.box('drawer', (cw - 0.004, 0.003, rh - 0.004), (x, yf, z), M('drawer'), bevel=0.001)
            P.box('tab', (0.02, 0.008, 0.004), (x, yf - 0.005, z - rh / 2 + 0.008), M('drawer'), bevel=0.0012)
            lb = P.plane('label', (cw - 0.014, 0.012), (x, yf - 0.0018, z + rh / 2 - 0.012), M('img_labels'), rot=(90, 0, 0))
            u0, v0 = (i % 4) / 4, 1 - (i // 4 + 1) / 6
            set_uv(lb, u0, v0, u0 + 0.25, v0 + 1 / 6)
            depth = 0.12
            if out > 0.02:
                for sx in (-1, 1):
                    P.box('dside', (0.002, depth, rh - 0.006), (x + sx * (cw / 2 - 0.003), yf + depth / 2, z - 0.001), M('drawer'), bevel=0)
                P.box('dbottom', (cw - 0.004, depth, 0.002), (x, yf + depth / 2, z - rh / 2 + 0.003), M('drawer'), bevel=0)
            ct = content[rnd.randrange(len(content))]
            for k in range(3 if out > 0.02 else 1):
                P.box('stuff', (cw * rnd.uniform(0.35, 0.75), 0.04, rh * rnd.uniform(0.2, 0.45)),
                      (x + rnd.uniform(-0.01, 0.01), yf + 0.03 + k * 0.03, z - rh / 2 + 0.008 + 0.004), M(ct), bevel=0.001,
                      rot=(0, 0, rnd.uniform(-15, 15)))
    return P


def _toolcup(col):
    """Metal can full of screwdrivers, pliers, a scalpel."""
    P = kit5.Prop('ws_toolcup', col)
    lathe(P, 'can', [(0, 0.0), (0.038, 0.0), (0.039, 0.003), (0.039, 0.108), (0.0405, 0.11), (0.0375, 0.11),
                     (0.0375, 0.006), (0, 0.006)], (0, 0, 0), M('steel_bare'), segs=32)
    rnd = random.Random(8)
    tools = [('grip_red', 0.010, 0.085), ('grip_yellow', 0.009, 0.08), ('grip_blue', 0.011, 0.09), ('knob', 0.008, 0.075),
             ('grip_red', 0.007, 0.07)]
    for k, (gm, r, L) in enumerate(tools):
        a = 2 * math.pi * k / len(tools) + 0.3
        bot = Vector((math.cos(a) * 0.012, math.sin(a) * 0.012, 0.008))
        d = Vector((math.cos(a) * 0.22, math.sin(a) * 0.22, 1.0)).normalized()
        sh = bot + d * 0.095
        rod(P, 'shaft', bot, sh, 0.0025, M('chrome'), verts=10)
        lathe(P, 'handle', [(0, 0), (r * 0.7, 0), (r, 0.012), (r, L - 0.01), (r * 0.8, L), (0, L)], tuple(sh), M(gm),
              rot_to(d), segs=12)
    # pliers: two handles splayed, joint above the rim
    j = Vector((-0.01, 0.0, 0.155))
    for s in (-1, 1):
        lo = Vector((s * 0.022, 0.012, 0.03))
        rod(P, 'plier_leg', lo, j, 0.0045, M('grip_red'), verts=12)
        rod(P, 'plier_jaw', j, j + Vector((s * 0.004, -0.004, 0.035)), 0.003, M('steel_bare'), verts=10, r2=0.0015)
    P.cyl('plier_pivot', 0.006, 0.008, tuple(j), M('steel_bare'), rot=(90, 0, 0), verts=16)
    rod(P, 'scalpel', (0.015, -0.02, 0.01), (0.02, -0.03, 0.15), 0.003, M('scalpel'), verts=10)
    return P


def _box_cardboard(P, name, size, loc, heading=0.0, open_flaps=False):
    w, d, h = size
    P.box(name, size, loc, M('cardboard'), rot=(0, 0, heading), bevel=0.003)
    P.box(name + '_tape', (w * 1.002, 0.05, h * 1.002), loc, M('tape'), rot=(0, 0, heading), bevel=0.0015)
    P.plane(name + '_label', (0.10, 0.07), (loc[0] - w * 0.2, loc[1] - d / 2 - 0.0012, loc[2]), M('label_paper'),
            rot=(90, 0, heading))


def _hang_drawer(P, x, w=0.50):
    """Steel drawer hanging under the top (runners on the apron)."""
    zt = TOP - TH
    P.box('hd_body', (w, 0.66, 0.10), (x, -0.03, zt - 0.06), M('steel_black'), bevel=0.003)
    P.box('hd_front', (w + 0.02, 0.018, 0.115), (x, -0.369, zt - 0.062), M('drawer_front'), bevel=0.004, segments=3)
    rod(P, 'hd_handle', (x - 0.09, -0.392, zt - 0.05), (x + 0.09, -0.392, zt - 0.05), 0.0055, M('steel_bare'), verts=12)
    for s in (-1, 1):
        P.box('hd_hpost', (0.012, 0.022, 0.012), (x + s * 0.09, -0.384, zt - 0.05), M('steel_bare'), bevel=0.002)
    P.plane('hd_label', (0.07, 0.025), (x, -0.3785, zt - 0.025), M('img_labels'), rot=(90, 0, 0))
    set_uv(P.parts[[k for k in P.parts if k.startswith('hd_label')][-1]], 0.25, 0.0, 0.5, 1 / 6)


# ------------------------------------------------------------------ the bench
def build_bench(collection=None, lamp_head=(0.47, -0.06, 1.25), lamp_target=BOARD, lamp_energy=70.0):
    """The whole workstation as one prop (bench-local coords; front edge y = -0.40, top at 0.78)."""
    wtex.make_all()
    P = kit5.Prop('workbench', collection)
    Lx, Dy = 2.90, 0.80
    # ---- frame: 50 mm black square tube legs, 40 mm apron, side + back lower rails, levelling feet
    fx, fy = 1.37, 0.33
    zt = TOP - TH
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * fx, sy * fy
            P.box('leg', (0.05, 0.05, zt - 0.03), (x, y, 0.03 + (zt - 0.03) / 2), 'steel_black', bevel=0.004)
            P.box('leg_plate', (0.064, 0.064, 0.006), (x, y, 0.033), 'steel_black', bevel=0.0015)
            P.cyl('foot_bolt', 0.008, 0.026, (x, y, 0.017), 'steel_bare', verts=12)
            P.cyl('foot_nut', 0.011, 0.006, (x, y, 0.024), 'steel_bare', verts=6, bevel=0.0008)
            P.cyl('foot_pad', 0.024, 0.008, (x, y, 0.004), 'rubber_black', verts=24, bevel=0.002)
            P.box('leg_cap', (0.048, 0.048, 0.003), (x, y, zt - 0.0015), 'rubber_black', bevel=0.0008)
    for sy in (-1, 1):
        P.box('apron', (2 * fx - 0.05, 0.04, 0.04), (0, sy * fy, zt - 0.02), 'steel_black', bevel=0.003)
    for sx in (-1, 1):
        P.box('apron_side', (0.04, 2 * fy - 0.05, 0.04), (sx * fx, 0, zt - 0.02), 'steel_black', bevel=0.003)
        P.box('rail_side', (0.04, 2 * fy - 0.05, 0.04), (sx * fx, 0, 0.17), 'steel_black', bevel=0.003)
    P.box('rail_back', (2 * fx - 0.05, 0.04, 0.04), (0, fy, 0.17), 'steel_black', bevel=0.003)
    P.box('rail_front', (2 * fx - 0.05, 0.03, 0.03), (0, -0.08, 0.175), 'steel_black', bevel=0.003)
    P.box('rail_mid', (0.03, 0.40, 0.03), (0.0, 0.13, 0.175), 'steel_black', bevel=0.003)
    P.box('shelf', (2 * fx - 0.05, 0.44, 0.018), (0, 0.125, 0.199), M('plywood'), bevel=0.002)
    # ---- butcher-block top
    P.box('top', (Lx, Dy, TH), (0, 0, TOP - TH / 2), M('butcher'), bevel=0.006, segments=3)
    _hang_drawer(P, -1.05)
    # ---- ESD mat + ground snap & cord
    P.box('esd_mat', (0.60, 0.50, 0.0025), (0.0, -0.13, TOP + 0.00125), M('esd'), bevel=0.0012, segments=2)
    P.cyl('esd_snap', 0.0065, 0.004, (0.27, 0.09, TOP + 0.004), 'chrome', verts=16, bevel=0.001)
    cable(P, 'esd_cord', [(0.27, 0.09, TOP + 0.006), (0.29, 0.13, TOP + 0.004), (0.24, 0.22, TOP + 0.003),
                          (0.18, 0.33, TOP + 0.003), (0.16, 0.395, TOP + 0.0), (0.155, 0.41, TOP - 0.03),
                          (0.16, 0.36, zt - 0.03)], 0.0018, M('cable_grey'))
    placed = {}

    def put(child, name, loc, heading):
        P.add(child, loc, heading)
        placed[name] = (loc, heading)
        return child

    def at(name, p):
        loc, h = placed[name]
        return xf(loc, h, p)

    col = P.col
    # ---- left: organiser, PSU + scope stack, monitor
    put(_organiser(col), 'org', (-1.27, 0.22, TOP), 4)
    psu = put(_psu(col), 'psu', (-0.93, 0.21, TOP), 7)
    sc = put(_scope(col), 'scope', (-0.93 + 0.0, 0.19, TOP + 0.126), 9)
    mon = put(_monitor(col), 'mon', (-0.50, 0.21, TOP), 26)
    # ---- centre: helping hands with the board, tools, components
    hands = put(_hands(col), 'hands', (BOARD[0], BOARD[1] + 0.125, TOP), 0)
    put(_toolcup(col), 'cup', (-0.20, 0.30, TOP), 0)
    # ---- right: station, stand, spool, lamp, mug, meter, notebook, strip
    st = put(_station(col), 'station', (0.53, 0.15, TOP), -12)
    stand = put(_stand(col), 'stand', (0.40, -0.15, TOP), -25)
    put(_spool(col), 'spool', (0.71, 0.19, TOP), -20)
    lamp_loc = (0.85, 0.36, TOP)
    lh = Vector(lamp_head) - Vector(lamp_loc)
    lt = Vector(lamp_target) - Vector(lamp_loc)
    lamp = put(_lamp(col, lh, lt, lamp_energy), 'lamp', lamp_loc, 0)
    mug = put(_mug(col), 'mug', (0.66, -0.27, TOP), -35)
    meter = put(_meter(col), 'meter', (0.97, -0.02, TOP), 14)
    put(_notebook(col), 'notebook', (1.17, -0.19, TOP), -7)
    strip = put(_strip(col), 'strip', (1.12, 0.335, TOP), 0)
    # ---- far right back: two books + a small parts box
    P.box('book1', (0.17, 0.24, 0.03), (1.30, 0.20, TOP + 0.015), M('cover_red'), rot=(0, 0, 84), bevel=0.002)
    P.box('book1_pages', (0.163, 0.233, 0.026), (1.302, 0.199, TOP + 0.015), M('pages'), rot=(0, 0, 84), bevel=0.001)
    P.box('book2', (0.15, 0.21, 0.024), (1.305, 0.205, TOP + 0.042), M('cover_grey'), rot=(0, 0, 79), bevel=0.002)
    P.box('book2_pages', (0.144, 0.204, 0.02), (1.307, 0.204, TOP + 0.042), M('pages'), rot=(0, 0, 79), bevel=0.001)
    _box_cardboard(P, 'pbox', (0.12, 0.09, 0.05), (1.29, 0.19, TOP + 0.054 + 0.025), 88)
    # ---- cables ---------------------------------------------------------------------------------------------
    # station power: strip plug 0 -> back of the station
    plugs = [(xf(placed['strip'][0], 0, p), c) for p, c in strip.plugs]
    bp = at('station', st.parts['back_pt'].location)
    p0 = plugs[0][0]
    cable(P, 'pw_station', [p0, p0 + Vector((0, 0.03, -0.01)), (p0.x - 0.06, 0.385, TOP + 0.005), (bp.x + 0.12, 0.33, TOP + 0.004),
                            (bp.x + 0.04, bp.y + 0.03, TOP + 0.006), bp], 0.0028, M('cable_black'))
    # lamp: strip plug 1 -> over the back edge -> up to the clamp cable end
    p1 = plugs[1][0]
    le = at('lamp', lamp.parts['cable_end'].location)
    cable(P, 'pw_lamp', [p1, p1 + Vector((0, 0.03, -0.012)), (p1.x - 0.01, 0.405, TOP - 0.005), (p1.x - 0.05, 0.425, TOP - 0.16),
                         (le.x + 0.06, 0.43, TOP - 0.20), le], 0.0022, M('cable_black'))
    # USB charger plug 3 -> thin white cable wandering to the notebook
    p3 = plugs[2][0]
    cable(P, 'usb', [p3, p3 + Vector((0.0, 0.02, 0.02)), (p3.x + 0.03, 0.3, TOP + 0.004), (1.2, 0.16, TOP + 0.003),
                     (1.10, 0.06, TOP + 0.003), (1.18, 0.0, TOP + 0.003), (1.26, 0.02, TOP + 0.003)], 0.0016, M('cable_white'))
    P.box('usb_plug', (0.012, 0.024, 0.006), (1.275, 0.03, TOP + 0.003), M('cable_white'), rot=(0, 0, -60), bevel=0.0015)
    # strip cord: over the back edge, down to the floor
    cs = xf(placed['strip'][0], 0, strip.cord_start)
    cable(P, 'strip_cord', [cs, cs + Vector((0.03, 0, 0)), (cs.x + 0.05, 0.41, TOP - 0.01), (cs.x + 0.06, 0.43, TOP - 0.3),
                            (cs.x + 0.05, 0.43, 0.2), (cs.x - 0.1, 0.42, 0.012), (cs.x - 0.5, 0.40, 0.006)], 0.0035, M('cable_white'))
    # monitor: power + video down behind the bench
    mo = at('mon', mon.parts['cable_out'].location)
    for k, (dx, r) in enumerate(((0.0, 0.0032), (0.025, 0.0028))):
        cable(P, f'mon_cable{k}', [mo + Vector((dx, 0, 0)), mo + Vector((dx + 0.01, 0.06, -0.05)), (mo.x + dx + 0.04, 0.33, TOP + 0.004),
                                   (mo.x + dx + 0.05, 0.395, TOP + 0.0), (mo.x + dx + 0.05, 0.425, TOP - 0.06),
                                   (mo.x + dx + 0.03, 0.43, 0.30), (mo.x + dx - 0.05, 0.42, 0.01)], r, M('cable_black'))
    # scope + PSU power down the back
    for name, p in (('scope', Vector((-0.07, 0.125, 0.048))), ('psu', Vector((0.06, 0.13, 0.04)))):
        a = at(name, p)
        cable(P, f'pw_{name}', [a, a + Vector((0, 0.04, -0.01)), (a.x + 0.02, 0.40, TOP + 0.001 if name == 'psu' else TOP + 0.05),
                                (a.x + 0.03, 0.425, TOP - 0.08), (a.x + 0.0, 0.43, 0.25), (a.x - 0.08, 0.42, 0.01)],
              0.003, M('cable_black'))
    # scope probe: CH1 BNC -> drapes down the PSU front -> across the bench -> probe hooked near the board
    ch1 = at('scope', sc.parts['ch1'].location)
    ptip = Vector((BOARD[0] - 0.06, BOARD[1] - 0.07, TOP + 0.004))
    pd = Vector((0.6, 0.5, 0.0)).normalized()
    pend = _probe(P, 'probe', ptip, pd, 'cable_grey')
    cable(P, 'probe_cable', [ch1, ch1 + Vector((0.0, -0.04, -0.02)), (ch1.x + 0.03, ch1.y - 0.07, TOP + 0.06),
                             (ch1.x + 0.08, ch1.y - 0.12, TOP + 0.004), (-0.55, -0.12, TOP + 0.003), (-0.40, -0.25, TOP + 0.004),
                             (-0.30, -0.27, TOP + 0.005), pend - pd * 0.03 + Vector((0, 0, 0.001)), pend], 0.0021, M('cable_grey'))
    cable(P, 'probe_gnd', [ptip - pd * 0.09 + Vector((0, 0, 0.005)), ptip - pd * 0.09 + Vector((-0.02, -0.03, -0.001)),
                           ptip + Vector((-0.04, -0.03, 0.0))], 0.0009, M('cable_black'))
    P.box('probe_gclip', (0.012, 0.005, 0.004), tuple(ptip + Vector((-0.045, -0.032, 0.0))), M('base_black'), bevel=0.001)
    # PSU leads (red / black) -> crocodile clips on the board's screw terminal
    yfp = -0.13 - 0.003
    j1 = Vector(BOARD) + Vector((0.042, 0.0, 0.0))
    for k, (z, colr) in enumerate(((0.081, 'cable_red'), (0.056, 'cable_black'))):
        a = at('psu', Vector((0.105, yfp - 0.02, z)))
        end = j1 + Vector((0.006 + 0.004 * k, -0.012 - 0.006 * k, -0.035 + 0.003 * k))
        cable(P, f'lead{k}', [a, a + Vector((0.004, -0.03, -0.01)), (a.x + 0.05, a.y - 0.09, TOP + 0.004),
                              (-0.45 + 0.02 * k, -0.02 - 0.015 * k, TOP + 0.004), (-0.18, 0.02 - 0.01 * k, TOP + 0.006),
                              (0.05 + 0.02 * k, 0.03, TOP + 0.006), (j1.x + 0.03, j1.y + 0.04, TOP + 0.02), end], 0.0022, M(colr))
        P.box(f'croc{k}', (0.004, 0.022, 0.005), tuple(end + Vector((0, 0.006, 0.006))), M('grip_red' if k == 0 else 'base_black'),
              rot=(35, 0, 10), bevel=0.0012)
    # multimeter probes
    for k, (jack, colr, tip, dd) in enumerate(((meter.jacks[2], 'cable_black', Vector((0.82, -0.32, TOP + 0.0045)), (-0.2, 1.0, 0)),
                                                (meter.jacks[3], 'cable_red', Vector((0.90, -0.355, TOP + 0.0045)), (-0.35, 1.0, 0)))):
        a = at('meter', jack)
        dd = Vector(dd).normalized()
        pe = _probe(P, f'mprobe{k}', tip, -dd, 'grip_red' if k else 'base_black')
        cable(P, f'mlead{k}', [a, a + Vector((0, 0, 0.015)), a + Vector((0.01 + 0.01 * k, -0.04, 0.0)),
                               (1.02 + 0.04 * k, -0.20, TOP + 0.003), (1.03 + 0.02 * k, -0.33, TOP + 0.004),
                               pe + dd * 0.06 + Vector((0, 0, -0.001)), pe], 0.0019, M(colr))
    # ---- loose things on the mat and around
    rnd = random.Random(31)
    # tweezers (two thin legs from a common heel)
    tw0, twd = Vector((-0.19, -0.27, TOP + 0.0045)), Vector((math.cos(0.5), math.sin(0.5), 0))
    side = Vector((-twd.y, twd.x, 0))
    for s in (-1, 1):
        bar(P, 'tweezer', tw0, tw0 + twd * 0.12 + side * s * 0.0045, 0.006, 0.0012, 'steel_bare', bevel=0.0004)
    for k in range(6):
        x, y = rnd.uniform(-0.25, -0.05), rnd.uniform(-0.33, -0.15)
        a = rnd.uniform(0, 180)
        d = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        if k < 3:   # resistors with long legs
            P.cyl('loose_res', 0.0012, 0.0065, (x, y, TOP + 0.0037), M('res_body'), rot=rot_to(d), verts=12, bevel=0.0003)
            for s in (-1, 1):
                rod(P, 'loose_leg', Vector((x, y, TOP + 0.0037)) + d * s * 0.003, Vector((x, y, TOP + 0.003)) + d * s * 0.03, 0.0003, M('pin'), verts=6)
        elif k < 5:  # LEDs on their side
            c = M('led_red' if k == 3 else 'led_grn')
            P.cyl('loose_led', 0.0025, 0.005, (x, y, TOP + 0.005), c, rot=rot_to(d), verts=16, bevel=0.0004)
            P.sphere('loose_led_dome', 0.0025, (x + d.x * 0.0025, y + d.y * 0.0025, TOP + 0.005), c, segments=12, rings=8)
            for s in (-1, 1):
                rod(P, 'loose_leg', Vector((x, y, TOP + 0.005)) - d * 0.0025 + Vector((-d.y, d.x, 0)) * s * 0.001,
                    Vector((x, y, TOP + 0.003)) - d * 0.028 + Vector((-d.y, d.x, 0)) * s * 0.002, 0.0003, M('pin'), verts=6)
        else:        # a DIP-8 chip
            P.box('loose_ic', (0.0098, 0.0064, 0.0034), (x, y, TOP + 0.0045), M('chip'), rot=(0, 0, a), bevel=0.0004)
    for k, c in enumerate(('wire_red', 'wire_blue', 'wire_yel', 'wire_red')):
        x, y = rnd.uniform(-0.22, 0.2), rnd.uniform(-0.36, -0.24)
        a = rnd.uniform(0, 6.28)
        p0 = Vector((x, y, TOP + 0.0035))
        d = Vector((math.cos(a), math.sin(a), 0))
        cable(P, 'snip', [p0, p0 + d * 0.012 + Vector((-d.y, d.x, 0)) * 0.003, p0 + d * 0.024], 0.0008, M(c), res=4)
    # anti-static bag with a part in it, foam pad with chips
    bag = grid(P, 'esd_bag', 0.10, 0.14, 6, 6, lambda u, v: 0.002 + 0.0035 * math.sin(math.pi * u) * math.sin(math.pi * v) ** 0.5,
               (-0.36, 0.02, TOP + 0.0006), M('esd_bag'), rot=(0, 0, 18))
    P.box('foam', (0.08, 0.05, 0.008), (-0.20, 0.03, TOP + 0.0065), M('foam_black'), rot=(0, 0, -8), bevel=0.0015)
    for k in range(3):
        P.box('foam_ic', (0.0196, 0.0064, 0.0034), (-0.225 + k * 0.022, 0.03, TOP + 0.0115), M('chip'), rot=(0, 0, 82), bevel=0.0004)
    # solder sucker lying on the left of the mat
    sd = Vector((math.cos(math.radians(-20)), math.sin(math.radians(-20)), 0))
    s0 = Vector((-0.39, -0.24, TOP + 0.0125))
    lathe(P, 'sucker', [(0, 0), (0.0035, 0.0), (0.009, 0.03), (0.0105, 0.035), (0.0105, 0.16), (0.0115, 0.162), (0.0115, 0.17),
                        (0.0, 0.17)], tuple(s0), M('aluminium'), rot_to(sd), segs=20)
    rod(P, 'sucker_plunger', s0 + sd * 0.17, s0 + sd * 0.215, 0.004, M('base_black'), verts=12)
    P.cyl('sucker_knob', 0.008, 0.008, tuple(s0 + sd * 0.219), M('base_black'), rot=rot_to(sd), verts=16)
    # flux pen next to the stand
    rod(P, 'flux_pen', (0.26, -0.33, TOP + 0.0065), (0.39, -0.37, TOP + 0.0065), 0.0065, M('cable_white'), verts=16)
    rod(P, 'flux_cap', (0.39, -0.37, TOP + 0.0065), (0.42, -0.379, TOP + 0.0065), 0.0068, M('grip_red'), verts=16)
    # ---- lower shelf: a crate of parts, cardboard boxes, a red toolbox, a cable reel
    shz = 0.208
    P.box('crate', (0.44, 0.32, 0.17), (-0.95, 0.15, shz + 0.085), M('crate'), rot=(0, 0, 3), bevel=0.008, segments=3)
    P.box('crate_in', (0.40, 0.28, 0.02), (-0.95, 0.15, shz + 0.16), M('chip'), rot=(0, 0, 3), bevel=0.0)
    for k in range(5):
        P.box('crate_stuff', (rnd.uniform(0.05, 0.12), rnd.uniform(0.05, 0.1), 0.04),
              (-1.08 + k * 0.06, 0.12 + rnd.uniform(-0.05, 0.05), shz + 0.17 + 0.01), M(rnd.choice(['cardboard', 'esd_bag', 'pcb_green', 'cable_grey'])),
              rot=(rnd.uniform(-8, 8), rnd.uniform(-8, 8), rnd.uniform(0, 90)), bevel=0.002)
    _box_cardboard(P, 'cbox', (0.38, 0.30, 0.22), (-0.42, 0.18, shz + 0.11), -4)
    _box_cardboard(P, 'cbox2', (0.24, 0.20, 0.12), (-0.40, 0.17, shz + 0.22 + 0.06), 9)
    P.box('toolbox', (0.40, 0.20, 0.17), (0.62, 0.20, shz + 0.085), M('toolbox'), rot=(0, 0, -2), bevel=0.006, segments=3)
    P.box('toolbox_lid', (0.405, 0.205, 0.012), (0.62, 0.20, shz + 0.165), M('toolbox'), rot=(0, 0, -2), bevel=0.004)
    rod(P, 'toolbox_handle', (0.53, 0.197, shz + 0.19), (0.71, 0.194, shz + 0.19), 0.008, M('base_black'), verts=12)
    for s in (-1, 1):
        rod(P, 'toolbox_hpost', (0.62 + s * 0.09, 0.197, shz + 0.171), (0.62 + s * 0.09, 0.197, shz + 0.19), 0.004, M('steel_bare'), verts=10)
        P.box('toolbox_latch', (0.03, 0.006, 0.03), (0.62 + s * 0.12, 0.097, shz + 0.15), M('steel_bare'), bevel=0.002)
    P.cyl('reel', 0.09, 0.07, (1.08, 0.16, shz + 0.09), M('cable_red'), rot=(90, 0, 0), verts=32, bevel=0.003)
    for s in (-1, 1):
        P.cyl('reel_flange', 0.11, 0.006, (1.08, 0.16 + s * 0.038, shz + 0.11), M('base_black'), rot=(90, 0, 0), verts=32, bevel=0.002)
    P.cyl('reel_hub', 0.02, 0.09, (1.08, 0.16, shz + 0.11), M('cardboard'), rot=(90, 0, 0), verts=20)
    # ---- exposed parts for the assembler / animator
    P.parts['iron_rest'] = stand.parts['iron_rest']
    P.parts['iron_socket'] = st.parts['socket_pt']
    P.parts['board'] = hands.parts['board']
    P.parts['lamp_light'] = lamp.spot
    P.parts['lamp_bulb'] = lamp.bulb
    P.parts['monitor_glow'] = mon.parts['glow']
    P.parts['monitor_screen'] = mon.screen
    P.parts['scope_screen'] = sc.screen
    P.parts['mug'] = mug.root
    P.subs = {k: v for k, v in placed.items()}
    return P


# ------------------------------------------------------------------ stool
def build_stool(collection=None):
    """Swivel workshop stool: 5-star nylon base with twin-wheel casters, gas lift, chrome foot ring, round padded
    seat (top at SEAT = 0.52).  The seat assembly is parented to the empty parts['pivot'] (column axis, z = 0.43):
    rotate pivot.rotation_euler.z to swivel the seat (parent the seated character to it as well)."""
    P = kit5.Prop('stool', collection)
    zh = 0.115
    lathe(P, 'hub', [(0, 0.085), (0.042, 0.085), (0.048, 0.095), (0.046, 0.135), (0.032, 0.145), (0, 0.145)], (0, 0, 0),
          M('base_black'), segs=32)
    for k in range(5):
        a = math.radians(90 + k * 72)
        d = Vector((math.cos(a), math.sin(a), 0))
        tip = d * 0.30 + Vector((0, 0, 0.078))
        taper_bar(P, 'leg', d * 0.03 + Vector((0, 0, zh)), tip, 0.05, 0.045, 0.034, 0.022, M('base_black'), bevel=0.006)
        P.cyl('leg_end', 0.017, 0.022, tuple(tip + Vector((0, 0, -0.002))), M('base_black'), verts=20, bevel=0.003)
        # twin-wheel caster under the tip
        P.cyl('stem', 0.0055, 0.018, tuple(tip + Vector((0, 0, -0.019))), M('steel_bare'), verts=12)
        cc = tip + Vector((0, 0, -0.046)) + d * 0.012
        rt = (0, 90, math.degrees(a))
        P.box('caster_hood', (0.030, 0.042, 0.028), tuple(cc + Vector((0, 0, 0.01))), M('base_black'),
              rot=(0, 0, math.degrees(a) + 90), bevel=0.008, segments=3)
        sd = Vector((-d.y, d.x, 0))
        for s in (-1, 1):
            wc = cc + sd * s * 0.019 + d * 0.006 + Vector((0, 0, -0.008))
            wc.z = 0.025
            P.cyl('wheel', 0.025, 0.013, tuple(wc), M('wheel'), rot=rot_to(sd), verts=24, bevel=0.004)
            P.cyl('wheel_cap', 0.012, 0.0145, tuple(wc), M('steel_bare'), rot=rot_to(sd), verts=16, bevel=0.001)
    # gas lift: black outer tube, ring, chrome piston
    P.cyl('lift', 0.0265, 0.20, (0, 0, 0.145 + 0.10), M('base_black'), verts=28, bevel=0.002)
    P.cyl('lift_ring', 0.03, 0.012, (0, 0, 0.345), M('base_black'), verts=28, bevel=0.002)
    P.cyl('piston', 0.0145, 0.09, (0, 0, 0.385), M('chrome'), verts=24, bevel=0.001)
    # foot ring
    zr = 0.27
    P.torus('foot_ring', 0.205, 0.0105, (0, 0, zr), M('chrome'))
    lathe(P, 'ring_collar', [(0, -0.018), (0.035, -0.018), (0.038, -0.012), (0.038, 0.012), (0.035, 0.018), (0, 0.018)],
          (0, 0, zr), M('base_black'), segs=28)
    for k in range(3):
        a = math.radians(30 + k * 120)
        d = Vector((math.cos(a), math.sin(a), 0))
        rod(P, 'ring_spoke', d * 0.036 + Vector((0, 0, zr)), d * 0.198 + Vector((0, 0, zr)), 0.0075, M('chrome'), verts=16)
    # seat on the pivot
    pv = empty(P, 'pivot', (0, 0, 0.43), size=0.08)
    P.box('mech', (0.17, 0.17, 0.02), (0, 0, 0.012), 'steel_black', bevel=0.004, parent=pv)
    P.cyl('mech_cone', 0.03, 0.02, (0, 0, -0.003), 'steel_black', verts=20, parent=pv)
    rod(P, 'lever', (0.07, -0.02, 0.006), (0.215, -0.06, -0.006), 0.004, M('chrome'), verts=12, parent=pv)
    P.box('lever_paddle', (0.04, 0.018, 0.01), (0.225, -0.064, -0.008), M('base_black'), rot=(0, 0, -15), bevel=0.004, parent=pv)
    lathe(P, 'shell', [(0, 0.02), (0.15, 0.02), (0.178, 0.026), (0.186, 0.036), (0.0, 0.036)], (0, 0, 0), M('base_black'),
          segs=48, parent=pv)
    top = SEAT - 0.43
    cush = [(0, 0.034), (0.178, 0.034), (0.188, 0.042), (0.193, 0.058), (0.192, top - 0.016), (0.184, top - 0.005),
            (0.165, top - 0.0005), (0.09, top), (0, top + 0.0015)]
    lathe(P, 'cushion', cush, (0, 0, 0), M('seat'), segs=48, parent=pv)
    P.torus('piping', 0.1905, 0.0028, (0, 0, top - 0.011), M('seat'), parent=pv)
    for k in range(8):
        a = math.radians(22.5 + k * 45)
        P.cyl('screw', 0.004, 0.003, (math.cos(a) * 0.06, math.sin(a) * 0.06, 0.0205), M('steel_bare'), verts=8, bevel=0, parent=pv)
    P.parts['pivot'] = pv
    return P


# ------------------------------------------------------------------ soldering iron
def build_iron(collection=None):
    """Soldering iron.  Origin = the point held between index and thumb (4 cm behind the front of the grip); local +Y
    points toward the tip.  Tip end at y = +0.136, rear (cable) at y = -0.140; parts['cable_end'] is there (the cable
    leaves along -Y), parts['tip'] at the tip end."""
    P = kit5.Prop('iron', collection)
    R = (-90, 0, 0)          # lathe Z -> prop +Y
    relief = [(0, -0.142), (0.0034, -0.142)]
    for k in range(7):
        z = -0.140 + k * 0.004
        r = 0.0036 + k * 0.0004
        relief += [(r, z), (r + 0.0006, z + 0.002)]
    relief += [(0.0066, -0.112), (0, -0.112)]
    lathe(P, 'relief', relief, (0, 0, 0), M('rubber_black'), R, segs=20)
    handle = [(0, -0.113), (0.0072, -0.113), (0.0082, -0.108), (0.0088, -0.07), (0.0084, -0.066), (0.0088, -0.062),
              (0.0094, -0.035), (0.009, -0.031), (0.0096, -0.027), (0.0099, -0.021), (0, -0.021)]
    lathe(P, 'handle', handle, (0, 0, 0), M('iron_handle'), R, segs=24)
    grip = [(0, -0.022), (0.0103, -0.022), (0.0108, -0.015), (0.0112, 0.0), (0.0108, 0.022), (0.0102, 0.034),
            (0.0094, 0.0365), (0, 0.0365)]
    lathe(P, 'grip', grip, (0, 0, 0), M('iron_grip'), R, segs=24)
    guard = [(0, 0.035), (0.0098, 0.035), (0.0128, 0.039), (0.0128, 0.0415), (0.0095, 0.044), (0.0072, 0.046), (0, 0.046)]
    lathe(P, 'guard', guard, (0, 0, 0), M('base_black'), R, segs=24)
    lathe(P, 'nut', [(0, 0.0455), (0.0068, 0.0455), (0.007, 0.048), (0.007, 0.056), (0.0058, 0.058), (0, 0.058)], (0, 0, 0),
          M('chrome'), R, segs=12)
    lathe(P, 'sleeve', [(0, 0.0575), (0.0038, 0.0575), (0.0036, 0.06), (0.0035, 0.111), (0.0028, 0.113), (0, 0.113)],
          (0, 0, 0), M('sleeve'), R, segs=16)
    lathe(P, 'tip', [(0, 0.112), (0.0024, 0.112), (0.0022, 0.121), (0.0013, 0.1295), (0, 0.1296)], (0, 0, 0),
          M('iron_tip'), R, segs=16)
    lathe(P, 'tip_tin', [(0, 0.1293), (0.00135, 0.1293), (0.0006, 0.1352), (0.0003, 0.136), (0, 0.1361)], (0, 0, 0),
          M('chrome'), R, segs=12)
    empty(P, 'cable_end', (0, -0.142, 0), size=0.01)
    empty(P, 'tip', (0, 0.136, 0), size=0.01)
    return P


def build_iron_cable(points, follow=None, radius=0.0021, collection=None, mat='cable_grey'):
    """The iron's silicone cable as a smooth tube through `points` (coordinates of the space the returned prop's root
    lives in: parent it like the bench, e.g. place it with the bench).  If `follow` (e.g. iron.parts['cable_end']) is
    given, the LAST point and its handles are hooked to it, so the end of the cable follows the iron when it moves."""
    P = kit5.Prop('iron_cable', collection)
    ob = cable(P, 'cable', [tuple(p) for p in points], radius, M(mat), res=10)
    if follow is not None:
        bpy.context.view_layer.update()
        n = len(points) - 1
        h = ob.modifiers.new('follow', 'HOOK')
        h.object = follow
        h.vertex_indices_set([3 * n, 3 * n + 1, 3 * n + 2])
        h.matrix_inverse = follow.matrix_world.inverted() @ ob.matrix_world
        if n >= 1:
            h2 = ob.modifiers.new('follow_soft', 'HOOK')
            h2.object = follow
            h2.vertex_indices_set([3 * (n - 1), 3 * (n - 1) + 1, 3 * (n - 1) + 2])
            h2.matrix_inverse = follow.matrix_world.inverted() @ ob.matrix_world
            h2.strength = 0.45
    return P


def rest_iron(bench, iron):
    """Put the iron in its stand: parent iron.root to bench.parts['iron_rest'] (identity offset)."""
    iron.root.parent = bench.parts['iron_rest']
    iron.root.matrix_parent_inverse.identity()
    iron.root.location = (0, 0, 0)
    iron.root.rotation_euler = (0, 0, 0)
    return iron


def iron_cable_points(bench, iron):
    """A plausible cable path (in BENCH-local coordinates) from the station socket, lying on the bench, looping in
    front of the stand, up to the rear of the iron wherever the iron currently is (uses world matrices)."""
    bpy.context.view_layer.update()
    inv = bench.root.matrix_world.inverted()
    s = inv @ bench.parts['iron_socket'].matrix_world.translation
    em = inv @ iron.parts['cable_end'].matrix_world
    e = em.translation
    back = (em.to_3x3() @ Vector((0, -1, 0))).normalized()     # direction the cable leaves the iron
    lie = TOP + 0.0022
    pts = [s, s + Vector((-0.005, -0.03, -0.004)), Vector((s.x - 0.01, s.y - 0.07, lie)), Vector((s.x + 0.04, -0.16, lie)),
           Vector((0.55, -0.31, lie)), Vector((0.42, -0.37, lie)), Vector((e.x - 0.01, min(e.y - 0.04, -0.33), lie + 0.002))]
    pts += [e + back * 0.07 + Vector((0, 0, -0.075)), e + back * 0.03, e]
    return pts


# ------------------------------------------------------------------ preview entry points (look5 preview uses build())
def build(collection=None):
    return build_bench(collection)


def build_all(collection=None):
    """bench + stool at Nox's mark + iron resting in its stand + cable, in BENCH-local coordinates."""
    B = build_bench(collection)
    S = build_stool(collection)
    kit5.place(S, (NOX_SEAT[0], NOX_SEAT[1], 0), 0)
    I = build_iron(collection)
    rest_iron(B, I)
    C = build_iron_cable(iron_cable_points(B, I), follow=I.parts['cable_end'], collection=collection)
    C.root.parent = B.root
    return B, S, I, C
