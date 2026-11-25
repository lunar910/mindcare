#!/usr/bin/env python3
"""Builds prompts.json (the prompt pack) from shotlist.json.

    python3 build_shotlist.py         first, if the shot list changed
    python3 build_prompts.py          writes prompts.json next to this file and checks it

Nothing is generated and no service is called: this only assembles text.
The spoken lines are taken from shotlist.json and checked against context/ep01_lines.json.

After the voice tests, write the winning set-up into the five PRODUCTION switches below and run this script
again: every clip entry of prompts.json then carries the winning model, medias layout and audio clause.
"""
import json
import os
import re
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTLIST = json.load(open(os.path.join(HERE, "shotlist.json"), encoding="utf-8"))
LINES_FULL = {x["id"]: x for x in json.load(open(os.path.join(HERE, "context", "ep01_lines.json"), encoding="utf-8"))}
LINES = {k: v["text"] for k, v in LINES_FULL.items()}
SHOTS = {s["n"]: s for s in SHOTLIST["shots"]}
SETUPS = {s["id"]: s for s in SHOTLIST["setups"]}
TAKES = OrderedDict((t["id"], t) for t in SHOTLIST["safety_takes"])
SPARES = OrderedDict((s["id"], s) for s in SHOTLIST["spare_stills"])
STYLE_MASTER = SHOTLIST["style_master"]

VIDEO_MAX = 1200          # "under about 1,200 characters"

# --------------------------------------------------------------------------- PRODUCTION switches
# Defaults = what is tested first. Change them to the winner of the voice tests, then run this script again.
MODEL = "seedance_2_5"            # or "seedance_2_0"
LAYOUT = "start_only"             # "start_only": start_image + audio_references
#                                   "start_plus_image_ref": the start image is also attached as image_references
AUDIO_TAG = ""                    # "" = the words "the audio reference"; otherwise the tag the tool wants, e.g. "@Audio1"
AUDIO_SOURCE = "sample"           # "sample": the character's voice sample (voice_nox / voice_pico)
#                                   "line":   the recording of the line itself (tts_lines), if the tests show that works better
#                                   "none":   no audio reference at all (then a voice-change pass follows)
SHORT_LINE_S = None               # set to 4 if the test "4 s against 6 s" shows that short lines are cleaner in a 4 s clip
SHORT_SHOTS = (3, 5, 7, 8, 10)    # lines of 5 to 8 syllables; shot 11 then goes from 6 to 5 s

assert MODEL in ("seedance_2_5", "seedance_2_0") and LAYOUT in ("start_only", "start_plus_image_ref")
assert AUDIO_SOURCE in ("sample", "line", "none") and SHORT_LINE_S in (None, 4)

# --------------------------------------------------------------------------- style

# First sentence of the style block: repeated word for word in every clip prompt.
STYLE_LINE = ("Stylised early-2000s cel-shaded game cutscene: flat colours, hard-edged shading, clean thin dark "
              "outlines, faceted hair, slightly aliased edges, dark night palette with neon-green accents; not "
              "photorealistic.")

STYLE_BLOCK = (STYLE_LINE + " "
               "Shading uses two or three flat tones per surface, with shadows drawn as flat darker shapes and no "
               "smooth gradients; faces are simple and matte, with crisp eyebrows, small eye highlights and no skin "
               "texture. Palette: deep navy, charcoal, olive grey and brick brown, with saturated emerald green, "
               "vivid red, mustard yellow and pale-blue screen glow. Lighting: night interior, soft even frontal light on the characters, "
               "almost no cast shadows, small soft glows round the green bulbs and the screens. Medium detail: many "
               "simplified, readable props, like a low-resolution console render. Sharp focus everywhere; not anime, "
               "not a smooth modern 3D render; no blur, no film grain.")

# --------------------------------------------------------------------------- characters

NOX_LOOK = ("A slim young man of about 22 with light skin and an angular face (straight nose, narrow chin). Blue-black "
            "hair in chunky faceted spikes: a long fringe swept across the forehead, strands down to the cheekbones at "
            "the temples, and one rebel lock sticking up at the crown. Thick dark eyebrows; green eyes behind "
            "thin rectangular dark-wire glasses with pale green-tinted lenses that are fully transparent: both eyes "
            "are always clearly visible through them, with no glare and no reflection. A small dark-grey wireless "
            "earbud in his LEFT ear only (hidden whenever his left side is turned away from the camera). Black "
            "turtleneck under an open anthracite-grey bomber jacket with a ribbed collar and a bright green zip trim "
            "down both front edges. Usually seated, shoulders slightly sloping. Resting face: calm, a faint wry "
            "half-smile, mouth closed.")
NOX_VOICE = ("A young man of about 22: a clear, fairly low, warm voice with a wry, teasing edge and a smile in it. "
             "Lively and brisk, crisp articulation, audible emotion (amused, teasing, eager as soon as he explains), "
             "always at full voice. He is deadpan in the face, never in the voice. Reject a take in which he sounds "
             "slow, flat, hushed, solemn or robotic. Standard French from France, no foreign accent. Series voice to "
             "match: Gemini TTS \"Umbriel\".")
NOX_LOOK_SHORT = ("blue-black spiky hair with a rebel lock on top, thin dark-wire glasses with pale transparent "
                  "green-tinted lenses (both eyes clearly visible through them, no glare or reflection on the "
                  "lenses), black turtleneck, open anthracite bomber jacket with green zip trim")
NOX_TAG = "a young man with spiky blue-black hair and green-tinted glasses"
NOX_VOICE_TAG = "a young man's clear, warm voice with a wry, teasing edge"

PICO_LOOK = ("An athletic young woman of about 20 with warm tan skin and an oval face: brown almond-shaped eyes, strong "
             "dark-red eyebrows, small nose, full lips. Vivid red hair tied in a high ponytail that stands up in a thick "
             "bunch above a GREEN elastic on the crown; forehead clear, long straight strands falling on both "
             "sides of the face to the collarbones. Black over-ear headphones resting round her neck. Loose "
             "mustard-yellow crew-neck sweatshirt with wide sleeves. A chunky black square smartwatch with a small "
             "dark-teal screen on her LEFT wrist: the only watch of the film. Arms held slightly away from the body. "
             "Resting face: lively and sceptical, one eyebrow ready to rise, mouth closed.")
PICO_VOICE = ("A young woman of about 20: a bright, clear, medium-high voice, energetic and spontaneous, quick and "
              "expressive, with quick changes of mood (pressing, stung, sulky, panicked). She answers at once, tit "
              "for tat. Reject a take in which she sounds childish, cute, shouted or slow. Standard French from "
              "France, no foreign accent. Series voice to match: Gemini TTS \"Laomedeia\".")
PICO_LOOK_SHORT = ("red high ponytail tied with a GREEN elastic, long red strands round the face, mustard-yellow "
                   "sweatshirt, black headphones round her neck, black square smartwatch on her LEFT wrist")
PICO_TAG = "a young woman with a red high ponytail and a yellow sweatshirt"
PICO_VOICE_TAG = "a young woman's bright, energetic voice"

# --------------------------------------------------------------------------- room

ROOM = ("ROOM MAP (fixed; draw only what this camera sees). A small electronics workshop at night. The young man sits "
        "behind a cream-topped workbench in the middle of the room, facing the door. BACK WALL, behind him: dark "
        "bookshelves at the top, a string of round glowing green bulbs hanging in a loose curve below them, a "
        "corkboard of blank pinned paper notes, two beige CRT monitors whose screens show a plain pale-blue glow "
        "with two or three blank rectangles, old test equipment. CORNER WINDOW, on his left: two identical tall "
        "multi-pane windows onto a night skyline with small lit windows, one at the left end of the back wall (as "
        "in image 1), one on the side wall at his left. DOOR WALL, facing him about 2.5 m beyond the bench: dark "
        "navy wall, grey door frame, grey door standing open; through it, a hallway with a dark brick wall, a metal "
        "shelf unit topped by a string of tiny green LEDs, a black pendant lamp. Side cameras stand on his right: "
        "from there he is on the left of the frame looking right, the door wall is at the right edge, and the "
        "side-wall window is the background. ON THE BENCH: a soldering station at his right hand (blue-handled "
        "iron, coiled-wire stand); a small green circuit board and a few black chips in the centre; a grey mug of "
        "black coffee at his left hand. There is no watch on the bench: the only watch in the scene is on the "
        "young woman's left wrist.")

# --------------------------------------------------------------------------- image prompts

TASK = ("NEW CAMERA ANGLE. Draw a new frame of the same scene from the camera position given under THIS FRAME. The "
        "reference image{s} give{v} only the character design, the set dressing and the rendering style: do not copy, "
        "crop, mirror or re-frame {its} composition.")
REF_LABEL = {
    "nox_ref": "the young man (his design; seen from the front at his workbench, with the back wall and a window)",
    "pico_ref": "the young woman (her design; seen from the front in a doorway, with a hallway behind her)",
    "deux_etabli": ("the approved side view of this same scene, with both characters at the workbench: it fixes the "
                    "room, the bench props and the poses"),
}
CHAR_NOX = "the young man: " + NOX_LOOK_SHORT
CHAR_PICO = "the young woman: " + PICO_LOOK_SHORT
CHAR_ARM = ("the young woman (only her left forearm is seen): warm tan skin, wide mustard-yellow sleeve, black "
            "square smartwatch on her LEFT wrist")
# Close-ups name only what the frame shows: image models draw what is named.
CHAR_NOX_HEAD = ("the young man: blue-black spiky hair with a rebel lock on top, thin dark-wire glasses with pale "
                 "transparent green-tinted lenses (both eyes clearly visible through them, no glare or reflection "
                 "on the lenses), black turtleneck collar")
CHAR_PICO_HEAD = ("the young woman: red high ponytail tied with a GREEN elastic, long red strands round the face, "
                  "mustard-yellow sweatshirt, black headphones round her neck")
CHAR_PICO_EYES = ("the young woman: warm tan skin, brown almond-shaped eyes, strong dark-red eyebrows, vivid red hair "
                  "with long strands round the face, wide mustard-yellow sleeve, black square smartwatch on her "
                  "LEFT wrist")
CHARS = {"nox": CHAR_NOX, "pico": CHAR_PICO, "arm": CHAR_ARM, "nox_head": CHAR_NOX_HEAD,
         "pico_head": CHAR_PICO_HEAD, "pico_eyes": CHAR_PICO_EYES}
RULES = ("RULES: one still frame, 4:3, as if paused from the cutscene; mouths closed; five fingers on each visible "
         "hand; monitor screens show a plain pale-blue glow with blank rectangles and pinned notes are blank paper, "
         "even where a reference image shows writing; no speech bubble, no interface, no border; no text, no "
         "subtitles, no logo, no watermark")

EARBUD_HIDDEN = "His earbud is in the far ear and is not visible; his visible ear is bare."
ONE_WATCH = "It is the only watch in the frame: there is no watch on the bench."

FRAMES = OrderedDict()
FRAMES["deux_etabli"] = dict(room=True, chars=("nox", "pico"), frame=(
    "THIS FRAME: side-on two-shot across the workbench, both characters waist up. Camera on the young man's "
    "right-hand side of the room, about 2.5 m from the bench, at right angles to the line between him and the door, "
    "lens at his seated eye height. SCREEN-LEFT: the young man seated behind the bench, in right profile, facing "
    "screen-right, bowed over a small green circuit board; his right hand holds the blue-handled soldering iron "
    "still, its tip resting on the board, one thin wisp of smoke. " + EARBUD_HIDDEN + " SCREEN-RIGHT: the young "
    "woman, in left profile, facing screen-left, bent forward over the bench from the visitor side: right forearm "
    "flat on the bench top, left elbow propped on it, left forearm reaching across so that her LEFT wrist, wearing "
    "the black smartwatch, is held about 15 cm in front of his glasses, between his face and the circuit board; "
    "the watch screen is turned toward him and is seen edge-on from here. " + ONE_WATCH + " START POSE: his eyes "
    "are on his work, mouth closed; she stares at him, one eyebrow raised, lips firmly closed. BACKGROUND between "
    "them: the tall night window of the side wall with city lights, the string of green bulbs along the top; "
    "bookshelves and one CRT monitor with a plain pale-blue glow behind him at the left edge; at the far right "
    "edge, the dark navy door wall with the grey door frame seen edge-on. The bench top crosses the lower third: "
    "the grey mug on its far side, the EMPTY coiled-wire soldering stand in the foreground (only one iron exists, "
    "the one in his hand). Both faces and the watch stay above the bottom fifth of the frame."))
FRAMES["nox_tgp"] = dict(room=False, chars=("nox_head",), frame=(
    "THIS FRAME: extreme close-up of the young man's face, from the front, hairline to chin. Camera at his seated "
    "eye height, on the same axis as image 1 but much closer: a new, closer camera position, redrawn, not an "
    "enlargement of image 1. His face fills the frame: the glasses span about two-thirds of the frame width, the "
    "rebel lock is cut by the top edge, the black turtleneck collar sits at the bottom edge, with a little air on "
    "both sides of the face. START POSE: flat deadpan expression, mouth closed, eyes looking just to the right of "
    "the lens, at the young woman, who is off-screen. A small dark-grey wireless earbud in his left ear, on "
    "screen-right. Behind him, dark and simple: dark bookshelves and three glowing green bulbs. He is alone in the "
    "frame. His mouth stays above the bottom fifth of the frame."))
FRAMES["nox_soudure"] = dict(room=True, chars=("nox",), frame=(
    "THIS FRAME: low-angle close-up of the young man at his soldering. Camera resting on the bench top at his "
    "right-hand side (the soldering-station side), about 40 cm from his hands, tilted up about 25 degrees. He is "
    "bowed over his work, body turned three-quarters toward screen-right; because the camera is low, his bowed "
    "face is seen almost from the front and fills the upper two-thirds of the frame. START POSE: eyes lowered, "
    "calm and focused, mouth closed and fully visible. Bottom of the frame: his right hand holds the blue-handled "
    "soldering iron still, its tip resting on a small green circuit board on the bench, one thin wisp of smoke "
    "rising. Only ONE soldering iron exists, the one in his hand; the stand is outside the frame. Beside the board "
    "the bench carries a few black chips and nothing else. " + EARBUD_HIDDEN + " Behind and above him: dark "
    "bookshelves, the string of green bulbs, the plain pale-blue glow of one CRT monitor on the left, a slice of "
    "the night window at the right edge. He is alone in the frame. His mouth and chin stay above the bottom fifth "
    "of the frame."))
FRAMES["ots_nox"] = dict(room=True, chars=("nox", "pico"), frame=(
    "THIS FRAME: over-the-shoulder shot onto the young man, chest up. Camera just behind the young woman's left "
    "shoulder, about 1.3 m high, looking slightly down at him across the bench. RIGHT EDGE of the frame: a dark "
    "foreground silhouette of the young woman seen from behind: her left shoulder in the yellow sweatshirt, the "
    "black headphones on her neck, a few red strands of hair; no part of her face is visible. Her LEFT wrist, "
    "wearing the black smartwatch, is raised into the lower-right third of the frame, below his chin and never in "
    "front of his mouth; the watch screen is turned toward him: the camera sees only the strap and the edge of the "
    "case. " + ONE_WATCH + " CENTRE-LEFT: the seated young man, face in three-quarter view turned toward "
    "screen-right; his hands are out of frame. " + EARBUD_HIDDEN + " START POSE: his head is slightly bowed and "
    "his eyes are lowered onto the watch, mouth closed, a faint smirk. Behind him, the back wall: bookshelves, "
    "green bulbs, the plain pale-blue glow of one CRT monitor; the night window on the right, behind her shoulder. "
    "The bench top and the soldering station are below the frame. His mouth stays above the bottom fifth of the "
    "frame."))
FRAMES["pico_gp"] = dict(room=False, chars=("pico_head",), frame=(
    "THIS FRAME: close-up of the young woman, head and shoulders, in three-quarter front view: a new angle and a "
    "tighter framing than image 1, redrawn, not a crop of it. Camera on the young man's side of the workbench, "
    "slightly to his right, at the eye height of the seated young man. She is leaning forward over the workbench "
    "exactly as in the side view (image 2): shoulders hunched toward the camera, her head at the same height as the seated "
    "young man's; the bench is below the frame. She is framed from just above the green elastic of her ponytail "
    "down to the collarbones; the headphones and the yellow collar sit at the bottom edge, and the frame ends there: "
    "nothing below her shoulders is in the frame. START POSE: her head is turned slightly toward the left edge of the frame and "
    "she looks level toward the left edge of the frame, at the seated young man, who is off-screen; expression "
    "neutral, a little taken aback: eyebrows level, eyes open, mouth closed. Behind her, dark and simple: mostly a "
    "plain dark navy wall; small and far behind her, in the right third of the frame, the open grey doorway with a "
    "glimpse of the brick hallway and its tiny green LEDs. She is alone in the frame. Her chin stays above the "
    "bottom fifth of the frame."))
FRAMES["pico_yeux_montre"] = dict(room=False, chars=("pico_eyes",), frame=(
    "THIS FRAME: extreme close-up at bench height: the young woman peeks at her own watch over her forearm, seen "
    "from the front. Camera resting on the cream bench top on the young man's side, lens a few centimetres above "
    "the surface, horizontal, about 30 cm from the watch. She crouches at the bench so that her chin is level with "
    "the bench top, and peeks over her own forearm. Her LEFT forearm lies flat on the bench top across the middle "
    "of the frame: it enters from screen-right, the loosely closed fist points to screen-left, and the black "
    "smartwatch on her wrist sits in the centre of the frame, seen edge-on: its screen faces the ceiling and is "
    "not visible from this low camera, only the side of the case and the strap. Bright green light leaks from "
    "between the watch case and her skin, onto her wrist and onto the bench top. Just above the forearm, about "
    "10 cm behind the watch: her brown eyes, her eyebrows, her forehead and her red hair, lit green from below; her "
    "nose, mouth and chin are completely hidden behind the forearm. START POSE: eyes narrowed in a sceptical "
    "squint, fixed on the watch. Background dark and simple: a plain dark navy wall and a hint of a grey door "
    "frame. The bench surface fills the bottom fifth of the frame. She is alone in the frame."))

SPARE_FRAMES = OrderedDict()
SPARE_FRAMES["montre_lueur"] = dict(room=False, chars=("arm",), frame=(
    "THIS FRAME: insert close-up of the young woman's forearm and watch on the workbench; there is no face in the "
    "frame. Camera about 40 cm above the cream bench top on the young man's side, looking down at about 30 degrees. "
    "Her LEFT forearm in the mustard-yellow sleeve lies flat on the bench top and enters from screen-right; the "
    "loosely closed fist points to screen-left; the black smartwatch on her wrist sits in the centre of the frame, "
    "seen from the side; its small screen is dark and blank. Bright green light leaks from between the watch case "
    "and her skin, onto her wrist and onto the bench top. Round the arm: the cream bench top, a few black chips, a "
    "small green circuit board at the left edge. START POSE: the arm lies still. Background dark and simple. The "
    "watch stays above the bottom fifth of the frame."))
SPARE_FRAMES["nox_soudure_sans_main"] = dict(room=True, chars=("nox",), frame=(
    FRAMES["nox_soudure"]["frame"]
    .replace("Bottom of the frame: his right hand holds the blue-handled soldering iron still, its tip resting on "
             "a small green circuit board on the bench, one thin wisp of smoke rising. Only ONE soldering iron "
             "exists, the one in his hand; the stand is outside the frame. Beside the board the bench carries a "
             "few black chips and nothing else.",
             "The frame ends at his chest: his hands and the bench are below it; one thin wisp of smoke rises "
             "from the bottom edge.")))
SPARE_FRAMES["ots_nox_sans_bras"] = dict(room=True, chars=("nox", "pico_head"), frame=(
    FRAMES["ots_nox"]["frame"]
    .replace("Her LEFT wrist, wearing the black smartwatch, is raised into the lower-right third of the frame, "
             "below his chin and never in front of his mouth; the watch screen is turned toward him: the camera "
             "sees only the strap and the edge of the case. " + ONE_WATCH,
             "Her arms are below the frame: the foreground holds only her shoulder, the headphones and her "
             "hair.")
    .replace("his eyes are lowered onto the watch", "his eyes are lowered toward her wrist, below the frame")))
assert "The frame ends at his chest" in SPARE_FRAMES["nox_soudure_sans_main"]["frame"]
assert "the foreground holds only her shoulder" in SPARE_FRAMES["ots_nox_sans_bras"]["frame"]
assert "below the frame, mouth closed" in SPARE_FRAMES["ots_nox_sans_bras"]["frame"]


def ref_block(refs):
    """Which image is which, and which one gives the rendering style."""
    items = ["image %d = %s" % (i + 1, REF_LABEL[r]) for i, r in enumerate(refs)]
    head = ("REFERENCES: " if len(refs) > 1 else "REFERENCE: ") + "; ".join(items) + "."
    if "deux_etabli" in refs:
        k = refs.index("deux_etabli") + 1
        style = ("Rendering style: exactly that of image %d (same outline weight, same flat shading, same slightly "
                 "pixelled edges). Image %d also gives the room and the bench props; the camera position of THIS "
                 "FRAME is new." % (k, k))
    else:
        k = refs.index(STYLE_MASTER) + 1 if STYLE_MASTER in refs else 1
        style = ("Rendering style: exactly that of image %d (its outline weight, its flat shading, its slightly "
                 "pixelled edges), for every character and for the whole room." % k)
    return head + " " + style


def image_prompt(frame, refs, compact=False):
    many = len(refs) > 1
    task = TASK.format(s="s" if many else "", v="" if many else "s", its="their" if many else "its")
    chars = [CHARS[c] for c in frame["chars"]]
    char_block = ("CHARACTERS: " if len(chars) > 1 else "CHARACTER: ") + "; ".join(chars) + "."
    parts = [task + " " + ref_block(refs), "STYLE: " + (STYLE_LINE if compact else STYLE_BLOCK), char_block]
    if frame["room"] and not compact:
        parts.append(ROOM)
    parts += [frame["frame"], RULES]
    return "\n\n".join(parts)


CHECK_ALL_STILLS = [
    "A NEW angle: not a copy, crop or mirror of an approved image.",
    "Rendering of the style master: flat shading, clean dark outlines, slightly pixelled edges; no smooth modern 3D, no photo look.",
    "No letter, digit or sign anywhere: screens are a plain pale-blue glow, pinned notes are blank, the watch shows no digits.",
    "Nox: spiky blue-black hair with the rebel lock, thin glasses, BOTH EYES VISIBLE through pale lenses (no opaque green, no mirror glare), black turtleneck, bomber with green zip trim.",
    "Pico: red high ponytail with the GREEN elastic, long strands round the face, yellow sweatshirt, black headphones round her neck.",
    "One watch only in the frame, on her LEFT wrist, never on the bench and never held in her fingers.",
    "Five fingers on each visible hand; no extra arm, no extra object.",
    "Mouths closed. The mouth of whoever will speak is fully visible and above the bottom fifth of the frame (caption zone).",
    "Screen direction: Nox looks toward the right edge, Pico toward the left edge.",
]
CHECK_STILL = {
    "deux_etabli": [
        "Nox on the LEFT in right profile, Pico on the RIGHT in left profile, both waist up, the bench between them.",
        "Her left wrist with the watch about 15 cm in front of his glasses; the watch seen edge-on (no screen toward the camera).",
        "One soldering iron only, in his right hand, tip resting on a small green board; the stand in the foreground is empty.",
        "His eyes on his work; she stares at him with one eyebrow raised; both mouths closed and readable in profile.",
        "His earbud is not visible (it is in the far ear).",
        "Night window behind them, door frame at the far right edge; grey mug on the bench; no watch on the bench.",
        "This still becomes the model of the room, the props and the poses: choose the candidate whose bench and characters you want to see in every other frame.",
    ],
    "nox_tgp": [
        "His face fills the frame, glasses about two-thirds of the width, hairline to chin.",
        "Flat deadpan, mouth closed, eyes just to the right of the lens.",
        "Room for the push-in: glasses and mouth sit inside the central 85 percent of the frame.",
        "Earbud on screen-right (his left ear). Background: bookshelves and green bulbs only.",
    ],
    "nox_soudure": [
        "Low angle from the bench; his bowed face is seen almost from the front; the mouth is fully visible.",
        "One iron only, in his right hand, tip resting on the green board; no stand, no second iron, no watch on the bench.",
        "The hand does not hide the mouth; eyes lowered but visible through the lenses.",
        "Same bench and same props as the approved deux_etabli. He is alone in the frame.",
    ],
    "ots_nox": [
        "At the RIGHT edge: her left shoulder, the headphones, a few red strands; no part of her face.",
        "Her wrist WEARING the watch in the lower-right third, below his chin, never over his mouth; strap and case edge only, no digits.",
        "Nox centre-left, three-quarter face toward the right edge, eyes down on the watch, mouth closed and fully visible.",
        "His hands are out of frame; no watch on the bench; his earbud is not visible.",
    ],
    "pico_gp": [
        "She is LEANING on the bench as in deux_etabli (shoulders hunched, head at Nox's height), not standing in the doorway.",
        "Background: mostly plain dark wall; the doorway small and far in the right third, or absent. If the door frame surrounds her, reject.",
        "Three-quarter front, looking level toward the left edge; neutral face, eyebrows level, mouth closed.",
        "No arm, hand or watch in the frame; green elastic and headphones visible; chin above the caption zone.",
    ],
    "pico_yeux_montre": [
        "Only her eyes, eyebrows, forehead and red hair above the forearm; nose, mouth and chin hidden. A full face above the arm: reject.",
        "The watch is seen edge-on, no screen and no digits; green light leaks from UNDER the case onto her skin and the bench.",
        "The forearm enters from the right; the hand has five fingers; the watch is on the wrist.",
        "Eyes squinting at the watch (not at the camera); the bench fills the bottom fifth of the frame.",
    ],
    "montre_lueur": [
        "No face in the frame. Forearm in the yellow sleeve from the right, watch in the centre, five fingers.",
        "Green light leaks from under the case onto the skin and the bench; the screen is dark, no digits.",
    ],
    "nox_soudure_sans_main": [
        "No hand and no tool in the frame; a thin wisp of smoke rises from the bottom edge.",
        "His bowed face is seen almost from the front; the mouth is fully visible; eyes visible through the lenses.",
    ],
    "ots_nox_sans_bras": [
        "No hand and no watch in the frame; her shoulder, headphones and red strands at the right edge.",
        "Nox looks down toward the lower right, below the frame; mouth closed and fully visible.",
    ],
}

# --------------------------------------------------------------------------- video prompts

HEAD = STYLE_LINE + " Start exactly from the first frame. Locked camera: no zoom, no pan, no cut."
HEAD_PUSH = STYLE_LINE + (" Start exactly from the first frame. Camera: one very slow 12 percent push-in over the "
                          "whole clip; no pan, no cut.")
TAIL = ("Same style and same character{pl} to the end, no morphing. No subtitles, no on-screen text, no music; only "
        "{pron} voice, close and clean, no background sound.")
TAIL_SILENT = "Same style and same character{pl} to the end, no morphing. No subtitles, no on-screen text."
SILENT_BANNED = ("speak", "speech", "voice", "says", "talk", "music", "sound", "word", "silen")


def vc_clause(audio_ref, tag=AUDIO_TAG):
    """The voice-reference clause, removed together with the audio media."""
    if not audio_ref:
        return "in "
    return "with the voice of %s, in " % (tag or "the audio reference")


N, P = NOX_TAG, PICO_TAG
NV, PV = NOX_VOICE_TAG, PICO_VOICE_TAG
SAYS = "he says in French from France, {vc}" + NV
SAYS_P = "she says in French from France, {vc}" + PV
END = "mouth closed and silent, until the end."
SOLDER = ("Low angle from a workbench: " + N + ", bowed over a circuit board; his right hand holds a soldering iron "
          "still, its tip resting on the board, a thin wisp of smoke.")
NOX_FRONT = (N[0].upper() + N[1:] + " sits facing the camera, chest up, alone in frame. The background stays "
             "perfectly still; the monitor screens are frozen.")
PICO_CU = ("Close-up of " + P + ", leaning forward, alone in frame; she looks toward the left edge of the frame "
           "at someone off-screen.")
TWO = ("Side view across a workbench. LEFT: a seated young man in green-tinted glasses, bowed over a circuit board, "
       "a soldering iron held still in his right hand, its tip on the board. RIGHT: a young woman with a red "
       "ponytail leans on the bench, her left wrist, wearing a black smartwatch, raised in front of his glasses, "
       "staring at him")
OTS = ("Over the shoulder of a young woman in a yellow sweatshirt, at the right edge, her left wrist, wearing a "
       "black smartwatch, raised in the lower right: she never moves or speaks. Facing us, a young man in "
       "green-tinted glasses looks down at the watch.")
PICO_DOOR = (P[0].upper() + P[1:] + " stands in an open doorway facing the camera, her left wrist, wearing a black "
             "smartwatch, raised across her chest")

# Each speaking body has exactly one pair of double quotes: the spoken line ({line}). {vc} is the voice-reference clause.
BODIES = {
    1: (PICO_DOOR + "; she has just run in. A very short beat, mouth closed, then " + SAYS_P + ", urgent and "
        "pressing, quick but clearly articulated, out of breath only before the first word: \"{line}\" Naming her "
        "watch, she shakes the raised wrist once toward the camera, eyes on the lens. Then she holds the wrist up "
        "and the stare, " + END),
    2: (SOLDER + " For one full second he stays like that, eyes down, mouth closed. Then, without looking up, "
        "talking to his circuit board, " + SAYS + ", brisk, exaggeratedly polite and mock-offended, a smile "
        "in it: \"{line}\" His face does not react and his eyes never leave the board. Then he stays bowed over "
        "his work, " + END),
    3: (TWO + ", frozen, lips firmly closed for the whole clip. One second of stillness, then ONLY the young man "
        "on the left speaks: he lifts his head a little toward her and says in French from France, {vc}" + NV +
        ", at a brisk pace, with amused, affectionate sarcasm: \"{line}\" Then he holds the look, " + END),
    4: (OTS + " A short beat, mouth closed, then " + SAYS + ", gently mocking, a smile in it, at a brisk pace: \"{line}\" "
        "At the pause he looks up at her over the top of his glasses, toward the right edge of the frame, with "
        "a corner smile, and finishes lightly. Then he holds the amused look, " + END),
    5: (PICO_CU + " A very short beat, mouth closed; then, stung, she snaps back and says in French from France, "
        "{vc}" + PV + ", fast, defensive, a little sulky: \"{line}\" On the last word she lifts her chin and pouts, glaring toward the left edge of "
        "the frame. Then she holds the sulky glare, " + END),
    6: (TWO + " with a sulky glare. Both hold perfectly still, lips closed, for the whole clip; his eyes stay on "
        "the board. The only movement is a thin wisp of smoke rising from the tip of the iron and, at most, one "
        "slow blink."),
    7: (OTS + " A short beat, mouth closed, then " + SAYS + ": \"{line}\" The first word is short and falling, "
        "amused and resigned, said with his eyes still down; then he lifts his head toward her, toward the right "
        "edge of the frame, and the rest brightens, eager, at a brisk pace. Then he holds a small eager smile, " + END),
    8: (NOX_FRONT + " A short beat, mouth closed, then " + SAYS + ", playful and inviting, a grin in it, at full "
        "voice, brisk: \"{line}\" Only after the last word, mouth closed, he pushes his glasses up with one index "
        "finger: one small green glint on the top rim of one lens for a quarter of a second; his eyes stay visible "
        "through the lenses the whole time. The hand drops out of frame and he holds a faint knowing smile until "
        "the end."),
    9: ("Extreme close-up at table height: the brown eyes and forehead of a red-haired young woman peeking over her "
        "own forearm, which lies flat on a workbench; on her wrist a black smartwatch seen edge-on, green light "
        "leaking from under it onto her skin. Her nose and mouth stay hidden behind the arm, and the arm stays "
        "perfectly still. For about three seconds she squints at the watch without moving while its green light "
        "pulses slowly. Then, once, her squint drops and her eyes go round, still fixed on the watch; she freezes "
        "like that until the end."),
    10: (PICO_CU + " Her eyes drop at once to her wrist below the frame; a short beat, mouth closed, then " + SAYS_P +
         ": \"{line}\" The first word is low and stunned, said looking down; on the second word her head jerks up "
         "and her wide eyes snap toward the left edge of the frame; the final question is loud and rising, a "
         "little panicked. Then she holds the shocked look, lips closed and silent, until the end."),
    11: ("Extreme close-up of a young man's face: spiky blue-black hair, thin green-tinted glasses, eyes clearly "
         "visible through the lenses; flat deadpan, gaze just past the lens toward the right edge of the frame. "
         "He stares a full second, mouth closed, with a single blink. Then " + SAYS +
         ", precise and amused, at an easy pace: \"{line}\" A tiny pause after the first sentence, then the last "
         "word placed crisply, with a falling tone, like a full stop. Then one corner of his mouth lifts into a "
         "small smirk, held, " + END),
}

# Extra takes named in the shot list (no extra still needed).
TAKE_BODIES = {
    "2b": (SOLDER + " For one full second he stays like that, eyes down, mouth closed. Then " + SAYS + ", brisk, "
           "exaggeratedly polite and mock-offended, a smile in it: \"{line}\" He says the first sentence to "
           "his circuit board; on the second he glances up toward the right edge of the frame. Then he looks "
           "back down, " + END),
    "4b": (NOX_FRONT + " A short beat, mouth closed, then " + SAYS + ", gently mocking, a smile in it, at a brisk pace: "
           "\"{line}\" As he starts, his eyes drop to something held up below the frame; at the pause in the "
           "middle he looks back up into the camera over the top of his glasses, with a corner smile, and finishes "
           "lightly. Then he holds the amused look, " + END),
    "7b": (SOLDER + " A short beat, mouth closed, then " + SAYS + ": \"{line}\" The first word is short and "
           "falling, amused and resigned, said to his circuit board; then he lifts his head toward the right edge "
           "of the frame, to his friend off-screen, and the rest brightens, eager, at a brisk pace. Then he holds "
           "a small eager smile, " + END),
    "8b": (NOX_FRONT + " His hands stay out of frame for the whole clip. A short beat, mouth closed, then " + SAYS +
           ", playful and inviting, a grin in it, at full voice, brisk: \"{line}\" As he says it he leans very "
           "slightly toward the camera; his eyes stay clearly visible through the lenses. Then he holds a faint "
           "knowing smile, " + END),
    "9b": (OTS + " A short beat, mouth closed, then " + SAYS + ", lively, relishing the story, at full voice: "
           "\"{line}\" A short pause in the middle, then the last three words a little lower and closer, fully "
           "voiced and clearly articulated, with mock mystery. Then he holds a faint smile, " + END),
    "11b": BODIES[11],
}
TAKE_HEAD = {"11b": HEAD_PUSH}
assert list(TAKE_BODIES) == list(TAKES), (list(TAKE_BODIES), list(TAKES))

# Test-only body: Pico's outcry on the approved doorway image (voice test, batch B).
BODY_PICO_DOOR_L04 = (PICO_DOOR + ". A short beat, mouth closed, then " + SAYS_P + ": \"{line}\" The first word is "
                      "low and stunned, said looking down at her watch; on the second word her head jerks up and "
                      "her wide eyes snap back to the camera; the final question is loud and rising, a little "
                      "panicked. Then she holds the shocked look, lips closed and silent, until the end.")

TWO_PEOPLE = ("deux_etabli", "ots_nox")

# Ready-made pronunciation hints. Added to a prompt ONLY if the word is wrong in every take: one sentence, without
# quotation marks, placed right after the closing quote of the line. The line itself is never respelled.
PRON = [
    ("Nox", "[nɔks]: the x is sounded, like the English word knocks",
     "The first word, a name, rhymes with the English word box."),
    ("run", "[ʁœn]: the English word, as French runners say it, with a French r",
     "The last word is the English word run, with a French r."),
    ("Pico", "[piko]: pee-ko", "The name is pronounced pee-ko."),
    ("deux ans", "[dø.zɑ̃]: with the liaison, deu-zan (no ready sentence: a missing liaison is a reason to generate again)", ""),
    ("s'allume", "[salym]", ""),
    ("ok", "[oke]: two syllables, as okay; never spelled out letter by letter, never one closed syllable",
     "The last word is pronounced okay, in two syllables."),
    ("peau", "[po]: one syllable, like the French word pot", "The last word rhymes with beau."),
    ("scanne", "[skan]: one syllable, like the English word scan",
     "The last verb is pronounced like the English word scan."),
    ("t'éclaire", "[teklɛʁ]: tay-clair", "The second word is pronounced tay-clair."),
    ("Nuance", "[nɥɑ̃s]: French, two syllables, nasal vowel, the final s sounded; never the English pronunciation",
     "The last word is French, with a nasal vowel."),
]
assert all('"' not in h for _, _, h in PRON)


def has_word(word, text):
    return re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) is not None


def hints_for(text):
    return [h for w, _, h in PRON if h and has_word(w, text)]


def start_value(setup_id):
    return setup_id          # media key = set-up id (see media_keys)


TAKE_LINE_KEY = {"2b": "02b", "4b": "04", "7b": "07", "8b": "08", "9b": "09", "11b": "11"}


def line_key(key):
    """Key of the recording of the line of a shot or of an extra take (tts_lines)."""
    key = str(key)
    return TAKE_LINE_KEY[key] if key in TAKE_LINE_KEY else "%02d" % int(key)


def audio_value(speaker, key):
    if AUDIO_SOURCE == "line":
        return "line_" + line_key(key)
    return "voice_" + speaker


def medias(setup_id, speaker, audio_ref=True, layout=LAYOUT, audio=None):
    m = [{"role": "start_image", "value": start_value(setup_id)}]
    if speaker != "none" and audio_ref:
        if layout == "start_plus_image_ref":
            m.append({"role": "image_references", "value": start_value(setup_id)})
        m.append({"role": "audio_references", "value": audio or ("voice_" + speaker)})
    return m


def video_prompt(body, line, speaker, setup_id, audio_ref=True, head=HEAD, tag=AUDIO_TAG):
    pl = "s" if setup_id in TWO_PEOPLE else ""
    if speaker == "none":
        return head + " " + body + " " + TAIL_SILENT.format(pl=pl)
    pron = "his" if speaker == "nox" else "her"
    return head + " " + body.format(vc=vc_clause(audio_ref, tag), line=line) + " " + TAIL.format(pron=pron, pl=pl)


def duration_of(key, default):
    if SHORT_LINE_S and key in [str(n) for n in SHORT_SHOTS] + ["7b", "8b"]:
        return SHORT_LINE_S
    if SHORT_LINE_S and key in ("11", "11b"):
        return 5
    return default


def video_entry(key, setup, speaker, line_id, text, duration, body, head=HEAD, purpose=None, required=None,
                silent=False, audio_from=""):
    use_ref = AUDIO_SOURCE != "none"
    e = OrderedDict()
    e["shot_n"] = str(key)
    e["setup_id"] = setup
    e["model"] = MODEL
    e["mode"] = "omni_reference" if MODEL == "seedance_2_5" else None
    e["duration"] = duration_of(str(key), duration)
    e["resolution"] = "720p"
    e["aspect_ratio"] = "4:3"
    e["generate_audio"] = not silent
    e["medias"] = medias(setup, "none" if silent else speaker, audio_ref=use_ref, audio=audio_value(speaker, key))
    e["speaker"] = speaker
    e["line_id"] = line_id
    e["text"] = text
    if required is not None:
        e["required"] = required
    if purpose:
        e["purpose"] = purpose
    if silent:
        e["audio_from"] = audio_from
        e["edit_note"] = ("Generated without sound. In the edit the sound of take %s is laid over this picture "
                          "(montage.py: audio_from)." % audio_from if audio_from else
                          "Generated without sound. Room tone and sound effects are added in the edit.")
        e["prompt"] = video_prompt(body, "", "none", setup, head=head)
    else:
        e["prompt"] = video_prompt(body, text, speaker, setup, audio_ref=use_ref, head=head)
        e["pronunciation_hints"] = hints_for(text)
    return e


# --------------------------------------------------------------------------- voice test

def test_variant(vid, who, setup, line_id, text, body, model, ref, layout="start_only", tag="", duration=6,
                 audio=None, what="", judge=""):
    v = OrderedDict()
    v["id"] = vid
    v["character"] = who
    v["what"] = what
    v["setup_id"] = setup
    v["line_id"] = line_id
    v["text"] = text
    v["model"] = model
    v["mode"] = "omni_reference" if model == "seedance_2_5" else None
    v["audio_reference"] = (audio or ("voice_" + who)) if ref else None
    v["layout"] = layout if ref else "no_audio_reference"
    v["duration"] = duration
    v["resolution"] = "720p"
    v["aspect_ratio"] = "4:3"
    v["generate_audio"] = True
    v["medias"] = medias(setup, who, audio_ref=ref, layout=layout, audio=audio)
    v["prompt"] = video_prompt(body, text, who, setup, audio_ref=ref, tag=tag)
    v["judge"] = judge
    return v


def voice_test():
    name = {"nox": "Nox", "pico": "Pico"}
    cases = [("nox", "4b", "nox_face", "l02b", LINES["l02b"], TAKE_BODIES["4b"]),
             ("pico", "1", "pico_porte", "l01", SHOTS[1]["text"], BODIES[1])]
    batch_a, batch_a2 = [], []
    i = j = 0
    for who, take, setup, line_id, text, body in cases:
        for model in ("seedance_2_5", "seedance_2_0"):
            for ref in (True, False):
                i += 1
                if ref:
                    judge = ("Does the voice sound like the sample voice_%s (same person: age, pitch, grain)? Is "
                             "it the same voice as in the other with-reference clips of %s? Is any word of the "
                             "sample text heard in the clip? Then every point of look_and_listen_all." % (who, name[who]))
                else:
                    judge = ("Control clip: the voice the model invents for %s from the picture and the prompt "
                             "alone. Every with-reference clip of the same model is compared with it. Then every "
                             "point of look_and_listen_all." % name[who])
                v = test_variant("V%d" % i, who, setup, line_id, text, body, model, ref,
                                 what=("with the voice sample, attached the plain way" if ref else "control, no audio reference"),
                                 judge=judge)
                v["take_of"] = take
                batch_a.append(v)
            for tagged in (False, True):
                j += 1
                v = test_variant("W%d" % j, who, setup, line_id, text, body, model, True,
                                 layout="start_plus_image_ref", tag="@Audio1" if tagged else "",
                                 what=("with the voice sample; the start image is ALSO attached as an image reference"
                                       + ("; the prompt names the audio by its tag" if tagged else "")),
                                 judge=("Compare with the V clip of the same model and character (plain attachment) "
                                        "and with its control: is this one closer to the sample voice_%s? If the "
                                        "V clip sounded like the control and this one sounds like the sample, the "
                                        "audio reference only works in this layout." % who))
                v["take_of"] = take
                batch_a2.append(v)

    l03a, l04 = "Regarde de plus près.", LINES["l04"]
    b = []
    b.append(test_variant("B1", "nox", "nox_face", "l02b", LINES["l02b"], TAKE_BODIES["4b"], MODEL, True, layout=LAYOUT, tag=AUDIO_TAG,
                          what="the winning with-reference clip of Nox, repeated unchanged",
                          judge="Same voice as the first one? Two takes of one set-up show how much chance there is."))
    b.append(test_variant("B2", "nox", "nox_face", "l03", l03a, TAKE_BODIES["8b"], MODEL, True, layout=LAYOUT, tag=AUDIO_TAG, duration=4,
                          what="another line with the reference, in a 4 s clip",
                          judge="Same voice as B1 on a different line? Delivery brisk, no word added, no stretched syllables?"))
    b.append(test_variant("B3", "nox", "nox_face", "l03", l03a, TAKE_BODIES["8b"], MODEL, True, layout=LAYOUT, tag=AUDIO_TAG, duration=6,
                          what="the same line with the reference, in a 6 s clip",
                          judge="Compare with B2: is the delivery slower or stretched, are words added to fill the time?"))
    b.append(test_variant("B4", "nox", "nox_face", "l03", l03a, TAKE_BODIES["8b"], MODEL, False, duration=4,
                          what="the same line WITHOUT the reference (control)",
                          judge="Second control for Nox: how far is an invented voice from B1, B2 and the sample?"))
    b.append(test_variant("B5", "nox", "nox_face", "l02b", LINES["l02b"], TAKE_BODIES["4b"], MODEL, True, layout=LAYOUT, tag=AUDIO_TAG,
                          audio="line_04", what="the line itself, recorded with the series voice, as the audio reference",
                          judge="Is the clip's voice the voice of the recording? Does it follow its rhythm and pause? Words and lips still right?"))
    b.append(test_variant("B6", "pico", "pico_porte", "l01", SHOTS[1]["text"], BODIES[1], MODEL, True, layout=LAYOUT, tag=AUDIO_TAG,
                          what="the winning with-reference clip of Pico, repeated unchanged",
                          judge="Same voice as the first one?"))
    b.append(test_variant("B7", "pico", "pico_porte", "l04", l04, BODY_PICO_DOOR_L04, MODEL, True, layout=LAYOUT, tag=AUDIO_TAG, duration=5,
                          what="another line with the reference (test only: the film plays this line on pico_gp)",
                          judge="Same voice as B6 on a loud, panicked line? Not childish, not shouted to clipping?"))
    b.append(test_variant("B8", "pico", "pico_porte", "l04", l04, BODY_PICO_DOOR_L04, MODEL, False, duration=5,
                          what="the same line WITHOUT the reference (control)",
                          judge="Second control for Pico."))
    b.append(test_variant("B9", "pico", "pico_porte", "l01", SHOTS[1]["text"], BODIES[1], MODEL, True, layout=LAYOUT, tag=AUDIO_TAG,
                          audio="line_01", what="the line itself, recorded with the series voice, as the audio reference",
                          judge="Is the clip's voice the voice of the recording? Words and lips still right?"))

    vt = OrderedDict()
    vt["purpose"] = (
        "Answer, before any still or clip of the film is made, the untested questions the whole method rests on: "
        "(1) does an audio reference make the character speak with that voice at all, and in which way must it be "
        "attached; (2) does the voice then hold from clip to clip; (3) how good are the French and the lip-sync, on "
        "seedance_2_5 (mode omni_reference) and on seedance_2_0; (4) is a short line cleaner in a 4 s clip than in "
        "a 6 s clip. Only the two approved images are used. Batches A and A2 (8 jobs each) compare models and ways "
        "of attaching the sample; batch B (9 jobs) is run on the winner. Each character says the line the shot "
        "list chose (l02b on nox_face, spare take 4b; l01 on pico_porte, the real shot 1), so every good clip is "
        "kept for the edit.")
    vt["read_first"] = [
        "Read-only and free, before the first job: the parameter texts of seedance_2_5 and seedance_2_0 in the catalogue.",
        "How are medias addressed in the prompt: by plain words, or by tags such as @Audio1 and @Image1? Write the exact form into AUDIO_TAG if tags are required.",
        "Does a start_image count as the image that an audio reference must be paired with, or must an image_references media be present too?",
        "The exact name and values of the audio switch (generate_audio) and of the duration limits.",
        "Does nano_banana_2_1 offer a 1K size, and how many image references does it accept (three are needed for ots_nox)?",
        "Is the voice-change tool usable during the trial, what does it cost per second, and what does a custom voice made from a sample cost? The trial gives no credits and the balance is 10.",
        "If the texts settle the two attachment questions, skip batch A2. If they leave any doubt, run it.",
    ]
    vt["before"] = [
        "Make the two voice samples from tts_samples (outside Higgsfield, with the validated series voices) and upload them as voice_nox and voice_pico. Each file lasts 11 to 13 s: seedance_2_0 accepts audio references of 2 to 15 s only.",
        "Record line_04 and line_01 from tts_lines (needed by B5 and B9).",
        "Within a batch the clips of one character share the start image, the resolution (720p), the aspect ratio (4:3) and the prompt. Only the model, the audio reference and the way it is attached change.",
        "seedance_2_5: mode omni_reference, the image as start_image. seedance_2_0 has no omni_reference mode: pass start_image and audio_references directly (\"mode\" is null in those variants; if the tool asks for a quality tier, the catalogue showed std and fast: take std).",
        "The tag @Audio1 in the W prompts is a placeholder: use the exact tag form the catalogue gives. If the catalogue shows no tags at all, skip the tagged W clips.",
        "A job refused because an audio reference needs an image reference is an answer too: note it and use the start_plus_image_ref layout everywhere.",
    ]
    vt["batch_A"] = batch_a
    vt["batch_A2"] = batch_a2
    vt["batch_B"] = b
    vt["batch_B_note"] = ("Batch B is written for the current PRODUCTION switches (model %s, layout %s). After "
                          "batches A and A2, set the switches at the top of build_prompts.py to the winner and run "
                          "the script again before launching batch B. Nine jobs: the ninth starts when a slot is "
                          "free." % (MODEL, LAYOUT))
    vt["look_and_listen_all"] = [
        "LISTEN, timbre: with the reference, is it recognisably the voice of the sample? Play the sample, the with-reference clip and the control one after the other.",
        "LISTEN, French: a native speaker from France, no foreign accent; clean u / ou and nasal vowels, French r. Target sounds of the risky words: " + "; ".join("%s %s" % (w, t) for w, t, _ in PRON) + ".",
        "LISTEN, words: exactly the written line; nothing added, dropped, repeated or rephrased; no word taken from the sample text.",
        "LISTEN, delivery: Nox alive, brisk and teasing, with a smile, at full voice (reject slow, flat, hushed, announcer-like or robotic takes); his \"…\" is a short held pause of about 0.3 to 0.5 s, not a slowdown. Pico urgent and pressing, quick but clear (reject childish, cute, shouted or slow takes; reject panting inside the sentence).",
        "LISTEN, sound: no music, no invented sound effect, no reverb, no clipping; the line ends at least 0.5 s before the end of the clip.",
        "LOOK, lips: mouth closed before the first syllable and after the last one; lips close on p, b and m (Pourquoi, ma montre, mon / portes, montre, depuis); no drift at the end of the line; no extra mouthed words.",
        "LOOK, first frame and camera: the clip opens on the start image itself; the camera does not move.",
        "LOOK, character and style: thin glasses with his eyes visible through the lenses, hair shape, earbud in his left ear, watch on her left wrist, five fingers; outlines and flat shading kept for the whole clip (no drift to smooth 3D or photorealism), no morphing.",
        "LOOK, picture: no subtitles and no text appearing; on nox_face the two monitor screens and the pinned notes do not crawl or flicker; no new object.",
        "LOOK, acting: the one beat is played once (Nox: eyes up over his glasses with a corner smile at the pause; Pico: one shake of the watch wrist) and nothing else moves.",
        "MEASURE: python3 montage.py qc <clip> gives a contact sheet and the start and end of the speech of each clip.",
    ]
    vt["decide"] = [
        "Does the reference do anything? For each model and character, compare every with-reference clip (V, and W if run) with the control. Conclude that the reference has no effect ONLY if all the ways of attaching it sound like the control. If one way works and another does not, the working way is the layout of the whole film.",
        "Model: keep the one with correct French and lip-sync first, timbre second. If they are equal, keep seedance_2_5 (the prompt pack is written for it; the same prompts run on seedance_2_0 without the mode).",
        "Write the winner into the PRODUCTION switches of build_prompts.py (MODEL, LAYOUT, AUDIO_TAG) and run it again: every clip entry then carries the winning medias layout.",
        "Does the voice hold? (batch B) Per character, three with-reference clips (the batch A winner, its repeat, another line) against two controls. If the three sound like one person and the controls do not, attach the sample to every speaking clip. If the three differ from each other as much as the controls do, the reference does not lock the voice: go to the next point.",
        "Line as audio (B5, B9): if the clip speaks with the voice of the recording and the words and lips stay right, set AUDIO_SOURCE to line and attach to each clip the recording of its own line (tts_lines). If not, set AUDIO_SOURCE as the tests justify and plan one voice-change pass per character over the chosen takes (same timing, so the lips stay in sync), after checking its cost.",
        "4 s against 6 s (B2, B3): if the 4 s clip is cleaner (brisk delivery, no added word), set SHORT_LINE_S to 4: shots 3, 5, 7, 8, 10 and takes 7b, 8b are then asked 4 s long and shot 11 5 s. The silent beats are added in the edit anyway (hold_start).",
        "If a risky word is mispronounced in every variant, add its ready-made sentence from pronunciation_hints right after the quoted line, without quotation marks, and generate again. Never respell the line itself: the captions and the approved text stay as they are.",
        "If the French is wrong in every variant (accent, swallowed or invented words): stop before making stills. The fallback is the audio-driven route: each line recorded with the series voice, and the clip driven by that recording (B5 and B9 show whether seedance does that; otherwise another tool is needed and that is the owner's decision).",
    ]
    return vt


# --------------------------------------------------------------------------- voice samples

TTS = OrderedDict()
TTS["nox"] = OrderedDict([
    ("text", "Un circuit, tu vois, c'est comme une recette de cuisine : chaque composant a son rôle. On inverse les câbles, et tout s'arrête. Ce n'est pas de la magie : juste un peu de logique… et beaucoup de café."),
    ("target_duration_s", [11, 13]),
    ("voice", "Gemini TTS \"Umbriel\" (validated series voice), through the series' usual voice pipeline; not a Higgsfield job."),
    ("delivery", "A young man of 22 talking to a close friend across his workbench, close to the microphone. Lively and brisk (about 5 syllables per second), wry and teasing with a smile in the voice, crisp consonants, natural rises and falls, at full voice. Short pauses at the punctuation only; the \"…\" before the last words is a half-second tease, then the end is said lightly. The sample colours every clip: it must not be slow, solemn, announcer-like or whispered (directed \"calm\", this voice turns robotic). No laugh, no sigh, no breath noise."),
    ("dir_fr", "Vif, pince-sans-rire, un sourire dans la voix, débit rapide et naturel, à pleine voix, comme s'il taquinait une amie de toujours ; petite pause complice avant « et beaucoup de café ». Surtout pas lent, ni posé, ni solennel."),
    ("file", "voice_nox (suggested file: voice/voice_nox.wav)"),
])
TTS["pico"] = OrderedDict([
    ("text", "Alors moi, ce matin : dix kilomètres au bord de l'eau, sous la pluie, et franchement, c'était génial ! Les jambes en compote, l'estomac dans les talons, mais demain, c'est sûr, on y retourne, avant le lever du soleil. Tu viens avec moi ?"),
    ("target_duration_s", [11, 13]),
    ("voice", "Gemini TTS \"Laomedeia\" (validated series voice), through the series' usual voice pipeline; not a Higgsfield job."),
    ("delivery", "A sporty young woman of 20 telling a friend about her morning, close to the microphone. Bright, energetic, spontaneous and fast (about 6 syllables per second), smiling, with real ups and downs: enthusiasm on the first sentence, a comic complaint on the second, a rising, inviting question at the end. Energetic but not shouted (no clipping), not out of breath (the sample must stay clean), not cute or childish. No laugh, no breath noise."),
    ("dir_fr", "Pleine d'énergie, spontanée, débit rapide, souriante ; enthousiaste sur la première phrase, faussement plaintive sur la deuxième, question finale qui monte, comme une invitation. Sans crier, sans essoufflement."),
    ("file", "voice_pico (suggested file: voice/voice_pico.wav)"),
])
TTS_RULES = [
    "One speaker, speech only: no music, no sound effect, no room reverb, no background noise.",
    "Length 11 to 13 s, never more than 14 s (seedance_2_0 accepts audio references of 2 to 15 s only). The texts are sized for it (about 47 and 58 syllables); if a take still runs long, generate it again faster rather than cut a sentence.",
    "The text is neutral on purpose: everyday words from the character's world, none of the lines of the sketch, no digits, no English word, no proper noun, and most French sounds (nasal vowels, u / ou, eu, oi, ui, r). No sentence opens like a line of the sketch and no group of words sounds like one, so that a clip that continues or echoes its sample is easy to spot.",
    "Mono WAV, 44.1 or 48 kHz, peaks near -3 dBFS, about 0.2 s of silence at the start and at the end. Keep the two files unchanged and attach the same file to every clip of the character.",
    "The delivery of the sample may colour every clip (rhythm and energy are reported to carry over, not only the timbre): choose the liveliest clean take, above all for Nox.",
    "Synthesise each text two or three times and keep one take per character; do not join takes from different requests, the voice can differ slightly between requests.",
]


def tts_lines():
    """The lines themselves, recorded with the series voices: for tests B5 and B9, for the line-as-audio route,
    and for the last fallback (a silent picture with the line laid over)."""
    out = OrderedDict()
    for s in SHOTLIST["shots"]:
        if not s["text"]:
            continue
        who = s["speaker"]
        e = OrderedDict()
        e["shot"] = str(s["n"])
        e["line_id"] = s["line_id"]
        e["text"] = s["text"]
        e["voice"] = "Umbriel" if who == "nox" else "Laomedeia"
        e["approved_direction_fr"] = LINES_FULL[s["line_id"]]["dir"]
        e["file"] = "voice/line_%02d.wav" % s["n"]
        out["line_%02d" % s["n"]] = e
    whole = OrderedDict([("shot", "2b"), ("line_id", "l02"), ("text", LINES["l02"]), ("voice", "Umbriel"),
                         ("approved_direction_fr", LINES_FULL["l02"]["dir"]), ("file", "voice/line_02b.wav")])
    out["line_02b"] = whole
    return out


TTS_LINES_RULES = [
    "Same voices and same pipeline as the samples. Nox is always lively, brisk and at full voice, whatever the approved direction says about calm: the calm is played in his face.",
    "A line split over two shots (l02: shots 2 and 3; l03: shots 8 and 9) is synthesised whole, in one request, then cut at the end of the first sentence: the two halves then share one voice and one energy.",
    "A recording used as an audio reference must last at least 2 s on seedance_2_0: pad the short ones with silence at the end (to about 2.2 s) rather than slow them down.",
    "If the recordings of these lines made for the pixel-art episode exist, listen to them first: any that is lively enough can be reused as it is.",
    "line_09 is the sound of shot 9 if take 9b gives no usable voice: laid over the silent picture, where no mouth is visible.",
]

TAKE_CHECKLIST = [
    "WORDS: exactly the approved line, nothing added, dropped, repeated or rephrased; the risky words sound as listed in pronunciation_hints.",
    "LIPS: closed before the first syllable and after the last; they close on p, b and m; no drift at the end; nobody else's lips move (shot 3: hers must stay shut).",
    "FACE: the same person as in the start image from first to last frame (glasses with visible eyes, hair shape, ponytail and green elastic); no morphing, five fingers.",
    "VOICE: the same voice as the character's reference take (the best clip of the voice tests); Nox alive and at full voice, Pico quick and clear.",
    "TEXT: no subtitle, letter or sign appears anywhere, screens and notes do not crawl.",
    "MUSIC AND NOISE: no music, no invented sound effect, no reverb; silence between the words.",
    "FRAME: opens on the start image, camera locked (except take 11b), flat shading and outlines kept to the end.",
    "TIMING: mouth closed at least 0.2 s before the line and 0.5 s after it, so that the edit can cut cleanly.",
]

# --------------------------------------------------------------------------- assemble


def image_entry(sid, frame, refs, used_by):
    assert not frame["room"] or refs[0] == "nox_ref", sid        # the room map says "as in image 1"
    e = OrderedDict()
    e["setup_id"] = sid
    e["model"] = "nano_banana_2_1"
    e["aspect_ratio"] = "4:3"
    e["resolution"] = "1k"
    e["reference_role"] = "image_references"
    e["references"] = refs
    e["used_by_shots"] = used_by
    e["room_map_in_prompt"] = frame["room"]
    e["checklist"] = CHECK_ALL_STILLS + CHECK_STILL[sid]
    e["prompt"] = image_prompt(frame, refs)
    e["prompt_compact"] = image_prompt(frame, refs, compact=True)
    return e


def build():
    out = OrderedDict()
    out["title"] = SHOTLIST["title"]
    out["version"] = SHOTLIST["version"]
    out["production"] = OrderedDict([
        ("model", MODEL), ("mode", "omni_reference" if MODEL == "seedance_2_5" else None), ("layout", LAYOUT),
        ("audio_tag", AUDIO_TAG), ("audio_source", AUDIO_SOURCE), ("short_line_s", SHORT_LINE_S),
        ("note", "These are the switches at the top of build_prompts.py. They hold the first guess until the voice "
                 "tests are done; set them to the winner and run the script again."),
    ])
    out["style_block"] = STYLE_BLOCK
    out["style_line_video"] = STYLE_LINE
    out["style_master"] = STYLE_MASTER
    out["characters"] = OrderedDict([
        ("nox", OrderedDict([("look", NOX_LOOK), ("voice", NOX_VOICE), ("look_short", NOX_LOOK_SHORT),
                             ("tag_in_clip_prompts", NOX_TAG), ("voice_in_clip_prompts", NOX_VOICE_TAG)])),
        ("pico", OrderedDict([("look", PICO_LOOK), ("voice", PICO_VOICE), ("look_short", PICO_LOOK_SHORT),
                              ("tag_in_clip_prompts", PICO_TAG), ("voice_in_clip_prompts", PICO_VOICE_TAG)])),
    ])
    out["room"] = ROOM
    mk = OrderedDict()
    mk["nox_ref"] = "refs/nox_ref.png: approved image of the young man. Reference image for the new stills."
    mk["pico_ref"] = "refs/pico_ref.png: approved image of the young woman. Reference image for the new stills."
    mk["nox_face"] = ("stills/nox_face.png: start image of set-up nox_face. The top-centre 1000x750 crop of nox_ref "
                      "(made by prep_refs.py, nothing generated): the bench top and its watch are out of the frame.")
    mk["pico_porte"] = ("stills/pico_porte.png: start image of set-up pico_porte. pico_ref saved without "
                        "transparency and trimmed to an exact 4:3, 1192x894 (made by prep_refs.py).")
    for sid in FRAMES:
        mk[sid] = "To make: the approved result of the image prompt %s (file: %s)." % (sid, SETUPS[sid]["start_file"])
    for sid in SPARE_FRAMES:
        mk[sid] = "Spare, made only if needed: the result of the spare image prompt %s (file: stills/%s.png)." % (sid, sid)
    mk["voice_nox"] = "To make: his voice sample, from tts_samples.nox (file: voice/voice_nox.wav)."
    mk["voice_pico"] = "To make: her voice sample, from tts_samples.pico (file: voice/voice_pico.wav)."
    mk["line_NN"] = "To make: the recording of the line of shot NN, from tts_lines (file: voice/line_NN.wav)."
    out["media_keys"] = mk

    out["image_prompts"] = []
    order = sorted(FRAMES, key=lambda s: (SETUPS[s]["make_order"], list(FRAMES).index(s)))
    assert order == list(FRAMES), order                 # FRAMES is written in the order of making
    for sid, f in FRAMES.items():
        assert SETUPS[sid]["start_image"] == "new"
        e = image_entry(sid, f, SETUPS[sid]["references"], [s["n"] for s in SHOTLIST["shots"] if s["setup"] == sid])
        e["make_order"] = SETUPS[sid]["make_order"]
        out["image_prompts"].append(e)
    out["spare_image_prompts"] = []
    for sid, f in SPARE_FRAMES.items():
        e = image_entry(sid, f, SPARES[sid]["references"], [])
        e["replaces"] = SPARES[sid]["replaces"]
        e["when"] = SPARES[sid]["when"]
        out["spare_image_prompts"].append(e)

    out["video_prompts"] = []
    for s in SHOTLIST["shots"]:
        silent = not s["generate_audio"]
        out["video_prompts"].append(video_entry(s["n"], s["setup"], s["speaker"], s["line_id"], s["text"],
                                                s["request_s"], BODIES[s["n"]], silent=silent,
                                                audio_from=s["audio_from"]))
    out["safety_take_prompts"] = []
    for k, t in TAKES.items():
        out["safety_take_prompts"].append(video_entry(k, t["setup"], t["speaker"], t["line_id"], t["text"],
                                                      t["request_s"], TAKE_BODIES[k], head=TAKE_HEAD.get(k, HEAD),
                                                      purpose=t["purpose"], required=t["required"]))
    out["voice_test"] = voice_test()
    out["pronunciation_hints"] = [OrderedDict([("word", w), ("target", t), ("hint_sentence", h),
                                               ("lines", [k for k, v in LINES.items() if has_word(w, v) and k in
                                                          [s["line_id"] for s in SHOTLIST["shots"]]])])
                                  for w, t, h in PRON]
    out["tts_samples"] = OrderedDict([("nox", TTS["nox"]), ("pico", TTS["pico"]), ("rules", TTS_RULES)])
    out["tts_lines"] = OrderedDict([("lines", tts_lines()), ("rules", TTS_LINES_RULES)])
    out["take_checklist"] = TAKE_CHECKLIST
    out["how_to_use"] = [
        "Order of work (the full procedure is runbook.md): before the trial, the voice samples, the line recordings and the two start images made by prep_refs.py; then the voice tests (batches A, A2, B); then the stills in two steps (deux_etabli and nox_tgp first; the four others once deux_etabli is approved, with it as an extra reference); then the clips, three takes of each, in batches of 8; then the edit.",
        "Image prompts: attach the references in the order of \"references\" (image 1, image 2, image 3) with the role image_references, at the 1K size. \"prompt\" is the first choice: it carries the room map for the three frames that show the room and no room map for the three close-ups (image models draw what is named). If the result copies the framing of a reference, generate again; if it still does, move the paragraph that begins THIS FRAME to the top of the prompt. \"prompt_compact\" (one-sentence style, no room map) is for the case where the tool refuses the length of \"prompt\": the length limit of nano_banana_2_1 was not checked.",
        "If the tool refuses three references for ots_nox, drop pico_ref (her face is not in that frame) and renumber: image 1 = nox_ref, image 2 = deux_etabli.",
        "If the watch of nox_ref keeps coming back on the bench of a new still, use nox_face (the crop without the bench) as image 1 instead of nox_ref.",
        "Check every still against its \"checklist\" before any clip is made from it. spare_image_prompts are made only in the cases their \"when\" describes.",
        "Clip prompts: each one contains the first sentence of style_block (style_line_video) word for word. The whole paragraph does not fit in 1,200 characters, and the start image already carries the look.",
        "Each speaking clip prompt holds exactly one pair of double quotes, round the French line. Never add another quoted word: the model may speak it. A pronunciation hint is one unquoted sentence placed right after the closing quote.",
        "The clause \"with the voice of the audio reference,\" goes with the audio_references media: remove both together, never one alone.",
        "Directions in the clip prompts are always given by the edges of the frame (toward the left edge, toward the right edge), never as a bare left or right.",
        "Clips are asked 5 or 6 s long (the minimum is 4 s) and trimmed in the edit. Captions, room tone, music and sound effects are added in the edit: reject any clip that contains text, subtitles or music.",
        "Shots 6 and 9 are generated with generate_audio false and no audio reference; their prompts contain no word about speech or sound. The voice of shot 9 is the sound of take 9b, which is therefore always made.",
        "Shot 11 is generated with a locked camera; the 12 to 15 percent push-in is made in the edit. Take 11b asks the model for the push-in and is only a plan B.",
        "safety_take_prompts are the extra takes named in the shot list (2b, 4b, 7b, 8b, 9b, 11b). They need no extra still. 4b is clip V1 of the voice test; 9b is required.",
        "Check every take against take_checklist. Play shots 2 and 3, then 8 and 9b, back to back: the two halves of a line must sound like one utterance (same pitch, level and energy); otherwise redo the pair, or use take 2b.",
        "Reject a take when a word is added, dropped or changed; when the lips of the listener move (shot 3); when Nox sounds slow, flat or hushed; when Pico sounds childish, cute, shouted or slow; when the style turns smooth or photorealistic; when anything morphs; when text appears.",
    ]
    return out


def check(out):
    # the lines, word for word
    acc = OrderedDict()
    for v in out["video_prompts"]:
        if v["line_id"]:
            acc.setdefault(v["line_id"], []).append(v["text"])
    for k, parts in acc.items():
        assert " ".join(parts) == LINES[k], k
    report = []
    vt = out["voice_test"]
    clips = out["video_prompts"] + out["safety_take_prompts"] + vt["batch_A"] + vt["batch_A2"] + vt["batch_B"]
    for v in clips:
        p = v["prompt"]
        name = v.get("shot_n", v.get("id"))
        assert isinstance(name, str), name
        speaking = v["generate_audio"]
        assert STYLE_LINE in p and "Start exactly from the first frame" in p, name
        assert "\n" not in p and "  " not in p, name
        assert "no morphing" in p and "No subtitles, no on-screen text" in p, name
        assert "Dialogue language" not in p and "room tone" not in p, name
        low = " " + p.lower() + " "
        assert " to the right" not in low and " to the left" not in low, name           # frame edges only
        for banned in ("sing-song", "whisper", "never slow", "not slow", "eyebrow", "holding out", "breath out",
                       "tossed", "dry"):
            assert banned not in low, (name, banned)
        if speaking:
            assert v["text"] and p.count('"') == 2, (name, p.count('"'))
            assert '"%s"' % v["text"] in p, name
            assert v["text"] in LINES[v["line_id"]], name
            assert "says in French from France" in p and "no music; only" in p, name
            assert "mouth closed" in p, name
            has_ref = any(m["role"] == "audio_references" for m in v["medias"])
            assert ("with the voice of" in p) == has_ref, name
            assert "{" not in p and "}" not in p, name
            longest = max([len(h) for h in hints_for(v["text"])] or [0])
            flag = "" if len(p) + longest + 1 <= VIDEO_MAX else "  <-- TOO LONG WITH A HINT"
        else:
            assert p.count('"') == 0 and len(v["medias"]) == 1, name
            assert not any(b in low for b in SILENT_BANNED), (name, [b for b in SILENT_BANNED if b in low])
            flag = ""
        if len(p) > VIDEO_MAX:
            flag = "  <-- TOO LONG"
        report.append("%-5s %5d%s" % (name, len(p), flag))
    assert not any("TOO LONG" in r for r in report), "\n".join(report)
    for e in out["image_prompts"] + out["spare_image_prompts"]:
        p = e["prompt"]
        sid = e["setup_id"]
        assert p.endswith("no text, no subtitles, no logo, no watermark"), sid
        assert e["prompt_compact"].endswith("no text, no subtitles, no logo, no watermark"), sid
        assert p.startswith("NEW CAMERA ANGLE") and STYLE_BLOCK in p, sid
        assert (ROOM in p) == e["room_map_in_prompt"] and ROOM not in e["prompt_compact"], sid
        assert "START POSE" in p and "{" not in p, sid
        assert "wristwatch under repair" not in p and "holds the black smartwatch" not in p, sid
        assert "dark brick at" not in p and "solders" not in p and "soldering in" not in p, sid
        for i in range(len(e["references"])):
            assert "image %d = " % (i + 1) in p, (sid, i)
        assert "image %d = " % (len(e["references"]) + 1) not in p, sid
        assert e["resolution"] == "1k" and e["checklist"], sid
        report.append("%-22s %5d  compact %5d  refs %s" % (sid, len(p), len(e["prompt_compact"]), "+".join(e["references"])))
    assert len(out["image_prompts"]) == sum(1 for s in SHOTLIST["setups"] if s["start_image"] == "new")
    assert [e["setup_id"] for e in out["spare_image_prompts"]] == list(SPARES)
    assert len(out["video_prompts"]) == len(SHOTLIST["shots"])
    assert [v["shot_n"] for v in out["video_prompts"]] == [str(s["n"]) for s in SHOTLIST["shots"]]
    assert [v["setup_id"] for v in out["video_prompts"]] == [s["setup"] for s in SHOTLIST["shots"]]
    assert [v["shot_n"] for v in out["safety_take_prompts"]] == list(TAKES)
    for v, s in zip(out["video_prompts"], SHOTLIST["shots"]):
        assert v["text"] == s["text"] and v["generate_audio"] == s["generate_audio"], s["n"]
    # the voice samples share no opening and no content word with the lines of the sketch
    used = " ".join(s["text"] for s in SHOTLIST["shots"]).lower()
    for who in ("nox", "pico"):
        first = out["tts_samples"][who]["text"].split()[0].lower().strip(",")
        assert all(not s["text"].lower().startswith(first + " ") for s in SHOTLIST["shots"] if s["text"]), (who, first)
        for w in ("montre", "lumière", "peau", "run", "fils", "deux", "bon,", "faim", "j'ai"):
            assert w not in out["tts_samples"][who]["text"].lower().split() and \
                not out["tts_samples"][who]["text"].lower().startswith(w), (who, w)
    return report


if __name__ == "__main__":
    data = build()
    rep = check(data)
    path = os.path.join(HERE, "prompts.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    json.load(open(path, encoding="utf-8"))
    print("\n".join(rep))
    print("style_block", len(STYLE_BLOCK), "| style_line", len(STYLE_LINE), "| room", len(ROOM))
    print("written", path)
