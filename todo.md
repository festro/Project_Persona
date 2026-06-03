# Project_Persona -- TODO

Short-term shared memory. See `knowledge.md` for project scope and
`changelog.md` for history.

Last updated: 2026-06-03 2108 UTC by Claude

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

## Live EVO-X2 state (checked 2026-06-03 2108 UTC, over SSH)

- Entire stack is DOWN. `scripts/status.sh`: API not running; persona
  llama-server shows a STALE pidfile (`run/persona.pid`); nothing listening on
  8090/8000/3000; no llama-server process. Not restarted since the 05-23 M2b run.
- Model confirmed Instruct-2507: config + on-disk file
  `Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf` (21G) present. No Qwen3.6 on
  EVO-X2 (that file is Windows-portable-only). KNOWLEDGE.md was correct.
- OpenWebUI not deployed (:3000 not listening). KNOWLEDGE.md was correct.
- The stale pidfile is the unclean-shutdown fingerprint of the stability ghost:
  it died ungracefully after the 05-23 revival and stayed down.

## Next (in order)

1. Bring the stack back up and capture the death cause. Clear the stale pidfile
   (`scripts/clean.sh` or `rm run/persona.pid`), start llama-server then API
   (`scripts/start_llama_servers.sh`, `scripts/start_api.sh`), confirm
   `curl 127.0.0.1:8090/health` and `:8000/health`. Before restarting, grab the
   last llama log (`logs/`) and `dmesg | tail` for OOM-killer / segfault
   evidence on the prior death -- the stability ghost has no root cause yet.
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
  signature), held through the 05-23 M2b run, but is DOWN again as of 06-03 with
  a stale pidfile -- so it recurred after 05-23. Still no root cause. See Next #1.
- `looks_degenerate()` + self-repair loop never landed; land with T2.4 `<think>`
  stripping or formally drop.
