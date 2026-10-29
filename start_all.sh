#!/bin/bash
# Starts both apps and opens them in the browser. Press Ctrl+C to stop both.
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Each server opens its page in the browser once it is ready (when there is a desktop).
[ -n "$DISPLAY" ] && export OPEN_BROWSER=1
"$ROOT/scripts/start_hazard_zone.sh" &
HAZARD=$!
"$ROOT/scripts/start_predictive_maintenance.sh" &
PM=$!
trap 'echo; echo "Stopping..."; kill $HAZARD $PM 2>/dev/null; wait' INT TERM

echo "Hazardous Zone Detector  -> http://127.0.0.1:8765/start"
echo "Predictive Maintenance   -> http://127.0.0.1:8766/start"
echo "Press Ctrl+C to stop both."

wait
