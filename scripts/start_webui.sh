#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
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

# WEBUI_HOST defaults to loopback (safe). Set it to a LAN address (0.0.0.0, or the host's
# 192.168.x.x) to reach the UI from another machine's browser without an SSH tunnel. OpenWebUI
# has its own account/auth (first visit = admin signup), so a LAN bind is less exposed than the
# raw persona API; still keep it to a trusted network.
WEBUI_HOST="${WEBUI_HOST:-127.0.0.1}"
WEBUI_PORT="${WEBUI_PORT:-3000}"

echo "Starting OpenWebUI on http://${WEBUI_HOST}:${WEBUI_PORT}"
echo "  OPENAI_API_BASE_URL=$OPENAI_API_BASE_URL"
echo "  WEBUI_DATA_DIR=$WEBUI_DATA_DIR"

exec open-webui serve --host "$WEBUI_HOST" --port "$WEBUI_PORT"
