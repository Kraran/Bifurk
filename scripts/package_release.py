"""Créer l'archive Windows portable ou son brouillon de release GitHub.

Exécuté après PyInstaller par BUILD_EXE.bat. La sélection est limitée aux fichiers
livrés, jamais aux PDF, données ou fichiers temporaires présents dans le dépôt.
--draft nécessite GitHub CLI et n'effectue pas la publication publique.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_info import APP_VERSION, REPOSITORY_URL

ARCHIVE_NAME = f'Bifurk-v{APP_VERSION}-windows-x64.zip'
DOCUMENTS = {
    'LISEZ-MOI.txt': 'docs/windows/LISEZ-MOI.txt',
    'COMPOSANTS-TIERS.md': 'docs/windows/COMPOSANTS-TIERS.md',
    'NOUVEAUTES.md': 'docs/windows/RELEASE_NOTES.md',
    # Livre le dossier de musique personnelle (vide) avec son mode d'emploi.
    'musique_perso/LISEZMOI.txt': 'musique_perso/LISEZMOI.txt',
}


def release_files(bundle):
    """Valider le dossier construit puis sélectionner uniquement le runtime livré.

Refuser PDF, liens symboliques et données de jeu même dans _internal : mieux vaut
arrêter l'archivage que publier un fichier privé par accident.
"""
    if (bundle / 'Bifurk.exe').is_symlink() or (bundle / '_internal').is_symlink():
        raise ValueError('La compilation ne doit pas rediriger vers des fichiers externes.')
    # Contrôler aussi les ressources introduites depuis la précédente version :
    # un vieux dossier dist ne doit pas produire un ZIP partiellement utilisable.
    required = ('Bifurk.exe', '_internal/assets/bifurk.ico',
                '_internal/assets/themes/grimoire/theme.json',
                '_internal/assets/themes/grimoire/theme.qss',
                '_internal/assets/themes/grimoire/page-parchment.jpg',
                '_internal/assets/themes/grimoire/sheet-leather.png',
                '_internal/assets/marks/cite-tattoo.png',
                '_internal/assets/check-bronze.svg',
                '_internal/assets/illustration-background.jpg',
                '_internal/assets/cite.jpg',
                '_internal/assets/sounds/FantasyFair.m4a',
                '_internal/assets/video/introduction.mp4',
                '_internal/assets/sounds/swords.wav',
                '_internal/assets/sounds/book_sorcier.wav',
                '_internal/assets/sounds/book_foret.wav',
                '_internal/assets/sounds/book_cite.wav',
                '_internal/assets/sounds/book_sounds.json',
                '_internal/catalogues/modules/sorcier_montagne_feu_1982.json',
                '_internal/catalogues/evenements_sorcier_1982.json',
                '_internal/catalogues/sorcier_montagne_feu_1982.json',
                '_internal/catalogues/modules/foret_malediction_1983.json',
                '_internal/catalogues/foret_malediction_1983.json',
                '_internal/catalogues/evenements_foret_1983.json',
                '_internal/catalogues/modules/cite_voleurs_1983.json',
                '_internal/catalogues/cite_voleurs_1983.json',
                '_internal/catalogues/evenements_cite_1983.json')
    for name in required:
        if not (bundle / name).is_file():
            raise ValueError(f'Compilation incomplète : {name}')
    if (bundle / 'donnees').exists():
        raise ValueError('Le dossier compilé contient des données de jeu. Utilisez une compilation propre.')
    files = [bundle / 'Bifurk.exe']
    for path in sorted((bundle / '_internal').rglob('*')):
        relative = path.relative_to(bundle)
        if (path.is_symlink() or path.suffix.lower() == '.pdf'
                or 'donnees' in (part.casefold() for part in relative.parts)):
            raise ValueError(f'Fichier non distribuable : {relative}')
        if path.is_file():
            files.append(path)
    return files


def sha256(path):
    """Calculer l'empreinte sans charger toute la distribution en mémoire."""
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def source_commit(root):
    """Identifier la source de compilation ; un arbre modifié n'a pas de révision publiable exacte."""
    try:
        status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
        if status.strip():
            return None
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def package(root=ROOT):
    """Écrire atomiquement le ZIP versionné, puis son SHA-256 pour vérifier le téléchargement."""
    root = Path(root)
    bundle = root / 'dist' / 'Bifurk'
    files = release_files(bundle)
    destination = root / 'dist' / ARCHIVE_NAME
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, suffix='.zip.tmp')
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, 'Bifurk/' + path.relative_to(bundle).as_posix())
            for name, source in DOCUMENTS.items():
                archive.write(root / source, 'Bifurk/' + name)
            archive.writestr('Bifurk/COMPILATION.json', json.dumps({
                'version': APP_VERSION, 'target': 'windows-x64',
                'source_repository': REPOSITORY_URL, 'source_commit': source_commit(root),
            }, ensure_ascii=False, indent=2))
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    digest = sha256(destination)
    destination.with_suffix('.zip.sha256').write_text(f'{digest}  {destination.name}\n', encoding='ascii')
    return destination


def draft(root=ROOT):
    """Téléverser le ZIP existant et son empreinte dans une nouvelle release brouillon.

Ne pas reconstruire ici : l'archive doit être exactement celle testée. Sa révision
Git enregistrée sert de cible au tag, même si la branche courante a changé.
"""
    root = Path(root)
    archive = root / 'dist' / ARCHIVE_NAME
    checksum = archive.with_suffix('.zip.sha256')
    expected = checksum.read_text(encoding='ascii').split()[0]
    if sha256(archive) != expected:
        raise ValueError('Le ZIP a changé depuis sa préparation. Relancez BUILD_EXE.bat et testez-le.')
    with zipfile.ZipFile(archive) as content:
        manifest = json.loads(content.read('Bifurk/COMPILATION.json'))
    commit = manifest.get('source_commit')
    if manifest.get('version') != APP_VERSION or not commit:
        raise ValueError('Recompilez depuis une révision Git propre avant de préparer une release.')
    subprocess.run(['gh', 'auth', 'status'], check=True)
    subprocess.run([
        'gh', 'release', 'create', f'v{APP_VERSION}', str(archive), str(checksum),
        '--repo', 'Kraran/Bifurk', '--draft', '--target', commit,
        '--title', f'Bifurk {APP_VERSION}',
        '--notes-file', str(root / 'docs/windows/RELEASE_NOTES.md'),
    ], check=True)


def main():
    """Choisir l'archivage local ou la préparation explicite d'un brouillon distant."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', action='store_true', help='Créer un brouillon GitHub avec le ZIP déjà testé')
    args = parser.parse_args()
    try:
        if sys.platform != 'win32':
            raise ValueError('La distribution Windows doit être compilée et préparée sous Windows.')
        if args.draft:
            draft()
        else:
            print(f'Archive prête : {package()}')
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Erreur : {exc}\n')


if __name__ == '__main__':
    main()
