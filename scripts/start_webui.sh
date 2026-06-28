#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
VENV="$AI_ROOT/env_webui"

if [ ! -x "$VENV/bin/python" ]; then
  echo "ERROR: WebUI venv not found at: $VENV"
  echo "Create it with:"
  echo "  python3 -m venv ~/AI/env_webui"
  echo "  source ~/AI/env_webui/bin/activate"
  echo "  pip install -U pip wheel"
  echo "  pip install open-webui==0.9.6   # + 'pip install -U ddgs' for the researcher web tool"
  exit 1
fi

# Activate isolated venv (keeps API env clean)
source "$VENV/bin/activate"

# Persistent WebUI data
mkdir -p "$AI_ROOT/openwebui"

export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-http://127.0.0.1:8000/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-local-anything}"
# OpenWebUI 0.8.8 reads DATA_DIR (NOT WEBUI_DATA_DIR) -- keep the DB/accounts/chats in the project,
# not inside env_webui/.../open_webui/data (which a venv rebuild would wipe).
export DATA_DIR="${DATA_DIR:-$AI_ROOT/openwebui}"
# We do not run Ollama; skip its probe so startup doesn't retry a dead :11434.
export ENABLE_OLLAMA_API="${ENABLE_OLLAMA_API:-false}"
# Web research (Brandon 2026-06-22): server-side web-search grounding, keyless via DuckDuckGo,
# toggled per-message in the chat UI. EMBEDDING+RETRIEVAL is ON (bypass=false): scraped pages are
# chunked and only the RELEVANT chunks are injected (local all-MiniLM-L6-v2, already cached).
# WHY NOT bypass: bypass injects FULL pages (200 KB+/turn observed) which overflows the 64K context
# and yields an empty reply by the ~3rd web turn (the bug from chat-export-...; fixed 2026-06-22).
# (Outbound web egress -> opt-in per web-search use; the local persona stays offline.) Initial
# defaults; the admin UI can override (Settings -> Admin -> Web Search).
export ENABLE_WEB_SEARCH="${ENABLE_WEB_SEARCH:-true}"
export WEB_SEARCH_ENGINE="${WEB_SEARCH_ENGINE:-duckduckgo}"
export WEB_SEARCH_RESULT_COUNT="${WEB_SEARCH_RESULT_COUNT:-3}"
export BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL="${BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL:-false}"
# CRITICAL (2026-06-22): the actual reason web search returned "I can't browse". OpenWebUI's
# retrieval/utils.py get_sources_from_items routes by item type; a web-search result is attached as
# {type:"web_search", collection_name:...}. No branch matches "web_search", so it falls to the
# generic `elif item.get("collection_name")` which -- with BYPASS_RETRIEVAL_ACCESS_CONTROL=false
# (the DEFAULT) -- IGNORES it as an "untrusted direct collection_name on item without type". Result:
# scraped+embedded web chunks get stored but NEVER retrieved/injected, so the model gets a bare
# question and falls back to "I cannot browse the live web" (confirmed by capturing a /v1 request:
# a single bare user message, no <context>). Setting this true makes the web-search collection
# trusted -> retrieved -> injected. Safe here: the access control guards multi-user collection-name
# substitution, which does not apply to this single-user admin instance.
export BYPASS_RETRIEVAL_ACCESS_CONTROL="${BYPASS_RETRIEVAL_ACCESS_CONTROL:-true}"
# Put the retrieved web/RAG context in a SYSTEM message (not appended to the user message) so the
# persona's /v1 path captures it as authoritative grounding (server.py _v1_injected_context) while
# the persisted user turn stays clean.
export RAG_SYSTEM_CONTEXT="${RAG_SYSTEM_CONTEXT:-true}"

# WEBUI_HOST defaults to loopback (safe). Set it to a LAN address (0.0.0.0, or the host's
# 192.168.x.x) to reach the UI from another machine's browser without an SSH tunnel. OpenWebUI
# has its own account/auth (first visit = admin signup), so a LAN bind is less exposed than the
# raw persona API; still keep it to a trusted network.
WEBUI_HOST="${WEBUI_HOST:-127.0.0.1}"
WEBUI_PORT="${WEBUI_PORT:-3000}"

echo "Starting OpenWebUI on http://${WEBUI_HOST}:${WEBUI_PORT}"
echo "  OPENAI_API_BASE_URL=$OPENAI_API_BASE_URL  DATA_DIR=$DATA_DIR  web_search=$ENABLE_WEB_SEARCH/$WEB_SEARCH_ENGINE"

exec open-webui serve --host "$WEBUI_HOST" --port "$WEBUI_PORT"
