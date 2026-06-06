# Project_Persona -- TODO

Short-term shared memory. See `roadmap.md` for the phased feature/completion
tracker, `knowledge.md` for project scope, and `changelog.md` for history.

Last updated: 2026-06-06 1838 UTC by Claude

## Rules of the road

- This file holds ONLY "just finished" and "next up". Nothing else.
- When something here is more than ~one session old, move it to `changelog.md`.
- Project scope / architecture lives in `knowledge.md`. Do not duplicate.
- Feature/phase completion status lives in `roadmap.md`. "Next up" here points at
  its phase/track IDs; do not restate them.
- Keep it ASCII (see `WORKFLOW.md`).
- Whoever edits this file: bump the "Last updated" stamp and put your name on it.

## Just finished (2026-06-06, Claude)

- Phase 0.5 #1 DONE (code) + offline-validated: `manage.py` at repo root --
  pure-stdlib cross-platform `up/down/status/doctor`, retires the bash-only
  lifecycle. Ports start_llama_server_win.sh+start_api.sh / stop_llama_servers.sh /
  status.sh / doctor.sh (incl. the safe-config T1 gate, PyYAML + regex paths). NOT
  yet live-host tested (no model/llama-server in sandbox). Handoff:
  `archive/handoffs/handoff_persona_20260606_1838.md`. See changelog 1838 +
  roadmap Phase 0.5 (launcher item now [~]).

## Just finished (2026-06-05, Claude)

Full detail in `changelog.md` (0108 / 0128 / 2226 / 2229) and
`archive/handoffs/handoff_persona_20260605_2248.md`. Also done earlier this run:
T1 (handoff 0755) + ops-script modernization (handoff 0102).

- Handoff written: `archive/handoffs/handoff_persona_20260606_0053.md` (covers the
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

## EVO-X2 state (as of 2026-06-03 2118 UTC)

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
   - T2.2: wire `enable_thinking` via `chat_template_kwargs` (needs query_llama on
     the messages format, or fall back to the current `/think`//`/no_think`
     prefix). Gate: trivial -> no <think>, non-trivial -> <think>. Best exercised
     once Qwen3.6 is the served model (Instruct-2507 has no thinking mode).
   - T2.3: wire `preserve_thinking: true` for Hermes-originated requests.
   - T2.4: RE-SCOPE first -- llama.cpp emits reasoning in `reasoning_content` under
     --jinja, so the user channel is already <think>-free server-side. Decide if a
     persona-side chokepoint is still needed (in-band/non-jinja paths only).
4. API gaps (2026-06-03 code read) -- DONE 2026-06-05 2312 (see changelog): stream
   field honored; /chat_submit removed; /agent/run non-blocking; prompt_tokens
   fixed. Follow-ups if wanted: true token-by-token streaming would require
   bypassing the post-hoc sanitizer; a real async-job path could reuse the retained
   jobs helpers.

## Housekeeping fix-its

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
