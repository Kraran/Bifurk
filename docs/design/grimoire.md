# Le Grimoire

Disposition panoramique de la direction choisie : bordeaux, or patiné et page ivoire,
avec une bibliothèque fantastique illustrée plutôt qu’un fond de formulaire.
L’illustration occupe une colonne redimensionnable à gauche du récit ; la fiche
d’aventurier et la sacoche sont à droite.

![Lecture et choix](grimoire-interface.png)

![Combat et soins](grimoire-combat.png)

Ces captures utilisent un court récit de démonstration original, sans extrait du PDF privé.

## Utilisation

- Importer son propre PDF avec **✦ Grimoires…** puis **Importer un PDF…** ; un livre déjà importé s’ouvre avec **Ouvrir ce grimoire**.
- Choisir **Nouvelle partie** et valider l'aventurier tiré, ou charger une sauvegarde.
- Choisir une destination sur les cartes sous le récit ; les longs libellés reviennent à la ligne.
  Les cartes sont numérotées : les touches **1** à **9** activent le choix correspondant.
  Un choix indisponible reste visible mais grisé ; dans Le Sorcier, l’infobulle précise ce qui manque.
- À l’ouverture d’un livre catalogué, sa couverture apparaît à gauche et le titre occupe la page de texte. Après le choix du nom et de la potion, **Valider cet aventurier et commencer → §1** (ou **Commencer avec cet aventurier → §1** une fois les deux relances utilisées) ouvre le premier paragraphe et son illustration. Aucun paragraphe n’est marqué comme visité avant ce clic. Ensuite, les illustrations des paragraphes prennent le relais ; la couverture sert de fond en leur absence. Un double-clic sur l’image ouvre son agrandissement. Dans les deux vues, la molette zoome, un glisser avec le bouton gauche déplace l’image (curseur en croix), et un simple clic rétablit le cadrage intégral. Le zoom se réinitialise à chaque changement d’image. La fenêtre indépendante possède les boutons natifs de maximisation et de restauration, et le raccourci **F11**. Les boutons supplémentaires de plein écran et de taille initiale ont été retirés. Échap quitte le plein écran. Le bouton « Voir l’illustration du paragraphe » a été supprimé au profit du double-clic.
- Le bouton **◈ Masquer l’image** masque la colonne d’illustration pour libérer de la place. Les images cataloguées
  du livre remplacent le décor et restent intégralement cadrées ; le double-clic
  ouvre la vue détaillée. La bibliothèque est un décor générique, pas une scène du livre.
- **Sacoche & Trésors** présente les objets dans une grille de cases : icône, nom,
  badge de quantité et marque de l’arme équipée. L’en-tête replie ou déplie la sacoche.
  Un double-clic sur une arme l’équipe, un clic droit retire un objet ;
  **Gérer les objets…** déplie l’ajout et le retrait manuels.
- La fiche présente Habileté, Endurance et Chance sur des écus-jauges ; à 2 ou moins,
  l’écu pulse lentement en rouge. **Bourse & Vivres** affiche l’Or, les Provisions et la potion.
- **⚔ Combattre ⚔** n’apparaît que lorsqu’un combat est disponible. En bas de la fiche,
  les sceaux **Soins**, **Actions…**, **Carnet**, **Sauvegarder** et **Charger** remplacent
  les anciens onglets. La navigation manuelle par numéro se trouve dans **Actions…**.
- La barre du haut réunit **Annuler**, **Rétablir**, **Règles**, **Carte d’exploration**,
  **Grimoires…** et le menu **⚙** (Ambiance sonore, Plein écran, Mode lecture, Journal,
  À propos, Quitter le jeu).
- Les panneaux peuvent défiler séparément dans les petites fenêtres ; sous 1100 px de large,
  l’illustration se masque et la fiche se replie en bande verticale ouverte en tiroir
  (clic ou **Tab**). Le plein écran reste accessible par F11 et le mode lecture par F10.

## Tester sous Windows

Dans PowerShell, depuis le dossier du projet :

```powershell
git fetch origin
git switch master
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Vérifier la lecture, les choix et le défilement à 930 × 650 puis en plein écran ;
masquer l’illustration, changer la taille du texte (**A−** / **A+**), replier la sacoche, ouvrir le carnet,
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

Le bouton permanent **Règles** (ou **F1**) ouvre les pages de règles déclarées par le module du livre
chargé (pages **PDF 3 à 14** pour Le Sorcier, **4 à 13** pour La Forêt),
dans une fenêtre séparée non modale. Précédente, Suivante et la liste des pages permettent
de naviguer ; le zoom et le déplacement de l’image restent disponibles. Aucun texte privé
n’est distribué avec le programme : les pages sont rendues depuis le PDF de l’utilisateur.
