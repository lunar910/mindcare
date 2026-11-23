"""Lip-sync: viseme shape keys (MakeHuman 'meta-style' viseme targets, CC0) and a rough French text -> viseme timeline.

    D = speech.add_visemes(ch)                      # shape keys vis_PP, vis_aa ... on the body
    tl = speech.timeline("Frérot, c'est pas moi.", start=0.5)
    speech.apply(ch, tl, t)                         # set the shape key values for time t (seconds)"""
import os
import re

import numpy as np

try:
    import mh
    VIS_DIR = os.path.join(mh.SP, 'mh-extra', 'visemes02', 'targets', 'visemes')
except ImportError:          # text -> viseme rules only
    mh = None
    VIS_DIR = None
VISEMES = ['PP', 'FF', 'TH', 'DD', 'kk', 'CH', 'SS', 'nn', 'RR', 'aa', 'E', 'I', 'O', 'U']
VOWELS = {'aa', 'E', 'I', 'O', 'U'}


def load_target(path, n):
    D = np.zeros((n, 3))
    with open(path) as fh:
        for line in fh:
            t = line.split()
            if len(t) == 4 and not t[0].startswith('#'):
                D[int(t[0])] = (float(t[1]), float(t[2]), float(t[3]))
    return D


def viseme_deltas():
    """{viseme: (n_base_verts, 3) displacement in MakeHuman coordinates}, helper geometry (teeth, tongue) included."""
    n = len(mh.base().v)
    return {v: load_target(os.path.join(VIS_DIR, f'viseme_{v}.target'), n) for v in VISEMES}


def add_visemes(ch):
    """Add shape keys vis_<name> to the body mesh. Returns the full-base deltas so attached meshes can be refitted."""
    body = ch['body']
    if body.data.shape_keys is None:
        body.shape_key_add(name='Basis', from_mix=False)
    kb = body.data.shape_keys.key_blocks
    n = len(body.data.vertices)
    basis = np.zeros(n * 3, dtype=np.float32)
    kb['Basis'].data.foreach_get('co', basis)
    basis = basis.reshape(n, 3)
    D = viseme_deltas()
    for v, d in D.items():
        if 'vis_' + v in kb:
            continue
        sk = body.shape_key_add(name='vis_' + v, from_mix=False)
        sk.data.foreach_set('co', (basis + mh.to_bl(d[ch['used']])).astype(np.float32).ravel())
        sk.value = 0.0
    ch['viseme_deltas'] = D
    ch['viseme_followers'] = follow(ch, D)
    return D


def _attachments(ch):
    """(object, asset kind, asset name) of the fitted face attachments that must move with the mouth."""
    import cfg_face as CF
    out = []
    mouth = ch.get('mouth') or {}
    for key in ('teeth', 'tongue'):
        if mouth.get(key) is not None and CF.MOUTH.get(key):
            out.append((mouth[key], key, CF.MOUTH[key]))
    if ch.get('lashes') is not None and CF.LASHES and CF.LASHES.get('asset'):
        out.append((ch['lashes'], 'eyelashes', CF.LASHES['asset']))
    return out


def follow(ch, D, min_move=2e-5):
    """Give teeth, tongue and lashes the viseme shape keys too (refitted on V + delta) and drive them from the body's keys."""
    import mhassets as A
    V = ch['V']
    body_keys = ch['body'].data.shape_keys
    done = []
    for ob, kind, name in _attachments(ch):
        folder = A.find(kind, name)
        info = A.parse_mhclo(os.path.join(folder, [f for f in os.listdir(folder) if f.endswith('.mhclo')][0]))
        S = np.ones(3)
        for k, (a, b, den) in info['scales'].items():
            S[k] = abs(V[a][k] - V[b][k]) / den

        def fit(W):
            r, w = info['refs'], info['w']
            return W[r[:, 0]] * w[:, 0:1] + W[r[:, 1]] * w[:, 1:2] + W[r[:, 2]] * w[:, 2:3] + info['off'] * S
        base = fit(V)
        n = len(ob.data.vertices)
        rest = np.zeros(n * 3, dtype=np.float32)
        ob.data.vertices.foreach_get('co', rest)
        rest = rest.reshape(n, 3)
        for v, d in D.items():
            key = 'vis_' + v
            if ob.data.shape_keys is not None and key in ob.data.shape_keys.key_blocks:
                continue
            dd = mh.to_bl(fit(V + d) - base)
            if np.abs(dd).max() < min_move:
                continue
            if ob.data.shape_keys is None:
                ob.shape_key_add(name='Basis', from_mix=False)
            sk = ob.shape_key_add(name=key, from_mix=False)
            sk.data.foreach_set('co', (rest + dd).astype(np.float32).ravel())
            sk.value = 0.0
            fc = ob.data.shape_keys.driver_add(f'key_blocks["{key}"].value')
            fc.driver.type = 'AVERAGE'
            var = fc.driver.variables.new()
            var.name = 'v'
            var.type = 'SINGLE_PROP'
            var.targets[0].id_type = 'KEY'
            var.targets[0].id = body_keys
            var.targets[0].data_path = f'key_blocks["{key}"].value'
        done.append(ob)
    return done


# ---------------------------------------------------------------- French text -> visemes
_RULES = [  # (regex on lowercase text, [visemes]); longest patterns first
    (r'eaux?', ['O']), (r'aux?(?![a-zàâéèêëîïôöùûü])', ['O']), (r'au', ['O']), (r'où|oû|ou', ['U']), (r'oi', ['U', 'aa']),
    (r'ai|ei|è|ê|ë|é', ['E']), (r'œu|eu|œ', ['O']),
    (r'(?:an|am|en|em)(?![aeiouyàâéèêëîïôöùûünm])', ['aa']), (r'(?:on|om)(?![aeiouyàâéèêëîïôöùûünm])', ['O']),
    (r'(?:ain|ein|in|im|un|um)(?![aeiouyàâéèêëîïôöùûünm])', ['E']),
    (r'ch|sh', ['CH']), (r'ph', ['FF']), (r'gn', ['nn']), (r'qu', ['kk']), (r'gu(?=[eiy])', ['kk']), (r'th', ['DD']),
    (r'ill', ['I']), (r'ss', ['SS']), (r'tt|dd', ['DD']), (r'nn|mm(?=e)', ['nn']), (r'rr', ['RR']), (r'll', ['nn']), (r'ff', ['FF']),
    (r'pp|bb', ['PP']),
    (r'[aàâ]', ['aa']), (r'[iîïy]', ['I']), (r'[oôö]', ['O']), (r'[uûùü]', ['U']), (r'e', ['E']),
    (r'[pbm]', ['PP']), (r'[fv]', ['FF']), (r'[td]', ['DD']), (r'[nl]', ['nn']), (r'[kq]', ['kk']),
    (r'g(?=[eiy])', ['CH']), (r'g', ['kk']), (r'c(?=[eiyéèê])', ['SS']), (r'c', ['kk']), (r'[çsz]', ['SS']), (r'j', ['CH']),
    (r'r', ['RR']), (r'x', ['kk', 'SS']), (r'w', ['U']), (r'h', []),
]
_RULES = [(re.compile(p), v) for p, v in _RULES]
_SILENT_END = re.compile(r'(?<=[a-zàâéèêëîïôöùûüç])(?:ent|es|e|s|t|d|x|z|p)$')
_KEEP = {'et': 'é', 'est': 'è', 'les': 'lé', 'des': 'dé', 'mes': 'mé', 'tes': 'té', 'ses': 'sé', 'ces': 'sé', 'de': 'de', 'le': 'le',
         'je': 'je', 'me': 'me', 'te': 'te', 'se': 'se', 'ne': 'ne', 'que': 'ke', 'ce': 'se', 'pas': 'pa', 'moi': 'moi', 'toi': 'toi',
         'tu': 'tu', 'un': 'un', 'il': 'il', 'elle': 'èl', 'tout': 'tou', 'plus': 'plu', 'fils': 'fis', 'vrai': 'vrè',
         'c': 's', 'j': 'j', 'l': 'l', 'd': 'd', 'n': 'n', 'm': 'm', 's': 's', 't': 't', 'qu': 'k', 'wesh': 'ouèch', 'ouais': 'ouè'}


def french_visemes(text):
    """Sequence of ('viseme' | 'sil', relative duration). Deliberately rough: enough for cartoon lip-sync."""
    out = []
    for tok in re.findall(r"[a-zàâéèêëîïôöùûüçœ]+|[,;:]|[.!?…]+", text.lower().replace('’', "'")):
        if tok[0] in ',;:':
            out.append(('sil', 1.6))
            continue
        if tok[0] in '.!?…':
            out.append(('sil', 3.0))
            continue
        w = _KEEP.get(tok)
        mute = 10 ** 6
        if w is None:
            w = tok
            m_end = _SILENT_END.search(tok) if len(tok) > 3 else None
            if m_end:
                mute = m_end.start()        # the ending is silent but still gives context (soft g / c before a mute e)
        i = 0
        while i < len(w):
            for rx, vis in _RULES:
                m = rx.match(w, i)
                if m:
                    for v in (vis if i < mute else []):
                        if out and out[-1][0] == v:     # merge repeats
                            out[-1] = (v, out[-1][1] + 0.4)
                        else:
                            out.append((v, 1.0 if v in VOWELS else 0.55))
                    i = m.end()
                    break
            else:
                i += 1
    return out


def timeline(text, start=0.0, duration=None, rate=0.105):
    """[(t0, t1, viseme)] for a spoken line. rate = seconds per unit (a vowel is 1 unit) unless duration is given."""
    seq = french_visemes(text)
    total = sum(d for _, d in seq) or 1.0
    k = (duration / total) if duration else rate
    tl, t = [], start
    for v, d in seq:
        if v != 'sil':
            tl.append((t, t + d * k, v))
        t += d * k
    return tl


def end_time(tl):
    return max((t1 for _, t1, _ in tl), default=0.0)


def weights_at(tl, t, attack=0.05, release=0.08):
    """{viseme: 0..1} at time t with soft attacks and releases (neighbouring mouth shapes blend into each other)."""
    w = {}
    for t0, t1, v in tl:
        if t < t0 - attack or t > t1 + release:
            continue
        if t < t0:
            x = 1 - (t0 - t) / attack
        elif t > t1:
            x = 1 - (t - t1) / release
        else:
            x = 1.0
        x = x * x * (3 - 2 * x)
        w[v] = max(w.get(v, 0.0), x)
    s = sum(w.values())
    if s > 1.0:
        w = {k: x / s for k, x in w.items()}
    return w


def apply(ch, tl, t, strength=1.0):
    kb = ch['body'].data.shape_keys.key_blocks
    w = weights_at(tl, t)
    for v in VISEMES:
        kb['vis_' + v].value = w.get(v, 0.0) * strength         # teeth, tongue and lashes follow through their drivers
    return w
