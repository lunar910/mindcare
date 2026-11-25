"""Version 5 modelling kit: real-scale primitives with bevelled edges (nothing in the real world has a razor edge,
and the bevel highlight is what makes CG props read as objects), grouped under one empty per prop.

Units: metres, Z up.  A prop is built at the origin, standing on Z = 0, its FRONT facing -Y (towards the camera side),
then placed with place(prop, (x, y, z), heading_deg).

    P = kit5.Prop('workbench')                 # an empty + a collection
    P.box('top', (1.8, 0.75, 0.04), (0, 0, 0.74), 'wood_oak', bevel=0.004)
    P.cyl('leg', 0.02, 0.72, (0.85, 0.33, 0.36), 'steel_black')
    kit5.place(P, (-2.8, 3.3, 0), 180)

Every part gets: the material (a mat5 library name or a bpy material), smooth shading with auto-smooth, and a bevel
modifier (width in metres, 2-3 segments) unless bevel=0."""
import math
import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

import mat5


def _mat(m):
    if m is None:
        return None
    return mat5.get(m) if isinstance(m, str) else m


def _finish(ob, mat, bevel, segments=2, smooth=True, angle=40.0):
    if mat is not None:
        ob.data.materials.append(_mat(mat))
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = True
        try:
            ob.data.set_sharp_from_angle(angle=math.radians(angle))
        except Exception:
            pass
    if bevel:
        b = ob.modifiers.new('bevel', 'BEVEL')
        b.width = bevel
        b.segments = segments
        b.limit_method = 'ANGLE'
        b.angle_limit = math.radians(35)
        b.harden_normals = False
        b.use_clamp_overlap = True
    return ob


class Prop:
    def __init__(self, name, collection=None):
        self.name = name
        self.col = bpy.data.collections.new(name)
        (collection or bpy.context.scene.collection).children.link(self.col)
        self.root = bpy.data.objects.new(name, None)
        self.root.empty_display_size = 0.2
        self.col.objects.link(self.root)
        self.parts = {}

    def _add(self, name, me, loc, rot, mat, bevel, segments=2, smooth=True, parent=None):
        ob = bpy.data.objects.new(f'{self.name}.{name}', me)
        self.col.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = Euler(tuple(math.radians(a) for a in rot))
        ob.parent = parent or self.root
        _finish(ob, mat, bevel, segments, smooth)
        key, i = name, 1
        while key in self.parts:
            i += 1
            key = f'{name}{i}'
        self.parts[key] = ob
        return ob

    # ---- primitives (sizes are full sizes, loc is the centre)
    def box(self, name, size, loc, mat, rot=(0, 0, 0), bevel=0.003, segments=2, parent=None):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        bm.to_mesh(me)
        bm.free()
        return self._add(name, me, loc, rot, mat, bevel, segments, parent=parent)

    def cyl(self, name, r, h, loc, mat, rot=(0, 0, 0), verts=32, bevel=0.002, r2=None, cap=True, parent=None):
        """Cylinder (or cone/frustum with r2) along local Z, centred at loc."""
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=h)
        bm.to_mesh(me)
        bm.free()
        return self._add(name, me, loc, rot, mat, bevel, parent=parent)

    def sphere(self, name, r, loc, mat, scale=(1, 1, 1), segments=32, rings=16, parent=None):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=r)
        bmesh.ops.scale(bm, vec=Vector(scale), verts=bm.verts)
        bm.to_mesh(me)
        bm.free()
        return self._add(name, me, loc, (0, 0, 0), mat, 0, parent=parent)

    def torus(self, name, R, r, loc, mat, rot=(0, 0, 0), parent=None):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        segs, rs = 48, 12
        verts = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            row = []
            for j in range(rs):
                b = 2 * math.pi * j / rs
                row.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))))
            verts.append(row)
        for i in range(segs):
            for j in range(rs):
                bm.faces.new((verts[i][j], verts[(i + 1) % segs][j], verts[(i + 1) % segs][(j + 1) % rs], verts[i][(j + 1) % rs]))
        bm.to_mesh(me)
        bm.free()
        return self._add(name, me, loc, rot, mat, 0, parent=parent)

    def plane(self, name, size, loc, mat, rot=(0, 0, 0), parent=None):
        """A flat rectangle in local XY (size = (x, y)), e.g. a poster (rot=(90,0,0) stands it up facing -Y)."""
        me = bpy.data.meshes.new(name)
        w, h = size[0] / 2, size[1] / 2
        me.from_pydata([(-w, -h, 0), (w, -h, 0), (w, h, 0), (-w, h, 0)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name='UVMap')
        for i, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
            uv.data[i].uv = c
        return self._add(name, me, loc, rot, mat, 0, smooth=False, parent=parent)

    def tube(self, name, points, radius, mat, resolution=6, parent=None):
        """A cable / pipe through world-space points (relative to the prop origin), smooth Bezier."""
        cu = bpy.data.curves.new(name, 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = radius
        cu.bevel_resolution = 3
        cu.resolution_u = resolution
        sp = cu.splines.new('BEZIER')
        sp.bezier_points.add(len(points) - 1)
        for bp, p in zip(sp.bezier_points, points):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        ob = bpy.data.objects.new(f'{self.name}.{name}', cu)
        self.col.objects.link(ob)
        ob.parent = parent or self.root
        ob.data.materials.append(_mat(mat))
        self.parts[name] = ob
        return ob

    def mesh(self, name, verts, faces, loc, mat, rot=(0, 0, 0), bevel=0.0, smooth=True, parent=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.validate()
        return self._add(name, me, loc, rot, mat, bevel, smooth=smooth, parent=parent)

    def profile(self, name, outline, depth, loc, mat, rot=(0, 0, 0), bevel=0.002, parent=None):
        """Extrude a 2D outline [(x, z), ...] (in the XZ plane) by depth along Y: brackets, frames, lamp arms."""
        n = len(outline)
        y0, y1 = -depth / 2, depth / 2
        verts = [(x, y0, z) for x, z in outline] + [(x, y1, z) for x, z in outline]
        faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        return self.mesh(name, verts, faces, loc, mat, rot, bevel)

    def light(self, name, kind, loc, energy, color=(1.0, 0.85, 0.65), size=0.1, rot=(0, 0, 0), spot_deg=None, parent=None):
        """A real light belonging to the prop (lamp bulb, LED glow). color is linear 0-1."""
        ld = bpy.data.lights.new(f'{self.name}.{name}', kind)
        ld.energy = energy
        ld.color = color
        if kind == 'AREA':
            ld.size = size
        else:
            ld.shadow_soft_size = size
        if kind == 'SPOT' and spot_deg:
            ld.spot_size = math.radians(spot_deg)
            ld.spot_blend = 0.6
        ob = bpy.data.objects.new(f'{self.name}.{name}', ld)
        self.col.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = Euler(tuple(math.radians(a) for a in rot))
        ob.parent = parent or self.root
        self.parts[name] = ob
        return ob

    def add(self, child, loc=(0, 0, 0), heading=0.0):
        """Nest another prop inside this one (e.g. a mug on the bench)."""
        child.root.parent = self.root
        child.root.location = loc
        child.root.rotation_euler = (0, 0, math.radians(heading))
        return child


def place(prop, loc, heading=0.0):
    prop.root.location = loc
    prop.root.rotation_euler = (0, 0, math.radians(heading))
    return prop


def rng(seed):
    import random
    return random.Random(seed)
