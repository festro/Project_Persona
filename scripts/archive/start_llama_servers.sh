#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
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
UBATCH_SIZE="${UBATCH_SIZE:-512}"
CACHE_TYPE_K="${CACHE_TYPE_K:-q8_0}"
CACHE_TYPE_V="${CACHE_TYPE_V:-q8_0}"

mkdir -p "$AI_ROOT/logs" "$AI_ROOT/run"

# Pin Vulkan to GPU0 (RADV/Strix Halo iGPU); excludes llvmpipe software fallback at GPU1
export GGML_VK_VISIBLE_DEVICES=0

start_one () {
  local name="$1"
  local model_file="$2"
  local port="$3"
  local ctx="$4"
  local gpu_layers="$5"
  local parallel="$6"

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

  echo "Starting $name on http://${HOST}:${port}"
  echo "  model=$model_path"
  echo "  ctx=$ctx parallel=$parallel gpu_layers=$gpu_layers"
  echo "  batch=$BATCH_SIZE ubatch=$UBATCH_SIZE cache_k=$CACHE_TYPE_K cache_v=$CACHE_TYPE_V"
  echo "  vulkan_device=$GGML_VK_VISIBLE_DEVICES (GPU0=RADV/GFX1151)"

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY RUN]"
    return 0
  fi

  LD_LIBRARY_PATH="$AI_ROOT/llama_cpp/build/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  nohup "$BIN" \
    --model "$model_path" \
    --host "$HOST" \
    --port "$port" \
    --ctx-size "$ctx" \
    --threads "$THREADS_DEFAULT" \
    --batch-size "$BATCH_SIZE" \
    --ubatch-size "$UBATCH_SIZE" \
    --cache-type-k "$CACHE_TYPE_K" \
    --cache-type-v "$CACHE_TYPE_V" \
    --n-gpu-layers "$gpu_layers" \
    --device Vulkan0 \
    --parallel "$parallel" \
    --cont-batching \
    --jinja \
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
start_one "persona" "$PERSONA_MODEL" "$PERSONA_PORT" "$PERSONA_CTX" "${GPU_LAYERS_PERSONA:-0}" "${PERSONA_PARALLEL:-1}" || FAILED=$((FAILED+1))

if [ "$FAILED" -eq 0 ]; then
  echo "Unified llama-server started."
else
  echo "WARNING: $FAILED llama server(s) failed to start."
fi
