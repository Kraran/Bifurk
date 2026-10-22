"""Identité, portrait, liens et absence de cadre dans la fenêtre À propos.

Exécution : python -m unittest discover -s tests -v, avec QT_QPA_PLATFORM=offscreen
pour une session sans écran. Les cas pilotent explicitement les jets et dialogues
nécessaires ; conserver ces contrôles pour éviter un test aléatoire ou bloquant.
Les tests nécessitant le PDF privé sont conditionnels et ne doivent pas embarquer
son texte ni publier leurs captures. Voir docs/maintenance.md pour les conventions."""
import unittest
from unittest.mock import patch, call

from PySide6.QtCore import Qt, QPoint, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QDialog

from main import MainWindow, ASSET_DIR
from about_dialog import AboutDialog, AuthorPortrait
from app_info import APP_NAME, APP_VERSION, AUTHOR_URL, REPOSITORY_URL


class AboutDialogTests(unittest.TestCase):
    """Scénarios de régression groupés ; chaque test décrit le comportement attendu."""
    @classmethod
    def setUpClass(cls):
        """Partager les ressources coûteuses de la suite, notamment l’application Qt unique."""
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        """Préparer un état indépendant pour éviter la contamination entre scénarios."""
        self.w = MainWindow()
        self.w.show()
        self.app.processEvents()

    def tearDown(self):
        """Libérer les ressources du scénario avant le test suivant."""
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def test_whole_brand_opens_about_without_changing_game(self):
        button = self.w.about_button
        title = button.findChild(QLabel, 'appTitle')
        subtitle = button.findChild(QLabel, 'subtitle')
        self.assertGreaterEqual(title.width(), title.sizeHint().width())
        self.assertGreaterEqual(subtitle.width(), subtitle.sizeHint().width())
        before = self.w._snapshot()
        points = [title.mapTo(button, QPoint(8, title.height() // 2)),
                  title.mapTo(button, title.rect().center()),
                  subtitle.mapTo(button, subtitle.rect().center())]
        with patch.object(AboutDialog, 'exec', return_value=QDialog.Accepted) as opened:
            for point in points:
                QTest.mouseClick(button, Qt.LeftButton, pos=point)
            button.setFocus()
            QTest.keyClick(button, Qt.Key_Space)
            self.assertEqual(opened.call_count, 4)
        self.assertEqual(self.w._snapshot(), before)
        self.w.resize(930, 800)
        self.app.processEvents()
        self.assertEqual(self.w.width(), 930)
        self.assertGreaterEqual(title.width(), title.sizeHint().width())

    def test_about_version_links_and_close(self):
        with patch('about_dialog.QDesktopServices.openUrl') as browse:
            dialog = AboutDialog(ASSET_DIR, self.w.theme, self.w)
            labels = '\n'.join(label.text() for label in dialog.findChildren(QLabel))
            self.assertIn(APP_VERSION, labels)
            self.assertIn('Franck Fornasari', labels)
            self.assertIn(REPOSITORY_URL, labels)
            browse.assert_not_called()
            dialog.findChild(QPushButton, 'aboutProfile').click()
            dialog.findChild(QPushButton, 'aboutRepository').click()
            self.assertEqual(browse.call_args_list, [call(QUrl(AUTHOR_URL)), call(QUrl(REPOSITORY_URL))])
            dialog.show()
            self.assertIsNone(dialog.findChild(QPushButton, 'aboutDismiss'))
            portrait = dialog.findChild(AuthorPortrait, 'aboutPortrait')
            self.app.processEvents()
            self.assertEqual(portrait.width(), 280)
            image = portrait.image_rect()
            self.assertLessEqual(image.width(), portrait.width())
            self.assertLessEqual(image.height(), portrait.height())
            self.assertAlmostEqual(image.width() / image.height(),
                                   portrait.pixmap.width() / portrait.pixmap.height(), delta=.005)
            self.assertAlmostEqual(image.width(), portrait.width(), delta=1)
            browse.reset_mock()
            QTest.mouseClick(portrait, Qt.LeftButton)
            browse.assert_called_once_with(QUrl(AUTHOR_URL))
            browse.reset_mock()
            portrait.setFocus()
            QTest.keyClick(portrait, Qt.Key_Space)
            browse.assert_called_once_with(QUrl(AUTHOR_URL))
            dialog.findChild(QPushButton, 'goldButton').click()
            self.assertEqual(dialog.result(), QDialog.Accepted)
            dialog.show()
            QTest.keyClick(dialog, Qt.Key_Escape)
            self.assertEqual(dialog.result(), QDialog.Rejected)
        self.assertEqual(self.w.windowTitle(), APP_NAME)
        self.assertEqual(APP_VERSION, '1.1.1')
        self.assertEqual(self.w._save_data()['version'], APP_VERSION)
