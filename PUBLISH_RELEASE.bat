@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Bifurk - Preparer la release GitHub
REM Cree uniquement un BROUILLON : la publication publique reste manuelle.
where gh >nul 2>&1
if errorlevel 1 goto :no_gh
if not exist ".venv-build\Scripts\python.exe" goto :no_build
".venv-build\Scripts\python.exe" scripts\package_release.py --draft
if errorlevel 1 goto :failed
echo.
echo Brouillon GitHub cree. Testez le ZIP avant de cliquer sur Publish release.
pause
exit /b 0

:no_gh
echo [ERREUR] Installez GitHub CLI, puis lancez gh auth login.
goto :error_exit
:no_build
echo [ERREUR] Lancez BUILD_EXE.bat et testez le ZIP en premier.
goto :error_exit
:failed
echo [ERREUR] Preparation du brouillon impossible. Consultez les messages ci-dessus.
:error_exit
pause
exit /b 1
