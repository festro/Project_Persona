# Handoff -- Project_Persona

Date/time: 2026-06-22 0610 PDT
Author: Claude (Claude Code on Daemonic-PC, driving EVO-X2 over SSH, with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
To resume: "continue from handoff_persona_20260622_0610.md".
Full incremental detail is in changelog.md (2026-06-21 / 06-22 entries); this consolidates the
session so the conversation can be compacted.

================================================================================
0. ORIENTATION
================================================================================

- Two machines:
  * Daemonic-PC = Windows daily-driver (RX 9060 XT, 31 GB RAM). The git gateway
    (D:\Projects\Git\Project_Persona) + Windows testbed. Portable python at portable\python\.
  * EVO-X2 (Daemonic-evox2, 192.168.8.114) = the always-on anchor node (Qwen3.6-35B-A3B on
    RADV GFX1151 Vulkan, 62 GB RAM). Driven over SSH (`ssh evox2`). Repo ~/Git/Project_Persona,
    venv env/, Hermes env_hermes/ (v0.16.0 @9b1e0d6f), OpenWebUI env_webui/. sudo = HARD-DENY.
- The stack: llama-server (:8090) + FastAPI persona API (:8000) + (Phase 8) the Hermes agent
  layer, all supervised by daemon.py (systemd --user unit persona-daemon; survives SSH/logout via
  linger, NOT reboot). OpenWebUI (:3000) runs as a separate systemd --user unit persona-webui.
- Persona name: "Daemonic". Memory/RAG = Qdrant (embedded). See knowledge.md for architecture,
  roadmap.md for phase status, the memory files (~/.claude/.../memory) for operating gotchas.

================================================================================
1. WHAT THIS SESSION DELIVERED (all PROVEN LIVE on EVO-X2, all committed + pushed)
================================================================================

PHASE 8 H3-H6 (the agentic layer) -- reconciled to the 2026-06-13 BRIDGE arch (Hermes owns
dispatch/retry; persona wires+validates, does NOT reimplement):
- H3 standing dispatcher: NEW tools/hermes_dispatch_loop.py loops the SUPPORTED `hermes kanban
  dispatch` (NOT the deprecated `kanban daemon`, NOT the messaging `gateway`). daemon.py
  hermes_dispatcher_spec + build_specs -> `manage.py daemon start --with-hermes` supervises FOUR
  children (llama/api/hermes-bridge/hermes-dispatcher). Makes the H2d chain UNATTENDED: a hands-off
  POST /agent/delegate -> bridge card -> dispatch loop spawns the 35B worker -> kanban_complete ->
  bridge mirrors ok+summary to /jobs (~100s). Also fixed the bridge log (flush=True).
- H6.2 reclaim+recovery, H6.3 failure-limit->blocked, H6.1 swarm fan-out->verifier->synthesizer:
  all PROVEN. H6.3 surfaced + fixed TWO bridge bugs in tools/hermes_bridge.py derive_update:
  settled columns (blocked/done/archived) are now authoritative over a transient run outcome
  (was mirroring auto-blocked cards as "error" and churning archived orphans at "running").
- H4 role-prefix template library: init_profiles.sh scaffolds 5 Hermes assignee profiles
  (researcher/critic/summarizer/coder/librarian); POST /agent/delegate gains a `role` param ->
  assignee -> the dispatcher spawns `hermes -p <role>`. cache_prompt defaults ON in llama.cpp.
- H5 routing: classify_triviality + topic routing + sorting_line + task-surfacing already exist
  (verified live: /chat injected the live board). H5.1 auto-delegate SUPERSEDED by the explicit
  role-delegation model.
- H6.4 cache-amortization measurement: DEFERRED (PARALLEL=1 single-slot contention + the llama
  rc=-6 instability blocked a clean read). Empirical 50-task study -> a multi-slot future.

LAN ACCESS (reach the stack from Daemonic-PC WITHOUT an SSH tunnel):
- manage.py api_argv host is now PERSONA_API_HOST (default 127.0.0.1); set "0.0.0.0" in
  run/config.daemonic-evox2.toml -> persona API at http://192.168.8.114:8000.
- OpenWebUI bound to 0.0.0.0:3000 (start_webui.sh WEBUI_HOST) -> http://192.168.8.114:3000.
- Both UNAUTHENTICATED on the LAN (OpenWebUI has its own signup). Trusted-network assumption.

OPENWEBUI (the browser chat UI, the Phase 2 choice):
- Installed open-webui (now 0.9.6) into env_webui on EVO-X2; persona-webui systemd --user unit,
  LAN-bound, wired to the persona /v1 (model id `project_persona`). Brandon signed up + chats.
- DATA_DIR fix: OpenWebUI reads DATA_DIR (not WEBUI_DATA_DIR) -- migrated the DB/accounts/chats out
  of the env_webui package dir into $AI_ROOT/openwebui (a venv rebuild would have wiped them).

WEB RESEARCH (Brandon: "give it web browsing / capabilities like you") -- BOTH paths live:
- A (in-chat): OpenWebUI server-side web search, keyless DuckDuckGo, per-message toggle in the
  chat. BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true so no embedding model is needed. Defaults
  baked into start_webui.sh.
- B (agentic, "like Claude"): the RESEARCHER role is web-enabled (web_search/web_extract/web_crawl
  on; browser_* still off -- no Chromium). PROVEN: delegate role=researcher -> the 35B worker ran a
  12-tool-call loop, web_search'd via ddgs, returned a CURRENT web-sourced answer. Keyless via the
  DuckDuckGo (ddgs) provider (Hermes supports ~7 backends; NOT locked to the paid Nous gateway).
  init_profiles.sh codifies the researcher web-enable (idempotent) + a .hermes.md "web is optional"
  note. Needs `ddgs` in env_hermes.

STACK UPDATE SWEEP (Python excluded): OpenWebUI -> 0.9.6 (done). Hermes (1501 commits behind),
llama.cpp (build 45b455e), and the API env deps (chromadb/hf_hub/fastapi/...) all FLAGGED but NOT
updated -- the agent layer + API stack are validated against the current pins; major jumps are
breaking. See section 4.

================================================================================
2. CURRENT LIVE STATE (EVO-X2)
================================================================================

- persona-daemon (systemd --user) supervising: llama-server :8090, api :8000, hermes-bridge,
  hermes-dispatcher. Started with `manage.py daemon start --with-hermes`. PARALLEL=1 (the Hermes
  64K ctx floor is real; one big worker slot over serving concurrency).
- persona-webui (systemd --user): OpenWebUI 0.9.6 on 0.0.0.0:3000, DATA_DIR=$AI_ROOT/openwebui,
  ENABLE_WEB_SEARCH=true/duckduckgo, ENABLE_OLLAMA_API=false.
- Reachable from Daemonic-PC: API http://192.168.8.114:8000 (OpenAI-compatible /v1, model
  `project_persona`); UI http://192.168.8.114:3000.
- Roles available (delegate via POST /agent/delegate {"role": "..."}): researcher (web-enabled),
  critic, summarizer, coder, librarian. Default assignee = "default" (local).
- Board/jobs are clean (H2d/H6 test cards archived; orphans resolved).

================================================================================
3. KEY FINDINGS / ISSUES
================================================================================

- LLAMA rc=-6 (SIGABRT) -- a llama.cpp prompt-cache bug, NOT memory. Fires ONLY on a fully-cached,
  EXACTLY-identical prompt (slot LCP sim=1.000 -> n_past backed off 1 -> common.cpp:1489 seq_rm
  abort). Normal multi-turn chat never repeats an exact prompt, so it does NOT trigger in normal
  use; the rare hit (a worker/sleep-cycle/health re-issue) is auto-recovered by the supervisor
  (~10s). `--swa-full` is a NO-OP on this model (unsupported). See memory evox2-llama-rc6-
  instability. DECISION: Option A (keep caching; tolerate the rare recovered crash). Option C
  (update llama.cpp past the seq_rm fix) left on the table.
- ddgs is SEARCH-ONLY (snippets + URLs, no deep page-content scrape). Fine for most research;
  deep page-reading would need a scraper or the browser toolset + Chromium (a follow-up).
- EGRESS is now ROLE-SCOPED, not blanket: the researcher worker has outbound DuckDuckGo; the local
  persona chat + every other role stay offline. The KERNEL egress baseline (scripts/egress_
  baseline.sh) is still owed (needs root; sudo hard-denied to the agent).
- The persona API + OpenWebUI are UNAUTHENTICATED on the LAN bind (trusted-network assumption).
- Hermes worker shells run with a CLEAN PATH -> handled by run/hermes_shell_init.sh on the worker
  shell PATH (the H2d fix). Persistence = systemd --user transient units (survive disconnect, NOT
  reboot).

================================================================================
4. DECISIONS (this session)
================================================================================

- Phase 8 H3-H6 = wire+supervise+validate Hermes-native (the bridge decision's conclusion), not
  reimplement. Dispatcher = loop the supported `dispatch` (not deprecated `kanban daemon`/gateway).
- llama rc=-6: Option A (keep prompt caching). C on the table.
- Web research: enable BOTH paths. Web scoped to the researcher role (web-enabled but NOT required
  to function) + the OpenWebUI chat toggle; everything else stays offline.
- OpenWebUI hosted on EVO-X2 (LAN), not on Daemonic-PC (no Docker there).
- Stack updates: OpenWebUI yes (0.9.6); Hermes/llama.cpp/API-deps no (validated pins; Python
  excluded per Brandon).

================================================================================
5. OPEN ITEMS / FOLLOW-UPS
================================================================================

- KERNEL egress baseline (scripts/egress_baseline.sh) live-applied on EVO-X2 (root; Brandon).
- llama rc=-6 Option C (llama.cpp rebuild) if the crash ever becomes a nuisance (heavy + re-validate).
- H6.4 empirical cache hit-rate study on a multi-slot / role-batched config.
- Deep web page-scrape for the researcher (a scraper or browser toolset + Chromium via
  `hermes tools post-setup`).
- Persona-surfaced swarm (POST /agent/delegate -> bridge builds a swarm graph + mirrors the
  synthesizer) -- a bridge feature; swarm cards currently have no /jobs row.
- Reboot-survival: persistent ~/.config/systemd/user/{persona-daemon,persona-webui}.service units
  (the transient units survive disconnect but not reboot).
- Hermes is 1501 commits behind upstream -- a deliberate re-validation if/when wanted.
- API env deps outdated -- update deliberately only if a specific need arises.

================================================================================
6. HOW TO OPERATE
================================================================================

- Stack up/status:    ssh evox2 'cd ~/Git/Project_Persona && env/bin/python manage.py daemon
                      start --with-hermes'  (status: ... daemon status)
- OpenWebUI:          systemctl --user {start,stop,restart,status} persona-webui  (logs/webui.log)
- Chat (any OpenAI client): http://192.168.8.114:8000/v1  model=project_persona  key=anything
- Delegate background work: POST http://192.168.8.114:8000/agent/delegate
                      {"role":"researcher","title":"...","body":"... self-contained ..."}
                      watch: GET /jobs/<id>  | board: GET /tasks
- In-chat web research: toggle the web/globe icon in OpenWebUI per message.
- Agentic web research: delegate role=researcher (it searches the web when current facts help).
- Trackers (update before any commit): roadmap.md + changelog.md + todo.md. Commit from the
  D:\ gateway; EVO-X2 pulls. ASCII only (WORKFLOW.md).
