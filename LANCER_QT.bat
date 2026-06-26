@echo off
cd /d "%~dp0_app"
start "" "%~dp0python_portable\python.exe" "%~dp0_app\app_qt.py"
