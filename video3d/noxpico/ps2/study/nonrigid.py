"""How much of the face moves, once the head's own motion is removed?  python nonrigid.py
Landmarks of each frame are aligned (2D similarity) to the segment's median shape on points that cannot move on a skull
(forehead, nose bridge, eye corners, temples); what is left is the deformation, in % of the distance between the eyes."""
import sys, json
import numpy as np
RIGID = [10, 67, 297, 109, 338, 6, 168, 197, 33, 263, 133, 362, 127, 356, 21, 251]
REG = {'menton': [152, 148, 377, 176, 400, 175, 199], 'levre_basse': [14, 17, 84, 314, 87, 317],
       'levre_haute': [13, 0, 37, 267, 82, 312], 'coins_bouche': [61, 291], 'joues': [205, 425, 50, 280, 187, 411, 207, 427],
       'nez': [1, 4, 5, 195, 129, 358, 98, 327], 'pommettes': [116, 345, 117, 346, 123, 352], 'sourcils': [105, 334, 66, 296, 107, 336, 70, 300],
       'front': [9, 151, 108, 337, 69, 299], 'machoire_cotes': [172, 397, 136, 365, 58, 288]}
def sim(a, b):                      # similarity a -> b (least squares), returns transformed a-like function
    ma, mb = a.mean(0), b.mean(0)
    A, B = a - ma, b - mb
    U, S, Vt = np.linalg.svd(A.T @ B)
    R = (U @ Vt)
    if np.linalg.det(R) < 0:
        U[:, -1] *= -1; R = U @ Vt
    s = S.sum() / (A ** 2).sum()
    return lambda p: (p - ma) @ R * s + mb
def seg(npz, slot, t0, t1):
    d = np.load(npz)
    t = d['t']; m = (t >= t0) & (t <= t1)
    L = d['face_lm'][m][:, :, :, :2]
    if slot == 'big':                # the largest face of each frame
        out = []
        for fr in L:
            sz = [np.nanmax(f[:, 1]) - np.nanmin(f[:, 1]) if np.isfinite(f[0, 0]) else -1 for f in fr]
            out.append(fr[int(np.argmax(sz))] if max(sz) > 0 else np.full((478, 2), np.nan))
        L = np.array(out)
    else:
        L = L[:, slot]
    L = L[np.isfinite(L[:, 0, 0])]
    ref = np.median(L, 0)
    io = np.linalg.norm(ref[468] - ref[473])
    al = np.array([sim(f[RIGID], ref[RIGID])(f) for f in L])
    res = al - np.median(al, 0)
    out = {'frames': len(L), 'io_px': round(float(io), 1)}
    for k, idx in REG.items():
        r = np.linalg.norm(res[:, idx], axis=2)                # frames x points
        out[k] = round(float(np.percentile(r, 90)) / io * 100, 1)
    out['rigid_residu'] = round(float(np.percentile(np.linalg.norm(res[:, RIGID], axis=2), 90)) / io * 100, 1)
    return out
SEGS = [('ref03 Red "Et moi, et moi, Zak ?"', 'data/reference.npz', 7.29, 8.67), ('ref07 Zak "ma mère soulève plus"', 'data/reference.npz', 17.75, 20.08),
        ('ref08 Red "la même barre"', 'data/reference.npz', 20.29, 21.33), ('ref11 Red "Mash\'Allah"', 'data/reference.npz', 29.33, 31.50),
        ('ref13 Zak "Allahou a3lam"', 'data/reference.npz', 34.33, 35.40),
        ('v5.1 Nox gros plan', 'data/mine_v51.npz', 15.28, 18.80), ('v5.1 Pico gros plan', 'data/mine_v51.npz', 19.30, 20.90)]
if len(sys.argv) > 1:
    SEGS = [tuple(x if i != 2 and i != 3 else float(x) for i, x in enumerate(a.split('|'))) for a in sys.argv[1:]]
keys = list(REG) + ['rigid_residu']
print('%-34s' % 'segment', ' '.join('%8s' % k[:8] for k in ['frames'] + keys))
for name, npz, t0, t1 in SEGS:
    o = seg(npz, 'big', t0, t1)
    print('%-34s' % name[:34], ' '.join('%8s' % o[k] for k in ['frames'] + keys))
