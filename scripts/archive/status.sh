#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
ENV_FILE="$AI_ROOT/run/llama-servers.env"

echo "=== AI Status ==="

echo ""
echo "API:"
api_pidfile="$AI_ROOT/run/api.pid"
if [ -f "$api_pidfile" ] && kill -0 "$(cat "$api_pidfile")" 2>/dev/null; then
  echo "  ✓ api: running (pid $(cat "$api_pidfile"))"
else
  echo "  - api: not running"
fi

echo ""
echo "llama.cpp servers:"
# Unified single-model topology: only persona is live.
# Legacy names kept in the case-exclusion below so stale scientist/reasoning/coder pidfiles
# do not double-show via the "extra" loop.
declare -a names=("persona")
for name in "${names[@]}"; do
  pidfile="$AI_ROOT/run/${name}.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      echo "  ✓ $name: running (pid $pid)"
    else
      echo "  ✗ $name: stale pidfile ($pidfile)"
    fi
  fi
done

# Show any other pidfiles (excluding api.pid + legacy names) for visibility.
shopt -s nullglob
extra=("$AI_ROOT/run/"*.pid)
shopt -u nullglob
for p in "${extra[@]}"; do
  base="$(basename "$p")"
  [ "$base" = "api.pid" ] && continue
  name="${base%.pid}"
  case "$name" in
    persona|scientist|reasoning|coder) continue ;;
  esac
  pid="$(cat "$p" 2>/dev/null || true)"
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
    echo "  ✓ $name: running (pid $pid)"
  else
    echo "  ✗ $name: stale pidfile ($p)"
  fi
done

echo ""
echo "Config:"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  echo "  env: $ENV_FILE"
  echo "  host: ${HOST:-127.0.0.1}"
  echo "  persona: port=${PERSONA_PORT:-8080} model=${PERSONA_MODEL:-<unset>} ctx=${PERSONA_CTX:-<unset>} gpu_layers=${GPU_LAYERS_PERSONA:-<unset>} parallel=${PERSONA_PARALLEL:-<unset>}"
else
  echo "  (missing) $ENV_FILE"
fi

echo ""
echo "Models:"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  for m in "${PERSONA_MODEL:-}"; do
    [ -z "${m:-}" ] && continue
    p="$AI_ROOT/models/$m"
    if [ -f "$p" ]; then
      echo "  ✓ $m ($(du -h "$p" | cut -f1))"
    else
      echo "  ✗ $m missing"
    fi
  done
else
  echo "  (no env loaded; skipping model checks)"
fi

echo ""
echo "Hermes:"
HERMES_VENV="$AI_ROOT/env_hermes"
if [ -x "$HERMES_VENV/bin/python" ]; then
  echo "  ✓ env_hermes venv present"
  if [ -x "$HERMES_VENV/bin/hermes" ]; then
    echo "  ✓ hermes binary present"
  else
    echo "  - hermes binary not installed in env_hermes"
  fi
else
  echo "  - env_hermes venv missing (run setup_native_stack.sh)"
fi
DEFAULT_PROFILE="${DEFAULT_PROFILE:-default}"
DEFAULT_CFG="$AI_ROOT/persona/profiles/$DEFAULT_PROFILE/config.yaml"
if [ -f "$DEFAULT_CFG" ]; then
  echo "  ✓ $DEFAULT_PROFILE/config.yaml present"
else
  echo "  - $DEFAULT_PROFILE/config.yaml missing (run init_profiles.sh)"
fi

echo ""
echo "Endpoints:"
echo "  API:        http://127.0.0.1:8000/docs"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  echo "  Persona:    http://${HOST:-127.0.0.1}:${PERSONA_PORT:-8080}/health"
fi
