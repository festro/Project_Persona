# Handoff -- Project_Persona

Date/time: 2026-06-29 0125 PDT
Author: Claude (Claude Code on Daemonic-PC, driving EVO-X2 over SSH, with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
To resume: "continue from handoff_persona_20260629_0125.md".
NEXT SESSION PRIORITY (Brandon): proposal C HARD containment -- a sandboxed/restricted shell for
Hermes workers (see section 5). Full incremental detail in changelog.md (2026-06-28 + 2026-06-29
entries). Prior handoff: handoff_persona_20260628_0030.md.

================================================================================
0. ORIENTATION
================================================================================

- Two machines:
  * Daemonic-PC = Windows daily-driver. The git GATEWAY (D:\Projects\Git\Project_Persona) +
    Windows testbed. Portable python at portable\python\python.exe (full deps -- runs the offline
    suite + py_compile). EDIT HERE, commit, push; EVO-X2 pulls.
  * EVO-X2 (Daemonic-evox2, 192.168.8.114, user festro33) = the always-on anchor (Qwen3.6-35B-A3B,
    UD Q5_K_XL, on RADV GFX1151 Vulkan). Driven over SSH (`ssh evox2`). Repo ~/Git/Project_Persona;
    venvs env/ (persona API), env_hermes/ (Hermes v0.16.0), env_webui/ (OpenWebUI 0.9.6).
    sudo = HARD-DENY. AI_ROOT resolves to the repo at runtime (self-ingest read repo docs fine).
- Stack: llama-server (:8090) + FastAPI persona API (:8000) + Hermes agent layer, supervised by
  daemon.py (systemd --user unit persona-daemon, --with-hermes). OpenWebUI (:3000) = a SEPARATE
  systemd --user unit persona-webui, LAN-bound. BOTH are now PERSISTENT enabled units (reboot-survive).
- Persona name "Daemonic". Memory/RAG = Qdrant (embedded). knowledge.md = architecture, roadmap.md =
  phase status, ~/.claude/.../memory = operating gotchas.
- Git: D:\, origin/main, and EVO-X2 are all at HEAD = c4f4d02. Offline suite 23/23.

================================================================================
1. WHAT THIS SESSION DELIVERED (all committed + pushed + deployed + verified)
================================================================================

REBOOT SURVIVAL -> AUTOMATIC (changelog 0045). Replaced the transient systemd-run units with
PERSISTENT ~/.config/systemd/user/{persona-daemon,persona-webui}.service, enabled to default.target
(+ linger=yes). PROVEN by an actual reboot: new boot id, stack auto-up, end-to-end probe OK. Reference
copies + install steps in scripts/systemd/; doc host_onboarding.md section 9. Cutover gotcha: a running
transient unit shadows the on-disk file -> stop it BEFORE enable.

WEB-SEARCH / CHAT FIXES:
- FIX (0115): context-based web search never auto-fired from the BROWSER. setdefault('web_search',..)
  is a no-op because the browser sends web_search:false EXPLICITLY. Now ORs the flag with the env
  default; the patch self-heals (replaces a prior version). scripts/start_webui.sh.
- INLINE-URL FETCH (0200): pasted links were paraphrased into keyword searches (-> lookalike repos),
  never visited. NEW scripts/webui_patches/persona_inline_urls.py + a marker-guarded middleware hook
  fetch URLs in the latest user message via OpenWebUI /process/web and skip the keyword search that
  turn. tests/test_inline_urls.py.
- FULLER RESPONSES (0200): default was "1 short paragraph". SOUL.md + both server.py prompt builders
  now default to a thorough answer (still deferring to explicit brevity/format). PERSONA_MAX_TOKENS
  192->800.
- NECESSITY-CHECK TUNED (0240): stock query-gen prompt was search-biased -> failed searches on
  general-knowledge turns. start_webui.sh exports a less-eager QUERY_GENERATION_PROMPT_TEMPLATE
  (search only for current/external facts; introspective/self-referential -> no search; short keyword
  queries, never echo conversation text; MESSAGES window 6->3).

SELF-AWARENESS / ANTI-SYCOPHANCY (the "doubling-down" saga -- root-caused + fixed):
- SELF-KNOWLEDGE IN RAG (0320): NEW services/api/self_knowledge.py chunks the project's own docs
  (knowledge.md, roadmap.md, host_onboarding.md, ...) into heading-scoped breadcrumbed chunks stored
  under kind=project_doc (added to RAG_KINDS_FOR_CHAT/SCIENCE; vector-gated). POST /memory/ingest_self
  (idempotent purge+reingest). The persona now cites its real stack.
- ECHO CHAMBER root cause (0430/0520): the per-turn distiller AND the sleep cycle were storing the
  ASSISTANT's own IBOS proposals as USER facts ("user wants/proposed Doctrine Cards...") -> retrieved
  -> model "defended the user's goals". FIX: DISTILL_PROMPT provenance section (only user-stated facts;
  covers [assistant] lines in a transcript, so both paths). 22 fabricated facts PURGED (reversible
  backups in archive/memory_backups/) via NEW POST /memory/facts + POST /memory/forget. Also fixed a
  DELETE bug: sleep_cycle ids are ints (uuid4().hex hashed), distiller ids are uuid strings;
  /memory/facts stringified ints so delete didn't match -- now native id round-trip + real deleted count.
- ALWAYS-ON SELF-IDENTITY (0545): RAG self-knowledge is similarity-gated (oblique self-questions
  missed it). NEW SELF_IDENTITY.md (repo root) is injected into EVERY system prompt (both builders),
  like SOUL.md for personality. tests/test_self_identity.py. PROVEN: oblique "which IBOS features do
  you already have" now grounded.
- ANTI-SYCOPHANCY (0610): a continued thread still doubled down (essay in history + leading question).
  Both builders gained an intellectual-honesty rule (genuinely reconsider; don't defend a prior answer;
  name what you ALREADY have; accuracy over agreement). VERIFIED via a /v1 multi-turn replay: persona
  now says "my previous assertion was too broad", lists what it has vs the real gap.

THE PERSONA'S OWN PROPOSALS, evaluated + acted on (A/B/C/D):
- A (0645) MEMORY CONTRADICTION RESOLUTION: structured intake now SUPERSEDES stale facts, not just
  surfaces them. ragstore.query_detailed (id+text, both stores); memory_intake.build_conflict_prompt/
  parse_conflict; structured_intake pulls K=5 nearest kind=fact candidates, asks the model which the
  new fact supersedes, DELETES those, stores new. MEMORY_INTAKE_RESOLVE_CONFLICTS=0 reverts. VERIFIED:
  "I now prefer light mode" superseded "prefers dark mode".
- B: DEFERRED (Git-backed canon/ markdown -- overlaps insight_journal.md + git-tracked SOUL.md; low ROI).
- C (06-29) SOFT SCOPE CONTRACTS: HARD containment NOT feasible (see section 5). Delivered the soft
  layer: scripts/apply_scope_contracts.sh idempotently appends a per-role operating-boundary block to
  each .hermes.md (wired into init_profiles.sh). Applied to all 7 EVO-X2 profiles.
- D (06-29) MEMORY HYGIENE SWEEP: NEW services/api/memory_hygiene.py (cosine + cluster_duplicates keep-
  newest + find_orphans). POST /memory/hygiene (dry-run default; ?apply=true). Auto-runs after the idle
  sleep cycle adds facts (MEMORY_HYGIENE_ENABLED, thr 0.97). VERIFIED: removed 26 accumulated dup facts
  (98->72), re-scan clean. Complements A (A = clean at write; D = clean the backlog).

================================================================================
2. CURRENT LIVE STATE (EVO-X2)
================================================================================

- persona-daemon (persistent, --with-hermes): ACTIVE. llama:8090 + api:8000 up. webui:3000 up.
  All health 200. global_memory ~242 points (72 facts + ~161 project_doc), insight_journal 21.
- Git D:\ = origin/main = EVO-X2 = c4f4d02.
- EVO-X2 UNCOMMITTED (Brandon's, PRESERVE -- do NOT clobber): persona/README.md,
  persona/profiles/default/config.yaml. UNTRACKED on EVO-X2 (only there): persona/profiles/{coder,
  critic,librarian,researcher,summarizer,test}/ (their SOUL.md/.hermes.md/config.yaml -- NOW carry the
  scope-contract block appended live by apply_scope_contracts.sh), persona/skills/, persona/SOUL.md
  (root), persona/bin/, persona/state.db, openwebui/. These are NOT in git -> not backed up.
- The OpenWebUI middleware patches (web-search default, inline-url, query-gen template) are re-applied
  on every `systemctl --user restart persona-webui` (idempotent). The inline-url helper is copied into
  the venv's open_webui/utils on each webui start.

================================================================================
3. WHERE THE NEW KNOBS / CODE LIVE
================================================================================

services/api/server.py:
  - self_identity_section()/load_self_identity() (SELF_IDENTITY.md), injected in build_persona_prompt
    + build_persona_messages (between Hermes rules and Output format). SELF_IDENTITY_ENABLED.
  - intellectual-honesty (anti-sycophancy) + fuller-default Output-format text in both builders.
  - SELF_KNOWLEDGE_* + ingest_self_knowledge() + POST /memory/ingest_self + _purge_kind().
  - structured_intake() + _intake_resolve_conflicts() + MEMORY_INTAKE_* ; POST /memory/intake.
  - memory_hygiene_pass() + POST /memory/hygiene + MEMORY_HYGIENE_* ; auto-call in _sleep_cycle_loop.
  - memory_query_detailed(); POST /memory/facts + POST /memory/forget (review + targeted purge).
services/api/self_knowledge.py / memory_intake.py / memory_hygiene.py (all stdlib, unit-tested).
services/api/memory_distiller.py: DISTILL_PROMPT provenance section (per-turn + sleep-cycle).
services/api/ragstore.py: query_detailed() (both stores); QdrantStore.delete returns REAL count.
SELF_IDENTITY.md (repo root): the always-on identity block.
scripts/start_webui.sh: web-search default (OR-override, self-healing) + inline-url patch + the
  less-eager QUERY_GENERATION_PROMPT_TEMPLATE.
scripts/webui_patches/persona_inline_urls.py: inline-URL fetch helper.
scripts/apply_scope_contracts.sh: per-role .hermes.md soft scope contracts (called by init_profiles.sh).
scripts/systemd/: persistent unit files + install README.
Tests (offline 23/23): test_inline_urls, test_self_knowledge, test_self_identity, test_memory_intake
  (incl. conflict parser), test_memory_hygiene, + the pre-existing suite.

================================================================================
4. HEADLESS TESTING (tools/webui_probe.py) -- still the debug loop
================================================================================

  ssh evox2 'cd ~/Git/Project_Persona && env_webui/bin/python tools/webui_probe.py [--web|--no-web] \
    [--expect-sources|--expect-contains TXT|--expect-absent TXT] [--json] "PROMPT"'
Drives OpenWebUI :3000 end to end (mints the HS256 JWT from .webui_secret_key). Single-turn only --
multi-turn must be tested by POSTing a messages[] array straight to the persona /v1/chat/completions
(that is how the anti-sycophancy reassessment was verified; OpenWebUI is bypassed, so no web search).

================================================================================
5. NEXT SESSION -- PRIORITIZE C: HARD CONTAINMENT FOR HERMES WORKERS
================================================================================

WHY soft-only this session: per-role command/filesystem containment is NOT achievable by config:
  - Every worker needs the LOCAL terminal tool -- it completes tasks by running `hermes kanban
    complete <id>` as a SHELL command (this is what the worker-shell PATH fix [run/hermes_shell_init.sh]
    exists for). Remove terminal -> the worker can't finish.
  - Hermes terminal is `backend: local` with NO command/path allowlist.
  - No docker on EVO-X2 for a sandboxed backend.
  - tools.disabled accepts TOOL names, not TOOLSET names (verified: toolset-name denies were ignored),
    and an open shell bypasses tool-level limits anyway.
Already-covered (do NOT redo): non-researcher roles are egress-off; the daemon strips cloud secrets
from worker children -> no network exfil / credential leak. Soft scope contracts are now in each
.hermes.md.

PATHS for HARD containment (Brandon to choose):
  (a) Restricted shell wrapper: point terminal.shell_init_files / a wrapper at a shim that allowlists
      commands (permit `hermes kanban *`, the role's needed binaries; deny rm -rf, network tools,
      writes outside the task workspace). Must keep `hermes kanban complete` working -> test the full
      delegate->dispatch->worker->complete->bridge-mirror chain after each change (~100s/cycle; it is
      FRAGILE -- the H2d chain).
  (b) A sandboxed terminal backend (bubblewrap/firejail/nsjail -- userspace, no docker/root needed?
      verify availability on EVO-X2) wrapping the worker shell with a read-only FS except the task
      workspace + no network. Cleanest if a userspace sandbox is installable without sudo.
  (c) Per-role workspace confinement: run each worker with CWD/HOME pinned to an ephemeral task dir.
VERIFY GATE for any option: a delegate (role=summarizer) must still reach status=ok+summary on /jobs.
Investigate Hermes' terminal/security config schema first (env_hermes; `hermes config --help`,
`hermes tools list`); v0.16.0 may have a sandbox/allowlist option not yet used.

================================================================================
6. OTHER OUTSTANDING (Brandon's call)
================================================================================

- UNTRACKED persona profiles on EVO-X2 (incl. the new scope-contract .hermes.md edits) are NOT in git
  -> not backed up. Decide whether to commit them (the H4 role profiles + skills/).
- B (Git-backed canon/ markdown memory): deferred; low ROI vs insight_journal.md.
- D extension: the in-sweep LLM contradiction pass (beyond near-identical dedup) is not wired -- intake
  (A) handles new writes; a manual `?resolve_conflicts=true` batch could be added if needed.
- Web-search content quality for breaking news: keyless DuckDuckGo ranks evergreen SEO; researcher
  role (path B, POST /agent/delegate {"role":"researcher"}) is the deep tool.
- Older owed: kernel egress baseline (scripts/egress_baseline.sh, root, Brandon); EVO-X2 35B/Vulkan
  llama rc=-6 instability (supervisor auto-recovers, root-cause owed); H6.4 cache study (multi-slot).

================================================================================
7. OPERATING EVO-X2 + ONE-LINER RESUME CHECK
================================================================================

- Health:  ssh evox2 'cd ~/Git/Project_Persona && env/bin/python manage.py daemon status'
- Restart persona stack: ssh evox2 'systemctl --user restart persona-daemon'
- Restart OpenWebUI (re-applies all middleware patches): ssh evox2 'systemctl --user restart persona-webui'
- Deploy a change: edit on D:\ -> portable\python\python.exe -m py_compile + tests/run_all_offline.py
  -> update changelog+todo+roadmap (Brandon's rule: BEFORE commit) -> commit -> push -> ssh evox2
  git pull --ff-only -> restart the relevant unit (persona-daemon for server.py/SELF_IDENTITY.md;
  persona-webui for start_webui.sh/inline-url).
- Memory admin: POST /memory/ingest_self ; POST /memory/intake {text} ; GET/POST /memory/facts ;
  POST /memory/forget {ids} ; POST /memory/hygiene[?apply=true]. Backups: archive/memory_backups/.

  ssh evox2 'cd ~/Git/Project_Persona && env/bin/python manage.py daemon status && \
    curl -s -o /dev/null -w "api:%{http_code} llama:%{http_code}\n" http://127.0.0.1:8000/health \
      http://127.0.0.1:8090/health && \
    env_webui/bin/python tools/webui_probe.py --no-web --expect-contains "Next actions" \
      "give me one productivity tip"'

Expect: daemon ACTIVE, api+llama 200, probe validation OK -> stack + debug loop live. Then start
section 5 (C hard containment).
