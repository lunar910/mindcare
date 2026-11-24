"""The excerpt's script for version 4: lines split into phrases with real pauses, and the shots cut on the words.

Timing follows the reference (study/reports/ref-visual.md §7.1): short phrases at 6-8 syllables per second separated
by 0.25-0.7 s pauses, silent beats around the lines (the voice now fills about half of the time instead of 79 %),
speaker shots that start 0.25-0.30 s before the first syllable, no cut inside a word, shots that end 0.3-0.7 s after
the last syllable, and the reaction shot (Nox's close-up) that speaks only after his turn.

    LINES   [(id, who, start, duration, text)]            whole lines (captions, who speaks)
    PHRASES {id: [(text, start, end), ...]}               the spoken phrases of each line (lip-sync, word times)
    SHOTS   [(start, end, name)]
    word_times(id) -> [(word, start, end)]
"""
import re

T_END = 21.6

PHRASES = {
    'l01': [("Nox !", 2.40, 2.72),
            ("Pourquoi ma montre fait des lumières vertes", 3.27, 4.95),
            ("à la fin de mon run ?", 5.25, 5.95)],
    'l02': [("Bonsoir à toi aussi, Pico.", 7.35, 8.65),
            ("Entre, fais comme chez toi.", 9.25, 10.45)],
    'l02b': [("Tu portes cette montre depuis deux ans…", 12.37, 14.05),
             ("et tu découvres qu'elle s'allume ?", 14.70, 15.90)],
    'l02c': [("J'ai jamais regardé dessous,", 16.50, 17.55),
             ("ok ?", 17.80, 18.10)],
    'l02d': [("Bon.", 19.07, 19.30),
             ("Laisse-moi t'expliquer.", 19.75, 20.60)],
}
WHO = {'l01': 'pico', 'l02': 'nox', 'l02b': 'nox', 'l02c': 'pico', 'l02d': 'nox'}
LINES = [(lid, WHO[lid], ph[0][1], ph[-1][2] - ph[0][1], ' '.join(p[0] for p in ph)) for lid, ph in PHRASES.items()]
SHOTS = [(0.0, 3.00, 'wide'), (3.00, 6.35, 'medP'), (6.35, 12.05, 'medN'), (12.05, 16.25, 'closeN'), (16.25, 18.80, 'closeP'),
         (18.80, T_END, 'two')]


def _weights(words):
    est = []
    for w in words:
        d = 0.05 + 0.058 * len(re.sub(r'[^\w]', '', w))
        if re.search(r'[.,!?…]$', w):
            d += 0.10
        est.append(d)
    return est


def word_times(line_id):
    """[(word, start, end)] for a line: each phrase's duration shared out among its words by length."""
    out = []
    for text, t0, t1 in PHRASES[line_id]:
        words = text.split()
        est = _weights(words)
        k = (t1 - t0) / sum(est)
        t = t0
        for w, d in zip(words, est):
            out.append((w, t, t + d * k))
            t += d * k
    return out
