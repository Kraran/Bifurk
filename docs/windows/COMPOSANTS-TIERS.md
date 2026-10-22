# Composants distribués avec Bifurk

L'archive inclut Python, PySide6 / Qt, shiboken6 et PyMuPDF / MuPDF, ainsi
que leurs bibliothèques natives collectées par PyInstaller. Les versions et
métadonnées Python sont conservées dans les dossiers `*.dist-info` de `_internal`.
Les plugins Qt peuvent inclure des bibliothèques multimédias supplémentaires.

- Python : licence PSF, <https://docs.python.org/3/license.html>.
- PySide6 / shiboken6 / Qt : licences LGPL / GPL ou commerciales selon le
  composant ; <https://doc.qt.io/qtforpython-6/licenses.html>.
- PyMuPDF / MuPDF : AGPL-3.0 ou licence commerciale Artifex ;
  <https://pymupdf.readthedocs.io/en/latest/about.html#license>.
  Le texte `COPYING` fourni par le paquet est inclus dans ses métadonnées.
- PyInstaller : GPL avec exception pour la distribution des exécutables ;
  <https://pyinstaller.org/en/stable/license.html>.

Les crédits et licences du portrait, des polices et des sons accompagnent les
assets sous `_internal/assets`. Les effets sonores Kenney sont CC0 ; le portrait reprend
une ressource du dépôt Gamelist Media Editor, dont la licence MIT est conservée.
La musique d’accueil `FantasyFair.m4a` fournie par l’utilisateur porte les
métadonnées « Tavern Loop One », Alexander Nakarada, album « Fantasy Fair ».
La licence CC0 des effets Kenney ne s’applique pas à cette musique.
Ces licences d'assets ne définissent pas la licence du code de Bifurk.

Les sources du projet sont sur <https://github.com/Kraran/Bifurk>. La révision
de compilation figure dans `COMPILATION.json`. Avant publication, vérifier les
conditions des versions effectivement embarquées, notamment celles de PyMuPDF
(AGPL ou licence commerciale) et les obligations de distribution de Qt.
Aucune licence générale de Bifurk n'est ajoutée par le script de compilation.
