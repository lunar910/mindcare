#!/usr/bin/env python3
"""Writes edit_modele.json, the edit file for montage.py, from shotlist.json.

    python3 build_edit.py                      writes edit_modele.json next to this file
    python3 montage.py build edit_modele.json  once the chosen takes are in clips/

The chosen take of each shot is copied to clips/sNN.mp4 (take 9b to clips/s09b.mp4).
Keys that montage.py does not know are ignored by it: "_a_completer" lists what is still to be added by hand.
Sound files are listed under "sfx" only if they exist today, because montage.py stops on a missing file.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SL = json.load(open(os.path.join(HERE, "shotlist.json"), encoding="utf-8"))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "ep01_tpl", "assets"))      # sounds of the pixel-art episode

TAIL = {8: 1.1, 11: 0.9}       # shot 8 keeps the glasses gesture after the line; shot 11 keeps the smirk
PUSH_IN = {11: 0.13}

shots = []
for s in SL["shots"]:
    n = s["n"]
    e = {"n": n, "clip": "clips/s%02d.mp4" % n}
    if not s["text"]:                                   # shot 6: silent picture
        e["silent_s"] = s["est_s"]
        e["mute"] = True
        shots.append(e)
        continue
    e["caption"] = s["caption"]
    e["lead"] = s["pre_beat_s"]                         # real footage kept before the first word
    e["tail"] = TAIL.get(n, 0.45)
    if s["audio_from"]:                                 # shot 9: silent picture, sound of take 9b
        e["audio_from"] = "clips/s%02db.mp4" % n
        e["in"] = 0.3                                   # picture in-point: set it so that her eyes go round on "dans ta peau"
    if n in PUSH_IN:
        e["push_in"] = PUSH_IN[n]
    shots.append(e)

candidates = [
    {"file": os.path.join(ASSETS, "sfx8", "door.mp3"), "shot": 1, "offset": 0.0, "gain_db": -8},
    {"file": os.path.join(ASSETS, "sfx8", "solder.mp3"), "shot": 2, "offset": 0.0, "gain_db": -16},
    {"file": os.path.join(ASSETS, "sfx8", "footsteps.mp3"), "shot": 2, "offset": 0.1, "gain_db": -10},
    {"file": os.path.join(ASSETS, "sfx8", "solder.mp3"), "shot": 6, "offset": 0.0, "gain_db": -16},
    {"file": os.path.join(ASSETS, "sfx", "sparkle.mp3"), "shot": 8, "offset": 1.6, "gain_db": -12},
]
sfx = [c for c in candidates if os.path.exists(c["file"])]

edit = {
    "size": [960, 720], "fps": 24, "out": "sortie/sketch_v1.mp4", "vertical": True,
    "shots": shots,
    "sfx": sfx,
    "_a_completer": {
        "music": {"file": "son/musique.mp3", "under_voice_db": -16, "enter_s": 0.6, "stop_at_shot": 11,
                  "note": "Rename this key to \"music\" (at the top level) once the file exists. " + SL["music"]},
        "sfx": [
            {"file": "son/ambiance.mp3", "at": 0.0, "gain_db": -30,
             "note": "One continuous, very quiet room tone, at least as long as the film."},
            {"file": "son/fracas.mp3", "shot": 3, "offset": 0.0, "gain_db": -8,
             "note": "Short clatter of components exactly on the cut; trim the footsteps so that they stop on it."},
            {"file": "son/souffle.mp3", "shot": 6, "offset": 0.8, "gain_db": -12,
             "note": "Optional: Nox's short amused breath through the nose, leading into his line of shot 7."},
            {"file": "son/pulsation.mp3", "shot": 9, "offset": 0.0, "gain_db": -18,
             "note": "Optional: soft low electronic pulse with the green light."},
        ],
        "notes": [
            "Shot 6 alternative: replace \"clip\" by \"still\": \"stills/deux_etabli.png\" (the still held 1.3 s).",
            "Shots 2, 3 and 11: \"lead\" keeps real footage before the first word; if the clip speaks earlier than that, add \"hold_start\" for the missing time (it freezes the first frame).",
            "Shot 8: if the glasses gesture is bad, set \"tail\" to 0.45 (the shot is cut right after the line) or use take 8b; move the sparkle sound with \"offset\".",
            "Shot 9: \"in\" is the time in the silent picture where the shot starts; move it until her eyes go round on the last three words.",
            "Shot 10: if the shot opens before her eyes are down, set \"in\" by hand.",
            "A caption written as a list is shown card after card; montage.py changes card in the longest pause of the line.",
        ],
    },
}
with open(os.path.join(HERE, "edit_modele.json"), "w", encoding="utf-8") as fh:
    json.dump(edit, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
print("écrit : edit_modele.json  (%d plans, %d sons déjà disponibles)" % (len(shots), len(sfx)))
