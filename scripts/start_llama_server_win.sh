#!/usr/bin/env bash
# Windows / Git Bash launcher for the Qwen3.6 prototype (T0.1 smoke test).
# Companion runbook: HANDOFF_2026-05-17_*_qwen36-windows-prototype.md
set -euo pipefail

AI_ROOT="${AI_ROOT:-/d/Projects/Git/Project_Persona}"

# After extracting llama-bXXXX-bin-win-vulkan-x64.zip into llama_cpp/windows/,
# llama-server.exe lives directly inside (the zip is flat at extract time).
LLAMA_BIN_DIR="${LLAMA_BIN_DIR:-$AI_ROOT/llama_cpp/windows}"
BIN="$LLAMA_BIN_DIR/llama-server.exe"

MODEL_FILE="${MODEL_FILE:-Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8090}"
CTX="${CTX:-16384}"
GPU_LAYERS="${GPU_LAYERS:-35}"
PARALLEL="${PARALLEL:-4}"
THREADS="${THREADS:-0}"
BATCH_SIZE="${BATCH_SIZE:-512}"
UBATCH_SIZE="${UBATCH_SIZE:-512}"
CACHE_TYPE_K="${CACHE_TYPE_K:-q8_0}"
CACHE_TYPE_V="${CACHE_TYPE_V:-q8_0}"

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=true; fi

MODEL_PATH="$AI_ROOT/models/$MODEL_FILE"
LOG_FILE="$AI_ROOT/logs/persona_win.log"
PID_FILE="$AI_ROOT/run/persona_win.pid"

mkdir -p "$AI_ROOT/logs" "$AI_ROOT/run"

if [ ! -f "$BIN" ]; then
  echo "ERROR: llama-server.exe not found: $BIN"
  echo "Hint: extract Windows Vulkan prebuilt from"
  echo "      https://github.com/ggml-org/llama.cpp/releases/latest"
  echo "      (file: llama-b<NNNN>-bin-win-vulkan-x64.zip) into"
  echo "      $LLAMA_BIN_DIR/"
  exit 1
fi

if [ ! -f "$MODEL_PATH" ]; then
  echo "ERROR: model not found: $MODEL_PATH"
  echo "Hint:  huggingface-cli download unsloth/Qwen3.6-35B-A3B-GGUF \\"
  echo "         --include \"$MODEL_FILE\" \\"
  echo "         --local-dir $AI_ROOT/models/"
  exit 1
fi

if [ -f "$PID_FILE" ]; then
  oldpid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "${oldpid:-}" ] && kill -0 "$oldpid" 2>/dev/null; then
    echo "SKIP: llama-server already running (pid $oldpid)"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

THREADS_EFFECTIVE="$THREADS"
if [ "$THREADS_EFFECTIVE" = "0" ]; then
  THREADS_EFFECTIVE="$(nproc 2>/dev/null || echo 8)"
fi

echo "Starting llama-server.exe (Windows / Vulkan) on http://${HOST}:${PORT}"
echo "  bin       $BIN"
echo "  model     $MODEL_PATH"
echo "  ctx       $CTX  parallel=$PARALLEL  gpu_layers=$GPU_LAYERS"
echo "  threads   $THREADS_EFFECTIVE  batch=$BATCH_SIZE  ubatch=$UBATCH_SIZE"
echo "  cache     k=$CACHE_TYPE_K  v=$CACHE_TYPE_V"
echo "  device    Vulkan0 (GGML_VK_VISIBLE_DEVICES=0)"
echo "  log       $LOG_FILE"

if [ "$DRY_RUN" = true ]; then
  echo "  [DRY RUN] not launching"
  exit 0
fi

export GGML_VK_VISIBLE_DEVICES=0

"$BIN" \
  --model "$MODEL_PATH" \
  --host "$HOST" \
  --port "$PORT" \
  --ctx-size "$CTX" \
  --threads "$THREADS_EFFECTIVE" \
  --batch-size "$BATCH_SIZE" \
  --ubatch-size "$UBATCH_SIZE" \
  --cache-type-k "$CACHE_TYPE_K" \
  --cache-type-v "$CACHE_TYPE_V" \
  --n-gpu-layers "$GPU_LAYERS" \
  --device Vulkan0 \
  --parallel "$PARALLEL" \
  --cont-batching \
  --jinja \
  > "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
sleep 2
if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "  OK pid=$(cat "$PID_FILE")"
  echo "  Tail log:  tail -F $LOG_FILE"
  echo "  Smoke:     curl -s http://${HOST}:${PORT}/health"
else
  echo "  FAILED — see $LOG_FILE"
  exit 1
fi
