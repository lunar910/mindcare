"""teeth6 - teeth, gums and tongue for the version 6 faces (separate parts, Cycles).

    import teeth6
    T = teeth6.build('nox', arch_width=0.046, collection=None)       # also: cavity=True, seed=None
    T['upper']    empty: root of the upper teeth + upper gum (+ palate and throat wall when cavity=True)
    T['lower']    empty: root of the lower teeth + lower gum (+ mouth floor when cavity=True) + tongue
    T['tongue']   mesh, child of 'lower', subdivision surface, shape keys 'up' and 'out' (0..1, slider up to 1.5)
    T['objects']  every mesh object created: upper teeth, upper gum, lower teeth, lower gum, tongue
    extras: T['upper_teeth'], T['upper_gum'], T['lower_teeth'], T['lower_gum'] (the meshes, children of the roots,
            identity transforms), T['bite'] (Vector, metres), T['scale'] (1 = adult human), T['dims'] (metres)

Conventions (metres, the character faces -Y, +Z up, +X = the character's left):
  'upper' origin = midpoint of the cutting edge of the two upper central incisors, on their front (labial) face;
           crowns go up (+Z) from the edge, the arch goes back (+Y).
  'lower' origin = same point of the lower central incisors; crowns go down (-Z), the arch goes back (+Y).
  Jaw closed: lower origin = upper origin + T['bite'], about (0, +2.5 mm, +2.0 mm) at the default size: the lower
  incisors stand 2.5 mm behind the upper ones and their edge is 2 mm above the upper edge (2 mm of overlap).
  teeth6.jaw_matrix(T, open_m, rot_deg) = matrix of the lower root in the upper root's space (closed bite, dropped
  by open_m, rotated rot_deg about X through the lower incisors' edge, positive = opening);
  teeth6.set_jaw(T, open_m, rot_deg) applies it when the two roots share the same parent.

arch_width = left-right width of the UPPER arch across the outer faces of the second premolars, i.e. the widest part
of the arch one can see through the lips.  0.046 m gives average adult teeth (central incisors 8.5 x 10.5 mm); the
molars behind flare out to 1.19 x arch_width.  Everything (teeth, gums, tongue, shape keys, the bite offset, texture
and subsurface sizes) scales with arch_width.

Tongue keys (lower root space, sizes at the default arch_width):
  'up'   the blade curls up, tip 12.5 mm higher and 1.2 mm further forward: it meets the palatal side of the upper
         incisors when the jaw is open about 5 mm; for another opening use up = min(1.1, 0.63 + 0.08 x opening_mm)
         (more than that pushes the tip through the upper incisors).
  'out'  the tip slides 6 mm forward and 4.6 mm up and lies flat on the edge of the lower incisors, just behind the
         upper ones; needs the jaw open >= 3 mm (it goes through the upper incisors when the jaw is closed).
  Neither key, nor the rest shape, touches the lower teeth; do not combine the two keys.  The back of the tongue
  goes through the throat wall and its underside through the mouth floor on purpose (no gap).

All the geometry is authored in millimetres at human size and scaled at the end.  The small per-tooth variations
(rotation, lean, height, in/out, wear of the edge) are seeded by `name` (or by `seed` if given), so a character keeps
its teeth from one build to the next."""
import math
import random
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

MM = 0.001
OVERBITE = 2.0          # mm, vertical overlap of the incisors when the jaw is closed
ROOT_Q = 1.30           # crowns are modelled down to 1.3 x their height (the part hidden in the gum)
GUM_BAND = 10.0         # mm of gum above the highest point of the gum line (12-13 mm from the papilla tips)

# name, kind, mesio-distal width, crown height, labio-lingual thickness, tip offset (how much shorter than the
# central incisor's edge), labial inclination in degrees (root leaning inwards).  Millimetres.
UPPER = [('I1', 'inc', 8.5, 10.5, 7.0, 0.00, 14.0),
         ('I2', 'inc2', 6.5, 9.2, 6.0, 0.90, 12.0),
         ('C', 'can', 7.5, 10.2, 8.0, 0.35, 8.0),
         ('P1', 'pm', 7.0, 8.0, 9.0, 0.70, 3.0),
         ('P2', 'pm', 6.5, 7.5, 9.0, 0.95, 2.0),
         ('M1', 'mol', 10.0, 7.0, 10.0, 1.20, 0.0),
         ('M2', 'mol', 9.0, 6.5, 9.5, 1.70, 0.0)]
LOWER = [('I1', 'linc', 5.3, 9.0, 6.0, 0.00, 12.0),
         ('I2', 'linc', 5.9, 9.3, 6.3, 0.05, 11.0),
         ('C', 'can', 6.9, 10.5, 7.2, 0.00, 8.0),
         ('P1', 'pm', 7.0, 8.0, 7.2, 0.55, 3.0),
         ('P2', 'pm', 7.0, 7.5, 7.6, 0.60, 2.0),
         ('M1', 'mol', 11.0, 7.0, 8.6, 0.45, 0.0),
         ('M2', 'mol', 10.0, 6.5, 8.4, 0.20, 0.0)]

# heading of the labial line of the upper arch (degrees from +X) against arc length from the midline (mm)
ARCH_S = [0.0, 4.25, 11.75, 18.75, 26.0, 32.75, 41.0, 50.5, 56.0, 90.0]
ARCH_T = [0.0, 8.0, 26.0, 50.0, 66.0, 72.0, 77.0, 80.0, 80.5, 81.0]

_Q_ANT = [0.0, 0.035, 0.12, 0.27, 0.45, 0.63, 0.80, 0.93, 1.03, ROOT_Q]
_Q_POST = [0.0, 0.10, 0.25, 0.45, 0.68, 0.88, 1.03, ROOT_Q]
# cross-sections against q = height / crown height (0 = tip, 1 = gum line): am / ad = mesial / distal half-width
# (x W), vl / vi = labial / lingual face position (x T), nl / ni = superellipse exponents of the two halves.
KIND = {
    'inc': dict(N=20, q=_Q_ANT, qf=0.5, nl=3.4, ni=2.0, taper=0.30, edge=('round', 0.09, 0.19),
                am=[.455, .475, .492, .493, .49, .465, .435, .405, .385, .30],
                ad=[.43, .46, .485, .493, .49, .46, .415, .375, .35, .28],
                vl=[.07, .035, .008, 0, 0, .015, .05, .10, .15, .27],
                vi=[.17, .215, .27, .36, .52, .72, .90, .985, .97, .88]),
    'linc': dict(N=20, q=_Q_ANT, qf=0.5, nl=3.2, ni=2.0, taper=0.30, edge=('round', 0.08, 0.11),
                 am=[.47, .485, .495, .493, .485, .45, .41, .375, .35, .28],
                 ad=[.465, .485, .495, .493, .485, .45, .41, .375, .35, .28],
                 vl=[.08, .04, .01, 0, 0, .02, .06, .11, .16, .27],
                 vi=[.20, .25, .31, .40, .55, .74, .90, .98, .965, .87]),
    'can': dict(N=20, q=[0.0, 0.04, 0.13, 0.28, 0.45, 0.63, 0.80, 0.93, 1.03, ROOT_Q], qf=0.6, nl=2.4, ni=2.0,
                taper=0.32, edge=('cusp', -0.05, 0.72, 0.80, 0.5),
                am=[.33, .39, .455, .495, .49, .455, .41, .375, .35, .28],
                ad=[.35, .41, .47, .493, .49, .455, .41, .37, .345, .28],
                vl=[.17, .10, .045, .008, 0, .012, .04, .085, .13, .24],
                vi=[.40, .47, .56, .68, .82, .93, .99, .985, .95, .85]),
    'pm': dict(N=16, q=_Q_POST, qf=0.8, nl=2.4, ni=2.4, taper=0.12, edge=('pm', 1.5, 0.7, 0.9),
               caps=[(0.74, 1.0, 0.0), (0.42, 0.55, 1.25), (0.13, 0.2, 2.1)],
               am=[.40, .465, .495, .493, .46, .40, .36, .28],
               ad=[.40, .465, .495, .493, .46, .40, .36, .28],
               vl=[.14, .06, .015, 0, .02, .06, .09, .18],
               vi=[.86, .94, .985, 1.0, .98, .94, .91, .82]),
    'mol': dict(N=16, q=_Q_POST, qf=0.8, nl=3.0, ni=3.0, taper=0.05, edge=('mol', 0.9, 0.3, 0.8),
                caps=[(0.74, 1.0, 0.0), (0.42, 0.5, 1.1), (0.13, 0.2, 1.9)],
                am=[.43, .475, .495, .493, .475, .44, .40, .32],
                ad=[.43, .475, .495, .493, .475, .44, .40, .32],
                vl=[.12, .05, .01, 0, .02, .05, .08, .16],
                vi=[.88, .95, .99, 1.0, .98, .95, .92, .84]),
}
KIND['inc2'] = dict(KIND['inc'], edge=('round', 0.15, 0.30))
PAPILLA = {'inc': 4.3, 'inc2': 4.0, 'linc': 3.6, 'can': 3.8, 'pm': 2.8, 'mol': 2.2}   # zenith -> papilla tip
EMINENCE = {'inc': 0.35, 'inc2': 0.30, 'linc': 0.25, 'can': 0.50, 'pm': 0.28, 'mol': 0.22}   # root bulge of the gum

# tongue cage stations in the lower root's space (mm): y, half-width wanted (it is then fitted inside the lower
# teeth), top z, thickness, depth of the median groove
TONGUE = [(7.3, 5.2, -1.5, 2.6, 0.00),
          (9.6, 8.2, -1.3, 4.4, 0.25),
          (13.0, 10.2, -1.2, 6.2, 0.50),
          (17.0, 11.5, -1.0, 7.6, 0.70),
          (22.5, 14.0, -0.6, 8.6, 0.85),
          (28.5, 16.0, 0.0, 10.0, 0.85),
          (34.5, 17.0, 0.5, 11.0, 0.65),
          (40.5, 17.5, 0.6, 11.5, 0.40),
          (46.0, 17.5, -0.8, 11.5, 0.10),
          (50.5, 16.0, -5.5, 10.0, 0.00),
          (53.0, 12.5, -11.0, 7.0, 0.00)]
TONGUE_NOSE = (6.2, -2.4)        # y, z of the very tip
TONGUE_TAIL = (53.6, -15.5)
# ring template: (x / half-width, w / thickness) with w = +0.5 at the top, -0.5 at the bottom
_RING = [(0.0, 0.5), (0.50, 0.53), (0.90, 0.34), (1.0, 0.12), (0.70, -0.35),
         (0.0, -0.5), (-0.70, -0.35), (-1.0, 0.12), (-0.90, 0.34), (-0.50, 0.53)]
TONGUE_CLEAR = 0.35              # mm between the tongue and the lingual faces of the lower teeth
_SUBD_SHRINK = 0.955             # a subdivided ring of 10 control points is that much narrower than its cage

_MATS = {}


# ------------------------------------------------------------------------------------------------ small helpers
def _smooth(a, w):
    a = np.asarray(a, float)
    if w <= 1:
        return a.copy()
    return np.convolve(np.pad(a, w // 2, mode='edge'), np.ones(w) / w, mode='valid')


def _lin(c):
    v = [x / 255.0 for x in c]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v) + (1.0,)


class _Arch:
    """Labial line of a dental arch: sampled for s >= 0 (the character's left), mirrored for s < 0."""

    def __init__(self, X, Y, ds):
        self.X, self.Y, self.ds = np.asarray(X), np.asarray(Y), ds
        self.S = np.arange(len(X)) * ds
        tx, ty = np.gradient(self.X, ds), np.gradient(self.Y, ds)
        n = np.hypot(tx, ty)
        self.TX, self.TY = tx / n, ty / n
        self.yoff = 0.0

    def frame(self, s):
        """point, tangent towards the back of the mouth, outward (labial) normal - all 2D numpy arrays."""
        a, sg = abs(s), (1.0 if s >= 0 else -1.0)
        x, y = np.interp(a, self.S, self.X), np.interp(a, self.S, self.Y) - self.yoff
        tx, ty = np.interp(a, self.S, self.TX), np.interp(a, self.S, self.TY)
        return np.array((sg * x, y)), np.array((sg * tx, ty)), np.array((sg * ty, -tx))


def _curves():
    ds = 0.05
    S = np.arange(0.0, 85.0, ds)
    th = np.interp(S, ARCH_S, ARCH_T)
    full = np.concatenate([-th[:0:-1], th])
    r = int(6.0 / ds)
    ker = np.exp(-0.5 * (np.arange(-r, r + 1) * ds / 2.0) ** 2)
    full = np.convolve(np.pad(full, r, mode='edge'), ker / ker.sum(), mode='valid')
    th = np.radians(full[len(S) - 1:])
    X = np.concatenate([[0.0], np.cumsum(0.5 * (np.cos(th[1:]) + np.cos(th[:-1]))) * ds])
    Y = np.concatenate([[0.0], np.cumsum(0.5 * (np.sin(th[1:]) + np.sin(th[:-1]))) * ds])
    upper = _Arch(X, Y, ds)
    # the lower labial line = the upper one moved inwards (overjet 2.6 mm in front, ~1.9 mm at the molars)
    d = 1.85 + 0.75 * np.exp(-(S / 10.0) ** 2) + 0.75 * np.exp(-((S - 17.0) / 6.0) ** 2)
    QX, QY = X - d * np.sin(th), Y + d * np.cos(th)
    SL = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(QX), np.diff(QY)))])
    S2 = np.arange(0.0, SL[-1], ds)
    lower = _Arch(np.interp(S2, SL, QX), np.interp(S2, SL, QY) - QY[0], ds)
    return upper, lower, float(QY[0])


# ------------------------------------------------------------------------------------------------ one crown
def _tooth_local(kind, W, H, T, incl, wear=(0.0, 1.0, 0.0)):
    """A crown in its own frame: u = along the arch (distal +), v = towards the tongue (0 = labial-most plane),
    h = from the tip towards the root.  Returns verts (n, 3), faces, q attribute (0 tip .. 1 gum line)."""
    sp = KIND[kind]
    N = sp['N']
    q = np.array(sp['q'])
    am, ad = W * np.array(sp['am']), W * np.array(sp['ad'])
    vl, vi = T * np.array(sp['vl']), T * np.array(sp['vi'])
    a = 2 * np.pi * np.arange(N) / N
    ca, sa = np.cos(a), np.sin(a)
    ca[np.abs(ca) < 1e-9] = 0.0
    sa[np.abs(sa) < 1e-9] = 0.0
    n = np.where(sa >= 0, sp['ni'], sp['nl'])
    cu = np.sign(ca) * np.abs(ca) ** (2.0 / n)
    sv = np.sign(sa) * np.abs(sa) ** (2.0 / n)
    # narrower towards the tongue: the widest point (the contact with the neighbour) sits in the labial third
    shape = cu * (1.0 - sp['taper'] * np.clip((sv + 1.0) / 2.0, 0.0, 1.0))
    shape[ca > 0] /= shape[ca > 0].max()
    shape[ca < 0] /= -shape[ca < 0].min()

    def ring(j):
        aw = np.where(ca >= 0, ad[j], am[j])
        v = 0.5 * (vl[j] + vi[j]) + 0.5 * (vi[j] - vl[j]) * sv
        return aw * shape, v, aw * cu

    u0, v0, uu = ring(0)
    ed = sp['edge']
    c = np.zeros(N)
    if ed[0] == 'round':                       # incisal edge with rounded corners (mesial sharper than distal)
        e = np.zeros(N)
        for i in range(N):
            r, half = (ed[1] * W, am[0]) if uu[i] < 0 else (ed[2] * W, ad[0])
            x = min(1.0, max(0.0, (abs(uu[i]) - (half - r)) / r))
            e[i] = r * (1.0 - math.sqrt(1.0 - x * x))
        e += wear[0] * 0.5 * (1.0 + np.cos(2 * np.pi * wear[1] * uu / W + wear[2]))     # uneven wear of the edge
    elif ed[0] == 'cusp':                      # canine: one pointed cusp, a little mesial of the middle
        du = uu - ed[1] * W
        e = np.sqrt((np.where(du < 0, ed[2], ed[3]) * du) ** 2 + ed[4] ** 2) - ed[4]
    elif ed[0] == 'pm':                        # premolar: buccal + (shorter) lingual cusp
        c = ed[1] * ca ** 2 + np.where(sa > 0, ed[2] * sa ** 2, 0.0)
        e = c + ed[3]
    else:                                      # molar: four cusps, grooves on the four sides
        c = ed[1] * (0.5 + 0.5 * np.cos(4 * a)) + np.where(sa > 0, ed[2] * sa ** 2, 0.0)
        e = c + ed[3]
    rows, qa = [], []
    uc, vc = float(np.mean(u0)), float(np.mean(v0))
    for rho, k1, k0 in reversed(sp.get('caps', [])):        # occlusal table, innermost ring first
        rows.append(np.column_stack([uc + rho * (u0 - uc), vc + rho * (v0 - vc), k1 * c + k0]))
        qa.append(np.zeros(N))
    for j in range(len(q)):
        u, v, _ = ring(j)
        fade = (1.0 - q[j] / sp['qf']) ** 2 if q[j] < sp['qf'] else 0.0
        rows.append(np.column_stack([u, v, q[j] * H + e * fade]))
        qa.append(np.full(N, q[j]))
    V = np.concatenate(rows)
    V[:, 1] += V[:, 2] * math.tan(math.radians(incl))
    R = len(rows)
    F = []
    for r in range(R - 1):
        for i in range(N):
            j = (i + 1) % N
            F.append((r * N + i, r * N + j, (r + 1) * N + j, (r + 1) * N + i))
    for base in (0, (R - 1) * N):              # close both ends with a 'zip' along the mesio-distal axis
        for i in range(N // 2):
            quad = [base + i, base + i + 1, base + N - i - 1, base + (N - i) % N]
            quad = [x for k, x in enumerate(quad) if x not in quad[:k]]
            F.append(tuple(quad))
    return V, F, np.concatenate(qa)


def _build_teeth(table, arch, rng, lower):
    """All the crowns of one arch in arch space (x, y, h) with h = distance from the incisal plane."""
    cum = np.concatenate([[0.0], np.cumsum([t[2] for t in table])])
    V, F, Q, recs, base = [], [], [], [], 0
    for sg in (1.0, -1.0):
        for k, (nm, kind, W, H, T, off, incl) in enumerate(table):
            wear = (rng.uniform(0.0, 0.14), rng.uniform(0.7, 1.6), rng.uniform(0.0, 6.28))
            lv, lf, lq = _tooth_local(kind, W, H, T, incl, wear)
            if k == 0:                   # degrees about the tooth axis, degrees of lean, mm in height, mm in/out
                amp = (2.2, 1.3, 0.12, 0.12) if not lower else (4.0, 1.5, 0.15, 0.25)
            elif k < 3:
                amp = (3.5, 1.5, 0.25, 0.22) if not lower else (5.0, 1.8, 0.25, 0.30)
            else:
                amp = (2.5, 1.0, 0.20, 0.20)
            rz, tilt = math.radians(rng.uniform(-1, 1) * amp[0]), math.radians(rng.uniform(-1, 1) * amp[1])
            dh, dv = rng.uniform(-1, 1) * amp[2], rng.uniform(-1, 1) * amp[3]
            u, v, h = lv[:, 0], lv[:, 1], lv[:, 2]
            u = u + (h - 0.5 * H) * math.tan(tilt)
            vc = 0.4 * T
            u2 = u * math.cos(rz) - (v - vc) * math.sin(rz)
            v2 = vc + u * math.sin(rz) + (v - vc) * math.cos(rz) + dv
            p0, p1 = arch.frame(sg * cum[k])[0], arch.frame(sg * cum[k + 1])[0]
            pc = arch.frame(sg * 0.5 * (cum[k] + cum[k + 1]))[0]
            U = (p1 - p0) / np.linalg.norm(p1 - p0)
            Vv = sg * np.array((-U[1], U[0]))
            mid = 0.5 * (p0 + p1)
            O = mid + float(np.dot(pc - mid, Vv)) * Vv      # labial face tangent to the arch line
            xy = O[None, :] + u2[:, None] * U[None, :] + v2[:, None] * Vv[None, :]
            V.append(np.column_stack([xy, h + off + dh]))
            F += [tuple(i + base for i in f) for f in lf]
            Q.append(lq)
            recs.append(dict(sg=sg, k=k, lo=base, hi=base + len(lv), kind=kind, W=W, H=H, T=T, off=off, incl=incl))
            base += len(lv)
    V, Q = np.concatenate(V), np.concatenate(Q)
    # put the origin on the cutting edge / labial face of the two central incisors
    ys, hs = [], []
    for r in recs:
        if r['k'] == 0:
            P = V[r['lo']:r['hi']]
            hmin = P[:, 2].min()
            hs.append(hmin)
            sel = (P[:, 2] - hmin > 0.8) & (P[:, 2] - hmin < 2.2)
            ys.append(P[sel, 1].min())
    yo, ho = float(np.mean(ys)), float(np.mean(hs))
    V[:, 1] -= yo
    V[:, 2] -= ho
    arch.yoff += yo
    for r in recs:
        r['off'] -= ho
    return V, F, Q, recs, cum


# ------------------------------------------------------------------------------------------------ gums
def _build_gum(table, arch, recs, cum, tV, tF, lower, cavity):
    """Gum of one arch in arch space (x, y, h): a band wrapped around the necks of the teeth (outer wall, rolled
    margin, a bottom hidden inside the crowns, inner wall) and, with cavity, the palate (upper) / mouth floor
    (lower) closing the inside of the arch, plus the soft palate hanging at the back (upper)."""
    bvh = BVHTree.FromPolygons([Vector(p) for p in tV], tF)
    tmax = max(t[4] for t in table)
    left = [(0.0, 0, -1.0)]
    for k in range(7):                  # stations across each tooth; +-0.86 wrap the gum around its corners
        for f in (-0.86, -0.6, -0.3, 0.0, 0.3, 0.6, 0.86, 1.0):
            left.append((cum[k] + table[k][2] * (f + 1.0) / 2.0, k, f))
    left += [(cum[7] + 1.6, 7, 0.0), (cum[7] + 3.4, 7, 0.0)]
    st = [(-s, k, f) for (s, k, f) in left[:0:-1]] + left
    n = len(st)
    zc = [table[k][3] + recs[k]['off'] for k in range(7)]
    hp = [PAPILLA[table[k][1]] for k in range(7)]
    bnd = [zc[0] - hp[0]] + [0.5 * (zc[k] - hp[k] + zc[k + 1] - hp[k + 1]) for k in range(6)] + [zc[6] - 0.7 * hp[6]]
    P, Nn = np.zeros((n, 2)), np.zeros((n, 2))
    zmo, zmi, zcs, inc, emi = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    dm, dl = np.full(n, np.nan), np.full(n, np.nan)
    far, din = 6.0, tmax + 5.0
    for i, (s, k, f) in enumerate(st):
        P[i], _, Nn[i] = arch.frame(s)
        if k < 7:
            B = bnd[k] if f < 0 else bnd[k + 1]
            zmo[i] = zc[k] - (zc[k] - B) * abs(f) ** 2.0
            zmi[i] = zc[k] - 0.9 - 0.55 * (zc[k] - B) * abs(f) ** 2.0
            zcs[i], inc[i] = zc[k], table[k][6]
            emi[i] = EMINENCE[table[k][1]] * math.cos(math.pi * f)
        else:
            zmo[i] = zmi[i] = bnd[7] + 0.3
            zcs[i], inc[i] = zc[6], table[6][6]
        nv = Vector((Nn[i][0], Nn[i][1], 0.0))
        o = Vector((P[i][0], P[i][1], zmo[i] + 0.2)) + nv * far
        hit = bvh.ray_cast(o, -nv, far + tmax + 3.0)
        if hit[0] is not None:
            dm[i] = hit[3] - far
        o = Vector((P[i][0], P[i][1], zmi[i] + 0.2)) - nv * din
        hit = bvh.ray_cast(o, nv, din + 3.0)
        if hit[0] is not None:
            dl[i] = din - hit[3]
    idx = np.arange(n)
    fa = np.array([abs(f) if k < 7 else 2.0 for (s, k, f) in st])
    core = fa < 0.61                                    # stations on the faces of the teeth, not on their corners
    ok_o, ok_i = core & ~np.isnan(dm), core & ~np.isnan(dl)
    lab = np.interp(idx, idx[ok_o], dm[ok_o])           # the line of the labial faces at the gum
    lin = np.interp(idx, idx[ok_i], dl[ok_i])           # the line of the lingual faces
    emb_o = emb_i = fa > 0.99                           # between two teeth (papilla) and behind the last molar
    # the gum dives behind the corners of the crowns, so the papilla only shows through the gap between two teeth
    dmf = np.where(fa > 1.5, lab + 0.8, np.where(emb_o, lab + 1.8, np.where(core, lab, np.fmax(dm, lab + 1.2))))
    dlf = np.where(fa > 1.5, lin - 0.8, np.where(emb_i, lin - 1.5, np.where(core, lin, np.fmin(dl, lin - 1.0))))
    dmf = np.where(core & ~np.isnan(dm), dm, dmf)
    dlf = np.where(core & ~np.isnan(dl), dl, dlf)
    alv_o, alv_i = _smooth(lab, 11), _smooth(lin, 11)
    zs = _smooth(zcs, 11)
    sl = np.tan(np.radians(_smooth(inc, 9)))
    top = GUM_BAND
    prof, shade = [], []
    for i in range(n):
        eo, ei = emb_o[i], emb_i[i]
        z2 = 0.5 * (zmo[i] + 3.2) + 0.5 * (zs[i] + 1.6)
        o = [(alv_o[i] + 0.6 - 0.3 * emi[i] + sl[i] * top * 0.9, zs[i] + top),
             (alv_o[i] - 0.6 - emi[i] + sl[i] * 5.5 * 0.9, zs[i] + 5.5),
             (0.4 * (dmf[i] - 0.42) + 0.6 * (alv_o[i] - 0.5 - emi[i]) + sl[i] * (z2 - zmo[i]), z2),
             (dmf[i] - (0.25 if eo else 0.40) + sl[i] * 0.9, zmo[i] + 1.0),
             (dmf[i] - (0.0 if eo else 0.22), zmo[i] + 0.12),
             (dmf[i] + (1.6 if eo else 0.6), zmo[i] - 0.15)]
        zi2 = zs[i] - 0.9 + 3.2
        inn = [(dlf[i] - (1.6 if ei else 0.6), zmi[i] - 0.15),
               (dlf[i] + (0.0 if ei else 0.22), zmi[i] + 0.12),
               (dlf[i] + (0.25 if ei else 0.45) + sl[i] * 0.9, zmi[i] + 1.0),
               (alv_i[i] + 1.0 + sl[i] * 3.5, zi2)]
        b = (0.5 * (o[5][0] + inn[0][0]), min(o[5][1], inn[0][1]) - 0.1)
        pts = [np.array((P[i][0] - Nn[i][0] * d, P[i][1] - Nn[i][1] * d, z)) for d, z in o + [b] + inn]
        sh = [0.30, 0.22, 0.12, 0.05, 0.0, 0.0, 0.05, 0.0, 0.0, 0.05, 0.15]
        if cavity:
            q2 = pts[-1]
            ysp = 5.5 + 0.93 * q2[1]
            if lower:
                zsp = 10.5 + 2.0 * (1.0 - math.exp(-max(0.0, q2[1] - 8.0) / 10.0))
            else:
                zsp = 9.5 + 10.5 * (1.0 - math.exp(-max(0.0, ysp - 8.0) / 9.0))
            back = 0.25 * min(1.0, max(0.0, q2[1] / 45.0))
            sh[-1] += back
            for t, s0 in ((0.25, 0.25), (0.5, 0.32), (0.75, 0.38), (1.0, 0.42)):
                w = math.sin(t * math.pi / 2) ** 0.9
                pts.append(np.array((q2[0] * (1 - t), q2[1] + (ysp - q2[1]) * t, q2[2] + (zsp - q2[2]) * w)))
                sh.append(s0 + back)
        else:
            pts.append(np.array((P[i][0] - Nn[i][0] * (alv_i[i] + 2.2 + sl[i] * 8.0),
                                 P[i][1] - Nn[i][1] * (alv_i[i] + 2.2 + sl[i] * 8.0), zs[i] + 7.5)))
            sh.append(0.35)
        prof.append(pts)
        shade.append(sh)
    m = len(prof[0])
    mid = n // 2
    V, S, index = [], [], np.zeros((n, m), int)
    for i in range(n):
        for j in range(m):
            if cavity and j == m - 1 and i < mid:           # the midline vertices are shared by both sides
                index[i, j] = -1
                continue
            index[i, j] = len(V)
            V.append(prof[i][j])
            S.append(shade[i][j])
    if cavity:
        for i in range(mid):
            index[i, m - 1] = index[n - 1 - i, m - 1]
    F = []
    ref = None
    for i in range(n - 1):
        for j in range(m - 1):
            if i == mid and j == 1:
                ref = len(F)
            F.append((index[i, j], index[i + 1, j], index[i + 1, j + 1], index[i, j + 1]))
    for i in (0, n - 1):                                    # close the band behind the last molar
        F.append(tuple(index[i, j] for j in range(11)))
    if cavity and not lower:                                # soft palate / back of the throat
        prev = ([index[n - 1, 0]] + [index[n - 1, j] for j in range(10, m)] +
                [index[0, j] for j in range(m - 2, 9, -1)] + [index[0, 0]])        # cheek to cheek, over the palate
        base = [V[r].copy() for r in prev]
        for dy, w, sx, s0 in ((2.5, 0.06, 1.0, 0.62), (5.0, 0.22, 0.98, 0.76), (7.0, 0.46, 0.95, 0.88),
                              (8.5, 0.74, 0.92, 0.96), (9.5, 1.0, 0.90, 1.0)):
            new = []
            for p0 in base:
                new.append(len(V))
                V.append(np.array((p0[0] * sx, p0[1] + dy, p0[2] + (-16.0 - p0[2]) * w)))
                S.append(s0)
            for c in range(len(prev) - 1):
                F.append((prev[c], prev[c + 1], new[c + 1], new[c]))
            prev = new
    return np.array(V), F, np.array(S), ref


# ------------------------------------------------------------------------------------------------ tongue
def _tongue_stations(mode):
    """[y, zc, half-width, thickness, groove, phi] per station (nose first, tail last; both with zero width)."""
    st = [[TONGUE_NOSE[0], TONGUE_NOSE[1], 0.0, 0.0, 0.0, 0.0]]
    st += [[y, top - th / 2.0, hw, th, g, 0.0] for (y, hw, top, th, g) in TONGUE]
    st.append([TONGUE_TAIL[0], TONGUE_TAIL[1], 0.0, 0.0, 0.0, 0.0])
    y0 = TONGUE_NOSE[0]
    if mode == 'up':                 # the blade curls up: tip against the palatal side of the upper incisors
        yh, stretch, pm = 30.0, 1.24, math.radians(62.0)
        A = yh - y0
        for s in st:
            if s[0] >= yh:
                continue
            a = yh - s[0]
            t = np.linspace(0.0, a, 48)
            ph = pm * (t / A) ** 1.3
            dt = t[1] - t[0]
            s[0] = yh - float(np.sum(0.5 * (np.cos(ph[1:]) + np.cos(ph[:-1]))) * dt) * stretch
            s[1] += float(np.sum(0.5 * (np.sin(ph[1:]) + np.sin(ph[:-1]))) * dt) * stretch
            s[5] = float(ph[-1])
    elif mode == 'out':              # the tip slides 6 mm forward over the lower incisors, flatter and narrower
        yh = 36.0
        A = yh - y0
        for s in st:
            w = min(1.0, max(0.0, (yh - s[0]) / A))
            s[0] -= 6.0 * w ** 1.15
            s[1] += 4.6 * min(1.0, w / 0.75) ** 1.5
            s[3] *= 1.0 - 0.28 * w
            s[2] *= 1.0 - 0.12 * w
    return st


def _fit_tongue(st, bvh):
    """Clamp the half-widths so that the tongue stays inside the lingual faces of the lower teeth."""
    last = None
    for s in st[1:-1]:
        y, zc, hw, th, g, ph = s
        lim = 1e9
        for xf, w in _RING[1:5]:
            for dy in (-3.0, -1.5, 0.0, 1.5, 3.0):
                o = Vector((0.0, y + w * th * math.sin(ph) + dy, zc + w * th * math.cos(ph)))
                for sx in (1.0, -1.0):
                    hit = bvh.ray_cast(o, Vector((sx, 0.0, 0.0)), 40.0)
                    if hit[0] is not None:
                        lim = min(lim, (hit[3] - TONGUE_CLEAR) / xf / _SUBD_SHRINK)
        hw = min(hw, lim)
        if lim > 1e8 and y > 42.0 and last is not None:      # behind the last molar: no sudden flare
            hw = min(hw, last[1] + 0.25 * abs(y - last[0]))
        s[2] = hw
        last = (y, hw)
    return st


def _tongue_verts(st):
    V = [(0.0, st[0][0], st[0][1])]
    for y, zc, hw, th, g, ph in st[1:-1]:
        for i, (xf, w) in enumerate(_RING):
            ww = w * th - (g if i == 0 else 0.0)
            V.append((xf * hw, y + ww * math.sin(ph), zc + ww * math.cos(ph)))
    V.append((0.0, st[-1][0], st[-1][1]))
    return np.array(V)


def _tongue_faces(nr):
    R = len(_RING)
    F = []
    for i in range(R):
        F.append((0, 1 + (i + 1) % R, 1 + i))
    for r in range(nr - 1):
        for i in range(R):
            j = (i + 1) % R
            F.append((1 + r * R + i, 1 + r * R + j, 1 + (r + 1) * R + j, 1 + (r + 1) * R + i))
    tail = 1 + nr * R
    for i in range(R):
        F.append((tail, 1 + (nr - 1) * R + i, 1 + (nr - 1) * R + (i + 1) % R))
    return F


# ------------------------------------------------------------------------------------------------ materials
def _ramp(nt, fac, stops):
    r = nt.nodes.new('ShaderNodeValToRGB')
    els = r.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for e, (p, c) in zip(els, stops):
        e.position = p
        e.color = _lin(c)
    nt.links.new(fac, r.inputs['Fac'])
    return r.outputs['Color']


def _object_coords(nt, scale):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    return mp.outputs['Vector']


def _bump(nt, height, strength, distance, invert=False):
    b = nt.nodes.new('ShaderNodeBump')
    b.invert = invert
    b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = distance
    nt.links.new(height, b.inputs['Height'])
    return b.outputs['Normal']


def _principled(name, rough, sss, radius, sss_scale, coat, coat_rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.subsurface_method = 'BURLEY'
    I = b.inputs
    I['Roughness'].default_value = rough
    I['Subsurface Weight'].default_value = sss
    I['Subsurface Radius'].default_value = radius
    I['Subsurface Scale'].default_value = sss_scale
    I['Coat Weight'].default_value = coat
    I['Coat Roughness'].default_value = coat_rough
    if 'Coat IOR' in I:
        I['Coat IOR'].default_value = 1.38
    return m, nt, b


def materials(scale=1.0):
    """{'enamel', 'gum', 'tongue'}: shared Cycles materials (cached per scale; scale 1 = human size).
    enamel reads the vertex attribute 'cerv' (0 cutting edge .. 1 gum line), gum reads 'shade' (0 gum margin ..
    0.4 palate .. 1 back of the throat)."""
    key = round(scale, 3)
    got = _MATS.get(key)
    try:
        if got and all(m.name in bpy.data.materials for m in got.values()):
            return got
    except ReferenceError:                     # the file was reset since: build them again
        pass
    k = scale * MM
    # enamel: warm off-white, yellower / darker towards the gum, wet coat, a little subsurface
    m, nt, b = _principled(f'teeth6_enamel_{key}', 0.25, 0.15, (1.0, 0.8, 0.6), 1.0 * k, 0.55, 0.05)
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'cerv'
    col = _ramp(nt, at.outputs['Fac'], [(0.0, (228, 226, 222)), (0.10, (238, 232, 218)), (0.45, (235, 227, 209)),
                                        (0.75, (230, 214, 186)), (1.0, (214, 190, 152))])
    nt.links.new(col, b.inputs['Base Color'])
    b.inputs['IOR'].default_value = 1.55
    ns = nt.nodes.new('ShaderNodeTexNoise')
    ns.inputs['Scale'].default_value = 0.45
    ns.inputs['Detail'].default_value = 2.0
    nt.links.new(_object_coords(nt, 1.0 / k), ns.inputs['Vector'])
    nt.links.new(_bump(nt, ns.outputs['Fac'], 0.06, 0.25 * k), b.inputs['Normal'])
    enamel = m
    # gums: pink-red, lighter at the margin, dark red at the back of the mouth
    m, nt, b = _principled(f'teeth6_gum_{key}', 0.30, 0.35, (1.0, 0.35, 0.25), 2.5 * k, 0.4, 0.12)
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'shade'
    col = _ramp(nt, at.outputs['Fac'], [(0.0, (208, 120, 118)), (0.06, (194, 100, 100)), (0.2, (186, 90, 92)),
                                        (0.45, (160, 68, 74)), (0.7, (104, 36, 40)), (1.0, (28, 8, 10))])
    nt.links.new(col, b.inputs['Base Color'])
    ns = nt.nodes.new('ShaderNodeTexNoise')
    ns.inputs['Scale'].default_value = 2.2
    ns.inputs['Detail'].default_value = 3.0
    nt.links.new(_object_coords(nt, 1.0 / k), ns.inputs['Vector'])
    nt.links.new(_bump(nt, ns.outputs['Fac'], 0.3, 0.3 * k), b.inputs['Normal'])
    gum = m
    # tongue: pink, velvety (papillae), darker towards the root
    m, nt, b = _principled(f'teeth6_tongue_{key}', 0.45, 0.30, (1.0, 0.4, 0.3), 3.0 * k, 0.3, 0.2)
    vec = _object_coords(nt, 1.0 / k)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(vec, sep.inputs['Vector'])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 6.0
    mr.inputs['From Max'].default_value = 52.0
    nt.links.new(sep.outputs['Y'], mr.inputs['Value'])
    col = _ramp(nt, mr.outputs['Result'], [(0.0, (208, 112, 118)), (0.35, (200, 110, 115)), (0.75, (178, 92, 98)),
                                           (1.0, (120, 52, 58))])
    big = nt.nodes.new('ShaderNodeTexNoise')
    big.inputs['Scale'].default_value = 0.35
    big.inputs['Detail'].default_value = 3.0
    nt.links.new(vec, big.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs[7].default_value = _lin((226, 196, 196))
    nt.links.new(big.outputs['Fac'], mix.inputs['Factor'])
    nt.links.new(col, mix.inputs[6])
    nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    vo = nt.nodes.new('ShaderNodeTexVoronoi')
    vo.feature = 'SMOOTH_F1'
    vo.inputs['Scale'].default_value = 1.9
    vo.inputs['Smoothness'].default_value = 0.6
    nt.links.new(vec, vo.inputs['Vector'])
    nt.links.new(_bump(nt, vo.outputs['Distance'], 0.45, 0.35 * k, invert=True), b.inputs['Normal'])
    tongue = m
    _MATS[key] = {'enamel': enamel, 'gum': gum, 'tongue': tongue}
    return _MATS[key]


# ------------------------------------------------------------------------------------------------ objects
def _mesh_object(name, V, F, col, parent, mat, attrs=None, ref=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, p)) for p in V], [], [tuple(int(i) for i in f) for f in F])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if ref is not None:                        # open sheet: make the reference face look to the front (-Y)
        bm.faces.ensure_lookup_table()
        if bm.faces[ref].normal.y > 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    for an, arr in (attrs or {}).items():
        at = me.attributes.new(an, 'FLOAT', 'POINT')
        at.data.foreach_set('value', np.asarray(arr, np.float32))
    me.materials.append(mat)
    me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.parent = parent
    return ob


def bite_offset(arch_width=0.046, name='teeth'):
    """Lower origin relative to the upper origin (metres, upper root space) when the jaw is closed."""
    g = _geometry(name, True)
    return Vector(g['bite']) * (arch_width * 1000.0 / g['ref']) * MM


def jaw_matrix(T, open_m=0.0, rot_deg=0.0, forward_m=0.0):
    """Matrix of the 'lower' root in the 'upper' root's space: closed bite, dropped by open_m, moved forward_m
    towards -Y, then rotated rot_deg about X through the lower incisors' edge (positive = the mouth opens)."""
    b = T['bite']
    return (Matrix.Translation((b.x, b.y - forward_m, b.z - open_m)) @
            Matrix.Rotation(math.radians(rot_deg), 4, 'X'))


def set_jaw(T, open_m=0.0, rot_deg=0.0, forward_m=0.0):
    """Place the 'lower' root from the 'upper' root (both roots must have the same parent, or none)."""
    T['lower'].matrix_basis = T['upper'].matrix_basis @ jaw_matrix(T, open_m, rot_deg, forward_m)


_GEO = {}


def _geometry(seed, cavity):
    """Everything in millimetres at human size.  Upper parts in the upper root's space, lower parts in the lower
    root's space (both with the real z: up positive)."""
    key = (seed, cavity)
    if key in _GEO:
        return _GEO[key]
    rng = random.Random(zlib.crc32(str(seed).encode()))
    au, al, d0 = _curves()
    uV, uF, uQ, urecs, ucum = _build_teeth(UPPER, au, rng, False)
    lV, lF, lQ, lrecs, lcum = _build_teeth(LOWER, al, rng, True)
    ugV, ugF, ugS, uref = _build_gum(UPPER, au, urecs, ucum, uV, uF, False, cavity)
    lgV, lgF, lgS, lref = _build_gum(LOWER, al, lrecs, lcum, lV, lF, True, cavity)
    flip = np.array((1.0, 1.0, -1.0))
    lV, lgV = lV * flip, lgV * flip
    bvh = BVHTree.FromPolygons([Vector(p) for p in lV], lF)
    keys = {m: _tongue_verts(_fit_tongue(_tongue_stations(m), bvh)) for m in ('rest', 'up', 'out')}
    p2 = [np.abs(uV[r['lo']:r['hi'], 0]).max() for r in urecs if r['k'] == 4]
    uw = [float(np.mean([np.abs(uV[r['lo']:r['hi'], 0]).max() for r in urecs if r['k'] == k])) * 2.0 for k in range(7)]
    g = dict(upper_widths=uw, ut=(uV, uF, uQ), lt=(lV, lF, lQ), ug=(ugV, ugF, ugS, uref), lg=(lgV, lgF, lgS, lref),
             tongue=keys, tongue_faces=_tongue_faces(len(TONGUE)), ref=float(2.0 * np.mean(p2)),
             bite=(0.0, d0 + al.yoff - au.yoff, OVERBITE))
    _GEO[key] = g
    return g


def build(name, arch_width=0.046, collection=None, cavity=True, seed=None):
    """Teeth, gums and tongue.  See the module docstring for the returned dict and the conventions.
    cavity=False leaves out the palate / throat wall / mouth floor (keep only the gum bands)."""
    g = _geometry(name if seed is None else seed, cavity)
    s = arch_width * 1000.0 / g['ref']
    k = s * MM
    col = collection or bpy.context.scene.collection
    mats = materials(s)
    roots = {}
    for part in ('upper', 'lower'):
        e = bpy.data.objects.new(f'{name}.{part}', None)
        e.empty_display_type = 'PLAIN_AXES'
        e.empty_display_size = 0.01
        col.objects.link(e)
        roots[part] = e
    V, F, Q = g['ut']
    ut = _mesh_object(f'{name}.upper.teeth', V * k, F, col, roots['upper'], mats['enamel'], {'cerv': Q})
    V, F, Q = g['lt']
    lt = _mesh_object(f'{name}.lower.teeth', V * k, F, col, roots['lower'], mats['enamel'], {'cerv': Q})
    V, F, S, ref = g['ug']
    ug = _mesh_object(f'{name}.upper.gum', V * k, F, col, roots['upper'], mats['gum'], {'shade': S}, ref)
    V, F, S, ref = g['lg']
    lg = _mesh_object(f'{name}.lower.gum', V * k, F, col, roots['lower'], mats['gum'], {'shade': S}, ref)
    tk = g['tongue']
    tg = _mesh_object(f'{name}.tongue', tk['rest'] * k, g['tongue_faces'], col, roots['lower'], mats['tongue'])
    tg.shape_key_add(name='Basis', from_mix=False)
    for kn in ('up', 'out'):
        kb = tg.shape_key_add(name=kn, from_mix=False)
        kb.data.foreach_set('co', (tk[kn] * k).astype(np.float32).ravel())
        kb.slider_min, kb.slider_max = 0.0, 1.5
        kb.value = 0.0                         # (new keys come with value 1 in Blender 5)
    sub = tg.modifiers.new('subsurf', 'SUBSURF')
    sub.levels = sub.render_levels = 2
    uV, lV, tV = g['ut'][0], g['lt'][0], tk['rest']
    dims = dict(
        upper_width=float(np.ptp(uV[:, 0])) * k, upper_depth=float(uV[:, 1].max() - uV[:, 1].min()) * k,
        lower_width=float(np.ptp(lV[:, 0])) * k, lower_depth=float(lV[:, 1].max() - lV[:, 1].min()) * k,
        upper_top=float(g['ug'][0][:, 2].max()) * k, lower_bottom=float(g['lg'][0][:, 2].min()) * k,
        back=float(g['ug'][0][:, 1].max()) * k, upper_widths=[w * k for w in g['upper_widths']],
        tongue_width=float(np.ptp(tV[:, 0])) * _SUBD_SHRINK * k, tongue_tip_y=float(tV[:, 1].min()) * k)
    return {'upper': roots['upper'], 'lower': roots['lower'], 'tongue': tg, 'objects': [ut, ug, lt, lg, tg],
            'upper_teeth': ut, 'upper_gum': ug, 'lower_teeth': lt, 'lower_gum': lg,
            'bite': Vector(g['bite']) * k, 'scale': s, 'dims': dims}
