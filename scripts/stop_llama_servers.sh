#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

stop_one () {
  local name="$1"
  local pidfile="$AI_ROOT/run/${name}.pid"
  if [ ! -f "$pidfile" ]; then
    echo "SKIP: $name not running"
    return 0
  fi
  local pid
  pid="$(cat "$pidfile")"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "SKIP: $name stale pidfile"
    rm -f "$pidfile"
    return 0
  fi
  echo "Stopping $name (pid $pid)"
  kill "$pid" 2>/dev/null || true
  for _ in {1..10}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$pidfile"
      echo "  stopped"
      return 0
    fi
    sleep 0.5
  done
  echo "  force killing"
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$pidfile"
}

stop_one "persona"
stop_one "reasoning"
stop_one "coder"
echo "All llama servers stopped."
