@echo off
rem Starts the Hazardous Zone Detector on http://127.0.0.1:8765
rem and opens it in the default browser. Close this window to stop it.
title Hazardous Zone Detector
cd /d "%~dp0..\hazard_zone"

set PY=python
if exist "%~dp0..\.venv\Scripts\python.exe" set PY="%~dp0..\.venv\Scripts\python.exe"

rem Open the browser once the server has had a few seconds to start.
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8765/start"

%PY% hazard_server.py
if errorlevel 1 (
  echo.
  echo The server stopped with an error. Check that Python is installed and that
  echo "pip install -r requirements.txt" was run from the project folder.
  pause
)
