#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

stop_one () {
  local name="$1"
  local pidfile="$AI_ROOT/run/${name}.pid"
  if [ ! -f "$pidfile" ]; then
    return 0
  fi

  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"

  if [ -z "${pid:-}" ] || ! kill -0 "$pid" 2>/dev/null; then
    echo "CLEAN: $name stale pidfile"
    rm -f "$pidfile"
    return 0
  fi

  echo "Stopping $name (pid $pid)"
  kill "$pid" 2>/dev/null || true

  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$pidfile"
      echo "  stopped"
      return 0
    fi
    sleep 0.25
  done

  echo "  force killing"
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$pidfile"
}

mkdir -p "$AI_ROOT/run"

# New architecture
stop_one "persona"
stop_one "scientist"

# Legacy cleanup (in case old pids exist)
stop_one "reasoning"
stop_one "coder"

echo "All llama servers stopped."
