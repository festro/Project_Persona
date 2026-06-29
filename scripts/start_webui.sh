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
export WEB_SEARCH_RESULT_COUNT="${WEB_SEARCH_RESULT_COUNT:-5}"
# RAG_TOP_K = OpenWebUI's retrieval depth (how many chunks of the scraped+embedded pages get
# injected). Default 3 was too few for web search -- a page splits into 100s of chunks, so top-3
# often missed the substantive ones and surfaced nav/boilerplate (Brandon hit a "generic AI-trends
# SEO page" result 2026-06-27). 6 gives the model more to work with; small chunks (~250 tok) keep
# it well within context.
export RAG_TOP_K="${RAG_TOP_K:-6}"
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
# Context-based web search (Brandon 2026-06-27): default the per-message web_search toggle ON so
# OpenWebUI's ENABLE_SEARCH_QUERY_GENERATION necessity check runs every turn and SEARCHES ONLY
# when the question needs current info (it returns no queries otherwise -> no search, normal reply).
# Set PERSONA_WEB_SEARCH_DEFAULT=0 to revert to manual-toggle-only. Trade-off: the necessity check
# is one extra task-model (35B) call per message (~a few seconds) -- the cost of auto-deciding.
export PERSONA_WEB_SEARCH_DEFAULT="${PERSONA_WEB_SEARCH_DEFAULT:-1}"

# Necessity-check tuning (Brandon 2026-06-28): OpenWebUI's stock QUERY_GENERATION_PROMPT_TEMPLATE is
# search-biased ("prioritize generating queries", "err on the side of suggesting... if there is ANY
# chance"), so general-knowledge turns ("explain how a hash map works") fired keyword searches that
# then FAILED under keyless-engine rate-limiting -- wasted latency + log noise. This override flips
# the bias: search ONLY when the answer needs current/external/hard-to-recall facts; for concepts,
# definitions, math, coding, reasoning -> return {"queries": []} (no search). Keeps the JSON contract
# + the {{CURRENT_DATE}}/{{MESSAGES:END:6}} placeholders. Empty value reverts to OpenWebUI's default.
if [ -z "${QUERY_GENERATION_PROMPT_TEMPLATE:-}" ]; then
  export QUERY_GENERATION_PROMPT_TEMPLATE
  QUERY_GENERATION_PROMPT_TEMPLATE="$(cat <<'EOF'
### Task:
Decide whether answering the user's latest message needs a web search, then return search queries in the given language. Search ONLY when the answer depends on CURRENT, EXTERNAL, or hard-to-recall FACTUAL information -- recent events or news, today's prices/weather/scores, release notes or version numbers, a specific named website/repo/product/company/person, or niche documentation the model would not know reliably. For general knowledge, concepts, definitions, explanations, math, logic, coding, writing, or anything answerable well from training, do NOT search.

### Guidelines:
- Respond EXCLUSIVELY with a JSON object. No commentary, explanation, or extra text.
- If a search is warranted, respond as { "queries": ["query1", "query2"] } with 1-3 distinct queries. Each query MUST be a SHORT keyword phrase (under ~12 words). NEVER copy or echo sentences, paragraphs, or a prior reply from the conversation as a query.
- If no search is warranted (general knowledge / reasoning, or the needed facts are already in the chat history), return { "queries": [] }.
- When in doubt on a general or conceptual question, prefer { "queries": [] } -- do NOT search "just in case".
- INTROSPECTIVE / SELF-REFERENTIAL questions return { "queries": [] }: anything about THIS assistant itself -- its own memory, RAG, architecture, design, capabilities, or earlier answers/proposals -- or a request to re-check, refresh, reconsider, or confirm something already discussed in this conversation. These are answered from internal memory + chat context, NOT the web (a web search would pull in unrelated look-alike projects).
- Today's date is: {{CURRENT_DATE}}.

### Output:
Strictly return in JSON format:
{
  "queries": ["query1", "query2"]
}

### Chat History (most recent turns; decide from the LATEST user message):
<chat_history>
{{MESSAGES:END:3}}
</chat_history>
EOF
)"
fi

# WEBUI_HOST defaults to loopback (safe). Set it to a LAN address (0.0.0.0, or the host's
# 192.168.x.x) to reach the UI from another machine's browser without an SSH tunnel. OpenWebUI
# has its own account/auth (first visit = admin signup), so a LAN bind is less exposed than the
# raw persona API; still keep it to a trusted network.
WEBUI_HOST="${WEBUI_HOST:-127.0.0.1}"
WEBUI_PORT="${WEBUI_PORT:-3000}"

# Idempotently teach OpenWebUI to honor PERSONA_WEB_SEARCH_DEFAULT. OpenWebUI gates web search on
# the per-message form_data.features.web_search with NO server-side default. The browser sends that
# flag EXPLICITLY as a bool (web_search:false when the chat toggle is off), so a setdefault() never
# takes effect -- the box only searched when the toggle was on. We instead OR the user's flag with
# the env default: when PERSONA_WEB_SEARCH_DEFAULT=1 web search is always ON and the per-turn
# ENABLE_SEARCH_QUERY_GENERATION necessity check decides whether to actually search (so casual turns
# still don't); =0 reverts to honoring the manual toggle. Self-healing: if a prior version of this
# line is present (the old setdefault) it is REPLACED, so an upgrade re-applies cleanly. Safe-failing:
# if the anchor moves on a pip upgrade the patch no-ops and the manual toggle is unchanged.
python - <<'PYPATCH'
import os
NEW = ("features['web_search'] = bool(features.get('web_search')) or "
       "os.getenv('PERSONA_WEB_SEARCH_DEFAULT', '1') == '1'  "
       "# PROJECT_PERSONA: default web search (context-based via ENABLE_SEARCH_QUERY_GENERATION)")
MARKER = "PROJECT_PERSONA: default web search"
try:
    import open_webui
    mw = os.path.join(os.path.dirname(open_webui.__file__), "utils", "middleware.py")
    src = open(mw, encoding="utf-8").read()
    lines = src.splitlines(keepends=True)
    prior = next((i for i, l in enumerate(lines) if MARKER in l), None)
    if prior is not None:
        if lines[prior].strip() == NEW:
            print("[start_webui] web-search default: already patched (current)")
        else:
            indent = lines[prior][: len(lines[prior]) - len(lines[prior].lstrip())]
            lines[prior] = indent + NEW + "\n"
            open(mw, "w", encoding="utf-8").write("".join(lines))
            print("[start_webui] web-search default: patch UPDATED (replaced prior version)")
    else:
        for i, l in enumerate(lines):
            if l.strip() == "features = form_data.pop('features', None) or {}":
                indent = l[: len(l) - len(l.lstrip())]
                lines.insert(i + 1, indent + NEW + "\n")
                open(mw, "w", encoding="utf-8").write("".join(lines))
                print("[start_webui] web-search default: PATCHED (env PERSONA_WEB_SEARCH_DEFAULT)")
                break
        else:
            print("[start_webui] web-search default: anchor not found; manual toggle unchanged")
except Exception as e:
    print("[start_webui] web-search default: patch skipped:", e)
PYPATCH

# Inline-URL fetch (Brandon 2026-06-28): when the user pastes a link, READ that page
# instead of letting web_search paraphrase it into keyword queries (which landed on
# lookalike repos). Two idempotent steps: (1) copy the helper module into open_webui/utils
# so the import resolves; (2) insert a marker-guarded call into middleware.py just before
# the web_search dispatch -- if links are fetched it flips features.web_search off so the
# keyword search is skipped for that turn. Safe-failing: the call is wrapped in try/except.
AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}" PERSONA_SRC="$AI_ROOT/scripts/webui_patches/persona_inline_urls.py" \
python - <<'PYPATCH2'
import os, shutil
try:
    import open_webui
    utils_dir = os.path.join(os.path.dirname(open_webui.__file__), "utils")
    src = os.environ["PERSONA_SRC"]
    dst = os.path.join(utils_dir, "persona_inline_urls.py")
    shutil.copyfile(src, dst)  # redeploy each start so helper updates land
    print("[start_webui] inline-url: helper module copied")

    mw = os.path.join(utils_dir, "middleware.py")
    txt = open(mw, encoding="utf-8").read()
    if "PROJECT_PERSONA: fetch inline URLs" in txt:
        print("[start_webui] inline-url: middleware already patched")
    else:
        lines = txt.splitlines(keepends=True)
        anchor = "if 'web_search' in features and features['web_search']:"
        for i, l in enumerate(lines):
            if l.strip() == anchor:
                ind = l[: len(l) - len(l.lstrip())]
                block = [
                    "# PROJECT_PERSONA: fetch inline URLs directly (read pasted links, don't keyword-search them)",
                    "if features.get('web_search') and metadata.get('params', {}).get('function_calling') != 'native':",
                    "    try:",
                    "        from open_webui.utils.persona_inline_urls import fetch_inline_urls as _persona_fetch_inline_urls",
                    "        if await _persona_fetch_inline_urls(request, form_data, extra_params, user):",
                    "            features['web_search'] = False  # links fetched; skip the keyword search this turn",
                    "    except Exception as _persona_e:",
                    "        log.warning('persona inline-url hook failed: %s', _persona_e)",
                ]
                lines.insert(i, "".join(ind + b + "\n" for b in block))
                open(mw, "w", encoding="utf-8").write("".join(lines))
                print("[start_webui] inline-url: middleware PATCHED")
                break
        else:
            print("[start_webui] inline-url: anchor not found; pasted links unchanged")
except Exception as e:
    print("[start_webui] inline-url: patch skipped:", e)
PYPATCH2

echo "Starting OpenWebUI on http://${WEBUI_HOST}:${WEBUI_PORT}"
echo "  OPENAI_API_BASE_URL=$OPENAI_API_BASE_URL  DATA_DIR=$DATA_DIR  web_search=$ENABLE_WEB_SEARCH/$WEB_SEARCH_ENGINE  web_search_default=$PERSONA_WEB_SEARCH_DEFAULT"

exec open-webui serve --host "$WEBUI_HOST" --port "$WEBUI_PORT"
