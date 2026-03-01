#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"
PIDFILE="$AI_ROOT/run/api.pid"
if [ ! -f "$PIDFILE" ]; then
  echo "API not running"
  exit 0
fi
PID="$(cat "$PIDFILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "Stopping API (pid $PID)"
  kill "$PID" 2>/dev/null || true
  sleep 1
fi
rm -f "$PIDFILE"
echo "API stopped."
