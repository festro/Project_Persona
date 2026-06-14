# Handoff -- Project_Persona

Date/time: 2026-06-14 1407 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: ALL edits LOCAL this session, nothing committed/pushed. git runs
Windows-side only (portable git); do NOT git or validate D:\ files from the Linux
sandbox. Continues from handoff_persona_20260614_0014.md.
To resume: "continue from handoff_persona_20260614_1407.md".

UPDATE 1427: C-track GREEN (test_api_offline 84/84, test_manage_pid 11/11 on portable
3.11.9) and D LIVE-CONFIRMED in WSL via scripts/verify_pid_recovery.sh (real 7B pid 480;
`down` killed the real pid, no orphan on :8090). Only A (orphan deletes + commit/push)
remains below.

================================================================================
DECISIONS THIS SESSION (Brandon)
================================================================================

- E (SSH-to-GitHub in WSL) SKIPPED. Keeping the local WSL <-> D:\ folder sync
  current + pushing via the D:\ git gateway is sufficient durability.
- B (EVO-X2 H2 Exit Gate) DEFERRED until everything else is finished.
- A / C / D left to Claude's discretion -> did D now (real fix), prepared C + A
  as Windows-side commands so the fix ships inside the milestone push.

================================================================================
DONE -- D CLOSED: manage.py WSL stale-pidfile robustness (changelog 1407)
================================================================================

Root cause: a recorded pid could read dead (pid_alive False) in WSL while the
server /health was still up. Effects: `status` reported a false "stale pidfile",
and `down` (via stop_named) saw the dead pid, deleted the pidfile, and left the
real server running = the stale-server trap from handoff 0014.

Fix (manage.py, all additive / back-compatible):
- http_health_up(url) -- reuses http_get_json; True iff /health answers.
- pids_by_cmdline(needles) -- dependency-free /proc cmdline scan, ALL needles must
  match; returns [] on Windows (so Windows behavior is unchanged).
- resolve_live_pid(pid, health_url, needles) -- trusts the recorded pid, else if
  /health is up recovers the real serving pid from the process table.
- stop_named(root, name, health_url=None, needles=None) -- kills the RESOLVED live
  pid instead of just unlinking the pidfile; also recovers a fully orphaned server
  (no pidfile but /health up). cmd_down passes markers: api -> :8000 /health +
  "server:app"; persona -> :PERSONA_PORT /health + ["llama-server","--port <port>"].
  scientist/reasoning/coder/persona_win keep prior behavior (defaults None).
- cmd_status -- corroborates pid with /health: "running but /health down" warning,
  and "/health UP on real pid N; pidfile pid M stale (WSL trap)" instead of a bare
  "stale pidfile". host/port hoisted to the top of the function (no duplicate).

Test (new, offline, stdlib): tests/test_manage_pid.py -- 10 checks monkeypatching
pid_alive / http_health_up / pids_by_cmdline / terminate_pid. Covers resolve_live_pid
(live / dead+up / dead+down / orphan) and stop_named (stale-but-up kills real pid,
dead+down just cleans pidfile, orphan kills real pid, normal kills recorded pid).

Files touched: manage.py, tests/test_manage_pid.py, changelog.md, todo.md,
knowledge.md, this handoff. NOT YET: run/ orphan deletes, the commit.

================================================================================
NEXT (pick up here) -- Windows-side; Claude reads logs
================================================================================

C. Run the offline suites on portable 3.11.9 (from D:\Projects\Git\Project_Persona):

   portable\python\python.exe tests\test_api_offline.py
   portable\python\python.exe tests\test_manage_pid.py

   Expect both: exit 0, all checks PASS. (Adjust the python path if the portable
   interpreter lives elsewhere -- whatever `find_api_python` resolves to.)
   Then delete orphans if present:
     del run\wsl_h2_sim.log
     del tools\_mount_probe.txt

D-LIVE. Confirm the fix against a real server (WSL or any host):
   - start persona, note the llama-server pid;
   - `python manage.py down` -> expect "Stopping persona (pid ...)" and a real kill
     (verify no leftover: `pgrep -af llama-server` empty / `ps ... gguf` gone),
     NOT "stale pidfile, removing" with the server still serving /health;
   - `python manage.py status` -> health-corroborated lines.

A. Milestone commit + push (D:\ -> origin), AFTER C is green. Keep the WSL <-> D:\
   sync current first (scripts/wsl_h2_sim.ps1 -Stage pullback if WSL is ahead, or
   -Stage sync if D:\ is ahead). Suggested message:

   Phase 8: Track C WSL-GREEN + per-host config + bidirectional sync; manage.py
   stale-pidfile robustness fix (D) + offline test.

   Bundle: manage.py, run/config.daemonic-pc.toml, scripts/wsl_h2_sim.ps1,
   tests/test_manage_pid.py, .gitignore, knowledge.md, todo.md, changelog.md,
   roadmap.md, WORKFLOW.md, D:\Projects\AGENTS.md, the review doc, and the handoffs.

DEFERRED: B (EVO-X2 Exit Gate) until the above is finished. SKIPPED: E.

================================================================================
GOTCHAS CARRIED FORWARD
================================================================================

- git + file validation are Windows-side only; the Linux sandbox mount serves
  stale/truncated reads of D:\ files -- do not parse/wc/md5/test them there.
- powershell 5.1 (not pwsh): powershell -ExecutionPolicy Bypass -File <ABS path>.
- WSL GPU is unreachable (CPU-only sim); GPU work belongs on EVO-X2.
- After a model swap verify the SERVED gguf (ps grep) before trusting a run.
