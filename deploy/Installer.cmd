@echo off
rem Installe BEG RMI pour l'utilisateur courant (sans droits admin) + raccourci Bureau.
setlocal
set "LAUNCHER=%~dp0BEG_RMI_Launcher.cmd"
echo Installation de BEG RMI...
call "%LAUNCHER%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\BEG RMI.lnk');" ^
  "$s.TargetPath='%LAUNCHER%'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7;" ^
  "$s.IconLocation=$env:LOCALAPPDATA+'\BEG_RMI\app\BEG_RMI.exe,0'; $s.Save()"
echo Raccourci "BEG RMI" cree sur le Bureau.
timeout /t 3 >nul
