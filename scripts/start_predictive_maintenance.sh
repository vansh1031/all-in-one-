#!/bin/bash
# Starts Edge AI Predictive Maintenance on http://127.0.0.1:8766
# (open http://127.0.0.1:8766/start from the dashboard).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../predictive_maintenance"
# Use $PYTHON if set, else the project's .venv (made by install_jetson.sh),
# else the Jetson's pyenv 3.12, else whatever python3 is on the PATH.
VENV_PY="$SCRIPT_DIR/../.venv/bin/python"
if [ -z "$PYTHON" ]; then
  if [ -x "$VENV_PY" ]; then PYTHON="$VENV_PY"
  elif [ -x "$HOME/.pyenv/versions/3.12.12/bin/python3" ]; then PYTHON="$HOME/.pyenv/versions/3.12.12/bin/python3"
  else PYTHON=python3
  fi
fi
exec "$PYTHON" pm_server.py
