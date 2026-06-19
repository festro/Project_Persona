# Handoff -- Project_Persona

Date/time: 2026-06-18 1816 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Continues from handoff_persona_20260618_1721.md.
To resume: "continue from handoff_persona_20260618_1816.md".

Repo state:
- origin/main = aa145fa (unchanged).
- local main: the P3 increment was COMMITTED by Brandon (provisioner P3 + ctx
  safeguard). The P4 increment below is NOT yet committed -- commit it locally.
- git + file validation are Windows-side only; the Linux sandbox D:\ mount serves
  stale/truncated reads. Do NOT git / py_compile / parse D:\ files from the sandbox.
  Author + test sandbox-native, then publish; run the launcher Windows-side.

================================================================================
HEADLINE
================================================================================

Directive: "work up the phases." Phase 0.5's first-run model provisioner is now
CODE COMPLETE end to end -- phases P1 (profiler), P2 (matcher), P3 (download +
preflight + config wiring), P4 (first-run hook + installer path) all done.

This session added P4 on top of the already-committed P1-P3 + ctx safeguard.

================================================================================
DONE THIS SESSION (P4)
================================================================================

1. scripts/provision_fetch.py -- NEW model_resolvable(models_dir, configured): a quiet
   mirror of manage.resolve_model()'s usable cases (a configured PERSONA_MODEL that
   exists, or exactly one GGUF present). No logging -- it is the trigger predicate for
   the cmd_up hook.

2. manage.py -- NEW _maybe_first_run(root, cfg, args), called at the top of cmd_up:
   - If a model is servable -> returns cfg unchanged (no-op, fast path).
   - Else warns and, unless `up --yes`, asks "[Y/n] run first-run provisioning now?".
     Decline -> err + return None (cmd_up aborts with rc 1).
   - Proceeds by calling cmd_provision with a synthetic Namespace
     (yes=True, write_config=True, dry_run=False) so the model is downloaded AND wired.
   - On provision failure -> return None (abort). On success -> load_config(root) again
     so start_llama sees the freshly wired PERSONA_MODEL.
   - `up` subparser gained --yes and --hf-token (the token is passed through to
     provisioning; HF_TOKEN env is the fallback). cmd_provision itself is unchanged.

3. scripts/setup_native_stack.sh -- NEW AUTO_PROVISION env gate (default 0). With
   AUTO_PROVISION=1 the installer runs `manage.py provision --yes` at the end (headless
   path). Next-steps text now offers `manage.py provision` (auto, host-fitted,
   Apache-2.0) alongside the manual GGUF drop, and notes `up` auto-offers provisioning.
   Content-only edit -> the file keeps its +x bit (no chmod needed). `bash -n` clean.

4. tests/test_provision_fetch.py -- +6 model_resolvable checks; 42/42 offline,
   stdlib-only, auto-discovered by tests/run_all_offline.py.

================================================================================
VERIFICATION
================================================================================

- DONE (sandbox, reliable): test_provision_fetch.py 42/42; provision_fetch.py AST OK;
  the cmd_up hook's four paths smoke-verified with fakes -- (a) model present ->
  pass-through, 0 provision calls; (b) no model + decline -> abort (None); (c) no model
  + --yes -> cmd_provision(yes=True, write_config=True) then cfg reloaded; (d) no model
  + --yes + provision fails (rc 4) -> abort. Installer block bash -n OK + AUTO_PROVISION=0
  correctly skips.
- NOT DONE (owed, Windows-side, OPTIONAL): a live `manage.py up` first-run -- clear
  PERSONA_MODEL with models/ empty to see the [Y/n] offer (or `up --yes`). The launcher
  can only run Windows-side. Earlier provisioner pieces (P3 dry-run) already
  live-confirmed on Daemonic-PC.

================================================================================
NEXT (pick up here)
================================================================================

A. COMMIT local (Windows-side): manage.py, scripts/provision_fetch.py,
   scripts/setup_native_stack.sh, tests/test_provision_fetch.py, roadmap.md,
   changelog.md, todo.md, docs/model_provisioner_design_20260607_2158.md, and this
   handoff. Local commit only (mid-Phase-0.5); push stays milestone-only.
   Run manage.py via .\portable\python\python.exe; capture with `*>&1 | Tee-Object`.
B. (Optional) live-confirm the `up` first-run path Windows-side, then flip the last
   provisioner OWED line.
C. KEEP WORKING UP PHASE 0.5 (the remaining open items, hardware-free first):
   - serving-side mmproj/VISION_ENABLED wiring (start_llama does not consume them yet)
     -- pairs naturally with the provisioner's vision picks.
   - deeper KV-aware ctx sizing in provision_match (replace the 0.85*budget step-down).
   - Per-OS egress story (WireGuard mesh + host firewall baseline).
   - Cross-OS installer/doctor parity.
   The Phase 0.5 Exit Gate's remaining checks (Linux x64 live, ARM64, non-Vulkan accel
   selection) all need hardware and stay deferred.

================================================================================
GOTCHAS CARRIED FORWARD
================================================================================

- Do NOT git / py_compile / parse D:\ files from the Linux sandbox (stale/truncated).
  Use the Read tool for D:\ content; author + test sandbox-native, then publish.
- manage.py invocation: .\portable\python\python.exe (bare `python` hits the Windows
  Store alias stub). Capture runs with `*>&1 | Tee-Object -FilePath logs\<cmd>.log`
  (Tee writes UTF-16; readable).
- powershell 5.1 (not pwsh) for the WSL sim; WSL is CPU-only; verify the served gguf
  after a model swap; manage.py up SKIPS a live server.
- PortableGit push prints a red NativeCommandError even on success -- judge by the
  ref-update line.
