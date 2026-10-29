@echo off
rem One-time setup for Windows: double-click this file.
rem It creates a .venv folder, installs the libraries and checks the setup.
rem Safe to run again: it reuses .venv and only installs what is missing.
setlocal
title Visual Inspection setup
cd /d "%~dp0"
echo === Visual Inspection setup (Windows) ===
echo.

rem Pick a Python: the py launcher with 3.12 first, then any python on the PATH.
rem ("python" can be a Microsoft Store shortcut that is not real Python, so test it.)
set "PY="
py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
if not defined PY (
  py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python was not found.
  echo Install Python 3.12 64-bit from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer, then run this file again.
  goto fail
)
for /f "delims=" %%v in ('%PY% --version') do echo Using %%v

if not exist ".venv\Scripts\python.exe" (
  echo Creating the virtual environment ^(.venv^)...
  %PY% -m venv .venv || goto fail
)

echo Installing libraries ^(the first run can take several minutes^)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto fail

echo.
".venv\Scripts\python.exe" scripts\check_setup.py

echo.
echo Setup finished.
echo   Start both apps:  double-click start_all.bat
echo   Hazard detector:  http://127.0.0.1:8765/start
echo   Maintenance:      http://127.0.0.1:8766/start
echo.
pause
exit /b 0

:fail
echo.
echo Setup did not finish. Read the message above, fix it, and run this file again.
pause
exit /b 1
