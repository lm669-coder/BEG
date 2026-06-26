@echo off
title BEG RMI — Configuration Python portable
chcp 65001 >nul 2>&1
echo ============================================
echo    BEG RMI — Configuration Python portable
echo ============================================
echo.
echo  Ce script installe Python dans le dossier
echo  de l'application. Aucune installation
echo  systeme n'est requise.
echo.
echo  Connexion internet necessaire la 1ere fois.
echo.

set "PORTABLE_DIR=%~dp0python_portable"
set "PYTHON_EXE=%PORTABLE_DIR%\python.exe"
set "PYTHON_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "PYTHON_ZIP=%~dp0_python_tmp.zip"

:: Deja installe ?
if exist "%PYTHON_EXE%" (
    echo Python portable deja present. Mise a jour des packages...
    goto :install_packages
)

echo [1/4] Telechargement de Python 3.12 portable...
powershell -NoProfile -Command ^
    "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%' -UseBasicParsing"
if errorlevel 1 (
    echo.
    echo ERREUR : Telechargement echoue.
    echo Verifiez votre connexion internet et relancez ce script.
    pause & exit /b 1
)

echo [2/4] Extraction...
powershell -NoProfile -Command ^
    "Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PORTABLE_DIR%' -Force"
del "%PYTHON_ZIP%" >nul 2>&1

echo [3/4] Activation de pip...
:: Decommenter "import site" dans le fichier .pth pour activer pip
powershell -NoProfile -Command ^
    "Get-ChildItem '%PORTABLE_DIR%' -Filter '*._pth' | ForEach-Object { " ^
    "  (Get-Content $_.FullName) -replace '#import site','import site' " ^
    "  | Set-Content $_.FullName }"

powershell -NoProfile -Command ^
    "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PORTABLE_DIR%\get-pip.py' -UseBasicParsing"
"%PYTHON_EXE%" "%PORTABLE_DIR%\get-pip.py" --quiet
del "%PORTABLE_DIR%\get-pip.py" >nul 2>&1

:install_packages
echo [4/4] Installation des dependances (streamlit, reportlab, openpyxl...)
"%PYTHON_EXE%" -m pip install -r "%~dp0_app\requirements.txt" --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo ERREUR lors de l'installation des packages.
    echo Verifiez votre connexion et relancez ce script.
    pause & exit /b 1
)

echo.
echo ============================================
echo   Installation terminee avec succes !
echo.
echo   Utilisez LANCER.bat pour demarrer l'app.
echo   Aucun Python systeme requis.
echo ============================================
echo.
pause
