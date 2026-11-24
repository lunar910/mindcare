"""Version 5 of the excerpt: Nox's loft at night, rendered for real (Cycles path tracing), in short PS2-cutscene shots.

    python excerpt5.py stills OUT --times 1.0,4.3:nox_work [--res 576x1024] [--samples 24]
    python excerpt5.py frames OUT --frames 0:737 [--step 1]
    python excerpt5.py layout OUT            # one quick low-sample still per shot (framing check)

The set is assembled from set5/* (built separately; a missing module falls back to a stand-in), the characters keep
their PBR materials (cast5), Nox sits (seat5), the acting is chore5, the lines and shots script5."""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from script5 import LINES, PHRASES, SHOTS, T_END
import chore5 as CHORE

FPS = 30
RES = (480, 854)
OUT_SIZE = (1080, 1920)
SAMPLES = 24
LOOK = 'AgX - Punchy'


def shot_at(t):
    for a, b, name in SHOTS:
        if a <= t < b:
            return name
    return SHOTS[-1][2]


def shot_range(name):
    return next((a, b) for a, b, n in SHOTS if n == name)


# ------------------------------------------------------------------ set
def _try(fn, what):
    try:
        return fn()
    except Exception as e:
        import traceback
        print(f'[set] {what} not available: {e!r}'[:300])
        traceback.print_exc(limit=2)
        return None


def standin_room():
    import kit5
    P = kit5.Prop('standin_room')
    P.box('floor', (9.0, 8.0, 0.05), (-0.5, 0.0, -0.025), 'concrete_floor', bevel=0)
    P.box('wall_left', (0.2, 8.0, 3.4), (-5.1, 0, 1.7), 'brick_painted', bevel=0)
    P.box('wall_right', (0.2, 8.0, 3.4), (4.1, 0, 1.7), 'plaster_warm', bevel=0)
    P.box('wall_front', (9.0, 0.2, 3.4), (-0.5, -4.1, 1.7), 'plaster_warm', bevel=0)
    P.box('ceiling', (9.0, 8.0, 0.2), (-0.5, 0, 3.5), 'concrete_wall', bevel=0)
    P.box('wall_back_r', (2.0, 0.2, 3.4), (3.0, 4.1, 1.7), 'brick_old', bevel=0)
    P.box('sill', (7.0, 0.3, 0.70), (-1.5, 4.1, 0.35), 'concrete_wall', bevel=0)
    for x in np.arange(-5.0, 2.01, 1.0):
        P.box('mullion', (0.06, 0.08, 2.45), (x, 4.0, 1.925), 'steel_black', bevel=0.003)
    for z in (0.70, 1.55, 2.35, 3.15):
        P.box('transom', (7.0, 0.08, 0.05), (-1.5, 4.0, z), 'steel_black', bevel=0.003)
    P.box('above', (7.0, 0.2, 0.25), (-1.5, 4.1, 3.275), 'concrete_wall', bevel=0)
    hinge = bpy.data.objects.new('door_hinge', None)
    bpy.context.scene.collection.objects.link(hinge)
    hinge.location = (4.0, 1.70, 0.0)
    P.box('door', (0.05, 0.95, 2.10), (0.0, -0.475, 1.05), 'wood_walnut', parent=hinge)
    return dict(prop=P, door_hinge=hinge, lights=[])


def assemble(W):
    """The loft: shell (set5.arch), city (set5.city), Nox's workstation (set5.workstation), lived-in props
    (set5.living).  A module that fails falls back to a stand-in / nothing, so the shot still renders."""
    import kit5
    S = {}
    arch = _try(lambda: __import__('set5.arch', fromlist=['build']).build(front_dressing=True), 'arch')
    S['arch'] = arch or standin_room()
    S['city'] = _try(lambda: __import__('set5.city', fromlist=['build']).build(), 'city')
    ws = _try(lambda: __import__('set5.workstation', fromlist=['build_bench']), 'workstation')
    if ws:
        S['bench'] = _try(lambda: kit5.place(ws.build_bench(), (-3.15, 3.55, 0.0), 0.0), 'bench')
        S['stool'] = _try(lambda: kit5.place(ws.build_stool(), (CHORE.NOX_PIVOT.x, CHORE.NOX_PIVOT.y, 0.0), 0.0), 'stool')
        S['iron'] = _try(lambda: ws.build_iron(), 'iron')
        bpy.context.view_layer.update()
        B = S.get('bench')
        if B is not None:
            W['anchors'] = dict(board=B.parts['board'].matrix_world.translation.copy(),
                                stand=B.parts['iron_rest'].matrix_world.translation.copy())
            W['iron_parked'] = B.parts['iron_rest'].matrix_world.copy()
    lv = _try(lambda: __import__('set5.living', fromlist=['build_sofa']), 'living')
    if lv:
        def put(name, fn, loc, hd, *a):
            p = _try(lambda: getattr(lv, fn)(*a), fn)
            if p is not None:
                kit5.place(p, loc, hd)
                S[name] = p
            return p
        S['living_zone'] = _try(lambda: lv.living_zone(), 'living_zone')
        for i, y in enumerate((-2.45, -1.20, 0.05)):
            put(f'shelf{i}', 'build_shelving_filled', (-4.75, y, 0.0), 90.0, i + 1)
        put('pegboard', 'build_pegboard', (-4.97, 2.75, 0.0), 90.0)
        put('drawers', 'build_drawer_cabinet', (-4.70, 2.75, 0.0), 90.0)
        put('kitchen', 'build_kitchenette', (2.95, 3.68, 0.0), 0.0)
        put('plant_small', 'build_plant_small', (-1.95, 3.62, 0.78), 0.0)
    ex = _try(lambda: __import__('set5.extras', fromlist=['build_bip']), 'extras')
    if ex:
        for name, fn, loc, hd in (('ball', 'build_basketball', (0.35, -0.80, 0.0), 0.0),
                                  ('skate', 'build_skateboard', (3.80, -0.30, 0.0), 90.0),
                                  ('bag', 'build_gym_bag', (2.70, -0.95, 0.0), 30.0),
                                  ('bip', 'build_bip', (-1.84, 3.80, 0.78), 205.0)):
            p = _try(lambda: getattr(ex, fn)(), fn)
            if p is not None:
                kit5.place(p, loc, hd)
                S[name] = p
    return S


# ------------------------------------------------------------------ lights
def room_lights(W):
    import look5
    L = {}
    # the night through the glazing: big soft cool sources just inside the window (city glow + sky)
    for i, x in enumerate((-3.9, -1.5, 0.9)):
        L[f'win{i}'] = look5.area(f'win{i}', (x, 3.85, 1.95), (x, 0.0, 1.2), 180.0, (0.42, 0.56, 1.0), 2.2, 2.2)
    # a faint bounce from the floor / room so that shadows are not black
    L['amb'] = look5.area('amb', (0.0, -1.0, 3.3), (0.0, -1.0, 0.0), 60.0, (0.55, 0.62, 0.85), 6.0, 5.0)
    return L


def character_lights(W):
    """Cinema cheats per shot: a soft key and a rim so that faces read (as in the reference)."""
    import look5
    C = {}
    C['key'] = look5.area('char_key', (0, 0, 2), (0, 0, 1), 0.0, (1.0, 0.84, 0.66), 0.7)
    C['rim'] = look5.area('char_rim', (0, 0, 2), (0, 0, 1), 0.0, (0.55, 0.7, 1.0), 0.6)
    return C


SHOT_LIGHT = {
    # shot: (key position, key target, key W, rim position, rim target, rim W)
    'establish':    None,
    'door':         ((2.6, 0.6, 2.2), (3.6, 1.3, 1.3), 40, None, None, 0),
    'nox_work':     ((-2.4, 3.6, 1.5), (-3.1, 2.9, 1.15), 25, (-3.6, 2.0, 1.9), (-3.1, 2.8, 1.2), 30),
    'pico_ms':      ((-2.4, 2.7, 2.0), (-1.55, 1.75, 1.45), 45, (-0.6, 1.2, 2.2), (-1.55, 1.75, 1.5), 40),
    'insert_watch': None,
    'nox_cu_work':  ((-2.5, 3.6, 1.45), (-3.1, 2.9, 1.15), 20, (-3.7, 2.1, 1.8), (-3.1, 2.8, 1.2), 30),
    'pico_react':   ((-2.4, 1.0, 2.0), (-1.6, 1.8, 1.5), 40, (-0.9, 2.6, 2.0), (-1.55, 1.75, 1.55), 40),
    'swivel':       ((-1.6, 2.6, 2.2), (-3.0, 2.8, 1.1), 25, None, None, 0),
    'nox_cu':       ((-2.2, 1.7, 1.9), (-3.05, 2.75, 1.2), 35, (-3.6, 3.6, 1.8), (-3.05, 2.8, 1.25), 45),
    'pico_cu':      ((-2.5, 2.2, 1.9), (-1.6, 1.8, 1.5), 40, (-0.9, 2.6, 2.0), (-1.55, 1.75, 1.55), 45),
    'two':          ((-3.2, 0.6, 2.2), (-2.3, 2.3, 1.2), 35, None, None, 0),
}


def set_shot_lights(W, shot):
    C = W['clights']
    cfg = SHOT_LIGHT.get(shot)
    for k in ('key', 'rim'):
        C[k].data.energy = 0.0
    if not cfg:
        return
    kp, kt, kw, rp, rt, rw = cfg
    import look5
    for o, p, tg, e in ((C['key'], kp, kt, kw), (C['rim'], rp, rt, rw)):
        if p is None:
            continue
        o.location = p
        o.rotation_euler = (Vector(tg) - Vector(p)).to_track_quat('-Z', 'Y').to_euler()
        o.data.energy = e


# ------------------------------------------------------------------ cameras
def camera_setup(W, cam, name, t=None):
    """Locked-off cameras (pos, target, lens mm on a 36 mm wide sensor; the frame is upright 9:16), depth of field on
    the close shots.  'nox_cu' pushes in slowly; 'insert_watch' is aimed at the wrist found at build time."""
    import look5
    cam.data.dof.use_dof = False
    M = W['marks_extra']
    if name == 'establish':
        look5.aim(cam, (-1.15, 1.05, 1.48), (-2.95, 3.85, 1.42), 26)
    elif name == 'door':
        look5.aim(cam, (2.05, -0.55, 1.22), (3.95, 1.20, 1.15), 24)
    elif name == 'nox_work':
        look5.aim(cam, (-4.30, 3.50, 1.20), (-2.20, 1.90, 1.15), 26)
        look5.dof(cam, (Vector((-3.1, 2.95, 1.15)) - Vector((-4.30, 3.50, 1.20))).length, 4.0)
    elif name == 'pico_ms':
        p, tg = (-3.25, 3.65, 1.78), M['pico_face'] - Vector((0, 0, 0.16))
        look5.aim(cam, p, tg, 72)
        look5.dof(cam, (tg - Vector(p)).length, 3.2)
    elif name == 'insert_watch':
        w = W['watch_pt']
        d = W['watch_view']
        p = w + d * 0.36
        look5.aim(cam, p, w, 60)
        look5.dof(cam, (w - p).length, 2.4)
    elif name == 'nox_cu_work':
        p, tg = (-2.80, 3.80, 1.28), M['nox_face_work'] + Vector((0.0, 0.0, -0.02))
        look5.aim(cam, p, tg, 42)
        look5.dof(cam, (tg - Vector(p)).length, 2.8)
    elif name == 'pico_react':
        hp = W['headings']['pico_face']
        f = Vector((math.sin(hp), -math.cos(hp), 0))
        a = math.radians(-38)
        d = Vector((f.x * math.cos(a) - f.y * math.sin(a), f.x * math.sin(a) + f.y * math.cos(a), 0))
        tg = M['pico_face'] - Vector((0, 0, 0.05))
        p = tg + d * 1.30 + Vector((0, 0, 0.0))
        look5.aim(cam, p, tg, 42)
        look5.dof(cam, (tg - p).length, 2.8)
    elif name == 'swivel':
        look5.aim(cam, (-0.55, 1.62, 1.62), (-3.10, 2.80, 0.95), 30)
    elif name == 'nox_cu':
        h = W['headings']['nox_to_pico']
        f = Vector((math.sin(h), -math.cos(h), 0))
        face = M['nox_face_up']
        dist = 1.05                                 # the slow push-in on the punchline is done in finish() (PUSH)
        p = face + f * dist + Vector((0, 0, 0.16)) + Vector((-f.y, f.x, 0)) * 0.12
        look5.aim(cam, p, face, 45)
        look5.dof(cam, (face - p).length, 2.8)
    elif name == 'pico_cu':
        tg = M['pico_face']
        p = M['nox_face_up'] + (tg - M['nox_face_up']).normalized() * 0.55 + Vector((0.08, 0.10, 0.02))
        look5.aim(cam, p, tg, 50)
        look5.dof(cam, (tg - p).length, 2.8)
    elif name == 'two':
        look5.aim(cam, (-3.60, 0.60, 1.30), (-2.20, 2.25, 1.10), 30)
    return cam


# ------------------------------------------------------------------ build
def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import addon_utils
    addon_utils.enable('cycles', default_set=True)
    import look5
    import cast5
    W = {}
    look5.setup(RES[0], RES[1], SAMPLES)
    try:
        bpy.context.scene.view_settings.look = LOOK
    except Exception:
        pass
    if not bpy.context.scene.world:
        look5.world((0.008, 0.012, 0.028), 1.0)
    W['set'] = assemble(W)
    if not bpy.context.scene.world:
        look5.world((0.008, 0.012, 0.028), 1.0)
    W['lights'] = room_lights(W)
    W['clights'] = character_lights(W)
    W['pico'] = cast5.actor('pico', CHORE.PICO_CLIPS)
    W['nox'] = cast5.actor('nox', CHORE.NOX_CLIPS)
    if W.get('anchors'):
        CHORE.set_anchors(**W['anchors'])
    W['perf'] = CHORE.performers(W, sys.modules[__name__])
    hand_tracks(W)
    # the watch light (green, pulsing): a tiny light at the back of Pico's left wrist
    ld = bpy.data.lights.new('watch_led', 'POINT')
    ld.color = (0.25, 1.0, 0.45)
    ld.shadow_soft_size = 0.004
    W['watch_led'] = bpy.data.objects.new('watch_led', ld)
    bpy.context.scene.collection.objects.link(W['watch_led'])
    # where the wrist is in the insert (for its camera)
    tm = 0.5 * sum(shot_range('insert_watch'))
    pose_at(W, tm)
    W['watch_pt'] = watch_point(W)
    to_nox = CHORE.NOX_PIVOT + Vector((0, 0, 1.15)) - W['watch_pt']
    to_nox.z = 0.0
    side = Vector((-to_nox.y, to_nox.x, 0.0)).normalized()
    W['watch_view'] = (to_nox.normalized() * 0.8 + side * 0.35 + Vector((0, 0, 0.25))).normalized()
    W['cam'] = look5.camera('cam', 35)
    return W


def hand_tracks(W):
    """Real finger poses (hands5) for both characters, per moment of the scene, plus the wrist's overlapping action."""
    if not (getattr(W['nox'], 'hands5', False) and getattr(W['pico'], 'hands5', False)):
        return
    import hands5
    T = W['times']
    a, b, c2 = T['iron']
    wl = CHORE.word(E_SELF, 'l02d', 'laisse')
    w_ok = CHORE.word(E_SELF, 'l02c', 'ok')
    w_montre = CHORE.word(E_SELF, 'l01', 'montre')
    drape = {'base': 'relaxed', 'index': (22, 28, 18), 'middle': (26, 32, 20), 'ring': (30, 36, 22), 'pinky': (34, 40, 26)}
    hip = {'base': 'flat', 'index': (10, 12, 8), 'middle': (12, 14, 8), 'ring': (14, 16, 10), 'pinky': (16, 18, 12),
           'thumb_spread': 25}
    nox_r = hands5.HandTrack([(0.0, 'pen'), (b + 0.05, drape), (wl - 0.10, 'palm_up_open')], xfade=0.35)
    nox_l = hands5.HandTrack([(0.0, 'pen'), (a + 0.10, drape)], xfade=0.45)
    pico_l = hands5.HandTrack([(0.0, 'relaxed'), (T['t_plant'], hip), (w_montre - 0.45, 'loose_fist'), (10.25, hip),
                               (23.65, 'relaxed')], xfade=0.35)
    pico_r = hands5.HandTrack([(0.0, 'relaxed'), (w_ok - 0.20, 'palm_up_open'), (w_ok + 0.85, 'relaxed')], xfade=0.25)
    hands5.install(W['perf']['nox'], left=nox_l, right=nox_r, seed=2.0)
    hands5.install(W['perf']['pico'], left=pico_l, right=pico_r, seed=5.0)


E_SELF = sys.modules[__name__]
CHORE_MOD = CHORE


def watch_point(W):
    """The back of Pico's left wrist, where the watch sits (world)."""
    arm = W['pico'].arm
    import acting as AC
    h = AC.joint(arm, 'LeftHand')
    fa = AC.joint(arm, 'LeftForeArm')
    P = W['perf']['pico']
    R0, f0, p0 = P.rest_hand['Left']
    M = (arm.matrix_world @ arm.pose.bones['LeftHand'].matrix).to_3x3().normalized()
    palm = (M @ (R0.inverted() @ p0)).normalized()
    return h + (fa - h).normalized() * 0.035 - palm * 0.028


def pose_at(W, t):
    import acting as AC
    # the door: flung open at T_DOOR (0 -> 104 deg in 0.16 s), a small bounce back, then it stays
    hinge = W['set']['arch']['door_hinge']
    td = CHORE.T_DOOR
    if t < td:
        ang = 0.0
    else:
        x = t - td
        ang = 104.0 * min(1.0, x / 0.16) ** 0.7 if x < 0.16 else 104.0 - 12.0 * math.sin(min(1.0, (x - 0.16) / 0.5) * math.pi) * math.exp(-(x - 0.16) * 2.0)
    hinge.rotation_euler.z = -math.radians(ang)
    pico = W['pico']
    pico.mesh.hide_render = t < CHORE.RUN_A[0] + 0.08
    W['perf']['pico'].pose(max(t, CHORE.RUN_A[0]))
    W['perf']['nox'].pose(t)
    for who in ('pico', 'nox'):
        a = W[who]
        vals = W['face'][who].values(t)
        vals.update(W['perf'][who].eyes(t))
        a.express(vals)
    # the stool's seat turns with Nox
    st = W['set'].get('stool')
    if st is not None and 'pivot' in st.parts:
        st.parts['pivot'].rotation_euler.z = W['nox'].heading - W['headings']['nox_work']
    # the iron: in his right hand while he works, then in its stand
    iron = W['set'].get('iron')
    if iron is not None:
        arm = W['nox'].arm
        if W['iron_in_hand'](t):
            if getattr(W['nox'], 'hands5', False):
                import hands5
                iron.root.matrix_world = hands5.pen_frame(arm, 'R')
            else:
                Mh = arm.matrix_world @ arm.pose.bones['RightHand'].matrix
                iron.root.matrix_world = Mh @ W.get('iron_offset', IRON_OFFSET)
        else:
            iron.root.matrix_world = W.get('iron_parked', Matrix.Translation(CHORE.ANCH['stand']))
    # the watch light pulses (only after the run)
    led = W['watch_led']
    led.location = watch_point(W)
    led.data.energy = W.get('led_power', 0.6) * CHORE.pulse(t)
    bpy.context.view_layer.update()


IRON_OFFSET = Matrix.Translation((0.0, 0.09, 0.02))     # refined once the iron prop is known


# ------------------------------------------------------------------ rendering
# Locked-off shots: the set is rendered once per shot as a clean high-sample PLATE (moving things hidden); each frame
# then renders only a border around the moving things at low samples, and is merged into the plate where it differs
# (characters, their shadows and bounce light, the door).  The background never boils from frame to frame.
PLATE_SAMPLES = 160
FRAME_SAMPLES = 8
PUSH = {'nox_cu': (1.0, 1.14)}            # 2D push-in over the shot (start, end zoom), done in finish()


def dynamic_objects(W):
    out = [W['pico'].mesh, W['nox'].mesh]
    for o in bpy.context.scene.objects:
        if o.type == 'MESH' and o.name.startswith(('noxR', 'picoR')) and o not in out and not o.hide_render:
            if o.parent in (W['pico'].arm, W['nox'].arm):
                out.append(o)
    hinge = W['set']['arch']['door_hinge']
    out += [o for o in hinge.children_recursive if o.type in ('MESH', 'CURVE')]
    iron = W['set'].get('iron')
    if iron is not None:
        out += [o for o in iron.root.children_recursive if o.type in ('MESH', 'CURVE')]
    st = W['set'].get('stool')
    if st is not None and 'pivot' in st.parts:
        out += [o for o in st.parts['pivot'].children_recursive if o.type in ('MESH', 'CURVE')]
    return out


def screen_box(W, cam):
    """Normalised screen rectangle (x0, y0, x1, y1) covering the moving things, or None for the full frame."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    pts = []
    for who in ('pico', 'nox'):
        a = W[who]
        if a.mesh.hide_render:
            continue
        for pb in a.arm.pose.bones:
            for q in (pb.head, pb.tail):
                pts.append(a.arm.matrix_world @ q)
        hf = a.arm.matrix_world @ a.arm.pose.bones['Head'].head
        pts += [hf + Vector((dx, dy, dz)) for dx in (-0.25, 0.25) for dy in (-0.25, 0.25) for dz in (-0.1, 0.45)]
    for o in dynamic_objects(W):
        if o in (W['pico'].mesh, W['nox'].mesh) or o.hide_render:
            continue
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs, ys = [], []
    for p in pts:
        v = world_to_camera_view(sc, cam, p)
        if v.z <= 0.05:
            return None
        xs.append(v.x)
        ys.append(v.y)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    x0, x1 = min(xs) - 0.08, max(xs) + 0.08
    y0, y1 = min(ys) - 0.12, max(ys) + 0.05          # more room below: shadows fall on the floor
    x0, y0, x1, y1 = max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)
    if x1 <= x0 or y1 <= y0:
        return (0.0, 0.0, 0.0, 0.0)
    if (x1 - x0) * (y1 - y0) > 0.75:
        return None
    return (x0, y0, x1, y1)


def _render(path, samples, box=None):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    r = sc.render
    if box is None:
        r.use_border = False
    else:
        r.use_border, r.use_crop_to_border = True, False
        r.border_min_x, r.border_min_y, r.border_max_x, r.border_max_y = box
    r.filepath = path
    r.image_settings.color_mode = 'RGBA'
    bpy.ops.render.render(write_still=True)
    r.image_settings.color_mode = 'RGB'
    r.use_border = False


def render_plate(W, shot, path):
    if os.path.exists(path):
        return path
    a, b = shot_range(shot)
    pose_at(W, a + 0.01)
    camera_setup(W, W['cam'], shot, a)
    set_shot_lights(W, shot)
    dyn = dynamic_objects(W)
    was = {o.name: o.hide_render for o in dyn}
    led = W['watch_led'].data.energy
    for o in dyn:
        o.hide_render = True
    W['watch_led'].data.energy = 0.0
    t = time.time()
    _render(path, PLATE_SAMPLES)
    print(f'plate {shot} {time.time() - t:.0f} s', flush=True)
    for o in dyn:
        o.hide_render = was[o.name]
    W['watch_led'].data.energy = led
    return path


def merge(raw, plate, box):
    """Frame pixels where they differ from the plate (blurred difference, dilated, feathered), plate elsewhere."""
    from PIL import Image, ImageFilter
    fr = np.asarray(Image.open(raw).convert('RGBA')).astype(np.float32)
    pl = np.asarray(Image.open(plate).convert('RGB')).astype(np.float32)
    H, Wd = pl.shape[:2]
    out = pl.copy()
    if box == (0.0, 0.0, 0.0, 0.0):
        return out
    x0, x1 = int(box[0] * Wd), int(math.ceil(box[2] * Wd))
    y0, y1 = int((1 - box[3]) * H), int(math.ceil((1 - box[1]) * H))
    f = fr[y0:y1, x0:x1, :3]
    p = pl[y0:y1, x0:x1]
    d = np.abs(f - p).mean(axis=2)
    dm = Image.fromarray(np.clip(d * 4, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.0))
    d = np.asarray(dm).astype(np.float32) / 4
    m = np.clip((d - 3.0) / 6.0, 0, 1)
    mi = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(3.0))
    m = np.asarray(mi).astype(np.float32) / 255
    # fade to the plate at the border edges so that the rectangle never shows
    hh, ww = m.shape
    ey = np.minimum(np.arange(hh), np.arange(hh)[::-1]) / 6.0
    ex = np.minimum(np.arange(ww), np.arange(ww)[::-1]) / 6.0
    m *= np.clip(np.minimum(ey[:, None], ex[None, :]), 0, 1)
    out[y0:y1, x0:x1] = p * (1 - m[..., None]) + f * m[..., None]
    return out


def render_frame(W, t, path, shot=None, samples=None, plates=None):
    shot = shot or shot_at(t)
    pose_at(W, t)
    camera_setup(W, W['cam'], shot, t)
    set_shot_lights(W, shot)
    raw = path.replace('.png', '_raw.png')
    if plates:
        plate = render_plate(W, shot, f'{plates}/{shot}.png')
        pose_at(W, t)
        camera_setup(W, W['cam'], shot, t)
        box = screen_box(W, W['cam'])
        _render(raw, samples or FRAME_SAMPLES, box)
        img = merge(raw, plate, box if box is not None else (0.0, 0.0, 1.0, 1.0))
    else:
        _render(raw, samples or SAMPLES)
        from PIL import Image
        img = np.asarray(Image.open(raw).convert('RGB')).astype(np.float32)
    finish(img, path, shot, t)
    if os.path.exists(raw):
        os.remove(raw)
    return path


def finish(img, out, shot=None, t=None):
    """Push-in (2D) where asked, upscale to 1080x1920 (Lanczos), a mild unsharp mask, a whisper of grain."""
    from PIL import Image, ImageFilter
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    if shot in PUSH and t is not None:
        a, b = shot_range(shot)
        x = min(1.0, max(0.0, (t - a) / (b - a)))
        k = x * x * (3 - 2 * x)
        z = PUSH[shot][0] + (PUSH[shot][1] - PUSH[shot][0]) * k
        w, h = im.size
        cw, ch = w / z, h / z
        cx, cy = w / 2, h * 0.42                         # zoom towards the eyes (upper part of the frame)
        box = (cx - cw / 2, max(0.0, cy - ch * 0.42), cx + cw / 2, max(0.0, cy - ch * 0.42) + ch)
        im = im.transform((w, h), Image.EXTENT, box, Image.BICUBIC)
    if OUT_SIZE and im.size != OUT_SIZE:
        im = im.resize(OUT_SIZE, Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=40, threshold=2))
    a = np.asarray(im).astype(np.float32)
    rng = np.random.default_rng(abs(hash(out)) % (2 ** 32))
    a += rng.normal(0, 1.6, a.shape[:2])[..., None]
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(out)


def main():
    global RES, SAMPLES, OUT_SIZE
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('out')
    ap.add_argument('--frames', default=None)
    ap.add_argument('--times', default=None)
    ap.add_argument('--res', default=None)
    ap.add_argument('--samples', type=int, default=None)
    ap.add_argument('--step', type=int, default=1)
    ap.add_argument('--native', action='store_true', help='keep the render size (no upscale)')
    ap.add_argument('--plates', action='store_true', help='static plate per shot + border renders (production)')
    a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
    if a.res:
        RES = tuple(int(x) for x in a.res.split('x'))
    if a.samples:
        SAMPLES = a.samples
    if a.native:
        OUT_SIZE = None
    os.makedirs(f'{a.out}/px', exist_ok=True)
    os.makedirs(f'{a.out}/plates', exist_ok=True)
    t0 = time.time()
    W = build()
    print(f'build {time.time() - t0:.0f} s', flush=True)
    if a.cmd == 'stills':
        for x in a.times.split(','):
            shot = None
            if ':' in x:
                x, shot = x.split(':')
            t = float(x)
            t1 = time.time()
            render_frame(W, t, f'{a.out}/px/t{t:06.2f}{"_" + shot if shot else ""}.png', shot,
                         plates=f'{a.out}/plates' if a.plates else None)
            print(f'still {t} {shot or shot_at(t)} {time.time() - t1:.1f} s', flush=True)
    elif a.cmd == 'layout':
        for s0, s1, name in SHOTS:
            t = 0.5 * (s0 + s1)
            t1 = time.time()
            render_frame(W, t, f'{a.out}/px/layout_{name}.png', name)
            print(f'layout {name} {time.time() - t1:.1f} s', flush=True)
    elif a.cmd == 'frames':
        n = int(round(T_END * FPS))
        f0, f1 = (0, n - 1) if not a.frames else (int(x) for x in a.frames.split(':'))
        for f in range(f0, f1 + 1, a.step):
            p = f'{a.out}/px/f{f:05d}.png'
            if os.path.exists(p):
                continue
            t1 = time.time()
            render_frame(W, f / FPS, p, plates=f'{a.out}/plates' if a.plates else None)
            print(f'frame {f} {shot_at(f / FPS)} {time.time() - t1:.1f} s', flush=True)
    print(f'done {time.time() - t0:.0f} s', flush=True)


if __name__ == '__main__':
    main()
