# Handoff -- Project_Persona  (SESSION CLOSE)

Date/time: 2026-06-13 1504 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: all edits LOCAL this session (mid-phase). git runs Windows-side (portable
git); do NOT git or validate the D:\ repo from the Linux sandbox. The WSL sim runs in
a SEPARATE native-fs clone (~/Git/Project_Persona); the D:\ repo holds code + docs.
Per-milestone detail lives in the handoffs this session produced (0256, 0311, 1458) +
the changelog; this is the consolidating session-close snapshot.

================================================================================
SESSION ARC (all local commits, nothing pushed)
================================================================================

1. CARRIED FIX-ITS (changelog 0049)
   - scripts/setup_native_stack.sh: wrong `pip install hermes-agent` -> real uv
     editable flow (clone @ HERMES_REF=9b1e0d6f, uv venv, uv pip install -e). Same
     file: env writer de-staled Instruct-2507 -> Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf.
   - .gitignore: models/archive/ (+ later run/hermes_kanban/, logs/wsl_h2_sim.log,
     persona/config.yaml.bak, tools/_mount_probe.txt).

2. H2 ARCH DECISION (Brandon): BRIDGE taskboard.py <-> Hermes native kanban
   (taskboard.py / persona /jobs stay canonical; Hermes = execution substrate).

3. H2a DESIGN (changelog 0204): docs/h2_bridge_design_20260613_0204.md.

4. H2b + H2c CODE (changelog 0256):
   - server.py: POST /agent/delegate writes a "delegated" row (no taskman2 run);
     title/dup guards; /health "delegate" block. +~10 offline checks.
   - tools/hermes_bridge.py (NEW, stdlib): enqueue_delegated (Flow A) + mirror_outcomes
     (Flow B) + tick(); runner/board injected; transport = Hermes public CLI.
   - tests/test_hermes_bridge.py (NEW): faked-CLI suite.

5. REAL-SHAPE RECONCILE (changelog 0311): source-dive into hermes-agent v0.16.0 @
   9b1e0d6f confirmed the wrapped `show --json` shape + status set; bridge fixed;
   suite 44/44 off-mount. docs/wsl_h2_runbook_20260613_0311.md written.

6. WSL ORCHESTRATOR + LIVE BRIDGE VALIDATION (changelog 0330/0423/1458):
   scripts/wsl_h2_sim.ps1 -- staged WSL driver. Stood up everything-in-WSL (llama
   1.5B + API + Hermes + bridge) and PROVED the bridge end to end (see section below).

7. LOG RELOCATION (this close): wsl_h2_sim.ps1 log -> logs/wsl_h2_sim.log (was run/).

================================================================================
H2d RESULT -- BRIDGE VALIDATED LIVE (completion model-gated)
================================================================================

PROVEN live against the real Hermes: POST /agent/delegate -> bridge `kanban create`
(hermes_task_id recorded) -> dispatcher CLAIMS -> SPAWNS worker -> worker runs the
agent (connects to persona :8090/v1) -> bridge MIRRORS delegated->running->error
back into /jobs (attempts/started_at/finished_at correct).

COMPLETION not reached: the 1.5B sim model can't drive Hermes' tool-calling loop
(worker log: "Messages: 2 (1 user, 0 tool calls)" / "I'm sorry, I can't continue").
Model-capability floor, NOT a bridge defect. EVO-X2's Qwen3.6-35B is the real target.

Integration findings (live-confirmed; first three are SIM-ONLY workarounds):
  A. default-assignee HERMES_HOME = ROOT (dir holding profiles/), reads
     <root>/config.yaml -- seed it (profiles stage does), or use named profiles.
  B. Hermes needs >=64K ctx on main + EVERY auxiliary model -> override
     model.context_length + auxiliary.<name>.context_length (profiles stage does).
  C. PERSONA_CTX splits across PERSONA_PARALLEL; worker prompt ~22k -> PERSONA_PARALLEL=1.
  D. (always) pin HERMES_KANBAN_HOME so dispatcher + bridge share one board.

================================================================================
CURRENT STATE
================================================================================

- D:\ repo (local commits only, unpushed): server.py, tools/hermes_bridge.py,
  tests/test_hermes_bridge.py, tests/test_api_offline.py, scripts/wsl_h2_sim.ps1,
  scripts/setup_native_stack.sh, .gitignore, knowledge.md, changelog.md, todo.md,
  roadmap.md, docs/h2_bridge_design_*.md, docs/wsl_h2_runbook_*.md, handoffs.
- Off-mount green: tests/test_hermes_bridge.py 44/44.
- WSL clone: stack may be left up (`-Stage down` to stop); sim-only config overrides
  live in the WSL clone only (not the D:\ repo).
- Logging: logs/wsl_h2_sim.log (clean UTF-8, ANSI-stripped, timestamped per run).

================================================================================
NEXT (pick up here)
================================================================================

A. WINDOWS-SIDE quick confirm: run tests/test_api_offline.py on portable 3.11.9
   (expect prior 72 + the new delegate/blocked checks all PASS), then commit locally.
   Delete the orphan logs: del run\wsl_h2_sim.log ; del tools\_mount_probe.txt.

B. PRIMARY -- H2d on EVO-X2 = the real Exit-Gate close (runbook section 10):
   1. 35B already serves >=64K -> SKIP sim overrides A/B/C; keep D + default-profile
      config.
   2. assignee=default (or role profile) -> model.base_url at the EVO-X2 persona
      endpoint; confirm safe-config (egress off).
   3. Delegate a real task -> bridge tick loop -> expect /jobs/<id> = ok + summary;
      confirm the spawned worker has no outbound network. That closes the H2 Exit Gate.
   4. Then wire the bridge as a service / Phase 3 daemon child -> H3-H6.

C. OPTIONAL WSL green: swap the sim model for a tool-calling-capable small model
   (e.g. Qwen2.5-7B-Instruct); slower on CPU but may actually complete.

================================================================================
OPERATING NOTES
================================================================================

- Bridge transport = Hermes PUBLIC CLI; never raw kanban.db writes.
- git: D:\ repo Windows-side only; the Linux sandbox mount corrupts the index /
  serves stale, truncated reads (bit us mid-session -- validate off-mount by copying
  fresh into the sandbox-local fs, never by parsing the D:\ file from the sandbox).
- Push rule: milestones only. H2 Exit Gate closes when a capable model completes a
  delegated task and the bridge mirrors ok+summary (EVO-X2). The WSL run is the
  de-risking milestone, not the Exit Gate itself.
- Docs convention: knowledge.md (scope) / todo.md (short-term) / changelog.md
  (history) / roadmap.md (phases). Stamps Pacific. To resume: "continue from
  handoff_persona_20260613_1504.md".
