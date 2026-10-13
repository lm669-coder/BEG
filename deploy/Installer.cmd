@echo off
rem Installe BEG pour l'utilisateur courant (sans droits admin) + raccourci Bureau.
setlocal
set "LAUNCHER=%~dp0BEG_Launcher.cmd"
echo Installation de BEG...
call "%LAUNCHER%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\BEG.lnk');" ^
  "$s.TargetPath='%LAUNCHER%'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7;" ^
  "$s.IconLocation=$env:LOCALAPPDATA+'\BEG\app\BEG.exe,0'; $s.Save();" ^
  "Remove-Item ($d+'\BEG RMI.lnk') -ErrorAction SilentlyContinue"
echo Raccourci "BEG" cree sur le Bureau.
timeout /t 3 >nul
