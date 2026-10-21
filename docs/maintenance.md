# Maintenir Bifurk

Ce guide décrit le code de la version 1.1.0. Les docstrings dans les modules
précisent les responsabilités, les effets de bord et les contraintes locales.
Les noms des méthodes et des tests permettent de retrouver les scénarios concernés.

## Carte du code

| Fichier | Responsabilité | Point d'entrée à lire |
| --- | --- | --- |
| `main.py` | Démarrage Qt, contrôleur, lecture, historique et persistance | `main`, `MainWindow`, `go_to`, `_track_action` |
| `book_events.py` | Calculs déterministes et effets du catalogue | `apply_effects`, `condition_met`, `apply_entry` |
| `book_actions.py` | Interactions particulières et combats complexes | `BookActions`, `perform_book_action` |
| `navigation.py` | Détection des renvois, libellés et HTML échappé | `destinations`, `render_links` |
| `rules_engine.py` | Suggestions heuristiques pour un texte non catalogué | `encounters`, `stat_events` |
| `illustrations.py` | Association PDF / catalogue / cadrages | `catalogue_for_pdf` |
| `grimoire_ui.py` | Parchemin, cartes de choix, titres, zoom et déplacement | `GrimoireScene`, `SingleLineTitle` |
| `rules_viewer.py` | Lecture des pages physiques 3–14 du PDF | `RulesDialog.render_page` |
| `save_slots.py` | Validation du format et menu des cinq sauvegardes | `read_save`, `SaveSlotsDialog` |
| `sound_effects.py` | Réglages, préchargement et demandes de sons | `SoundBank.play` |
| `pcm_audio.py` | Mélange des voix et sortie audio continue | `Mixer.readData`, `PcmEffect` |
| `themes.py` | Manifestes et substitution du QSS | `available_themes`, `Theme` |
| `about_dialog.py`, `app_info.py` | Identité, version, portrait et liens | `AboutDialog` |
| `scripts/prepare_sounds.py` | Reconstruction des WAV depuis les archives créditées | `prepare` |
| `tools/audit_pdf.py`, `tools/audit_windows.py` | Audits locaux et captures privées | `run`, `scenario` |

Le contrôleur hérite de `BookActions`. Ce mixin suppose les services et attributs
de `MainWindow` ; il ne représente pas une partie autonome. `book_events` ne dépend
pas de Qt : commencer par ce module pour comprendre une règle calculable.

## Démarrage et création

1. `main` prépare les dossiers, crée `QApplication`, conserve les traducteurs Qt
   puis affiche `MainWindow(startup=True)`.
2. Un timer ouvre le menu Nouvelle partie / Charger. Une nouvelle partie reprend
   le livre chargé, à défaut le dernier grimoire importé, sinon demande un PDF.
3. `_prepare_adventurer` effectue le tirage initial : Habileté 1d6+6,
   Endurance 2d6+12, Chance 1d6+6. L'écran de couverture demande le nom.
4. `_reroll_adventurer` autorise deux relances au maximum. La dernière valide
   automatiquement si le nom est renseigné ; sinon le tirage reste figé.
5. `_begin_adventure` accepte exactement le tirage affiché, réinitialise la
   progression, efface le brouillon puis entre au paragraphe 1.

Un rafraîchissement visuel ne doit pas relancer les dés. L'équipement provisoire
et le brouillon de création ne sont pas une sauvegarde en cours de partie.
Les tests construisent normalement `MainWindow()` sans menu modal initial.

## État et historique

`character` contient caractéristiques courantes, maxima `initial`, inventaire,
nom, monnaie et provisions, potion, équipement et faits particuliers du livre.
`book_state` conserve la progression locale par paragraphe ; `book_facts` mémorise
les événements durables ; `book_visits` compte les entrées. Leurs clés de
paragraphes sont des chaînes pour rester stables dans JSON.

Le contrôleur conserve aussi le paragraphe courant, la liste des lieux visités,
les transitions, les rencontres et leur statut, les événements déjà appliqués,
les adversaires déjà préparés et les phases des combats particuliers.

`_snapshot` copie cet ensemble, y compris les valeurs de l'adversaire dans les
widgets. Un nouvel état de jeu doit être ajouté à **la capture et la restauration**,
puis, s'il est obligatoire dans le format courant, à `read_save`. Les préférences,
les objets Qt, le texte du PDF et les ressources audio restent hors de l'instantané.

Les méthodes énumérées après `_track_action` sont enveloppées à la définition de
la classe. Le premier appel capture l'état ; les appels imbriqués partagent sa
transaction d'historique. À la sortie, le contrôleur termine les règles de combat
puis `_record` compare les états, ajoute Undo, vide Redo et écrit l'autosave.
Les limites sont 100 états annulables et 200 libellés d'historique.

Le bloc `finally` rétablit la profondeur d'appel et enregistre l'état effectivement
atteint : il ne constitue pas une annulation automatique en cas d'exception.
Valider les préconditions avant de commencer une mutation en plusieurs étapes.

`_restore` active `_restoring` pendant la reconstruction. `go_to` peut alors
rafraîchir la page sans appliquer une seconde fois effets, visites ou préparation
d'adversaire. Undo et chargement ne doivent ni octroyer un butin supplémentaire,
ni consommer un dé, ni rejouer les sons de résultat. Revenir par Undo à un héros
déjà accepté ne rend pas disponibles de nouvelles relances de création.

## Navigation et règles vérifiées

La détection des renvois reconnaît les formulations explicites françaises, y
compris les césures PDF. Les liens et boutons utilisent la même détection.
Le HTML échappe le texte avant d'insérer les ancres `paragraph:N`.

Pour l'édition connue, le catalogue n'est activé qu'après correspondance du
SHA-256 du fichier. Seules les entrées `status: verifie` sont exécutables comme
règles. Un PDF différent peut recevoir des suggestions heuristiques, soumises
à confirmation ; ne pas transformer une détection textuelle en effet automatique.

Lors d'une entrée réelle, `go_to` contrôle les verrous, mémorise la transition,
traite les effets spécifiques et automatiques, prépare les combats, puis actualise
le titre, le numéro, le texte, les commandes et l'image. Cet ordre est significatif.
Une route affichée reste à valider lors du clic : inventaire, coût, phase de combat
et décisions peuvent avoir changé.

Les marqueurs `completed_book_events` et `completed_optional_events` empêchent
les récompenses répétées. `prepared_book_encounters` évite de recréer un ennemi
lors d'un retour. Certains effets sont propres à chaque visite : les distinguer
des effets uniques dans `BookActions._enter_complex_book`.

`resolve_roll` choisit une branche à partir d'un total fourni ; il ne lance pas
les dés et ne modifie pas le héros. Les tests de Chance comparent la valeur
**avant** la dépense. Les soins usuels respectent les maxima initiaux. Changer ou
jeter une arme doit également mettre à jour ses bonus, pas seulement le sac.

Pour compléter le catalogue, lire [sa documentation](../catalogues/README_evenements.md),
implémenter le calcul réutilisable dans `book_events`, l'interaction dans
`book_actions` ou le contrôleur, puis couvrir réussite, échec, annulation et reprise.

## Fichiers et sauvegardes

Les chemins partent du script, ou de l'exécutable empaqueté :

- `donnees/grimoires/` : copies importées, nommées avec une empreinte du contenu ;
- `donnees/sauvegardes/emplacement-1.json` à `emplacement-5.json` : sauvegardes manuelles ;
- `donnees/sauvegardes/autosave.json` : état technique distinct, sans reprise automatique au démarrage ;
- `donnees/parametres/preferences.json` : thème, sons et dernier grimoire ;
- `donnees/parametres/audio.log` : journal audio borné, avec une rotation.

`_save_data` ajoute à l'instantané la version, la date ISO, le nom de l'aventurier,
la référence relative et l'empreinte PDF, ainsi que les piles Undo / Redo.
Le livre doit rester dans les grimoires importés. Aucun texte du livre n'est copié
dans la sauvegarde. Il n'existe pas de migration des formats anciens.

`read_save` valide les champs requis et les métadonnées de base ; ce n'est pas un
validateur exhaustif de toutes les structures imbriquées. `load_game` contrôle
ensuite le chemin et l'identité du PDF, recharge les catalogues, puis restaure.

`_write_atomic` écrit un temporaire dans le même répertoire, vide les buffers,
appelle `fsync` puis `os.replace`. Conserver ce protocole pour les sauvegardes.
Le menu demande confirmation avant remplacement, suppression et nouvelle partie
depuis Charger ; annuler doit laisser dialogue et partie dans leur état courant.

## Rendu Qt, PDF et thèmes

Les règles du jeu doivent rester dans l'état Python : une vue reconstruit sa
présentation et ne décide pas d'une récompense. Le QSS couvre les contrôles ;
les surfaces dessinées lisent également les couleurs du manifeste.
Voir [Thèmes et ambiance](themes-et-ambiance.md).

Pièges déjà rencontrés :

- Ne pas remettre `line-height` sur le `div` du lecteur : Qt applique la hauteur
  seulement au premier bloc dans ce rendu, créant un grand espace après la première ligne.
- `SingleLineTitle` adapte une copie de police, en points ou pixels selon Qt,
  sans modifier le libellé ni élargir tout le panneau.
- Le portrait utilise `QAbstractButton` : le QSS global des `QPushButton` avait
  réduit sa largeur utile. Conserver son rapport d'image et son activation clavier.
- Le label d'une carte de choix est transparent aux événements souris : toute
  la carte doit rester cliquable.
- Les coordonnées cataloguées utilisent des pages PDF base 1. Le rendu PyMuPDF
  et les listes Qt utilisent des index base zéro.
- `QImage` peut référencer les pixels du pixmap PyMuPDF : garder `image.copy()`
  avant que le document ou le pixmap source ne disparaisse.
- Les widgets retirés d'un layout sont détruits avec `deleteLater` ; Qt doit
  traiter ses événements pour achever leur nettoyage.

`GrimoireScene` ajuste une illustration entière avec le minimum des rapports de
largeur / hauteur. Le décor couvre la zone avec le maximum. Le zoom relatif va
de 1 à 12 et garde le point sous la souris ; le déplacement est borné au débordement.
Un clic recentre, un glissement déplace, un double clic émet `activated`.
Ces états visuels n'appartiennent pas à la sauvegarde.

## Audio et diagnostic Windows

`SoundBank` orchestre les sons ; `PcmEffect` charge les WAV et partage un seul
`QAudioSink` avec toutes les voix de la banque. `Mixer` fournit en permanence
des trames stéréo PCM 16 bits à 44,1 kHz, y compris du silence entre les actions.
Cette continuité évite la perte de l'attaque des effets très courts sur Windows.

Les assets sont mono 16 bits ; les sons à 22,05 kHz sont doublés en mémoire.
Le mélange additionne les voix et sature les échantillons pour empêcher le
débordement numérique. Les boucles infinies sont réservées à l'ambiance actuelle.
Ne pas ajouter d'accès aux widgets ou au disque dans le callback `readData`.
Arrêter le sink avant destruction du mixer pour éviter les rappels natifs tardifs.

Le signal `stateChanged` utilise une lambda **sans argument** qui relit l'état :
transmettre directement `QAudio::State` provoquait une erreur de conversion PySide
sur Windows. `setLoopCount` reçoit un entier, y compris lorsque le backend expose
une énumération pour `Infinite`.

Le son de page est demandé au changement de paragraphe ; les dés sont associés
au jet et les épées à l'assaut. `_play_state_sounds` choisit un résultat prioritaire
à partir de l'état avant / après. Aucun service audio ne tire de nombre aléatoire.
Sous `offscreen` ou `minimal`, le backend réel est désactivé : les tests automatisés
ne prouvent donc pas l'audibilité sur un périphérique Windows.

En cas de problème, consulter `audio.log`, tester la préécoute puis un vrai assaut.
La reconstruction des WAV utilise FFmpeg et les archives exactes du manifeste ;
le jeu ne nécessite pas l'exécutable FFmpeg pour lire ses WAV. Conserver les crédits
et licences de [assets/sounds](../assets/sounds).

## Vérification et livraison

Dans PowerShell, depuis `D:\Bifurk` avec les dépendances installées :

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
.\.venv\Scripts\python.exe main.py
```

Sous Linux :

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Les suites couvrent règles de référence, interactions complexes et finales,
chien de feu, cycle de partie, sauvegardes, carte, libellés, géométrie, À propos,
ambiance et PCM. Leurs docstrings et noms de tests indiquent les cas attendus.
Les tests remplacent les dialogues et jets nécessaires ; utiliser une seule
`QApplication`, fermer les fenêtres et traiter les destructions différées.

Le PDF privé de référence active les contrôles d'extraction et de cadrage ;
sans lui, ces tests sont ignorés. Un cadrage de couverture a un défaut connu
marqué comme échec attendu. Ne pas remplacer ce statut par un succès silencieux.
Les outils d'audit ne font pas partie des tests portables et leurs captures
peuvent contenir le livre. Ne publier ni PDF ni captures privées dans Git.

Avant une livraison fonctionnelle : lancer la suite, vérifier `git diff --check`,
puis tester visuellement création, navigation, combat, sauvegarde / chargement
et sons sur Windows pour les zones concernées. Pour une modification limitée aux
commentaires, comparer aussi les arbres syntaxiques en retirant les docstrings :
les instructions exécutables doivent rester identiques.

La version et la date publiques sont centralisées dans `app_info.py`. Une
modification documentaire seule ne nécessite pas une nouvelle version du jeu.
