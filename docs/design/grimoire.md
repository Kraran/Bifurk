# Le Grimoire

Disposition panoramique de la direction choisie : bordeaux, or patiné et page ivoire,
avec une bibliothèque fantastique illustrée plutôt qu’un fond de formulaire.
L’illustration occupe une colonne redimensionnable à gauche du récit ; la fiche
d’aventurier et l’inventaire compact sont à droite.

![Lecture et choix](grimoire-interface.png)

![Combat et soins](grimoire-combat.png)

Ces captures utilisent un court récit de démonstration original, sans extrait du PDF privé.

## Utilisation

- Importer le PDF avec **Ouvrir un grimoire**.
- Choisir **Nouvelle partie** et valider l'aventurier tiré, ou charger une sauvegarde.
- Choisir une destination sur les cartes sous le récit ; les longs libellés reviennent à la ligne.
- À l’ouverture d’un livre catalogué, sa couverture apparaît à gauche et le titre occupe la page de texte. **Commencer l’aventure → §1** ouvre le premier paragraphe et son illustration. Aucun paragraphe n’est marqué comme visité avant ce clic. Ensuite, les illustrations des paragraphes prennent le relais ; la couverture sert de fond en leur absence. Un double-clic sur l’image ouvre son agrandissement. Dans les deux vues, la molette zoome, un glisser avec le bouton gauche déplace l’image (curseur en croix), et un simple clic rétablit le cadrage intégral. Le zoom se réinitialise à chaque changement d’image. La fenêtre indépendante possède les boutons natifs de maximisation et de restauration, et le raccourci **F11**. Les boutons supplémentaires de plein écran et de taille initiale ont été retirés. Échap quitte le plein écran. Le bouton « Voir l’illustration du paragraphe » a été supprimé au profit du double-clic.
- Le bouton **Image** masque la colonne d’illustration pour libérer de la place. Les images cataloguées
  du livre remplacent le décor et restent intégralement cadrées ; le double-clic
  ouvre la vue détaillée. La bibliothèque est un décor générique, pas une scène du livre.
- La sacoche utilise des lignes compactes. **Gérer les objets…** déplie l’ajout et le retrait ; les noms des objets restent visibles.
- La fiche affiche valeurs et jauges numériques. La **Sacoche** reste dans le lecteur ;
  **Combattre / Reprendre**, **Soins** et **Actions…** remplacent les anciens onglets.
  La navigation manuelle par numéro se trouve dans **Actions…**.
- Les panneaux peuvent défiler séparément dans les petites fenêtres ; le plein écran reste accessible par F11.

## Tester sous Windows

Dans PowerShell, depuis le dossier du projet :

```powershell
git fetch origin
git switch feat/sons-libres-reactifs
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Vérifier la lecture, les choix et le défilement à 930 × 650 puis en plein écran ;
masquer l’illustration, changer la taille du texte, ouvrir les trois onglets,
charger une sauvegarde et résoudre un combat. Pour le PDF catalogué, vérifier
qu’une illustration apparaît dans la page et que son agrandissement fonctionne.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

L’illustration `assets/grimoire-library.png` a été générée pour cette interface.
Les emblèmes de l’inventaire sont dessinés en vecteur et ne dépendent pas des polices emoji du système.
Validation graphique effectuée avec Qt hors écran sous Linux ; le rendu Windows reste à vérifier localement.

La texture de parchemin fournie dans `assets/parchment.jpg` est peinte sur toute la page ; le lecteur et les sections la laissent apparaître sans répétition de motif.

## Carte et règles

La carte affiche les adversaires rencontrés et leur issue (rencontré, vaincu, fui ou repoussé).
Cet historique suit les sauvegardes, l’annulation et le rétablissement. Seules les
rencontres enregistrées pendant la partie sont affichées.

Le bouton permanent **Règles** (ou **F1**) ouvre les pages **PDF 3 à 14** du livre chargé,
dans une fenêtre séparée non modale. Précédente, Suivante et la liste des pages permettent
de naviguer ; le zoom et le déplacement de l’image restent disponibles. Aucun texte privé
n’est distribué avec le programme : les pages sont rendues depuis le PDF de l’utilisateur.
