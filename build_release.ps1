<#
 Construit l'application (PyInstaller, mode onedir) sur disque LOCAL puis publie
 dans release\ (a copier / partager). Usage :
   powershell -ExecutionPolicy Bypass -File build_release.ps1
#>
param([string]$Version = (Get-Date -Format "yyyy.MM.dd.HHmm"))
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $env:LOCALAPPDATA "BEG_RMI_build"     # build en local (10x plus rapide que P:)
$venv = Join-Path $work "venv"
$py   = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Creation de l'environnement de build local..."
    New-Item -ItemType Directory -Force $work | Out-Null
    # Python systeme (3.12+) : launcher "py" si present, sinon installation utilisateur
    $sys = (Get-Command py -ErrorAction SilentlyContinue)
    if ($sys) { & py -3 -m venv $venv }
    else {
        $cand = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1
        if (-not $cand) { throw "Aucun Python 3 trouve : installez Python 3.12+ (python.org)." }
        & $cand.FullName -m venv $venv
    }
    if ($LASTEXITCODE -ne 0) { throw "Creation du venv impossible" }
    & $py -m pip install --quiet --disable-pip-version-check -r "$root\_app\requirements_qt.txt" pyinstaller
}

Remove-Item -Recurse -Force (Join-Path $work "dist"), (Join-Path $work "build") -ErrorAction SilentlyContinue
$hidden = "ui.tab_historique","ui.tab_dashboard","ui.tab_photos","ui.tab_import","import_data","pdf_export"
$exclude = "tkinter","matplotlib","numpy","pandas","streamlit","PyQt6.QtWebEngineCore","PyQt6.QtWebEngineWidgets","PyQt6.QtQml","PyQt6.QtQuick","PyQt6.QtMultimedia","PyQt6.QtSql","PyQt6.QtBluetooth","PyQt6.QtPdf"
$data = "$root\Donn$([char]0xE9)es\logo.png;Donn$([char]0xE9)es"
$piArgs = @("-m","PyInstaller","--noconfirm","--clean","--windowed","--onedir","--noupx",
            "--name","BEG","--distpath","$work\dist","--workpath","$work\build","--specpath",$work,
            "--paths","$root\_app","--add-data",$data)
foreach ($h in $hidden)  { $piArgs += @("--hidden-import",$h) }
foreach ($e in $exclude) { $piArgs += @("--exclude-module",$e) }
$piArgs += "$root\_app\app_qt.py"
& $py @piArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller a echoue" }

$rel  = Join-Path $root "release"
$inst = Join-Path $rel "Installation"
New-Item -ItemType Directory -Force $inst | Out-Null
# Nettoyage de l'ancienne disposition (fichiers a plat a la racine de release\)
foreach ($name in "app","BEG_Launcher.cmd","BEG_RMI_Launcher.cmd","Lancer BEG RMI.cmd","Installer.cmd","version.txt") {
    $o = Join-Path $rel $name
    if (Test-Path $o) { Remove-Item -Recurse -Force $o }
}
Copy-Item "$root\deploy\beg_config.ini" "$work\dist\BEG\beg_config.ini" -Force
robocopy "$work\dist\BEG" "$inst\app" /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copie vers release\Installation echouee" }
Remove-Item (Join-Path $inst "BEG_RMI_Launcher.cmd") -ErrorAction SilentlyContinue
Copy-Item "$root\deploy\BEG_Launcher.cmd","$root\deploy\Installer.cmd" $inst -Force
Copy-Item "$root\deploy\Lancer BEG.cmd" $rel -Force
Set-Content -Path "$inst\version.txt" -Value $Version -Encoding ASCII
$size = [math]::Round(((Get-ChildItem "$inst\app" -Recurse -File | Measure-Object Length -Sum).Sum)/1MB)
Write-Host "OK : version $Version, $size Mo -> $rel"
