"""Night city seen through the loft's back window (version 5 set), built in WORLD coordinates.

The loft floor (z = 0) is the 6th floor: the street is at z = -18.  The loft sits at the top of a steep slope (think
Lyon, Croix-Rousse): across the boulevard there is a block of old workshops and Haussmann-style flats (zinc mansard
roofs, chimneys, balconies), then the roofscape falls away to a river and the far bank climbs a hill covered in a
carpet of small warm lights, with a floodlit basilica and a lattice TV mast on the crest and a cluster of office
towers on the right - the reference's night city: saturated blue-hour sky, dark navy mass, dense small warm lights.

Everything is EMISSION ONLY ("baked" night lighting in the shaders, like a game skybox): no lights, no shadows, one ray
hit per pixel, ~150 k triangles, a few seconds per frame at 576 x 1024.  The city objects are visible to camera / glossy /
transmission rays (seen through the glazing and reflected in glass and polished floors) but NOT to diffuse or shadow
rays: they never block or add noise to the room lighting, which the assembler controls with its world + lights.

Forced perspective: everything beyond the river (the hill, its buildings, the basilica, the mast, the towers) is built
at K = 0.62 scale, so it reads ~1.6x further away than it is (a 2 m camera move inside the room gives no measurable
parallax at that distance anyway).  Everything stays within 355 m of the room origin and the sky dome has a radius of
378 m, so look5.camera (clip_end = 400) never clips it from anywhere in the room.

Layers (azimuth 0 = +Y, distances from the room origin):
    street      y 4..33 below the window: asphalt, sidewalks, curbs, lamp posts, light pools, plane trees, parked cars
    near block  y 34..80: Haussmann flats with mansards and balconies, old workshops (sawtooth skylights) in the
                middle, a side street, water towers, AC units, chimneys, antennas
    roofscape   r 85..165 on the slope down to the river (~300 blocks, many with zinc mansards and lit dormers)
    river       r ~190: dark water with broken reflections, lamp-lined quays, a lit bridge
    far hill    r 215..352 (built at K scale): terrain with procedural street lamps and window lights + ~1500 small
                blocks, a floodlit basilica in its park, a lattice TV mast, office towers on the right
    sky dome    r 378: blue-hour gradient (reference-matched), faint clouds lit from below

    P = city.build(collection=None, strength=1.0)
    P.beacons      -> list of red aviation-light objects (small emissive spheres)
    P.beacon_mats  -> list of (material, phase_s, steady) ; city.animate(P, f0, f1, fps) keys the blinking
    city.blink(t, phase=0.0) -> 0..1 brightness of a flashing beacon at time t (seconds)
    city.SKY_HORIZON, city.SKY_TOP -> linear RGB of the sky (to match a world colour / window fill light)
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils import noise as mnoise

import kit5

STREET = -18.0                  # street level
LOW = -44.0                     # quays
WATER = -46.5
EYE = (-1.5, 0.0, 1.5)          # reference eye for the aerial haze
R_FLAT = 75.0                   # the plateau ends here, the slope starts
R_SLOPE = 150.0                 # bottom of the slope
R_MAX = 352.0
DOME_R = 378.0
AZ0, AZ1 = math.radians(-112), math.radians(112)
RIV_HALF = 22.0
K = 0.62                        # forced-perspective scale beyond the river
CHURCH_AZ, CHURCH_R = -0.30, 326.0
MAST_AZ, MAST_R = 0.24, 334.0

# sky colour by sin(elevation), calibrated so that the AgX render matches the reference frames
# (just above the hill crest ~6 deg: sRGB 23,65,115, then 15,39,88 ; 12,29,72 ; 10,26,64 within ~10 deg; the
# reference's bright band sits right above the far hills, so the ramp is shifted up by the crest height)
SKY_STOPS = [(0.000, (0.0140, 0.050, 0.170)), (0.060, (0.0160, 0.058, 0.205)), (0.110, (0.0160, 0.058, 0.208)),
             (0.150, (0.0150, 0.048, 0.185)), (0.195, (0.0125, 0.022, 0.100)), (0.245, (0.0085, 0.0115, 0.064)),
             (0.290, (0.0068, 0.0088, 0.051)), (0.420, (0.0055, 0.0062, 0.037)), (0.650, (0.0047, 0.0046, 0.028)),
             (1.000, (0.0042, 0.0038, 0.024))]
SKY_HORIZON = SKY_STOPS[2][1]
SKY_TOP = SKY_STOPS[-1][1]
HAZE = (0.0030, 0.0052, 0.016)


# ------------------------------------------------------------------ terrain
def smooth(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def r_river(az):
    return 190.0 + 8.0 * math.sin(2.3 * az + 0.7)


def crest(az):
    return (22.0 + 10.0 * (0.5 + 0.5 * math.sin(1.7 * az + 0.9)) + 6.0 * (0.5 + 0.5 * math.sin(4.3 * az + 2.3))
            + 13.0 * math.exp(-((az - CHURCH_AZ) / 0.16) ** 2) + 6.0 * math.exp(-((az - MAST_AZ) / 0.10) ** 2))


def ground(x, y):
    r = math.hypot(x, y)
    az = math.atan2(x, y)
    rr = r_river(az)
    a, b = rr - RIV_HALF, rr + RIV_HALF
    if r < a - 2:
        return STREET + (LOW - STREET) * smooth(R_FLAT, R_SLOPE, r)
    if r < a:
        return LOW
    if r < b:
        return LOW - 6.0
    if r < b + 5:
        return LOW
    s = (r - (b + 5)) / (338.0 - (b + 5))
    s = min(1.0, max(0.0, s))
    return LOW + (crest(az) - LOW) * (s * s * (3 - 2 * s)) ** 0.8


# ------------------------------------------------------------------ shader graph helper
class NB:
    """Small node-graph builder: arithmetic on sockets or numbers, emission-only output."""

    def __init__(self, name):
        self.m = bpy.data.materials.new(name)
        try:
            self.m.use_nodes = True
        except Exception:
            pass
        self.nt = self.m.node_tree
        self.nt.nodes.clear()
        self.out = self.nt.nodes.new('ShaderNodeOutputMaterial')
        try:
            self.m.cycles.emission_sampling = 'NONE'
        except Exception:
            pass
        self.geo = self.nt.nodes.new('ShaderNodeNewGeometry')

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def _set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif isinstance(v, (tuple, list)):
            n = len(sock.default_value)
            v = tuple(v)[:n]
            sock.default_value = v + (1.0,) * (n - len(v))
        elif hasattr(sock.default_value, '__len__'):
            n = len(sock.default_value)
            sock.default_value = (v,) * min(n, 3) + (1.0,) * (n - 3)
        else:
            sock.default_value = v

    # scalar math
    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        self._set(n.inputs[0], a)
        self._set(n.inputs[1], b)
        self._set(n.inputs[2], c)
        return n.outputs[0]

    def add(self, a, b): return self.math('ADD', a, b)
    def sub(self, a, b): return self.math('SUBTRACT', a, b)
    def mul(self, a, b): return self.math('MULTIPLY', a, b)
    def div(self, a, b): return self.math('DIVIDE', a, b)
    def mad(self, a, b, c): return self.math('MULTIPLY_ADD', a, b, c)
    def floor(self, a): return self.math('FLOOR', a)
    def fract(self, a): return self.math('FRACT', a)
    def abs(self, a): return self.math('ABSOLUTE', a)
    def lt(self, a, b): return self.math('LESS_THAN', a, b)
    def gt(self, a, b): return self.math('GREATER_THAN', a, b)
    def mn(self, a, b): return self.math('MINIMUM', a, b)
    def mx(self, a, b): return self.math('MAXIMUM', a, b)
    def pw(self, a, b): return self.math('POWER', a, b)
    def exp(self, a): return self.math('EXPONENT', a)
    def sqrt(self, a): return self.math('SQRT', a)
    def sin(self, a): return self.math('SINE', a)
    def cos(self, a): return self.math('COSINE', a)
    def atan2(self, a, b): return self.math('ARCTAN2', a, b)
    def clamp01(self, a): return self.math('ADD', a, 0.0, clamp=True)

    def smooth(self, e0, e1, x):
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        self._set(n.inputs[0], x)
        self._set(n.inputs[1], e0)
        self._set(n.inputs[2], e1)
        n.inputs[3].default_value = 0.0
        n.inputs[4].default_value = 1.0
        return n.outputs[0]

    def remap(self, x, a, b, c, d):
        n = self.node('ShaderNodeMapRange')
        self._set(n.inputs[0], x)
        self._set(n.inputs[1], a)
        self._set(n.inputs[2], b)
        self._set(n.inputs[3], c)
        self._set(n.inputs[4], d)
        return n.outputs[0]

    # vectors / colours (colours are plain linear RGB vectors)
    def vmath(self, op, a, b=(0, 0, 0), scale=None):
        n = self.node('ShaderNodeVectorMath', operation=op)
        self._set(n.inputs[0], a)
        self._set(n.inputs[1], b)
        if scale is not None:
            self._set(n.inputs[3], scale)
        return n

    def vadd(self, a, b): return self.vmath('ADD', a, b).outputs[0]
    def vmul(self, a, b): return self.vmath('MULTIPLY', a, b).outputs[0]
    def vscale(self, a, s): return self.vmath('SCALE', a, scale=s).outputs[0]
    def length(self, a): return self.vmath('LENGTH', a).outputs[1]
    def normalize(self, a): return self.vmath('NORMALIZE', a).outputs[0]

    def flerp(self, f, a, b):
        n = self.node('ShaderNodeMix', data_type='FLOAT')
        self._set(n.inputs[0], f)
        self._set(n.inputs[2], a)
        self._set(n.inputs[3], b)
        return n.outputs[0]

    def lerp(self, f, a, b):
        n = self.node('ShaderNodeMix', data_type='VECTOR')
        self._set(n.inputs[0], f)
        self._set(n.inputs[4], a)
        self._set(n.inputs[5], b)
        return n.outputs[1]

    def sep(self, v):
        n = self.node('ShaderNodeSeparateXYZ')
        self._set(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x, y, z):
        n = self.node('ShaderNodeCombineXYZ')
        self._set(n.inputs[0], x)
        self._set(n.inputs[1], y)
        self._set(n.inputs[2], z)
        return n.outputs[0]

    def attr(self, name):
        n = self.node('ShaderNodeAttribute', attribute_name=name, attribute_type='GEOMETRY')
        return n.outputs[2]

    def noise(self, vec, scale, detail=3.0, rough=0.55, dims='3D'):
        n = self.node('ShaderNodeTexNoise', noise_dimensions=dims)
        self._set(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        return n.outputs[0]

    def white(self, vec, w=None):
        n = self.node('ShaderNodeTexWhiteNoise', noise_dimensions='4D' if w is not None else '3D')
        self._set(n.inputs['Vector'], vec)
        if w is not None:
            self._set(n.inputs['W'], w)
        r, g, b = self.sep(n.outputs[1])
        return n.outputs[0], r, g, b

    def voronoi(self, vec, scale, dims='2D'):
        n = self.node('ShaderNodeTexVoronoi', voronoi_dimensions=dims, feature='F1', distance='EUCLIDEAN')
        self._set(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        return n.outputs[0], n.outputs[1]

    def dist_eye(self):
        return self.length(self.vmath('SUBTRACT', self.geo.outputs['Position'], EYE).outputs[0])

    def haze(self, col, start=45.0, dist=520.0, amount=0.85, color=HAZE):
        """Aerial perspective: fade towards the night haze colour with the distance from the window.  Beyond the
        river the geometry is at K scale, so the distance is stretched there to match its apparent distance."""
        d = self.dist_eye()
        d = self.mul(d, self.remap(d, 190.0, 230.0, 1.0, 1.0 / K))
        f = self.mul(self.sub(1.0, self.exp(self.div(self.mx(self.sub(d, start), 0.0), -dist))), amount)
        return self.lerp(f, col, color)

    def emit(self, col, strength=1.0):
        e = self.node('ShaderNodeEmission')
        self._set(e.inputs['Color'], col)
        self._set(e.inputs['Strength'], strength)
        self.nt.links.new(e.outputs[0], self.out.inputs['Surface'])
        return self.m


# ------------------------------------------------------------------ materials
SKY_AMB = (0.016, 0.024, 0.050)          # what a facade receives from the blue-hour sky
STREET_GLOW = (0.20, 0.11, 0.045)        # warm street lighting on the lower floors


def mat_buildings(S=1.0, ewin=2.4):
    B = NB('city_buildings')
    P = B.geo.outputs['Position']
    nx, ny, nz = B.sep(B.geo.outputs['True Normal'])
    uv = B.node('ShaderNodeUVMap', uv_map='UVMap')
    U, V, _ = B.sep(uv.outputs['UV'])
    A = {k: B.attr(k) for k in BATTRS}
    ux = B.div(U, A['ww'])
    cu, fu = B.floor(ux), B.fract(ux)
    vy = B.div(V, A['fh'])
    cv, fv = B.floor(vy), B.fract(vy)
    cell = B.comb(cu, cv, B.mul(A['fid'], 977.0))
    r0, r1, r2, r3 = B.white(cell)
    r4, r5, r6, r7 = B.white(cell, 3.7)
    vert = B.sub(1.0, B.smooth(0.45, 0.75, B.abs(nz)))
    one_mx = B.sub(1.0, A['mx'])
    inx = B.mul(B.gt(fu, A['mx']), B.lt(fu, one_mx))
    iny = B.mul(B.gt(fv, A['my0']), B.lt(fv, A['my1']))
    infl = B.mul(B.lt(cv, A['nf']), B.gt(V, 0.0))
    win = B.mul(B.mul(inx, iny), B.mul(infl, vert))
    lu = B.div(B.sub(fu, A['mx']), B.sub(one_mx, A['mx']))
    lv = B.div(B.sub(fv, A['my0']), B.sub(A['my1'], A['my0']))

    # ---- facade (wall): stone / grey render / ochre / brick / zinc mansard, lit by the sky and the street lamps
    stone, grey, ochre, brick = (0.50, 0.44, 0.36), (0.36, 0.36, 0.35), (0.52, 0.36, 0.21), (0.34, 0.19, 0.13)
    alb = B.lerp(B.smooth(0.28, 0.32, A['tone']), stone, grey)
    alb = B.lerp(B.smooth(0.55, 0.59, A['tone']), alb, ochre)
    alb = B.lerp(B.smooth(0.76, 0.80, A['tone']), alb, brick)
    alb = B.lerp(A['zinc'], alb, (0.20, 0.22, 0.25))
    grime = B.remap(B.noise(P, 0.25, 4.0, 0.6), 0.3, 0.7, 0.72, 1.18)
    streaks = B.remap(B.noise(B.comb(B.mul(U, 3.0), B.mul(V, 0.15), A['fid']), 1.0, 2.0, 0.5), 0.3, 0.7, 0.85, 1.1)
    band = B.add(1.0, B.mul(0.22, B.mul(B.lt(fv, 0.06), B.sub(1.0, A['zinc']))))   # floor slabs / string courses
    face = B.remap(nx, -1.0, 1.0, 1.30, 0.72)                            # the sky is brighter on the left
    face = B.mul(face, B.remap(ny, -1.0, 1.0, 1.0, 0.85))
    face = B.mul(face, B.add(1.0, B.mul(A['zinc'], B.mul(B.mx(nz, 0.0), 2.5))))  # sloping zinc sees more sky
    sky = B.vscale(SKY_AMB, B.mul(B.mul(face, grime), B.mul(band, streaks)))
    # street lamps: pools of warm light on the lower floors, one lamp every ~23 m along the facade
    pool = B.pw(B.add(0.5, B.mul(0.5, B.cos(B.mul(B.add(B.div(U, 23.0), B.mul(A['fid'], 5.3)), 6.2832)))), 3.0)
    vpos = B.mx(V, 0.0)
    st = B.vscale(STREET_GLOW, B.mul(B.mul(A['glow'], B.exp(B.div(vpos, -4.0))), B.mad(pool, 0.75, 0.25)))
    wall = B.vmul(alb, B.vadd(sky, st))
    wall = B.vscale(wall, B.flerp(B.smooth(170.0, 250.0, B.dist_eye()), 1.0, 0.55))   # far facades sink into the night

    # ---- lit window: warm or cool, a ceiling lamp, furniture in silhouette, curtains, French-window mullions
    c_warm = B.lerp(r3, (1.0, 0.44, 0.15), (1.0, 0.64, 0.32))
    c_cool = B.lerp(r3, (0.55, 0.66, 1.0), (0.86, 0.90, 1.0))
    c = B.lerp(B.lt(r2, A['warm']), c_cool, c_warm)
    bright = B.mad(B.mul(r0, r0), 0.85, 0.15)
    grad = B.mad(lv, 0.55, 0.45)
    dlu, dlv = B.sub(lu, B.add(0.35, B.mul(r6, 0.3))), B.sub(lv, 0.97)
    hot = B.mul(B.exp(B.mul(B.add(B.mul(B.mul(dlu, dlu), 14.0), B.mul(B.mul(dlv, dlv), 18.0)), -1.0)), B.gt(r6, 0.35))
    furn = B.sub(1.0, B.mul(B.mul(B.lt(lv, B.mad(r7, 0.28, 0.10)), B.gt(r5, 0.45)), 0.65))
    side = B.smooth(0.0, 0.3, B.mn(lu, B.sub(1.0, lu)))
    curt = B.sub(1.0, B.mul(B.lt(r5, 0.40), B.sub(1.0, B.mad(side, 0.75, 0.25))))
    mull = B.sub(1.0, B.mul(B.mul(A['mull'], B.lt(B.abs(B.sub(lu, 0.5)), 0.04)), 0.9))
    mull = B.mul(mull, B.sub(1.0, B.mul(B.mul(A['mull'], B.lt(B.abs(B.sub(lv, 0.74)), 0.03)), 0.85)))
    k = B.mul(B.mul(bright, B.add(grad, B.mul(hot, 1.2))), B.mul(B.mul(curt, mull), B.mul(furn, ewin)))
    litcol = B.vscale(c, k)
    islit = B.lt(r1, A['lit'])
    # dark window: the night sky reflected in the glass, sometimes a dim lamp deep in the flat or a TV
    glass = B.lerp(lv, (0.003, 0.005, 0.012), (0.010, 0.017, 0.040))
    dim = B.mul(B.lt(r1, B.mul(A['lit'], 1.8)), 0.06)
    glass = B.vadd(glass, B.vscale(B.lerp(B.lt(r6, 0.3), (1.0, 0.55, 0.25), (0.35, 0.5, 1.0)), B.mul(dim, B.mul(lv, 1.2))))
    # roller shutters (volets roulants) closed on some dark windows
    slat = B.add(0.82, B.mul(0.18, B.lt(B.fract(B.mul(fv, 22.0)), 0.5)))
    shutter = B.vscale(wall, B.mul(slat, 0.9))
    dark = B.lerp(B.mul(B.lt(r7, A['shut']), B.mul(B.gt(lv, 0.0), 1.0)), glass, shutter)
    wcol = B.lerp(islit, dark, litcol)

    # ---- ground-floor shops: bright shop windows or closed grey shutters
    g0 = B.mul(B.lt(cv, 0.5), B.lt(r4, A['shop']))
    sw = B.mul(B.mul(B.gt(fu, 0.06), B.lt(fu, 0.94)), B.mul(B.gt(fv, 0.10), B.lt(fv, 0.78)))
    sw = B.mul(B.mul(sw, vert), B.gt(V, 0.0))
    sv = B.div(B.sub(fv, 0.10), 0.68)
    shelves = B.sub(1.0, B.mul(B.mul(B.lt(sv, 0.45), B.gt(r7, 0.4)), 0.55))          # counters / displays
    shelves = B.mul(shelves, B.sub(1.0, B.mul(B.lt(B.abs(B.sub(B.fract(B.mul(fu, 3.0)), 0.5)), 0.03), 0.6)))
    shopc = B.vscale(B.lerp(r5, (1.0, 0.62, 0.32), (0.90, 0.88, 0.80)),
                     B.mul(B.mul(B.mad(r3, 0.35, 0.18), ewin), B.mul(shelves, B.mad(sv, 0.5, 0.6))))
    shopc = B.lerp(B.lt(r6, 0.42), shopc, B.vscale((0.05, 0.05, 0.055), B.add(0.8, B.mul(0.2, B.lt(B.fract(B.mul(fv, 30.0)), 0.5)))))

    col = B.lerp(win, wall, wcol)
    col = B.lerp(B.mul(g0, sw), col, shopc)

    # ---- wrought-iron balcony railings (continuous balconies on the 2nd and top floors of the flats)
    onfl = B.clamp01(B.add(B.lt(B.abs(B.sub(cv, 2.0)), 0.5), B.lt(B.abs(B.sub(cv, B.sub(A['nf'], 1.0))), 0.5)))
    isb = B.mul(B.mul(A['balc'], onfl), B.mul(B.mul(vert, infl), B.gt(cv, 1.5)))
    rb = B.mul(B.gt(fv, B.sub(A['my0'], 0.03)), B.lt(fv, B.add(A['my0'], 0.31)))
    bars = B.mx(B.lt(B.fract(B.mul(U, 7.0)), 0.30), B.lt(B.abs(B.sub(fv, B.add(A['my0'], 0.29))), 0.025))
    bars = B.mx(bars, B.mul(B.lt(B.abs(B.sub(B.fract(B.mul(U, 1.4)), 0.5)), 0.12), 0.6))     # scrollwork panels
    col = B.lerp(B.mul(B.mul(isb, rb), B.mul(bars, 0.92)), col, (0.004, 0.004, 0.005))

    # ---- roofs: gravel / membrane / zinc reflecting the sky
    roof = B.vscale((0.008, 0.011, 0.020), B.remap(B.noise(P, 0.4, 3.0), 0.3, 0.7, 0.6, 1.3))
    col = B.lerp(B.smooth(0.75, 0.9, nz), col, roof)
    return B.emit(B.haze(col), S)


def mat_ground(S=1.0, elamp=6.0, edot=5.0, church=(0.0, 0.0)):
    """Terrain under the city: dark ground, street lamps on rotated grids (dotted lines + pools), random lights,
    dark parks (one around the basilica)."""
    B = NB('city_ground')
    P = B.geo.outputs['Position']
    x, y, _ = B.sep(P)
    nz = B.sep(B.geo.outputs['True Normal'])[2]
    r = B.sqrt(B.add(B.mul(x, x), B.mul(y, y)))
    far = B.smooth(200.0, 225.0, r)
    sc = B.flerp(far, 1.0, K)                                  # forced perspective beyond the river
    Q = B.vscale(P, B.div(1.0, sc))
    dist = B.noise(Q, 1 / 90.0, 2.0, 0.5)
    dens = B.remap(dist, 0.34, 0.64, 0.15, 0.95)
    park = B.smooth(0.30, 0.38, B.noise(B.vadd(Q, (500, 200, 0)), 1 / 55.0, 2.0, 0.5))
    cx, cy = church
    dcx, dcy = B.sub(x, cx), B.sub(y, cy)
    dch = B.sqrt(B.add(B.mul(dcx, dcx), B.mul(dcy, dcy)))
    park = B.mul(park, B.smooth(42.0, 75.0, dch))
    dens = B.mul(dens, park)
    # random small lights (windows, courtyards, cars)
    d, colr = B.voronoi(Q, 1 / 5.0)
    a, b, c = B.sep(colr)
    dot = B.sub(1.0, B.smooth(0.05, 0.12, d))
    on = B.lt(a, dens)
    dcol = B.lerp(B.lt(b, 0.60), B.lerp(B.lt(b, 0.85), (0.72, 0.82, 1.0), (1.0, 0.42, 0.12)), (1.0, 0.62, 0.30))
    dots = B.vscale(dcol, B.mul(B.mul(dot, on), B.mul(B.mad(B.mul(c, c), 0.8, 0.2), edot)))

    # street lamps: two districts with differently rotated street grids
    def lattice(q, sx, sy):
        qx, qy, _ = B.sep(q)
        dx = B.mul(B.sub(B.fract(B.add(B.div(qx, sx), 0.5)), 0.5), sx)
        dy = B.mul(B.sub(B.fract(B.add(B.div(qy, sy), 0.5)), 0.5), sy)
        dl2 = B.add(B.mul(dx, dx), B.mul(dy, dy))
        lamp = B.sub(1.0, B.smooth(0.10, 0.45, dl2))
        pool = B.exp(B.div(dl2, -2 * 6.5 ** 2))
        return lamp, pool

    def grid(angle):
        rot = B.node('ShaderNodeVectorRotate', rotation_type='Z_AXIS')
        B._set(rot.inputs['Vector'], Q)
        rot.inputs['Angle'].default_value = angle
        q = rot.outputs[0]
        l1, p1 = lattice(q, 52.0, 22.0)
        l2, p2 = lattice(B.vadd(q, (11.0, 26.0, 0)), 22.0, 52.0)
        return B.mx(l1, l2), B.mx(p1, p2)

    la, pa = grid(0.30)
    lb, pb = grid(-0.55)
    dm = B.smooth(0.48, 0.52, B.noise(B.vadd(Q, (37, 91, 0)), 1 / 140.0, 1.0, 0.5))
    pathl = B.add(0.25, B.mul(0.75, park))                      # a few lamps along the paths in the parks
    lamps = B.mul(B.flerp(dm, la, lb), pathl)
    pools = B.mul(B.flerp(dm, pa, pb), pathl)
    sod = B.lerp(B.smooth(0.4, 0.6, B.noise(Q, 1 / 70.0, 1.0)), (1.0, 0.45, 0.13), (1.0, 0.70, 0.42))
    trees = B.remap(B.noise(Q, 0.12, 4.0, 0.6), 0.3, 0.7, 0.45, 1.25)
    base = B.vscale((0.0040, 0.0050, 0.0085), B.flerp(park, trees, B.remap(B.noise(Q, 0.05, 3.0), 0.3, 0.7, 0.7, 1.3)))
    glow = B.vscale(sod, B.add(B.mul(pools, 0.028), B.mul(dens, 0.0035)))
    col = B.vadd(B.vadd(base, glow), B.vadd(dots, B.vscale(sod, B.mul(lamps, elamp))))
    col = B.lerp(B.smooth(-0.2, 0.3, nz), B.vscale(base, 0.6), col)       # quay walls stay dark
    return B.emit(B.haze(col), S)


def mat_water(S=1.0):
    """River: dark water reflecting the sky, with broken vertical reflections of the far-bank lights."""
    B = NB('city_water')
    P = B.geo.outputs['Position']
    x, y, _ = B.sep(B.vmath('SUBTRACT', P, EYE).outputs[0])
    az = B.atan2(x, y)
    r = B.sqrt(B.add(B.mul(x, x), B.mul(y, y)))
    q = B.comb(B.mul(az, 900.0), B.div(r, 3.0), 0.0)
    streak = B.smooth(0.60, 0.74, B.noise(q, 1.0, 2.0, 0.5))
    rip = B.remap(B.noise(B.comb(B.mul(az, 2000.0), B.mul(r, 1.4), 0.0), 1.0, 2.0, 0.6), 0.3, 0.7, 0.4, 1.4)
    near_bank = B.smooth(r_river(0) - 6, r_river(0) + 18, r)
    refl = B.vscale((1.0, 0.55, 0.22), B.mul(B.mul(streak, rip), B.mul(near_bank, 0.9)))
    col = B.vadd(B.vscale((0.008, 0.020, 0.055), rip), refl)
    return B.emit(B.haze(col), S)


def mat_sky(S=1.0):
    """Dome: saturated blue-hour gradient (sampled from the reference frames), a faint light dome over the city at
    the horizon, very faint clouds lit from below."""
    B = NB('city_sky')
    P = B.geo.outputs['Position']
    D = B.normalize(B.vmath('SUBTRACT', P, EYE).outputs[0])
    dx, dy, e = B.sep(D)
    ramp = B.node('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'LINEAR'
    B._set(ramp.inputs[0], e)
    stops = SKY_STOPS
    els = ramp.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for el, (p, c) in zip(els, stops):
        el.position = p
        el.color = tuple(c) + (1.0,)
    col = ramp.outputs[0]
    # the city's light dome hugging the horizon (very slightly warm)
    lp = B.exp(B.div(B.mx(e, 0.0), -0.045))
    col = B.vadd(col, B.vscale((0.010, 0.010, 0.012), lp))
    # clouds: noise projected on a plane above the city, stretched, lit by the city from below near the horizon
    hh = B.mx(e, 0.03)
    cp = B.comb(B.div(dx, hh), B.mul(B.div(dy, hh), 2.6), 0.0)
    cl = B.smooth(0.50, 0.78, B.noise(cp, 0.45, 5.0, 0.62))
    cl = B.mul(cl, B.smooth(0.02, 0.10, e))
    lit_by_city = B.lerp(B.smooth(0.05, 0.4, e), (0.020, 0.040, 0.105), (0.006, 0.016, 0.052))
    col = B.lerp(B.mul(cl, 0.35), col, lit_by_city)
    return B.emit(col, S)


def mat_fake(name, albedo, S=1.0, under=(0.0, 0.0, 0.0), emit=None, haze=True, clumps=0.0, top=(0.0, 0.0, 0.0)):
    """Unlit-but-shaded surface for props (rooftop gear, trees, cars): sky light from above / the left, optional warm
    light from below (street lamps) or from above (top), optional leafy clumps (dark gaps)."""
    B = NB(name)
    nx, ny, nz = B.sep(B.geo.outputs['True Normal'])
    P = B.geo.outputs['Position']
    g = B.remap(B.noise(P, 1.3, 3.0), 0.3, 0.7, 0.75, 1.2)
    if clumps:
        d, _ = B.voronoi(P, clumps, '3D')
        g = B.mul(g, B.remap(d, 0.15, 0.75, 1.15, 0.35))
    up = B.mad(nz, 0.35, 0.75)
    side = B.remap(nx, -1.0, 1.0, 1.3, 0.75)
    sky = B.vscale(SKY_AMB, B.mul(B.mul(up, side), g))
    low = B.vscale(under, B.mul(B.mx(B.sub(0.0, nz), 0.0), g))
    hi = B.vscale(top, B.mul(B.mx(nz, 0.0), g))
    col = B.vmul(albedo, B.vadd(B.vadd(sky, low), hi))
    if emit is not None:
        col = B.vadd(col, emit)
    return B.emit(B.haze(col) if haze else col, S)


def mat_glow(name, rgb, strength, S=1.0, haze=True):
    B = NB(name)
    col = B.haze(rgb, amount=0.5) if haze else rgb
    return B.emit(col, strength * S)


def mat_car(S=1.0):
    """Parked cars under the street lamps: body colour per car (attribute cc), dark glass with a sky reflection,
    warm lamp light on the roof / bonnet, a little light from below."""
    B = NB('city_car')
    nx, ny, nz = B.sep(B.geo.outputs['True Normal'])
    P = B.geo.outputs['Position']
    z = B.sep(P)[2]
    cc, base, lamp = B.attr('cc'), B.attr('base'), B.attr('lamp')
    h = B.sub(z, base)
    pal = [(0.02, 0.02, 0.022), (0.30, 0.31, 0.33), (0.70, 0.70, 0.68), (0.05, 0.08, 0.16), (0.32, 0.04, 0.03),
           (0.45, 0.46, 0.48), (0.10, 0.11, 0.10)]
    alb = pal[0]
    for i, c in enumerate(pal[1:], 1):
        alb = B.lerp(B.gt(cc, i / len(pal)), alb, c)
    light = B.vadd(B.vscale(SKY_AMB, B.mad(nz, 0.4, 0.8)),
                   B.vscale((0.075, 0.050, 0.024), B.mul(B.mx(nz, 0.0), B.mad(lamp, 0.9, 0.1))))
    light = B.vadd(light, B.vscale((0.05, 0.032, 0.016), B.mx(B.sub(0.0, nz), 0.0)))
    body = B.vmul(alb, light)
    # paint gloss: a soft warm sheen on the upper body
    body = B.vadd(body, B.vscale((0.012, 0.008, 0.004), B.mul(B.smooth(0.3, 0.9, nz), lamp)))
    gl = B.mul(B.gt(h, 0.93), B.lt(nz, 0.92))
    glass = B.vadd(B.vscale((0.006, 0.010, 0.022), B.mad(nz, 0.8, 0.6)),
                   B.vscale((0.30, 0.20, 0.10), B.mul(B.mul(lamp, B.smooth(0.5, 0.8, nz)), 0.15)))
    col = B.lerp(gl, body, glass)
    tyre = B.lt(h, 0.30)
    col = B.lerp(B.mul(tyre, 0.9), col, (0.003, 0.003, 0.004))
    return B.emit(B.haze(col), S)


def mat_street(S=1.0, lamps=()):
    """The boulevard below the window: asphalt, sidewalks, markings, warm pools under the lamp posts."""
    B = NB('city_street')
    P = B.geo.outputs['Position']
    x, y, _ = B.sep(P)
    side = B.add(B.lt(y, 8.6), B.gt(y, 28.4))
    asph = B.remap(B.noise(P, 1.5, 5.0, 0.6), 0.3, 0.7, 0.045, 0.075)
    patch = B.remap(B.noise(P, 0.15, 2.0, 0.5), 0.3, 0.7, 0.8, 1.15)
    asph = B.mul(asph, patch)
    pav = B.remap(B.noise(P, 3.0, 4.0, 0.6), 0.3, 0.7, 0.16, 0.22)
    tiles = B.mul(B.lt(B.fract(B.mul(x, 2.0)), 0.06), 0.4)
    alb = B.flerp(side, asph, B.mul(pav, B.sub(1.0, tiles)))
    # markings: dashed centre line, parking-lane lines, a zebra crossing at the side street
    dash = B.mul(B.lt(B.abs(B.sub(y, 18.5)), 0.08), B.lt(B.fract(B.div(x, 9.0)), 0.33))
    edge = B.add(B.lt(B.abs(B.sub(y, 11.0)), 0.07), B.lt(B.abs(B.sub(y, 26.0)), 0.07))
    zebra = B.mul(B.mul(B.gt(x, 23.0), B.lt(x, 27.5)), B.mul(B.lt(B.fract(B.div(y, 1.0)), 0.5),
                                                          B.mul(B.gt(y, 9.0), B.lt(y, 28.0))))
    mark = B.mx(B.mx(dash, edge), zebra)
    worn = B.remap(B.noise(B.vscale(P, 4.0), 1.0, 3.0, 0.6), 0.35, 0.65, 0.35, 0.9)
    alb = B.flerp(B.mul(mark, worn), alb, 0.42)
    alb = B.comb(alb, alb, alb)
    light = B.vscale((0.020, 0.024, 0.040), 1.0)
    pool = None
    for (lx, ly) in lamps:
        dx, dy = B.sub(x, lx), B.sub(y, ly)
        p = B.exp(B.div(B.add(B.mul(dx, dx), B.mul(dy, dy)), -2 * 5.5 ** 2))
        pool = p if pool is None else B.add(pool, p)
    if pool is not None:
        light = B.vadd(light, B.vscale((1.0, 0.66, 0.36), B.mul(pool, 0.55)))
    col = B.vmul(alb, light)
    return B.emit(B.haze(col), S)


def mat_skylight(S=1.0):
    """Sawtooth-roof glazing of the old workshop across the street (now studios): wired glass panes in steel
    glazing bars, a few bays lit warm from inside (dimly - it is frosted), the rest reflecting the sky."""
    B = NB('city_skylight')
    uv = B.node('ShaderNodeUVMap', uv_map='UVMap')
    U, V, _ = B.sep(uv.outputs['UV'])
    fu, fv = B.fract(B.div(U, 1.2)), B.fract(B.div(V, 0.82))
    pane = B.mul(B.mul(B.gt(fu, 0.09), B.lt(fu, 0.91)), B.mul(B.gt(fv, 0.10), B.lt(fv, 0.90)))
    r0, r1, r2, _ = B.white(B.comb(B.floor(B.div(U, 1.2)), B.floor(B.div(V, 0.82)), 3.0))
    zone = B.white(B.comb(B.floor(B.div(U, 7.2)), B.attr('row'), 1.0))[0]
    on = B.lt(zone, 0.35)
    fall = B.remap(V, 0.0, 2.5, 1.0, 0.55)                         # lamps hang low: brighter at the bottom
    zr = B.white(B.comb(B.floor(B.div(U, 7.2)), B.attr('row'), 5.0))[0]
    on = B.lt(zone, 0.22)
    lampx = B.sub(B.fract(B.div(U, 3.6)), 0.5)                      # pendant lamps hanging inside, every 3.6 m
    hot = B.exp(B.mul(B.add(B.mul(B.mul(lampx, lampx), 40.0), B.mul(B.mul(V, V), 0.6)), -1.0))
    k = B.mul(B.mul(on, pane), B.mul(B.mad(r0, 0.10, 0.90), B.add(B.mul(fall, 0.45), B.mul(hot, 1.3))))
    k = B.mul(k, B.sub(1.0, B.mul(B.lt(r2, 0.10), 0.7)))           # some panes painted over / boarded
    col = B.vscale(B.lerp(zr, (1.0, 0.50, 0.20), (1.0, 0.66, 0.38)), B.mul(k, 2.0))
    skyref = B.vscale((0.0035, 0.0055, 0.0140), B.mad(B.add(r0, B.mul(V, 0.3)), 0.25, 0.75))
    col = B.vadd(col, B.vmul(skyref, B.comb(pane, pane, pane)))
    return B.emit(B.haze(col), S)


def mat_church(S=1.0):
    """Floodlit pale stone basilica (projectors at the foot of the walls), dark arched windows with a faint warm
    glow, cornices, dark roofs, a gilded statue.  Window sizes are in K-scaled metres."""
    B = NB('city_church')
    P = B.geo.outputs['Position']
    nx, ny, nz = B.sep(B.geo.outputs['True Normal'])
    z = B.sep(P)[2]
    base, kind = B.attr('base'), B.attr('kind')
    uv = B.node('ShaderNodeUVMap', uv_map='UVMap')
    U, V, _ = B.sep(uv.outputs['UV'])
    h = B.div(B.sub(z, base), K)                                   # metres in the unscaled model
    u = B.div(U, K)
    flood = B.add(B.mul(B.exp(B.div(B.mx(h, 0.0), -9.0)), 1.0), 0.45)
    flood = B.mul(flood, B.smooth(-18.0, 1.0, h))                 # the retaining wall fades into the dark below
    vd = B.normalize(B.vmath('SUBTRACT', EYE, P).outputs[0])
    facing = B.mx(B.vmath('DOT_PRODUCT', vd, B.geo.outputs['True Normal']).outputs[1], 0.0)
    face = B.mul(B.remap(nx, -1.0, 1.0, 1.1, 0.9), B.mad(facing, 0.75, 0.25))
    stone = B.remap(B.noise(P, 0.9, 3.0), 0.3, 0.7, 0.85, 1.08)
    kk = B.mul(B.mul(flood, face), B.mul(stone, B.flerp(B.gt(kind, 3.5), 0.40, 0.08)))
    col = B.vscale((1.0, 0.86, 0.68), kk)
    # cornices / string courses: thin bright lines with a dark shadow line under them
    for hc in (15.5, 22.0):
        dl = B.sub(h, hc)
        col = B.vscale(col, B.sub(1.0, B.mul(B.mul(B.gt(dl, -0.9), B.lt(dl, 0.0)), 0.45)))
    # tall arched windows on the walls (kind 0): every 5.2 m, 1.7 m wide, from 4.5 m to 13 m with a round head
    fu = B.sub(B.fract(B.div(u, 5.2)), 0.5)
    ax = B.abs(B.mul(fu, 5.2))
    rect = B.mul(B.mul(B.lt(ax, 0.85), B.gt(h, 4.5)), B.lt(h, 12.2))
    dh = B.sub(h, 12.2)
    arch = B.mul(B.lt(B.add(B.mul(ax, ax), B.mul(dh, dh)), 0.85 * 0.85), B.gt(dh, 0.0))
    w_wall = B.mul(B.mx(rect, arch), B.lt(kind, 0.5))
    # tower slits (kind 1): one per octagon face, 0.8 m wide, from 18 to 26 m (belfry openings)
    fu2 = B.abs(B.sub(B.fract(B.div(u, 3.83)), 0.5))
    w_tow = B.mul(B.mul(B.lt(fu2, 0.13), B.mul(B.gt(h, 17.0), B.lt(h, 25.0))), B.mul(B.gt(kind, 0.5), B.lt(kind, 1.5)))
    w_tow = B.mx(w_tow, B.mul(B.mul(B.lt(fu2, 0.08), B.mul(B.gt(h, 7.0), B.lt(h, 11.0))),
                              B.mul(B.gt(kind, 0.5), B.lt(kind, 1.5))))
    wv = B.mul(B.mx(w_wall, w_tow), B.lt(B.abs(nz), 0.5))
    glow_in = B.vscale((0.05, 0.028, 0.012), B.remap(B.noise(P, 2.0, 2.0), 0.3, 0.7, 0.3, 1.2))
    col = B.lerp(B.mul(wv, 0.94), col, glow_in)
    # roofs (kind 2): dark slate/copper catching a little floodlight at the eaves; statue (kind 3): gilded
    roofc = B.vscale((0.030, 0.034, 0.042), B.add(0.6, B.mul(B.exp(B.div(B.sub(h, 22.0), -2.0)), 1.5)))
    col = B.lerp(B.mul(B.gt(kind, 1.5), B.lt(kind, 2.5)), col, roofc)
    col = B.lerp(B.mul(B.gt(kind, 2.5), B.lt(kind, 3.5)), col, B.vscale((1.0, 0.70, 0.30), B.mul(face, 1.4)))
    return B.emit(B.haze(col, amount=0.6), S)


# ------------------------------------------------------------------ mesh accumulation
class Acc:
    """Accumulate many small meshes into one object (one material), with per-face float attributes and a UV map."""

    def __init__(self, attrs=()):
        self.v, self.f, self.uv = [], [], []
        self.attrs = {a: [] for a in attrs}
        self.smooth = []

    def add(self, verts, faces, fattrs=None, uvs=None, smooth=False):
        base = len(self.v)
        self.v.extend(tuple(p) for p in verts)
        for i, f in enumerate(faces):
            self.f.append(tuple(base + j for j in f))
            fa = fattrs(i) if callable(fattrs) else (fattrs or {})
            for a in self.attrs:
                self.attrs[a].append(float(fa.get(a, 0.0)))
            if uvs is not None:
                self.uv.extend(uvs[i])
            else:
                self.uv.extend([(0.0, 0.0)] * len(f))
            self.smooth.append(smooth)

    def add_bm(self, bm, fattrs=None, uvfn=None, smooth=False):
        bm.verts.index_update()
        bm.faces.index_update()
        bm.normal_update()
        verts = [v.co.copy() for v in bm.verts]
        faces, uvs, fas = [], [], []
        for f in bm.faces:
            faces.append([v.index for v in f.verts])
            uvs.append(uvfn(f) if uvfn else [(0.0, 0.0)] * len(f.verts))
            fas.append(fattrs(f) if callable(fattrs) else (fattrs or {}))
        self.add(verts, faces, lambda i: fas[i], uvs, smooth)

    def build(self, name, mat, P):
        if not self.f:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        for a, vals in self.attrs.items():
            at = me.attributes.new(a, 'FLOAT', 'FACE')
            at.data.foreach_set('value', vals)
        uvl = me.uv_layers.new(name='UVMap')
        flat = [c for uv in self.uv for c in uv]
        uvl.data.foreach_set('uv', flat)
        me.polygons.foreach_set('use_smooth', self.smooth)
        me.validate()
        me.materials.append(mat)
        ob = bpy.data.objects.new(f'city.{name}', me)
        P.col.objects.link(ob)
        ob.parent = P.root
        P.parts[name] = ob
        return ob


BATTRS = ('fid', 'fh', 'ww', 'nf', 'lit', 'mx', 'my0', 'my1', 'tone', 'warm', 'shop', 'glow', 'mull', 'shut',
          'zinc', 'balc')


def box_bm(w, d, h, bevel=0.0, seg=1):
    """A box w (x) by d (y) by h (z) standing on z = 0, centred on x/y; optional bevel of the vertical/top edges."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(w, d, h), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
    if bevel > 0:
        edges = [e for e in bm.edges if not all(v.co.z < 1e-4 for v in e.verts)]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=seg, affect='EDGES', profile=0.5)
    return bm


def frustum_bm(w, d, h, inset_x, inset_y=None):
    """A mansard / hip block: bottom w x d at z = 0, top inset, no bottom face."""
    iy = inset_x if inset_y is None else inset_y
    bm = bmesh.new()
    hw, hd = w / 2, d / 2
    tw, td = max(0.05, hw - inset_x), max(0.05, hd - iy)
    vs = [bm.verts.new(p) for p in ((-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
                                     (-tw, -td, h), (tw, -td, h), (tw, td, h), (-tw, td, h))]
    for f in ((0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)):
        bm.faces.new([vs[i] for i in f])
    bm.normal_update()
    return bm


def facade_uv(base_z):
    """UV in metres: U along the face (starting at 0 at its left edge), V = height above base_z."""
    def fn(f):
        n = f.normal
        if abs(n.z) > 0.5:
            return [(v.co.x, v.co.y) for v in f.verts]
        t = Vector((-n.y, n.x, 0.0))
        if t.length < 1e-6:
            t = Vector((1, 0, 0))
        t.normalize()
        us = [v.co.dot(t) for v in f.verts]
        u0 = min(us)
        return [(u - u0, v.co.z - base_z) for u, v in zip(us, f.verts)]
    return fn


def _facade_attrs(common, bid, wwt, kmin=2.0):
    def fa(f):
        a = dict(common)
        a['fid'] = (bid + 0.137 * f.index) % 1.0
        n = f.normal
        if abs(n.z) < 0.5:
            t = Vector((-n.y, n.x, 0.0)).normalized()
            us = [v.co.dot(t) for v in f.verts]
            W = max(us) - min(us)
            if W < kmin:
                a['nf'] = 0.0
                a['ww'] = 1.0
            else:
                k = max(1, round(W / wwt))
                a['ww'] = W / k
        else:
            a['ww'] = 1.0
        return a
    return fa


def window_style(rng, kind, k=1.0):
    if kind == 'res':
        wwt, mxv, y0, y1 = rng.uniform(2.5, 3.2), rng.uniform(0.27, 0.33), rng.uniform(0.18, 0.24), rng.uniform(0.80, 0.86)
        warm, mull, shut, litf = 0.9, 1.0, rng.uniform(0.2, 0.45), rng.uniform(0.18, 0.40)
    elif kind == 'office':
        wwt, mxv, y0, y1 = rng.uniform(1.5, 1.9), rng.uniform(0.03, 0.06), rng.uniform(0.22, 0.30), rng.uniform(0.88, 0.94)
        warm, mull, shut, litf = 0.25, 0.0, 0.0, rng.uniform(0.05, 0.22)
    else:
        wwt, mxv, y0, y1 = rng.uniform(3.8, 5.0), rng.uniform(0.08, 0.14), rng.uniform(0.35, 0.45), rng.uniform(0.82, 0.88)
        warm, mull, shut, litf = 0.6, 0.0, 0.0, rng.uniform(0.1, 0.3)
    return wwt * k, dict(mx=mxv, my0=y0, my1=y1, warm=warm, mull=mull, shut=shut, lit=litf)


def add_building(acc, rng, cx, cy, ang, w, d, nf, fh, base_z, ground_z, kind='res', near=False, extra_h=None,
                 bevel=0.0, lit=None, height=None, k=1.0, balc=0.0, glow=None, tone=None):
    """A building block: box with per-face window parameters.  kind: 'res' (French windows, shutters), 'office'
    (ribbon windows, cool light), 'ind' (big industrial windows).  k scales the window grid (forced perspective).
    Returns its roof height."""
    h = (ground_z - base_z) + nf * fh + (extra_h if extra_h is not None else rng.uniform(0.6, 1.4) * k)
    if height is not None:
        h = height
    bm = box_bm(w, d, h, bevel)
    M = Matrix.Translation((cx, cy, base_z)) @ Matrix.Rotation(ang, 4, 'Z')
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    bm.normal_update()
    wwt, st = window_style(rng, kind, k)
    if lit is not None:
        st['lit'] = lit
    common = dict(fh=fh, nf=nf, tone=rng.random() if tone is None else tone,
                  shop=0.0 if kind == 'ind' else (0.55 if near else 0.45), glow=(1.0 if near else 0.6) if glow is None else glow,
                  zinc=0.0, balc=balc, **st)
    acc.add_bm(bm, _facade_attrs(common, rng.random(), wwt, 2.0 * k), facade_uv(ground_z))
    bm.free()
    return base_z + h


def add_mansard(acc, rng, cx, cy, ang, w, d, z0, h=2.9, inset=1.15, lit=None, k=1.0):
    """Zinc mansard roof (Paris / Lyon) on top of a block: sloping sides with lit dormer windows, flat top."""
    bm = frustum_bm(w, d, h, inset)
    M = Matrix.Translation((cx, cy, z0)) @ Matrix.Rotation(ang, 4, 'Z')
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    bm.normal_update()
    common = dict(fh=h, nf=1.0, tone=0.5, shop=0.0, glow=0.0, zinc=1.0, balc=0.0, mx=rng.uniform(0.33, 0.38),
                  my0=0.16, my1=0.74, warm=0.92, mull=0.0, shut=0.15,
                  lit=(rng.uniform(0.12, 0.35) if lit is None else lit))
    acc.add_bm(bm, _facade_attrs(common, rng.random(), rng.uniform(2.6, 3.2) * k, 2.0 * k), facade_uv(z0))
    bm.free()
    return z0 + h


# ------------------------------------------------------------------ rooftop / street props (simple meshes)
def bm_to_acc(acc, bm, M, smooth=False, fattrs=None, uvfn=None):
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    acc.add_bm(bm, fattrs, uvfn, smooth=smooth)
    bm.free()


def cyl_bm(r, h, n=16, r2=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=n, radius1=r, radius2=r if r2 is None else r2,
                          depth=h)
    bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
    return bm


def water_tower(metal, wood, x, y, z, s=1.0, rot=0.0):
    """Classic timber water tank on a steel stand: legs, ring beam, staved tank with hoops, conical roof, ladder."""
    R = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, 'Z') @ Matrix.Scale(s, 4)
    for lx, ly in ((-1.3, -1.3), (1.3, -1.3), (1.3, 1.3), (-1.3, 1.3)):
        bm_to_acc(metal, box_bm(0.22, 0.22, 3.2), R @ Matrix.Translation((lx, ly, 0)))
    for k in (1.1, 2.4):
        for (ax, ay, w, d) in ((0, -1.3, 2.8, 0.12), (0, 1.3, 2.8, 0.12), (-1.3, 0, 0.12, 2.8), (1.3, 0, 0.12, 2.8)):
            bm_to_acc(metal, box_bm(w, d, 0.12), R @ Matrix.Translation((ax, ay, k)))
    bm_to_acc(metal, box_bm(3.2, 3.2, 0.25), R @ Matrix.Translation((0, 0, 3.2)))
    bm_to_acc(wood, cyl_bm(1.85, 4.2, 24), R @ Matrix.Translation((0, 0, 3.45)), smooth=True)
    for k in (0.5, 1.4, 2.3, 3.2, 4.0):
        bm_to_acc(metal, cyl_bm(1.88, 0.07, 24), R @ Matrix.Translation((0, 0, 3.45 + k)), smooth=True)
    bm_to_acc(wood, cyl_bm(2.0, 1.4, 24, r2=0.05), R @ Matrix.Translation((0, 0, 7.65)), smooth=True)
    for k in range(9):
        bm_to_acc(metal, box_bm(0.6, 0.05, 0.05), R @ Matrix.Translation((0, -1.95, 3.6 + k * 0.45)))
    for sx in (-0.3, 0.3):
        bm_to_acc(metal, box_bm(0.05, 0.05, 4.3), R @ Matrix.Translation((sx, -1.95, 3.45)))


def ac_unit(metal, x, y, z, rng, k=1.0):
    w, d, h = rng.uniform(1.4, 2.6) * k, rng.uniform(1.0, 1.6) * k, rng.uniform(0.9, 1.4) * k
    M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rng.choice((0, math.pi / 2)), 4, 'Z')
    bm_to_acc(metal, box_bm(w, d, h, 0.04 * k), M)
    bm_to_acc(metal, cyl_bm(0.42 * k, 0.16 * k, 16), M @ Matrix.Translation((rng.uniform(-0.3, 0.3) * w, 0, h)))


def chimney(brick, metal, x, y, z, rng, k=1.0, ang=0.0):
    """Paris-style chimney stack: a brick block with a cap and a row of terracotta pots."""
    w, d, h = rng.uniform(0.9, 2.2) * k, rng.uniform(0.45, 0.65) * k, rng.uniform(1.0, 2.0) * k
    M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(ang, 4, 'Z')
    bm_to_acc(brick, box_bm(w, d, h, 0.02 * k), M)
    bm_to_acc(brick, box_bm(w + 0.12 * k, d + 0.12 * k, 0.12 * k), M @ Matrix.Translation((0, 0, h)))
    n = max(1, int(w / (0.32 * k)))
    for i in range(n):
        px = (-w / 2 + (i + 0.5) * w / n)
        bm_to_acc(brick, cyl_bm(0.09 * k, rng.uniform(0.35, 0.55) * k, 8, r2=0.07 * k),
                  M @ Matrix.Translation((px, 0, h + 0.12 * k)))


def antenna(metal, beacons, x, y, z, h, mat_beacon):
    bm_to_acc(metal, cyl_bm(0.06, h, 8, r2=0.03), Matrix.Translation((x, y, z)))
    for k in (0.35, 0.6, 0.82):
        bm_to_acc(metal, box_bm(1.1 * (1 - k * 0.5), 0.04, 0.04), Matrix.Translation((x, y, z + h * k)))
    beacons.append((x, y, z + h + 0.15, 0.22, mat_beacon))


def tree_bm(rng, seed, rad=1.0, sub=2):
    """A leafy canopy lump: an icosphere pushed around by 3D noise (irregular, lumpy outline)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=rad)
    off = Vector((seed * 3.1, seed * 1.7, seed * 2.3))
    for v in bm.verts:
        p = v.co / rad
        n1 = mnoise.noise(p * 1.6 + off)
        n2 = mnoise.noise(p * 4.0 + off * 2.0)
        v.co *= 1.0 + 0.30 * n1 + 0.12 * n2
    return bm


def car_bm(L, W, H, style=0):
    """Side profile of a hatchback / saloon / van extruded across its width, wheel arches implied by the tyre band."""
    if style == 0:      # hatchback
        prof = [(-0.50, 0.18), (0.50, 0.18), (0.50, 0.40), (0.48, 0.50), (0.30, 0.57), (0.12, 0.92), (-0.36, 0.96),
                (-0.48, 0.80), (-0.50, 0.62)]
    elif style == 1:    # saloon
        prof = [(-0.50, 0.18), (0.50, 0.18), (0.50, 0.40), (0.47, 0.50), (0.27, 0.56), (0.12, 0.90), (-0.20, 0.92),
                (-0.33, 0.62), (-0.48, 0.58), (-0.50, 0.48)]
    else:               # small van
        prof = [(-0.50, 0.18), (0.50, 0.18), (0.50, 0.45), (0.46, 0.58), (0.36, 0.66), (0.24, 1.00), (-0.50, 1.00)]
    bm = bmesh.new()
    top = [bm.verts.new((x * L, -W / 2, z * H)) for x, z in prof]
    f = bm.faces.new(top)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, W, 0), verts=nv)
    # pinch the greenhouse inwards (tumblehome)
    for v in bm.verts:
        if v.co.z > 0.62 * H:
            v.co.y *= 0.84
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


# ------------------------------------------------------------------ the city
def build(collection=None, strength=1.0, seed=11):
    rng = random.Random(seed)
    S = strength
    P = kit5.Prop('city', collection)
    P.beacons, P.beacon_mats = [], []
    church_xy = (CHURCH_R * math.sin(CHURCH_AZ), CHURCH_R * math.cos(CHURCH_AZ))

    m_bld = mat_buildings(S)
    m_gnd = mat_ground(S, church=church_xy)
    m_wat = mat_water(S)
    m_sky = mat_sky(S)
    m_metal = mat_fake('city_metal', (0.30, 0.31, 0.33), S, under=(0.05, 0.03, 0.015))
    m_wood = mat_fake('city_wood', (0.30, 0.20, 0.13), S, under=(0.04, 0.025, 0.012))
    m_brick = mat_fake('city_brick', (0.34, 0.19, 0.13), S, under=(0.03, 0.02, 0.01))
    m_stone = mat_fake('city_stone', (0.42, 0.40, 0.36), S, under=(0.16, 0.10, 0.05))
    m_tree = mat_fake('city_tree', (0.10, 0.15, 0.07), S, under=(0.30, 0.20, 0.08), clumps=3.2,
                      top=(0.010, 0.014, 0.026))
    m_ftree = mat_fake('city_far_tree', (0.05, 0.07, 0.05), S, clumps=0.5)
    m_trunk = mat_fake('city_trunk', (0.18, 0.15, 0.12), S, under=(0.25, 0.16, 0.08))
    m_car = mat_car(S)
    m_lamp = mat_glow('city_lamp', (1.0, 0.72, 0.45), 18.0, S, haze=False)
    m_sodium = mat_glow('city_sodium', (1.0, 0.50, 0.16), 14.0, S)
    m_sky_l = mat_skylight(S)
    m_church = mat_church(S)
    beacon_mats = []
    for i, (ph, steady) in enumerate(((0.0, False), (0.55, False), (0.95, False), (0.0, True))):
        bmat = mat_glow(f'city_beacon{i}', (1.0, 0.012, 0.004), 3.5, S, haze=False)
        beacon_mats.append(bmat)
        P.beacon_mats.append((bmat, ph, steady))

    bld = Acc(BATTRS)
    metal, wood, brick, stone, trees, ftrees, trunks = Acc(), Acc(), Acc(), Acc(), Acc(), Acc(), Acc()
    cars = Acc(('cc', 'base', 'lamp'))
    lamps_g, sodium_g, sky_l, church = Acc(), Acc(), Acc(('row',)), Acc(('base', 'kind'))
    beacons = []

    # ---------------- street below the window (y 4..33)
    street = Acc()
    xs = [x * 6.0 for x in range(-28, 29)]
    for y0, y1 in ((4.0, 8.6), (8.6, 28.4), (28.4, 33.5)):
        zoff = 0.15 if (y0 == 4.0 or y0 == 28.4) else 0.0
        verts, faces = [], []
        for i, x in enumerate(xs):
            for y in (y0, y1):
                verts.append((x, y, ground(x, y) + zoff))
        for i in range(len(xs) - 1):
            a = 2 * i
            faces.append((a, a + 2, a + 3, a + 1))
        street.add(verts, faces)
    lamp_xy = []
    for i in range(-6, 7):
        for (ly, off, toward) in ((8.2, 0.0, 1), (28.8, 12.0, -1)):
            lx = i * 24.0 + off
            if abs(lx) > 150:
                continue
            gz = ground(lx, ly) + 0.15
            bm_to_acc(metal, cyl_bm(0.09, 7.6, 10, r2=0.06), Matrix.Translation((lx, ly, gz)))
            bm_to_acc(metal, cyl_bm(0.16, 0.9, 10, r2=0.10), Matrix.Translation((lx, ly, gz)))
            bm_to_acc(metal, box_bm(0.08, 1.5, 0.08), Matrix.Translation((lx, ly + toward * 0.7, gz + 7.5)))
            bm_to_acc(metal, box_bm(0.38, 0.65, 0.16, 0.03), Matrix.Translation((lx, ly + toward * 1.4, gz + 7.38)))
            bm_to_acc(lamps_g, box_bm(0.30, 0.52, 0.03), Matrix.Translation((lx, ly + toward * 1.4, gz + 7.35)))
            if abs(lx) < 110:
                lamp_xy.append((lx, ly + toward * 1.4))
    m_street = mat_street(S, [p for p in lamp_xy if abs(p[0]) < 80])
    # curbs
    for yc in (8.6, 28.4):
        bm_to_acc(stone, box_bm(160, 0.25, 0.17), Matrix.Translation((0, yc, STREET - 0.02)))
    # plane trees on the far sidewalk (lumpy canopies of several clumps), parked cars along both curbs
    for i in range(-11, 12):
        tx = i * 9.0 + rng.uniform(-0.6, 0.6)
        if 20 < tx < 31:
            continue
        ty = 30.8 + rng.uniform(-0.3, 0.3)
        gz = ground(tx, ty) + 0.15
        th = rng.uniform(4.0, 5.0)
        bm_to_acc(trunks, cyl_bm(0.22, th + 1.5, 10, r2=0.14), Matrix.Translation((tx, ty, gz)))
        for (bx, by, bl) in ((0.9, 0.3, 1.8), (-0.8, -0.2, 1.6)):     # main branches
            p0 = Vector((tx, ty, gz + th - 0.5))
            p1 = Vector((tx + bx * 1.6, ty + by, gz + th + bl))
            dv = p1 - p0
            bm = cyl_bm(0.12, dv.length, 6, r2=0.06)
            bm_to_acc(trunks, bm, Matrix.Translation(p0) @ dv.to_track_quat('Z', 'Y').to_matrix().to_4x4())
        for k in range(11):
            bm = tree_bm(rng, i * 13 + k, 1.0, 2)
            sc = (rng.uniform(1.1, 1.7), rng.uniform(1.0, 1.6), rng.uniform(0.9, 1.4))
            off = (rng.uniform(-2.6, 2.6), rng.uniform(-1.8, 1.8), th + rng.uniform(0.8, 4.8))
            M = Matrix.Translation((tx + off[0], ty + off[1], gz + off[2])) @ Matrix.Diagonal(sc + (1,))
            bm_to_acc(trees, bm, M, smooth=True)
    for i in range(-14, 15):
        for (cy_, prob, side) in ((10.0, 0.7, -1), (27.0, 0.75, 1)):
            cx_ = i * 5.6 + rng.uniform(-0.5, 0.5)
            if rng.random() > prob or 21 < cx_ < 31:
                continue
            gz = ground(cx_, cy_)
            style = rng.choices((0, 1, 2), (0.5, 0.38, 0.12))[0]
            L, W = (rng.uniform(3.9, 4.3), 1.76) if style == 0 else ((rng.uniform(4.5, 4.9), 1.84) if style == 1 else
                                                                    (4.6, 1.95))
            H = 1.5 if style < 2 else 1.95
            lampd = min(math.hypot(cx_ - lx, cy_ - ly) for lx, ly in lamp_xy) if lamp_xy else 99.0
            fa = {'cc': rng.random(), 'base': gz + 0.02, 'lamp': math.exp(-(lampd / 7.0) ** 2)}
            M = Matrix.Translation((cx_, cy_ + side * rng.uniform(0.0, 0.15), gz + 0.02)) @ \
                Matrix.Rotation(rng.choice((0.0, math.pi)) + rng.uniform(-0.03, 0.03), 4, 'Z')
            bm_to_acc(cars, car_bm(L, W, H, style), M, fattrs=fa)
            for wx in (-L * 0.32, L * 0.32):
                for wy in (-W / 2 + 0.12, W / 2 - 0.12):
                    bm = cyl_bm(0.32, 0.22, 12)
                    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'), verts=bm.verts)
                    bm_to_acc(cars, bm, M @ Matrix.Translation((wx, wy + (0.11 if wy > 0 else -0.11), 0.32)),
                              fattrs=dict(fa, base=gz + 0.6))

    # ---------------- near block across the boulevard (facades on y = 34): flats with zinc mansards and balconies,
    # old workshops in the middle (so the view opens over the roofscape)
    near = [  # x0, x1, depth, floors, fh, kind
        (-150, -126, 18, 7, 3.1, 'res'), (-126, -104, 16, 6, 3.0, 'res'), (-104, -84, 15, 6, 3.2, 'res'),
        (-84, -63, 20, 8, 3.1, 'office'), (-58, -44, 16, 5, 3.1, 'res'),
        (-44, -30, 20, 3, 4.3, 'ind'), (-30, -6, 30, 2, 4.6, 'ind'), (-6, 12, 16, 3, 3.3, 'res'),
        (12, 22, 15, 4, 3.1, 'res'),
        (33, 46, 16, 5, 3.1, 'res'), (46, 68, 18, 6, 3.0, 'res'), (68, 90, 16, 6, 3.1, 'res'),
        (90, 118, 20, 8, 3.2, 'office'), (118, 150, 16, 6, 3.1, 'res'),
    ]
    roofs = []
    for (x0, x1, dep, nf, fh, kind) in near:
        cx, cy = (x0 + x1) / 2, 34.0 + dep / 2
        gz = ground(cx, 34.0)
        w = x1 - x0 - 0.3
        top = add_building(bld, rng, cx, cy, 0.0, w, dep, nf, fh, gz - 1.0, gz, kind, near=True, bevel=0.12,
                           extra_h=(0.9 if kind != 'ind' else 0.6), balc=(1.0 if kind == 'res' else 0.0))
        if kind == 'res':
            # stone cornice, zinc mansard with dormers, balcony slabs on the 2nd and top floors
            add_building(bld, rng, cx, cy, 0.0, w + 0.5, dep + 0.5, 0, fh, top - 0.5, gz, kind, near=True,
                         height=0.55, bevel=0.08)
            top = add_mansard(bld, rng, cx, cy, 0.0, w, dep, top + 0.05, rng.uniform(2.8, 3.3), 1.25)
            for fl in (2, nf - 1):
                zb = gz + fl * fh + 0.20 * fh - 0.16
                bm_to_acc(stone, box_bm(w - 0.4, 0.75, 0.16, 0.03), Matrix.Translation((cx, 34.0 - 0.37, zb)))
        roofs.append((x0, x1, cy, dep, top, kind, nf))
    # second row behind (y 54..80): lower in the middle, so the view goes over it
    for x in range(-150, 150, 17):
        cx = x + rng.uniform(0, 4)
        cy = 66 + rng.uniform(-4, 6)
        if 18 < cx < 36:
            continue
        mid = abs(cx + 4) < 48
        nf = rng.randint(2, 3) if mid else rng.randint(5, 7)
        gz = ground(cx, cy)
        w, d = rng.uniform(12, 16), rng.uniform(14, 20)
        ang = rng.uniform(-0.03, 0.03)
        kind = rng.choice(('res', 'res', 'ind'))
        top = add_building(bld, rng, cx, cy, ang, w, d, nf, rng.uniform(3.0, 3.3), gz - 1.5, gz, kind, near=True,
                           bevel=0.1)
        if kind == 'res' and rng.random() < 0.7:
            top = add_mansard(bld, rng, cx, cy, ang, w, d, top, rng.uniform(2.5, 3.0), 1.05)
        roofs.append((cx - 6, cx + 6, cy, 14, top, 'res', nf))
    # side street (x 22..33) going away: buildings along it on both sides, stepping down the slope
    for k in range(8):
        y = 84 + k * 16
        for sx in (14.0, 41.0):
            cx = sx + rng.uniform(-1, 1)
            gz = ground(cx, y)
            nf = rng.randint(4, 6)
            top = add_building(bld, rng, cx, y, 0.0, 14.0, 15.0, nf, 3.1, gz - 2.0, gz, 'res', near=True)
            if rng.random() < 0.6:
                add_mansard(bld, rng, cx, y, 0.0, 14.0, 15.0, top, 2.7, 1.05)
        for (lx, ly) in ((24.2, y - 6), (30.8, y + 2)):
            gz = ground(lx, ly)
            bm_to_acc(sodium_g, box_bm(0.35, 0.6, 0.18), Matrix.Translation((lx, ly, gz + 7.0)))

    # sawtooth skylights on the big workshop (x -30..-6)
    x0, x1 = -29.6, -6.4
    roof_z = [r for r in roofs if r[0] == -30][0][4]
    for k in range(6):
        y = 36.0 + k * 4.6
        verts = [(x0, y, roof_z), (x1, y, roof_z), (x1, y + 0.9, roof_z + 2.3), (x0, y + 0.9, roof_z + 2.3)]
        uvs = [[(0, 0), (x1 - x0, 0), (x1 - x0, 2.47), (0, 2.47)]]
        sky_l.add(verts, [(0, 1, 2, 3)], {'row': float(k)}, uvs=uvs)
        verts2 = [(x0, y + 0.9, roof_z + 2.3), (x1, y + 0.9, roof_z + 2.3), (x1, y + 4.6, roof_z), (x0, y + 4.6, roof_z)]
        metal.add(verts2, [(0, 1, 2, 3)])
        metal.add([(x0, y, roof_z), (x0, y + 0.9, roof_z + 2.3), (x0, y + 4.6, roof_z)], [(0, 1, 2)])
        metal.add([(x1, y, roof_z), (x1, y + 4.6, roof_z), (x1, y + 0.9, roof_z + 2.3)], [(0, 1, 2)])
        bm_to_acc(metal, box_bm(x1 - x0, 0.12, 0.10), Matrix.Translation(((x0 + x1) / 2, y + 0.9, roof_z + 2.25)))

    # rooftop gear: AC units, stair bulkheads, chimney stacks
    for (x0, x1, cy, dep, top, kind, nf) in roofs:
        if kind == 'ind' and x0 == -30:
            continue
        for _ in range(rng.randint(0, 2)):
            ac_unit(metal, rng.uniform(x0 + 3, x1 - 3), cy + rng.uniform(-dep / 4, dep / 4), top, rng)
        if kind != 'res' and rng.random() < 0.6:   # stair/lift bulkhead
            bm_to_acc(metal, box_bm(rng.uniform(2.5, 4), rng.uniform(2.5, 4), rng.uniform(2.4, 3.0), 0.05),
                      Matrix.Translation((rng.uniform(x0 + 3, x1 - 3), cy + rng.uniform(-2, 2), top)))
        for _ in range(rng.randint(2, 5) if kind == 'res' else rng.randint(0, 2)):
            chimney(brick, metal, rng.uniform(x0 + 2, x1 - 2), cy + rng.uniform(-dep / 3.5, dep / 3.5), top - 0.1,
                    rng, 1.0, rng.choice((0.0, math.pi / 2)))
    water_tower(metal, wood, 3.0, 44.0, [r for r in roofs if r[0] == -6][0][4], 1.0, 0.3)
    water_tower(metal, wood, 57.0, 46.0, [r for r in roofs if r[0] == 46][0][4], 1.1, -0.2)
    water_tower(metal, wood, -36.5, 47.0, [r for r in roofs if r[0] == -44][0][4], 0.9, 0.1)
    antenna(metal, beacons, -74.0, 40.0, [r for r in roofs if r[0] == -84][0][4], 9.0, beacon_mats[0])
    antenna(metal, beacons, 104.0, 41.0, [r for r in roofs if r[0] == 90][0][4], 7.0, beacon_mats[1])
    antenna(metal, beacons, 17.0, 40.0, [r for r in roofs if r[0] == 12][0][4], 4.5, beacon_mats[3])

    # ---------------- roofscape on the slope (full scale) and the far hill (K scale)
    def zone_ok(x, y):
        r = math.hypot(x, y)
        az = math.atan2(x, y)
        if az < AZ0 + 0.05 or az > AZ1 - 0.05 or r > R_MAX - 8:
            return None
        rr = r_river(az)
        if y < 82 and abs(x) < 160:
            return None
        if 18 < x < 37 and y < 200:      # keep the side street open
            return None
        if rr - RIV_HALF - 6 < r < rr + RIV_HALF + 7:
            return None
        if r < 86:
            return None
        return 'mid' if r < rr else 'far'

    def sightline(r):
        """Height of the line from the eye to the middle of the far hill: roofs below it keep the hill visible."""
        return 1.5 - 0.062 * r

    mid_towers = [(-0.82, 132.0, 15), (0.60, 122.0, 13), (0.98, 146.0, 17), (-1.15, 112.0, 11)]
    for (az, rad, nf) in mid_towers:
        x, y = rad * math.sin(az), rad * math.cos(az)
        gz = min(ground(x + dx, y + dy) for dx in (-7, 7) for dy in (-7, 7))
        top = add_building(bld, rng, x, y, az * 0.5, rng.uniform(16, 20), rng.uniform(14, 18), nf, 3.6, gz - 1.0,
                           ground(x, y), 'office', bevel=0.15)
        beacons.append((x, y, top + 0.6, 0.32, beacon_mats[rng.randint(0, 3)]))
        bm_to_acc(metal, cyl_bm(0.12, 0.6, 8), Matrix.Translation((x, y, top)))
        bm_to_acc(metal, box_bm(5.0, 4.0, 3.0, 0.05), Matrix.Translation((x + 2.0, y, top)))

    def near_tower(x, y, rmin=14.0):
        return any(math.hypot(x - t[1] * math.sin(t[0]), y - t[1] * math.cos(t[0])) < rmin for t in mid_towers)

    # mid roofscape: jittered 15 m grid of blocks, heights limited by the sight line (a few poke above it)
    for gx in range(-240, 241, 15):
        for gy in range(-40, 200, 15):
            x = gx + rng.uniform(-3.5, 3.5)
            y = gy + rng.uniform(-3.5, 3.5)
            if zone_ok(x, y) != 'mid' or near_tower(x, y):
                continue
            r = math.hypot(x, y)
            az = math.atan2(x, y)
            ang = (0.30 if math.sin(x / 140.0 + y / 90.0) > 0 else -0.55) + 0.35 * az + rng.uniform(-0.05, 0.05)
            w, d = rng.uniform(10, 13.5), rng.uniform(9, 13)
            kind = rng.choices(('res', 'office', 'ind'), (0.78, 0.10, 0.12))[0]
            fh = 3.6 if kind == 'office' else rng.uniform(2.9, 3.3)
            gz = min(ground(x + dx, y + dy) for dx in (-w / 2, w / 2) for dy in (-d / 2, d / 2))
            gc = ground(x, y)
            room = sightline(r) - gc - (3.0 if kind == 'res' else 0.0)
            nmax = max(2, int(room / fh))
            nf = min(rng.randint(3, 7), nmax) + (rng.randint(1, 2) if rng.random() < 0.15 else 0)
            top = add_building(bld, rng, x, y, ang, w, d, nf, fh, gz - 1.0, gc, kind)
            if kind == 'res' and rng.random() < 0.65:
                top = add_mansard(bld, rng, x, y, ang, w, d, top, rng.uniform(2.4, 3.0), 1.0)
            if kind != 'office':
                ca, sa = math.cos(ang), math.sin(ang)
                for _ in range(rng.randint(1, 3)):
                    lx, ly = rng.uniform(-w / 3, w / 3), rng.uniform(-d / 4, d / 4)
                    chimney(brick, metal, x + lx * ca - ly * sa, y + lx * sa + ly * ca, top - 0.1, rng, 1.0, ang)
            elif rng.random() < 0.7:
                ac_unit(metal, x, y, top, rng)

    # far hill: a denser grid of small blocks at K scale, a park around the basilica
    mast_xy = (MAST_R * math.sin(MAST_AZ), MAST_R * math.cos(MAST_AZ))
    step = 15.0 * K
    gx = -R_MAX
    while gx < R_MAX:
        gy = 150.0
        while gy < R_MAX:
            x = gx + rng.uniform(-0.25, 0.25) * step
            y = gy + rng.uniform(-0.25, 0.25) * step
            gy += step
            if zone_ok(x, y) != 'far':
                continue
            if math.hypot(x - church_xy[0], y - church_xy[1]) < 48.0 or math.hypot(x - mast_xy[0], y - mast_xy[1]) < 18.0:
                continue
            if rng.random() < 0.30:
                continue
            az = math.atan2(x, y)
            ang = (0.30 if math.sin(x / 110.0 + y / 70.0) > 0 else -0.55) + 0.25 * az + rng.uniform(-0.06, 0.06)
            w, d = rng.uniform(9, 13.5) * K, rng.uniform(9, 13) * K
            kind = rng.choices(('res', 'office', 'ind'), (0.80, 0.08, 0.12))[0]
            fh = (3.6 if kind == 'office' else rng.uniform(2.9, 3.3)) * K
            nf = rng.randint(2, 5) if rng.random() > 0.04 else rng.randint(7, 10)
            gz = min(ground(x + dx, y + dy) for dx in (-w / 2, w / 2) for dy in (-d / 2, d / 2))
            gc = ground(x, y)
            top = add_building(bld, rng, x, y, ang, w, d, nf, fh, gz - 1.0, gc, kind, k=K, glow=0.25,
                               lit=rng.uniform(0.15, 0.42) if kind == 'res' else None)
            if kind == 'res' and rng.random() < 0.4:
                add_mansard(bld, rng, x, y, ang, w, d, top, 2.6 * K, 0.95 * K, k=K)
        gx += step

    # office towers on the right of the hill (a small business district), at K scale
    for (az, rad, nf) in ((0.80, 300.0, 24), (0.86, 318.0, 31), (0.92, 296.0, 19), (0.97, 324.0, 27),
                          (1.04, 306.0, 22), (0.75, 330.0, 17)):
        x, y = rad * math.sin(az), rad * math.cos(az)
        w = rng.uniform(17, 24) * K
        gz = min(ground(x + dx, y + dy) for dx in (-w / 2, w / 2) for dy in (-w / 2, w / 2))
        top = add_building(bld, rng, x, y, az * 0.4 + rng.uniform(-0.2, 0.2), w, w * rng.uniform(0.7, 1.0), nf, 3.7 * K,
                           gz - 1.0, ground(x, y), 'office', k=K, lit=rng.uniform(0.18, 0.34))
        bm_to_acc(metal, box_bm(w * 0.5, w * 0.4, 3.0 * K, 0.03), Matrix.Translation((x, y, top)))
        if nf > 20:
            beacons.append((x, y, top + 3.4 * K, 0.5, beacon_mats[rng.randint(0, 3)]))

    # ---------------- terrain (polar grid, rings snapped to the river banks)
    nA = 160
    tv, tf = [], []
    rings_n1, rings_n2 = 40, 56
    for i in range(nA + 1):
        az = AZ0 + (AZ1 - AZ0) * i / nA
        rr = r_river(az)
        a, b = rr - RIV_HALF, rr + RIV_HALF
        radii = [16 + (a - 4 - 16) * (k / rings_n1) ** 1.1 for k in range(rings_n1 + 1)]
        radii += [a - 0.05, a + 0.05, b - 0.05, b + 0.05, b + 5]
        radii += [b + 5 + (R_MAX - b - 5) * (k / rings_n2) for k in range(1, rings_n2 + 1)]
        for rad in radii:
            x, y = rad * math.sin(az), rad * math.cos(az)
            gz = ground(x, y)
            if rad < 35 and abs(x) < 160 and y > 3.5:
                gz -= 0.3
            tv.append((x, y, gz))
    nr = len(radii)
    for i in range(nA):
        for k in range(nr - 1):
            a0, a1 = i * nr + k, (i + 1) * nr + k
            tf.append((a0, a1, a1 + 1, a0 + 1))
    terr = Acc()
    terr.add(tv, tf)
    terr.build('terrain', m_gnd, P)

    # river surface
    wv, wf = [], []
    for i in range(nA + 1):
        az = AZ0 + (AZ1 - AZ0) * i / nA
        rr = r_river(az)
        for rad in (rr - RIV_HALF, rr + RIV_HALF):
            wv.append((rad * math.sin(az), rad * math.cos(az), WATER))
    for i in range(nA):
        wf.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    wat = Acc()
    wat.add(wv, wf)
    wat.build('river', m_wat, P)

    # quay lamps along both banks (sodium dots on short posts)
    for side, off in ((-1, -2.5), (1, 2.5)):
        az = AZ0 + 0.03
        while az < AZ1 - 0.03:
            rr = r_river(az) + side * RIV_HALF + off
            x, y = rr * math.sin(az), rr * math.cos(az)
            if math.hypot(x, y) < R_MAX:
                bm_to_acc(sodium_g, box_bm(0.5, 0.5, 0.4), Matrix.Translation((x, y, LOW + 4.5)))
            az += 22.0 / rr
    # trees along the far quay (a line of dark plane trees at K scale)
    az = AZ0 + 0.05
    while az < AZ1 - 0.05:
        rr = r_river(az) + RIV_HALF + 4.0
        x, y = rr * math.sin(az), rr * math.cos(az)
        bm = tree_bm(rng, az * 100, 1.0, 1)
        sc = 3.2 * K
        bm_to_acc(ftrees, bm, Matrix.Translation((x, y, LOW + 5.5 * K)) @ Matrix.Diagonal((sc * 1.2, sc, sc, 1)),
                  smooth=True)
        az += 9.0 / rr

    # bridge across the river (az ~ -0.17): deck, piers, lamps
    bz = math.radians(-10.0)
    rr = r_river(bz)
    L = 2 * RIV_HALF + 16
    c = Vector((rr * math.sin(bz), rr * math.cos(bz), 0))
    Mb = Matrix.Translation((c.x, c.y, LOW + 1.2)) @ Matrix.Rotation(-bz, 4, 'Z')
    bm_to_acc(stone, box_bm(14.0, L, 1.4, 0.1), Mb)
    for k in (-1, 0, 1):
        bm_to_acc(stone, box_bm(4.0, 3.0, 9.0), Mb @ Matrix.Translation((0, k * L / 3.2, -8.2)))
    for k in range(-5, 6):
        for sx in (-6.6, 6.6):
            bm_to_acc(sodium_g, box_bm(0.45, 0.45, 0.35), Mb @ Matrix.Translation((sx, k * L / 11.0, 5.8)))
            bm_to_acc(metal, cyl_bm(0.08, 4.4, 6), Mb @ Matrix.Translation((sx, k * L / 11.0, 1.4)))

    # ---------------- the basilica on the crest (Fourviere-like: long nave, four octagonal crenellated towers,
    # an apse, a chapel bell tower with a gilded statue), at K scale, seen three-quarter
    cx, cy = church_xy
    gz = ground(cx, cy) - 1.5 * K
    Mc = Matrix.Translation((cx, cy, gz)) @ Matrix.Rotation(-CHURCH_AZ + 0.50, 4, 'Z') @ Matrix.Scale(K, 4)
    cuv = facade_uv(gz)

    def cpart(bm, M, kind):
        bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
        bm.normal_update()
        church.add_bm(bm, {'base': gz, 'kind': float(kind)}, cuv)
        bm.free()

    NL, NW, NH = 62.0, 24.0, 22.0                       # nave (length along local x), walls 22 m
    cpart(box_bm(NL, NW, NH, 0.3), Mc, 0)
    cpart(box_bm(NL + 1.2, NW + 1.2, 1.2, 0.1), Mc @ Matrix.Translation((0, 0, 15.0)), 0)       # string course
    cpart(box_bm(NL + 1.6, NW + 1.6, 1.4, 0.1), Mc @ Matrix.Translation((0, 0, NH - 0.6)), 0)   # cornice
    for i in range(-5, 6):                               # buttresses on both long sides
        for sy in (-1, 1):
            cpart(box_bm(1.6, 1.4, NH - 2.0, 0.1), Mc @ Matrix.Translation((i * 5.2 + 2.6, sy * (NW / 2 + 0.6), 0)), 0)
    # roof: a long gable
    rv = [(-NL / 2, -NW / 2 - 0.6, NH + 0.8), (NL / 2, -NW / 2 - 0.6, NH + 0.8), (NL / 2, 0, NH + 8.5),
          (-NL / 2, 0, NH + 8.5), (-NL / 2, NW / 2 + 0.6, NH + 0.8), (NL / 2, NW / 2 + 0.6, NH + 0.8)]
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in rv]
    for f in ((0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2)):
        bm.faces.new([vs[i] for i in f])
    cpart(bm, Mc, 2)
    # four octagonal towers at the corners with crenellated tops
    for tx in (-NL / 2, NL / 2):
        for ty in (-NW / 2, NW / 2):
            Mt = Mc @ Matrix.Translation((tx, ty, 0))
            cpart(cyl_bm(5.0, 34.0, 8), Mt @ Matrix.Rotation(math.pi / 8, 4, 'Z'), 1)
            cpart(cyl_bm(5.6, 1.2, 8), Mt @ Matrix.Translation((0, 0, 33.0)) @ Matrix.Rotation(math.pi / 8, 4, 'Z'), 1)
            for m in range(8):
                a = 2 * math.pi * (m + 0.5) / 8
                cpart(box_bm(1.6, 0.9, 1.6), Mt @ Matrix.Translation((5.0 * math.cos(a), 5.0 * math.sin(a), 34.2))
                      @ Matrix.Rotation(a + math.pi / 2, 4, 'Z'), 1)
            cpart(cyl_bm(3.6, 2.5, 8, r2=0.4), Mt @ Matrix.Translation((0, 0, 34.0)), 2)
    # apse at the back end (half cylinder) and a front porch with a pediment
    cpart(cyl_bm(10.0, NH - 4.0, 16), Mc @ Matrix.Translation((NL / 2 + 2.0, 0, 0)), 0)
    cpart(cyl_bm(10.5, 4.0, 16, r2=0.6), Mc @ Matrix.Translation((NL / 2 + 2.0, 0, NH - 4.0)), 2)
    cpart(box_bm(6.0, 18.0, 16.0, 0.2), Mc @ Matrix.Translation((-NL / 2 - 3.0, 0, 0)), 0)
    # chapel bell tower with the gilded statue (to the side, behind)
    Mb2 = Mc @ Matrix.Translation((-NL / 2 + 4.0, NW / 2 + 16.0, 0))
    cpart(box_bm(8.0, 8.0, 30.0, 0.15), Mb2, 1)
    cpart(cyl_bm(4.6, 5.0, 16, r2=2.0), Mb2 @ Matrix.Translation((0, 0, 30.0)), 2)
    cpart(cyl_bm(0.8, 4.2, 8, r2=0.5), Mb2 @ Matrix.Translation((0, 0, 35.0)), 3)
    cpart(cyl_bm(0.6, 0.9, 8, r2=0.3), Mb2 @ Matrix.Translation((0, 0, 39.2)), 3)
    # esplanade: the terrace the basilica stands on, its retaining walls fading into the dark slope below
    cpart(box_bm(NL + 18.0, NW + 16.0, 18.0, 0.1), Mc @ Matrix.Translation((2.0, -2.0, -17.6)), 4)

    def tree_cluster(x, y, n, spread, size, drop=0.85):
        for _ in range(n):
            tx, ty = x + rng.uniform(-spread, spread), y + rng.uniform(-spread, spread)
            if math.hypot(tx, ty) > R_MAX - 2:
                continue
            g = ground(tx, ty)
            sc = rng.uniform(0.7, 1.25) * size
            bm = tree_bm(rng, rng.random() * 100, 1.0, 2)
            bm_to_acc(ftrees, bm, Matrix.Translation((tx, ty, g + sc * drop)) @
                      Matrix.Diagonal((sc * rng.uniform(1.0, 1.3), sc, sc * rng.uniform(0.95, 1.2), 1)), smooth=True)

    # the wooded park around it: clumps of dark trees on the slope (break the silhouette of the crest)
    for _ in range(34):
        a = rng.uniform(0, 2 * math.pi)
        rd = rng.uniform(34.0, 78.0)
        tree_cluster(cx + rd * math.cos(a), cy + rd * math.sin(a), rng.randint(3, 5), 5.0 * K, 4.6 * K)
    # groves on the crest line elsewhere (silhouettes against the horizon glow)
    for _ in range(46):
        az = rng.uniform(AZ0 + 0.1, AZ1 - 0.1)
        rd = rng.uniform(328.0, R_MAX - 4)
        tx, ty = rd * math.sin(az), rd * math.cos(az)
        if math.hypot(tx - mast_xy[0], ty - mast_xy[1]) < 14:
            continue
        tree_cluster(tx, ty, rng.randint(2, 5), 6.0 * K, 4.0 * K)

    # ---------------- lattice TV mast on the crest (K scale), red aviation lights
    mx_, my_ = mast_xy
    mz = ground(mx_, my_) - 1.0
    H = 62.0 * K
    legs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]

    def leg_pos(k, t):
        s = (5.0 * (1 - t) + 0.9 * t) * K
        return Vector((mx_ + legs[k][0] * s, my_ + legs[k][1] * s, mz + H * t))

    def strut(p, q, rad=0.18):
        d = q - p
        bm = cyl_bm(rad, d.length, 6)
        rot = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        bm_to_acc(metal, bm, Matrix.Translation(p) @ rot)

    levels = [0.0, 0.14, 0.28, 0.42, 0.56, 0.70, 0.84, 1.0]
    for k in range(4):
        for j in range(len(levels) - 1):
            strut(leg_pos(k, levels[j]), leg_pos(k, levels[j + 1]), 0.35 * K)
            strut(leg_pos(k, levels[j]), leg_pos((k + 1) % 4, levels[j + 1]), 0.14 * K)
            strut(leg_pos((k + 1) % 4, levels[j]), leg_pos(k, levels[j + 1]), 0.14 * K)
            strut(leg_pos(k, levels[j + 1]), leg_pos((k + 1) % 4, levels[j + 1]), 0.16 * K)
    strut(Vector((mx_, my_, mz + H)), Vector((mx_, my_, mz + H + 16 * K)), 0.3 * K)
    for k, t in enumerate((0.45, 1.0)):
        for kk in range(4):
            p = leg_pos(kk, t)
            beacons.append((p.x, p.y, p.z + 0.4, 0.55, beacon_mats[3 if k == 0 else 2]))
    beacons.append((mx_, my_, mz + H + 16.5 * K, 0.65, beacon_mats[0]))

    # ---------------- sky dome
    dv, df = [], []
    nU, nV = 64, 24
    e0, e1 = math.radians(-12), math.radians(89)
    for i in range(nU + 1):
        az = math.radians(-125) + math.radians(250) * i / nU
        for j in range(nV + 1):
            e = e0 + (e1 - e0) * (j / nV) ** 1.3
            dv.append((DOME_R * math.cos(e) * math.sin(az), DOME_R * math.cos(e) * math.cos(az), DOME_R * math.sin(e)))
    for i in range(nU):
        for j in range(nV):
            a0, a1 = i * (nV + 1) + j, (i + 1) * (nV + 1) + j
            df.append((a0, a0 + 1, a1 + 1, a1))
    dome = Acc()
    dome.add(dv, df, smooth=True)
    dome.build('sky', m_sky, P)

    # ---------------- objects
    street.build('street', m_street, P)
    bld.build('buildings', m_bld, P)
    metal.build('metal', m_metal, P)
    wood.build('wood', m_wood, P)
    brick.build('chimneys', m_brick, P)
    stone.build('stone', m_stone, P)
    trees.build('trees', m_tree, P)
    ftrees.build('far_trees', m_ftree, P)
    trunks.build('trunks', m_trunk, P)
    cars.build('cars', m_car, P)
    lamps_g.build('lamps', m_lamp, P)
    sodium_g.build('sodium', m_sodium, P)
    sky_l.build('skylights', m_sky_l, P)
    church.build('church', m_church, P)
    for i, (x, y, z, r, mb) in enumerate(beacons):
        me = bpy.data.meshes.new(f'beacon{i}')
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=r)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mb)
        ob = bpy.data.objects.new(f'city.beacon{i}', me)
        P.col.objects.link(ob)
        ob.parent = P.root
        ob.location = (x, y, z)
        P.parts[f'beacon{i}'] = ob
        P.beacons.append(ob)

    for ob in P.col.objects:
        if ob.type == 'MESH':
            ob.visible_diffuse = False
            ob.visible_shadow = False
            ob.visible_volume_scatter = False
    P.blink = blink
    return P


# ------------------------------------------------------------------ aviation lights
def blink(t, phase=0.0, period=1.5, on=0.22):
    """Brightness 0..1 of a flashing red obstruction light at time t (s): a short flash with a soft attack/decay."""
    u = ((t + phase) % period) / period
    w = on / period
    if u < w:
        x = u / w
        return math.sin(math.pi * x) ** 0.6
    return 0.0


def animate(P, frame_start, frame_end, fps=24, low=0.06):
    """Keyframe the beacon materials (emission strength) so the red lights flash; 'steady' ones stay on."""
    for mat, phase, steady in P.beacon_mats:
        em = next(n for n in mat.node_tree.nodes if n.type == 'EMISSION')
        sock = em.inputs['Strength']
        full = sock.default_value
        if steady:
            continue
        for f in range(frame_start, frame_end + 1):
            sock.default_value = full * max(low, blink(f / fps, phase))
            sock.keyframe_insert('default_value', frame=f)
        sock.default_value = full
