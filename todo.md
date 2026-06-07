# Project_Persona -- TODO

Short-term shared memory. See `roadmap.md` for the phased feature/completion
tracker, `knowledge.md` for project scope, and `changelog.md` for history.

Last updated: 2026-06-07 1617 PDT by Claude

## Rules of the road

- This file holds ONLY "just finished" and "next up". Nothing else.
- When something here is more than ~one session old, move it to `changelog.md`.
- Project scope / architecture lives in `knowledge.md`. Do not duplicate.
- Feature/phase completion status lives in `roadmap.md`. "Next up" here points at
  its phase/track IDs; do not restate them.
- Keep it ASCII (see `WORKFLOW.md`).
- Whoever edits this file: bump the "Last updated" stamp and put your name on it.

## Just finished (2026-06-07, Claude)

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

## EVO-X2 state (as of 2026-06-03 1418 PDT)

- Stack was UP and healthy after a clean restart (persona pid 20606 on :8090, api
  pid 20683 on :8000; all /health green). Deployed model is Instruct-2507 (NOT
  Qwen3.6 -- that is Windows-portable-only). Details in `changelog.md` 2118/2112.
  Re-verify before relying on it.

## Next (in order)

PRIORITY (2026-06-06 directive): Phase 0.5 cross-OS/arch portability hardening --
make every node run on Windows + Linux, x86-64 + ARM64, CPU/CUDA/ROCm/Vulkan
(Apple OUT). See `roadmap.md` Phase 0.5 + `docs/portability_audit.md`. The
`manage.py` launcher is WRITTEN + offline-validated (changelog 1838); the
`/agent/run` python3 -> sys.executable fix is done. Remaining first moves:
live-host test manage.py up/down (Win Vulkan + Linux), then dependency tiers
(torch optional).

1. ENTRY POINT (Brandon to run, post results next session): stand up the Qwen3.6
   llama-server on :8090 (Windows portable flow; llama.cpp Vulkan build + the
   Qwen3.6 GGUF are already on this host). Use `scripts/start_llama_server_win.sh`
   with `--jinja`. GOTCHA: it does NOT survive being launched via `bash.exe
   scripts/...` from PowerShell (backgrounded server torn down on shell exit) --
   run it FOREGROUND in a dedicated window. Then with the API up
   (`bootstrap_portable_python.ps1 -Run`), POST /v1/chat/completions and verify
   T2.1 picks no_think for a "chat" topic and think for science/coding/math/
   research (via /chat debug `sampling_preset`). This unblocks T2.2.
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

- 2026-06-07 (low, CONFIRM): live persona.log shows `new slot, n_ctx = 4096` across
  4 slots on the Qwen3.6 run -- implies live --ctx-size ~16384, not the documented
  PERSONA_CTX=32768 target (which at --parallel 4 should give ~8192/slot). Could be
  an intentional 16 GB VRAM fit or config drift. Confirm against run/config.toml.
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

- Hermes adoption (H1-H6) -- gated on single-model migration; M5 done, M2b passed.
  Confirm M6 before starting H1. H1 also now owns the config.yaml schema
  validation (Next #2).
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
- Two model files / two flows by design: native EVO-X2 uses Instruct-2507; the
  Windows portable flow uses Qwen3.6. The Windows native env points at a model not
  present there -- expected.
- git on D:\Projects repos must run Windows-side (portable git at
  `D:\Projects\Tools\PortableGit\cmd`); the Linux sandbox mount corrupts the index.
- llama-server "stability ghost" (died once 05-19/20, no graceful-shutdown
  signature) never recurred; the 06-03 down-state was a clean shutdown. Watch on
  sustained runs.
- Windows launcher `start_llama_server_win.sh` does not survive being invoked as
  `bash.exe scripts/...` from PowerShell (backgrounded server torn down on shell
  exit). Run foreground in a dedicated window until a real detach / service wrapper
  exists.
