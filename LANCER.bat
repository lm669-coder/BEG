@echo off
title Bilan d'Experience BEG RMI
echo ============================================
echo    Bilan d'Experience - BEG RMI
echo ============================================
echo.

:: Python portable en priorite
if exist "%~dp0python_portable\python.exe" (
    set "PY=%~dp0python_portable\python.exe"
    set "SCRIPTS=%~dp0python_portable\Scripts"
    echo Python portable detecte.
    goto :run
)

:: Fallback Python systeme
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python introuvable.
    pause
    exit /b 1
)
set "PY=python"
set "SCRIPTS="

:run
set "GIT_PYTHON_REFRESH=quiet"
set "GIT_CEILING_DIRECTORIES=%~dp0"
set "STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"

echo Demarrage en cours (30-60 sec sur VPN - ne pas fermer cette fenetre)...
echo.

:: Ouvrir le navigateur en arriere-plan quand le port 8501 est pret
start "" /B powershell -NoProfile -WindowStyle Hidden -Command "do { Start-Sleep 5 } until ((Test-NetConnection 127.0.0.1 -Port 8501 -WarningAction SilentlyContinue -InformationLevel Quiet).TcpTestSucceeded); Start-Process 'http://127.0.0.1:8501'"

:: Streamlit en premier plan (les messages d'erreur sont visibles ici)
pushd "%~dp0_app"
if defined SCRIPTS (
    "%SCRIPTS%\streamlit.exe" run app.py
) else (
    "%PY%" -m streamlit run app.py
)

echo.
echo L'application s'est arretee.
pause
popd
