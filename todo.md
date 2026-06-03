# Project_Persona -- TODO

Short-term shared memory. See `knowledge.md` for project scope and
`changelog.md` for history.

Last updated: 2026-06-03 0301 UTC by Claude

## Rules of the road

- This file holds ONLY "just finished" and "next up". Nothing else.
- When something here is more than ~one session old, move it to `changelog.md`.
- Project scope / architecture lives in `knowledge.md`. Do not duplicate.
- Keep it ASCII (see `WORKFLOW.md`).
- Whoever edits this file: bump the "Last updated" stamp and put your name on it.

## Just finished (2026-06-03, Claude -- workflow-compliance restructure)

- Split the old `KNOWLEDGE.md` + living `HANDOFF.md` into the three-file
  convention: `knowledge.md` (scope/arch), `todo.md` (this), `changelog.md`
  (history). Converted everything to ASCII; stripped inline comments from
  config blocks; added the root `WORKFLOW.md` pointer.
- Archived the originals to `archive/pre-workflow/` (KNOWLEDGE.md, HANDOFF.md,
  HANDOFF.html).
- Prior work session (2026-05-23, before this restructure): M2b sustained-load
  baseline PASSED -- 30-min run at concurrency 4 on EVO-X2, 2066/2066 OK,
  gen_tps_mean 28.26 per slot (~113 tok/s aggregate), per-minute throughput
  flat, stability ghost did not recur. Report: `logs/m2b_2026-05-23_0723.json`.

## Next (in order)

1. RECONCILE the current-state discrepancy between the two archived living docs
   before trusting either downstream. `archive/pre-workflow/KNOWLEDGE.md`
   (2026-05-23) says: unified Qwen3-30B-A3B-INSTRUCT-2507 is deployed on :8090,
   M2b is done, next is M6/Hermes-H1. `archive/pre-workflow/HANDOFF.md`
   (2026-05-16) says: the critical path is still the QWEN3.6 T0.1 GO/NO-GO arch
   test and OpenWebUI is "running". These contradict each other on (a) which
   model is actually deployed, (b) whether T0.1 has been run, (c) OpenWebUI
   status. Determine ground truth on EVO-X2 (`scripts/status.sh`; check listener
   on :8090; inspect the loaded model file), then correct this file.
2. (Pending step 1) If Instruct-2507 path is real: resume at M6 -- parallelize
   RAG retrieval + worker dispatch with `asyncio.gather`, replacing the serial
   in-band reasoning call. Alternatively start the Hermes H1 pre-flight block
   (H1.1 read docs -> H1.5 egress integration test with packet capture).
3. Housekeeping fix-its surfaced 2026-05-23: `scripts/load_test_m2b.py`
   DEFAULT_ENDPOINT drift (8080 -> 8090); `start_api.sh` cosmetic SCIENTIST_*
   banner; `prompt_tokens=0` in API responses (token-counter bug?); min-1
   bucket race in `bucketize_by_minute`.
4. Repair the git index: `.git/index` is corrupt and a stale `.git/index.lock`
   exists (could not be cleared from the sandbox). See `changelog.md` top entry
   for the exact commands, then stage and commit this restructure.

## Blocked / waiting

- Hermes adoption (H1-H6) -- gated on single-model migration completing. M5 is
  done and M2b passed; confirm M6 status during step 1 above before starting H1.
- T4 deferred/opt-in items (dual-memory unification, vision pathway, MTP /
  speculative decoding) -- each has a documented trigger; none active.
- TODO #36 -- re-evaluate Qwen3.5/3.6 after ~2026-08, gated on bartowski
  publishing a Qwen3.5 imatrix Q5_K_M GGUF AND llama.cpp confirming qwen3_5_moe
  arch support.

## Notes for next editor

- The git repo index is currently corrupt (see Next #4) -- do not run git from
  the Linux sandbox; use the Windows-side git.
- llama-server "stability ghost": the process died at least once (05-19/20) with
  no graceful-shutdown signature; root cause unidentified. It did NOT recur
  during the 05-23 M2b run. Watch for it.
- Peak-load thermal was never captured for M2b (only a post-test idle sample).
  Parallel-log `sensors` during the next baseline pass.
- `looks_degenerate()` + self-repair loop were spec'd historically but never
  landed in `services/api/server.py`. Decision: land alongside T2.4 `<think>`
  stripping or formally drop. Do not treat as live behavior.
