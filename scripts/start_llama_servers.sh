#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"
ENV_FILE="$AI_ROOT/run/llama-servers.env"
DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=true; fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Missing env file: $ENV_FILE"
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

BIN="$AI_ROOT/llama_cpp/build/bin/llama-server"
if [ ! -x "$BIN" ]; then
  echo "ERROR: llama-server not found: $BIN"
  exit 1
fi

THREADS_EFFECTIVE="${THREADS:-0}"
if [ "$THREADS_EFFECTIVE" = "0" ]; then THREADS_EFFECTIVE="$(nproc)"; fi

HOST="${HOST:-127.0.0.1}"

# Global defaults (fallbacks)
CTX_SIZE="${CTX_SIZE:-8192}"
GPU_LAYERS="${GPU_LAYERS:-0}"
BATCH_SIZE="${BATCH_SIZE:-512}"

# Per-model overrides (optional)
PERSONA_CTX="${PERSONA_CTX:-$CTX_SIZE}"
REASONING_CTX="${REASONING_CTX:-$CTX_SIZE}"
CODER_CTX="${CODER_CTX:-$CTX_SIZE}"

GPU_LAYERS_PERSONA="${GPU_LAYERS_PERSONA:-$GPU_LAYERS}"
GPU_LAYERS_REASONING="${GPU_LAYERS_REASONING:-$GPU_LAYERS}"
GPU_LAYERS_CODER="${GPU_LAYERS_CODER:-$GPU_LAYERS}"

mkdir -p "$AI_ROOT/logs" "$AI_ROOT/run"

start_one () {
  local name="$1"
  local model_file="$2"
  local port="$3"
  local ctx="$4"
  local gpu_layers="$5"

  local pidfile="$AI_ROOT/run/${name}.pid"
  local logfile="$AI_ROOT/logs/${name}.log"
  local model_path="$AI_ROOT/models/${model_file}"

  if [ ! -f "$model_path" ]; then
    echo "ERROR: Missing model for $name: $model_path"
    return 1
  fi

  # If pidfile exists, verify process still alive; otherwise remove stale pidfile
  if [ -f "$pidfile" ]; then
    oldpid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "${oldpid:-}" ] && kill -0 "$oldpid" 2>/dev/null; then
      echo "SKIP: $name already running (pid $oldpid)"
      return 0
    else
      echo "WARN: stale pidfile for $name; removing"
      rm -f "$pidfile"
    fi
  fi

  echo "Starting $name on http://${HOST}:${port}"
  echo "  model=$model_path"
  echo "  ctx=$ctx threads=$THREADS_EFFECTIVE gpu_layers=$gpu_layers batch=$BATCH_SIZE"

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY RUN]"
    return 0
  fi

  nohup "$BIN" \
    --model "$model_path" \
    --host "$HOST" \
    --port "$port" \
    --ctx-size "$ctx" \
    --threads "$THREADS_EFFECTIVE" \
    --batch-size "$BATCH_SIZE" \
    --n-gpu-layers "$gpu_layers" \
    > "$logfile" 2>&1 &

  echo $! > "$pidfile"
  sleep 1
  if kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "  OK pid=$(cat "$pidfile") log=$logfile"
  else
    echo "  FAILED (see $logfile)"
    return 1
  fi
}

FAILED=0
start_one "persona"   "$PERSONA_MODEL"   "$PERSONA_PORT"   "$PERSONA_CTX"   "$GPU_LAYERS_PERSONA"   || FAILED=$((FAILED+1))
start_one "reasoning" "$REASONING_MODEL" "$REASONING_PORT" "$REASONING_CTX" "$GPU_LAYERS_REASONING" || FAILED=$((FAILED+1))
start_one "coder"     "$CODER_MODEL"     "$CODER_PORT"     "$CODER_CTX"     "$GPU_LAYERS_CODER"     || FAILED=$((FAILED+1))

if [ "$FAILED" -eq 0 ]; then
  echo "All llama servers started."
else
  echo "WARNING: $FAILED llama server(s) failed to start."
fi
