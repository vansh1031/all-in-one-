#!/bin/bash
# Starts the Hazardous Zone Detector on http://127.0.0.1:8765
# (the dashboard card opens http://127.0.0.1:8765/start).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../hazard_zone"
# Use $PYTHON if set, else the project's .venv (made by install_jetson.sh),
# else the Jetson's pyenv 3.12, else whatever python3 is on the PATH.
VENV_PY="$SCRIPT_DIR/../.venv/bin/python"
if [ -z "$PYTHON" ]; then
  if [ -x "$VENV_PY" ]; then PYTHON="$VENV_PY"
  elif [ -x "$HOME/.pyenv/versions/3.12.12/bin/python3" ]; then PYTHON="$HOME/.pyenv/versions/3.12.12/bin/python3"
  else PYTHON=python3
  fi
fi
exec "$PYTHON" hazard_server.py
