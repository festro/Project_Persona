#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

echo "==> Cleaning runtime state in $AI_ROOT"

rm -f "$AI_ROOT/run/"*.pid 2>/dev/null || true
rm -f "$AI_ROOT/logs/"*.log 2>/dev/null || true

echo "==> (Optional) Removing venv (env/) if you want a fresh install"
echo "    Run manually if desired: rm -rf \"$AI_ROOT/env\""

echo "==> (Optional) Removing memory databases (Chroma) if you want a blank persona"
echo "    Run manually if desired:"
echo "      rm -rf \"$AI_ROOT/persona/global_memory/chroma\""
echo "      rm -rf \"$AI_ROOT/persona/profiles\"/*/memory/chroma"

echo "✓ Done."
