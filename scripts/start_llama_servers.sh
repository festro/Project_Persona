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

HOST="${HOST:-127.0.0.1}"
THREADS_DEFAULT="${THREADS:-0}"
if [ "$THREADS_DEFAULT" = "0" ]; then THREADS_DEFAULT="$(nproc)"; fi

BATCH_SIZE="${BATCH_SIZE:-512}"

mkdir -p "$AI_ROOT/logs" "$AI_ROOT/run"

start_one () {
  local name="$1"
  local model_file="$2"
  local port="$3"
  local ctx="$4"
  local gpu_layers="$5"
  local threads_override="${6:-}"

  local pidfile="$AI_ROOT/run/${name}.pid"
  local logfile="$AI_ROOT/logs/${name}.log"
  local model_path="$AI_ROOT/models/${model_file}"

  if [ ! -f "$model_path" ]; then
    echo "ERROR: Missing model for $name: $model_path"
    return 1
  fi

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

  local threads_effective="$THREADS_DEFAULT"
  if [ -n "${threads_override:-}" ]; then
    threads_effective="$threads_override"
  fi

  echo "Starting $name on http://${HOST}:${port}"
  echo "  model=$model_path"
  echo "  ctx=$ctx threads=$threads_effective gpu_layers=$gpu_layers batch=$BATCH_SIZE"

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY RUN]"
    return 0
  fi

  nohup "$BIN" \
    --model "$model_path" \
    --host "$HOST" \
    --port "$port" \
    --ctx-size "$ctx" \
    --threads "$threads_effective" \
    --batch-size "$BATCH_SIZE" \
    --ubatch-size 512 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
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
start_one "persona"   "$PERSONA_MODEL"   "$PERSONA_PORT"   "$PERSONA_CTX"   "${GPU_LAYERS_PERSONA:-0}"   "${PERSONA_THREADS:-}" || FAILED=$((FAILED+1))
start_one "scientist" "$SCIENTIST_MODEL" "$SCIENTIST_PORT" "$SCIENTIST_CTX" "${GPU_LAYERS_SCIENTIST:-0}" "${SCIENTIST_THREADS:-}" || FAILED=$((FAILED+1))

if [ "$FAILED" -eq 0 ]; then
  echo "All llama servers started."
else
  echo "WARNING: $FAILED llama server(s) failed to start."
fi
