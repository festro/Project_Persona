#!/usr/bin/env bash
# scripts/doctor.sh
# Native AI stack health checker (llama.cpp servers + FastAPI + RAG dirs)
# Deep mode: ./doctor.sh --deep
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"
ENV_FILE="$AI_ROOT/run/llama-servers.env"
HOST="${HOST:-127.0.0.1}"

DEEP=false
if [ "${1:-}" = "--deep" ]; then
  DEEP=true
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*"; }
info() { echo -e "${BLUE}==>${NC} $*"; }

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    warn "Missing command: $1"
    return 1
  fi
  ok "Found command: $1"
  return 0
}

curl_get() {
  local url="$1"
  local mt="${2:-2}"
  curl -sS --max-time "$mt" "$url" 2>/dev/null || true
}

curl_post() {
  local url="$1"
  local json="$2"
  local mt="${3:-30}"
  curl -sS --max-time "$mt" -X POST "$url" -H "Content-Type: application/json" -d "$json" 2>/dev/null || true
}

has_json_key() {
  local js="$1"
  local key="$2"
  echo "$js" | grep -q "$key"
}

info "AI doctor starting"
echo "AI_ROOT: $AI_ROOT"
echo "Mode:    $([ "$DEEP" = true ] && echo "DEEP" || echo "standard")"
echo ""

info "Basic filesystem checks"
[ -d "$AI_ROOT" ] && ok "AI_ROOT exists" || { err "AI_ROOT missing: $AI_ROOT"; exit 1; }

for d in scripts services/api run logs models persona; do
  [ -d "$AI_ROOT/$d" ] && ok "Dir present: $d" || warn "Dir missing: $d"
done

[ -f "$ENV_FILE" ] && ok "Env file present: run/llama-servers.env" || warn "Env file missing: $ENV_FILE"

PERSONA_ROOT="${PERSONA_ROOT:-$AI_ROOT/persona}"
PROFILES_DIR="${PROFILES_DIR:-$PERSONA_ROOT/profiles}"
GLOBAL_MEMORY_DIR="${GLOBAL_MEMORY_DIR:-$PERSONA_ROOT/global_memory}"

[ -d "$PROFILES_DIR" ] && ok "Profiles dir: $PROFILES_DIR" || warn "Profiles dir missing: $PROFILES_DIR"
[ -d "$GLOBAL_MEMORY_DIR" ] && ok "Global memory dir: $GLOBAL_MEMORY_DIR" || warn "Global memory dir missing: $GLOBAL_MEMORY_DIR"
echo ""

info "Command availability"
need_cmd bash || true
need_cmd curl || true
need_cmd python3 || true
need_cmd grep || true
need_cmd tail || true
need_cmd awk || true
echo ""

info "Python venv checks"
[ -x "$AI_ROOT/env/bin/python" ] && ok "Venv python: $AI_ROOT/env/bin/python" || warn "Venv not found at $AI_ROOT/env/"
[ -x "$AI_ROOT/env/bin/uvicorn" ] && ok "Venv uvicorn: $AI_ROOT/env/bin/uvicorn" || warn "uvicorn missing in venv"
echo ""

info "llama.cpp binary check"
LLAMA_BIN="$AI_ROOT/llama_cpp/build/bin/llama-server"
[ -x "$LLAMA_BIN" ] && ok "llama-server binary present: $LLAMA_BIN" || warn "llama-server binary missing: $LLAMA_BIN"
echo ""

info "Load ports & models from env (if available)"
PERSONA_PORT=8080
SCIENTIST_PORT=8081
PERSONA_MODEL="persona.gguf"
SCIENTIST_MODEL="scientist.gguf"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  PERSONA_PORT="${PERSONA_PORT:-8080}"
  SCIENTIST_PORT="${SCIENTIST_PORT:-8081}"
  PERSONA_MODEL="${PERSONA_MODEL:-persona.gguf}"
  SCIENTIST_MODEL="${SCIENTIST_MODEL:-scientist.gguf}"
  HOST="${HOST:-127.0.0.1}"
  ok "Loaded ports/models from env"
else
  warn "Using default ports/models (env missing)"
fi

echo "Ports:  persona=$PERSONA_PORT scientist=$SCIENTIST_PORT"
echo "Models: $PERSONA_MODEL $SCIENTIST_MODEL"
echo ""

info "Model file presence"
for m in "$PERSONA_MODEL" "$SCIENTIST_MODEL"; do
  if [ -f "$AI_ROOT/models/$m" ]; then
    size="$(du -h "$AI_ROOT/models/$m" | awk '{print $1}')"
    ok "Model present: models/$m ($size)"
  else
    warn "Model missing: models/$m"
  fi
done
echo ""

info "Profile wrapper files check (default profile)"
DEFAULT_PROFILE="${DEFAULT_PROFILE:-default}"
PBASE="$PROFILES_DIR/$DEFAULT_PROFILE"
if [ -d "$PBASE" ]; then
  ok "Default profile dir exists: $PBASE"
  for f in persona.md style.md system_rules.md; do
    [ -f "$PBASE/$f" ] && ok "Wrapper present: $DEFAULT_PROFILE/$f" || warn "Wrapper missing: $DEFAULT_PROFILE/$f"
  done
else
  warn "Default profile dir missing: $PBASE"
fi
echo ""

info "Runtime process checks (pidfiles) — optional"
check_pid() {
  local name="$1"
  local pidfile="$AI_ROOT/run/${name}.pid"
  if [ -f "$pidfile" ]; then
    local pid
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      ok "$name running (pid $pid)"
      return 0
    else
      warn "$name pidfile exists but process not running (stale pidfile?)"
      return 1
    fi
  else
    warn "$name pidfile not found"
    return 1
  fi
}
check_pid "persona" || true
check_pid "scientist" || true
check_pid "api" || true
echo ""

info "Service health checks (live)"
check_llama_health() {
  local name="$1"
  local port="$2"
  local url="http://${HOST}:${port}/health"
  local resp
  resp="$(curl_get "$url" 2)"
  if has_json_key "$resp" '"status"'; then
    ok "$name /health OK ($url)"
    return 0
  else
    warn "$name /health not responding ($url)"
    return 1
  fi
}

check_llama_health "persona" "$PERSONA_PORT" || true
check_llama_health "scientist" "$SCIENTIST_PORT" || true

API_HOST="127.0.0.1"
API_PORT="8000"
API_HEALTH_URL="http://${API_HOST}:${API_PORT}/health"
API_RESP="$(curl_get "$API_HEALTH_URL" 2)"
if has_json_key "$API_RESP" '"status"'; then
  ok "API /health OK ($API_HEALTH_URL)"
else
  warn "API /health not responding ($API_HEALTH_URL)"
fi
echo ""

info "Quick completion smoke test (live)"
SMOKE_PROMPT="Say 'ok' and one short sentence."
smoke_completion() {
  local name="$1"
  local port="$2"
  local resp
  resp="$(curl_post "http://${HOST}:${port}/completion" \
    "{\"prompt\":\"$SMOKE_PROMPT\",\"n_predict\":32,\"temperature\":0.2}" \
    12)"
  if has_json_key "$resp" '"content"'; then
    ok "$name completion OK"
  else
    warn "$name completion failed or timed out"
  fi
}

smoke_completion "persona" "$PERSONA_PORT"
smoke_completion "scientist" "$SCIENTIST_PORT"
echo ""

info "RAG directories sanity"
[ -d "$GLOBAL_MEMORY_DIR/chroma" ] && ok "Global chroma dir exists" || warn "Global chroma dir missing"
[ -d "$GLOBAL_MEMORY_DIR/exports" ] && ok "Global exports dir exists" || warn "Global exports dir missing"
echo ""

info "Jobs persistence file (optional)"
JOBS_FILE="${JOBS_PERSIST_PATH:-$AI_ROOT/run/jobs.jsonl}"
if [ -f "$JOBS_FILE" ]; then
  ok "Jobs file exists: $JOBS_FILE"
  tail -n 1 "$JOBS_FILE" >/dev/null 2>&1 && ok "Jobs file readable" || warn "Jobs file not readable"
else
  warn "Jobs file not found yet (will be created after first job): $JOBS_FILE"
fi
echo ""

info "Doctor done"
