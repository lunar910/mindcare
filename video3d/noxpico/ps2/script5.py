"""Version 5 script: the same lines, staged in the big loft as a PS2-style cutscene of short shots.

Rhythm from the reference (study/reports/ref-visual.md §8): shots of 1.2-3.9 s (mean ~2.5 s), one idea per shot, never
the same size on the same subject twice in a row, locked-off cameras (one slow push-in on the punchline), speaker shots
cut 0.26-0.28 s before the first syllable, reaction/action shots open 0.8-2 s before any word, silences between lines.

Staging: Nox sits at his bench by the window, his back to the room, soldering.  Pico bursts through the door on the far
side of the loft, runs across (the run is cheated across the cut 'door' -> 'nox_work') and stops behind him.  He does not
turn round ("Bonsoir à toi aussi, Pico") until he has put the iron down; then he swivels his stool to face her.

    LINES   [(id, who, start, duration, text)]
    PHRASES {id: [(text, start, end), ...]}
    SHOTS   [(start, end, name)]
    word_times(id) -> [(word, start, end)]
"""
import re

T_END = 24.6

PHRASES = {
    'l01': [("Nox !", 4.30, 4.62),
            ("Pourquoi ma montre fait des lumières vertes", 5.28, 6.96),
            ("à la fin de mon run ?", 7.26, 7.96)],
    'l02': [("Bonsoir à toi aussi, Pico.", 9.98, 11.28),
            ("Entre, fais comme chez toi.", 11.86, 13.06)],
    'l02b': [("Tu portes cette montre depuis deux ans…", 15.28, 16.96),
             ("et tu découvres qu'elle s'allume ?", 17.60, 18.80)],
    'l02c': [("J'ai jamais regardé dessous,", 19.30, 20.35),
             ("ok ?", 20.60, 20.90)],
    'l02d': [("Bon.", 21.97, 22.20),
             ("Laisse-moi t'expliquer.", 22.66, 23.50)],
}
WHO = {'l01': 'pico', 'l02': 'nox', 'l02b': 'nox', 'l02c': 'pico', 'l02d': 'nox'}
LINES = [(lid, WHO[lid], ph[0][1], ph[-1][2] - ph[0][1], ' '.join(p[0] for p in ph)) for lid, ph in PHRASES.items()]

SHOTS = [
    (0.00, 2.40, 'establish'),     # wide: the loft at night, Nox small on the left at his bench in the lamp's pool
    (2.40, 3.12, 'door'),          # the door bangs open, Pico bursts in running
    (3.12, 5.02, 'nox_work'),      # Nox from the window side, soldering, unmoved; Pico arrives behind him, "Nox !"
    (5.02, 8.30, 'pico_ms'),       # Pico medium: the question, wrist raised
    (8.30, 9.72, 'insert_watch'),  # the underside of the watch: green lights pulsing
    (9.72, 13.30, 'nox_cu_work'),  # Nox close, eyes on his board: "Bonsoir à toi aussi, Pico. Entre..."
    (13.30, 14.06, 'pico_react'),  # Pico, miffed by "fais comme chez toi": chin up, a puff (a reaction shot, no words)
    (14.06, 15.02, 'swivel'),      # over Pico's shoulder: he has set the iron down and swivels round to face her
    (15.02, 19.02, 'nox_cu'),      # Nox close, facing her: "Tu portes cette montre..." (slow push-in)
    (19.02, 21.70, 'pico_cu'),     # Pico close: "J'ai jamais regardé dessous, ok ?"
    (21.70, T_END, 'two'),         # side two-shot: "Bon. Laisse-moi t'expliquer." - his hand out, her wrist
]


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

# sound effects (post2.mix_audio): the door sample starts so that its bang lands on the door (chore5.T_DOOR = 2.55),
# the running steps from the moment she bursts in until she stops behind Nox
DOOR_SFX = 2.18
STEPS_SFX = 2.62
