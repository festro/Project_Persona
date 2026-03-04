#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"
VENV="$AI_ROOT/env_webui"

if [ ! -x "$VENV/bin/python" ]; then
  echo "ERROR: WebUI venv not found at: $VENV"
  echo "Create it with:"
  echo "  python3 -m venv ~/AI/env_webui"
  echo "  source ~/AI/env_webui/bin/activate"
  echo "  pip install -U pip wheel"
  echo "  pip install open-webui==0.8.8"
  exit 1
fi

# Activate isolated venv (keeps API env clean)
source "$VENV/bin/activate"

# Persistent WebUI data
mkdir -p "$AI_ROOT/openwebui"

export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-http://127.0.0.1:8000/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-local-anything}"
export WEBUI_DATA_DIR="${WEBUI_DATA_DIR:-$AI_ROOT/openwebui}"

echo "Starting OpenWebUI on http://127.0.0.1:3000"
echo "  OPENAI_API_BASE_URL=$OPENAI_API_BASE_URL"
echo "  WEBUI_DATA_DIR=$WEBUI_DATA_DIR"

exec open-webui serve --host 127.0.0.1 --port 3000
