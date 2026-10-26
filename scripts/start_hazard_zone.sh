#!/bin/bash
# Starts the Hazardous Zone Detector on http://127.0.0.1:8765
# (the dashboard card opens http://127.0.0.1:8765/start).
cd "$(dirname "$0")/../hazard_zone"
PYTHON="${PYTHON:-/home/jetiot/.pyenv/versions/3.12.12/bin/python3}"
[ -x "$PYTHON" ] || PYTHON=python3
exec "$PYTHON" hazard_server.py
