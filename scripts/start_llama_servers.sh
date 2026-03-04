#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"
ENV_FILE="$AI_ROOT/run/llama-servers.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Missing env file: $ENV_FILE"
  exit 1
fi

source "$ENV_FILE"

BIN="$AI_ROOT/llama_cpp/build/bin/llama-server"

if [ ! -x "$BIN" ]; then
  echo "ERROR: llama-server not found: $BIN"
  exit 1
fi

THREADS_EFFECTIVE="${THREADS:-0}"

mkdir -p "$AI_ROOT/logs" "$AI_ROOT/run"

start_model () {

  NAME="$1"
  MODEL_FILE="$2"
  PORT="$3"
  CTX="$4"
  GPU="$5"

  MODEL_PATH="$AI_ROOT/models/$MODEL_FILE"
  PIDFILE="$AI_ROOT/run/${NAME}.pid"
  LOGFILE="$AI_ROOT/logs/${NAME}.log"

  if [ ! -f "$MODEL_PATH" ]; then
    echo "ERROR: Missing model for $NAME: $MODEL_PATH"
    return 1
  fi

  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "SKIP: $NAME already running (pid $(cat "$PIDFILE"))"
    return 0
  fi

  rm -f "$PIDFILE"

  echo "Starting $NAME on http://${HOST}:${PORT}"
  echo "  model=$MODEL_PATH"

  nohup "$BIN" \
    --model "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    --ctx-size "$CTX" \
    --threads "$THREADS_EFFECTIVE" \
    --batch-size "$BATCH_SIZE" \
    --ubatch-size 512 \
    --cache-type-k q8_0 \
    --cache-type-v q8_0 \
    --n-gpu-layers "$GPU" \
    > "$LOGFILE" 2>&1 &

  echo $! > "$PIDFILE"

  sleep 1

  if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "  OK pid=$(cat "$PIDFILE") log=$LOGFILE"
  else
    echo "  FAILED (see $LOGFILE)"
  fi
}

FAILED=0

start_model "persona" \
"$PERSONA_MODEL" \
"$PERSONA_PORT" \
"$PERSONA_CTX" \
"$GPU_LAYERS_PERSONA" || FAILED=$((FAILED+1))

start_model "scientist" \
"$SCIENTIST_MODEL" \
"$SCIENTIST_PORT" \
"$SCIENTIST_CTX" \
"$GPU_LAYERS_SCIENTIST" || FAILED=$((FAILED+1))

if [ "$FAILED" -eq 0 ]; then
  echo "All llama servers started."
else
  echo "WARNING: $FAILED llama server(s) failed to start."
fi
