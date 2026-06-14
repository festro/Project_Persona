# Handoff -- Project_Persona  (Phase 8 H2 progress)

Date/time: 2026-06-13 0256 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: Windows clone, all edits LOCAL (mid-phase = local commit only, no push).
Prior session-close: handoff_persona_20260612_2339.md (origin/main = 0cb85bf).

================================================================================
SESSION ARC (this run -- all local, no push)
================================================================================

1. CARRIED FIX-ITS (changelog 0049)
   - scripts/setup_native_stack.sh: replaced the wrong `pip install hermes-agent`
     with the real uv editable flow (install uv if missing -> clone
     NousResearch/hermes-agent @ HERMES_REF=9b1e0d6f -> `uv venv env_hermes
     --python 3.11` -> `uv pip install -e $HERMES_SRC[all,dev]`; repo/ref/src
     env-overridable). Same file: env-fallback writer + next-steps echo de-staled
     off Instruct-2507 -> Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf.
   - .gitignore: added models/archive/.
   - In-place edits -> no chmod needed (executable bit preserved). bash -n OK.

2. H2 KANBAN ARCH DECISION (Brandon): BRIDGE taskboard.py <-> Hermes native kanban
   (was "leaning native"). Recorded in changelog/todo/roadmap.

3. H2a DESIGN (changelog 0204): docs/h2_bridge_design_20260613_0204.md. Researched
   Hermes v0.16.0 kanban from the docs; full schema/status/field mapping, transport
   = Hermes public CLI (not raw DB), additive delegated/blocked statuses, job_id<->
   hermes_task_id correlation, Hermes owns retry. 7 EVO-X2 open questions listed.

4. H2b + H2c CODE (changelog 0256), off-mount green:
   - H2b services/api/server.py: POST /agent/delegate -> writes a "delegated" row
     (kind=hermes_delegate), NO taskman2 run; title-required (400) + dup job_id
     (409) guards; /health "delegate" block. tests/test_api_offline.py +~10 checks.
   - H2c tools/hermes_bridge.py (NEW, stdlib): enqueue_delegated (Flow A, idempotent)
     + mirror_outcomes (Flow B) + tick() + main() loop; runner/board injected.
     tests/test_hermes_bridge.py (NEW): faked-CLI suite, 43/43 ALL PASS off-mount.

================================================================================
CURRENT STATE
================================================================================

- Bridge logic PROVEN off-mount (43/43). Server delegate path py_compile-clean
  off-mount; full FastAPI offline suite NOT run here (needs the pinned chain).
- No model / no Hermes / no EVO-X2 touched this run. Nothing pushed.
- Files changed: scripts/setup_native_stack.sh, .gitignore, services/api/server.py,
  tests/test_api_offline.py, knowledge.md, changelog.md, todo.md, roadmap.md;
  NEW: docs/h2_bridge_design_20260613_0204.md, tools/hermes_bridge.py,
  tests/test_hermes_bridge.py, this handoff.

================================================================================
NEXT (pick up here)
================================================================================

A. WINDOWS-SIDE (Daemonic-PC, portable 3.11.9) -- quick confirm:
   - Run the offline suite: expect the prior 72 + the new delegate/blocked checks
     all PASS. (tests/test_api_offline.py, or via manage.py test / run_logged.py.)
   - git status / commit locally (do NOT push -- mid-phase). git runs Windows-side.

B. EVO-X2 (SSH relay) -- H2d LIVE WIRE = the H2 Exit-Gate evidence. Resolve the 7
   open questions in docs/h2_bridge_design_20260613_0204.md, then:
   1. `hermes kanban init`; find the kanban.db path under HERMES_HOME (profile dir).
   2. Confirm `kanban create/show --json` field shapes match derive_update()'s
      assumptions (id, status/column, runs[].outcome/summary/metadata/log_path,
      block_reason). Adjust the parse helpers in hermes_bridge.py if shapes differ.
   3. Run the dispatcher headless (gateway vs kanban-only daemon -- open question 3).
   4. POST /agent/delegate one task; run `python3 tools/hermes_bridge.py --once`
      (TASKS_DB pointed at the live data/tasks.db, HERMES_HOME set, `hermes` on PATH);
      confirm the /jobs row goes delegated -> running -> ok with the Hermes summary
      attached. Confirm the spawned worker inherits the safe-config (egress off).

C. THEN H3-H6: role-prefix template library, cache_prompt amortization,
   Tenacity-style failure semantics; runtime egress containment (H1.6) is separate.

================================================================================
NOTES / GOTCHAS
================================================================================

- hermes_bridge.py transport is the Hermes PUBLIC CLI by design; do NOT switch to
  raw kanban.db writes (Hermes routes mutation through its tools; schema is internal).
- derive_update()/parse helpers centralize every --json shape assumption -- that is
  the ONE place to edit after the EVO-X2 JSON shapes are confirmed.
- The bridge runs ON EVO-X2 (Hermes is Linux/WSL2-only) and is loopback-only (no new
  egress). It needs TASKS_DB on the same data/tasks.db the API uses + HERMES_HOME set.
- Git: D:\ repo git runs Windows-side (portable git); the Linux sandbox mount
  corrupts the index / serves stale reads -- do not git or validate D:\ files from it.
  (All off-mount validation this run copied files into the sandbox-local fs first.)
- Push rule: milestones only. H2 is not closed until H2d passes live.
