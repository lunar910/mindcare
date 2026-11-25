"""Version 6 eyeballs: a STATIC, depth-flattened ellipsoid the eyelids can hug; the gaze slides the iris in the SHADER.

    import eyes6
    L = eyes6.build('nox.eyeL')                       # dict: root, eye, holder, gaze, material (+ radius, depth, iris_radius)
    L['root'].parent = head_object_or_bone_proxy      # origin of root = centre of the ellipsoid
    eyes6.set_gaze(L, yaw, pitch)                     # radians of unit-sphere rotation; +yaw = iris to +X (character's left), +pitch = up
    eyes6.set_gaze(L, *eyes6.shift_to_gaze(L, 0.004, -0.001))     # or: iris centre 4 mm to the left, 1 mm down
    eyes6.set_look(L, iris_rgb=(0.23, 0.12, 0.06), pupil=0.30)    # brown, smaller pupil

Convention (same as the cast): metres, the character faces -Y, +Z up, +X = the character's LEFT.

Objects
    root    empty, origin = centre of the ellipsoid, uniform scale 1.  Parent THIS to the head.
    eye     mesh, child of root (identity transform): ellipsoid with radii (radius, depth, radius) on X, Y, Z, front pole at
            (0, -depth, 0).  Pole-free quad-sphere topology (2352 triangles), smooth, analytic normals.  It never rotates.
    holder  empty, child of root, scale (radius, depth, radius): its local space maps the ellipsoid to the unit sphere.
    gaze    empty, child of holder, rotation_mode 'XYZ'.  rotation_euler.z = yaw, rotation_euler.x = pitch.  The iris is
            centred on its local -Y axis.  (Its parent-inverse matrix holds a Z mirror so that +pitch moves the iris UP:
            do not clear the parent inverse or re-parent it.)

Shader (Cycles, one Principled BSDF, no refraction / transmission / volume)
    'gaze_coord'   Texture Coordinate (object = gaze)   -> unit-sphere coordinates that turn with the gaze: iris, pupil,
                                                           corneal bulge.
    'static_coord' Texture Coordinate (object = holder) -> unit-sphere coordinates of the static eye: sclera falloff, veins,
                                                           upper-lid shade.
    The crisp catch-light comes from the coat layer, whose normal is bumped into a spherical corneal cap over the iris disc
    (the real ellipsoid is far too flat there: its reflection of a soft box would cover half the iris).  The diffuse iris
    under it uses a slightly CONCAVE normal, so the side of the iris opposite the key light glows a little, as in a real eye.

Parameter nodes (material.node_tree.nodes[<name>]; Value/RGB nodes -> .outputs[0].default_value, or use set_look()):
    'iris_rgb' (LINEAR rgb, the mid-tone of the iris), 'pupil' (fraction of the iris radius), 'iris_rho' (= iris_radius /
    radius, radians on the unit sphere), 'cornea' (sine of the edge slope of the corneal cap, 0 = flat), 'iris_concavity',
    'lid_shade' (0..1 darkening under the upper lid) with its range in the Map Range node 'lid_shade_range' (static z on the
    unit sphere: From Min/From Max), 'sclera_rgb', 'sclera_edge_rgb' with its range in 'sclera_edge_range' (distance from
    the front pole on the unit sphere), 'vein_strength', 'limbal_strength', 'cornea_roughness' (coat over the iris: the
    crisp catch-light), 'sclera_roughness' (coat over the white: a softer wet sheen).
"""
import math

import bpy
from mathutils import Matrix, Vector

SCLERA_SRGB = (232, 228, 222)
SCLERA_EDGE_SRGB = (180, 142, 134)


def srgb(r, g, b):
    """sRGB (0-255, or 0-1 floats) -> the LINEAR rgb this module expects for iris_rgb."""
    v = [c / 255.0 if max(r, g, b) > 1.0 else c for c in (r, g, b)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v)


# ---------------------------------------------------------------------------------------------------------------- mesh
def _ellipsoid_mesh(name, rx, ry, rz, n=14):
    """Quad-sphere (6 warped grids of n x n quads, no pole anywhere) scaled to the radii; analytic split normals."""
    frames = (((1, 0, 0), (0, 1, 0), (0, 0, 1)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
              ((0, 1, 0), (0, 0, 1), (1, 0, 0)), ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
              ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (0, 1, 0), (1, 0, 0)))
    unit, index, faces = [], {}, []
    ts = [math.tan((i / n - 0.5) * math.pi / 2) for i in range(n + 1)]

    def vid(p):
        p = p.normalized()
        key = (round(p.x, 5), round(p.y, 5), round(p.z, 5))
        if key not in index:
            index[key] = len(unit)
            unit.append(p)
        return index[key]

    for w, u, v in frames:
        w, u, v = Vector(w), Vector(u), Vector(v)
        g = [[vid(w + u * ts[i] + v * ts[j]) for j in range(n + 1)] for i in range(n + 1)]
        for i in range(n):
            for j in range(n):
                faces.append((g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]))
    me = bpy.data.meshes.new(name)
    me.from_pydata([(p.x * rx, p.y * ry, p.z * rz) for p in unit], [], faces)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    me.update()
    try:
        me.normals_split_custom_set_from_vertices([Vector((p.x / rx, p.y / ry, p.z / rz)).normalized() for p in unit])
    except Exception:
        pass
    return me


# ------------------------------------------------------------------------------------------------------------- shader
class _G:
    """Tiny node-graph builder: every method returns an output socket; arguments are sockets or constants."""

    def __init__(self, nt):
        self.nt = nt

    def new(self, kind, name=None, **props):
        n = self.nt.nodes.new(kind)
        if name:
            n.name = n.label = name
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif isinstance(v, (tuple, list)) and len(v) == 3 and len(sock.default_value) == 4:
            sock.default_value = tuple(v) + (1.0,)
        else:
            sock.default_value = v

    def value(self, name, v):
        n = self.new('ShaderNodeValue', name)
        n.outputs[0].default_value = v
        return n.outputs[0]

    def rgb(self, name, c):
        n = self.new('ShaderNodeRGB', name)
        n.outputs[0].default_value = tuple(c[:3]) + (1.0,)
        return n.outputs[0]

    def m(self, op, a, b=None, c=None, clamp=False):
        n = self.new('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        self.put(n.inputs[2], c)
        return n.outputs[0]

    def v(self, op, a, b=None, scale=None):
        n = self.new('ShaderNodeVectorMath', operation=op)
        self.put(n.inputs[0], a)
        self.put(n.inputs[1], b)
        if scale is not None:
            self.put(n.inputs['Scale'], scale)
        return n.outputs[0]

    def smooth(self, x, lo, hi, to0=0.0, to1=1.0, name=None, kind='SMOOTHSTEP'):
        n = self.new('ShaderNodeMapRange', name, interpolation_type=kind)
        for key, val in (('Value', x), ('From Min', lo), ('From Max', hi), ('To Min', to0), ('To Max', to1)):
            self.put(n.inputs[key], val)
        return n.outputs[0]

    def mix(self, fac, a, b):
        n = self.new('ShaderNodeMix', data_type='RGBA', blend_type='MIX', clamp_factor=True)
        self.put(n.inputs[0], fac)
        self.put(n.inputs[6], a)
        self.put(n.inputs[7], b)
        return n.outputs[2]

    def noise(self, vec, scale, detail=2.0, rough=0.5, distortion=0.0):
        n = self.new('ShaderNodeTexNoise', noise_dimensions='3D')
        self.put(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        n.inputs['Distortion'].default_value = distortion
        return n.outputs[0]

    def xyz(self, x, y, z):
        n = self.new('ShaderNodeCombineXYZ')
        for s, val in zip(n.inputs, (x, y, z)):
            self.put(s, val)
        return n.outputs[0]

    def sep(self, vec):
        n = self.new('ShaderNodeSeparateXYZ')
        self.put(n.inputs[0], vec)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def bump(self, height, name=None):
        n = self.new('ShaderNodeBump', name)
        n.inputs['Strength'].default_value = 1.0
        n.inputs['Distance'].default_value = 1.0          # heights are given in metres (object space of the eye mesh)
        self.put(n.inputs['Height'], height)
        return n.outputs[0]


def _material(name, gaze, holder, radius, iris_radius, iris_rgb, pupil):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    g = _G(nt)
    out = g.new('ShaderNodeOutputMaterial')
    bsdf = g.new('ShaderNodeBsdfPrincipled', 'eye_bsdf')
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])

    # ---- parameters (named nodes)
    p_rgb = g.rgb('iris_rgb', iris_rgb)
    p_pupil = g.value('pupil', pupil)
    p_rho = g.value('iris_rho', iris_radius / radius)
    p_radius = g.value('radius_m', radius)
    p_cornea = g.value('cornea', 0.62)
    p_conc = g.value('iris_concavity', 0.40)
    p_lid = g.value('lid_shade', 0.45)
    p_scl = g.rgb('sclera_rgb', srgb(*SCLERA_SRGB))
    p_scl_edge = g.rgb('sclera_edge_rgb', srgb(*SCLERA_EDGE_SRGB))
    p_vein = g.value('vein_strength', 0.30)
    p_limbal = g.value('limbal_strength', 0.92)
    p_crough = g.value('cornea_roughness', 0.045)
    p_srough = g.value('sclera_roughness', 0.15)

    # ---- coordinates: q turns with the gaze (iris axis = -Y), s is static (front pole = -Y); both on the unit sphere
    tcg = g.new('ShaderNodeTexCoord', 'gaze_coord', object=gaze)
    tch = g.new('ShaderNodeTexCoord', 'static_coord', object=holder)
    q, s = tcg.outputs['Object'], tch.outputs['Object']
    qx, qy, qz = g.sep(q)
    sx, sy, sz = g.sep(s)
    lat = g.m('SQRT', g.m('ADD', g.m('MULTIPLY', qx, qx), g.m('MULTIPLY', qz, qz)))
    rho = g.m('ARCTAN2', lat, g.m('MULTIPLY', qy, -1.0))            # angle from the iris axis = distance on the unit sphere
    t = g.m('DIVIDE', rho, p_rho)                                   # 0 centre of the pupil .. 1 edge of the iris
    tc = g.m('MINIMUM', t, 1.0)
    inv = g.m('DIVIDE', 1.0, g.m('MAXIMUM', lat, 1e-5))
    dx, dz = g.m('MULTIPLY', qx, inv), g.m('MULTIPLY', qz, inv)     # unit direction around the iris axis (no atan2 seam)

    # ---- pupil and position across the iris annulus
    pm = g.smooth(t, g.m('SUBTRACT', p_pupil, 0.015), g.m('ADD', p_pupil, 0.015))        # 0 in the pupil, soft 3 % edge
    u = g.m('DIVIDE', g.m('SUBTRACT', t, p_pupil), g.m('MAXIMUM', g.m('SUBTRACT', 1.0, p_pupil), 0.05), clamp=True)

    # ---- radial fibres: noise sampled on a circle (polar angle) and barely stretched along the radius
    def ring_vec(freq, radial, off):
        return g.xyz(g.m('MULTIPLY_ADD', dx, freq, off[0]), g.m('MULTIPLY_ADD', dz, freq, off[1]),
                     g.m('MULTIPLY_ADD', t, radial, off[2]))

    n1 = g.noise(ring_vec(6.0, 1.1, (0.0, 0.0, 0.0)), 1.0, 3.0, 0.60)
    n2 = g.noise(ring_vec(15.0, 2.2, (11.3, 4.1, 2.7)), 1.0, 2.0, 0.55)
    n3 = g.noise(ring_vec(1.4, 1.6, (3.7, 9.2, 5.0)), 1.0, 2.0, 0.50)
    fib = g.smooth(g.m('ADD', g.m('MULTIPLY', n1, 0.62), g.m('MULTIPLY', n2, 0.38)), 0.36, 0.66, kind='LINEAR')
    patch = g.smooth(n3, 0.36, 0.64)

    dark = g.v('SCALE', p_rgb, scale=0.11)
    light = g.v('ADD', g.v('SCALE', p_rgb, scale=0.86), (0.006, 0.006, 0.006))
    col = g.mix(fib, dark, light)
    # lighter, warmer collarette around the pupil (central heterochromia), broken up by the low-frequency patches
    warm = g.v('ADD', g.v('MULTIPLY', p_rgb, (1.35, 0.98, 0.50)), (0.034, 0.019, 0.004))
    warm = g.v('SCALE', warm, scale=g.m('MULTIPLY_ADD', fib, 0.80, 0.22))
    ring = g.m('MULTIPLY', g.smooth(u, 0.0, 0.06), g.smooth(u, 0.10, 0.48, 1.0, 0.0))
    col = g.mix(g.m('MULTIPLY', ring, g.m('MULTIPLY_ADD', patch, 0.45, 0.40)), col, warm)
    # the outer half is a little deeper, then the soft limbal ring
    col = g.v('SCALE', col, scale=g.smooth(t, 0.40, 0.88, 1.0, 0.62))
    limb = g.m('MULTIPLY', g.smooth(t, 0.72, 0.975), p_limbal)
    col = g.mix(limb, col, (0.010, 0.012, 0.016))
    col = g.mix(pm, (0.0025, 0.0025, 0.003), col)                    # pupil

    # ---- sclera: off-white, pinker and darker towards the rim of the static eye, faint veins near the sides
    lat_s = g.m('SQRT', g.m('ADD', g.m('MULTIPLY', sx, sx), g.m('MULTIPLY', sz, sz)))
    scl = g.mix(g.smooth(lat_s, 0.16, 0.88, name='sclera_edge_range'), p_scl, p_scl_edge)
    va = g.noise(s, 4.2, 3.0, 0.60, 1.4)
    vb = g.noise(g.v('ADD', s, (5.1, 2.3, 7.7)), 8.5, 2.0, 0.55, 1.0)
    la = g.smooth(g.m('ABSOLUTE', g.m('SUBTRACT', va, 0.5)), 0.0, 0.028, 1.0, 0.0)
    lb = g.smooth(g.m('ABSOLUTE', g.m('SUBTRACT', vb, 0.5)), 0.0, 0.022, 0.6, 0.0)
    where = g.m('MULTIPLY', g.smooth(lat_s, 0.34, 0.72), g.smooth(g.noise(g.v('ADD', s, (1.9, 8.4, 3.3)), 2.4), 0.40, 0.62))
    vein = g.m('MULTIPLY', g.m('MULTIPLY', g.m('MAXIMUM', la, lb), where), p_vein)
    scl = g.mix(vein, scl, (0.50, 0.085, 0.065))

    # ---- iris over sclera (soft outer edge of the limbal ring), then the shade of the upper lid (static)
    iris = g.smooth(t, 0.965, 1.055, 1.0, 0.0)
    base = g.mix(iris, scl, col)
    lid = g.m('MULTIPLY', g.smooth(sz, 0.0, 0.30, name='lid_shade_range'), p_lid)
    base = g.v('SCALE', base, scale=g.m('SUBTRACT', 1.0, lid))
    not_iris = g.m('SUBTRACT', 1.0, iris)

    # ---- normals: spherical corneal cap for the coat (catch-light), shallow bowl for the diffuse iris
    ri = g.m('MULTIPLY', p_rho, p_radius)                            # iris radius in metres
    k = g.m('MAXIMUM', p_cornea, 1e-3)
    k2 = g.m('MULTIPLY', k, k)
    cap = g.m('SUBTRACT', g.m('SQRT', g.m('SUBTRACT', 1.0, g.m('MULTIPLY', k2, g.m('MULTIPLY', tc, tc)))),
              g.m('SQRT', g.m('SUBTRACT', 1.0, k2)))
    h_cornea = g.m('MULTIPLY', g.m('DIVIDE', cap, k), ri)
    h_iris = g.m('MULTIPLY', g.m('MULTIPLY', g.m('SUBTRACT', g.m('MULTIPLY', tc, tc), 1.0), 0.5), g.m('MULTIPLY', p_conc, ri))
    n_cornea = g.bump(h_cornea, 'cornea_bump')
    n_iris = g.bump(h_iris, 'iris_bump')

    # ---- surface
    I = bsdf.inputs
    g.put(I['Base Color'], base)
    I['Roughness'].default_value = 0.30                              # base gloss only exists on the sclera (see below)
    I['IOR'].default_value = 1.40
    g.put(I['Specular IOR Level'], g.m('MULTIPLY', not_iris, 0.5))   # the iris itself is matte: its gloss is the cornea
    g.put(I['Normal'], n_iris)
    g.put(I['Subsurface Weight'], g.m('MULTIPLY', not_iris, 0.28))   # sclera only
    I['Subsurface Radius'].default_value = (1.0, 0.50, 0.35)
    I['Subsurface Scale'].default_value = 0.0016
    I['Coat Weight'].default_value = 1.0
    cornea = g.smooth(t, 1.0, 1.14, 1.0, 0.0)                        # crisp over the cornea, softer wet sheen on the white
    g.put(I['Coat Roughness'], g.m('ADD', g.m('MULTIPLY', cornea, p_crough),
                                   g.m('MULTIPLY', g.m('SUBTRACT', 1.0, cornea), p_srough)))
    I['Coat IOR'].default_value = 1.45
    g.put(I['Coat Normal'], n_cornea)
    return mat


# ---------------------------------------------------------------------------------------------------------- public API
def build(name, radius=0.0245, depth=0.0148, iris_radius=0.0077, iris_rgb=(0.20, 0.42, 0.30), pupil=0.38, collection=None):
    """Build one eye at the origin. Returns {'root', 'eye', 'holder', 'gaze', 'material', 'radius', 'depth', 'iris_radius'}.

    radius       half width/height of the ellipsoid (X and Z), depth = half thickness (Y), metres.
    iris_radius  metres on the real surface at the front pole (works up to ~0.0095).
    iris_rgb     LINEAR rgb mid-tone of the iris (use eyes6.srgb(r, g, b) to convert a picked colour).
    pupil        pupil radius as a fraction of the iris radius."""
    col = collection or bpy.context.scene.collection
    root = bpy.data.objects.new(f'{name}.root', None)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = radius
    holder = bpy.data.objects.new(f'{name}.holder', None)
    holder.empty_display_size = 1.0
    holder.empty_display_type = 'SPHERE'
    holder.parent = root
    holder.scale = (radius, depth, radius)
    gaze = bpy.data.objects.new(f'{name}.gaze', None)
    gaze.empty_display_type = 'SINGLE_ARROW'
    gaze.empty_display_size = 1.2
    gaze.parent = holder
    gaze.rotation_mode = 'XYZ'
    gaze.matrix_parent_inverse = Matrix.Diagonal((1.0, 1.0, -1.0, 1.0))       # mirror Z: +rotation_euler.x = iris UP
    mat = _material(f'{name}.mat', gaze, holder, radius, iris_radius, iris_rgb, pupil)
    eye = bpy.data.objects.new(f'{name}.eye', _ellipsoid_mesh(f'{name}.eye', radius, depth, radius))
    eye.parent = root
    eye.data.materials.append(mat)
    for o in (root, holder, gaze, eye):
        col.objects.link(o)
    for o in (root, holder, gaze):
        o.hide_render = True
    root['eyes6_radius'], root['eyes6_depth'], root['eyes6_iris_radius'] = radius, depth, iris_radius
    return {'root': root, 'eye': eye, 'holder': holder, 'gaze': gaze, 'material': mat,
            'radius': radius, 'depth': depth, 'iris_radius': iris_radius}


def set_gaze(parts, yaw, pitch):
    """Unit-sphere rotation in radians: +yaw slides the iris towards +X (the character's left), +pitch slides it up."""
    parts['gaze'].rotation_euler = (pitch, 0.0, yaw)


def gaze_to_shift(parts, yaw, pitch):
    """(yaw, pitch) -> (dx, dz): where the iris centre sits, in metres from the front pole, seen from the front."""
    r = parts['radius']
    return r * math.sin(yaw) * math.cos(pitch), r * math.sin(pitch)


def shift_to_gaze(parts, dx, dz):
    """Desired position of the iris centre, metres from the front pole measured in the XZ plane (as seen from the front;
    +dx = the character's left, +dz = up) -> (yaw, pitch) for set_gaze()."""
    r = parts['radius']
    pitch = math.asin(max(-0.95, min(0.95, dz / r)))
    yaw = math.asin(max(-0.95, min(0.95, dx / (r * math.cos(pitch)))))
    return yaw, pitch


def iris_center(parts, yaw=None, pitch=None):
    """Centre of the iris on the surface, in ROOT space (metres), for the given or the current gaze."""
    if yaw is None:
        e = parts['gaze'].rotation_euler
        yaw, pitch = e.z, e.x
    r, d = parts['radius'], parts['depth']
    return Vector((r * math.sin(yaw) * math.cos(pitch), -d * math.cos(yaw) * math.cos(pitch), r * math.sin(pitch)))


def look_at(parts, target_world, eyeball_radius=0.0135, max_shift=0.0085):
    """Aim at a world-space point as a real eyeball of the given radius would (the iris slides by radius * sin(angle)),
    clamped to max_shift metres. Returns (yaw, pitch) after setting them. Call it after the head is posed
    (bpy.context.view_layer.update())."""
    p = parts['root'].matrix_world.inverted() @ Vector(target_world)
    if p.length < 1e-9:
        set_gaze(parts, 0.0, 0.0)
        return 0.0, 0.0
    d = p.normalized()
    dx, dz = eyeball_radius * d.x, eyeball_radius * d.z
    if d.y > 0.0:                                   # target behind the face: keep the direction, push to the limit
        k = max_shift / max(math.hypot(dx, dz), 1e-9)
        dx, dz = dx * k, dz * k
    n = math.hypot(dx, dz)
    if n > max_shift:
        dx, dz = dx * max_shift / n, dz * max_shift / n
    yaw, pitch = shift_to_gaze(parts, dx, dz)
    set_gaze(parts, yaw, pitch)
    return yaw, pitch


def set_look(parts, iris_rgb=None, pupil=None, iris_radius=None, cornea=None, lid_shade=None, vein_strength=None):
    """Change the look after build (None = keep). iris_rgb is LINEAR; pupil is a fraction of the iris radius;
    iris_radius in metres; cornea 0..0.8 (bulge of the catch-light cap); lid_shade 0..1."""
    nd = parts['material'].node_tree.nodes
    if iris_rgb is not None:
        nd['iris_rgb'].outputs[0].default_value = tuple(iris_rgb[:3]) + (1.0,)
    if pupil is not None:
        nd['pupil'].outputs[0].default_value = pupil
    if iris_radius is not None:
        nd['iris_rho'].outputs[0].default_value = iris_radius / parts['radius']
        parts['iris_radius'] = iris_radius
        parts['root']['eyes6_iris_radius'] = iris_radius
    for key, val in (('cornea', cornea), ('lid_shade', lid_shade), ('vein_strength', vein_strength)):
        if val is not None:
            nd[key].outputs[0].default_value = val
