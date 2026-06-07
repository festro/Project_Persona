#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

URL="http://${HOST}:${PORT}/agent/run"

echo "[smoke] POST ${URL}"
resp=$(curl -sS -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '{"ping":"pong"}')

echo "[smoke] response: $resp"

echo "$resp" | grep -q '"status"'
echo "$resp" | grep -q '"ok"'

echo "[smoke] OK"
