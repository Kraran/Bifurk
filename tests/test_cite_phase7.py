"""Cité des Voleurs, phase 7 : annonce sonore, décor de lecture et catalogue d’illustrations.

Couverture lue à la volée (page 1 du PDF) ; illustrations pleine page associées à leur
paragraphe, vignettes et ornements exclus des popups. Aucun texte ni image du livre :
le contrôle des coordonnées sur l’édition réelle ne s’exécute que si elle est présente.
"""
import gc
import json
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel

import main
from grimoire_modules.registry import pdf_digest
from illustrations import images_for_paragraph
from sound_effects import BOOK_SOUNDS, SoundBank
from tests.test_cite_presentation import CATALOGUES, CitePresentationTests
from tests.test_sound_feedback import FakeEffect

# Illustrations pleine page : numéro lu dans la légende imprimée (page PDF → paragraphe).
CAPTIONED = {19: 1, 26: 17, 30: 27, 32: 31, 37: 40, 46: 62, 53: 80, 77: 148, 98: 203,
             106: 224, 112: 239, 117: 250, 122: 265, 125: 271, 132: 292, 137: 307,
             142: 319, 147: 329, 153: 344, 155: 349, 160: 356, 166: 370, 175: 398}
# Sans légende : placée dans le texte du paragraphe, ou association confirmée par le joueur.
BY_POSITION = {64: 113}
CONFIRMED = {56: 88, 72: 135, 86: 171}


def private_pdf():
    """Chercher l’édition réelle aux mêmes endroits que test_cite_presentation."""
    root = Path(__file__).resolve().parents[1]
    candidates = [*root.glob('*.pdf'), *(root/'donnees/grimoires').glob('*.pdf'),
                  *(root.parent/'attachments').rglob('*.pdf')]
    digest = catalogue()['pdf_sha256']
    return next((path for path in candidates if pdf_digest(path) == digest), None)


def catalogue():
    return json.loads((CATALOGUES/'cite_voleurs_1983.json').read_text(encoding='utf-8'))


class CiteIllustrationCatalogueTests(unittest.TestCase):
    def test_cover_stays_first_and_ids_are_unique(self):
        entries = catalogue()['illustrations']
        self.assertEqual(entries[0]['id'], 'couverture')
        self.assertEqual(entries[0]['page_pdf'], 1)
        ids = [entry['id'] for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        for entry in entries[1:]:
            self.assertRegex(entry['id'], rf"^cite-p{entry['page_pdf']}-image\d+$")
            self.assertTrue(2 <= entry['page_pdf'] <= 177)
            x0, y0, x1, y1 = entry['rect']
            self.assertTrue(x0 < x1 and y0 < y1)

    def test_full_page_illustrations_map_to_their_paragraph(self):
        entries = catalogue()['illustrations']
        art = [entry for entry in entries if entry['type'] == 'illustration']
        expected = ({page: (number, 'verifie_legende') for page, number in CAPTIONED.items()}
                    | {page: (number, 'verifie_position') for page, number in BY_POSITION.items()}
                    | {page: (number, 'verifie_utilisateur') for page, number in CONFIRMED.items()})
        self.assertEqual({entry['page_pdf']: (entry['paragraphes'][0], entry['statut']) for entry in art},
                         expected)
        self.assertTrue(all(len(entry['paragraphes']) == 1 for entry in art))
        for entry in art:
            self.assertNotIn('probable', entry['statut'])
            self.assertNotIn('concordante', entry.get('note', ''))
        data = catalogue()
        for number in range(1, 401):
            shown = [entry['page_pdf'] for entry in images_for_paragraph(data, number)]
            pages = [page for page, (target, _status) in expected.items() if target == number]
            self.assertEqual(shown, pages, number)

    def test_ornaments_and_adventure_sheet_never_open_a_popup(self):
        entries = catalogue()['illustrations']
        others = [entry for entry in entries[1:] if entry['type'] != 'illustration']
        self.assertEqual({entry['type'] for entry in others}, {'ornement', 'feuille_aventure'})
        self.assertEqual([entry['page_pdf'] for entry in others if entry['type'] == 'feuille_aventure'], [5])
        for entry in others:
            self.assertEqual((entry['statut'], entry['paragraphes']), ('hors_paragraphe', []))
        audit = catalogue()['audit']
        self.assertEqual(audit['illustrations'], 27)
        self.assertEqual(audit['ornements_exclus_des_popups'],
                         sum(entry['type'] == 'ornement' for entry in entries))

    def test_private_pdf_every_image_is_catalogued_at_its_place(self):
        path = private_pdf()
        if path is None:
            self.skipTest('Édition PDF privée absente.')
        with pymupdf.open(path) as document:
            found = [(number, image['bbox']) for number, page in enumerate(document, 1)
                     for image in page.get_image_info()]
            entries = catalogue()['illustrations']
            self.assertEqual(len(entries), len(found))
            for entry in entries:
                rect = pymupdf.Rect(entry['rect'])
                page = document[entry['page_pdf'] - 1]
                self.assertTrue(page.rect.contains(rect), entry['id'])
                self.assertTrue(any(number == entry['page_pdf']
                                    and max(abs(a-b) for a, b in zip(rect, bbox)) < 3
                                    for number, bbox in found), entry['id'])
                if entry['type'] == 'illustration' and entry['statut'] != 'verifie_position':
                    # Pleine page : au moins 30 % de la page.
                    self.assertGreater(rect.get_area(), .3*page.rect.get_area(), entry['id'])
                if entry['type'] == 'ornement':
                    self.assertLess(rect.get_area(), .1*page.rect.get_area(), entry['id'])


class CiteAmbienceAssetTests(unittest.TestCase):
    def test_announcement_is_prepared_like_the_other_books(self):
        self.assertEqual(BOOK_SOUNDS, {'sorcier-1982': 'book_sorcier', 'foret-1983': 'book_foret',
                                       'cite-1983': 'book_cite'})
        manifest = json.loads((main.ASSET_DIR/'sounds/book_sounds.json').read_text(encoding='utf-8'))
        entry = manifest['sounds']['book_cite']
        self.assertAlmostEqual(entry['rms_dbfs'], -21.0, places=1)
        self.assertLessEqual(entry['peak_dbfs'], -2.0)
        with wave.open(str(main.ASSET_DIR/'sounds/book_cite.wav')) as stream:
            self.assertEqual((stream.getnchannels(), stream.getsampwidth(), stream.getframerate()),
                             (1, 2, 22050))
            self.assertLess(stream.getnframes()/stream.getframerate(), 3)

    def test_background_matches_the_forest_format(self):
        cite = QImage(str(main.ASSET_DIR/'cite.jpg'))
        forest = QImage(str(main.ASSET_DIR/'foret.jpg'))
        self.assertFalse(cite.isNull())
        self.assertEqual(cite.size(), forest.size())
        self.assertLess((main.ASSET_DIR/'cite.jpg').stat().st_size, 1_200_000)
        self.assertEqual(main.BOOK_BACKGROUNDS, {'foret-1983': 'foret.jpg', 'cite-1983': 'cite.jpg'})

    def test_city_announcement_replaces_the_previous_one(self):
        with patch.object(SoundBank, '_backend', return_value=FakeEffect):
            bank = SoundBank(main.ASSET_DIR/'sounds')
            bank.play_book_intro('foret-1983')
            foret, cite = bank.effects['book_foret'], bank.effects['book_cite']
            stops = foret.stop_count
            bank.play_book_intro('cite-1983')
            self.assertGreater(foret.stop_count, stops)
            self.assertEqual(cite.play_count, 1)
            bank.set_enabled(False)
            bank.play_book_intro('cite-1983')
            self.assertEqual(cite.play_count, 1)


class CiteAmbienceWindowTests(CitePresentationTests):
    """Réutilise la fenêtre et les PDF synthétiques de la présentation de la Cité."""

    def background(self):
        return self.w.scene_art.background_art.toImage()

    def test_city_reading_uses_its_own_background(self):
        self.open()
        self.start()
        self.w.paragraphs.update({2: 'Une porte.'})
        self.w.go_to(2)
        self.assertIsNone(self.w.scene_entry)
        self.assertFalse(self.w.scene_art.is_book_art)
        self.assertEqual(self.background(), main.QPixmap(str(main.ASSET_DIR/'cite.jpg')).toImage())
        self.open('foret')
        self.start()
        self.w.go_to(2)
        self.assertEqual(self.background(), main.QPixmap(str(main.ASSET_DIR/'foret.jpg')).toImage())

    def test_captioned_illustration_is_shown_on_its_paragraph_only(self):
        self.open()
        self.start()
        self.assertEqual(self.w.scene_entry['paragraphes'], [1])
        self.assertTrue(self.w.scene_art.is_book_art)
        self.w.paragraphs.update({86: 'Un quai.', 88: 'Un boudoir.'})
        self.w.go_to(86)
        self.assertIsNone(self.w.scene_entry)
        self.w.go_to(88)
        self.assertEqual((self.w.scene_entry['page_pdf'], self.w.scene_entry['statut']),
                         (56, 'verifie_utilisateur'))
        shown = []
        def capture(dialog):
            shown.append(dialog.findChild(QLabel, 'illustrationStatus').text())
            return 0
        with patch.object(self.w, '_illustration_pixmap', return_value=QPixmap(8, 8)), \
                patch.object(main.IllustrationDialog, 'exec', capture):
            self.w._show_illustration(self.w.scene_entry, 'Illustration')
        self.assertEqual(shown, ['Page PDF 56 · association vérifiée'])

    def ambience_label(self):
        labels = []
        def capture():
            dialog = self.w.findChild(QDialog, 'ambienceDialog')
            labels.extend(box.text() for box in dialog.findChildren(QCheckBox)
                          if box.text().startswith('Ambiance de fond'))
            dialog.reject()
        QTimer.singleShot(0, capture)
        self.w.show_ambience()
        # Détruire le dialogue et ses fermetures ici, avant tout chargement en fil secondaire.
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()
        return labels

    def test_ambience_setting_names_the_loop_of_the_open_book(self):
        self.assertEqual(self.ambience_label(), ['Ambiance de fond : caverne'])
        self.open()
        self.assertEqual(self.w.sounds.ambient, 'ambient_cite')
        self.assertEqual(self.ambience_label(), ['Ambiance de fond : ville'])
        self.open('foret')
        self.assertEqual(self.w.sounds.ambient, 'ambient_foret')
        self.assertEqual(self.ambience_label(), ['Ambiance de fond : forêt'])
        self.open()
        self.assertEqual(self.ambience_label(), ['Ambiance de fond : ville'])


# Les tests hérités sont déjà exécutés par test_cite_presentation.
for _name in [name for name in vars(CitePresentationTests) if name.startswith('test_')]:
    setattr(CiteAmbienceWindowTests, _name, None)

if __name__ == '__main__':
    unittest.main()
