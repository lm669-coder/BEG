@echo off
setlocal
rem Lanceur BEG : copie locale de l'app (rapide), mise a jour auto depuis le partage.
set "SRC=%~dp0"
set "BASE=%LOCALAPPDATA%\BEG"
set "DEST=%BASE%\app"
set "NEWVER="
set "OLDVER="
if exist "%SRC%version.txt" set /p NEWVER=<"%SRC%version.txt"
if exist "%BASE%\version.txt" set /p OLDVER=<"%BASE%\version.txt"

if not defined NEWVER goto :run
if "%NEWVER%"=="%OLDVER%" goto :run

echo Installation / mise a jour de BEG (%NEWVER%)...
if not exist "%DEST%" mkdir "%DEST%"
robocopy "%SRC%app" "%DEST%" /MIR /NFL /NDL /NJH /NJS /NP /R:2 /W:2 >nul
if errorlevel 8 (
    echo.
    echo Mise a jour impossible ^(application deja ouverte ou partage indisponible^).
    if not exist "%DEST%\BEG.exe" ( pause & exit /b 1 )
    echo Lancement de la version deja installee.
    timeout /t 3 >nul
    goto :run
)
>"%BASE%\version.txt" echo %NEWVER%

:run
if not exist "%DEST%\BEG.exe" (
    echo BEG n'est pas installe et le partage est injoignable.
    pause & exit /b 1
)
start "" "%DEST%\BEG.exe"
endlocal
