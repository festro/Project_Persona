# Handoff -- Project_Persona

Date/time: 2026-06-18 2245 PDT
Author: Claude (Claude Code, native WSL session, with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Continues from: handoff_persona_20260618_2133.md.
To resume: "continue from handoff_persona_20260618_2245.md".

================================================================================
0. READ-ME FIRST (orientation)
================================================================================

- Local-first portable AI-companion stack: one llama-server (:8090) + a FastAPI
  companion API (:8000), driven by the cross-platform stdlib launcher manage.py.
  roadmap.md = status source of truth, knowledge.md = scope/architecture,
  changelog.md = append-only history, todo.md = short-term, docs/ = design notes.
- THIS checkout is the WSL clone ~/Git/Project_Persona = /home/festro33/Git/
  Project_Persona. It has NO .git -- the D:\ repo is the git gateway (per WORKFLOW.md).
  So this session did EDIT/RUN/TEST only; ALL commits are owed to Brandon (D:\ side).
- Interpreter here: the repo venv env/bin/python (CPython 3.12.3) has the API deps
  (fastapi 0.136.3, chromadb 0.6.3, fastembed, huggingface_hub). The system python3
  does NOT. manage.py self-locates env/bin/python for the API and
  llama_cpp/build/bin/llama-server (b9620, CPU build) for serving, so it can be invoked
  with either interpreter; this session used env/bin/python for everything.
- This host = Daemonic-PC (host_tag daemonic-pc). On Linux the effective config merges
  [base]+[runtime]+[linux]+config.daemonic-pc.toml -> Qwen2.5-7B-Instruct-Q4_K_M.gguf,
  CPU (GPU_LAYERS=0), PERSONA_PARALLEL=1, ctx 32768. WSL is CPU-only (no GPU).

================================================================================
1. TL;DR -- WHAT THIS SESSION DID
================================================================================

Goal: advance the phase ladder autonomously, up to but not into Phase 9; finish
hardware-free Phase 0.5 work on the two primary surfaces (Windows x64 + AMD Linux
via WSL). Result:

1. PHASE 0.5 LOCKED GREEN. Ran the missing AMD-Linux-via-WSL Exit-Gate check: a clean
   standalone manage.py lifecycle pass in this clone. Both Exit-Gate surface checks are
   now green -> Phase 0.5 [x].
2. T1 SAFE-CONFIG GATE REGRESSION found + fixed. Hermes' v28 schema migration (H1)
   had silently broken the project-side safe-config gate; restored it.
3. PHASE 10 ITEM 10.0 -> [x]. Offline regression suite green on Linux x64 (this WSL);
   Windows x64 was already green. (Offline portion only; rest of Phase 10 needs Phase 9.)
4. Reconciliation clean; docs updated (roadmap/changelog/todo); this handoff.

Everything is LOCAL + UNCOMMITTED (no git here). No pushes.

================================================================================
2. RECONCILIATION RESULT (reported to Brandon at session start)
================================================================================

- Git: no .git in this WSL clone (matches the handoff). -> edit/run/test only.
- py_compile manage.py: OK (env/bin/python 3.12.3).
- tests/run_all_offline.py: 5/5 suites PASS (test_api_offline, test_hermes_bridge,
  test_manage_pid, test_provision_fetch, test_provision_match).
- Stale run/persona.pid (7372) + run/api.pid (14032): both DEAD (ps showed nothing
  live); harmless, handled by resolve_live_pid. They were overwritten by the up/down
  cycle and removed on down -- run/ is now clean.
- No discrepancies blocking work. (The one surprise -- the T1 gate failure -- was
  resolvable; see section 3B.)

================================================================================
3. WHAT WAS DONE -- DETAIL
================================================================================

--- 3A. Phase 0.5 GREEN: standalone WSL/AMD-Linux lifecycle pass ---
Ran, in this clone, with env/bin/python:
  status  -> down state shown, stale pidfiles reported (not fatal).
  doctor  -> Filesystem/interpreters/binary/profile all OK; accel = CPU; T1 gate PASS
             (after the 3B fix).
  up      -> llama-server (Qwen2.5-7B, CPU) pid + FastAPI pid; both /health responding.
             API /health: status ok, embedder_ok=true (fastembed), chroma_ok=true.
  test health -> persona + API /health OK.
  /chat   -> POST {"text": "...", "topic":"chat", "debug":true} returned a real persona
             reply with sampling_preset=no_think. Serves /chat through the one entrypoint.
  down    -> clean: api + persona stopped, no orphans, :8090/:8000 free, pidfiles removed.
No bash used for any of it. This is the AMD-Linux-via-WSL Exit-Gate check, previously
[~]; now [x]. With Windows x64 already [x] (2026-06-07), Phase 0.5 LOCKS GREEN per the
roadmap's own lock rule.

--- 3B. T1 safe-config gate regression: auxiliary.*.provider auto->main ---
doctor's T1 gate FAILED on first run: 8 auxiliary tasks in persona/profiles/default/
config.yaml (skills_hub, approval, mcp, title_generation, triage_specifier,
kanban_decomposer, profile_describer, curator) had provider=auto. The project-side
validator manage.validate_safe_config requires auxiliary.*.provider=main (route ALL
auxiliary inference to the local main model; egress containment).
ROOT CAUSE: Hermes' schema 0->28 migration (H1, 2026-06-12) added those new auxiliary
tasks with its default provider=auto. H1 was validated with Hermes' own
`hermes config check` (passed) -- NOT the project's doctor T1 gate -- so the regression
went unnoticed (T1 last ran green 2026-06-04, before the migration).
FIX: set the 8 to provider=main (a tightening; with providers:{} empty + no API keys,
auto would resolve to main anyway). doctor T1 gate green again; YAML re-parses fine.
This is the project-side gate; the documented design intent (knowledge.md "all auxiliary
tasks routed to the local main model") is exactly this. config.yaml is git-tracked.
FOLLOW-UP (note only, not done): a normalizer (doctor --fix, or init_profiles re-pin)
that re-asserts auxiliary.*.provider=main after any future Hermes schema migration, so
this can't silently regress again.

--- 3C. Phase 10 Item 10.0: offline suite green on Linux x64 ---
tests/run_all_offline.py 5/5 PASS via env/bin/python (3.12.3) in this WSL clone =
the Linux x64 surface. Windows x64 was already green (2026-06-14). Both primary surfaces
green -> Item 10.0 [~] -> [x]. JUDGMENT-CALL NOTE: Phase 10 is past Phase 9, but 10.0 is
the hardware-free offline-runner check the roadmap explicitly lets run on any host; I
flipped only that one (decision-free, factual) and touched no other Phase 10 item.
Revert if you'd rather keep it [~] until a non-WSL Linux runs it.

--- 3D. Docs updated (this clone, uncommitted) ---
- roadmap.md: Phase 0.5 -> [x] GREEN (+ GREEN note, lock line, Current position);
  launcher Item -> [x] + WSL-pass tail; AMD-Linux Exit-Gate check -> [x]; egress +
  installer/doctor-parity Items annotated NON-GATING + design-gated; Phase 8 T1 note
  (the regression+fix); Phase 10 Item 10.0 -> [x]; stamp bumped.
- changelog.md: 3 new entries on top (2231 Phase 0.5 GREEN, 2225 T1 restore, 2215 10.0).
- todo.md: stamp + "Just finished" (4 bullets) + "Next up" (commit owed + the 4 design
  decisions + hardware/Phase-9 deferrals).
- This handoff.

================================================================================
4. VERIFICATION STATUS
================================================================================

Verified (this session, on WSL):
- py_compile manage.py OK.
- tests/run_all_offline.py 5/5 (re-run at end of session, post-edits).
- doctor T1 gate: safe_config=pass.
- Full live lifecycle up/down with real /chat reply; clean teardown; run/ clean.

Owed (Brandon / D:\ side):
- COMMIT the working tree (no git here). Files: persona/profiles/default/config.yaml,
  roadmap.md, changelog.md, todo.md, this handoff -- PLUS the still-uncommitted prior
  batch from handoff _2133 (P4 + vision wiring + roadmap re-scope). Local only; push is
  milestone-only.
- (Optional) re-confirm on Windows x64 that nothing regressed (offline suite + doctor).
  Nothing this session touched Windows-specific paths; config.yaml is shared.

================================================================================
5. NEXT STEPS / OPEN DECISIONS (need Brandon)
================================================================================

The autonomous, hardware-free, decision-free 0-8 work is done. What remains needs a
decision or hardware:

DESIGN DECISIONS (the reason this session stopped here):
  1. Per-OS egress baseline (Phase 0.5 Item + Phase 8 runtime egress): WireGuard mesh +
     host firewall, netns/iptables as a Linux bonus. Pick the shape before building.
  2. Cross-OS installer/doctor parity: setup_native_stack.sh still writes the legacy
     run/llama-servers.env while run/config.toml is the committed source of truth. KEEP
     the env fallback or DROP it? This gates the installer/doctor-parity item.
  3. (minor) provisioner --tier: needs a tier taxonomy first. The playbook's tiers are
     comments only; the "Tier 1 / 0" group is combined and a 14B sits under "SBC/Pi", so
     the boundaries are ambiguous. Deferred rather than guess. Decide the tier->model
     mapping and it's a quick add (tier field in run/model_playbook.toml + a --tier
     filter in manage._filter_playbook, with offline tests).
  4. (minor) KV-aware ctx sizing: the matcher's 0.85*budget step-down is crude. A real KV
     estimate needs per-model metadata (GQA ratio, n_layers, cache type) or HW
     measurement -- do NOT invent constants (your standing instruction). Flagged, parked.

HARDWARE / Phase 9 (out of this scope, deferred by you):
  - H2d EVO-X2 Exit Gate (35B + GPU + egress-off -> ok+summary).
  - EVO-X2-native (Linux + Vulkan GPU) lifecycle parity, Linux ARM64, non-Vulkan accel
    selection proof -- relocated to Phase 9 Item 9.0 / 9.x.
  - The mesh (Phase 9.1-9.5).

LARGER 0-8 WORK AVAILABLE (not started; not "hardening", a new feature -- your call):
  - Phase 2 (frontend/UX): OpenWebUI thin client, conversations.db history, Item 2a
    ChromaDB->Qdrant migration. Sizeable; left for an explicit go-ahead.

================================================================================
6. KEY FILES / POINTERS
================================================================================

- Launcher: manage.py (host_tag/load_config, resolve_model, start_llama [+_mmproj_args],
  start_api, _maybe_first_run, cmd_up/down/status/doctor/provision/test, validate_safe_
  config at ~756, _filter_playbook at ~1342).
- Safe-config: persona/profiles/default/config.yaml (auxiliary.*.provider now all main).
- Provisioner: scripts/provision_match.py (matcher), scripts/provision_fetch.py (P3/P4),
  run/model_playbook.toml (catalog; tiers are comments only -- see decision 3).
- Config: run/config.toml ([base]/[runtime]/[linux]/[windows]) + run/config.daemonic-pc.toml
  (CPU-WSL 7B exception).
- Tests: tests/run_all_offline.py (runner) + tests/test_*.py.
- Status/scope/history: roadmap.md, knowledge.md, changelog.md, todo.md.

================================================================================
7. GOTCHAS CARRIED FORWARD
================================================================================

- No git in this WSL clone: commit on the D:\ side. Edit/run/test only here.
- Use env/bin/python (3.12.3) on this box; system python3 lacks the API deps. On Windows
  use .\portable\python\python.exe.
- WSL here is CPU-only (no GPU; ~slow for big models). The 7B on CPU is fine for a
  lifecycle smoke; the 35B + GPU is EVO-X2 (Phase 9).
- The safe-config T1 gate can regress whenever Hermes migrates config.yaml's schema and
  adds auxiliary tasks with provider!=main. Re-run `manage.py doctor` after any Hermes
  upgrade; re-pin to main if it flags (see 3B; consider the normalizer follow-up).
- manage.py up SKIPS a live llama-server; reliable liveness = /health + a `ps ... gguf`
  grep. After a model swap, down/kill first.
- Stamping: trust the environment's "today" (2026-06-18) for dates; this box's clock read
  PDT and agreed.
