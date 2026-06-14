# Handoff -- Project_Persona  (track C COMPLETE: WSL-green)

Date/time: 2026-06-13 2112 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: all edits LOCAL this session (scripts/wsl_h2_sim.ps1 + docs + memory).
Nothing pushed. git runs Windows-side (portable git); do NOT git or validate the
D:\ repo from the Linux sandbox. Continues from handoff_persona_20260613_1617.md.

================================================================================
HEADLINE -- TRACK C DONE (WSL-green de-risking milestone achieved)
================================================================================

The H2 bridge ran to a literal ok+summary in WSL on a capable model.

  sim-003 / card t_ad33008e: status="ok", card "done", run #24 = 1618s (~27 min)
  on the CPU Qwen2.5-7B. The agent drove the full tool loop to kanban_complete; the
  bridge mirrored the terminal state back into /jobs WITH the summary string,
  finished_at, and worker_session_id. Full chain confirmed on a capable model:
  delegate -> bridge create -> dispatch -> spawn -> agent tool loop -> complete ->
  ok+summary mirrored.

This is the de-risking milestone, NOT the H2 Exit Gate. The Exit Gate (ok+summary
on EVO-X2 35B + GPU + worker egress off) is unchanged and still pending.

================================================================================
WHAT THIS SESSION DID
================================================================================

1. MODEL-SWAP SUPPORT (changelog 1617): scripts/wsl_h2_sim.ps1 gained -PersonaModel
   / -PersonaCtx / -PersonaParallel / -ModelUrl + a "model" stage that fetches the
   GGUF into the WSL clone's models/ and patches the WSL clone's run/config.toml
   (table-aware: [linux] model/ctx + [base] parallel; [windows] + D:\ repo untouched,
   35B stays the EVO-X2 target). Model used: Qwen2.5-7B-Instruct-Q4_K_M (Apache-2.0).

2. 7B DRIVES THE LOOP (changelog 1945/1957): on CPU the 7B made real tool calls
   (kanban_show -> read -> kanban_block/complete) -- past the 1.5B's 0-tool-call
   floor. sim-002 ended "blocked" because the task used a repo-relative path and
   Hermes runs workers in an ISOLATED scratch workspace (empty), so docs/..md was not
   found; the agent correctly blocked. The bridge mirrored "blocked" + block_reason.
   sim-003 (self-contained, no-file task) then ran clean to "ok" (above).

3. CPU THROUGHPUT REALITY (from logs/persona.log): pure CPU ~18 tok/s; each agent
   turn re-prefills the ~22k-token Hermes orientation prompt (~15-20 min/turn);
   ~27 min for a 2-turn task. Functional, not fast.

4. GPU IN WSL = DEAD END FOR THIS AMD CARD ("caps" probe): WSL2 exposes only /dev/dxg
   (no /dev/dri), so RADV finds nothing and vulkaninfo shows only llvmpipe (software);
   the shipped llama.cpp is a CPU-only build. AMD GPU acceleration belongs on EVO-X2
   (real Ubuntu, /dev/dri, RADV) or a Windows-native llama-server + WSL Hermes split
   (WSL mirrored networking so model.base_url stays 127.0.0.1 for the safe-config
   gate). Saved to memory (wsl-amd-no-gpu).

5. ORCHESTRATOR HARDENING (scripts/wsl_h2_sim.ps1), all to fix issues hit live:
   - Stream WSL output per-line (was buffered via Out-String) -> long stages show
     progress instead of looking hung.
   - Wrap the native wsl call in ErrorActionPreference=Continue -> curl/native stderr
     no longer throws NativeCommandError under -ErrorAction Stop. (This was the first
     blocker: curl's progress meter aborted the download.)
   - curl --no-progress-meter; timestamp each smoke/mirror tick.
   - New "model" stage now tears the stack DOWN after patching, because manage.py up
     SKIPS starting if a llama-server is already alive -- a stale 1.5B server kept
     serving the old model until force-killed (pkill -9 -f llama-server). After any
     swap, verify the served gguf:
       wsl -- bash -lc "ps aux | grep -o 'models/[^ ]*\.gguf' | grep -v grep | head -1"
   - New "logs" stage: tails the WSL-clone stack/worker logs (persona.log, api.log,
     run/hermes_kanban/kanban/logs/<tid>.log) into logs/wsl_h2_sim.log.
   - New "caps" stage: GPU/Vulkan/llama-backend probe.

6. WORKFLOW / CONTINUITY: WORKFLOW.md gained a "Logs and session continuity" section
   -- Claude reads logs/wsl_h2_sim.log (Windows side) with the Read tool instead of
   asking Brandon to paste; -Stage logs surfaces the WSL-only logs. Saved to memory
   (read-run-logs-directly, wsl-amd-no-gpu).

================================================================================
HOW TO REPRODUCE THE WSL-GREEN RUN (Windows + WSL2, CPU)
================================================================================

The 7B + patched config already live in the WSL clone. If starting clean:

  # one-time, full pipeline (downloads the gguf if absent, then runs everything):
  powershell -ExecutionPolicy Bypass -File D:\Projects\Git\Project_Persona\scripts\wsl_h2_sim.ps1 `
    -PersonaModel "Qwen2.5-7B-Instruct-Q4_K_M.gguf" -PersonaParallel 1 -PersonaCtx 32768 `
    -ModelUrl "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf"

  # a clean ok+summary on a self-contained task (~27 min on CPU):
  powershell ... wsl_h2_sim.ps1 -Stage smoke -JobId sim-NNN `
    -Title "Summary of agent bridges" `
    -Body "Write a 5-line summary explaining how a task-board bridge hands work from a delegating API to an autonomous agent runtime, then mark the task complete." `
    -DispatchTicks 80 -TickSleep 30

Gotchas (all bit us this session):
  - pwsh vs powershell: the box has Windows PowerShell 5.1 -> use `powershell`.
  - manage.py up skips a live server -> after a model swap, down/kill first, then
    verify the served gguf (command above). The model stage now auto-downs.
  - Tasks needing repo files FAIL: Hermes workers run in an isolated scratch
    workspace, so repo-relative paths are not visible. Use self-contained tasks (or
    stage files into the workspace) for WSL tests.
  - A file-read task would need the doc inside the worker workspace or an
    absolute-path read the agent's read-tool is allowed to reach (untested).

================================================================================
NEXT (pick up here)
================================================================================

A. EVO-X2 35B -- the REAL H2 Exit Gate (handoff 1504 section B): delegate a real
   task against the 35B (GPU, fast), expect /jobs/<id> = ok + summary, confirm the
   spawned worker has NO outbound network (egress-off). Skip the sim ctx/parallel
   overrides; the 35B already serves >=64K.
B. A-track Windows confirm+commit (handoff 1504 section A): run tests/test_api_offline
   .py on portable 3.11.9, commit locally; delete orphans (run\wsl_h2_sim.log,
   tools\_mount_probe.txt).
C. PUSH: WSL-green is a de-risking milestone -> a local commit is warranted; per the
   push rule (milestones only) the bigger push point is the EVO-X2 Exit Gate. Brandon's
   call.

================================================================================
OPERATING NOTES (abbreviated; see 1504 for the rest)
================================================================================

- Read run output, do not ask to paste: logs/wsl_h2_sim.log (Read tool, Windows side);
  -Stage logs for the WSL-only stack/worker logs. -Stage caps for GPU probe.
- git: D:\ repo Windows-side only; the Linux sandbox mount serves stale/truncated
  reads -- don't parse D:\ files from the sandbox.
- Docs: knowledge.md (scope) / todo.md (short-term) / changelog.md (history) /
  roadmap.md (phases). Stamps Pacific. To resume: "continue from
  handoff_persona_20260613_2112.md".
