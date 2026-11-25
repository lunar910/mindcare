# Nox & Pico — version « tout IA »

Nouvelle méthode décidée le 25 novembre 2026 : on abandonne la 3D faite à la main (dossier `../ps2`)
et on fabrique le sketch comme les vidéos de référence, avec des outils de génération.

1. Une image fixe par cadrage (personnages + atelier).
2. Un clip généré par réplique : l'outil vidéo fabrique aussi la voix et le mouvement des lèvres.
3. Montage, sous-titres et musique ajoutés ensuite avec `montage.py`.

## Décisions prises

| Sujet | Décision |
| --- | --- |
| Style | « Essai 1 » : `refs/nox_ref.png` et `refs/pico_ref.png` (rendu dessiné, aplats et contours) |
| Format | 4:3 comme les références, sous-titres blancs en bas, une réplique par plan |
| Extrait pilote | Début de l'épisode 1 (Pico débarque chez Nox), 30 à 45 s |
| Outil | Higgsfield : images avec Nano Banana 2.1, clips avec Seedance |
| Financement | Essai gratuit de 3 jours, à démarrer par l'auteur quand tout est prêt, renouvellement à annuler aussitôt |

Sur Higgsfield, les deux images validées sont les générations `82401413-858b-4123-9707-13d5751a1be1` (Nox)
et `a6317df2-181e-4e63-a54f-a99782da787f` (Pico) : ces identifiants servent directement de référence.

## Ce qu'on sait, ce qu'on ne sait pas

- L'offre gratuite refuse la vidéo (« Requires basic plan or higher »).
- Tarifs relevés : environ 1,5 crédit par image, 0,5 crédit par seconde de clip parlant en 480p.
- Non testé : la qualité du français parlé, et si la voix reste la même d'un plan à l'autre.
  C'est le premier essai à faire dès que la vidéo est débloquée.

`contexte/` contient l'enquête (méthode des créateurs, outils, voix, prix) et le découpage plan par plan
des deux vidéos de référence. `essais/` contient les images du test de style.

## Montage

```
python3 montage.py qc clips/s02_prise1.mp4      # planche d'images + repérage de la parole d'une prise
python3 montage.py build edit.json               # coupes calées sur la parole, sous-titres, musique, export
```

`build` écrit le film en 4:3, une version verticale 1080×1920 et un rapport des coupes.
Le format de `edit.json` est décrit en tête de `montage.py`.

## Découpage final (11 plans, environ 32 s)

`shotlist.md` (en français) et `shotlist.json` : du début de l'épisode 1 jusqu'à « Elle t'éclaire. Nuance. ».
Choisi par un panel de trois découpages (référence, comédie, sécurité IA) puis relu deux fois
(français et comédie, pièges techniques). Le texte validé est gardé mot pour mot.

## Outil de génération : Google Flow (depuis le 25 novembre)

Higgsfield refusant la vidéo sans abonnement, la génération passe par Google Flow (offre Google AI
étudiant : 1 000 crédits par mois). Flow n'a pas d'accès automatique : les clips sont générés à la main
avec les consignes de `flow/`, puis renvoyés pour le montage.

- Modèle : Omni Flash 1.2 en mode « Ingrédients » (les deux images validées comme références),
  seul mode où une voix créée dans Flow (« Nox », « Pico ») reste la même d'un clip à l'autre.
- Format 16:9, recadré au centre en 4:3 au montage. Environ 3 crédits par seconde en 720p.
- `flow/etape1_test_flow.txt` : création des deux voix et deux clips test (G01 Nox, G02 Pico).
- `flow/etape2_tous_les_plans.txt` : les 10 clips de l'étape 2 (cartes G03 à G12), les secours G13 à G18,
  la règle des trois prises, le budget (192 crédits pour une prise de chaque, environ 350 avec les
  reprises, arrêt à 450). `flow/prompts/` : un prompt prêt à copier par carte, plus les 3es prises.
- `flow/flow_kit.json` : le même kit pour Claude, avec la découpe de chaque plan (`shots_map`).
  Les trois fichiers sont produits par `flow/build_flow_kit.py`, qui vérifie chaque prompt.

`suite/` contient le guide de reprise (`00_A_LIRE_EN_PREMIER.md`), le premier message pour une nouvelle
conversation et `montage.json`, le montage prêt à lancer avec les clips nommés G01 à G12. Le zip
envoyé à l'utilisateur contient aussi les images, les sons et l'outil de montage.

`montage.py` sait aussi retourner une prise (`hflip`) et couper les bruitages (`from`, `dur`,
`until_shot`) : sans ça, un bruitage jouait jusqu'au bout de son fichier.

Le dossier `seedance/` garde la version des consignes écrite pour Higgsfield (Seedance), avec son
mode d'emploi : elle sert si l'on revient à cet outil.
