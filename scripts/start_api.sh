#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

mkdir -p "$AI_ROOT/logs" "$AI_ROOT/run"

PIDFILE="$AI_ROOT/run/api.pid"
LOGFILE="$AI_ROOT/logs/api.log"

# If already running, exit cleanly
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "API already running (pid $(cat "$PIDFILE"))"
  exit 0
fi

# Remove stale pidfile
rm -f "$PIDFILE"

if [ ! -x "$AI_ROOT/env/bin/uvicorn" ]; then
  echo "ERROR: uvicorn not found at $AI_ROOT/env/bin/uvicorn"
  echo "Hint: run ./scripts/setup_native_stack.sh first."
  exit 1
fi

export AI_ROOT="$AI_ROOT"
export PERSONA_ROOT="${PERSONA_ROOT:-$AI_ROOT/persona}"
export PROFILES_DIR="${PROFILES_DIR:-$PERSONA_ROOT/profiles}"
export GLOBAL_MEMORY_DIR="${GLOBAL_MEMORY_DIR:-$PERSONA_ROOT/global_memory}"
export DEFAULT_PROFILE="${DEFAULT_PROFILE:-default}"

export LLAMA_HOST="${LLAMA_HOST:-127.0.0.1}"
export PERSONA_PORT="${PERSONA_PORT:-8080}"
export REASONING_PORT="${REASONING_PORT:-8081}"
export CODER_PORT="${CODER_PORT:-8082}"

# Timeouts/budgets (tune here)
export EXPERT_MAX_TOKENS=192
export EXPERT_TIMEOUT_S=120
export HTTP_TIMEOUT_S="${HTTP_TIMEOUT_S:-180}"
export EXPERT_TIMEOUT_S="${EXPERT_TIMEOUT_S:-240}"
export EXPERT_MAX_TOKENS="${EXPERT_MAX_TOKENS:-512}"


# Memory / embeddings
export EMBED_MODEL="${EMBED_MODEL:-BAAI/bge-small-en-v1.5}"

echo "Starting FastAPI on http://127.0.0.1:8000"

# Run from the API folder without requiring python packages
cd "$AI_ROOT"

nohup "$AI_ROOT/env/bin/uvicorn" "server:app" \
  --app-dir "$AI_ROOT/services/api" \
  --host 127.0.0.1 --port 8000 \
  > "$LOGFILE" 2>&1 &

echo $! > "$PIDFILE"
sleep 1

if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "  OK pid=$(cat "$PIDFILE") log=$LOGFILE"
  echo "  Health: http://127.0.0.1:8000/health"
  echo "  Docs:   http://127.0.0.1:8000/docs"
else
  echo "  FAILED (see $LOGFILE)"
  exit 1
fi
