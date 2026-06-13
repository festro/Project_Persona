# Project_Persona -- TODO

Short-term shared memory. See `roadmap.md` for the phased feature/completion
tracker, `knowledge.md` for project scope, and `changelog.md` for history.

Last updated: 2026-06-12 2311 PDT by Claude

## Rules of the road

- This file holds ONLY "just finished" and "next up". Nothing else.
- When something here is more than ~one session old, move it to `changelog.md`.
- Project scope / architecture lives in `knowledge.md`. Do not duplicate.
- Feature/phase completion status lives in `roadmap.md`. "Next up" here points at
  its phase/track IDs; do not restate them.
- Keep it ASCII (see `WORKFLOW.md`).
- Whoever edits this file: bump the "Last updated" stamp and put your name on it.

## Just finished (2026-06-12, Claude)

- PHASE 8 HERMES STARTED -- T1 close-out + H1 DONE (changelog 2311; handoff
  handoff_persona_20260612_2311.md). hermes-agent v0.16.0 installed on EVO-X2 (isolated/
  portable: uv + CPython 3.11.15 + pinned editable clone ~/src/hermes-agent@9b1e0d6f in
  env_hermes/; no global mutations). H1 validated against v0.16.0: HERMES_HOME->profile
  dir, model.sampling.* + tools.disabled valid; profile config.yaml migrated 0->28
  (safe-config preserved), committed 70d7fb2. Egress off via 4 layers (tools.disabled +
  API-key-gating + terminal.backend=local + browser.allow_private_urls=false). KEY
  FINDINGS: (a) Hermes = NousResearch full agent, installs via install.sh/uv NOT pip --
  setup_native_stack.sh needs updating; (b) Linux-only (WSL2), so Hermes node = EVO-X2;
  (c) Hermes has its OWN kanban+dispatcher -> H2 must decide native-kanban vs bridge
  taskboard.py.

## Just finished (2026-06-08, Claude)

- EVO-X2 SINGLE-MODEL CONVERGENCE DONE (changelog 1029; handoff
  handoff_persona_20260608_1029.md) -- M6 milestone closed. EVO-X2 now runs Qwen3.6
  on a fresh llama.cpp b9219 Vulkan build (built from source over SSH; prereq
  spirv-headers). Full repo sync to origin/main first, native venv refreshed.
  Live-validated end to end (incl. T2.4 reasoning_content via messages path).
  Instruct-2507 archived. Single model on EVERY host. config.toml [linux] committed +
  pushed from EVO-X2 (milestone). Findings: 62 GiB system RAM = BIOS iGPU carve-out of
  96 GB unified; PERSONA_MAX_TOKENS>=4096 needed when thinking on; shallow-clone makes
  --version read 1 (cosmetic). See "EVO-X2 state".
- T2.4 PAYOFF DONE (changelog 0846; handoff handoff_persona_20260608_0846.md): the
  lossy two-part sanitize_persona_reply is RETIRED on the messages path. New
  PERSONA_SANITIZE_MESSAGES env flag (OFF by default = retired; escape hatch to re-
  sanitize). New will_sanitize/finalize_persona_reply helpers centralize the decision;
  /chat + /v1 call finalize_persona_reply. /health persona_sanitize_messages; /chat
  debug sanitizer_applied. tests/test_api_offline.py +8 -> 72/72 (off-mount, fastapi
  0.136.3). Raw /completion path UNCHANGED. roadmap T2.4 FOLLOW-UP closed. NOT committed
  (mid-phase = LOCAL COMMIT ONLY, no push). OWED: canonical Windows-side run on portable
  3.11.9 (off-mount is not the pinned chain). No live model needed -- this is a
  format/finalization change, not a generation change.
  CANONICAL RUN DONE (0856): Brandon ran it Windows-side on portable 3.11.9 -> 72/72
  ALL PASS. T2.4 payoff fully validated.
- OFFLINE SELF-TEST NOW LOGS (changelog 0856): tests/test_api_offline.py writes
  logs/test_api_offline.log on a direct run (Brandon noticed a direct run left logs/
  empty -- only run_logged.py logged before). Tee + header/footer; stdout restored
  before close (avoids the closed-tee flush -> exit 120). run_logged.py sets RUN_LOGGED=1
  so the self-test skips its own log under the wrapper (no path collision). Mechanism
  validated off-mount. OWED: a Windows-side re-run after these logging edits to
  reconfirm 72/72 + that the log file appears.

## Just finished (2026-06-07 evening, Claude)

- SESSION ARC (changelog 1827/2200/2254; handoff handoff_persona_20260607_2300.md).
  Three threads, ALL mid-phase = LOCAL COMMITS ONLY, no push (per the new push-at-
  milestones rule):
  1. DOC RECONCILIATION: single-model Qwen3.6-35B-A3B-UD-Q5_K_XL is canonical on
     EVERY host (Instruct-2507 = dropped no-thinking fallback; T0.1 arch + T0.2
     tool-calling gates both passed). Obsolete-entry sweep across knowledge/roadmap/
     todo/READMEs: retired HANDOFF.md pointers, Qdrant/OpenWebUI status, Unix-socket
     ->NATS label, Phase 9->8, py314 3.12->3.11.9, config.toml-primary, stamps.
     Audit: docs/doc_audit_conflicts_20260607_1827.md.
  2. .gitignore tools/ -> tools/*.json so the taskman /agent/run scripts are
     tracked. VERIFY Windows-side: `git ls-files tools/`; if empty,
     `git add tools/taskman.py tools/taskman2.py` (else fresh clones break
     /agent/run). Context-size "drift" was a non-issue (per-OS 32768 linux / 16384
     windows; live 4096/slot = the windows fit).
  3. MODEL PROVISIONER (new Phase 0.5 feature): design
     docs/model_provisioner_design_20260607_2158.md. P1 (manage.py) -- detect_vram_mb
     (vulkaninfo DEVICE_LOCAL heap, x-vendor) + detect_memory_model + detect_camera;
     node_capabilities.json gains vram_mb/memory_model/camera_present. VALIDATED live
     RX 9060 XT: vram_mb=16304, memory_model=discrete. P2 -- run/model_playbook.toml
     (10 Apache-2.0 models) + scripts/provision_match.py + tests/test_provision_match.py
     (7/7). RESOLVED: model=open/AGPL-compatible only; vision default = camera-gated.
- M6 confirmation runbook: docs/m6_confirmation_runbook_20260607_1827.md (the actual
  Phase 1 close was DEFERRED while we did the above; M6 is still the Phase 1 head).

## Just finished (2026-06-07, Claude)

- PHASE 1 LIVE VALIDATION COMPLETE (changelog 1758). All three owed passes green on
  Qwen3.6 (build e7bd3b3) via run_logged.py: T2.4 messages (1746), per-profile Chroma
  (1752, mem_alice/mem_bob created), Task Board /agent/run smoke (1758, recorded ok
  into data/tasks.db). Default Exit Gate re-proven (1729). Logs + server logs clean
  (Error=0/Traceback=0/Warning=0, truncated=0). roadmap: T2.4, per-profile, Task Board
  all -> [x]. Phase 1 now has only M6 open.
- FOLLOW-UPS surfaced: (a) retire the post-hoc sanitizer on the messages path (T2.4
  payoff); (b) the per-profile run left untracked persona/profiles/alice/ + bob/ on
  disk -- gitignore or clean before commit.
- Test-run logger: tests/run_logged.py (changelog 1716). Wraps any test script, tees
  stdout+stderr live, writes logs/<label>.log (overwritten each run, undated) with a
  header (command/git HEAD/feature flags) + footer (exit code/duration/scan). Proven
  this session driving all four live gate runs. Offline suite = 64/64 ALL PASS.

- Session milestone handoff: archive/handoffs/handoff_persona_20260607_1640.md
  (changelog 1640). Summarizes the full arc + the LIVE validation owed.
  exit_gate_live.py made adaptive ([messages] + [per-profile] sections gated on
  /health flags). One command now validates the Exit Gate + the flagged features.
  NEXT SESSION = live validation pass (see the handoff's "Validation owed").

- T2.4 --jinja messages migration (changelog 1635): PERSONA_USE_MESSAGES (OFF default).
  query_llama_messages (POST /v1/chat/completions + chat_template_kwargs{enable_thinking},
  parses reasoning_content) + build_persona_messages (system/user split) + persona_generate
  helper both endpoints call. Off = byte-identical raw /completion path; on = messages,
  server reasoning_content preferred, split_reasoning fallback. /health
  persona_use_messages(+url). +8 offline checks; parse logic 6/6; functions AST OK.
  roadmap T2.4 -> [~]. NOT committed. LIVE VALIDATION REQUIRED (the real --jinja split
  is the one thing offline can't prove): set PERSONA_USE_MESSAGES=1, POST /chat
  preserve_thinking=true on a thinking topic, confirm reasoning comes from the server's
  reasoning_content and content is <think>-free. Then it can retire the sanitizer on
  that path.

- Offline suite 56/56 across the batch (changelog 1617): gate + preserve + Task Board
  + per-profile naming + topic routing all green through the real endpoints. roadmap
  Topic routing -> [x]. Task Board + per-profile stay [~] -- each has ONE live-only
  smoke left (real /agent/run subprocess into the board; mem_<profile> creation under
  RAG_PER_PROFILE=1). NOT committed (doc update).

- Topic routing policy (changelog 1613): classify_topic + resolve_topic (OFF default).
  topic="auto" always classifies; explicit non-chat respected; chat/absent classifies
  only when TOPIC_ROUTING=1. /chat + /v1 resolve topic before downstream. /health
  topic_routing(+topics); /chat debug topic_routing. +8 offline checks; logic 14/14;
  server AST+COMPILE OK. Phase 1 topic routing -> [~]. NOT committed. Pending: full
  offline suite + live smoke. LAST Phase-1 feature item draftable offline; remaining
  Phase 1 = M6 (live) + T2.4 (--jinja migration).

- Per-profile Chroma (changelog 1243): RAG_PER_PROFILE (OFF default) routes
  memory_add/query to "mem_<profile>" collections via _get_collection; off = shared
  global_memory as before. profile threaded through /chat, /v1, distill, writeback.
  /health rag_per_profile + rag_collections. +6 offline checks; name logic 8/8; server
  AST+COMPILE OK. Phase 1 per-profile Chroma -> [~]. NOT committed. CAVEAT: enabling
  does not migrate existing global_memory rows (migration helper = follow-up). Pending:
  full offline suite + live smoke (set RAG_PER_PROFILE=1, confirm mem_<profile>).

- Task Board / SQLite (changelog 1236): new services/api/taskboard.py (stdlib
  sqlite3) replaces the in-memory jobs dict + jobs.jsonl. server wired: TASKS_DB
  (default AI_ROOT/data/tasks.db), init+migrate at startup, /agent/run now records
  run->ok/error/timeout, new GET /jobs list, /jobs/{id} + /health task_store from the
  board. +6 offline checks; taskboard harness 15/15; server AST+COMPILE OK off-mount.
  Phase 1 Task Board -> [~]. NOT committed. Pending: full offline suite (~40) + a live
  /agent/run smoke Windows-side. NOTE: /agent/run behavior CHANGED (now persists to
  the board) -- verify a real taskman2 run shows up in GET /jobs.

- Phase 1 EXIT GATE PROVEN live on Qwen3.6 (changelog 1222) via new
  tests/exit_gate_live.py (stdlib live check): ALL REQUIRED PASS -- /health green,
  topic resolution, preserve off, /v1 stream + prompt_tokens. T2.3 preserve CONFIRMED
  LIVE (/v1 reasoning_content populated by a real <think>). One soft WARN = /think is
  advisory and the model skipped reasoning on one /chat prompt (variance, not a bug).
  Phase 1 stays [~] (M6, per-profile Chroma, topic routing, Task Board still open).
  exit_gate_live.py NOT yet committed.

- T2.3 preserve_thinking, Path A (changelog 1208): split_reasoning() extracts in-band
  <think> before sanitizing (also fixes the latent <think>-leak pre-Qwen3.6);
  preserve_thinking flag (req + PRESERVE_THINKING_DEFAULT, off) returns the answer
  un-sanitized + reasoning (`reasoning` on /chat, `reasoning_content` on /v1 incl.
  stream). /health preserve_thinking_default; /chat debug preserve_thinking. +9
  offline checks (35 live). Advances T2.4 (in-band strip done; --jinja migration
  remains). VALIDATED Windows-side: offline suite 35/35 (changelog 1212). roadmap
  T2.3 -> [x]. Commit staged (commit_msg_t23.log). Live-model spot check -> Exit Gate.

- T2.2 thinking gate, Path A (changelog 1151): chose the prefix path over the
  messages migration (latter folded into T2.4). server.py gains classify_triviality
  + an OFF-by-default THINKING_AUTO_GATE that promotes non-trivial non-thinking-topic
  requests to think; resolve_think/thinking_prefix/sampling_for take an optional
  `text`. /health -> thinking_auto_gate; /chat debug -> thinking_gate. +8 offline
  checks. VALIDATED Windows-side: tests/test_api_offline.py 22/22 (changelog 1155).
  Handoff: handoff_persona_20260607_1151.md. roadmap T2.2 -> [x]. NOT yet committed
  (commit staged for Brandon).

- Handoff written: `archive/handoffs/handoff_persona_20260607_1140.md` (frozen
  session snapshot; commit 8088ff2). Next session starts at Phase 1 / T2.2.
- Windows-side manage.py VALIDATED (changelog 1105): on Daemonic-PC (RX 9060 XT),
  status/capabilities/doctor all green under portable 3.11.9 -- config.toml read;
  run/node_capabilities.json written (accel detect+select=vulkan, tier1 AMD RX 9060
  XT, llama-server build b9219); filesystem/binary/profile checks OK; T1
  safe_config=pass (env_hermes_installed=no). Plus an off-host AST/syntax re-check
  (completeness-verified copy): COMPILE OK + AST OK. Closes the pending Windows-side
  caveats on the launcher, the TOML migration, and the capabilities/detection layer.
  Live CLI lifecycle ALSO proven this session: up (llama pid 3044 + API pid 8340,
  GPU auto-fit) -> status (both up) -> doctor --deep (live persona completion smoke
  PASS) -> test quick (offline 14/14 + health persona+API OK) -> down (clean) ->
  status (down). FINDING: doctor --deep flagged API /health not responding right
  after up while test health moments later showed it OK -- API readiness race
  (embedder/Chroma init); see fix-its.

## Just finished (2026-06-06, Claude)

- Phase 0.5 #4 IPC DECIDED (changelog 2105): NATS+JetStream is the primary
  control-plane bus for the Phase 3 daemon (nats-server as a supervised child,
  loopback, JetStream R=1) -- groundwork for the Phase 10 mesh -- with a stdlib
  loopback-TCP compatibility fallback behind one EventBus interface. Cross-platform
  support verified (nats-server binaries for Win/Linux/ARM64; nats-py official
  client). Full rationale + sources: `docs/ipc_decision.md`. roadmap #4 -> [x];
  Phase 3 + knowledge.md IPC text rewritten; nats-server added to the Phase 3 child
  map. Phase 0.5 remaining is live-host work: manage.py AST + up/down on the Win
  Vulkan box (do-able now); the Linux x64 + ARM64 pass is DEFERRED 2026-06-06 (no
  hardware -- trigger: hardware available); then #5 egress story + installer/doctor
  parity. roadmap Phase 0.5 owns the deferral status + Exit Gate note.
- COMMITTED + PUSHED: the consolidation arc is on origin/main as b75a853 (21 files).
- Phase C done (changelog 0323): archived 11 bash lifecycle scripts to
  scripts/archive/ (start/stop/llama/api/status/doctor/smoke_agent/unified_test) --
  core lifecycle is now manage.py-only, no bash. Reference cleanup in
  setup_native_stack.sh + bootstrap ps1; `.gitignore` adds *.log. Scientist/M2
  remnants left with the archived scripts.
  NEXT options: Phase 0.5 #4 cross-platform IPC decision (loopback TCP vs NATS)
  before the Phase 3 daemon; finish Phase 1 live proof (/chat persona reply +
  streaming + per-topic sampling, embedder_ok/chroma_ok on /health); or M5
  `manage.py setup` to remove the last bash (portable_setup_win.sh + Debian bits).
- LIVE end-to-end validation on Windows (changelog 0253): panel toggle brought the
  whole stack up (Qwen3.6 :8090 + API :8000) and tore it down cleanly; test playbook
  green incl. live /agent/run; thinking mode active. Closes the "stand up Qwen3.6 on
  :8090" entry point. GPU auto-fit fix applied: GPU_LAYERS_PERSONA="auto" -> omit
  --n-gpu-layers so llama fits VRAM (windows overlay now auto; was a forced 35 that
  overrode auto-fit on the 16 GB RX 9060 XT). manage.py needs a Windows-side AST
  re-check after the edits.
- Panel detached mode (changelog 0302): `manage.py panel --detach` (background,
  survives terminal close, run/panel.pid) + `--stop`; panel now shows in `status`.
  Fixes "dashboard stops when I close the window".

## Just finished (2026-06-06, Claude)

- manage.py `panel` web control panel (changelog 0237): stdlib http.server on
  127.0.0.1:8765, live status/health/capabilities dashboard + full start/stop/
  toggle/restart/test control (worker thread, stdout captured to a live log).
  Drives manage.py now; re-points at the Phase 3 daemon later. Validated off-mount;
  needs Windows-side AST + `manage.py panel` smoke.
- manage.py `toggle` + `test` playbook + entry shims (changelog 2213): toggle =
  start-if-down/stop-if-up; test = named-step dispatcher (offline/health/smoke/load,
  sets quick/all, `test list`). Root shims start-stop.sh/.bat + test.sh/.bat call
  manage.py. smoke_agent.sh/unified_test.sh fold into `test` (TUI dropped) -> Phase C
  archive list updated. Linux shims need +x: `git update-index --chmod=+x
  start-stop.sh test.sh` (Windows-side) and `chmod +x start-stop.sh test.sh` (Linux).
  Dispatch validated off-mount; manage.py needs Windows-side AST + `test list`/toggle.
- Config migrated to TOML (changelog 2028): `run/config.toml` typed single source
  ([base]+[runtime]+[<os>] overlays), read by manage.py via stdlib tomllib with
  .env fallback. windows_portable_run.bat shrunk to a thin manage.py shim (no bash).
  LLAMA_LIB_DIR now defaults from root. Validated off-mount; needs Windows-side
  manage.py status to confirm config.toml is read under 3.11.9.
- Phase B detection layer IMPLEMENTED in manage.py (changelog 2014): host detection
  (os/arch/accel 3-tier/ram/cpu), OS-level GPU fallback (PowerShell CIM / lspci so a
  GPU is seen without vendor CLIs), `llama-server --version` backend parse,
  select-only-what-binary-supports, `manage.py capabilities` ->
  run/node_capabilities.json, doctor Accelerators section (flags Tier-3 as
  present-but-unused), and accel-aware start_llama (H3, no forced Vulkan off-vendor).
  Detection logic AST+unit validated off-mount; manage.py needs a Windows-side AST +
  capabilities/doctor run (mount cannot parse it). NEXT: Phase C (retire bash
  lifecycle scripts) after this validates.
- Broadened accel detection design (changelog 1934): verified the current
  llama.cpp backend set and added a 3-tier classification to
  `docs/llama_build_matrix.md` -- Tier 1 selectable (CUDA/ROCm/Intel-SYCL/Vulkan/
  OpenCL/CANN/MUSA), Tier 2 in-progress (Intel NPU OpenVINO, Hexagon, WebGPU),
  Tier 3 detect-but-never-select (Hailo/Coral/Gaudi -- own runtimes, no GGUF) +
  "select only what the binary supports". Intel SYCL build recipe + broader probe
  list + reworked capability schema (accel_selected + accel_present[]). Support
  matrix in portability_audit.md updated. Design-stage; implements in Phase B.
- Pre-consolidation review + Phase A fixes (changelog 1925):
  `docs/script_consolidation_review.md` (full config/script audit vs the
  manage.py-as-bootstrap goal). Applied: C3 manage.py host-aware model resolution +
  per-OS env overlay (`run/llama-servers.windows.env`); C2 setup_native_stack.sh no
  longer clobbers requirements.txt (installs -r committed; WITH_TORCH_EMBED=1 for
  the extra); H1 port 8080->8090 defaults; H2 --jinja on the Linux launcher; M1
  ggerganov->ggml-org; L1 load_test port. Deferred (architectural): H3/H4/M2-M5.
  server.py + manage.py need a Windows-side parse/offline-test (mount stale).
- Phase 0.5 #3 matrix DOCUMENTED: `docs/llama_build_matrix.md` -- per-accel build
  + acquire (prebuilt + source; CUDA/ROCm/Vulkan/CPU; Win/Linux/ARM64), binary
  placement aligned to manage.py, build-accept flow. Capability-advertising hook
  DESIGNED (descriptor + detection + node_capabilities.json); impl of
  `manage.py capabilities` is the remaining near-term piece. Roadmap #3 -> [~].
  See changelog 1902.
- Phase 0.5 #2 DONE (code): dependency tiers. requirements.txt is now the lean
  tier (dropped sentence-transformers; fastembed/onnxruntime only, no torch). New
  opt-in `services/api/requirements-embed-torch.txt`. server.py gained
  EMBED_BACKEND (auto|fastembed|sentence-transformers) + a guarded ST fallback +
  `/health` embedder_backend. Default lean behavior unchanged. VALIDATED
  Windows-side: AST OK + tests/test_api_offline.py ALL PASS. Roadmap Phase 0.5 #2
  now [x]. See changelog 1859/1853.
- Phase 0.5 #1 DONE (code) + offline-validated: `manage.py` at repo root --
  pure-stdlib cross-platform `up/down/status/doctor`, retires the bash-only
  lifecycle. Ports start_llama_server_win.sh+start_api.sh / stop_llama_servers.sh /
  status.sh / doctor.sh (incl. the safe-config T1 gate, PyYAML + regex paths). NOT
  yet live-host tested (no model/llama-server in sandbox). Handoff:
  `archive/handoffs/handoff_persona_20260606_1138.md`. See changelog 1838 +
  roadmap Phase 0.5 (launcher item now [~]).

## Just finished (2026-06-05, Claude)

Full detail in `changelog.md` (0108 / 0128 / 2226 / 2229) and
`archive/handoffs/handoff_persona_20260605_1548.md`. Also done earlier this run:
T1 (handoff 0755) + ops-script modernization (handoff 0102).

- Handoff written: `archive/handoffs/handoff_persona_20260605_1753.md` (covers the
  roadmap, the distributed-mesh design, and the portability audit; has the
  uncommitted-files list + commit guidance).
- Portability audit + cross-OS hardening: `docs/portability_audit.md` (findings +
  support matrix; Apple OUT) + roadmap Phase 0.5. FIX: /agent/run now uses
  sys.executable (was literal python3, broke Windows portable). See changelog 0047.
- Distributed node-mesh design captured: `docs/distributed_nodes.md` + roadmap
  Phase 10 (NATS+JetStream peer mesh, shared-token admission, self-gen keys +
  $SYS/connz connection log for roster/reputation, validation for bad actors).
  Extended track; the only near-term piece is the Stage 0 LLAMA_HOST offload
  experiment. See changelog 0035.
- API gap fixes (changelog/handoff 2312): /v1/chat/completions now honors `stream`
  (SSE pseudo-stream, [DONE]-terminated) and reports real prompt_tokens via
  llama.cpp tokens_evaluated; /agent/run offloaded with asyncio.to_thread (no more
  event-loop block); /chat_submit stub + SubmitRequest removed; added GET / +
  /favicon.ico (bare URL stops 404ing). Validated offline with a FastAPI TestClient
  suite (15/15, query_llama monkeypatched); live generation still needs :8090. Env:
  bootstrap pins setuptools<82, requirements pins posthog>=2.4.0,<3.0.0 -> clean
  startup (no setuptools bounce, no posthog telemetry errors).
- T2.1 DONE + validated LIVE: per-mode sampling presets in server.py
  (`resolve_think` / `sampling_for`, applied on /chat + /v1) sourced from
  `run/config.env`. /health on the portable 3.11.9 returned the exact presets.
- Portable services env OPERATIONAL: Python 3.11.9 embeddable in portable/python;
  full committed services/api/requirements.txt installed (chromadb 0.6.3 +
  fastembed + torch, all 3.11 wheels, no source builds). /health 200 OK with
  embedder_ok=true + chroma_ok=true (RAG stack runs, not just imports). Bootstrap:
  `scripts/bootstrap_portable_python.ps1` (+ `.bat`).
- Interpreter DECISION: 3.11.9 (last 3.11 with official binaries). 3.14 blocks
  ChromaDB (pypika/ast.Str). Full report: `docs/py314_compatibility.md`.
- Fixes: PS execution-policy + `$ErrorActionPreference=Stop`/native-stderr in the
  bootstrap; API port-source bug (-Run now sources llama-servers.env so
  PERSONA_PORT=8090, not the 8080 default). config.env gained RAG_ENABLED=1 +
  ANONYMIZED_TELEMETRY=False.

## EVO-X2 state (as of 2026-06-08 1029 PDT) -- CONVERGED

- CONVERGENCE COMPLETE 2026-06-08 (changelog 1029; handoff
  handoff_persona_20260608_1029.md). EVO-X2 now runs the single model
  Qwen3.6-35B-A3B-UD-Q5_K_XL on a fresh llama.cpp b9219 Vulkan build (built from
  source; old b8157 could not load qwen3_5_moe). Synced to origin/main first
  (8e4b92b -> 11e2948), native venv refreshed (py3.12.3). Live-validated: llama
  /health green, API /health green (embedder fastembed + chroma ok), default /chat
  coherent, messages-path /chat returns reasoning_content (T2.4). Instruct-2507
  archived to models/archive/. Stack left UP steady-state (messages OFF default).
- Build: llama_cpp/build is a symlink -> ~/src/llama.cpp/build (clone at tag b9219;
  old tree at llama_cpp/build.stale.*). Rebuild = re-pull ~/src/llama.cpp + cmake.
  Prereq pkg: spirv-headers (see docs/llama_build_matrix.md).
- WATCH: PERSONA_MAX_TOKENS=192 starves thinking-mode answers (raise >= 4096 if
  enabling messages/thinking); raw default path unaffected. Occasional raw-path
  empty-reply -> sanitizer placeholder (variance, intermittent).

## Next (in order)

PRIORITY (2026-06-06 directive): Phase 0.5 cross-OS/arch portability hardening --
make every node run on Windows + Linux, x86-64 + ARM64, CPU/CUDA/ROCm/Vulkan
(Apple OUT). See `roadmap.md` Phase 0.5 + `docs/portability_audit.md`. The
`manage.py` launcher is WRITTEN + offline-validated (changelog 1838); the
`/agent/run` python3 -> sys.executable fix is done. Remaining first moves:
live-host test manage.py up/down (Win Vulkan + Linux), then dependency tiers
(torch optional).

1. M6 single-model migration confirmation (LIVE) -- NOW THE HEAD. The last open
   Phase 1 item; clearing it unblocks the Hermes H-track. See roadmap Phase 1 /
   Phase 8 (Hermes; Phase 9 is DELETED).
   DONE 2026-06-07 1827: the validated-work COMMIT is in -- `git status` Windows-side
   = working tree clean, up to date with origin/main. The 1758 session's
   run_logged.py + exit_gate_live adaptive + test_api_offline warning-silence + doc
   updates + roadmap [x] flips were already committed + pushed in a prior session;
   the sandbox-mount "modified" list was the stale-index phantom. Per-profile
   residue needed no action (persona/profiles/alice|bob already gitignored, L50-52).
2. T2.4 PAYOFF -- DONE 2026-06-08 0846 (changelog/roadmap). Sanitizer retired on the
   messages path behind PERSONA_SANITIZE_MESSAGES (OFF=retired). Off-mount 72/72; the
   canonical Windows-side portable 3.11.9 run is the only thing owed.
3. EVO-X2 single-model CONVERGENCE -- DONE 2026-06-08 1029 (changelog/roadmap M6;
   handoff handoff_persona_20260608_1029.md). Built llama.cpp b9219 from source for
   Vulkan (prereq spirv-headers), symlinked llama_cpp/build, swapped config.toml
   [linux] -> Qwen3.6 (committed+pushed from EVO-X2), archived Instruct-2507,
   live-validated. PERSONA_CTX kept at 32768 (the 96 GB box shows ~62 GiB system RAM
   -- BIOS iGPU carve-out -- so no ctx increase; full offload fits VRAM). Single model
   now on every host. See "EVO-X2 state" above.
4. MODEL PROVISIONER P3/P4 (Phase 0.5; design + P1 + P2 done -- see
   docs/model_provisioner_design_20260607_2158.md). P3: huggingface_hub downloader
   (base GGUF + mmproj), license/disk preflight, write pick into config.toml; P4:
   manage.py `provision` cmd + first-run hook in cmd_up. BEFORE P3 download code
   depends on it: re-verify run/model_playbook.toml repo IDs + filenames + quant
   sizes against real HF pages (they are 2026-06-07 estimates). DECIDE: may
   `provision` overwrite an existing PERSONA_MODEL, or only fill when unset?
   Also refine the KV-aware ctx sizing (the tight-budget step-down currently picks
   8192 vs the working 16384 on the RX 9060 XT).
2. Close out T1 on a live host (needs network + target): run
   `setup_native_stack.sh` (or just the env_hermes step) on EVO-X2 and/or the
   Windows portable host so `doctor.sh` reports env_hermes_installed=yes.
2. H1 validation of the config.yaml schema: confirm `model.sampling.*` and
   `tools.disabled` key paths against the installed hermes-agent
   (`hermes config check`); confirm HERMES_HOME resolves to the profile dir. These
   keys are schema-PROVISIONAL (current docs did not confirm them).
3. T2 (core integration). T2.1 DONE 2026-06-05 (per-mode sampling presets in
   server.py + run/config.env; see changelog 0108). Remaining:
   - T2.2: DONE 2026-06-07 Path A (changelog 1151/1155) -- prefix path + OFF-by-
     default THINKING_AUTO_GATE (trivial -> no_think, non-trivial -> think).
     Validated Windows-side: offline suite 22/22. Remaining: commit + push, then an
     optional live-model spot check (set THINKING_AUTO_GATE=1, POST /chat debug=true
     with Qwen3.6 served) folded into the Phase 1 Exit Gate proof. The
     chat_template_kwargs/messages migration is now T2.4's.
   - T2.3: CODE DONE 2026-06-07 Path A (changelog 1208) -- preserve_thinking flag +
     split_reasoning. LIVE validation PENDING (Brandon, Qwen3.6 served): with
     /think firing, POST /chat (and /v1) with preserve_thinking true vs false and
     confirm reasoning is surfaced (reasoning / reasoning_content) under preserve
     and stripped from the default persona text. Then run the offline suite (31).
     The daemon (Phase 3) sets the flag on Hermes-forwarded work; default stays off.
   - T2.4: RE-SCOPE first -- llama.cpp emits reasoning in `reasoning_content` under
     --jinja, so the user channel is already <think>-free server-side. Decide if a
     persona-side chokepoint is still needed (in-band/non-jinja paths only).
4. API gaps (2026-06-03 code read) -- DONE 2026-06-05 2312 (see changelog): stream
   field honored; /chat_submit removed; /agent/run non-blocking; prompt_tokens
   fixed. Follow-ups if wanted: true token-by-token streaming would require
   bypassing the post-hoc sanitizer; a real async-job path could reuse the retained
   jobs helpers.

## Housekeeping fix-its

- DONE 2026-06-07 (confirmed): live persona.log `new slot, n_ctx = 4096` x4 is the
  INTENDED windows fit, not drift -- run/config.toml [windows] PERSONA_CTX=16384 /
  PERSONA_PARALLEL=4 = 4096/slot (16 GB VRAM). The 32768 figure is the [linux]
  overlay. knowledge.md env block annotated with the per-OS split.
- 2026-06-07 (info, WATCH): persona.log has recurring `W slot update_slots: erased
  invalidated context checkpoint` paired with `speculative decoding will use
  checkpoints` (Qwen3.6 MTP). Expected churn under parallel mixed prompts; low
  prompt-cache reuse. Not an error -- watch if it correlates with latency.

- DONE 2026-06-07 (verified live): API /health readiness race -- doctor --deep right
  after `up` saw API /health down while `test health` moments later showed it OK
  (embedder/Chroma init delay). cmd_up now polls API /health (timeout 120, respects
  --no-wait) after start_api. Confirmed: `up` printed "API /health responding".
- DONE 2026-06-07 1158: StarletteDeprecationWarning (httpx/httpx2 in the FastAPI
  TestClient) silenced via a scoped warnings.filterwarnings in
  tests/test_api_offline.py (before the TestClient import). Pinned deps untouched
  (test-harness only, not the serving path). Re-run Windows-side to confirm clean
  output + still 22/22, then commit.
- DONE 2026-06-07 (verified live): capabilities `llama_build: null` -- a cold Vulkan
  `--version` exceeded the 10s timeout, so build went null while backends came from
  the --list-devices fallback. Bumped `--version` to 30s + one retry in
  llama_version_info (build still parsed from --version only). Confirmed:
  capabilities now reports `"llama_build": "b9219"`.
- DONE 2026-06-04: `setup_native_stack.sh` env writer modernized to the unified
  single-server topology and made non-destructive (FORCE_ENV=1 + .bak). Clobber
  hazard closed. See `changelog.md` 1017.
- DONE 2026-06-05: `init_profiles.sh` + `doctor.sh` modernized to the 2-file
  profile convention (SOUL.md + .hermes.md) and the retired scientist port/model
  removed from doctor.sh. All script-drift items from the T1 handoff are now
  closed. See `changelog.md` 0058.
- From 2026-05-23: `load_test_m2b.py` DEFAULT_ENDPOINT 8080 -> 8090; `start_api.sh`
  cosmetic SCIENTIST_* banner; min-1 bucket race in `bucketize_by_minute`.

## Blocked / waiting

- Hermes adoption: M6 + T1 close-out + H1 ALL DONE 2026-06-12 (hermes-agent v0.16.0
  on EVO-X2; config validated + migrated). NEXT = H2: decide whether to ride Hermes'
  NATIVE kanban (HERMES_KANBAN_*) + dispatcher or bridge to taskboard.py, then wire
  Hermes to claim + execute work. NOT blocked.
- T4 deferred/opt-in items (dual-memory unification, vision, MTP / speculative
  decoding) -- each has a documented trigger; none active.
- TODO #36 -- re-evaluate Qwen3.5/3.6 maturity after ~2026-08 (separate from the
  active swap track).

## Notes for next editor

- Services interpreter DECIDED 2026-06-05: Python 3.11.9 (Windows x64 embeddable)
  in portable/python -- runs the COMPLETE stack incl. ChromaDB RAG, matches the
  Hermes version. 3.11.9 is the last 3.11 with official binaries (security-only
  after). Install via scripts/bootstrap_portable_python.ps1 (installs the committed
  services/api/requirements.txt full stack; -CoreOnly for API-only; -Run to launch).
  NOTE: chromadb>=0.5.0,<1.0.0 in requirements.txt is an INTENTIONAL API pin
  (server.py targets chromadb 0.5.x) -- do not bump to 1.x without porting the
  chromadb usage. The requirements-py314*.txt files are 3.14-fallback reference
  only. Full report: docs/py314_compatibility.md. (3.14 would block ChromaDB and
  is a nudge toward Qdrant / Phase 2a if ever revisited.)
- config.yaml is intentionally git-tracked (no secrets; Hermes secrets live in a
  separate .env). env_hermes/ is gitignored.
- The egress safe-config is the construction-time half of containment; the runtime
  half (H1.6 kernel netns/iptables + daemon env hygiene) is still required and is
  not in T1.
- Single model EVERYWHERE (2026-06-07 directive): Qwen3.6-35B-A3B-UD-Q5_K_XL on
  every host, EVO-X2 included. The earlier "two flows" (EVO=Instruct-2507,
  Windows=Qwen3.6) was transitional host-state, NOT a design -- EVO-X2 converges to
  Qwen3.6 (legacy llama.cpp build bump is the only blocker). Instruct-2507 = dropped
  no-thinking fallback. See knowledge.md "Stable architectural decisions".
- git on D:\Projects repos must run Windows-side (portable git at
  `D:\Projects\Tools\PortableGit\cmd`); the Linux sandbox mount corrupts the index.
- llama-server "stability ghost" (died once 05-19/20, no graceful-shutdown
  signature) never recurred; the 06-03 down-state was a clean shutdown. Watch on
  sustained runs.
- Windows launcher `start_llama_server_win.sh` does not survive being invoked as
  `bash.exe scripts/...` from PowerShell (backgrounded server torn down on shell
  exit). Run foreground in a dedicated window until a real detach / service wrapper
  exists.
