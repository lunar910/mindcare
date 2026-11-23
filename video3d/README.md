# video3d : personnages 3D style cinématique PS2

Projet à part de l'appli MindCare : la fabrication des personnages et des images pour les sketchs vidéo
(rendu 4:3 basse définition, textures peintes, façon cinématique de jeu des années 2000).
Tout est généré par des scripts Python qui pilotent Blender, sans interface graphique.

## Réinstaller

    cd video3d
    bash setup.sh

Le script installe Blender (module Python `bpy`), récupère les données MakeHuman et télécharge les packs
d'éléments 3D (environ 1 Go, rangés dans des dossiers ignorés par git). Il faut un accès à
`files.makehumancommunity.org` : dans Claude Code, c'est l'environnement `mindcare-video-3d`.

## Rendre des images

    cd video3d/hero
    ../blender-venv/bin/python diag.py out room_close room_medium      # héros assis dans le salon
    ../blender-venv/bin/python diag.py out face_front hair_back body_front   # vues de contrôle en studio

La liste des vues est en tête de `hero/diag.py`. Une image 640x480 prend environ 10 secondes sur 4 cœurs.
`tools/grade.cjs` ajoute l'étalonnage et le sous-titre façon reel (Node + Playwright).

## Organisation du code (`hero/`)

| Fichier | Rôle |
| --- | --- |
| `cfg_face.py`, `cfg_hair.py`, `cfg_body.py`, `cfg_pose.py` | les réglages du perso, par domaine |
| `mh.py` | corps MakeHuman : morphologie, squelette, poids de peau, yeux, outils de pose |
| `mhassets.py` | ajuste les vêtements, chaussures et accessoires MakeHuman sur le corps |
| `da.py`, `face.py` | peau peinte (sourcils, cils, lèvres, ombres), yeux, expressions |
| `hairda.py` | cheveux en plaques de polygones et leur texture |
| `outfit.py` | tenue : recoloration, chaussures, accessoires |
| `posing.py` | poses (assis sur la banquette) et regard |
| `room_bl.py` | le salon marocain de nuit |
| `herolib.py`, `diag.py` | assemblage du perso et banc de rendu |

## Sources et licences

- Corps, squelette, peaux, vêtements, chaussures, poses : MakeHuman (https://static.makehumancommunity.org),
  éléments sous licence CC0, utilisables sans condition.
- Le personnage, sa peinture de visage, ses cheveux et le décor sont créés pour ce projet.
