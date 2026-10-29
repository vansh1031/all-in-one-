@echo off
rem Stops the apps that start_all.bat or the "Visual Inspection" shortcut started.
if not exist "%~dp0.venv\Scripts\pythonw.exe" exit /b 0
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0scripts\launcher.py" --stop
