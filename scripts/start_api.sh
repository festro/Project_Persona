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
export SCIENTIST_PORT="${SCIENTIST_PORT:-8081}"

# Fast-by-default: async scientist OFF unless explicitly enabled.
export ASYNC_SCIENTIST_ENABLED="${ASYNC_SCIENTIST_ENABLED:-0}"
export ASYNC_SCIENTIST_TOPICS="${ASYNC_SCIENTIST_TOPICS:-science,biology,coding,math}"

echo "Starting FastAPI on http://127.0.0.1:8000"
echo "  Persona:   http://${LLAMA_HOST}:${PERSONA_PORT}"
echo "  Scientist: http://${LLAMA_HOST}:${SCIENTIST_PORT}"
echo "  Async scientist enabled: ${ASYNC_SCIENTIST_ENABLED}"

cd "$AI_ROOT"

nohup "$AI_ROOT/env/bin/uvicorn" "server:app" \
  --app-dir "$AI_ROOT/services/api" \
  --host 127.0.0.1 --port 8000 \
  > "$LOGFILE" 2>&1 &

echo $! > "$PIDFILE"
sleep 1

if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "  OK pid=$(cat "$PIDFILE") log=$LOGFILE"
  echo "  Health: http://127.0.0.1:8000/health (if implemented)"
  echo "  Docs:   http://127.0.0.1:8000/docs"
else
  echo "  FAILED (see $LOGFILE)"
  exit 1
fi
