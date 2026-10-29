@echo off
rem Starts both apps in the background - no windows stay open - and opens them
rem in the browser when they are ready. Stop them with stop_all.bat or the
rem "Stop Visual Inspection" shortcut. (The Desktop shortcut "Visual Inspection"
rem does the same as this file without even a brief flash of this window.)
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Setup has not been run on this computer yet.
  echo Double-click install_windows.bat first, then try again.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0scripts\launcher.py"
