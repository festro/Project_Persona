# Project_Persona -- TODO

Short-term shared memory. See `knowledge.md` for project scope and
`changelog.md` for history.

Last updated: 2026-06-03 2120 UTC by Claude

## Rules of the road

- This file holds ONLY "just finished" and "next up". Nothing else.
- When something here is more than ~one session old, move it to `changelog.md`.
- Project scope / architecture lives in `knowledge.md`. Do not duplicate.
- Keep it ASCII (see `WORKFLOW.md`).
- Whoever edits this file: bump the "Last updated" stamp and put your name on it.

## Just finished (2026-06-03, Claude)

- Adopted the three-file WORKFLOW convention (knowledge/todo/changelog), ASCII,
  archived originals to `archive/pre-workflow/`. Git index repaired and committed
  (6d1c25e, case fix 0b7d1f2). That work is DONE.
- Reconciled the KNOWLEDGE.md (05-23) vs HANDOFF.md (05-16) discrepancy against
  code + config + git history (see `changelog.md` 0439 entry for full table).
  Outcome: the two docs are each right about different things.
  - Deployment (EVO-X2): KNOWLEDGE.md is correct. Unified Qwen3-30B-A3B
    -Instruct-2507 Q5_K_M on :8090 (config confirms PERSONA_MODEL + PERSONA_PORT),
    M2b PASSED 05-23. HANDOFF.md's :8080 / "model not downloaded" is stale.
  - Qwen3.6 track: T0.1 GO/NO-GO actually RAN and PASSED 2026-05-18 (git commit).
    The Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf (26.6 GB) is the model present in the
    Windows `models/` dir, used by the portable prototype. So HANDOFF.md's "run
    T0.1" critical path is stale -- it is done. T1-T3 swap work was never started.
  - API behavior: HANDOFF.md is correct, KNOWLEDGE.md System State was stale.
    Verified in `services/api/server.py`: /v1/chat/completions ignores the
    `stream` field and returns one JSON body (no streaming, line 861-890);
    /chat_submit returns "disabled in this build" (line 837); /agent/run runs a
    blocking `subprocess.run(timeout=300)` inside async (line 684); `usage`
    hardcodes `prompt_tokens: 0` (line 888).

## Live EVO-X2 state (restored 2026-06-03 2118 UTC, over SSH)

- Stack is UP and healthy. Restarted via `start_llama_servers.sh` (cleared the
  orphan pidfile itself, new pid 20606) + `start_api.sh` (pid 20683).
  :8090/health = ok, :8000/health all green (embedder_ok, chroma_ok, rag_enabled,
  persona_concurrency=4, thinking_mode=auto). End-to-end smoke via
  /v1/chat/completions returned a real completion.
- Earlier down-state (since 05-23) was a CLEAN shutdown, not a crash: api.log
  ended "Application shutdown complete"; persona.log ended "operator(): cleaning
  up before exit..." + memory breakdown. No OOM/segfault. Stack was simply stopped
  after the M2b run and not restarted; the stale pidfile was an orphan, NOT a
  stability-ghost recurrence.
- Model confirmed Instruct-2507: config + on-disk file
  `Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf` (21G). No Qwen3.6 on EVO-X2
  (that file is Windows-portable-only). KNOWLEDGE.md was correct.
- OpenWebUI not deployed (:3000 not listening). KNOWLEDGE.md was correct.
- Smoke test surfaced two known items: usage.prompt_tokens=0 (counter bug), and
  the persona leaked its "Next actions" output scaffolding twice on a trivial
  greeting (mild repetition -- the looks_degenerate / trivial-routing territory).

## Next (in order)

1. Fix AI_ROOT drift in `scripts/stop_llama_servers.sh` and `scripts/clean.sh`:
   both still default AI_ROOT to the legacy `$HOME/Live/AIStack/Project_Persona`,
   while `start_llama_servers.sh` uses `$HOME/Git/Project_Persona`. Run without
   AI_ROOT exported they target the wrong workspace (same bug fixed in
   start_api/stop_api on 05-19). Flip both defaults to `$HOME/Git/Project_Persona`.
2. DECISION (now a real fork, not stale docs): pursue the Qwen3.6 swap (T1-T3;
   T0 gate already PASSED) OR keep hardening the validated Instruct-2507 stack
   (M6, then Hermes H1). Pick one and record it as a dated decision.
3. API gaps surfaced by the code read: either implement streaming in
   /v1/chat/completions or stop advertising `stream`; re-enable or remove
   /chat_submit; make /agent/run non-blocking (run_in_executor) or fold it into
   the planned Task Board; fix `prompt_tokens: 0`.
4. Housekeeping fix-its (from 05-23): `load_test_m2b.py` DEFAULT_ENDPOINT drift
   8080 -> 8090; `start_api.sh` cosmetic SCIENTIST_* banner; min-1 bucket race in
   `bucketize_by_minute`.

## Blocked / waiting

- Hermes adoption (H1-H6) -- gated on single-model migration; M5 done, M2b passed.
  Confirm M6 before starting H1.
- T4 deferred/opt-in items (dual-memory unification, vision, MTP / speculative
  decoding) -- each has a documented trigger; none active.
- TODO #36 -- re-evaluate Qwen3.5/3.6 maturity after ~2026-08 (separate from the
  T0-passed Qwen3.6 swap track in Next #2).

## Notes for next editor

- Two model files / two flows by design: native EVO-X2 flow
  (`run/llama-servers.env`) uses Instruct-2507; the Windows portable flow
  (`scripts/portable_setup_win.sh`) uses Qwen3.6. The Windows `models/` dir only
  has the Qwen3.6 file, so the native env there points at a model that is not
  present -- expected, not a bug.
- KNOWLEDGE.md's per-endpoint "Verified" rows were never re-checked against code;
  do not trust status rows without a code/runtime check (lesson from this recon).
- git on D:\Projects repos must run Windows-side (portable git at
  `D:\Projects\Tools\PortableGit\cmd`); the Linux sandbox mount corrupts the
  index.
- llama-server "stability ghost": died once 05-19/20 (no graceful-shutdown
  signature), still unexplained. It did NOT recur on 05-23 or since -- the 06-03
  down-state was a clean shutdown (logs verified), not the ghost. Watch for it on
  future sustained runs, but it is not the current problem.
- `looks_degenerate()` + self-repair loop never landed; land with T2.4 `<think>`
  stripping or formally drop.
