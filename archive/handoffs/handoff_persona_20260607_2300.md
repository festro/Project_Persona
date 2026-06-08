# Handoff -- Project_Persona

Date/time: 2026-06-07 2300 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Status of repo: working tree has UNCOMMITTED local changes (this session). Nothing
pushed -- per the new rule, pushes are reserved for milestones (phase completions /
big pivots); local commits as you go.

================================================================================
WHERE WE ARE
================================================================================

Phase 1 is functionally done; its formal close (M6) was DEFERRED this session while
we (1) reconciled the docs, (2) fixed a gitignore gap, and (3) built the first two
phases of a new model auto-provisioner (Phase 0.5). The single-model identity is now
settled and consistent across every doc: Qwen3.6-35B-A3B-UD-Q5_K_XL on EVERY host.

Active head of queue remains M6 (the Phase 1 close). The provisioner work is a
Phase 0.5 track that ran ahead because Brandon prioritized it.

================================================================================
WHAT HAPPENED THIS SESSION (3 threads)
================================================================================

1. DOC RECONCILIATION (changelog 1827; audit docs/doc_audit_conflicts_20260607_1827.md)
   - MODEL IDENTITY settled: single model Qwen3.6-35B-A3B-UD-Q5_K_XL on ALL hosts,
     EVO-X2 included. Instruct-2507 is the DROPPED no-thinking fallback (the 2507
     release split off the thinking toggle). T0.1 (arch) + T0.2 (tool-calling) gates
     both passed -> Qwen3.6 confirmed; fallback not in use. The old "two flows by
     design" wording was transitional host-state, now corrected everywhere.
   - Obsolete-entry sweep: retired HANDOFF.md/.html "open first" pointers ->
     todo/roadmap/knowledge/changelog; README "uses Qdrant"->ChromaDB now/Qdrant
     Phase 2a; OpenWebUI "Running"->dormant; roadmap "Unix-socket IPC"->NATS;
     todo Phase 9->8 (Hermes); knowledge stale Phase 1 "Remaining" list; py314
     3.12->3.11.9; config.toml-primary narrative; stamps bumped.

2. GITIGNORE + CONTEXT (changelog 1827)
   - .gitignore `tools/` (blanket) -> `tools/*.json`. The taskman orchestration
     SCRIPTS (tools/taskman.py, taskman2.py) that /agent/run shells out to were
     being ignored; job artifacts actually go to run/jobs/ (already ignored).
   - Context-size "drift" was a non-issue: run/config.toml is per-OS (32768 linux /
     16384 windows, PARALLEL=4); live n_ctx=4096/slot = the windows 16384 fit.

3. MODEL PROVISIONER -- new Phase 0.5 feature (design doc:
   docs/model_provisioner_design_20260607_2158.md; changelog 2200 + 2254)
   - GOAL: first run profiles the host, matches a playbook, downloads the best-fit
     model, writes config.toml. Range: Raspberry-Pi/8 GB CPU floor -> 96 GB unified.
   - LICENSING (Brandon): default catalog = OSI-open / AGPL-compatible only
     (Apache-2.0/MIT, ungated). Gemma/Llama/Qwen2.5-VL-3B&72B excluded from defaults.
   - VISION (Brandon): camera-gated. VISION_ENABLED on iff a camera is detected,
     else off with opt-in; vision-capable model + mmproj fetched regardless.
   - P1 DONE (manage.py): detect_vram_mb() [vulkaninfo DEVICE_LOCAL heap, x-vendor;
     nvidia-smi/sysfs/registry fallbacks] + detect_memory_model() + detect_camera();
     detect_host() emits vram_mb/memory_model/camera_present. NPU classify already
     existed (Intel/OpenVINO usable; Hailo/Gaudi detect-but-never-select).
     VALIDATED LIVE on the RX 9060 XT: vram_mb=16304, memory_model=discrete.
   - P2 DONE: run/model_playbook.toml (10 Apache-2.0 models, quant ladders, vision,
     ranks) + scripts/provision_match.py (budget=max(RAM-reserve,VRAM-reserve);
     unified uses RAM; largest fitting quant; rank+vision/camera scoring) +
     tests/test_provision_match.py (7/7 PASS). The matcher picks qwen3.6-35b on the
     RX 9060 XT -- matching the live config.

================================================================================
VALIDATION STATUS
================================================================================

DONE (live or offline):
- Profiler P1 live on RX 9060 XT (vram_mb=16304, memory_model=discrete).
- Matcher P2 offline 7/7 (incl. Brandon's host, EVO unified, Pi, 4GB->none).
- detect_camera() compiles + sandbox-checked (no camera -> False).

PENDING:
- [ ] Windows-side `git ls-files tools/` -- if empty, `git add tools/taskman.py
      tools/taskman2.py` (else fresh clones break /agent/run).
- [ ] `manage.py capabilities` on the host to eyeball the new camera_present field.
- [ ] EVO-X2 `capabilities` run to confirm memory_model "unified" on Strix Halo.
- [ ] (optional) run tests/test_provision_match.py on the host:
      `.\portable\python\python.exe tests\test_provision_match.py` (expect 7/7).

================================================================================
DECISIONS
================================================================================

RESOLVED this session:
- Canonical model = single Qwen3.6-35B-A3B-UD-Q5_K_XL everywhere.
- Provisioner catalog = OSI-open / AGPL-compatible only.
- Vision default = camera-gated.
- Push cadence = milestones only (local commits as you go).

STILL OPEN (for P3):
- May `provision` OVERWRITE an existing PERSONA_MODEL, or only fill when unset?
- Confirm the committed Qwen3.6 ships a usable vision mmproj for Tier 4.
- Re-verify playbook repo IDs / filenames / quant sizes vs real HF pages (current
  values are 2026-06-07 estimates) before P3 download code depends on them.

================================================================================
NEXT (in order) -- see todo.md for the live list
================================================================================

1. M6 single-model migration confirmation (LIVE) -- the Phase 1 close / head.
   Runbook: docs/m6_confirmation_runbook_20260607_1827.md (the owed piece is an
   M2b sustained-load run on the Qwen3.6 build).
2. T2.4 payoff: retire the post-hoc sanitizer on the messages path.
3. EVO-X2 single-model convergence -- gated on bumping EVO-X2 llama.cpp to a
   Qwen3.6-capable build FIRST, THEN swap run/config.toml [linux] model. Do not
   interleave with the Phase 1 close.
4. Provisioner P3 (huggingface_hub downloader + license/disk preflight + config
   wiring) then P4 (manage.py `provision` + first-run hook in cmd_up). Refine the
   KV-aware ctx sizing (tight-budget step-down picks 8192 vs the working 16384).

================================================================================
FILES TOUCHED THIS SESSION (for the local commit)
================================================================================

Modified: knowledge.md, roadmap.md, todo.md, changelog.md, README.md,
  README_models_hardware.md, .gitignore, manage.py
New: docs/doc_audit_conflicts_20260607_1827.md,
  docs/m6_confirmation_runbook_20260607_1827.md,
  docs/model_provisioner_design_20260607_2158.md,
  run/model_playbook.toml, scripts/provision_match.py,
  tests/test_provision_match.py,
  archive/handoffs/handoff_persona_20260607_2300.md
Gitignored (won't appear): commit_msg_phase1_live_20260607_1827.log (*.log)

COMMIT (Windows-side portable git; LOCAL ONLY, no push):
  git add -A
  git commit -m "docs reconcile (single-model Qwen3.6) + model provisioner P1/P2 + gitignore tools fix"
  # verify tools scripts are tracked:
  git ls-files tools/    # expect taskman.py + taskman2.py; if empty, git add them

================================================================================
POINTERS
================================================================================
- Provisioner design: docs/model_provisioner_design_20260607_2158.md
- Doc audit: docs/doc_audit_conflicts_20260607_1827.md
- M6 runbook: docs/m6_confirmation_runbook_20260607_1827.md
- Matcher: scripts/provision_match.py ; catalog: run/model_playbook.toml ;
  tests: tests/test_provision_match.py
- Architecture / scope: knowledge.md ; phase status: roadmap.md ; history: changelog.md
