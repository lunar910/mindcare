# Nox & Pico en 3D — style PS2 / pixel

Personnages et atelier créés avec **Meshy** (images de départ, modèles 3D, allègement, squelettes, animations),
puis mis en scène et rendus dans **Blender** (Cycles) avec un rendu « pixel art » : aplats d'ombre, contours d'un pixel,
image calculée en basse résolution (360×640) puis agrandie ×3 en 1080×1920.

## Contenu
- `scripts/atelier.py` — l'atelier de Nox (disposition de l'épisode 1) à partir des accessoires Meshy + murs, parquet, fenêtre, guirlande.
- `scripts/excerpt.py` — l'extrait de l'épisode 1 (entrée de Pico → « Bon. Laisse-moi t'expliquer. ») : plans, animations Meshy
  enchaînées, mains de Nox sur l'établi, regards, bouches et clignements par échange de texture (façon PS2).
- `scripts/excerpt_post.py` — passage en pixel art, sous-titres au style de la série (icônes, police Pixelify Sans, mots-clés verts), sons, MP4.
- `scripts/pxrender.py`, `scripts/pxpost.py` — réglages de rendu (passes) et recomposition « pixel cel ».
- `scripts/rigext.py` — ajout des os des doigts (bloc des doigts + pouce) au squelette Meshy.
- `scripts/facefx.py`, `scripts/facevar.py` — variantes de texture du visage (bouche entrouverte / ouverte / grande ouverte, yeux fermés).
- `scripts/procpose.py` — placement des mains et des regards à partir des articulations (les os Meshy ont des longueurs arbitraires).
- `meshy_taches.md` — identifiants des tâches Meshy pour retélécharger les modèles.

## Lancer
```
python excerpt.py -- out --fps 12 --samples 20          # rendu (Blender en module Python : bpy)
python excerpt_post.py frames out && python excerpt_post.py video out
```
Les chemins des modèles Meshy sont en tête de `atelier.py` et `excerpt.py`.
