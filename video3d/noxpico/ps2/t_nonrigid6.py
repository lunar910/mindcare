"""Exact version of study/work/face6/nonrigid.py for our own faces: how far each part of the face moves, in the
head's own frame, while the character speaks (shape keys only; the head motion is not in it by construction).
    python t_nonrigid6.py 5|6"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ver = int(sys.argv[1]); sys.argv = ['x']
import bpy, numpy as np
bpy.ops.wm.read_factory_settings(use_empty=True)
import addon_utils; addon_utils.enable('cycles', default_set=True)
import cast2, face4, script5 as E, chore5
E.CHORE = chore5
cast2.MATTE = False
cast2.FACE = 'face6' if ver == 6 else 'facemorph'
face4.use_version(6 if ver == 6 else 4)
REG = {'menton': [152, 148, 377, 176, 400, 175, 199], 'levre_basse': [17, 84, 314], 'levre_haute': [0, 37, 267],
       'coins_bouche': [61, 291], 'joues': [205, 425, 50, 280, 187, 411, 207, 427], 'nez': [1, 4, 5, 195, 129, 358, 98, 327],
       'pommettes': [116, 345, 117, 346, 123, 352], 'sourcils': [105, 334, 66, 296, 107, 336, 70, 300], 'front': [9, 151, 108, 337, 69, 299],
       'machoire_cotes': [172, 397, 136, 365, 58, 288]}
out = {}
for who, name, rig, clip, glasses in (('nox', 'noxR', 'noxR_rigged', 'nox2:listen', True), ('pico', 'picoR', 'picoR_rigged', 'pico:listen', False)):
    a = cast2.Actor(name, rig, [clip], glasses=glasses)
    L = np.array(json.load(open(f'{HERE}/out_face2/{name}_landmarks.json'))['points'])
    io = np.linalg.norm(L[468] - L[473])
    me = a.mesh.data
    n = len(me.vertices)
    M = np.array(a.mesh.matrix_world)[:3, :3]
    kb = me.shape_keys.key_blocks
    basis = np.empty(n * 3); kb['Basis'].data.foreach_get('co', basis); basis = basis.reshape(n, 3)
    W = basis @ M.T + np.array(a.mesh.matrix_world)[:3, 3]
    # only skin vertices seen from the front: nearest vertex to each landmark, in front (smallest y within 3 mm in x-z)
    def nearest(p):
        d = np.hypot(W[:, 0] - p[0], W[:, 2] - p[2])
        c = np.nonzero(d < 0.004)[0]
        if len(c) == 0:
            return int(np.argmin(d))
        return int(c[np.argmin(W[c, 1])])
    idx = {k: [nearest(L[i]) for i in v] for k, v in REG.items()}
    used = sorted({i for v in idx.values() for i in v})
    D = {}
    for k in kb:
        if k.name == 'Basis':
            continue
        co = np.empty(n * 3); k.data.foreach_get('co', co)
        D[k.name] = (co.reshape(n, 3)[used] - basis[used]) @ M.T
    pos = {v: j for j, v in enumerate(used)}
    FT = face4.FaceTrack(E, who, None, base=[(0.0, {})], blinks=[], amp=1.15 if who == 'pico' else 1.2, t_end=E.T_END)
    import facemorph
    rows = []
    for lid, w, t0, dur, text in E.LINES:
        if w != who:
            continue
        disp = []
        for t in np.arange(t0, t0 + dur, 1 / 30):
            vals = facemorph.expand(FT.values(float(t)))
            if 'lipsUp' in vals and 'lipUpperUp' in D:
                vals['lipUpperUp'] = vals.get('lipUpperUp', 0) + vals['lipsUp']
            tot = np.zeros((len(used), 3))
            for kname, v in vals.items():
                if kname in D and v:
                    tot += D[kname] * min(max(v, 0.0), 1.0)
            disp.append(np.linalg.norm(tot, axis=1))
        rows.append(np.array(disp))
    disp = np.vstack(rows)
    res = {k: round(float(np.percentile(disp[:, [pos[i] for i in v]], 90)) / io * 100, 1) for k, v in idx.items()}
    out[who] = res
keys = list(REG)
print('%-22s' % f'version {ver}', ' '.join('%8s' % k[:8] for k in keys))
for who, r in out.items():
    print('%-22s' % who, ' '.join('%8s' % r[k] for k in keys))
