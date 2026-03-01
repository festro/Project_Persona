#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

echo "Starting llama servers..."
"$AI_ROOT/scripts/start_llama_servers.sh"
echo ""
echo "Starting API..."
"$AI_ROOT/scripts/start_api.sh"
echo ""
"$AI_ROOT/scripts/status.sh"
