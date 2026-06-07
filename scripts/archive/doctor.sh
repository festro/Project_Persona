#!/usr/bin/env bash
# scripts/doctor.sh
# Native AI stack health checker (llama.cpp servers + FastAPI + RAG dirs)
# Deep mode: ./doctor.sh --deep
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
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

info "Hermes venv checks (T1.1)"
HERMES_VENV="$AI_ROOT/env_hermes"
HERMES_INSTALLED=0
if [ -x "$HERMES_VENV/bin/python" ]; then
  ok "env_hermes venv: $HERMES_VENV"
  if [ -x "$HERMES_VENV/bin/hermes" ]; then
    ok "hermes binary present in env_hermes"
    HERMES_INSTALLED=1
  else
    warn "hermes not installed in env_hermes (pip install hermes-agent)"
  fi
else
  warn "env_hermes venv missing: $HERMES_VENV (run setup_native_stack.sh)"
fi
echo ""

info "llama.cpp binary check"
LLAMA_BIN="$AI_ROOT/llama_cpp/build/bin/llama-server"
[ -x "$LLAMA_BIN" ] && ok "llama-server binary present: $LLAMA_BIN" || warn "llama-server binary missing: $LLAMA_BIN"
echo ""

info "Load port & model from env (if available)"
PERSONA_PORT=8090
PERSONA_MODEL="Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  PERSONA_PORT="${PERSONA_PORT:-8090}"
  PERSONA_MODEL="${PERSONA_MODEL:-Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf}"
  HOST="${HOST:-127.0.0.1}"
  ok "Loaded port/model from env"
else
  warn "Using default port/model (env missing)"
fi

echo "Port:  persona=$PERSONA_PORT"
echo "Model: $PERSONA_MODEL"
echo ""

info "Model file presence"
if [ -f "$AI_ROOT/models/$PERSONA_MODEL" ]; then
  size="$(du -h "$AI_ROOT/models/$PERSONA_MODEL" | awk '{print $1}')"
  ok "Model present: models/$PERSONA_MODEL ($size)"
else
  warn "Model missing: models/$PERSONA_MODEL"
fi
echo ""

info "Profile files check (default profile)"
DEFAULT_PROFILE="${DEFAULT_PROFILE:-default}"
PBASE="$PROFILES_DIR/$DEFAULT_PROFILE"
if [ -d "$PBASE" ]; then
  ok "Default profile dir exists: $PBASE"
  for f in SOUL.md .hermes.md config.yaml; do
    [ -f "$PBASE/$f" ] && ok "Profile file present: $DEFAULT_PROFILE/$f" || warn "Profile file missing: $DEFAULT_PROFILE/$f"
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

info "Safe-config conformance (T1 gate)"
DEFAULT_PROFILE="${DEFAULT_PROFILE:-default}"
DEFAULT_CFG="$PROFILES_DIR/$DEFAULT_PROFILE/config.yaml"
T1_GATE="unknown"

pick_python_with_yaml() {
  for cand in "$AI_ROOT/env_hermes/bin/python" "$AI_ROOT/env/bin/python" python3; do
    if command -v "$cand" >/dev/null 2>&1 || [ -x "$cand" ]; then
      if "$cand" -c "import yaml" >/dev/null 2>&1; then
        echo "$cand"
        return 0
      fi
    fi
  done
  return 1
}

if [ ! -f "$DEFAULT_CFG" ]; then
  warn "Default profile config.yaml missing: $DEFAULT_CFG (run init_profiles.sh)"
  T1_GATE="fail"
else
  PYBIN="$(pick_python_with_yaml || true)"
  if [ -n "${PYBIN:-}" ]; then
    if "$PYBIN" - "$DEFAULT_CFG" <<'PYEOF'
import sys, yaml
with open(sys.argv[1]) as f:
    c = yaml.safe_load(f) or {}
errors = []
model = c.get('model') or {}
if model.get('provider') != 'custom':
    errors.append("model.provider must be 'custom'")
base = str(model.get('base_url') or '')
if not (base.startswith('http://127.0.0.1:') or base.startswith('http://localhost:')):
    errors.append("model.base_url must be a local endpoint (127.0.0.1/localhost)")
api_key = str(model.get('api_key') or '')
if api_key and api_key not in ('not-needed', 'local', 'local-key') and not api_key.startswith('${'):
    errors.append("model.api_key looks like a real secret; secrets belong in .env")
fb = c.get('fallback_model')
if fb not in (None, {}, '', [], False):
    errors.append("fallback_model must be empty (no cloud failover)")
aux = c.get('auxiliary') or {}
for name, spec in aux.items():
    spec = spec or {}
    if spec.get('provider') != 'main':
        errors.append("auxiliary.%s.provider must be 'main'" % name)
tools = c.get('tools') or {}
disabled = set(tools.get('disabled') or [])
missing = {'web_search', 'web_extract', 'web_crawl'} - disabled
if missing:
    errors.append("tools.disabled missing egress tools: %s" % ','.join(sorted(missing)))
if not any(str(t).startswith('browser') for t in disabled):
    errors.append("tools.disabled must disable browser_* tools")
if errors:
    for e in errors:
        print("  VIOLATION: " + e)
    sys.exit(1)
sys.exit(0)
PYEOF
    then
      ok "Default profile config.yaml conforms to safe-config schema"
      T1_GATE="pass"
    else
      err "Default profile config.yaml FAILED safe-config conformance"
      T1_GATE="fail"
    fi
  else
    warn "No python with PyYAML available; running grep-based fallback checks"
    fail=0
    grep -Eq '^[[:space:]]*provider:[[:space:]]*custom' "$DEFAULT_CFG" || { err "model.provider: custom not found"; fail=1; }
    grep -Eq 'base_url:[[:space:]]*http://(127\.0\.0\.1|localhost):' "$DEFAULT_CFG" || { err "local base_url not found"; fail=1; }
    grep -Eq 'fallback_model:[[:space:]]*\{\}' "$DEFAULT_CFG" || { err "empty fallback_model not found"; fail=1; }
    for t in web_search web_extract web_crawl; do
      grep -Eq "^[[:space:]]*-[[:space:]]*$t([[:space:]]|$)" "$DEFAULT_CFG" || { err "tools.disabled missing $t"; fail=1; }
    done
    grep -Eq "^[[:space:]]*-[[:space:]]*browser" "$DEFAULT_CFG" || { err "tools.disabled missing browser_* tools"; fail=1; }
    if [ "$fail" = "0" ]; then
      ok "Default profile config.yaml passes grep-based safe-config checks"
      T1_GATE="pass"
    else
      T1_GATE="fail"
    fi
  fi
fi

echo ""
echo "T1 GATE: env_hermes_installed=$([ "$HERMES_INSTALLED" = "1" ] && echo yes || echo no) safe_config=$T1_GATE"
if [ "${STRICT_GATE:-0}" = "1" ]; then
  if [ "$T1_GATE" != "pass" ] || [ "$HERMES_INSTALLED" != "1" ]; then
    err "STRICT_GATE=1 and T1 gate not fully green"
    exit 2
  fi
fi
echo ""

info "Doctor done"
