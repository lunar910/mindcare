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

## Version 2 — rendu « cinématique PS2 » (dossier `ps2/`)

Refonte après le premier extrait (image trop sombre, mouvements saccadés, décor aux proportions incohérentes, son gênant).

**Ce qui change**
- **Rendu** : Cycles ne sert plus que de « rasteriseur » (1 échantillon par pixel, passes de données : couleur, normale, position,
  profondeur). L'éclairage est calculé ensuite en numpy comme sur une PS2 : lumière ambiante + quelques lampes, pas d'ombres
  portées, ombres rondes sous les pieds, léger halo des lampes, image interne 432×768 agrandie en 1080×1920.
  Le décor est rendu une fois par plan, les personnages à chaque image (≈ 1 s par image au lieu de 24 s) → 30 images/s.
- **Décor** (`atelier2.py`, `tex2.py`) : tout est à l'échelle réelle (porte 2,04 m, établi à hauteur de hanches, outils de 15–30 cm) ;
  le panneau d'outils, l'horloge et le tapis sont redessinés de face (les anciens étaient des images en perspective collées à plat) ;
  vraie ouverture de porte avec un couloir éclairé derrière.
- **Mise en scène** (`excerpt2.py`) : six plans (large, plan moyen de Pico, plan moyen de Nox, deux gros plans en champ / contrechamp,
  plan à deux), personnages sur la même ligne, focales longues pour garder les proportions.
- **Animation** (`anim2.py`, `cast2.py`) : clips Meshy échantillonnés à 30 Hz, lissés, recalés pour que les pieds restent sur la marque,
  fondus doux entre les clips, changements de pose faits hors champ ; mains de Nox toujours à portée de l'établi.
- **Son** (`post2.py`) : musique de la série, porte et pas ; plus de grésillement de fer à souder ; niveau réglé à −17 LUFS.
- `fix_hood.py` repeint la doublure verte de la capuche de Pico ; `check_video.py` et `motion_report.py` contrôlent les sauts d'image
  et les à-coups ; `meshy_pico_anim.py` a ajouté l'animation « Talk with Left Hand Raised » (3 crédits).

**Lancer**
```
python excerpt2.py statics out            # décor + occlusion ambiante de chaque plan (une fois, ~9 min)
python excerpt2.py frames out --frames 0:215   # images (lancer plusieurs plages en parallèle)
python post2.py video out                 # sous-titres + son -> MP4 30 i/s
python check_video.py out                 # contrôle
```
Aperçus : `apercus/v2_images_cles.jpg`, `apercus/v2_plans.jpg`, `apercus/v2_avant_apres.jpg`.

### Expressions du visage (`ps2/faceprep.py`, `ps2/landmarks.py`, `ps2/facemorph.py`)
Les modèles Meshy n'ont pas de squelette de visage. Les expressions sont donc fabriquées :
1. `faceprep.py` rend la tête de face (pose de repos) avec la position 3D de chaque pixel, puis `landmarks.py` (MediaPipe Face
   Landmarker, dans un environnement Python à part) y trouve 478 repères : yeux, sourcils, lèvres, contour ;
2. `facemorph.py` affine le maillage du visage, coupe les lèvres le long de la bouche, ajoute l'intérieur de la bouche et deux
   rangées de dents, puis crée des « shape keys » : sourcils (levés / froncés / tristes), yeux (écarquillés / plissés / fermés),
   sourire, moue, bouche étroite / large, mâchoire. Les yeux et sourcils étant peints sur la texture, déplacer la surface les déplace.
3. `excerpt2.py` : piste d'expressions par personnage (`FACE`), formes de bouche tirées du texte (`MOUTH`), clignements.

`anim2.retarget` rejoue une animation Meshy sur un autre squelette Meshy (écart moyen ~3°) : pas besoin de racheter les clips.

Aperçus : `apercus/v2_expressions.jpg` ; essais de personnages réalistes (style de la vidéo de référence) : `apercus/v3_concepts_realistes.jpg`.

## Version 3 — personnages réalistes, éclairage de nuit, décor enrichi (`ps2/excerpt3.py`)

Après la vidéo de référence fournie (cinématique façon PS2 avec personnages réalistes, visages expressifs, décor riche) :
- **Personnages** : Nox et Pico refaits dans un style réaliste (proportions adultes, visage peint, cheveux anguleux).
  Dessins de départ par `ps2/meshy_t2i.py` / `ps2/meshy_i2i.py` (textes dans `ps2/prompts/`), puis `ps2/meshy_char3d.py`
  (image → 3D texturé en T-pose → allègement à 80 000 triangles → squelette). Identifiants dans `meshy_taches.md`.
- **Animations** : celles des premiers modèles, rejouées sur les nouveaux squelettes (`anim2.retarget`), sans rachat.
- **Expressions** : `faceprep.py` + `facemorph.py` sur les nouveaux modèles ; piste `FACE` dans `excerpt3.py`.
- **Lumière** : pièce sombre et froide, une lumière principale chaude qui projette de vraies ombres (carte d'ombres :
  `ps2render.shadow_setup` / `render_shadow`, `ps2shade.shadow`), personnages plus éclairés que le décor.
- **Décor** (`decor3.py`) : suspension au premier plan, meuble sous la fenêtre (radio, livres, cactus), caisse à outils,
  étagère au-dessus de la porte, couloir habillé (tableau, applique, porte-manteau avec veste et casquette).

```
./run_v3.sh                      # décors des plans puis les 648 images (3 processus)
python post2.py video out_v3 Nox-et-Pico-ep01-extrait-3D-v3.mp4
```
Aperçus : `apercus/v3_images_cles.jpg`, `apercus/v3_expressions.jpg`.
