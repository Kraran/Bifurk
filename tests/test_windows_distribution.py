"""Contrats de distribution sans compilateur Windows ni compte GitHub.

Les faux dossiers de compilation sont temporaires. Les tests vérifient la
séparation des ressources / données, l'exclusion du livre privé et l'archive
effectivement téléversée ; aucun test ne crée de release distante.
"""
import json
import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import package_release as release


class WindowsDistributionTests(unittest.TestCase):
    """Sécurité et contenu de l'archive portable construite par BUILD_EXE.bat."""

    def test_build_dll_search_path_excludes_external_pdf_tools(self):
        from scripts.windows_build_environment import windows_build_path
        paths = windows_build_path(r'D:\jeu\.venv-build\Scripts\python.exe',
                                   r'C:\Python313', r'C:\Windows').split(';')
        self.assertEqual(paths, [r'D:\jeu\.venv-build\Scripts', r'C:\Python313',
                                 r'C:\Python313\DLLs', r'C:\Windows\System32', r'C:\Windows'])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bundle = self.root / 'dist' / 'Bifurk'
        for relative in ('Bifurk.exe', '_internal/assets/bifurk.ico',
                         '_internal/assets/themes/grimoire/theme.json',
                         '_internal/assets/themes/grimoire/theme.qss',
                         '_internal/assets/check-bronze.svg',
                         '_internal/assets/illustration-background.jpg',
                         '_internal/assets/sounds/FantasyFair.m4a',
                         '_internal/assets/video/introduction.mp4',
                         '_internal/assets/sounds/swords.wav',
                         '_internal/assets/sounds/book_sorcier.wav',
                         '_internal/assets/sounds/book_foret.wav',
                         '_internal/assets/sounds/book_sounds.json',
                         '_internal/catalogues/modules/sorcier_montagne_feu_1982.json',
                         '_internal/catalogues/evenements_sorcier_1982.json',
                         '_internal/catalogues/sorcier_montagne_feu_1982.json',
                         '_internal/catalogues/modules/foret_malediction_1983.json',
                         '_internal/catalogues/foret_malediction_1983.json',
                         '_internal/catalogues/evenements_foret_1983.json'):
            self.write(self.bundle / relative)
        for source in release.DOCUMENTS.values():
            self.write(self.root / source)
        self.write(self.root / 'docs/windows/RELEASE_NOTES.md')

    def write(self, path, data=b'test'):
        """Créer un fichier factice et ses parents dans le répertoire temporaire."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def package(self, commit='a' * 40):
        """Forcer la révision pour ne pas dépendre de l'état Git de la machine de test."""
        with patch.object(release, 'source_commit', return_value=commit):
            return release.package(self.root)

    def test_archive_excludes_repository_and_personal_files_and_has_checksum(self):
        self.write(self.root / 'livre-prive.pdf')
        self.write(self.root / 'donnees/sauvegardes/emplacement-1.json')
        self.write(self.bundle / 'fichier-sans-rapport.txt')
        archive = self.package()
        with zipfile.ZipFile(archive) as content:
            names = content.namelist()
            self.assertIn('Bifurk/Bifurk.exe', names)
            self.assertIn('Bifurk/_internal/assets/sounds/swords.wav', names)
            self.assertIn('Bifurk/LISEZ-MOI.txt', names)
            self.assertIn('Bifurk/NOUVEAUTES.md', names)
            self.assertFalse(any('donnees' in n or n.endswith('.pdf') or 'sans-rapport' in n for n in names))
            manifest = json.loads(content.read('Bifurk/COMPILATION.json'))
            self.assertEqual(manifest['source_commit'], 'a' * 40)
        self.assertEqual(archive.with_suffix('.zip.sha256').read_text().split()[0], release.sha256(archive))

    def test_incomplete_build_is_not_archived(self):
        (self.bundle / '_internal/assets/sounds/swords.wav').unlink()
        with self.assertRaisesRegex(ValueError, 'incomplète'):
            self.package()

    def test_new_interface_and_music_assets_are_required_for_release(self):
        """Refuser un ancien dossier dist auquel manquent les ressources de la 1.1.2."""
        for name in ('themes/grimoire/theme.qss', 'check-bronze.svg',
                     'illustration-background.jpg', 'sounds/FantasyFair.m4a'):
            with self.subTest(asset=name):
                path = self.bundle / '_internal/assets' / name
                path.unlink()
                try:
                    with self.assertRaisesRegex(ValueError, 'Compilation incomplète'):
                        self.package()
                finally:
                    self.write(path)

    def test_game_data_is_rejected_instead_of_published(self):
        for relative in ('donnees/sauvegardes/test.json', '_internal/DONNEES/test.json',
                         '_internal/assets/livre.PDF'):
            with self.subTest(relative=relative):
                path = self.bundle / relative
                self.write(path)
                with self.assertRaises(ValueError):
                    self.package()
                path.unlink()
                # Le dossier donnees, même vide, interdit une compilation réutilisée.
                if relative.startswith('donnees/'):
                    path.parent.rmdir()
                    path.parent.parent.rmdir()

    def test_packaging_error_preserves_previous_zip(self):
        archive = self.package()
        previous = archive.read_bytes()
        (self.root / release.DOCUMENTS['LISEZ-MOI.txt']).unlink()
        with self.assertRaises(OSError):
            self.package()
        self.assertEqual(archive.read_bytes(), previous)
        self.assertFalse(list(archive.parent.glob('*.zip.tmp')))

    def test_draft_uploads_tested_archive_without_rebuilding_or_publishing(self):
        archive = self.package()
        digest = release.sha256(archive)
        with patch.object(release.subprocess, 'run') as run:
            release.draft(self.root)
        command = run.call_args_list[-1].args[0]
        self.assertIn('--draft', command)
        self.assertEqual(command[command.index('--target') + 1], 'a' * 40)
        self.assertIn(str(archive), command)
        self.assertEqual(release.sha256(archive), digest)

    def test_changed_zip_or_uncommitted_sources_block_draft(self):
        archive = self.package(commit=None)
        with patch.object(release.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'révision Git propre'):
                release.draft(self.root)
            run.assert_not_called()
        archive.write_bytes(archive.read_bytes() + b'changed')
        with patch.object(release.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'ZIP a changé'):
                release.draft(self.root)
            run.assert_not_called()

    def test_frozen_resources_and_writable_data_have_separate_roots(self):
        # Importer dans un processus isolé évite de changer les constantes utilisées
        # par les autres suites. Aucun QApplication ni fenêtre n'est construit.
        code = '''
import json, sys
from pathlib import Path
sys.frozen = True
sys.executable = str(Path(sys.argv[1]) / 'Bifurk.exe')
import main
print(json.dumps([str(main.APP_DIR), str(main.DATA_DIR), str(main.ASSET_DIR)]))
'''
        output = subprocess.check_output([sys.executable, '-c', code, str(self.root)], cwd=ROOT, text=True)
        app, data, assets = map(Path, json.loads(output))
        self.assertEqual(app, self.root)
        self.assertEqual(data, self.root / 'donnees')
        self.assertEqual(assets, ROOT / 'assets')

    @unittest.skipUnless(importlib.util.find_spec('PyInstaller'), 'PyInstaller requis : environnement de compilation')
    def test_spec_collects_installed_pymupdf_layout_models_and_configuration(self):
        """Exécuter la sélection réelle du spec sans lancer le compilateur.

La liste attendue vient du paquet installé : ne pas figer le nom d'un modèle
qui peut changer entre versions. Les tests de jeu seuls ne détectent pas une
configuration ou un modèle absent du binaire.
"""
        package_root = Path(importlib.util.find_spec('pymupdf').origin).parent
        expected = {p.resolve() for p in (package_root / 'layout').rglob('*')
                    if p.suffix in ('.yaml', '.onnx')}
        if not expected:
            self.skipTest('Cette version PyMuPDF ne fournit pas de modèles de mise en page')
        collected = []

        def analysis(*args, **kwargs):
            collected.extend(Path(source).resolve() for source, destination in kwargs['datas'])
            return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])

        namespace = {'SPECPATH': str(ROOT), 'Analysis': analysis,
                     'PYZ': lambda *args, **kwargs: None,
                     'EXE': lambda *args, **kwargs: None,
                     'COLLECT': lambda *args, **kwargs: None}
        spec = ROOT / 'Bifurk.spec'
        with patch.dict(os.environ):
            exec(compile(spec.read_text(encoding='utf-8'), str(spec), 'exec'), namespace)
        self.assertFalse(expected - set(collected), f'Ressources PyMuPDF manquantes : {expected - set(collected)}')


if __name__ == '__main__':
    unittest.main()
