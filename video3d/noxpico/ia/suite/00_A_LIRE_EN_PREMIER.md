# Nox & Pico — sketch IA : tout pour continuer

**Version 2 du 25 novembre 2026. Elle remplace la version 1.** Elle ajoute :
- les fiches de tous les plans (étape 2) ;
- les mêmes noms de clips partout (G01, G02, G03…) ;
- un montage aux bruitages corrigés.

Ce dossier contient tout ce qu'il faut pour finir le sketch dans une autre conversation avec Claude.
Il est écrit pour toi et pour le Claude qui prendra la suite.

## En bref

- **Le sketch** : environ 32 secondes, le début de l'épisode 1. Pico débarque chez Nox et demande pourquoi sa montre fait des lumières vertes. Ça se termine sur « Elle t'éclaire. Nuance. ».
- **Le rendu** : « cinématique de jeu vidéo du début des années 2000 », dessiné, avec des contours fins, la nuit et des touches de vert. Ce sont les deux images du dossier `images/`, celles que tu as choisies (l'« essai 1 »).
- **La fabrication** : comme dans les vidéos de référence. Chaque plan est un clip généré par une IA vidéo, qui fait aussi la voix et les lèvres. Ensuite viennent le montage, les sous-titres, la musique et les bruitages.
- **L'outil** : Google Flow, avec ton compte Google AI étudiant (1 000 crédits par mois, plus 50 crédits gratuits par jour).
- **Où on en est** : tout est prêt, c'est-à-dire :
  - les fiches de l'étape 1 et de l'étape 2 ;
  - un fichier de prompt prêt à copier pour chaque clip ;
  - le montage, testé avec de faux clips.

  À ma connaissance, aucune vidéo n'est encore générée. Si tu as déjà fait l'étape 1, dis-le au nouveau Claude et envoie-lui G01 et G02.
- **Prochaine étape** : créer les deux voix dans Flow et faire les deux clips test (`flow/etape1_test_flow.txt`). Ensuite, faire les clips de l'étape 2 (`flow/etape2_tous_les_plans.txt`).

## Continuer dans une nouvelle conversation

1. Dézippe ce dossier sur ton PC, par exemple dans `Documents\Nox et Pico\NoxPico_suite`.
2. Ouvre l'application Claude sur ton PC et commence une nouvelle conversation. Si elle te demande un dossier de travail, choisis `NoxPico_suite`.
3. Copie le message du fichier `01_message_a_coller.txt` (corrige le chemin s'il le faut) et envoie-le.
4. Claude ouvre Flow dans un navigateur sur ton PC : celui de l'application, ou Chrome avec l'extension Claude. **Tu te connectes toi-même à ton compte Google** ; Claude ne doit jamais voir ton mot de passe.
5. Chaque prise est enregistrée dans `clips/` sous le nom de sa carte (voir « Noms des fichiers »).

Si Claude ne peut pas piloter le navigateur, fais les clics toi-même avec les fiches. Les fiches te parlent directement (« envoie-moi ») : tu envoies les prises à Claude dans la conversation. Tu peux aussi revenir dans l'ancienne conversation m'envoyer les clips : j'ai tout pour faire le montage.

## Ce qui est décidé (à ne pas changer sans raison)

| Sujet | Décision |
| --- | --- |
| Style | `images/ingredient_nox.png` et `images/ingredient_pico.png` (essai 1). Les personnages et le rendu viennent de ces deux images. |
| Texte | Le dialogue de l'épisode 1 est validé et se garde mot pour mot (`plan/dialogue_ep01.json`). Le sketch va de la réplique l01 à l04b. |
| Découpage | 11 plans (`plan/shotlist.md`), choisis parmi trois découpages puis relus. On ne le refait pas. |
| Clips | 10 clips à générer à l'étape 2, en plus des 2 clips test de l'étape 1. Les fiches ont été écrites puis relues trois fois. |
| Format final | Image 4:3 (960×720) au centre d'une vidéo verticale 1080×1920, comme la référence. |
| Sous-titres | Blancs cernés de noir, en bas, la réplique entière. Les plans 4, 9 et 11 ont un sous-titre en deux temps, pour ne pas dévoiler la chute avant la pause. |
| Voix | Nox vivant : vif, ironique, jamais lent ni robotique, même quand la consigne dit « calmement ». Pico spontanée et rapide. |
| Fin | Le sketch s'arrête avant l'explication : c'est une partie 1. La suite (répliques l05 à l07) fera un deuxième sketch. |

`plan/shotlist.md` a été écrit pour un autre outil (Higgsfield). L'histoire, les plans, les répliques, le jeu et les sous-titres restent valables. Ce qui parle d'images de départ, d'échantillons de voix ou d'« essai de 3 jours » ne sert plus : avec Flow, on suit les fiches du dossier `flow/`.

## Google Flow : ce qu'il faut savoir (vérifié le 25 novembre 2026)

- **Pas d'accès automatique** : tout se fait sur le site labs.google/flow, connecté à ton compte. Google ne fournit pas d'API pour Flow. Les outils non officiels passent par la connexion de ton compte : à éviter.
- **Modèle** : Omni Flash 1.2, en mode **Ingrédients** (on lui donne les images des personnages comme références).
- **Voix** : c'est le seul mode où l'on peut joindre une voix créée dans Flow, et une seule voix par vidéo. Donc **une seule personne parle par clip**.
- **Créer les voix** : sous la zone de texte, Add → Voices → Create New Voice. On choisit une voix de base et on ajoute une description. On ne peut pas envoyer d'enregistrement.
- **Format** : 16:9 ou 9:16 seulement. On génère en 16:9 et le montage garde le centre en 4:3 : il faut donc que **les personnages restent au centre de l'image**.
- **Durée** : 3 à 10 secondes avec des images de référence. Les fiches demandent 6 s pour une réplique courte et 8 s pour une longue ; le montage coupe autour de la parole.
- **Coût** :
  - environ 3 crédits par seconde en 720p (6 s = 18 crédits, 8 s = 24) ;
  - Flow affiche le prix avant de lancer ;
  - régler **1 vidéo par demande**, sinon le prix est multiplié ;
  - Veo 3.1 Lite coûte 10 crédits par clip, mais il ne garde pas la voix : il ne sert que pour un plan muet (carte de secours G17).
- **Attention** : selon une source non officielle, Veo 3.1 Fast et Quality, ainsi qu'Omni Flash 1.1, pourraient quitter Flow le 5 décembre 2026. On utilise Omni Flash 1.2.
- **Pas vérifié** :
  - la longueur maximale d'un prompt (le plus long fait 2 867 caractères) ;
  - la façon dont le @ relie une image dans le texte.

  Les fiches disent quoi faire dans les deux cas.

## Les étapes

### 1. Les voix et deux clips test (48 crédits)
Suis `flow/etape1_test_flow.txt` : création des voix « Nox » et « Pico », puis un clip de Nox et un clip de Pico. **Renomme le clip de Nox `G01.mp4` et celui de Pico `G02.mp4`.**

Ce qu'il faut regarder :
- le rendu est le même que sur les deux images ;
- le français est naturel, sans accent étranger ;
- les voix sont vivantes ;
- les lèvres suivent les mots ;
- les lunettes de Nox restent transparentes ;
- il n'y a ni texte ni musique.

G02 (Pico à la porte) sert directement de plan 1. G01 sert de secours pour le plan 4.

### 2. Les clips de l'étape 2 (192 crédits pour une prise de chaque, environ 350 avec les reprises)
Les fichiers :
- `flow/etape2_tous_les_plans.txt` : les instructions en français, carte par carte. Lis d'abord « EN BREF » et la section A.
- `flow/prompts/G03.txt` … `G18.txt` : le prompt de chaque carte, seul dans son fichier. Pour copier, on fait « Tout sélectionner », puis « Copier ».
- `flow/prompts/prise3/` : les prompts tout prêts pour une 3e prise (une correction chacun).
- `flow/flow_kit.json` : le même contenu pour Claude. On y trouve aussi la découpe de chaque plan, les secours et le budget détaillé.

Les règles principales :
- **Ordre** : G03, G05, G07, G08, G09, G10, G11, G12, puis G04 et G06 seulement quand Claude a validé G03 (le plan à deux). Si G03 rate trois fois, on fait G13 et G14 à la place de G04 et G06, et le plan 6 disparaît.
- **Dans chaque prompt**, remplace les repères par un @ :
  - `[IMAGE NOX]` et `[IMAGE PICO]` → l'image du personnage ;
  - `[VOIX NOX]` et `[VOIX PICO]` → la voix créée à l'étape 1. Attention : c'est bien la voix qu'il faut choisir, pas l'image du même nom.
- **Avant chaque carte**, vide la zone de texte et enlève les images et la voix de la carte d'avant.
- **Trois prises au plus par carte** :
  - prise 2 : le même prompt ;
  - prise 3 : le fichier de `prompts/prise3` qui corrige le défaut ;
  - jamais de 4e prise sans l'accord de Claude.
- **Arrêt** : si l'étape 2 dépasse 450 crédits, on s'arrête et on fait le point.
- **Secours** (G13 à G18, 106 crédits en tout) : seulement si une carte le dit ou si Claude le demande.

| Plan | Ce qu'on voit | Qui parle | Réplique | Clip | Durée |
| --- | --- | --- | --- | --- | --- |
| 1 | Pico à la porte, de face, montre levée | Pico | « Nox ! Pourquoi ma montre fait des lumières vertes à la fin de mon run ? » | `G02` (clip test 2) | 8 s |
| 2 | Gros plan de Nox qui soude, vu d'en bas. 1 s de silence, il ne lève pas les yeux | Nox | « Bonsoir à toi aussi, Pico. » | `G04` | 6 s |
| 3 | Plan à deux de profil : Pico affalée sur l'établi, la montre sous le nez de Nox. Elle se tait | Nox | « Entre, fais comme chez toi. » | `G03` | 6 s |
| 4 | Par-dessus l'épaule de Pico, sur Nox qui regarde la montre puis lève les yeux | Nox | « Tu portes cette montre depuis deux ans… et tu découvres qu'elle s'allume ? » | `G05` (secours : `G01`) | 8 s |
| 5 | Gros plan de Pico, vexée | Pico | « J'ai jamais regardé dessous, ok ? » | `G10` | 6 s |
| 6 | Silence à deux | — | — | `G03` réutilisé, son coupé : rien à générer | — |
| 7 | Par-dessus l'épaule de Pico, sur Nox | Nox | « Bon. Laisse-moi t'expliquer. » | `G06` | 6 s |
| 8 | Nox de face, il remonte ses lunettes | Nox | « Regarde de plus près. » | `G08` | 6 s |
| 9 | Très gros plan : les yeux de Pico au ras de sa montre, lumière verte sur la peau | Nox, hors champ | « Ta montre envoie de la lumière verte… dans ta peau. » | image `G12` (muet) + son de `G07` | 6 s + 8 s |
| 10 | Gros plan de Pico, paniquée | Pico | « Attends… quoi ?! Elle me scanne ?! » | `G11` | 6 s |
| 11 | Très gros plan de Nox : un temps de silence, la réplique, un petit sourire (zoom lent ajouté au montage) | Nox | « Elle t'éclaire. Nuance. » | `G09` | 6 s |

### 3. Vérifier chaque prise
Les fiches séparent deux choses :
- ce qui fait relancer tout de suite (liste « Relance si », section A et chaque carte) ;
- ce que Claude vérifie lui-même (« Je vérifierai »).

On relance si :
- un mot est changé, ajouté ou manquant ;
- la bouche de celui qui écoute bouge ;
- ce n'est pas la bonne voix ;
- du texte, de la musique ou des bandes noires apparaissent ;
- un visage ou des habits changent ;
- une main ou une montre se déforme ;
- un visage, la montre ou une main sort du centre (test du doigt sur les bords, expliqué dans la fiche).

En cas de doute, on garde la prise et on l'envoie à Claude.

### 4. Le montage (`outils/montage.py`)
Il faut Python 3 avec numpy et Pillow (`py -m pip install numpy pillow`), et FFmpeg installé.

Dans le dossier `NoxPico_suite` :
```
python outils/montage.py qc clips/G05.mp4     # planche d'images + où la parole commence et finit
python outils/montage.py build montage.json   # assemble tout
```
`build` écrit trois fichiers :
- `sortie/nox_pico_sketch.mp4`, la version 4:3 ;
- `sortie/nox_pico_sketch_vertical.mp4`, en 1080×1920 pour TikTok ;
- un rapport des coupes.

Il coupe chaque clip autour de la parole, recadre en 4:3, ajoute les sous-titres, la musique (`cute.mp3`, celle de l'épisode 1) et les bruitages, puis règle le volume pour TikTok (−15 LUFS). Testé avec des faux clips 16:9 aux bons noms : environ 35 s.

`montage.json` prend la **première prise** de chaque carte (`clips/G05.mp4`). Si une autre prise est meilleure, on change le nom dans `montage.json` (par exemple `clips/G05_prise2.mp4`).

À régler à la main une fois les vrais clips arrivés :
- **Plan 6** : `in` = durée de G03 − 1,4 et `out` = durée − 0,1 (4,6 et 5,9 pour un clip de 6,0 s). On le prend à la fin du clip, quand plus rien ne bouge. Sinon, `in` 0,0 et `out` 1,3.
- **Plan 9** : `in` (vers 0,3 s), pour que les yeux de Pico s'arrondissent sur « dans ta peau ».
- **Plan 8** : le tintement (`sparkle`, 1,6 s après le début du plan) se cale sur le reflet des lunettes.

Réglages dans `montage.json`, plan par plan :

| Réglage | Effet |
| --- | --- |
| `lead` | Marge avant la réplique. Le plan 2 garde 1 s de silence exprès, le plan 11 1,2 s. |
| `tail` | Marge après la réplique. |
| `in` / `out` | Début et fin choisis à la main, en secondes dans le clip. |
| `silent_s` | Durée gardée pour un plan sans parole (à partir de `in`). |
| `hold_start` | Fige la première image un moment, si le clip parle trop tôt. |
| `push_in` | Zoom lent du plan 11. |
| `mute` | Coupe le son du clip. |
| `audio_from` | Prend le son d'un autre clip (plan 9 : le son de G07). |
| `hflip` | Retourne l'image gauche-droite. Seulement pour G09, G10, G11 et G16 (pas de montre ni de fer à souder dans l'image). |
| `music` → `stop_at_shot` | La musique se coupe net à l'entrée du plan 11. |

Pour les bruitages (`sfx`) :

| Réglage | Effet |
| --- | --- |
| `from` | Moment du fichier son où l'on commence. |
| `dur` | Durée maximale. |
| `until_shot` | Arrête le son net à l'entrée du plan indiqué. |

Ce qui est prévu :
- le claquement de porte sur la première image ;
- la soudure et les pas de Pico au plan 2, coupés net à l'entrée du plan 3 ;
- la soudure au plan 6 ;
- le tintement au plan 8 ;
- un bip discret au plan 9.

En option, deux idées des fiches :
- un fracas de composants sur la coupe du plan 3 (pas de fichier fourni) ;
- un petit souffle amusé de Nox à la fin du plan 6.

## Noms des fichiers

Mets **toutes les prises** dans `clips/`, sous le nom de leur carte :
- `G01.mp4` (clip test de Nox) et `G02.mp4` (clip test de Pico) pour l'étape 1 ;
- `G03.mp4`, puis `G03_prise2.mp4`, `G03_prise3.mp4`, et de même pour les autres cartes ;
- aucun clip pour le plan 6 : il réutilise G03.

Ne supprime aucune prise, même ratée : son son ou une partie de l'image peuvent servir.

## Règles pour Claude (la conversation suivante)

- Répondre en français simple.
- Ne jamais demander, taper ni regarder un mot de passe ou un code : l'utilisateur se connecte lui-même. Ne jamais saisir de moyen de paiement.
- Crédits, sur les 1 000 du mois :
  - budget prévu : 48 pour l'étape 1, puis 192 à 350 pour l'étape 2 ;
  - arrêt si l'étape 2 dépasse 450 ;
  - secours (106) seulement si besoin ;
  - toujours 1 vidéo par demande, et prévenir avant de dépasser.
- Suivre les cartes à la lettre : ordre, trois prises au plus, fichiers de 3e prise. Le détail est dans `flow/flow_kit.json` (champs `shots_map`, `fallbacks`, `edit_notes`).
- Vérifier chaque prise reçue avant de dire quoi refaire : `montage.py qc` donne une planche d'images et indique où la parole commence et finit.
- Ne changer aucun mot des répliques. Une seule paire de guillemets par prompt : la réplique.
- Aucun texte, sous-titre ou musique dans les clips : tout s'ajoute au montage.
- Ne mettre ni le nom, ni l'e-mail, ni d'autre information personnelle de l'utilisateur dans une requête vers un service extérieur.
- Respecter la série : montrer plutôt qu'expliquer, des piques complices, Nox vivant, Pico spontanée.
- Les images de `plan/references/` viennent de vidéos d'autres créateurs : elles servent à comprendre le style visé, on ne les copie pas.

## Déjà essayé : à ne pas refaire

- **La 3D faite à la main dans Blender** (versions 1 à 6) : abandonnée, l'utilisateur ne la trouvait pas jolie.
- **Higgsfield** : l'offre gratuite refuse la vidéo (« Requires basic plan or higher ») et le paiement par carte n'a pas marché.
- **Un rendu plus réaliste (« essai 3 »)** : écarté au profit de l'essai 1.
- **Les vidéos de référence** : elles sont très probablement faites en IA, image puis vidéo (voir `plan/analyse_des_videos_de_reference.md`).
- **Le montage de la version 1 du zip** : ses bruitages duraient trop longtemps. La porte claquait au milieu de la réplique, les pas couraient sous tout le film et la soudure couvrait la voix. C'est corrigé ici.

## Pour publier

Titre proposé (règle de la série) : « Nox & Pico ép. 1 — Pourquoi ma montre s'allume en vert ? (partie 1) ». La question doit être lisible dès la première seconde : c'est le sous-titre du plan 1.

## Contenu du dossier

```
00_A_LIRE_EN_PREMIER.md     ce document
01_message_a_coller.txt     le premier message pour la nouvelle conversation
images/                     les deux images validées (ingrédients pour Flow)
flow/etape1_test_flow.txt   étape 1 : les deux voix et les deux clips test (G01, G02)
flow/etape2_tous_les_plans.txt   étape 2 : les cartes G03 à G12, les secours G13 à G18, les règles
flow/prompts/               un prompt prêt à copier par carte (+ prise3/ : les 3es prises)
flow/flow_kit.json          tout le kit pour Claude (cartes, découpe des plans, secours, budget)
plan/                       découpage (shotlist.md/.json), dialogue, bible des personnages,
                            analyse des vidéos de référence, images de référence
outils/montage.py           l'outil de montage (+ sa police)
montage.json                le montage prêt à lancer (noms de fichiers G01 à G12)
sons/                       musique et bruitages de l'épisode 1
clips/                      c'est ici que vont toutes les prises
```

Tout l'historique du projet (3D, analyses, versions) est aussi sur GitHub : dépôt `lunar910/mindcare`, branche `ccr-025d044e-543zrn`, dossier `video3d/noxpico/ia`.
