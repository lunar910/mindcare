"""Nox and Pico as actors: Meshy rig + fingers, clips, face texture swaps (mouth, blink), root placement.   import cast2"""
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

import anim2
import rigext

S = '/tmp/claude-0/-home-user-mindcare/a7878755-9e4c-5740-b306-7f25e8d8722e/scratchpad'
RIG = S + '/meshy/models/rig'
ANIM = S + '/meshy/models/anim'
VAR = S + '/np3d_prod/out_face/var'
FIX = S + '/ps2/out_fix'
MATTE = True          # v2-v4: flat PS2 materials; v5 keeps Meshy's full PBR maps (normal, roughness)
FACE = 'facemorph'    # 'face6': the face rebuilt from separate parts (eyeballs, lids, teeth, tongue, jaw: face6.py)


def matte(ob):
    """Base colour only: no metal, no gloss, no normal map (the PS2 had none of that on a character)."""
    for m in ob.data.materials:
        if not m or not m.node_tree:
            continue
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                for k in ('Metallic', 'Roughness', 'Normal'):
                    for l in list(n.inputs[k].links):
                        m.node_tree.links.remove(l)
                n.inputs['Metallic'].default_value = 0.0
                n.inputs['Roughness'].default_value = 1.0
                n.inputs['Specular IOR Level'].default_value = 0.0
                if 'Coat Weight' in n.inputs:
                    n.inputs['Coat Weight'].default_value = 0.0


class Actor:
    def __init__(self, name, rig, clips, scale=1.0, smooth=1.0, glasses=False):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=f'{RIG}/{rig}.glb')
        new = [o for o in bpy.data.objects if o not in before]
        self.arm = next(o for o in new if o.type == 'ARMATURE')
        self.mesh = next(o for o in new if o.type == 'MESH' and o.vertex_groups)
        for o in new:
            if o.type == 'MESH' and not o.vertex_groups:
                o.hide_render = True                                   # stray helper geometry
        if self.arm.animation_data:
            self.arm.animation_data.action = None
        for b in self.arm.pose.bones:
            b.location = (0, 0, 0)
            b.rotation_mode = 'QUATERNION'
            b.rotation_quaternion = (1, 0, 0, 0)
        bpy.context.view_layer.update()
        rigext.add_fingers(self.arm, self.mesh)
        if MATTE:
            matte(self.mesh)
        # real facial expressions (shape keys) when the face has been located on this model (see faceprep.py)
        self.face = None
        self.face6 = None
        import facemorph
        if FACE == 'face6' and os.path.exists(f'{facemorph.OUT}/../out_face6/{name}_meta.json'):
            import face6
            self.face6 = face6.build(self.mesh, self.arm, name)
            self.face, self.face_keys, self.face_info = self.face6['F'], self.face6['keys'], {}
        elif os.path.exists(f'{facemorph.OUT}/{name}_landmarks.json'):
            self.face_keys, self.face_info, self.face = facemorph.build(self.mesh, self.arm, name, glasses=glasses)
        self.name, self.scale = name, scale
        self.root = bpy.data.objects.new(name + '_root', None)
        bpy.context.scene.collection.objects.link(self.root)
        self.arm.parent = self.root
        self.root.scale = (scale, scale, scale)
        # clips: 'talk' = this character's own file, 'nox2:shrug' = a clip downloaded for another rig, re-targeted here
        self.rest = anim2.rest_of(self.arm)
        self.clips = {}
        for k in clips:
            src, key = k.split(':') if ':' in k else (name, k)
            c = anim2.load_clip(f'{ANIM}/{src}_{key}.glb', f'{src}_{key}', smooth=smooth)
            self.clips[key] = anim2.retarget(c, self.rest) if src != name else c
        # face texture variants (mouth shapes, blink): PS2-style texture swaps
        self.tex_node = next(n for m in self.mesh.data.materials for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links)
        self.tex_base = self.tex_node.image
        cs = self.tex_base.colorspace_settings.name
        if os.path.exists(f'{FIX}/{name}_base.png'):                   # repainted texture (see fix_hood.py)
            self.tex_base = bpy.data.images.load(f'{FIX}/{name}_base.png')
            self.tex_base.colorspace_settings.name = cs
            self.tex_node.image = self.tex_base
        self.variants = {'closed': self.tex_base}
        for k in ('mouth_half', 'mouth_open', 'mouth_wide', 'blink'):
            p = f'{FIX}/{name}_{k}.png'
            if not os.path.exists(p):
                p = f'{VAR}/{name}_{k}.png'
            if os.path.exists(p):
                im = bpy.data.images.load(p)
                im.colorspace_settings.name = self.tex_base.colorspace_settings.name
                self.variants[k] = im
        bpy.context.view_layer.update()
        hb, nb = self.arm.pose.bones['Head'], self.arm.pose.bones['neck']
        front = Vector((0, -1, 0))                                     # the characters face -Y in their rest pose
        self.face_fwd = tuple(((self.arm.matrix_world @ hb.matrix).to_3x3().inverted() @ front).normalized())
        self.face_fwd_neck = tuple(((self.arm.matrix_world @ nb.matrix).to_3x3().inverted() @ front).normalized())
        self.heading = 0.0

    # ---- pose and placement
    def pose(self, clip_pose, bones=None):
        anim2.apply(self.arm, bones or next(iter(self.clips.values())).bones, clip_pose)

    def place(self, xy, heading):
        self.heading = heading
        self.root.rotation_euler = (0, 0, heading)
        self.root.location = (xy[0], xy[1], 0.0)

    def joint(self, bone):
        return self.arm.matrix_world @ self.arm.pose.bones[bone].head

    def feet_local(self):
        """Mid-point of the two ankles in the actor's own frame (metres, before heading and placement)."""
        bpy.context.view_layer.update()
        inv = self.root.matrix_world.inverted()
        p = (inv @ self.joint('LeftFoot') + inv @ self.joint('RightFoot')) / 2
        return Vector((p.x, p.y)) * self.scale

    def anchor(self, clip, t0, t1, n=7, loop=False):
        """Where the feet are on average while clip[t0..t1] plays (actor frame): used to stand the actor on a mark."""
        c = self.clips[clip]
        acc = Vector((0.0, 0.0))
        for k in range(n):
            tt = t0 + (t1 - t0) * k / max(n - 1, 1)
            self.pose(c.sample_loop(tt) if loop else c.sample(tt), c.bones)
            acc += self.feet_local()
        return acc / n

    def hips_map(self):
        """3x3 matrix: translation of the Hips bone (bone units) -> displacement in the actor's frame (metres)."""
        pb = self.arm.pose.bones['Hips']
        keep = pb.location.copy()
        inv = None
        cols = []
        pb.location = (0, 0, 0)
        bpy.context.view_layer.update()
        inv = self.root.matrix_world.inverted()
        p0 = inv @ self.joint('Hips')
        for i in range(3):
            v = [0.0, 0.0, 0.0]
            v[i] = 10.0
            pb.location = v
            bpy.context.view_layer.update()
            cols.append(((inv @ self.joint('Hips')) - p0) * (self.scale / 10.0))
        pb.location = keep
        bpy.context.view_layer.update()
        return np.array([[c[r] for c in cols] for r in range(3)])

    def hips_shift(self, anchor):
        """Hips translation (bone units) that brings a feet anchor (actor frame, metres) onto the actor's origin."""
        if not hasattr(self, '_hmap_inv'):
            self._hmap_inv = np.linalg.inv(self.hips_map())
        return self._hmap_inv @ np.array([-anchor[0], -anchor[1], 0.0])

    def root_for(self, mark, heading, anchor):
        R = Matrix.Rotation(heading, 2)
        v = R @ anchor
        return Vector((mark[0] - v.x, mark[1] - v.y))

    def facing(self):
        th = self.heading
        f = Vector((math.sin(th), -math.cos(th), 0.0))
        return f, Vector((-f.y, f.x, 0.0))

    def set_face(self, key):
        self.tex_node.image = self.variants.get(key, self.tex_base)

    def express(self, values):
        """Shape-key values of the face, e.g. {'browUp': 0.6, 'smile_L': 1, 'jawOpen': 0.3} (see facemorph.EXPR)."""
        import facemorph
        if self.face6 is not None:
            import face6
            face6.apply(self.face6, values)
        elif self.face is not None:
            facemorph.apply(self.mesh, facemorph.expand(values))

    def face_point(self):
        return self.joint('headfront')
