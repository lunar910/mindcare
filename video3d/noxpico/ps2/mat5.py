"""Version 5 materials: physically based, procedural (no image files), for Cycles path tracing.

The look we match is the reference cutscene: real materials under soft night lighting - matte painted walls, worn wood,
brushed and painted steel, concrete, fabric, plastic, glass - with gentle roughness variation so that nothing reads as
flat CG colour.  All textures use OBJECT coordinates in metres (so a pattern keeps its real size whatever the object),
optionally rotated (wood grain along a plank) and offset per object (seed) so that two planks never look identical.

    m = mat5.get('wood_oak')                     # shared, cached by name
    m = mat5.wood('bench_top', (120, 84, 56), grain_axis='X', seed=3)   # custom
    mat5.LIBRARY                                 # the names get() knows

Colours are given as sRGB 0-255 (as you would pick them) and converted to linear."""
import math
import bpy

_CACHE = {}


def lin(c):
    """sRGB 0-255 (or 0-1 floats when all <= 1 and any is fractional) -> linear 0-1."""
    if all(isinstance(x, float) for x in c) and max(c) <= 1.0:
        v = c
    else:
        v = [x / 255.0 for x in c]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v[:3])


class _NT:
    """Tiny node-tree builder."""

    def __init__(self, name):
        self.m = bpy.data.materials.new(name)
        self.m.use_nodes = True
        self.nt = self.m.node_tree
        self.bsdf = self.nt.nodes['Principled BSDF']
        self.out = self.nt.nodes['Material Output']
        self._coord = None

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            if k in n.inputs and not hasattr(n, k):
                n.inputs[k].default_value = v
            else:
                setattr(n, k, v)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def coord(self, scale=1.0, rot=(0, 0, 0), seed=0.0):
        """Object coordinates in metres, scaled (pattern repeats per metre), rotated (degrees), offset by seed."""
        tc = self.node('ShaderNodeTexCoord')
        mp = self.node('ShaderNodeMapping')
        mp.inputs['Rotation'].default_value = tuple(math.radians(a) for a in rot)
        s = scale if isinstance(scale, (tuple, list)) else (scale, scale, scale)
        mp.inputs['Scale'].default_value = s
        mp.inputs['Location'].default_value = (seed * 7.31, seed * 3.17, seed * 5.53)
        self.link(tc.outputs['Object'], mp.inputs['Vector'])
        return mp.outputs['Vector']

    def noise(self, vec, scale, detail=4.0, rough=0.55, distortion=0.0):
        n = self.node('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        n.inputs['Distortion'].default_value = distortion
        self.link(vec, n.inputs['Vector'])
        return n

    def ramp(self, fac, stops):
        """stops: [(pos, rgb or value)] -> colour ramp output."""
        r = self.node('ShaderNodeValToRGB')
        els = r.color_ramp.elements
        while len(els) > len(stops):
            els.remove(els[-1])
        while len(els) < len(stops):
            els.new(0.5)
        for e, (p, c) in zip(els, stops):
            e.position = p
            if isinstance(c, (int, float)):
                e.color = (c, c, c, 1.0)
            else:
                e.color = tuple(lin(c)) + (1.0,)
        self.link(fac, r.inputs['Fac'])
        return r.outputs['Color']

    def maprange(self, val, a, b, c, d):
        n = self.node('ShaderNodeMapRange')
        n.inputs['From Min'].default_value = a
        n.inputs['From Max'].default_value = b
        n.inputs['To Min'].default_value = c
        n.inputs['To Max'].default_value = d
        self.link(val, n.inputs['Value'])
        return n.outputs['Result']

    def bump(self, height, strength=0.2, distance=0.002, normal=None):
        b = self.node('ShaderNodeBump')
        b.inputs['Strength'].default_value = strength
        b.inputs['Distance'].default_value = distance
        self.link(height, b.inputs['Height'])
        if normal is not None:
            self.link(normal, b.inputs['Normal'])
        return b.outputs['Normal']

    def mix(self, fac, a, b, blend='MIX'):
        n = self.node('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        if isinstance(fac, (int, float)):
            n.inputs['Factor'].default_value = fac
        else:
            self.link(fac, n.inputs['Factor'])
        for sock, v in ((n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, (tuple, list)):
                sock.default_value = tuple(lin(v)) + (1.0,)
            else:
                self.link(v, sock)
        return n.outputs[2]

    def set(self, **kw):
        names = {'base': 'Base Color', 'rough': 'Roughness', 'metal': 'Metallic', 'spec': 'Specular IOR Level',
                 'normal': 'Normal', 'emit_color': 'Emission Color', 'emit': 'Emission Strength', 'alpha': 'Alpha',
                 'transmission': 'Transmission Weight', 'ior': 'IOR', 'coat': 'Coat Weight', 'coat_rough': 'Coat Roughness',
                 'sheen': 'Sheen Weight', 'sss': 'Subsurface Weight', 'aniso': 'Anisotropic'}
        for k, v in kw.items():
            sock = self.bsdf.inputs[names[k]]
            if isinstance(v, (tuple, list)):
                sock.default_value = tuple(lin(v)) + (1.0,) if len(sock.default_value) == 4 else v
            elif isinstance(v, (int, float)):
                sock.default_value = v
            else:
                self.link(v, sock)
        return self.m


# ------------------------------------------------------------------ families
def matte(name, rgb, rough=0.85, var=0.06, bump=0.03, scale=6.0, seed=0.0):
    """Painted plaster / matte paint / plain plastic: a flat colour with a little tonal variation and micro bump."""
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    n = T.noise(v, scale, 5.0, 0.6)
    lo = tuple(max(0, x * (1 - var)) for x in rgb)
    hi = tuple(min(255, x * (1 + var)) for x in rgb)
    col = T.ramp(n.outputs['Fac'], [(0.3, lo), (0.7, hi)])
    fine = T.noise(v, scale * 40, 3.0, 0.5)
    return T.set(base=col, rough=T.maprange(n.outputs['Fac'], 0.3, 0.7, rough - 0.05, min(1, rough + 0.05)),
                 normal=T.bump(fine.outputs['Fac'], bump, 0.002), spec=0.4)


def wood(name, rgb=(120, 84, 56), grain_axis='X', ring_scale=45.0, rough=0.55, varnish=0.0, seed=0.0, dark=0.62):
    """Wood: growth rings around grain_axis (so every face shows lines running along the grain), the pattern stretched
    along the grain, broken up by noise; pores in the bump; a little roughness variation.  ring_scale ~45 = 7 mm rings."""
    T = _NT(name)
    k = {'X': (0.10, 1.0, 1.0), 'Y': (1.0, 0.10, 1.0), 'Z': (1.0, 1.0, 0.10)}[grain_axis]
    v = T.coord(k, seed=seed)                                   # slow variation along the grain
    w = T.node('ShaderNodeTexWave')
    w.wave_type = 'RINGS'
    w.rings_direction = grain_axis
    w.inputs['Scale'].default_value = ring_scale
    w.inputs['Distortion'].default_value = 10.0
    w.inputs['Detail'].default_value = 4.0
    w.inputs['Detail Scale'].default_value = 0.6
    w.inputs['Detail Roughness'].default_value = 0.6
    T.link(v, w.inputs['Vector'])
    n = T.noise(v, 6.0, 6.0, 0.6)                              # broad tone changes between boards/areas
    fac = T.mix(0.45, w.outputs['Color'], n.outputs['Color'])
    bw = T.node('ShaderNodeRGBToBW')
    T.link(fac, bw.inputs['Color'])
    darkc = tuple(x * dark for x in rgb)
    lightc = tuple(min(255, x * 1.12) for x in rgb)
    col = T.ramp(bw.outputs['Val'], [(0.2, darkc), (0.5, rgb), (0.8, lightc)])
    kp = {'X': (8.0, 300.0, 300.0), 'Y': (300.0, 8.0, 300.0), 'Z': (300.0, 300.0, 8.0)}[grain_axis]
    pores = T.noise(T.coord(kp, seed=seed), 1.0, 2.0, 0.5)
    T.set(base=col, rough=T.maprange(bw.outputs['Val'], 0.2, 0.9, rough + 0.08, rough - 0.08),
          normal=T.bump(pores.outputs['Fac'], 0.12, 0.001), spec=0.5)
    if varnish:
        T.set(coat=varnish, coat_rough=0.25)
    return T.m


def concrete(name, rgb=(128, 126, 122), rough=0.7, polish=0.0, seed=0.0):
    """Concrete floor/wall: blotchy tone, fine pits; `polish` > 0 gives a sealed floor that softly reflects lamps."""
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    big = T.noise(v, 0.8, 4.0, 0.6)
    mid = T.noise(v, 6.0, 6.0, 0.6)
    fac = T.mix(0.5, big.outputs['Color'], mid.outputs['Color'])
    bw = T.node('ShaderNodeRGBToBW')
    T.link(fac, bw.inputs['Color'])
    col = T.ramp(bw.outputs['Val'], [(0.35, tuple(x * 0.82 for x in rgb)), (0.65, tuple(min(255, x * 1.1) for x in rgb))])
    pits = T.noise(v, 90.0, 2.0, 0.6)
    pit = T.maprange(pits.outputs['Fac'], 0.62, 0.7, 0.0, 1.0)
    r = rough - 0.45 * polish
    return T.set(base=col, rough=T.maprange(bw.outputs['Val'], 0.3, 0.7, r + 0.1, max(0.05, r - 0.1)),
                 normal=T.bump(pit, 0.15, 0.001), spec=0.5)


def brick(name, rgb=(132, 66, 48), mortar=(150, 146, 138), rough=0.85, seed=0.0, painted=None):
    """Brick wall (bricks 0.22 x 0.065 m, 1 cm mortar). painted=rgb: an old coat of paint over the bricks."""
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    b = T.node('ShaderNodeTexBrick')
    b.offset = 0.5
    b.inputs['Scale'].default_value = 1.0
    b.inputs['Mortar Size'].default_value = 0.01
    b.inputs['Mortar Smooth'].default_value = 0.2
    b.inputs['Brick Width'].default_value = 0.23
    b.inputs['Row Height'].default_value = 0.075
    b.inputs['Bias'].default_value = 0.0
    c1 = rgb
    c2 = tuple(x * 0.78 for x in rgb)
    b.inputs['Color1'].default_value = tuple(lin(c1)) + (1,)
    b.inputs['Color2'].default_value = tuple(lin(c2)) + (1,)
    b.inputs['Mortar'].default_value = tuple(lin(mortar)) + (1,)
    # wall in the XZ or YZ plane: brick texture works on its X/Y, so feed (horizontal, vertical) = (x + y, z)
    sep = T.node('ShaderNodeSeparateXYZ')
    T.link(v, sep.inputs['Vector'])
    add = T.node('ShaderNodeMath', operation='ADD')
    T.link(sep.outputs['X'], add.inputs[0])
    T.link(sep.outputs['Y'], add.inputs[1])
    comb = T.node('ShaderNodeCombineXYZ')
    T.link(add.outputs['Value'], comb.inputs['X'])
    T.link(sep.outputs['Z'], comb.inputs['Y'])
    T.link(comb.outputs['Vector'], b.inputs['Vector'])
    grime = T.noise(v, 3.0, 6.0, 0.65)
    col = T.mix(T.maprange(grime.outputs['Fac'], 0.3, 0.7, 0.0, 0.35), b.outputs['Color'], (40, 34, 30), 'MULTIPLY')
    if painted:
        chips = T.noise(v, 14.0, 6.0, 0.7)
        col = T.mix(T.maprange(chips.outputs['Fac'], 0.58, 0.62, 1.0, 0.0), col, painted)
    T.set(base=col, rough=rough, normal=T.bump(b.outputs['Fac'], 0.5, 0.006), spec=0.35)
    return T.m


def metal(name, rgb=(170, 172, 176), rough=0.32, brushed=True, seed=0.0):
    """Bare steel / aluminium / chrome (rough ~0.1): metallic, faint brushing streaks."""
    T = _NT(name)
    v = T.coord((1.0, 1.0, 1.0) if not brushed else (1.0, 1.0, 60.0), seed=seed)
    n = T.noise(v, 18.0, 4.0, 0.6)
    return T.set(base=rgb, metal=1.0, rough=T.maprange(n.outputs['Fac'], 0.3, 0.7, max(0.03, rough - 0.08), rough + 0.08),
                 normal=T.bump(n.outputs['Fac'], 0.03, 0.0005))


def painted_metal(name, rgb=(40, 44, 48), rough=0.45, wear=0.15, seed=0.0):
    """Powder-coated / painted steel (bench legs, shelving, window frames) with worn edges showing bare metal."""
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    n = T.noise(v, 9.0, 6.0, 0.65)
    worn = T.maprange(n.outputs['Fac'], 0.72 - wear * 0.3, 0.75 - wear * 0.3, 0.0, 1.0)
    col = T.mix(worn, rgb, (150, 150, 152))
    return T.set(base=col, metal=worn, rough=T.maprange(n.outputs['Fac'], 0.3, 0.7, rough - 0.06, rough + 0.06),
                 normal=T.bump(T.noise(v, 120.0, 2.0, 0.5).outputs['Fac'], 0.04, 0.0005), spec=0.5)


def plastic(name, rgb, rough=0.38, seed=0.0):
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    n = T.noise(v, 30.0, 3.0, 0.5)
    return T.set(base=rgb, rough=T.maprange(n.outputs['Fac'], 0.3, 0.7, rough - 0.05, rough + 0.05), spec=0.5,
                 normal=T.bump(n.outputs['Fac'], 0.02, 0.0005))


def rubber(name, rgb=(26, 26, 28), rough=0.75):
    T = _NT(name)
    return T.set(base=rgb, rough=rough, spec=0.35)


def fabric(name, rgb, rough=0.92, weave=420.0, sheen=0.5, seed=0.0):
    """Sofa/cushion/curtain cloth: soft sheen, tonal mottling, fine weave bump."""
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    mott = T.noise(v, 4.0, 4.0, 0.6)
    col = T.ramp(mott.outputs['Fac'], [(0.35, tuple(x * 0.88 for x in rgb)), (0.65, tuple(min(255, x * 1.06) for x in rgb))])
    w = T.node('ShaderNodeTexWave')
    w.inputs['Scale'].default_value = weave
    w.inputs['Distortion'].default_value = 0.5
    T.link(v, w.inputs['Vector'])
    return T.set(base=col, rough=rough, sheen=sheen, normal=T.bump(w.outputs['Fac'], 0.08, 0.0006), spec=0.3)


def leather(name, rgb=(60, 40, 30), rough=0.5, seed=0.0):
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    n = T.noise(v, 160.0, 3.0, 0.6)
    mott = T.noise(v, 3.0, 4.0, 0.6)
    col = T.ramp(mott.outputs['Fac'], [(0.3, tuple(x * 0.8 for x in rgb)), (0.7, tuple(min(255, x * 1.1) for x in rgb))])
    return T.set(base=col, rough=T.maprange(mott.outputs['Fac'], 0.3, 0.7, rough + 0.1, rough - 0.1),
                 normal=T.bump(n.outputs['Fac'], 0.25, 0.0008), spec=0.45)


def glass(name, tint=(235, 242, 248), rough=0.02, ior=1.5):
    T = _NT(name)
    return T.set(base=tint, rough=rough, transmission=1.0, ior=ior, spec=0.5)


def emissive(name, rgb, strength=4.0, base=(20, 20, 20)):
    """A light source surface (lamp shade inside, LED, screen glow)."""
    T = _NT(name)
    return T.set(base=base, emit_color=rgb, emit=strength, rough=0.5)


def screen(name, image=None, strength=2.0, rgb=(80, 200, 140)):
    """A monitor / oscilloscope screen: an image (bpy image) or a flat colour, emissive, behind glossy glass."""
    T = _NT(name)
    if image is not None:
        tx = T.node('ShaderNodeTexImage')
        tx.image = image
        T.link(tx.outputs['Color'], T.bsdf.inputs['Emission Color'])
        T.link(tx.outputs['Color'], T.bsdf.inputs['Base Color'])
    else:
        T.set(emit_color=rgb, base=tuple(x * 0.3 for x in rgb))
    return T.set(emit=strength, rough=0.08, spec=0.6, coat=0.6, coat_rough=0.05)


def paper(name, rgb=(236, 232, 222), rough=0.9):
    T = _NT(name)
    return T.set(base=rgb, rough=rough, spec=0.3, sss=0.05)


def ceramic(name, rgb=(30, 30, 32), rough=0.18):
    T = _NT(name)
    return T.set(base=rgb, rough=rough, spec=0.5, coat=0.5, coat_rough=0.08)


def plant(name, rgb=(52, 92, 48), rough=0.55, seed=0.0):
    T = _NT(name)
    v = T.coord(1.0, seed=seed)
    n = T.noise(v, 25.0, 3.0, 0.6)
    col = T.ramp(n.outputs['Fac'], [(0.3, tuple(x * 0.75 for x in rgb)), (0.7, tuple(min(255, x * 1.15) for x in rgb))])
    return T.set(base=col, rough=rough, sss=0.15, spec=0.4)


def soil(name='soil', rgb=(46, 34, 26)):
    T = _NT(name)
    v = T.coord(1.0)
    n = T.noise(v, 80.0, 4.0, 0.7)
    return T.set(base=rgb, rough=0.95, normal=T.bump(n.outputs['Fac'], 0.5, 0.002), spec=0.2)


# ------------------------------------------------------------------ the shared library
LIBRARY = {
    # architecture
    'plaster_warm':   lambda n: matte(n, (176, 168, 156), 0.9),
    'plaster_dark':   lambda n: matte(n, (70, 76, 86), 0.9),
    'brick_old':      lambda n: brick(n, (124, 62, 46)),
    'brick_painted':  lambda n: brick(n, (124, 62, 46), painted=(200, 196, 186)),
    'concrete_floor': lambda n: concrete(n, (118, 116, 112), 0.65, polish=0.5),
    'concrete_wall':  lambda n: concrete(n, (140, 138, 134), 0.85),
    'steel_black':    lambda n: painted_metal(n, (28, 30, 32), 0.4, 0.1),
    'steel_grey':     lambda n: painted_metal(n, (92, 96, 100), 0.45, 0.2),
    'steel_bare':     lambda n: metal(n, (160, 162, 166), 0.35),
    'aluminium':      lambda n: metal(n, (200, 202, 206), 0.28),
    'chrome':         lambda n: metal(n, (230, 232, 236), 0.08, brushed=False),
    'brass':          lambda n: metal(n, (200, 160, 90), 0.3, brushed=False),
    'copper':         lambda n: metal(n, (200, 120, 80), 0.3, brushed=False),
    'glass_clear':    lambda n: glass(n),
    'glass_window':   lambda n: glass(n, (225, 235, 245), 0.03),
    # wood
    'wood_oak':       lambda n: wood(n, (150, 108, 70), 'X'),
    'wood_walnut':    lambda n: wood(n, (92, 62, 42), 'X'),
    'wood_pine':      lambda n: wood(n, (186, 146, 100), 'X'),
    'wood_floor':     lambda n: wood(n, (128, 90, 60), 'Y', varnish=0.4),
    'plywood':        lambda n: wood(n, (196, 162, 118), 'X', ring_scale=3.0, dark=0.8),
    # soft
    'fabric_sofa':    lambda n: fabric(n, (66, 74, 82)),
    'fabric_cushion': lambda n: fabric(n, (150, 92, 60)),
    'fabric_rug':     lambda n: fabric(n, (110, 70, 58), weave=180.0),
    'leather_brown':  lambda n: leather(n),
    'paper_white':    lambda n: paper(n),
    'cardboard':      lambda n: matte(n, (168, 128, 84), 0.9, 0.12),
    # plastics and gear
    'plastic_black':  lambda n: plastic(n, (22, 22, 24), 0.42),
    'plastic_grey':   lambda n: plastic(n, (120, 122, 124), 0.45),
    'plastic_white':  lambda n: plastic(n, (220, 220, 216), 0.4),
    'plastic_red':    lambda n: plastic(n, (170, 30, 26), 0.35),
    'plastic_blue':   lambda n: plastic(n, (40, 84, 160), 0.35),
    'plastic_yellow': lambda n: plastic(n, (226, 180, 40), 0.35),
    'rubber_black':   lambda n: rubber(n),
    'pcb_green':      lambda n: plastic(n, (24, 92, 52), 0.3),
    'ceramic_black':  lambda n: ceramic(n, (24, 24, 26)),
    'ceramic_white':  lambda n: ceramic(n, (228, 226, 220)),
    'plant_leaf':     lambda n: plant(n),
    'soil':           lambda n: soil(n),
    'terracotta':     lambda n: matte(n, (168, 92, 62), 0.85, 0.1),
    # lights
    'lamp_warm':      lambda n: emissive(n, (255, 196, 140), 12.0, (240, 230, 210)),
    'led_green':      lambda n: emissive(n, (60, 255, 120), 18.0),
    'led_red':        lambda n: emissive(n, (255, 40, 30), 14.0),
}


def get(name):
    """A shared material from LIBRARY (built once)."""
    m = _CACHE.get(name)
    if m is None or m.name not in bpy.data.materials:
        m = LIBRARY[name](name)
        _CACHE[name] = m
    return m
