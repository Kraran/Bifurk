# Bifurk : audit de référence du 20 octobre 2026

## Périmètre et préservation

Audit du projet source Windows 1.0.13 avant correction fonctionnelle. Les quatre modules applicatifs, le README, les dépendances, les ressources, les licences de polices, le catalogue, l'ancien audit et la structure des données ont été examinés. Aucun changement dans `main.py`, `navigation.py`, `rules_engine.py`, `illustrations.py`, les ressources graphiques, le catalogue ou le PDF. Aucune fonctionnalité retirée. L'identité parchemin, cuir et bronze est conservée.

Dépôt Git local initialisé : commit de référence `f6dcd44`, étiquette `reference-1.0.13`. Les PDF, sauvegardes, données du joueur, environnement Python et sorties privées d'audit sont ignorés. Aucun dépôt distant ni envoi du livre. Les captures contenant le livre et les planches restent dans `audit-output/`, hors Git et hors livrables versionnés.

## Architecture existante

- `main.py` : fenêtre PySide6, thème et polices embarquées, extraction PDF, dialogues français, import portable, navigation, carte, feuille d'aventurier, inventaire, dés, potions, repas, combats, événements à confirmer, annulation/rétablissement et sauvegardes JSON atomiques.
- `navigation.py` : détection conservatrice des renvois français et création de liens HTML échappés.
- `rules_engine.py` : suggestions de rencontres, issues de combat, variations de caractéristiques et objets. Le joueur conserve la validation.
- `illustrations.py` et `catalogues/` : reconnaissance de l'édition par SHA-256, couverture et associations par coordonnées PDF. Pas d'OCR au lancement.
- `assets/` : icônes, textures et polices. `donnees/` : grimoires copiés, sauvegardes et emplacement réservé aux paramètres.

## Environnement et exécution

Windows, Python 3.13.0 x64, PySide6 6.12.0, PyMuPDF 2.0 (MuPDF 1.28.5). `pip install -r requirements.txt` confirme que les dépendances sont déjà installées ; `pip check` ne signale aucune incompatibilité. L'installation n'a nécessité aucun nouveau téléchargement. Pip a émis des avertissements de nettoyage de ses répertoires temporaires de sandbox, sans affecter sa vérification.

`requirements-reference.txt` fige les versions présentes pour documenter l'environnement observé ; la reconstruction dans un environnement neuf reste à tester. Les exigences originales sont conservées.

Lancement normal de `main.py` sur le bureau Windows, fenêtre réellement observée avec sa barre de titre bronze. Second lancement via le vrai point d'entrée `main()` instrumenté par `tools/audit_windows.py` : plateforme Qt `windows`, boucle événementielle réelle, 16 captures, aucune erreur de scénario. Le banc ferme ses fenêtres ; la fenêtre du lancement normal reste disponible.

Les captures Qt montrent la zone cliente ; elles ne constituent pas à elles seules un contrôle des décorations Windows. La barre de titre de la fenêtre principale a été vérifiée séparément à l'écran. Les barres de titre de toutes les fenêtres secondaires restent à contrôler individuellement.

## Résultats des tests

Commande : `.venv\Scripts\python.exe -m unittest discover -s tests -v`.

**13 tests : 9 réussites et 4 échecs attendus reproduisant des anomalies connues.** Un résultat `OK (expected failures=4)` ne signifie pas que ces anomalies sont corrigées. Chaque correction future devra retirer son marqueur `expectedFailure` et faire réussir le test correspondant.

Couverture : renvois multilignes et échappement HTML, règles simples et effet conditionnel, repas plafonné et annulation/rétablissement, JSON atomique, confinement des chemins, copie PDF identique et réutilisation de la copie, chemins de sauvegarde relatifs, autosave dans le dossier prévu et résolution après déplacement simulé. Les 400 paragraphes sont affichés successivement. Les 52 éléments du catalogue sont rendus et leurs références vérifiées.

Les tests isolent leurs écritures dans des répertoires temporaires sous Bifurk. Le scénario graphique désactive uniquement son autosave en mémoire pour préserver celle du joueur. Les empreintes de tous les fichiers de `donnees/` avant/après le scénario sont identiques.

## Livre et illustrations

PDF privé : SHA-256 `03a86d77c4323e126a37546caf62032aa57fd9e63edf005fbcc81fd6818d6d46`, 171 pages.

- Paragraphes : exactement 1 à 400, aucun absent, aucun numéro supplémentaire, tous non vides et affichables.
- Renvois explicites reconnus : 675 occurrences ; toutes ciblent un paragraphe présent. Ce décompte ne prouve pas que toutes les formulations du livre sont reconnues.
- Images : 52 occurrences raster dans le PDF et 52 entrées dans le catalogue. Aucune occurrence sans correspondance géométrique (tolérance de 3 points pour les coordonnées arrondies).
- Répartition : 1 couverture, 34 illustrations, 17 ornements exclus des fenêtres d'illustration. Les rendus des 52 entrées ont été testés et les deux planches privées ont été inspectées.
- Statuts du catalogue : 1 `verifie`, 17 `verifie_legende`, 5 `verifie_utilisateur`, 12 `a_confirmer`, 17 `hors_paragraphe`. Les statuts historiques ne sont pas transformés en nouvelles validations humaines par cet audit.

Associations encore provisoires : p39→§71, p52→§106, p67→§143, p82→§179, p102→§227, p106→§240, p121→§275, p129→§296, p140→§326, p163→§383, p167→§394, p170→§400. Les planches permettent de contrôler l'inventaire et le cadrage ; elles ne suffisent pas à certifier les associations narratives sans légende. Le texte du livre et les associations n'ont pas été modifiés.

`audit-output/pdf.json` contient un résultat par paragraphe et par image, avec longueurs et empreintes du texte, sans exporter le texte intégral. La fidélité littérale des 400 extractions n'a pas été vérifiée humainement ligne par ligne ; l'algorithme peut confondre des nombres isolés avec des titres sur d'autres éditions.

## Français et portabilité

Les deux catalogues `qtbase_fr` et `qt_fr` sont chargés depuis l'environnement PySide6. Ouverture, sauvegarde, chargement, Oui/Non, carte, rencontre, événement, inventaire et combat ont été capturés. Les six infobulles des sélecteurs sont françaises : Précédent, Suivant, Dossier parent, Créer un nouveau dossier, Vue en liste et Vue détaillée. Le relevé des textes, infobulles et noms accessibles est dans `audit-output/windows.json`.

La présence des traductions Qt est nécessaire pour une couverture complète : les secours du code ne traduisent pas tous les menus contextuels, erreurs système ou boutons de dialogues génériques. Les sous-dialogues de création de dossier, remplacement de fichier, permissions et les menus contextuels ne sont pas tous parcourus. La traduction est donc confirmée pour les parcours observés, pas pour toutes les branches Qt possibles.

Les écritures explicites de l'application examinées utilisent `donnees/`, y compris les fichiers temporaires d'import et de sauvegarde. Les sauvegardes manuelles sélectionnées hors de `donnees/sauvegardes` sont refusées par le code. Copie locale, référence relative et résolution après déplacement simulé passent les tests. L'ouverture normale crée les répertoires portables prévus.

La portabilité absolue reste **partiellement vérifiée** : pas de traçage exhaustif système des écritures Qt/Windows, du registre ou des caches ; pas d'exécutable autonome ni de test sur une seconde machine sans Python. Les éventuelles préférences internes de QFileDialog restent à instrumenter. Le déplacement simulé teste la résolution des chemins et l'autosave, pas l'ensemble d'une distribution installée ailleurs. La différence entre `APP_DIR` et le chemin `__file__` du catalogue devra être contrôlée lors de l'empaquetage.

## Anomalies avant correction

| ID | Priorité | Constat et reproduction | Conséquence |
|---|---|---|---|
| A01 | Haute | Charger une sauvegarde dans une fenêtre neuve : `load_game()` n'affecte jamais `illustration_catalogue`. Test attendu en échec. | Illustrations absentes après chargement ; un catalogue d'un livre précédemment ouvert pourrait aussi rester actif. |
| A02 | Haute | Gagner un assaut sans tenter la Chance, puis annuler. `_snapshot()` ne contient pas l'état de l'adversaire. Test attendu en échec. | L'Endurance ennemie ne revient pas à sa valeur précédente. Les assauts ne modifiant que l'ennemi peuvent ne produire aucune entrée annulable. La sauvegarde ne conserve pas non plus cet état. |
| A03 | Moyenne | Avec Chance = 0, lancer un test de Chance. Test attendu en échec. | La valeur interne devient -1, tandis que le champ Qt borné à 0 masque cet état. Les branches de combat décrémentent aussi sans borne. |
| A04 | Moyenne | Fenêtre de 930 × 650, paragraphe 1 : capture 16. | Boutons de choix écrasés verticalement, valeurs de caractéristiques et contenu latéral tronqués ; la barre horizontale rend le panneau peu pratique. Un débordement latéral existe aussi dans la capture d'accueil à 1380 × 850. |
| A05 | Moyenne | `_show_illustration()` n'a pas de libellé particulier pour `a_confirmer`. | Les 12 associations provisoires affichent « association vérifiée », information trompeuse. |
| A06 | Faible | Couverture `p1-x4` : hauteur du rectangle 844,50 points contre 842,04 pour la page. Test attendu en échec. | Dépassement de 2,46 points ; MuPDF produit néanmoins une image par intersection. |
| A07 | Moyenne | Comparer `AUDIT_ILLUSTRATIONS.md` au catalogue actuel. | Ancien rapport : 15 provisoires ; catalogue : 12. P86→§190, p132→§303 et p159→§370 sont validées utilisateur dans le catalogue, alors que le document indique encore §191, §305 et §372 provisoires. |
| A08 | Faible | Importer `fitz` avec PyMuPDF 2.0. | Avertissement de dépréciation de l'API `fitz` ; risque lors d'une future mise à jour puisque les dépendances d'origine n'ont pas de borne supérieure. |

Points supplémentaires issus de la lecture, non reproduits de bout en bout : un chargement invalide peut modifier `pdf_path` avant l'échec de vérification du hash ; l'échec d'autosave est silencieux ; l'extraction ne ferme pas explicitement son document PDF. Ces points ne sont pas présentés comme des incidents effectivement observés.

## Reproduction et suite

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\audit_pdf.py
.\.venv\Scripts\python.exe tools\audit_windows.py
.\.venv\Scripts\python.exe main.py
```

Les deux audits attendent le PDF privé à la racine. Les tests liés au PDF sont ignorés explicitement s'il manque. Le scénario Windows ouvre puis ferme ses dialogues automatiquement ; ses captures peuvent contenir le livre et restent privées. `audit-output/` ne doit pas être joint à une distribution publique.

Ordre proposé pour la phase suivante : chargement/catalogue, état des combats et historique, borne de Chance, présentation des associations provisoires, géométrie à petite taille, cohérence de la documentation, puis empaquetage et traçage de portabilité. Effectuer une correction isolée, ses tests et une capture si nécessaire avant de passer à la suivante. Aucune de ces corrections n'est appliquée dans cette référence d'audit.
