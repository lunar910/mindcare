"""MakeHuman-based character builder for headless Blender (bpy).

Data comes from the CC0 MakeHuman assets: base mesh, compiled targets,
default skeleton + weights, high-poly eyes.
Coordinates: MakeHuman is Y-up in decimetres, facing +Z.
Blender here is Z-up in metres, characters face -Y.
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

SP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MHD = os.path.join(SP, 'mh-data')
NPZ = os.path.join(SP, 'mh-pkg', 'makehuman', 'data', 'targets.npz')


def to_bl(a):
    a = np.asarray(a, dtype=np.float64)
    return np.stack([a[..., 0], -a[..., 2], a[..., 1]], axis=-1) * 0.1


# ---------------------------------------------------------------- base data
class _Base:
    def __init__(self):
        v, vt, faces = [], [], []
        group = None
        with open(os.path.join(MHD, 'base.obj')) as fh:
            for line in fh:
                if line.startswith('v '):
                    v.append([float(x) for x in line.split()[1:4]])
                elif line.startswith('vt '):
                    vt.append([float(x) for x in line.split()[1:3]])
                elif line.startswith('g '):
                    group = line.split()[1]
                elif line.startswith('f '):
                    vi, ti = [], []
                    for tok in line.split()[1:]:
                        p = tok.split('/')
                        vi.append(int(p[0]) - 1)
                        ti.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                    faces.append((vi, ti, group))
        self.v = np.array(v, dtype=np.float64)
        self.vt = np.array(vt, dtype=np.float64)
        self.faces = faces
        self.skel = json.load(open(os.path.join(MHD, 'rigs', 'default.mhskel')))
        self.weights = json.load(open(os.path.join(MHD, 'rigs', 'default_weights.mhw')))['weights']
        self.npz = np.load(NPZ)
        self._eye = None

    def target(self, name):
        k = 'targets/' + name
        if k + '.index' not in self.npz.files:
            return None
        return self.npz[k + '.index'].astype(np.int64), self.npz[k + '.vector'].astype(np.float64) * 1e-3

    def eye_proxy(self):
        if self._eye is None:
            ev, ef, evt = [], [], []
            with open(os.path.join(MHD, 'eyes', 'high-poly', 'high-poly.obj')) as fh:
                for line in fh:
                    if line.startswith('v '):
                        ev.append([float(x) for x in line.split()[1:4]])
                    elif line.startswith('vt '):
                        evt.append([float(x) for x in line.split()[1:3]])
                    elif line.startswith('f '):
                        vi, ti = [], []
                        for tok in line.split()[1:]:
                            p = tok.split('/')
                            vi.append(int(p[0]) - 1)
                            ti.append(int(p[1]) - 1 if len(p) > 1 and p[1] else -1)
                        ef.append((vi, ti))
            refs, scales, reading = [], {}, False
            with open(os.path.join(MHD, 'eyes', 'high-poly', 'high-poly.mhclo')) as fh:
                for line in fh:
                    t = line.split()
                    if not t or t[0].startswith('#'):
                        continue
                    if t[0] in ('x_scale', 'y_scale', 'z_scale'):
                        scales[t[0][0]] = (int(t[1]), int(t[2]), float(t[3]))
                    elif t[0] == 'verts':
                        reading = True
                    elif reading and len(t) == 9:
                        refs.append([float(x) for x in t])
                    elif reading and len(t) == 1:
                        refs.append([float(t[0]), float(t[0]), float(t[0]), 1, 0, 0, 0, 0, 0])
            self._eye = dict(v=np.array(ev), f=ef, vt=np.array(evt), refs=np.array(refs), scales=scales)
        return self._eye


_BASE = None


def base():
    global _BASE
    if _BASE is None:
        _BASE = _Base()
    return _BASE


# ---------------------------------------------------------------- morphing
def macro_weights(gender=1.0, age=0.5, muscle=0.5, weight=0.5, height=0.5, proportions=0.5, races=None):
    races = races or {'african': 1 / 3, 'asian': 1 / 3, 'caucasian': 1 / 3}
    G = {'female': 1 - gender, 'male': gender}
    if age < 0.5:
        baby = max(0.0, 1 - age * 5.333)
        young = max(0.0, (age - 0.1875) * 3.2)
        child = max(0.0, min(1.0, 5.333 * age) - young)
        old = 0.0
    else:
        baby = child = 0.0
        old = max(0.0, age * 2 - 1)
        young = 1 - old
    A = {'baby': baby, 'child': child, 'young': young, 'old': old}
    mx, mn = max(0.0, muscle * 2 - 1), max(0.0, 1 - muscle * 2)
    M = {'minmuscle': mn, 'averagemuscle': 1 - (mx + mn), 'maxmuscle': mx}
    wx, wn = max(0.0, weight * 2 - 1), max(0.0, 1 - weight * 2)
    W = {'minweight': wn, 'averageweight': 1 - (wx + wn), 'maxweight': wx}
    H = {'minheight': max(0.0, 1 - height * 2), 'maxheight': max(0.0, height * 2 - 1)}
    P = {'idealproportions': max(0.0, proportions * 2 - 1), 'uncommonproportions': max(0.0, 1 - proportions * 2)}
    tot = sum(races.values())
    R = {k: v / tot for k, v in races.items()}
    out = {}
    for g, gv in G.items():
        for a, av in A.items():
            for r, rv in R.items():
                out[f'macrodetails/{r}-{g}-{a}'] = rv * gv * av
            for m, mv in M.items():
                for w, wv in W.items():
                    b = gv * av * mv * wv
                    out[f'macrodetails/universal-{g}-{a}-{m}-{w}'] = b
                    for h, hv in H.items():
                        out[f'macrodetails/height/{g}-{a}-{m}-{w}-{h}'] = b * hv
                    for p, pv in P.items():
                        out[f'macrodetails/proportions/{g}-{a}-{m}-{w}-{p}'] = b * pv
    return {k: v for k, v in out.items() if v > 1e-5}


def morph(macro, details):
    B = base()
    V = B.v.copy()
    weights = macro_weights(**macro)
    weights.update(details or {})
    for name, w in weights.items():
        t = B.target(name)
        if t is None:
            if not name.startswith('macrodetails/proportions'):
                print('missing target', name)
            continue
        idx, d = t
        V[idx] += w * d
    return V


def expression_deltas(race_mix, units):
    """Blend expression-unit targets over the three ethnic variants."""
    B = base()
    out = {}
    tot = sum(race_mix.values())
    for u in units:
        D = np.zeros_like(B.v)
        for r, rv in race_mix.items():
            t = B.target(f'expression/units/{r}/{u}')
            if t is not None:
                D[t[0]] += (rv / tot) * t[1]
        out[u] = D
    return out


# ---------------------------------------------------------------- build
def joint_positions(V):
    B = base()
    return {n: V[np.array(ix)].mean(axis=0) for n, ix in B.skel['joints'].items()}


def _plane_normal(J, plane):
    p1, p2, p3 = (J[j] for j in plane)
    a = (p2 - p1) / (np.linalg.norm(p2 - p1) + 1e-12)
    b = (p3 - p2) / (np.linalg.norm(p3 - p2) + 1e-12)
    n = np.cross(b, a)
    return n / (np.linalg.norm(n) + 1e-12)


def build(name, macro, details=None, expr_units=(), race_mix=None, location=(0, 0, 0)):
    """Create body mesh + armature (+ eyes). Returns dict of objects/handles."""
    B = base()
    V = morph(macro, details)
    race_mix = race_mix or macro.get('races') or {'african': 1 / 3, 'asian': 1 / 3, 'caucasian': 1 / 3}

    body_faces = [f for f in B.faces if f[2] == 'body']
    used = sorted({i for f in body_faces for i in f[0]})
    remap = -np.ones(len(V), dtype=np.int64)
    remap[np.array(used)] = np.arange(len(used))
    Vb = to_bl(V[np.array(used)])

    me = bpy.data.meshes.new(name + '_body')
    me.from_pydata(Vb.tolist(), [], [[int(remap[i]) for i in f[0]] for f in body_faces])
    uv = me.uv_layers.new(name='UVMap')
    loop_uvs = []
    for f in body_faces:
        for ti in f[1]:
            loop_uvs.append(B.vt[ti] if ti >= 0 else (0, 0))
    uv.data.foreach_set('uv', np.array(loop_uvs, dtype=np.float32).ravel())
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    body = bpy.data.objects.new(name + '_body', me)
    bpy.context.scene.collection.objects.link(body)

    # shape keys: basis + expression units
    if expr_units:
        body.shape_key_add(name='Basis', from_mix=False)
        for u, D in expression_deltas(race_mix, expr_units).items():
            sk = body.shape_key_add(name=u, from_mix=False)
            co = Vb + to_bl(D[np.array(used)])
            sk.data.foreach_set('co', co.astype(np.float32).ravel())
            sk.value = 0.0

    # armature
    J = joint_positions(V)
    arm_data = bpy.data.armatures.new(name + '_rig')
    arm = bpy.data.objects.new(name + '_rig', arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    skel = B.skel
    order = []

    def visit(n):
        if n in order:
            return
        p = skel['bones'][n]['parent']
        if p:
            visit(p)
        order.append(n)

    for n in skel['bones']:
        visit(n)
    for n in order:
        bd = skel['bones'][n]
        eb = arm_data.edit_bones.new(n)
        h = to_bl(J[bd['head']])
        t = to_bl(J[bd['tail']])
        if np.linalg.norm(t - h) < 1e-4:
            t = h + np.array([0, 0, 0.01])
        eb.head, eb.tail = Vector(h), Vector(t)
        plane = bd.get('rotation_plane')
        if isinstance(plane, str) and plane in skel['planes']:
            nrm = to_bl(_plane_normal(J, skel['planes'][plane])) * 10
            y = (t - h) / np.linalg.norm(t - h)
            z = np.cross(nrm, y)
            if np.linalg.norm(z) > 1e-6:
                eb.align_roll(Vector(z / np.linalg.norm(z)))
        if bd['parent']:
            eb.parent = arm_data.edit_bones[bd['parent']]
    bpy.ops.object.mode_set(mode='OBJECT')

    # skin weights
    for bname, pairs in B.weights.items():
        vg = body.vertex_groups.new(name=bname)
        by_w = {}
        for vi, w in pairs:
            ni = remap[vi]
            if ni >= 0:
                by_w.setdefault(round(w, 4), []).append(int(ni))
        for w, ids in by_w.items():
            vg.add(ids, w, 'REPLACE')
    body.parent = arm
    mod = body.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm

    # eyes
    eyes = _build_eyes(name, V, arm)
    arm.location = location
    return dict(name=name, body=body, rig=arm, eyes=eyes, V=V, used=np.array(used), remap=remap, J=J)


def _build_eyes(name, V, arm):
    B = base()
    E = B.eye_proxy()
    sc = {}
    for ax, (a, b, ref) in E['scales'].items():
        sc[ax] = np.linalg.norm(V[a] - V[b]) / ref
    refs = E['refs']
    i1, i2, i3 = refs[:, 0].astype(int), refs[:, 1].astype(int), refs[:, 2].astype(int)
    P = refs[:, 3:4] * V[i1] + refs[:, 4:5] * V[i2] + refs[:, 5:6] * V[i3]
    off = refs[:, 6:9] * np.array([sc['x'], sc['y'], sc['z']])
    P = P + off
    Pb = to_bl(P)
    out = []
    # split the two eyes by x sign
    for side, sel in (('L', Pb[:, 0] > 0), ('R', Pb[:, 0] <= 0)):
        idx = np.where(sel)[0]
        remap = {int(o): k for k, o in enumerate(idx)}
        faces = [[remap[i] for i in f[0]] for f in E['f'] if all(i in remap for i in f[0])]
        me = bpy.data.meshes.new(f'{name}_eye{side}')
        me.from_pydata(Pb[idx].tolist(), [], faces)
        me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
        ob = bpy.data.objects.new(f'{name}_eye{side}', me)
        bpy.context.scene.collection.objects.link(ob)
        c = Pb[idx].mean(axis=0)
        # recentre origin at eyeball centre so procedural iris uses object coords
        me.transform(Matrix.Translation(Vector(-c)))
        ob.location = Vector(c)
        bone = arm.data.bones[f'eye.{side}']
        ob.parent = arm
        ob.parent_type = 'BONE'
        ob.parent_bone = f'eye.{side}'
        # keep world position: bone parenting puts object at bone tail
        tail = arm.matrix_world @ bone.tail_local
        ob.matrix_parent_inverse = (arm.matrix_world @ Matrix.Translation(bone.tail_local) @ bone.matrix_local.to_3x3().to_4x4()).inverted()
        ob.location = Vector(c)
        out.append(ob)
    return out


# ---------------------------------------------------------------- posing
def _upd():
    bpy.context.view_layer.update()


def pb(ch, n):
    return ch['rig'].pose.bones[n]


def rotate_arm_space(p, q):
    """Apply extra rotation q (armature space) about the bone head."""
    h = p.head.copy()
    p.matrix = Matrix.Translation(h) @ q.to_matrix().to_4x4() @ Matrix.Translation(-h) @ p.matrix
    _upd()


def aim(p, direction, twist_keep=True):
    d = Vector(direction).normalized()
    cur = (p.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()
    rotate_arm_space(p, cur.rotation_difference(d))


def rot(p, axis, deg):
    rotate_arm_space(p, Quaternion(Vector(axis).normalized(), math.radians(deg)))


def local_rot(p, x=0, y=0, z=0):
    p.rotation_mode = 'XYZ'
    p.rotation_euler = (math.radians(x), math.radians(y), math.radians(z))
    _upd()


def world_to_arm(ch, v):
    return ch['rig'].matrix_world.inverted() @ Vector(v)


def two_bone(root, target, l1, l2, pole):
    root, target, pole = Vector(root), Vector(target), Vector(pole)
    d = target - root
    dist = min(d.length, (l1 + l2) * 0.999)
    dist = max(dist, abs(l1 - l2) * 1.01)
    dn = d.normalized()
    a = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist)
    h = math.sqrt(max(0.0, 1 - a * a)) * l1
    pp = (pole - dn * pole.dot(dn)).normalized()
    return root + dn * (a * l1) + pp * h


def bone_len(ch, names):
    return sum(ch['rig'].data.bones[n].length for n in names)


def pose_limb(ch, chain_a, chain_b, target, pole):
    """chain_a: bones from root to mid joint, chain_b: mid joint to end. Target/pole in armature space."""
    a0 = pb(ch, chain_a[0])
    l1, l2 = bone_len(ch, chain_a), bone_len(ch, chain_b)
    mid = two_bone(a0.head, target, l1, l2, pole)
    for n in chain_a:
        aim(pb(ch, n), mid - a0.head)
    b0 = pb(ch, chain_b[0])
    for n in chain_b:
        aim(pb(ch, n), Vector(target) - b0.head)
    return mid


def curl_fingers(ch, side, amount=1.0, thumb=0.6):
    for f in range(2, 6):
        for s, deg in ((1, 22), (2, 35), (3, 25)):
            n = f'finger{f}-{s}.{side}'
            if n in ch['rig'].pose.bones:
                p = pb(ch, n)
                p.rotation_mode = 'XYZ'
                p.rotation_euler = (math.radians(deg * amount), 0, 0)
    for s, deg in ((2, 15), (3, 20)):
        n = f'finger1-{s}.{side}'
        p = pb(ch, n)
        p.rotation_mode = 'XYZ'
        p.rotation_euler = (math.radians(deg * thumb), 0, 0)
    _upd()
