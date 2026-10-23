# La Forêt de la Malédiction — module et présentation

Cette deuxième étape ajoute l'identité du livre et sa consultation, après
l'extraction du socle commun. Elle ne présente pas comme jouables des événements
qui n'ont pas encore été vérifiés.

## Édition reconnue

- Module : `foret_malediction_1983`, adaptateur `foret-1983`.
- Titre : **La Forêt de la Malédiction**.
- PDF privé fourni : 170 pages, 400 paragraphes retrouvés par l'extracteur.
- SHA-256 : `0abac11c0e88ce244c5513bf4b1537fa46159df5606d3e3c8c28b83e6614f6e1`.
- Couverture : page physique 1 ; cadrage contrôlé dans les limites de la page.
- Règles : pages physiques 4–13.
- Prologue « Un Marteau pour Gillibran » : pages physiques 14–16.

La couverture, les règles et le prologue sont rendus depuis le PDF importé par
le joueur. Aucun PDF, texte narratif ou pixel extrait du livre n'est distribué.
Les associations aux illustrations des paragraphes seront étudiées à l'étape 5.
Le décor neutre du thème est utilisé en attendant, sans reprendre celui du Sorcier.

## Parcours dans Bifurk

Le bouton **Grimoires…** ouvre une bibliothèque des PDF importés, avec miniatures,
titres et état de chaque aventure. Les deux aventures sont indiquées comme complètes depuis Bifurk 1.2.0. Le bouton d'import ouvre le sélecteur PDF existant.
Annuler la bibliothèque ne modifie pas la partie ; ouvrir un autre livre pendant
une partie demande confirmation de l'abandon de la progression non sauvegardée.

**Nouvelle partie** conserve le parcours direct lorsqu'un seul livre est disponible.
Avec plusieurs livres, il propose la bibliothèque et présélectionne le livre courant
ou le dernier ouvert. Le choix est mémorisé comme auparavant dans les préférences.
Les livres doivent être importés une première fois ; ils ne sont pas téléchargés.

Sur la couverture de la Forêt, le joueur retrouve la création commune et un bouton
**Lire le prologue**. Le prologue s'ouvre dans une fenêtre de pages PDF zoomables,
sans lancer de dés, modifier la fiche ni interrompre la musique. Le bouton permanent
**Règles** lit les pages du module courant. Changer d'aventure ferme les fenêtres
liées à l'ancien PDF ainsi que le combat éventuellement conservé.

Le profil de départ ajoute les **30 pièces d'or et la carte de Yaztromo** au matériel
commun. Le gabarit est reconstruit pour une nouvelle aventure, et non ajouté au
héros en place : ni un reroll, ni une lecture du prologue, ni le chargement d'une
sauvegarde ne redonnent ces ressources. Une sauvegarde de la Forêt conserve l'or
réellement restant. Le Sorcier garde son profil de départ existant.

Les emplacements affichent le titre du grimoire sur leur première ligne, sans
ajouter une quatrième ligne à la carte de sauvegarde. Les données conservent
l'identifiant du module et l'empreinte PDF ; le titre ajouté est une métadonnée
d'affichage, pas un critère de reconnaissance du livre.

## État des règles de l'aventure

`catalogues/evenements_foret_1983.json` contient **400 analyses documentaires**
et aucune entrée de règle exécutable. Les titres, choix et notes de mécanique
sont recensés ; leur automatisation reste en attente. L’adaptateur ne dépend
pas du contrôleur du Sorcier. Les renvois textuels permettent la consultation et
la sauvegarde de la position, mais n'appliquent pas de conditions ou d'effets.
Depuis l’étape 4, les rencontres explicitement intégrées activent la fenêtre de combat.
Les autres passages restent en consultation.

L'interface le précise dès la couverture et dans les passages. Les achats chez
Yaztromo, les objets magiques, rencontres, pertes/gains et fins d'aventure seront
intégrés progressivement après analyse. Passer aux §§86 ou 350 n'active notamment pas les règles
du Crocodile et des Piranhas du Sorcier.

## Fichiers et validation

- `catalogues/modules/foret_malediction_1983.json` : manifeste, pages et ressources initiales.
- `catalogues/foret_malediction_1983.json` : association de couverture.
- `catalogues/evenements_foret_1983.json` : revue documentaire des 400 paragraphes, distincte des règles exécutables.
- `grimoire_modules/foret/controller.py` : navigation de consultation sans automatismes.
- `grimoire_library.py` : bibliothèque, sélection et miniatures privées en mémoire.
- `tests/test_foret_presentation.py` : ouverture, prologue, profils, sauvegardes,
  changement de module, annulation et absence de règles implicites du Sorcier.

Les scénarios d'interface utilisent des PDF synthétiques. Un contrôle conditionnel
reconnaît également le PDF privé fourni et vérifie son cadrage. Le contrôle de
l'archive Windows exige les trois ressources de catalogue du nouveau module ;
les imports Python et le dossier catalogues sont déjà suivis par PyInstaller.
Aucune compilation Windows n'est nécessaire pour cette étape.

La revue des 400 paragraphes est documentée dans [le bilan d’analyse](reviews/foret-400-paragraphes.md). Les mécaniques intégrées sont détaillées dans [le bilan de l’étape 4](foret-mecaniques-particulieres.md). Le raccordement fonctionnel est clôturé en version 1.2.0 ; voir le [bilan final](reviews/2026-10-23-foret-cloture.md).
