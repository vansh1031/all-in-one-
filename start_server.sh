#!/bin/bash
# Kept so the existing hazard-server.service keeps working after the folder
# reorganisation. New setups can call scripts/start_hazard_zone.sh directly.
exec "$(dirname "$0")/scripts/start_hazard_zone.sh"
