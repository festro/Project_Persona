# Project_Persona -- Changelog

Reverse-chronological history. New entries go at the TOP.

Conventions:
- Header format: `## YYYY-MM-DD HHMM UTC -- short summary (<author>)`
- One bullet per change, past tense, terse.
- File / line references where useful.
- ASCII only (see `WORKFLOW.md`).
- Append-only. To correct a prior entry, add a new entry on top; do not
  edit history.
- Entries reconstructed from the pre-convention File Change Tracker keep their
  recorded date; HHMM is shown only where the original recorded it.

---

## 2026-06-03 0301 UTC -- Workflow-compliance restructure (Claude)

- Split the pre-convention `KNOWLEDGE.md` (1022 lines) and living `HANDOFF.md`
  into the three-file convention: `knowledge.md`, `todo.md`, `changelog.md`.
- Converted all content to ASCII (removed em-dashes, smart quotes, box-drawing
  `--` rules, and status emoji); removed inline `#` comments from config code
  blocks per the executable-code-only rule.
- Added root `WORKFLOW.md` one-line pointer.
- Archived originals to `archive/pre-workflow/` (KNOWLEDGE.md, HANDOFF.md,
  HANDOFF.html). README.md and README_models_hardware.md left in place
  (external-facing, separate concern).
- Recorded the unresolved KNOWLEDGE.md-vs-HANDOFF.md current-state discrepancy
  as the top item in `todo.md` rather than picking a winner.
- Git index found corrupt with a stale `.git/index.lock` that could not be
  removed from the sandbox (mount blocks writes under `.git/`). Repair from a
  Windows shell at the repo root: remove `.git/index.lock`, remove `.git/index`,
  run `git reset` to rebuild the index from HEAD, then `git status` to confirm
  the moved/created docs, then stage and commit. No git history was lost; only
  the working index needs rebuilding.

## 2026-05-23 0918 UTC -- M2b sustained-load baseline + handoff (Brandon + Claude)

- Revived llama-server (pid 1810898, :8090) and API (pid 1813299) on EVO-X2;
  /health returned the M5 shape.
- 30-min M2b run at concurrency 4 on unified Qwen3-30B-A3B Q5_K_M: 2066/2066 OK,
  60/60 health polls OK, lat_p50 4.358s / p95 4.553s / max 4.763s, gen_tps_mean
  28.26 per slot (~113 tok/s aggregate), per-minute throughput flat 27.78-28.79.
- Stability ghost did NOT recur. Peak-load thermal not captured (only +1h23m
  post-test idle sample). Report: `logs/m2b_2026-05-23_0723.json`.
- See `archive/handoffs/HANDOFF_2026-05-23_0918_docs-drift-m2b-baseline.md`.

## 2026-05-22 1523 UTC -- Documentation drift cleanup (Brandon + Claude)

- System State unified-llama row rewritten for :8090 with rationale + stability
  follow-up; OpenWebUI corrected to "scaffolded, not deployed" after EVO-X2
  diagnostic (no listener on :3000, empty data dir, venv only in legacy path).
- Port references 8080 -> 8090 across inference table, child-process diagram,
  T1.2, H1.2, M12. Runtime Configuration block rewritten to unified topology;
  legacy dual-server vars collapsed.
- Corrected the 05-19/20 framing: the :8080 squatter was an unrelated co-tenant
  container, not OpenWebUI. Flagged llama-server then down on EVO-X2.

## 2026-05-20 0102 UTC -- EVO-X2 M5 commit + push (Brandon + Claude)

- Pulled the three 05-19 in-flight EVO-X2 patches to Windows, verified via
  tar-over-ssh diff. Caught a mode flip on `load_test_m2b.py` (0644 -> 0755) and
  two pre-existing oddities in `start_api.sh` (dead MEMORY_DISTILL_ENABLED
  export; lingering SCIENTIST_* env names working via back-compat).
- Commit 61790de landed the four file changes; 8177b20 archived both dated
  handoffs. EVO-X2 fast-forwarded to origin/main. M5 declared done.
- See `archive/handoffs/HANDOFF_2026-05-20_0102_m5-validated-evox2.md`.

## 2026-05-19 1130 UTC -- EVO-X2 M5 validation (Brandon + Claude)

- Three sed-patches on EVO-X2: PERSONA_PORT 8080 -> 8090; `start_api.sh` and
  `stop_api.sh` AI_ROOT default flipped from the quarantined `~/Live/AIStack`
  path to `~/Git/Project_Persona/`.
- llama-server died once with no graceful-shutdown signature; root cause
  unidentified (stability ghost). Suspect list carried forward.
- See `archive/handoffs/HANDOFF_2026-05-19_1130_evox2-m5-validation.md`.

## 2026-05-17 1830 UTC -- Windows zero-install portable instance (Brandon + Claude)

- Two double-click `.bat` entry points at repo root. `windows_portable_setup.bat`
  resolves + extracts PortableGit, then hands off to portable bash;
  `scripts/portable_setup_win.sh` downloads the latest llama.cpp Windows-Vulkan
  binary and the Qwen3.6 GGUF (idempotent, resumable). `windows_portable_run.bat`
  prepends PortableGit to PATH for the session only. `.gitignore` adds
  `portable/`.
- See `archive/handoffs/HANDOFF_2026-05-17_1830_qwen36-windows-prototype.md`.

## 2026-05-17 1730 UTC -- M5 server.py single-model migration (Brandon + Claude)

- Removed SCIENTIST_URL/PORT; role differentiation moved from URL dispatch to
  the prompt layer. Env migration with back-compat: ASYNC_SCIENTIST_* ->
  ASYNC_REASONING_*, SCIENTIST_INBAND_* -> REASONING_INBAND_*.
- Added `thinking_prefix()` (/think vs /no_think by topic); `build_persona_prompt`
  gained `reasoning_notes` and `thinking_mode`. PERSONA_CONCURRENCY default 2 -> 4;
  `/v1/chat/completions` gated by `persona_sem`. `/health` reshaped.
- Persona loader switched to the 2-file Hermes naming (SOUL.md + .hermes.md),
  dropping persona.md/style.md/system_rules.md. Closed the Phase 1 "wire SOUL.md
  + .hermes.md" gap.
- See `archive/handoffs/HANDOFF_2026-05-17_1730_m5-server-py-migration.md`.

## 2026-05-17 1430 UTC -- Qwen-test canonicalize + M2b script (Brandon + Claude)

- Mirrored EVO-X2's 05-16 env + launcher rewrites onto Windows byte-identically.
- Fixed `scripts/status.sh` (AI_ROOT -> ~/Git/Project_Persona, names trimmed to
  ("persona"), scientist refs removed). Added `scripts/load_test_m2b.py`
  (asyncio + httpx sustained-load client). M3 + M4 marked done.
- See `archive/handoffs/HANDOFF_2026-05-17_1430_qwen-test-canonicalize.md`.

## 2026-05-17 -- Handoff layout cleanup (Brandon + Claude)

- Moved all seven dated `HANDOFF_*` files from repo root into
  `archive/handoffs/`; only the living `HANDOFF.md` + rendered `HANDOFF.html`
  stayed at root. Updated cross-references. (Time not recorded.)

## 2026-05-16 2337 UTC -- Qwen-test first boot (Brandon + Claude)

- Rewrote `run/llama-servers.env` + `scripts/start_llama_servers.sh` on EVO-X2
  for the unified Qwen3-30B-A3B-Instruct-2507 Q5_K_M topology: full GPU offload
  (49/49 on Vulkan0), 4 slots x 8192 ctx, q8_0 KV cache, Flash Attention, Hermes
  2 Pro template, ~63 tok/s gen / ~67 tok/s prompt eval.
- Repo reconciliation (stash/pull/pop), two commits (3910a37 profile rename,
  57dad37 docs). Moved the Qwen3 model into `~/Git/Project_Persona/models/`;
  quarantined the legacy `~/Live/AIStack/` workspace.
- See `archive/handoffs/HANDOFF_2026-05-16_2337_qwen-test-first-boot.md`.

## 2026-05-15 0827 UTC -- Compatibility re-eval, tiered T0-T4 (Brandon + Claude)

- Added the tiered compatibility re-eval action plan (T0 GO/NO-GO arch test, T1
  foundation, T2 core integration, T3 hardening, T4 deferred) alongside the
  Hermes (H) and single-model (M) blocks.
- Also this date (time not recorded): created the living `HANDOFF.md` +
  `HANDOFF.html` + `scripts/regen_handoff_html.sh`; ran a 12-action consolidation
  batch (archived cruft and AIP_* docs, rewrote README.md / persona/README.md /
  README_models_hardware.md / .gitignore, renamed profile files to SOUL.md /
  .hermes.md, corrected the `looks_degenerate()` claim).
- See `archive/handoffs/HANDOFF_2026-05-15_0827_compat-reeval-tiered.md`.

## 2026-05-14 -- Frontend lock, Hermes naming, M1/M2 progress (Brandon + Claude)

- M1 resolved: bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF Q5_K_M chosen.
  M2 split into M2a (Vulkan/RADV build verified, bf16=0 noted) and M2b
  (sustained-load, deferred).
- OpenWebUI locked as primary frontend (SillyTavern out of scope). Profile files
  renamed to Hermes naming (persona.md -> SOUL.md, system_rules.md -> .hermes.md,
  style.md retired); profile folder doubles as HERMES_HOME. (Time not recorded.)

## 2026-05-11 0038 UTC -- Hermes Agent adoption decision (Brandon + Claude)

- Adopted Hermes Agent (Nous Research, MIT) as the agent-work backbone; six
  brainstorm forks resolved. Deleted AG2 (Phase 2.5) and CrewAI (Phase 9);
  reshaped LangGraph (Phase 8) into Hermes integration. Extended the Task Board
  schema with Tenacity-style failure-semantics columns.
- Enumerated the network-egress risk surface (7 paths + Claude Code creds risk)
  with a safe-config recipe (Appendix A) and kernel-level containment (H1.6).
- See `archive/handoffs/HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md`.

## 2026-05-09 0950 UTC -- Single-model consolidation decision (Brandon + Claude)

- Decided to replace the multi-model topology (persona 8080 + reasoning 8081 +
  planned coder 8082) with a single Qwen3-30B-A3B Q5_K_M served from one
  llama.cpp instance with parallel slots and mode-switched prompts. Sequenced
  the M1-M12 migration. Cancelled the coder server.
- See `archive/handoffs/HANDOFF_2026-05-09_0950_single-model-migration.md`.

## Pre-convention baseline

The project began tracking state on 2026-04-05 in a single sprawling
`KNOWLEDGE.md` ("Knowledge & Task Tracker"): initial tracker created, Phases 2-8
spec'd, the Task Board system component added (schema, surfacing behavior,
difficulty/time_score, phase touchpoints), a license audit completed (component
table, model-exclusion policy, hardware tiers), and `README_models_hardware.md`
created. From 2026-05-09 onward that file accumulated dated decision and
session entries, and from 2026-05-15 a parallel living `HANDOFF.md` (+
`HANDOFF.html`) carried current-state. Both were the authoritative docs until
the 2026-06-03 restructure split them into this convention. The frozen originals
are preserved at `archive/pre-workflow/KNOWLEDGE.md`, `.../HANDOFF.md`, and
`.../HANDOFF.html`; dated frozen handoffs from this period live in
`archive/handoffs/`.
