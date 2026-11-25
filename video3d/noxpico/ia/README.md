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
