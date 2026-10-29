#!/bin/bash
# Starts both apps and opens them in the browser. Press Ctrl+C to stop both.
ROOT="$(cd "$(dirname "$0")" && pwd)"

"$ROOT/scripts/start_hazard_zone.sh" &
HAZARD=$!
"$ROOT/scripts/start_predictive_maintenance.sh" &
PM=$!
trap 'echo; echo "Stopping..."; kill $HAZARD $PM 2>/dev/null; wait' INT TERM

echo "Hazardous Zone Detector  -> http://127.0.0.1:8765/start"
echo "Predictive Maintenance   -> http://127.0.0.1:8766/start"
echo "Press Ctrl+C to stop both."

if [ -n "$DISPLAY" ] && command -v xdg-open >/dev/null 2>&1; then
  sleep 4
  xdg-open "http://127.0.0.1:8765/start" >/dev/null 2>&1 &
  xdg-open "http://127.0.0.1:8766/start" >/dev/null 2>&1 &
fi
wait
