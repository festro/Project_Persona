# Project_Persona -- Changelog

Reverse-chronological history. New entries go at the TOP.

Conventions:
- Header format: `## YYYY-MM-DD HHMM UTC -- short summary (<author>)`
- One bullet per change, past tense, terse.
- File / line references where useful.
- ASCII only (see `WORKFLOW.md`).
- Append-only. To correct a prior entry, add a new entry on top; do not
  edit history.
- Entries reconstructed from the pre-convention File Change Tracker keep their
  recorded date; HHMM is shown only where the original recorded it.

---

## 2026-06-06 1838 UTC -- manage.py cross-platform launcher (Phase 0.5 #1) (Claude)

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

## 2026-06-06 0053 UTC -- Handoff written (handoff_persona_20260606_0053) (Brandon + Claude)

- Froze the session's work (roadmap.md + distributed-mesh design + portability
  audit + the sys.executable fix) into
  `archive/handoffs/handoff_persona_20260606_0053.md`. Next-session entry point =
  Phase 0.5 portability hardening (manage.py launcher + dependency tiers),
  alongside the still-open Phase 1 :8090 llama-server standup. Includes the
  uncommitted-files list + Windows-side commit guidance.

## 2026-06-06 0047 UTC -- Portability audit + cross-OS hardening track; /agent/run python3 fix (Brandon + Claude)

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

## 2026-06-06 0035 UTC -- Captured distributed node-mesh design (docs/distributed_nodes.md + roadmap Phase 10) (Brandon + Claude)

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

## 2026-06-05 2325 UTC -- Added roadmap.md (phased feature/completion tracker) (Brandon + Claude)

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

## 2026-06-05 2312 UTC -- API gap fixes: streaming, prompt_tokens, /agent/run, /chat_submit, root route (Brandon + Claude)

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

## 2026-06-05 2226 UTC -- Portable 3.11.9 services env operational (Brandon + Claude)

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

## 2026-06-05 2229 UTC -- Live API boot on portable 3.11.9; port-source fix (Brandon + Claude)

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

## 2026-06-05 0128 UTC -- Decision: services interpreter = Python 3.11.9 embeddable (Brandon + Claude)

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

## 2026-06-05 0118 UTC -- Python 3.14 compat validation + portable bootstrap (Brandon + Claude)

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

## 2026-06-05 0108 UTC -- T2.1: per-mode sampling presets in server.py + config.env (Brandon + Claude)

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

## 2026-06-05 0058 UTC -- Modernized init_profiles.sh + doctor.sh to 2-file profiles (Brandon + Claude)

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

## 2026-06-04 1017 UTC -- Modernized setup_native_stack.sh env writer (Brandon + Claude)

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

## 2026-06-04 0755 UTC -- T1 implemented: env_hermes + per-profile safe-config (Brandon + Claude)

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
  already flagged this). See handoff_persona_20260604_0755.
- Logged pre-existing drift NOT fixed here (see todo.md): setup_native_stack.sh
  still writes the retired multi-server llama-servers.env (8080/8081/8082
  persona/reasoning/coder) -- a clobber hazard; init_profiles.sh + doctor.sh still
  scaffold/check the retired 3-file profile (persona.md/style.md/system_rules.md)
  instead of SOUL.md/.hermes.md; doctor.sh still probes a scientist port.

## 2026-06-03 2305 UTC -- T0.2 PASSED; Qwen3.6 tool-calling verified (Brandon + Claude)

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

## 2026-06-03 2140 UTC -- Clarified Qwen3.6 T0 gate status; T0.2 still open (Brandon + Claude)

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

## 2026-06-03 2124 UTC -- Fixed AI_ROOT drift in stop/clean scripts (Brandon + Claude)

- `scripts/stop_llama_servers.sh` line 3: AI_ROOT default flipped from
  `$HOME/Live/AIStack/Project_Persona` to `$HOME/Git/Project_Persona`.
- `scripts/clean.sh` line 3: same flip.
- Both now match `start_llama_servers.sh`; run without AI_ROOT exported they no
  longer target the legacy workspace. Closes todo Next #1 (the start_api/stop_api
  equivalent was fixed 05-19).

## 2026-06-03 2118 UTC -- Restarted EVO-X2 stack; healthy (Brandon + Claude)

- Restarted via `scripts/start_llama_servers.sh` (auto-cleared the orphan pidfile,
  new persona pid 20606) and `scripts/start_api.sh` (pid 20683). :8090/health ok,
  :8000/health all green, /v1/chat/completions smoke returned a real completion.
- Found AI_ROOT drift while reading scripts: `stop_llama_servers.sh` and
  `clean.sh` still default AI_ROOT to the legacy `$HOME/Live/AIStack/Project_Persona`
  (start_llama_servers.sh uses `$HOME/Git/Project_Persona`). Logged as todo Next #1.
- Smoke reconfirmed usage.prompt_tokens=0 and showed mild output repetition (the
  persona emitted its "Next actions" scaffolding twice on a trivial greeting).

## 2026-06-03 2112 UTC -- CORRECTION: 05-23 shutdown was clean, not the ghost (Brandon + Claude)

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

## 2026-06-03 2108 UTC -- EVO-X2 live state checked over SSH (Brandon + Claude)

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

## 2026-06-03 0439 UTC -- Reconciled the KNOWLEDGE/HANDOFF discrepancy (Claude)

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

## 2026-06-03 0301 UTC -- Workflow-compliance restructure (Claude)

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

## 2026-05-23 0918 UTC -- M2b sustained-load baseline + handoff (Brandon + Claude)

- Revived llama-server (pid 1810898, :8090) and API (pid 1813299) on EVO-X2;
  /health returned the M5 shape.
- 30-min M2b run at concurrency 4 on unified Qwen3-30B-A3B Q5_K_M: 2066/2066 OK,
  60/60 health polls OK, lat_p50 4.358s / p95 4.553s / max 4.763s, gen_tps_mean
  28.26 per slot (~113 tok/s aggregate), per-minute throughput flat 27.78-28.79.
- Stability ghost did NOT recur. Peak-load thermal not captured (only +1h23m
  post-test idle sample). Report: `logs/m2b_2026-05-23_0723.json`.
- See `archive/handoffs/HANDOFF_2026-05-23_0918_docs-drift-m2b-baseline.md`.

## 2026-05-22 1523 UTC -- Documentation drift cleanup (Brandon + Claude)

- System State unified-llama row rewritten for :8090 with rationale + stability
  follow-up; OpenWebUI corrected to "scaffolded, not deployed" after EVO-X2
  diagnostic (no listener on :3000, empty data dir, venv only in legacy path).
- Port references 8080 -> 8090 across inference table, child-process diagram,
  T1.2, H1.2, M12. Runtime Configuration block rewritten to unified topology;
  legacy dual-server vars collapsed.
- Corrected the 05-19/20 framing: the :8080 squatter was an unrelated co-tenant
  container, not OpenWebUI. Flagged llama-server then down on EVO-X2.

## 2026-05-20 0102 UTC -- EVO-X2 M5 commit + push (Brandon + Claude)

- Pulled the three 05-19 in-flight EVO-X2 patches to Windows, verified via
  tar-over-ssh diff. Caught a mode flip on `load_test_m2b.py` (0644 -> 0755) and
  two pre-existing oddities in `start_api.sh` (dead MEMORY_DISTILL_ENABLED
  export; lingering SCIENTIST_* env names working via back-compat).
- Commit 61790de landed the four file changes; 8177b20 archived both dated
  handoffs. EVO-X2 fast-forwarded to origin/main. M5 declared done.
- See `archive/handoffs/HANDOFF_2026-05-20_0102_m5-validated-evox2.md`.

## 2026-05-19 1130 UTC -- EVO-X2 M5 validation (Brandon + Claude)

- Three sed-patches on EVO-X2: PERSONA_PORT 8080 -> 8090; `start_api.sh` and
  `stop_api.sh` AI_ROOT default flipped from the quarantined `~/Live/AIStack`
  path to `~/Git/Project_Persona/`.
- llama-server died once with no graceful-shutdown signature; root cause
  unidentified (stability ghost). Suspect list carried forward.
- See `archive/handoffs/HANDOFF_2026-05-19_1130_evox2-m5-validation.md`.

## 2026-05-17 1830 UTC -- Windows zero-install portable instance (Brandon + Claude)

- Two double-click `.bat` entry points at repo root. `windows_portable_setup.bat`
  resolves + extracts PortableGit, then hands off to portable bash;
  `scripts/portable_setup_win.sh` downloads the latest llama.cpp Windows-Vulkan
  binary and the Qwen3.6 GGUF (idempotent, resumable). `windows_portable_run.bat`
  prepends PortableGit to PATH for the session only. `.gitignore` adds
  `portable/`.
- See `archive/handoffs/HANDOFF_2026-05-17_1830_qwen36-windows-prototype.md`.

## 2026-05-17 1730 UTC -- M5 server.py single-model migration (Brandon + Claude)

- Removed SCIENTIST_URL/PORT; role differentiation moved from URL dispatch to
  the prompt layer. Env migration with back-compat: ASYNC_SCIENTIST_* ->
  ASYNC_REASONING_*, SCIENTIST_INBAND_* -> REASONING_INBAND_*.
- Added `thinking_prefix()` (/think vs /no_think by topic); `build_persona_prompt`
  gained `reasoning_notes` and `thinking_mode`. PERSONA_CONCURRENCY default 2 -> 4;
  `/v1/chat/completions` gated by `persona_sem`. `/health` reshaped.
- Persona loader switched to the 2-file Hermes naming (SOUL.md + .hermes.md),
  dropping persona.md/style.md/system_rules.md. Closed the Phase 1 "wire SOUL.md
  + .hermes.md" gap.
- See `archive/handoffs/HANDOFF_2026-05-17_1730_m5-server-py-migration.md`.

## 2026-05-17 1430 UTC -- Qwen-test canonicalize + M2b script (Brandon + Claude)

- Mirrored EVO-X2's 05-16 env + launcher rewrites onto Windows byte-identically.
- Fixed `scripts/status.sh` (AI_ROOT -> ~/Git/Project_Persona, names trimmed to
  ("persona"), scientist refs removed). Added `scripts/load_test_m2b.py`
  (asyncio + httpx sustained-load client). M3 + M4 marked done.
- See `archive/handoffs/HANDOFF_2026-05-17_1430_qwen-test-canonicalize.md`.

## 2026-05-17 -- Handoff layout cleanup (Brandon + Claude)

- Moved all seven dated `HANDOFF_*` files from repo root into
  `archive/handoffs/`; only the living `HANDOFF.md` + rendered `HANDOFF.html`
  stayed at root. Updated cross-references. (Time not recorded.)

## 2026-05-16 2337 UTC -- Qwen-test first boot (Brandon + Claude)

- Rewrote `run/llama-servers.env` + `scripts/start_llama_servers.sh` on EVO-X2
  for the unified Qwen3-30B-A3B-Instruct-2507 Q5_K_M topology: full GPU offload
  (49/49 on Vulkan0), 4 slots x 8192 ctx, q8_0 KV cache, Flash Attention, Hermes
  2 Pro template, ~63 tok/s gen / ~67 tok/s prompt eval.
- Repo reconciliation (stash/pull/pop), two commits (3910a37 profile rename,
  57dad37 docs). Moved the Qwen3 model into `~/Git/Project_Persona/models/`;
  quarantined the legacy `~/Live/AIStack/` workspace.
- See `archive/handoffs/HANDOFF_2026-05-16_2337_qwen-test-first-boot.md`.

## 2026-05-15 0827 UTC -- Compatibility re-eval, tiered T0-T4 (Brandon + Claude)

- Added the tiered compatibility re-eval action plan (T0 GO/NO-GO arch test, T1
  foundation, T2 core integration, T3 hardening, T4 deferred) alongside the
  Hermes (H) and single-model (M) blocks.
- Also this date (time not recorded): created the living `HANDOFF.md` +
  `HANDOFF.html` + `scripts/regen_handoff_html.sh`; ran a 12-action consolidation
  batch (archived cruft and AIP_* docs, rewrote README.md / persona/README.md /
  README_models_hardware.md / .gitignore, renamed profile files to SOUL.md /
  .hermes.md, corrected the `looks_degenerate()` claim).
- See `archive/handoffs/HANDOFF_2026-05-15_0827_compat-reeval-tiered.md`.

## 2026-05-14 -- Frontend lock, Hermes naming, M1/M2 progress (Brandon + Claude)

- M1 resolved: bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF Q5_K_M chosen.
  M2 split into M2a (Vulkan/RADV build verified, bf16=0 noted) and M2b
  (sustained-load, deferred).
- OpenWebUI locked as primary frontend (SillyTavern out of scope). Profile files
  renamed to Hermes naming (persona.md -> SOUL.md, system_rules.md -> .hermes.md,
  style.md retired); profile folder doubles as HERMES_HOME. (Time not recorded.)

## 2026-05-11 0038 UTC -- Hermes Agent adoption decision (Brandon + Claude)

- Adopted Hermes Agent (Nous Research, MIT) as the agent-work backbone; six
  brainstorm forks resolved. Deleted AG2 (Phase 2.5) and CrewAI (Phase 9);
  reshaped LangGraph (Phase 8) into Hermes integration. Extended the Task Board
  schema with Tenacity-style failure-semantics columns.
- Enumerated the network-egress risk surface (7 paths + Claude Code creds risk)
  with a safe-config recipe (Appendix A) and kernel-level containment (H1.6).
- See `archive/handoffs/HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md`.

## 2026-05-09 0950 UTC -- Single-model consolidation decision (Brandon + Claude)

- Decided to replace the multi-model topology (persona 8080 + reasoning 8081 +
  planned coder 8082) with a single Qwen3-30B-A3B Q5_K_M served from one
  llama.cpp instance with parallel slots and mode-switched prompts. Sequenced
  the M1-M12 migration. Cancelled the coder server.
- See `archive/handoffs/HANDOFF_2026-05-09_0950_single-model-migration.md`.

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
