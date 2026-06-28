# Handoff -- Project_Persona

Date/time: 2026-06-28 0030 PDT
Author: Claude (Claude Code on Daemonic-PC, driving EVO-X2 over SSH, with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
To resume: "continue from handoff_persona_20260628_0030.md".
Full incremental detail is in changelog.md (2026-06-22 + 2026-06-27 + 2026-06-28 entries); this
consolidates the session so the conversation can be compacted. Prior handoff:
handoff_persona_20260622_0610.md.

================================================================================
0. ORIENTATION
================================================================================

- Two machines:
  * Daemonic-PC = Windows daily-driver. The git GATEWAY (D:\Projects\Git\Project_Persona) +
    Windows testbed. Portable python at portable\python\python.exe (HAS the full deps -- runs the
    offline suite + py_compile). EDIT HERE, commit, push; EVO-X2 pulls.
  * EVO-X2 (Daemonic-evox2, 192.168.8.114) = the always-on anchor (Qwen3.6-35B-A3B on RADV
    GFX1151 Vulkan). Driven over SSH (`ssh evox2`). Repo ~/Git/Project_Persona; venvs env/
    (persona API), env_hermes/ (Hermes v0.16.0), env_webui/ (OpenWebUI 0.9.6). sudo = HARD-DENY.
- Stack: llama-server (:8090) + FastAPI persona API (:8000) + Hermes agent layer, all supervised
  by daemon.py (systemd --user unit persona-daemon, started `--with-hermes`). OpenWebUI (:3000)
  is a SEPARATE systemd --user unit persona-webui, LAN-bound (WEBUI_HOST=0.0.0.0). BOTH are
  TRANSIENT systemd-run units: they survive SSH disconnect/logout (linger=yes) but NOT a reboot.
- Persona name "Daemonic". Memory/RAG = Qdrant (embedded, persona side). knowledge.md =
  architecture, roadmap.md = phase status, ~/.claude/.../memory = operating gotchas.
- Git: D:\, origin/main, and EVO-X2 are all at HEAD = 81a9c85 (this session's last commit).

================================================================================
1. WHAT THIS SESSION DELIVERED (all committed + pushed + deployed + verified live)
================================================================================

THE WEB-SEARCH SAGA -- OpenWebUI in-chat web search now WORKS end to end. It was FOUR stacked
bugs, each hiding the next (changelog 2026-06-22 0640/0725/0815/1850):
  1) (0640) BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true injected FULL pages -> 64K overflow.
     Fix: bypass=false (chunk + retrieve top-k).
  2) (0725) conversations.db POISON: full pages (injected while bypass was true) were persisted as
     giant user turns, and windowing.window_turns honored HISTORY_MIN_RECENT=4 with NO ceiling, so
     ~110K tokens of baked pages were dragged into every request -> overflow -> bare 500. Fix:
     window_turns max_turn_tokens(=1024)/hard_cap_tokens(=8192) caps (poisoned threads auto-recover)
     + a graceful ContextOverflowError -> 400 context_length_exceeded + the global handler now logs.
  3) (0815) the persona /v1 path DROPPED OpenWebUI's <context> system message (it owns its identity
     prompt). Fix: server.py _v1_injected_context extracts the <context> payload -> persona_generate
     external_context, grounded as authoritative.
  4) (1850) THE DECISIVE ONE: OpenWebUI's retrieval/utils.py get_sources_from_items routes attached
     items by `type`; a web-search result is {type:"web_search", collection_name:...}. No branch
     matches "web_search", so it falls to a generic `elif item.get("collection_name")` that IGNORES
     it as an "untrusted direct collection_name on item without type" UNLESS
     BYPASS_RETRIEVAL_ACCESS_CONTROL=true (default false). So chunks were stored but never injected
     -> model got a bare question -> "I cannot browse the live web". Fix (start_webui.sh):
     BYPASS_RETRIEVAL_ACCESS_CONTROL=true (safe single-user admin box) + RAG_SYSTEM_CONTEXT=true
     (context -> system message, where _v1_injected_context grabs it).

ADAPTIVE OUTPUT FORMAT (1850/f4ce197) -- Brandon: "doesn't follow instructions". The rigid "always
1 paragraph + Next actions" came from BOTH persona/profiles/default/SOUL.md ("Always answer with...")
AND server.py build_persona_prompt/messages ("Output exactly TWO parts"). Both reworded to a DEFAULT
that DEFERS to an explicit per-message format/length request (bullets, tables, pros/cons, long-form,
"no next actions"). Verified: a Pros/Cons-bullets request was honored, no forced Next-actions.

WEB-SEARCH TUNING (2026-06-27 5df74ae) -- a "latest news" query drew generic evergreen SEO pages
(content quality, NOT a bug -- the model honestly declined to fabricate). Changes (start_webui.sh):
WEB_SEARCH_RESULT_COUNT 3->5, RAG_TOP_K 3->6 (deeper retrieval); DEFAULT-ON / CONTEXT-BASED web
search via PERSONA_WEB_SEARCH_DEFAULT=1 + an idempotent one-line OpenWebUI patch -> the
ENABLE_SEARCH_QUERY_GENERATION necessity check runs each turn and SEARCHES ONLY when the question
needs current info (=0 reverts; trade-off = +1 35B task-model call/msg, ~8s). server.py: a
helpfulness nudge (summarize thin/generic results, do not refuse outright).

AUTOMATED DEBUG LOOP (2026-06-28 81a9c85) -- see section 2. THE headline deliverable: the stack can
now be smoke-tested end to end over SSH, no browser.

================================================================================
2. THE AUTOMATED DEBUG LOOP -- tools/webui_probe.py  (USE THIS to continue debugging)
================================================================================

WHY: the persona API (:8000) can be hit directly, but that BYPASSES OpenWebUI, so it can't exercise
web search. tools/webui_probe.py drives OpenWebUI's /api/chat/completions (:3000) so the WHOLE
pipeline runs (web-search necessity check -> search -> scrape -> embed -> retrieve -> inject ->
persona -> reply). It mints the same HS256 JWT the browser uses, signed with the gitignored
~/Git/Project_Persona/.webui_secret_key (read at runtime, never committed/printed; ENABLE_API_KEYS
is off so JWT is the path). User id auto-detected from openwebui/webui.db. Run with the WEBUI venv
(it has PyJWT).

  ssh evox2 'cd ~/Git/Project_Persona && env_webui/bin/python tools/webui_probe.py --web \
    --expect-sources "what did Anthropic announce recently?"'

Flags: --web / --no-web (force the toggle; omit = let the server default decide), --expect-sources,
--expect-contains TEXT, --expect-absent TEXT (assertions -> exit 0 pass / 1 fail), --json, --model.

VALIDATION RUN at handoff (all 4/4 OK):
  [1] --web "latest AI model releases this week"   -> sources=1, 35s, real facts (Opus 4.8, Mythos)
  [2] --no-web "structure my workday"              -> 9s, kept "Next actions" (default style)
  [3] --no-web "6 focus tips, numbered, no NA"     -> 10s, clean numbered list, NO Next actions
  [4] (no flag) "what is a hash map" (casual)      -> 17s, sources=0 (necessity check SKIPPED search)

So: web search grounds, default format holds, explicit format overrides win, context-based
auto-search skips casual turns. The ~17s vs ~9s on [4] is the necessity-check overhead (expected).

================================================================================
3. CURRENT LIVE STATE (EVO-X2)
================================================================================

- persona-daemon (systemd --user, --with-hermes): ACTIVE. Supervises llama:8090 + api:8000 +
  hermes-bridge + hermes-dispatcher. `ssh evox2 'cd ~/Git/Project_Persona && env/bin/python
  manage.py daemon status'`.
- persona-webui (systemd --user transient): ACTIVE on :3000, WEBUI_HOST=0.0.0.0 (reachable at
  http://192.168.8.114:3000 from Daemonic-PC). Logs -> logs/webui.log.
- Git EVO-X2 = 81a9c85. UNCOMMITTED there (Brandon's, PRESERVE -- do NOT git checkout/clobber):
  persona/README.md, persona/profiles/default/config.yaml (shell_init_files PATH fix). UNTRACKED
  there (only on EVO-X2, NOT in git/D:\): persona/profiles/{coder,critic,librarian,researcher,
  summarizer}/, persona/skills/, persona/SOUL.md (root), persona/bin/, persona/state.db, openwebui/.
- NOTE on deploy hygiene: this session scp'd debug builds to EVO-X2 mid-debug, then restored with
  `git checkout services/api/server.py scripts/start_webui.sh` before pulling. Those two files are
  now clean (committed versions). If you ever scp again, restore the same way before pulling.

================================================================================
4. WHERE THE FIXES LIVE (the knobs)
================================================================================

scripts/start_webui.sh (OpenWebUI env + the idempotent web-search-default patch):
  ENABLE_WEB_SEARCH=true, WEB_SEARCH_ENGINE=duckduckgo, WEB_SEARCH_RESULT_COUNT=5,
  BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=false, BYPASS_RETRIEVAL_ACCESS_CONTROL=true,
  RAG_SYSTEM_CONTEXT=true, RAG_TOP_K=6, PERSONA_WEB_SEARCH_DEFAULT=1. The patch block (before
  `exec open-webui serve`) injects one line into open_webui/utils/middleware.py to default
  features.web_search from PERSONA_WEB_SEARCH_DEFAULT; it is idempotent (marker comment),
  safe-failing (no-ops if the anchor line moves on a pip upgrade), re-applied each webui start.
services/api/server.py: window_turns caps wiring; ContextOverflowError + _raise_for_llama_error +
  the context-overflow 400 handler + the logging unhandled handler; _v1_injected_context +
  external_context threaded through persona_generate/build_persona_prompt/build_persona_messages
  (with the authoritative-grounding + helpfulness-nudge text); the adaptive "Output format" block
  in both builders. (PERSONA_USE_MESSAGES=1 is the default -> the lossy sanitizer is OFF, so the
  system prompt is the only format lever.)
services/api/windowing.py: window_turns max_turn_tokens / hard_cap_tokens + _truncate_turn.
persona/profiles/default/SOUL.md: adaptive "By default... but follow explicit requests".
tools/webui_probe.py: the headless smoke harness (section 2).
Tests: tests/test_windowing.py (+ caps regression), tests/test_v1_history.py (+ _v1_injected_context
  + grounding). Offline suite 18/18 (run: portable\python\python.exe tests/run_all_offline.py on
  Windows, or env/bin/python tests/run_all_offline.py on EVO-X2).

================================================================================
5. OUTSTANDING / NEXT  (CONTINUE THE DEBUG LOOP)
================================================================================

CONTINUE: keep using tools/webui_probe.py to exercise scenarios and validate. Good next probes:
  - multi-turn web (does grounding hold across a follow-up; the harness is single-turn today --
    extending it to accept a --messages JSON / a second turn would test the windowing path live);
  - more format overrides (table, JSON, markdown headings, "one word answer");
  - a few current-info topics to gauge keyless-DDG quality variance;
  - confirm context-based gating: casual prompts -> sources=0, current prompts -> sources>0.
OPEN ITEMS (Brandon's call):
  - REBOOT-SURVIVAL (raised, not done): the transient units die on reboot (the stack was DOWN after
    a ~02:09 reboot this session; restarted manually). Persistent ~/.config/systemd/user/
    persona-daemon.service + persona-webui.service (enabled) would auto-start after reboot. Needs
    files OUTSIDE the project dir. Offered; awaiting go.
  - WEB-SEARCH CONTENT QUALITY for breaking news: keyless DuckDuckGo is hit-or-miss (ranks evergreen
    SEO content; no recency filter). Deeper retrieval helped; for serious research the agentic
    `researcher` role (path B, POST /agent/delegate {"role":"researcher"}) digs further.
  - UNTRACKED PERSONA PROFILES on EVO-X2 (coder/critic/librarian/researcher/summarizer + skills/)
    are NOT in git -> not backed up. Decide whether to commit them.
  - PERSONA_WEB_SEARCH_DEFAULT trade-off: +1 task-model call (~8s) per message. =0 reverts to manual
    toggle if the latency annoys.
  - Older owed items (pre-this-session): kernel egress baseline (scripts/egress_baseline.sh, root,
    Brandon); the EVO-X2 35B/Vulkan llama rc=-6 instability (supervisor auto-recovers; root-cause
    owed); H6.4 cache study on a multi-slot config.

================================================================================
6. OPERATING EVO-X2 OVER SSH  (+ reboot recovery)
================================================================================

- Health:   ssh evox2 'cd ~/Git/Project_Persona && env/bin/python manage.py daemon status'
            ssh evox2 'curl -s -o /dev/null -w "api:%{http_code} llama:%{http_code}\n" \
              http://127.0.0.1:8000/health -o /dev/null; curl ... :8090/health' (api+llama 200)
- Restart persona stack:  ssh evox2 'systemctl --user restart persona-daemon'  (llama reload ~secs)
- Restart OpenWebUI:      ssh evox2 'systemctl --user restart persona-webui'   (re-applies the patch)
- AFTER A REBOOT (both units gone -- transient, linger only covers logout): bring them back with
    ssh evox2 'cd ~/Git/Project_Persona && env/bin/python manage.py daemon start --with-hermes'
    ssh evox2 'cd ~/Git/Project_Persona && systemd-run --user --unit=persona-webui --collect \
      --working-directory=$HOME/Git/Project_Persona --setenv=AI_ROOT=$HOME/Git/Project_Persona \
      --setenv=WEBUI_HOST=0.0.0.0 bash -c "exec bash scripts/start_webui.sh > logs/webui.log 2>&1"'
- Logs: logs/webui.log (OpenWebUI -- web-search activity, "added N items to collection", any
  "Error processing chat payload"); logs/persona.log (llama-server, UPTIME-relative timestamps,
  watch for "exceeds the available context size"); logs/daemon.log (supervisor); logs/api.log.
- Deploy a change: edit on D:\ -> portable\python\python.exe -m py_compile + tests/run_all_offline.py
  -> commit (update changelog+todo+roadmap first) -> push -> ssh evox2 git pull --ff-only ->
  restart the relevant unit. Brandon's workflow rule: trackers updated BEFORE the commit.

================================================================================
7. ONE-LINER RESUME CHECK
================================================================================

  ssh evox2 'cd ~/Git/Project_Persona && env/bin/python manage.py daemon status && \
    curl -s -o /dev/null -w "webui:%{http_code}\n" http://127.0.0.1:3000/ && \
    env_webui/bin/python tools/webui_probe.py --no-web --expect-contains "Next actions" \
      "give me one productivity tip"'

Expect: daemon ACTIVE (llama+api up), webui:200, and the probe prints validation OK -> the whole
stack + the automated loop are live. Then continue from section 5 (CONTINUE THE DEBUG LOOP).
