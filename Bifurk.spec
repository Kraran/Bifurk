# -*- mode: python ; coding: utf-8 -*-
"""Distribution portable en dossier ; lancer PyInstaller depuis BUILD_EXE.bat.

Seuls les assets et catalogues livrés sont embarqués : jamais donnees ni PDF.
Les hooks Qt collectent les plugins natifs (plateforme, images, multimédia).
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT))
from app_info import APP_VERSION, AUTHOR

windows_version = None
if sys.platform == 'win32':
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct,
    )

    version = tuple(int(part) for part in APP_VERSION.split('.')) + (0,)
    windows_version = VSVersionInfo(
        ffi=FixedFileInfo(filevers=version, prodvers=version, mask=0x3f,
                          flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
        kids=[
            StringFileInfo([StringTable('040c04b0', [
                StringStruct('CompanyName', AUTHOR),
                StringStruct('FileDescription', 'Bifurk - Chroniques d’aventure'),
                StringStruct('FileVersion', APP_VERSION),
                StringStruct('InternalName', 'Bifurk'),
                StringStruct('OriginalFilename', 'Bifurk.exe'),
                StringStruct('ProductName', 'Bifurk'),
                StringStruct('ProductVersion', APP_VERSION),
            ])]),
            VarFileInfo([VarStruct('Translation', [1036, 1200])]),
        ],
    )

datas = [(str(ROOT / 'assets'), 'assets'), (str(ROOT / 'catalogues'), 'catalogues')]
# PyMuPDF récent charge automatiquement son analyseur de mise en page lors du
# premier import. Les modules Python seuls ne suffisent pas : conserver également
# configurations YAML et modèles ONNX, aux chemins relatifs attendus par le paquet.
# Les en-têtes et archives de développement MuPDF ne servent pas à l'exécution.
datas += collect_data_files('pymupdf', excludes=['mupdf-devel/**'])
# Inclure les traductions françaises même si le hook Qt change sa sélection.
datas += collect_data_files('PySide6', includes=['Qt/translations/qtbase_fr.qm',
                                               'Qt/translations/qt_fr.qm',
                                               'translations/qtbase_fr.qm',
                                               'translations/qt_fr.qm'])
# Conserver métadonnées et textes de licence des dépendances dans _internal.
for distribution in ('PyMuPDF', 'PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6'):
    datas += copy_metadata(distribution)

a = Analysis(
    [str(ROOT / 'main.py')], pathex=[str(ROOT)], binaries=[], datas=datas,
    hiddenimports=['pymupdf', 'pcm_audio'], hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='Bifurk',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon=str(ROOT / 'assets' / 'bifurk.ico'),
    version=windows_version if sys.platform == 'win32' else None,
    contents_directory='_internal',
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Bifurk')
