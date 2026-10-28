# Manette

`gamepad.py` ajoute la manette sans dépendance : XInput est appelée par `ctypes`
(`xinput1_4.dll`, sinon `xinput1_3` ou `xinput9_1_0`, présentes dans Windows). Hors
Windows, `XInputBackend.create()` renvoie `None` et rien ne tourne. Les manettes
PlayStation ou génériques passent par Steam Input ou DS4Windows, qui les présentent
en XInput.

## Lecture (`XInputBackend`, `GamepadPoller`)

- Lecture toutes les 16 ms, uniquement quand Bifurk est l'application active ; seul
  l'emplacement de la manette connue est lu, les quatre emplacements sont réexaminés
  toutes les 1,5 s quand aucune n'est branchée (lire un emplacement vide est lent).
- Zones mortes XInput standard (sticks 7849/8689, gâchettes 30). Le stick gauche
  au-delà de 55 % et la croix donnent les directions ; LT/RT au-delà de 50 %.
- Directions répétées après 380 ms, puis toutes les 110 ms ; les autres boutons
  n'agissent qu'à l'appui.
- Les appuis sont traités au tour de boucle suivant (`QTimer.singleShot(0)`) : un
  clic qui ouvre un dialogue modal (`exec()`) laisse la manette piloter ce dialogue.

## Navigation (`GamepadNavigator`)

La cible est le menu ouvert, sinon le dialogue modal, sinon la fenêtre active.

- **Contrôles sélectionnables** : boutons (`QAbstractButton`), listes déroulantes non
  éditables, curseurs, listes et grilles (sacoche), onglets, compteurs des dialogues.
  Jamais les champs de saisie (nom de l'aventurier, notes du carnet), ni les compteurs
  de la fenêtre principale : ce sont les corrections manuelles de la fiche, qui
  marquent la partie « assistée » et restent à la souris ou au clavier.
- **Directions** : d'abord dans le contrôle (case suivante de la sacoche, valeur d'un
  curseur ou d'une liste déroulante, onglet voisin), puis vers le contrôle le plus
  proche dans ce sens (cône d'environ 50°, les contrôles alignés sont préférés).
  Le contrôle choisi est ramené dans la zone visible des panneaux défilants.
- **A** : clic, case cochée, liste déroulante ouverte, objet activé ; un objet de la
  sacoche ouvre son menu contextuel. **B** : Échap dans les dialogues et les menus.
- **Première sélection** : le premier choix du paragraphe, Grimoires sans livre ;
  dans un dialogue, le contrôle qui a le focus ou le bouton par défaut. La sélection de
  chaque fenêtre est retenue : fermer un dialogue ramène à l'ancienne. Si la sélection
  disparaît (paragraphe suivant), le premier choix est repris.
- **Halo** (`FocusHalo`) : cadre doré du thème (`gamepad_halo_color`) peint au-dessus
  de la fenêtre, transparent pour la souris ; il s'efface au premier clic, à la molette,
  à une touche du clavier ou après un déplacement de souris de plus de 12 pixels.

## Crochets de la fenêtre principale (`main.py`)

`gamepad_command` (X lecture vocale, Y Annuler, Menu Réglages, Affichage mode lecture,
LT/RT taille du texte, clic du stick droit carnet, B fermeture du carnet, du tiroir ou
du mode lecture), `gamepad_scope` (carnet ou fiche en tiroir : la sélection y reste),
`gamepad_default`, `gamepad_zones` (bandeau, page, fiche pour LB/RB) et
`gamepad_scroll_area` (le texte du livre pour le stick droit).

La préférence `gamepad_enabled` (vrai par défaut) se règle dans **Réglages → Manette…**.

## Tests

`tests/test_manette.py` remplace `XInputGetState` par une fonction Python et éprouve
la répétition, la navigation, le halo et les commandes de la fenêtre principale.
