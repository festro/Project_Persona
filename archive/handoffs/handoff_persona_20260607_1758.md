# Handoff -- Project_Persona -- 2026-06-07 1758 PDT (PHASE 1 VALIDATION CLOSED)

Author: Brandon + Claude. Branch: main. HEAD at handoff: 6e23d2e (local, not yet
pushed). Build under test: e7bd3b3 (Qwen3.6, Windows portable, llama-server :8090
+ API :8000). Keep ASCII (see WORKFLOW.md).

## TL;DR

The LIVE validation owed by the 1640 milestone handoff is DONE. All three open
Phase 1 feature items (T2.4 messages, per-profile Chroma, Task Board) passed live
on Qwen3.6 and are now roadmap [x]. The default Exit Gate was re-proven on the same
build. Logs (gate + server) were clean throughout: no errors, no warnings, no
context truncation. A small test-residue issue was found and fixed. Phase 1 now has
exactly one open item: M6.

## What landed this session (commit 6e23d2e)

1. tests/run_logged.py -- stdlib test-run logger. Runs a test script with the
   launching interpreter (preserves portable python), tees the child's merged
   stdout+stderr to console live, and writes logs/<label>.log (overwritten each
   run, undated). Header: label, Pacific time, full command, cwd, python, platform,
   git HEAD (+clean/dirty), active feature flags. Footer: finish time, duration,
   child exit code, and a PASS/FAIL/Error/Traceback/Warning scan tally. Exits with
   the child return code. Motivation: a green "ALL PASS" can still hide suppressed
   warnings or stderr noise; every run now leaves an auditable artifact.
2. .gitignore -- added persona/profiles/alice/ + bob/ (per-profile gate fixtures).
3. roadmap.md -- T2.4, per-profile Chroma, Task Board flipped [~] -> [x] with live
   validation notes + timestamps.
4. changelog.md (1716 + 1758) + todo.md -- logger + validation milestone recorded.

## Validation results (LIVE, Qwen3.6 / e7bd3b3, via run_logged.py)

- Default Exit Gate (1729): ALL REQUIRED PASS. 23 checks. /health green, topic ->
  think/no_think presets, preserve on/off, /v1 stream + prompt_tokens.
- T2.4 messages (1746, PERSONA_USE_MESSAGES=1): ALL REQUIRED PASS + [messages]
  section -- reasoning sourced from the server reasoning_content, text <think>-free,
  /v1 reasoning_content present. 26 checks.
- Per-profile Chroma (1752, RAG_PER_PROFILE=1 + RAG_ENABLED=1): ALL REQUIRED PASS +
  [per-profile] -- mem_alice + mem_bob collections created. 25 checks.
- Task Board (1758): POST /agent/run with a read-only job (task_id smoke-taskboard,
  steps-only, no edits/commands) -> status ok / returncode 0; recorded into
  data/tasks.db; GET /jobs + /jobs/{id} returned the row with started/finished
  timestamps; /health task_store count=1.
- Under the hood: api.log all 200 OK; persona.log no warn/error/exception, every
  slot release truncated=0 (responses topped ~560 tok, well under the 4096 slot).

## Issue found + fixed this session

- RESIDUE: the per-profile gate created untracked persona/profiles/alice/ + bob/ on
  disk (surfaced by the Task Board smoke's post_context git status). FIX: gitignored
  both (test fixtures) and deleted the dirs. git status --porcelain persona/profiles/
  is now clean. NOTE: mem_alice/mem_bob also persist in the Chroma store (harmless;
  data/ is gitignored).

## Phase 1 status (roadmap)

- [x] Exit Gate proven (1222, re-proven 1729).
- [x] T2.1 sampling presets, [x] T2.2 thinking gate, [x] T2.3 preserve_thinking,
  [x] topic routing, [x] T2.4 messages, [x] per-profile Chroma, [x] Task Board.
- [ ] M6 single-model migration milestone confirmed (LIVE) -- the ONLY open item.
  Clearing it unblocks the Hermes H-track (Phase 9).

## Next session (in order)

1. ENTRY POINT: M6 -- confirm the single-model migration milestone live (M2b passed,
   M5 done). See roadmap Phase 1 / Phase 9. This is the last gate before Hermes.
2. T2.4 PAYOFF: retire the post-hoc sanitizer on the messages path now that
   PERSONA_USE_MESSAGES is live-proven to deliver clean reasoning_content. (Keep the
   raw /completion path's sanitizer; only the messages path can drop it.)
3. git push (6e23d2e is local only).
4. Standing PRIORITY (2026-06-06 directive): Phase 0.5 cross-OS/arch portability --
   live-host manage.py up/down on the Win Vulkan box is done; Linux x64 + ARM64 legs
   remain DEFERRED (no hardware). See roadmap Phase 0.5.

## Checklist for the next operator

- [ ] git push origin main (carry 6e23d2e up).
- [ ] M6 live confirmation -> flip roadmap [ ] to [x].
- [ ] Retire post-hoc sanitizer on the messages path (T2.4 follow-up).
- [ ] Optional: per-profile global_memory migration helper (turning on
      RAG_PER_PROFILE does not move existing global_memory rows).
- [ ] Re-validate via: .\portable\python\python.exe tests\run_logged.py
      tests\exit_gate_live.py (stack up). Flag-gated sections need the matching env
      (PERSONA_USE_MESSAGES=1 / RAG_PER_PROFILE=1 + RAG_ENABLED=1) + a restart.

## Open / watch

- (low, CONFIRM) live n_ctx=4096 x4 slots vs documented PERSONA_CTX=32768 -- confirm
  run/config.toml (possible intentional 16 GB VRAM fit). No truncation observed at
  current response sizes.
- (info) Qwen3.6 MTP speculative-decoding checkpoint churn under parallel prompts.
- (info) Each exit_gate_live.py run overwrites logs/exit_gate_live.log (latest-only
  by design); upload/copy the log if a specific pass needs to be retained.
