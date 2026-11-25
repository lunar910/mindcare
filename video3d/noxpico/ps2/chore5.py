"""Version 5 choreography: who does what, moment by moment, in the loft (script5.py has the lines and the shots).

Same acting rules as version 4 (study/reports): held poses, one motivated one-handed gesture per line, eyes -> head ->
chest, fast-start turns that settle long, nods on the stressed vowel, blinks on head turns.  New in v5:
  - Nox SITS on a swivel stool at his bench (seat5.SeatedPerformer), back to the room, soldering: iron in the right
    hand, solder wire in the left, small real strokes only while nobody talks.  He ignores "Nox !", answers without
    turning, puts the iron in its stand, swivels to face her, and talks seated, looking up at her.
  - Pico's run is cheated across the cut 'door' -> 'nox_work' (two segments of the same sprint clip).
  - The watch: green light pulses under it after her run (pulse(t)), seen in the insert.

Positions are world metres (set5/SPEC.md).  Anchors that depend on the props (board, iron stand) are module constants
that excerpt5 overwrites from the built props (set_anchors)."""
import math
import re

import bpy
from mathutils import Matrix, Quaternion, Vector

import acting as AC
import face4
import perform as PF
import seat5

PICO_CLIPS = ('sprintstop', 'listen', 'hip')
NOX_CLIPS = ('listen',)

NOX_PIVOT = Vector((-3.10, 2.95, 0.0))
SEAT_Z = 0.52
PICO_MARK = Vector((-1.55, 1.75, 0.0))
DOOR_PT = Vector((3.95, 1.22, 0.0))
T_DOOR = 2.43                       # the door is flung open (before she reaches it: v5 critique)
RUN_A = (2.52, 0.00)                # (time, clip time): through the door, once it is open
RUN_B = (3.12, 0.55)                # (time, clip time): arriving behind Nox (after the cut)
CLIP_PLANT = 1.45                   # clip time of the final plant
ANCH = dict(board=Vector((-3.08, 3.33, 0.80)), stand=Vector((-2.62, 3.40, 0.86)))


def set_anchors(**kw):
    for k, v in kw.items():
        ANCH[k] = Vector(v)


def heading_to(src, dst):
    d = Vector(dst) - Vector(src)
    return math.atan2(d.x, -d.y)


def word_times(E, line_id):
    import script5
    return script5.word_times(line_id)


def word(E, line_id, w, nth=0):
    norm = lambda x: re.sub(r'[^\w]', '', x.lower())
    wt = word_times(E, line_id)
    hits = [s for ww, s, e in wt if norm(ww).startswith(w.lower())] or [s for ww, s, e in wt if w.lower() in norm(ww)]
    if not hits:
        raise KeyError(f'word {w!r} not in line {line_id}')
    return hits[nth]


def nod(tv, deg):
    return (tv - 0.10, 'nod', deg, 0.10, 0.25)


def held(t0, kind, deg, rise, hold, fall):
    return (t0, kind, deg, rise, hold, fall)


def pulse(t):
    """The optical heart-rate sensor: green flashes at ~2.3 Hz (a heart still racing after the run), 0..1."""
    if t < 4.0:
        return 0.0
    ph = (t * 2.3) % 1.0
    return max(0.0, 1.0 - ph / 0.18) if ph < 0.18 else 0.06


# ------------------------------------------------------------------ the performers
def performers(W, E):
    pico, nox = W['pico'], W['nox']
    T_END = E.T_END
    NOX_WORK = math.pi                                   # facing the window (+y)
    NOX_TO_PICO = heading_to(NOX_PIVOT, PICO_MARK)
    PICO_FACE = heading_to(PICO_MARK, NOX_PIVOT)
    W['headings'] = dict(nox_work=NOX_WORK, nox_to_pico=NOX_TO_PICO, pico_face=PICO_FACE)

    # ================================================================ PICO
    c = pico.clips['sprintstop']
    pico.place(tuple(PICO_MARK), 0.0)
    pico.pose(c.sample(RUN_A[1] + 0.17), c.bones)
    aA = pico.feet_local()
    pico.pose(c.sample(0.0), c.bones)
    a0 = pico.feet_local()
    pico.pose(c.sample(c.dur), c.bones)
    a1 = pico.feet_local()
    travel = a1 - a0
    want = (PICO_MARK - DOOR_PT).normalized()
    run_h = math.atan2(want.x, -want.y) - math.atan2(travel.x, -travel.y)
    t_plant = RUN_B[0] + (CLIP_PLANT - RUN_B[1])
    t_stop = RUN_B[0] + (1.10 - RUN_B[1])
    base_p = PF.BaseTrack(pico, [(RUN_A[0], 'sprintstop', RUN_A[1], 1.0, 0.0, 'clamp'),
                                 (RUN_B[0], 'sprintstop', RUN_B[1], 1.0, 0.0, 'clamp'),
                                 (t_plant - 0.15, 'hip', 0.55, 0.0, 0.60)])    # lands in a sporty recovery: left hand on hip (v4-acting)
    # segment A: the feet cross the threshold (DOOR_PT) 0.17 s into the clip; segment B ends on the mark
    R = Matrix.Rotation(-run_h, 2)
    L = R @ (DOOR_PT - PICO_MARK).to_2d()
    base_p.shift[0] = pico.hips_shift(aA - L)
    base_p.shift[1] = pico.hips_shift(a1)
    # the turn towards Nox happens in the last stride, not on planted feet (v4-body F3)
    heading_p = [(0.0, run_h), (t_plant - 0.45, run_h), (t_plant - 0.05, PICO_FACE), (T_END, PICO_FACE)]

    nox_face_work = NOX_PIVOT + Vector((0.0, 0.10, 1.18))          # his head, bent over the bench (from behind)
    nox_face_up = NOX_PIVOT + Vector((0.05, -0.03, 1.24))          # his face once he has turned round, seated
    pico_face = PICO_MARK + Vector((-0.03, 0.02, 1.52))
    fp = Vector((math.sin(PICO_FACE), -math.cos(PICO_FACE), 0))
    rp = Vector((-fp.y, fp.x, 0)) * -1
    chest_p = PICO_MARK + Vector((0, 0, 1.28))

    def pico_off(off):
        return chest_p + rp * off[0] + fp * off[1] + Vector((0, 0, off[2]))

    w_nox = word(E, 'l01', 'nox')
    w_montre = word(E, 'l01', 'montre')
    w_lum = word(E, 'l01', 'lumi')
    w_vertes = word(E, 'l01', 'vertes')
    w_run = word(E, 'l01', 'run')
    v1 = face4.stressed_vowels(E, 'l01', ['nox', 'vertes', 'run'])
    # the watch: left forearm up across her chest on "montre", back of the wrist to Nox (he has his back to her!),
    # pushed out on "run ?", kept up through the insert, lowered while the camera is on Nox
    show = (0.04, 0.27, -0.06)
    push = (0.05, 0.35, -0.04)
    look = (0.02, 0.30, 0.02)                                  # brought up to her own eyes during the insert
    palm_in, fing_x = (0.0, -1.0, 0.12), (1.0, 0.18, 0.12)
    g_watch = PF.Gesture('Left', [
        (w_montre - 0.50, (-0.18, 0.12, -0.32), None, None, 0.32),
        (w_montre + 0.10, show, palm_in, fing_x, 0.55),
        (w_run - 0.12, (show[0] + 0.005, show[1] + 0.01, show[2]), palm_in, fing_x, 0.55),
        (w_run + 0.10, push, palm_in, fing_x, 0.58),
        (8.40, (push[0], push[1] - 0.005, push[2] - 0.005), palm_in, fing_x, 0.58),
        (8.75, look, (0.15, -1.0, 0.25), fing_x, 0.5),
        (9.80, (look[0], look[1] + 0.01, look[2]), (0.15, -1.0, 0.25), fing_x, 0.5),
        (10.45, (-0.20, 0.03, -0.52), None, None, 0.32),
    ], elbow=(-0.50, -0.30, -0.80), ease_in=0.50, ease_out=0.45, profile='minjerk', thumb=0.65)
    w_ok = word(E, 'l02c', 'ok')
    rest_r, palm_rest, fing_down = (0.18, 0.02, -0.56), (-1.0, 0.0, 0.0), (0.05, 0.10, -1.0)
    ok_pos, palm_up, fing_fwd = (0.14, 0.28, -0.10), (0.2, 0.1, 1.0), (0.1, 1.0, 0.1)
    g_ok = PF.Gesture('Right', [                    # the right arm never hangs in the clip's A-pose (v5 critique)
        (t_stop - 0.05, rest_r, palm_rest, fing_down, 0.35),
        (t_stop + 0.60, rest_r, palm_rest, fing_down, 0.35),
        (w_ok - 0.30, rest_r, palm_rest, fing_down, 0.35),
        (w_ok + 0.05, ok_pos, palm_up, fing_fwd, 0.20),
        (w_ok + 0.55, (ok_pos[0] + 0.01, ok_pos[1] + 0.01, ok_pos[2] - 0.01), palm_up, fing_fwd, 0.22),
        (w_ok + 0.95, rest_r, palm_rest, fing_down, 0.35),
        (T_END + 1.0, rest_r, palm_rest, fing_down, 0.35),
    ], elbow=(0.6, -0.5, -0.6), ease_in=0.55, ease_out=0.05, profile='minjerk', thumb=0.3)
    # the end: she gives him her left wrist (from her hip), reluctantly, into his open hand
    g_give = PF.Gesture('Left', [
        (23.65, (-0.22, 0.02, -0.38), None, None, 0.32),
        (24.20, (-0.03, 0.40, -0.40), (0.0, 0.10, -1.0), (0.25, 1.0, -0.2), 0.45),
        (26.00, (-0.03, 0.41, -0.40), (0.0, 0.10, -1.0), (0.25, 1.0, -0.2), 0.45),
    ], elbow=(-0.5, -0.4, -0.7), ease_in=0.55, ease_out=0.05, profile='minjerk')
    w_jamais = word(E, 'l02c', 'jamais')
    w_dessous = word(E, 'l02c', 'dessous')
    v4 = face4.stressed_vowels(E, 'l02c', ['dessous', 'ok'])
    gaze_p = PF.Gaze([
        (0.0, nox_face_work, 0),
        (w_lum - 0.05, pico_off(show) + Vector((0, 0, 0.03)), 0, 0.45),     # "lumières": a glance at her watch...
        (w_vertes + 0.20, nox_face_work, 0),                                 # ...back to (the back of) his head
        (8.55, pico_off(look) + Vector((0, 0, 0.02)), 0, 1.0),               # the insert: she looks at the light herself
        (9.95, nox_face_work, 0),
        (14.20, lambda t: nox_face_up, 0),                                   # he turns round: she follows his face
        (w_jamais - 0.08, nox_face_up + Vector((0.45, -0.35, -0.30)), 0, 0.5),   # embarrassed, looks away
        (w_dessous - 0.05, nox_face_up, 0),
        (22.95, nox_face_up + Vector((0.0, 0.0, 0.60)), 0, 0.35),           # rolls her eyes (the head goes up a little)
        (23.55, nox_face_up, 0),
    ], origin=pico_face, head_delay=0.05, chest=0.35, chest_delay=0.05, head_weight=1.0, speed=0.55)
    w_pq = word(E, 'l01', 'pourquoi')
    acc_p = [held(t_stop - 0.05, 'lean', 6.0, 0.12, 0.0, 0.32),
             held(w_nox - 0.12, 'lean', 6.0, 0.18, 0.15, 0.35),
             nod(v1[0], 4.5),
             held(w_nox + 0.40, 'pitch', 7.0, 0.30, 0.25, 0.30),           # catching her breath, head down a moment
             held(w_pq - 0.15, 'lean', 3.0, 0.12, 0.30, 0.35),             # line start: the body leads the watch raise
             nod(w_pq - 0.02, 2.5),
             nod(v1[1], 4.5),                                                # "VERtes"
             held(w_run - 0.05, 'pitch', -8.0, 0.20, 1.5, 0.4),
             held(w_run - 0.05, 'lean', 4.0, 0.20, 1.5, 0.4),
             held(13.38, 'pitch', -5.0, 0.15, 0.45, 0.30),                  # "fais comme chez toi": chin up, offended
             held(13.38, 'roll', 4.0, 0.15, 0.45, 0.30),
             held(w_jamais - 0.08, 'pitch', 6.0, 0.25, 0.28, 0.25),         # embarrassed: down while looking away, one move back
             held(w_ok - 0.06, 'pitch', -8.0, 0.18, 2.8, 0.4),              # "ok ?": chin up, held into the two-shot
             held(w_ok - 0.06, 'roll', -5.0, 0.18, 2.8, 0.4),
             held(23.55, 'lean', 2.5, 0.15, 0.30, 0.40)]                   # leads the reluctant wrist
    life_p = PF.Life(seed=3.0, breath_rate=0.30, breath_deg=0.30, sway_cm=0.12, sway_rate=0.06, head_deg=0.35,
                     pant=(t_stop, t_stop + 5.0, 0.70, 1.0),
                     events=[(t_stop + 0.10, 0.25, 0.0, 0.35, 1.5),
                             (13.45, 0.12, 0.10, 0.45, -1.2)])                 # "pff": a short exhale through the nose
    # after the hard stop she settles her feet with two small steps (the clip blend moves them; each foot lifts as it
    # goes), then the feet are planted for good in the relaxed hip stance
    def pico_extra(P, t, phase):
        if phase != 'body':
            return
        arm = P.a.arm
        f, r, u = AC.body_frame(P.a)
        for s_, t0 in (('Left', t_plant + 0.12), ('Right', t_plant + 0.30)):
            lift = 0.055 * AC.bump(t, t0, 0.10, 0.0, 0.12)
            if lift > 1e-4:
                R = AC.world_rot(arm, f'{s_}Foot').copy()
                foot = AC.joint(arm, f'{s_}Foot') + Vector((0, 0, lift))
                pole = AC.joint(arm, f'{s_}Leg') + f * 0.6
                AC.ik2(arm, f'{s_}UpLeg', f'{s_}Leg', f'{s_}Foot', foot, pole)
                AC.set_world_rot(arm, f'{s_}Foot', R)

    perf_p = PF.Performer(pico, base_p, tuple(PICO_MARK), PICO_FACE, gaze=gaze_p, gestures=[g_watch, g_ok, g_give],
                          accents=acc_p, life=life_p, lock_from=t_plant + 0.55, heading_keys=heading_p,
                          lock_capture=0.0, lock_ramp=0.08, extra=pico_extra,
                          gaze_weight=[(0.0, 0.0), (t_stop - 0.3, 0.0), (t_stop + 0.3, 1.0), (T_END, 1.0)],
                          torso_share=0.45)
    face_p = face4.FaceTrack(E, 'pico', perf_p, base=[
        (0.0, {'browUp': 0.12, 'eyeWide': 0.25}),
        (t_stop, {'browUp': 0.30, 'browSad': 0.25, 'eyeWide': 0.30}),             # puzzled, out of breath
        (w_run + 0.10, {'browUp': 0.40, 'eyeWide': 0.35}, 0.17),                  # "run ?": expectant
        (9.0, {'browUp': 0.30, 'eyeWide': 0.40, 'mouthNarrow': 0.15}, 0.2),       # staring at the green light
        (10.3, {'browUp': 0.18, 'eyeWide': 0.20}),
        (11.9, {'browDown': 0.45, 'frown_L': 0.45, 'frown_R': 0.25, 'mouthNarrow': 0.15}, 0.07),   # "fais comme chez toi": miffed (snap)
        (15.5, {'browDown': 0.20, 'frown': 0.20}),
        (19.0, {'frown_L': 0.80, 'frown_R': 0.55, 'mouthNarrow': 0.30, 'browUp': 0.30, 'browSad': 0.35, 'eyeWide': 0.15}),   # the pout (lopsided)
        (w_jamais - 0.02, {'browSad': 0.80, 'browUp': 0.20, 'frown_L': 0.30, 'frown_R': 0.12, 'eyeSquint': 0.12}, 0.07),   # on the defensive
        (w_ok - 0.04, {'browUp': 0.60, 'frown': 0.12, 'eyeWide': 0.35}, 0.07),                            # defiant
        (21.05, {'browUp': 0.25, 'frown_L': 0.35, 'frown_R': 0.25, 'mouthNarrow': 0.15}, 0.25),           # the mouth closes into...
        (21.40, {'frown_L': 0.85, 'frown_R': 0.50, 'mouthNarrow': 0.30, 'browDown': 0.60, 'eyeSquint': 0.25}, 0.35),   # ...a glare, not the pout she started from
    ], events=[(v1[0], {'browUp': 0.22}, 0.17, 0.25, 0.30),
               (v4[0], {'browUp': 0.28}, 0.20, 0.20, 0.30),                                               # "desSOUS"
               (23.15, {'eyeClosed': 0.35, 'browUp': 0.20}, 0.12, 0.30, 0.25)],                          # the eye-roll: heavy lids
        blinks=[], amp=1.0, t_end=T_END,
        stress=[('l01', ['nox', 'montre', 'vertes', 'run']), ('l02c', ['jamais', 'dessous', 'ok'])])

    # ================================================================ NOX
    base_n = PF.BaseTrack(nox, [(0.0, 'listen', 0.6, 0.0, 0.0)])          # a held pose (v4-body F9)
    board, stand = ANCH['board'], ANCH['stand']
    T_IRON = (14.00, 14.36, 14.50)                        # reach the stand, iron in, hand back - on screen in the 'swivel' shot
    T_SWIVEL = (14.42, 15.00)
    heading_n = [(0.0, NOX_WORK), (T_SWIVEL[0], NOX_WORK), (T_SWIVEL[1], NOX_TO_PICO), (T_END, NOX_TO_PICO)]
    lean_n = [(0.0, 13.0), (T_SWIVEL[0] - 0.1, 13.0), (T_SWIVEL[1], 2.0), (T_END, 2.0)]
    # soldering: the iron tip touches a joint and holds, lifts 1-2 cm, moves 2-3 cm to the next one in ~0.25 s;
    # the solder hand feeds wire at the same joint.  Only while nobody talks.
    WORK = [(0.0, 4.25), (4.95, 5.10), (8.0, 9.85), (11.35, 11.75)]     # + one stroke in the pause between his phrases
    JOINTS = [Vector((0, 0, 0)), Vector((0.022, -0.008, 0)), Vector((0.010, -0.026, 0)), Vector((-0.014, -0.018, 0)), Vector((0.004, 0.012, 0))]

    def work_w(t):
        """0..1: how much he is working (smooth 0.2 s edges at each window)."""
        w = 0.0
        for a, b in WORK:
            if a - 0.2 <= t <= b + 0.2:
                w = max(w, min(1.0, AC.minjerk((t - a + 0.2) / 0.2) if t < a else 1.0, 1.0 - AC.minjerk((t - b) / 0.2) if t > b else 1.0))
        return w

    def stroke(t):
        """Joint-to-joint strokes on a clock that only runs while he works (so a started stroke finishes)."""
        period, move = 1.15, 0.26
        n = max(1, int(t * 30))
        done = sum(work_w((i + 0.5) * t / n) for i in range(n)) * t / n
        k = int(done // period)
        x = done % period
        p0, p1 = JOINTS[k % len(JOINTS)], JOINTS[(k + 1) % len(JOINTS)]
        if x < move:
            w = AC.minjerk(x / move)
            return p0.lerp(p1, w) + Vector((0, 0, 0.016 * math.sin(math.pi * w)))
        return p1

    iron_tip = Vector((0.080, -0.090, 0.060))            # iron hand to the right of / behind the joint (pen angle)
    solder_hand = Vector((-0.20, -0.05, 0.045))           # solder hand from the left: the two hands never overlap
    talk_rest = Vector((0.0, -0.012, 0.010))              # while he talks: the hands lift off the joint a little
    rest_keys = [(0.0, 0.0), (9.85, 0.0), (10.30, 1.0), (13.0, 1.0)]

    def knee_rest(P, s):
        arm = P.a.arm
        k = AC.joint(arm, f'{s}Leg')
        h = AC.joint(arm, f'{s}UpLeg')
        return k + (h - k) * 0.22 + Vector((0, 0, 0.075))

    def nox_extra(P, t, phase):
        if phase != 'arms':
            return
        arm = P.a.arm
        f, r, u = AC.body_frame(P.a)
        pole_r = AC.joint(arm, 'RightArm') + r * 0.9 - f * 0.4 - u * 0.6        # elbows open: hands approach from either side
        pole_l = AC.joint(arm, 'LeftArm') - r * 0.9 - f * 0.4 - u * 0.6
        # one target per hand, always at full IK weight; the transitions move the TARGET (never a blend with the clip pose):
        #   left  : solder wire at the joint -> onto the thigh (0.85 s)
        #   right : iron at the joint -> into the stand (careful, 0.42 s) -> onto the thigh (0.9 s)
        lift = AC.curve(rest_keys, t)
        jt = board + stroke(t)
        work_r = jt + iron_tip + talk_rest * lift
        work_l = jt + solder_hand + talk_rest * lift
        kl, kr = knee_rest(P, 'Left'), knee_rest(P, 'Right')
        a, b, c2 = T_IRON
        sp = stand + Vector((0.0, -0.06, 0.10))
        xl = AC.minjerk(min(1.0, max(0.0, (t - a) / 0.85)))
        tl = work_l.lerp(kl, xl)
        if t < a:
            tr = work_r
        elif t < b:
            tr = work_r.lerp(sp, AC.minjerk((t - a) / (b - a)))
        elif t < b + 0.12:
            tr = sp
        else:
            tr = sp.lerp(kr, AC.minjerk(min(1.0, (t - b - 0.12) / (c2 + 0.9 - b - 0.12))))
        AC.ik2(arm, 'LeftArm', 'LeftForeArm', 'LeftHand', tl, pole_l, 1.0)
        AC.ik2(arm, 'RightArm', 'RightForeArm', 'RightHand', tr, pole_r, 1.0)

    W['iron_in_hand'] = lambda t: t < T_IRON[1]

    w_pico = word(E, 'l02', 'pico')
    v2 = face4.stressed_vowels(E, 'l02', ['pico'])
    v3 = face4.stressed_vowels(E, 'l02b', ['montre', 'deux', 'allume'])
    w_allume = word(E, 'l02b', 'allume')
    v5 = face4.stressed_vowels(E, 'l02d', ['bon'])
    w_laisse = word(E, 'l02d', 'laisse')
    # the end: on "Laisse-moi" his right hand comes off his knee, palm up, towards her wrist, and stays
    g_give_n = PF.Gesture('Right', [
        (w_laisse - 0.08, (0.18, 0.10, -0.45), None, None, 0.32),
        (w_laisse + 0.22, (0.05, 0.40, -0.30), (0.0, 0.0, 1.0), (-0.35, 0.94, 0.0), 0.28),
        (26.0, (0.05, 0.41, -0.30), (0.0, 0.0, 1.0), (-0.35, 0.94, 0.0), 0.32),
    ], elbow=(0.6, -0.4, -0.6), ease_in=0.45, ease_out=0.05, profile='minjerk', thumb=0.35)
    gaze_n = PF.Gaze([
        (0.0, board, 0),
        (13.98, stand, 0, 0.6),                    # a glance at the stand to put the iron in
        (14.40, pico_face, 0),                     # then up to her: eyes first, the head, then the stool turns
    ], origin=[(0.0, tuple(nox_face_work)), (T_SWIVEL[0], tuple(nox_face_work)), (T_SWIVEL[1], tuple(nox_face_up))],
        head_delay=0.05, chest=0.25, chest_delay=0.12, head_weight=1.0, speed=1.0)
    v3b = face4.stressed_vowels(E, 'l02b', ['découvres'])
    acc_n = [nod(v2[0], 1.2),
             nod(v3b[0], 3.0),                                    # one real accent per phrase, not two invisible ones
             held(w_allume - 0.05, 'roll', 5.0, 0.20, 2.0, 0.4),
             nod(v5[0], 4.5),
             held(w_laisse - 0.25, 'lean', 2.0, 0.12, 0.40, 0.40),    # the body leads the hand
             held(w_laisse - 0.25, 'pitch', 3.0, 0.15, 0.30, 0.35)]
    life_n = PF.Life(seed=7.0, breath_rate=0.23, breath_deg=0.22, sway_cm=0.0, sway_rate=0.06, head_deg=0.30,
                     events=[(T_DOOR, 0.07, 0.15, 0.30, 1.0),              # the door bang: a 1 cm shoulder tick, nothing else
                             (w_allume - 0.03, 0.15, 0.50, 0.33, 2.5),
                             (v5[0] - 0.15, 0.40, 0.20, 0.60, -1.5)])
    perf_n = seat5.SeatedPerformer(nox, base_n, pivot=NOX_PIVOT.to_2d(), seat_z=SEAT_Z, heading=NOX_WORK,
                                   heading_keys=heading_n, lean_keys=lean_n, gaze=gaze_n, gestures=[g_give_n],
                                   accents=acc_n, life=life_n, extra=nox_extra, relax_curl=0.45, torso_share=0.15)
    face_n = face4.FaceTrack(E, 'nox', perf_n, base=[
        (0.0, {'eyeSquint': 0.18, 'eyeClosed': 0.10}),                       # heavy lids, on his work
        (15.0, {'eyeClosed': 0.20, 'eyeSquint': 0.15, 'browDown': 0.20}),     # turned round: the deadpan stare
        (v3[1] - 0.05, {'browUp_R': 0.50, 'browUp_L': 0.30, 'eyeClosed': 0.18}, 0.17),   # "deux ANS…": one brow higher, lids heavy
        (w_allume - 0.05, {'browUp_R': 0.45, 'browUp_L': 0.30, 'eyeClosed': 0.15}, 0.17),        # "s'allume ?"
        (18.95, {'browUp_R': 0.20, 'smile_L': 0.40, 'smile_R': 0.06, 'eyeSquint': 0.15, 'eyeClosed': 0.12}, 0.30),   # a one-sided smirk
        (21.9, {'eyeSquint': 0.10, 'smile_L': 0.15, 'eyeClosed': 0.12}),
    ], events=[
        (w_pico + 0.05, {'browUp': 0.12}, 0.17, 0.30, 0.30),
        (v5[0], {'eyeClosed': 0.6}, 0.12, 0.22, 0.25),
    ], blinks=[], amp=1.0, t_end=T_END, stress=[('l02b', ['montre', 'deux', 'allume']), ('l02d', ['bon'])])

    for P in (perf_p, perf_n):
        P.prepare(T_END)
    face_p._blinks([12.4, 16.2, 19.30, 20.60, 21.32])       # on her head tilt, on the turn before 'ok ?', inside the glare
    face_n._blinks([w_nox + 0.12, 7.4, 11.9, 15.42, 17.25])    # "Nox !": he blinks, that is all; 17.25: a deadpan blink in the pause
    W['face'] = {'pico': face_p, 'nox': face_n}
    W['marks_extra'] = dict(nox_face_work=nox_face_work, nox_face_up=nox_face_up, pico_face=pico_face)
    W['times'] = dict(t_plant=t_plant, t_stop=t_stop, iron=T_IRON, swivel=T_SWIVEL, run_h=run_h)
    return {'pico': perf_p, 'nox': perf_n}
