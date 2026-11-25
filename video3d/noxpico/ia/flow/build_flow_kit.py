#!/usr/bin/env python3
"""Builds the Google Flow kit of the sketch « Elle t'éclaire. Nuance. » (Nox & Pico, ep. 1 opening).

    python3 build_flow_kit.py

Reads (never writes) ../shotlist.json, ../shotlist.md, ../context/ep01_lines.json (or ../dialogue_ep01.json) and
etape1_test_flow.txt (step 1, already sent to the owner: never rewritten). Writes, in this folder:
  flow_kit.json               everything, for Claude (cards, shot map, budget, fallbacks)
  etape2_tous_les_plans.txt   the owner's instructions (French), card for card the same as the JSON
  prompts/Gnn.txt             one file per card: its prompt only, ready to copy
  prompts/prise3/Gnn_*.txt    the ready-made third-take prompts (one correction each)
The style sentence, the two character phrases and the voice texts are extracted from
etape1_test_flow.txt, so they stay word for word what the owner already has. The prompts that
step 1 actually sent for G01 and G02 are kept in flow_kit.json (prompt_sent_etape1); their cards
carry corrected prompts, used only if Claude asks for a redo.
Every prompt is checked before anything is written; the written files are read back and compared.
"""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROD = os.path.dirname(HERE)

SHOTLIST = json.load(open(os.path.join(PROD, "shotlist.json"), encoding="utf-8"))
LINES_PATH = next(p for p in (os.path.join(PROD, "context", "ep01_lines.json"), os.path.join(PROD, "dialogue_ep01.json"))
                  if os.path.exists(p))
LINES = {x["id"]: x["text"] for x in json.load(open(LINES_PATH, encoding="utf-8"))}
ETAPE1_TEXT = open(os.path.join(HERE, "etape1_test_flow.txt"), encoding="utf-8").read()
ETAPE1 = ETAPE1_TEXT.split("\n")
SHOTLIST_MD = open(os.path.join(PROD, "shotlist.md"), encoding="utf-8").read().split("\n")


# ---------------------------------------------------------------- étape 1, word for word
def etape1_prompt(marker):
    """Lines of the prompt that follows the 'Ingrédient : ...' line of the given test clip."""
    i = next(k for k, l in enumerate(ETAPE1) if l.startswith(marker))
    j = next(k for k in range(i, len(ETAPE1)) if ETAPE1[k].startswith("Ingrédient :"))
    out = []
    for l in ETAPE1[j + 1:]:
        if l.startswith("──"):
            break
        if l.strip():
            out.append(l)
    return out


def etape1_voice(marker):
    i = next(k for k, l in enumerate(ETAPE1) if l.strip().startswith(marker))
    d = next(k for k in range(i, len(ETAPE1)) if ETAPE1[k].strip() == "Description :")
    t = next(k for k in range(d, len(ETAPE1)) if ETAPE1[k].strip().startswith("Phrase test :"))
    desc = " ".join(l.strip() for l in ETAPE1[d + 1:t])
    phrase = ETAPE1[t].strip()[len("Phrase test :"):].strip()
    head = ETAPE1[i].strip()
    base = head.split("voix de base :")[1].strip()
    return {"name": head.split("nom :")[1].split("—")[0].strip(), "base_voice": base,
            "description": desc, "test_phrase": phrase}


G01_LINES = etape1_prompt("C. CLIP TEST 1")
G02_LINES = etape1_prompt("D. CLIP TEST 2")
G01_SENT = "\n".join(G01_LINES)
G02_SENT = "\n".join(G02_LINES)
STYLE = G01_LINES[0]
assert STYLE == G02_LINES[0], "the two étape 1 prompts must share the style sentence"
assert STYLE.count("as the reference image:") == 1
NOX = G01_LINES[1][: G01_LINES[1].index(")") + 1]
PICO = G02_LINES[1][: G02_LINES[1].index(")") + 1]
NOX_FRONT_SETTING = G01_LINES[1][len(NOX):]          # " sits behind his cluttered ... city lights."
LOCKED = "Locked camera: no zoom, no pan, no cut."
CLOSE_HE_E1 = G01_LINES[-1]
CLOSE_SHE_E1 = G02_LINES[-1]
assert NOX.startswith("The young man from the reference image (")
assert PICO.startswith("The young woman from the reference image (")
assert CLOSE_HE_E1.startswith("Only him on screen") and CLOSE_SHE_E1.startswith("Only her on screen")
VOICES = {"Nox": etape1_voice("VOIX 1"), "Pico": etape1_voice("VOIX 2")}
VOICES["Nox"]["series_voice_if_offered"] = "Umbriel"
VOICES["Pico"]["series_voice_if_offered"] = "Laomedeia"
VOICES["note"] = ("Both voices were created in step 1 and are not re-created. Only if one must be re-created: same "
                  "description; if Flow's list of base voices offers Umbriel and Laomedeia (the series' validated "
                  "Gemini voices), Umbriel for Nox and Laomedeia for Pico.")

# ---------------------------------------------------------------- markers and house sentences
IMG = {"Nox": "[IMAGE NOX]", "Pico": "[IMAGE PICO]"}
VOX = {"Nox": "[VOIX NOX]", "Pico": "[VOIX PICO]"}
ING = {"Nox": "ingredient_nox.png", "Pico": "ingredient_pico.png"}
NOX_B = NOX.replace("from the reference image (", "from the reference image " + IMG["Nox"] + " (", 1)
PICO_B = PICO.replace("from the reference image (", "from the reference image " + IMG["Pico"] + " (", 1)
# two images attached: the style master is named (shot list decision: new frames follow nox_ref)
STYLE_TWO = STYLE.replace("as the reference image:", "as the reference image of the young man:", 1)
# Frames mode (G17): a start image, no reference image
STYLE_START = STYLE.replace("as the reference image:", "as the start image:", 1)

FULL_FRAME = "The picture fills the whole frame: no black bars, no game interface, no dialogue box."
CLOSE_HE = CLOSE_HE_E1 + " " + FULL_FRAME
CLOSE_SHE = CLOSE_SHE_E1 + " " + FULL_FRAME
CLOSE_TWO = ("Only he speaks: her mouth stays closed and still for the whole clip and she never says a word. "
             "No subtitles, no on-screen text, no music: only his voice in a quiet room. " + FULL_FRAME)
CLOSE_OTS = ("Only he speaks; she never moves and never speaks. "
             "No subtitles, no on-screen text, no music: only his voice in a quiet room. " + FULL_FRAME)
CLOSE_SILENT = "Nobody speaks. No subtitles, no on-screen text, no music. " + FULL_FRAME
PROMPT_END = "no dialogue box."
assert FULL_FRAME.endswith(PROMPT_END)

NEW_ANGLE_1 = "New camera angle in the same room, not the composition of the reference image: "
NEW_ANGLE_2 = "New camera angle in the same room, not the composition of the reference images: "
MONITOR = "an old monitor whose screen is a plain pale-blue glow with no windows, icons or writing"
FRONT_STILL = ("The background stays still: the monitor screens show only a plain, still pale-blue glow with no "
               "windows, icons or writing, and the pinned notes are blank.")
PUSH_IN = "Camera: one very slow, steady push-in toward his face over the whole clip; no pan, no cut."

# ---------------------------------------------------------------- approved lines
L = {
    "l01": LINES["l01"],
    "l02a": "Bonsoir à toi aussi, Pico.",
    "l02b_half": "Entre, fais comme chez toi.",
    "l02": LINES["l02"],
    "l02b": LINES["l02b"],
    "l02c": LINES["l02c"],
    "l02d": LINES["l02d"],
    "l03a": "Regarde de plus près.",
    "l03b": "Ta montre envoie de la lumière verte… dans ta peau.",
    "l04": LINES["l04"],
    "l04b": LINES["l04b"],
}
assert L["l02a"] + " " + L["l02b_half"] == LINES["l02"]
assert L["l03a"] + " " + L["l03b"] == LINES["l03"]
SHOT_TEXT = {s["n"]: s["text"] for s in SHOTLIST["shots"]}
assert SHOT_TEXT[2] == L["l02a"] and SHOT_TEXT[3] == L["l02b_half"] and SHOT_TEXT[9] == L["l03b"]
assert SHOT_TEXT[8] == L["l03a"]

# ---------------------------------------------------------------- shared set-ups (one text per camera set-up)
SOLDER_SETUP = [
    NEW_ANGLE_1 + "a low-angle close-up, the camera resting on the bench top near his hands and tilted up at his face, in his workshop at night.",
    NOX_B + " is bowed over his work, his body turned three-quarters toward the right edge of the frame; because the camera is low, his lowered face is seen almost from the front: eyes down behind the clear lenses, mouth fully visible.",
    "At the bottom edge of the frame: only the blue handle of the soldering iron in his hand and a thin wisp of smoke.",
    "Behind and above him: dark bookshelves, a string of glowing green bulbs, " + MONITOR + ". There is no watch anywhere on the bench and no second soldering iron. His face stays in the centre of the frame. " + LOCKED,
]
SOLDER_HANDS_LINE = SOLDER_SETUP[2]
SOLDER_NO_HANDS = "His hands stay below the frame; only a thin wisp of smoke rises from the bottom edge."

OTS_SETUP = [
    NEW_ANGLE_2 + "an over-the-shoulder shot in his workshop at night, from just behind the young woman at her shoulder height, looking slightly down at the young man seated across his workbench.",
    NOX_B + " sits a little to the left of the centre of the frame, chest up, in three-quarter view, facing toward the right edge of the frame, head slightly bowed, eyes on her watch; his hands are below the frame.",
    PICO_B + " is seen from behind, close to the camera: her back, her left shoulder, her headphones and her red ponytail form a large dark foreground shape that covers the right third of the frame and reaches well in toward the centre; her face is never visible. Her left arm comes forward from that shoulder across the bench, the raised forearm and the watch on her wrist turned toward him, just below his chin, never in front of his mouth.",
    "His face and her wrist stay well inside the frame, away from its outer edges. Behind him: dark bookshelves, a string of glowing green bulbs, " + MONITOR + ", a night window with city lights. " + LOCKED,
]

FRONT_SETUP = [
    NOX_B + NOX_FRONT_SETTING,
    "Medium close-up, chest up, at his eye height; the bench top stays below the frame. He faces the camera and stays in the centre of the frame. " + FRONT_STILL + " " + LOCKED,
]

ECU_SETUP = [
    NEW_ANGLE_1 + "a very close shot of his face from the front, at his eye height, in his workshop at night.",
    NOX_B + " sits at his workbench; his face fills the frame from the top of his hair to the collar of his turtleneck, both green eyes clearly visible through the clear lenses, with no glare. Behind him: only dark bookshelves and two or three glowing green bulbs. His face stays in the centre of the frame, his mouth well above the bottom edge. " + LOCKED,
]

PICO_CU_SETUP = [
    NEW_ANGLE_1 + "a close-up inside the workshop at night, at the eye height of someone seated across the workbench from her.",
    PICO_B + " leans forward over the workbench, her shoulders hunched toward the camera, seen three-quarter from the front, framed from the top of her ponytail down to her collarbones: the headphones and the yellow collar at the bottom of the frame, her arms and the watch below the frame.",
    "Behind her, dark and simple: only a plain dark navy wall; no door or door frame anywhere near her. Her face stays in the centre of the frame, her chin well above the bottom edge. " + LOCKED,
]


def P(style, *parts):
    """Prompt = a style sentence, then the given paragraphs, one per line."""
    flat = [style]
    for p in parts:
        flat.extend(p if isinstance(p, list) else [p])
    return "\n".join(flat)


def apply_changes(text, changes):
    for old, new in changes:
        assert text.count(old) == 1, ("change not applicable exactly once", old)
        text = text.replace(old, new)
    return text


# ---------------------------------------------------------------- G01 / G02: corrected prompts for a redo
# The prompts sent in step 1 stay in flow_kit.json (prompt_sent_etape1). These lists are the only differences.
G01_CHANGES = [
    ("The young man from the reference image (", NOX_B[: NOX_B.index("(") + 1]),
    ("Medium close-up, chest up. He faces the camera and stays in the centre of the frame.",
     "Medium close-up, chest up, at his eye height; the bench top stays below the frame. He faces the camera and stays in the centre of the frame. " + FRONT_STILL),
    ("He looks at the camera, amused and teasing, then says in French, with the voice [VOIX NOX]:",
     "After a short beat, mouth closed, his eyes drop to something held up just below the frame, and he says in French, with the voice [VOIX NOX], teasing and gently mocking, at full voice, brisk, with a smile in his voice:"),
    ("He makes a short pause at the dots and raises one eyebrow, then finishes quickly with a mocking smile in his voice.",
     "At the dots he makes a short held pause and looks back up into the camera over the top of his glasses, with a corner smile; then he finishes the question lightly, enjoying it."),
    (CLOSE_HE_E1, CLOSE_HE),
]
G02_CHANGES = [
    ("The young woman from the reference image (", PICO_B[: PICO_B.index("(") + 1]),
    ("urgent and a little breathless but clearly articulated:",
     "urgent and pressing, fast but clearly articulated, out of breath only before the first word, never inside the sentence:"),
    ('On "ma montre" she shakes the wrist once.', "Early in the question, she shakes the wrist once."),
    ("mouth closed, waiting for an answer, until the end.", "mouth closed and silent, until the end."),
    (CLOSE_SHE_E1, CLOSE_SHE),
]
G01_PROMPT = apply_changes(G01_SENT, G01_CHANGES)
G02_PROMPT = apply_changes(G02_SENT, G02_CHANGES)
assert G01_PROMPT.split("\n")[1:3] == FRONT_SETUP, "G01 must use the frontal set-up of G08 word for word"

# ---------------------------------------------------------------- third-take corrections
HINT = {   # pasted by the script at the start of the paragraph that holds the line, never after the quote
    "nox": "In her French line, the first word, a name, rhymes with the English word box.",
    "run": "In her French line, the last word is the English word run, with a French r.",
    "pico": "In his French line, the name is pronounced pee-ko.",
    "ok": "In her French line, the last word is pronounced okay, in two syllables.",
    "peau": "In his French line, the last word is one short syllable that rhymes with the English word toe.",
    "scanne": "In her French line, the last verb is pronounced like the English word scan.",
    "teclaire": "In his French line, the second word is pronounced tay-clair.",
    "nuance": "In his French line, the last word is French, with a nasal vowel.",
}
HINT_WHEN = {
    "nox": "« Nox » mal dit (le x doit s'entendre)",
    "run": "« run » mal dit (le mot anglais, avec un r français)",
    "pico": "« Pico » mal dit (« pi-ko »)",
    "ok": "« ok » mal dit (deux syllabes, « o-ké »)",
    "peau": "« peau » mal dit (comme « pot »)",
    "scanne": "« scanne » mal dit (comme l'anglais « scan »)",
    "teclaire": "« t'éclaire » mal dit (« té-clair »)",
    "nuance": "« Nuance » mal dit (à la française, ni à l'anglaise ni avalé)",
}
GESTE_WHEN = "lèvres décalées, visage qui se déforme ou geste raté"


def T_hint(key):
    return {"key": "aide_" + key, "kind": "hint", "hint": HINT[key], "when_fr": HINT_WHEN[key],
            "what_fr": "phrase d'aide en anglais ajoutée au début du paragraphe de la réplique : " + HINT[key]}


def T_geste(old, new, what_fr):
    return {"key": "geste", "kind": "edit", "old": old, "new": new, "when_fr": GESTE_WHEN,
            "what_fr": what_fr + " ; la voix et les pauses ne changent pas"}


def T_hands():
    return {"key": "sans_main", "kind": "edit", "old": SOLDER_HANDS_LINE, "new": SOLDER_NO_HANDS,
            "when_fr": "le fer ou la main se déforment",
            "what_fr": "les mains et le fer hors du cadre ; seule la fumée monte du bas de l'image"}


def with_hint(prompt, hint):
    lines = prompt.split("\n")
    idx = [i for i, l in enumerate(lines) if '"' in l]
    assert len(idx) == 1
    lines[idx[0]] = hint + " " + lines[idx[0]]
    return "\n".join(lines)


# ---------------------------------------------------------------- the cards
CARDS = []


def card(**k):
    k.setdefault("mode", "Ingredients")
    k.setdefault("model", "Omni Flash 1.2")
    k.setdefault("resolution", "720p")
    k.setdefault("outputs", 1)
    k.setdefault("take3", [])
    k.setdefault("after3", None)
    k.setdefault("notes", [])
    k.setdefault("why", [])
    k.setdefault("start_image", None)
    k["est_credits"] = 10 if k["model"] == "Veo 3.1 Lite" else 3 * k["duration_s"]
    CARDS.append(k)
    return k


OTS_RELAUNCH = [
    "on voit le visage de Pico, ou son épaule ou son poignet bouge ;",
    "au recadrage (le doigt à plat sur le bord droit), son épaule, son casque et sa queue de cheval disparaissent et son bras semble sortir de nulle part ;",
    "la montre se détache, flotte ou cache la bouche de Nox ; des chiffres sur la montre.",
]
SOLDER_RELAUNCH = [
    "une voix marmonnée vers le circuit au lieu d'une voix pleine ;",
    "le fer se tord ou change de longueur, les doigts fondent dans le circuit, la fumée devient du brouillard ;",
    "une montre posée sur l'établi, ou deux fers.",
]
GLASSES_DOWN = "les lunettes : yeux baissés, c'est normal ; pas de reflet blanc qui cache les yeux."
AFTER3_PICO = ("envoie-moi toutes les prises ; si le son de l'une d'elles est bon, je le pose sur une image où sa bouche "
               "ne se voit pas (Nox qui écoute, à la fin de G05 ou de G06), sans rien générer.")

# --- étape 1, already done (cards in the annex; corrected prompts, used only for a redo)
card(id="G01", group="etape1", order=None, shots=[4], ingredients=[ING["Nox"]], voice="Nox", duration_s=8,
     line=LINES["l02b"],
     title="G01 — ESSAI NOX (étape 1, clip test 1) — plan 4 de secours",
     status="DÉJÀ FAIT (clip test 1 de l'étape 1) — à refaire seulement si je te le demande, ou si G05 rate trois fois et que ton G01 ne peut pas servir de plan 4",
     what="Nox de face, à son établi : « Tu portes cette montre depuis deux ans… et tu découvres qu'elle s'allume ? ». Clip étalon de la voix de Nox, et plan 4 de secours.",
     prompt=G01_PROMPT, prompt_sent_etape1=G01_SENT, changes_from_etape1=G01_CHANGES,
     relaunch=[
         "un mot changé, ou « deux ans » sans la liaison (« deu-zan ») ;",
         "un sourcil levé (c'est le geste de Pico) ;",
         "une montre visible à l'image (posée sur l'établi ou ailleurs) ;",
         "des reflets blancs sur les lunettes qui cachent ses yeux.",
     ],
     claude=[
         "la voix : un jeune Parisien vif, taquin, un sourire dans la voix ; jamais lent, monotone ou robotique ;",
         "ses yeux qui descendent vers la montre (sous le cadre), puis remontent vers nous par-dessus les lunettes sur la pause.",
     ],
     take3=[T_geste("At the dots he makes a short held pause and looks back up into the camera over the top of his glasses, with a corner smile; then",
                    "At the dots he makes a short held pause; then", "sans le regard par-dessus les lunettes")],
     after3="envoie-moi les prises.",
     notes=[
         "Ce prompt n'est plus tout à fait celui de l'étape 1 : c'est la version à utiliser si on refait G01 pour le plan 4 (établi hors du cadre, pas de sourcil levé, le regard par-dessus les lunettes sur la pause).",
         "Clip étalon de la voix de Nox : il sert à comparer à l'oreille ; rien à joindre dans Flow.",
     ],
     why=["Step 1 made G01 with a raised eyebrow (Pico's signature) and the bench 'as in the reference', where a dismantled watch lies: that take can serve as shot 4 only without the eyebrow and without a watch on the bench."])

card(id="G02", group="etape1", order=None, shots=[1], ingredients=[ING["Pico"]], voice="Pico", duration_s=8,
     line=LINES["l01"],
     title="G02 — ESSAI PICO (étape 1, clip test 2) — PLAN 1",
     status="DÉJÀ FAIT (clip test 2 de l'étape 1) — c'est le plan 1, l'accroche : je vérifie ton G02 et je te dirai s'il faut le refaire avec ce prompt (trois prises au plus)",
     what="Pico dans l'encadrement de la porte : « Nox ! Pourquoi ma montre fait des lumières vertes à la fin de mon run ? ». Clip étalon de la voix de Pico, et plan 1 du film (l'accroche).",
     prompt=G02_PROMPT, prompt_sent_etape1=G02_SENT, changes_from_etape1=G02_CHANGES,
     relaunch=[
         "un mot changé ; « Nox » avec le x prononcé ; « run » à la française ;",
         "des chiffres ou du texte lisibles sur l'écran de la montre ;",
         "plus d'un mouvement du poignet, ou la montre qui se détache du poignet gauche.",
     ],
     claude=[
         "la voix : une jeune Parisienne rapide et pleine d'énergie, essoufflée avant la phrase mais pas dedans ; ni enfantine, ni criée ;",
         "les lèvres suivent les mots ; une inspiration bouche entrouverte juste avant « Nox ! » est normale ; fermées après le dernier mot ;",
         "une petite lueur verte sous la montre est bienvenue.",
     ],
     take3=[T_hint("nox"), T_hint("run"),
            T_geste("Early in the question, she shakes the wrist once. ", "", "sans le geste du poignet")],
     after3="envoie-moi les prises ; c'est l'accroche, on décide ensemble.",
     notes=[
         "Ce prompt diffère de celui de l'étape 1 sur quelques phrases : le souffle seulement avant la phrase, le geste du poignet sans mot entre guillemets, un silence final sans « attente de réponse », l'image pleine.",
         "Clip étalon de la voix de Pico : il sert à comparer à l'oreille ; rien à joindre dans Flow.",
     ],
     why=["The step-1 prompt quoted \"ma montre\" a second time (quoted words may be spoken) and asked for a breathless delivery inside the line; the approved acting keeps the breath before the first word."])

# --- étape 2, Nox (voice Nox)
card(id="G03", group="base", order=1, shots=[3, 6], ingredients=[ING["Nox"], ING["Pico"]], voice="Nox", duration_s=6,
     line=L["l02b_half"],
     title="G03 — PLANS 3 ET 6 — le plan à deux (voix Nox)",
     status="À FAIRE EN PREMIER",
     what="Le seul plan où l'on voit leurs deux visages, de profil : Nox, juste à gauche du centre, dit « Entre, fais comme chez toi. » ; Pico, juste à droite, vautrée sur l'établi, tend sa montre sous le nez de Nox et le fixe sans bouger ni parler.",
     prompt=P(STYLE_TWO,
              NEW_ANGLE_2 + "a profile two-shot from the side of the room, in his workshop at night, at the eye height of a seated person, waist up: the workbench top crosses the lower third of the frame between them.",
              NOX_B + " sits at the bench just left of the centre of the frame, in profile, facing toward the right edge of the frame, bowed over a small green circuit board; his hand holds a blue-handled soldering iron still, its tip on the board, a thin wisp of smoke rising.",
              PICO_B + " is sprawled across his bench just right of the centre of the frame, making herself at home, in profile, facing toward the left edge of the frame: her right forearm lies flat among his components, her left elbow is planted on the bench and her left wrist is held up a hand's width in front of his glasses, between his face and the circuit board, never in front of his mouth.",
              "They stay close together near the middle of the frame, with only the room on the outer sides. Behind them: a night window with city lights, a string of glowing green bulbs, dark bookshelves, " + MONITOR + ". The only watch in the scene is the one on her wrist. " + LOCKED,
              'For the first two seconds nobody moves: he stays bowed over his circuit board, she stares at him, unimpressed, one eyebrow raised. Then he lifts his head slightly, just enough to look at her over the watch, and says in French, with the voice [VOIX NOX], brisk and lively, at full voice, with warm, amused sarcasm, like an old habit between them: "' + L["l02b_half"] + '" Then he bows his head back over his circuit board; she keeps glaring at him, sulky, lips firmly closed, and both of them hold perfectly still until the end.',
              CLOSE_TWO),
     relaunch=[
         "autre chose que « Entre, fais comme chez toi. » : rien avant, rien après ;",
         "la bouche de Pico bouge, même un peu : c'est le point le plus important de ce clip ;",
         "leurs visages ou leurs vêtements se mélangent ; Nox n'est pas à gauche, tourné vers le bord droit, ou Pico pas à droite, tournée vers le bord gauche ;",
         "la montre n'est pas au poignet de Pico, une montre est posée sur l'établi, ou il y a deux fers.",
     ],
     claude=[
         "le moment immobile du plan 6, au début ou à la fin du clip (s'il n'y en a pas, je tiens une image fixe) ;",
         "la voix vive et amusée, à pleine voix, la même que G01 ;",
         "les lunettes : de profil, on ne voit qu'un œil à travers le verre, c'est normal.",
     ],
     after3="ne fais ni G04 ni G06 ; fais à la place les cartes de secours G13 (plans 2 et 3 en un seul clip) et G14 (plan 7). Le plan 6 disparaît ; le film fait alors environ 30 s.",
     notes=[
         "Dès qu'une prise te paraît bonne, envoie-la-moi tout de suite et continue avec G05 : je te dirai si G03 est bon avant que tu fasses G04 et G06.",
         "Il sert deux plans : le plan 3 (la réplique) et le plan 6 (le face-à-face muet, que je découpe au début ou à la fin du clip, son coupé).",
     ],
     why=["Shot 6 is cut from this clip: 2 s of stillness are asked at the start, and the end shows him back at his board with her sulky glare (the look that ends shot 5), which is the preferred source.",
          "Its success decides plan B (G13 + G14), so G04 and G06 wait for Claude's confirmation."])

card(id="G05", group="base", order=2, shots=[4], ingredients=[ING["Nox"], ING["Pico"]], voice="Nox", duration_s=8,
     line=L["l02b"],
     title="G05 — PLAN 4 — par-dessus l'épaule de Pico (voix Nox)",
     status="À FAIRE",
     what="Par-dessus l'épaule de Pico, de dos, vers Nox assis : « Tu portes cette montre depuis deux ans… et tu découvres qu'elle s'allume ? »",
     prompt=P(STYLE_TWO, OTS_SETUP,
              'After a short beat, mouth closed, he says in French, with the voice [VOIX NOX], teasing and gently mocking, at full voice, brisk, with a smile in his voice: "' + L["l02b"] + '" At the dots he makes a short held pause and lifts only his eyes to her, over the top of his glasses, with a corner smile, his head still bowed; then he finishes the question lightly, enjoying it. Then he holds the amused look, mouth closed, until the end.',
              CLOSE_OTS),
     relaunch=["un mot changé, ou « deux ans » sans la liaison (« deu-zan ») ;"] + OTS_RELAUNCH,
     claude=[
         "la pause des points de suspension : courte, pas un ralentissement ;",
         "sur la pause, seuls ses yeux se lèvent vers elle par-dessus les lunettes, avec un sourire en coin ; pas de sourcil levé (c'est le geste de Pico) ;",
         "la voix vive et taquine, la même que G01.",
     ],
     take3=[T_geste("At the dots he makes a short held pause and lifts only his eyes to her, over the top of his glasses, with a corner smile, his head still bowed; then",
                    "At the dots he makes a short held pause; then", "sans le regard par-dessus les lunettes")],
     after3="envoie-moi les prises. Si ton G01 (déjà fait) n'a ni sourcil levé ni montre posée sur l'établi, il devient le plan 4 : rien à générer ; sinon, refais G01 avec le prompt de sa carte (annexe, 8 s, 24 crédits).",
     notes=["G05 et G07 ont les mêmes images et la même voix : enchaîne-les."])

card(id="G07", group="base", order=3, shots=[9], ingredients=[ING["Nox"], ING["Pico"]], voice="Nox", duration_s=8,
     line=L["l03b"],
     title="G07 — LA VOIX DU PLAN 9 — même cadre que G05 (voix Nox)",
     status="À FAIRE (c'est la voix du plan 9)",
     what="Même cadre que G05 : « Ta montre envoie de la lumière verte… dans ta peau. » Au montage, on garde surtout le son : c'est la voix hors champ de Nox sous l'image de Pico (G12).",
     prompt=P(STYLE_TWO, OTS_SETUP,
              'After a short beat, mouth closed, he says in French, with the voice [VOIX NOX], lively, relishing the story, at full voice: "' + L["l03b"] + '" A short suspense pause at the dots, then the last three words a little lower and closer, with mock mystery, still fully voiced and clearly articulated, never whispered. Then he holds a faint smile, mouth closed, until the end.',
              CLOSE_OTS),
     relaunch=[
         "un mot changé ; « peau » doit sonner comme « pot » ;",
         "« dans ta peau » chuchoté, avalé ou à peine audible ;",
         "de l'écho : c'est ce son qui passera sous le plan 9.",
     ],
     claude=[
         "la pause après « verte… » (je la règle au montage) ;",
         "la voix, la même que G08 : c'est la même réplique coupée en deux ;",
         "l'image : elle ne sert qu'en dernier recours (même cadre que G05).",
     ],
     take3=[T_hint("peau"),
            {"key": "meme_niveau", "kind": "edit",
             "old": "a little lower and closer, with mock mystery, still fully voiced and clearly articulated, never whispered",
             "new": "at the same level, with mock mystery, fully voiced and clearly articulated, never whispered",
             "when_fr": "« dans ta peau » chuchoté, avalé ou à peine audible",
             "what_fr": "les trois derniers mots au même niveau que le reste, jamais chuchotés"}],
     after3="ne coupe jamais la réplique en deux clips. Envoie-moi les trois prises : au plan 9 on ne voit pas la bouche de Nox (on voit les yeux de Pico, G12), je peux donc prendre le début d'une prise et la fin d'une autre, et régler la pause au montage. Si aucune ne va, je t'envoie un prompt corrigé.",
     notes=["C'est la voix du plan 9 : on y voit les yeux de Pico (G12) et on entend Nox hors champ."],
     why=["Making Nox speak off-screen in Pico's clip could give the wrong voice or Pico's mouth speaking: so G12 is silent and the sound comes from here, where Nox is on screen.",
          "If two takes must be combined, Claude joins the two halves into one sound file (pause about 0.5 s) before the edit: montage.py's audio_from takes one file per shot."])

card(id="G08", group="base", order=4, shots=[8], ingredients=[ING["Nox"]], voice="Nox", duration_s=6,
     line=L["l03a"],
     title="G08 — PLAN 8 — Nox de face, le geste des lunettes (voix Nox)",
     status="À FAIRE",
     what="Nox de face : « Regarde de plus près. », puis, juste après la phrase, il remonte ses lunettes d'un doigt (petit reflet vert).",
     prompt=P(STYLE, FRONT_SETUP,
              'After a short beat, mouth closed, he looks into the camera and says in French, with the voice [VOIX NOX], playful and inviting, a grin in his voice, at full voice, brisk: "' + L["l03a"] + '" Right after the last word, within half a second, mouth closed, he pushes his glasses up his nose with one index finger and a small green glint flashes on the rim of one lens; his eyes stay visible through the lenses the whole time. Then his hand drops out of the frame and he holds a faint knowing smile until the end.',
              CLOSE_HE),
     relaunch=[
         "un mot ajouté pour remplir le clip ;",
         "la main arrive pendant la phrase ou cache ses yeux (après deux prises comme ça : carte de secours G15) ;",
         "le doigt déforme les lunettes, ou des reflets blancs cachent ses yeux ;",
         "une montre visible à l'image (posée sur l'établi ou ailleurs) ;",
         "sur les écrans du fond, des lettres lisibles ou qui défilent (des fenêtres floues comme sur l'image de Nox : ça va).",
     ],
     claude=[
         "le geste des lunettes dans la seconde qui suit la phrase : s'il rate APRÈS la phrase, rien à refaire, je coupe juste après « près. » ;",
         "le reflet vert : un bonus (le petit tintement est ajouté au montage) ;",
         "la voix, la même que G07 : écoute G08 puis G07 à la suite, ça doit sonner comme une seule réplique.",
     ],
     after3="si c'est la main (pendant la phrase ou devant ses yeux), passe à G15 dès la deuxième prise ratée pour ça ; pour un autre défaut, envoie-moi les trois prises.",
     why=["The cut into shot 9 lands on the glint: the edit keeps 1.1 s after « près. », so the gesture must start within half a second."])

card(id="G09", group="base", order=5, shots=[11], ingredients=[ING["Nox"]], voice="Nox", duration_s=6,
     line=L["l04b"],
     title="G09 — PLAN 11 — la chute, très gros plan de Nox (voix Nox)",
     status="À FAIRE",
     what="Très gros plan de Nox, la chute du film : environ deux secondes de regard fixe en silence, puis « Elle t'éclaire. Nuance. » et un petit sourire en coin.",
     prompt=P(STYLE, ECU_SETUP,
              'He looks just past the camera, slightly toward the right edge of the frame, at someone off-screen: a flat deadpan for about two seconds, mouth closed, with one slow blink. Then he says in French, with the voice [VOIX NOX], precise and amused, lively, at full voice, at a natural conversational pace, never slow: "' + L["l04b"] + '" A tiny pause after the first sentence, then the last word placed crisply with a falling tone, like a full stop. Then one corner of his mouth lifts into a small smirk, held, mouth closed, until the end.',
              CLOSE_HE),
     relaunch=[
         "un mot changé ; « t'éclaire » doit sonner « té-clair », « Nuance » à la française (ni à l'anglaise, ni avalé, ni en question) ;",
         "une voix lente ou robotique : impassible dans le visage, vivant dans la voix ;",
         "sa bouche coupée par le bas de l'image, ou des reflets blancs sur les lunettes.",
     ],
     claude=[
         "le regard fixe et le clignement avant de parler (s'il parle tout de suite, je fige la première image) ;",
         "la petite pause avant « Nuance. » et la voix qui descend ;",
         "le petit sourire en coin à la fin ;",
         "son regard tourné vers le mauvais bord : je retourne l'image au montage.",
     ],
     take3=[T_hint("teclaire"), T_hint("nuance")],
     after3="envoie-moi les prises ; je t'envoie une variante sur le cadre de G08 (de face, zoom au montage).",
     notes=["Le lent zoom avant (13 %) se fait au montage, d'où la caméra fixe ici. S'il est flou, je te demanderai la carte de secours G16."])

# --- étape 2, Pico (voice Pico)
card(id="G10", group="base", order=6, shots=[5], ingredients=[ING["Pico"]], voice="Pico", duration_s=6,
     line=L["l02c"],
     title="G10 — PLAN 5 — gros plan de Pico (voix Pico)",
     status="À FAIRE",
     what="Gros plan de Pico penchée sur l'établi, qui répond du tac au tac : « J'ai jamais regardé dessous, ok ? »",
     prompt=P(STYLE, PICO_CU_SETUP,
              'She looks level toward the left edge of the frame, at someone seated off-screen. After a very short beat, mouth closed, stung, she snaps back at once and says in French, with the voice [VOIX PICO], her breath back, no panting, fast, defensive, a little sulky: "' + L["l02c"] + '" On the last word she lifts her chin and pouts, glaring toward the left edge of the frame. Then she holds the sulky glare, mouth closed, until the end.',
              CLOSE_SHE),
     relaunch=[
         "un mot changé : « J'ai jamais » (pas « Je n'ai jamais »), « dessous » (dé-sou, pas « dessus »), « ok » en deux syllabes (« o-ké ») ;",
         "elle est dans l'encadrement d'une porte, ou une porte encadre son visage ;",
         "ses bras ou sa montre à l'image ;",
         "une voix enfantine ou criée.",
     ],
     claude=[
         "la réponse du tac au tac, rapide et vexée ;",
         "sur « ok ? », le menton qui se lève et la moue ;",
         "pas d'essoufflement dans la voix (il n'appartient qu'au plan 1) ;",
         "son regard vers le bord gauche de l'image (s'il part vers l'autre bord, je retourne l'image au montage).",
     ],
     take3=[T_hint("ok"),
            T_geste(" On the last word she lifts her chin and pouts, glaring toward the left edge of the frame.", "", "sans la moue")],
     after3=AFTER3_PICO,
     notes=["G10 et G11 ont les mêmes images et la même voix : enchaîne-les."])

card(id="G11", group="base", order=7, shots=[10], ingredients=[ING["Pico"]], voice="Pico", duration_s=6,
     line=L["l04"],
     title="G11 — PLAN 10 — même cadre que G10 (voix Pico)",
     status="À FAIRE",
     what="Même cadre que G10 : son double regard. « Attends… » les yeux baissés sur sa montre, puis la tête qui se redresse d'un coup : « quoi ?! Elle me scanne ?! »",
     prompt=P(STYLE, PICO_CU_SETUP,
              'At the start she looks toward the left edge of the frame, then her eyes drop at once to her own wrist, below the frame. After a short beat, mouth closed, she says in French, with the voice [VOIX PICO], her breath back, no panting, spontaneous and quick: "' + L["l04"] + '" The first word is low and stunned, eyes down; on the second word her head jerks up and her wide eyes snap toward the left edge of the frame; the last question rises, louder, with a touch of panic, without shouting. Then she holds the shocked face, mouth closed, until the end.',
              CLOSE_SHE),
     relaunch=[
         "un mot changé ; « scanne » doit sonner comme l'anglais « scan » ;",
         "elle est dans l'encadrement d'une porte ;",
         "un cri saturé.",
     ],
     claude=[
         "« Attends… » bas, les yeux baissés ; sur « quoi ?! », la tête qui se redresse d'un coup, les yeux écarquillés vers le bord gauche (s'ils partent vers l'autre bord, je retourne l'image) ;",
         "la fin qui monte, sans cri ;",
         "pas d'essoufflement dans la voix ; la même voix que G02 et G10.",
     ],
     take3=[T_hint("scanne"),
            T_geste("eyes down; on the second word her head jerks up and her wide eyes snap toward the left edge of the frame;", "then", "sans le mouvement de tête")],
     after3=AFTER3_PICO,
     notes=["Au montage, le plan commence quand ses yeux sont déjà baissés."],
     why=["Never split this line into two clips: the model would pad such short clips with invented words."])

# --- étape 2, silent
card(id="G12", group="base", order=8, shots=[9], ingredients=[ING["Pico"]], voice="none", duration_s=6,
     line=None,
     title="G12 — IMAGE DU PLAN 9 — muet, sans voix",
     status="À FAIRE",
     what="Très gros plan muet au ras de l'établi : les yeux de Pico juste au-dessus de sa montre, la lumière verte sur sa peau. On y entendra la voix de Nox de G07.",
     prompt=P(STYLE,
              NEW_ANGLE_1 + "an extreme close-up at the height of the workbench top, in the workshop at night, the camera resting on the bench and looking straight across it.",
              PICO_B + " crouches behind the bench so that only her eyes, eyebrows, forehead and red hair show above her own left forearm, which lies flat on the bench across the middle of the frame, coming in from the right edge of the frame, the hand loosely closed.",
              "The black smartwatch on her wrist sits in the centre of the frame, seen edge-on, its screen facing up and not visible; bright green light leaks from under the watch onto her skin and onto the bench, and lights her eyes from below. Her nose, mouth and chin stay hidden behind her forearm for the whole clip. Her neck and her headphones stay below the bench, out of sight.",
              "The bench top fills the bottom of the frame. Behind her: a plain dark navy wall. Her eyes and the watch stay in the centre of the frame. " + LOCKED,
              "For about three seconds she squints at the watch, sceptical, without moving, while its green light pulses slowly. Then, once, her squint drops and her eyes go wide and round, still fixed on the watch; she freezes like that until the end. Her forearm never moves and her eyes never look at the camera.",
              CLOSE_SILENT),
     relaunch=[
         "on voit son nez, sa bouche ou son menton au-dessus du bras (il ne doit rester que ses yeux, ses sourcils, son front et ses cheveux) ;",
         "un écran ou des chiffres sur la montre ;",
         "l'avant-bras bouge, la main se déforme, ou la montre se détache du poignet ;",
         "ses yeux regardent la caméra.",
     ],
     claude=[
         "le moment où ses yeux s'arrondissent (je le cale sur « dans ta peau ») ;",
         "la lumière verte sur sa peau ;",
         "le son de ce clip ne compte pas : je mets celui de G07.",
     ],
     after3="carte de secours G18 (l'insert de la montre) ; en dernier recours, l'image et le son de G07.",
     why=["No other clip shows this frame, and it is the image of the subject (the green light on the skin). Veo 3.1 Lite would need a start image we do not have. 6 s rather than 4: the edit picks the moment her eyes go round so that it falls on « dans ta peau »."])

# --- étape 2, Nox, after Claude has confirmed G03
card(id="G04", group="base", order=9, shots=[2], ingredients=[ING["Nox"]], voice="Nox", duration_s=6,
     line=L["l02a"],
     title="G04 — PLAN 2 — Nox à sa soudure, vu d'en bas (voix Nox)",
     status="À FAIRE quand je t'ai confirmé que G03 est bon (si G03 rate, c'est G13 qui le remplace)",
     what="Gros plan en contre-plongée, caméra posée sur l'établi : Nox penché sur sa soudure ne réagit pas pendant une seconde et demie, puis dit « Bonsoir à toi aussi, Pico. » sans lever les yeux.",
     prompt=P(STYLE, SOLDER_SETUP,
              'For about a second and a half he does not react: eyes on his work, mouth closed. Then, without looking up, talking to his circuit board, he says in French, with the voice [VOIX NOX], brisk, at full voice, wry, exaggeratedly polite and mock-offended, with a smile in his voice: "' + L["l02a"] + '" His face does not react and his eyes never leave his work. Then he keeps working, mouth closed, until the end.',
              CLOSE_HE),
     relaunch=[
         "autre chose que « Bonsoir à toi aussi, Pico. » : rien avant, rien après (s'il enchaîne « Entre, fais comme chez toi. », c'est à refaire) ; « Pico » doit sonner « pi-ko » ;",
         "il lève les yeux, ou sa bouche est cachée ;",
     ] + SOLDER_RELAUNCH,
     claude=[
         "la seconde et demie sans réaction avant la phrase (s'il parle tout de suite, je fige la première image au montage) ;",
         "son visage qui ne réagit pas : c'est la blague ;",
         "la voix, la même que G03 : écoute G04 puis G03 à la suite, ça doit sonner comme une seule phrase ;",
         GLASSES_DOWN,
     ],
     take3=[T_hint("pico"), T_hands()],
     after3="carte de secours G13 (je n'en garderai que la première phrase pour le plan 2).")

card(id="G06", group="base", order=10, shots=[7], ingredients=[ING["Nox"], ING["Pico"]], voice="Nox", duration_s=6,
     line=L["l02d"],
     title="G06 — PLAN 7 — même cadre que G05 (voix Nox)",
     status="À FAIRE quand je t'ai confirmé que G03 est bon (si G03 rate, c'est G14 qui le remplace)",
     what="Même cadre que G05 : « Bon. Laisse-moi t'expliquer. » Il rend les armes, puis s'éclaire : il adore expliquer.",
     prompt=P(STYLE_TWO, OTS_SETUP,
              'After a short beat, mouth closed, eyes still on the watch, he says in French, with the voice [VOIX NOX], lively, at full voice: "' + L["l02d"] + '" The first word is short and falling, amused and resigned, eyes still down; then he lifts his whole head toward her, toward the right edge of the frame, and the rest brightens, eager and brisk: he loves explaining. Then he holds a small eager smile, mouth closed, until the end.',
              CLOSE_OTS),
     relaunch=["un mot changé ou ajouté ;"] + OTS_RELAUNCH,
     claude=[
         "« Bon. » court et qui retombe, puis la suite plus gaie ;",
         "après « Bon. », toute la tête qui se relève vers elle ;",
         "même décor et même voix que G05 : les deux plans doivent se ressembler.",
     ],
     take3=[T_geste("eyes still down; then he lifts his whole head toward her, toward the right edge of the frame, and the rest",
                    "then the rest", "sans le mouvement de tête")],
     after3="carte de secours G14.",
     notes=["Si je te dis qu'on enlève le plan 6 au montage, fais G14 à la place."])

# --- secours (only when a card says so or Claude asks)
card(id="G13", group="secours", order=None, shots=[2, 3], ingredients=[ING["Nox"]], voice="Nox", duration_s=8,
     line=L["l02"],
     title="G13 — SECOURS des plans 2 et 3 (voix Nox)",
     status="SECOURS — si G03 rate trois fois (il remplace alors les plans 2 et 3), ou si G04 rate trois fois (je n'en garde que la première phrase)",
     what="Toute la réplique « Bonsoir à toi aussi, Pico. Entre, fais comme chez toi. » sur le gros plan de la soudure (le cadre de G04).",
     prompt=P(STYLE, SOLDER_SETUP,
              'For about a second and a half he does not react: eyes on his work, mouth closed. Then he says in French, with the voice [VOIX NOX], brisk, at full voice, wry, exaggeratedly polite and mock-offended, with a smile in his voice: "' + L["l02"] + '" He says the first sentence to his circuit board without looking up; on the second he glances up toward the right edge of the frame, with warm, amused sarcasm. Then he looks back down at his work, mouth closed, until the end.',
              CLOSE_HE),
     relaunch=[
         "un mot changé ou ajouté ; « Pico » doit sonner « pi-ko » ;",
         "il lève les yeux pendant la première phrase ;",
     ] + SOLDER_RELAUNCH,
     claude=[
         "la seconde et demie sans réaction ;",
         "sur la seconde phrase, le regard qui se lève vers le bord droit ;",
         "la voix, la même que G01 ;",
         GLASSES_DOWN,
     ],
     take3=[T_hint("pico"), T_hands(),
            T_geste("on the second he glances up toward the right edge of the frame, with", "the second with", "sans le regard levé")],
     after3="envoie-moi les prises.",
     notes=["Avec G13, le plan 6 disparaît et le plan 7 passe sur G14 : le film fait alors environ 30 s."])

card(id="G14", group="secours", order=None, shots=[7], ingredients=[ING["Nox"]], voice="Nox", duration_s=6,
     line=L["l02d"],
     title="G14 — SECOURS du plan 7 (voix Nox)",
     status="SECOURS — si G03 a raté trois fois (avec G13), si G06 rate trois fois, ou si je te dis qu'on enlève le plan 6",
     what="« Bon. Laisse-moi t'expliquer. » sur le gros plan de la soudure (le cadre de G04).",
     prompt=P(STYLE, SOLDER_SETUP,
              'After a short beat, mouth closed, he says in French, with the voice [VOIX NOX], lively, at full voice: "' + L["l02d"] + '" The first word is short and falling, amused and resigned, said to his circuit board; then he lifts his head toward the right edge of the frame, to his friend off-screen, and the rest brightens, eager and brisk. Then he holds a small eager smile, mouth closed, until the end.',
              CLOSE_HE),
     relaunch=["un mot changé ou ajouté ;"] + SOLDER_RELAUNCH[1:],
     claude=[
         "« Bon. » court et qui retombe ;",
         "la tête qui se relève vers le bord droit après « Bon. » ;",
         "la voix, la même que G04 (ou G13) ;",
         GLASSES_DOWN,
     ],
     take3=[T_hands(),
            T_geste("then he lifts his head toward the right edge of the frame, to his friend off-screen, and the rest",
                    "then the rest", "sans le mouvement de tête")],
     after3="envoie-moi les prises.")

card(id="G15", group="secours", order=None, shots=[8], ingredients=[ING["Nox"]], voice="Nox", duration_s=6,
     line=L["l03a"],
     title="G15 — SECOURS du plan 8, sans la main (voix Nox)",
     status="SECOURS — si, sur deux prises de G08, la main arrive pendant la phrase ou cache ses yeux",
     what="« Regarde de plus près. » sans le geste des lunettes : il se penche à peine vers nous.",
     prompt=P(STYLE, FRONT_SETUP,
              'His hands stay below the frame for the whole clip. After a short beat, mouth closed, he looks into the camera and says in French, with the voice [VOIX NOX], playful and inviting, a grin in his voice, at full voice, brisk: "' + L["l03a"] + '" As he says it, he leans very slightly toward the camera; his eyes stay clearly visible through the lenses. Then he holds a faint knowing smile, mouth closed, until the end.',
              CLOSE_HE),
     relaunch=[
         "un mot ajouté ;",
         "une main à l'image ;",
         "sur les écrans du fond, des lettres lisibles ou qui défilent (des fenêtres floues : ça va).",
     ],
     claude=["il se penche à peine vers nous ;", "la voix, la même que G07."],
     after3="envoie-moi les prises.",
     notes=["Le reflet des lunettes devient alors un simple son au montage."])

card(id="G16", group="secours", order=None, shots=[11], ingredients=[ING["Nox"]], voice="Nox", duration_s=6,
     line=L["l04b"],
     title="G16 — SECOURS du plan 11, avec zoom de Flow (voix Nox)",
     status="SECOURS — si je te dis que le zoom fait au montage sur G09 est flou",
     what="La chute de G09, avec le lent zoom avant fait par Flow au lieu du montage.",
     prompt=P(STYLE, [ECU_SETUP[0], ECU_SETUP[1].replace(LOCKED, PUSH_IN)],
              'He looks just past the camera, slightly toward the right edge of the frame, at someone off-screen: a flat deadpan for about two seconds, mouth closed, with one slow blink. Then he says in French, with the voice [VOIX NOX], precise and amused, lively, at full voice, at a natural conversational pace, never slow: "' + L["l04b"] + '" A tiny pause after the first sentence, then the last word placed crisply with a falling tone, like a full stop. Then one corner of his mouth lifts into a small smirk, held, mouth closed, until the end.',
              CLOSE_HE),
     relaunch=[
         "tout ce qui fait relancer G09 ;",
         "un zoom qui saute ou s'arrête, ou un visage qui devient flou.",
     ],
     claude=["tout ce que je vérifie sur G09 (s'il regarde vers le mauvais bord, je retourne l'image)."],
     take3=[T_hint("teclaire"), T_hint("nuance")],
     after3="envoie-moi les prises.")

card(id="G17", group="secours", order=None, shots=[6], mode="Frames", model="Veo 3.1 Lite", ingredients=[],
     start_image="G03_plan6.png", voice="none", duration_s=4, line=None,
     title="G17 — SECOURS muet du plan 6 (Veo 3.1 Lite, mode Frames)",
     status="SECOURS — seulement si je te le demande (si G03 n'a aucun moment immobile pour le plan 6 et que son image fixe paraît trop figée)",
     what="Le face-à-face muet du plan 6, animé à partir d'une image de G03 que je t'envoie (G03_plan6.png).",
     prompt=P(STYLE_START,
              "Continue exactly from the start image, a profile two-shot at his workbench at night; nothing in the frame changes.",
              "The young man in the start image stays bowed over his circuit board, eyes down, mouth closed.",
              "The young woman in the start image stays sprawled over the bench, her left wrist held up in front of his glasses, keeping exactly the expression she has in the start image, mouth closed.",
              "Both hold perfectly still; the only movement is the thin wisp of smoke rising from the soldering iron and, at most, one slow blink. " + LOCKED,
              CLOSE_SILENT),
     relaunch=[
         "une bouche qui s'ouvre ;",
         "un visage, une place ou une montre qui changent par rapport à l'image de départ.",
     ],
     claude=["rien ne bouge sauf la fumée (un clignement au plus) ;", "le son ne compte pas : je le coupe."],
     after3="envoie-moi les prises.",
     why=["Exception to the default model: the shot is silent, so it needs neither a voice nor Ingredients mode; Veo 3.1 Lite in Frames mode costs 10 credits and starts from a real frame of G03 (same faces, same room). Its resolution setting is assumed to be 720p."])

card(id="G18", group="secours", order=None, shots=[9], ingredients=[ING["Pico"]], voice="none", duration_s=6,
     line=None,
     title="G18 — SECOURS muet du plan 9 — insert de la montre",
     status="SECOURS — si G12 rate trois fois",
     what="L'avant-bras de Pico posé sur l'établi, la montre au centre, la lumière verte qui pulse ; aucun visage.",
     prompt=P(STYLE,
              NEW_ANGLE_1 + "an insert at the height of the workbench top, in the workshop at night.",
              "Only the left forearm of the young woman from the reference image " + IMG["Pico"] + " is in the frame, in her mustard-yellow sleeve, with her black smartwatch on the wrist: it lies flat on the cream workbench across the middle of the frame, coming in from the right edge of the frame, the hand loosely closed. No face, no hair, nothing else of her in the frame.",
              "The black smartwatch sits in the centre of the frame, its screen facing up and not visible; bright green light pulses slowly from under the watch onto her skin and onto the bench. The forearm never moves. " + LOCKED,
              CLOSE_SILENT),
     relaunch=[
         "un visage, des cheveux ou un corps à l'image ;",
         "un écran ou des chiffres sur la montre ;",
         "l'avant-bras bouge, la main se déforme, ou la montre se détache.",
     ],
     claude=["la lumière verte qui pulse sous la montre ;", "le son ne compte pas : je mets celui de G07."],
     after3="envoie-moi les prises ; en dernier recours, je prends l'image et le son de G07.",
     notes=["On perd ses yeux qui s'arrondissent : sa réaction passe alors au plan 10."],
     why=["6 s, like G12: shot 9 lasts the G07 line plus 0.85 s and its picture starts near 0.3 s; with 4 s, a slow take of G07 would freeze the last frame. Omni Flash rather than Veo 3.1 Lite: the ingredient keeps the style, the yellow sleeve and the watch."])

CARDS.sort(key=lambda c: c["id"])   # defined in working order above; listed by id everywhere else
BY_ID = {c["id"]: c for c in CARDS}
ORDER =[c["id"] for c in sorted((c for c in CARDS if c["group"] == "base"), key=lambda c: c["order"])]
WAIT_FOR_G03 = ["G04", "G06"]
ETAPE1_IDS = [c["id"] for c in CARDS if c["group"] == "etape1"]
SECOURS_IDS = [c["id"] for c in CARDS if c["group"] == "secours"]

for c in CARDS:
    c["prompt_file"] = f"prompts/{c['id']}.txt"
    for t in c["take3"]:
        if t["kind"] == "hint":
            t["prompt"] = with_hint(c["prompt"], t["hint"])
        else:
            assert c["prompt"].count(t["old"]) == 1, (c["id"], t["key"])
            t["prompt"] = c["prompt"].replace(t["old"], t["new"])
        t["file"] = f"prompts/prise3/{c['id']}_{t['key']}.txt"

# ---------------------------------------------------------------- common checks, rules
COMMON_RELAUNCH = [
    "un mot de la réplique est changé, ajouté ou manquant, ou la réplique est coupée avant la fin ;",
    "la mauvaise personne parle, ou la bouche de l'autre personnage bouge ;",
    "la voix n'est clairement pas la bonne (autre personne, accent étranger) : vérifie d'abord que c'est bien la VOIX, et pas l'image, qui a été choisie au @ ;",
    "des lettres lisibles, des chiffres ou des sous-titres apparaissent (les petites fenêtres floues sur les écrans du fond, comme sur l'image de Nox, sont acceptées) ;",
    "de la musique ;",
    "des bandes noires en haut ou en bas, une interface de jeu ou une boîte de dialogue ;",
    "un visage, une coiffure ou des vêtements qui ne sont pas les leurs, ou qui changent pendant le clip ;",
    "une main ou une montre qui flotte ou se déforme, des doigts en trop ;",
    "le cadre : je recadre en 4:3 au montage et un huitième de la largeur part de chaque côté. Mets la vidéo en plein écran, cache le bord gauche puis le bord droit avec un doigt à plat : si un visage, la montre ou une main qui joue disparaît sous ton doigt, relance.",
]
COMMON_CLAUDE = [
    "le débit, la longueur des pauses et les gestes ;",
    "le silence avant et après la réplique, et les lèvres pendant ces silences ;",
    "la voix pareille d'un clip à l'autre ;",
    "un léger bruit de fond ;",
    "un regard tourné vers le mauvais bord (pour certains plans, je retourne l'image au montage).",
]
HESITATE = "Tu hésites sur une prise ? Ne relance pas : garde-la, passe à la carte suivante et envoie-la-moi."
RETAKE_RULE = ("Trois prises au plus par carte. Prise 1 : le prompt tel quel. Prise 2 : le même prompt (le hasard joue beaucoup). "
               "Prise 3 : la correction que la carte donne pour ce défaut (un fichier du dossier prompts/prise3, ou une durée "
               "changée, voir la section C), sinon le même prompt. Si la prise 3 rate aussi : fais ce que dit la ligne "
               "« Après trois prises ratées » de la carte, puis passe à la carte suivante et envoie-moi les trois prises. "
               "Jamais de prise 4 sans mon accord. Seule exception : G08 passe à G15 dès la deuxième prise où la main arrive "
               "pendant la phrase.")
SESSION = [
    "Ouvre le projet de l'étape 1 (« Nox et Pico ep01 ») : les deux images et les deux voix y sont.",
    "Vérifie les réglages : Vidéo → Ingredients (Ingrédients), modèle Omni Flash 1.2, format 16:9 (paysage), qualité 720p, 1 résultat par demande. Seule exception : la carte de secours G17. Jamais d'essai en 360p : une bonne prise en 360p ne se refait pas à l'identique en 720p.",
    "Note ton solde de crédits (là où Flow les affiche, souvent dans le menu de ton compte) au début et à la fin de la séance.",
    "Si tu peux, travaille sur un ordinateur ; sur téléphone, coupe la correction automatique du clavier avant de toucher à un prompt.",
]
STEPS = [
    "a) Vide la zone de texte et enlève les images et la voix restées de la carte d'avant (la petite croix sur chacune).",
    "b) Règle la durée de la carte (si Flow ne propose pas cette valeur, prends la plus proche au-dessus).",
    "c) Copie le prompt : ouvre le fichier de la carte dans le dossier prompts (par exemple prompts/G03.txt) puis Tout sélectionner et Copier ; ou copie tout ce qui est entre les lignes ▼ et ▲ de la carte, sans ces deux lignes. Colle-le dans la zone de texte et vérifie qu'il se termine bien par « " + PROMPT_END + " » (sinon, recolle).",
    "d) Remplace chaque repère entre crochets : efface-le, tape @ et choisis l'élément :",
    "   [IMAGE NOX] → l'image ingredient_nox (le garçon à lunettes devant ses écrans) ;",
    "   [IMAGE PICO] → l'image ingredient_pico (la rousse dans l'encadrement de la porte) ;",
    "   [VOIX NOX] → la VOIX Nox (une voix : pas l'image ingredient_nox, qui peut apparaître dans la même liste) ;",
    "   [VOIX PICO] → la VOIX Pico (pas l'image ingredient_pico).",
    "   Si le @ ne propose pas une image, ajoute-la d'abord comme à l'étape 1, puis tape @ à nouveau. Si le @ ne propose pas une voix, ajoute-la avec Add → Voices et écris Nox (ou Pico) à la place du repère.",
    "e) Vérifie : plus aucun crochet [ ] dans le texte ; seules les images de la carte sont jointes ; une seule voix (aucune pour G12, G17 et G18) ; aucun mot de la réplique en français n'a changé.",
    "f) Vérifie le prix affiché : celui de la carte (12 crédits pour 4 s, 18 pour 6 s, 24 pour 8 s, 30 pour 10 s ; G17 : 10). Deux ou quatre fois plus : Flow va faire plusieurs vidéos, remets 1 résultat par demande. Trois fois moins (4, 6, 8 ou 10) : c'est la qualité 360p, remets 720p. Un autre prix : ne lance pas et dis-moi ce que tu vois.",
    "g) Lance. Dès que le clip est prêt, avant la carte suivante : télécharge-le en MP4, taille d'origine (720p ; pas de GIF, pas d'agrandissement « upscale » ou 1080p) et renomme-le tout de suite (G03.mp4, puis G03_prise2.mp4, G03_prise3.mp4). Ne supprime aucune prise dans Flow.",
]

# ---------------------------------------------------------------- shots map
SFX_FR = {}
in_table = False
for row in SHOTLIST_MD:
    if row.startswith("| N° | Jeu de celui qui parle"):
        in_table = True
        continue
    if in_table:
        if not row.startswith("|"):
            break
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if cells and cells[0].isdigit():
            SFX_FR[int(cells[0])] = cells[4]
assert len(SFX_FR) == 11, SFX_FR

G03_LEN = BY_ID["G03"]["duration_s"]
SHOT_GEN = {
    1: dict(gens=["G02"], part="G02 : de 0,15 s avant « Nox ! » à 0,45 s après « run ? » (montage.py cale la coupe sur la parole).",
            edit={"clip": "G02.mp4", "lead": 0.15, "tail": 0.45},
            fallback="Pas de plan de secours : c'est l'accroche. Si le G02 de l'étape 1 ne va pas, G02 refait avec le prompt de sa carte (trois prises au plus)."),
    2: dict(gens=["G04"], part="G04 : 1 s avant « Bonsoir » (si le clip parle trop tôt, la première image est figée le temps qui manque, réglage hold_start) jusqu'à 0,45 s après « Pico. ».",
            edit={"clip": "G04.mp4", "lead": 1.0, "tail": 0.45},
            fallback="Si G03 rate : G13 remplace les plans 2 et 3, avec deux cartons de sous-titres. Si seul G04 rate : la première phrase de G13."),
    3: dict(gens=["G03"], part="G03 : de 0,9 s avant « Entre » (le tableau immobile) à 0,45 s après « toi. ».",
            edit={"clip": "G03.mp4", "lead": 0.9, "tail": 0.45},
            fallback="Si G03 rate : plans 2 et 3 sur G13, plan 6 retiré, plan 7 sur G14."),
    4: dict(gens=["G05", "G01"], part="G05 : de 0,25 s avant « Tu » à 0,45 s après « s'allume ? ». Secours : G01, même découpe.",
            edit={"clip": "G05.mp4", "lead": 0.25, "tail": 0.45},
            fallback="G01 (déjà fait) seulement si Nox n'y lève pas le sourcil et si aucune montre n'est posée sur l'établi ; sinon G01 refait avec le prompt de sa carte."),
    5: dict(gens=["G10"], part="G10 : de 0,15 s avant « J'ai » à 0,45 s après « ok ? ».",
            edit={"clip": "G10.mp4", "lead": 0.15, "tail": 0.45},
            fallback="Le son d'une prise ratée à l'image se pose sur Nox qui écoute (fin de G05 ou de G06), où sa bouche à elle ne se voit pas. Prise bonne mais à l'envers : image retournée (hflip)."),
    6: dict(gens=["G03"], part=f"G03 réutilisé, son coupé, rien à générer : 1,3 s où tout est immobile, de préférence à la fin du clip (il est revenu à son circuit, elle le fusille du regard : réglage edit, in = durée du clip − 1,4, out = durée − 0,1), sinon de 0,0 à 1,3 s, avant qu'il relève la tête (edit_alt) ; sinon une image fixe extraite de G03, tenue 1,3 s (réglage still). Écrire in et out (avec in seul, montage.py garde silent_s à partir de in).",
            edit={"clip": "G03.mp4", "in": round(G03_LEN - 1.4, 2), "out": round(G03_LEN - 0.1, 2), "mute": True},
            edit_alt={"clip": "G03.mp4", "in": 0.0, "out": 1.3, "mute": True},
            fallback="Image fixe de G03 tenue 1,3 s ; dernier recours G17 (Veo 3.1 Lite, 10 crédits). Si le plan 6 est retiré, le plan 7 passe sur G14."),
    7: dict(gens=["G06"], part="G06 : de 0,25 s avant « Bon. » à 0,45 s après « t'expliquer. ».",
            edit={"clip": "G06.mp4", "lead": 0.25, "tail": 0.45},
            fallback="G14 (gros plan de la soudure), aussi quand le plan 6 est retiré."),
    8: dict(gens=["G08"], part="G08 : de 0,25 s avant « Regarde » à 1,1 s après « près. » (le geste des lunettes ; la coupe tombe sur le reflet). Si le geste rate : 0,45 s après « près. ».",
            edit={"clip": "G08.mp4", "lead": 0.25, "tail": 1.1},
            fallback="G15 (sans la main) si la main gêne pendant la phrase."),
    9: dict(gens=["G12", "G07"], part="Image : G12, son coupé, à partir de « in » (vers 0,3 s, à régler pour que ses yeux s'arrondissent sur « dans ta peau »). Son : G07, de 0,4 s avant « Ta » à 0,45 s après « peau. ». Si le son doit venir de deux prises de G07, je les colle d'abord en un seul fichier (montage.py ne prend qu'un fichier son par plan).",
            edit={"clip": "G12.mp4", "audio_from": "G07.mp4", "in": 0.3, "lead": 0.4, "tail": 0.45},
            fallback="Image G18 (insert de la montre, 6 s) avec le même son ; dernier recours : G07 image et son."),
    10: dict(gens=["G11"], part="G11 : à partir du moment où ses yeux sont déjà baissés (réglage in, à la main), jusqu'à 0,45 s après « scanne ?! ».",
             edit={"clip": "G11.mp4", "lead": 0.3, "tail": 0.45},
             fallback="Le son d'une prise ratée à l'image se pose sur Nox qui écoute (fin de G05 ou de G06). Prise bonne mais à l'envers : image retournée (hflip)."),
    11: dict(gens=["G09"], part="G09 : de 1,2 s avant « Elle » (le regard fixe) à 0,9 s après « Nuance. » (le petit sourire) ; lent zoom avant de 13 % fait au montage.",
             edit={"clip": "G09.mp4", "lead": 1.2, "tail": 0.9, "push_in": 0.13},
             fallback="G16 (zoom fait par Flow ; alors pas de zoom au montage) si le zoom du montage est flou ; si G09 rate trois fois, une variante sur le cadre de G08. Prise bonne mais à l'envers : image retournée (hflip)."),
}

SHOTS_MAP = []
for s in SHOTLIST["shots"]:
    g = SHOT_GEN[s["n"]]
    m = {"shot": s["n"], "setup": s["setup"], "speaker": s["speaker"], "line_id": s["line_id"], "text": s["text"],
         "generations": g["gens"], "clip_part": g["part"], "captions": s["caption"], "sfx": s["sfx"], "sfx_fr": SFX_FR[s["n"]],
         "edit": g["edit"]}
    if "edit_alt" in g:
        m["edit_alt"] = g["edit_alt"]
    m["fallback"] = g["fallback"]
    SHOTS_MAP.append(m)

EDIT_NOTES = [
    "Shot 6 (muted reuse of G03): give both \"in\" and \"out\" (with \"in\" alone, montage.py keeps \"silent_s\" seconds from \"in\", default 1.6).",
    "Mirrored takes (G09, G10, G11, G16 only: no watch, text or hand side in frame) can be flipped with montage.py's \"hflip\": true on that shot. Never flip G02, G03, G05-G07, G12 or G18 (the watch would move to her right wrist) nor the soldering shots (the iron would change hands).",
    "Shot 9: when the sound must come from two takes of G07, join the two halves into one file first (about 0.5 s of pause before « dans ta peau »): audio_from takes a single file.",
    "Clip lengths: \"in\"/\"out\" values assume the requested duration; Flow's files can be a few hundredths longer or shorter, and montage.py clamps to the real length.",
]

# ---------------------------------------------------------------- budget
cost = lambda ids: sum(BY_ID[i]["est_credits"] for i in ids)
e1 = cost(ETAPE1_IDS)
e2 = cost(ORDER)
sec = cost(SECOURS_IDS)
e2_speaking = [i for i in ORDER if BY_ID[i]["voice"] != "none"]
e2_silent = [i for i in ORDER if BY_ID[i]["voice"] == "none"]
speak_real = cost(e2_speaking) * 1.5
silent_real = cost(e2_silent) * 2
provision = sec // 2
assert speak_real == int(speak_real)
e2_real = int(speak_real) + silent_real + provision
cap3 = 3 * e2
STOP = int(round((e2_real + 100) / 50.0) * 50)
BUDGET = {
    "rates": {
        "Omni Flash 1.2, 720p": "about 3 credits per second: 4 s = 12, 6 s = 18, 8 s = 24, 10 s = 30",
        "Omni Flash 1.2, 360p": "1 credit per second: never used (a good 360p take cannot be reproduced at 720p)",
        "Veo 3.1 Lite": "10 credits per clip of 4-8 s, Frames or text, silent clips only (only in secours card G17)",
        "note": "Flow shows the exact cost before each generation; these figures are the ones given for November 2026.",
    },
    "allowance": {"monthly_credits": 1000, "daily_free_credits": 50},
    "etape1_already_spent": {i: BY_ID[i]["est_credits"] for i in ETAPE1_IDS} | {"total": e1},
    "etape2_one_take_each": {i: BY_ID[i]["est_credits"] for i in ORDER} | {"total": e2},
    "secours_one_take_each": {i: BY_ID[i]["est_credits"] for i in SECOURS_IDS} | {"total": sec},
    "etape2_realistic": {
        "assumptions": [
            f"1.5 takes per speaking clip of step 2 ({len(e2_speaking)} clips, {cost(e2_speaking)} credits for one take of each): {int(speak_real)}",
            f"2 takes of the silent clip G12, the hardest framing: {silent_real}",
            f"provision for one or two secours cards, half of their total: {provision}",
        ],
        "total": e2_real,
        "with_etape1": e2_real + e1,
        "left_of_monthly_after_both": 1000 - e2_real - e1,
    },
    "etape2_three_takes_of_every_card": cap3,
    "stop_rule_credits_for_etape2": STOP,
    "plan_b_difference": f"G13 + G14 instead of G04 + G06: {cost(['G13', 'G14']) - cost(['G04', 'G06']):+d} credits per take",
    "not_included": "A redo of G01 or G02, only if Claude asks (24 credits per take, three takes at most).",
    "daily_free_note": "The 50 free credits of each day pay for about two clips; whether Flow spends them before the monthly credits is not known.",
}

# ---------------------------------------------------------------- general fallbacks (section C)
FALLBACKS = [
    {"when": "Règle des prises.", "do": RETAKE_RULE.replace(", voir la section C)", ", voir ci-dessous)")},
    {"when": "Tu hésites sur une prise.", "do": "Ne relance pas : garde-la, passe à la carte suivante et envoie-la-moi."},
    {"when": "Flow affiche une erreur et ne donne pas de vidéo.",
     "do": "Relance une fois (si aucun crédit n'a été pris, ça ne compte pas comme une prise) ; si l'erreur revient, envoie-moi une capture du message et dis-moi si des crédits ont été pris."},
    {"when": "La voix n'est pas la bonne.",
     "do": "Vérifie que le repère [VOIX …] a été remplacé par la VOIX, pas par l'image ingredient_…, puis relance. Une prise bonne à l'image mais pas à la voix : garde-la et dis-le-moi."},
    {"when": "Un mot est mal prononcé.",
     "do": "Prise 3 : le fichier « aide » de la carte (le même prompt, avec une phrase d'aide en anglais au début du paragraphe de la réplique). Ne change jamais l'orthographe de la réplique."},
    {"when": "Des mots sont ajoutés, le débit traîne, ou la fin du clip part en vrille.",
     "do": "Prise 3 : le même prompt avec 2 s de moins (8 → 6, 6 → 4). Sauf G03, G08, G09, G12 et G16 : garde leur durée (le moment immobile du plan 6, le geste des lunettes, le regard fixe et la pause, les yeux qui s'arrondissent en ont besoin)."},
    {"when": "La réplique est coupée avant la fin, ou le clip s'arrête juste sur le dernier mot.",
     "do": "Prise suivante avec 2 s de plus (6 → 8, 8 → 10). N'utilise jamais « Extend » (Prolonger) ni « Add to scene »."},
    {"when": "Lèvres décalées, visage qui se déforme ou geste raté.",
     "do": "Prise 3 : le fichier « geste » de la carte s'il y en a un (il enlève seulement le geste, jamais la voix ni les pauses) ; sinon le même prompt."},
    {"when": "Flow recopie l'image ingrédient (Pico dans la porte, Nox de face comme sur son image) au lieu du cadre demandé.",
     "do": "Relance ; si ça revient, arrête cette carte et envoie-moi les prises."},
    {"when": "Plan à deux (G03, G05, G06, G07) : leurs visages ou leurs vêtements se mélangent.",
     "do": "Vérifie que [IMAGE NOX] a bien été remplacé par l'image de Nox et [IMAGE PICO] par celle de Pico, puis relance ; si ça revient, envoie-moi les prises."},
    {"when": "Du texte, des chiffres ou de faux sous-titres (écran, montre, mur).",
     "do": "Relance ; si ça revient, envoie-moi le clip : j'adapte la phrase du décor. Les petites fenêtres floues des écrans du fond, comme sur l'image de Nox, sont acceptées."},
    {"when": "De la musique sous la voix.",
     "do": "Relance : une musique sous la voix ne s'enlève pas au montage. Si elle revient aux trois prises, envoie-les-moi."},
    {"when": "Des bandes noires en haut ou en bas, une interface de jeu ou une boîte de dialogue.", "do": "Relance."},
    {"when": "Flow refuse le prompt ou le coupe (trop long).",
     "do": "Supprime la phrase du décor, celle qui commence par « Behind », puis relance. G01, G02, G08, G15, G17 et G18 n'en ont pas : envoie-moi le message de Flow."},
    {"when": "Pico essoufflée sur G10 ou G11 à chaque prise.",
     "do": "Dis-le-moi : on verra s'il faut retirer « sometimes a little out of breath after running » de la description de la voix Pico (et revérifier G02)."},
    {"when": "Une voix doit être recréée (elle a disparu, ou je te le demande).",
     "do": "Reprends la description de l'étape 1. Si la liste des voix de base de Flow propose « Umbriel » et « Laomedeia » (les voix validées de la série), prends Umbriel pour Nox et Laomedeia pour Pico ; sinon, comme à l'étape 1."},
    {"when": "Le français est mauvais sur tous les clips (accent étranger, mots inventés).",
     "do": "Arrête-toi et dis-le-moi avant de dépenser plus."},
    {"when": "Les crédits fondent.",
     "do": f"Règle d'arrêt : si cette étape a pris plus de {STOP} crédits (ton solde de départ moins ton solde actuel), arrête-toi et envoie-moi ce que tu as ; on choisit ensemble les reprises."},
]

# ---------------------------------------------------------------- checks
problems = []
ALLOWED_DIR = re.compile(
    r"\b(?:left|right) (?:edge|half|part|third) of the frame\b|\b(?:left|right) of the centre of the frame\b|"
    r"\b(?:her|his|the) (?:own )?(?:raised )?(?:left|right) (?:wrist|forearm|shoulder|hand|elbow|arm)\b", re.I)
TWO_IMAGES = {"G03", "G05", "G06", "G07"}


def check_prompt(c, p, label):
    i = label
    if c["mode"] == "Frames":
        if not p.startswith(STYLE_START + "\n"):
            problems.append(f"{i}: Frames prompt must start with the start-image style sentence")
        if "reference image" in p:
            problems.append(f"{i}: Frames prompt mentions a reference image")
    elif c["id"] in TWO_IMAGES:
        if not p.startswith(STYLE_TWO + "\n"):
            problems.append(f"{i}: two-image prompt must start with the style sentence naming the young man's image")
        if NEW_ANGLE_2 not in p:
            problems.append(f"{i}: new-angle sentence (plural) missing")
    elif not p.startswith(STYLE + "\n"):
        problems.append(f"{i}: style sentence not first / not verbatim")
    for who in ("Nox", "Pico"):
        has_ing = ING[who] in c["ingredients"]
        n_marker = p.count(IMG[who])
        if has_ing and n_marker != 1:
            problems.append(f"{i}: {n_marker} {IMG[who]} markers for an attached {ING[who]}")
        if not has_ing and n_marker:
            problems.append(f"{i}: {IMG[who]} marker without the ingredient")
    if ING["Nox"] in c["ingredients"] and NOX_B not in p:
        problems.append(f"{i}: Nox phrase (with its marker) missing")
    if ING["Pico"] in c["ingredients"] and PICO_B not in p and c["id"] != "G18":
        problems.append(f"{i}: Pico phrase (with its marker) missing")
    nq = p.count('"')
    markers = re.findall(r"\[VOIX (NOX|PICO)\]", p)
    if c["voice"] == "none":
        if nq or markers or "says in French" in p:
            problems.append(f"{i}: silent card with speech, quotes or voice marker")
    else:
        if nq != 2:
            problems.append(f"{i}: {nq} double quotes (must be exactly one pair)")
        if markers != [c["voice"].upper()]:
            problems.append(f"{i}: voice markers {markers} for voice {c['voice']}")
        spoken = p.split('"')[1] if nq == 2 else None
        if spoken != c["line"]:
            problems.append(f"{i}: spoken line {spoken!r} differs from approved {c['line']!r}")
        quote_line = next(l for l in p.split("\n") if '"' in l)
        if p.split("\n").index(quote_line) != len(p.split("\n")) - 2:
            problems.append(f"{i}: the line is not in the second-to-last paragraph")
    if not p.endswith(FULL_FRAME) or not p.endswith(PROMPT_END):
        problems.append(f"{i}: does not end with the full-frame sentence")
    if "No subtitles, no on-screen text, no music" not in p:
        problems.append(f"{i}: closing constraint missing")
    if LOCKED not in p and c["id"] != "G16":
        problems.append(f"{i}: locked-camera sentence missing")
    if re.search(r"screen-(left|right)", p):
        problems.append(f"{i}: screen-left/right used")
    if re.search(r"\bbeau\b", p) or "raises one eyebrow" in p or "glowing pale blue" in p or "doorway far behind" in p:
        problems.append(f"{i}: a phrase removed after review came back")
    stripped = ALLOWED_DIR.sub("", p)
    for m in re.finditer(r"\b(left|right)\b", stripped):
        problems.append(f"{i}: bare '{m.group(0)}' near …{stripped[max(0, m.start() - 40):m.end() + 20]}…")
    if "[" in p.replace(IMG["Nox"], "").replace(IMG["Pico"], "").replace(VOX["Nox"], "").replace(VOX["Pico"], ""):
        problems.append(f"{i}: unknown bracket marker")


for c in CARDS:
    check_prompt(c, c["prompt"], c["id"])
    for t in c["take3"]:
        check_prompt(c, t["prompt"], c["id"] + "/" + t["key"])
        if t["prompt"] == c["prompt"]:
            problems.append(f"{c['id']}/{t['key']}: variant identical to the main prompt")
    if c["voice"] not in ("Nox", "Pico", "none"):
        problems.append(f"{c['id']}: bad voice")
    if not (3 <= c["duration_s"] <= 10):
        problems.append(f"{c['id']}: duration out of range")
    if c["mode"] == "Frames" and (c["ingredients"] or not c["start_image"] or c["voice"] != "none"):
        problems.append(f"{c['id']}: Frames card must have a start image, no ingredient and no voice")
    if c["mode"] == "Ingredients" and not c["ingredients"]:
        problems.append(f"{c['id']}: Ingredients card without ingredient")
    if not c["relaunch"] or not c["claude"]:
        problems.append(f"{c['id']}: checklist missing")
if [c["id"] for c in CARDS] != [f"G{k:02d}" for k in range(1, len(CARDS) + 1)]:
    problems.append("ids are not G01..Gnn in order")
NO_BEHIND = ["G01", "G02", "G08", "G15", "G17", "G18"]   # named in section C ("Flow refuse le prompt")
for c in CARDS:
    has = bool(re.search(r"(?:^|\n|[.;] )Behind\b", c["prompt"]))
    if has == (c["id"] in NO_BEHIND):
        problems.append(f"{c['id']}: 'Behind' sentence {'present' if has else 'missing'}, section C says otherwise")
if ORDER != ["G03", "G05", "G07", "G08", "G09", "G10", "G11", "G12", "G04", "G06"]:
    problems.append(f"unexpected order {ORDER}")
if BY_ID["G01"]["prompt_sent_etape1"] != G01_SENT or BY_ID["G02"]["prompt_sent_etape1"] != G02_SENT:
    problems.append("prompt_sent_etape1 differs from étape 1")
if apply_changes(G01_SENT, G01_CHANGES) != BY_ID["G01"]["prompt"] or apply_changes(G02_SENT, G02_CHANGES) != BY_ID["G02"]["prompt"]:
    problems.append("G01/G02 prompts differ from étape 1 by more than the listed changes")
for v in ("Nox", "Pico"):
    if VOICES[v]["description"] not in " ".join(l.strip() for l in ETAPE1):
        problems.append(f"voice {v} description not from étape 1")
covered = sorted({n for c in CARDS if c["group"] != "secours" for n in c["shots"]})
if covered != list(range(1, 12)):
    problems.append(f"shots covered by base cards: {covered}")
for m in SHOTS_MAP:
    src = next(s for s in SHOTLIST["shots"] if s["n"] == m["shot"])
    if m["captions"] != src["caption"]:
        problems.append(f"shot {m['shot']}: captions differ")
    for e in (m["edit"], m.get("edit_alt")):
        if e and e.get("mute") and "lead" not in e and ("in" not in e or "out" not in e):
            problems.append(f"shot {m['shot']}: muted reuse without both in and out")
if problems:
    print("PROBLEMS:")
    for x in problems:
        print(" -", x)
    sys.exit(1)

# ---------------------------------------------------------------- flow_kit.json
def gen_json(c):
    g = {"id": c["id"], "order": c["order"], "group": c["group"], "status": c["status"], "title": c["title"],
         "what": c["what"], "shots": c["shots"], "mode": c["mode"], "model": c["model"], "ingredients": c["ingredients"]}
    if c["start_image"]:
        g["start_image"] = c["start_image"]
    g |= {"markers": re.findall(r"\[(?:IMAGE|VOIX) (?:NOX|PICO)\]", c["prompt"]),
          "voice": c["voice"], "duration_s": c["duration_s"], "resolution": c["resolution"], "outputs": c["outputs"],
          "est_credits": c["est_credits"], "line": c["line"], "prompt": c["prompt"], "prompt_file": c["prompt_file"]}
    if c.get("prompt_sent_etape1"):
        g["prompt_sent_etape1"] = c["prompt_sent_etape1"]
        g["changes_from_etape1"] = [{"old": o, "new": n} for o, n in c["changes_from_etape1"]]
    g["checklist_fr"] = {"relance_si": c["relaunch"], "je_verifierai": c["claude"]}
    g["take3"] = [{k: t[k] for k in ("key", "when_fr", "what_fr", "file", "hint", "old", "new", "prompt") if k in t}
                  for t in c["take3"]]
    g["after_three_fails_fr"] = c["after3"]
    g["notes"] = c["notes"]
    g["why"] = c["why"]
    return g


kit = {
    "version": 2,
    "date": "2026-11-25",
    "title": "Nox & Pico — « Elle t'éclaire. Nuance. » — kit Google Flow (étape 2 : tous les plans)",
    "tool": "Google Flow",
    "model_default": "Omni Flash 1.2",
    "mode_default": "Ingredients",
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "outputs_per_request": 1,
    "crop_in_edit": "4:3 centre",
    "crop_note": "montage.py scales the 1280x720 clip and keeps the central 960x720: one eighth of the width goes on each side, so every prompt keeps the characters and the action in the centre.",
    "source_shotlist": "../shotlist.json (version %d, 11 shots); the French lines are the approved ones, word for word." % SHOTLIST["version"],
    "files": {
        "instructions_fr": "etape2_tous_les_plans.txt",
        "prompt_files": "prompts/Gnn.txt: one file per card, its prompt only, identical to generations[].prompt",
        "take3_files": "prompts/prise3/Gnn_<key>.txt: identical to generations[].take3[].prompt",
        "etape1": "etape1_test_flow.txt: step 1 as sent to the owner; never rewritten",
    },
    "voices": VOICES,
    "markers": {
        IMG["Nox"]: "replaced in Flow by @ + the image ingredient_nox.png (binds the young man to his image)",
        IMG["Pico"]: "replaced in Flow by @ + the image ingredient_pico.png",
        VOX["Nox"]: "replaced in Flow by @ + the custom voice Nox (not the image)",
        VOX["Pico"]: "replaced in Flow by @ + the custom voice Pico (not the image)",
    },
    "session_checks_fr": SESSION,
    "per_card_steps_fr": STEPS,
    "retake_rule_fr": RETAKE_RULE,
    "common_checks_fr": {"relance_si": COMMON_RELAUNCH, "je_verifierai": COMMON_CLAUDE, "hesitation": HESITATE},
    "style_sentence": STYLE,
    "style_sentence_two_characters": STYLE_TWO,
    "style_sentence_frames": STYLE_START,
    "characters": {
        "Nox": {"prompt_phrase": NOX, "prompt_phrase_with_marker": NOX_B, "ingredient": ING["Nox"], "voice": "Nox",
                "frontal_setting": NOX_FRONT_SETTING.strip(),
                "screen_side": "Always left of the centre of the frame, facing toward the right edge of the frame (except frontal shots 8 and 11; in shot 11 his eyes go just past the lens, toward the right edge of the frame)."},
        "Pico": {"prompt_phrase": PICO, "prompt_phrase_with_marker": PICO_B, "ingredient": ING["Pico"], "voice": "Pico",
                 "screen_side": "Always right of the centre of the frame, facing toward the left edge of the frame (her close-ups look toward the left edge of the frame, at Nox off-screen); the watch is on her left wrist, her left forearm enters from the right edge of the frame in shot 9."},
    },
    "house_sentences": {"locked_camera": LOCKED, "new_angle_one_image": NEW_ANGLE_1, "new_angle_two_images": NEW_ANGLE_2,
                        "monitor": MONITOR, "frontal_background": FRONT_STILL, "full_frame": FULL_FRAME,
                        "closing_him": CLOSE_HE, "closing_her": CLOSE_SHE, "closing_two_shot": CLOSE_TWO,
                        "closing_over_shoulder": CLOSE_OTS, "closing_silent": CLOSE_SILENT,
                        "pronunciation_hints": HINT},
    "screen_direction": "The camera always stays on Nox's right-hand side of the room: Nox left of the centre of the frame looking toward the right edge, Pico right of the centre looking toward the left edge. Directions in prompts are always given by frame edges.",
    "order": {"etape1_already_done": ETAPE1_IDS, "etape2_in_this_order": ORDER,
              "etape2_wait_for_claude_ok_on_G03": WAIT_FOR_G03,
              "secours_if_card_says_or_asked": SECOURS_IDS},
    "file_naming": "G03.mp4 pour la première prise, puis G03_prise2.mp4, G03_prise3.mp4. Les fichiers sont renvoyés dans la conversation, avec à côté du nom le fichier de prompt de 3e prise ou la durée changée, s'il y en a.",
    "generations": [gen_json(c) for c in CARDS],
    "shots_map": SHOTS_MAP,
    "edit_notes": EDIT_NOTES,
    "budget": BUDGET,
    "fallbacks": FALLBACKS,
}

# ---------------------------------------------------------------- etape2_tous_les_plans.txt
SEP = "─" * 28
BIG = "═" * 28
out = []
w = out.append
SHORT_ING = {ING["Nox"]: "ingredient_nox", ING["Pico"]: "ingredient_pico"}


def section(title):
    w(SEP)
    w(title)
    w(SEP)


def images_line(c):
    names = [SHORT_ING[x] for x in c["ingredients"]]
    marks = [IMG["Nox"] if x == ING["Nox"] else IMG["Pico"] for x in c["ingredients"]]
    if len(names) == 1:
        return f"{names[0]} seulement (repère {marks[0]}) ; enlève toute autre image"
    return f"{' + '.join(names)} (repères {' et '.join(marks)}) ; rien d'autre"


def voice_line(c):
    if c["voice"] == "none":
        return "aucune : enlève toute voix restée de la carte d'avant"
    return f"la voix {c['voice']}, pas l'image (repère {VOX[c['voice']]})"


def write_card(c):
    w(BIG)
    w(c["title"])
    w(BIG)
    w("Ce que c'est : " + c["what"])
    w("Statut : " + c["status"])
    if c["mode"] == "Frames":
        w(f"Mode : Vidéo → Frames — {c['model']} — 16:9 — {c['resolution']} — 1 vidéo (cette carte seulement ; après, remets Ingredients et Omni Flash 1.2)")
        w(f"Image de départ : {c['start_image']} (je te l'envoie) — dans Frames, touche la case de la première image et importe {c['start_image']} ; laisse vide la case de la dernière image")
    else:
        w(f"Mode : Vidéo → Ingredients — {c['model']} — 16:9 — {c['resolution']} — 1 vidéo")
        w("Images : " + images_line(c))
    w("Voix : " + voice_line(c))
    w(f"Durée : {c['duration_s']} s — prix affiché : {c['est_credits']} crédits")
    w(f"Prompt : fichier {c['prompt_file']}, ou le bloc ci-dessous")
    w(f"Vidéo : {c['id']}.mp4 (puis {c['id']}_prise2.mp4, {c['id']}_prise3.mp4)")
    w("")
    w("▼ PROMPT À COPIER ▼")
    w(c["prompt"])
    w("▲ FIN DU PROMPT ▲")
    w("")
    w("Relance si (en plus de la liste commune de la section A) :")
    for x in c["relaunch"]:
        w("- " + x)
    w("Je vérifierai (ne relance pas pour ça) :")
    for x in c["claude"]:
        w("- " + x)
    if c["take3"]:
        w("Prise 3, selon le défaut (pour un autre défaut, voir la section C) :")
        for t in c["take3"]:
            w(f"- {t['when_fr']} : {t['file']} ({t['what_fr']})")
    else:
        w("Prise 3 : le même prompt (pour un problème de durée, voir la section C).")
    if c["after3"]:
        w("Après trois prises ratées : " + c["after3"])
    if c["notes"]:
        w("Notes :")
        for x in c["notes"]:
            w("- " + x)
    w("")


w("NOX & PICO — ÉTAPE 2 : TOUS LES PLANS DANS GOOGLE FLOW")
w("Sketch « Elle t'éclaire. Nuance. » — 11 plans, environ 32 s")
w("Fichiers : ce document ; le dossier prompts (un fichier par carte, avec seulement son prompt ; prompts/prise3 : les prompts de 3e prise, tout prêts). Les deux images et les deux voix sont déjà dans ton projet Flow.")
w("")
w("EN BREF")
w("1. Avant : l'étape 1 est faite (voix Nox et Pico créées ; G01 = clip test 1 et G02 = clip test 2, téléchargés) et je t'ai dit que les voix sont bonnes.")
w(f"2. À faire : {len(ORDER)} clips, dans l'ordre des cartes de ce document : {', '.join(i for i in ORDER if i not in WAIT_FOR_G03)}, puis {' et '.join(WAIT_FOR_G03)} quand je t'ai confirmé que G03 est bon. Le plan 6 et les silences se découpent dans ces clips : rien de plus à générer.")
w("3. Pour chaque carte, suis les étapes a) à g) de la section A : vider, régler la durée, coller le prompt, remplacer les crochets par des @, vérifier le prix, lancer (1 vidéo), télécharger.")
w("4. Regarde chaque clip deux fois, son fort ou avec des écouteurs. Relance seulement pour un défaut de la liste « Relance si » (section A et carte) ; le reste, je le vérifie.")
w("5. " + RETAKE_RULE)
w("6. G03 passe en premier : dès qu'une prise te paraît bonne, envoie-la-moi et continue avec G05. S'il rate trois fois, ne fais ni G04 ni G06 : fais G13 et G14 à la place.")
w("7. Dès qu'un clip est prêt, avant la carte suivante : télécharge-le en MP4, taille d'origine (720p), et renomme-le tout de suite : G03.mp4, puis G03_prise2.mp4, G03_prise3.mp4. Ne supprime aucune prise dans Flow.")
w(f"8. Coût : {e2} crédits pour une prise de chacun des {len(ORDER)} clips ; avec les reprises, compte environ {round(e2_real, -1)}. Note ton solde avant de commencer : si cette étape a pris plus de {STOP} crédits, arrête-toi et envoie-moi ce que tu as.")
w("9. Les cartes G13 à G18 (section F) sont des secours : ne les fais que si une carte te le dit ou si je te le demande.")
w("10. Envoie-moi toutes les prises, même ratées, ici, au fur et à mesure (section D) : je vérifie, je te dis quoi refaire, puis je monte le film.")
w("")
w("Liste à cocher (copie-la dans une note ; une case par prise) :")
w(" · ".join(f"{i} ☐☐☐" for i in ORDER))
w("Chaque génération prend quelques minutes : prévois une ou deux séances.")
w("")
section("A. COMMENT FAIRE CHAQUE CARTE")
w("Au début de chaque séance :")
for x in SESSION:
    w("- " + x)
w("")
w("Pour chaque carte, dans cet ordre :")
for x in STEPS:
    w(x)
w("")
w("À vérifier sur TOUS les clips. Regarde le clip deux fois, son fort ou avec des écouteurs.")
w("Relance si :")
for x in COMMON_RELAUNCH:
    w("- " + x)
w("Je vérifierai moi-même (ne relance pas pour ça) :")
for x in COMMON_CLAUDE:
    w("- " + x)
w(HESITATE)
w("")
section("B. L'ORDRE (les cartes suivent dans cet ordre)")
ROLE = {"G07": "voix du plan 9", "G12": "image du plan 9"}
for i in ORDER:
    c = BY_ID[i]
    role = ROLE.get(i, f"plan{'s' if len(c['shots']) > 1 else ''} {' et '.join(str(n) for n in c['shots'])}")
    voice = "sans voix" if c["voice"] == "none" else "voix " + c["voice"]
    extra = {"G03": " — en premier ; envoie-le-moi dès qu'une prise te paraît bonne"}.get(i, "")
    if i in WAIT_FOR_G03:
        extra = " — quand je t'ai confirmé G03"
    w(f"{i} — {role} — {voice} — {c['duration_s']} s, {c['est_credits']} crédits{extra}")
w("Secours, seulement si une carte te le dit ou si je te le demande : G13 à G18 (section F).")
w("Déjà faits à l'étape 1 : G01 (= clip test 1) et G02 (= clip test 2) ; leurs cartes sont en annexe, à ne refaire que si je te le demande.")
w("")
for i in ORDER:
    write_card(BY_ID[i])
w(BIG)
w("FIN DES CARTES À FAIRE. Ne fais pas les cartes qui suivent sans raison : si une carte a raté, va à la section C ; sinon, va à la section D.")
w(BIG)
w("")
section("C. SI UNE PRISE RATE")
for fb in FALLBACKS:
    w("- " + fb["when"])
    w("  → " + fb["do"])
w("")
section("D. ENSUITE")
w("Envoie-moi ici, dans la conversation, toutes les prises (même ratées : leur son ou une partie de l'image peut servir), nommées comme indiqué, par 4 ou 5 fichiers à la fois, avec :")
w("- ton solde de crédits au début et à la fin de chaque séance ;")
w("- ce qui t'a semblé raté, même si tu n'es pas sûr ;")
w("- si tu as utilisé un fichier du dossier prompts/prise3 ou changé la durée : écris-le à côté du nom (par exemple : G05_prise3 — G05_geste.txt ; G10_prise3 — 4 s).")
w("Je vérifie les mots, les lèvres et les voix, je te dis quoi refaire, puis je monte le film : recadrage 4:3, sous-titres, musique et bruitages.")
w("Si une option de ce document n'existe pas dans ton Flow, dis-moi ce que tu vois et j'adapte.")
w("")
section("E. BUDGET")
w("- Prix : environ 3 crédits par seconde en 720p (4 s = 12, 6 s = 18, 8 s = 24, 10 s = 30) ; G17 (Veo 3.1 Lite) : 10.")
w(f"- Une prise de chacun des {len(ORDER)} clips : {e2} crédits. Avec les reprises (environ 1,5 prise par clip parlé, 2 pour G12, et un ou deux secours) : environ {round(e2_real, -1)} crédits, en plus des {e1} de l'étape 1.")
w(f"- Règle d'arrêt : si cette étape a pris plus de {STOP} crédits (ton solde de départ moins ton solde actuel), arrête-toi et envoie-moi ce que tu as ; on choisit ensemble les reprises.")
w("- Tes 50 crédits gratuits par jour paient environ deux clips : étaler sur plusieurs jours ménage les 1 000 du mois.")
w("")
section("F. CARTES DE SECOURS (seulement si une carte te le dit ou si je te le demande)")
w("")
for i in SECOURS_IDS:
    write_card(BY_ID[i])
section("ANNEXE — DÉJÀ FAITS À L'ÉTAPE 1 (ne pas refaire, sauf si je te le demande)")
w("G01 = clip test 1 (Nox) ; G02 = clip test 2 (Pico). Leurs prompts ci-dessous sont les versions corrigées, à utiliser seulement pour les refaire.")
w("")
for i in ETAPE1_IDS:
    write_card(BY_ID[i])
TXT = "\n".join(out).rstrip("\n") + "\n"

# ---------------------------------------------------------------- write everything
with open(os.path.join(HERE, "flow_kit.json"), "w", encoding="utf-8") as f:
    json.dump(kit, f, ensure_ascii=False, indent=1)
    f.write("\n")
with open(os.path.join(HERE, "etape2_tous_les_plans.txt"), "w", encoding="utf-8") as f:
    f.write(TXT)
PROMPTS_DIR = os.path.join(HERE, "prompts")
if os.path.isdir(PROMPTS_DIR):
    shutil.rmtree(PROMPTS_DIR)
os.makedirs(os.path.join(PROMPTS_DIR, "prise3"))
for c in CARDS:
    with open(os.path.join(HERE, c["prompt_file"]), "w", encoding="utf-8") as f:
        f.write(c["prompt"] + "\n")
    for t in c["take3"]:
        with open(os.path.join(HERE, t["file"]), "w", encoding="utf-8") as f:
            f.write(t["prompt"] + "\n")

# ---------------------------------------------------------------- read back and compare
back = json.load(open(os.path.join(HERE, "flow_kit.json"), encoding="utf-8"))
txt = open(os.path.join(HERE, "etape2_tous_les_plans.txt"), encoding="utf-8").read()
blocks = re.findall(r"▼ PROMPT À COPIER ▼\n(.*?)\n▲ FIN DU PROMPT ▲", txt, re.S)
txt_order = ORDER + SECOURS_IDS + ETAPE1_IDS
errs = []
if len(blocks) != len(CARDS):
    errs.append(f"{len(blocks)} prompt blocks in the TXT for {len(CARDS)} cards")
gj = {g["id"]: g for g in back["generations"]}
for cid, block in zip(txt_order, blocks):
    g = gj[cid]
    if block != g["prompt"]:
        errs.append(f"{cid}: TXT prompt differs from JSON")
    if open(os.path.join(HERE, g["prompt_file"]), encoding="utf-8").read() != g["prompt"] + "\n":
        errs.append(f"{cid}: prompt file differs from JSON")
    for t in g["take3"]:
        if open(os.path.join(HERE, t["file"]), encoding="utf-8").read() != t["prompt"] + "\n":
            errs.append(f"{cid}/{t['key']}: take-3 file differs from JSON")
        if t["file"] not in txt:
            errs.append(f"{cid}/{t['key']}: take-3 file not named in the TXT")
    seg = txt[txt.index(BIG + "\n" + g["title"] + "\n"):]
    seg = seg[: seg.index("▼ PROMPT")]
    if f"Durée : {g['duration_s']} s — prix affiché : {g['est_credits']} crédits" not in seg:
        errs.append(f"{cid}: duration/credits line differs from JSON")
    for x in g["checklist_fr"]["relance_si"] + g["checklist_fr"]["je_verifierai"]:
        if "- " + x not in txt:
            errs.append(f"{cid}: checklist line missing from the TXT")
n_files = sum(1 + len(g["take3"]) for g in back["generations"])
on_disk = sum(len(fs) for _, _, fs in os.walk(PROMPTS_DIR))
if n_files != on_disk:
    errs.append(f"{on_disk} prompt files on disk for {n_files} expected")
if open(os.path.join(HERE, "etape1_test_flow.txt"), encoding="utf-8").read() != ETAPE1_TEXT:
    errs.append("etape1_test_flow.txt changed")
if errs:
    print("READ-BACK PROBLEMS:")
    for x in errs:
        print(" -", x)
    sys.exit(1)

# ---------------------------------------------------------------- report
print("checks: OK (prompts, JSON, TXT, prompt files read back and compared)")
print(f"cards: {len(CARDS)} ({len(ETAPE1_IDS)} étape 1, {len(ORDER)} étape 2, {len(SECOURS_IDS)} secours); prompt files {n_files}")
print(f"étape 2 order: {' '.join(ORDER)} (wait for G03 ok: {' '.join(WAIT_FOR_G03)})")
print(f"credits: étape 1 {e1}; étape 2 one take {e2}, realistic {e2_real}, 3 takes each {cap3}, stop rule {STOP}; secours {sec}")
print(f"TXT lines: {TXT.count(chr(10))}")
for c in CARDS:
    print(f"  {c['id']} {c['voice']:5} {c['duration_s']:2}s {c['est_credits']:3} cr  prompt {len(c['prompt']):5} chars  take3 {len(c['take3'])}  shots {c['shots']}")
