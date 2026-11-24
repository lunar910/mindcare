"""Choreography of version 4: what Nox and Pico do, moment by moment, in the restrained style of the reference.

Built from the three studies of the reference (study/reports/ref-visual.md §7.2, mine-visual.md §6, body-data.md,
face-data.md):
  - characters HOLD natural poses; nothing sways; the head is still between accents;
  - one motivated, one-handed gesture per line at most, reached with a fast attack and then held;
  - the order of every action: eyes -> head (a blink in the fast part) -> mouth -> hand;
  - turns start fast and settle long (half done in about a third of the time), then hold;
  - nods land on the stressed vowel (3-6 deg for Pico's emphatic lines, <= 1.5 deg for Nox's calm ones);
  - Nox (calm, deadpan) barely moves; Pico (excitable) snaps.

Everything is in seconds of the excerpt (script4.py has the phrases and the shots).  Positions: metres in the world
(Z up, the camera side is -Y)."""
import math
import re

import bpy
from mathutils import Matrix, Quaternion, Vector

import acting as AC
import face4
import perform as PF

PICO_CLIPS = ('sprintstop', 'listen', 'hip')
NOX_CLIPS = ('listen',)
SPRINT_T0, SPRINT_OFF = 0.50, 0.33        # she bursts in as the door opens, with more of the run seen in the room


def word_times(E, line_id):
    import script4
    return script4.word_times(line_id)


def word(E, line_id, w, nth=0):
    """Start time of a word in a line (first match; nth for repeated words)."""
    norm = lambda x: re.sub(r'[^\w]', '', x.lower())
    hits = [s for ww, s, e in word_times(E, line_id) if norm(ww).startswith(w.lower())]
    hits = hits or [s for ww, s, e in word_times(E, line_id) if w.lower() in norm(ww)]      # "t'expliquer", "s'allume"
    if not hits:
        raise KeyError(f'word {w!r} not in line {line_id}: {[ww for ww, _, _ in word_times(E, line_id)]}')
    return hits[nth]


def nod(tv, deg):
    """A nod whose lowest point is on the vowel at tv: 3 frames down, then 7-8 frames to settle."""
    return (tv - 0.10, 'nod', deg, 0.10, 0.25)


def held(t0, kind, deg, rise, hold, fall):
    """A one-way head pose ('pitch' > 0 = down, 'roll') or a chest 'lean': snap there, hold, ease back."""
    return (t0, kind, deg, rise, hold, fall)


# ------------------------------------------------------------------ the performers
def performers(W, E):
    E.SPRINT_T0, E.SPRINT_OFF = SPRINT_T0, SPRINT_OFF
    pico, nox = W['pico'], W['nox']
    A, AT = W['A'], W['AT']
    marks = A['marks']
    mark_p, mark_n = Vector(marks['pico']), Vector(marks['nox'])
    T_END = E.T_END

    # ================================================================ PICO
    # the sprint ends exactly on her mark; she then stands (a calm stance), and later puts a hand on her hip
    c = pico.clips['sprintstop']
    pico.place(tuple(mark_p), 0.0)
    pico.pose(c.sample(SPRINT_OFF), c.bones)
    a0 = pico.feet_local()
    pico.pose(c.sample(c.dur), c.bones)
    a1 = pico.feet_local()
    travel = a1 - a0
    want = (mark_p - Vector(marks['door'])).normalized()
    run_heading = math.atan2(want.x, -want.y) - math.atan2(travel.x, -travel.y)
    t_plant = SPRINT_T0 + (1.45 - SPRINT_OFF)                     # the clip's final plant (hips almost stopped)
    base_p = PF.BaseTrack(pico, [(SPRINT_T0, 'sprintstop', SPRINT_OFF, 1.0, 0.0, 'clamp'),
                                 (t_plant + 0.15, 'listen', 1.2, 0.10, 0.6),
                                 (8.0, 'hip', 0.55, 0.05, 1.2)])   # hand on her hip, changed while the camera is on Nox
    base_p.shift[0] = pico.hips_shift(a1)
    heading_p = [(0.0, run_heading), (t_plant - 0.10, run_heading), (t_plant + 0.40, E.PICO_FACE), (T_END, E.PICO_FACE)]

    # where things are (for the eyes)
    nox_face = Vector((mark_n.x + 0.01, mark_n.y - 0.10, 1.585))
    pico_face = Vector((mark_p.x - 0.03, mark_p.y - 0.06, 1.50))
    fp = Vector((math.sin(E.PICO_FACE), -math.cos(E.PICO_FACE), 0))            # Pico's forward and right, standing
    rp = Vector((-fp.y, fp.x, 0)) * -1
    chest_p = Vector((mark_p.x, mark_p.y, 1.28))

    def pico_off(off):
        return chest_p + rp * off[0] + fp * off[1] + Vector((0, 0, off[2]))

    w_nox = word(E, 'l01', 'nox')
    w_montre = word(E, 'l01', 'montre')
    w_lum = word(E, 'l01', 'lumi')
    w_vertes = word(E, 'l01', 'vertes')
    w_run = word(E, 'l01', 'run')
    v1 = face4.stressed_vowels(E, 'l01', ['nox', 'vertes', 'run'])
    # the watch: on "montre" her LEFT forearm comes up across the front of her chest, back of the wrist (the watch)
    # turned to Nox; held; on "run ?" pushed 8 cm towards him; held to the cut, lowered off camera.  Right hand: nothing.
    show = (0.05, 0.27, -0.07)
    push = (0.06, 0.35, -0.05)
    palm_in, fing_x = (0.0, -1.0, 0.12), (1.0, 0.18, 0.12)
    g_watch = PF.Gesture('Left', [
        (w_montre - 0.24, (-0.20, 0.03, -0.52), None, None, 0.32),
        (w_montre + 0.08, show, palm_in, fing_x, 0.55),
        (w_run - 0.12, (show[0] + 0.005, show[1] + 0.01, show[2]), palm_in, fing_x, 0.55),
        (w_run + 0.10, push, palm_in, fing_x, 0.58),
        (6.45, (push[0], push[1] - 0.005, push[2] - 0.005), palm_in, fing_x, 0.58),
        (6.85, (-0.20, 0.03, -0.52), None, None, 0.32),
    ], elbow=(-0.50, -0.30, -0.80), ease_in=0.32)
    # closeP: on "ok ?" a small flick of the right hand, palm up, low in the frame; dropped after
    w_ok = word(E, 'l02c', 'ok')
    g_ok = PF.Gesture('Right', [
        (w_ok - 0.20, (0.20, 0.04, -0.50), None, None, 0.32),
        (w_ok + 0.05, (0.16, 0.26, -0.34), (0.20, 0.10, 1.0), (0.10, 1.0, 0.10), 0.20),
        (w_ok + 0.55, (0.17, 0.27, -0.35), (0.20, 0.10, 1.0), (0.10, 1.0, 0.10), 0.22),
        (w_ok + 0.95, (0.20, 0.04, -0.50), None, None, 0.32),
    ], elbow=(0.75, -0.3, -0.5), ease_in=0.25)
    # two-shot, after Nox's line: she holds her left wrist out to him (from her hip), reluctantly, and keeps it there
    g_give = PF.Gesture('Left', [
        (21.00, (-0.22, 0.02, -0.38), None, None, 0.32),
        (21.40, (-0.02, 0.36, -0.22), (0.0, 0.10, -1.0), (0.25, 1.0, 0.0), 0.45),
        (24.00, (-0.02, 0.37, -0.22), (0.0, 0.10, -1.0), (0.25, 1.0, 0.0), 0.45),
    ], elbow=(-0.5, -0.4, -0.7), ease_in=0.40, ease_out=0.05)

    w_jamais = word(E, 'l02c', 'jamais')
    w_dessous = word(E, 'l02c', 'dessous')
    v4 = face4.stressed_vowels(E, 'l02c', ['dessous', 'ok'])
    gaze_p = PF.Gaze([
        (0.0, nox_face, 0),
        (w_lum - 0.05, pico_off(show) + Vector((0, 0, 0.03)), 0, 0.45),    # "lumières": a glance down at the watch…
        (w_vertes + 0.20, nox_face, 0),                                    # …and back to him
        (w_jamais - 0.08, nox_face + Vector((0.40, -0.30, -0.45)), 0, 0.5),   # "J'ai jamais…": looks away, embarrassed
        (w_dessous - 0.05, nox_face, 0),                                   # "…dessous": back to him
        (20.70, nox_face + Vector((0.0, 0.0, 0.55)), 0, 0.0),              # rolls her eyes (eyes only)…
        (21.05, nox_face, 0),                                              # …and back
    ], origin=pico_face, head_delay=0.05, chest=0.40, chest_delay=0.05, head_weight=1.0, speed=0.55)
    acc_p = [held(t_plant - 0.05, 'lean', 6.0, 0.12, 0.0, 0.32),         # the stop: the chest carries on, then settles
             held(w_nox - 0.12, 'lean', 6.0, 0.18, 0.15, 0.35),           # "Nox !": the head pushed forward
             nod(v1[0], 4.5),
             nod(v1[1], 4.5),                                            # "VERtes"
             held(w_run - 0.05, 'pitch', -8.0, 0.20, 1.5, 0.4),          # "run ?": chin up, held to the cut
             held(w_run - 0.05, 'lean', 4.0, 0.20, 1.5, 0.4),
             held(w_jamais - 0.08, 'pitch', 6.0, 0.30, 0.55, 0.35),      # embarrassed: head down while looking away
             nod(v4[0], 4.0),                                            # "desSOUS" (a blink at the bottom)
             held(w_ok - 0.06, 'pitch', -8.0, 0.18, 1.2, 0.4),           # "ok ?": chin up…
             held(w_ok - 0.06, 'roll', -5.0, 0.18, 1.2, 0.4)]            # …and a defiant tilt
    life_p = PF.Life(seed=3.0, breath_rate=0.27, breath_deg=0.25, sway_cm=0.12, sway_rate=0.06, head_deg=0.10,
                     events=[(t_plant + 0.35, 0.40, 0.05, 0.50, 1.5)])     # one visible breath after the run
    perf_p = PF.Performer(pico, base_p, tuple(mark_p), E.PICO_FACE, gaze=gaze_p, gestures=[g_watch, g_ok, g_give],
                          accents=acc_p, life=life_p, lock_from=t_plant + 0.35, heading_keys=heading_p,
                          gaze_weight=[(0.0, 0.0), (t_plant - 0.4, 0.0), (t_plant + 0.3, 1.0), (T_END, 1.0)])
    face_p = face4.FaceTrack(E, 'pico', perf_p, base=[
        (0.0, {'browUp': 0.12, 'eyeWide': 0.25}),
        (2.3, {'browUp': 0.10, 'browSad': 0.08, 'eyeWide': 0.20}),          # puzzled, out of breath
        (w_run + 0.10, {'browUp': 0.24, 'eyeWide': 0.25}, 0.17),            # "run ?": brows up, held (expectant)
        (7.2, {'browUp': 0.12}),
        (12.0, {'browDown': 0.10}),
        (16.20, {'frown': 0.45, 'mouthNarrow': 0.25, 'browUp': 0.16, 'eyeWide': 0.20}),   # a pout before she answers
        (w_jamais - 0.02, {'browSad': 0.32, 'frown': 0.15, 'eyeSquint': 0.10}, 0.07),     # snap: embarrassed
        (w_ok - 0.04, {'browUp': 0.22, 'frown': 0.10}, 0.07),                             # "ok ?": defiant
        (18.25, {'frown': 0.40, 'mouthNarrow': 0.15, 'browDown': 0.12}, 0.20),            # pout, brows knitted
    ], events=[
        (v1[0], {'browUp': 0.22}, 0.17, 0.25, 0.30),
    ], blinks=[], amp=1.0, stress=[('l01', ['nox', 'montre', 'vertes', 'run']), ('l02c', ['jamais', 'dessous', 'ok'])])

    # ================================================================ NOX
    base_n = PF.BaseTrack(nox, [(0.0, 'listen', 0.6, 0.06, 0.0)])          # a held pose: breathing and gaze do the rest
    top = A['bench_top']

    def lean(P, k):
        axis = Vector((math.cos(P.a.heading), math.sin(P.a.heading), 0.0))
        AC.rotate(P.a.arm, 'Spine01', Quaternion(axis, math.radians(8 * k)))
        AC.rotate(P.a.arm, 'Spine', Quaternion(axis, math.radians(6 * k)))

    # hand targets on the bench, reachable from his (leaning) pose
    nox.place(tuple(mark_n), E.NOX_FACE)
    hand_t, pole_t = {}, {}
    samples = []

    class _P:
        pass
    for i in range(8):
        nox.pose(base_n.sample(i * 1.4), base_n.bones)
        bpy.context.view_layer.update()
        pp = _P()
        pp.a = nox
        lean(pp, 1.0)
        bpy.context.view_layer.update()
        samples.append({s: (AC.joint(nox.arm, f'{s}Arm').copy(), (AC.joint(nox.arm, f'{s}Arm') - AC.joint(nox.arm, f'{s}ForeArm')).length
                            + (AC.joint(nox.arm, f'{s}ForeArm') - AC.joint(nox.arm, f'{s}Hand')).length) for s in ('Left', 'Right')})
    for s, sx in (('Left', 1), ('Right', -1)):
        sh = sum((smp[s][0] for smp in samples), Vector((0, 0, 0))) / len(samples)
        reach = min(smp[s][1] for smp in samples)
        tgt = Vector((sh.x + sx * 0.02, mark_n.y - 0.44, top + 0.05))
        for _ in range(80):
            if max((tgt - smp[s][0]).length for smp in samples) <= 0.92 * reach:
                break
            tgt.y += 0.005
        hand_t[s] = tgt
        pole_t[s] = Vector((mark_n.x + sx * 0.75, mark_n.y + 0.3, 0.95))
    bench_work = (hand_t['Left'] + hand_t['Right']) / 2 + Vector((0.0, -0.04, -0.03))
    rest_l = Vector((mark_n.x + 0.25, mark_n.y - 0.26, top + 0.035))      # hands resting on the bench edge, by his sides
    rest_r = Vector((mark_n.x - 0.24, mark_n.y - 0.27, top + 0.035))
    W['bench_hands'] = hand_t

    # soldering: the tip touches a joint and holds, lifts 1-2 cm, moves 2-3 cm to the next one in about 0.25 s; the
    # hands work only in silences (they stop for the door, for "Nox !", and while he speaks)
    WORK = [(0.0, 0.50), (0.80, 2.40), (2.95, 7.30), (8.70, 9.20)]
    JOINTS = [Vector((0, 0, 0)), Vector((0.022, -0.008, 0)), Vector((0.010, -0.026, 0)), Vector((-0.014, -0.018, 0)), Vector((0.004, 0.012, 0))]

    def work_offset(side, t):
        if side == 'Left':                                   # the hand holding the board: shifts only once in a while
            k = int(t // 3.7)
            pts = [Vector((0, 0, 0)), Vector((-0.008, 0.005, 0)), Vector((0.004, -0.006, 0))]
            x = (t % 3.7)
            w = AC.snappy(x / 0.3) if x < 0.3 else 1.0
            return pts[k % 3].lerp(pts[(k + 1) % 3], w) if any(a <= t <= b for a, b in WORK) else pts[k % 3]
        # the iron: count the working time spent so far; a stroke every `period` seconds of work
        period, move = 1.05, 0.25
        done, inside = 0.0, False
        for a, b in WORK:
            if t >= b:
                done += b - a
            elif t >= a:
                done += t - a
                inside = True
                break
            else:
                break
        k = int(done // period)
        x = done % period
        p0, p1 = JOINTS[k % len(JOINTS)], JOINTS[(k + 1) % len(JOINTS)]
        if inside and x < move:
            w = AC.snappy(x / move)
            return p0.lerp(p1, w) + Vector((0, 0, 0.014 * math.sin(math.pi * w)))
        return p1 if (inside or x >= move) else p0

    solder_keys = [(0.0, 1.0), (10.45, 1.0), (11.0, 0.55), (11.62, 0.55), (12.30, 0.0)]   # 10.45: off the work; 11.62: straightens
    rest_keys = {'Left': [(0.0, 0.0), (10.45, 0.0), (11.0, 1.0), (T_END, 1.0)],
                 'Right': [(0.0, 0.0), (10.45, 0.0), (11.0, 1.0), (11.62, 1.0), (12.20, 0.0), (T_END, 0.0)]}
    work_keys = [(0.0, 1.0), (10.45, 1.0), (11.0, 0.0), (T_END, 0.0)]

    def nox_extra(P, t, phase):
        if phase == 'torso':
            solder = AC.curve(solder_keys, t)
            if solder > 0:
                lean(P, solder)
            return
        if phase != 'arms':
            return
        arm = P.a.arm
        work = AC.curve(work_keys, t)
        if work > 0:
            for s in ('Left', 'Right'):
                AC.ik2(arm, f'{s}Arm', f'{s}ForeArm', f'{s}Hand', hand_t[s] + work_offset(s, t), pole_t[s], work)
        for s, rt in (('Left', rest_l), ('Right', rest_r)):
            rw = AC.curve(rest_keys[s], t)
            if rw > 0:
                AC.ik2(arm, f'{s}Arm', f'{s}ForeArm', f'{s}Hand', rt, pole_t[s], rw)

    w_pico = word(E, 'l02', 'pico')
    v2 = face4.stressed_vowels(E, 'l02', ['pico'])
    v3 = face4.stressed_vowels(E, 'l02b', ['montre', 'deux', 'allume'])
    w_allume = word(E, 'l02b', 'allume')
    v5 = face4.stressed_vowels(E, 'l02d', ['bon'])
    w_laisse = word(E, 'l02d', 'laisse')
    # two-shot: on "Laisse-moi" his right hand comes out palm up towards her wrist ("give it here"), held to the end
    g_give_n = PF.Gesture('Right', [
        (w_laisse - 0.08, (0.20, 0.04, -0.52), None, None, 0.32),
        (w_laisse + 0.18, (-0.10, 0.33, -0.26), (0.0, 0.0, 1.0), (-0.55, 0.85, 0.0), 0.28),
        (24.0, (-0.10, 0.34, -0.26), (0.0, 0.0, 1.0), (-0.55, 0.85, 0.0), 0.30),
    ], elbow=(0.6, -0.4, -0.6), ease_in=0.26, ease_out=0.05)
    gaze_n = PF.Gaze([
        (0.0, bench_work, 0),
        (11.55, pico_face, 0),                                 # stops working: eyes first, the head follows, the chest after
    ], origin=[(0.0, (mark_n.x, mark_n.y - 0.10, 1.47)), (11.55, (mark_n.x, mark_n.y - 0.10, 1.47)), (12.3, tuple(nox_face))],
       head_delay=0.05, chest=0.30, chest_delay=0.12, head_weight=1.0, speed=1.0)
    acc_n = [nod(v2[0], 1.2),                                  # "PiCO" (head stays down)
             held(11.40, 'pitch', 3.5, 0.15, 0.0, 0.25),       # anticipation: a little further down before the lift
             nod(v3[0], 1.2), nod(v3[1], 1.5),                 # "MONtre", "deux ANS"
             held(w_allume - 0.05, 'roll', 5.0, 0.20, 2.0, 0.4),   # "s'allume ?": a one-way tilt, held to the cut
             nod(v5[0], 4.5)]                                  # "Bon." (a sigh)
    life_n = PF.Life(seed=7.0, breath_rate=0.23, breath_deg=0.22, sway_cm=0.10, sway_rate=0.06, head_deg=0.08,
                     events=[(0.50, 0.07, 0.15, 0.30, 1.0),          # the door bang: a 1 cm shoulder tick, nothing else
                             (w_allume - 0.03, 0.15, 0.50, 0.33, 2.5),   # "s'allume ?": a micro-shrug, held, released
                             (v5[0] - 0.15, 0.40, 0.20, 0.60, -1.5)])     # "Bon.": the shoulders drop (a sigh)
    perf_n = PF.Performer(nox, base_n, tuple(mark_n), E.NOX_FACE, gaze=gaze_n, gestures=[g_give_n], accents=acc_n, life=life_n,
                          lock_from=0.0, heading_keys=None, extra=nox_extra,
                          hips_yaw=[(0.0, 0.0), (11.62, 0.0), (12.30, 8.0), (T_END, 8.0)],        # he turns to her, feet planted
                          spine_yaw=[(0.0, 0.0), (11.65, 0.0), (12.35, 20.0), (T_END, 20.0)])
    face_n = face4.FaceTrack(E, 'nox', perf_n, base=[
        (0.0, {'eyeSquint': 0.18, 'eyeClosed': 0.08}),                     # heavy lids, on his work
        (11.5, {'eyeSquint': 0.12}),
        (v3[1] - 0.05, {'browUp_L': 0.25, 'eyeSquint': 0.12}, 0.17),        # "deux ANS…": one eyebrow up, held through the stare
        (w_allume - 0.05, {'browUp': 0.22, 'browUp_L': 0.08, 'eyeSquint': 0.05}, 0.17),   # "s'allume ?": both brows up
        (15.95, {'browUp': 0.10, 'smile_L': 0.35, 'eyeSquint': 0.12}, 0.25),            # a closed-mouth half smirk
        (19.0, {'eyeSquint': 0.10, 'smile': 0.08}),
    ], events=[
        (w_pico + 0.05, {'browUp': 0.12}, 0.17, 0.30, 0.30),                # "Pico": a dry brow lift, head down
        (v5[0], {'eyeClosed': 0.6}, 0.12, 0.22, 0.25),                      # "Bon.": a slow, sighing blink
    ], blinks=[], amp=1.2, stress=[('l02b', ['montre', 'deux', 'allume']), ('l02d', ['bon'])])

    for P in (perf_p, perf_n):
        P.prepare(T_END)
    face_p._blinks([v4[0] - 0.08, 9.2, 13.9])           # blinks on her head turns, at the bottom of "desSOUS", and two off camera
    face_n._blinks([4.6, 17.2])
    W['face'] = {'pico': face_p, 'nox': face_n}
    W['marks_extra'] = dict(nox_face=nox_face, pico_face=pico_face)
    return {'pico': perf_p, 'nox': perf_n}
