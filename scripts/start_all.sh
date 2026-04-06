#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

FRESH=false
if [ "${1:-}" = "--fresh" ]; then
  FRESH=true
fi

if [ "$FRESH" = true ]; then
  echo "Fresh start requested: stopping everything first..."
  "$AI_ROOT/scripts/stop_all.sh" || true
  echo ""
fi

echo "Starting llama servers..."
"$AI_ROOT/scripts/start_llama_servers.sh"
echo ""

echo "Starting API..."
"$AI_ROOT/scripts/start_api.sh"
echo ""

"$AI_ROOT/scripts/status.sh"
