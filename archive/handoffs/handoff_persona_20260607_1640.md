# Handoff -- Project_Persona -- 2026-06-07 1640 PDT (SESSION MILESTONE)

Author: Brandon + Claude. Branch: main. HEAD at handoff: a41138c (pushed) + one
uncommitted change (the extended exit_gate_live.py + this handoff). This is a
session-spanning summary; the per-feature handoffs below carry the detail. Keep
ASCII (see `WORKFLOW.md`).

## TL;DR

A long build session that took Phase 1 from "Exit Gate pending" to "Exit Gate
PROVEN + every offline-draftable feature item landed." Seven shipped units, all
committed + pushed, each default-off where it changes behavior so the proven serving
path was never at risk. What remains is all LIVE validation -- yours -- now collapsed
into one adaptive command (`tests/exit_gate_live.py`).

## What shipped this session (in order, all on origin/main)

1. T2.2 thinking gate (Path A) -- commit 90c8a5b. OFF-by-default THINKING_AUTO_GATE +
   classify_triviality; promotes a non-thinking-topic request to think when
   non-trivial. Offline 22/22. Handoff 1151.
2. StarletteDeprecationWarning silenced (test-harness filter) -- commit 0d90532.
3. T2.3 preserve_thinking (Path A) -- commit e3bf370. split_reasoning() pulls in-band
   <think> before the sanitizer (also fixes the latent leak pre-Qwen3.6);
   preserve_thinking flag surfaces reasoning (`reasoning` /chat, `reasoning_content`
   /v1). Offline 35/35; preserve confirmed live via /v1. Handoff 1208.
4. Phase 1 EXIT GATE -- commit 73d2e31. New tests/exit_gate_live.py; PROVEN live on
   Qwen3.6 (ALL REQUIRED PASS). Changelog 1222.
5. Task Board (SQLite) -- commit 8b2a5d8. services/api/taskboard.py replaces the
   in-memory jobs dict + jobs.jsonl; /agent/run records into it; GET /jobs list.
   taskboard 15/15. Handoff 1236.
6. Per-profile Chroma (OFF default) -- commit 04e96a6. RAG_PER_PROFILE routes
   memory_add/query to mem_<profile> via _get_collection. Handoff 1243.
7. Topic routing (OFF default) -- commit 2911a51. classify_topic + resolve_topic;
   resolved topic drives thinking/sampling/RAG. Handoff 1613.
   Then: offline suite 56/56 across the whole batch (commit 0923eef).
8. T2.4 --jinja messages migration (OFF default) -- commit a41138c.
   PERSONA_USE_MESSAGES; persona_generate() helper both endpoints call;
   query_llama_messages + build_persona_messages; server reasoning_content preferred,
   split_reasoning fallback. Handoff 1635.
   Then (UNCOMMITTED): exit_gate_live.py extended with adaptive [messages] +
   [per-profile] sections; this handoff.

## Phase 1 status (roadmap)

- [x] Exit Gate PROVEN (Qwen3.6, changelog 1222).
- [x] T2.1 sampling presets, [x] T2.2 gate, [x] T2.3 preserve, [x] topic routing.
- [~] Task Board, [~] per-profile Chroma, [~] T2.4 messages -- all CODE DONE +
  offline-green; each has a LIVE smoke remaining (see below).
- [ ] M6 single-model migration confirmation (live) -- then the Hermes H-track
  unblocks.

## Validation owed (all LIVE, all in one command)

`tests/exit_gate_live.py` is now adaptive: it reads /health and validates whichever
flags are on, skipping the rest with a note. Run order:

1. Offline suite (proves wiring): `.\portable\python\python.exe tests\test_api_offline.py`
   -- expect ~64/64 ALL PASS.
2. Default live (stack up): `.\portable\python\python.exe tests\exit_gate_live.py`
   -- re-confirms the Exit Gate; [messages] + [per-profile] print SKIP.
3. T2.4 messages: restart with `PERSONA_USE_MESSAGES=1` (--jinja is launcher default;
   ensure --reasoning-format deepseek), re-run the script -- the [messages] section
   asserts reasoning comes from the server's reasoning_content and text is
   <think>-free.
4. Per-profile: restart with `RAG_PER_PROFILE=1` (+ RAG_ENABLED), re-run -- the
   [per-profile] section confirms mem_alice/mem_bob collections appear.
5. Task Board live smoke (NOT in the script -- /agent/run mutates the repo via
   taskman2, unsafe to auto-run): POST a tiny job to /agent/run, then GET /jobs and
   /jobs/{task_id}; confirm the run records with a terminal status and /health
   task_store.count increments.

If all green: flip Task Board, per-profile, and T2.4 roadmap items to [x], and decide
whether to retire the post-hoc sanitizer on the messages path (the T2.4 payoff).

## Open / watch

- (low, CONFIRM) live `n_ctx=4096` x4 slots vs documented PERSONA_CTX=32768 -- confirm
  run/config.toml (possible intentional 16 GB VRAM fit).
- (info) Qwen3.6 MTP speculative-decoding checkpoint churn under parallel prompts.
- Per-profile Chroma migration story (existing global_memory rows are not moved when
  RAG_PER_PROFILE flips on) -- a one-time splitter is a follow-up.
- (low) defaults are all OFF; turning on topic routing / gate / per-profile / messages
  are independent, deliberate switches.

## Gotchas / notes (environment)

- Windows-authoritative. The Linux sandbox mount of D:\Projects is stale/truncating
  (this session it truncated server.py at ~1000 lines as the file grew, and corrupts
  the git index). Validate via the Read tool / segment-parse; run git + live checks
  Windows-side. Codified in AGENTS.md.
- Commit messages: `git commit -F <gitignored .log file>`, never `-F-` (interactive
  PowerShell does not pipe a pasted message to stdin -> silent no-op, push says
  "Everything up-to-date").
- All behavior-changing features are default-off; committing them is safe and changes
  nothing at runtime until each flag/env is set.

## Uncommitted at this handoff -- commit these

- tests/exit_gate_live.py (adaptive [messages] + [per-profile] sections)
- archive/handoffs/handoff_persona_20260607_1640.md (this file)
- changelog.md / todo.md (the entry + stamp for this handoff)
