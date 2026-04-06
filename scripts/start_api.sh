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

# Feature toggles:
# - RAG is cheap and helpful, default ON.
# - Scientist async can starve CPU if abused, default OFF.
export RAG_ENABLED="${RAG_ENABLED:-1}"
export ASYNC_SCIENTIST_ENABLED="${ASYNC_SCIENTIST_ENABLED:-0}"

# Convergence step 1: profile wrappers (safe; no extra model calls)
export PROFILE_WRAPPERS_ENABLED="${PROFILE_WRAPPERS_ENABLED:-1}"

# Convergence step 2: memory tagging (safe)
export PERSONA_WRITEBACK_ENABLED="${PERSONA_WRITEBACK_ENABLED:-1}"

# Convergence step 3: job persistence (safe)
export JOBS_PERSIST_ENABLED="${JOBS_PERSIST_ENABLED:-1}"
export JOBS_PERSIST_PATH="${JOBS_PERSIST_PATH:-$AI_ROOT/run/jobs.jsonl}"
export JOBS_PERSIST_MAX_LOAD="${JOBS_PERSIST_MAX_LOAD:-5000}"

# Convergence step 4: in-band scientist notes (DEFAULT OFF for stability)
export SCIENTIST_INBAND_ENABLED="${SCIENTIST_INBAND_ENABLED:-0}"
export SCIENTIST_INBAND_TOPICS="${SCIENTIST_INBAND_TOPICS:-science,biology,coding,math}"
export SCIENTIST_INBAND_MAX_TOKENS="${SCIENTIST_INBAND_MAX_TOKENS:-256}"
export SCIENTIST_INBAND_TIMEOUT_S="${SCIENTIST_INBAND_TIMEOUT_S:-45}"

# Optional knobs
export ASYNC_SCIENTIST_TOPICS="${ASYNC_SCIENTIST_TOPICS:-science,biology,coding,math}"
export RAG_TOP_K="${RAG_TOP_K:-6}"
export EMBED_MODEL="${EMBED_MODEL:-BAAI/bge-small-en-v1.5}"

export PERSONA_MAX_TOKENS="${PERSONA_MAX_TOKENS:-192}"
export SCIENTIST_MAX_TOKENS="${SCIENTIST_MAX_TOKENS:-512}"
export PERSONA_TIMEOUT_S="${PERSONA_TIMEOUT_S:-90}"
export SCIENTIST_TIMEOUT_S="${SCIENTIST_TIMEOUT_S:-600}"

echo "Starting FastAPI on http://127.0.0.1:8000"
echo "  Persona:   http://${LLAMA_HOST}:${PERSONA_PORT}"
echo "  Scientist: http://${LLAMA_HOST}:${SCIENTIST_PORT}"
echo "  RAG enabled: ${RAG_ENABLED}"
echo "  Async scientist enabled: ${ASYNC_SCIENTIST_ENABLED}"
echo "  Profile wrappers enabled: ${PROFILE_WRAPPERS_ENABLED}"
echo "  Persona writeback enabled: ${PERSONA_WRITEBACK_ENABLED}"
echo "  Jobs persistence enabled: ${JOBS_PERSIST_ENABLED} (${JOBS_PERSIST_PATH})"
echo "  Scientist in-band enabled: ${SCIENTIST_INBAND_ENABLED}"

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
export MEMORY_DISTILL_ENABLED="${MEMORY_DISTILL_ENABLED:-1}"
