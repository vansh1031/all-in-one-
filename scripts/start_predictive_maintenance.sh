#!/bin/bash
# Starts Edge AI Predictive Maintenance on http://127.0.0.1:8766
# (open http://127.0.0.1:8766/start from the dashboard).
cd "$(dirname "$0")/../predictive_maintenance"
PYTHON="${PYTHON:-/home/jetiot/.pyenv/versions/3.12.12/bin/python3}"
[ -x "$PYTHON" ] || PYTHON=python3
exec "$PYTHON" pm_server.py
