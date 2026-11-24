"""Version 5 set: the ROOM SHELL of Nox's loft, built in WORLD coordinates (see SPEC.md, 'The room').

    A = arch.build(collection=None, front_dressing=True, lamp_power=1.0)

    A['prop']        kit5.Prop 'arch' (all objects live in A['prop'].col, root empty at the world origin)
    A['door_hinge']  empty at (4.0, 1.70, 0.0): the door leaf, its handles and peephole are parented to it;
                     hinge.rotation_euler.z = -math.radians(angle) swings the free edge INTO the room
                     (90 deg -> the leaf lies along y = 1.70 from x = 4.0 to x = 3.05)
    A['lights']      [bench pendant L, bench pendant R, living pendant, corridor wall lamp]  (real Blender lights)
    A['pendants']    [dict(name, light, bulb=(x, y, z), rim_z, shade=obj)]  in the same order as the first 3 lights
    A['corridor_light']  the corridor wall lamp light
    A['bench_zone']  dict(x0, x1, y0, y1, top, sill_z, stool, board, iron_x, lamp_x)   (SPEC 'Zones and marks')
    A['window']      dict(x0, x1, sill, head, transoms, mullions, glass_y, vent=(x0, x1, z0, z1), glass=[objs])
    A['door']        dict(y0, y1, h, hinge, leaf=obj, open_95=-radians(95))
    A['corridor']    dict(x0, x1, y0, y1, h, lamp=(x, y, z))
    A['room']        dict(x0, x1, y0, y1, ceiling, beams_y, duct=(y, z, r))
    A['pico_lane']   dict(x0, x1, y0, y1)   (kept clear: nothing of the shell stands on the floor there)
    A['front']       dict(print=[objs], radiator=[objs])   (front_dressing=False omits them, e.g. when the living
                     module brings its own print and radiator)

Everything is real-scale and bevelled; materials are procedural (object coordinates = world metres because every shell
object sits at the origin), plus one PIL-generated print (lab/set5/tex/arch_print.png, made on first build).
"""
import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

import kit5
import mat5
from mat5 import _NT, lin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEX = os.path.join(ROOT, 'lab', 'set5', 'tex')

# ------------------------------------------------------------------ dimensions (SPEC.md)
X0, X1, Y0, Y1, CEIL = -5.0, 4.0, -4.0, 4.0, 3.4
WT = 0.22                                          # plaster/brick wall thickness
WIN_X0, WIN_X1, SILL, HEAD = -5.0, 2.0, 0.70, 3.15
TRANSOMS = (1.55, 2.35)
MULLIONS = (-4.0, -3.0, -2.0, -1.0, 0.0, 1.0)
FR_Y0, FR_Y1 = 4.02, 4.09                          # steel frame depth (glass at its middle)
GLASS_Y = 4.055
VENT = (-2.0, -1.0, 2.35, 3.15)                    # the top-hung opening vent (x0, x1, z0, z1)
DOOR_Y0, DOOR_Y1, DOOR_H = 0.75, 1.70, 2.10
HINGE = (4.0, 1.70, 0.0)
COR_X0, COR_X1, COR_Y0, COR_Y1, COR_H = 4.22, 6.5, -1.0, 3.4, 2.80
DADO = 1.05
BEAMS_Y = (-1.0, 2.0)
DUCT_Y, DUCT_Z, DUCT_R = 0.1, 3.15, 0.15
PENDANTS = [('bench_l', -4.0, 3.3, 2.10, 0.36, 55.0),
            ('bench_r', -2.6, 3.3, 2.10, 0.36, 55.0),
            ('living', 1.3, -1.4, 2.30, 0.44, 75.0)]     # name, x, y, bulb z, shade diameter, watts
CORRIDOR_LAMP = (6.40, 2.30, 2.02)
WARM = (1.0, 0.66, 0.40)                          # ~2700 K incandescent, linear
PRINT_PX = (2400, 1700)                           # generated print size (aspect drives the frame size)


# ------------------------------------------------------------------ small node helpers
def _math(T, op, a, b=None, clamp=False):
    n = T.nt.nodes.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            T.link(v, n.inputs[i])
    return n.outputs[0]


def _sep(T, vec):
    s = T.nt.nodes.new('ShaderNodeSeparateXYZ')
    T.link(vec, s.inputs[0])
    return s.outputs


def _comb(T, x, y, z=0.0):
    c = T.nt.nodes.new('ShaderNodeCombineXYZ')
    for i, v in enumerate((x, y, z)):
        if isinstance(v, (int, float)):
            c.inputs[i].default_value = v
        else:
            T.link(v, c.inputs[i])
    return c.outputs[0]


def _bw(T, col):
    n = T.nt.nodes.new('ShaderNodeRGBToBW')
    T.link(col, n.inputs[0])
    return n.outputs[0]


def _line_dist(T, coord, period, offset):
    """Distance (m) from coord to the nearest of the lines offset + k * period."""
    u = _math(T, 'DIVIDE', _math(T, 'SUBTRACT', coord, offset), period)
    f = _math(T, 'FRACT', _math(T, 'ADD', u, 0.5))
    return _math(T, 'MULTIPLY', _math(T, 'ABSOLUTE', _math(T, 'SUBTRACT', f, 0.5)), period)


def _scale(rgb, k):
    return tuple(min(255.0, x * k) for x in rgb)


def _cached(name, fn):
    m = bpy.data.materials.get(name)
    return m if m is not None else fn(name)


# ------------------------------------------------------------------ materials
def m_floor(name='arch_floor'):
    """Sealed, polished concrete slab: blotchy cloud tone, aggregate specks, a few dark stains (oil, coffee, a
    soldering-flux drip trail), saw-cut control joints every 3 m, soft lamp reflections."""
    T = _NT(name)
    v = T.coord(1.0, seed=2.0)
    big = T.noise(v, 0.45, 4.0, 0.55)
    mid = T.noise(v, 3.0, 6.0, 0.6)
    tone = _bw(T, T.mix(0.45, big.outputs['Color'], mid.outputs['Color']))
    col = T.ramp(tone, [(0.30, (58, 58, 57)), (0.50, (78, 77, 75)), (0.72, (96, 94, 91))])          # v5.1: darker (night)
    vor = T.nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 160.0
    T.link(v, vor.inputs['Vector'])
    speck = T.maprange(vor.outputs['Distance'], 0.02, 0.10, 0.35, 0.0)
    col = T.mix(speck, col, (150, 146, 140))
    s1 = T.noise(T.coord(1.0, seed=7.0), 0.55, 3.0, 0.55, distortion=0.9)
    s2 = T.noise(T.coord((1.0, 3.0, 1.0), seed=13.0), 1.6, 2.0, 0.5, distortion=1.4)
    m1 = T.maprange(s1.outputs['Fac'], 0.72, 0.76, 0.0, 0.6)
    m2 = T.maprange(s2.outputs['Fac'], 0.76, 0.79, 0.0, 0.45)
    stain = _math(T, 'MAXIMUM', m1, m2)
    col = T.mix(stain, col, (52, 48, 44))
    sp = _sep(T, v)
    j = _math(T, 'MINIMUM', _line_dist(T, sp[0], 3.0, 1.0 + 7.31 * 2.0), _line_dist(T, sp[1], 8.0 / 3.0, 4.0 / 3.0 + 3.17 * 2.0))
    joint = T.maprange(j, 0.0018, 0.0032, 1.0, 0.0)
    col = T.mix(joint, col, (34, 33, 31))
    rough = T.maprange(tone, 0.3, 0.7, 0.40, 0.24)
    rough = _math(T, 'ADD', rough, _math(T, 'MULTIPLY', stain, -0.08))
    rough = _math(T, 'MAXIMUM', rough, _math(T, 'MULTIPLY', joint, 0.85))
    pits = T.noise(v, 90.0, 2.0, 0.6)
    h = _math(T, 'SUBTRACT', T.maprange(pits.outputs['Fac'], 0.62, 0.70, 0.0, 0.4), joint)
    return T.set(base=col, rough=rough, normal=T.bump(h, 0.12, 0.002), spec=0.5)


def m_plaster(name, rgb, seed=0.0, grime=0.45):
    """Matte painted plaster: trowel unevenness, faint patches of retouched paint, grime and scuffs near the floor."""
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    n1 = T.noise(v, 0.9, 5.0, 0.6)
    n2 = T.noise(v, 6.0, 4.0, 0.6)
    tone = _bw(T, T.mix(0.5, n1.outputs['Color'], n2.outputs['Color']))
    col = T.ramp(tone, [(0.30, _scale(rgb, 0.93)), (0.70, _scale(rgb, 1.035))])
    patch = T.noise(T.coord(1.0, seed=seed + 3.0), 1.4, 2.0, 0.4)
    col = T.mix(T.maprange(patch.outputs['Fac'], 0.60, 0.70, 0.0, 0.25), col, _scale(rgb, 1.035))
    z = _sep(T, T.coord(1.0))[2]
    low = T.maprange(z, 0.04, 0.75, grime, 0.0)
    sc = T.noise(T.coord((4.0, 4.0, 1.0), seed=seed + 1.0), 3.0, 5.0, 0.7)
    dirt = _math(T, 'MULTIPLY', low, T.maprange(sc.outputs['Fac'], 0.42, 0.62, 0.15, 1.0))
    col = T.mix(dirt, col, _scale(rgb, 0.55))
    fine = T.noise(v, 260.0, 3.0, 0.5)
    trowel = T.noise(v, 2.2, 3.0, 0.5)
    hgt = _math(T, 'ADD', _math(T, 'MULTIPLY', fine.outputs['Fac'], 0.5), trowel.outputs['Fac'])
    return T.set(base=col, rough=T.maprange(tone, 0.3, 0.7, 0.86, 0.93), normal=T.bump(hgt, 0.05, 0.004), spec=0.38)


def m_brick(name, rgb=(124, 62, 46), mortar=(150, 144, 134), painted=None, seed=0.0, wear=0.5):
    """Old brick, optionally under an old coat of paint that has flaked off in patches (more near the floor and
    where things rubbed).  The brick relief (recessed mortar, uneven faces, chipped arrises) shows through the paint."""
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    raw = T.coord(1.0)
    sp = _sep(T, raw)
    uv = _comb(T, _math(T, 'ADD', sp[0], sp[1]), sp[2])
    b = T.nt.nodes.new('ShaderNodeTexBrick')
    b.offset = 0.5
    b.inputs['Scale'].default_value = 1.0
    b.inputs['Mortar Size'].default_value = 0.011
    b.inputs['Mortar Smooth'].default_value = 0.35
    b.inputs['Brick Width'].default_value = 0.23
    b.inputs['Row Height'].default_value = 0.0755
    b.inputs['Bias'].default_value = 0.0
    b.inputs['Color1'].default_value = tuple(lin(rgb)) + (1,)
    b.inputs['Color2'].default_value = tuple(lin(_scale(rgb, 0.74))) + (1,)
    b.inputs['Mortar'].default_value = tuple(lin(mortar)) + (1,)
    T.link(uv, b.inputs['Vector'])
    # per-brick variation and burnt spots
    spot = T.noise(v, 9.0, 5.0, 0.65)
    bcol = T.mix(T.maprange(spot.outputs['Fac'], 0.55, 0.72, 0.0, 0.45), b.outputs['Color'], (58, 34, 28), 'MULTIPLY')
    grime = T.noise(v, 2.5, 6.0, 0.65)
    bcol = T.mix(T.maprange(grime.outputs['Fac'], 0.35, 0.7, 0.0, 0.3), bcol, (44, 38, 34), 'MULTIPLY')
    mortar_m = b.outputs['Fac']                                   # 1 on mortar
    face = T.noise(v, 28.0, 4.0, 0.6)
    hgt = _math(T, 'SUBTRACT', _math(T, 'MULTIPLY', face.outputs['Fac'], 0.25), mortar_m)
    rough = 0.88
    col = bcol
    if painted:
        big = T.noise(T.coord(1.0, seed=seed + 5.0), 0.45, 3.0, 0.5, distortion=0.4)
        chips = T.noise(T.coord(1.0, seed=seed + 2.0), 11.0, 6.0, 0.7)
        edge = _math(T, 'ADD', big.outputs['Fac'], _math(T, 'MULTIPLY', chips.outputs['Fac'], 0.22))
        thr = 0.835 - 0.06 * wear / 0.5
        flake = T.maprange(edge, thr, thr + 0.006, 0.0, 1.0)
        tiny = T.noise(T.coord(1.0, seed=seed + 9.0), 26.0, 4.0, 0.6)
        reveal = _math(T, 'MAXIMUM', flake, T.maprange(tiny.outputs['Fac'], 0.775, 0.78, 0.0, 1.0))
        bcol = T.mix(0.45, bcol, (96, 84, 76))                  # old brick under paint: dusty, desaturated
        ptone = T.noise(v, 1.5, 3.0, 0.5)
        pcol = T.ramp(ptone.outputs['Fac'], [(0.3, _scale(painted, 0.93)), (0.7, painted)])
        pcol = T.mix(_math(T, 'MULTIPLY', mortar_m, 0.55), pcol, _scale(painted, 0.72))   # paint in the joints darkens
        pcol = T.mix(T.maprange(grime.outputs['Fac'], 0.4, 0.75, 0.0, 0.25), pcol, (120, 112, 100), 'MULTIPLY')
        z = sp[2]
        low = T.maprange(z, 0.0, 0.5, 0.35, 0.0)
        pcol = T.mix(_math(T, 'MULTIPLY', low, T.maprange(chips.outputs['Fac'], 0.4, 0.7, 0.3, 1.0)), pcol, (110, 104, 96), 'MULTIPLY')
        col = T.mix(reveal, pcol, bcol)
        hgt = _math(T, 'ADD', hgt, _math(T, 'MULTIPLY', reveal, -0.25))
        rough = T.maprange(reveal, 0.0, 1.0, 0.78, 0.9)
    return T.set(base=col, rough=rough, normal=T.bump(hgt, 0.55, 0.008), spec=0.35)


def m_ceiling(name='arch_ceiling'):
    """Board-formed concrete soffit: 12 cm formwork boards along X with their seams and tone changes, blotches,
    a couple of old water marks."""
    T = _NT(name)
    v = T.coord(1.0, seed=4.0)
    sp = _sep(T, T.coord(1.0))
    b = T.nt.nodes.new('ShaderNodeTexBrick')
    b.offset = 0.37
    b.inputs['Scale'].default_value = 1.0
    b.inputs['Mortar Size'].default_value = 0.0025
    b.inputs['Mortar Smooth'].default_value = 0.3
    b.inputs['Brick Width'].default_value = 2.4
    b.inputs['Row Height'].default_value = 0.12
    b.inputs['Bias'].default_value = 0.0
    b.inputs['Color1'].default_value = (1, 1, 1, 1)
    b.inputs['Color2'].default_value = (0.86, 0.86, 0.86, 1)
    b.inputs['Mortar'].default_value = (0.7, 0.7, 0.7, 1)
    T.link(_comb(T, sp[0], sp[1]), b.inputs['Vector'])
    big = T.noise(v, 0.7, 4.0, 0.6)
    mid = T.noise(T.coord((0.25, 1.0, 1.0), seed=4.0), 6.0, 5.0, 0.6)
    tone = _bw(T, T.mix(0.5, big.outputs['Color'], mid.outputs['Color']))
    col = T.ramp(tone, [(0.3, (66, 66, 65)), (0.7, (92, 91, 89))])
    col = T.mix(1.0, col, b.outputs['Color'], 'MULTIPLY')
    wm = T.noise(T.coord(1.0, seed=9.0), 0.8, 3.0, 0.5, distortion=1.2)
    col = T.mix(T.maprange(wm.outputs['Fac'], 0.80, 0.84, 0.0, 0.3), col, (60, 56, 50))
    pits = T.noise(v, 70.0, 2.0, 0.6)
    hgt = _math(T, 'SUBTRACT', T.maprange(pits.outputs['Fac'], 0.6, 0.7, 0.0, 0.5), b.outputs['Fac'])
    return T.set(base=col, rough=0.9, normal=T.bump(hgt, 0.2, 0.003), spec=0.35)


def m_galv(name='arch_galv'):
    """Galvanised spiral duct: zinc spangle crystals, seam ribs every 15 cm, grey dust on top."""
    T = _NT(name)
    v = T.coord(1.0, seed=1.0)
    vor = T.nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 26.0
    T.link(v, vor.inputs['Vector'])
    sp_ = _bw(T, vor.outputs['Color'])
    col = T.ramp(sp_, [(0.0, (128, 132, 136)), (1.0, (178, 181, 185))])
    sp = _sep(T, T.coord(1.0))
    dust = T.maprange(sp[2], DUCT_Z + 0.04, DUCT_Z + 0.14, 0.0, 0.55)
    col = T.mix(dust, col, (110, 106, 100))
    seam = T.maprange(_line_dist(T, sp[0], 0.15, 0.0), 0.0015, 0.004, 1.0, 0.0)
    smear = T.noise(v, 3.0, 4.0, 0.6)
    col = T.mix(T.maprange(smear.outputs['Fac'], 0.5, 0.75, 0.0, 0.35), col, (70, 70, 72))
    rough = _math(T, 'ADD', T.maprange(sp_, 0.0, 1.0, 0.26, 0.48), _math(T, 'MULTIPLY', dust, 0.4))
    T.set(base=col, metal=_math(T, 'SUBTRACT', 1.0, _math(T, 'MULTIPLY', dust, 0.7)), rough=rough,
          normal=T.bump(seam, 0.5, 0.002))
    return T.m


def m_paint_wood(name, rgb, rough=0.4, seed=0.0, wear=0.12):
    """Satin paint on wood (door, trim): brush drag along Z, worn spots showing primer/wood."""
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    n = T.noise(v, 4.0, 4.0, 0.6)
    col = T.ramp(n.outputs['Fac'], [(0.3, _scale(rgb, 0.94)), (0.7, _scale(rgb, 1.04))])
    ch = T.noise(v, 22.0, 6.0, 0.7)
    worn = T.maprange(ch.outputs['Fac'], 0.73 - wear * 0.3, 0.745 - wear * 0.3, 0.0, 1.0)
    col = T.mix(worn, col, (150, 120, 88))
    brush = T.noise(T.coord((30.0, 30.0, 1.0), seed=seed), 1.0, 3.0, 0.5)
    return T.set(base=col, rough=T.maprange(n.outputs['Fac'], 0.3, 0.7, rough - 0.05, rough + 0.06),
                 normal=T.bump(brush.outputs['Fac'], 0.06, 0.001), spec=0.5)


def m_boards(name='arch_boards'):
    """Old varnished floorboards (corridor): 13 cm boards along Y, staggered ends, tone per board, grain streaks."""
    T = _NT(name)
    sp = _sep(T, T.coord(1.0))
    b = T.nt.nodes.new('ShaderNodeTexBrick')
    b.offset = 0.41
    b.inputs['Scale'].default_value = 1.0
    b.inputs['Mortar Size'].default_value = 0.0022
    b.inputs['Mortar Smooth'].default_value = 0.2
    b.inputs['Brick Width'].default_value = 1.65
    b.inputs['Row Height'].default_value = 0.13
    b.inputs['Bias'].default_value = 0.0
    b.inputs['Color1'].default_value = tuple(lin((132, 86, 52))) + (1,)
    b.inputs['Color2'].default_value = tuple(lin((96, 60, 36))) + (1,)
    b.inputs['Mortar'].default_value = tuple(lin((30, 20, 14))) + (1,)
    T.link(_comb(T, sp[1], sp[0]), b.inputs['Vector'])
    streak = T.noise(T.coord((40.0, 0.8, 40.0), seed=6.0), 1.0, 6.0, 0.7)
    col = T.mix(T.maprange(streak.outputs['Fac'], 0.3, 0.7, 0.0, 0.45), b.outputs['Color'], (60, 36, 22), 'MULTIPLY')
    wear = T.noise(T.coord(1.0, seed=3.0), 1.2, 3.0, 0.5)
    col = T.mix(T.maprange(wear.outputs['Fac'], 0.45, 0.7, 0.0, 0.3), col, (150, 118, 86))
    T.set(base=col, rough=T.maprange(wear.outputs['Fac'], 0.4, 0.7, 0.32, 0.55),
          normal=T.bump(_math(T, 'SUBTRACT', streak.outputs['Fac'], _math(T, 'MULTIPLY', b.outputs['Fac'], 3.0)), 0.25, 0.002),
          spec=0.5, coat=0.3, coat_rough=0.3)
    return T.m


def m_coir(name='arch_coir'):
    T = _NT(name)
    v = T.coord((1.0, 1.0, 1.0), seed=2.0)
    f1 = T.noise(T.coord((260.0, 40.0, 40.0), seed=1.0), 1.0, 3.0, 0.7)
    f2 = T.noise(T.coord((40.0, 260.0, 40.0), seed=2.0), 1.0, 3.0, 0.7)
    fib = _math(T, 'MAXIMUM', f1.outputs['Fac'], f2.outputs['Fac'])
    dirt = T.noise(v, 4.0, 3.0, 0.5)
    col = T.ramp(fib, [(0.45, (78, 52, 30)), (0.75, (160, 116, 70))])
    col = T.mix(T.maprange(dirt.outputs['Fac'], 0.45, 0.7, 0.0, 0.5), col, (60, 50, 40), 'MULTIPLY')
    return T.set(base=col, rough=0.95, normal=T.bump(fib, 0.9, 0.004), spec=0.2, sheen=0.3)


def m_glass(name, tint=(1.0, 1.0, 1.0), dust=0.25, smudge=0.06, seed=0.0, refl=0.35):
    """THIN window glass: no refraction (Transparent BSDF, so the city lines up and light passes as through real
    float glass), Fresnel reflection (a faint mirror of the lamps at night), dust film and smudges.  Transparent rays
    keep their type, so the city (camera/glossy/transmission-visible only) is seen through it.
    refl scales the physical Fresnel reflection: at 24 samples the mirrored room is too noisy for the denoiser (the
    glass gives it no guiding features), 0.35 keeps the lamp reflections and hides the grain."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new
    out = N('ShaderNodeOutputMaterial')
    tc = N('ShaderNodeTexCoord')
    mp = N('ShaderNodeMapping')
    mp.inputs['Location'].default_value = (seed * 3.1, seed * 1.7, seed * 2.3)
    L(tc.outputs['Object'], mp.inputs['Vector'])
    nz = N('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 1.6
    nz.inputs['Detail'].default_value = 2.0
    nz.inputs['Distortion'].default_value = 0.6
    L(mp.outputs['Vector'], nz.inputs['Vector'])
    rr = N('ShaderNodeMapRange')
    rr.inputs['From Min'].default_value, rr.inputs['From Max'].default_value = 0.35, 0.75
    rr.inputs['To Min'].default_value, rr.inputs['To Max'].default_value = 0.015, 0.015 + smudge
    L(nz.outputs['Fac'], rr.inputs['Value'])
    gl = N('ShaderNodeBsdfGlossy')
    gl.inputs['Color'].default_value = (1, 1, 1, 1)
    L(rr.outputs['Result'], gl.inputs['Roughness'])
    tr = N('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = tuple(tint) + (1,)
    fr = N('ShaderNodeFresnel')
    fr.inputs['IOR'].default_value = 1.52
    k = N('ShaderNodeMath')
    k.operation = 'MULTIPLY'
    k.inputs[1].default_value = refl
    L(fr.outputs[0], k.inputs[0])
    mx = N('ShaderNodeMixShader')
    L(k.outputs[0], mx.inputs[0])
    L(tr.outputs[0], mx.inputs[1])
    L(gl.outputs[0], mx.inputs[2])
    # dust: a faint, large-scale diffuse film
    df = N('ShaderNodeBsdfDiffuse')
    df.inputs['Color'].default_value = (0.42, 0.42, 0.42, 1)
    dn = N('ShaderNodeMapRange')
    dn.inputs['From Min'].default_value, dn.inputs['From Max'].default_value = 0.3, 0.8
    dn.inputs['To Min'].default_value, dn.inputs['To Max'].default_value = 0.0, 0.05 * dust
    L(nz.outputs['Fac'], dn.inputs['Value'])
    mx2 = N('ShaderNodeMixShader')
    L(dn.outputs['Result'], mx2.inputs[0])
    L(mx.outputs[0], mx2.inputs[1])
    L(df.outputs[0], mx2.inputs[2])
    L(mx2.outputs[0], out.inputs['Surface'])
    return m


def m_bulb(name='arch_bulb', strength=3.0):
    """Clear amber vintage bulb envelope: thin glass + a soft glow (the filament inside carries the hot spot)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new
    out = N('ShaderNodeOutputMaterial')
    tr = N('ShaderNodeBsdfTransparent')
    tr.inputs['Color'].default_value = (1.0, 0.82, 0.55, 1)
    gl = N('ShaderNodeBsdfGlossy')
    gl.inputs['Roughness'].default_value = 0.04
    fr = N('ShaderNodeFresnel')
    fr.inputs['IOR'].default_value = 1.5
    mx = N('ShaderNodeMixShader')
    L(fr.outputs[0], mx.inputs[0])
    L(tr.outputs[0], mx.inputs[1])
    L(gl.outputs[0], mx.inputs[2])
    em = N('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.55, 0.24, 1)
    em.inputs['Strength'].default_value = strength
    ad = N('ShaderNodeAddShader')
    L(mx.outputs[0], ad.inputs[0])
    L(em.outputs[0], ad.inputs[1])
    L(ad.outputs[0], out.inputs['Surface'])
    return m


def m_print(name='arch_print_img'):
    path = os.path.join(TEX, 'arch_print.png')
    if not os.path.exists(path):
        make_print_image(path)
    T = _NT(name)
    tx = T.nt.nodes.new('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(path, check_existing=True)
    tc = T.nt.nodes.new('ShaderNodeTexCoord')
    T.link(tc.outputs['UV'], tx.inputs['Vector'])
    return T.set(base=tx.outputs['Color'], rough=0.62, spec=0.4)


def materials():
    M = {}
    M['floor'] = _cached('arch_floor', m_floor)
    M['plaster'] = _cached('arch_plaster', lambda n: m_plaster(n, (124, 121, 117), 1.0))
    M['plaster_front'] = _cached('arch_plaster_front', lambda n: m_plaster(n, (118, 115, 111), 8.0))
    M['brick_painted'] = _cached('arch_brick_painted', lambda n: m_brick(n, painted=(192, 186, 174), seed=3.0))
    M['brick_old'] = _cached('arch_brick_old', lambda n: m_brick(n, (118, 60, 44), (128, 122, 112), seed=11.0))
    M['ceiling'] = _cached('arch_ceiling', m_ceiling)
    M['lintel'] = _cached('arch_lintel', lambda n: mat5.concrete(n, (128, 126, 121), 0.85, seed=5.0))
    M['sill'] = _cached('arch_sill', lambda n: mat5.concrete(n, (150, 147, 141), 0.6, polish=0.3, seed=6.0))
    M['frame'] = _cached('arch_frame', lambda n: mat5.painted_metal(n, (24, 26, 28), 0.42, 0.10, seed=2.0))
    M['beam'] = _cached('arch_beam', lambda n: mat5.painted_metal(n, (52, 56, 60), 0.5, 0.18, seed=4.0))
    M['galv'] = _cached('arch_galv', m_galv)
    M['conduit'] = _cached('arch_conduit', lambda n: mat5.metal(n, (150, 152, 154), 0.42))
    M['box_grey'] = _cached('arch_box_grey', lambda n: mat5.plastic(n, (150, 150, 146), 0.5))
    M['switch'] = _cached('arch_switch', lambda n: mat5.plastic(n, (226, 222, 212), 0.35))
    M['glass'] = _cached('arch_glass', lambda n: m_glass(n, (0.97, 0.99, 1.0), 0.25, 0.05, 0.0))
    M['glass_old'] = _cached('arch_glass_old', lambda n: m_glass(n, (0.90, 0.97, 0.93), 0.6, 0.10, 3.0))
    M['glass_new'] = _cached('arch_glass_new', lambda n: m_glass(n, (0.99, 1.0, 1.0), 0.05, 0.02, 7.0))
    M['trim'] = _cached('arch_trim', lambda n: m_paint_wood(n, (222, 218, 206), 0.38, 2.0, 0.08))
    M['door'] = _cached('arch_door', lambda n: m_paint_wood(n, (50, 68, 72), 0.36, 5.0, 0.16))
    M['oak'] = _cached('arch_oak', lambda n: mat5.wood(n, (128, 92, 60), 'Y', varnish=0.3, seed=2.0))
    M['brass'] = _cached('arch_brass', lambda n: mat5.metal(n, (168, 132, 80), 0.34, brushed=False))
    M['iron'] = _cached('arch_iron', lambda n: mat5.painted_metal(n, (20, 20, 21), 0.5, 0.1, seed=8.0))
    M['dado'] = _cached('arch_dado', lambda n: m_paint_wood(n, (64, 80, 72), 0.42, 9.0, 0.10))
    M['cream'] = _cached('arch_cream', lambda n: m_plaster(n, (206, 192, 166), 12.0, 0.25))
    M['cor_ceiling'] = _cached('arch_cor_ceiling', lambda n: mat5.matte(n, (222, 216, 204), 0.9))
    M['boards'] = _cached('arch_boards', m_boards)
    M['coir'] = _cached('arch_coir', m_coir)
    M['rubber'] = _cached('arch_rubber', lambda n: mat5.rubber(n, (24, 24, 25), 0.8))
    M['jacket'] = _cached('arch_jacket', lambda n: mat5.fabric(n, (52, 60, 46), 0.9, 300.0, 0.4, seed=2.0))
    M['tote'] = _cached('arch_tote', lambda n: mat5.fabric(n, (196, 184, 160), 0.9, 500.0, 0.3, seed=5.0))
    M['shade_out'] = _cached('arch_shade_out', lambda n: mat5.painted_metal(n, (34, 46, 42), 0.32, 0.14, seed=3.0))
    M['shade_in'] = _cached('arch_shade_in', lambda n: mat5.ceramic(n, (238, 234, 224), 0.28))
    M['bakelite'] = _cached('arch_bakelite', lambda n: mat5.plastic(n, (26, 20, 16), 0.3))
    M['cord'] = _cached('arch_cord', lambda n: mat5.fabric(n, (20, 20, 20), 0.8, 900.0, 0.3))
    M['bulb'] = _cached('arch_bulb', m_bulb)
    M['filament'] = _cached('arch_filament', lambda n: mat5.emissive(n, (255, 170, 90), 60.0))
    M['opal'] = _cached('arch_opal', lambda n: mat5.emissive(n, (255, 214, 170), 7.0, (240, 236, 228)))
    M['radiator'] = _cached('arch_radiator', lambda n: mat5.painted_metal(n, (212, 206, 192), 0.42, 0.10, seed=6.0))
    M['copper'] = _cached('arch_copper', lambda n: mat5.metal(n, (176, 108, 76), 0.38, brushed=False))
    M['frame_black'] = _cached('arch_pframe', lambda n: mat5.wood(n, (30, 28, 27), 'X', ring_scale=60.0, rough=0.45, seed=4.0))
    M['mat_board'] = _cached('arch_matboard', lambda n: mat5.paper(n, (232, 228, 218), 0.92))
    M['print'] = _cached('arch_print_img', m_print)
    M['led_red'] = _cached('arch_led_red', lambda n: mat5.emissive(n, (255, 40, 30), 8.0))
    M['led_orange'] = _cached('arch_led_orange', lambda n: mat5.emissive(n, (255, 140, 40), 3.0, (120, 70, 30)))
    return M


# ------------------------------------------------------------------ geometry helpers
class Acc:
    """Accumulate many simple parts into ONE mesh object (fewer objects, one bevel modifier), several materials."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def _mi(self, mat):
        for i, m in enumerate(self.mats):
            if m is mat:
                return i
        self.mats.append(mat)
        return len(self.mats) - 1

    def _tag(self, verts, mat):
        mi = self._mi(mat)
        fs = set()
        for v in verts:
            fs.update(v.link_faces)
        for f in fs:
            f.material_index = mi

    @staticmethod
    def _M(loc, rot, scale=(1, 1, 1)):
        R = Euler(tuple(math.radians(a) for a in rot)).to_matrix().to_4x4()
        return Matrix.Translation(loc) @ R @ Matrix.Diagonal((scale[0], scale[1], scale[2], 1.0))

    def box(self, size, loc, mat, rot=(0, 0, 0)):
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=self._M(loc, rot, size))
        self._tag(r['verts'], mat)

    def span(self, lo, hi, mat):
        """Axis-aligned box from corner lo to corner hi."""
        size = tuple(abs(b - a) for a, b in zip(lo, hi))
        loc = tuple((a + b) / 2 for a, b in zip(lo, hi))
        self.box(size, loc, mat)

    def cyl(self, r, h, loc, mat, rot=(0, 0, 0), verts=16, r2=None, cap=True):
        res = bmesh.ops.create_cone(self.bm, cap_ends=cap, cap_tris=False, segments=verts, radius1=r,
                                    radius2=r if r2 is None else r2, depth=h, matrix=self._M(loc, rot))
        self._tag(res['verts'], mat)

    def sphere(self, r, loc, mat, scale=(1, 1, 1), segs=16, rings=8):
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=r,
                                        matrix=self._M(loc, (0, 0, 0), scale))
        self._tag(res['verts'], mat)

    def quad(self, pts, mat):
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self._mi(mat)

    def lathe(self, prof, loc, mats, segs=32, closed=True):
        """Revolve an outline [(r, z)] around the vertical axis through loc; mats: one material, or one per edge."""
        rings = []
        for (r, z) in prof:
            rings.append([self.bm.verts.new((loc[0] + r * math.cos(2 * math.pi * i / segs),
                                             loc[1] + r * math.sin(2 * math.pi * i / segs), loc[2] + z))
                          for i in range(segs)])
        n = len(prof)
        new = []
        for k in range(n if closed else n - 1):
            ra, rb = rings[k], rings[(k + 1) % n]
            mi = self._mi(mats[k] if isinstance(mats, list) else mats)
            for i in range(segs):
                j = (i + 1) % segs
                f = self.bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
                f.material_index = mi
                new.append(f)
        bmesh.ops.recalc_face_normals(self.bm, faces=new)

    def build(self, P, name, bevel=0.003, segments=2, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), smooth=True):
        me = bpy.data.meshes.new(name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        ob = P._add(name, me, loc, rot, None, bevel, segments, smooth=smooth, parent=parent)
        for m in self.mats:
            me.materials.append(kit5._mat(m))
        return ob


def pipe(P, name, pts, r, mat, bend=0.06, res=5, parent=None):
    """Rigid conduit / pipe along a polyline with real bends (radius ~bend) instead of Bezier wobble."""
    P_ = [Vector(p) for p in pts]
    out = [P_[0]]
    for i in range(1, len(P_) - 1):
        a, b, c = P_[i - 1], P_[i], P_[i + 1]
        d1, d2 = (b - a).normalized(), (c - b).normalized()
        rr = min(bend, (b - a).length / 2, (c - b).length / 2)
        p1, p2 = b - d1 * rr, b + d2 * rr
        for k in range(res + 1):
            t = k / res
            out.append((1 - t) ** 2 * p1 + 2 * (1 - t) * t * b + t * t * p2)
    out.append(P_[-1])
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = r
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    sp = cu.splines.new('POLY')
    sp.points.add(len(out) - 1)
    for p, q in zip(sp.points, out):
        p.co = (q.x, q.y, q.z, 1.0)
    sp.use_smooth = True
    ob = bpy.data.objects.new(f'{P.name}.{name}', cu)
    P.col.objects.link(ob)
    ob.parent = parent or P.root
    cu.materials.append(kit5._mat(mat))
    P.parts[name] = ob
    return ob


# ------------------------------------------------------------------ the shell
def _shell(P, M):
    A = Acc()
    # floor slab (ends at x = 4.11, under the threshold, where the corridor boards begin)
    A.span((X0 - WT, Y0 - WT, -0.25), (4.11, Y1 + 0.32, 0.0), M['floor'])
    P_floor = A.build(P, 'floor', bevel=0)

    A = Acc()
    A.span((X0 - WT, Y0 - WT, 0.0), (X0, Y1 + 0.32, CEIL), M['brick_painted'])           # left wall
    A.span((X0, 4.0, 0.0), (WIN_X1, 4.32, SILL - 0.04), M['brick_painted'])              # upstand under the glazing
    P.parts['wall_left'] = A.build(P, 'wall_left', bevel=0)

    A = Acc()
    A.span((WIN_X1, 4.0, 0.0), (X1 + WT, 4.32, CEIL), M['brick_old'])                    # back-right brick
    A.build(P, 'wall_back_brick', bevel=0)

    A = Acc()
    A.span((X1, Y0 - WT, 0.0), (X1 + WT, DOOR_Y0 - 0.025, CEIL), M['plaster'])          # right wall, door gap
    A.span((X1, DOOR_Y1 + 0.025, 0.0), (X1 + WT, Y1 + 0.32, CEIL), M['plaster'])
    A.span((X1, DOOR_Y0 - 0.025, DOOR_H + 0.025), (X1 + WT, DOOR_Y1 + 0.025, CEIL), M['plaster'])
    A.build(P, 'wall_right', bevel=0)

    A = Acc()
    A.span((X0 - WT, Y0 - WT, 0.0), (X1 + WT, Y0, CEIL), M['plaster_front'])            # front wall
    A.build(P, 'wall_front', bevel=0)

    A = Acc()
    A.span((X0 - WT, Y0 - WT, CEIL), (X1 + WT, Y1 + 0.32, CEIL + 0.25), M['ceiling'])
    A.build(P, 'ceiling', bevel=0)

    # window: concrete lintel above, concrete sill cap below
    A = Acc()
    A.span((WIN_X0, 4.0, HEAD), (WIN_X1, 4.32, CEIL), M['lintel'])
    A.build(P, 'lintel', bevel=0.004)
    A = Acc()
    A.span((WIN_X0, 3.962, SILL - 0.045), (WIN_X1, 4.34, SILL), M['sill'])
    A.build(P, 'sill', bevel=0.006)

    # skirting on the plaster walls (painted, like the trim)
    A = Acc()
    sk_h, sk_t = 0.11, 0.016
    A.span((X1 - sk_t, Y0, 0.0), (X1, DOOR_Y0 - 0.075, sk_h), M['trim'])
    A.span((X1 - sk_t, DOOR_Y1 + 0.075, 0.0), (X1, Y1, sk_h), M['trim'])
    A.span((X0, Y0, 0.0), (X1 - sk_t, Y0 + sk_t, sk_h), M['trim'])
    # a low cement fillet along the brick walls (old loft: the brick stops on a rough concrete upstand)
    A.span((X0, Y0 + sk_t, 0.0), (X0 + 0.022, Y1, 0.06), M['lintel'])
    A.span((WIN_X1 + 0.0, Y1 - 0.022, 0.0), (X1 - sk_t, Y1, 0.06), M['lintel'])
    A.build(P, 'skirting', bevel=0.003)
    return P_floor


def _glazing(P, M):
    F = Acc()
    d0, d1 = FR_Y0, FR_Y1
    # perimeter frame
    F.span((WIN_X0, d0, SILL), (WIN_X1, d1, SILL + 0.06), M['frame'])
    F.span((WIN_X0, d0, HEAD - 0.06), (WIN_X1, d1, HEAD), M['frame'])
    F.span((WIN_X0, d0, SILL), (WIN_X0 + 0.06, d1, HEAD), M['frame'])
    F.span((WIN_X1 - 0.06, d0, SILL), (WIN_X1, d1, HEAD), M['frame'])
    # mullions (T sections: a narrow web towards the room + the glazing flange)
    for x in MULLIONS:
        F.span((x - 0.024, d0 + 0.012, SILL + 0.04), (x + 0.024, d1, HEAD - 0.04), M['frame'])
        F.span((x - 0.008, d0 - 0.022, SILL + 0.04), (x + 0.008, d0 + 0.02, HEAD - 0.04), M['frame'])
    for z in TRANSOMS:
        F.span((WIN_X0 + 0.04, d0 + 0.012, z - 0.022), (WIN_X1 - 0.04, d1, z + 0.022), M['frame'])
        F.span((WIN_X0 + 0.04, d0 - 0.022, z - 0.008), (WIN_X1 - 0.04, d0 + 0.02, z + 0.008), M['frame'])
    # glazing putty beads on the outside of every pane (a slightly lighter, rougher line around the glass)
    xs = [WIN_X0] + list(MULLIONS) + [WIN_X1]
    zs = [SILL] + list(TRANSOMS) + [HEAD]
    # bolts at mullion/transom crossings (inside)
    for x in MULLIONS:
        for z in TRANSOMS:
            F.cyl(0.008, 0.012, (x, d0 - 0.026, z), M['frame'], rot=(90, 0, 0), verts=8)
    frame = F.build(P, 'window_frame', bevel=0.003)

    G = Acc()
    special = {(1, 0): 'glass_old', (5, 1): 'glass_old', (6, 2): 'glass_new', (0, 2): 'glass_new'}
    panes = []
    for c in range(len(xs) - 1):
        for r in range(len(zs) - 1):
            xa, xb, za, zb = xs[c], xs[c + 1], zs[r], zs[r + 1]
            if (xa, xb, za, zb) == VENT:
                continue
            m = M[special.get((c, r), 'glass')]
            G.quad([(xa + 0.01, GLASS_Y, za + 0.01), (xb - 0.01, GLASS_Y, za + 0.01),
                    (xb - 0.01, GLASS_Y, zb - 0.01), (xa + 0.01, GLASS_Y, zb - 0.01)], m)
            panes.append((xa, xb, za, zb))
    glass = G.build(P, 'window_glass', bevel=0, smooth=False)

    # the top-hung vent: its own sash, open 14 deg outwards, a stay and a cockspur handle
    xa, xb, za, zb = VENT
    xa += 0.024
    xb -= 0.024
    za += 0.022
    zb -= 0.06
    piv = Vector(((xa + xb) / 2, d1, zb))
    S = Acc()
    w, dd = 0.034, (d0 + 0.006 - d1, d1 - 0.016 - d1)       # local y range of the sash
    hx = (xb - xa) / 2
    S.span((-hx, dd[0], -(zb - za)), (hx, dd[1], -(zb - za) + w), M['frame'])
    S.span((-hx, dd[0], -w), (hx, dd[1], 0.0), M['frame'])
    S.span((-hx, dd[0], -(zb - za)), (-hx + w, dd[1], 0.0), M['frame'])
    S.span((hx - w, dd[0], -(zb - za)), (hx, dd[1], 0.0), M['frame'])
    S.cyl(0.006, 0.05, (-0.12, dd[0] - 0.012, -(zb - za) + 0.017), M['frame'], rot=(90, 0, 0), verts=8)
    S.box((0.11, 0.008, 0.016), (-0.17, dd[0] - 0.036, -(zb - za) + 0.017), M['frame'], rot=(0, 0, 8))
    S.quad([(-hx + 0.01, (dd[0] + dd[1]) / 2, -(zb - za) + 0.01), (hx - 0.01, (dd[0] + dd[1]) / 2, -(zb - za) + 0.01),
            (hx - 0.01, (dd[0] + dd[1]) / 2, -0.01), (-hx + 0.01, (dd[0] + dd[1]) / 2, -0.01)], M['glass_old'])
    vent = S.build(P, 'window_vent', bevel=0.0025, loc=tuple(piv), rot=(14, 0, 0))
    # stay arm from the transom up to the open sash's bottom rail (a flat bar with holes = a thin box)
    L = (zb - za)
    tip = piv + Vector((0.18, L * math.sin(math.radians(14)) + (dd[0] + dd[1]) / 2 * math.cos(math.radians(14)),
                        -L * math.cos(math.radians(14)) + 0.02))
    base = Vector((piv.x + 0.18, d0 + 0.01, za - 0.005))
    St = Acc()
    mid = (tip + base) / 2
    ln = (tip - base).length
    ang = math.degrees(math.atan2(tip.z - base.z, tip.y - base.y))
    St.box((0.008, ln + 0.02, 0.016), tuple(mid), M['frame'], rot=(ang, 0, 0))
    St.cyl(0.007, 0.03, tuple(base), M['frame'], rot=(0, 90, 0), verts=8)
    St.build(P, 'window_stay', bevel=0.0015)
    return frame, glass, vent, panes


def _ceiling_services(P, M):
    # two painted steel I-beams along X (300 x 160), stiffeners, bearing plates with bolts at the walls
    B = Acc()
    for yb in BEAMS_Y:
        B.span((X0 - 0.1, yb - 0.08, CEIL - 0.016), (X1 + 0.1, yb + 0.08, CEIL), M['beam'])
        B.span((X0 - 0.1, yb - 0.005, CEIL - 0.284), (X1 + 0.1, yb + 0.005, CEIL - 0.016), M['beam'])
        B.span((X0 - 0.1, yb - 0.08, CEIL - 0.30), (X1 + 0.1, yb + 0.08, CEIL - 0.284), M['beam'])
        for x in (-3.5, -2.0, -0.5, 1.0, 2.5):
            for s in (-1, 1):
                B.span((x - 0.005, yb + s * 0.005, CEIL - 0.284), (x + 0.005, yb + s * 0.074, CEIL - 0.016), M['beam'])
        for xw, sgn in ((X0, 1), (X1, -1)):
            B.span((xw if sgn > 0 else xw - 0.014, yb - 0.13, CEIL - 0.38), (xw + 0.014 if sgn > 0 else xw, yb + 0.13, CEIL), M['beam'])
            for dy in (-0.095, 0.095):
                for z in (CEIL - 0.34, CEIL - 0.06):
                    B.cyl(0.013, 0.012, (xw + sgn * 0.019, yb + dy, z), M['beam'], rot=(0, 90, 0), verts=6)
    B.build(P, 'beams', bevel=0.0025)

    # exposed spiral duct with couplings, strap hangers on rods, two side grilles, wall collars
    D = Acc()
    L = X1 - X0
    D.cyl(DUCT_R, L + 0.2, ((X0 + X1) / 2, DUCT_Y, DUCT_Z), M['galv'], rot=(0, 90, 0), verts=40, cap=False)
    for x in (-3.5, -0.5, 2.5):
        D.cyl(DUCT_R + 0.004, 0.07, (x, DUCT_Y, DUCT_Z), M['galv'], rot=(0, 90, 0), verts=40)
    for x in (-4.3, -2.5, -0.7, 1.1, 2.9):
        D.cyl(DUCT_R + 0.003, 0.025, (x, DUCT_Y, DUCT_Z), M['conduit'], rot=(0, 90, 0), verts=40)
        D.cyl(0.005, CEIL - (DUCT_Z + DUCT_R) + 0.01, (x, DUCT_Y, (CEIL + DUCT_Z + DUCT_R) / 2), M['conduit'], verts=8)
        D.cyl(0.02, 0.008, (x, DUCT_Y, CEIL - 0.004), M['conduit'], verts=10)
        D.box((0.03, 0.012, 0.03), (x, DUCT_Y, DUCT_Z + DUCT_R + 0.012), M['conduit'])
    for xw in (X0 + 0.01, X1 - 0.01):
        D.cyl(DUCT_R + 0.035, 0.012, (xw, DUCT_Y, DUCT_Z), M['galv'], rot=(0, 90, 0), verts=40)
    for x in (-2.2, 1.0):
        yf = DUCT_Y - DUCT_R - 0.012
        D.span((x - 0.17, yf - 0.012, DUCT_Z - 0.06), (x + 0.17, yf + 0.05, DUCT_Z + 0.06), M['galv'])
        D.span((x - 0.155, yf - 0.016, DUCT_Z - 0.048), (x + 0.155, yf - 0.006, DUCT_Z + 0.048), M['iron'])
        for k in range(6):
            z = DUCT_Z - 0.04 + k * 0.016
            D.box((0.30, 0.004, 0.012), (x, yf - 0.017, z), M['galv'], rot=(35, 0, 0))
    D.build(P, 'duct', bevel=0.002)

    # electrical: switches, steel conduit runs, junction boxes, sockets
    r = 0.011
    E = Acc()
    # bench lamps: switch on the left wall by the window, conduit up and along the ceiling at y = 3.3
    sw_l = (X0 + 0.012, 3.72, 1.15)
    E.box((0.024, 0.085, 0.085), sw_l, M['switch'])
    E.box((0.008, 0.012, 0.026), (X0 + 0.026, 3.72, 1.155), M['switch'], rot=(0, 0, 0))
    pipe(P, 'conduit_bench', [(X0 + 0.013, 3.72, 1.19), (X0 + 0.013, 3.72, CEIL - 0.025), (X0 + 0.013, 3.30, CEIL - 0.025),
                              (-2.6, 3.30, CEIL - 0.025)], r, M['conduit'])
    pipe(P, 'conduit_sockets', [(X0 + 0.013, 3.72, 1.11), (X0 + 0.013, 3.72, 0.35), (X0 + 0.013, 3.985, 0.35),
                                (-2.30, 3.985, 0.35)], r, M['conduit'])
    for x in (-3.9, -2.32):
        E.box((0.15, 0.04, 0.085), (x, 3.98, 0.35), M['box_grey'])
        for dx in (-0.036, 0.036):
            E.cyl(0.021, 0.006, (x + dx, 3.958, 0.35), M['switch'], rot=(90, 0, 0), verts=16)
    # living pendant + door switch: right wall, horizontal run under the duct, up and along the ceiling at y = -1.4
    sw_d = (X1 - 0.012, 0.45, 1.10)
    E.box((0.024, 0.085, 0.085), sw_d, M['switch'])
    E.box((0.008, 0.012, 0.026), (X1 - 0.026, 0.45, 1.105), M['switch'])
    pipe(P, 'conduit_living', [(X1 - 0.013, 0.45, 1.14), (X1 - 0.013, 0.45, 2.85), (X1 - 0.013, -1.40, 2.85),
                               (X1 - 0.013, -1.40, CEIL - 0.025), (1.3, -1.40, CEIL - 0.025)], r, M['conduit'])
    # kitchenette socket on the back brick wall
    pipe(P, 'conduit_kitchen', [(X1 - 0.013, Y1 - 0.013, CEIL - 0.025), (2.6, Y1 - 0.013, CEIL - 0.025),
                                (2.6, Y1 - 0.013, 1.16)], r, M['conduit'])
    E.box((0.15, 0.04, 0.085), (2.6, Y1 - 0.02, 1.12), M['box_grey'])
    for dx in (-0.036, 0.036):
        E.cyl(0.021, 0.006, (2.6 + dx, Y1 - 0.042, 1.12), M['switch'], rot=(90, 0, 0), verts=16)
    # saddles holding the conduit every ~0.8 m
    clip = {'x': (0.014, 0.03, 0.03), 'y': (0.03, 0.014, 0.03), 'z': (0.03, 0.03, 0.014)}
    for (x, y, z, ax) in [(X0 + 0.013, 3.72, 2.0, 'z'), (X0 + 0.013, 3.72, 2.8, 'z'), (X0 + 0.013, 3.72, 0.7, 'z'),
                          (-4.5, 3.30, CEIL - 0.025, 'x'), (-3.3, 3.30, CEIL - 0.025, 'x'),
                          (X1 - 0.013, 0.45, 1.9, 'z'), (X1 - 0.013, -0.5, 2.85, 'y'),
                          (3.0, -1.40, CEIL - 0.025, 'x'), (2.1, -1.40, CEIL - 0.025, 'x'),
                          (3.3, Y1 - 0.013, CEIL - 0.025, 'x'), (2.6, Y1 - 0.013, 2.2, 'z'),
                          (-3.2, 3.985, 0.35, 'x')]:
        E.box(clip[ax], (x, y, z), M['conduit'])
    # junction boxes (also the pendants' ceiling roses)
    for (x, y) in ((-4.0, 3.30), (-2.6, 3.30), (1.3, -1.40)):
        E.cyl(0.042, 0.045, (x, y, CEIL - 0.0225), M['conduit'], verts=20)
        E.cyl(0.046, 0.006, (x, y, CEIL - 0.047), M['conduit'], verts=20)
    E.box((0.10, 0.10, 0.05), (X1 - 0.025, -1.40, 2.85), M['box_grey'])
    # smoke detector
    E.cyl(0.058, 0.032, (-0.6, 1.05, CEIL - 0.016), M['switch'], verts=24)
    E.cyl(0.004, 0.003, (-0.585, 1.05, CEIL - 0.0335), M['led_red'], verts=8)
    E.build(P, 'electrical', bevel=0.003)


def _pendant(P, M, name, x, y, zb, D, watts, power):
    """Industrial dome pendant: spun steel shade (painted outside, white enamel inside), bakelite socket, clear
    vintage bulb with a glowing filament, fabric cord to the ceiling rose, and a REAL point light at the bulb."""
    R = D / 2
    z_rim = zb - 0.03
    neck_top = zb + 0.15
    Hd = neck_top - 0.045 - z_rim
    rn = 0.036
    t = 0.0016
    outer, inner = [], []
    for k in range(13):
        th = math.pi / 2 * (1 - k / 12)               # rim -> top
        outer.append((rn + (R - rn) * math.sin(th), Hd * math.cos(th)))
    # closed outline: rolled lip -> outer dome up to the neck -> across the neck top -> inner surface back down
    prof = [(R + 0.007, 0.0)] + outer + [(rn, Hd + 0.045), (rn - t, Hd + 0.045)]
    inner = [(rn - t, Hd)] + [((r - t) if r > rn else rn - t, z - t) for (r, z) in reversed(outer)]
    prof += inner + [(R + 0.006, -0.003)]
    n_out = 1 + len(outer) + 1                  # lip edge, dome edges, neck, neck top
    n_in = len(inner)                           # inner neck + inner dome
    mats = ['out'] * n_out + ['in'] * n_in
    mats += ['out'] * (len(prof) - len(mats))   # rim edges
    mats = [M['shade_out'] if m == 'out' else M['shade_in'] for m in mats]
    S = Acc()
    S.lathe(prof, (x, y, z_rim), mats, segs=40)
    shade = S.build(P, f'pendant_{name}_shade', bevel=0)
    Bk = Acc()
    Bk.cyl(0.021, 0.065, (x, y, zb + 0.115), M['bakelite'], verts=20)
    Bk.cyl(0.024, 0.012, (x, y, zb + 0.088), M['bakelite'], verts=20)
    Bk.cyl(0.011, 0.03, (x, y, neck_top + 0.012), M['bakelite'], verts=12)
    Bk.cyl(0.0034, CEIL - 0.047 - (neck_top + 0.027), (x, y, (CEIL - 0.047 + neck_top + 0.027) / 2), M['cord'], verts=8)
    Bk.build(P, f'pendant_{name}_fitting', bevel=0.0015)
    bp = [(0.0135, 0.0), (0.0135, -0.02), (0.017, -0.035), (0.024, -0.05), (0.030, -0.068), (0.032, -0.085),
          (0.030, -0.103), (0.024, -0.117), (0.014, -0.127), (0.002, -0.131)]
    Bu = Acc()
    Bu.lathe(bp, (x, y, zb + 0.082), M['bulb'], segs=24, closed=False)
    bulb = Bu.build(P, f'pendant_{name}_bulb', bevel=0)
    fil = P.tube(f'pendant_{name}_filament', [(x - 0.010, y, zb + 0.012), (x - 0.005, y + 0.002, zb - 0.010),
                                               (x, y, zb + 0.014), (x + 0.005, y - 0.002, zb - 0.010),
                                               (x + 0.010, y, zb + 0.012)], 0.0008, M['filament'], resolution=4)
    for o in (bulb, fil):
        o.visible_shadow = False
        o.visible_diffuse = False
    fil.visible_glossy = False
    lt = P.light(f'pendant_{name}_light', 'POINT', (x, y, zb), watts * power, WARM, size=0.028)
    return dict(name=name, light=lt, bulb=(x, y, zb), rim_z=z_rim, shade=shade, bulb_obj=bulb)


def _door(P, M):
    """Frame (jambs, stops, architraves both sides, oak threshold), the panelled leaf on the hinge empty, brass
    lever handles, deadbolt, peephole, three butt hinges."""
    F = Acc()
    ya, yb = DOOR_Y0, DOOR_Y1
    F.span((X1, yb, 0.0), (X1 + WT, yb + 0.025, DOOR_H + 0.025), M['trim'])
    F.span((X1, ya - 0.025, 0.0), (X1 + WT, ya, DOOR_H + 0.025), M['trim'])
    F.span((X1, ya - 0.025, DOOR_H), (X1 + WT, yb + 0.025, DOOR_H + 0.025), M['trim'])
    F.span((X1 + 0.047, yb - 0.014, 0.012), (X1 + 0.085, yb, DOOR_H), M['trim'])
    F.span((X1 + 0.047, ya, 0.012), (X1 + 0.085, ya + 0.014, DOOR_H), M['trim'])
    F.span((X1 + 0.047, ya, DOOR_H - 0.014), (X1 + 0.085, yb, DOOR_H), M['trim'])
    for xs, xe in ((X1 - 0.02, X1), (X1 + WT + 0.015, X1 + WT + 0.035)):
        F.span((xs, yb + 0.005, 0.0), (xe, yb + 0.075, DOOR_H + 0.075), M['trim'])
        F.span((xs, ya - 0.075, 0.0), (xe, ya - 0.005, DOOR_H + 0.075), M['trim'])
        F.span((xs, ya - 0.075, DOOR_H + 0.005), (xe, yb + 0.075, DOOR_H + 0.075), M['trim'])
    F.span((X1 - 0.004, ya, 0.0), (X1 + WT, yb, 0.010), M['oak'])
    for z in (0.25, 1.06, 1.85):                       # hinge knuckles (coaxial with the hinge empty)
        F.cyl(0.0075, 0.11, (HINGE[0], HINGE[1], z), M['brass'], verts=12)
        F.cyl(0.0045, 0.012, (HINGE[0], HINGE[1], z + 0.061), M['brass'], verts=12)
        F.cyl(0.0045, 0.012, (HINGE[0], HINGE[1], z - 0.061), M['brass'], verts=12)
    frame = F.build(P, 'door_frame', bevel=0.0025)

    hinge = bpy.data.objects.new('door_hinge', None)
    hinge.empty_display_type = 'ARROWS'
    hinge.empty_display_size = 0.3
    P.col.objects.link(hinge)
    hinge.parent = P.root
    hinge.location = HINGE
    P.parts['door_hinge'] = hinge

    # leaf in hinge-local coordinates: x 0.001..0.046 (interior face at x = 0), y -0.947..-0.003, z 0.016..2.092
    L = Acc()
    x0, x1 = 0.001, 0.046
    yA, yB = -0.947, -0.003
    zA, zB = 0.016, 2.092
    st = 0.115
    L.span((x0, yA, zA), (x1, yA + st, zB), M['door'])
    L.span((x0, yB - st, zA), (x1, yB, zB), M['door'])
    rails = [(zA, 0.24), (0.90, 1.10), (1.96, zB)]
    for (za, zb) in rails:
        L.span((x0, yA + st, za), (x1, yB - st, zb), M['door'])
    ym = (yA + yB) / 2
    for (za, zb) in ((0.24, 0.90), (1.10, 1.96)):
        L.span((x0, ym - 0.05, za), (x1, ym + 0.05, zb), M['door'])
    cols = [(yA + st, ym - 0.05), (ym + 0.05, yB - st)]
    rows = [(0.24, 0.90), (1.10, 1.96)]
    pt = 0.018
    xc = (x0 + x1) / 2
    for (ya_, yb_) in cols:
        for (za, zb) in rows:
            L.span((xc - pt / 2, ya_ - 0.008, za - 0.008), (xc + pt / 2, yb_ + 0.008, zb + 0.008), M['door'])
            # raised field (fielded panel) on both faces
            L.span((xc - pt / 2 - 0.004, ya_ + 0.05, za + 0.05), (xc + pt / 2 + 0.004, yb_ - 0.05, zb - 0.05), M['door'])
            for face, sgn in ((x0, 1), (x1, -1)):
                xin = xc - sgn * pt / 2
                xs = sorted((xin, xin - sgn * 0.011))
                m = 0.014
                L.span((xs[0], ya_, za), (xs[1], ya_ + m, zb), M['door'])
                L.span((xs[0], yb_ - m, za), (xs[1], yb_, zb), M['door'])
                L.span((xs[0], ya_, za), (xs[1], yb_, za + m), M['door'])
                L.span((xs[0], ya_, zb - m), (xs[1], yb_, zb), M['door'])
    leaf = L.build(P, 'door_leaf', bevel=0.0025, parent=hinge)

    H = Acc()
    yh = yA + 0.062
    for face, sgn in ((x0, -1), (x1, 1)):
        H.span((face, yh - 0.022, 0.88), (face + sgn * 0.006, yh + 0.022, 1.12), M['brass'])
        H.cyl(0.012, 0.045, (face + sgn * 0.028, yh, 1.06), M['brass'], rot=(0, 90, 0), verts=16)
        H.cyl(0.009, 0.13, (face + sgn * 0.05, yh + 0.058, 1.06), M['brass'], rot=(90, 0, 0), verts=12)
        H.sphere(0.0105, (face + sgn * 0.05, yh + 0.123, 1.06), M['brass'], scale=(1, 1.2, 1))
        H.span((face + sgn * 0.006, yh - 0.004, 0.935), (face + sgn * 0.0068, yh + 0.004, 0.958), M['iron'])
        H.cyl(0.021, 0.009, (face + sgn * 0.0045, yh, 1.30), M['brass'], rot=(0, 90, 0), verts=20)
        H.cyl(0.006, 0.012, (face + sgn * 0.0095, ym, 1.53), M['brass'], rot=(0, 90, 0), verts=12)
    H.box((0.014, 0.008, 0.034), (x0 - 0.016, yh, 1.30), M['brass'])
    H.cyl(0.009, 0.004, (x1 + 0.0105, yh, 1.30), M['iron'], rot=(0, 90, 0), verts=12)
    H.build(P, 'door_hardware', bevel=0.0012, parent=hinge)
    return hinge, leaf, frame


def _two_tone(A, M, lo, hi):
    """Corridor wall slab, dark satin dado below 1.05 m, cream above."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    if z0 < DADO:
        A.span((x0, y0, z0), (x1, y1, min(z1, DADO)), M['dado'])
    if z1 > DADO:
        A.span((x0, y0, max(z0, DADO)), (x1, y1, z1), M['cream'])


def _corridor(P, M):
    """The landing/entrance hall behind the door: boards, two-tone walls with a dado rail, skirting, a warm opal
    wall lamp opposite the door, a coat rail with a parka and a tote bag, a coir doormat, the orange glowing
    stair-light timer button ('minuterie')."""
    A = Acc()
    cx0, cx1, cy0, cy1, ch = COR_X0, COR_X1, COR_Y0, COR_Y1, COR_H
    A.span((4.11, cy0 - 0.2, -0.25), (cx1 + 0.2, cy1 + 0.2, 0.0), M['boards'])
    A.span((X1 + 0.08, cy0 - 0.2, ch), (cx1 + 0.2, cy1 + 0.2, ch + 0.12), M['cor_ceiling'])
    A.build(P, 'corridor_floor_ceiling', bevel=0)
    W = Acc()
    _two_tone(W, M, (cx1, cy0 - 0.2, 0.0), (cx1 + 0.2, cy1 + 0.2, ch))
    _two_tone(W, M, (cx0, cy0 - 0.2, 0.0), (cx1, cy0, ch))
    _two_tone(W, M, (cx0, cy1, 0.0), (cx1, cy1 + 0.2, ch))
    xc = cx0 + 0.015
    _two_tone(W, M, (cx0, cy0, 0.0), (xc, DOOR_Y0 - 0.025, ch))
    _two_tone(W, M, (cx0, DOOR_Y1 + 0.025, 0.0), (xc, cy1, ch))
    _two_tone(W, M, (cx0, DOOR_Y0 - 0.025, DOOR_H + 0.025), (xc, DOOR_Y1 + 0.025, ch))
    W.build(P, 'corridor_walls', bevel=0)
    T = Acc()
    # dado rail and skirting
    T.span((cx1 - 0.022, cy0, DADO - 0.02), (cx1, cy1, DADO + 0.025), M['trim'])
    T.span((cx0, cy0, DADO - 0.02), (cx1, cy0 + 0.022, DADO + 0.025), M['trim'])
    T.span((cx0, cy1 - 0.022, DADO - 0.02), (cx1, cy1, DADO + 0.025), M['trim'])
    T.span((xc, cy0, DADO - 0.02), (xc + 0.022, DOOR_Y0 - 0.075, DADO + 0.025), M['trim'])
    T.span((xc, DOOR_Y1 + 0.075, DADO - 0.02), (xc + 0.022, cy1, DADO + 0.025), M['trim'])
    T.span((cx1 - 0.018, cy0, 0.0), (cx1, cy1, 0.12), M['dado'])
    T.span((cx0, cy0, 0.0), (cx1, cy0 + 0.018, 0.12), M['dado'])
    T.span((cx0, cy1 - 0.018, 0.0), (cx1, cy1, 0.12), M['dado'])
    T.span((xc, cy0, 0.0), (xc + 0.018, DOOR_Y0 - 0.075, 0.12), M['dado'])
    T.span((xc, DOOR_Y1 + 0.075, 0.0), (xc + 0.018, cy1, 0.12), M['dado'])
    # wall lamp opposite the door: brass rose and arm, gallery, opal globe
    lx, ly, lz = CORRIDOR_LAMP
    T.cyl(0.055, 0.018, (cx1 - 0.009, ly, lz - 0.09), M['brass'], rot=(0, 90, 0), verts=24)
    T.cyl(0.009, cx1 - lx, ((cx1 + lx) / 2, ly, lz - 0.09), M['brass'], rot=(0, 90, 0), verts=12)
    T.cyl(0.046, 0.04, (lx, ly, lz - 0.085), M['brass'], verts=24, r2=0.036)
    T.cyl(0.036, 0.012, (lx, ly, lz - 0.06), M['brass'], verts=24)
    # coat rail: oak board with three cast hooks
    T.span((cx1 - 0.022, 2.62, 1.68), (cx1, 3.32, 1.77), M['oak'])
    hooks = (2.74, 2.97, 3.20)
    for hy in hooks:
        T.cyl(0.007, 0.07, (cx1 - 0.055, hy, 1.73), M['iron'], rot=(0, 90, 0), verts=10)
        T.cyl(0.006, 0.05, (cx1 - 0.09, hy, 1.75), M['iron'], rot=(0, -30, 0), verts=10)
        T.sphere(0.009, (cx1 - 0.103, hy, 1.772), M['iron'])
        T.cyl(0.006, 0.035, (cx1 - 0.08, hy, 1.70), M['iron'], rot=(0, 40, 0), verts=10)
    # doormat: coir in a rubber border, a little askew
    T.box((0.52, 0.78, 0.016), (4.56, 1.24, 0.008), M['rubber'], rot=(0, 0, 2.5))
    T.box((0.48, 0.74, 0.004), (4.56, 1.24, 0.017), M['coir'], rot=(0, 0, 2.5))
    # stair-light timer push button next to the door (corridor side)
    T.box((0.012, 0.07, 0.07), (xc + 0.006, DOOR_Y0 - 0.22, 1.25), M['switch'])
    T.cyl(0.016, 0.008, (xc + 0.014, DOOR_Y0 - 0.22, 1.25), M['led_orange'], rot=(0, 90, 0), verts=16)
    T.build(P, 'corridor_details', bevel=0.003)

    globe = P.sphere('corridor_globe', 0.082, (lx, ly, lz), M['opal'], scale=(1, 1, 1.08))
    globe.visible_shadow = False
    lt = P.light('corridor_light', 'POINT', (lx, ly, lz), 40.0, (1.0, 0.74, 0.50), size=0.07)

    # parka hanging from the middle hook by its collar loop + sleeves; a tote bag on the last hook
    jy = hooks[1]
    secs = [(1.745, 0.012, 0.025), (1.71, 0.035, 0.07), (1.66, 0.06, 0.13), (1.58, 0.085, 0.19), (1.48, 0.10, 0.225),
            (1.30, 0.11, 0.235), (1.10, 0.112, 0.24), (0.92, 0.105, 0.245), (0.86, 0.10, 0.24)]
    n = 20
    verts, faces = [], []
    for k, (z, hx, hy) in enumerate(secs):
        cxk = cx1 - 0.04 - hx + 0.004 * math.sin(k * 1.7)
        cyk = jy + 0.006 * math.sin(k * 2.3)
        for i in range(n):
            a = 2 * math.pi * i / n
            bulge = 1.0 + 0.04 * math.sin(3 * a + k)
            verts.append((cxk + hx * math.cos(a) * bulge, cyk + hy * math.sin(a) * bulge, z + 0.01 * math.cos(2 * a) * (k > 1)))
    for k in range(len(secs) - 1):
        for i in range(n):
            j = (i + 1) % n
            faces.append((k * n + i, k * n + j, (k + 1) * n + j, (k + 1) * n + i))
    top = len(verts)
    verts.append((cx1 - 0.052, jy, secs[0][0] + 0.008))
    for i in range(n):
        faces.append((top, (i + 1) % n, i))
    body = P.mesh('corridor_parka', verts, faces, (0, 0, 0), M['jacket'])
    sub = body.modifiers.new('sub', 'SUBSURF')
    sub.levels = sub.render_levels = 2
    for s in (-1, 1):
        P.tube(f'corridor_sleeve{s}', [(cx1 - 0.12, jy + s * 0.20, 1.55), (cx1 - 0.15, jy + s * 0.245, 1.33),
                                        (cx1 - 0.17, jy + s * 0.235, 1.08), (cx1 - 0.165, jy + s * 0.215, 0.93)],
               0.048, M['jacket'], resolution=8)
    P.box('corridor_tote', (0.05, 0.30, 0.38), (cx1 - 0.05, hooks[2] - 0.02, 1.33), M['tote'], rot=(0, -4, 2), bevel=0.012)
    P.tube('corridor_tote_strap', [(cx1 - 0.045, hooks[2] - 0.08, 1.52), (cx1 - 0.08, hooks[2] - 0.02, 1.70),
                                    (cx1 - 0.1, hooks[2], 1.765), (cx1 - 0.08, hooks[2] + 0.04, 1.70),
                                    (cx1 - 0.045, hooks[2] + 0.12, 1.52)], 0.006, M['tote'], resolution=6)
    return lt, globe


def _front(P, M):
    """Front wall dressing: an old cast-iron column radiator (cream paint, valve and pipe into the floor) and a large
    framed blueprint print (generated: a 1930s two-valve radio receiver schematic) behind glass."""
    objs_r, objs_p = [], []
    R = Acc()
    n, pitch = 14, 0.062
    xc, yc = -1.6, Y0 + 0.105
    for k in range(n):
        x = xc + (k - (n - 1) / 2) * pitch
        for dy in (-0.046, 0.0, 0.046):
            R.cyl(0.0175, 0.50, (x, yc + dy, 0.43), M['radiator'], verts=12)
        for z in (0.17, 0.69):
            R.cyl(0.028, 0.124, (x, yc, z), M['radiator'], rot=(90, 0, 0), verts=14)
            R.box((0.05, 0.124, 0.05), (x, yc, z + (0.012 if z > 0.5 else -0.012)), M['radiator'])
        if k < n - 1:
            for z in (0.17, 0.69):
                R.cyl(0.021, pitch, (x + pitch / 2, yc, z), M['radiator'], rot=(0, 90, 0), verts=12)
    for s in (-1, 1):
        x = xc + s * ((n - 1) / 2 * pitch - 0.0)
        R.cyl(0.018, 0.15, (x, yc, 0.075), M['radiator'], verts=12)
        R.cyl(0.03, 0.012, (x, yc, 0.006), M['radiator'], verts=14)
    xe = xc - ((n - 1) / 2 * pitch) - 0.035
    R.cyl(0.013, 0.05, (xe - 0.005, yc, 0.17), M['copper'], rot=(0, 90, 0), verts=12)
    R.cyl(0.02, 0.055, (xe - 0.04, yc, 0.17), M['brass'], verts=14)
    R.cyl(0.024, 0.03, (xe - 0.04, yc, 0.215), M['bakelite'], verts=16)
    R.cyl(0.0105, 0.17, (xe - 0.04, yc, 0.075), M['copper'], verts=12)
    R.cyl(0.02, 0.006, (xe - 0.04, yc, 0.003), M['brass'], verts=12)
    xb = xc + ((n - 1) / 2 * pitch) + 0.03
    R.cyl(0.006, 0.02, (xb, yc, 0.69), M['brass'], rot=(0, 90, 0), verts=10)
    for s in (-1, 1):
        R.span((xc + s * 0.25 - 0.012, Y0, 0.66), (xc + s * 0.25 + 0.012, yc - 0.03, 0.68), M['iron'])
    objs_r.append(R.build(P, 'radiator', bevel=0.003))

    # framed print centred over the sofa, built around its own centre and hung very slightly crooked
    fw, fd, margin = 0.032, 0.028, 0.075
    iw = 1.086
    ih = iw * PRINT_PX[1] / PRINT_PX[0]
    pw, ph = iw + 2 * (fw + margin), ih + 2 * (fw + margin)
    cx, cz = 1.5, 1.66
    Fr = Acc()
    Fr.span((-pw / 2, 0.0, -ph / 2), (pw / 2, fd, -ph / 2 + fw), M['frame_black'])
    Fr.span((-pw / 2, 0.0, ph / 2 - fw), (pw / 2, fd, ph / 2), M['frame_black'])
    Fr.span((-pw / 2, 0.0, -ph / 2), (-pw / 2 + fw, fd, ph / 2), M['frame_black'])
    Fr.span((pw / 2 - fw, 0.0, -ph / 2), (pw / 2, fd, ph / 2), M['frame_black'])
    Fr.span((-pw / 2 + fw, 0.002, -ph / 2 + fw), (pw / 2 - fw, 0.010, ph / 2 - fw), M['mat_board'])
    fo = Fr.build(P, 'print_frame', bevel=0.003, loc=(cx, Y0, cz), rot=(0, 0.35, 0))
    img = P.plane('print_image', (iw, ih), (0.0, 0.0112, 0.0), M['print'], rot=(90, 0, 180), parent=fo)
    gl = P.plane('print_glass', (pw - 2 * fw + 0.01, ph - 2 * fw + 0.01), (0.0, fd - 0.004, 0.0), M['glass_new'],
                 rot=(90, 0, 180), parent=fo)
    objs_p += [fo, img, gl]
    return objs_r, objs_p


# ------------------------------------------------------------------ the print (PIL)
def make_print_image(path, W=PRINT_PX[0], H=PRINT_PX[1]):
    """A blueprint-style plate of a 1930s two-valve radio receiver (French lettering), drawn at 2x and downsampled."""
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def font(sz, mono=False, bold=False):
        cands = (['/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf']
                 if mono else ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
        for c in cands + ['/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf']:
            if os.path.exists(c):
                return ImageFont.truetype(c, sz)
        return ImageFont.load_default()

    S = 2
    ink = Image.new('L', (W * S, H * S), 0)
    d = ImageDraw.Draw(ink)
    lw = 3 * S

    def P(x, y):
        return (int(x * S), int(y * S))

    def line(pts, w=lw, a=255):
        d.line([P(*p) for p in pts], fill=a, width=w, joint='curve')

    def text(x, y, s, sz=30, mono=True, bold=False, a=235, anchor='la'):
        d.text(P(x, y), s, fill=a, font=font(sz * S, mono, bold), anchor=anchor)

    def dot(x, y, r=7):
        d.ellipse([P(x - r, y - r), P(x + r, y + r)], fill=255)

    def resistor(x0, y, x1, label=None):
        n = 6
        seg = (x1 - x0 - 60) / n
        pts = [(x0, y), (x0 + 30, y)]
        for i in range(n):
            pts.append((x0 + 30 + seg * (i + 0.5), y + (-18 if i % 2 == 0 else 18)))
        pts += [(x1 - 30, y), (x1, y)]
        line(pts)
        if label:
            text((x0 + x1) / 2, y - 34, label, 26, anchor='mb')

    def resistor_v(x, y0, y1, label=None):
        n = 6
        seg = (y1 - y0 - 60) / n
        pts = [(x, y0), (x, y0 + 30)]
        for i in range(n):
            pts.append((x + (-18 if i % 2 == 0 else 18), y0 + 30 + seg * (i + 0.5)))
        pts += [(x, y1 - 30), (x, y1)]
        line(pts)
        if label:
            text(x + 30, (y0 + y1) / 2, label, 26, anchor='lm')

    def cap_h(x0, y, x1, label=None):
        m = (x0 + x1) / 2
        line([(x0, y), (m - 8, y)])
        line([(m + 8, y), (x1, y)])
        line([(m - 8, y - 30), (m - 8, y + 30)], lw + 2)
        line([(m + 8, y - 30), (m + 8, y + 30)], lw + 2)
        if label:
            text(m, y - 42, label, 26, anchor='mb')

    def cap_v(x, y0, y1, label=None, var=False):
        m = (y0 + y1) / 2
        line([(x, y0), (x, m - 8)])
        line([(x, m + 8), (x, y1)])
        line([(x - 32, m - 8), (x + 32, m - 8)], lw + 2)
        line([(x - 32, m + 8), (x + 32, m + 8)], lw + 2)
        if var:
            line([(x - 40, m + 40), (x + 40, m - 40)])
            line([(x + 40, m - 40), (x + 22, m - 36)])
            line([(x + 40, m - 40), (x + 36, m - 22)])
        if label:
            text(x + 48, m, label, 26, anchor='lm')

    def coil_v(x, y0, y1, n=5, side=1, label=None):
        h = (y1 - y0) / n
        for i in range(n):
            d.arc([P(x - 24, y0 + i * h), P(x + 24, y0 + (i + 1) * h)], 270 if side > 0 else 90,
                  90 if side > 0 else 270, fill=255, width=lw)
        if label:
            text(x - 40 * side, (y0 + y1) / 2, label, 26, anchor='rm' if side > 0 else 'lm')

    def ground(x, y):
        line([(x, y), (x, y + 24)])
        for i, w in enumerate((34, 22, 10)):
            line([(x - w, y + 24 + i * 11), (x + w, y + 24 + i * 11)])

    def valve(cx, cy, r, label):
        d.ellipse([P(cx - r, cy - r), P(cx + r, cy + r)], outline=255, width=lw)
        line([(cx - 40, cy - 52), (cx + 40, cy - 52)], lw + 2)                     # plate
        for k in range(-4, 5):                                                     # grid (dashed)
            line([(cx + k * 10 - 3, cy - 6), (cx + k * 10 + 3, cy - 6)])
        line([(cx - 30, cy + 40), (cx - 30, cy + 28), (cx + 30, cy + 28), (cx + 30, cy + 40)])  # cathode
        line([(cx - 22, cy + 70), (cx, cy + 50), (cx + 22, cy + 70)])           # filament
        text(cx + r + 14, cy - r + 10, label, 30, bold=True)

    # border, grid
    for k in range(0, W, 60):
        line([(k, 0), (k, H)], 1 * S, 40)
    for k in range(0, H, 60):
        line([(0, k), (W, k)], 1 * S, 40)
    d.rectangle([P(70, 70), P(W - 70, H - 70)], outline=255, width=5 * S)
    d.rectangle([P(88, 88), P(W - 88, H - 88)], outline=200, width=2 * S)
    text(150, 130, 'RÉCEPTEUR À DEUX LAMPES — TYPE R.36', 58, mono=False, bold=True)
    text(152, 210, 'Schéma de principe  ·  détecteur à réaction + basse fréquence', 30, mono=False)
    # --- the schematic
    yb, yg = 420, 1040
    line([(330, yb), (1980, yb)])
    text(1990, yb, '+ 90 V', 30, bold=True, anchor='lm')
    line([(330, yg), (1980, yg)])
    # antenna and tuned circuit
    line([(330, 300), (330, 560)])
    line([(290, 300), (330, 340), (370, 300)])
    line([(330, 300), (330, 270)])
    text(390, 290, 'ANT.', 28, bold=True)
    coil_v(330, 560, 820, 6, 1, 'L1')
    line([(330, 820), (330, yg)])
    line([(330, 560), (520, 560)])
    cap_v(520, 560, yg, 'C1  500 pF', var=True)
    dot(330, 560)
    dot(520, 560)
    dot(330, yg)
    dot(520, yg)
    # grid leak + capacitor to V1 grid
    cap_h(520, 560, 700, 'C2  250 pF')
    line([(700, 560), (760, 560), (760, 714), (800, 714)])
    resistor_v(700, 560 - 0, 760, None)
    line([(700, 760), (700, 800)])
    text(610, 690, 'R1', 26)
    text(610, 720, '2 MΩ', 26)
    valve(900, 720, 120, 'V1')
    line([(800, 714), (860, 714)])
    # V1 cathode/filament to ground
    line([(870, 760), (870, yg)])
    dot(870, yg)
    # V1 plate -> reaction coil -> headphone transformer -> B+
    line([(900, 668), (900, 600)])
    line([(900, 600), (1080, 600)])
    coil_v(1080, 600, 760, 4, -1, None)
    text(1120, 680, 'L2 réaction', 26)
    line([(1080, 760), (1080, 840)])
    cap_v(1080, 840, yg, 'C3  100 pF', var=True)
    dot(1080, yg)
    resistor(900, 520, 1240, 'R2  50 kΩ')
    line([(900, 520), (900, 600)])
    dot(900, 600)
    line([(1240, 520), (1240, yb)])
    dot(1240, yb)
    # coupling to V2
    cap_h(1240, 520, 1420, 'C4  10 nF')
    line([(1420, 520), (1480, 520), (1480, 714), (1520, 714)])
    resistor_v(1460, 714, yg, 'R3  1 MΩ')
    dot(1460, yg)
    dot(1480, 714)
    valve(1620, 720, 120, 'V2')
    line([(1520, 714), (1580, 714)])
    line([(1590, 760), (1590, yg)])
    dot(1590, yg)
    # output transformer + loudspeaker
    line([(1620, 668), (1620, 600), (1760, 600)])
    coil_v(1760, 600, 820, 5, 1, None)
    line([(1760, 820), (1760, 860), (1700, 860), (1700, yb + 0), (1700, yb)])
    dot(1700, yb)
    line([(1800, 590), (1800, 830)], lw + 1)
    line([(1812, 590), (1812, 830)], lw + 1)
    coil_v(1852, 600, 820, 5, -1, None)
    text(1790, 870, 'T1', 28, bold=True, anchor='mt')
    line([(1852, 600), (1950, 600), (1950, 660)])
    line([(1852, 820), (1950, 820), (1950, 760)])
    d.rectangle([P(1930, 660), P(1970, 760)], outline=255, width=lw)
    line([(1970, 660), (2030, 620), (2030, 800), (1970, 760)])
    text(2050, 710, 'H.P.', 30, bold=True, anchor='lm')
    # batteries
    line([(2100, yb), (2100, 680)])
    for k in range(3):
        y = 680 + k * 40
        line([(2070, y), (2130, y)], lw + 2)
        line([(2085, y + 18), (2115, y + 18)], lw + 4)
    line([(2100, 800), (2100, yg)])
    line([(1980, yb), (2100, yb)])
    line([(1980, yg), (2100, yg)])
    text(2150, 740, 'PILE H.T.', 26, anchor='lm')
    # --- a mechanical side view of a valve with dimensions
    ox, oy = 230, 1100
    line([(ox + 60, oy + 340), (ox + 60, oy + 120), (ox + 80, oy + 60), (ox + 140, oy + 30), (ox + 200, oy + 60),
          (ox + 220, oy + 120), (ox + 220, oy + 340)])
    d.rectangle([P(ox + 50, oy + 340), P(ox + 230, oy + 400)], outline=255, width=lw)
    for k in range(4):
        line([(ox + 80 + k * 40, oy + 400), (ox + 80 + k * 40, oy + 440)])
    line([(ox + 100, oy + 300), (ox + 100, oy + 140), (ox + 180, oy + 140), (ox + 180, oy + 300)], 2 * S, 200)
    line([(ox + 300, oy + 30), (ox + 300, oy + 440)], 2 * S, 220)
    line([(ox + 290, oy + 30), (ox + 310, oy + 30)], 2 * S)
    line([(ox + 290, oy + 440), (ox + 310, oy + 440)], 2 * S)
    text(ox + 320, oy + 235, '112', 28, anchor='lm')
    line([(ox + 60, oy + 480), (ox + 220, oy + 480)], 2 * S, 220)
    text(ox + 140, oy + 492, 'Ø 32', 28, anchor='mt')
    text(ox + 40, oy - 10, 'LAMPE A 409 — vue de profil', 26, anchor='lb')
    # --- notes and title block
    notes = ['NOTES :', '1. Bobines L1/L2 sur mandrin de 40 mm, fil émaillé 3/10.',
             '2. Réaction : ne pas pousser C3 jusqu’à l’accrochage.', '3. Écouteurs ou H.P. 4 000 Ω.']
    for i, s in enumerate(notes):
        text(760, 1180 + i * 46, s, 28, bold=(i == 0))
    bx0, by0, bx1, by1 = 1560, 1350, 2290, 1600
    d.rectangle([P(bx0, by0), P(bx1, by1)], outline=255, width=3 * S)
    for yy in (by0 + 70, by0 + 130, by0 + 190):
        line([(bx0, yy), (bx1, yy)], 2 * S)
    line([(bx0 + 380, by0 + 70), (bx0 + 380, by1)], 2 * S)
    text(bx0 + 20, by0 + 36, 'ATELIER — RADIO-RÉCEPTEURS', 32, bold=True, anchor='lm')
    text(bx0 + 20, by0 + 100, 'Planche n° 3 / 7', 28, anchor='lm')
    text(bx0 + 400, by0 + 100, 'Éch. 1 : 1', 28, anchor='lm')
    text(bx0 + 20, by0 + 160, 'Dessiné : M. L.', 28, anchor='lm')
    text(bx0 + 400, by0 + 160, 'Paris, 1936', 28, anchor='lm')
    text(bx0 + 20, by0 + 220, 'Réf. R36-SP-03', 28, anchor='lm')
    text(bx0 + 400, by0 + 220, 'Vérifié', 28, anchor='lm')

    a = np.asarray(ink.resize((W, H), Image.LANCZOS), np.float32) / 255.0
    rng = np.random.default_rng(5)
    mott = np.asarray(Image.fromarray((rng.random((H // 60 + 2, W // 60 + 2)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255.0
    grain = rng.random((H, W)).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy)) / 160.0
    fade = 1.0 - 0.18 * np.exp(-edge)
    paper = np.array((26, 56, 104), np.float32)[None, None, :] * (0.88 + 0.22 * mott[..., None]) * (0.96 + 0.08 * grain[..., None])
    paper *= fade[..., None]
    paper += np.array((14, 12, 6), np.float32) * (1 - fade[..., None]) * 4
    inkc = np.array((226, 233, 240), np.float32)[None, None, :]
    a = a * (0.78 + 0.22 * mott)[..., :] * (0.9 + 0.1 * grain)
    out = paper * (1 - a[..., None]) + inkc * a[..., None]
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(path)
    return path


# ------------------------------------------------------------------ build
def build(collection=None, front_dressing=True, lamp_power=1.0):
    P = kit5.Prop('arch', collection)
    M = materials()
    _shell(P, M)
    frame, glass, vent, panes = _glazing(P, M)
    _ceiling_services(P, M)
    pend = [_pendant(P, M, n, x, y, zb, D, w, lamp_power) for (n, x, y, zb, D, w) in PENDANTS]
    hinge, leaf, dframe = _door(P, M)
    clight, globe = _corridor(P, M)
    front = dict(print=[], radiator=[])
    if front_dressing:
        r, p = _front(P, M)
        front = dict(print=p, radiator=r)
    lights = [p['light'] for p in pend] + [clight]
    return dict(
        prop=P, door_hinge=hinge, lights=lights, pendants=pend, corridor_light=clight,
        bench_zone=dict(x0=-4.6, x1=-1.7, y0=3.15, y1=3.95, top=0.78, sill_z=SILL, stool=(-3.1, 2.70, 0.52),
                        board=(-3.1, 3.45), iron_x=-2.6, lamp_x=-2.3),
        window=dict(x0=WIN_X0, x1=WIN_X1, sill=SILL, head=HEAD, transoms=TRANSOMS, mullions=MULLIONS,
                    glass_y=GLASS_Y, frame_y=(FR_Y0, FR_Y1), vent=VENT, glass=[glass, vent], frame=frame),
        door=dict(y0=DOOR_Y0, y1=DOOR_Y1, h=DOOR_H, hinge=HINGE, leaf=leaf, frame=dframe,
                  open_95=-math.radians(95)),
        corridor=dict(x0=COR_X0, x1=COR_X1, y0=COR_Y0, y1=COR_Y1, h=COR_H, lamp=CORRIDOR_LAMP, globe=globe),
        room=dict(x0=X0, x1=X1, y0=Y0, y1=Y1, ceiling=CEIL, beams_y=BEAMS_Y, duct=(DUCT_Y, DUCT_Z, DUCT_R)),
        pico_lane=dict(x0=-1.2, x1=4.0, y0=0.8, y1=2.3),
        front=front,
    )
