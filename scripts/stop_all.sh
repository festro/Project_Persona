#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

echo "Stopping API..."
"$AI_ROOT/scripts/stop_api.sh" || true
echo "Stopping llama servers..."
"$AI_ROOT/scripts/stop_llama_servers.sh" || true
echo "All stopped."
