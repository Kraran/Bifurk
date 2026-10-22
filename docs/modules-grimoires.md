# Modules de grimoires

Un module associe une **édition exacte du PDF** à ses bases de données et à son
adaptateur de règles. Le PDF reste dans `donnees/grimoires`, jamais dans les
ressources distribuées. Importer un autre livre ne constitue pas son analyse :
les règles et associations doivent être vérifiées avant leur intégration.

Le [socle commun de Défis Fantastiques](socle-defis-fantastiques.md) fournit
désormais les règles réutilisables pour les aventures compatibles.

## Organisation actuelle

- `catalogues/modules/sorcier_montagne_feu_1982.json` : identité stable, SHA-256,
  moteur, nombre de paragraphes, intervalle physique des règles et chemins des bases.
- `catalogues/evenements_sorcier_1982.json` : événements, combats, itinéraires et effets.
- `catalogues/sorcier_montagne_feu_1982.json` : couverture et illustrations.
- `grimoire_modules/registry.py` : découverte et validation des manifestes,
  reconnaissance du PDF, chargement des bases et réparations propres à l'édition.
- `grimoire_modules/fighting_fantasy/` : calculs et commandes communes, sans exceptions de livre.
- `grimoire_modules/sorcier/actions.py` : interactions particulières de ce livre.
- `grimoire_modules/sorcier/controller.py` : combats, fuite, création, Chance,
  extensions des combats/soins, objets particuliers, navigation et commandes du récit.
  Création, potions et assauts ordinaires sont hérités du socle commun.
- `grimoire_modules/controller.py` : interface `ModuleActions` déléguant chaque
  commande au contrôleur du module ouvert, sans conserver une ancienne liaison.
- `book_actions.py` : ancien point d'import maintenu pour les outils.

Le lecteur garde les widgets, les jets, l'historique et l'état de partie.
`book_events.py` fournit les opérations déclaratives existantes ; leur vocabulaire
reste celui du moteur actuel. Le contrôleur du Sorcier construit aussi les commandes du récit et contrôle les
changements de paragraphe ; les vues communes affichent ses rencontres.
Ce découpage prépare d'autres systèmes de règles ; il ne prétend pas rendre
n'importe quel livre jouable en ajoutant seulement un fichier JSON.

## Intégrer un prochain grimoire

1. Identifier l'édition PDF et son SHA-256. Étudier les règles de création,
   caractéristiques, combats, fuite, soins, inventaire et victoire/mort.
2. Analyser tous les paragraphes : destinations, conditions, effets, rencontres,
   actions spéciales, noms de lieux et illustrations. Ne pas transformer une
   déduction heuristique en règle marquée `verifie`.
3. Créer des catalogues propres au livre et conservant la même empreinte PDF.
   Utiliser le vocabulaire existant seulement si sa sémantique est adaptée.
4. Ajouter un adaptateur Python dans `grimoire_modules/<livre>/`. Implémenter les
   commandes de `ModuleActions` et ajouter les extensions de présentation requises.
   Les signatures restent compatibles avec les signaux Qt et `_track_action`.
   Hériter de `FightingFantasyActions` si les règles correspondent, et ajouter
   les seules extensions nécessaires. Réutiliser les utilitaires compatibles, sans copier les numéros ou
   exceptions du Sorcier. Les méthodes de l'adaptateur reçoivent le contrôleur
   hôte : aucun état mutable ne doit vivre sur la classe du registre.
5. Déclarer le moteur dans `registry.SUPPORTED_ENGINES` et
   `controller.CONTROLLERS`, puis ajouter le manifeste dans `catalogues/modules`.
   Les adaptateurs livrés sont `sorcier-1982` et `foret-1983` ; ce dernier
   reste en préparation avec les [mécaniques particulières intégrées](foret-mecaniques-particulieres.md).
6. Tester les règles ordinaires et les exceptions avec des jets contrôlés, puis
   les changements de livre, sauvegardes, chargements et annulations. Ajouter au
   besoin les contrôles de ressources dans `scripts/package_release.py`.

Les chemins des catalogues sont relatifs à `catalogues/`. Les sorties du dossier,
ressources absentes, moteurs inconnus, intervalles invalides, identités/empreintes
dupliquées et bases d'une autre édition sont refusés. Aucun code Python indiqué
arbitrairement dans un manifeste n'est exécuté.

## Métadonnées de présentation

Les champs optionnels `intro_pages` et `intro_title` décrivent le prologue PDF.
`status` vaut `ready` ou `preview`. `starting_gold` et `starting_items` configurent
les ressources de départ d'une nouvelle partie, jamais celles d'un héros chargé.
Les valeurs absentes conservent le parcours du Sorcier et les tests de modules
simples. Le détail du second module est dans
[La Forêt — présentation](foret-module-presentation.md).

## Sauvegardes et distribution

Une sauvegarde enregistre `module_id` en plus de l'empreinte du livre. Au chargement,
une identité incohérente est rejetée avant de remplacer l'état courant. Les parties
1.1.2 sans ce champ continuent de sélectionner leur édition par le SHA-256 du PDF,
sans conversion du fichier. Le contenu des catalogues n'est pas copié dans les slots.

Un PDF inconnu reste dans le mode manuel existant : aucun catalogue connu ni
réparation du Sorcier ne lui est attribué. Les pages 3–14 restent le repli du
lecteur manuel ; un module reconnu fournit son propre intervalle de règles.

PyInstaller suit les imports Python des adaptateurs ; le dossier `catalogues`
est déjà distribué récursivement, manifestes compris. Le contrôle du ZIP exige
maintenant aussi le manifeste du Sorcier. Aucune dépendance supplémentaire.

Tests : `python -m unittest discover -s tests` ; le contrat spécifique aux modules
est couvert dans `tests/test_grimoire_modules.py`, avec deux bases fictives et sans
publier le texte d'un livre.
