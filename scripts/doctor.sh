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
  # Usage: curl_get URL [max_time_seconds]
  local url="$1"
  local mt="${2:-2}"
  curl -sS --max-time "$mt" "$url" 2>/dev/null || true
}

curl_post() {
  # Usage: curl_post URL JSON [max_time_seconds]
  local url="$1"
  local json="$2"
  local mt="${3:-30}"
  curl -sS --max-time "$mt" -X POST "$url" -H "Content-Type: application/json" -d "$json" 2>/dev/null || true
}

has_json_key() {
  # Usage: has_json_key "json" '"key"'
  local js="$1"
  local key="$2"
  echo "$js" | grep -q "$key"
}

# ------------------------------------------------------------------------------
info "AI doctor starting"
echo "AI_ROOT: $AI_ROOT"
echo "Mode:    $([ "$DEEP" = true ] && echo "DEEP" || echo "standard")"
echo ""

# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
info "Command availability"
need_cmd bash || true
need_cmd curl || true
need_cmd python3 || true
need_cmd grep || true
need_cmd tail || true
need_cmd awk || true
echo ""

# ------------------------------------------------------------------------------
info "Python venv checks"
[ -x "$AI_ROOT/env/bin/python" ] && ok "Venv python: $AI_ROOT/env/bin/python" || warn "Venv not found at $AI_ROOT/env/"
[ -x "$AI_ROOT/env/bin/uvicorn" ] && ok "Venv uvicorn: $AI_ROOT/env/bin/uvicorn" || warn "uvicorn missing in venv"
echo ""

# ------------------------------------------------------------------------------
info "llama.cpp binary check"
LLAMA_BIN="$AI_ROOT/llama_cpp/build/bin/llama-server"
[ -x "$LLAMA_BIN" ] && ok "llama-server binary present: $LLAMA_BIN" || warn "llama-server binary missing: $LLAMA_BIN"
echo ""

# ------------------------------------------------------------------------------
info "Load ports & models from env (if available)"
PERSONA_PORT=8080
REASONING_PORT=8081
CODER_PORT=8082
PERSONA_MODEL="persona.gguf"
REASONING_MODEL="reasoning.gguf"
CODER_MODEL="coder.gguf"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  PERSONA_PORT="${PERSONA_PORT:-8080}"
  REASONING_PORT="${REASONING_PORT:-8081}"
  CODER_PORT="${CODER_PORT:-8082}"
  PERSONA_MODEL="${PERSONA_MODEL:-persona.gguf}"
  REASONING_MODEL="${REASONING_MODEL:-reasoning.gguf}"
  CODER_MODEL="${CODER_MODEL:-coder.gguf}"
  HOST="${HOST:-127.0.0.1}"
  ok "Loaded ports/models from env"
else
  warn "Using default ports/models (env missing)"
fi

echo "Ports:  persona=$PERSONA_PORT reasoning=$REASONING_PORT coder=$CODER_PORT"
echo "Models: $PERSONA_MODEL $REASONING_MODEL $CODER_MODEL"
echo ""

# ------------------------------------------------------------------------------
info "Model file presence"
for m in "$PERSONA_MODEL" "$REASONING_MODEL" "$CODER_MODEL"; do
  if [ -f "$AI_ROOT/models/$m" ]; then
    size="$(du -h "$AI_ROOT/models/$m" | awk '{print $1}')"
    ok "Model present: models/$m ($size)"
  else
    warn "Model missing: models/$m"
  fi
done
echo ""

# ------------------------------------------------------------------------------
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
check_pid "reasoning" || true
check_pid "coder" || true
check_pid "api" || true
echo ""

# ------------------------------------------------------------------------------
info "Service health checks (live)"
llama_ok=0
api_ok=0

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

check_llama_health "persona" "$PERSONA_PORT"   && llama_ok=$((llama_ok+1)) || true
check_llama_health "reasoning" "$REASONING_PORT" && llama_ok=$((llama_ok+1)) || true
check_llama_health "coder" "$CODER_PORT"       && llama_ok=$((llama_ok+1)) || true

API_HOST="127.0.0.1"
API_PORT="8000"
API_HEALTH_URL="http://${API_HOST}:${API_PORT}/health"
API_RESP="$(curl_get "$API_HEALTH_URL" 2)"
if has_json_key "$API_RESP" '"status"'; then
  ok "API /health OK ($API_HEALTH_URL)"
  api_ok=1
else
  warn "API /health not responding ($API_HEALTH_URL)"
fi
echo ""

# ------------------------------------------------------------------------------
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
smoke_completion "reasoning" "$REASONING_PORT"
smoke_completion "coder" "$CODER_PORT"
echo ""

# ------------------------------------------------------------------------------
info "GPU/Vulkan offload hints (log evidence only — may be from older runs)"
scan_offload() {
  local name="$1"
  local logfile="$AI_ROOT/logs/${name}.log"
  if [ ! -f "$logfile" ]; then
    warn "No log for $name at $logfile"
    return 0
  fi

  local vulkan_lines offload_lines
  vulkan_lines="$(grep -iE 'ggml_vulkan: Found|using device Vulkan|Vulkan0' "$logfile" | tail -n 3 || true)"
  offload_lines="$(grep -iE 'offloaded [0-9]+/[0-9]+ layers|offloading .* to GPU' "$logfile" | tail -n 3 || true)"

  if [ -n "$vulkan_lines" ] || [ -n "$offload_lines" ]; then
    ok "$name: GPU/Vulkan evidence found in logs"
    [ -n "$vulkan_lines" ] && echo "$vulkan_lines" | sed 's/^/  /'
    [ -n "$offload_lines" ] && echo "$offload_lines" | sed 's/^/  /'
  else
    warn "$name: No obvious GPU/Vulkan offload evidence in logs"
  fi
}

scan_offload "persona"
scan_offload "reasoning"
scan_offload "coder"
echo ""

# ------------------------------------------------------------------------------
info "RAG directories sanity"
[ -d "$GLOBAL_MEMORY_DIR/chroma" ] && ok "Global chroma dir exists" || warn "Global chroma dir missing"
[ -d "$GLOBAL_MEMORY_DIR/exports" ] && ok "Global exports dir exists" || warn "Global exports dir missing"

if [ -d "$PROFILES_DIR" ]; then
  profiles=( "$PROFILES_DIR"/* )
  if [ "${profiles[0]}" = "$PROFILES_DIR/*" ]; then
    warn "No profiles found in $PROFILES_DIR"
  else
    ok "Profiles found:"
    for p in "$PROFILES_DIR"/*; do
      [ -d "$p" ] || continue
      name="$(basename "$p")"
      echo "  - $name"
      [ -f "$p/persona.md" ] && ok "    persona.md" || warn "    persona.md missing"
      [ -f "$p/style.md" ] && ok "    style.md" || warn "    style.md missing"
      [ -f "$p/system_rules.md" ] && ok "    system_rules.md" || warn "    system_rules.md missing"
      [ -d "$p/memory/chroma" ] && ok "    memory/chroma" || warn "    memory/chroma missing"
      [ -d "$p/memory/exports" ] && ok "    memory/exports" || warn "    memory/exports missing"
    done
  fi
fi
echo ""

# ------------------------------------------------------------------------------
# Deep mode: requires live API
# ------------------------------------------------------------------------------
if [ "$DEEP" = true ]; then
  info "DEEP MODE: API chat + RAG verification"

  if [ "$api_ok" != "1" ]; then
    warn "Deep mode requires API running, but API /health is not responding."
    echo "Start the stack first:"
    echo "  $AI_ROOT/scripts/start_all.sh"
    echo "Or at minimum:"
    echo "  $AI_ROOT/scripts/start_llama_servers.sh"
    echo "  $AI_ROOT/scripts/start_api.sh"
    echo ""
    warn "Skipping deep mode because services are not reachable."
  else
    CHAT_URL="http://${API_HOST}:${API_PORT}/chat"
    PROFILES_URL="http://${API_HOST}:${API_PORT}/profiles"
    MEM_ADD_URL="http://${API_HOST}:${API_PORT}/memory/add"
    MEM_SEARCH_URL="http://${API_HOST}:${API_PORT}/memory/search"

    profiles_resp="$(curl_get "$PROFILES_URL" 4)"
    if has_json_key "$profiles_resp" '"profiles"'; then
      ok "API /profiles OK"
    else
      warn "API /profiles failed (continuing anyway)"
    fi

    TEST_PROFILE="${DEFAULT_PROFILE:-default}"
    echo "Deep test profile: $TEST_PROFILE"
    echo ""

    make_chat_payload() {
      local topic="$1"
      local text="$2"
      local profile="$3"
      python3 - "$topic" "$text" "$profile" <<'PY'
import json, sys
topic, text, profile = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({
  "text": text,
  "topic": topic,
  "profile": profile,
  "debug": True,
  "max_tokens": 128,
  "temperature": 0.6
}))
PY
    }

    run_chat_test() {
      local topic="$1"
      local text="$2"
      local payload
      payload="$(make_chat_payload "$topic" "$text" "$TEST_PROFILE")"

      local resp
      resp="$(curl_post "$CHAT_URL" "$payload" 180)"

      if has_json_key "$resp" '"text"'; then
        ok "/chat topic=$topic OK"
        python3 - "$resp" <<'PY'
import json, sys
raw=sys.argv[1]
try:
  d=json.loads(raw)
  dbg=d.get("debug") or {}
  mem=dbg.get("memory") or {}
  t=dbg.get("timings_ms") or {}
  print(f"  confidence={d.get('confidence')} body_cue={d.get('body_cue')} experts={d.get('experts_consulted')}")
  print(f"  profile_hits={t.get('profile_hits','n/a')} global_hits={t.get('global_hits','n/a')} mem_ms={t.get('memory_retrieval_ms','n/a')} persona_ms={t.get('persona_ms','n/a')} expert_ms={t.get('expert_ms','n/a')}")
except Exception as e:
  print("  (debug parse failed)", e)
PY
      else
        warn "/chat topic=$topic FAILED"
        echo "  Response (truncated):"
        echo "$resp" | head -c 600; echo
      fi
    }

    info "DEEP: /chat smoke tests (debug=true)"
    run_chat_test "general" "What did we decide about GPU layers tuning? (If you have memory, use it.)"
    run_chat_test "biology" "Summarize key assumptions in RNA-seq differential expression analysis."
    run_chat_test "coding"  "Write a bash snippet to check if a port is listening and print a message."
    echo ""

    info "DEEP: /memory/add + /memory/search verification"
    SENT="doctor-sentinel-$(date +%s)"

    add_payload="$(python3 - "$TEST_PROFILE" "$SENT" <<'PY'
import json, sys
profile, sent = sys.argv[1], sys.argv[2]
print(json.dumps({
  "text": f"This is a doctor test memory. Sentinel={sent}. Remember: GPU layers use per-model overrides.",
  "scope": "profile",
  "profile": profile,
  "kind": "note",
  "tags": ["doctor","gpu_layers"],
  "source": "doctor_deep"
}))
PY
)"
    add_resp="$(curl_post "$MEM_ADD_URL" "$add_payload" 30)"
    if has_json_key "$add_resp" '"ok": true'; then
      ok "Memory add (profile) OK"
    else
      warn "Memory add (profile) FAILED"
      echo "$add_resp" | head -c 800; echo
    fi

    search_payload="$(python3 - "$TEST_PROFILE" "$SENT" <<'PY'
import json, sys
profile, sent = sys.argv[1], sys.argv[2]
print(json.dumps({
  "query": f"Sentinel={sent}",
  "scope": "profile",
  "profile": profile,
  "top_k_profile": 5,
  "top_k_global": 0
}))
PY
)"
    search_resp="$(curl_post "$MEM_SEARCH_URL" "$search_payload" 30)"
    if echo "$search_resp" | grep -q "$SENT"; then
      ok "Memory search found sentinel"
    else
      warn "Memory search did NOT find sentinel"
      echo "$search_resp" | head -c 1200; echo
    fi

    echo ""
    ok "DEEP MODE complete."
  fi
fi

# ------------------------------------------------------------------------------
info "Doctor summary"
echo "If something is failing:"
echo "  - Check logs:  tail -n 200 ~/AI/logs/api.log"
echo "                tail -n 200 ~/AI/logs/persona.log"
echo "                tail -n 200 ~/AI/logs/reasoning.log"
echo "                tail -n 200 ~/AI/logs/coder.log"
echo "  - Check status: ~/AI/scripts/status.sh"
echo "  - Restart stack: ~/AI/scripts/stop_all.sh && ~/AI/scripts/start_all.sh"
echo ""
ok "Doctor finished."
