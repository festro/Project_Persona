# Handoff -- Project_Persona  (SESSION CLOSE)

Date/time: 2026-06-14 0014 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: ALL edits LOCAL this session, nothing committed/pushed. git runs
Windows-side only (portable git); do NOT git or validate D:\ files from the Linux
sandbox. Continues from handoff_persona_20260613_1504.md (and the 1617/2112 mid-session
handoffs). To resume: "continue from handoff_persona_20260614_0014.md".

================================================================================
HEADLINE
================================================================================

1. PHASE 8 TRACK C COMPLETE -- WSL-GREEN. The H2 bridge ran end to end to a literal
   ok+summary on a capable model in WSL (the 1.5B couldn't tool-call; the 7B does).
2. SOURCE-OF-TRUTH MODEL SET + per-host config + bidirectional sync implemented and
   revalidated.
3. WORKFLOW captured: keep/pass catalogue merged into the official AGENTS.md +
   WORKFLOW.md; memory updated so new sessions don't reset to zero.

================================================================================
TRACK C -- WSL-GREEN (done)
================================================================================

- Swapped the WSL sim model to Qwen2.5-7B-Instruct-Q4_K_M (Apache-2.0; CPU).
- sim-003 AND sim-004 both reached status="ok": the 7B drove the full Hermes tool loop
  (kanban_show -> reason -> kanban_complete) and the bridge mirrored ok + the summary
  string back to /jobs (finished_at, worker_session_id present). ~26-27 min/run on CPU.
- sim-002 ended "blocked" = CORRECT agent behavior: the task used a repo-relative path
  and Hermes runs workers in an ISOLATED scratch workspace, so the file wasn't found
  and the agent blocked with a reason (bridge mirrored blocked + block_reason). ok and
  blocked both mirror via the same mirror_outcomes path. WSL test tasks must be
  self-contained (no repo-relative file reads).
- Throughput reality: pure CPU ~18 tok/s; each agent turn re-prefills the ~22k Hermes
  orientation prompt = ~15-20 min/turn. Functional, not fast.
- GPU is NOT reachable in WSL2 for this AMD card: WSL2 exposes only /dev/dxg (no
  /dev/dri), so RADV finds nothing and vulkaninfo shows only llvmpipe; the llama.cpp
  build is CPU-only. GPU completion belongs on EVO-X2 (real Ubuntu, /dev/dri, RADV).
- This is the de-risking milestone, NOT the H2 Exit Gate. The Exit Gate (ok+summary on
  EVO-X2 35B + GPU + worker egress OFF) is unchanged and still pending.

================================================================================
SOURCE OF TRUTH + SYNC (new model, finalized by Brandon)
================================================================================

- origin/main on GitHub (git@github.com:festro/Project_Persona.git, LFS) = durable
  OFFSITE backstop, reached via D:\ Windows-side git push.
- WSL clone ~/Git/Project_Persona = PRIMARY dev/run surface (closest to EVO-X2; endgame
  is everything on EVO-X2).
- D:\ repo = REDUNDANT copy + Windows multi-platform testbed + git gateway (on the D:
  drive, survives a Windows reinstall; holds the only .git).
- TWO durability mechanisms, kept distinct:
  (1) LOCAL WSL <-> D:\ sync is FREQUENT (the redundancy). After a WSL wipe, restore
      WSL from the D:\ backup.
  (2) git push D:\ -> origin = MILESTONES ONLY (offsite backstop if the D: drive dies).
- Sync mechanism: scripts/wsl_h2_sim.ps1 -Stage sync (D:\ -> WSL, forward, tar) and
  -Stage pullback (WSL -> D:\, reverse, rsync; -Prune for --delete). Pullback PROTECTS
  .git, models/, env*, llama_cpp/, portable/, runtime. Direction is manual.
- DEFERRED UPGRADE: make the WSL clone a real git checkout of origin (needs SSH-to-
  GitHub in WSL, NOT set up) so git could replace the folder sync.

================================================================================
PER-HOST CONFIG (committed, hostname-selected) -- replaces the old clone patch
================================================================================

- manage.py: host_tag() (lowercased short hostname; PERSONA_HOST env overrides) +
  _merge_host_overrides() merges a committed run/config.<host>.toml AFTER
  [base]/[runtime]/[<os>]. `status` prints host_config=... when one applies.
- run/config.daemonic-pc.toml (COMMITTED, tracked): this box's override
  (Qwen2.5-7B-Instruct-Q4_K_M, ctx 32768, PERSONA_PARALLEL=1, ngl 0). Canonical
  run/config.toml [linux] stays the EVO-X2 35B target -> EVO-X2 needs NO file.
- wsl_h2_sim.ps1 "model" stage no longer patches the clone (divergence retired); it
  caches the gguf (-PersonaModel/-ModelUrl) + reloads + prints the effective config.
- Verified off-mount AND live: -Stage sync/model/up showed host_config=
  config.daemonic-pc.toml + model=7B + /health ok; sim-004 -> ok. Nothing broke.

================================================================================
ORCHESTRATOR (scripts/wsl_h2_sim.ps1) -- this session's hardening
================================================================================

- Stream WSL output per-line (was buffered via Out-String) -> long stages show progress.
- Wrap the native wsl call in ErrorActionPreference=Continue -> curl/native stderr no
  longer throws NativeCommandError (the first blocker we hit). curl --no-progress-meter.
- Timestamped smoke/mirror ticks.
- New stages: pullback (reverse sync), caps (GPU/Vulkan/llama-backend probe), logs
  (tails WSL persona/api/worker logs into logs/wsl_h2_sim.log), model (gguf cache +
  reload). down-after-patch so 'up' reloads.
- Dropped -PersonaCtx/-PersonaParallel (now in the committed per-host file).

================================================================================
WORKFLOW / CONTINUITY (so new sessions don't reset)
================================================================================

- Keep/pass catalogue: docs/workflow_patterns_review_20260613_2112.md (24 items).
  Merged into:
  - D:\Projects\AGENTS.md (cross-project agent behavior): "How to run a session" --
    one-command-then-read loop, ground-in-logs, verify-runtime, concise/no-preamble,
    AskUserQuestion at genuine forks, USE+MAINTAIN the TaskCreate widget (esp. for side
    tangents), record negative results, PowerShell native-stderr, git push cadence.
  - Project WORKFLOW.md (P): source-of-truth/sync, per-host config, WSL gotchas.
- Memory updated: read-run-logs-directly, wsl-amd-no-gpu, project-persona-wsl-sim-ops,
  brandon-session-working-loop, project-persona-source-of-truth (final model).
- READ run output directly (logs/wsl_h2_sim.log via Read tool; -Stage logs surfaces
  WSL-only logs). Do NOT ask Brandon to paste console output.

================================================================================
KNOWN ISSUES / GOTCHAS
================================================================================

- BUG (owed): manage.py pidfile/pid_alive is unreliable in WSL -- reports persona/api
  "stale/not alive" even when /health is up. Root of the stale-server trap (down can
  miss the real process). Reliable checks: /health + `ps ... gguf`. Hammer:
  pkill -9 -f llama-server. A robustness fix is owed.
- powershell 5.1, not pwsh: powershell -ExecutionPolicy Bypass -File <ABS path>.
- After a model swap, verify the SERVED gguf (ps grep) before trusting a run.
- WSL diagnostics from PowerShell = one quoted call: wsl -- bash -lc "...".

================================================================================
NEXT (pick up here)
================================================================================

A. Commit + push (Windows-side, D:\ -> origin). This milestone is a good push point and
   it is what makes tonight's work reinstall-safe. (Lots of new/changed files: manage.py,
   run/config.daemonic-pc.toml, scripts/wsl_h2_sim.ps1, .gitignore, knowledge/todo/
   changelog/roadmap, WORKFLOW.md, D:\Projects\AGENTS.md + WORKFLOW pointer, the review
   doc, and the handoffs.)
B. H2 EXIT GATE on EVO-X2 (the real close; handoff 1504 sec B): delegate a real task
   against the 35B (GPU), expect /jobs ok + summary, confirm the worker has NO outbound
   network (egress off). No sim overrides needed (35B already serves >=64K).
C. A-track Windows confirm (handoff 1504 sec A): run tests/test_api_offline.py on
   portable 3.11.9; delete orphans (run\wsl_h2_sim.log if present, tools\_mount_probe.txt).
D. Fix the manage.py WSL pidfile/pid_alive robustness bug.
E. DEFERRED: SSH-to-GitHub in WSL -> make the WSL clone a real checkout -> git replaces
   the folder sync.
