#!/usr/bin/env python3
"""Writes shotlist.json (English, for the prompt writers) and shotlist.md (French, for the owner).

    python3 build_shotlist.py        then: python3 build_prompts.py   (prompts.json is built from shotlist.json)

The spoken text of every shot is copied from context/ep01_lines.json and checked:
a line split over two shots must give back the approved line exactly.
Version 2: the two reviews of the first pack are applied (see DECISIONS).
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LINES = {l["id"]: l for l in json.load(open(os.path.join(HERE, "context", "ep01_lines.json"), encoding="utf-8"))}

NNBSP = " "   # espace fine insécable, devant ? et !
NBSP = " "

STYLE_MASTER = "nox_ref"      # the approved image whose rendering wins when the two differ (owner may overrule)


def caption(text):
    """Typographie française propre : apostrophe courbe, espace fine insécable devant ? et !."""
    t = text.replace("'", "’")
    t = re.sub(r" (?=[?!])", NNBSP, t)
    return t


COMMON = (" Common to every new still: the rendering of the style master (nox_ref by default: its outline weight, "
          "flat shading and slightly pixelled edges), with the palette and night lighting of the approved images; "
          "4:3, generated at 1K (the approved images are 1200x896 and the clips 720p: a 2K still would have finer "
          "lines than shots 1 and 8); no text, letters or numbers anywhere (monitor screens show a plain pale-blue "
          "glow with blank rectangles, pinned notes are blank paper); Pico: red high ponytail with GREEN elastic, "
          "long strands round the face, yellow sweatshirt, black headphones round her neck, black smartwatch on her "
          "LEFT wrist, the only watch of the film; Nox: blue-black spiky hair with a rebel lock, thin glasses with "
          "pale transparent green-tinted lenses (both eyes always visible through them, no glare), black turtleneck, "
          "anthracite bomber with green zip trim, earbud in his LEFT ear (hidden whenever his left side is turned "
          "away); screen direction for the whole film: Nox on the left looking right, Pico on the right looking left "
          "(the camera never crosses to the window side of the Nox-door axis: it stays on that axis or on Nox's "
          "right-hand side). Ask for it as a NEW camera angle with the approved images as image_references, never as "
          "a copy of them.")

SETUPS = [
    {
        "id": "pico_porte",
        "framing": "Medium single of Pico, frontal, eye level, waist up (approved image, used as is)",
        "description": (
            "The approved image pico_ref.png is the start image, used as is. Start file stills/pico_porte.png: the "
            "same picture saved without transparency and trimmed by a few pixels to an exact 4:3 (1192x894), made "
            "by prep_refs.py; nothing is generated. Camera inside the workshop on Nox's side of the bench (his point "
            "of view), about 2.5 m from the door, at standing eye height. Pico has just stopped in the open doorway, "
            "centred, facing the lens; her left forearm is raised across her chest with the smartwatch toward the "
            "camera, brows frowned, mouth closed. Behind her: the dark brick hallway, a metal shelf with books and a "
            "small green LED string, a pendant lamp top right; the grey door leaf stands open at screen-left; dark "
            "workshop wall in the left foreground. Used for shot 1 only, and for the voice tests."),
        "start_image": "pico_ref", "start_file": "stills/pico_porte.png", "references": [], "make_order": 0,
        "fr_framing": "Plan moyen de Pico, de face, à hauteur des yeux, cadrée à la taille",
        "fr_description": (
            "Caméra dans l'atelier, du côté de Nox (son point de vue), à environ 2,5 m de la porte. Pico vient de "
            "s'arrêter dans l'encadrement de la porte ouverte, face à nous, avant-bras gauche levé devant elle, "
            "montre vers la caméra, sourcils froncés, bouche fermée. Derrière elle : le couloir en briques sombres, "
            "une étagère métallique avec une petite guirlande verte, une suspension en haut à droite ; le battant "
            "gris de la porte, ouvert, à gauche. Fichier de départ : la même image, enregistrée sans transparence "
            "et rognée de quelques pixels pour être exactement en 4:3."),
    },
    {
        "id": "nox_soudure",
        "framing": "Close-up of Nox at his soldering, low angle from bench level, three-quarter front",
        "description": (
            "Camera resting on the workbench top on Nox's right-hand side (the soldering-station side), about "
            "40 cm from his hands, tilted up about 25 degrees at his face, which is bowed over his work; his body "
            "is turned three-quarters toward screen-right. Bottom of the frame: his right hand holds the soldering "
            "iron (blue handle) still, its tip resting on a small green circuit board, a thin wisp of smoke: a held "
            "pose, not an action, because fine hand work is what video models do worst. His face fills the upper "
            "two-thirds: eyes lowered and clearly visible behind pale transparent lenses, mouth closed, rebel lock "
            "of hair. Because the camera is low, the bowed face is seen almost frontally: the mouth must be fully "
            "visible and above the bottom fifth of the frame (caption zone). Behind and above him: dark "
            "bookshelves, the string of round green bulbs, the plain glow of one CRT monitor, a slice of the night "
            "window at the right edge. Nobody else in frame; no watch on the bench; the soldering stand is out of "
            "frame (the iron is in his hand; nox_ref shows it in its stand, and two irons must not appear). His "
            "earbud is in the far ear and is not visible. References: nox_ref for the character, then the approved "
            "deux_etabli for the room, the bench props and his pose. Used for shot 2 and for the safety takes 2b "
            "and 7b. Spare still if the hand or the iron deforms in the clips: nox_soudure_sans_main." + COMMON),
        "start_image": "new", "start_file": "stills/nox_soudure.png", "references": ["nox_ref", "deux_etabli"],
        "make_order": 2,
        "fr_framing": "Gros plan de Nox à sa soudure, en contre-plongée depuis l'établi, de trois quarts",
        "fr_description": (
            "Caméra posée sur l'établi, à la droite de Nox (côté fer à souder), à 40 cm de ses mains, inclinée vers "
            "le haut, vers son visage penché sur son travail. En bas de l'image : sa main droite tient le fer "
            "immobile, la pointe posée sur un petit circuit vert, un filet de fumée (une pose tenue, pas un geste : "
            "les gestes fins des mains sont ce que la vidéo IA réussit le moins bien). Son visage occupe les deux "
            "tiers du haut : yeux baissés, bien visibles derrière des verres clairs et transparents, bouche fermée "
            "et bien visible, mèche rebelle. Derrière et au-dessus de lui : étagères de livres sombres, guirlande "
            "de boules vertes, lueur d'un écran, un bord de la fenêtre de nuit à droite. Personne d'autre à "
            "l'image, aucune montre sur l'établi, le support du fer hors cadre (sinon on verrait deux fers)."),
    },
    {
        "id": "deux_etabli",
        "framing": "Side-on two-shot across the workbench, waist up, at the eye level of the seated Nox",
        "description": (
            "The only frame with both faces, and the FIRST still to make: once approved it becomes a reference for "
            "the other new stills (same room, same props, same poses). Camera perpendicular to the Nox-door axis, "
            "on Nox's right-hand side of the room, about 2.5 m from the bench, lens at the eye height of the seated "
            "Nox (about 1.15 m), normal lens, everything in focus. Screen-left: Nox seated behind his bench, right "
            "profile facing screen-right, bowed over a small green circuit board; his right hand holds the "
            "soldering iron still, its tip resting on the board; eyes on his work, mouth closed; his earbud is in "
            "the far ear and is not visible. Screen-right: Pico on the visitor side, bent forward over the bench, "
            "right forearm planted flat on the bench top among his components, left elbow propped on the bench and "
            "left forearm reaching across so that her LEFT wrist, wearing the watch, sits about 15 cm in front of "
            "his glasses, between his face and the board; the watch screen is turned toward him and is seen "
            "edge-on. It is the only watch in the frame (no watch on the bench). She stares at him, one eyebrow "
            "raised, lips firmly closed (left profile). Background between them: the tall night window of the side "
            "wall with city lights (the workshop has a corner window: one window on the back wall as in nox_ref, an "
            "identical one on the side wall at Nox's left), the string of green bulbs along the top, bookshelves "
            "and a CRT monitor behind Nox; at the far right edge, the dark navy door wall with the grey door frame "
            "seen edge-on. The bench top crosses the lower third (grey mug on the far side, empty soldering stand "
            "in the foreground). Both faces and the watch stay above the bottom fifth of the frame (caption zone). "
            "References: nox_ref (image 1, also the style master) and pico_ref (image 2). Used for shots 3 and 6." + COMMON),
        "start_image": "new", "start_file": "stills/deux_etabli.png", "references": ["nox_ref", "pico_ref"],
        "make_order": 1,
        "fr_framing": "Plan à deux de profil, en travers de l'établi, cadré à la taille, à hauteur des yeux de Nox assis",
        "fr_description": (
            "Le seul cadre où l'on voit les deux visages, et la première image à créer : une fois validée, elle "
            "sert de modèle aux autres (même pièce, mêmes objets, mêmes poses). Caméra sur le côté de la pièce, à "
            "la droite de Nox, à 2,5 m de l'établi. À gauche : Nox assis derrière l'établi, de profil, tourné vers "
            "la droite, penché sur son circuit vert, le fer tenu immobile, la pointe posée sur le circuit, yeux sur "
            "son travail, bouche fermée ; son écouteur est du côté caché. À droite : Pico, côté visiteur, penchée "
            "sur l'établi, avant-bras droit posé à plat au milieu des composants, coude gauche posé et avant-bras "
            "gauche tendu : son poignet gauche, qui porte la montre, est à 15 cm des lunettes de Nox, entre son "
            "visage et son circuit ; l'écran de la montre est tourné vers lui, on la voit par la tranche. C'est la "
            "seule montre de l'image (aucune montre sur l'établi). Elle le fixe, un sourcil levé, lèvres bien "
            "fermées. Entre eux, au fond : la grande fenêtre de nuit du mur de côté et les lumières de la ville "
            "(l'atelier a une fenêtre d'angle : celle du fond, comme sur l'image validée, et la même sur le mur de "
            "côté), la guirlande verte en haut, les étagères et un écran derrière Nox ; tout à droite, le mur bleu "
            "nuit de la porte et son encadrement gris vu par la tranche. Le plateau de l'établi traverse le tiers "
            "bas (tasse au fond, support du fer vide devant). Visages et montre restent au-dessus du cinquième bas "
            "de l'image (zone des sous-titres)."),
    },
    {
        "id": "ots_nox",
        "framing": "Over-the-shoulder: over Pico (from behind) onto Nox, chest up",
        "description": (
            "Camera just behind Pico's left shoulder, about 1.3 m high, looking slightly down at the seated Nox "
            "across the bench. Right edge of the frame: a soft dark foreground shape made of her left shoulder "
            "(yellow sweatshirt), the headphones on her neck and a few red strands; no part of her face is "
            "visible. Her LEFT wrist, wearing the watch, is raised into the lower-right third, below Nox's chin so "
            "that it never covers his mouth; the watch screen is turned toward him, the camera sees only the strap "
            "and the edge of the case (a watch \"held out\" in her fingers would invite a detached watch or a "
            "hand-over). Nox is centre-left, chest up, three-quarter face turned toward screen-right, head "
            "slightly bowed, eyes lowered onto the watch, mouth closed, faint smirk; his hands are out of frame; "
            "his earbud is in the far ear and is not visible. Behind him the wall of nox_ref: bookshelves, green "
            "bulbs, CRT glow, the night window at the right behind Pico's shoulder. Bench top and soldering station "
            "below the frame. If the foreground wrist or watch comes out badly, use the spare still "
            "ots_nox_sans_bras (her arms below the frame; he then looks down at her wrist below the frame). "
            "References: nox_ref, pico_ref, then the approved deux_etabli. Used for shots 4 and 7 and for take 9b "
            "(the voice of shot 9)." + COMMON),
        "start_image": "new", "start_file": "stills/ots_nox.png", "references": ["nox_ref", "pico_ref", "deux_etabli"],
        "make_order": 2,
        "fr_framing": "Par-dessus l'épaule de Pico (de dos) vers Nox, cadré à la poitrine",
        "fr_description": (
            "Caméra juste derrière l'épaule gauche de Pico, à 1,30 m de haut, légèrement plongeante vers Nox assis "
            "de l'autre côté de l'établi. Bord droit : une amorce sombre faite de son épaule gauche (sweat jaune), "
            "du casque autour du cou et de quelques mèches rouges ; on ne voit rien de son visage. Son poignet "
            "gauche, qui porte la montre, est levé dans le tiers bas-droit, sous le menton de Nox, sans jamais "
            "cacher sa bouche ; l'écran de la montre est tourné vers lui, on n'en voit que le bracelet et la "
            "tranche (une montre « tendue » dans la main risquerait de sortir détachée du poignet). Nox est au "
            "centre-gauche, de trois quarts, tourné vers la droite, tête un peu baissée, yeux sur la montre, bouche "
            "fermée, léger sourire en coin ; ses mains sont hors cadre, son écouteur du côté caché. Derrière lui : "
            "le mur de l'image validée (étagères, boules vertes, lueur d'écran), la fenêtre de nuit à droite "
            "derrière l'épaule de Pico. Si le poignet ou la montre du premier plan sortent mal : image de secours "
            "sans le bras."),
    },
    {
        "id": "pico_gp",
        "framing": "Close-up of Pico leaning on the bench, head and shoulders, three-quarter front, at the eye level of the seated Nox",
        "description": (
            "Camera on Nox's side of the bench, slightly to his right, at the eye height of the seated Nox. Pico is "
            "leaning forward over the bench exactly as in the two-shot (shoulders hunched toward the camera, her "
            "head level with his), so that she does not seem to jump back to the door between shots 3, 5 and 6. "
            "Framed from just above the green elastic of the ponytail to the collarbones; headphones and yellow "
            "collar at the bottom edge; arms, hands and watch below the frame. She looks level toward the left edge "
            "of the frame, at the seated Nox off-screen. Neutral, a little taken aback, mouth closed: the same "
            "still must serve a sulky line and a panicked one. Behind her, kept dark and simple: mostly the plain "
            "dark navy wall; the open doorway small and far behind her in the right third (never the door frame "
            "round her, which would read as the doorway of shot 1). Chin above the bottom fifth of the frame "
            "(caption zone). References: pico_ref (a new three-quarter angle, not a crop of it), then the approved "
            "deux_etabli for her pose. Used for shots 5 and 10." + COMMON),
        "start_image": "new", "start_file": "stills/pico_gp.png", "references": ["pico_ref", "deux_etabli"],
        "make_order": 2,
        "fr_framing": "Gros plan de Pico penchée sur l'établi, tête et épaules, de trois quarts, à hauteur des yeux de Nox assis",
        "fr_description": (
            "Caméra du côté de Nox, un peu sur sa droite, à hauteur des yeux de Nox assis. Pico est penchée sur "
            "l'établi exactement comme dans le plan à deux (épaules vers nous, tête à la hauteur de celle de Nox) : "
            "ainsi elle ne semble pas retourner à la porte entre les plans 3, 5 et 6. Cadrée du dessus de "
            "l'élastique vert jusqu'aux clavicules ; casque et col jaune en bas ; bras, mains et montre sous le "
            "cadre. Elle regarde droit vers le bord gauche de l'image, vers Nox assis hors champ. Expression "
            "neutre, un peu interdite, bouche fermée : la même image sert à une réplique boudeuse et à une "
            "réplique paniquée. Derrière elle, sombre et simple : surtout le mur bleu nuit ; la porte ouverte, "
            "petite et lointaine, dans le tiers droit (jamais l'encadrement autour d'elle, qui rappellerait le "
            "plan 1). Menton au-dessus du cinquième bas de l'image."),
    },
    {
        "id": "nox_face",
        "framing": "Medium single of Nox, frontal, eye level, chest up (approved image, tightened by a 1.2x crop)",
        "description": (
            "The approved image nox_ref.png is the start image, tightened: start file stills/nox_face.png is the "
            "top-centre 1000x750 crop of nox_ref (a 1.2x punch-in anchored at the top), made by prep_refs.py; "
            "nothing is generated. The crop takes the bench top out of the frame: nox_ref shows an opened watch "
            "lying in the middle of the bench, which the viewer would read as Pico's watch, taken off and "
            "dismantled, at the very moment Nox says the line of shot 8. Camera in front of the bench at Pico's "
            "place (her point of view), at the eye height of the seated Nox. Nox faces the lens, mouth closed, "
            "hands below the frame. At the bottom edge only: the top of the soldering iron in its stand "
            "(screen-left) and the rim of the grey mug (screen-right). Behind him: bookshelves, the string of green "
            "bulbs, two CRT monitors, pinned notes; night window with city lights at screen-right. Used once in the "
            "film, for shot 8 (his glasses gesture), because the interface-like detail on the two screens may "
            "shimmer in video; also the start image of the voice tests (the tease l02b, kept as spare take 4b of "
            "shot 4) and of take 8b."),
        "start_image": "nox_ref", "start_file": "stills/nox_face.png", "references": [], "make_order": 0,
        "fr_framing": "Plan moyen de Nox, de face, à hauteur des yeux, cadré à la poitrine (image validée, resserrée)",
        "fr_description": (
            "L'image validée de Nox, resserrée : on garde le haut de l'image (grossissement de 1,2), sans rien "
            "régénérer. Ce recadrage fait sortir le plateau de l'établi : sur l'image validée, une montre démontée "
            "est posée au milieu de l'établi, et on croirait que c'est celle de Pico au moment même où Nox dit "
            "« Regarde de plus près. ». Caméra devant l'établi, à la place de Pico (son point de vue). Nox regarde "
            "l'objectif, bouche fermée, mains sous le cadre. Tout en bas : le haut du fer sur son support (à "
            "gauche) et le bord de la tasse (à droite). Derrière lui : étagères, guirlande de boules vertes, deux "
            "écrans cathodiques, notes épinglées ; fenêtre de nuit à droite. Utilisée une seule fois dans le "
            "film : les écrans peuvent scintiller en vidéo."),
    },
    {
        "id": "pico_yeux_montre",
        "framing": "Extreme close-up at bench height: Pico's eyes just above her watch, frontal",
        "description": (
            "The only frame that shows the green light, and the hardest still. Camera resting on the bench top on "
            "Nox's side, about 30 cm from the watch, lens a few centimetres above the bench surface, horizontal. "
            "Pico crouches at the bench so that her chin is level with the bench top and peeks over her own "
            "forearm: her left forearm lies flat on the bench across the middle of the frame (it comes in from "
            "screen-right, fist loosely closed toward screen-left), the watch in the centre, seen edge-on: its "
            "screen faces the ceiling and is not visible (no screen, so no digits); bright green light leaks from "
            "between the watch case and her skin, onto her wrist and onto the bench. Just above the forearm, only "
            "her eyes, eyebrows, forehead and red fringe are visible, about 10 cm behind the watch and lit green "
            "from below; her nose, mouth and chin are hidden behind the forearm. Eyes narrowed in a sceptical "
            "squint, fixed on the watch. Background dark and simple (plain navy wall, a hint of the door frame). "
            "The bench surface fills the bottom fifth of the frame (caption zone). References: pico_ref, then the "
            "approved deux_etabli. Used for shot 9. If it keeps failing (full face above the arm, digits on the "
            "watch, extra fingers): spare still montre_lueur, an insert of her forearm and watch on the bench with "
            "the green glow and no face, which keeps the green light in the film." + COMMON),
        "start_image": "new", "start_file": "stills/pico_yeux_montre.png", "references": ["pico_ref", "deux_etabli"],
        "make_order": 2,
        "fr_framing": "Très gros plan au ras de l'établi : les yeux de Pico juste au-dessus de sa montre, de face",
        "fr_description": (
            "Le seul cadre où l'on voit la lumière verte, et l'image la plus difficile. Caméra posée sur l'établi, "
            "du côté de Nox, à 30 cm de la montre, quelques centimètres au-dessus du plateau. Pico s'est "
            "accroupie, le menton à la hauteur du plateau, et regarde par-dessus son propre avant-bras : "
            "l'avant-bras gauche est posé à plat sur l'établi, en travers du milieu de l'image (il entre par la "
            "droite, poing à demi fermé vers la gauche), la montre au centre, vue par la tranche : son écran est "
            "tourné vers le plafond et ne se voit pas (pas d'écran, donc pas de chiffres) ; une lumière verte vive "
            "s'échappe entre le boîtier et la peau, et éclaire son poignet et l'établi. Juste au-dessus de "
            "l'avant-bras, on ne voit que ses yeux, ses sourcils, son front et ses mèches rouges, à 10 cm de la "
            "montre, éclairés en vert par en dessous ; son nez, sa bouche et son menton sont cachés derrière "
            "l'avant-bras. Yeux plissés, sceptiques, fixés sur la montre. Fond sombre et simple. Le plateau de "
            "l'établi occupe le cinquième bas de l'image (zone des sous-titres). Si l'image échoue plusieurs "
            "fois : image de secours, un insert de l'avant-bras et de la montre avec la lueur verte, sans visage."),
    },
    {
        "id": "nox_tgp",
        "framing": "Extreme close-up of Nox, frontal, hairline to chin",
        "description": (
            "Camera at the eye height of the seated Nox, frontal, on the axis of nox_ref but much closer (asked as "
            "a new, closer camera position, not as a crop). His face fills the frame: the glasses span about "
            "two-thirds of the width, the rebel lock is cut by the top edge, the turtleneck collar sits at the "
            "bottom edge. Pale transparent lenses, both eyes clearly visible, no glare. Flat deadpan, mouth closed, "
            "eyes on Pico just to the right of the lens. Behind him: dark bookshelves and three green bulbs, "
            "nothing else. The mouth sits above the bottom fifth of the frame, with enough air round the face that "
            "a 12-15% push-in still holds glasses and mouth. Reference: nox_ref only (it does not depend on the "
            "two-shot, so it is made in the first batch). Reserved for shot 11, the punchline." + COMMON),
        "start_image": "new", "start_file": "stills/nox_tgp.png", "references": ["nox_ref"], "make_order": 1,
        "fr_framing": "Très gros plan de Nox, de face, de la racine des cheveux au menton",
        "fr_description": (
            "Caméra à hauteur des yeux de Nox assis, de face, dans l'axe de l'image validée mais beaucoup plus "
            "près. Son visage remplit l'image : les lunettes occupent les deux tiers de la largeur, la mèche "
            "rebelle est coupée par le bord haut, le col roulé touche le bord bas. Verres clairs et transparents, "
            "les deux yeux bien visibles, sans reflet. Visage impassible, bouche fermée, regard sur Pico, juste à "
            "droite de l'objectif. Derrière lui : étagères sombres et trois boules vertes, rien d'autre. La bouche "
            "est au-dessus du cinquième bas de l'image, avec assez de marge pour qu'un léger zoom avant garde les "
            "lunettes et la bouche."),
    },
]

# Stills made only when a main still or its clips keep failing. They are not set-ups of the planned cut.
SPARE_STILLS = [
    {
        "id": "montre_lueur", "replaces": "pico_yeux_montre", "references": ["pico_ref", "deux_etabli"],
        "when": ("pico_yeux_montre fails three times (full face above the arm, digits on the watch, deformed "
                 "hand). Easy picture that keeps the green light in the film; the eyes are lost, so the reaction "
                 "is carried by shot 10 alone."),
        "description": ("Insert: her left forearm in the yellow sleeve lying flat on the cream bench top, the black "
                        "smartwatch in the centre with bright green light leaking from under the case onto her "
                        "skin and the bench; no face in the frame."),
        "fr": ("Insert de secours pour le plan 9 : l'avant-bras de Pico posé sur l'établi, la montre au centre, la "
               "lumière verte qui s'échappe sous le boîtier ; aucun visage. À créer seulement si l'image des yeux "
               "au ras de la montre échoue trois fois. On perd ses yeux qui s'arrondissent : la réaction est alors "
               "portée par le plan 10."),
    },
    {
        "id": "nox_soudure_sans_main", "replaces": "nox_soudure", "references": ["nox_ref", "deux_etabli"],
        "when": ("The hand or the iron deforms in the clips of shot 2 (iron bending or changing length, fingers "
                 "merging with the board, smoke turning to fog)."),
        "description": ("The nox_soudure frame with his hands and the bench below the frame; one thin wisp of "
                        "smoke rises from the bottom edge."),
        "fr": ("Le gros plan de Nox à sa soudure, sans les mains : elles sont sous le cadre, seul un filet de "
               "fumée monte du bord bas. À créer seulement si la main ou le fer se déforment dans les clips du "
               "plan 2."),
    },
    {
        "id": "ots_nox_sans_bras", "replaces": "ots_nox", "references": ["nox_ref", "pico_ref", "deux_etabli"],
        "when": "The foreground wrist or watch of ots_nox comes out badly in the still or deforms in the clips.",
        "description": ("The ots_nox frame without her wrist: her arms are below the frame; Nox looks down at her "
                        "wrist below the frame."),
        "fr": ("Le plan par-dessus l'épaule sans le poignet de Pico au premier plan (ses bras sont sous le cadre, "
               "Nox baisse les yeux vers sa montre, sous le cadre). À créer seulement si le poignet ou la montre "
               "sortent mal."),
    },
]

# Subtitle cards: one card per shot, except where a pause protects the second half of the line.
CARDS = {
    4: ["Tu portes cette montre depuis deux ans…", "et tu découvres qu'elle s'allume ?"],
    9: ["Ta montre envoie de la lumière verte…", "dans ta peau."],
    11: ["Elle t'éclaire.", "Nuance."],
}

# text = exact piece of the approved line; a line split over two shots is split at a sentence end only.
SHOTS = [
    {
        "n": 1, "setup": "pico_porte", "speaker": "pico", "line_id": "l01",
        "text": "Nox ! Pourquoi ma montre fait des lumières vertes à la fin de mon run ?",
        "est_s": 3.8, "request_s": 6, "pre_beat_s": 0.15,
        "acting": ("She has just skidded to a stop, out of breath; no hello. \"Nox !\" sharp, then the question, "
                   "urgent and pressing, quick but clearly articulated, very intrigued (the breathlessness is heard "
                   "before the first word, not inside the sentence). One beat: she shakes her raised watch wrist "
                   "toward him once on \"ma montre\", eyes locked on him (the lens). After the last word she holds "
                   "the wrist up and the stare, mouth closed."),
        "listener": "Nox is off-screen (the camera is his point of view).",
        "camera": "Locked. The clip opens on the posed still, door already open.",
        "sfx": "Door bang on the first frame; a short sneaker squeak under it (optional).",
        "notes": ("The caption of the question is on screen from 0.1 s: it is the hook (two lines: \"Nox ! Pourquoi "
                  "ma montre fait\" / \"des lumières vertes à la fin de mon run ?\"). Longest line (14 words): "
                  "frontal, medium size, one mouth. \"run\" is the English word as French runners say it. A faint "
                  "green flicker under the watch case is welcome but must not be forced. This clip is also the Pico "
                  "clip of the voice tests: it needs no new still."),
        "fr_acting": ("Elle vient de piler net, essoufflée ; pas de bonjour. « Nox ! » sec, puis la question, "
                      "pressante, rapide mais bien articulée, très intriguée (l'essoufflement s'entend avant le "
                      "premier mot, pas dans la phrase). Un seul geste : elle secoue une fois son poignet levé "
                      "vers lui sur « ma montre », les yeux plantés dans les siens (l'objectif). Après le dernier "
                      "mot, elle garde le poignet levé et le regard, bouche fermée."),
        "fr_listener": "Nox est hors champ (la caméra est à sa place).",
        "fr_camera": "Fixe. Le plan s'ouvre sur l'image posée, porte déjà ouverte.",
        "fr_sfx": "Claquement de porte sur la première image ; petit crissement de basket (facultatif).",
        "fr_notes": ("Le sous-titre de la question est à l'écran dès 0,1 s : c'est l'accroche (sur deux lignes : "
                     "« Nox ! Pourquoi ma montre fait », puis « des lumières vertes à la fin de mon run ? »). "
                     "Réplique la plus longue (14 mots) : de face, de taille moyenne, une seule bouche. « run » se "
                     "dit comme le disent les coureurs français. Une petite lueur verte sous la montre est "
                     "bienvenue, sans la forcer. Ce plan sert aussi aux essais de voix : il ne demande aucune "
                     "nouvelle image."),
    },
    {
        "n": 2, "setup": "nox_soudure", "speaker": "nox", "line_id": "l02",
        "text": "Bonsoir à toi aussi, Pico.",
        "est_s": 2.9, "request_s": 5, "pre_beat_s": 1.0,
        "acting": ("First sentence of l02. He does not react: bowed over his work, motionless, the iron tip resting "
                   "on the board, through one silent second. Then he says it to his circuit board without looking "
                   "up: brisk, wry, exaggeratedly polite, mock-offended, a smile in the voice. No gesture and no "
                   "change of face: his non-reaction is the joke."),
        "listener": "Pico is off-screen; her sneaker steps cross the room under the silent second (added in the edit).",
        "camera": "Locked, low angle.",
        "sfx": ("Faint soldering sizzle; Pico's quick steps approaching under the silent second and the line, cut "
                "dead by the clatter on the cut into shot 3."),
        "notes": ("The silent second before the deadpan answer is the first laugh (as reference 2, shot 11). If the "
                  "model starts speaking at once, hold the first frame in the edit. Safety take 2b on this same "
                  "still: the whole of l02 in one clip (about 4.2 s), which replaces shots 2 and 3 if the two-shot "
                  "fails. Shots 2 and 3 are the two halves of one line: played back to back they must sound like "
                  "one utterance (same pitch, level and energy)."),
        "fr_acting": ("Première phrase de l02. Il ne réagit pas : penché sur son travail, immobile, la pointe du "
                      "fer posée sur le circuit, pendant une seconde de silence. Puis il le dit à son circuit, "
                      "sans lever les yeux : pince-sans-rire, d'une politesse exagérée, faussement vexé, un "
                      "sourire dans la voix, débit vif. Aucun geste, aucune mimique : son absence de réaction est "
                      "le gag."),
        "fr_listener": ("Pico est hors champ ; on entend ses pas traverser la pièce pendant la seconde de silence "
                        "(ajoutés au montage)."),
        "fr_camera": "Fixe, en contre-plongée.",
        "fr_sfx": ("Léger grésillement de la soudure ; pas rapides de Pico qui approche, coupés net par le fracas "
                   "du plan 3."),
        "fr_notes": ("La seconde de silence avant la réponse pince-sans-rire est le premier rire (comme le plan 11 "
                     "de la référence 2). Si le modèle parle tout de suite, on prolonge la première image au "
                     "montage. Prise de sécurité 2 bis sur la même image : toute la réplique l02 en un seul clip "
                     "(environ 4,2 s), qui remplace les plans 2 et 3 si le plan à deux échoue. Les plans 2 et 3 "
                     "sont les deux moitiés d'une même réplique : écoutés à la suite, ils doivent sonner comme une "
                     "seule phrase (même hauteur, même niveau, même énergie)."),
    },
    {
        "n": 3, "setup": "deux_etabli", "speaker": "nox", "line_id": "l02",
        "text": "Entre, fais comme chez toi.",
        "est_s": 2.7, "request_s": 5, "pre_beat_s": 0.9,
        "acting": ("Second sentence of l02. The hard cut reveals that she is already sprawled on his bench with the "
                   "watch under his nose: the laugh is on the cut, and the tableau is held for almost a second "
                   "before the line. He stays bowed over his work; one beat: he lifts his head a few centimetres, "
                   "just enough to look at her over the watch. Warm, amused sarcasm, an old habit between them, "
                   "brisk."),
        "listener": ("Pico frozen, wrist held 15 cm from his glasses, staring at him, eyebrow raised, lips closed. "
                     "Her stillness is the joke."),
        "camera": ("Locked. Almost one second on the tableau before the line, so that the reveal reads (reference "
                   "1 gives its wide gag frames more than 3 s)."),
        "sfx": ("A short clatter of components exactly on the cut (her elbows landing on the bench); the footsteps "
                "stop on it."),
        "notes": ("The only speaking shot with two visible faces: the prompt names the speaker (the young man on "
                  "the left) and says the young woman on the right keeps her lips closed and does not move. Short "
                  "line (6 syllables), in profile. If her lips move anyway: remake the still with her head turned "
                  "further from the camera. If the still itself fails: use safety takes 2b and 7b and drop shots 3 "
                  "and 6."),
        "fr_acting": ("Deuxième phrase de l02. La coupe révèle qu'elle est déjà affalée sur son établi, la montre "
                      "sous son nez : le rire est sur la coupe, et le tableau reste près d'une seconde avant la "
                      "réplique. Il reste penché sur son travail ; un seul geste : il relève la tête de quelques "
                      "centimètres, juste assez pour la regarder par-dessus la montre. Sarcasme chaleureux et "
                      "amusé, vieille habitude entre eux, débit vif."),
        "fr_listener": ("Pico figée, poignet tendu à 15 cm de ses lunettes ; elle le fixe, sourcil levé, lèvres "
                        "fermées. Son immobilité est le gag."),
        "fr_camera": ("Fixe. Près d'une seconde sur le tableau avant la réplique, pour que la surprise se lise (la "
                      "référence 1 laisse plus de 3 s à ses plans larges de gag)."),
        "fr_sfx": ("Petit fracas de composants pile sur la coupe (ses coudes qui atterrissent sur l'établi) ; les "
                   "pas s'arrêtent dessus."),
        "fr_notes": ("Seul plan parlé où l'on voit deux visages : la consigne nomme celui qui parle (le jeune homme "
                     "à gauche) et précise que la jeune femme à droite garde les lèvres fermées et ne bouge pas. "
                     "Réplique courte (6 syllabes), de profil. Si ses lèvres bougent quand même : refaire l'image "
                     "avec sa tête plus tournée vers le fond. Si l'image elle-même échoue : prises de sécurité "
                     "2 bis et 7 bis, et on retire les plans 3 et 6."),
    },
    {
        "n": 4, "setup": "ots_nox", "speaker": "nox", "line_id": "l02b",
        "text": "Tu portes cette montre depuis deux ans… et tu découvres qu'elle s'allume ?",
        "est_s": 4.4, "request_s": 6, "pre_beat_s": 0.25,
        "acting": ("Kept whole so that the pause plays in real time. Teasing, deadpan-playful, brisk, a smile in "
                   "the voice. His eyes are on the watch for \"Tu portes cette montre depuis deux ans…\"; one "
                   "beat: on the \"…\" he looks up at her over the top of his glasses with a corner smile (only "
                   "his eyes move, his head stays bowed), then finishes the question lightly, enjoying it."),
        "listener": "Pico's shoulder and raised wrist in the foreground do not move.",
        "camera": "Locked. The one shot above 4 s.",
        "sfx": "",
        "notes": ("12 words on a three-quarter face of medium size, never on a close-up, so that a lip-sync slip "
                  "shows least. The \"…\" is a short held pause, not a slowdown. Two caption cards: the second "
                  "half appears only after the pause. No raised eyebrow for Nox: that is Pico's signature. Spare "
                  "take 4b: the same line on nox_face (made anyway as part of the voice tests)."),
        "fr_acting": ("Réplique gardée entière pour que la pause se joue en temps réel. Taquin, pince-sans-rire, "
                      "vif, un sourire dans la voix. Ses yeux sont sur la montre pendant « Tu portes cette montre "
                      "depuis deux ans… » ; un seul geste : sur les points de suspension, il lève les yeux vers "
                      "elle par-dessus ses lunettes, sourire en coin (seuls ses yeux bougent, la tête reste "
                      "baissée), puis termine la question d'un ton léger, en se régalant."),
        "fr_listener": "L'épaule et le poignet de Pico, au premier plan, ne bougent pas.",
        "fr_camera": "Fixe. Le seul plan de plus de 4 s.",
        "fr_sfx": "",
        "fr_notes": ("12 mots sur un visage de trois quarts et de taille moyenne, jamais en gros plan : c'est là "
                     "qu'un défaut de synchronisation des lèvres se voit le moins. Les points de suspension sont "
                     "une courte pause tenue, pas un ralentissement. Sous-titre en deux temps : la seconde moitié "
                     "n'apparaît qu'après la pause. Pas de sourcil levé pour Nox : c'est la signature de Pico. "
                     "Prise de rechange 4 bis : la même réplique sur l'image validée de Nox (faite de toute façon "
                     "pour les essais de voix)."),
    },
    {
        "n": 5, "setup": "pico_gp", "speaker": "pico", "line_id": "l02c",
        "text": "J'ai jamais regardé dessous, ok ?",
        "est_s": 2.3, "request_s": 5, "pre_beat_s": 0.15,
        "acting": ("Stung, she snaps back at once, tit for tat: fast, defensive, a bit sulky. One beat: on \"ok ?\" "
                   "she lifts her chin and pouts, glaring straight back at him (toward the left edge of the frame); "
                   "she holds the sulky glare."),
        "listener": "Nox is off-screen.",
        "camera": "Locked.",
        "sfx": "",
        "notes": ("First use of the Pico close-up. No silence before her line: the held silence is Nox's device, "
                  "not hers. Her sulky glare at him is the look she still has in shot 6. Listen for the word \"ok\" "
                  "(two syllables, as okay)."),
        "fr_acting": ("Piquée au vif, elle répond du tac au tac : vite, sur la défensive, un peu boudeuse. Un seul "
                      "geste : sur « ok ? », elle lève le menton et fait la moue en le fusillant du regard (vers "
                      "la gauche de l'image) ; elle garde ce regard boudeur."),
        "fr_listener": "Nox est hors champ.",
        "fr_camera": "Fixe.",
        "fr_sfx": "",
        "fr_notes": ("Première utilisation du gros plan de Pico. Pas de silence avant sa réplique : le silence est "
                     "l'arme de Nox, pas la sienne. Son regard boudeur est celui qu'elle a encore au plan 6. "
                     "Écouter le mot « ok » (deux syllabes, « oké »)."),
    },
    {
        "n": 6, "setup": "deux_etabli", "speaker": "none", "line_id": "",
        "text": "",
        "est_s": 1.3, "request_s": 5, "pre_beat_s": 0,
        "acting": ("Silent stand-off. Exactly the tableau of shot 3: he is already back at his circuit board and "
                   "does not look at her; she is still planted on his bench, wrist under his nose, glaring at him "
                   "(the sulky glare that ends shot 5). Nothing moves except the wisp of smoke."),
        "listener": "Both hold perfectly still, lips closed.",
        "camera": "Locked. Same still as shot 3 (reference 1 also reuses its wide before and after the gag).",
        "sfx": ("Soldering sizzle and room tone only (the clip is generated without sound). Optional: one short "
                "amused breath through the nose from Nox on the last frames, leading into his \"Bon.\"."),
        "notes": ("The only silence of this passage, played with both characters in frame. Generated with "
                  "generate_audio off, from the same still as shot 3; failing that, the still itself held for "
                  "1.3 s. If the shot is dropped in the edit, shot 7 is replaced by take 7b (the soldering close-up), "
                  "so that the over-the-shoulder frame does not come twice in a row for Nox."),
        "fr_acting": ("Face-à-face muet. Exactement le tableau du plan 3 : il s'est déjà remis à son circuit et ne "
                      "la regarde pas ; elle est toujours plantée sur son établi, poignet sous son nez, et le "
                      "fusille du regard (le regard boudeur qui termine le plan 5). Rien ne bouge, sauf le filet "
                      "de fumée."),
        "fr_listener": "Les deux restent parfaitement immobiles, lèvres fermées.",
        "fr_camera": ("Fixe. Même image que le plan 3 (la référence 1 réutilise aussi son plan large avant et "
                      "après le gag)."),
        "fr_sfx": ("Grésillement de la soudure et ambiance de pièce seulement (le clip est généré sans son). "
                   "Facultatif : un petit souffle amusé de Nox, par le nez, sur les dernières images, qui amène "
                   "son « Bon. »."),
        "fr_notes": ("Le seul silence de ce passage, joué avec les deux personnages à l'image. Clip généré sans "
                     "son, à partir de la même image que le plan 3 ; à défaut, l'image elle-même tenue 1,3 s. Si on "
                     "retire ce plan au montage, le plan 7 est remplacé par la prise 7 bis (gros plan de la "
                     "soudure), pour que le cadre par-dessus l'épaule ne revienne pas deux fois de suite sur "
                     "Nox."),
    },
    {
        "n": 7, "setup": "ots_nox", "speaker": "nox", "line_id": "l02d",
        "text": "Bon. Laisse-moi t'expliquer.",
        "est_s": 2.5, "request_s": 5, "pre_beat_s": 0.25,
        "acting": ("\"Bon.\" short and falling, amused and resigned (he gives in), eyes still down on the watch. One "
                   "beat: he lifts his head toward her (toward the right edge of the frame) and the rest brightens, "
                   "eager and brisk: \"Laisse-moi t'expliquer.\" (he loves explaining)."),
        "listener": "Pico's shoulder and raised wrist in the foreground do not move.",
        "camera": "Locked. Same still as shot 4.",
        "sfx": "",
        "notes": ("Played over Pico's shoulder, not on the soldering close-up: her wrist and watch are in front of "
                  "his face in shots 3, 4 and 6 and would vanish on a hard cut to a frame without her. Same still "
                  "as shot 4, two shots apart, with a different beat (shot 4: only his eyes come up; shot 7: his "
                  "whole head). The amused sigh is no longer asked of the model (it could come out as a word): it "
                  "is a sound added at the end of shot 6. Safety take 7b: the same line on nox_soudure, for the cut "
                  "without the two-shot."),
        "fr_acting": ("« Bon. » court, qui retombe, amusé et résigné (il rend les armes), les yeux encore baissés "
                      "sur la montre. Un seul geste : il relève la tête vers elle (vers la droite de l'image) et "
                      "la suite s'éclaire, gourmande, débit vif : « Laisse-moi t'expliquer. » (il adore "
                      "expliquer)."),
        "fr_listener": "L'épaule et le poignet de Pico, au premier plan, ne bougent pas.",
        "fr_camera": "Fixe. Même image que le plan 4.",
        "fr_sfx": "",
        "fr_notes": ("Joué par-dessus l'épaule de Pico, et non plus sur le gros plan de la soudure : son poignet et "
                     "sa montre sont devant le visage de Nox aux plans 3, 4 et 6, et ils disparaîtraient d'un coup "
                     "sur une image où elle n'est pas. Même image que le plan 4, à deux plans d'écart, avec un "
                     "geste différent (plan 4 : seuls ses yeux se lèvent ; plan 7 : toute la tête). Le petit "
                     "soupir amusé n'est plus demandé au modèle (il risquait de devenir un mot) : c'est un son "
                     "ajouté à la fin du plan 6. Prise de sécurité 7 bis : la même réplique sur le gros plan de la "
                     "soudure, pour le montage sans plan à deux."),
    },
    {
        "n": 8, "setup": "nox_face", "speaker": "nox", "line_id": "l03",
        "text": "Regarde de plus près.",
        "est_s": 2.6, "request_s": 5, "pre_beat_s": 0.25,
        "acting": ("First sentence of l03, his catchphrase: playful and inviting, a grin in it, at full voice, "
                   "brisk. One beat, AFTER the line: he pushes his glasses up with one index finger, a small green "
                   "glint on the rim of one lens; the cut to shot 9 lands on that glint."),
        "listener": "Pico is off-screen (the camera is her point of view).",
        "camera": "Locked.",
        "sfx": "A tiny glint sound on the glasses.",
        "notes": ("His signature before every revelation (the revelation is shot 9). The gesture comes after the "
                  "line: the hand is never near the mouth while he speaks, and if the gesture comes out badly the "
                  "shot is cut right after the last word. His eyes stay visible through the lenses the whole time. "
                  "Take 8b: no hand and no glint (he leans a little toward the lens); the glint is then a sound "
                  "only. Ask for a perfectly still background with frozen screens. Five syllables in a 5 s clip: "
                  "check that no word is added and that the delivery is not stretched. Shots 8 and 9 are the two "
                  "halves of one line: same voice, same energy."),
        "fr_acting": ("Première phrase de l03, sa phrase fétiche : joueuse, comme une invitation, un sourire dans "
                      "la voix, à pleine voix, débit vif. Un seul geste, APRÈS la réplique : il remonte ses "
                      "lunettes d'un doigt, petit reflet vert sur le bord d'un verre ; la coupe vers le plan 9 "
                      "tombe sur ce reflet."),
        "fr_listener": "Pico est hors champ (la caméra est à sa place).",
        "fr_camera": "Fixe.",
        "fr_sfx": "Petit tintement sur le reflet des lunettes.",
        "fr_notes": ("Sa signature avant chaque révélation (la révélation est au plan 9). Le geste vient après la "
                     "réplique : la main n'est jamais près de la bouche pendant qu'il parle, et si le geste sort "
                     "mal on coupe juste après le dernier mot. Ses yeux restent visibles derrière les verres tout "
                     "le long. Prise 8 bis : sans la main et sans reflet (il se penche un peu vers nous) ; le "
                     "reflet n'est alors qu'un son. Demander un fond parfaitement immobile, écrans figés. Cinq "
                     "syllabes dans un clip de 5 s : vérifier qu'aucun mot n'est ajouté et que le débit n'est pas "
                     "étiré. Les plans 8 et 9 sont les deux moitiés d'une même réplique : même voix, même "
                     "énergie."),
    },
    {
        "n": 9, "setup": "pico_yeux_montre", "speaker": "nox", "line_id": "l03",
        "text": "Ta montre envoie de la lumière verte… dans ta peau.",
        "est_s": 3.7, "request_s": 6, "pre_beat_s": 0.4,
        "acting": ("Second sentence of l03, spoken OFF-SCREEN by Nox. The sound is that of take 9b (Nox on screen, "
                   "over her shoulder), laid over this picture in the edit. Lively storyteller relish, at full "
                   "voice; a short suspense pause after \"verte…\", then \"dans ta peau.\" a little lower and "
                   "closer, fully voiced and clearly articulated, with mock mystery."),
        "listener": ("Pico is on screen and has taken \"look closer\" literally: crouched, eyes 10 cm from the "
                     "watch, squinting, green light pulsing on her skin. One beat: on \"dans ta peau\" her squint "
                     "drops and her eyes go round, still fixed on the watch; she freezes. She does not look up at "
                     "him: that look is kept for \"quoi ?!\" in shot 10. Her mouth stays hidden behind her "
                     "forearm, which does not move."),
        "camera": "Locked, at bench height.",
        "sfx": "A soft, low electronic pulse in time with the green light (optional).",
        "notes": ("The image of the sketch: the green light on her skin, the subject of the episode, shown rather "
                  "than told. The picture is generated without sound (generate_audio off): an off-screen voice "
                  "could come out in the wrong voice, in the young woman's mouth, or not at all. In the edit the "
                  "sound of take 9b is placed so that \"dans ta peau\" falls on her eyes going round. Two caption "
                  "cards: \"dans ta peau.\" appears only after the pause. If the still fails: the spare insert "
                  "montre_lueur (forearm, watch, green glow, no face); as a last resort, take 9b as picture and "
                  "sound."),
        "fr_acting": ("Deuxième phrase de l03, dite par Nox HORS CHAMP. Le son est celui de la prise 9 bis (Nox à "
                      "l'image, par-dessus l'épaule de Pico), posé sur cette image au montage. Plaisir de conteur, "
                      "vivant, à pleine voix ; une courte pause de suspense après « verte… », puis « dans ta "
                      "peau. » un peu plus bas et plus proche, bien timbré et bien articulé, faussement "
                      "mystérieux."),
        "fr_listener": ("Pico est à l'image : elle a pris « regarde de plus près » au pied de la lettre, "
                        "accroupie, les yeux à 10 cm de sa montre, plissés, la lumière verte qui pulse sur sa "
                        "peau. Un seul geste : sur « dans ta peau », ses yeux cessent de se plisser et "
                        "s'arrondissent, toujours fixés sur la montre ; elle se fige. Elle ne lève pas les yeux "
                        "vers Nox : ce regard-là est gardé pour « quoi ?! », au plan 10. Sa bouche reste cachée "
                        "derrière son avant-bras, qui ne bouge pas."),
        "fr_camera": "Fixe, au ras de l'établi.",
        "fr_sfx": "Pulsation électronique douce et grave, calée sur la lumière verte (facultatif).",
        "fr_notes": ("L'image du sketch : la lumière verte sur sa peau, le sujet de l'épisode, montré plutôt que "
                     "raconté. L'image est générée sans son : une voix hors champ pouvait sortir avec la mauvaise "
                     "voix, dans la bouche de Pico, ou ne pas sortir du tout. Au montage, on place le son de la "
                     "prise 9 bis pour que « dans ta peau » tombe sur ses yeux qui s'arrondissent. Sous-titre en "
                     "deux temps : « dans ta peau. » n'apparaît qu'après la pause. Si l'image échoue : l'insert de "
                     "secours (avant-bras et montre, lueur verte, sans visage) ; en dernier recours, la prise "
                     "9 bis entière, image et son."),
    },
    {
        "n": 10, "setup": "pico_gp", "speaker": "pico", "line_id": "l04",
        "text": "Attends… quoi ?! Elle me scanne ?!",
        "est_s": 2.8, "request_s": 5, "pre_beat_s": 0.3,
        "acting": ("Her signature double-take, played once. The shot opens as her eyes are already dropping toward "
                   "her wrist (below the frame), carrying on from shot 9: \"Attends…\" low and stunned, eyes down; "
                   "one beat: on \"quoi ?!\" her head jerks up and her wide eyes snap to Nox (toward the left edge "
                   "of the frame); then \"Elle me scanne ?!\" loud, rising, a touch of panic. She holds the shocked "
                   "face after the last word."),
        "listener": "Nox is off-screen.",
        "camera": "Locked.",
        "sfx": "",
        "notes": ("The line stays whole in one clip: split in two it would give two clips of 3 syllables that the "
                  "model pads with invented words, and two voices for one outcry. Same still as shot 5, but her "
                  "previous appearance is the eyes-over-watch shot, so the framing is not repeated twice in a row. "
                  "In the edit the shot starts when her eyes are already down. Listen for the word \"scanne\"."),
        "fr_acting": ("Son double regard, sa signature, joué une seule fois. Le plan s'ouvre alors que ses yeux "
                      "tombent déjà vers son poignet (sous le cadre), dans la continuité du plan 9 : « Attends… » "
                      "bas, sidéré, les yeux baissés ; un seul geste : sur « quoi ?! », sa tête se redresse d'un "
                      "coup et ses yeux écarquillés se plantent sur Nox (vers la gauche de l'image) ; puis « Elle "
                      "me scanne ?! » fort, qui monte, avec une pointe de panique. Elle garde le visage choqué "
                      "après le dernier mot."),
        "fr_listener": "Nox est hors champ.",
        "fr_camera": "Fixe.",
        "fr_sfx": "",
        "fr_notes": ("La réplique reste entière dans un seul clip : coupée en deux, elle donnerait deux clips de "
                     "3 syllabes que le modèle remplit de mots inventés, et deux voix pour un seul cri. Même image "
                     "que le plan 5, mais sa précédente apparition est le très gros plan sur ses yeux : le cadrage "
                     "n'est donc pas répété deux fois de suite. Au montage, le plan commence quand ses yeux sont "
                     "déjà baissés. Écouter le mot « scanne »."),
    },
    {
        "n": 11, "setup": "nox_tgp", "speaker": "nox", "line_id": "l04b",
        "text": "Elle t'éclaire. Nuance.",
        "est_s": 3.6, "request_s": 6, "pre_beat_s": 1.2,
        "acting": ("A silent deadpan stare for 1.2 s, with one slow blink. Then, precise and amused, at an easy "
                   "conversational pace: \"Elle t'éclaire.\", a tiny pause, and \"Nuance.\" placed crisply, with a "
                   "falling tone, like a full stop. One beat: the corner of his mouth lifts after \"Nuance.\"; he "
                   "holds the smirk 0.7 s to the final cut. Deadpan in the face, alive in the voice."),
        "listener": "Pico is off-screen.",
        "camera": ("Slow push-in of about 12-15% over the whole shot, the only camera move of the film. Generate "
                   "the clip locked and do the push-in in the edit; plan B (take 11b) is to ask the model for a "
                   "very slow push-in."),
        "sfx": ("None: the music bed stops on the cut into this shot, so that the stare and the line play over "
                "silence."),
        "notes": ("Punchline and end of the film (as the last shot of reference 1: silent stare, line, faint "
                  "smirk). \"Nuance.\" is the punchline word: neither swallowed nor rising like a question. Two "
                  "caption cards: \"Nuance.\" appears only when he says it. The approved direction says \"très "
                  "posé\": that is played in the face and in the pause, not in a slow voice, which makes him "
                  "robotic."),
        "fr_acting": ("Regard fixe et impassible, en silence, pendant 1,2 s, avec un lent clignement. Puis, précis "
                      "et amusé, sur un ton de conversation : « Elle t'éclaire. », une toute petite pause, et "
                      "« Nuance. » posé net, la voix qui descend, comme un point final. Un seul geste : le coin de "
                      "sa bouche se relève après « Nuance. » ; il tient ce petit sourire 0,7 s jusqu'à la coupe "
                      "finale. Impassible dans le visage, vivant dans la voix."),
        "fr_listener": "Pico est hors champ.",
        "fr_camera": ("Lent zoom avant d'environ 12 à 15 % sur tout le plan, seul mouvement de caméra du film. Le "
                      "clip est généré en plan fixe et le zoom est fait au montage ; solution de repli (prise "
                      "11 bis) : demander au modèle un zoom avant très lent."),
        "fr_sfx": ("Aucun : la musique s'arrête sur la coupe d'entrée dans ce plan ; le regard et la réplique se "
                   "jouent dans le silence."),
        "fr_notes": ("Chute et fin du film (comme le dernier plan de la référence 1 : regard silencieux, réplique, "
                     "léger sourire). « Nuance. » est le mot de la chute : ni avalé, ni lancé comme une question. "
                     "Sous-titre en deux temps : « Nuance. » n'apparaît qu'au moment où il le dit. L'indication "
                     "validée dit « très posé » : on le joue dans le visage et dans la pause, pas dans une voix "
                     "lente, qui le rend robotique."),
    },
]

# Extra takes that need no extra still. "required" = always made (9b is the sound of shot 9).
SAFETY_TAKES = [
    {"id": "2b", "setup": "nox_soudure", "speaker": "nox", "line_id": "l02", "text": LINES["l02"]["text"],
     "request_s": 6, "required": False,
     "purpose": ("Whole line l02 in one clip on the soldering close-up. With take 7b it replaces shots 2, 3 and 7 "
                 "(and shot 6 is dropped) if the two-shot still or its lip-sync fails."),
     "fr": ("toute la réplique l02 sur `nox_soudure`, en un seul clip. Avec la prise 7 bis, elle remplace les "
            "plans 2, 3 et 7 si le plan à deux échoue ; le plan 6 disparaît alors et le film tombe à 30 s "
            "environ : on rallonge les silences des plans 2 et 11.")},
    {"id": "4b", "setup": "nox_face", "speaker": "nox", "line_id": "l02b", "text": LINES["l02b"]["text"],
     "request_s": 6, "required": False,
     "purpose": ("The tease l02b on the approved frontal image of Nox. Spare take of shot 4, and the Nox clip of "
                 "the voice tests (V1)."),
     "fr": "l02b sur l'image validée de Nox (resserrée). C'est aussi le clip de Nox des essais de voix."},
    {"id": "7b", "setup": "nox_soudure", "speaker": "nox", "line_id": "l02d", "text": LINES["l02d"]["text"],
     "request_s": 5, "required": False,
     "purpose": ("Shot 7's line on the soldering close-up. Used when shot 6 is dropped or in the cut without the "
                 "two-shot (2b, no shots 3 and 6): in both cases ots_nox would otherwise come twice in a row for "
                 "Nox. Also used if ots_nox fails."),
     "fr": ("« Bon. Laisse-moi t'expliquer. » sur le gros plan de la soudure. Sert si on retire le plan 6, au "
            "montage sans plan à deux (avec la prise 2 bis), ou si l'image par-dessus l'épaule échoue.")},
    {"id": "8b", "setup": "nox_face", "speaker": "nox", "line_id": "l03", "text": "Regarde de plus près.",
     "request_s": 5, "required": False,
     "purpose": ("Shot 8 without the hand and without any glint (a finger next to thin glasses is the riskiest "
                 "gesture of the film): he leans in very slightly. The glint is then only a sound in the edit. "
                 "Make it anyway and choose in the edit."),
     "fr": ("« Regarde de plus près. » sans la main et sans reflet (il se penche un peu vers nous) ; le reflet "
            "n'est alors qu'un son ajouté au montage.")},
    {"id": "9b", "setup": "ots_nox", "speaker": "nox", "line_id": "l03",
     "text": "Ta montre envoie de la lumière verte… dans ta peau.", "request_s": 6, "required": True,
     "purpose": ("REQUIRED: the sound of shot 9. Shot 9's sentence with Nox on screen; its sound is laid over the "
                 "silent picture of shot 9, where no mouth is visible. Last resort only: the take replaces the "
                 "shot, picture and sound."),
     "fr": ("obligatoire, c'est le son du plan 9. La deuxième phrase de l03 sur `ots_nox`, avec Nox à l'image ; "
            "le son de cette prise est posé sur l'image muette du plan 9. En dernier recours, la prise remplace "
            "le plan, image et son.")},
    {"id": "11b", "setup": "nox_tgp", "speaker": "nox", "line_id": "l04b", "text": "Elle t'éclaire. Nuance.",
     "request_s": 6, "required": False,
     "purpose": ("Plan B for the punchline, only if the push-in made in the edit looks too soft at 720p: the same "
                 "shot with the push-in made by the model."),
     "fr": ("la chute avec le zoom avant fait par le modèle, seulement si le zoom fait au montage paraît trop "
            "flou.")},
]

MUSIC = ("A discreet, slow lo-fi loop (soft bass, no lead melody, no vocals), mixed about 16 dB under the voices, "
         "entering just after the door bang and cut dead on the cut into shot 11 so that the stare and the "
         "punchline play over silence.")
FR_MUSIC = ("Une boucle lo-fi lente et discrète (basse douce, pas de mélodie en avant, pas de voix), mixée environ "
            "16 dB sous les voix ; elle entre juste après le claquement de porte et s'arrête net sur la coupe "
            "d'entrée dans le plan 11, pour que le regard et la chute se jouent dans le silence.")
SOUND_BED = ("The clips are generated with the voice only (no room tone asked of the model: eleven generated "
             "ambiences would change at every cut and would spoil a later voice-change pass). One continuous, very "
             "quiet room tone is laid under the whole film in the edit, with the sound effects listed shot by shot.")
FR_SOUND_BED = ("Les clips sont générés avec la voix seule : on ne demande plus d'ambiance au modèle (onze ambiances "
                "différentes changeraient à chaque coupe et gêneraient un éventuel changement de voix). Une seule "
                "ambiance de pièce, très discrète et continue, est posée sous tout le film au montage, avec les "
                "bruitages listés plan par plan.")

# Decisions taken while applying the two reviews (English for the json, French for the owner's document).
DECISIONS = [
    ("Teaser, accepted as such: the hook asks why the watch makes green lights and the film ends on \"Nuance.\" "
     "(l04b), before the answer, which starts at l05. The comedy closes, the question does not: the sketch is a "
     "part 1. The follow-up is announced outside the 4:3 picture (post text or pinned comment), and l05 to l07 are "
     "the material of a second sketch. No line changes. Owner to confirm."),
    ("Style master: where the two approved images differ in rendering (nox_ref is grittier and more pixel-edged, "
     "pico_ref smoother), new stills follow nox_ref: only shot 1, in the hallway, then keeps the smoother look. "
     "Owner may overrule before the stills are made (STYLE_MASTER in the build scripts)."),
    ("Stills in dependency order: deux_etabli first (3 or 4 candidates, the owner picks one), together with "
     "nox_tgp; then the four others with the approved deux_etabli as an extra reference (same room, same props, "
     "same poses). Stills are generated at 1K."),
    ("Shot 7 is played on ots_nox, not on the soldering close-up: Pico's wrist and watch are in front of Nox in "
     "shots 3, 4 and 6 and would vanish on a frame without her. The other fix that was proposed (she snatches her "
     "wrist back during the silent shot 6) was not kept: it adds a large arm move to the only frame with two "
     "faces, and fails if shot 6 is dropped."),
    ("Shot 8: the start image is nox_ref tightened by a 1.2x crop, which takes the dismantled watch lying on the "
     "bench out of the frame; the line comes first, the glasses gesture after it."),
    ("Shot 9: the picture is generated silent and the sound always comes from take 9b (Nox on screen). Pico's "
     "double-take is played once: eyes round on the watch in shot 9, the look up to Nox on \"quoi ?!\" in shot 10."),
    ("Pico answers tit for tat (no held silence before \"J'ai jamais regardé dessous, ok ?\"); the only silence of "
     "the middle of the film is shot 6. Nox always speaks at full voice (no whisper, no hush)."),
    ("Captions: one card per shot; two timed cards in shots 4, 9 and 11, so that the second half of the line is "
     "not readable before the pause that protects it."),
    ("Sound: clips are generated with the voice only; shots 6 and 9 with generate_audio off. Room tone, sound "
     "effects and music are laid in the edit."),
]
FR_DECISIONS = [
    ("**Un sketch qui pose la question sans y répondre, et c'est assumé.** L'accroche demande pourquoi la montre "
     "fait des lumières vertes, et le film s'arrête sur « Nuance. » (l04b), avant la réponse, qui commence à l05. "
     "La comédie se referme, la question non : c'est une partie 1. La suite s'annonce hors de l'image (texte de la "
     "publication ou commentaire épinglé), et l05 à l07 feront un deuxième sketch. Aucune réplique n'est modifiée. "
     "À confirmer."),
    ("**Quelle image fait référence pour le rendu.** Les deux images validées n'ont pas tout à fait le même "
     "rendu : celle de Nox a plus de grain et des bords plus « pixel », celle de Pico est plus lisse. Par défaut, "
     "les nouvelles images suivent celle de Nox : seul le plan 1, dans le couloir, garde alors le rendu plus "
     "lisse. À confirmer avant de créer les images."),
    ("**Les images dans l'ordre.** D'abord le plan à deux (3 ou 4 essais, on en choisit un), en même temps que le "
     "très gros plan de Nox ; ensuite les quatre autres, avec le plan à deux validé comme modèle supplémentaire "
     "(même pièce, mêmes objets, mêmes poses). Les images sont créées en 1K, pas en 2K."),
    ("**Le plan 7 se joue par-dessus l'épaule de Pico**, et non plus sur le gros plan de la soudure : son poignet "
     "et sa montre sont devant Nox aux plans 3, 4 et 6, et ils disparaîtraient sur une image où elle n'est pas. "
     "L'autre correction proposée (elle retire brusquement son poignet pendant le plan muet) n'a pas été retenue : "
     "elle ajoute un grand geste dans le seul cadre à deux visages, et ne marche plus si on retire le plan 6."),
    ("**Plan 8.** L'image de départ est l'image validée de Nox, resserrée : la montre démontée posée sur l'établi "
     "sort du cadre. Il dit sa réplique d'abord, et remonte ses lunettes ensuite."),
    ("**Plan 9.** L'image est générée sans son ; la voix vient toujours de la prise 9 bis, où Nox est à l'image. "
     "Le double regard de Pico n'est joué qu'une fois : ses yeux s'arrondissent sur la montre au plan 9, et elle "
     "ne lève les yeux vers Nox que sur « quoi ?! », au plan 10."),
    ("**Pico répond du tac au tac** (plus de silence avant « J'ai jamais regardé dessous, ok ? ») ; le seul "
     "silence du milieu du film est le plan 6. **Nox parle toujours à pleine voix** (ni chuchotement, ni voix "
     "basse)."),
    ("**Sous-titres.** Un carton par plan ; deux cartons qui se suivent aux plans 4, 9 et 11, pour que la fin de "
     "la réplique ne se lise pas avant la pause qui la protège."),
    ("**Son.** Les clips sont générés avec la voix seule ; les plans 6 et 9 sans aucun son. L'ambiance, les "
     "bruitages et la musique sont posés au montage."),
]

OPEN_QUESTIONS = [
    ("Voice: does an audio reference make the character speak in that exact voice, clip after clip, and how good "
     "is the French? Tested before anything else with the two approved images only: batch A (8 clips: l01 on "
     "pico_porte and l02b on nox_face, on seedance_2_0 and seedance_2_5, with and without the voice sample), batch "
     "A2 (8 clips: the two other ways of attaching the sample), then batch B on the winner (9 clips: repeat, "
     "another line, a control, the line itself as audio, and 4 s against 6 s). Details in prompts.json "
     "(voice_test) and runbook.md."),
    ("Voice samples: are there clean recordings of 11-13 s, without music, of the two validated voices (Nox: "
     "Umbriel, Pico: Laomedeia)? seedance_2_0 only takes audio references of 2-15 s. Texts and rules: prompts.json "
     "(tts_samples)."),
    ("If the voices still drift from clip to clip, is a voice-change pass after generation acceptable (same "
     "timing, so the lips still match)? Its cost and its availability during the trial must be read first: the "
     "trial gives no credits and the balance is 10."),
    ("Style master: nox_ref by default (see decisions). Confirm, or choose pico_ref."),
    ("Teaser: the film ends before the answer to its own hook (see decisions). Confirm, and say where the "
     "follow-up is announced."),
    ("An alternative shot 10 would need one more still: the side two-shot again, with Pico recoiled, arm "
     "outstretched, and Nox sipping his coffee, the mug hiding his mouth (from the comedy-first proposal). Wanted?"),
    ("Length: {total} s estimated from syllable counts (expect 30-36 s with generated speech). If the cut lands "
     "under 30 s, lengthen the silent beats of shots 2, 6 and 11 rather than add a shot?"),
    ("The room will not match perfectly from one angle to the next (it does not in reference 2 either): acceptable "
     "as long as the characters, the props and the screen direction hold?"),
    ("Captions: white with a dark outline at the bottom (reference 1), one card per shot and two timed cards in "
     "shots 4, 9 and 11, with \"ok\" kept in lower case as in the approved text?"),
    ("Trial: it needs a card and renews automatically at 75 EUR unless the renewal is cancelled within the three "
     "days. Starting it and cancelling the renewal are the owner's decisions; nothing was started."),
]
FR_OPEN_QUESTIONS = [
    ("Voix : un échantillon de voix donné au modèle fait-il vraiment parler le personnage avec cette voix, d'un "
     "clip à l'autre, et le français est-il bon ? On le teste avant tout le reste, avec les deux images validées "
     "seulement : lot A (8 clips : l01 sur l'image de Pico et l02b sur l'image de Nox, sur seedance_2_0 et sur "
     "seedance_2_5, avec et sans échantillon de voix), lot A2 (8 clips : les deux autres façons de joindre "
     "l'échantillon), puis lot B sur la formule gagnante (9 clips : la même prise refaite, une autre réplique, un "
     "témoin, la réplique elle-même donnée comme son, et 4 s contre 6 s). Le détail est dans `runbook.md`."),
    ("Échantillons de voix : existe-t-il un enregistrement propre de 11 à 13 s, sans musique, de chacune des deux "
     "voix validées (Nox : Umbriel, Pico : Laomedeia) ? seedance_2_0 n'accepte que des échantillons de 2 à 15 s. "
     "Les textes à enregistrer sont dans `prompts.json`."),
    ("Si les voix changent encore d'un clip à l'autre, accepte-t-on de passer les clips dans un changeur de voix "
     "après coup (même rythme, donc les lèvres restent calées) ? Son prix et sa disponibilité pendant l'essai "
     "gratuit sont à lire d'abord : l'essai ne donne aucun crédit et le solde est de 10."),
    ("Rendu de référence : l'image de Nox par défaut (voir les décisions). À confirmer, ou choisir celle de Pico."),
    ("Partie 1 : le film s'arrête avant la réponse à sa propre accroche (voir les décisions). À confirmer, et dire "
     "où l'on annonce la suite."),
    ("Une variante du plan 10 demanderait une image de plus : le plan à deux de profil, avec Pico qui a bondi en "
     "arrière, bras tendu, et Nox qui boit son café, la tasse devant la bouche (idée de la proposition "
     "« comédie »). La veut-on ?"),
    ("Durée : {total} s estimées d'après le nombre de syllabes (attendu : 30 à 36 s avec les voix générées). Si le "
     "montage tombe sous 30 s, rallonge-t-on les silences des plans 2, 6 et 11 plutôt que d'ajouter un plan ?"),
    ("Le décor ne sera pas parfaitement identique d'un angle à l'autre (il ne l'est pas non plus dans la "
     "référence 2) : acceptable tant que les personnages, les objets et le sens des regards tiennent ?"),
    ("Sous-titres : blancs cernés de sombre, en bas (référence 1), un carton par plan et deux cartons aux plans 4, "
     "9 et 11, avec « ok » en minuscules comme dans le texte validé ?"),
    ("Essai gratuit : il demande une carte bancaire et se renouvelle tout seul à 75 EUR si le renouvellement "
     "n'est pas annulé dans les trois jours. Le lancer et annuler le renouvellement sont des décisions du "
     "propriétaire ; rien n'a été lancé."),
]

# ---------------------------------------------------------------- vérifications

setup_ids = [s["id"] for s in SETUPS]
assert len(set(setup_ids)) == len(setup_ids)
new_stills = [s["id"] for s in SETUPS if s["start_image"] == "new"]
assert len(new_stills) <= 6, new_stills
assert all(s["start_image"] in ("nox_ref", "pico_ref", "new") for s in SETUPS)
first_batch = [s["id"] for s in SETUPS if s["make_order"] == 1]
second_batch = [s["id"] for s in SETUPS if s["make_order"] == 2]
assert sorted(first_batch + second_batch) == sorted(new_stills)
for s in SETUPS:
    if s["make_order"] == 1:
        assert "deux_etabli" not in s["references"], s["id"]          # the first batch cannot depend on it
    if s["make_order"] == 2:
        assert s["references"][-1] == "deux_etabli", s["id"]
for sp in SPARE_STILLS:
    assert sp["replaces"] in new_stills and sp["id"] not in setup_ids

parts = {}
for sh in SHOTS:
    assert sh["setup"] in setup_ids, sh["n"]
    assert sh["request_s"] in (5, 6), sh["n"]
    assert sh["speaker"] in ("nox", "pico", "none")
    assert "fr_sfx" in sh and "sfx" in sh, sh["n"]
    if sh["speaker"] == "none":
        assert sh["line_id"] == "" and sh["text"] == ""
        continue
    line = LINES[sh["line_id"]]
    assert line["who"] == sh["speaker"], (sh["n"], line["who"])
    assert sh["text"] in line["text"], sh["n"]
    parts.setdefault(sh["line_id"], []).append(sh["text"])
for lid, ps in parts.items():
    assert " ".join(ps) == LINES[lid]["text"], (lid, ps)       # texte validé, mot pour mot
ids = list(LINES)
used = list(parts)
assert used == ids[ids.index(used[0]): ids.index(used[-1]) + 1], used    # aucune réplique sautée
assert [sh["n"] for sh in SHOTS] == list(range(1, len(SHOTS) + 1))
for n, cards in CARDS.items():
    assert " ".join(cards) == SHOTS[n - 1]["text"], n                    # les cartons redonnent la réplique
for t in SAFETY_TAKES:
    assert t["setup"] in setup_ids and t["text"] in LINES[t["line_id"]]["text"], t["id"]
    assert LINES[t["line_id"]]["who"] == t["speaker"], t["id"]

# jamais le même cadrage deux fois de suite sur le même personnage, ni sur deux plans qui se suivent
ON_SCREEN = {"pico_porte": {"pico"}, "nox_soudure": {"nox"}, "deux_etabli": {"nox", "pico"}, "ots_nox": {"nox", "pico"},
             "pico_gp": {"pico"}, "nox_face": {"nox"}, "pico_yeux_montre": {"pico"}, "nox_tgp": {"nox"}}


def no_repeat(seq_of_setups):
    for who in ("nox", "pico"):
        seq = [s for s in seq_of_setups if who in ON_SCREEN[s]]
        assert all(a != b for a, b in zip(seq, seq[1:])), (who, seq)
    assert all(a != b for a, b in zip(seq_of_setups, seq_of_setups[1:]))


no_repeat([sh["setup"] for sh in SHOTS])
no_repeat([("nox_soudure" if sh["n"] == 7 else sh["setup"]) for sh in SHOTS if sh["n"] != 6])   # sans le plan muet : 7b
no_repeat(["pico_porte", "nox_soudure", "ots_nox", "pico_gp", "nox_soudure", "nox_face",
           "pico_yeux_montre", "pico_gp", "nox_tgp"])                                       # montage sans plan à deux (2b, 7b)

total = round(sum(sh["est_s"] for sh in SHOTS), 1)
assert 30 <= total <= 45, total
assert sum(1 for sh in SHOTS if sh["est_s"] > 4.0) <= 1
both = round(sum(sh["est_s"] for sh in SHOTS if len(ON_SCREEN[sh["setup"]]) == 2), 1)
no_two_shot = round(total - SHOTS[1]["est_s"] - SHOTS[2]["est_s"] - SHOTS[5]["est_s"] + 4.2, 1)
OPEN_QUESTIONS = [q.replace("{total}", str(total)) for q in OPEN_QUESTIONS]
FR_OPEN_QUESTIONS = [q.replace("{total}", str(total).replace(".", ",")) for q in FR_OPEN_QUESTIONS]

# ---------------------------------------------------------------- shotlist.json

SILENT_PICTURE = {6: "", 9: "9b"}      # shots generated with generate_audio off; value = take whose sound is used


def cards_of(sh):
    if not sh["text"]:
        return []
    return [caption(c) for c in CARDS.get(sh["n"], [sh["text"]])]


END = SHOTS[-1]["line_id"]
out = {
    "title": "Nox & Pico — « Elle t’éclaire. Nuance. » (sketch IA, début de l’épisode 1)",
    "version": 2,
    "end_line_id": END,
    "est_total_s": total,
    "format": "4:3",
    "style_master": STYLE_MASTER,
    "decisions": DECISIONS,
    "setups": [{k: s[k] for k in ("id", "framing", "description", "start_image", "start_file", "references",
                                  "make_order")} for s in SETUPS],
    "spare_stills": [{k: s[k] for k in ("id", "replaces", "references", "when", "description")} for s in SPARE_STILLS],
    "shots": [],
    "safety_takes": [{k: t[k] for k in ("id", "setup", "speaker", "line_id", "text", "request_s", "required",
                                        "purpose")} for t in SAFETY_TAKES],
    "music": MUSIC,
    "sound_bed": SOUND_BED,
    "open_questions": OPEN_QUESTIONS,
}
for sh in SHOTS:
    d = {"n": sh["n"], "setup": sh["setup"], "speaker": sh["speaker"], "line_id": sh["line_id"], "text": sh["text"],
         "caption": cards_of(sh), "est_s": sh["est_s"], "request_s": sh["request_s"],
         "pre_beat_s": sh["pre_beat_s"], "generate_audio": sh["n"] not in SILENT_PICTURE,
         "audio_from": SILENT_PICTURE.get(sh["n"], ""), "acting": sh["acting"], "listener": sh["listener"],
         "camera": sh["camera"], "sfx": sh["sfx"], "notes": sh["notes"]}
    out["shots"].append(d)
with open(os.path.join(HERE, "shotlist.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

# ---------------------------------------------------------------- shotlist.md (français)


def fr(t):
    """Espaces insécables de la typographie française."""
    t = t.replace("« ", "«" + NBSP).replace(" »", NBSP + "»")
    t = re.sub(r" (?=[?!;:])", NBSP, t)
    t = re.sub(r"(?<=\d) (?=(s|m|cm|dB|%)\b)", NBSP, t)
    t = re.sub(r"(?<=\d) %", NBSP + "%", t)
    return t.replace("'", "’")


def num(x):
    return (f"{x:.2f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)).replace(".", ",")


WHO = {"nox": "Nox", "pico": "Pico", "none": "personne (plan muet)"}
IMG = {"nox_ref": "image validée de Nox, resserrée", "pico_ref": "image validée de Pico, telle quelle",
       "new": "nouvelle image à créer"}
used_in = {s["id"]: [sh["n"] for sh in SHOTS if sh["setup"] == s["id"]] for s in SETUPS}
share = both / total
share_fr = "un tiers" if 0.29 <= share <= 0.37 else ("un quart" if share < 0.29 else "près de la moitié")

L = []
L.append("# Découpage final — « Elle t'éclaire. Nuance. »")
L.append("")
L.append("Sketch tiré du début de l'épisode 1 de Nox & Pico, entièrement fabriqué par IA, dans le style des deux "
         "sketches de référence. Rien n'a été généré : ce document est un plan. Version 2, corrigée après deux "
         "relectures ; la marche à suivre pendant les trois jours d'essai est dans `runbook.md`.")
L.append("")
L.append(f"- **Durée estimée : {num(total)} s** (attendu : 30 à 36 s selon le débit des voix générées).")
L.append(f"- **{len(SHOTS)} plans**, tous en coupe franche, dont un plan muet de {num(SHOTS[5]['est_s'])} s.")
L.append(f"- **{len(SETUPS)} cadrages** : les 2 images validées (celle de Pico telle quelle, celle de Nox "
         f"resserrée) et {len(new_stills)} nouvelles images à créer ; {len(SPARE_STILLS)} images de secours sont "
         "prévues, à créer seulement en cas d'échec.")
L.append("- **Début** : l01 (« Nox ! Pourquoi ma montre fait des lumières vertes à la fin de mon run ? »). "
         "**Fin** : l04b (« Elle t'éclaire. Nuance. »).")
L.append("- **Texte** : les répliques validées, mot pour mot. Deux répliques (l02 et l03) sont réparties sur deux "
         "plans, coupées à la fin d'une phrase.")
L.append(f"- **Les deux personnages ensemble à l'image** : {num(both)} s sur {num(total)} s, soit environ "
         f"{share_fr} du film. Les références sont à plus de la moitié, mais chaque plan qui montre deux visages "
         "est un risque pour les lèvres : ici, un seul plan parlé en montre deux.")
L.append("- Format 4:3. Sous-titres, musique et bruitages sont ajoutés au montage : aucune image ni aucun clip "
         "généré ne doit contenir de texte ou de musique.")
L.append("- Le même plan, en anglais et prêt pour l'écriture des consignes : `shotlist.json`, dans le même "
         "dossier ; les consignes elles-mêmes : `prompts.json`.")
L.append("")
L.append("## Décisions prises après les deux relectures")
L.append("")
for d in FR_DECISIONS:
    L.append(f"- {d}")
L.append("")
L.append("## Les trois propositions, notées sur 10")
L.append("")
L.append("| Critère | A — copie de la référence | B — comédie d'abord | C — risque minimal |")
L.append("|---|---|---|---|")
SCORES = [("Fidélité à la grammaire des références", 9, 8, 5), ("Comédie", 7, 9, 5),
          ("Faisabilité en génération IA", 4, 5, 9), ("Respect du texte et des règles de la série", 7, 9, 7),
          ("Durée (30 à 45 s)", 7, 8, 7)]
for name, a, b, c in SCORES:
    L.append(f"| {name} | {a} | {b} | {c} |")
L.append(f"| **Total sur 50** | **{sum(s[1] for s in SCORES)}** | **{sum(s[2] for s in SCORES)}** | "
         f"**{sum(s[3] for s in SCORES)}** |")
L.append("")
L.append("- **A** suit la référence 1 presque plan par plan, mais demande 8 nouvelles images (6 au maximum), un "
         "plan large en pied, une pince à l'image, et coupe « Attends… quoi ?! Elle me scanne ?! » en deux clips "
         "de trois syllabes.")
L.append("- **B** a les meilleurs gags (la coupe qui la révèle affalée sur l'établi, « regarde de plus près » pris "
         "au pied de la lettre), mais demande aussi 8 nouvelles images, dont deux variantes de pose.")
L.append("- **C** est la plus sûre (3 nouvelles images, un seul visage par plan), mais ressemble à un appel "
         "vidéo : un seul plan sur dix montre les deux personnages, Nox ne soude plus, la chute réutilise un gros "
         "plan déjà vu deux fois.")
L.append("")
L.append("**Base retenue : B.** Ce qui est gardé, greffé, ajouté et écarté :")
L.append("")
DECISIONS_FR = [
    "Gardé de B : l'ossature du sketch ; la coupe qui révèle Pico déjà affalée sur l'établi ; la taquinerie en un "
    "seul plan par-dessus l'épaule ; Nox qui s'est déjà remis à son circuit avant « Bon. » ; le geste des lunettes "
    "sur l'image validée de Nox ; les yeux de Pico au ras de sa montre pendant que Nox parle hors champ ; la "
    "musique qui s'arrête sur la chute.",
    "Greffé de A : le gros plan de Nox à sa soudure est pris en contre-plongée depuis l'établi. Tête baissée, son "
    "visage est alors vu presque de face, ce qui aide les lèvres, et le cadre ne ressemble pas à l'image validée "
    "de Nox.",
    "Greffé de A : les pas de Pico, ajoutés au montage sous la seconde de silence du plan 2, couvrent son "
    "déplacement de la porte à l'établi. Personne ne marche à l'image.",
    "Greffé de C : « Attends… quoi ?! Elle me scanne ?! » reste entière, sur un gros plan de Pico seule ; une "
    "prise sans la main est prévue pour le geste des lunettes ; les essais de voix n'utilisent que les deux "
    "images validées ; chaque plan fragile a un plan de repli qui ne change rien au reste.",
    "Ajouté par la réalisation : le plan 6, un face-à-face muet de 1,3 s sur l'image du plan à deux, déjà créée. "
    "C'est le silence avant la réponse de Nox, et il remet les deux personnages à l'image au milieu du sketch.",
    "Écarté : l'ouverture l00 (autre décor, course à pied, et la même question que l01 un plan plus tard).",
    "Écarté faute d'images (6 nouvelles au maximum) : le recul de Pico en plan à deux pendant que Nox boit son "
    "café, et la moue de Pico qui se change en sourire. Le premier reste proposé en option (question 6).",
    "Écarté : le plan large en pied et la pince de A, Bip le drone, les émotions en pixels, tout objet tenu en "
    "main autre que le fer à souder.",
    "Les indications « calmement », « patient » et « très posé » du texte validé sont jouées dans le visage et les "
    "silences ; la voix de Nox est toujours demandée vive, amusée et à pleine voix.",
]
for d in DECISIONS_FR:
    L.append(f"- {d}")
L.append("")
L.append("## Les cadrages")
L.append("")
L.append("Sens des regards pour tout le film : Nox à gauche regarde vers la droite, Pico à droite regarde vers la "
         "gauche. La caméra reste toujours du même côté de la pièce (à la droite de Nox). Toutes les nouvelles "
         "images reprennent le rendu des images validées (aplats, contours nets, atelier de nuit) et ne "
         "contiennent aucun texte : les écrans montrent une simple lueur bleu pâle, les notes épinglées sont "
         "blanches. Une seule montre dans tout le film : celle que Pico porte au poignet gauche. Les lunettes de "
         "Nox ont des verres clairs : on voit toujours ses yeux.")
L.append("")
L.append("| Nom | Cadrage | Image de départ | Ce qu'on voit | Plans |")
L.append("|---|---|---|---|---|")
for s in SETUPS:
    L.append(f"| `{s['id']}` | {s['fr_framing']} | {IMG[s['start_image']]} | {s['fr_description']} | "
             f"{', '.join(str(n) for n in used_in[s['id']])} |")
L.append("")
L.append("### Images de secours (à créer seulement si nécessaire)")
L.append("")
for sp in SPARE_STILLS:
    L.append(f"- `{sp['id']}` : {sp['fr']}")
L.append("")
L.append("## Le découpage")
L.append("")
L.append("Dans la colonne des répliques, « → » sépare deux cartons de sous-titre qui se suivent dans le même plan.")
L.append("")
L.append("| N° | Cadrage | Qui parle | Réplique (texte du sous-titre) | Durée finale | Durée demandée | Silence avant |")
L.append("|---|---|---|---|---|---|---|")
for sh in SHOTS:
    cap = " → ".join(cards_of(sh)) if sh["text"] else "(plan muet)"
    who = WHO[sh["speaker"]] + (" (hors champ)" if sh["n"] == 9 else "")
    lid = f"{sh['line_id']} — " if sh["line_id"] else ""
    L.append(f"| {sh['n']} | `{sh['setup']}` | {who} | {lid}{cap} | {num(sh['est_s'])} s | {sh['request_s']} s | "
             f"{num(float(sh['pre_beat_s']))} s |")
L.append(f"| | | | **Total** | **{num(total)} s** | | |")
L.append("")
L.append("## Jeu, caméra et son, plan par plan")
L.append("")
L.append("| N° | Jeu de celui qui parle | L'autre personnage | Caméra | Son ajouté au montage | Remarques |")
L.append("|---|---|---|---|---|---|")
for sh in SHOTS:
    L.append(f"| {sh['n']} | {sh['fr_acting']} | {sh['fr_listener']} | {sh['fr_camera']} | "
             f"{sh['fr_sfx'] or '—'} | {sh['fr_notes']} |")
L.append("")
L.append("## Musique et ambiance")
L.append("")
L.append(FR_MUSIC)
L.append("")
L.append(FR_SOUND_BED)
L.append("")
L.append("## Prises supplémentaires (aucune image en plus)")
L.append("")
for t in SAFETY_TAKES:
    L.append(f"- **Prise {t['id'].replace('b', ' bis')}** : {t['fr']}")
L.append("")
L.append(f"Montage sans plan à deux (prises 2 bis et 7 bis, plans 3 et 6 retirés) : environ {num(no_two_shot)} s.")
L.append("")
L.append("## Ordre de travail")
L.append("")
L.append("La marche à suivre complète, étape par étape, est dans `runbook.md`. En résumé :")
L.append("")
L.append("1. **Avant de lancer l'essai** : les deux échantillons de voix, les répliques enregistrées, les deux "
         "images de départ déjà prêtes, la lecture des réglages des modèles.")
L.append("2. **Essais de voix** : lot A (8 clips), lot A2 (8 clips), lot B (9 clips), avec les deux images "
         "validées seulement.")
L.append("3. **Les images** : d'abord " + " et ".join(f"`{i}`" for i in first_batch) + " ; puis, une fois le plan "
         "à deux validé, " + ", ".join(f"`{i}`" for i in second_batch) + ". Aucune vidéo avant qu'une image soit "
         "validée.")
L.append("4. **Les clips** : 9 plans parlés, la prise 9 bis, 2 plans sans son et 4 prises de rechange, 3 prises "
         "chacun, par lots de 8.")
L.append("5. **Montage** : choix des prises, coupes, silences, zoom du dernier plan, sous-titres, ambiance, "
         "musique, bruitages.")
L.append("")
L.append("## Questions ouvertes")
L.append("")
for i, q in enumerate(FR_OPEN_QUESTIONS, 1):
    L.append(f"{i}. {q}")
L.append("")
with open(os.path.join(HERE, "shotlist.md"), "w", encoding="utf-8") as fh:
    fh.write(fr("\n".join(L)))

print(f"{len(SHOTS)} plans, {len(SETUPS)} cadrages dont {len(new_stills)} nouvelles images "
      f"(+ {len(SPARE_STILLS)} de secours), total {total} s, les deux à l'image {both} s, "
      f"sans plan à deux {no_two_shot} s, fin {END}")
