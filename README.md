# Bifurk 1.0.13 — Français et mode portable

## Démarrage

```bash
pip install -r requirements.txt
python main.py
```

Bifurk crée à côté de `main.py` (ou de l'exécutable Windows empaqueté) :

```
Bifurk/
├── main.py
├── assets/
├── catalogues/
└── donnees/
    ├── grimoires/       # copies locales des PDF importés
    ├── sauvegardes/     # sauvegardes manuelles et autosave.json
    └── parametres/      # réservé aux futurs réglages
```

- Les sélecteurs Qt utilisent les libellés français ; les catalogues `qtbase_fr.qm` / `qt_fr.qm` sont chargés automatiquement depuis `translations/` ou les traductions de Qt si elles sont installées. Les commandes courantes et leurs infobulles disposent également d'une traduction de secours.
- Les PDF choisis en dehors de Bifurk sont **copiés** dans `donnees/grimoires/`. Le fichier d'origine n'est pas modifié.
- Les sauvegardes manuelles sont limitées à `donnees/sauvegardes/` et la sauvegarde automatique y est créée.
- Les chemins PDF des nouvelles sauvegardes sont relatifs au dossier Bifurk. Une ancienne sauvegarde peut importer automatiquement son PDF d'origine si celui-ci est toujours accessible.
- Les répertoires de données sont créés au démarrage. Bifurk doit donc être installé dans un dossier **accessible en écriture**, par exemple une clé USB ou un dossier personnel, et non dans `Program Files` protégé.
- Les dépendances Python restent nécessaires en mode source. Pour une distribution portable Windows autonome sans installation de Python, un empaquetage en exécutable sera nécessaire.

## Limites

Les dialogues Qt peuvent contenir des libellés propres à une version de Qt qui ne sont traduits intégralement que si les fichiers `.qm` correspondants sont présents. Les traductions de secours couvrent les libellés usuels du sélecteur, mais leur exhaustivité visuelle reste à vérifier sur Windows.

Le mode portable concerne les **données de Bifurk**. Windows, Python et Qt peuvent créer leurs propres caches ou fichiers temporaires hors du dossier de l'application ; une garantie absolue « aucune écriture extérieure par aucun composant » nécessite une validation spécifique de l'exécutable empaqueté.

## Tests de développement sur Windows

Depuis le dossier du projet, dans PowerShell (créer `.venv` seulement s’il n’existe pas) :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

Le PDF privé de référence, placé à la racine du projet, active les tests d’extraction et de rendu. Sans ce fichier, ces contrôles sont ignorés. Le cadrage de la couverture possède un défaut connu signalé comme échec attendu. Le PDF ne doit pas être ajouté à Git.

Pour tester visuellement après les tests :

```powershell
.\.venv\Scripts\python.exe main.py
```

Le catalogue couvre les 400 paragraphes de l’édition vérifiée. La logique du dernier lot et les scénarios de validation sont détaillés dans [la documentation des événements](catalogues/README_evenements.md).
