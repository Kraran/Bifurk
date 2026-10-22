# Vérification avant publication de Bifurk 1.1.2

## Périmètre

Revue des dernières évolutions d’interface, de leurs rafraîchissements et cycles
de vie, des données de cadrage, de l’identité de version et du chemin de
préparation de la distribution Windows. Les règles restent couvertes par la suite
complète, avec le PDF privé de référence présent dans l’environnement de test.

## Corrections apportées

- **Rafraîchissements** : le sac et les icônes ne sont plus reconstruits après
  une simple variation de caractéristique. La sélection et le défilement sont
  conservés. La signature est invalidée par les objets, l’arme équipée ou les
  couleurs des icônes. Les listes d’armes et le document des ennemis restent
  également stables tant que leur contenu ne change pas.
- **Fenêtres temporaires** : les sélecteurs de fichiers et les grandes
  illustrations libèrent leurs widgets après fermeture. Les minuteries de
  traduction et de retouche des fenêtres sont liées à leur dialogue.
  Trois fermetures immédiates reproduisaient trois rappels sur des objets C++
  détruits ; ce scénario est désormais couvert sans erreur.
- **Couverture** : la limite basse du cadrage dépassait la hauteur de la page PDF
  d’environ 2,46 points. Le rectangle est maintenant contenu dans la page. Le
  test anciennement marqué `expectedFailure` réussit normalement.
- **Distribution** : l’archivage vérifie aussi le QSS du thème, la coche SVG,
  l’illustration fixe et la musique d’accueil. Les notes de version sont incluses
  sous `NOUVEAUTES.md`. Les crédits distinguent effets CC0 et musique fournie.
- **Maintenance** : version 1.1.2 centralisée, notes et exemples Windows mis à
  jour, carte des modules et commentaires des invariants complétés. Le minimum
  PyMuPDF est aligné sur le module `pymupdf`, également utilisé par les audits
  et tests au lieu de l’entrée dépréciée `fitz`.

## Validation

- 48 fichiers Python analysés sans erreur de syntaxe ; `git diff --check` propre.
- **424 tests réussis**, sans échec attendu, en 45 secondes dans l’environnement
  Linux Qt `offscreen` ; PySide6 6.12.0 et PyMuPDF 2.0.
- Six nouveaux scénarios de préparation de version vérifient la conservation
  du sac, l’invalidation du cache, les listes de combat stables, la libération
  des fenêtres et les fermetures rapides. Le contrôle de distribution couvre
  l’absence des nouvelles ressources.
- Les tests de distribution utilisent des dossiers temporaires ; la sélection
  des données PyMuPDF du spec est exercée sans lancer PyInstaller.
- Cinq créations/fermetures de fenêtre principale puis collecte explicite
  n’ont laissé aucun objet dans `gc.garbage`.

## Livraison

Aucune compilation Windows, aucun ZIP binaire ni aucune release distante n’a été
créé pendant cette vérification. Après fusion, lancer `BUILD_EXE.bat` sur Windows,
tester le ZIP extrait dans un autre dossier, puis utiliser `PUBLISH_RELEASE.bat`
pour créer le brouillon GitHub. La vérification des périphériques audio, de la
barre native Windows et de l’exécutable compilé reste à effectuer sur ce ZIP.
