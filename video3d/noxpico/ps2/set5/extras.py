"""Small props the living builder did not get to: Pico's traces (basketball, skateboard, gym bag) and Bip, Nox's drone.
Same conventions as living.py: built at the origin, standing on Z = 0, front facing -Y."""
import math

import bpy
from mathutils import Vector

import kit5
import mat5


def _m(name, fn):
    m = bpy.data.materials.get(name)
    return m if m is not None else fn(name)


def build_basketball(collection=None):
    P = kit5.Prop('basketball', collection)
    r = 0.119
    ball = _m('ex_ball', lambda n: mat5.leather(n, (196, 92, 40), rough=0.62))
    seam = _m('ex_seam', lambda n: mat5.rubber(n, (22, 20, 18), 0.6))
    P.sphere('ball', r, (0, 0, r), ball, segments=48, rings=24)
    P.torus('seam_h', r * 1.002, 0.0025, (0, 0, r), seam, rot=(0, 0, 0))
    P.torus('seam_v1', r * 1.002, 0.0025, (0, 0, r), seam, rot=(90, 0, 0))
    P.torus('seam_v2', r * 1.002, 0.0025, (0, 0, r), seam, rot=(0, 90, 0))
    for o in P.parts.values():
        if o.type == 'MESH':
            for p in o.data.polygons:
                p.use_smooth = True
    return P


def build_skateboard(collection=None, lean=True):
    """Leaning against a wall: the deck stands on its tail, tilted 12 deg back towards +Y (the wall)."""
    P = kit5.Prop('skateboard', collection)
    pivot = bpy.data.objects.new('skateboard.pivot', None)
    P.col.objects.link(pivot)
    pivot.parent = P.root
    if lean:
        pivot.location = (0, 0.0, 0.0)
        pivot.rotation_euler = (math.radians(-78), 0, 0)      # deck long axis from +Y to almost vertical
    wood = _m('ex_deck', lambda n: mat5.wood(n, (168, 128, 86), 'Y'))
    grip = _m('ex_grip', lambda n: mat5.matte(n, (26, 26, 28), 0.95, 0.04, bump=0.2, scale=40.0))
    alu = mat5.get('aluminium')
    wheel = _m('ex_wheel', lambda n: mat5.plastic(n, (232, 222, 196), 0.5))
    # deck along Y (0.80 m), lying on its tail end at the origin when leaning
    L, Wd = 0.80, 0.205
    P.box('deck', (Wd, L, 0.012), (0, L / 2, 0.06), wood, bevel=0.006, parent=pivot)
    P.box('grip', (Wd - 0.01, L - 0.06, 0.002), (0, L / 2, 0.067), grip, bevel=0.0, parent=pivot)
    for y in (0.17, L - 0.17):
        P.box('baseplate', (0.06, 0.08, 0.012), (0, y, 0.048), alu, bevel=0.002, parent=pivot)
        P.cyl('hanger', 0.012, 0.19, (0, y, 0.030), alu, rot=(0, 90, 0), verts=16, parent=pivot)
        for x in (-0.095, 0.095):
            P.cyl('wheel', 0.027, 0.032, (x, y, 0.030), wheel, rot=(0, 90, 0), verts=24, bevel=0.004, parent=pivot)
    return P


def build_gym_bag(collection=None):
    P = kit5.Prop('gym_bag', collection)
    cloth = _m('ex_bag', lambda n: mat5.fabric(n, (36, 44, 66), 0.85, weave=300.0, sheen=0.3))
    strap = _m('ex_strap', lambda n: mat5.fabric(n, (20, 20, 22), 0.9, weave=500.0, sheen=0.1))
    me = bpy.data.meshes.new('bag')
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((0.52, 0.27, 0.25)), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = P._add('body', me, (0, 0, 0.125), (0, 0, 0), cloth, 0.0)
    sub = ob.modifiers.new('sub', 'SUBSURF')
    sub.levels = sub.render_levels = 2
    # slumped: squash the top a little
    for v in me.vertices:
        if v.co.z > 0:
            v.co.z -= 0.025 * (1 - abs(v.co.x) / 0.26)
    P.torus('handle1', 0.11, 0.008, (0, -0.06, 0.24), strap, rot=(90, 0, 0))
    P.torus('handle2', 0.11, 0.008, (0, 0.06, 0.24), strap, rot=(90, 0, 0))
    P.box('stripe', (0.44, 0.004, 0.028), (0, -0.122, 0.13), _m('ex_stripe', lambda n: mat5.fabric(n, (60, 200, 110), 0.8)), bevel=0)
    return P


def build_bip(collection=None):
    """Bip: a palm-sized drone (12 cm body), rounded white shell, one camera eye with a green ring, four rotor guards."""
    P = kit5.Prop('bip', collection)
    shell = _m('ex_bip_shell', lambda n: mat5.plastic(n, (226, 228, 230), 0.3))
    dark = mat5.get('plastic_black')
    led = _m('ex_bip_led', lambda n: mat5.emissive(n, (70, 255, 140), 6.0))
    P.sphere('body', 0.06, (0, 0, 0.07), shell, scale=(1.0, 1.0, 0.78), segments=40, rings=20)
    P.cyl('eye', 0.026, 0.012, (0, -0.055, 0.075), dark, rot=(90, 0, 0), verts=32, bevel=0.003)
    P.torus('ring', 0.027, 0.0028, (0, -0.0615, 0.075), led, rot=(90, 0, 0))
    P.sphere('lens', 0.012, (0, -0.061, 0.075), _m('ex_bip_lens', lambda n: mat5.ceramic(n, (12, 14, 20), 0.05)))
    for a in (45, 135, 225, 315):
        x, y = math.cos(math.radians(a)) * 0.075, math.sin(math.radians(a)) * 0.075
        P.box('arm', (0.05, 0.012, 0.008), (x * 0.6, y * 0.6, 0.075), shell, rot=(0, 0, a), bevel=0.003)
        P.torus('guard', 0.032, 0.004, (x, y, 0.078), shell)
        P.cyl('rotor', 0.028, 0.002, (x, y, 0.082), dark, verts=24, bevel=0)
    for x, y in ((-0.035, -0.035), (0.035, -0.035), (-0.035, 0.035), (0.035, 0.035)):
        P.cyl('foot', 0.006, 0.02, (x, y, 0.01), dark, verts=12, bevel=0.002)
    P.light('eye_glow', 'POINT', (0, -0.075, 0.075), 0.02, (0.3, 1.0, 0.5), 0.004)
    return P
