# Handoff -- Project_Persona -- 2026-06-03 1420 PDT

Author: Claude (with Brandon)
Branch: main
Session commits: 6d1c25e, 0b7d1f2, 907120c, d3cd350, c4c3a19, 04a387c
Type: frozen snapshot. Living state is in `todo.md`; history in `changelog.md`.

## What this session did

1. Adopted the three-file WORKFLOW convention (`D:\Projects\WORKFLOW.md`).
   - Split the old `KNOWLEDGE.md` (1022 lines) + living `HANDOFF.md` into
     `knowledge.md` (scope/arch), `todo.md` (current state), `changelog.md`
     (history). ASCII-only; no inline comments in code blocks; root `WORKFLOW.md`
     pointer added; originals archived to `archive/pre-workflow/`.
   - Repaired a corrupt git index (from an interrupted sandbox `git mv`) Windows-
     side with portable git, then fixed a case-only filename issue (the new file
     had been committed as `KNOWLEDGE.md`; renamed to `knowledge.md`).
2. Reconciled the KNOWLEDGE.md (05-23) vs HANDOFF.md (05-16) discrepancy against
   code, config, and git history. Conclusion: each doc was right about different
   things (see "Reconciliation results" below).
3. Checked live EVO-X2 state over SSH, found the stack down by a CLEAN shutdown
   (not the stability ghost), and restarted it to a healthy, serving state.

## Reconciliation results (evidence-based)

- Deployed model: KNOWLEDGE.md correct. EVO-X2 runs unified Qwen3-30B-A3B
  -Instruct-2507 Q5_K_M on :8090; config + 21G on-disk file confirm. M2b passed
  05-23. HANDOFF.md's :8080 / "model not downloaded" was stale.
- Qwen3.6 swap track: the T0.1 GO/NO-GO arch test RAN and PASSED 2026-05-18 (git
  commit). The 26.6G Qwen3.6 GGUF exists only in the Windows portable models/ dir.
  So HANDOFF.md's "run T0.1" critical path was stale (done); T1-T3 never started.
  Two model files / two flows coexist by design (native = Instruct-2507, Windows
  portable = Qwen3.6).
- API behavior: HANDOFF.md correct, KNOWLEDGE.md System State stale. Verified in
  `services/api/server.py`: /v1/chat/completions ignores `stream`, returns one
  JSON body (861-890), prompt_tokens hardcoded 0 (888); /chat_submit disabled
  (837); /agent/run blocking subprocess.run(timeout=300) (684).
- OpenWebUI: not deployed (:3000 down). KNOWLEDGE.md correct.

## Current state (VERIFIED)

- EVO-X2 stack UP and healthy as of 1420 PDT. llama-server pid 20606 (:8090
  /health ok), API pid 20683 (:8000 /health all green). End-to-end smoke via
  /v1/chat/completions returned a real completion.
- The 05-23 down-state was a clean shutdown (api.log "Application shutdown
  complete"; persona.log "operator(): cleaning up before exit..." + memory
  breakdown). No OOM/segfault. Stale pidfile was an orphan, auto-cleared on
  restart by start_llama_servers.sh.
- Docs are workflow-compliant and ASCII-clean (knowledge.md, todo.md,
  changelog.md, WORKFLOW.md). All session work committed (head 04a387c).

## Next (in order) -- mirrors todo.md

1. Fix AI_ROOT drift: `scripts/stop_llama_servers.sh` and `scripts/clean.sh`
   still default AI_ROOT to the legacy `$HOME/Live/AIStack/Project_Persona`;
   flip both to `$HOME/Git/Project_Persona` to match start_llama_servers.sh.
2. DECISION: pursue the Qwen3.6 swap (T1-T3; T0 gate PASSED) OR keep hardening
   the validated Instruct-2507 stack (M6, then Hermes H1). Record as a dated
   decision.
3. API gaps: implement or stop advertising /v1 streaming; re-enable or remove
   /chat_submit; make /agent/run non-blocking or fold into the Task Board; fix
   prompt_tokens=0.
4. Housekeeping: load_test_m2b.py DEFAULT_ENDPOINT 8080->8090; start_api.sh
   cosmetic SCIENTIST_* banner; min-1 bucket race in bucketize_by_minute.

## Gotchas for the next editor

- git on D:\Projects repos must run Windows-side (portable git at
  `D:\Projects\Tools\PortableGit\cmd`; not on PATH). The Linux sandbox mount
  corrupts the index and blocks deletes under `.git/`.
- Do NOT trust KNOWLEDGE.md-style per-endpoint "Verified" rows without a code or
  runtime check -- several were stale this session.
- Do NOT run `scripts/clean.sh` casually: it wipes `logs/` (incl. the 158M
  persona.log) and currently has the wrong AI_ROOT default.
- Stability ghost (05-19/20 unexplained death) has not recurred but has no root
  cause; watch sustained runs.
- looks_degenerate() + self-repair loop never landed; the 2120 smoke showed mild
  output repetition that such a guard would catch.
