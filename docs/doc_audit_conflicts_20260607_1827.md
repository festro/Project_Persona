# Doc Audit -- obsolete / conflicting entries

Prepared: 2026-06-07 1827 PDT by Claude
Scope: knowledge.md, roadmap.md, todo.md, README.md, README_models_hardware.md,
AGENTS.md. Goal: surface entries that contradict current reality or each other so
they are not picked back up. NOTHING edited -- decisions are Brandon's. ASCII only.

Severity: [P1] could cause wrong action (deploy/build) ; [P2] contradiction that
misleads ; [P3] stale label / stamp / pointer.

================================================================================
P1 -- MODEL IDENTITY (the big one)
================================================================================

The docs disagree on what the canonical model IS. A reader following knowledge.md
would deploy Qwen3-30B-A3B-Instruct-2507 -- which has NO thinking mode -- yet every
T2.x feature (thinking gate, preserve_thinking, --jinja reasoning_content) and all
of this week's live validation runs on Qwen3.6-35B-A3B (thinking-capable).

Evidence:
- knowledge.md L93: "One Qwen3-30B-A3B-class MoE model" (30B; no thinking mention).
- knowledge.md L172: unified config "verified working on EVO-X2: Qwen3-30B-A3B-
  Instruct-2507 Q5_K_M".
- knowledge.md L217: PERSONA_MODEL=Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf.
- roadmap.md L42/L59: "T0-T4 = Qwen3.6 model-swap"; "T0 model swap to Qwen3.6
  committed (T0.1 2026-05-18)".
- roadmap.md Current position L47-48: "Qwen3.6 llama-server now stands up LIVE".
- README_models_hardware.md L57: "Recommended model: Qwen3.6-35B-A3B".
- todo.md "Notes for next editor": "Two model files / two flows by design: native
  EVO-X2 uses Instruct-2507; the Windows portable flow uses Qwen3.6."

Conflict: knowledge.md presents Instruct-2507 as the single canonical model;
roadmap/README/todo treat Qwen3.6-35B-A3B as the committed model. The deliberate
"two flows" arrangement (EVO=Instruct-2507, Windows=Qwen3.6) exists ONLY in todo.md
and is absent from knowledge.md.

DECISION NEEDED: Is the canonical model (a) Qwen3.6-35B-A3B everywhere, or (b) a
deliberate two-host split? Either way knowledge.md "Stable architectural decisions"
+ Operational notes + the env block must be reconciled to match, and the 30B-class
vs 35B size wording fixed.

Related stale gating (same theme):
- README_models_hardware.md L70: "The exact model lock is gated behind ... T0.1 --
  Until that test passes, the fallback is Qwen3-30B-A3B-Instruct-2507." T0.1 PASSED
  2026-05-18 (roadmap L59). [P1]
- README_models_hardware.md L134: "Tested model: Qwen3-30B-A3B Q5_K_M (target:
  Qwen3.6-35B-A3B ... pending T0.1)" -- same stale "pending T0.1". [P2]

================================================================================
P1 -- RETIRED-DOC POINTERS (new contributor sent to files that no longer exist)
================================================================================

The repo moved to the knowledge/todo/roadmap/changelog convention; HANDOFF.md /
HANDOFF.html were retired to archive/pre-workflow/ (knowledge.md L315-316). README
still tells readers to open them first.

- README.md L77-78: "HANDOFF.md -- open this first when resuming work";
  "HANDOFF.html". Both retired. [P1]
- README.md L87: Roadmap section: "Current state ... live in HANDOFF.md". [P2]
- README_models_hardware.md L42, L70, L139: bare "HANDOFF.md" / "HANDOFF_2026-05-09
  ..." references (the dated one is under archive/handoffs/). [P3]

================================================================================
P2 -- STATUS CONTRADICTIONS
================================================================================

- README.md L47: "Project_Persona uses Qdrant for typed semantic memory" (present
  tense). Reality: ChromaDB now; Qdrant is PLANNED Phase 2a (README L64/L95,
  roadmap Phase 2a, knowledge L137). Internal contradiction in the same file.
- README.md L66 + L92: OpenWebUI "Running" / "locked as primary". Reality: DORMANT;
  Phase 2 (frontend) NOT STARTED (knowledge L64/L170, roadmap L228).
- README.md L62: Model row status "Migrating to single-model topology". Reality:
  single-model topology is live; T0 swap committed.
- knowledge.md L256-258 (Architecture roadmap, Phase 1): "Remaining: per-profile
  Chroma, Task Board replacing the jobs dict, topic routing policy." All THREE are
  [x] done in roadmap (L190/L199/L205). Stale.
- roadmap.md Current position L49-51: "Remaining Phase 1 proof: live /chat persona
  replies + streaming + per-topic sampling ... embedder_ok/chroma_ok on /health."
  PROVEN 2026-06-07 (roadmap L221, changelog 1222). Only M6 remains.

================================================================================
P2 -- DECOMMISSIONED TECH STILL REFERENCED
================================================================================

- roadmap.md L369-371 (Cross-cutting components): "Unix-socket IPC" and "IPC ->
  Phase 3". The IPC decision RULED OUT Unix sockets (no asyncio AF_UNIX on Windows
  Proactor loop) and chose NATS+JetStream (roadmap L125-130, knowledge L139-145).
  "Unix-socket IPC" is a stale label.
- roadmap.md L363 + todo.md "Blocked" #36: "Qwen3.5/3.6 maturity re-evaluation
  after ~2026-08" listed as deferred -- but Qwen3.6 is ALREADY deployed (build
  e7bd3b3). Clarify whether this means a future 3.5-vs-3.6 re-eval or is obsolete.

================================================================================
P2 -- PHASE-NUMBER REFERENCE ERRORS
================================================================================

- todo.md "Blocked/waiting" + M6 note: "See roadmap Phase 1 / Phase 9" for the
  Hermes H-track. Hermes is Phase 8; Phase 9 is DELETED (roadmap L300/L322,
  knowledge L286). Should read Phase 8.

================================================================================
P2 -- OBSOLETE MILESTONE DEFINITION (M6)
================================================================================

- Original M6 (archive/handoffs/HANDOFF_2026-05-09_0250, item M6): "Replace serial
  in-band SCIENTIST call with asyncio.gather parallel dispatch." Obsolete -- the
  scientist/multi-server split is retired (knowledge L57-60), so there is no
  scientist call to parallelize.
- roadmap.md L189 reframes M6 as a confirmation milestone but gives NO acceptance
  criteria. Underspecified. (See docs/m6_confirmation_runbook_20260607_1827.md for
  the proposed criteria.)

================================================================================
P3 -- CONFIG-SOURCE DRIFT (config.toml vs config.env)
================================================================================

- knowledge.md L179-187: "Runtime tunables live in run/llama-servers.env ... and
  scripts/start_api.sh ... Consolidation into run/config.env is underway." Predates
  the TOML migration -- run/config.toml is now the primary source read via tomllib
  (knowledge L35, changelog 2028, manage.py). The L179 narrative is stale.
- README_models_hardware.md L92-99: instructs editing run/config.env. config.toml
  is now primary (lower priority -- onboarding doc, env still has fallback).

================================================================================
P3 -- STAMP / CONVENTION DRIFT
================================================================================

- knowledge.md L6: "Last updated: 2026-06-06 2105 PDT" but the file contains
  2026-06-07 content (Task Board L78/82, per-profile L130, T2.2 L188, T2.3 L193,
  topic routing L199, T2.4 L205). Stamp not bumped.
- roadmap.md L8: "Last updated: 2026-06-07 1110 PDT" but Phase 1 items cite 1746 /
  1752 / 1758 events. Stamp not bumped.

================================================================================
P3 -- MINOR / VERIFY
================================================================================

- Context size: PERSONA_CTX=32768 (knowledge L218) vs "262K native context"
  (README_models L63) vs observed live n_ctx=4096/slot ~= 16384 total (todo
  housekeeping). Three numbers; reconcile against run/config.toml. (Already a todo
  fix-it.)
- knowledge.md L75: "/agent/run shells out to tools/taskman2.py", but tools/ is
  gitignored (.gitignore L89) -- the orchestration entrypoint is not tracked.
  Intentional or a gap? Verify.
- README.md uses emoji + has no stamp; it predates the ASCII/stamp convention.
  External-facing, so emoji may be acceptable -- but its content is the most stale
  in the repo (see P1/P2 above) and a refresh pass is warranted.

================================================================================
SUGGESTED ORDER
================================================================================

1. Resolve P1 model identity (one decision) -> reconcile knowledge.md + the two
   READMEs to match.
2. Fix P1 retired-doc pointers in README (HANDOFF.md -> knowledge/todo/roadmap).
3. Sweep P2 status contradictions + the Unix-socket label + the Phase 9->8 ref.
4. Mechanical P3 (stamps, config-source narrative) -- low-risk, batchable.
