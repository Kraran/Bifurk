# Forêt : illustrations de l’édition reconnue

Le catalogue conserve 75 occurrences d’images du PDF privé : couverture,
25 illustrations narratives, carte, feuille d’aventure et 47 ornements.
Il ne contient aucun pixel du livre. Les coordonnées sont protégées par
l’empreinte SHA-256 exacte de cette édition.

Les 24 grandes scènes portent une légende imprimée qui donne directement
le numéro de paragraphe. Le mode d’emploi de l’Œil d’Ambre est situé entre
les en-têtes des §§91 et 92. Aucune association ne reste ambiguë après
contrôle visuel des légendes et de la page 52.

| Paragraphe | Page PDF | Vérification |
| --- | --- | --- |
| 1 | 18 | Légende imprimée |
| 15 | 25 | Légende imprimée |
| 29 | 30 | Légende imprimée |
| 38 | 33 | Légende imprimée |
| 49 | 37 | Légende imprimée |
| 57 | 40 | Légende imprimée |
| 69 | 44 | Légende imprimée |
| 90 | 51 | Légende imprimée |
| 91 | 52 | Position dans le §91 |
| 107 | 59 | Légende imprimée |
| 142 | 70 | Légende imprimée |
| 160 | 77 | Légende imprimée |
| 181 | 85 | Légende imprimée |
| 212 | 95 | Légende imprimée |
| 230 | 101 | Légende imprimée |
| 253 | 108 | Légende imprimée |
| 265 | 115 | Légende imprimée |
| 285 | 123 | Légende imprimée |
| 294 | 128 | Légende imprimée |
| 317 | 136 | Légende imprimée |
| 340 | 144 | Légende imprimée |
| 351 | 149 | Légende imprimée |
| 360 | 153 | Légende imprimée |
| 378 | 159 | Légende imprimée |
| 396 | 166 | Légende imprimée |

La carte (page 17) est incluse dans le prologue, pages 14 à 17, accessible
avant la partie et par Actions → Prologue et carte du livre pendant la
lecture. La feuille d’aventure (page 11) reste dans les pages de règles.
Les ornements n’apparaissent pas comme scènes de paragraphes.

Le lecteur emploie les cadrages existants pour l’aperçu et la fenêtre
d’agrandissement. Une page sans illustration efface la scène précédente.
L’ouverture d’une image ne joue aucun dé et ne modifie pas le héros.
Le titre de couverture suit désormais le livre ouvert.

Contrôles effectués : inventaire visuel des 75 images, lecture des légendes,
contrôle des limites des cadrages sur le PDF privé, aperçu Qt du §1,
agrandissement du §91 et carte du prologue. Les captures restent dans
audit-output, hors Git. Le PDF original n’est pas modifié et aucun
exécutable n’est compilé.

Validation finale : 611 tests exécutés, 610 réussites et un test ignoré faute
de PyInstaller ; les 156 tests de la Forêt passent. Les profils de livres
sans prologue restent compatibles. L’arbre testé inclut les corrections
d’audit locales encore séparées de cette PR.
