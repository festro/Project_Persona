# Handoff -- Project_Persona  (Phase 8 H2d: bridge validated live in WSL)

Date/time: 2026-06-13 1458 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: all edits LOCAL (mid-phase). git runs Windows-side. The WSL sim runs in a
SEPARATE native-fs clone (~/Git/Project_Persona); the D:\ repo holds the code/docs.
Prior handoffs today: 0256 (H2b/H2c code), 0311 (shapes + WSL plan).

================================================================================
HEADLINE
================================================================================

The H2 bridge (persona Task Board <-> Hermes native kanban) is VALIDATED END TO END
against the REAL Hermes, run entirely inside Windows WSL2 (everything-in-WSL:
llama qwen2.5-1.5b + persona API + Hermes v0.16.0 + tools/hermes_bridge.py).

Proven chain (live): POST /agent/delegate -> bridge `kanban create` (hermes_task_id
recorded) -> dispatcher CLAIMS -> SPAWNS worker -> worker runs the real agent
(connects to persona :8090/v1, receives task + orientation) -> terminates -> bridge
MIRRORS state (delegated -> running -> error/blocked) back into /jobs with
attempts/started_at/finished_at. Correlation, idempotent create, and lifecycle
mirror all confirmed against the real CLI (not the faked-CLI unit suite).

COMPLETION (status=ok + summary) was NOT reached -- by design of the sim model. The
1.5B cannot drive Hermes' tool-calling loop: worker log = "Messages: 2 (1 user,
0 tool calls)" then "I'm sorry, I can't continue." It never calls kanban_show()/
kanban_complete(). This is a MODEL-CAPABILITY floor, not a bridge defect. EVO-X2's
Qwen3.6-35B (the model Hermes' >=64K-context requirement is built for) is expected to
complete and close the Exit Gate.

================================================================================
INTEGRATION FINDINGS (live-confirmed; the why behind the long debug)
================================================================================

1. default-assignee HERMES_HOME = the ROOT. Hermes' resolve_profile_env('default')
   returns get_profile_dir('default') = <root> (the dir holding profiles/), and the
   worker reads <root>/config.yaml -- NOT profiles/default/config.yaml. The project's
   "profile dir == HERMES_HOME" convention collides. FIX: seed persona/config.yaml
   from the default profile (the profiles stage now does this), or use NAMED profiles
   (profiles/<name>/) which Hermes resolves directly.
2. >=64K context gate on EVERY model. Hermes validates the main model AND each
   auxiliary (compression, decomposer, ...) separately at >=64000. For sub-64K
   models, override model.context_length + auxiliary.<name>.context_length (the
   profiles stage sets all to 65536). Sim-only; the 35B doesn't need it.
3. PERSONA_CTX splits across PERSONA_PARALLEL (per-slot = CTX/PARALLEL). A Hermes
   worker prompt is ~22k tokens; at CTX=32768/PAR=4 = 8192/slot it 400'd
   ("exceeds context"). FIX: PERSONA_PARALLEL=1 (single 32768 slot). Sim-only.
4. Pin HERMES_KANBAN_HOME so dispatcher + bridge share one board
   (run/hermes_kanban/kanban.db). Always required.
5. setup_native_stack.sh uv Hermes flow + init_profiles + kanban init all worked
   live on WSL -- the carried installer fix is real-world proven.

================================================================================
TOOLING (scripts/wsl_h2_sim.ps1) -- fixes made this session
================================================================================

Staged WSL orchestrator: preflight/sync/setup/profiles/up/dispatch/smoke/mirror/
status/down. Tees clean UTF-8 output to logs/wsl_h2_sim.log (Windows-side, readable).
Bugs fixed along the way (all PowerShell 5.1 / WSL boundary issues):
  - transport: base64-encode the stage script, decode to /tmp/h2_stage.sh, run the
    FILE (piping into `bash` via stdin corrupted heredocs).
  - $body/$Body case-collision: PS is case-insensitive + dynamic-scoped, so
    Invoke-Wsl's $body shadowed the script's $Body -> the delegate body got the stage
    script. Renamed params to $stageBody.
  - Out-Null swallowed WSL stdout (only stderr showed); removed it.
  - mojibake: set [Console]::OutputEncoding=UTF8 + strip ANSI escapes (PS 5.1 was
    decoding WSL UTF-8 as the OEM codepage); NO_COLOR/TERM=dumb in the prelude.
  - -SkipDeps switch (sudo apt has no TTY under non-interactive wsl).
  - profiles stage bakes in the config seed + 64K overrides; mirror stage polls an
    existing job without re-delegating.
Companion runbook: docs/wsl_h2_runbook_20260613_0311.md (section 10 = these results
+ EVO-X2 deployment steps).

================================================================================
CURRENT STATE
================================================================================

- D:\ repo: bridge code (server.py /agent/delegate, tools/hermes_bridge.py),
  faked-CLI suite (tests/test_hermes_bridge.py, 44/44 off-mount), wsl_h2_sim.ps1,
  runbook, design doc, knowledge/changelog/todo/roadmap all updated. Local commits
  only; nothing pushed; D: git runs Windows-side.
- WSL clone: stack may be left up (llama/api) -- `-Stage down` to stop. The sim-only
  config overrides live in the WSL clone's persona/config.yaml + run/config.toml,
  NOT in the D:\ repo (gitignored runtime / separate clone).
- OWED Windows-side: run tests/test_api_offline.py on portable 3.11.9 to confirm the
  delegate/blocked offline checks (72 + new) pass; then commit.

================================================================================
NEXT (pick up here)
================================================================================

PRIMARY -- H2d on EVO-X2 (the real Exit-Gate close). Per runbook section 10:
  1. EVO-X2 serves Qwen3.6-35B (>=64K) -> SKIP the sim overrides (A/B/C); keep
     HERMES_KANBAN_HOME pinned + the default-profile config.
  2. assignee=default (or a role profile) -> model.base_url at the EVO-X2 persona
     endpoint; confirm safe-config (egress off) on that profile.
  3. Delegate a real task -> bridge tick loop -> expect /jobs/<id> = ok + summary.
     Confirm the spawned worker has no outbound network (egress posture).
  4. Then wire the bridge as a service / Phase 3 daemon child -> H3-H6.

SECONDARY -- if a WSL green is still wanted: swap the sim model for a small but
tool-calling-capable model (e.g. Qwen2.5-7B-Instruct); slower on CPU, may complete.

================================================================================
NOTES
================================================================================

- Bridge transport = Hermes PUBLIC CLI by design; never raw kanban.db writes.
- Push rule: milestones only. H2's Exit Gate closes when a capable model completes a
  delegated task and the bridge mirrors ok+summary (EVO-X2). The WSL run proves the
  mechanics; treat it as the de-risking milestone, not the Exit Gate itself.
- Stray file to delete Windows-side (gitignored, cosmetic): tools\_mount_probe.txt.
