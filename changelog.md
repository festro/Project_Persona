# Project_Persona -- Changelog

Reverse-chronological history. New entries go at the TOP.

Conventions:
- Header format: `## YYYY-MM-DD HHMM PDT -- short summary (<author>)`
- One bullet per change, past tense, terse.
- File / line references where useful.
- ASCII only (see `WORKFLOW.md`).
- Append-only. To correct a prior entry, add a new entry on top; do not
  edit history.
- Entries reconstructed from the pre-convention File Change Tracker keep their
  recorded date; HHMM is shown only where the original recorded it.

---

## 2026-06-21 2115 PDT -- Phase 8 H6.1: swarm fan-out -> verifier -> synthesizer PROVEN on EVO-X2 (Brandon + Claude)

- Proved the Hermes swarm substrate end to end on the standing dispatcher (driven over SSH).
  `hermes kanban swarm` built a graph (2 parallel workers -> verifier -> synthesizer); the
  dispatcher ran it serialized on PARALLEL=1 honoring the dependencies: both workers completed
  -> the verifier ran -> the synthesizer combined them into one paragraph (draft saved in the
  synthesizer's workspace). The fan-out -> verifier -> synthesizer orchestrator (H6.1 / the
  "research-grade query" path) works on the anchor node.
- GOTCHA (recorded): `--worker PROFILE:TITLE[:SKILL,...]` is colon-delimited, so a worker TITLE
  containing ':' is mis-parsed -- the tail becomes a bogus SKILL ("Unknown skill" -> the worker
  crashes -> auto-blocked). Use colon-free worker titles. (The first attempt blocked exactly this
  way -- a clean re-confirmation of the auto-block ceiling; the colon-free retry completed.)
- INTEGRATION NOTE (follow-up): swarm cards are created directly on the kanban board, NOT via
  POST /agent/delegate, so they have no persona /jobs rows and are not surfaced on /jobs yet. A
  persona-surfaced swarm (delegate -> bridge builds a swarm graph + mirrors the synthesizer result)
  is a bridge feature for later; H6.1 here proves the substrate. No code change (Hermes-native +
  existing bridge); validation only. Cleaned up the swarm + H6.2/H6.3 test cards (archived).

## 2026-06-21 2035 PDT -- Phase 8 H6.3 confirmed live + bridge settled-column precedence generalized (Brandon + Claude)

- H6.3 CONFIRMED LIVE on EVO-X2 with the fix deployed: killed the worker on each spawn -> after 2
  consecutive crashes the dispatcher auto-blocked the card (`auto_blocked=1`) -> the bridge mirrored
  /jobs status=blocked (attempts=2, block_reason "pid ... not alive"). The failure ceiling now
  surfaces as recoverable-blocked, not error. The bridge log also confirmed flushing (the H3 fix).
- GENERALIZED the bridge status precedence (one more bug, same class, surfaced by the now-flushing
  bridge log): two stale orphan jobs (h2d-005/006) were re-patched to "running" every tick. Cause:
  their archived cards' latest run outcome was "reclaimed" (-> _RUNNING), which overrode the
  terminal "archived" column. FIX: tools/hermes_bridge.py derive_update now treats SETTLED columns
  (blocked/done/archived) as authoritative over the transient run outcome (was a blocked-only
  special case at 1915). So an archived card settles to ok, a done card to ok, a blocked card to
  blocked -- regardless of a trailing reclaimed/crashed run. The orphans self-resolved to ok on the
  next tick after deploy. tests/test_hermes_bridge.py +1 (50 checks); offline suite 18/18.

## 2026-06-21 1915 PDT -- Phase 8 H6.2/H6.3: failure-semantics validated; bridge auto-block mapping fix (Brandon + Claude)

- Exercised the Hermes-native failure semantics through the now-standing dispatcher (H3) on
  EVO-X2, driven over SSH. (The daemon + Hermes children had persisted ~7h since the H3
  checkpoint -- further durability proof.)
- H6.2 PROVEN (reclaim + recovery): delegated a task, killed the spawned worker mid-run
  (SIGKILL, card t_5dfab12a). The dispatch loop logged `crashed=1 spawned=[t_5dfab12a]` -- it
  reclaimed the stale claim and re-dispatched in ONE tick; attempts 1->2; the re-run completed
  -> /jobs ok, attempts=2. Reclaim of a dead worker + automatic re-dispatch + recovery, hands-off.
- H6.3 surfaced a BRIDGE BUG (then fixed it): killed the worker on every spawn -> after 2
  consecutive crashes the dispatcher auto-blocked the card (`crashed=1 auto_blocked=1`,
  failure-limit=2) -- Hermes' native ceiling works. BUT /jobs showed "error", not "blocked":
  tools/hermes_bridge.py derive_update preferred the latest run OUTCOME (crashed->error) over the
  card COLUMN (blocked). An auto-blocked card is PARKED + recoverable (`hermes kanban unblock`),
  not a dead error. FIX: the literal "blocked" column is now authoritative over a crashed/
  timed_out run -> the bridge mirrors "blocked" + block_reason. (gave_up still -> error;
  failure-limit only auto-blocks on spawn_failed/timed_out/crashed, never gave_up -- so the old
  test's blocked-col + gave_up payload was unrealistic and was made realistic.)
  tests/test_hermes_bridge.py +3 (49 checks); offline suite 18/18.
- Re-verifying live on EVO-X2 after deploy (auto-block -> /jobs blocked).

## 2026-06-21 1225 PDT -- Phase 8 H3 PROVEN LIVE on EVO-X2: hands-off delegate -> ok+summary (Brandon + Claude)

- Brought the standing Hermes layer up on EVO-X2 (driven over SSH) and proved H3 end to end
  with ZERO manual dispatch. `manage.py daemon start --with-hermes` now supervises FOUR
  children: llama-server, api, hermes-bridge, hermes-dispatcher. Confirmed the daemon + both
  Hermes children persist across fresh SSH sessions (systemd --user + linger; same pids held
  over 5+ min of separate SSH connections).
- THE H3 GATE (unattended): POST /agent/delegate "H3 hands-off smoke" -> the bridge created
  Hermes card t_97ebe628 (~25s) -> the supervised dispatch loop spawned the worker
  (logs/hermes_dispatcher.log: `[hermes_dispatch] spawned=[t_97ebe628]`) -> the 35B ran the
  agent loop -> kanban_complete -> the bridge mirrored ok + summary to /jobs. ~100s
  delegate->ok, attempts=1. This is H2d made UNATTENDED: the dispatch pass that was run BY
  HAND in H2d now runs on the 60s loop with no operator. (job delegate-c391ee760eca, summary
  mirrored: "H3 hands-off smoke test passed: Hermes worker ... ran autonomously ...".)
- Cleaned 2 stuck p4 orphans (t_2e5bc9c1/t_aa26e318, leftovers of the 2026-06-21 PARALLEL=4
  test) by archiving them so the dispatcher would not auto-rerun them -> active board clean
  before the gate test.
- FIX (observability): tools/hermes_bridge.py main() print now flush=True. Under the supervisor
  a child's stdout is a block-buffered pipe, so the bridge log sat at 0 bytes despite the
  bridge working (the dispatch loop already flushed); an unattended standing child must log
  promptly. Pre-existing; surfaced by the H3 live run.
- ROADMAP: Phase 8 H3 -> [x]; the "Hermes runs as a daemon child" Exit-Gate line -> [x] (bridge
  + dispatcher run as supervised children, live on EVO-X2). Offline 18/18 retained. NEXT: H4-H6
  per the approved plan.

## 2026-06-21 1200 PDT -- Phase 8 H3: standing dispatcher child (loops the SUPPORTED `dispatch`) (Brandon + Claude)

- H3 makes the H2d chain UNATTENDED. H2d proved delegate -> bridge card -> `hermes kanban
  dispatch` (run BY HAND) -> 35B worker -> mirror ok+summary; H3 supervises that dispatch
  pass as a standing daemon child so no operator is needed.
- Command surface RE-VERIFIED on EVO-X2 (env_hermes v0.16.0, pinned @9b1e0d6f): `hermes
  kanban daemon` is DEPRECATED ("dispatcher now runs in the gateway"); the `gateway` is a
  messaging service (Telegram/Discord/WhatsApp) needing its own OUT-OF-PROJECT
  systemd/launchd unit + platform creds -- against the portability rule + egress-off. So the
  standing dispatcher LOOPS THE SUPPORTED one-shot `hermes kanban dispatch` (reclaim stale +
  promote ready + spawn workers + `--failure-limit` auto-block) instead. (Brandon's call.)
- NEW tools/hermes_dispatch_loop.py (stdlib, mirrors tools/hermes_bridge.py): interval loop
  over `hermes kanban dispatch --failure-limit N --json`; parses the v0.16.0 result shape
  (reclaimed/promoted/spawned[]/auto_blocked/...); logs only ticks that change something;
  `--once` for tests; HERMES_DISPATCH_INTERVAL (default 60). HERMES_CLI is absolute so the
  dispatch call has no worker-shell PATH dependency.
- daemon.py: hermes_dispatcher_spec(root) mirrors hermes_bridge_spec (hygiene=True, HERMES_*
  env, logs/hermes_dispatcher.log, run/hermes_dispatcher.pid); build_specs(with_hermes=True)
  now supervises BOTH Hermes children (bridge + dispatcher) under the three-strike
  supervisor, so one `manage.py daemon start --with-hermes` brings up the whole standing
  Hermes layer (satisfies H3.1 daemon-child + H3.4 three-strike reuse; the original
  H3.2/H3.3 custom dispatcher/heartbeat are Hermes-native under the 2026-06-13 bridge arch).
- tests/test_daemon_hermes.py +12 checks (dispatcher spec shape/hygiene, build_specs
  inclusion, dispatch-loop argv builder + dispatch_changed/summarize + tick + `--once`);
  offline suite 18/18, py_compile clean (Windows portable 3.11).
- ROADMAP: Phase 8 H3 -> [~] (CODE DONE + offline green). LIVE on EVO-X2 (restart
  --with-hermes + clean the 2 stuck p4 orphans + hands-off delegate -> ok+summary) is the
  next step, then [x].

## 2026-06-21 0035 PDT -- EVO-X2 per-host config canonicalized: PARALLEL=1 required for the Hermes worker (Brandon + Claude)

- Tested PARALLEL=1 vs 4 on EVO-X2 (CTX fixed 65536) for the Hermes kanban-worker:
  * PARALLEL=1 -> 65536 tokens/slot -> worker COMPLETES the agent loop (~105s; proven 3x earlier:
    jobs h2d-001/002/003 reached status=ok + summary).
  * PARALLEL=4 -> 16384 tokens/slot -> worker does NOT complete (died after one call once, then ran
    6+ min without finishing on retry).
  So the earlier hunch that PARALLEL=1 was "over-cautious" (because visible prefill counts were
  ~750 tok) was WRONG -- the Hermes 64K context floor is real in effect; the agent loop needs the
  large per-slot context. Reverted EVO-X2 to PARALLEL=1; daemon confirmed back up.
- run/config.daemonic-evox2.toml COMMITTED as the canonical per-host anchor (like
  config.daemonic-pc.toml) at CTX=65536/PARALLEL=1, with the measurement recorded inline. Brandon's
  rationale for keeping a constant per-host file: it is the per-node config anchor and aligns with
  the Phase 9 plan to key node identity off stable system specs. Trade-off: the agentic anchor node
  serves one big worker slot over chat concurrency.

## 2026-06-20 2010 PDT -- Portable persistence: `manage.py daemon` + init_profiles PATH fix (Brandon + Claude)

- Brandon's portability rule: everything must run from INSIDE the project folder; the only exception
  is python (prefer the in-folder venv). Reworked the EVO-X2 H2d setup to honor it (no /usr/local/bin):
  * init_profiles.sh now generates run/hermes_shell_init.sh (project-relative; puts $AI_ROOT/env_hermes/bin
    on PATH) and wires it into the generated config.yaml terminal.shell_init_files, so a worker's
    clean-PATH shell resolves `hermes` from inside the project -- no system symlink. New hosts get it
    automatically; write_hermes_config still skips existing configs.
  * manage.py gained a `daemon [start|stop|status]` command for PORTABLE background persistence:
    Windows -> detached process group (run/daemon.pid); Linux+systemd -> a transient `systemd --user`
    unit (survives SSH disconnect/logout via linger; NO unit file outside the project; daemon runs from
    the project via env/bin/python); non-systemd -> setsid best-effort with a warning. Encapsulates the
    systemd-run detail inside the project launcher (was a manual command on EVO-X2).
- FINDING (why systemd is unavoidable for an always-on daemon on this OS): plain setsid/nohup/double-fork
  do NOT survive an SSH session end on a systemd host -- the process stays in the SSH session's systemd
  cgroup, which is torn down at session end (proven: a setsid marker died though KillUserProcesses=no).
  systemd-run --user is the only unprivileged escape to the persistent user manager.
- Offline 18/18; `manage.py daemon status/help` verified on Windows + py_compile clean. VERIFIED
  LIVE on EVO-X2: `manage.py daemon start` launched the systemd --user unit and the stack PERSISTED
  across a fresh SSH session (unit active, llama+api up) -- replaces the manual systemd-run.

## 2026-06-20 1915 PDT -- Phase 8 H2d Exit Gate PROVEN on EVO-X2 (driven over SSH) (Brandon + Claude)

- Brought EVO-X2 (Daemonic-evox2, KDE neon, RADV GFX1151 Vulkan) up to date over SSH and proved
  the Phase 8 H2d Exit Gate end to end. SSH access fixed first: the `evox2` ~/.ssh/config used the
  GitHub key + the box had no authorized key for this host -> Brandon added the brandonnet key,
  config IdentityFile corrected.
- RE-BASELINE: EVO-X2 was 29 commits behind (0cb85bf); pulled to a18a78f. Same qdrant-client venv
  gap as Windows -> installed (1.18.0). Offline 18/18; doctor green incl. T1 (env_hermes present,
  safe_config=pass). Phase 1 exit_gate_live ALL PASS on the real GPU incl. the messages-path default
  (persona_use_messages=True) + /v1 reasoning_content.
- PERSISTENCE: a one-shot `ssh ... manage.py up`/`daemon.py` gets SIGHUP/SIGTERM'd when the SSH
  session closes (nohup+setsid insufficient through the tool's SSH teardown). Fixed by running the
  daemon as a systemd --user transient service (linger=yes) -> survives SSH close + logout.
- H2d (the gate): delegate -> bridge creates the kanban card -> `hermes kanban dispatch` spawns the
  worker -> the 35B runs the kanban-worker agent loop -> kanban_complete with summary -> bridge
  mirrors ok+summary to /jobs. h2d-001/002/003 all status=ok + summary; unattended dispatcher-spawned
  workers complete in ~105s.
- ROOT-CAUSE FIX (why the first dispatcher worker died): the worker's shell tool runs with a CLEAN
  PATH (/usr/local/bin:...), so its `hermes kanban show/complete` calls hit exit 127 and floundered
  (one fallback hit a 60s command-deny) until timing out. Fix (no sudo): a terminal shell_init_files
  entry (run/hermes_shell_init.sh) puts env_hermes/bin on the worker-shell PATH -> workers find
  `hermes` immediately and complete cleanly. (A /usr/local/bin symlink would also work but needs root.)
- EVO-X2 H2d setup (runtime, EVO-X2-local): run/config.daemonic-evox2.toml (CTX 65536/PARALLEL 1 --
  over-cautious; the worker prompt is ~750 tok not 20k, so PARALLEL=4 would allow concurrency),
  run/hermes.env pins (+ PATH), seeded persona/config.yaml (default-assignee root config), kanban
  init, .gitignore run/hermes_kanban/.
- Egress: config-level OFF (no provider keys, browser off, terminal.backend=local, llama on
  loopback). Kernel nftables layer (scripts/egress_baseline.sh) still owed -- needs root (sudo is a
  hard-deny for the remote agent). FOLLOW-UPS: codify the PATH fix in init_profiles.sh (or
  env_passthrough:[PATH]); a persistent ~/.config/systemd/user unit for reboot survival; H3-H6.

## 2026-06-20 1510 PDT -- Windows verification pass: thinking-model fixes + messages-path default (Brandon + Claude)

- Verified the WSL-built stack LIVE on Windows (Daemonic-PC, 35B/Vulkan): Phases 1, 2, 3,
  6, 7 Exit Gates pass on the second primary surface; offline 18/18. Pushed a70fe90 +
  cf79270 to origin/main.
- THINKING-MODEL HANDLING (the through-line): the stack was built/validated in WSL on the
  non-thinking Qwen2.5-7B; the production 35B is a thinking model and several paths
  mishandled <think> output. All fixed + verified live:
  * Sanitizer (server.py sanitize_persona_reply): when the model emits no head before
    "Next actions:", promote its real content instead of the canned "I can help with
    local..." fallback (was discarding real answers ~1/3 of the time on the 35B). a70fe90.
  * Distiller (memory_distiller + _sleep_distill): append /no_think, strip residual <think>
    in parse_facts, raise MEMORY_DISTILL_MAX_TOKENS 96->256. Phase 7 sleep cycle distilled
    ZERO facts on the 35B before this; now distills (facts + links + insight journal). a70fe90.
  * MESSAGES PATH NOW DEFAULT (PERSONA_USE_MESSAGES=1, cf79270): reliable thinking control --
    enable_thinking off on casual topics (0/5 canned vs 2/5 raw), on for THINKING_MODE topics
    with a per-OS PERSONA_MAX_TOKENS budget (linux 4096 = 8192/slot, windows 2048 = 4096/slot)
    so the chain of thought completes. Verified: no_think recall 5/5 clean; a science question
    returned full reasoning + a complete answer. manage.api_env now forwards
    PERSONA_USE_MESSAGES + PERSONA_MAX_TOKENS from config.toml.
- WINDOWS-BLOCKING BUGS (a70fe90):
  * daemon.py imported `manage` without the repo root on sys.path -> ModuleNotFoundError on
    the Windows embeddable Python; Phase 3 could not start on Windows at all (only ever ran
    on WSL). Fixed (sys.path.insert repo root) -> supervise/restart/IPC all verified live.
  * qdrant-client missing from the Windows portable env (predates the Phase 2a requirement)
    -> RAG fully down (rag_ok=false); installed it. requirements.txt was already correct; the
    env had not been re-bootstrapped since Phase 2a.
  * exit_gate_live.py asserted stale chroma_ok -> now backend-agnostic rag_ok.
- FINDING (not in repo): Daemonic-PC is RAM-tight (31 GB, ~21 in use) for sustained 35B live
  testing -- the OS silently killed the stack under a long inference run (clean logs, no
  crash). EVO-X2 is the node for sustained/deep work.

## 2026-06-20 0300 PDT -- README: status reconciled with reality (Brandon + Claude)

- Updated the README to match the current build (it lagged the session's phase work):
  * Memory & Context: ChromaDB-current/"Qdrant planned" -> Qdrant is the DEFAULT (embedded, on-disk;
    ChromaDB fallback), since Phase 2a.
  * Current Stack table: Vector store -> Default (done); Agent backbone -> bridge wired as a daemon
    child, execution EVO-X2-gated; Frontend -> stood up + wired to /v1 (click-test owed); Voice +
    Avatar -> scaffolded (engines/client host-side). Dropped the inaccurate "Wyoming protocol" voice
    component (the scaffold uses HTTP server children).
  * Roadmap summary list: Qdrant, always-on daemon, Sorting Line, Sleep Cycle flipped ⏳ -> ✅; Hermes
    / embodiment / voice -> 🔄 scaffolded; added Phase 2 history+task-surfacing and Phases 9-10 parked.

## 2026-06-20 0250 PDT -- README: vibe-coded disclosure (Brandon + Claude)

- Added a clear callout under the README tagline: Project_Persona is a vibe-coded project (the
  large majority of code/tests/docs written by an AI coding agent under human direction); inspect
  + review before trusting it; issues/audits/PRs welcome. Transparency for anyone landing on the repo.
- NOTE (not changed): the README "Memory & Context" section still says ChromaDB is current with the
  Qdrant migration "planned (Phase 2a)" -- stale, Qdrant is now the default (flipped 2026-06-19).

## 2026-06-20 0240 PDT -- Tracker reconciliation: todo + roadmap stamps current (Brandon + Claude)

- The session moved fast and the trackers drifted. Reconciled: roadmap.md "Last updated" stamp
  bumped 06-19 -> 06-20 with the session summary (Phases 2-8 + optional 4-5 + audit, all pushed
  through a2a8e6f); roadmap Phase 2 keying description corrected to the FIXED behavior (the `user`
  field is folded into the hash, not used as the id -- it was describing the pre-audit bug).
- todo.md: bumped the stamp; collapsed THREE drifted/overlapping "Next up" sections (one still said
  "PUSH PENDING ... origin at b23a476") into ONE accurate snapshot -- host-gated (EVO-X2 Phase 8
  H2d/H3-H6 + kernel egress; egress live-apply; provisioner Windows confirm), manual (OpenWebUI
  click-test; Godot/audio), housekeeping (the stale 2nd D: clone; optional inbox/processed cap).
  Added a "Just finished 06-20" entry for the audit. (Older Just-finished history retained below;
  it is authoritative in changelog.md -- a deeper todo trim is offered, not yet done.)

## 2026-06-20 0230 PDT -- docs/host_onboarding.md (new-machine checklist) (Brandon + Claude)

- Ordered, copy-pasteable checklist to bring a new host to a working stack: per-host SSH key ->
  clone (LFS) -> scripts/setup_native_stack.sh (or windows_portable_setup.bat) -> provide a model
  (manage.py provision) -> per-host run/config.<host>.toml -> verify (status/doctor/run_all_offline
  18/18 + live up/health/down) -> run (manage.py up OR daemon.py [--with-hermes|--with-voice]) ->
  optional surfaces (OpenWebUI, memory endpoints, sorting line, egress) -> EVO-X2 specifics (the
  35B Vulkan target, Hermes/H2d, kernel egress) -> troubleshooting. Written for the move to EVO-X2.

## 2026-06-20 0210 PDT -- Audit fixes round 2: the remaining polish items (Brandon + Claude)

Cleared the rest of the Phase 1-8 reevaluation backlog. Offline suite 17 -> 18 suites.

- daemon.py: max_total_starts ceiling (default 20) -- a child crashing just slower than
  stable_reset_s would reset its strikes and restart forever; now it stays down after the cap.
  Removed the dead GOOGLE_APPLICATION_CREDENTIALS_OK sanitize KEEP typo. tests/test_daemon.py +
  a slow-crash-loop case (17 checks).
- sleep_cycle.consolidate: a conversation that distills to nothing (no facts + empty summary) is
  no longer marked distilled (a transient empty no longer permanently retires the turns); its cid
  goes into a caller-owned skip set (server._sleep_skip) so it's retried after a restart but not
  re-hammered each pass. tests/test_sleep_cycle.py + empty-distill case (18 checks).
- sorting_line.classify: word-aware matching (_kw_hit -- single words use a \b boundary, phrases
  stay substring) and dropped the bare pronouns (i/my/we) from the personal bin, which were
  swallowing everything. "we import the dataset" -> research/code (not personal); "git" no longer
  fires inside "digit". tests/test_sorting_line.py + over-match regression (35 checks).
- server.py: replaced the deprecated @app.on_event("startup") with a FastAPI lifespan handler for
  the inbox-watcher + sleep-cycle loops (live-verified: the lifespan watcher still ingests a drop).
  NEW memory-inspection endpoints (the embedded Qdrant store is single-writer + held by the API):
  GET /memory/collections, GET /memory/search, POST /memory/ingest_inbox. tests/test_memory_
  endpoints.py (7 checks). scripts/ingest_inbox.py now routes through POST /memory/ingest_inbox
  when the API is up (no store-lock conflict) and only opens the store directly when it's down --
  live-verified both the lifespan watcher and the API-routed manual trigger.

## 2026-06-20 0140 PDT -- Audit fixes: /v1 thread-merge bug + gitignore + sleep-cycle profile (Brandon + Claude)

Found in a Phase 1-8 reevaluation; three issues fixed (offline suite 17/17).

- BUG (Phase 2 /v1): _v1_conversation_id keyed on the OpenAI `user` field BEFORE the per-thread
  hash. `user` is a per-END-USER id (not per-conversation), so two unrelated threads from the same
  user collapsed into one conversation_id -- confirmed live (cats + france, user="brandon", both
  got id "brandon"). FIX: an explicit conversation_id still wins; otherwise `user` is folded INTO
  the hash (user + system + first_user), namespacing the per-thread key -- distinct threads stay
  distinct, distinct users stay isolated. tests/test_v1_history.py +regression (29 checks).
- .gitignore: only persona/global_memory/chroma/ was ignored -- persona/global_memory/qdrant/ and
  insight_journal.md were NOT, so a full WSL->D:\ pullback could land the vector DB + journal
  untracked (a stray `git add -A` could commit them). FIX: ignore persona/global_memory/ wholesale
  (covers chroma + qdrant + journal). (Inline `#` comments are not valid in .gitignore -- fixed.)
- sleep_cycle.consolidate took a fixed fact_collection and server.py passed _collection_name(None)
  (always global_memory), diverging from the per-turn distiller's _collection_name(profile) if
  RAG_PER_PROFILE is ever enabled. FIX: consolidate now takes collection_for(profile) and routes
  each conversation's facts to its own profile collection; server passes _collection_name.
  tests/test_sleep_cycle.py +per-profile routing check (15 checks).
- Not fixed (reported, lower priority): embedded-Qdrant single-writer lock (ingest_inbox.py can't
  run while the API holds the store; no live-inspection endpoint); FastAPI on_event deprecation;
  sorting-line `personal` bin over-matching common pronouns; sleep cycle marking turns distilled on
  an empty distill; daemon stable-reset vs slow crash-loops; sanitize_env dead KEEP entry.

## 2026-06-20 0100 PDT -- Phase 4 + 5 scaffolding (optional phases) (Brandon + Claude)

- Phase 4 (embodiment) persona side -- the two-channel RESPONSE + STATE protocol:
  * services/api/avatar_state.py (NEW): derive_state(text, speaking) -> {emotion, intensity,
    gesture, speaking, viseme} in a fixed vocabulary (EMOTIONS/GESTURES). Pure + deterministic
    keyword-cue deriver (concerned/confused/excited/happy/amused; questions -> thinking; "!"
    amplifies). No model call.
  * server.py: /chat returns a `state` object alongside `text` (AVATAR_STATE_ENABLED, default on,
    additive). /health.avatar_state advertises the enums. docs/avatar_protocol.md documents the
    two-channel protocol + STATE vocabulary for a Godot/VR client. tests/test_avatar_state.py 14.
- Phase 5 (voice) -- Whisper STT / Piper TTS as supervised daemon children:
  * daemon.py: stt_present/tts_present + whisper_stt_spec/piper_tts_spec (guarded child specs;
    None when binary/model absent), build_specs(with_voice) + `daemon.py --with-voice` /
    VOICE_DAEMON_ENABLED. Engines are host-provided (env-overridable WHISPER_SERVER_BIN/MODEL/PORT,
    PIPER_BIN/MODEL/PORT); Piper GPL-3.0 runs as a separate process (never linked).
    docs/voice_pipeline.md (offline STT->LLM->TTS design + install + tts_speaking->avatar tie-in).
  * tests/test_daemon_hermes.py extended (now 20 checks): voice specs None when absent; build with
    a fake binary+model; with_voice includes both children when present.
- Offline suite 16 -> 17 suites. Both phases are OPTIONAL: the Godot client and the audio engines/
  device are host-side; the persona STATE channel + the daemon supervision wiring are done + tested.

## 2026-06-20 0050 PDT -- Phase 8 scaffolding (WSL): Hermes daemon child + daemon env hygiene (Brandon + Claude)

- "All that can be done on WSL without the 35B/GPU" toward Phase 8. Two Exit-Gate items advanced.
- daemon.py -- Hermes as a supervised daemon child (the persona-side H2 bridge):
  * hermes_present(root) + hermes_bridge_spec(root): guarded by env_hermes/; builds a ChildSpec
    that runs `env_hermes/bin/python tools/hermes_bridge.py --interval N` under the three-strike
    supervisor with HERMES_CLI / HERMES_KANBAN_HOME / HERMES_HOME / TASKS_DB env, hygiene=True.
  * build_specs gains with_hermes; `daemon.py --with-hermes` + HERMES_DAEMON_ENABLED (opt-in,
    default OFF so base daemon behavior is unchanged). Skips with a log if env_hermes/ is absent.
  * LIVE on WSL: `daemon.py --with-hermes --no-llama --no-api` spawned + supervised the bridge
    child (pid up under env_hermes python), clean SIGTERM shutdown.
- daemon.py -- env hygiene (runtime egress containment): ChildSpec.hygiene + sanitize_env() strip
  cloud/egress secrets (keyed list incl. OPENAI/ANTHROPIC/HF/GitHub/Slack tokens + prefixes
  AWS_/AZURE_/GOOGLE_/GCP_/OPENAI_/ANTHROPIC_/LANGCHAIN_/LANGSMITH_/OTEL_EXPORTER_, with an
  AWS_REGION-style KEEP list) from a supervised agent's env at launch; applied to the hermes child.
- tests/test_daemon_hermes.py: 14 checks -- sanitize_env stripping/keeping, hygiene honoured by a
  REAL subprocess (hygiene child sees secret=MISSING, plain child still sees it), hermes spec shape,
  build_specs with_hermes inclusion/exclusion. Offline suite 15 -> 16 suites.
- Remaining Phase 8 is EVO-X2/host-gated: H2d (Hermes worker + 35B + GPU), H3-H6 execution, and the
  kernel netns/iptables egress layer. roadmap Phase 8 sub-items marked [~] accordingly.

## 2026-06-20 0020 PDT -- Phase 7 COMPLETE: the Sleep Cycle (Brandon + Claude)

- Idle-time consolidation: when the persona is quiet, a background pass distills recent
  un-distilled conversations into durable facts, discovers relationship links, and writes an
  insight-journal entry -- without disrupting the foreground. All Exit-Gate legs proven LIVE;
  tests/test_sleep_cycle.py 14 checks; offline suite 14 -> 15 suites.
- services/api/sleep_cycle.py (NEW, pure pipeline -- injected convo/embed/store/distill):
  consolidate() = select conversations with undistilled turns -> distill each transcript ->
  store facts (RAG) -> mark_distilled -> discover_links (k nearest memories) -> build_insight ->
  journal + insight RAG collection. should_continue() lets it stop between conversations.
- services/api/conversations.py: conversations_with_undistilled(min_turns, limit, profile) and
  undistilled_turns(cid) -- the work queue for the sleep cycle (turns.distilled flag, existing).
- services/api/server.py: idle trigger. An http middleware stamps _last_activity (excluding
  /health so liveness polls never starve it); _sleep_cycle_loop fires consolidate() only after
  SLEEP_CYCLE_IDLE_S of quiet and passes should_continue=idle-probe (the foreground-safety gate).
  _sleep_distill reuses build_distill_prompt + parse_facts; facts -> global_memory, insights ->
  the insight_journal collection + persona/global_memory/insight_journal.md. SLEEP_CYCLE_* config,
  /health sleep_cycle block, consolidation_done event.
- LIVE (Qwen + Qdrant, idle threshold 5s): both undistilled conversations consolidated (undistilled
  2 -> 0); insight_journal.md got 2 entries (teal -> "favorite color is teal"; the other -> the
  OpenWebUI/Qdrant tasks) with 4 + 2 relationship links; insight_journal RAG collection count=2 and
  retrievable; the teal fact landed in global_memory. Foreground: a request mid-window returned in
  0.011s and reset idle. roadmap Phase 7 -> [x] COMPLETE. Local; push pending Brandon's OK.

## 2026-06-19 2355 PDT -- Phase 6 COMPLETE: the Sorting Line (Brandon + Claude)

- Auto-contextual RAG: a file dropped in inbox/ is read, classified, routed into a per-bin
  Qdrant collection, and (on a trigger) promoted provisional -> mature. All Exit-Gate legs
  proven LIVE; tests/test_sorting_line.py 31 checks; offline suite 13 -> 14 suites.
- services/api/sorting_line.py (NEW, pure pipeline -- injected embed + RagStore):
  * read_document: stdlib text family (txt/md/code/json/csv + html via html.parser),
    utf-8/utf-16/latin-1 decode fallback, 8 MiB cap; optional pypdf/python-docx degrade
    gracefully; unsupported/oversized/binary -> ok=False (never raises).
  * classify: deterministic keyword score per bin + weighted cosine-to-prototype when an
    embedder is present (build_prototypes); DEFAULT_BINS code/research/reference/personal/
    finance + misc fallback.
  * ingest_text/ingest_path -> the bin's sl_<bin>__provisional collection with metadata
    (kind=inbox_doc, bin, status=provisional, origin, fmt); emits ingest_complete.
  * process_inbox: scan inbox/, ingest, move to inbox/processed | inbox/failed.
  * promote + age_trigger + mature_alias: graduate provisional -> sl_<bin> (mature), delete
    from provisional, point alias sl_<bin>_current at mature (the alias chain).
- services/api/ragstore.py: added delete(collection, ids) + set_alias(alias, collection) to
  both stores (Qdrant native alias; Chroma set_alias -> False fallback).
- services/api/server.py: API hosts the watcher (_inbox_watch_loop, startup task; runs inline
  so it never races request-path RAG on the embedded store), builds bin prototypes once, /health
  sorting_line block, SORTING_LINE_WATCH/POLL_S + INBOX_DIR config. scripts/ingest_inbox.py =
  one-shot/manual trigger reusing the live store+embedder.
- LIVE (real Qwen embedder + Qdrant): dropped snippet.py + groceries.txt in inbox/ -> routed to
  sl_code__provisional / sl_personal__provisional, both retrievable; promote() moved both to
  sl_<bin> (mature), emptied provisional, set aliases; querying the alias sl_code_current hit the
  promoted doc. roadmap Phase 6 -> [x] COMPLETE. Local; push pending Brandon's OK (end of phase).

## 2026-06-19 2330 PDT -- Phase 3 COMPLETE on LoopbackBus: API event publishing (Brandon + Claude)

- Decision (Brandon): finish Phase 3 on the stdlib LoopbackBus; DEFER NatsBus + the nats-server
  child to ride with the Phase 9 mesh unpark (the EventBus abstraction makes it a config swap).
  No nats-py / nats-server-bin installed.
- services/api/server.py: one-way control-plane publishing. publish_event(event, payload) schedules
  the publish on the running loop via a module LoopbackBus client (token from DAEMON_TOKEN, port
  from IPC_LOOPBACK_PORT) and returns immediately -- it NEVER awaits, blocks, or raises into a
  request; no daemon listening => silent drop. Wired task_ready on /agent/delegate (job_id/title/
  status) and /agent/run (job_id/kind/status). EVENTBUS_ENABLED flag + /health eventbus block.
- tests/test_api_events.py (NEW): 6 checks -- publish off-loop and on-loop-with-no-daemon both
  never raise, /agent/delegate emits task_ready (job_id+status), /health advertises the bus.
- LIVE end-to-end (daemon --no-llama hosting the bus + supervising the API): POST /agent/delegate
  returned "delegated" immediately AND the daemon logged
  "event task_ready: {'job_id': 'delegate-...', 'title': 'Phase 3 IPC smoke task', 'status':
  'delegated'}" -- proving one-way delivery without the API blocking. SIGTERM -> clean shutdown.
- Phase 3 Exit Gate fully green (bring-up + supervise, kill->restart, 4th-stays-down, one-way IPC).
  roadmap.md Phase 3 -> [x] COMPLETE on LoopbackBus (NatsBus deferred to Phase 9). Offline 13/13.
  Local; mid-/end-of-phase -- push pending Brandon's OK.

## 2026-06-19 2110 PDT -- Phase 3 foundation: daemon supervisor + EventBus/LoopbackBus (Brandon + Claude)

- Phase 3 STARTED. Two foundational pieces, both fully tested + the Exit Gate proven live.
- services/api/eventbus.py (NEW): EventBus interface + stdlib LoopbackBus per
  docs/ipc_decision.md section 7. asyncio.start_server on 127.0.0.1, 4-byte length-prefixed
  JSON frames (1 MiB cap), shared-token gated, "*" wildcard subscribe. Hard guarantees:
  ONE-WAY fire-and-forget and never-block/never-raise (publish to a dead/closed endpoint
  returns False, never throws). tests/test_eventbus.py 12 checks (round-trip, wildcard,
  token rejection, dead-endpoint, oversized-frame, post-stop).
- daemon.py (NEW): single asyncio entry point. Supervisor + ChildSpec supervise a child map
  as REAL children (asyncio.create_subprocess_exec -> death seen instantly via proc.wait()).
  THREE-STRIKE restart: relaunch on death; a child up > stable_reset_s (60s) resets its strike
  count; after max_strikes (3) a further death STAYS DOWN. Fresh-logs-on-start (truncate once,
  restarts append). Hosts the EventBus. SIGINT/SIGTERM -> graceful SIGTERM-then-SIGKILL of all
  children + bus, writes run/<name>.pid for manage.py compat. tests/test_daemon.py 14 checks
  (stable stays up, crash-loop gives up after 4 starts, kill->restart, hosted bus).
- manage.py: refactored start_llama/start_api -> extracted llama_argv(root,cfg) and
  api_argv(root,cfg) returning (argv, extra_env). The daemon and the CLI now build the
  byte-identical child command from one source. Behavior unchanged; offline suite 12/12.
- LIVE Exit-Gate smoke (Qwen2.5-7B, CPU): daemon brought up llama-server + api (both /health
  200) + bus on 127.0.0.1:8791; SIGKILL'd the API child -> daemon logged "restart 1/3" ->
  relaunched (new pid) -> /health 200; SIGTERM -> "all children stopped", ports freed.
- roadmap.md Phase 3 -> [~] (daemon/restart/fresh-logs [x]; IPC [~] LoopbackBus done, NatsBus +
  API event wiring next). Offline suite 10 -> 12 suites. Local (mid-phase; not pushed).

## 2026-06-19 1645 PDT -- Phase 2: task surfacing (all three surfaces) + RAG_BACKEND flip (Brandon + Claude)

- Task surfacing -- ALL THREE surfaces (Brandon's spec). Shared data + helpers in
  services/api/server.py: tasks_summary (normalized board view: title/status/assignee,
  newest first), render_tasks_block (compact text), is_task_query (intent gate),
  tasks_block_for (gated injection), GET /tasks endpoint, /health task_store.inchat_surfacing,
  TASKS_INCHAT_ENABLED/TASKS_INCHAT_LIMIT config.
- (1) IN-CHAT: tasks_block woven into build_persona_prompt + build_persona_messages +
  persona_generate (visible "Live task board" block, persona MAY share it), injected on /chat
  and /v1 when is_task_query(text). /chat debug.tasks {enabled,is_task_query,injected,chars}.
  LIVE on Qwen2.5-7B: "what tasks are you working on?" -> persona listed the 3 real board
  tasks (injected, 248 chars).
- (2) OPENWEBUI TOOL: tools/openwebui/persona_tasks_tool.py -- self-contained Tools class
  (list_tasks/get_task) calling the API /tasks + /jobs via an api_base_url valve (127.0.0.1
  native / host.docker.internal from Docker), with install instructions in the header.
- (3) STATUS PANEL: manage.py panel gains a /api/tasks handler that server-side-proxies the
  API /tasks (the API has no CORS, so the browser cannot fetch :8000 cross-origin) + a
  "Task board" section in PANEL_HTML polling every 2s. LIVE: panel /api/tasks returned 3 tasks.
- tests/test_tasks_surface.py (NEW): 24 checks -- intent gate, summary/render formatting against
  a temp tasks.db, gated injection (incl. disabled), GET /tasks shape, and /chat injection
  (block reaches persona_generate + debug.tasks) via TestClient. Offline suite 10/10 (was 9/9).
- RAG_BACKEND default FLIPPED chroma -> qdrant (Phase 2a / Exit Gate). Ran
  scripts/migrate_chroma_to_qdrant.py on this clone (mem_default 8, mem_bob 1, global_memory 56,
  mem_alice 1 -> qdrant, exact counts). Proved LIVE parity: chroma vs qdrant top-3 identical
  across 5 queries on the migrated 66-point corpus. Flipped services/api/server.py default
  (RAG_BACKEND env default chroma -> qdrant); API restarts clean (/health rag_backend=qdrant,
  rag_ok, 4 collections). RAG_BACKEND=chroma still falls back. Closes the last Phase 2 Exit-Gate
  box.
- roadmap.md Phase 2 -> [~] CODE-COMPLETE (task surfacing [x], Item 2a [x], all Exit-Gate boxes
  [x] except the manual browser UI click-test [~]). todo.md + stamp updated; a SYNC PENDING note
  records that all Phase 2 work is local on the WSL clone, not yet pulled back to D:\ or pushed.

## 2026-06-19 1505 PDT -- Phase 2: /v1 conversation wiring + OpenWebUI stood up (Brandon + Claude)

- services/api/server.py: /v1/chat/completions brought to parity with /chat for Phase 2.
  Added `import hashlib`. OA_ChatCompletionsReq gains optional `conversation_id` + `user`.
- HYBRID conversation keying (_v1_conversation_id): explicit `conversation_id` wins, else the
  OpenAI `user` field, else a stable `owui-<sha256[:16]>` hash of the system+first-user prefix
  -- so stock OpenWebUI threads (which carry no conversation id) map deterministically with no
  plugin, and a future plugin can override with an explicit id.
- _v1_latest_user_text: the trailing user message is the new input; conversations.db (NOT the
  client's resent message array) is the history source -> no double-counting. _v1_prior_turns +
  _v1_prepare_conversation: on first sight of a thread, SEED the DB from the client's prior
  user/assistant turns (system dropped) so server history converges with the client; then window
  prior DB turns into history and persist the user turn. Assistant turn persisted after generate;
  conversation_id returned in the response (extra key, OpenAI clients ignore it).
- tests/test_v1_history.py (NEW): 25 checks -- hybrid id resolution (explicit/user/hash,
  stability, distinctness, system participates), latest-user + prior-turns extraction, cold-thread
  seeding, warm-thread no-double-seed, windowing handoff, and a TestClient run of the endpoint
  (generation monkeypatched) confirming persistence + returned conversation_id. Offline suite 9/9
  (was 8/8). py_compile clean.
- LIVE validation on Qwen2.5-7B (Daemonic-PC WSL, CPU): manage.py up; /v1 turn 1 stated "favorite
  color is teal" (19s), turn 2 "what is my favorite color?" answered "Teal." (9s) purely from
  reloaded DB history -- the latest user message carried no color. Thread owui-412592b70b86d273
  held 4 ordered turns, no duplication. Exit-Gate persist/reload/windowing boxes proven on /v1.
- OpenWebUI stood up (no docker on this box -> pip route): created env_webui venv +
  open-webui==0.8.8; scripts/start_webui.sh run AI_ROOT-relative with OPENAI_API_BASE_URL ->
  http://127.0.0.1:8000/v1. Serving on :3000 (/health status:true) and wired -- OpenWebUI's
  startup GET /v1/models hit the API 200. OWED: a human browser click-test (interactive admin
  signup), not doable headless.
- roadmap.md Phase 2: OpenWebUI item -> [~] (stood up + wired); conversations.db item -> [x]
  (/v1 + UI mapping done); Exit Gate persist/reload/windowing -> [x], UI box -> [~], Qdrant
  parity still open. todo.md + stamp updated. Local (not yet synced to D:\ / committed).

## 2026-06-19 0442 PDT -- Phase 2: hybrid conversation windowing (history -> prompt) (Brandon + Claude)

- services/api/windowing.py: window_turns(turns, budget, min_recent, summarize?) keeps the
  newest turns verbatim within HISTORY_TOKEN_BUDGET and folds older turns into one summary
  block (distilled turns use their stored summary; else truncating heuristic; or an injected
  summarize() callback for the LLM distiller). render_history_messages (OpenAI msgs path:
  summary system note + recent role msgs) + render_history_text (raw /completion: "Summary
  of earlier..." + "Conversation so far:" block).
- server.py: build_persona_messages gained history_messages, build_persona_prompt gained
  history_text, persona_generate gained history; /chat windows PRIOR turns (fetched before
  the new user turn is recorded) and passes them in. HISTORY_ENABLED/HISTORY_TOKEN_BUDGET
  (2048)/HISTORY_MIN_RECENT (4) config; /health + /chat debug.history.
- VALIDATED: tests/test_windowing.py 16 checks; full offline suite 8/8; live 2-turn
  integration (turn 2's persona prompt carries turn 1: "Conversation so far: User: my
  favorite color is teal ..."). Multi-turn memory now works end to end (stored + recalled).

## 2026-06-19 0435 PDT -- Phase 2: conversations.db history store + /chat persistence (Brandon + Claude)

- services/api/conversations.py: stdlib-sqlite3 history store (taskboard.py posture --
  fresh conn/call, WAL, file-backed). Tables: conversations (thread) + turns (messages,
  chronological) with distilled/summary columns for hybrid windowing. CRUD: new_conversation,
  add_turn (auto-creates + bumps updated_at), get_turns (chronological; recent-N via limit),
  list_conversations (per-profile), count_turns, mark_distilled, delete_conversation.
- server.py: CONVERSATIONS_DB config + CONVO_PERSIST_ENABLED (on); init at startup; /chat
  resolves/auto-creates conversation_id, persists user+assistant turns, returns
  conversation_id; GET /conversations + GET/DELETE /conversations/{id} for reload/list;
  /health conversations block; estimate_tokens helper (~4 chars/token) for the tokens column.
- VALIDATED: tests/test_conversations.py 21 checks; full offline suite 7/7; live API
  round-trip via TestClient (auto-create -> continue same cid -> reload 4 turns in order ->
  list). OWED: /v1 + UI conversation-id mapping (rides with OpenWebUI wiring); history is
  STORED now but not yet fed into the prompt (that is the next item, hybrid windowing).

## 2026-06-19 0430 PDT -- Phase 2 STARTED: Item 2a Chroma->Qdrant (embedded) RagStore + migration (Brandon + Claude)

- DECISIONS (Brandon): do ALL of Phase 2; Qdrant runs EMBEDDED/on-disk (no server,
  mirrors Chroma's posture); task surfacing = ALL THREE surfaces (in-chat, OpenWebUI
  Tool/Function plugin, separate status panel). The stale chore/chroma-to-qdrant branch
  (50 behind main, dep-swap only) was abandoned -- starting fresh on main.
- ITEM 2a BUILT: services/api/ragstore.py -- backend-agnostic RagStore (server.py keeps
  computing fastembed vectors and passes them in). ChromaStore (mirrors prior behavior) +
  QdrantStore (qdrant-client local mode, lazy collection create at the embed dim, cosine,
  'kind' in payload). server.py routes memory_add/memory_query through make_store(RAG_BACKEND)
  -- default chroma until live parity is proven, then flip; /health gained rag_backend/
  rag_ok/rag_error (chroma_ok kept back-compat = ok && backend==chroma). qdrant-client added
  to requirements.txt. scripts/migrate_chroma_to_qdrant.py reuses stored vectors (no
  re-embed), idempotent.
- VALIDATED: tests/test_ragstore.py 22 checks incl. Chroma<->Qdrant parity; full offline
  suite 6/6; real-data migration (mem_default=8, mem_bob=1, global_memory=51, mem_alice=1 ->
  exact qdrant counts); live server.py qdrant smoke (rag_ok=True, dim=384, fact filter
  excludes 'note'). py_compile clean. OWED: flip RAG_BACKEND default + live multi-turn gate.

## 2026-06-19 0410 PDT -- KV-aware ctx sizing (GGUF-metadata-driven) + provisioner --tier closed (Brandon + Claude)

- DECISION (Brandon): the model provisioner + ctx sizing are a HARDWARE-SPEC-DRIVEN
  recommender (suggest/auto-download from the specs manage.py gathers); no manual tier
  taxonomy. Resolves both prior "pending decisions".
- KV-AWARE CTX SIZING: replaced provision_match's crude `quant > 0.85*budget -> min_ctx`
  step-down with a real KV-headroom estimate.
  * provision_fetch.py NEW: read_gguf_meta (stdlib GGUF header parser -> arch, n_layers,
    n_head, n_head_kv, n_embd, head_dim; header only, None on non-GGUF/truncated/missing);
    kv_dtype_bytes (real ggml block byte sizes for --cache-type-k/-v, f16 fallback);
    kv_bytes_per_token (K+V across layers); max_ctx_for_budget (clamp [min_ctx, ctx_default],
    floor 1024). resolve_ctx/config_kv gained a gguf_ctx arg.
  * provision_match.match now also returns ctx_default, min_ctx, vram_budget_mb.
  * manage.py NEW _gguf_ctx_for: free-for-KV pool = VRAM on full offload else RAM (budget -
    weights); cmd_provision computes it pre-download (preview) and RECOMPUTES from the real
    GGUF after download. --ctx-size is llama.cpp's TOTAL ctx (split across --parallel), so
    KV scales with ctx alone (no per-slot multiply).
  * resolve_ctx precedence: existing host-validated PERSONA_CTX (CAPPED to the GGUF fit) ->
    GGUF-derived fit -> matcher guess. Under-set is always the safe direction.
  * Constants are real ggml type sizes + read model metadata -- nothing invented (Brandon's
    rule). +23 offline checks (synthetic GGUF + KV math + precedence); full suite 5/5;
    py_compile clean. Live-validated reading a real gguf: qwen2-7B n_head_kv=4 head_dim=128
    -> 30464 B/tok (q8_0 K+V).
- provisioner `--tier` flag CLOSED as not-needed: selection is already hardware-driven
  (budget-fit + curated rank); the playbook's "Tier N" headers are documentation only.
- SCOPE: Phases 9-10 parked until 0-8 are all ironed out + green (Brandon).

## 2026-06-19 0345 PDT -- WSL GitHub SSH + origin push (backstop gap closed) (Brandon + Claude)

- Generated an ed25519 SSH key in WSL (~/.ssh/id_ed25519, no passphrase, perms 600);
  Brandon added the public half to GitHub. ssh -T git@github.com now authenticates
  ("Hi festro!").
- PUSHED main -> origin: fast-forward aa145fa..41cb82e (P3 + roadmap-runner + P4 + egress
  + docs). origin/main == local (0/0). The 6-commit offsite-backstop gap is closed.
- Decided AGAINST scp for the WSL<->D: hop: same physical machine, D: is a local /mnt/d
  mount, so rsync/cp over the mount (the existing -Stage pullback) beats scp on
  delta/excludes/--delete with no SSH hop. scp/rsync-over-SSH is the right tool only for
  the WSL/D: <-> EVO-X2 hop (Phase 9).
- WORKFLOW "deferred upgrade" (WSL clone as a real git checkout over SSH) is now UNBLOCKED
  -- the SSH-to-GitHub prerequisite is met; remains a Brandon decision, not an infra gap.

## 2026-06-19 0335 PDT -- Egress batch committed (3645431) + Windows read-only verify + doc-discrepancy fixes (Brandon + Claude)

- COMMITTED the egress batch to the canonical D:\ gateway (D:\Projects\Git\Project_Persona),
  commit 3645431: 12 files (egress_baseline.{sh,ps1} + design doc; manage.py egress bits;
  test_manage_pid +5; setup_native_stack.sh .env stop-write; profiles/default/config.yaml
  T1 pin; roadmap/changelog/todo; handoffs _2245 + _0052). Staged surgically (not git add
  -A: the WSL clone carries untracked runtime artifacts + a diverged tracked llama_cpp/).
  NOT pushed (origin/main behind by 5; push is milestones-only, pending Brandon).
- egress_baseline.ps1 Windows READ-ONLY verify DONE (PowerShell 5.1.26100 via WSL interop):
  -Plan / -Status / -Plan -Strict / -Plan -Provision all rc=0 with valid output (-Status
  correctly reports "NOT loaded"). Live -Apply/-Remove (admin) + Linux root live-apply still
  owed (would disrupt this dev surface).
- DOC DISCREPANCY FIXES: (1) roadmap self-note claiming knowledge.md + distributed_nodes.md
  "still call the mesh Phase 10 / keep a CrewAI Phase 9" was STALE -- both already use the
  06-14 numbering; replaced with an "all three docs agree" note. (2) SURFACED: two diverged
  Project_Persona git clones on D: -- D:\Projects\Git\Project_Persona (canonical, used by the
  sync script) vs D:\Projects\Project_Persona (stale, HEAD at P3); recommend deleting the
  stale one (pending Brandon -- did not delete a repo Claude did not create).

## 2026-06-19 0052 PDT -- Phase 0.5 egress baseline: design + per-OS scripts + doctor report (Brandon + Claude)

- DECISION (Brandon): the per-OS egress story is a HOST FIREWALL default-deny-outbound
  baseline NOW on the two primary surfaces; WireGuard mesh DEFERRED to Phase 9; delivery
  is SCRIPTED + documented, NOT auto-enforced by manage.py (no silent firewalling).
  Allowlist = loopback + internet only during provisioning/setup.
- NEW docs/egress_baseline_design_20260619.md: threat model (network-level half of egress
  containment; config-level half already exists), two postures (SERVE locked = loopback +
  established only; PROVISION = + DNS/HTTPS for downloads), per-OS mechanism, doctor
  read-only report, fit with the Phase 8 worker-jail + Phase 9 WireGuard, verify/rollback.
- NEW scripts/egress_baseline.sh (Linux/nftables): isolated table inet persona_egress,
  subcommands plan (default; pure text print) / status / apply [--provision] / remove;
  root-guarded; --yes for mutating ops; established,related accepted FIRST so apply over
  SSH does not cut the session; remove = clean total rollback. bash -n clean; plan output
  verified (valid nftables ruleset for both postures).
- NEW scripts/egress_baseline.ps1 (Windows Firewall): -Status/-Plan/-Apply/-Remove,
  -Provision, -Strict. Default = process-scoped outbound BLOCK for llama-server.exe (group
  PersonaEgress); -Strict = host-wide DefaultOutboundAction=Block + allow rules. Written +
  reviewed; LIVE WINDOWS VERIFY OWED (no PowerShell on the Linux dev surface).
- manage.py: NEW egress_posture(present, provision_open) pure classifier (serve/provision/
  none/unknown) + _probe_egress(root) read-only probe (nft list / Get-NetFirewallRule;
  never mutates); doctor gained a read-only "Egress baseline" section that REPORTS posture
  and points at the scripts when none is loaded. tests/test_manage_pid.py +5 egress_posture
  checks; offline suite 5/5. OWED: live-apply SERVE-lock test on a real box; iptables
  fallback. Local.

## 2026-06-19 0035 PDT -- Installer .env: keep read-fallback, stop writing (Brandon + Claude)

- OPEN QUESTION RESOLVED (Brandon): setup_native_stack.sh wrote the legacy
  run/llama-servers.env while run/config.toml is the committed source of truth -> KEEP
  manage.py's .env READ-fallback (the portability hedge for a no-tomllib / Python<3.11
  host, and for a missing/broken config.toml) but STOP the installer WRITING it (the only
  real drift source: the launcher ignores the .env whenever config.toml parses).
- Why this is safe: load_config (manage.py:165) reads the .env files ONLY as a fallback;
  with config.toml present they are never read. The API (server.py) reads os.environ that
  manage.py fills FROM config.toml, never the .env directly. All live bash lifecycle
  scripts that used to source the .env are archived. So nothing on a real host loses
  config; the stale written file just disappears.
- DONE: setup_native_stack.sh no longer writes run/llama-servers.env by default; an
  existing one is left untouched; FORCE_ENV=1 regenerates it for a no-tomllib host. Scope:
  only llama-servers.env was auto-written (config.env is committed/fallback-read only;
  start_api.sh is archived). bash -n clean. Local.

## 2026-06-18 2231 PDT -- Phase 0.5 LOCKED GREEN: standalone WSL/AMD-Linux lifecycle pass (Claude)

- Ran a clean standalone manage.py lifecycle in the WSL clone (the AMD-Linux-via-WSL
  Exit-Gate check, previously [~]): status -> doctor (all checks green incl. the T1
  safe-config gate) -> up (llama-server Qwen2.5-7B on CPU + FastAPI, both /health
  responding) -> test health (persona + API OK) -> /chat (real persona reply, no_think
  preset) -> down (clean teardown, no orphans, :8090/:8000 free). No bash; one entrypoint.
- Effective host config: host_tag=daemonic-pc -> config.daemonic-pc.toml selects
  Qwen2.5-7B-Instruct-Q4_K_M (CPU, GPU_LAYERS=0, PARALLEL=1, ctx 32768). llama-server
  b9620 CPU build at llama_cpp/build/bin; API via env/bin/python (venv 3.12.3).
- roadmap.md: Phase 0.5 -> [x] GREEN (both Exit-Gate surface checks now [x]: Windows x64
  2026-06-07 + AMD-Linux-via-WSL 2026-06-18); launcher Item -> [x]; Current position +
  lock line updated. Two NON-GATING Items remain as design-gated follow-ups (per-OS
  egress baseline; cross-OS installer/doctor parity) -- pending Brandon decisions.
- No git in this WSL clone (D:\ is the git gateway) -> edit/run/test only; the commit is
  owed to Brandon. Local.

## 2026-06-18 2225 PDT -- T1 safe-config gate restored: auxiliary providers auto->main (Claude)

- FOUND via manage.py doctor on WSL: the default profile's safe-config T1 gate FAILED --
  8 auxiliary tasks (skills_hub, approval, mcp, title_generation, triage_specifier,
  kanban_decomposer, profile_describer, curator) had provider=auto, but the project-side
  validator (manage.validate_safe_config) requires auxiliary.*.provider=main (route all
  auxiliary inference to the local main model; egress containment).
- ROOT CAUSE: Hermes' schema 0->28 migration (H1, 2026-06-12) added these new auxiliary
  tasks with its default provider=auto. H1 was validated with Hermes' own
  `hermes config check` (which passed); the project's doctor T1 gate was not re-run, so
  the regression went unnoticed (T1 last ran green 2026-06-04, before the migration).
- FIX: pinned the 8 auxiliary providers to main in persona/profiles/default/config.yaml
  (a tightening -- with providers:{} + no API keys, auto resolves to main anyway). doctor
  T1 gate green again (safe_config=pass); YAML re-parsed OK.
- config.yaml is git-tracked (no secrets). roadmap Phase 8 T1 note added. Local.
- FOLLOW-UP (note, not done): a normalizer (doctor --fix / init_profiles) could re-pin
  auxiliary providers automatically after any future Hermes schema migration.

## 2026-06-18 2215 PDT -- Phase 10 Item 10.0: offline regression suite green on Linux x64 (Claude)

- Ran tests/run_all_offline.py in the WSL clone via env/bin/python (venv 3.12.3): 5/5
  suites PASS (test_api_offline, test_hermes_bridge, test_manage_pid, test_provision_fetch,
  test_provision_match). This is the AMD-Linux-via-WSL = Linux x64 surface.
- With Windows x64 already green (2026-06-14, portable 3.11.9), both primary surfaces are
  now green -> roadmap Item 10.0 [~] -> [x]. NOTE: only the hardware-free offline portion
  of Phase 10; live / cross-host Items 10.1-10.5 still depend on Phase 9.
- Reconciliation also confirmed: py_compile manage.py OK; stale run/*.pid (7372/14032)
  were dead (handled by resolve_live_pid). No git in this clone. Local.

## 2026-06-18 1903 PDT -- Serving-side vision wiring: start_llama --mmproj (Claude)

- manage.py: NEW _truthy + _mmproj_args helpers; start_llama now appends
  `--mmproj <models/MMPROJ_PATH>` (verified flag `-mm/--mmproj` in llama_cpp/common/
  arg.cpp) when VISION_ENABLED is truthy AND the projector file is present. GATED:
  the provisioner fetches the mmproj regardless, but a headless node stays text-only
  until VISION_ENABLED is opted in (design sec 6). MMPROJ_PATH resolves under models/
  if not absolute; a missing projector warns and falls back to text-only.
- doctor: reports vision status (mmproj present + ON / unset+missing / OFF) in the
  Model file section.
- tests/test_manage_pid.py: +7 checks for _truthy + _mmproj_args (off/on/present/
  missing/no-path/absolute). Logic also verified sandbox-native (7/7) before publish.
- Closes the provisioner vision loop: provision writes MMPROJ_PATH/VISION_ENABLED ->
  start_llama now consumes them. OWED: a live serving smoke with an actual vision
  model + image (the deferred "Vision input" feature itself stays parked). Local.

## 2026-06-18 1858 PDT -- Roadmap re-scope: 0-8 = primary surfaces; multiplatform hardening -> 9/10 capstone (Brandon + Claude)

- DECISION (Brandon): Phases 0-8 build a solid working foundation on the two PRIMARY
  dev surfaces ONLY -- Windows x64 + AMD Linux via WSL (CPU) on Daemonic-PC. Broader
  portability (ARM64, non-Vulkan accel, EVO-X2-native GPU) is the multiplatform /
  troubleshooting CAPSTONE, folded into Phase 9 (migration to EVO-X2 + other systems +
  mesh) and Phase 10 (full-system + cross-host validation). Rationale: maximize WSL/
  Windows compatibility now so Phase 9 migration to EVO-X2 and other systems is clean.
- roadmap.md: added a PLATFORM SCOPE framing block; rewrote Current position; NARROWED
  Phase 0.5 to "Cross-OS foundation (Windows x64 + AMD Linux via WSL)" with its Exit
  Gate reduced to the two primary surfaces (Windows x64 [x] + AMD-Linux-via-WSL [~]).
  RELOCATED the former 0.5 hardware-gated checks -- EVO-X2-native Linux+Vulkan GPU
  lifecycle parity, Linux ARM64, non-Vulkan accel-selection proof -- to Phase 9
  (migration, Item 9.0 scope) + cross-host behavioral parity to Phase 10 Item 10.2.
  Net: 0.5 is UNBLOCKED from GREEN (no longer waits on EVO-X2/ARM64 hardware).
- knowledge.md: synced the portability pointer + Phase 9 entry to the new scope.
- The done 0.5 foundation (manage.py launcher, dep tiers, provisioner, IPC) stays the
  baseline phases 1-8 rely on -- only the cross-arch/cross-accel/other-hardware work
  moved. Docs only, local.

## 2026-06-18 1841 PDT -- Research/design: MCP gateway eval + Phase 9 federation prior art (Brandon + Claude)

- NEW docs/mcp_gateway_eval_20260618_1831.md: evaluation of MCPJungle (self-hosted MCP
  gateway) for the Phase 8/9 TOOL PLANE. License = MPL-2.0 (OSI-open, AGPL-compatible,
  file-level copyleft; standalone-process use imposes nothing on our code -> clears the
  bar). Fits as a per-node aggregation hub in front of Hermes' built-in MCP client; tool
  groups == the local-only tool whitelist; loopback + enterprise ACLs = egress chokepoint.
  Maturity snapshot (Tools/Prompts/groups stable; Resources/OAuth/GUI beta; audit logs
  limited; CLI stable; SQLite-direct so manage.py can supervise it). Verdict: adopt at
  Phase 8/9 when local-MCP-server or node count grows, NOT now. Docs only, local.
- docs/distributed_nodes.md +section 5c "Prior art: federation models (Matrix et al.)"
  (Brandon's framing): Phase 9 = "a federation of interconnectable yet independent
  systems" == Matrix's model. Maps Matrix mechanisms onto the sec 5/5b opens (signed
  event DAG -> node_id+keypair; m.room.server_acl -> deny-list/eviction; state resolution
  -> split-brain reconcile; power levels/auth rules -> re-key quorum; backfill -> cutover/
  rejoin). Brandon's "chatroom-as-feature" point: for a hardware/OS-agnostic personal
  assistant a synced (E2EE) cross-device conversation timeline is a FEATURE, elevating
  Matrix from prior-art toward candidate substrate. Fork parked in sec 9: reimplement on
  NATS+token (a) vs run a light homeserver (b) vs hybrid; + an offline/P2P survey (Briar/
  SSB/libp2p/Iroh/Veilid) needing current-status web research. Stamp -> 1841. Docs only, local.

## 2026-06-18 1816 PDT -- Phase 0.5 provisioner P4: first-run hook in cmd_up + installer --yes (Claude)

- scripts/provision_fetch.py: NEW model_resolvable(models_dir, configured) -- quiet
  mirror of manage.resolve_model()'s usable cases (configured PERSONA_MODEL present, or
  exactly one GGUF), so cmd_up can decide whether to trigger first-run provisioning.
- manage.py: NEW _maybe_first_run(root, cfg, args) called at the top of cmd_up. When no
  model is servable it offers provisioning interactively ([Y/n]) or, under `up --yes`,
  auto-provisions (cmd_provision with yes/write_config); on success it reloads cfg so
  start_llama sees the wired PERSONA_MODEL, and aborts cleanly (return 1) if the user
  declines or provisioning fails. `up` gained --yes + --hf-token. cmd_provision unchanged.
- scripts/setup_native_stack.sh: NEW AUTO_PROVISION=1 env gate -> runs `manage.py
  provision --yes` at the end (headless install path); next-steps text now points at
  `manage.py provision` (auto, host-fitted, Apache-2.0) alongside the manual model drop,
  and notes `up` auto-offers provisioning. Script keeps its +x bit (content-only edit);
  `bash -n` clean.
- tests/test_provision_fetch.py: +6 checks (model_resolvable: none / exactly-one /
  multiple / configured-present / configured-missing / missing-dir), 42/42 offline.
  cmd_up hook paths (present -> pass-through; decline -> abort; --yes -> auto-provision
  + cfg reload; provision-fail -> abort) smoke-verified with fakes.
- Provisioner P1-P4 now CODE DONE. OWED: Windows-side live-confirm of `up` first-run
  (e.g. temporarily unset PERSONA_MODEL with models/ empty); serving-side
  mmproj/VISION_ENABLED wiring; deeper KV-aware ctx sizing; `--tier`. All local.

## 2026-06-18 1758 PDT -- Provisioner P3 live-confirmed + ctx-preserve safeguard (Brandon + Claude)

- LIVE-CONFIRMED on Daemonic-PC (RX 9060 XT) via `provision --dry-run` (captured to
  logs/provision_dryrun.log; PowerShell Tee writes UTF-16): pick = qwen3.6-35b Q5_K_XL,
  weights [present] -> 0 MiB to download, per-host target config.daemonic-pc.toml
  [windows], vision off (no camera), nothing written. End-to-end pipeline good.
- FINDING: the matcher's tight-budget ctx step-down proposed PERSONA_CTX=8192 on a host
  that runs 16384 (the design's flagged P2 tunable). Root cause: ctx is penalized when
  the MODEL FILE exceeds 0.85*budget, but KV headroom is a separate pool.
- FIX (safeguard, not the full KV-aware rework): provision_fetch.resolve_ctx() + a
  widened config_kv(pick, existing_ctx). cmd_provision now passes the EFFECTIVE merged
  cfg PERSONA_CTX; when present it is preserved over the matcher's guess (host-validated
  value wins) and a note is printed. Fresh hosts (no existing ctx) still take the
  matcher's conservative value -- under-setting is the safe direction (won't OOM).
  Verified: Daemonic-PC case now wires 16384, not 8192.
- tests/test_provision_fetch.py: +6 checks (resolve_ctx + config_kv existing-ctx),
  36/36 offline. The deeper KV-aware ctx sizing stays a flagged follow-up. All local.

## 2026-06-18 1721 PDT -- Phase 0.5 provisioner P3: downloader + preflight + config wiring (Claude)

- NEW scripts/provision_fetch.py: the P3 stage of the first-run model provisioner,
  consuming a pick from scripts/provision_match.match(). disk preflight (free >=
  size+20%); license_gate (Apache-2.0/MIT/BSD ungated = happy path, gated needs an
  explicit HF_TOKEN, never auto-accept); build_plan (base GGUF + matching mmproj when
  vision, skip-if-present, total download MiB); download via huggingface_hub
  (resumable, network branch only) + verify_download light post-check; config_kv /
  config_block / wire_config = NON-DESTRUCTIVE [<os>] TOML edit (changed PERSONA_MODEL
  left as a `# was: ...` rollback breadcrumb, missing keys appended, missing section
  appended, idempotent on rerun); target_config_path prefers the active per-host
  config.<host>.toml when present, else config.toml.
- manage.py: NEW `provision` subcommand + cmd_provision + _filter_playbook. Flow:
  detect_host -> envelope -> match (honors --model / --text-only) -> print pick + plan
  + config block -> license gate -> (--dry-run stops here) -> disk preflight -> confirm
  (or --yes) -> download -> OPT-IN config wiring (--write-config or --yes; default just
  prints the block to protect the live serving config). Flags: --yes --model
  --text-only --dry-run --write-config --hf-token.
- NEW tests/test_provision_fetch.py: 30/30 offline (stdlib-only, 3.8+; no tomllib/no
  network) -- preflight math, license gate (open/gated/token), plan (vision mmproj,
  skip-present), kv/block render, wiring (replace+comment / append-key / missing-section
  / dry-run / idempotent / other-sections-preserved), per-host target selection,
  download dry-run + verify. Auto-discovered by tests/run_all_offline.py.
- DESIGN-vs-reality note: the provisioner design predates the per-host
  config.<host>.toml convention; the write target now resolves to the per-host file
  when one exists. OWED: Windows-side `manage.py provision --dry-run` live-confirm; P4
  (cmd_up first-run hook + installer --yes path); serving-side mmproj/VISION_ENABLED
  wiring (start_llama does not consume them yet); `--tier` (needs a playbook tier field).
- DOCS: roadmap Phase 0.5 provisioner line + design doc P3/P4 updated; the stale
  roadmap "capabilities llama_build=null" note corrected (that flake was fixed +
  verified-live 2026-06-07). All local.

## 2026-06-14 1535 PDT -- Mesh design: coordinated eviction + node_id (Brandon proposal captured) (Brandon + Claude)

- docs/distributed_nodes.md gained section 5b "Coordinated eviction + key rotation"
  (Brandon's design): (1) honest nodes gossip a bad-actor flag among themselves
  (excluding the actor) and JOINTLY rotate the shared token, distributing the new one
  only to known-good node ids; (2) nodes that missed the rotation are re-keyed OUT OF
  BAND via NFC/Bluetooth (+ QR/manual fallback for headless nodes); (3) a stable
  per-node id hashed from salted system specs at manage.py first boot, bound to the
  signing keypair, embedded in the message layer (Meshtastic-style).
- WHY IT MATTERS: turns section 4's "advisory" per-key deny-list into an ENFORCEABLE
  eviction -- node_id survives a re-key, so deny-by-node-id bites; token rotation
  becomes a concrete distributed action. Section 4 caveat + section 5 identity updated
  accordingly.
- OPENS flagged (section 9): re-key authorization quorum (avoid eviction-as-attack),
  cutover window (don't lock out slow honest nodes), split-brain reconcile, node_id
  spec/salt/re-enrollment, OOB transport choice. node_id = sybil DETERRENT not proof
  (specs spoofable); token rotation stays the hard guarantee.
- roadmap Phase 9 updated: node_id -> Item 9.3, coordinated eviction -> Item 9.4.
- Docs only; local.

## 2026-06-14 1520 PDT -- Phase 10 Item 10.0: one-command offline regression runner (Claude)

- NEW tests/run_all_offline.py (stdlib): auto-discovers tests/test_*.py, runs each as
  a subprocess with the current interpreter (cwd=repo), aggregates pass/fail, prints
  full output only for failures, exits 0 only if all pass. Future suites auto-included.
- First build of the new Phase 10 (full-system / feature test) capstone. roadmap Item
  10.0 -> [~] (flips [x] once green on Windows x64 AND Linux x64).
- OWED: run it Windows-side (portable 3.11.9) + on a Linux host. Local; no push yet.

## 2026-06-14 1500 PDT -- roadmap.md simplified (one vocabulary) + status refresh + EVO-X2 migration (Brandon + Claude)

- TERM CLEANUP (Brandon: "too many terms used interchangeably"): roadmap.md now uses
  exactly four nouns -- Phase / Item / Exit Gate / Status -- defined in a new "Terms"
  section. Retired the loose synonyms "track", "milestone", "stage", "leg" (old
  changelog/handoff entries read them as Item or Exit Gate). Every Exit Gate is now a
  checklist (each condition its own [x]/[~]/[ ]) instead of prose, so partial states
  (e.g. the Linux x64 / ARM64 portability checks) are visible per-line.
- IDs KEPT (Brandon: keep but standardize): T0-T4 / H1-H6 / M* kept verbatim so history
  resolves; treated as Item IDs, not a separate hierarchy. Phase 10 mesh "Stage 0-4"
  renamed to Items 10.1-10.5 (kills the collision with the orchestrator's -Stage flags;
  mapping noted in the Phase 10 intro).
- STATUS REFRESH (was stamped 2026-06-07, stale): Phase 1 flipped [~] -> [x] GREEN
  (all Items closed, M6 last 2026-06-08; Exit Gate proven 2026-06-07). "Current
  position" rewritten: Phases 0+1 GREEN; Phase 0.5 in progress (Win x64 proven, Linux
  x64 mostly via EVO-X2, ARM64 deferred on hardware); active focus = Phase 8 H2, next
  lock = Item H2d on EVO-X2. H2 sub-items folded under one [~] H2 with H2a/b/c [x],
  H2d [ ].
- EVO-X2 MIGRATION added as Item 9.0 [~] (Brandon): consolidate the full stack onto
  EVO-X2 as the anchor node (endgame: everything on EVO-X2); 35B + Hermes already
  there, native persona+API+Hermes + H2d still owed. Added to the mesh Exit Gate.
- PHASE 9/10 SWAP (Brandon): the deleted CrewAI "Phase 9" tombstone is gone; the
  decentralized node mesh moved from Phase 10 -> Phase 9 (Items renumbered 9.0-9.5,
  EVO-X2 migration = 9.0). NEW Phase 10 = "Full-system / feature test" capstone
  (one-command regression suite, live system playbook, cross-host parity, failure
  injection, system-level egress check, perf baseline; all [ ]). Cross-refs updated
  in-file.
- REPO-WIDE NUMBERING SYNC (done, not owed): updated every LIVE doc that called the
  mesh "Phase 10" -> knowledge.md (architecture roadmap entry rewritten: Phase 9 =
  mesh, new Phase 10 = system test; 2 inline refs), docs/distributed_nodes.md (Phase 9
  + a Stage<->Item map: Stage 0-4 = Items 9.1-9.5, 9.0 = EVO-X2 migration),
  docs/ipc_decision.md, docs/portability_audit.md, docs/llama_build_matrix.md
  (Stage 2 -> Item 9.3). FROZEN/left as-is: changelog history (append-only) + archive/
  + dated audit notes keep their original numbering as point-in-time records.
- Docs only; no code touched. Local (push at the next milestone).

## 2026-06-14 1407 PDT -- manage.py WSL stale-pidfile robustness fix (D closed) (Claude)

- ROOT CAUSE: in WSL the recorded pid could read dead (pid_alive False) while the
  server's /health was still up -> status lied ("stale pidfile") and `down` orphaned
  the live server (stop_named saw the dead pid, deleted the pidfile, and walked away).
  This was the stale-server trap noted in handoff 0014 / todo.
- FIX (manage.py): added http_health_up(url) (reuses http_get_json), pids_by_cmdline(
  needles) (dependency-free /proc cmdline scan; Linux/WSL only, [] on Windows), and
  resolve_live_pid(pid, health_url, needles) -- trusts the recorded pid, else if /health
  is up recovers the REAL pid from the process table.
- stop_named() now takes (health_url, needles) and kills the resolved live pid instead
  of just unlinking the pidfile; recovers even a fully orphaned server (no pidfile but
  /health up). cmd_down passes per-service markers: api -> :8000 /health + "server:app";
  persona -> :PERSONA_PORT /health + ["llama-server","--port <port>"]. Aux servers
  (scientist/reasoning/coder/persona_win) keep prior behavior (back-compat defaults).
- cmd_status() now corroborates pid with /health: flags "running but /health down" and
  the WSL trap ("/health UP on real pid N; pidfile pid M stale") instead of a bare
  "stale pidfile". Windows path unchanged (scan returns [] -> existing behavior).
- TEST: tests/test_manage_pid.py (new, stdlib, offline) -- 11 checks monkeypatching
  pid_alive/http_health_up/pids_by_cmdline/terminate_pid: resolve_live_pid (4 cases) +
  stop_named (stale-but-up, dead+down, orphan, normal). GREEN on portable 3.11.9 11/11;
  test_api_offline.py also re-confirmed 84/84.
- LIVE CONFIRM (WSL, Daemonic-PC 7B, 1427): scripts/verify_pid_recovery.sh (new,
  reusable on any Linux host) started the real 7B (pid 480), injected a stale pid (517),
  and proved status surfaced "/health UP on real pid 480" and `down` killed the REAL pid
  480 with NO orphan left on :8090. The bug class is closed in practice, not just in unit
  logic. Run: PERSONA_HOST=daemonic-pc bash scripts/verify_pid_recovery.sh.
- All local; nothing pushed yet.

## 2026-06-14 0014 PDT -- Session close: workflow keep/pass merged to AGENTS.md/WORKFLOW; handoff (Brandon + Claude)

- Keep/pass catalogue (docs/workflow_patterns_review_20260613_2112.md) finalized and
  merged into the official files: D:\Projects\AGENTS.md gained a "How to run a session"
  section (one-command-then-read loop, ground-in-logs, verify-runtime, concise,
  AskUserQuestion discipline, USE+MAINTAIN the TaskCreate widget incl. side tangents,
  record negative results, PowerShell native-stderr, git push cadence); project
  WORKFLOW.md carries the source-of-truth/sync + per-host config + WSL gotchas.
  Decisions: #7 (preamble) PASS; #12 (task widget) KEEP -- maintain it, useful for
  tangents (Brandon); #15 clarified (git push = milestones; local WSL<->D:\ sync is the
  frequent redundancy, separate mechanism); #18 done (per-host config).
- Connected D:\Projects to edit the cross-project AGENTS.md (revised stamp 2026-06-14).
- Session-close handoff: archive/handoffs/handoff_persona_20260614_0014.md.
- All local; nothing pushed. NEXT = commit+push (Windows-side), then EVO-X2 Exit Gate.

## 2026-06-13 2340 PDT -- Source-of-truth model finalized + bidirectional sync + revalidated (Brandon + Claude)

- SOURCE-OF-TRUTH MODEL (Brandon, final): GitHub origin/main = durable backstop;
  WSL clone = PRIMARY dev/run surface (closest to the EVO-X2 target); D:\ repo =
  REDUNDANT copy + Windows multi-platform testbed + git gateway to origin (holds the
  only .git; survives Windows reinstall on the D: drive). Keep BOTH folders synced.
  Supersedes the 2205 "D:\ is the single source of truth" framing. Memory updated
  (project-persona-source-of-truth); review doc section 0 + WORKFLOW pending merge.
- scripts/wsl_h2_sim.ps1: new "pullback" stage (reverse sync WSL -> D:\ via rsync;
  -Prune for --delete) so WSL-primary work flows back to the durable D:\ copy.
  Protects .git, models/, env*, llama_cpp/, portable/, runtime (Windows-only + heavy
  artifacts never touched). Forward "sync" (D:\ -> WSL) unchanged. Direction is manual
  (whoever changed last pushes to the other).
- REVALIDATION after the per-host-config refactor + source-of-truth churn: -Stage sync
  carried the new manage.py + config.daemonic-pc.toml into the clone and reconciled its
  stale patched config.toml; -Stage model/up showed host_config=config.daemonic-pc.toml,
  model=Qwen2.5-7B, /health ok; -Stage smoke sim-004 / t_f9c45966 reached status="ok"
  (~26 min) with summary mirrored + finished_at + worker_session_id. Nothing broke; the
  committed per-host path is equivalent to the old clone patch.
- KNOWN ISSUE (pre-existing, not from this change): manage.py status reports persona/api
  pidfiles "stale/not alive" even when both /health respond -- the pidfile pid doesn't
  match the real process in WSL. Cosmetic for runs (smoke checks /health), but it is the
  mechanism behind the stale-server trap (down may miss the server). Reliable checks:
  /health + `ps ... gguf`; force-kill with pkill -9 -f llama-server. Robustness fix owed.

## 2026-06-13 2205 PDT -- Source-of-truth amendment: committed per-host config (Brandon + Claude)

- AMENDMENT (Brandon): the D:\ repo is the SINGLE SOURCE OF TRUTH and durable store
  (D: drive + git remote survive a Windows reinstall); the WSL clone lives on C: and
  is disposable/derived. No authored work may live only in the clone; per-host
  differences must be COMMITTED host-aware config in D:\, not an ephemeral clone patch.
  Recorded in memory (project-persona-source-of-truth) + the keep/pass review doc.
- IMPLEMENTED (Option A, host-selected per-host config files):
  - manage.py: host_tag() (lowercased short hostname; PERSONA_HOST env overrides) +
    _merge_host_overrides() merges run/config.<host>.toml AFTER [base]/[runtime]/[<os>];
    `status` prints host_config=... when one applies.
  - run/config.daemonic-pc.toml (COMMITTED, tracked): Windows+WSL2 box override
    (Qwen2.5-7B-Instruct-Q4_K_M, ctx 32768, PERSONA_PARALLEL=1, ngl 0). Canonical
    run/config.toml [linux] stays the EVO-X2 35B target, so EVO-X2 needs no file.
  - wsl_h2_sim.ps1: the "model" stage NO LONGER patches the clone's config.toml (the
    7B-vs-35B clone divergence is retired). It only caches the gguf
    (-PersonaModel/-ModelUrl), reloads, and prints the effective merged config.
    Dropped -PersonaCtx/-PersonaParallel (now owned by the committed per-host file).
  - .gitignore: noted run/config.toml + run/config.<host>.toml are tracked source of
    truth (no broad run/*.toml ignore).
  - Verified off-mount: daemonic-pc merges to 7B/parallel=1/ngl=0; a host with no
    override file stays canonical 35B.
- ADOPTION: run wsl_h2_sim.ps1 -Stage sync once (carries the updated manage.py +
  config.daemonic-pc.toml into the clone), then -Stage up; confirm `status` shows
  host_config=config.daemonic-pc.toml and model=Qwen2.5-7B. Local edits only.

## 2026-06-13 2112 PDT -- Phase 8 track C COMPLETE: WSL-green, literal ok+summary (Brandon + Claude)

- MILESTONE (WSL-green achieved): self-contained task sim-003 / t_ad33008e finished
  status="ok", card "done", run #24 completed in 1618s (~27 min) on the CPU 7B. The
  bridge mirrored the terminal state back to /jobs WITH the agent's summary
  ("The task-board bridge receives tasks from a delegating API, breaks them down...
  reports back ... upon completion."), finished_at + worker_session_id recorded. Full
  chain proven on a capable model: delegate -> bridge create -> dispatch -> spawn ->
  agent tool loop -> kanban_complete -> ok+summary mirrored. This is the de-risking
  milestone; the real H2 Exit Gate (ok+summary on EVO-X2 35B w/ GPU + egress-off) is
  unchanged. Confirms sim-002's "blocked" was correct agent behavior (bad path), not a
  defect: ok and blocked both mirror correctly via mirror_outcomes.
- Track C net: model-swap support + the 7B WSL completion are done. NEXT = EVO-X2 35B
  (handoff 1504 section B) and the A-track Windows confirm+commit.

## 2026-06-13 1957 PDT -- Phase 8 track C: 7B ran the FULL tool loop; bridge mirrored a terminal state (Brandon + Claude)

- KEY RESULT: the 7B worker drove the complete Hermes tool-calling loop on sim-002 /
  t_8325c4dc -- worker log shows kanban_show -> read(<file>) -> kanban_block. It
  reached a TERMINAL Hermes state and the bridge mirrored it back to /jobs as
  status="blocked" with block_reason "File not found: h2_bridge_design_..md". That is
  a full, correct end-to-end cycle (delegate -> real multi-tool execution -> terminal
  state -> mirrored with reason). The 1.5B never made a single tool call; the 7B made
  several and self-blocked correctly. Bridge + capable-model tool loop = PROVEN.
- The "blocked" (not "ok") is a TASK/workspace detail, not a bridge/model defect:
  Hermes runs the worker in an isolated scratch workspace
  (run/hermes_kanban/kanban/workspaces/t_8325c4dc, empty), so the repo-relative path
  "docs/h2_bridge_design_..md" resolved inside that empty dir -> not found. The agent
  correctly blocked instead of hallucinating. "ok" mirrors via the same
  mirror_outcomes path; banking a literal green ok needs a self-contained (no-file)
  task -- re-run queued as sim-003.
- Net: track C de-risk goal fully met. Remaining gap to a literal ok+summary is a
  task-design tweak; the real ok+summary Exit Gate still belongs on EVO-X2 (GPU).

## 2026-06-13 1945 PDT -- Phase 8 track C: 7B drives the loop on CPU; WSL+AMD has no GPU; diagnostics added (Brandon + Claude)

- RESULT (bridge re-proven with a CAPABLE model): swapped the WSL sim to
  Qwen2.5-7B-Instruct-Q4_K_M and ran delegate -> bridge create -> dispatch -> spawn
  -> mirror. Job sim-002 / card t_8325c4dc: claimed (run 23), spawned (pid 7384),
  heartbeating, status mirrored to /jobs. The 7B DRIVES the agent tool loop -- it
  completed turn 1 (generated tokens) and advanced to turn 2 -- which the 1.5B never
  did (0 tool calls). Track C's de-risk goal (a capable model exercises the bridge's
  tool loop end to end) = MET.
- THROUGHPUT (from logs/persona.log): pure CPU, ~18 tok/s prefill. Each agent turn
  re-prefills the ~22k-token Hermes orientation prompt (prompt-cache miss, sim~0.19)
  = ~15-20 min PER TURN; llama-server pegged at ~1200% CPU. A full task is ~1-2h on
  CPU. Functional, not practical -- completion is throughput-gated, not a defect.
- GPU OFFLOAD NOT AVAILABLE IN WSL2 FOR THIS AMD CARD (caps probe): /dev/dxg present
  but vulkaninfo enumerates ONLY llvmpipe (software, deviceType CPU). RADV
  (radeon_icd) needs /dev/dri, which WSL2 does not expose; Mesa Dozen did not bring
  up a device. The shipped llama.cpp is a CPU-only build (--list-devices empty).
  => GPU completion belongs on EVO-X2 (Strix Halo, real Ubuntu, /dev/dri, RADV) =
  the H2 Exit Gate target anyway; or a future Windows-native llama-server + WSL
  Hermes split via mirrored networking. DECISION (Brandon): let the CPU 7B finish
  this run for a WSL completion; GPU stays on EVO-X2.
- scripts/wsl_h2_sim.ps1 hardening this session: stream WSL output live (per-line,
  was buffered via Out-String) so long stages show progress; wrap the native wsl
  call in ErrorActionPreference=Continue (curl/native stderr no longer throws
  NativeCommandError under -ErrorAction Stop); curl --no-progress-meter; timestamp
  each smoke/mirror tick; new "logs" stage (tails WSL persona/api/worker logs into
  logs/wsl_h2_sim.log) and "caps" stage (GPU/Vulkan/llama-backend probe); the
  "model" stage now tears the stack down after patching so 'up' reloads the new
  model (manage.py up skips a live server -- this bit us: a stale 1.5B server kept
  serving until force-killed).
- Local edits only, nothing pushed.

## 2026-06-13 1617 PDT -- Phase 8 track C: WSL sim model-swap support (Qwen2.5-7B-Instruct) (Brandon + Claude)

- scripts/wsl_h2_sim.ps1: added a sim-model override so the WSL run can use a
  tool-calling-capable small model instead of the 1.5B that could not drive
  Hermes' tool loop. New params -PersonaModel / -PersonaCtx / -PersonaParallel /
  -ModelUrl; new "model" stage (runs after sync, before setup in the all-pipeline).
  The stage fetches the GGUF into the WSL clone's models/ (curl -fL -C -, resumable;
  only if absent) and patches the WSL clone's run/config.toml in place -- table-aware:
  [linux] PERSONA_MODEL/PERSONA_CTX and [base] PERSONA_PARALLEL only; [windows] and
  the D:\ repo config.toml are left untouched (35B stays the real EVO-X2 target).
  Override is sim-only and lives in the WSL clone. Header log now records the model.
- Recommended model: bartowski/Qwen2.5-7B-Instruct-GGUF, Qwen2.5-7B-Instruct-Q4_K_M.gguf
  (4.68 GB, single file, Apache-2.0 -- OSI-open, fits the model-license default). Ships
  the Qwen2.5 tool-calling chat template, which is what manage.py's llama-server --jinja
  needs to surface tool calls.
- Caveat recorded: Qwen2.5-7B native context caps at 32K (128K only with YaRN). Run
  PERSONA_PARALLEL=1 so the full 32K is one KV slot for the ~22k worker prompt; the
  profiles stage still declares context_length=65536 to Hermes (its >=64K gate) -- that
  declared value is decoupled from the 32K llama-server serves, fine as long as a single
  request stays under 32K.
- Patcher verified off-mount (sample config.toml round-trips through tomli: linux model
  swapped, base parallel=1, windows untouched). No change to default behavior when
  -PersonaModel is omitted (ctx/parallel guards skip on "0").
- Local edit only, nothing pushed. NEXT = Brandon runs the staged WSL flow with the swap.

## 2026-06-13 1504 PDT -- Session close: consolidating handoff + log moved to logs/ (Brandon + Claude)

- Session-close handoff: archive/handoffs/handoff_persona_20260613_1504.md -- full arc
  (carried fix-its -> H2 bridge decision -> H2a design -> H2b/H2c code -> real-shape
  reconcile -> WSL live validation), current state, and the EVO-X2 Exit-Gate next steps.
- scripts/wsl_h2_sim.ps1: log path moved run/ -> logs/wsl_h2_sim.log (designated logs
  dir); .gitignore + doc refs updated. Orphan run/wsl_h2_sim.log can be deleted.
- All local commits, nothing pushed.

## 2026-06-13 1458 PDT -- Phase 8 H2d: bridge VALIDATED live in WSL (completion model-gated) (Brandon + Claude)

- MILESTONE: the H2 bridge ran end to end on Windows WSL2 (everything-in-WSL:
  llama qwen2.5-1.5b + persona API + Hermes v0.16.0 + tools/hermes_bridge.py, all
  on the WSL native fs). PROVEN live: POST /agent/delegate -> bridge creates the
  Hermes card (hermes_task_id recorded) -> dispatcher CLAIMS -> SPAWNS worker ->
  worker runs the real agent (connects to persona :8090/v1, gets task+orientation)
  -> terminates -> bridge MIRRORS every state (delegated->running->error/blocked)
  back into /jobs with attempts/started_at/finished_at. Correlation + idempotent
  create + lifecycle mirror all confirmed against the REAL Hermes, not a fake CLI.
- COMPLETION NOT reached, by design of the sim model: the 1.5B can't drive Hermes'
  tool-calling loop -- worker log showed "Messages: 2 (1 user, 0 tool calls)" and
  "I'm sorry, I can't continue" (it never calls kanban_show()/kanban_complete()).
  Model-capability floor, NOT a bridge defect. The real target (EVO-X2 Qwen3.6-35B,
  which Hermes' >=64K-context requirement is built for) is expected to complete.
- INTEGRATION FINDINGS (all live-confirmed; critical for EVO-X2):
  1. Hermes resolves the "default" kanban assignee's HERMES_HOME to the ROOT
     (<root>=persona), reading <root>/config.yaml -- NOT persona/profiles/default/
     config.yaml. The project's "profile dir = HERMES_HOME" convention collides;
     FIX applied: seed persona/config.yaml from the default profile (or use NAMED
     profiles, which map to persona/profiles/<name>/ as Hermes expects).
  2. Hermes enforces >=64K context on the MAIN model AND every auxiliary model
     (compression, decomposer, etc.), each detected separately. Override per-model
     via model.context_length + auxiliary.<name>.context_length for sub-64K models.
  3. llama PERSONA_CTX is split across PERSONA_PARALLEL slots (per-slot = CTX/PAR).
     Hermes' ~22k-token worker prompt needs one large slot -> PERSONA_PARALLEL=1
     (or raise CTX). At PAR=4/CTX=32768 the 8192/slot 400'd "exceeds context".
  4. Pin HERMES_KANBAN_HOME so the dispatcher + bridge share one board
     (run/hermes_kanban/kanban.db); confirmed live.
  5. setup_native_stack.sh uv Hermes flow + init_profiles + kanban init all worked
     live on WSL (the carried installer fix is now real-world proven).
- TOOLING: scripts/wsl_h2_sim.ps1 -- staged WSL orchestrator (preflight/sync/setup/
  profiles/up/dispatch/smoke/mirror/status/down) that tees clean UTF-8 output to
  logs/wsl_h2_sim.log (Windows-side). Fixes this session: base64->tempfile transport
  (heredoc/stdin-safe), $body/$Body case-collision (PS dynamic scope), Out-Null
  output-swallow, console UTF-8 + ANSI-strip (mojibake), -SkipDeps, context/aux
  overrides + PARALLEL note baked into the profiles stage, the mirror stage.
- The sim-only config overrides (context_length lies, PARALLEL=1) are NOT needed on
  EVO-X2's real 35B model; they exist purely so a tiny CPU model could be exercised.
- Local commit only (WSL clone is separate; D: repo edits here). git Windows-side.

## 2026-06-13 0423 PDT -- Phase 8 H2: wsl_h2_sim.ps1 transport fixes; preflight+sync green on WSL (Brandon + Claude)

- scripts/wsl_h2_sim.ps1 two fixes after live runs on Daemonic-PC WSL2 (Ubuntu-24.04):
  (1) QUOTING: Windows PowerShell 5.1 mangled embedded shell quotes crossing PS ->
  wsl.exe -> bash (a `$(... echo 'absent (..)' ...)` line died with `127`,
  "syntax error near unexpected token `('"). Fix: base64-encode the expanded bash
  body in PS and decode in WSL -- `wsl -- bash -lc "echo <b64> | base64 -d | bash"`.
  Immune to quote/space/newline mangling for every stage. (2) OUTPUT: the stage
  dispatcher piped Invoke-Wsl to Out-Null (to drop the returned exit int), which also
  swallowed all WSL stdout. Fix: Invoke-Wsl no longer returns the code; dropped the
  Out-Null. VERIFIED live: -Stage preflight prints uname/python3.12.3/git/uv-absent/
  AI_ROOT, -Stage sync tars the tree into ~/Git/Project_Persona. NEXT live step:
  -Stage setup (llama build + uv Hermes install; WSL can fetch CPython 3.11 unlike the
  sandbox). Local commit only.

## 2026-06-13 0330 PDT -- Phase 8 H2: WSL sim orchestrator (scripts/wsl_h2_sim.ps1) (Brandon + Claude)

- scripts/wsl_h2_sim.ps1: a staged PowerShell driver for the everything-in-WSL H2
  sim (companion to docs/wsl_h2_runbook_20260613_0311.md). Stages: preflight | sync
  (tar the Windows working tree -- incl. uncommitted edits -- into the WSL native fs,
  excluding .git/models/llama_cpp/venvs) | setup (the updated setup_native_stack.sh,
  CPU by default, -Gpu to opt into Vulkan) | profiles (init_profiles + kanban init) |
  up (manage.py up + /health) | dispatch | smoke (POST /agent/delegate -> loop
  kanban dispatch + hermes_bridge --once -> poll /jobs/<id> to a terminal status) |
  status | down. Pins HERMES_KANBAN_HOME so the bridge + dispatcher share one board.
  Params: -Distro -RepoWin -WslRepoRel -Stage -Gpu -SkipHermes -JobId -Title -Body
  -DispatchTicks -TickSleep. Default `-Stage all` leaves the stack up. Not executed
  here (Windows/WSL only). Local commit only.

## 2026-06-13 0311 PDT -- Phase 8 H2: real Hermes shapes confirmed + bridge reconciled + WSL runbook (Brandon + Claude)

- DIRECTION (Brandon): stage H2 on Windows WSL2 (everything-in-WSL) before EVO-X2;
  Hermes is Linux/WSL2-only so WSL faithfully mirrors EVO-X2. Migrate when stable.
- SANDBOX SOURCE DIVE: cloned hermes-agent v0.16.0 @ 9b1e0d6f in the Ubuntu sandbox
  (uv 0.11.19 present; full install blocked -- uv could not fetch CPython 3.11, host
  not allowlisted -- so validated against SOURCE, which is authoritative). Resolved
  most H2 open questions:
  * kanban board is SHARED ACROSS PROFILES -- kanban_home() walks HERMES_HOME=
    <root>/profiles/<name> UP to <root>; default DB = <root>/kanban.db (NOT the
    profile dir). PIN HERMES_KANBAN_HOME so bridge + dispatcher agree.
  * `kanban create --json` = bare task dict (.id). `kanban show --json` = WRAPPED
    {"task":{...}, "latest_summary", "runs":[{outcome,summary,error,metadata,
    ended_at}], "events":[...]} -- no block_reason/log_path keys; block reason lives
    in the blocked run's summary/error; tasks.result usually null (handoff = latest
    run summary). status set: triage/todo/scheduled/ready/running/blocked/review/
    done/archived. dispatcher: `kanban dispatch` (one pass) or `gateway start`
    (embedded 60s); standalone --daemon deprecated.
- BRIDGE RECONCILED (tools/hermes_bridge.py): derive_update now reads the WRAPPED
  show payload (task.* under "task", top-level "runs", block reason from run
  summary/error, metadata json-string tolerant, finished_at from ended_at);
  _COLUMN_MAP updated to the real status set (review->blocked, scheduled->None,
  +archived). tests/test_hermes_bridge.py updated to the real shapes -- 44/44 ALL
  PASS off-mount (re-run via heredoc into the sandbox-local fs; the 9p mount served
  a stale truncated read of the edited files -- known gotcha).
- WSL RUNBOOK: docs/wsl_h2_runbook_20260613_0311.md -- everything-in-WSL topology,
  install (updated uv flow), env pinning (HERMES_KANBAN_HOME), dispatcher options,
  and the delegate->dispatch->mirror smoke that is the H2d gate. Confirmed findings
  baked into section 0; the design doc's open-questions section updated with
  RESOLVED/LIVE-CONFIRM status.
- .gitignore: run/hermes_kanban/ (kanban runtime) + tools/_mount_probe.txt (a probe
  file the sandbox could not unlink -- DELETE Windows-side: del tools\_mount_probe.txt).
- STILL LIVE-ONLY (the point of the WSL sim): worker safe-config/egress inheritance,
  gateway headless footprint, timeout tuning. Local commit only (mid-phase).

## 2026-06-13 0256 PDT -- Phase 8 H2b+H2c: delegate endpoint + hermes_bridge.py (off-mount green) (Brandon + Claude)

- H2b (persona side, services/api/server.py): new POST /agent/delegate writes a
  Task Board row at status="delegated" kind="hermes_delegate" (title/body/assignee/
  tenant/priority/delegated_at) and does NOT run taskman2 -- the bridge executes it.
  Guards: title required (400), duplicate job_id (409). /health gains a "delegate"
  block (default_assignee/default_tenant; env DELEGATE_DEFAULT_ASSIGNEE/_TENANT).
  Existing /agent/run inline path untouched.
- H2b tests (tests/test_api_offline.py): +~10 checks -- delegate returns delegated,
  row kind/timestamps, did-NOT-run-taskman2, no hermes_task_id yet, missing-title
  400, dup 409, delegated/blocked statuses round-trip /jobs, /health delegate block.
  NOT run here (needs the pinned FastAPI chain); py_compile OK off-mount. OWED:
  Windows-side portable 3.11.9 full-suite run (expect 72 + the new checks all PASS).
- H2c (tools/hermes_bridge.py, NEW, stdlib-only): the bridge. Pure helpers
  (map_hermes_status, map_hermes_column, build_create_args, parse_created_id,
  derive_update) + Flow A enqueue_delegated (create cards for delegated rows lacking
  an id; idempotent on hermes_task_id; inflight marker for reconcile) + Flow B
  mirror_outcomes (read `hermes kanban show --json`, map running/ok/error/timeout/
  blocked + summary/metadata/log_path back) + tick() + a main() polling loop. runner
  + board are INJECTED for testability; transport = Hermes public CLI, not raw DB.
- H2c tests (tests/test_hermes_bridge.py, NEW): faked `hermes` CLI + in-memory board.
  43/43 ALL PASS off-mount (python3, stdlib). Covers the status map, create
  idempotency (two delegated -> two creates, re-run creates nothing), running/
  completed/blocked mirroring with summary+metadata+log_path, terminal failure
  derive, and tick().
- STILL OWED before H2 Exit Gate: H2d EVO-X2 live wire (the 7 open questions in the
  design doc -- kanban.db path under HERMES_HOME, --json shapes, headless dispatcher
  mode, assignee/egress inheritance, tenant scoping, timeouts) + the Windows-side
  offline-suite confirmation for the server.py change. Design only ran the bridge
  unit suite live; no model/Hermes touched.
- Local commit only (mid-phase). Files: server.py, tests/test_api_offline.py,
  tools/hermes_bridge.py (new), tests/test_hermes_bridge.py (new), knowledge.md.

## 2026-06-13 0204 PDT -- Phase 8 H2a: bridge design doc (taskboard.py <-> Hermes kanban) (Brandon + Claude)

- docs/h2_bridge_design_20260613_0204.md: full design for H2's chosen BRIDGE
  architecture. taskboard.py / persona /jobs stay canonical; Hermes' native kanban
  is the execution substrate for delegated work; a one-process bridge on EVO-X2
  keeps them consistent (loopback only, no new egress).
- Researched Hermes' kanban from the v0.16.0 docs (tutorial + worker-lanes +
  overview): lifecycle ready->running->blocked/done/archived, task_runs +
  task_events tables, kanban_* worker tools, the HERMES_KANBAN_* spawn env, the
  --json CLI, and the (not-yet-paved) external-worker-lane contract.
- Key design calls: (a) transport = Hermes PUBLIC surface (`kanban create --json`
  + `kanban watch/runs --json`) NOT raw DB writes; (b) two new persona statuses
  "delegated" + "blocked" added additively (existing running|ok|error|timeout
  untouched); (c) status/field/payload mapping tables; (d) correlation = our
  job_id <-> hermes_task_id captured at create, merge-idempotent mirroring with a
  last_event_seq high-water mark + reconcile-on-boot; (e) Hermes owns retry/circuit
  breaker, the bridge only mirrors outcomes.
- Implementation plan H2a(done)/H2b(persona delegate entry + status tests,
  off-mount)/H2c(tools/hermes_bridge.py + faked-CLI unit tests, off-mount)/H2d(EVO-X2
  live wire = the Exit-Gate evidence)/H2e(docs). 7 open questions flagged for EVO-X2
  confirmation (kanban.db path under HERMES_HOME, --json shapes, headless dispatcher
  mode, assignee/profile + egress inheritance, tenant scoping, timeouts).
- Design only; no code. Local commit only (mid-phase).

## 2026-06-13 0049 PDT -- Carried fix-its: installer uv flow + stale model name + gitignore (Brandon + Claude)

- scripts/setup_native_stack.sh: replaced the wrong `pip install hermes-agent` block
  with the uv editable flow actually used on EVO-X2 (changelog 2311). Now: install
  user-local uv if missing (astral install.sh -> ~/.local/bin), clone
  NousResearch/hermes-agent to $HERMES_SRC (default ~/src/hermes-agent), checkout
  $HERMES_REF (default 9b1e0d6f), `uv venv env_hermes --python 3.11`, then
  `uv pip install --python env_hermes/bin/python -e $HERMES_SRC[all,dev]`. Repo/ref/src
  all env-overridable; graceful WARN if uv unavailable. Closes the 2311/2339 carried
  fix-it. Syntax-checked (bash -n) off-mount.
- Same file: env writer + next-steps echo still emitted the RETIRED
  Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf. Swapped to the canonical single model
  Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf (matches config.toml [linux]/[windows]). A fresh
  EVO-X2 setup would otherwise have written the wrong PERSONA_MODEL into the .env
  fallback. (config.toml stays primary; this is the fallback writer only.)
- .gitignore: added `models/archive/` (previously only models/*.gguf was ignored, so
  the archived Instruct gguf on EVO-X2 showed as untracked).
- H2 DIRECTION (Brandon): the kanban lean is BRIDGE taskboard.py <-> Hermes' native
  kanban (was "leaning native" in the 2311/2339 notes). taskboard.py / persona /jobs
  stay the canonical board the persona surfaces; H2 wires a bridge to Hermes'
  HERMES_KANBAN_*. No code yet -- decision recorded for the H2 session.
- Mid-phase = LOCAL COMMIT ONLY, no push (per the push-at-milestones rule). Edits are
  Windows-clone files; git runs Windows-side.

## 2026-06-12 2311 PDT -- Phase 8 Hermes: T1 close-out (env_hermes) + H1 config validated (Brandon + Claude)

- MILESTONE: Phase 8 H-track started. hermes-agent INSTALLED on EVO-X2 and H1
  (config schema validation) PASSED. Done over SSH (relay).
- WHAT HERMES IS (corrects the repo): NousResearch/hermes-agent (MIT), a full agent
  (TUI, messaging gateway, skills, memory, MCP, cron, subagents) + its OWN kanban +
  worker dispatcher. Drives any OpenAI-compatible endpoint -> points at the persona
  :8090/v1. NOT a `pip install hermes-agent` package: installs via install.sh OR uv
  editable. Native Windows unsupported (WSL2 only) -> Hermes node = EVO-X2 (Linux).
- INSTALL (portable, per Brandon's directive): isolated + pinned, no global mutations.
  uv 0.11.19 (user-local ~/.local/bin); clone ~/src/hermes-agent pinned at 9b1e0d6f;
  `uv venv env_hermes --python 3.11` (uv fetched CPython 3.11.15); `uv pip install -e
  ~/src/hermes-agent[all,dev]` into env_hermes. Verified: hermes-agent v0.16.0,
  OpenAI SDK 2.24.0. node v18.19.1 already present (TUI). T1 close-out done:
  env_hermes/bin/python exists -> manage.py detection satisfied.
  scripts/setup_native_stack.sh still uses the WRONG `pip install hermes-agent` --
  needs updating to this flow.
- H1 VALIDATED against v0.16.0 (all three key paths): HERMES_HOME -> profile dir
  (`config path` resolved to persona/profiles/default/config.yaml); model.sampling.
  default/thinking (all 5 keys) parsed verbatim; tools.disabled egress list preserved
  + valid (config check: no Required missing). Config MIGRATED in place 0 -> 28
  (additive; model/sampling/tools.disabled/security all preserved). Committed +
  pushed from EVO-X2 (70d7fb2).
- EGRESS POSTURE (defense in depth, all confirmed): tools.disabled list +
  egress tools are API-key-gated (no EXA/TAVILY/BROWSERBASE keys set -> off) +
  terminal.backend=local + browser.allow_private_urls=false + agent.disabled_toolsets.
- ARCHITECTURE NOTE for H2-H6: Hermes ships its own kanban (HERMES_KANBAN_HOME/BOARD/
  DB/WORKSPACES_ROOT) + dispatcher. The Phase 8 "Hermes pulls from OUR Task Board
  (taskboard.py)" plan should ride Hermes' native kanban, or bridge the two -- revisit
  at H2.

## 2026-06-08 1029 PDT -- EVO-X2 single-model convergence: Qwen3.6 live on b9219 Vulkan (Brandon + Claude)

- MILESTONE: EVO-X2 (Daemonic-evox2, Strix Halo) converged to the single model
  Qwen3.6-35B-A3B-UD-Q5_K_XL, completing the 2026-06-07 "single model everywhere"
  directive. Done over SSH (relay). config.toml [linux] PERSONA_MODEL swapped off
  Instruct-2507; Instruct-2507 moved to models/archive/ as rollback. Committed +
  PUSHED from EVO-X2 (milestone, not an exception).
- llama.cpp BUMP (the gate): EVO-X2's old build was stale/broken (Apr-1 binary,
  missing libmtmd.so.0, < b8770 so no qwen3_5_moe arch). Built fresh from a clean
  clone at tag b9219 with -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release; symlinked
  llama_cpp/build -> ~/src/llama.cpp/build (old tree moved to llama_cpp/build.stale.*).
  manage.py resolves it via the default llama_cpp/build/bin path; no config edit.
- BUILD DEP (new, Ubuntu 24.04): the Vulkan configure needs the SPIRV-Headers CMake
  package -- `sudo apt-get install -y spirv-headers spirv-tools`. Without it,
  ggml/src/ggml-vulkan/CMakeLists.txt fails find_package(SPIRV-Headers). cmake 3.30.5,
  gcc 13.3, vulkan-dev 1.3.275, glslc were already present. Recorded in
  docs/llama_build_matrix.md.
- COSMETIC: `--depth 1` shallow clone makes llama-server --version report
  `version: 1 (45b455e)` -- the build NUMBER can't be counted from a shallow tree.
  45b455e IS tag b9219 (clean git describe). Functionally b9219; only the mesh
  metadata string is affected. Fix later via full clone or -DLLAMA_BUILD_NUMBER=9219.
- VALIDATED LIVE on EVO-X2: llama-server loads qwen3_5_moe (old build could not),
  /health green; API /health green on the refreshed native venv (py3.12.3,
  embedder_ok fastembed + chroma_ok true); default /chat returns coherent persona
  answers (Daemonic voice + 2-part format); messages path (PERSONA_USE_MESSAGES=1)
  returns server reasoning_content with sanitizer_applied=false -> T2.4 live-proven
  on EVO-X2 too.
- TUNABLE (finding): with thinking ON (messages path / enable_thinking), the default
  PERSONA_MAX_TOKENS=192 STARVES the answer -- the CoT consumes the whole budget and
  text comes back empty. Needs >= ~4096 (at 4096 the reasoning concluded and a full
  answer emitted). Default raw path (messages OFF) is unaffected; persona stays short.
- VARIANCE (watch): the raw /completion path occasionally returns an empty/unusable
  reply -> sanitize_persona_reply emits its placeholder ("I can help with local,
  offline assistance..."). Intermittent (2 of 3 retries were clean); matches the
  documented advisory-/think variance. Not a defect.
- EVO-X2 left running steady-state: Qwen3.6, messages OFF (default), API+llama up.

## 2026-06-08 0856 PDT -- T2.4 verified Windows-side + offline self-test now logs (Brandon + Claude)

- CANONICAL VALIDATION: Brandon ran tests/test_api_offline.py on the portable 3.11.9
  interpreter Windows-side -> 72/72 ALL PASS (the off-mount sandbox run was fastapi
  0.136.3; this is the pinned-chain confirmation). T2.4 payoff is fully validated.
- tests/test_api_offline.py: the offline suite now writes its own
  logs/test_api_offline.log when run directly (previously only tests/run_logged.py
  emitted a log, so a direct `python tests\test_api_offline.py` left nothing in logs/).
  Tee mirrors stdout to the log with a header (started/python/platform) + footer
  (finished/scan checks=PASS/FAIL/log path). stdout is restored to the real stream
  before the log handle closes (else interpreter-shutdown flush hit the closed tee ->
  ValueError + exit 120).
- tests/run_logged.py: sets RUN_LOGGED=1 in the child env. The self-test skips its own
  log when RUN_LOGGED is set, so the wrapper stays the single logger (its default label
  "test_api_offline" would otherwise collide with the self-log path). Mechanism validated
  off-mount: direct run writes the log + exit 0; RUN_LOGGED=1 run writes no self-log.
- OWED: a Windows-side re-run after the logging edits to reconfirm 72/72 + that
  logs/test_api_offline.log appears (logic unchanged; logging mechanism proven in
  isolation). NOT committed (mid-phase = local-only, no push).

## 2026-06-08 0846 PDT -- T2.4 payoff: retire post-hoc sanitizer on the messages path (Claude)

- services/api/server.py: the lossy two-part sanitize_persona_reply is RETIRED on the
  messages path now that PERSONA_USE_MESSAGES is live-proven (1746, 06-07) to return
  clean content + server-side reasoning_content. New PERSONA_SANITIZE_MESSAGES env flag
  (OFF by default = retired) is the escape hatch: set 1 to re-apply the sanitizer on the
  messages path if a model ignores the format contract.
- New helpers will_sanitize(preserve) + finalize_persona_reply(answer, preserve)
  centralize the reply-finalization decision; /chat and /v1 both call
  finalize_persona_reply (replaced the inline `answer if preserve else sanitize...`).
  Decision table: preserve -> never sanitize (unchanged); messages path -> sanitize only
  if PERSONA_SANITIZE_MESSAGES; raw /completion path -> always sanitize (UNCHANGED, proven
  default deployment byte-identical).
- /health gains persona_sanitize_messages. /chat debug gains sanitizer_applied (audits
  whether the post-hoc sanitizer ran -- usable in a live POST to confirm the messages
  path skipped it).
- tests/test_api_offline.py: +8 checks (now 72/72). Messages path returns server content
  verbatim with no forced "Next actions:" and debug sanitizer_applied=false; escape hatch
  re-sanitizes; raw /completion path still sanitizes; /v1 messages content verbatim;
  health key present. OFF-MOUNT VALIDATED: py_compile + AST OK, suite 72/72 ALL PASS
  (sandbox fastapi 0.136.3). Canonical Windows-side run on portable 3.11.9 still OWED.
- NOT committed (local-only when committed; mid-phase = no push per push-at-milestones).
  roadmap T2.4 FOLLOW-UP closed; todo "Next" #2 cleared.

## 2026-06-07 2254 PDT -- Model provisioner P2: playbook + matcher (Brandon + Claude)

- run/model_playbook.toml (NEW, tracked, human-editable): 10-model Apache-2.0
  catalog with quant ladders, vision flags, ranks, repos, mmproj; [meta] reserves +
  vision boosts + cpu file cap. Catalog stamped "verified 2026-06-07" (sizes/repos
  are estimates to re-verify at download time).
- scripts/provision_match.py (NEW, pure stdlib + tomllib): envelope_from_caps +
  compute_budget (max of RAM-reserve and VRAM-reserve; unified uses RAM only) +
  largest-fitting-quant + rank scoring with vision soft-preference and camera boost
  + cpu-only file cap. Emits model/quant/file/repo/mmproj/ctx/vision_enabled/
  full_gpu_offload/budget. Camera gates vision_enabled (per the P1 decision).
- tests/test_provision_match.py (NEW): 7/7 PASS offline against the real playbook.
  Picks: RX 9060 XT (16GB VRAM/32GB) -> qwen3.6-35b (matches live config, partial
  offload); EVO 96GB unified -> qwen3.6-35b full-offload ctx16384; 16/8GB+cam ->
  pixtral-12b vision; Pi 8GB headless -> qwen3-4b text; Pi+cam -> smolvlm2 vision;
  4GB -> none (below 8GB floor).
- KNOWN TUNABLE: tight-budget ctx step-down drops the RX 9060 XT pick to ctx 8192
  vs the working 16384; KV-aware ctx sizing deferred to P3/P4.
- NEXT: P3 (huggingface_hub downloader + license/disk preflight + config wiring),
  P4 (manage.py `provision` + first-run hook). Vision default = camera-gated.

## 2026-06-07 2200 PDT -- Model provisioner design + profiler P1 (Brandon + Claude)

- DESIGN: docs/model_provisioner_design_20260607_2158.md -- first-run host profile
  -> playbook match -> confirm (--yes bypass) -> huggingface_hub download -> wire
  config.toml. Wide hardware range (Raspberry-Pi/8 GB CPU floor to 96 GB unified /
  discrete VRAM); vision-capable PREFERRED (soft), never a hard filter.
- LICENSING (Brandon directive): default catalog = OSI-open / AGPL-compatible only
  (Apache-2.0 / MIT, ungated) -> SmolVLM, Qwen2.5-VL 7B/32B, Pixtral, Mistral Small
  3.1, Qwen3/Qwen3.6. EXCLUDED from defaults (gated/restrictive): Gemma, Llama, and
  Qwen2.5-VL 3B/72B (Qwen license, not Apache). Removes first-run token/accept
  friction. Catalog license-verified via web search 2026-06-07.
- PROFILER P1 (manage.py, CODE DONE): detect_vram_mb() -- PRIMARY source is
  vulkaninfo's largest MEMORY_HEAP_DEVICE_LOCAL_BIT heap (cross-vendor; ships with
  the GPU driver, confirmed at C:\WINDOWS\system32\vulkaninfo.exe on the RX 9060 XT),
  with nvidia-smi / Linux sysfs mem_info_vram_total / Windows registry qwMemorySize
  as fallbacks. detect_memory_model() (vulkaninfo deviceType + APU-name heuristic)
  + detect_host() now emit vram_mb + memory_model. NPU classify already present
  (Intel/OpenVINO tier 2 usable=false; Hailo/Gaudi tier 3). Parser verified against
  the host's real vulkaninfo output -> 16304 MiB (discrete RX 9060 XT DEVICE_LOCAL
  heap; the machine also has an integrated Radeon at a 10.5 GiB RAM carve-out, max
  wins). VALIDATED live on the RX 9060 XT (Daemonic-PC): vram_mb=16304,
  memory_model=discrete. PENDING only: an EVO-X2 run to confirm "unified".
- node_capabilities.json schema gains vram_mb + memory_model + camera_present.
- detect_camera() added (Windows CIM PNPClass Camera/usbvideo; Linux /dev/video*).
  VISION DEFAULT decision (Brandon): camera-gated at every tier -- VISION_ENABLED on
  iff a camera is detected, else off with opt-in; vision-capable model + mmproj
  fetched regardless. Compiled + sandbox-checked (no camera -> False).
- roadmap Phase 0.5 provisioner item -> [~] with design link; knowledge.md noted.

## 2026-06-07 1827 PDT -- Doc reconciliation: model identity + obsolete-entry sweep (Brandon + Claude)

- Combed the living docs for obsolete/conflicting entries; findings recorded in
  `docs/doc_audit_conflicts_20260607_1827.md` (~20 items, tiered P1-P3).
- MODEL IDENTITY (P1): reconciled all docs to the single committed model
  Qwen3.6-35B-A3B-UD-Q5_K_XL on EVERY host. knowledge.md "Stable architectural
  decisions" rewritten (30B-class -> 35B; added light/heavy = thinking toggle and
  Hermes sub-agents on parallel slots; model-lock history with T0.1 arch + T0.2
  tool-calling gates, both passed, Instruct-2507 = dropped no-thinking fallback).
  knowledge.md operational config + env block PERSONA_MODEL + model-card links
  updated. README_models_hardware.md: Instruct-2507 demoted to dropped fallback,
  "pending T0.1" gating removed, T0.1/T0.2 pass status added, ~/Live/AIStack path
  + config.env -> config.toml. README.md: model row + roadmap line -> single-model
  live; "uses Qdrant" -> ChromaDB now/Qdrant Phase 2a; OpenWebUI Running ->
  dormant; retired HANDOFF.md/.html "open first" pointers -> todo/roadmap/
  knowledge/changelog + archive/handoffs.
- Roadmap: stale "Current position" proof text -> Phase 1 Exit Gate proven, only
  M6 left; "Unix-socket IPC" cross-cutting label -> NATS-based; Qwen3.5/3.6
  re-eval note clarified (3.6 already committed); NEW Phase 0.5 item -- first-run
  model auto-provisioning sized to detected resources (node_capabilities.json).
- knowledge.md: stale Phase 1 "Remaining" list (per-profile/Task Board/topic
  routing all done) corrected; config.toml flagged as primary over config.env;
  py314 pointer 3.12 -> 3.11.9; first-run provisioner noted.
- todo.md: Hermes H-track ref Phase 9 -> Phase 8 (Phase 9 is DELETED).
- Stamps bumped (knowledge/roadmap/todo). M6 confirmation runbook added:
  `docs/m6_confirmation_runbook_20260607_1827.md`.
- LEFT FOR BRANDON (flagged, not edited): tools/taskman2.py is gitignored
  (.gitignore L89) yet /agent/run shells to it -- verify intent; live n_ctx vs
  PERSONA_CTX/262K context numbers reconcile; README emoji/no-stamp style.

## 2026-06-07 1758 PDT -- Phase 1 live validation complete: messages + per-profile + Task Board (Brandon + Claude)

- Ran the three owed LIVE passes on Qwen3.6 (build e7bd3b3) via run_logged.py;
  each left logs/exit_gate_live.log (overwritten per pass). All ALL REQUIRED PASS,
  scan Error=0 Traceback=0 Warning=0; api.log + persona.log clean (no errors,
  truncated=0 throughout).
- T2.4 messages (PERSONA_USE_MESSAGES=1, 1746): [messages] section PASS -- reasoning
  sourced from server reasoning_content, text <think>-free, /v1 reasoning_content
  present. roadmap T2.4 -> [x]. FOLLOW-UP: retire the post-hoc sanitizer on the
  messages path.
- Per-profile Chroma (RAG_PER_PROFILE=1 + RAG_ENABLED=1, 1752): [per-profile]
  section PASS -- mem_alice + mem_bob collections created. roadmap per-profile -> [x].
- Task Board (1758): POST /agent/run with a read-only job (task_id smoke-taskboard,
  steps-only, no edits/commands) returned status ok / returncode 0; the run recorded
  into data/tasks.db; GET /jobs + /jobs/{id} returned the row with started/finished
  timestamps; /health task_store count=1. roadmap Task Board -> [x].
- FINDING (residue): the smoke job's post_context git status shows the per-profile
  run left untracked persona/profiles/alice/ + persona/profiles/bob/ on disk. Decide:
  gitignore the test profiles or clean them up before commit. (mem_alice/mem_bob also
  persist in the Chroma store.)
- Phase 1 now: Exit Gate [x] + T2.1/T2.2/T2.3 [x] + topic routing [x] + T2.4 [x] +
  per-profile [x] + Task Board [x]. Only M6 (single-model migration confirmation)
  remains open; clearing it unblocks the Hermes H-track.

## 2026-06-07 1716 PDT -- tests/run_logged.py test-run logger (Brandon + Claude)

- tests/run_logged.py: new stdlib wrapper that runs any test script with the
  launching interpreter (preserves portable python), tees the child's merged
  stdout+stderr to the console live, and writes logs/<label>.log (overwritten
  each run; latest only -- no dated files cluttering the folder). Captures
  as-is (no warning filtering changed), in true chronological order (stderr
  folded into stdout). tz stamp abbreviated (PDT/PST).
- Log header records: label, Pacific start time, full command, cwd, python
  version+path, platform, git HEAD (+clean/dirty), and which feature flags were
  set for the run (PERSONA_USE_MESSAGES, RAG_PER_PROFILE, RAG_ENABLED,
  TOPIC_ROUTING, THINKING_AUTO_GATE, PRESERVE_THINKING_DEFAULT, EMBED_BACKEND,
  PERSONA_PORT, API_PORT). Footer records finish time, duration, child exit
  code, log path, and a quick scan tally (PASS/FAIL/Error/Traceback/Warning).
- Motivation: a green "ALL PASS" can still hide suppressed warnings or stderr
  noise; every run now leaves an auditable artifact next to api.log/persona.log.
- Usage: .\portable\python\python.exe tests\run_logged.py tests\test_api_offline.py
  (or exit_gate_live.py). Optional --label NAME overrides the log prefix.
- Exits with the child's return code (CI-friendly). Compile-checked off-mount
  (py_compile OK); not run against the live repo from the sandbox.

## 2026-06-07 1640 PDT -- exit_gate_live.py adaptive + session milestone handoff (Brandon + Claude)

- tests/exit_gate_live.py: added adaptive [messages] (PERSONA_USE_MESSAGES) and
  [per-profile] (RAG_PER_PROFILE + RAG_ENABLED) sections. Re-reads /health and only
  asserts the flag-gated behavior that is actually on, skipping the rest with a note
  + printing the active flags. So one script validates the Exit Gate by default and
  the T2.4 / per-profile features when their flags are flipped on a restart. Block
  AST OK + dry-run (default-off -> clean skips, ALL REQUIRED PASS). Task Board's
  /agent/run smoke intentionally left manual (it mutates the repo via taskman2).
- Handoff written: archive/handoffs/handoff_persona_20260607_1640.md -- session
  milestone summarizing the full arc (T2.2 -> T2.3 -> Exit Gate -> Task Board ->
  per-profile -> topic routing -> T2.4) and the LIVE validation owed.

## 2026-06-07 1635 PDT -- T2.4 --jinja messages migration, OFF by default (Brandon + Claude)

- server.py: the persona can now generate via the chat-completions/messages path.
  New query_llama_messages(url, messages, ..., enable_thinking, extra) POSTs the
  OpenAI-compatible /v1/chat/completions on the llama-server with
  chat_template_kwargs{enable_thinking} and parses choices[0].message.content +
  reasoning_content + usage (mapped to the same stats keys as query_llama).
- build_persona_messages(): system/user split mirroring build_persona_prompt's
  persona block, minus the /think prefix and trailing "Assistant:" (the chat template
  owns the assistant turn; thinking is the enable_thinking kwarg).
- persona_generate(): single helper that both /chat and /v1 now call. Off (default,
  PERSONA_USE_MESSAGES) -> the proven raw /completion + /think-prefix path,
  byte-identical. On -> messages path; the server's reasoning_content is preferred,
  split_reasoning() is the in-band fallback. This is the refactor that de-duplicates
  the two endpoints' generation call.
- Config: PERSONA_USE_MESSAGES (default 0) + PERSONA_CHAT_URL (/v1/chat/completions on
  PERSONA_PORT). Confirmed against the vendored server README: --jinja default-on,
  --reasoning-format deepseek -> reasoning_content, chat_template_kwargs{enable_thinking}.
- Observability: /health adds persona_use_messages + persona_chat_url.
- tests/test_api_offline.py: +8 checks (build_persona_messages structure + no think
  prefix; messages path via a monkeypatched query_llama_messages -> preserve surfaces
  server reasoning, default sanitizes, /v1 reasoning_content; health field).
- Verified: new functions AST OK (head parse to the distill boundary); query_llama_
  messages parse logic 6/6 standalone; both endpoint call sites read-back balanced.
- LIVE VALIDATION REQUIRED: the real --jinja reasoning_content behavior is the one
  piece offline can't cover. Default off keeps the proven path until then. roadmap
  T2.4 -> [~].

## 2026-06-07 1617 PDT -- Offline suite 56/56 across the Phase 1 batch (Brandon + Claude)

- Ran tests/test_api_offline.py on the portable 3.11.9: ALL PASS, 56/56. Exercises
  the gate, preserve, Task Board (/jobs CRUD + health), per-profile collection naming,
  and topic routing (auto->math drives the think preset) through the real /chat + /v1
  endpoints. Clears the validation debt from stacking three default-off features.
- roadmap Topic routing -> [x] (offline coverage is complete + rides the proven Exit
  Gate). Task Board and per-profile Chroma stay [~]: their offline coverage is green
  but each still has ONE live-only gap -- a real /agent/run subprocess recording into
  the board, and actual mem_<profile> collection creation/isolation under
  RAG_PER_PROFILE=1 (offline runs with RAG_ENABLED=0). Both are confirmatory smokes.

## 2026-06-07 1613 PDT -- Topic routing policy, OFF by default (Brandon + Claude)

- server.py: classify_topic(text) -- deterministic keyword classifier (coding/math/
  biology/science/research, else chat; scores keyword hits, first TOPIC_PRIORITY
  topic with the strict-max score wins). resolve_topic(req_topic, text) precedence:
  "auto" always classifies; an explicit non-chat topic is respected as-is;
  ""/"chat" classifies only when TOPIC_ROUTING is on, else stays "chat".
- /chat + /v1 now resolve the topic via resolve_topic before everything downstream,
  so an unlabeled request can route to the right thinking/sampling/RAG-kinds/inband
  path instead of defaulting to chat.
- Config: TOPIC_ROUTING (default 0 = off -> topic taken as given, behavior
  unchanged), TOPIC_KEYWORDS, TOPIC_PRIORITY.
- Observability: /health adds topic_routing + topic_routing_topics; /chat debug adds
  topic_routing {enabled, requested, resolved}.
- tests/test_api_offline.py: +8 checks (classify coding/chat; explicit respected;
  /chat auto->math drives think preset; routing off keeps chat; routing on classifies
  chat->coding; /health fields). Standalone topic harness 14/14.
- Verified: server.py AST+COMPILE OK (spliced authoritative full file, 1238 lines;
  mount truncates at ~1057). Full offline suite + live smoke pending Windows-side.
- This is the last Phase 1 feature item draftable offline; remaining Phase 1 = M6
  (live) + T2.4 (--jinja migration).

## 2026-06-07 1243 PDT -- Per-profile Chroma collections, OFF by default (Brandon + Claude)

- server.py: RAG retrieval/writeback can now be scoped per persona. New
  _collection_name(profile) + _get_collection(profile) (lazy get-or-create + cache);
  the single module-global _collection is gone, replaced by a _collections dict keyed
  by collection name. memory_add/memory_query gained a keyword `profile`; /chat, /v1,
  distill, and chat-log writeback all pass the active profile.
- Config: RAG_PER_PROFILE (default 0 = off -> all add/query use the shared
  RAG_GLOBAL_COLLECTION "global_memory", behavior unchanged) and RAG_GLOBAL_COLLECTION.
  On -> "mem_<sanitized-profile>" collections. CAVEAT: enabling does NOT move existing
  global_memory rows; pre-existing memory is invisible under per-profile scoping until
  migrated (documented; a migration helper is a follow-up).
- Observability: /health adds rag_per_profile + rag_collections (cached names).
- tests/test_api_offline.py: +6 checks (collection_name off/on/None/sanitize; health
  rag_per_profile + rag_collections). Env-independent (no chroma needed). Standalone
  name-logic harness 8/8.
- Verified: server.py AST+COMPILE OK (spliced authoritative full file, 1161 lines;
  mount truncates at ~1063). Full offline suite + live smoke pending Windows-side.

## 2026-06-07 1236 PDT -- Task Board (SQLite) replaces the jobs dict (Brandon + Claude)

- New services/api/taskboard.py: stdlib sqlite3 store (no deps). One row per job_id
  with a merged JSON state blob + queryable status + created/updated timestamps.
  API: init_db (idempotent + one-time jobs.jsonl migration), task_set (upsert-merge,
  same semantics as the old jobs.setdefault().update()), task_get, task_list,
  task_delete, count, migrate_from_jsonl. Fresh connection per call + WAL +
  busy_timeout so the API's to_thread worker threads are safe (sqlite3 forbids
  cross-thread connection sharing); store is therefore file-backed by design.
- server.py wired: removed the in-memory `jobs` dict + _load_persisted_jobs/
  _persist_job_event (jobs.jsonl event log); TASKS_DB config (default
  AI_ROOT/data/tasks.db, env override) with JOBS_PERSIST_PATH kept only as the
  migration source. taskboard.init_db() at import. _job_set() is now a thin
  taskboard.task_set wrapper.
- Behavior gain: /agent/run now RECORDS into the board (status running ->
  ok/error/timeout, returncode, started/finished_at), so /jobs/{id} reflects agent
  runs (previously it only saw the jsonl-loaded retained jobs, never agent runs).
  New GET /jobs (list, ?limit) endpoint. /jobs/{id} reads the board. /health adds
  task_store {db, count}.
- Dropped config: JOBS_PERSIST_ENABLED, JOBS_PERSIST_MAX_LOAD (event-log only).
- .gitignore: data/ already ignored (covers the default db); added tasks.db +
  -wal/-shm guards for TASKS_DB overrides.
- tests/test_api_offline.py: +6 Task Board checks (/health task_store, /jobs missing
  -> not_found, upsert-merge via /jobs/{id}, timestamps, /jobs list membership +
  status). Plus a standalone taskboard harness 15/15 (migration, merge, idempotent
  re-init, unicode) run off-mount.
- Verified: taskboard 15/15 standalone; server.py AST+COMPILE OK (spliced
  authoritative full file, 1118 lines -- the mount truncates at ~1074); test block
  AST OK. Full FastAPI offline suite + live smoke pending Windows-side (Brandon).

## 2026-06-07 1222 PDT -- Phase 1 Exit Gate PROVEN live on Qwen3.6 (Brandon + Claude)

- Ran tests/exit_gate_live.py against the live stack (llama-server :8090 Qwen3.6 pid
  15820 + API :8000 pid 15504): ALL REQUIRED PASS. /health green (embedder_ok +
  chroma_ok); chat->no_think, science/coding/math/research->think (preset + directive);
  preserve off strips reasoning; /v1 stream SSE+[DONE]; /v1 non-stream prompt_tokens>0.
- T2.3 preserve CONFIRMED LIVE: /v1 preserve returned a populated reasoning_content --
  split_reasoning() extracted a real Qwen3.6 <think> block and surfaced it. Proof the
  preserve path works against the actual model, not just the faked offline suite.
- One soft WARN: the /chat preserve check saw reasoning_chars=0 (model answered that
  prompt with no <think>). Expected -- Qwen3's /think is a soft/advisory switch, so a
  simple prompt may skip reasoning; the check WARNs by design and the /v1 pass shows
  the path is sound. Generation variance, not a defect.
- roadmap Phase 1 Exit Gate annotated PROVEN. Remaining Phase 1 feature items (M6,
  per-profile Chroma wiring, topic routing, Task Board) still open.

## 2026-06-07 1215 PDT -- Live Exit Gate validation script (Brandon + Claude)

- Added tests/exit_gate_live.py: stdlib-only (urllib) live check against a running
  stack (manage.py up). Covers the roadmap Phase 1 Exit Gate in one command --
  /health green, chat->no_think / science|coding|math|research->think, T2.3 preserve
  on/off, /v1 stream SSE + [DONE], /v1 non-stream prompt_tokens>0, /v1
  reasoning_content under preserve. Model-dependent reasoning checks are SOFT (WARN,
  not FAIL) so it still passes on a non-thinking model. Off-mount COMPILE OK; run
  Windows-side with the stack up. NOT yet committed.

## 2026-06-07 1212 PDT -- T2.3 validated 35/35 Windows-side (Brandon + Claude)

- Ran tests/test_api_offline.py on the portable 3.11.9 interpreter: ALL PASS, 35/35
  (the 9 new T2.3 checks green: split_reasoning units, /chat default strip + empty
  reasoning, /chat preserve reasoning + un-sanitized answer, /v1 preserve
  reasoning_content, /v1 default none). Preserve logic exercised through the real
  /chat + /v1 endpoints (only query_llama faked). roadmap T2.3 -> [x]. Live-model
  spot check folded into the Phase 1 Exit Gate proof.

## 2026-06-07 1208 PDT -- T2.3 preserve_thinking, Path A (Brandon + Claude)

- server.py: new `split_reasoning(text) -> (reasoning, answer)` pulls the in-band
  Qwen3 <think>...</think> out of the raw model content (handles normal wrap,
  multiple blocks, case, and a truncated unclosed <think>); no-op when absent (the
  future --jinja reasoning_content path).
- preserve_thinking flag: req field on ChatRequest + OA_ChatCompletionsReq, default
  from PRESERVE_THINKING_DEFAULT (off). resolve_preserve_thinking() = req value else
  default. Intended for the Phase 3 daemon to set on Hermes-forwarded work.
- /chat + /v1 now split reasoning BEFORE sanitizing. Default (off): reasoning is
  stripped then the persona two-part sanitizer runs -- this also closes the latent
  leak where <think> would bleed into the persona paragraph once Qwen3.6 thinking
  fires. Preserve (on): answer returned un-sanitized + reasoning surfaced
  (`reasoning` on /chat; `reasoning_content` on the /v1 message, plus a
  reasoning_content delta on the stream).
- DESIGN NOTE: preserve mode skips the lossy two-part persona sanitizer (agent loops
  want the whole answer). Documented in roadmap T2.3 as revisitable.
- Observability: /health adds preserve_thinking_default; /chat debug adds
  preserve_thinking {resolved, reasoning_chars}.
- T2.4 partially advanced: the non-jinja in-band <think> stripping is now done by
  split_reasoning; only the --jinja messages migration remains.
- tests/test_api_offline.py: +9 checks (split_reasoning units; /chat default strips
  think + empty reasoning; /chat preserve returns reasoning + un-sanitized answer;
  /v1 preserve emits reasoning_content; /v1 default has none). Suite 22 -> 31 live.
- Verified: authoritative file complete + balanced through the /v1 return (Read;
  the sandbox mount truncates at ~1084 lines, a known artifact). Standalone logic
  harness 12/12 on the extracted split_reasoning/resolve_preserve_thinking. Full
  offline suite + live validation pending Windows-side (Brandon).

## 2026-06-07 1201 PDT -- Silence StarletteDeprecationWarning in offline suite (Brandon + Claude)

- tests/test_api_offline.py: added a scoped warnings.filterwarnings (message
  r"Using .*starlette\.testclient.* is deprecated") before the TestClient import,
  so the cosmetic httpx/httpx2 deprecation no longer prints. Verified the regex
  suppresses the exact message and leaves unrelated DeprecationWarnings intact.
- Pinned FastAPI-chain deps deliberately untouched (warning is test-harness only,
  not the serving path); avoids a Starlette/httpx bump in the 3.11.9 env. Closes
  the low-pri fix-it. Re-run Windows-side to confirm clean 22/22.

## 2026-06-07 1155 PDT -- T2.2 validated 22/22 Windows-side (Brandon + Claude)

- Ran tests/test_api_offline.py on the portable 3.11.9 interpreter: ALL PASS, 22/22
  (was 14/14 + the 8 new gate checks). Gate logic exercised through the real /chat +
  /v1 endpoints (only query_llama faked). roadmap T2.2 -> [x].
- Known cosmetic warning persists: StarletteDeprecationWarning (httpx vs httpx2 in
  the FastAPI TestClient) -- still the open low-pri fix-it, not a failure.

## 2026-06-07 1151 PDT -- T2.2 thinking gate, Path A (Brandon + Claude)

- DECISION (Path A): T2.2 stays on the /think//no_think prefix + raw /completion
  flow; the chat_template_kwargs/messages migration is deferred to T2.4 (same
  --jinja reasoning_content world). Rationale: do the messages rework once, where
  the post-hoc sanitizer cleanup is its payoff.
- server.py: new OFF-by-default thinking gate. classify_triviality(text) -> a
  deterministic, stdlib-only (no model call) (is_nontrivial, signals) verdict from
  code fences, multi-question, multi-sentence, length, and a reasoning-keyword set.
- resolve_think / thinking_prefix / sampling_for gain an optional `text` arg.
  With THINKING_AUTO_GATE=1 the gate PROMOTES a non-thinking-topic request (e.g.
  "chat") to think when non-trivial; explicit on/off and the THINKING_MODE_TOPICS
  set keep their deterministic mapping (so the Phase 1 exit-gate proof is
  unchanged with the gate off, the default).
- Config: THINKING_AUTO_GATE, THINKING_GATE_TRIVIAL_MAX_WORDS (6),
  THINKING_GATE_COMPLEX_MIN_WORDS (30), THINKING_GATE_KEYWORDS.
- Observability: /health adds `thinking_auto_gate`; /chat debug adds
  `thinking_gate` {enabled, is_nontrivial, signals}.
- tests/test_api_offline.py: +8 gate checks (gate-on/off, promote/demote, thinking
  topic still deterministic). Offline suite goes 14/14 -> 22/22 when run live.
- Verified: AST + py_compile OK on a completeness-verified off-mount copy (1087
  lines, edit markers present); standalone logic harness 14/14 against the extracted
  classify_triviality/resolve_think. LIVE /chat debug validation pending (Brandon).

## 2026-06-07 1140 PDT -- Handoff written (handoff_persona_20260607_1140) (Brandon + Claude)

- Froze the session into archive/handoffs/handoff_persona_20260607_1140.md:
  timestamp->Pacific conversion + handoff renames, the cross-project WORKFLOW/AGENTS
  standard, the Phase 0.5 #4 IPC decision, Windows-side manage.py validation, and the
  two verified manage.py fixes -- all in commit 8088ff2. Next session: Phase 1 / T2.2.

## 2026-06-07 1129 PDT -- manage.py fix-its verified live (Brandon + Claude)

- Confirmed both 1125 fixes on Daemonic-PC: `manage.py up` printed "API /health
  responding" (readiness wait works); `manage.py capabilities` now reports
  llama_build "b9219" (was null). Clean `down` after.

## 2026-06-07 1125 PDT -- manage.py fix-its: API /health wait + llama_build parse (Brandon + Claude)

- cmd_up now polls API /health (timeout 120, respects --no-wait) after start_api, so
  `up` returns only once the API has finished embedder/Chroma init -- fixes the
  readiness race where doctor --deep saw API /health down right after up.
- llama_version_info: `--version` timeout 10->30 + one retry if the first call comes
  back empty, so a cold Vulkan `--version` no longer leaves llama_build=null while
  backends populate from --list-devices. Build is still parsed only from `--version`
  (avoids matching VRAM numbers in --list-devices).
- Both confirmed at the source Windows-side (Read) and syntactically sound. Live
  re-verify pending: `manage.py up` should print "API /health responding";
  `manage.py capabilities` should show llama_build "b9219". (Off-host sandbox AST is
  unreliable for this file -- the mount serves truncated reads.)
- httpx2 TestClient deprecation left as documented low-priority (cosmetic; needs a
  dependency change).

## 2026-06-07 1110 PDT -- Windows live manage.py lifecycle validated (Brandon + Claude)

- Extends the 1105 entry with the live CLI run on Daemonic-PC (RX 9060 XT): up (GPU
  layers auto; llama-server pid 3044 /health OK; API pid 8340) -> status (both up) ->
  doctor --deep (live persona completion smoke PASS) -> test quick (offline suite
  14/14 incl. streaming / [DONE] / prompt_tokens=42 / chat_submit 404, plus live
  health persona+API OK) -> down (clean) -> status (down). The manage.py launcher's
  Windows leg is now fully proven via the CLI (not just the panel); only the deferred
  Linux/ARM64 pass keeps it from [x].
- FINDING (fix-it): doctor --deep reported API /health not responding immediately
  after up, while test health moments later showed API /health OK -- an API readiness
  race (embedder/Chroma init delay). up should wait on API /health; doctor should
  retry before declaring it down.
- Minor: offline suite emits a StarletteDeprecationWarning (httpx vs httpx2).

## 2026-06-07 1105 PDT -- Windows-side manage.py validation pass (Brandon + Claude)

- AST/syntax re-check off-host on a completeness-verified copy (51002 bytes, matches
  the Windows-side size): COMPILE OK + AST OK, no 3.11-only syntax, tomllib has a
  tomli fallback.
- Live host Daemonic-PC (RX 9060 XT) under portable Python 3.11.9: manage.py
  status/capabilities/doctor all green. config.toml read; run/node_capabilities.json
  written (accel_selected=vulkan, tier1 AMD RX 9060 XT, llama_backends_compiled
  [vulkan], llama-server build b9219); filesystem/binaries/profiles OK; T1
  safe_config=pass (env_hermes_installed=no -- the known T1 close-out).
- Closes the Windows-side validation caveats on the manage.py launcher, the TOML
  migration, and the capabilities/detection layer (roadmap Phase 0.5). Linux x64 +
  ARM64 remain deferred (no hardware). Live CLI up/down/test not re-run this session
  (up/down already proven via the panel).
- FIX-IT logged: capabilities reports llama_build=null while doctor detects build
  b9219; populate it from the same version parse.

## 2026-06-06 2123 PDT -- Deferred Phase 0.5 Linux/ARM64 live validation (no hardware) (Brandon + Claude)

- The Linux x64 + ARM64 live passes for the manage.py launcher and H3 accel
  selection are deferred -- no Linux/ARM64 hardware on hand. Trigger: hardware
  available. Windows x64 validation (manage.py AST + up/down on the Vulkan box)
  remains the near-term step.
- roadmap Phase 0.5: launcher item + Exit Gate annotated with the deferral and
  trigger; the phase cannot go GREEN until the deferred legs are validated. todo
  "next" updated to match.

## 2026-06-06 2105 PDT -- IPC decided: NATS+JetStream primary, loopback-TCP fallback (Phase 0.5 #4) (Brandon + Claude)

- Settled Phase 0.5 #4. The Phase 3 daemon's IPC uses NATS+JetStream as the primary
  control-plane bus -- nats-server supervised as a daemon child (loopback, JetStream
  R=1) -- laying groundwork for the Phase 10 mesh, which is already locked to
  NATS+JetStream. A stdlib loopback-TCP bus is the compatibility fallback; both sit
  behind one EventBus interface, so transport is config, not a code fork.
- Unix sockets ruled out: Python asyncio has no create_unix_server/create_unix_
  connection on the Windows ProactorEventLoop, so AF_UNIX is not drivable
  cross-platform from one code path.
- Verified cross-platform support (web, June 2026): nats-server ships first-class
  binaries for Win x64 / Linux x64 / Linux ARM64 (plus pip nats-server-bin); nats-py
  is the official asyncio JetStream client. Compatibility risk low; the fallback is
  insurance for locked-down/exotic nodes.
- New doc: docs/ipc_decision.md (rationale, EventBus sketch, sources). roadmap Phase
  0.5 #4 -> [x]; roadmap Phase 3 + knowledge.md "Unix socket IPC" rewritten to the
  NATS-primary + fallback shape; nats-server added to the Phase 3 child-process map.

## 2026-06-06 2052 PDT -- Timestamps converted UTC->Pacific; WORKFLOW.md standard change (Brandon + Claude)

- Swept every UTC-labeled timestamp to Pacific (PDT, -7h with date rollback where
  the UTC time was before 0700) across all 35 project docs -- live 4, docs/,
  scripts/, archive/handoffs/, archive/pre-workflow/. llama_cpp vendor submodule
  left untouched.
- Preserved the non-timestamp "UTC" strings: the `date -u` command + its comment in
  archive/pre-workflow/HANDOFF.md, and the filename-origin meta-note in
  HANDOFF_2026-05-20_0102. Collapsed dual-labeled stamps (e.g. "1430 UTC (0730 PDT)")
  to their PDT value. Flipped the changelog header-format spec line to PDT.
- Renamed 17 UTC-named handoff files to PDT (e.g. handoff_persona_20260607_0329 ->
  handoff_persona_20260606_2029); left the 3 already-PDT handoffs unchanged
  (HANDOFF_2026-05-16_2337, _2026-05-19_1130, _2026-05-20_0102). Rewrote 118
  cross-references in lockstep -- 0 broken links (verified Windows-side).
- Root D:\Projects\WORKFLOW.md revised: timestamp standard switched UTC->Pacific
  (Rule 2 + format specs + skeletons + handoff section), and new Rule 8 makes
  imperial / US-customary units the default (data/compute units exempt). This is the
  first changelog entry authored under the new Pacific standard.

## 2026-06-06 2029 PDT -- Handoff written (handoff_persona_20260606_2029) (Brandon + Claude)

- Froze the whole session (manage.py bootstrap consolidation: detection + TOML +
  toggle/test/panel + Phase A fixes + GPU auto-fit + Phase C bash retirement, all
  live-validated on Windows and pushed as b75a853 + 5649466) into
  `archive/handoffs/handoff_persona_20260606_2029.md`. Standalone: state, decisions,
  known issues, run commands, and the forward roadmap (Linux/ARM live pass, IPC
  decision, manage.py setup, Phase 1 live /chat proof).

## 2026-06-06 2023 PDT -- Phase C: retire the bash lifecycle scripts (Brandon + Claude)

- Milestone commit b75a853 (the consolidation arc) pushed to origin/main first.
- Archived to scripts/archive/ (superseded by manage.py): start_all, stop_all,
  start_llama_servers, start_llama_server_win, start_api, stop_api,
  stop_llama_servers, status, doctor, smoke_agent, unified_test. Core lifecycle is
  now manage.py-only -- no bash required. (git mv run Windows-side.)
- Reference cleanup so nothing points at moved files: setup_native_stack.sh "next
  steps" now say `manage.py up/status/doctor/test` (and config.toml, not the .env);
  bootstrap_portable_python.ps1 "done" hint points at `manage.py up`. load_test_m2b.py
  stays (invoked by `manage.py test load`); init_profiles.sh stays.
- The scientist/reasoning/coder pidfile + SCIENTIST_* remnants (M2) left with the
  archived stop/status scripts; manage.py never carried them.
- `.gitignore`: added `*.log` (logs/ was already ignored) -- belt-and-suspenders for
  stray logs outside logs/.

## 2026-06-06 2002 PDT -- Panel: detached/background mode + status visibility (Brandon + Claude)

- `manage.py panel` was foreground-only (died when its terminal closed). Added:
  `--detach` (re-spawns itself detached via spawn_detached, writes run/panel.pid,
  opens the browser, returns -- survives terminal close), `--stop` (kills the
  detached/running panel via the pidfile), and a pidfile in the foreground path too
  (cleaned on exit). `manage.py status` now lists `panel` alongside persona/api.
  Idempotent: --detach no-ops if already running. Branch logic validated off-mount.
- Detection now reports `ram_available_mb` (ullAvailPhys / MemAvailable) next to
  `ram_mb` -- total physical overstates usable memory when RAM is carved out (e.g. a
  ramdisk); available nets that out. `detect_ram_mb` returns (total, available); the
  panel shows avail/total. `.gitignore`: ignore generated run/node_capabilities.json;
  whitelist run/llama-servers.<os>.env overlays so the .env fallback stays complete
  (config.toml remains primary).

## 2026-06-06 1953 PDT -- LIVE end-to-end validation on Windows + GPU auto-fit (Brandon + Claude)

- Milestone: the full consolidation ran live on the Windows host (RX 9060 XT /
  Ryzen 9 9900X). Via the panel toggle: llama-server came up on :8090 (Qwen3.6 from
  the TOML windows overlay), API on :8000, `manage.py test` passed offline + health
  + live /agent/run smoke, and toggle shut both down cleanly (incl. sweeping the
  stale persona_win.pid). Confirms TOML config, per-OS overlay, detection (accel via
  the OS-GPU fallback), toggle, test playbook, and the web panel all work on real
  hardware. Logs show `thinking = 1` (Qwen3.6 thinking mode active under --jinja).
  This closes the long-open "stand up Qwen3.6 on :8090" entry point.
- GPU auto-fit fix: persona.log showed `failed to fit params to free device memory:
  n_gpu_layers already set by user to 35, abort` -- the forced 35 (a Strix-Halo-era
  value) overrode llama.cpp's VRAM auto-fit on the 16 GB discrete card. Now
  `GPU_LAYERS_PERSONA = "auto"` (or unset) makes `manage.py start_llama` OMIT
  `--n-gpu-layers` so llama-server fits the offload to VRAM itself. Set windows
  overlay (config.toml + .env fallback) to "auto"; linux stays 999 (EVO-X2 full
  offload). Default is now "auto" when unset.
- Noted (not changed): n_ctx_seq 4096 = PERSONA_CTX 16384 / 4 parallel slots (vs
  262K train) -- deliberate 4-slot config; tune PARALLEL/CTX for longer single
  convos. Vulkan lacks fused Gated Delta Net for this arch -> disabled, falls back
  (llama.cpp/Vulkan limitation, not ours).

## 2026-06-06 1937 PDT -- manage.py panel: local web control panel (Brandon + Claude)

- `manage.py panel [--port 8765] [--no-browser]`: a service control panel served by
  Python stdlib `http.server` (no new deps, and no Tkinter -- which the portable
  embeddable interpreter omits). Binds 127.0.0.1 only. Auto-opens a browser.
- Endpoints: GET `/` (self-contained dashboard HTML, no external assets), GET
  `/api/status` (cheap poll: persona/api pidfile + /health + busy + recent log tail),
  GET `/api/capabilities` (detect_host cached once at startup, not re-probed per
  poll), POST `/api/action` ({action: up|down|toggle|restart|test, which}).
- Full control: action buttons run cmd_up/down/toggle/test in a daemon worker thread
  under a single busy-lock; stdout is captured (ANSI-stripped) into a ring buffer the
  page shows live. Buttons disable while busy. Dashboard polls every 2s. The primary
  control is ONE button that relabels Start/Stop by live state (calls toggle; no
  redundant separate Start/Stop buttons), with Restart + the test runner beside it.
- Drives manage.py functions directly now; designed to re-point at the Phase 3
  daemon later with no UI change (Brandon's call: build now on manage.py).
- Validation: server mechanics + the HTML raw-string (literal \n preserved, AST OK)
  exercised off-mount (GET/POST, status JSON, action->log capture, busy guard).
  manage.py needs a Windows-side AST + `manage.py panel` smoke (mount serves stale
  reads).

## 2026-06-06 1513 PDT -- manage.py toggle + test playbook + entry shims (Brandon + Claude)

- `manage.py toggle`: start the stack if down, stop if up (the cross-platform
  "start-stop toggle"). Reads persona/api pidfiles; dispatches to cmd_up/cmd_down.
- `manage.py test [which]`: a test PLAYBOOK -- a registry of named steps dispatched
  by argument (the "named functions + dispatcher" pattern). Steps: `offline`
  (tests/test_api_offline.py), `health` (live persona+API /health), `smoke`
  (/agent/run, from smoke_agent.sh), `load` (load_test_m2b.py). Sets: `quick`
  (offline+health, default), `all` (offline+health+smoke). `test list` prints the
  playbook. rc aggregates (any fail -> nonzero; unknown step -> 2).
- Entry shims at repo root (muscle-memory names, ~4 lines each, zero logic):
  `start-stop.sh`/`.bat` -> `manage.py toggle`; `test.sh`/`.bat` -> `manage.py
  test`. Each finds the right interpreter (env/portable, else python3/python) and
  execs manage.py. Same doorknob pattern as windows_portable_run.bat.
- Folds the non-interactive parts of the bash diagnostics into one place:
  smoke_agent.sh -> `test smoke`; unified_test.sh's health checks -> `test health`
  (its interactive dialog/whiptail TUI is Linux-only with stale paths/ports
  $HOME/Live + 8080-8082 and is retired in Phase C). load_test stays a step.
- Answers the "run specific blocks of a script" question: the robust mechanism is
  the subcommand/dispatcher pattern (run one named function), which manage.py
  already is -- not sed/awk line-range execution (fragile, anti-pattern).
- Validation: playbook dispatch (list / set expansion / single step / rc aggregate
  / unknown->2) verified off-mount. manage.py needs a Windows-side AST + `test list`
  / `toggle` run (mount serves stale reads). Linux shims need +x (see todo).

## 2026-06-06 1328 PDT -- Config to TOML + windows_portable_run.bat thin shim (Brandon + Claude)

- Cross-compatible config: added `run/config.toml` as the typed single source,
  read by `manage.py` via stdlib `tomllib` (Python 3.11+; the node's pinned
  interpreter). Structure: `[base]` shared + `[linux]`/`[windows]` overlays +
  `[runtime]` (sampling/thinking/rag/embed). `load_config` flattens
  `[base]+[runtime]+[<os>]` into the same KEY names the stack already uses (values
  stringified for env). The OS table wins, replacing the `.env` overlay mechanism.
  Falls back to the legacy `run/*.env` if config.toml is absent or no TOML parser
  (so nothing breaks on a <3.11 host); the .env files are kept as that fallback
  until proven on all hosts. Machine-written artifacts (node_capabilities.json)
  stay JSON by design.
- `start_llama` now defaults `LLAMA_LIB_DIR` to `<root>/llama_cpp/build/bin` when
  unset, so config.toml needn't carry a `$HOME`-style path (the old env had a
  literal unexpanded `$HOME`).
- `windows_portable_run.bat` rewritten as a ~10-line thin shim: find the bundled
  `portable\python\python.exe` and call `manage.py up`. Removes the PortableGit/bash
  dependency for RUNNING (bash predated manage.py). Answers "why a .bat if Python is
  cross-platform": the .bat is just the OS-native double-click doorknob + finds the
  bundled interpreter (no `python` on PATH on a fresh host); all logic stays in
  manage.py. Linux's equivalent is calling the interpreter directly.
- Design note (for the curious): launcher stays Python -- the node already requires
  Python for the API/RAG stack, the bundled interpreter runs identically on all
  targets, and manage.py is pure-stdlib. A Go/Rust static bootstrap only pays off
  for a future Python-free inference-only node tier.
- Validation: TOML parse + flatten (OS-overlay wins, array->csv, all-str) verified
  off-mount with tomli. manage.py + config.toml need a Windows-side check (mount
  serves stale reads): `manage.py status` should now show the windows model/ctx
  sourced from config.toml.

## 2026-06-06 1314 PDT -- Phase B: manage.py host-detection layer (Claude)

- Implemented the detection layer in `manage.py` (consolidation Phase B). New:
  `detect_accelerators()` (3-tier, per the 1934 design), `detect_os_gpus()` +
  `_classify_gpu_vendor()` (PowerShell Win32_VideoController on Windows, lspci on
  Linux -- the cross-vendor fallback so a GPU is seen even when vendor CLIs and
  vulkaninfo are absent), `detect_vulkan_devices()`, `llama_version_info()` (build
  from `--version`; compiled backends from `--list-devices` since `--version` does
  not list them), `select_backend()`
  (select-only-what-the-binary-supports), `detect_total_ram_mb()` (ctypes on
  Windows, /proc/meminfo on Linux), and `detect_host()` building the full
  capability descriptor.
- New subcommand `manage.py capabilities`: prints the descriptor and writes
  `run/node_capabilities.json` (accel_selected + accel_present[] with per-device
  vendor/tier/backends/usable_for_llm/native_runtime, llama build/compiled
  backends, models, cpu/ram, endpoints).
- `doctor` now has an Accelerators section: lists usable backends, flags Tier-3
  devices as "present but NOT used for LLM (needs <native runtime>)", reports the
  binary's compiled backends, and the selected backend.
- H3 fix: `start_llama` is backend-aware -- only adds `--device Vulkan0` +
  GGML_VK_VISIBLE_DEVICES when the resolved backend is vulkan (LLAMA_BACKEND
  override, default vulkan on Windows / unset on Linux as before). A CUDA/ROCm/SYCL
  node no longer gets Vulkan flags forced on it.
- Validation: the detection functions were AST-parsed + unit-exercised in isolation
  (vendor classification, select-only-what-binary-supports, graceful empty result,
  capabilities JSON write) via a non-mount path, since the sandbox mount serves a
  stale truncated view of manage.py. Full manage.py still needs a Windows-side AST
  parse + `capabilities`/`doctor` run to confirm (the mount cannot parse it here).

## 2026-06-06 1234 PDT -- Broadened accelerator detection scope (Intel + non-LLM NPUs) (Brandon + Claude)

- Expanded the accel detection design in `docs/llama_build_matrix.md` beyond
  NVIDIA/AMD. Verified the current llama.cpp backend set (build.md): CUDA, HIP,
  Vulkan, SYCL (Intel GPU), OpenCL (Adreno), CANN (Ascend), MUSA (Moore Threads),
  plus in-progress OpenVINO/Hexagon/WebGPU.
- Introduced a 3-tier accelerator classification:
  - Tier 1 (selectable for llama-server): NVIDIA->CUDA, AMD->ROCm, Intel GPU->SYCL,
    Adreno->OpenCL, Ascend->CANN, Moore Threads->MUSA, all GPUs->Vulkan fallback,
    else CPU.
  - Tier 2 (detect, do not select): Intel NPU (OpenVINO in progress), Snapdragon
    Hexagon, WebGPU, IBM zDNN.
  - Tier 3 (detect, NEVER select -- own runtime, cannot load GGUF): Hailo-8/10
    (HailoRT GenAI), Google Coral (TFLite), Intel Gaudi (SynapseAI). Recorded as
    present-but-unusable-for-LLM so the mesh never routes GGUF to them.
- Key correctness rule added: "select only what the binary supports" -- the chosen
  backend must be in BOTH the detected Tier-1 set AND the llama-server compiled
  backends (parsed from `--version`), else fall back to CPU + point at the right
  build.
- Added the Intel SYCL build recipe (`-DGGML_SYCL=ON` + oneAPI) and brief
  OpenCL/CANN/MUSA flags; broadened the probe list (sycl-ls/xpu-smi, vulkaninfo
  vendor sweep, npu-smi, hailortcli, hl-smi, intel_vpu). Reworked the capability
  schema to `accel_selected` + `accel_present[]` (per-device vendor/tier/backends/
  usable_for_llm/native_runtime).
- Support matrix in `docs/portability_audit.md` updated to add Intel SYCL/Vulkan and
  the detected-but-not-served NPU class. Still design-stage; implementation lands
  with the Phase B `manage.py` detection layer + `manage.py capabilities`.

## 2026-06-06 1225 PDT -- Pre-consolidation script/config review + Phase A fixes (Brandon + Claude)

- Added `docs/script_consolidation_review.md`: full pre-commit evaluation of every
  config file + lifecycle script against the manage.py-as-bootstrap goal (detect
  OS/arch/resources -> run compatible stack -> deactivate vestigial). Findings
  graded C/H/M/L with fix directions + a consolidation plan (detection layer,
  retire bash sprawl, absorb setup into manage.py).
- Applied the Phase A (low-risk, pre-commit) fixes:
  - C3 (manage.py host-awareness): `start_llama` now resolves the model via
    `resolve_model()` (configured PERSONA_MODEL, else the sole GGUF in models/, else
    a clear error) instead of trusting the Linux env on every OS; `load_config` now
    layers a per-OS overlay `run/llama-servers.<os>.env` over the shared env. Added
    `run/llama-servers.windows.env` (Qwen3.6-35B-A3B-UD-Q5_K_XL, ctx 16384, 35 gpu
    layers) so a Windows host stops trying to load the EVO-X2 Instruct-2507 / full
    offload. Fixes a wrong-model + over-offload bug before manage.py ships.
  - C2 (`setup_native_stack.sh`): stopped regenerating `requirements.txt` from a
    stale inline heredoc (which dropped the posthog<3 + numpy pins and the
    dependency tiers); now `pip install -r` the committed lean file, with an opt-in
    `WITH_TORCH_EMBED=1` path for the torch extra. Closes a clobber that silently
    undid Phase 0.5 #2.
  - H1 (port drift): `server.py` PERSONA_PORT default 8080 -> 8090;
    `start_llama_server_win.sh` PORT default 8080 -> 8090.
  - H2 (`start_llama_servers.sh`): added the missing `--jinja` (Linux launcher now
    matches the Windows launcher + manage.py; restores reasoning_content/T2.4).
  - M1 (`setup_native_stack.sh`): clone URL ggerganov -> ggml-org.
  - L1 (`load_test_m2b.py`): DEFAULT_ENDPOINT/HEALTH 8080 -> 8090.
- Deferred to the consolidation effort (documented, not blockers): H3 accel
  hardcoded to Vulkan in the bash launchers (needs the detection layer; manage.py
  Linux path already omits --device), H4 persona_win.pid vs persona.pid, M2
  scientist->reasoning rename, M3 dual interpreter strategy, M4 3.14 req regen, M5
  Python `manage.py setup` to remove the last bash dependency, L2/L3 cosmetics.
- Validation: bash `-n` clean for the edited shell scripts; load_test AST OK.
  server.py + manage.py need a Windows-side parse + offline test (sandbox mount
  serves a stale truncated view of both -- see git-runs-windows-side note).

## 2026-06-06 1202 PDT -- llama.cpp build/acquire matrix doc (Phase 0.5 #3) (Claude)

- Added `docs/llama_build_matrix.md` (audit H2 / roadmap Phase 0.5 #3): per-accel
  build + acquire guide. Covers prebuilt (Windows x64 assets per accel incl. the
  CUDA cudart pairing) and build-from-source (CPU / CUDA `-DGGML_CUDA=ON` / ROCm
  `-DGGML_HIP=ON -DGPU_TARGETS=...` / Vulkan `-DGGML_VULKAN=ON`), Win/Linux/ARM64,
  with GPU target notes (gfx1030/1100/1151; Strix Halo -> Vulkan when ROCm is
  uneven). Binary placement aligned to manage.py `llama_binary()`
  (llama_cpp/windows vs llama_cpp/build/bin; LLAMA_BIN/LLAMA_LIB_DIR overrides).
  Build acceptance = `manage.py up --llama-only` + `doctor --deep`.
- Designed the capability-advertising hook: a `node_capabilities.json` descriptor
  (os/arch/accel/llama_build/backend/models/ctx/embedder_backend/endpoints) +
  best-effort detection (nvidia-smi/rocminfo/vulkaninfo + `llama-server --version`)
  + integration steps (manage.py capabilities -> /health -> Phase 10 signed KV
  roster). Only `manage.py capabilities` is near-term; mesh wiring is Phase 10.
- Roadmap Phase 0.5 #3 -> [~] (matrix documented; capability hook impl pending).
  Build flags verified against current ggml-org/llama.cpp docs + releases.

## 2026-06-06 1159 PDT -- Windows-side validation of Phase 0.5 #1/#2 (Brandon + Claude)

- Closed the validation gap from the 1853/1838 entries (sandbox mount could not
  parse server.py). Run Windows-side with the portable interpreter:
  - `python -c "import ast; ast.parse(open('services/api/server.py').read())"` -> AST OK.
  - `python tests/test_api_offline.py` -> RESULT: ALL PASS (14 checks: /, favicon,
    /health, /v1/models, usage token counts, SSE streaming envelope + [DONE],
    /chat_submit removed). Confirms the embedder init refactor + EMBED_BACKEND
    selection import and serve cleanly; /health returns 200 (now with
    embedder_backend). Lean fastembed default path proven.
  - Note: the sentence-transformers backend itself is exercised only when the
    opt-in torch extra is installed (not done here); the lean default tier is the
    validated deliverable.
- Roadmap: Phase 0.5 #2 -> [x]. #1 (manage.py) stays [~] (status/doctor validated;
  up/down still need a live-host serving pass).

## 2026-06-06 1153 PDT -- Dependency tiers: lean default + torch opt-in (Phase 0.5 #2) (Claude)

- `services/api/requirements.txt` now the LEAN tier: dropped
  `sentence-transformers` (the only torch puller). Default node runs RAG on
  fastembed/onnxruntime alone -- no torch. The running code already used only
  fastembed; the dropped dep was an unused notional fallback.
- New `services/api/requirements-embed-torch.txt` -- OPT-IN heavy extra pinning
  sentence-transformers (>=2.6,<4). Lean nodes do not install it.
- `services/api/server.py`: made the fallback real and selectable.
  - New `EMBED_BACKEND` env (auto | fastembed | sentence-transformers; default
    auto). auto tries fastembed then sentence-transformers.
  - Guarded `from sentence_transformers import SentenceTransformer` (None if
    absent, same pattern as fastembed/chromadb).
  - Refactored embedder init into `_init_fastembed` / `_init_sentence_transformers`
    returning (embedder, error); records active backend in `_embedder_backend`,
    aggregates init errors into `_embedder_error`.
  - `_embed` dispatches by backend (ST uses `.encode([text])[0].tolist()`,
    fastembed unchanged).
  - `/health` now reports `embedder_backend`.
  - Default behavior unchanged on a lean node: EMBED_BACKEND=auto + no ST installed
    -> fastembed exactly as before.
- VALIDATION GAP: server.py edits are confirmed correct via the authoritative
  Read tool (imports/init/dispatch/health all clean + balanced), but were NOT
  AST-parsed: the Linux sandbox mount served a stale/truncated view of server.py
  (32886 bytes / 979 lines vs the real 1021), so any sandbox parse/wc/md5 is
  meaningless for this file. Run a real parse Windows-side before relying on it:
  `python -c "import ast,sys; ast.parse(open('services/api/server.py').read())"`
  (or run tests/test_api_offline.py). Mount-unreliability recorded for future runs.

## 2026-06-06 1138 PDT -- manage.py cross-platform launcher (Phase 0.5 #1) (Claude)

- Added `manage.py` at repo root: a pure-stdlib (3.8+) cross-platform lifecycle
  launcher with `up` / `down` / `status` / `doctor`, retiring the bash-only
  start/stop/status/doctor split for core lifecycle (Phase 0.5 top blocker).
- Ports: `start_llama_server_win.sh` + `start_api.sh` (up), `stop_llama_servers.sh`
  + api stop (down), `status.sh` (status), `doctor.sh` incl. the embedded
  safe-config T1-gate check (doctor). Reads `run/llama-servers.env` + `run/config.env`
  via a built-in dotenv parser; no shell sourcing.
- Cross-platform process model: detached spawn (DETACHED_PROCESS+NEW_PROCESS_GROUP
  on Windows, start_new_session on POSIX); liveness via OpenProcess/GetExitCodeProcess
  on Windows (avoids os.kill(pid,0), which TerminateProcesses on Windows) and
  os.kill(pid,0) on POSIX; stop via taskkill /T[/F] on Windows, SIGTERM->SIGKILL on
  POSIX. Binary/interpreter resolution branches per-OS (llama_cpp/windows vs
  llama_cpp/build; portable/python vs env/bin), with LLAMA_BIN/AI_ROOT overrides.
- Safe-config validation reimplemented natively with a PyYAML path and a regex
  fallback; both agree with doctor.sh (PASS) against the default profile.
- Validation: AST OK; `--help`, `status`, `doctor` run clean against the repo with
  services down; install md5 verified against source. `up`/`down` spawn/kill paths
  mirror the bash scripts but are NOT yet live-host tested (no llama-server/model in
  the sandbox). Roadmap Phase 0.5 launcher item -> [~]. Apple/Metal out of scope.

## 2026-06-05 1753 PDT -- Handoff written (handoff_persona_20260605_1753) (Brandon + Claude)

- Froze the session's work (roadmap.md + distributed-mesh design + portability
  audit + the sys.executable fix) into
  `archive/handoffs/handoff_persona_20260605_1753.md`. Next-session entry point =
  Phase 0.5 portability hardening (manage.py launcher + dependency tiers),
  alongside the still-open Phase 1 :8090 llama-server standup. Includes the
  uncommitted-files list + Windows-side commit guidance.

## 2026-06-05 1747 PDT -- Portability audit + cross-OS hardening track; /agent/run python3 fix (Brandon + Claude)

- Combed the stack for cross-OS/arch weak links given the system-agnostic node
  goal. New `docs/portability_audit.md`: severity-ranked findings + a target
  support matrix -- Windows + Linux, x86-64 + ARM64, CPU/CUDA/ROCm/Vulkan. Apple
  (macOS / Apple Silicon / Metal) is not a consideration -- no effort spent, not
  tested, but not deliberately broken either (Brandon's decision).
- FIX (server.py): `/agent/run` spawned the worker as literal `python3`, which
  fails on the Windows portable flow (interpreter is python.exe, no python3 on
  PATH). Now uses `sys.executable` (+ added `import sys`).
- Findings: the ops/lifecycle layer is bash-only (top blocker) -> plan a single
  `manage.py` launcher; torch/sentence-transformers is the heaviest, most
  arch-variable dep and only the FALLBACK embedder -> make it an opt-in extra and
  default a lean node to fastembed/onnxruntime; GPU backend is per-node (build
  matrix + capability advertising); the Phase 3 daemon's planned Unix-socket IPC
  is POSIX-only -> choose loopback TCP / NATS; egress netns/iptables is Linux-only
  -> WireGuard mesh + host firewall as the portable baseline.
- Added `roadmap.md` Phase 0.5 (cross-OS/arch portability hardening, IN PROGRESS)
  with exit gate: a node bootstraps, runs, self-checks, and serves /chat on
  Win x64 / Linux x64 / Linux ARM64 (CPU + one GPU accel) through one entrypoint,
  no bash for lifecycle. Pointer added to knowledge.md.

## 2026-06-05 1735 PDT -- Captured distributed node-mesh design (docs/distributed_nodes.md + roadmap Phase 10) (Brandon + Claude)

- New `docs/distributed_nodes.md`: handoff-quality design note for a decentralized,
  system-agnostic cooperative node mesh (BOINC / Folding@home inspired). Captures
  the decisions from the 2026-06-05/06 discussion.
- Key decisions: distribute TASKS not single inferences (single-inference pooling
  is bandwidth-bound; lean on task parallelism + specialization + redundant
  execution/validation). Transport = NATS + JetStream, one per-node server
  clustered as equals (no central broker); durable state on a 3/5-node JetStream
  Raft core, ephemeral nodes as clients/leaf. Auth = single shared admission token
  (rotation = hard evict); identity/tracking via NATS connection log
  ($SYS/connz, by hostname) + self-generated per-node keypairs (pubkey = node id,
  signs heartbeats/results) + TTL'd KV roster; bad actors handled by
  validation/quorum + advisory key deny-list (auth keeps strangers out, validation
  keeps bad results out). Egress posture reconciled by running the mesh over
  WireGuard.
- Added `roadmap.md` Phase 10 (extended track) with staged, independently testable
  gates: Stage 0 LLAMA_HOST offload (no new infra) -> Stage 1 2-node work queue +
  reclaim -> Stage 2 roster + node keys + capability routing -> Stage 3 HA core +
  reputation/evict. Pointers added to knowledge.md (Pointers) and the roadmap
  read-me note. Near-term experiment is Stage 0 only.

## 2026-06-05 1625 PDT -- Added roadmap.md (phased feature/completion tracker) (Brandon + Claude)

- New `roadmap.md`: single source of truth for feature/track completion status,
  as a phase ladder (Phase 0 Foundation + Phases 1-8 mirroring knowledge.md's
  architecture roadmap; Phase 9 deleted). Each phase carries a status checklist
  and an Exit Gate (testable acceptance) so a phase is "locked" to a functional
  state before the next begins.
- Boundary: roadmap.md owns status; todo.md = next-up pointers; changelog.md =
  when a gate flips; knowledge.md = architecture. Wired pointers into todo.md
  (header + rules of the road), knowledge.md (repo map + architecture-roadmap
  intro), and WORKFLOW.md (project-local fourth-file note).
- Initial statuses: Phase 0 GREEN (foundation/portable runtime/env). Phase 1
  IN PROGRESS (core serving; the live :8090 standup is the open gate). Phase 8
  FOUNDATION STARTED (T1 safe-config done; H1-H6 gated on M6). Phases 2-3, 6-7
  not started; 4-5 optional; extended items (vision, speculative decoding,
  dual-memory, model re-eval) deferred.

## 2026-06-05 1612 PDT -- API gap fixes: streaming, prompt_tokens, /agent/run, /chat_submit, root route (Brandon + Claude)

- /v1/chat/completions now honors `stream`: stream=true returns text/event-stream
  with OpenAI `chat.completion.chunk` deltas ending in `data: [DONE]`. Pseudo-stream
  by design -- the reply is finalized through sanitize_persona_reply first (the
  sanitizer needs the whole text), then chunked word-wise; not token-by-token from
  the model. server.py:946-960.
- /v1/chat/completions `usage` now reports real token counts. query_llama captures
  llama.cpp `tokens_evaluated` alongside `tokens_predicted`; prompt_tokens =
  tokens_evaluated, completion_tokens = tokens_predicted, total = sum (was
  prompt_tokens hardcoded 0). server.py:513-515, 943-944, 968-972.
- /agent/run no longer blocks the event loop: the blocking
  subprocess.run(timeout=300) is offloaded via asyncio.to_thread. Same
  request/response shape. server.py:729-733.
- /chat_submit disabled stub + SubmitRequest model REMOVED (was "disabled in this
  build"). Jobs persistence helpers (_job_set / _persist_job_event /
  _load_persisted_jobs, /jobs/{id}) kept for a future real async-job
  implementation. No external code refs (docs/archive only).
- Added GET / (status JSON: service/status/docs/health) and GET /favicon.ico (204)
  so the bare base URL stops 404ing (/health was always present and thorough).
- Validated offline: FastAPI TestClient with query_llama monkeypatched, 15/15
  checks pass (/, favicon, /health, /v1/models, prompt_tokens=42 / completion=11 /
  total=53, SSE envelope + [DONE] + content reconstruction, /chat_submit -> 404).
  Live generation still needs the llama-server on :8090 (entry point unchanged).
- Earlier this session (env; already applied Windows-side): bootstrap
  scripts/bootstrap_portable_python.ps1 pins `setuptools<82` in the pip-upgrade
  step (stops the install->downgrade bounce against torch's setuptools<82 pin and
  the scary resolver ERROR); services/api/requirements.txt pins
  `posthog>=2.4.0,<3.0.0` (chromadb 0.6.3 calls the old posthog capture()
  signature; posthog 7.x broke it -- the actual fix for the telemetry errors,
  complementing ANONYMIZED_TELEMETRY=False). Re-run confirmed: setuptools held at
  81.0.0, posthog downgraded 7.17.0 -> 2.5.0, startup log clean.

## 2026-06-05 1526 PDT -- Portable 3.11.9 services env operational (Brandon + Claude)

- Bootstrap succeeded on the Python 3.11.9 embeddable in portable/python. The full
  committed services/api/requirements.txt installed cleanly (all native deps got
  3.11 wheels, no source builds) and the core import smoke test passed
  (`core imports OK; pydantic 2.13.4`). End-to-end confirmation of the 3.11
  compatibility call.
- Resolved versions of note: chromadb 0.6.3 (within the intentional <1.0.0 pin,
  matches server.py's 0.5.x-era client API), pypika 0.51.1, chroma-hnswlib 0.7.6,
  fastembed 0.8.0, onnxruntime 1.26.0, tokenizers 0.22.2, torch 2.12.0, numpy
  2.4.6, fastapi 0.136.3, uvicorn 0.49.0, httptools 0.8.0, pydantic 2.13.4 /
  pydantic-core 2.46.4, tenacity 8.5.0.
- Fixed two bootstrap blockers found while running it Windows-side:
  1. PowerShell default execution policy blocked the .ps1. Added
     scripts/bootstrap_portable_python.bat (invokes powershell -ExecutionPolicy
     Bypass), matching the repo's windows_portable_*.bat convention. (Brandon also
     set CurrentUser RemoteSigned.)
  2. The .ps1 used `$ErrorActionPreference = "Stop"`, which makes PowerShell treat
     ANY native-command stderr as terminating -- so the expected "pip not yet
     installed" stderr (and pip's normal warnings) aborted the run. Rewrote to drop
     the global Stop, route native calls through an Invoke-Native helper that
     checks $LASTEXITCODE, and keep -ErrorAction Stop only on Invoke-WebRequest.
- Bootstrap flags: default installs the full stack; -CoreOnly = API-only; -Run =
  launch uvicorn on 127.0.0.1:8000 (sets AI_ROOT/profile env, sources run/config.env).
- Not yet exercised live: API boot + /health (which now reports the T2.1
  sampling_presets) -- next validation step. /chat needs a llama-server on :8090.

## 2026-06-05 1529 PDT -- Live API boot on portable 3.11.9; port-source fix (Brandon + Claude)

- Booted uvicorn on the portable 3.11.9 and hit /health: 200 OK. Validates the
  stack end-to-end on Windows. T2.1 confirmed live: sampling_presets returns the
  exact no_think (0.7/pp1.5) and think (0.6/pp0.0) presets. embedder_ok=true and
  chroma_ok=true -- fastembed downloaded bge-small-en-v1.5-onnx and chromadb 0.6.3
  initialized at runtime against server.py's code (no API drift from the 0.5.x
  assumption). RAG stack works on 3.11.9, not just imports.
- BUG found + fixed: /health showed unified_endpoint on :8080, not :8090.
  server.py defaults PERSONA_PORT=8080, and the bootstrap -Run path only sourced
  run/config.env (sampling/thinking), not run/llama-servers.env (PERSONA_PORT=8090).
  Fix: bootstrap -Run now sources llama-servers.env THEN config.env (same order as
  start_api.sh), via a stricter env-var regex that skips comments. Port lives in
  llama-servers.env (single source); not duplicated into config.env.
- config.env additions (consolidation point): RAG_ENABLED=1 (parity with
  start_api.sh) and ANONYMIZED_TELEMETRY=False (silences the chromadb 0.6.3
  posthog telemetry error seen at startup -- "capture() takes 1 positional
  argument but 3 were given" -- and keeps Chroma from phoning home, matching the
  offline design).
- Cosmetic, not addressed: fastembed/HF symlink cache warning on Windows (needs
  Developer Mode or admin for symlinks; harmless, set HF_HUB_DISABLE_SYMLINKS_
  WARNING=1 to silence if desired).

## 2026-06-04 1828 PDT -- Decision: services interpreter = Python 3.11.9 embeddable (Brandon + Claude)

- Brandon chose Python 3.11.9 (Windows x64 embeddable zip) for the portable
  services interpreter, kept in portable/python. Rationale: 3.11.9 is the LAST
  3.11 with official binaries (3.11 is security-only/source-only since, PEP 664,
  to Oct 2027); 3.11 runs the COMPLETE stack incl. ChromaDB RAG and matches the
  Hermes interpreter version. localhost-only/offline posture makes the missing
  post-3.11.9 CVE fixes a low concern.
- Bootstrap repointed: `scripts/bootstrap_portable_python.ps1` now installs the
  committed `services/api/requirements.txt` (full tested stack) instead of the
  3.14 subset; `-WithRag` replaced by `-CoreOnly` (full stack is the default on
  3.11; -CoreOnly does an API-only install). The python*._pth glob already matches
  python311._pth, so the embeddable handling is unchanged.
- CORRECTION to the 0118 entry: `services/api/requirements.txt`'s
  `chromadb>=0.5.0,<1.0.0` is an INTENTIONAL API pin (server.py targets the
  chromadb 0.5.x client API), not staleness. On 3.11 the committed requirements.txt
  installs the full stack as-is; do not bump chromadb to 1.x without porting
  server.py's chromadb usage. Updated docs/py314_compatibility.md accordingly.
- The `requirements-py314.txt` / `requirements-py314-rag.txt` files are retained
  (mount blocks deletion) but are now scoped strictly as the 3.14-fallback
  reference (API-only-on-3.14); the 3.11 path does not use them.

## 2026-06-04 1818 PDT -- Python 3.14 compat validation + portable bootstrap (Brandon + Claude)

- Brandon added a Windows embeddable CPython 3.14 at `portable/python/`. Validated
  the whole stack against 3.14 (win_amd64) before building a bootstrap.
- Finding: the FastAPI API + T2.1 run on 3.14. Single hard blocker is ChromaDB
  (latest 1.5.9 depends on pypika -> uses ast.Str, removed in 3.14). server.py
  imports Chroma fail-soft, so the API runs on 3.14 with the Chroma RAG layer off.
  All other deps are 3.14-ready as of late May 2026: onnxruntime 1.26.0 (cp314
  win_amd64), pydantic-core 2.47.0, httptools 0.8.0, grpcio, tokenizers 0.22.2
  (abi3), numpy, fastembed (unblocked by onnxruntime 1.26). Hermes wants Python
  3.11 (separate env_hermes), not 3.14.
- Recommendation recorded: for COMPLETE single-interpreter support incl. ChromaDB
  RAG, use Python 3.12 (3.13 likely-but-rough, 3.14 API-only). The 3.14 block is a
  concrete nudge to bring the Qdrant migration (Phase 2a) forward -- Qdrant +
  fastembed is a fully-3.14-compatible RAG path.
- Added `docs/py314_compatibility.md` (full report + sources + version rec),
  `services/api/requirements-py314.txt` (3.14-ready core; the existing
  requirements.txt is stale -- chromadb<1.0.0 excludes all current chromadb),
  `services/api/requirements-py314-rag.txt` (fastembed/onnxruntime; Chroma omitted),
  and `scripts/bootstrap_portable_python.ps1` (enables site in the embeddable
  ._pth, get-pip bootstrap, installs core, optional -WithRag, optional -Run to
  launch uvicorn). Bootstrap is Windows-side and unrun in this Linux sandbox.

## 2026-06-04 1808 PDT -- T2.1: per-mode sampling presets in server.py + config.env (Brandon + Claude)

- Started T2 (core integration). T2.1 done: sampling is no longer hardcoded
  temperature=0.7. server.py now selects a per-mode preset by routing +
  thinking-mode toggle.
- server.py: added `resolve_think(topic, mode) -> think|no_think` as the single
  source of truth; `thinking_prefix()` now derives from it (behavior unchanged);
  new `sampling_for(topic, mode) -> (key, temperature, extra)`. `SAMPLING_PRESETS`
  (no_think / think) read from env with Qwen3.6 defaults (no_think:
  temp0.7/top_p0.8/top_k20/min_p0.0/presence_penalty1.5; think:
  temp0.6/top_p0.95/top_k20/min_p0.0/presence_penalty0.0), mirroring the
  per-profile config.yaml.
- Wired both handlers: /chat and /v1/chat/completions select the preset and pass
  top_p/top_k/min_p/presence_penalty to query_llama via its existing `extra` arg.
  /v1 still honors an explicit request `temperature` (overrides the preset temp).
  Added optional `thinking_mode` to ChatRequest + OA_ChatCompletionsReq for
  per-request override. /health now reports `sampling_presets`; /chat debug
  reports the selected `sampling_preset` + resolved sampling.
- New `run/config.env` (git-allowlisted) as the consolidation point for runtime
  tunables (THINKING_MODE_* + SAMPLING_*). `start_api.sh` now sources it after
  llama-servers.env (overrides). server.py falls back to correct defaults if
  config.env is absent.
- Verified: py_compile clean; start_api.sh bash -n clean; function-level test
  (heavy imports stubbed) confirms chat->no_think preset, science->think preset,
  on/off overrides, prefix/preset consistency, and config.env env override flows
  through. Live HTTP path not exercised (no model in sandbox); T2.1 gate is the
  preset-selection logic, which is covered.
- Scope note: did NOT fix start_api.sh's other staleness (PERSONA_PORT default
  8080 line, scientist banners, misplaced MEMORY_DISTILL export) -- still logged.

## 2026-06-04 1758 PDT -- Modernized init_profiles.sh + doctor.sh to 2-file profiles (Brandon + Claude)

- Closed the last script-drift item from the T1 handoff. Both scripts now match the
  M5 unified-topology reality (SOUL.md + .hermes.md; single persona server).
- `init_profiles.sh`: default-profile scaffold and the normalize loop now write
  SOUL.md (identity/personality/communication style) and .hermes.md (hard rules/
  output format) instead of the retired persona.md/style.md/system_rules.md. The
  persona README heredoc updated to list SOUL.md / .hermes.md / config.yaml.
  config.yaml generation (T1.2) and memory subdir creation unchanged.
- `doctor.sh`: profile check now verifies SOUL.md + .hermes.md + config.yaml; the
  retired scientist port/model is gone (env-load defaults to the unified
  PERSONA_PORT=8090 + Instruct-2507 model; model-presence loop, pidfile check,
  /health check, and smoke test no longer reference a scientist server).
- Verified: bash -n clean on both; grep confirms no remaining persona.md/style.md/
  system_rules.md or scientist/SCIENTIST references; init_profiles dry-run into a
  temp root scaffolds SOUL.md/.hermes.md/config.yaml; doctor.sh reports all three
  profile files present and `T1 GATE: safe_config=pass`.

## 2026-06-04 0317 PDT -- Modernized setup_native_stack.sh env writer (Brandon + Claude)

- Removed the clobber hazard flagged in the 0755 handoff. `setup_native_stack.sh`
  no longer writes the retired multi-server `run/llama-servers.env`
  (8080/8081/8082 persona/reasoning/coder). It now writes the validated unified
  single-server topology (PERSONA_PORT=8090, Qwen3-30B-A3B-Instruct-2507 Q5_K_M,
  CTX 32768, 4 parallel slots, q8_0 KV cache, BATCH/UBATCH 512), mirroring the
  live `run/llama-servers.env`.
- Made the writer non-destructive: if `run/llama-servers.env` already exists it is
  left untouched; `FORCE_ENV=1` overwrites but first copies the current file to a
  timestamped `.bak`. A fresh setup with no env still gets the template. Verified
  in sandbox: write-when-absent, preserve-on-rerun, and backup+rewrite under
  FORCE_ENV all behave correctly; bash -n clean (mount lag noted below).
- Updated the stale "Next steps" footer: single unified model (not the three
  retired gguf names), and real script names (init_profiles.sh / start_llama_
  servers.sh / start_api.sh / doctor.sh / load_test_m2b.py; the referenced
  bench.sh does not exist).
- The env-writer content is comment-free (executable settings only).
- Ops note: the Linux sandbox mount of D:\ served a stale, mid-line-truncated view
  of this file after the edit and did not converge; syntax was verified via the
  Windows-side file API plus a reconstructed-structure bash -n. Reinforces the
  standing "git/verify Windows-side for D:\Projects" rule.

## 2026-06-04 0055 PDT -- T1 implemented: env_hermes + per-profile safe-config (Brandon + Claude)

- Decision recorded: pursue the Qwen3.6 swap track (Next #1 fork resolved in favor
  of the swap; T0 fully passed 2026-06-03). T1 is the first swap tier.
- T1.2 (per-profile Hermes config.yaml): added `write_hermes_config()` to
  `scripts/init_profiles.sh`; it emits a safe-config-conformant `config.yaml` into
  each profile dir (idempotent -- skips if present, so Hermes-managed edits are not
  clobbered). Shipped concrete `persona/profiles/default/config.yaml` and
  `persona/profiles/test/config.yaml`. Invariants: model.provider=custom pinned to
  http://127.0.0.1:8090/v1, empty fallback_model (no cloud failover), all
  auxiliary.* provider=main, egress tools disabled (web_search/web_extract/
  web_crawl/browser_*), redact_secrets on. Qwen3.6 per-mode sampling under
  model.sampling (default temp0.7/top_p0.8/top_k20/presence_penalty1.5; thinking
  temp0.6/top_p0.95/top_k20/presence_penalty0.0).
- T1.1 (env_hermes venv + ops awareness): `scripts/setup_native_stack.sh` now
  creates an isolated `env_hermes` venv and runs `pip install hermes-agent`
  (SKIP_HERMES=1 to skip; non-fatal on failure). `scripts/status.sh` gained a
  Hermes section (env_hermes venv + hermes binary + default config.yaml presence).
  `scripts/doctor.sh` gained an env_hermes venv check and the T1 conformance gate.
- T1 gate (doctor.sh): validates the default profile config.yaml against the
  safe-config schema via PyYAML (env_hermes/env python preferred; grep fallback if
  no PyYAML). Prints `T1 GATE: env_hermes_installed=<y/n> safe_config=<pass/fail>`.
  STRICT_GATE=1 makes a non-green gate exit 2. Verified: real default config
  passes; a tampered config (cloud fallback + cloud auxiliary) correctly fails.
- AI_ROOT default flipped to `$HOME/Git/Project_Persona` in the three remaining
  legacy holdouts touched here (setup_native_stack.sh, init_profiles.sh,
  doctor.sh), completing the AI_ROOT-drift campaign (start/stop/clean were fixed
  2026-05-19 / 2026-06-03).
- Hermes config schema confirmed against current docs (config v17+, MIT, 2026):
  config.yaml in HERMES_HOME; provider:custom for local endpoint; "main" valid
  only in auxiliary/compression/fallback; secrets in .env not config.yaml. Exact
  Hermes key paths for model.sampling and tools.disabled are schema-PROVISIONAL --
  validate against the installed hermes-agent in H1 (the 2026-05-11 Appendix A
  already flagged this). See handoff_persona_20260604_0055.
- Logged pre-existing drift NOT fixed here (see todo.md): setup_native_stack.sh
  still writes the retired multi-server llama-servers.env (8080/8081/8082
  persona/reasoning/coder) -- a clobber hazard; init_profiles.sh + doctor.sh still
  scaffold/check the retired 3-file profile (persona.md/style.md/system_rules.md)
  instead of SOUL.md/.hermes.md; doctor.sh still probes a scientist port.

## 2026-06-03 1605 PDT -- T0.2 PASSED; Qwen3.6 tool-calling verified (Brandon + Claude)

- Ran T0.2 on the Windows prototype (RX 9060 XT 16 GB, Vulkan, 35 GPU layers,
  llama.cpp build b9219). Qwen3.6-35B-A3B-UD-Q5_K_XL returned a clean tool call:
  `finish_reason=tool_calls`, `tool_calls[0].function` = get_current_weather with
  `arguments={"city":"Tokyo"}` (valid JSON). Acceptance "parseable tool call
  emitted" met. T0 is now fully closed (T0.1 + T0.2), resolving the 2140 caveat.
- Required `--jinja` on llama-server for the Hermes 2 Pro template to emit the
  tool-call field; added `--jinja` to `scripts/start_llama_server_win.sh`.
- Notable: reasoning came back in a separate `reasoning_content` field with
  `content` empty -- so llama.cpp strips `<think>` from the user-facing channel
  server-side under `--jinja`. This de-risks T2.4 (`<think>` stripping) for the
  swap path; revisit whether a persona-side chokepoint is still needed.
- Ops note: the backgrounding launcher (`start_llama_server_win.sh` invoked via
  `bash.exe scripts/...` from PowerShell) did not keep llama-server alive --
  server torn down mid-generation. Ran foreground in a dedicated window for the
  test. If the Windows path becomes first-class, the launcher needs a real
  detach (nohup/disown equivalent) or a Windows service wrapper.
- Added `scripts/t0_2_payload.json` (the test request body).
- Qwen3.6 swap path now unblocked at T1; the Next #1 decision is a pure priority
  call, no remaining gate.

## 2026-06-03 1440 PDT -- Clarified Qwen3.6 T0 gate status; T0.2 still open (Brandon + Claude)

- Correction to the 0439 reconciliation: "T0 PASSED" was overstated. T0 has two
  sub-gates. Only T0.1 (model loads + generates coherent output) passed
  (2026-05-18). T0.2 (tool-calling round-trip -- model emits a parseable tool
  call) was never run.
- T0.2 is the gate that actually unblocks Hermes Phase 8 (Hermes drives the
  model via tool calls), so the Qwen3.6 swap path does NOT start at T1 -- it
  starts at T0.2.
- Likely a pass: chat template auto-detected as Hermes 2 Pro (ChatML superset,
  tool-calling compatible). If T0.2 fails (call emitted as plain text, not a
  `tool_calls` field), remedy is a GBNF grammar (~1-2h, no arch change).
- Added runnable procedure `scripts/t0_2_tool_calling_test.md` (preconditions,
  --jinja note, curl round-trip, pass/fail criteria, result-recording steps).
- Updated `todo.md`: caveat on the "Just finished" reconciliation, and Next #1
  now carries sub-item 1a (run T0.2 before T1).

## 2026-06-03 1424 PDT -- Fixed AI_ROOT drift in stop/clean scripts (Brandon + Claude)

- `scripts/stop_llama_servers.sh` line 3: AI_ROOT default flipped from
  `$HOME/Live/AIStack/Project_Persona` to `$HOME/Git/Project_Persona`.
- `scripts/clean.sh` line 3: same flip.
- Both now match `start_llama_servers.sh`; run without AI_ROOT exported they no
  longer target the legacy workspace. Closes todo Next #1 (the start_api/stop_api
  equivalent was fixed 05-19).

## 2026-06-03 1418 PDT -- Restarted EVO-X2 stack; healthy (Brandon + Claude)

- Restarted via `scripts/start_llama_servers.sh` (auto-cleared the orphan pidfile,
  new persona pid 20606) and `scripts/start_api.sh` (pid 20683). :8090/health ok,
  :8000/health all green, /v1/chat/completions smoke returned a real completion.
- Found AI_ROOT drift while reading scripts: `stop_llama_servers.sh` and
  `clean.sh` still default AI_ROOT to the legacy `$HOME/Live/AIStack/Project_Persona`
  (start_llama_servers.sh uses `$HOME/Git/Project_Persona`). Logged as todo Next #1.
- Smoke reconfirmed usage.prompt_tokens=0 and showed mild output repetition (the
  persona emitted its "Next actions" scaffolding twice on a trivial greeting).

## 2026-06-03 1412 PDT -- CORRECTION: 05-23 shutdown was clean, not the ghost (Brandon + Claude)

- Pulled EVO-X2 logs. Both api.log and persona.log show a GRACEFUL shutdown at
  ~05-23 0921: api.log ends "Application shutdown complete / Finished server
  process [1813299]"; persona.log ends "operator(): cleaning up before exit..."
  with a memory-breakdown dump (llama-server's clean signal-handler path). No
  OOM / segfault (journalctl -k empty).
- Corrects the 2026-06-03 2108 entry below: the down-state is NOT an ungraceful
  stability-ghost recurrence. The stack was cleanly stopped after the M2b run and
  never restarted. The 05-19/20 ghost remains a separate, still-unexplained event;
  it did not recur on 05-23.
- The stale `run/persona.pid` is orphaned pidfile hygiene, not a crash:
  llama-server was stopped by a direct signal / Ctrl-C rather than
  `stop_llama_servers.sh`, so the wrapper never removed the pidfile. Minor real
  issue: stop-path vs pidfile cleanup (and/or start should clear stale pidfiles).
- Aside: old coder/reasoning/scientist logs (Apr 1) still present because the
  Phase 3 daemon "wipe logs on start" contract is not implemented yet.

## 2026-06-03 1408 PDT -- EVO-X2 live state checked over SSH (Brandon + Claude)

- Ran status + health checks on EVO-X2. Whole stack DOWN: API not running,
  llama-server not running (stale `run/persona.pid` left behind), nothing
  listening on 8090/8000/3000.
- Confirmed deployed model is Instruct-2507: config + on-disk file
  `Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf` (21G) present; no Qwen3.6 on
  EVO-X2. OpenWebUI confirmed not deployed (:3000 down). Both confirm the 05-23
  KNOWLEDGE.md state.
- Stale pidfile is the unclean-shutdown signature of the stability ghost: the
  stack died ungracefully after the 05-23 M2b revival and stayed down. Root cause
  still unidentified. Closed the three live-check items in todo.md; new top
  action is a clean restart with log/dmesg capture of the prior death.

## 2026-06-02 2139 PDT -- Reconciled the KNOWLEDGE/HANDOFF discrepancy (Claude)

- Resolved the conflict between the archived KNOWLEDGE.md (05-23) and HANDOFF.md
  (05-16) using code, config, and git history rather than assuming the newer doc
  wins. Each was right about different things.
- Deployment: KNOWLEDGE.md correct. `run/llama-servers.env` confirms
  PERSONA_MODEL=Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf and PERSONA_PORT=8090;
  M2b PASSED 05-23. HANDOFF.md's :8080 / "model not downloaded" is stale.
- Qwen3.6 track: the T0.1 GO/NO-GO arch test RAN and PASSED 2026-05-18 (git commit
  "Windows zero-install portable instance + Qwen3.6 T0.1 prototype (PASSED)"). The
  Windows `models/` dir holds only Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf (26.6 GB), used
  by the portable flow. HANDOFF.md's "run T0.1" critical path is therefore stale.
  T1-T3 swap work was never started; the swap is a parked-but-viable upgrade.
- API behavior: HANDOFF.md correct, KNOWLEDGE.md System State stale. Verified in
  `services/api/server.py`: /v1/chat/completions ignores `stream`, returns one
  JSON body (lines 861-890), prompt_tokens hardcoded 0 (line 888); /chat_submit
  disabled (line 837); /agent/run blocking subprocess.run(timeout=300) (line 684).
- Two model files coexist by design: native EVO-X2 flow uses Instruct-2507, the
  Windows portable flow uses Qwen3.6. Updated knowledge.md (API surface note) and
  todo.md (remaining open items reduced to live EVO-X2 checks + a model-track
  decision + API gap fixes).

## 2026-06-02 2001 PDT -- Workflow-compliance restructure (Claude)

- Split the pre-convention `KNOWLEDGE.md` (1022 lines) and living `HANDOFF.md`
  into the three-file convention: `knowledge.md`, `todo.md`, `changelog.md`.
- Converted all content to ASCII (removed em-dashes, smart quotes, box-drawing
  `--` rules, and status emoji); removed inline `#` comments from config code
  blocks per the executable-code-only rule.
- Added root `WORKFLOW.md` one-line pointer.
- Archived originals to `archive/pre-workflow/` (KNOWLEDGE.md, HANDOFF.md,
  HANDOFF.html). README.md and README_models_hardware.md left in place
  (external-facing, separate concern).
- Recorded the unresolved KNOWLEDGE.md-vs-HANDOFF.md current-state discrepancy
  as the top item in `todo.md` rather than picking a winner.
- Git index found corrupt with a stale `.git/index.lock` that could not be
  removed from the sandbox (mount blocks writes under `.git/`). Repair from a
  Windows shell at the repo root: remove `.git/index.lock`, remove `.git/index`,
  run `git reset` to rebuild the index from HEAD, then `git status` to confirm
  the moved/created docs, then stage and commit. No git history was lost; only
  the working index needs rebuilding.

## 2026-05-23 0218 PDT -- M2b sustained-load baseline + handoff (Brandon + Claude)

- Revived llama-server (pid 1810898, :8090) and API (pid 1813299) on EVO-X2;
  /health returned the M5 shape.
- 30-min M2b run at concurrency 4 on unified Qwen3-30B-A3B Q5_K_M: 2066/2066 OK,
  60/60 health polls OK, lat_p50 4.358s / p95 4.553s / max 4.763s, gen_tps_mean
  28.26 per slot (~113 tok/s aggregate), per-minute throughput flat 27.78-28.79.
- Stability ghost did NOT recur. Peak-load thermal not captured (only +1h23m
  post-test idle sample). Report: `logs/m2b_2026-05-23_0723.json`.
- See `archive/handoffs/HANDOFF_2026-05-23_0218_docs-drift-m2b-baseline.md`.

## 2026-05-22 0823 PDT -- Documentation drift cleanup (Brandon + Claude)

- System State unified-llama row rewritten for :8090 with rationale + stability
  follow-up; OpenWebUI corrected to "scaffolded, not deployed" after EVO-X2
  diagnostic (no listener on :3000, empty data dir, venv only in legacy path).
- Port references 8080 -> 8090 across inference table, child-process diagram,
  T1.2, H1.2, M12. Runtime Configuration block rewritten to unified topology;
  legacy dual-server vars collapsed.
- Corrected the 05-19/20 framing: the :8080 squatter was an unrelated co-tenant
  container, not OpenWebUI. Flagged llama-server then down on EVO-X2.

## 2026-05-19 1802 PDT -- EVO-X2 M5 commit + push (Brandon + Claude)

- Pulled the three 05-19 in-flight EVO-X2 patches to Windows, verified via
  tar-over-ssh diff. Caught a mode flip on `load_test_m2b.py` (0644 -> 0755) and
  two pre-existing oddities in `start_api.sh` (dead MEMORY_DISTILL_ENABLED
  export; lingering SCIENTIST_* env names working via back-compat).
- Commit 61790de landed the four file changes; 8177b20 archived both dated
  handoffs. EVO-X2 fast-forwarded to origin/main. M5 declared done.
- See `archive/handoffs/HANDOFF_2026-05-20_0102_m5-validated-evox2.md`.

## 2026-05-19 0430 PDT -- EVO-X2 M5 validation (Brandon + Claude)

- Three sed-patches on EVO-X2: PERSONA_PORT 8080 -> 8090; `start_api.sh` and
  `stop_api.sh` AI_ROOT default flipped from the quarantined `~/Live/AIStack`
  path to `~/Git/Project_Persona/`.
- llama-server died once with no graceful-shutdown signature; root cause
  unidentified (stability ghost). Suspect list carried forward.
- See `archive/handoffs/HANDOFF_2026-05-19_1130_evox2-m5-validation.md`.

## 2026-05-17 1130 PDT -- Windows zero-install portable instance (Brandon + Claude)

- Two double-click `.bat` entry points at repo root. `windows_portable_setup.bat`
  resolves + extracts PortableGit, then hands off to portable bash;
  `scripts/portable_setup_win.sh` downloads the latest llama.cpp Windows-Vulkan
  binary and the Qwen3.6 GGUF (idempotent, resumable). `windows_portable_run.bat`
  prepends PortableGit to PATH for the session only. `.gitignore` adds
  `portable/`.
- See `archive/handoffs/HANDOFF_2026-05-17_1130_qwen36-windows-prototype.md`.

## 2026-05-17 1030 PDT -- M5 server.py single-model migration (Brandon + Claude)

- Removed SCIENTIST_URL/PORT; role differentiation moved from URL dispatch to
  the prompt layer. Env migration with back-compat: ASYNC_SCIENTIST_* ->
  ASYNC_REASONING_*, SCIENTIST_INBAND_* -> REASONING_INBAND_*.
- Added `thinking_prefix()` (/think vs /no_think by topic); `build_persona_prompt`
  gained `reasoning_notes` and `thinking_mode`. PERSONA_CONCURRENCY default 2 -> 4;
  `/v1/chat/completions` gated by `persona_sem`. `/health` reshaped.
- Persona loader switched to the 2-file Hermes naming (SOUL.md + .hermes.md),
  dropping persona.md/style.md/system_rules.md. Closed the Phase 1 "wire SOUL.md
  + .hermes.md" gap.
- See `archive/handoffs/HANDOFF_2026-05-17_1030_m5-server-py-migration.md`.

## 2026-05-17 0730 PDT -- Qwen-test canonicalize + M2b script (Brandon + Claude)

- Mirrored EVO-X2's 05-16 env + launcher rewrites onto Windows byte-identically.
- Fixed `scripts/status.sh` (AI_ROOT -> ~/Git/Project_Persona, names trimmed to
  ("persona"), scientist refs removed). Added `scripts/load_test_m2b.py`
  (asyncio + httpx sustained-load client). M3 + M4 marked done.
- See `archive/handoffs/HANDOFF_2026-05-17_0730_qwen-test-canonicalize.md`.

## 2026-05-17 -- Handoff layout cleanup (Brandon + Claude)

- Moved all seven dated `HANDOFF_*` files from repo root into
  `archive/handoffs/`; only the living `HANDOFF.md` + rendered `HANDOFF.html`
  stayed at root. Updated cross-references. (Time not recorded.)

## 2026-05-16 1637 PDT -- Qwen-test first boot (Brandon + Claude)

- Rewrote `run/llama-servers.env` + `scripts/start_llama_servers.sh` on EVO-X2
  for the unified Qwen3-30B-A3B-Instruct-2507 Q5_K_M topology: full GPU offload
  (49/49 on Vulkan0), 4 slots x 8192 ctx, q8_0 KV cache, Flash Attention, Hermes
  2 Pro template, ~63 tok/s gen / ~67 tok/s prompt eval.
- Repo reconciliation (stash/pull/pop), two commits (3910a37 profile rename,
  57dad37 docs). Moved the Qwen3 model into `~/Git/Project_Persona/models/`;
  quarantined the legacy `~/Live/AIStack/` workspace.
- See `archive/handoffs/HANDOFF_2026-05-16_2337_qwen-test-first-boot.md`.

## 2026-05-15 0127 PDT -- Compatibility re-eval, tiered T0-T4 (Brandon + Claude)

- Added the tiered compatibility re-eval action plan (T0 GO/NO-GO arch test, T1
  foundation, T2 core integration, T3 hardening, T4 deferred) alongside the
  Hermes (H) and single-model (M) blocks.
- Also this date (time not recorded): created the living `HANDOFF.md` +
  `HANDOFF.html` + `scripts/regen_handoff_html.sh`; ran a 12-action consolidation
  batch (archived cruft and AIP_* docs, rewrote README.md / persona/README.md /
  README_models_hardware.md / .gitignore, renamed profile files to SOUL.md /
  .hermes.md, corrected the `looks_degenerate()` claim).
- See `archive/handoffs/HANDOFF_2026-05-15_0127_compat-reeval-tiered.md`.

## 2026-05-14 -- Frontend lock, Hermes naming, M1/M2 progress (Brandon + Claude)

- M1 resolved: bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF Q5_K_M chosen.
  M2 split into M2a (Vulkan/RADV build verified, bf16=0 noted) and M2b
  (sustained-load, deferred).
- OpenWebUI locked as primary frontend (SillyTavern out of scope). Profile files
  renamed to Hermes naming (persona.md -> SOUL.md, system_rules.md -> .hermes.md,
  style.md retired); profile folder doubles as HERMES_HOME. (Time not recorded.)

## 2026-05-10 1738 PDT -- Hermes Agent adoption decision (Brandon + Claude)

- Adopted Hermes Agent (Nous Research, MIT) as the agent-work backbone; six
  brainstorm forks resolved. Deleted AG2 (Phase 2.5) and CrewAI (Phase 9);
  reshaped LangGraph (Phase 8) into Hermes integration. Extended the Task Board
  schema with Tenacity-style failure-semantics columns.
- Enumerated the network-egress risk surface (7 paths + Claude Code creds risk)
  with a safe-config recipe (Appendix A) and kernel-level containment (H1.6).
- See `archive/handoffs/HANDOFF_2026-05-10_1738_agent-swarm-hermes-adoption.md`.

## 2026-05-09 0250 PDT -- Single-model consolidation decision (Brandon + Claude)

- Decided to replace the multi-model topology (persona 8080 + reasoning 8081 +
  planned coder 8082) with a single Qwen3-30B-A3B Q5_K_M served from one
  llama.cpp instance with parallel slots and mode-switched prompts. Sequenced
  the M1-M12 migration. Cancelled the coder server.
- See `archive/handoffs/HANDOFF_2026-05-09_0250_single-model-migration.md`.

## Pre-convention baseline

The project began tracking state on 2026-04-05 in a single sprawling
`KNOWLEDGE.md` ("Knowledge & Task Tracker"): initial tracker created, Phases 2-8
spec'd, the Task Board system component added (schema, surfacing behavior,
difficulty/time_score, phase touchpoints), a license audit completed (component
table, model-exclusion policy, hardware tiers), and `README_models_hardware.md`
created. From 2026-05-09 onward that file accumulated dated decision and
session entries, and from 2026-05-15 a parallel living `HANDOFF.md` (+
`HANDOFF.html`) carried current-state. Both were the authoritative docs until
the 2026-06-03 restructure split them into this convention. The frozen originals
are preserved at `archive/pre-workflow/KNOWLEDGE.md`, `.../HANDOFF.md`, and
`.../HANDOFF.html`; dated frozen handoffs from this period live in
`archive/handoffs/`.
