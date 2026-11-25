# Marche à suivre — les 3 jours d'essai

Sketch « Elle t'éclaire. Nuance. » (début de l'épisode 1 de Nox & Pico), 11 plans, environ 32 s, format 4:3.

Ce document dit quoi faire, dans quel ordre, et comment décider à chaque étape. Rien n'a encore été généré.

- Le découpage (en français) : `shotlist.md`. Les mêmes données pour les outils : `shotlist.json`.
- Toutes les consignes à copier, mot pour mot : `prompts.json`.
- L'outil de montage : `montage.py`, et son fichier de montage déjà rempli : `edit_modele.json`.

**Trois règles qui ne changent jamais**

1. Le texte des répliques ne se réécrit pas. On peut couper une réplique en deux clips à une pause écrite ; on ne change aucun mot.
2. Une consigne de clip ne contient qu'une seule paire de guillemets : celle de la réplique. Tout autre mot entre guillemets risque d'être prononcé.
3. Aucune image, aucun clip ne doit contenir de texte, de sous-titre ou de musique. Tout cela s'ajoute au montage.

**Ce qui n'a pas pu être vérifié avant l'essai** (c'est l'objet des étapes 0.2 et 1)

- Un échantillon de voix fait-il parler le personnage avec cette voix ? Et faut-il le joindre d'une façon particulière ?
- Le français des deux modèles vidéo est-il bon ?
- La taille « 1K » et trois images de référence à la fois sont-elles acceptées par le modèle d'images ?
- Le changeur de voix est-il utilisable pendant l'essai, et à quel prix ? L'essai ne donne aucun crédit ; le solde est de 10 crédits.

---

## 0. Avant de lancer l'essai (le chronomètre ne tourne pas encore)

Tout ce qui suit se fait sans l'essai gratuit. Plus cette étape est complète, plus les trois jours servent à générer.

### 0.1 Quatre décisions du propriétaire

| Question | Choix par défaut si rien n'est dit |
|---|---|
| Le film s'arrête sur « Nuance. », avant la réponse à la question de départ. C'est une partie 1 : d'accord ? | Oui. La suite est annoncée dans le texte de la publication. |
| Les deux images validées n'ont pas tout à fait le même rendu. Laquelle fait référence ? | Celle de Nox (plus de grain, bords plus « pixel »). Seul le plan 1 garde alors le rendu plus lisse de l'image de Pico. |
| Si les voix changent d'un clip à l'autre, accepte-t-on un changement de voix après coup ? | Oui, si son prix tient dans les 10 crédits ; sinon on en reparle. |
| Qui lance l'essai, et qui annule le renouvellement automatique ? | Le propriétaire, lui-même. L'essai demande une carte bancaire et prélève 75 EUR hors taxes s'il n'est pas annulé dans les 3 jours. |

Si le rendu de référence devient l'image de Pico : mettre `STYLE_MASTER = "pico_ref"` en haut de `build_shotlist.py`, puis relancer `python3 build_shotlist.py` et `python3 build_prompts.py`.

### 0.2 Lire les réglages des modèles (lecture seule, gratuit)

Ouvrir la fiche des modèles `seedance_2_5`, `seedance_2_0` et `nano_banana_2_1` dans le catalogue, et noter les réponses :

1. Dans une consigne, comment désigne-t-on un fichier joint : par des mots (« the audio reference ») ou par une étiquette (du type `@Audio1`) ?
2. Un échantillon de voix doit être accompagné d'une image. L'image de départ (`start_image`) suffit-elle, ou faut-il joindre aussi une image de référence (`image_references`) ?
3. Le nom exact du réglage qui coupe le son (`generate_audio`) et les durées permises.
4. `nano_banana_2_1` propose-t-il la taille 1K ? Combien d'images de référence accepte-t-il ? (Il en faut trois pour `ots_nox`.)
5. Le changeur de voix : est-il compris dans l'essai ? Son prix à la seconde ? Le prix d'une voix sur mesure faite à partir d'un échantillon ?

Si les points 1 et 2 ont une réponse nette, on peut sauter le lot A2 de l'étape 1. Au moindre doute, on le fait.

### 0.3 Les deux échantillons de voix

Ils servent de modèle de voix pour tous les clips. Ils se fabriquent avec les voix validées de la série (Gemini, « Umbriel » pour Nox, « Laomedeia » pour Pico), comme d'habitude, hors de Higgsfield.

1. Prendre les deux textes dans `prompts.json`, rubrique `tts_samples` (champ `text`), et l'indication de jeu en français (champ `dir_fr`).
2. Fabriquer chaque texte deux ou trois fois. Garder une seule prise par personnage, la plus vivante. Ne pas coller des morceaux de prises différentes.
3. Vérifier chaque fichier :
   - durée entre 11 et 13 s, jamais plus de 14 s (un des deux modèles n'accepte que 2 à 15 s) ;
   - une seule voix, aucun bruit, aucune musique, aucune réverbération ;
   - Nox : vif, taquin, un sourire dans la voix, à pleine voix. S'il est lent ou posé, on refait : cette voix déteint sur tous les clips ;
   - Pico : pleine d'énergie, rapide, sans crier et sans essoufflement.
4. Enregistrer en WAV mono, sous les noms `voice/voice_nox.wav` et `voice/voice_pico.wav`. Ne plus jamais les modifier.

Les textes ont été écrits pour ne ressembler à aucune réplique du sketch : si on entend un mot de l'échantillon dans un clip, on le repère tout de suite.

### 0.4 Les répliques enregistrées avec les voix de la série

Elles servent à deux essais de l'étape 1 et aux plans de repli de l'étape 4. Liste et textes : `prompts.json`, rubrique `tts_lines`.

1. Si les enregistrements de ces répliques faits pour l'épisode en pixel art existent, les écouter d'abord : on réutilise ceux qui sont assez vivants.
2. Sinon, les fabriquer avec les mêmes voix. Une réplique répartie sur deux plans (l02 : plans 2 et 3 ; l03 : plans 8 et 9) se fabrique entière, puis se coupe à la fin de la première phrase : les deux moitiés ont alors la même voix et la même énergie.
3. Noms : `voice/line_01.wav`, `voice/line_02.wav`, … (un par plan parlé), et `voice/line_02b.wav` pour la réplique l02 entière.
4. Indispensables dès l'étape 1 : `line_04` (« Tu portes cette montre… ») et `line_01` (« Nox ! Pourquoi… »). Les autres peuvent attendre l'étape 4.

### 0.5 Les deux images de départ déjà prêtes

Commande : `python3 prep_refs.py` (déjà lancée une fois ; les deux fichiers existent).

- `stills/pico_porte.png` : l'image validée de Pico, sans transparence, rognée de quelques pixels pour être exactement en 4:3. Plan 1.
- `stills/nox_face.png` : l'image validée de Nox, resserrée sur le haut. La montre démontée posée sur l'établi sort du cadre. Plan 8 et essais de voix.

Les deux images validées d'origine (`refs/nox_ref.png`, `refs/pico_ref.png`) restent les modèles pour créer les nouvelles images.

### 0.6 Les sons du montage

Déjà disponibles (sons de l'épisode en pixel art, déjà inscrits dans `edit_modele.json`) : claquement de porte, pas, grésillement de soudure, petit tintement.

À trouver avant le jour 3, et à ranger dans `son/` :

- `ambiance.mp3` : une ambiance de pièce très discrète et continue, au moins aussi longue que le film ;
- `fracas.mp3` : un petit fracas de composants (les coudes de Pico qui atterrissent sur l'établi) ;
- `musique.mp3` : une boucle lo-fi lente et discrète, sans mélodie en avant, sans voix ;
- facultatifs : `souffle.mp3` (petit souffle amusé de Nox, par le nez) et `pulsation.mp3` (pulsation électronique douce).

### 0.7 Lancer l'essai

1. Le propriétaire lance l'essai gratuit de 3 jours. Noter l'heure exacte : c'est l'heure limite, trois jours plus tard.
2. D'après la notice de l'outil, on peut annuler le renouvellement tout de suite en gardant l'accès pendant les 3 jours. Ce n'est pas testé : si le propriétaire le fait, vérifier aussitôt que la génération marche encore.
3. Pendant l'essai : 8 demandes à la fois au maximum, un résultat par demande. Les modèles compris sont `seedance_2_5` et `seedance_2_0` jusqu'en 720p, et les modèles d'images. Tout le reste coûte des crédits.
4. Télécharger chaque résultat dès qu'il est jugé bon. Ne rien laisser seulement en ligne.

**Rangement des fichiers** (dans le dossier `ia_prod`)

| Quoi | Où |
|---|---|
| Essais de voix | `essais/V1.mp4`, `essais/W3.mp4`, `essais/B2.mp4`… |
| Essais d'une image | `stills/deux_etabli_c1.png`, `_c2`… ; l'image choisie : `stills/deux_etabli.png` |
| Prises d'un plan | `clips/s04_t1.mp4`, `clips/s04_t2.mp4`… ; la prise choisie : `clips/s04.mp4` |
| Prises supplémentaires | `clips/s09b_t1.mp4`… ; choisie : `clips/s09b.mp4` |

---

## 1. Jour 1, matin — l'essai de voix

**But.** Savoir si l'échantillon de voix fait vraiment parler le personnage avec cette voix, quel modèle parle le mieux français, et si la voix tient d'un clip à l'autre. Tout le reste en dépend.

**Avec quoi.** Les deux images de départ de l'étape 0.5 et les deux échantillons de voix. Aucune nouvelle image.

**Quelle réplique.** Une seule par personnage, toujours la même :

- Nox, sur `nox_face` : « Tu portes cette montre depuis deux ans… et tu découvres qu'elle s'allume ? »
- Pico, sur `pico_porte` : « Nox ! Pourquoi ma montre fait des lumières vertes à la fin de mon run ? »

Chaque bon clip de cet essai est gardé pour le film (plan 1 pour Pico, prise de rechange du plan 4 pour Nox).

### 1.1 Lot A — avec ou sans échantillon (8 demandes)

Consignes : `prompts.json`, rubrique `voice_test`, liste `batch_A` (V1 à V8). Chaque entrée donne le modèle, la durée, les fichiers à joindre et la consigne.

| | Avec l'échantillon | Sans (témoin) |
|---|---|---|
| Nox, `seedance_2_5` | V1 | V2 |
| Nox, `seedance_2_0` | V3 | V4 |
| Pico, `seedance_2_5` | V5 | V6 |
| Pico, `seedance_2_0` | V7 | V8 |

Réglages communs : 6 s, 720p, 4:3. Pour `seedance_2_5`, le mode `omni_reference` est obligatoire (sinon l'image de départ est ignorée). Pour `seedance_2_0`, pas de mode.

Dans une consigne « avec », on trouve les mots `with the voice of the audio reference,`. Ils vont avec le fichier de voix : on enlève les deux ensemble, jamais l'un sans l'autre.

### 1.2 Lot A2 — les deux autres façons de joindre l'échantillon (8 demandes)

Liste `batch_A2` (W1 à W8). À lancer juste après le lot A, sans attendre son verdict, sauf si l'étape 0.2 a tout tranché.

- W impairs : l'image de départ est jointe une seconde fois, comme image de référence.
- W pairs : la même chose, et la consigne désigne l'échantillon par son étiquette. L'étiquette `@Audio1` écrite dans ces consignes est un exemple : la remplacer par la forme exacte lue à l'étape 0.2. Si le catalogue ne parle d'aucune étiquette, ne pas lancer les W pairs.

Une demande refusée (« il faut une image de référence ») est aussi une réponse : on la note.

### 1.3 Comment écouter et regarder

Pour chaque clip, lancer `python3 montage.py qc essais/V1.mp4` : on obtient une planche d'images et le début et la fin de la parole.

Écouter dans cet ordre : l'échantillon, le clip « avec », le clip « sans ». Puis remplir cette grille.

| Point | Bon si… |
|---|---|
| Voix | on reconnaît la personne de l'échantillon (âge, hauteur, grain) |
| Français | accent de France, aucun accent étranger ; « Nox » avec le x prononcé ; « run » dit à la française ; « deux ans » avec la liaison (« deu-zan ») |
| Mots | exactement la réplique écrite ; rien d'ajouté, d'enlevé, de répété ; aucun mot de l'échantillon |
| Jeu de la voix | Nox vif, taquin, à pleine voix ; sa pause des points de suspension est courte (0,3 à 0,5 s), pas un ralentissement. Pico pressante, rapide mais claire |
| Son | pas de musique, pas de bruit inventé, pas d'écho ; la réplique finit au moins 0,5 s avant la fin du clip |
| Lèvres | bouche fermée avant le premier mot et après le dernier ; les lèvres se ferment sur p, b et m ; rien ne flotte à la fin |
| Image | le clip s'ouvre sur l'image de départ ; la caméra ne bouge pas ; pas de texte qui apparaît ; les écrans et les notes ne grouillent pas |
| Personnage | lunettes fines avec les yeux visibles, forme des cheveux, montre au poignet gauche, cinq doigts ; les aplats et les contours tiennent jusqu'au bout |

À écarter d'office : Nox lent, plat, à voix basse ou robotique ; Pico enfantine, « mignonne », criée ou lente.

### 1.4 Décider

1. **L'échantillon sert-il à quelque chose ?** Pour chaque modèle et chaque personnage, comparer tous les clips « avec » (V, et W s'ils existent) au témoin « sans ». On conclut que l'échantillon ne sert à rien **seulement si toutes les façons de le joindre sonnent comme le témoin**. Si une façon marche et pas l'autre, c'est cette façon qu'on garde pour tout le film.
2. **Quel modèle ?** D'abord le français et les lèvres, ensuite la ressemblance de la voix. À égalité : `seedance_2_5`.
3. **Si le français est mauvais partout** (accent, mots avalés ou inventés) : on s'arrête là, on ne crée aucune image. Voir l'étape 4.4.
4. **Reporter le résultat.** En haut de `build_prompts.py`, régler `MODEL`, `LAYOUT` et `AUDIO_TAG` sur la formule gagnante, puis lancer `python3 build_prompts.py`. Toutes les consignes de clips de `prompts.json` sont alors à jour, lot B compris.

### 1.5 Lot B — la voix tient-elle d'un clip à l'autre ? (9 demandes)

Liste `batch_B` (B1 à B9), sur la formule gagnante. La neuvième demande part dès qu'une place se libère.

| | Nox | Pico |
|---|---|---|
| Le clip gagnant, refait à l'identique | B1 | B6 |
| Une autre réplique, avec l'échantillon | B2 (clip de 4 s) et B3 (clip de 6 s) | B7 |
| La même autre réplique, sans échantillon | B4 | B8 |
| La réplique elle-même donnée comme son (`line_04`, `line_01`) | B5 | B9 |

Décider :

1. **La voix tient-elle ?** Par personnage, on a trois clips « avec » (le gagnant du lot A, sa copie, une autre réplique) et deux témoins « sans ». Si les trois sonnent comme une seule personne et pas les témoins : on joint l'échantillon à tous les clips. C'est le cas normal, on ne change rien.
2. **Sinon, la réplique donnée comme son (B5, B9).** Si le clip parle avec la voix de l'enregistrement, et que les mots et les lèvres restent justes : régler `AUDIO_SOURCE = "line"` et relancer `build_prompts.py`. Chaque clip reçoit alors l'enregistrement de sa propre réplique (étape 0.4).
3. **Sinon, changement de voix après coup.** On génère quand même, on choisit les prises sur le jeu et les lèvres, et on passe les prises choisies dans le changeur de voix à la fin (même rythme, donc les lèvres restent calées). Vérifier son prix avant (étape 0.2). C'est la décision n° 3 du propriétaire.
4. **4 s ou 6 s (B2 contre B3).** Si le clip de 4 s est plus net (débit vif, aucun mot ajouté) : régler `SHORT_LINE_S = 4` et relancer `build_prompts.py`. Les répliques courtes sont alors demandées en 4 s.
5. **Un mot mal prononcé dans tous les essais.** `prompts.json`, rubrique `pronunciation_hints`, donne une phrase toute prête par mot à risque (Nox, run, Pico, ok, peau, scanne, t'éclaire, Nuance). On l'ajoute juste après le guillemet fermant de la réplique, sans guillemets, et on relance. On ne change jamais l'orthographe de la réplique.

Garder de côté, par personnage, le meilleur clip : c'est la **voix étalon**, à laquelle on comparera toutes les prises de l'étape 3.

---

## 2. Jour 1, après-midi — les images

Six nouvelles images, en deux temps. Aucun clip n'est lancé à partir d'une image qui n'a pas passé son contrôle.

Consignes : `prompts.json`, rubrique `image_prompts`. Pour chaque image : modèle `nano_banana_2_1`, format 4:3, taille 1K, images de référence à joindre **dans l'ordre indiqué** (image 1, image 2, image 3), avec le rôle `image_references`. Une image par demande.

Pourquoi 1K et pas 2K : les images validées font 1200 × 896 et les clips sont en 720p. Une image en 2K aurait des traits plus fins que les plans 1 et 8. Si la taille 1K n'existe pas, créer en 2K puis réduire l'image choisie à 1200 × 900 avant de s'en servir.

### 2.1 Premier temps — le plan à deux et le très gros plan (8 demandes)

| Image | Essais | Références à joindre |
|---|---|---|
| `deux_etabli` | 4 : deux avec `nox_ref` en image 1, deux avec `nox_face` en image 1 | image 1 = Nox, image 2 = `pico_ref` |
| `nox_tgp` | 3 ou 4 | image 1 = `nox_ref` |

Les deux essais de `deux_etabli` avec `nox_face` (l'image resserrée, sans l'établi) servent de parade : sur `nox_ref`, une montre est posée sur l'établi, et le modèle d'images recopie volontiers ce qu'il voit.

**`deux_etabli` est l'image la plus importante.** Une fois choisie, elle sert de modèle aux quatre suivantes : même pièce, mêmes objets, mêmes poses. Le propriétaire choisit lui-même.

**Contrôle commun à toutes les images**

- [ ] C'est un nouvel angle, pas une copie ni un recadrage d'une image validée.
- [ ] Le rendu de l'image de référence : aplats, contours sombres et nets, bords un peu « pixel ». Ni 3D lisse, ni photo.
- [ ] Aucune lettre, aucun chiffre, aucun signe : les écrans sont une simple lueur bleu pâle, les notes épinglées sont blanches, la montre n'affiche rien.
- [ ] Nox : cheveux noir-bleu en pointes et mèche rebelle, lunettes fines, **les deux yeux visibles derrière des verres clairs** (ni verres verts opaques, ni reflet), col roulé noir, veste à zip vert.
- [ ] Pico : queue de cheval rouge haute et **élastique vert**, longues mèches, sweat jaune, casque noir autour du cou.
- [ ] Une seule montre dans l'image, au **poignet gauche** de Pico. Jamais sur l'établi, jamais tenue dans la main.
- [ ] Cinq doigts à chaque main visible ; aucun bras ni objet en trop.
- [ ] Bouches fermées. La bouche de celui qui parlera est bien visible, et au-dessus du cinquième bas de l'image (zone des sous-titres).
- [ ] Sens des regards : Nox regarde vers la droite de l'image, Pico vers la gauche.

**Contrôle de `deux_etabli`** (plans 3 et 6)

- [ ] Nox à gauche, de profil, tourné vers la droite ; Pico à droite, de profil, tournée vers la gauche ; cadrés à la taille, l'établi entre eux.
- [ ] Le poignet gauche de Pico, avec la montre, à une quinzaine de centimètres des lunettes de Nox ; la montre vue par la tranche.
- [ ] Un seul fer à souder, dans la main droite de Nox, la pointe posée sur un petit circuit vert ; le support du fer, devant, est vide.
- [ ] Nox regarde son travail ; Pico le fixe, un sourcil levé ; les deux bouches fermées et lisibles de profil.
- [ ] L'écouteur de Nox ne se voit pas (il est du côté caché).
- [ ] Fenêtre de nuit derrière eux, encadrement de la porte tout à droite, tasse grise sur l'établi, aucune montre sur l'établi.
- [ ] Question à se poser : est-ce l'établi et les personnages que je veux revoir dans toutes les autres images ?

**Contrôle de `nox_tgp`** (plan 11, la chute)

- [ ] Son visage remplit l'image, de la racine des cheveux au menton ; les lunettes occupent environ les deux tiers de la largeur.
- [ ] Visage impassible, bouche fermée, regard juste à droite de l'objectif.
- [ ] De la marge pour le zoom du montage : lunettes et bouche tiennent dans les 85 % du centre de l'image.
- [ ] Écouteur à droite de l'image (son oreille gauche). Derrière lui : étagères et boules vertes, rien d'autre.

Enregistrer les images choisies sous `stills/deux_etabli.png` et `stills/nox_tgp.png`.

### 2.2 Second temps — les quatre autres (8 demandes)

Deux essais par image. `deux_etabli`, validée, est jointe en dernière image de référence.

| Image | Références à joindre, dans l'ordre | Plans |
|---|---|---|
| `nox_soudure` | `nox_ref`, `deux_etabli` | 2 |
| `ots_nox` | `nox_ref`, `pico_ref`, `deux_etabli` | 4, 7, prise 9 bis |
| `pico_gp` | `pico_ref`, `deux_etabli` | 5, 10 |
| `pico_yeux_montre` | `pico_ref`, `deux_etabli` | 9 |

Si l'outil refuse trois références pour `ots_nox` : enlever `pico_ref` (son visage n'est pas dans ce cadre) et corriger la consigne en conséquence (image 1 = Nox, image 2 = le plan à deux).

**Contrôle de `nox_soudure`**

- [ ] Vue d'en bas, depuis l'établi ; son visage penché est vu presque de face ; la bouche est entièrement visible.
- [ ] Un seul fer, dans sa main droite, la pointe posée sur le circuit vert ; pas de support, pas de second fer, pas de montre.
- [ ] La main ne cache pas la bouche ; les yeux, baissés, restent visibles derrière les verres.
- [ ] Le même établi et les mêmes objets que dans `deux_etabli`. Il est seul à l'image.

**Contrôle de `ots_nox`**

- [ ] Au bord droit : l'épaule gauche de Pico, son casque, quelques mèches rouges. Rien de son visage.
- [ ] Son poignet **porte** la montre, dans le tiers bas-droit, sous le menton de Nox, jamais devant sa bouche ; on voit le bracelet et la tranche, aucun chiffre.
- [ ] Nox au centre-gauche, de trois quarts, tourné vers la droite, yeux baissés sur la montre, bouche fermée et entièrement visible.
- [ ] Les mains de Nox hors cadre ; aucune montre sur l'établi ; son écouteur ne se voit pas.

**Contrôle de `pico_gp`**

- [ ] Elle est **penchée sur l'établi**, comme dans `deux_etabli` (épaules en avant, tête à la hauteur de Nox). Pas debout dans l'encadrement de la porte.
- [ ] Fond : surtout un mur sombre et uni ; la porte, petite et lointaine, dans le tiers droit, ou absente. Si l'encadrement de la porte l'entoure : on refait.
- [ ] De trois quarts, regard droit vers la gauche de l'image ; visage neutre, sourcils à plat, bouche fermée.
- [ ] Ni bras, ni main, ni montre ; élastique vert et casque visibles ; menton au-dessus de la zone des sous-titres.

**Contrôle de `pico_yeux_montre`** (l'image la plus difficile)

- [ ] Au-dessus de l'avant-bras, on ne voit que ses yeux, ses sourcils, son front et ses cheveux rouges. Nez, bouche et menton cachés. Un visage entier au-dessus du bras : on refait.
- [ ] La montre est vue par la tranche : pas d'écran, pas de chiffres. La lumière verte sort de **sous** le boîtier et éclaire la peau et l'établi.
- [ ] L'avant-bras entre par la droite ; la main a cinq doigts ; la montre est au poignet.
- [ ] Ses yeux, plissés, regardent la montre, pas l'objectif. L'établi occupe le cinquième bas de l'image.

### 2.3 Quand une image ne vient pas

Dans l'ordre :

1. Relancer deux essais à l'identique.
2. Si l'image recopie le cadrage d'une référence : déplacer le paragraphe qui commence par `THIS FRAME` tout en haut de la consigne.
3. Si l'outil refuse la longueur de la consigne : prendre la version courte, `prompt_compact`.
4. Si la montre de l'établi revient sans cesse : remplacer `nox_ref` par `nox_face` en image 1.
5. Après trois échecs, passer à l'image de secours (`prompts.json`, rubrique `spare_image_prompts`) :

| Image de secours | Remplace | Ce qu'on y perd |
|---|---|---|
| `montre_lueur` : l'avant-bras et la montre, lueur verte, sans visage | `pico_yeux_montre` | les yeux de Pico qui s'arrondissent ; la réaction passe au plan 10 |
| `nox_soudure_sans_main` : le même gros plan, mains sous le cadre | `nox_soudure` | on ne voit plus le fer ; le grésillement du montage suffit |
| `ots_nox_sans_bras` : le même cadre sans le poignet de Pico | `ots_nox` | la montre n'est plus à l'image dans les plans 4 et 7 |

Si `deux_etabli` reste impossible : on se passe du plan à deux. Les plans 2 et 3 sont remplacés par la prise 2 bis, le plan 6 disparaît, le plan 7 est remplacé par la prise 7 bis. Le film fait alors 30 s environ ; on rallonge un peu les silences des plans 2 et 11.

Avant de passer aux clips : comparer une nouvelle image à `nox_face`, côte à côte, réduites à 720 lignes. Si l'une paraît nettement plus fine ou plus lisse que l'autre, le signaler au propriétaire avant d'animer.

---

## 3. Jour 2 — les clips

Consignes : `prompts.json`, rubriques `video_prompts` (les 11 plans) et `safety_take_prompts` (les prises supplémentaires). Pour chaque demande, reprendre tels quels : `model`, `mode`, `duration`, `resolution`, `aspect_ratio`, `generate_audio`, `medias` (les fichiers à joindre et leur rôle) et `prompt`.

### 3.1 Combien de prises

- Plan parlé : **3 prises d'un coup**, puis on choisit. On ne lance pas une prise, puis une autre.
- Plan sans son (6 et 9) : 2 prises.
- Prise de rechange (2 bis, 7 bis, 8 bis) : 2 prises.
- Prise 9 bis : 3 prises. Elle est **obligatoire** : c'est la voix du plan 9.
- Prise 11 bis : seulement si le zoom fait au montage paraît flou.
- Prise 4 bis : elle existe déjà, c'est le meilleur clip de Nox de l'étape 1.
- Plan 1 : les bons clips de Pico de l'étape 1 comptent comme des prises.

Les plans 6 et 9 se génèrent **sans son** (`generate_audio` à `false`) et sans échantillon de voix.

### 3.2 Dans quel ordre (5 lots de 8)

Les plans les plus risqués d'abord, pour avoir le temps d'appliquer un plan de repli.

| Lot | Contenu | Images utilisées |
|---|---|---|
| C1 | plan 3 × 3, plan 9 (sans son) × 2, prise 9 bis × 3 | `deux_etabli`, `pico_yeux_montre`, `ots_nox` |
| C2 | plan 4 × 3, plan 7 × 3, plan 6 (sans son) × 2 | `ots_nox`, `deux_etabli` |
| C3 | plan 8 × 3, prise 8 bis × 2, plan 11 × 3 | `nox_face`, `nox_tgp` |
| C4 | plan 2 × 3, plan 5 × 3, prise 2 bis × 2 | `nox_soudure`, `pico_gp` |
| C5 | plan 10 × 3, plan 1 × 3 (s'il en manque), prise 7 bis × 2 | `pico_gp`, `pico_porte`, `nox_soudure` |

### 3.3 Ce qu'on vérifie sur chaque prise

Lancer `python3 montage.py qc clips/s04_t1.mp4`, regarder la planche, puis regarder et écouter le clip deux fois : une fois les yeux sur la bouche, une fois les yeux fermés.

| Point | La prise est bonne si… |
|---|---|
| **Les mots** | c'est exactement la réplique validée : rien d'ajouté, d'enlevé, de répété, de reformulé |
| **Les lèvres** | fermées avant le premier mot et après le dernier ; elles se ferment sur p, b, m ; rien ne flotte à la fin ; personne d'autre ne bouge les lèvres |
| **Le visage** | c'est la même personne que sur l'image de départ, du début à la fin : lunettes avec les yeux visibles, forme des cheveux, élastique vert ; rien ne se déforme ; cinq doigts |
| **La voix** | c'est la voix étalon du personnage (étape 1.5) ; Nox vif et à pleine voix, Pico rapide et claire |
| **Pas de texte** | aucun sous-titre, aucune lettre, aucun signe n'apparaît ; les écrans et les notes ne grouillent pas |
| **Pas de musique** | ni musique, ni bruit inventé, ni écho ; du silence entre les mots |
| **Le cadre** | le clip s'ouvre sur l'image de départ ; la caméra ne bouge pas ; aplats et contours tiennent jusqu'au bout |
| **Les marges** | bouche fermée au moins 0,2 s avant la réplique et 0,5 s après, pour pouvoir couper proprement |

Une prise qui rate un seul des six premiers points est écartée. On ne « répare » pas une prise au montage, sauf deux cas : un geste raté **après** la réplique (on coupe avant), et un début trop rapide (on fige la première image).

**Points particuliers, plan par plan**

| Plan | À surveiller |
|---|---|
| 1 | « Nox » avec le x ; « run » ; un seul mouvement du poignet ; pas de halètement au milieu de la phrase |
| 2 | il ne lève pas les yeux, son visage ne réagit pas ; « Pico » ; le fer ne se tord pas, les doigts ne fusionnent pas avec le circuit |
| 3 | **les lèvres de Pico ne bougent pas** ; seul Nox parle ; il relève à peine la tête |
| 4 | la pause courte ; ses yeux se lèvent par-dessus les lunettes ; le poignet de Pico reste immobile et la montre reste au poignet |
| 5 | elle répond tout de suite ; « ok » en deux syllabes (« oké ») ; elle finit sur un regard boudeur vers la gauche |
| 6 | rien ne bouge sauf la fumée ; aucune bouche ne s'ouvre |
| 7 | « Bon. » court et qui retombe, puis la suite plus gaie ; il relève la tête vers la droite ; aucun mot ajouté |
| 8 | la réplique d'abord, le geste des lunettes ensuite ; les yeux restent visibles ; le doigt ne déforme pas les lunettes ; aucun mot ajouté pour remplir le clip |
| 9 | son nez et sa bouche restent cachés ; les yeux s'arrondissent une seule fois et restent sur la montre ; la lumière verte pulse |
| 9 bis | seul le son compte : voix de Nox, pause courte, « dans ta peau » bien timbré, pas chuchoté |
| 10 | « Attends… » les yeux baissés, la tête qui se redresse sur « quoi ?! » ; « scanne » ; pas de cri saturé |
| 11 | une seconde de regard fixe ; « Nuance. » posé net, la voix qui descend (ni avalé, ni en question) ; petit sourire à la fin |

**Deux moitiés d'une même réplique.** Écouter à la suite le plan 2 puis le plan 3, et le plan 8 puis la prise 9 bis. Ils doivent sonner comme une seule phrase : même hauteur de voix, même niveau, même énergie. Sinon : refaire la paire, ou prendre la prise 2 bis pour la première.

Tenir un petit tableau : plan, prise, bonne ou non, défaut. Il sert à l'étape 4.

---

## 4. Reprises et plans de repli

### 4.1 L'échelle, à monter dans l'ordre

Pour un plan dont aucune des 3 prises n'est bonne. Deux tours au plus par barreau.

| Barreau | Quoi faire | Quand |
|---|---|---|
| 1. Relancer | 3 prises à l'identique | toujours en premier : une partie des échecs est due au hasard |
| 2. Simplifier le jeu | supprimer de la consigne la phrase qui décrit le geste (elle suit la réplique) ; garder la réplique, « mouth closed » et la fin | lèvres décalées, visage qui se déforme, geste raté |
| 3. Raccourcir le clip | demander 4 s au lieu de 5 ou 6 | mots ajoutés, débit étiré, dérive en fin de clip |
| 4. Changer de modèle | la même consigne sur l'autre modèle (`seedance_2_0` : pas de mode) | deux tours ratés sur le modèle choisi |
| 5. Couper la réplique en deux clips | seulement à une pause écrite, voir 4.2 | réplique longue dont une moitié rate toujours |
| 6. Plan de réaction sans son, réplique posée dessus | voir 4.3 | tout le reste a échoué |

À chaque barreau, les défauts orientent le choix :

- **Un mot mal prononcé à chaque fois** : ajouter la phrase toute prête de `pronunciation_hints`, après le guillemet fermant, sans guillemets.
- **Du texte ou de faux sous-titres apparaissent** : relancer ; si cela revient sur toutes les prises d'une même image, c'est l'image qui contient des signes : la refaire.
- **De la musique** : relancer. La consigne l'interdit déjà.
- **La voix n'est pas la bonne** : vérifier que l'échantillon est bien joint et que les mots `with the voice of the audio reference,` sont dans la consigne ; relancer. Si la prise est bonne par ailleurs, la garder pour le changement de voix (étape 1.5, point 3).
- **Les lèvres de Pico bougent au plan 3** : refaire l'image `deux_etabli` avec sa tête un peu plus tournée vers le fond, ou passer à la prise 2 bis.
- **La main ou le fer se déforment au plan 2** : image de secours `nox_soudure_sans_main`.

### 4.2 Couper une réplique en deux clips

On coupe à la pause écrite, jamais ailleurs, et on ne change aucun mot. Les deux cartons de sous-titres sont déjà prévus à ces endroits.

| Plan | Première moitié | Seconde moitié |
|---|---|---|
| 4 | « Tu portes cette montre depuis deux ans… » sur `ots_nox` | « et tu découvres qu'elle s'allume ? » sur `nox_face` |
| 9 bis (son seul) | « Ta montre envoie de la lumière verte… » | « dans ta peau. » ; les deux sons sont mis bout à bout sous l'image du plan 9 |

À ne pas couper : le plan 10 (deux clips de trois syllabes, que le modèle remplit de mots inventés), le plan 11 (deux très gros plans à la suite) et le plan 1 (« Nox ! » seul est trop court).

Pour la consigne de chaque moitié : reprendre la consigne du plan, remplacer la réplique entre guillemets par la moitié voulue, supprimer la phrase qui parle de la pause.

### 4.3 Plan de réaction sans son, réplique posée dessus

On montre celui qui écoute, ou un cadre où la bouche de celui qui parle ne se voit pas, et on pose la réplique par-dessus au montage (réglage `audio_from` de `montage.py`). C'est déjà ce qu'on fait pour le plan 9.

**D'où vient le son**, par ordre de préférence :

1. d'une prise ratée à l'image mais bonne au son (c'est fréquent) ;
2. sinon, de l'enregistrement de la réplique avec la voix de la série (étape 0.4).

**Quelle image**, selon le plan. Le clip se génère sans son, avec une consigne réduite à la pose : « elle reste immobile, lèvres fermées, un seul battement de paupières ».

| Plan raté | Image du plan de réaction | Pourquoi ça marche |
|---|---|---|
| 2 (Nox) | `pico_porte` : Pico, dans l'encadrement, baisse lentement le poignet | Nox répond sans lever les yeux : on reste sur elle |
| 3, 4 ou 7 (Nox) | `pico_gp` : Pico l'écoute, lèvres fermées | Nox est hors champ |
| 5 ou 10 (Pico) | `ots_nox` : Nox la regarde, amusé, lèvres fermées ; elle est de dos | la bouche de Pico ne se voit pas |
| 10 (Pico), autre solution | `pico_yeux_montre` : ses yeux se lèvent d'un coup | sa bouche est cachée par son avant-bras |
| 8 (Nox) | on réunit les plans 8 et 9 : toute la réplique l03 sur l'image du plan 9 | la bouche de Nox ne se voit pas |
| 11 (Nox) | d'abord essayer la réplique sur `nox_face` (bouche plus petite, zoom fait au montage) ; en dernier recours, la réplique sur `pico_gp` figée, puis une seconde de `nox_tgp` muet avec son petit sourire | la chute garde son sourire final |
| 1 (Pico) | pas de plan de repli : c'est l'accroche, de face. On multiplie les prises et on change de modèle | — |

Dans ces cas, la règle « jamais deux fois de suite le même cadrage sur le même personnage » peut céder : un plan qui existe vaut mieux qu'une règle respectée.

### 4.4 Si le français est mauvais sur les deux modèles

On ne crée ni image ni clip. Deux issues, à décider avec le propriétaire :

- les essais B5 et B9 montrent que le modèle suit un enregistrement donné comme son : on donne à chaque clip l'enregistrement de sa réplique (`AUDIO_SOURCE = "line"`) ;
- sinon, il faut un autre outil, payant, qui anime une image à partir d'un enregistrement. Ce n'est pas compris dans l'essai.

### 4.5 Savoir s'arrêter

- Fin du jour 2 : tout plan qui n'a pas de bonne prise passe directement au barreau 6.
- Midi du jour 3 : on ne génère plus que des retouches de plans déjà presque bons. Le reste du temps va au montage.

---

## 5. Jour 3 — le montage

### 5.1 Préparer

1. Copier la prise choisie de chaque plan sous le nom `clips/s01.mp4` … `clips/s11.mp4`, et la prise 9 bis sous `clips/s09b.mp4`.
2. Si un changement de voix a été décidé : passer d'abord les prises choisies dans le changeur de voix, un personnage après l'autre, et vérifier que les lèvres sont toujours calées.
3. Copier `edit_modele.json` en `edit.json`. Ce fichier contient déjà les 11 plans, les sous-titres, les silences, le zoom du dernier plan et les sons disponibles. Il a été essayé avec des clips de remplacement : `montage.py` l'accepte tel quel.
4. Dans `edit.json`, la rubrique `_a_completer` liste ce qui reste à brancher : la musique (renommer la clé en `music` au premier niveau, une fois `son/musique.mp3` en place) et les sons de l'étape 0.6 (les déplacer dans la liste `sfx`). `montage.py` s'arrête si un fichier inscrit n'existe pas.

### 5.2 Monter

Commande : `python3 montage.py build edit.json`. On obtient le film en 4:3, sa version verticale pour TikTok, et un rapport avec la durée de chaque plan.

Réglages utiles, plan par plan (tous dans `edit.json`) :

| Réglage | Effet | Où il sert |
|---|---|---|
| `lead` | durée gardée avant le premier mot | plans 2 (1 s), 3 (0,9 s) et 11 (1,2 s) : les silences avant la réplique |
| `hold_start` | fige la première image pendant ce temps | si le clip parle trop tôt pour laisser le silence voulu |
| `tail` | durée gardée après le dernier mot | plan 8 (1,1 s, le geste des lunettes) ; plan 11 (0,9 s, le petit sourire) |
| `in`, `out` | début et fin choisis à la main | plan 9 (voir ci-dessous) ; plan 10 (commencer quand ses yeux sont déjà baissés) |
| `audio_from` | son pris sur un autre clip | plan 9 : le son de la prise 9 bis |
| `push_in` | zoom avant lent | plan 11 : 0,13 |
| `still` | une image fixe à la place d'un clip | plan 6, si le clip sans son n'est pas bon : `stills/deux_etabli.png` |
| `caption` | un sous-titre, ou une liste de cartons qui se suivent | plans 4, 9 et 11 : deux cartons |

**Plan 9.** Les yeux de Pico doivent s'arrondir sur « dans ta peau ». On règle `in`, le moment du clip sans son où le plan commence, puis on regarde le résultat :

- ses yeux s'arrondissent trop tard : augmenter `in` (de 0,3 à 0,6 par exemple) ;
- trop tôt : diminuer `in` ; s'il est déjà à 0, augmenter `lead`, qui ajoute du silence avant la voix.

**Plan 8.** Si le geste des lunettes est raté : mettre `tail` à 0,45 (on coupe juste après la réplique) ou prendre la prise 8 bis. Déplacer le tintement avec `offset`.

**Sans plan à deux.** Retirer les plans 3 et 6 de `edit.json`, mettre la prise 2 bis à la place du plan 2 et la prise 7 bis à la place du plan 7. Le sous-titre de la prise 2 bis s'écrit en deux cartons : « Bonsoir à toi aussi, Pico. », puis « Entre, fais comme chez toi. ».

**Sans le plan 6 seulement.** Retirer le plan 6 et mettre la prise 7 bis à la place du plan 7 : sinon le cadre par-dessus l'épaule revient deux fois de suite sur Nox.

### 5.3 Contrôle du film monté

- [ ] Durée entre 30 et 36 s. En dessous de 30 s : rallonger les silences des plans 2, 6 et 11.
- [ ] Le sous-titre de la question est à l'écran dès la première seconde, sur deux lignes.
- [ ] Plans 4, 9 et 11 : le second carton n'apparaît qu'après la pause. « dans ta peau. » et « Nuance. » ne se lisent pas avant d'être dits.
- [ ] Chaque sous-titre correspond mot pour mot à ce qu'on entend ; « ok » en minuscules.
- [ ] Aucune coupe ne tombe dans un mot ; aucune bouche ouverte sur la première ou la dernière image d'un plan.
- [ ] Jamais deux fois de suite le même cadrage sur le même personnage.
- [ ] Une seule montre, toujours au poignet gauche de Pico. Les yeux de Nox toujours visibles.
- [ ] La voix de chaque personnage est la même du début à la fin. Les plans 2 et 3, puis 8 et 9, sonnent comme une seule phrase chacun.
- [ ] Le claquement de porte sur la première image ; le fracas pile sur la coupe du plan 3, et les pas s'arrêtent dessus.
- [ ] La musique entre après la porte, reste nettement sous les voix, et s'arrête net à l'entrée du plan 11 : la chute se joue dans le silence.
- [ ] L'ambiance de pièce est continue ; aucun trou de son aux coupes.
- [ ] Regarder la version verticale sur un téléphone, avec le haut-parleur du téléphone : « dans ta peau » et « Nuance » s'entendent.

### 5.4 Avant la fin de l'essai

1. Tout est téléchargé : images choisies, toutes les prises choisies, les essais de voix utiles.
2. Le propriétaire a annulé le renouvellement automatique, et l'a vérifié.
3. Noter ce qui a marché pour la suite de la série : le modèle, la façon de joindre la voix, la durée demandée, les phrases de prononciation utiles, les plans qui ont demandé un plan de repli.

---

## Aide-mémoire

| Jour | Matin | Après-midi |
|---|---|---|
| Avant | décisions, lecture des réglages, échantillons de voix, répliques enregistrées, sons | — |
| 1 | essai de voix : lots A et A2 (16 clips), décision, lot B (9 clips) | images : premier temps (8 essais), choix du plan à deux, second temps (8 essais) |
| 2 | clips : lots C1, C2, C3 | clips : lots C4, C5, puis reprises |
| 3 | dernières reprises (jusqu'à midi) | montage, contrôle, téléchargements, annulation du renouvellement |

Compte des demandes prévues : 25 clips d'essai de voix, 16 essais d'images, 40 clips, plus les reprises.
