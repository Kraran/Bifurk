"""Les tests n'écrivent jamais dans les vraies données du joueur (donnees/, musique_perso/).

Exécution : python -m unittest tests.test_isolation_donnees
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import main

ROOT = Path(__file__).resolve().parents[1]
PROBE = 'import json, main; print(json.dumps([str(main.APP_DIR), str(main.DATA_DIR)]))'


def probe(env=None, argv0=None):
    code = PROBE if argv0 is None else f'import sys; sys.argv[0] = {argv0!r}; ' + PROBE
    output = subprocess.check_output([sys.executable, '-c', code], cwd=ROOT, text=True,
                                     env={**os.environ, **(env or {})})
    return [Path(p) for p in json.loads(output.strip().splitlines()[-1])]


class IsolationTests(unittest.TestCase):
    def test_this_test_run_uses_a_temporary_folder(self):
        self.assertNotEqual(main.APP_DIR, ROOT)
        self.assertTrue(main.APP_DIR.name.startswith('bifurk-tests-'))
        for folder in (main.DATA_DIR, main.SAVES_DIR, main.SETTINGS_DIR, main.BOOKS_DIR, main.MUSIC_DIR):
            self.assertTrue(folder.is_relative_to(main.APP_DIR), folder)
            self.assertFalse(folder.is_relative_to(ROOT), folder)

    def test_normal_launch_keeps_the_folder_next_to_the_program(self):
        env = {key: '' for key in ('BIFURK_DATA_ROOT',)}
        self.assertEqual(probe(env), [ROOT, ROOT / 'donnees'])

    def test_unittest_launcher_and_explicit_root(self):
        app, data = probe({'BIFURK_DATA_ROOT': ''}, argv0='python -m unittest')
        self.assertNotEqual(app, ROOT)
        self.assertTrue(app.name.startswith('bifurk-tests-'))
        self.assertFalse(app.exists())             # Effacé à la fin du processus.
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(probe({'BIFURK_DATA_ROOT': folder}),
                             [Path(folder).resolve(), Path(folder).resolve() / 'donnees'])


if __name__ == '__main__':
    unittest.main()
