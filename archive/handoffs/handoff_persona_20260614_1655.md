# Handoff -- Project_Persona  (SESSION CLOSE)

Date/time: 2026-06-14 1655 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Continues from handoff_persona_20260614_0014.md.
To resume: "continue from handoff_persona_20260614_1655.md".

Repo state:
- origin/main = aa145fa (PUSHED this session): Track C WSL-GREEN + per-host config +
  bidirectional sync + the manage.py pidfile fix (28 files).
- local main = 2eb8c94 (LOCAL ONLY, not pushed): all the docs + the regression runner
  + the mesh design below. Sits on top of aa145fa.
- git + file validation are Windows-side only; do NOT git or validate D:\ files from
  the Linux sandbox (stale/truncated reads).

================================================================================
HEADLINE
================================================================================

1. Item D CLOSED + PUSHED: manage.py WSL stale-pidfile robustness fix, unit-tested
   (11/11) and live-confirmed in WSL; shipped in aa145fa.
2. ROADMAP re-evaluated + simplified to one vocabulary; status refreshed; Phase 9/10
   SWAPPED; EVO-X2 migration added.
3. Phase 10 (new full-system test phase) STARTED: a one-command offline regression
   runner, green 4/4 on Windows.
4. MESH design extended: section 5b coordinated eviction + node_id (Brandon's proposal).
5. Brandon's standing calls: E (SSH-in-WSL) SKIPPED; B (EVO-X2 H2d Exit Gate) DEFERRED
   until the rest is finished.

================================================================================
DONE THIS SESSION
================================================================================

D -- manage.py WSL stale-pidfile fix (changelog 1407; in aa145fa)
- Root cause: a recorded pid could read dead while /health was still up, so `status`
  lied ("stale pidfile") and `down` orphaned the live server.
- Fix: http_health_up() + pids_by_cmdline() (/proc scan, Linux-only, [] on Windows) +
  resolve_live_pid(); stop_named() kills the resolved live pid (recovers orphans too);
  cmd_status corroborates pid with /health. Windows path unchanged.
- Proof: tests/test_manage_pid.py 11/11 + test_api_offline.py 84/84 (portable 3.11.9);
  LIVE in WSL via scripts/verify_pid_recovery.sh (real 7B pid 480; `down` killed the
  real pid, no orphan on :8090).

ROADMAP simplify + renumber (changelog 1500; local 2eb8c94)
- One vocabulary: Phase / Item / Exit Gate / Status. Retired track/milestone/stage/leg.
  Exit Gates are now checklists. T/H/M IDs kept as Item IDs.
- Status refresh: Phase 1 -> [x] GREEN (M6 was the last item; gate proven 2026-06-07).
  "Current position" rewritten.
- Phase 9/10 SWAP: deleted CrewAI "Phase 9" tombstone removed; node mesh moved to
  Phase 9 (Items 9.0-9.5; mesh "Stage 0-4" -> Items 9.1-9.5); NEW Phase 10 = full-system
  / feature-test capstone.
- EVO-X2 migration added as Item 9.0 [~] (anchor node; endgame = everything on EVO-X2).
- Repo-wide numbering sync (DONE): knowledge.md, docs/distributed_nodes.md (+Stage<->Item
  map), ipc_decision.md, portability_audit.md, llama_build_matrix.md. Changelog history +
  archive/ left frozen.

Phase 10 Item 10.0 -- regression runner (changelog 1520; local 2eb8c94)
- tests/run_all_offline.py: auto-discovers tests/test_*.py, runs each in its own process
  with the current interpreter, aggregates pass/fail, exits 0 only if all pass.
- WINDOWS x64 GREEN 2026-06-14 1530: 4/4 suites PASS (portable 3.11.9). Item 10.0 -> [~].

Mesh design -- section 5b (changelog 1535; local 2eb8c94)
- docs/distributed_nodes.md section 5b "Coordinated eviction + key rotation" (Brandon):
  (1) honest nodes gossip a bad-actor flag (excluding the actor) + JOINTLY rotate the
  shared token, distributing the new one only to known-good node ids; (2) nodes that
  missed the rotation re-keyed OUT OF BAND via NFC/Bluetooth (+ QR/manual fallback for
  headless nodes); (3) a stable node_id hashed from salted system specs at manage.py
  first boot, bound to the signing keypair, embedded in the message layer.
- WHY: turns section 4's advisory per-key deny-list into an ENFORCEABLE eviction --
  node_id survives a re-key, so deny-by-node-id bites; token rotation is the hard
  backstop. node_id = a sybil/re-key DETERRENT (specs are spoofable), not proof.

================================================================================
NEXT (pick up here)
================================================================================

A. Item 10.0 Linux leg: run `<py> tests/run_all_offline.py` on a Linux host (EVO-X2, or
   a WSL clone that has the API deps for test_api_offline). Green there flips 10.0 -> [x].
B. H2 EXIT GATE on EVO-X2 (Item H2d, DEFERRED by Brandon until the rest is done):
   delegate a real task against the 35B + GPU, expect /jobs ok + summary, worker egress
   OFF. This is the next true Phase 8 lock and a natural milestone push point.
C. EVO-X2 migration (Item 9.0): run persona + API + Hermes natively on EVO-X2 as the
   canonical node; make it the source-of-truth dev/run surface.
D. Mesh section 5b opens (when Phase 9 is actually worked): re-key authorization quorum
   (avoid eviction-as-attack), cutover window, split-brain reconcile, node_id spec/salt/
   re-enrollment, OOB transport choice.
E. Carried fix-it: manage.py capabilities reports llama_build=null while doctor detects
   b9219.
F. PUSH local 2eb8c94 -> origin at the next milestone (e.g. with the EVO-X2 H2d work).
   The PortableGit push shows a red NativeCommandError even on success -- judge by the
   ref-update line, not the error.

================================================================================
GOTCHAS CARRIED FORWARD
================================================================================

- powershell 5.1 (not pwsh): powershell -ExecutionPolicy Bypass -File <ABS path>.
- WSL GPU is unreachable (CPU-only sim); GPU work belongs on EVO-X2.
- After a model swap verify the SERVED gguf (ps grep) before trusting a run.
- manage.py up SKIPS a live server; reliable liveness = /health + `ps ... gguf` (the
  pidfile fix now makes down/status agree, but the manual check still holds).
