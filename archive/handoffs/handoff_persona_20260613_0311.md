# Handoff -- Project_Persona  (Phase 8 H2: real shapes + WSL staging plan)

Date/time: 2026-06-13 0311 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: all edits LOCAL this run (mid-phase = local commit only, no push).
Prior handoffs today: 0256 (H2b/H2c code), 0204 (H2a design). origin/main = 0cb85bf.

================================================================================
WHAT HAPPENED THIS RUN
================================================================================

1. DIRECTION (Brandon): stage H2 in Windows WSL2 (everything-in-WSL) before EVO-X2.
   Hermes is Linux/WSL2-only -> WSL is a faithful EVO-X2 mirror. Migrate when stable.

2. SANDBOX SOURCE DIVE -- de-risked the Hermes CLI contract independently of any
   target box. Cloned hermes-agent v0.16.0 @ 9b1e0d6f in the Ubuntu sandbox (uv
   0.11.19 present). Full install was BLOCKED (uv could not fetch CPython 3.11 -- the
   python-build-standalone download host is not allowlisted; only git clone is), so
   validated against SOURCE (authoritative). Confirmed:
   - Kanban board is SHARED ACROSS PROFILES: kanban_home() walks HERMES_HOME=
     <root>/profiles/<name> UP to <root>; default DB = <root>/kanban.db (NOT the
     profile dir). => PIN HERMES_KANBAN_HOME so bridge + dispatcher agree.
   - `kanban create --json` = bare task dict (read .id). `kanban show --json` =
     WRAPPED {"task":{...}, "latest_summary", "runs":[{outcome,summary,error,
     metadata,ended_at}], "events":[...]}. No block_reason/log_path keys; block
     reason is the blocked run's summary/error; tasks.result usually null.
   - status set: triage/todo/scheduled/ready/running/blocked/review/done/archived.
   - dispatcher: `kanban dispatch` (one pass) or `gateway start` (embedded 60s);
     standalone --daemon deprecated. assignee must be a real profile.

3. BRIDGE RECONCILED (tools/hermes_bridge.py): derive_update now reads the wrapped
   show payload; _COLUMN_MAP = real status set (review->blocked etc.); metadata
   json-string tolerant; finished_at from ended_at. tests/test_hermes_bridge.py
   updated -> 44/44 ALL PASS off-mount.

4. WSL RUNBOOK: docs/wsl_h2_runbook_20260613_0311.md (everything-in-WSL: install via
   the updated uv flow, env pinning, dispatcher options, the delegate->dispatch->
   mirror smoke = H2d gate). Design-doc open questions annotated RESOLVED/LIVE-CONFIRM.

================================================================================
VALIDATION GOTCHA (important for next session)
================================================================================

The Linux sandbox 9p mount served STALE/TRUNCATED reads of files I had just edited
(hermes_bridge.py / test cached at a pre-edit length; cp + python open both saw the
truncated bytes, while the file-tool Read showed the true content). A brand-NEW file
path read fresh. Workaround used: re-authored the current files into the sandbox-local
fs (/tmp, via heredoc) and ran there -> 44/44. Lesson: to run an EDITED D:\ file in
the sandbox, copy it to a fresh /tmp path authored from known content, do not trust a
cp of the just-edited mount inode. (Consistent with the standing "don't validate D:\
files from the sandbox" rule.)

================================================================================
CURRENT STATE
================================================================================

- H2a design + H2b (delegate endpoint) + H2c (bridge) all in, off-mount green
  (bridge 44/44). Shapes confirmed against real Hermes source.
- Nothing pushed; no model/Hermes/EVO-X2 touched (sandbox source-read only).
- Files this run: tools/hermes_bridge.py, tests/test_hermes_bridge.py,
  docs/h2_bridge_design_20260613_0204.md (open Qs), .gitignore; NEW:
  docs/wsl_h2_runbook_20260613_0311.md, this handoff. (Plus 0256's server.py +
  test_api_offline.py + knowledge.md.)

================================================================================
NEXT (pick up here)
================================================================================

A. WINDOWS-SIDE quick confirm (portable 3.11.9): run tests/test_api_offline.py ->
   expect the prior 72 + the new delegate/blocked checks all PASS. Commit locally
   (no push). DELETE the stray probe: `del tools\_mount_probe.txt` (gitignored, but
   tidy it). git runs Windows-side.

B. WSL SIM = the H2d gate. Follow docs/wsl_h2_runbook_20260613_0311.md:
   native-fs clone in WSL -> setup_native_stack.sh -> pin env (HERMES_KANBAN_HOME)
   -> init_profiles + stack up -> kanban dispatch loop -> POST /agent/delegate ->
   `python3 tools/hermes_bridge.py --once` -> confirm /jobs row delegated->running->
   ok with the Hermes summary. PROVE the worker runs under the safe-config (egress
   off) -- the main live-only unknown. Adjust hermes_bridge.derive_update()/parse
   helpers if any live --json field differs from the source-derived shape (one place).

C. THEN migrate to EVO-X2 (same steps; runbook section 9) and H3-H6.

================================================================================
NOTES
================================================================================

- Bridge transport = Hermes PUBLIC CLI by design; do NOT switch to raw kanban.db.
- Pin HERMES_KANBAN_HOME for BOTH dispatcher and bridge (shared-board resolution).
- Everything-in-WSL keeps tasks.db + kanban.db on a native fs (no /mnt 9p SQLite-WAL
  locking). Do not run the sim against a /mnt/d clone.
- Push rule: milestones only. H2 closes when the WSL (or EVO-X2) live smoke passes.
