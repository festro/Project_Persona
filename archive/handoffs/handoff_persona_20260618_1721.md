# Handoff -- Project_Persona

Date/time: 2026-06-18 1721 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Continues from handoff_persona_20260614_1655.md.
To resume: "continue from handoff_persona_20260618_1721.md".

UPDATE 1758: P3 was LIVE-CONFIRMED on Daemonic-PC (`provision --dry-run`: qwen3.6-35b
pick, weights present, per-host [windows] target, nothing written) and a ctx-preserve
safeguard was added (provision_fetch.resolve_ctx + config_kv(existing_ctx); cmd_provision
preserves an existing effective PERSONA_CTX over the matcher's conservative guess, which
had under-set ctx to 8192 on a 16384 host). Tests now 36/36. See changelog 1758. The
"OWED: Windows-side dry-run live-confirm" item below is now DONE.

Repo state:
- origin/main = aa145fa (unchanged this session).
- local main = 2eb8c94 + THIS SESSION'S WORK (provisioner P3 + docs), NOT yet committed.
  Commit it locally (mid-Phase-0.5); push rides the next milestone.
- git + file validation are Windows-side only; the Linux sandbox D:\ mount serves
  stale/truncated reads (re-confirmed this session -- a sandbox copy of manage.py came
  back garbled at line 1570). Do NOT git or py_compile D:\ files from the sandbox.

================================================================================
HEADLINE
================================================================================

Directive: "work our way up the phases." Lowest non-green phase = Phase 0.5
(cross-OS portability hardening). Within it, the first-run model provisioner was the
open, hardware-free code rung: P1 (profiler) + P2 (matcher) were already CODE DONE;
P3 (downloader + preflight + config wiring) was not. P3 is now CODE DONE.

Also: the carried "E" fix-it (capabilities llama_build=null vs doctor b9219) turned out
to be ALREADY FIXED + verified-live on 2026-06-07 (the `--version` probe was bumped to
30s + one retry in llama_version_info). Only a stale roadmap note remained; corrected.

================================================================================
DONE THIS SESSION
================================================================================

1. scripts/provision_fetch.py (NEW) -- provisioner P3, consumes a pick from
   scripts/provision_match.match():
   - disk_free_mb / preflight_disk: free space >= file size + 20% margin.
   - license_gate: Apache-2.0 / MIT / BSD-2/3 = ungated happy path (no token); a
     non-open license is allowed ONLY with an explicit HF_TOKEN (never auto-accept).
   - build_plan: base GGUF + matching mmproj when the model is vision; marks files
     already on disk; sums the MiB still to download.
   - download: huggingface_hub.hf_hub_download (resumable; network branch only),
     huggingface_hub imported lazily; verify_download is a light post-check on top of
     HF's own blob-hash verification.
   - config_kv / config_block / wire_config: NON-DESTRUCTIVE edit of the [<os>] table
     of a TOML file. A changed PERSONA_MODEL leaves the old line as a
     `# was: ... (provision rollback)` breadcrumb; missing keys are appended inside the
     section; a missing section is appended at EOF; rerunning the same pick is
     idempotent. MMPROJ_PATH + VISION_ENABLED are written for vision models (forward-
     looking -- see OWED).
   - target_config_path: writes the per-host run/config.<host>.toml when one exists
     (that file is the host's source of truth), else run/config.toml.

2. manage.py -- NEW `provision` subcommand:
   - _filter_playbook + cmd_provision inserted between cmd_capabilities and
     _test_offline; "provision" registered in build_parser and the main() handler dict.
   - Flow: detect_host -> envelope_from_caps -> match (honors --model / --text-only)
     -> print pick (pm.explain) + download plan + the config block -> license gate ->
     (--dry-run STOPS here) -> disk preflight -> confirm prompt (or --yes) -> download
     -> OPT-IN config wiring. Wiring writes ONLY with --write-config or --yes; the
     default prints the block so the live serving config is never silently rewritten.
   - Flags: --yes --model --text-only --dry-run --write-config --hf-token
     (token also read from the HF_TOKEN env var).
   - Return codes: 0 ok/dry-run/abort; 1 no-fit/module-missing; 2 license-gate;
     3 disk-preflight; 4 download-failure.

3. tests/test_provision_fetch.py (NEW) -- 30/30 PASS offline, stdlib-only (3.8+, no
   tomllib, no network). Covers preflight math, license gate (open/gated/token), plan
   (vision mmproj + skip-present), kv/block render, wiring (replace+comment /
   append-key / missing-section / dry-run / idempotent / other-sections-preserved),
   per-host target selection, download dry-run + verify. Auto-discovered by
   tests/run_all_offline.py.

4. Docs: roadmap Phase 0.5 provisioner line -> P3 CODE DONE (P4/owed listed);
   design doc P3 detailed + P4 marked NOT STARTED; the stale roadmap
   "capabilities llama_build=null" note corrected; changelog 1721; todo + this handoff.

================================================================================
VERIFICATION DONE / NOT DONE
================================================================================

- DONE (sandbox, reliable): test_provision_fetch.py 30/30; provision_fetch.py AST OK;
  cmd_provision body + the argparse block compiled in isolation (py_compile) and the
  control-flow paths (dry-run rc 0, no-fit rc 1, gated-deny rc 2) smoked with a faked
  matcher; wire_config eyeballed against a faithful replica of the real config.toml
  ([linux] edited, [windows]/[runtime] untouched, old model commented).
- NOT DONE (owed, Windows-side): a live `python manage.py provision --dry-run` on
  Daemonic-PC. The sandbox is Linux/CPU and the D:\ mount serves stale reads, so the
  launcher can only be exercised Windows-side -- same constraint as every prior
  manage.py change. test_provision_match.py (7/7) also needs Windows portable 3.11.9
  (tomllib); the sandbox here is 3.10.

================================================================================
NEXT (pick up here)
================================================================================

A. WINDOWS-SIDE: `python manage.py provision --dry-run` on Daemonic-PC. Expect the
   RX 9060 XT envelope -> qwen3.6-35b pick, the weights+mmproj plan, and the
   [linux]/per-host config block printed; nothing downloaded or written. Green ->
   clear the roadmap OWED line. Optionally also run tests/run_all_offline.py
   Windows-side (now includes test_provision_fetch.py).
B. COMMIT local: the three new/edited files + docs. Local commit only (mid-phase);
   push rides the next milestone (P4 or EVO-X2).
C. PHASE 0.5 continue up: P4 (first-run hook in cmd_up: no model present + no
   PERSONA_MODEL resolvable -> offer/auto-run provision; installer --yes path), then
   serving-side mmproj/VISION_ENABLED wiring in start_llama, then the open Per-OS
   egress + Cross-OS installer/doctor-parity items. The Exit Gate's remaining checks
   (Linux x64 live, ARM64, non-Vulkan accel selection) all need hardware.
D. Add a `tier` field to run/model_playbook.toml if `--tier` is wanted (the flag was
   intentionally omitted -- the playbook has no tier field today).

================================================================================
OPEN DECISION FOR BRANDON
================================================================================

- CONFIG-WRITE TARGET: the provisioner design (2026-06-07) predates the per-host
  config.<host>.toml convention. I defaulted the write target to the per-host file
  when one exists (else config.toml [<os>]), reasoning that the per-host file is that
  host's source of truth. On Daemonic-PC that means `provision --yes` would rewrite
  run/config.daemonic-pc.toml [linux], not the canonical config.toml. Confirm that is
  the behavior you want, or say if provision should always target config.toml [<os>].

================================================================================
GOTCHAS CARRIED FORWARD
================================================================================

- Do NOT git / py_compile / parse D:\ files from the Linux sandbox -- stale/truncated
  reads (re-confirmed this session). Use the Read tool for D:\ content; run/validate
  Windows-side or sandbox-native (author + test in the outputs dir, then publish).
- powershell 5.1 (not pwsh) for the WSL sim; WSL is CPU-only; verify the served gguf
  after a model swap; manage.py up SKIPS a live server.
- PortableGit push prints a red NativeCommandError even on success -- judge by the
  ref-update line.
