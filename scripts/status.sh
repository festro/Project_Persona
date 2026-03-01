#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

echo "=== AI Status ==="

echo ""
echo "llama.cpp servers:"
for name in persona reasoning coder; do
  pidfile="$AI_ROOT/run/${name}.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "  ✓ $name: running (pid $pid)"
    else
      echo "  ✗ $name: stale pidfile"
    fi
  else
    echo "  - $name: not running"
  fi
done

echo ""
echo "API:"
pidfile="$AI_ROOT/run/api.pid"
if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
  echo "  ✓ api: running (pid $(cat "$pidfile"))"
else
  echo "  - api: not running"
fi

echo ""
echo "Models:"
for m in persona.gguf reasoning.gguf coder.gguf; do
  p="$AI_ROOT/models/$m"
  if [ -f "$p" ]; then
    echo "  ✓ $m ($(du -h "$p" | cut -f1))"
  else
    echo "  ✗ $m missing"
  fi
done

echo ""
echo "Endpoints:"
echo "  API health:  http://127.0.0.1:8000/health"
echo "  API docs:    http://127.0.0.1:8000/docs"
