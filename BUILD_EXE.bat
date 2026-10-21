@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Bifurk - Compilation Windows
echo ============================================================
echo  Bifurk - Compilation Windows et archive de publication
echo ============================================================
echo.

REM PyInstaller remplace son dossier de sortie. Ne jamais effacer une partie.
if exist "dist\Bifurk\donnees" goto :player_data
if exist ".venv-build\Scripts\python.exe" goto :dependencies

echo [1/4] Creation de l'environnement de compilation...
where py >nul 2>&1
if not errorlevel 1 goto :python_launcher
where python >nul 2>&1
if errorlevel 1 goto :no_python
python -m venv .venv-build
if errorlevel 1 goto :failed
goto :dependencies

:python_launcher
py -3 -m venv .venv-build
if errorlevel 1 goto :failed

:dependencies
REM Le ZIP cible Windows x64 ; une version Python 64 bits est necessaire.
".venv-build\Scripts\python.exe" -c "import sys,sysconfig; sys.exit(0 if sys.platform == 'win32' and sysconfig.get_platform() == 'win-amd64' and sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto :wrong_python
echo [2/4] Installation des dependances...
".venv-build\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv-build\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :failed

echo [3/4] Compilation de Bifurk.exe avec son icone...
".venv-build\Scripts\python.exe" -m PyInstaller --noconfirm --clean Bifurk.spec
if errorlevel 1 goto :failed

echo [4/4] Preparation du ZIP de publication...
".venv-build\Scripts\python.exe" scripts\package_release.py
if errorlevel 1 goto :failed
echo.
echo Compilation terminee : dist\Bifurk\Bifurk.exe
echo Le ZIP versionne est dans dist. Distribuez le ZIP complet.
echo Pour tester, extrayez ce ZIP dans un autre dossier et lancez Bifurk.exe.
echo Pour preparer la release GitHub : PUBLISH_RELEASE.bat
echo.
explorer "%cd%\dist"
pause
exit /b 0

:player_data
echo [ERREUR] dist\Bifurk\donnees contient des donnees de jeu.
echo Deplacez le dossier dist\Bifurk complet avant de recompiler.
echo Aucun fichier n'a ete supprime.
goto :error_exit

:no_python
echo [ERREUR] Installez Python 3.13 Windows 64 bits avec Python Launcher.
goto :error_exit

:wrong_python
echo [ERREUR] Python Windows 64 bits version 3.11 ou plus est requis.
echo Installez de preference Python 3.13 x64, puis recreez .venv-build.
goto :error_exit

:failed
echo [ERREUR] La compilation a echoue. Consultez les messages ci-dessus.
:error_exit
pause
exit /b 1
