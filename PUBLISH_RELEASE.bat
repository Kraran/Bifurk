@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Bifurk - Preparer la release GitHub
REM Cree uniquement un BROUILLON : la publication publique reste manuelle.
REM Version, titre et notes viennent de app_info.py et de docs\windows\RELEASE_NOTES.md.
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
echo ============================================================
echo  Bifurk - Brouillon de release GitHub
echo ============================================================
echo.
where gh >nul 2>&1
if errorlevel 1 goto :no_gh
if not exist ".venv-build\Scripts\python.exe" goto :no_build
gh auth status >nul 2>&1
if errorlevel 1 goto :no_auth

echo [1/2] Verification du ZIP teste et des notes de version...
echo.
".venv-build\Scripts\python.exe" scripts\package_release.py --check
if errorlevel 1 goto :failed
echo.
echo ------------------------------------------------------------
choice /C ON /N /M "Creer ce brouillon sur GitHub (Kraran/Bifurk) ? [O/N] "
if errorlevel 2 goto :cancelled

echo.
echo [2/2] Creation du brouillon et televersement du ZIP...
".venv-build\Scripts\python.exe" scripts\package_release.py --draft
if errorlevel 1 goto :failed
echo.
echo Brouillon GitHub cree. Relisez-le sur GitHub, puis cliquez sur Publish release.
start "" "https://github.com/Kraran/Bifurk/releases"
pause
exit /b 0

:cancelled
echo Aucun brouillon cree.
pause
exit /b 0

:no_gh
echo [ERREUR] Installez GitHub CLI : winget install --id GitHub.cli -e
echo Puis rouvrez la console et lancez gh auth login.
goto :error_exit
:no_auth
echo [ERREUR] GitHub CLI n'est pas connecte : lancez gh auth login.
goto :error_exit
:no_build
echo [ERREUR] Lancez BUILD_EXE.bat et testez le ZIP en premier.
goto :error_exit
:failed
echo [ERREUR] Preparation du brouillon impossible. Consultez les messages ci-dessus.
:error_exit
pause
exit /b 1
