# Handoff -- Project_Persona  (FULL SESSION, start to finish)

Date/time: 2026-06-18 2133 PDT
Author: Claude (Cowork session, with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Continues from: handoff_persona_20260618_1816.md (this session) <- _1721.md <- the
  prior session's handoff_persona_20260614_1655.md.
Intended reader: a fresh coding agent (Claude Code) picking up in the live repo.
To resume: "continue from handoff_persona_20260618_2133.md".

================================================================================
0. READ-ME FIRST (orientation for the next agent)
================================================================================

- This is a local-first, portable AI-companion stack: one llama-server (Qwen3.6-35B-
  A3B, :8090) + a FastAPI companion API (:8000), driven by a single cross-platform
  launcher `manage.py` (stdlib-only, no bash for core lifecycle). Hermes is the Phase 8
  agentic layer. The roadmap is a phased ladder; `roadmap.md` is the status source of
  truth, `knowledge.md` is scope/architecture, `changelog.md` is append-only history,
  `todo.md` is short-term "just finished / next up", `docs/` holds design notes.
- You are running NATIVELY in the repo (Windows or WSL), so unlike the Cowork sandbox
  that produced this handoff you CAN run git, py_compile, the launcher, and the tests
  directly. The "stale D:\ mount" caveat in older handoffs was a Cowork-sandbox artifact
  and does NOT apply to you -- ignore it.
- Run the launcher and tests with the committed PORTABLE interpreter on Windows:
  `.\portable\python\python.exe manage.py <cmd>` (a bare `python` hits the Windows
  Store alias stub and fails). On Linux use the env interpreter / `python3`.
- Timestamps: Pacific (PDT/PST), format `YYYY-MM-DD HHMM`. See the date-correction note
  in section 7 -- this session was initially mis-stamped 2026-06-14 (a frozen sandbox
  clock) and corrected to 2026-06-18.

================================================================================
1. TL;DR -- WHAT THIS SESSION DID
================================================================================

Theme: "work up the phase ladder." Lowest non-green phase is Phase 0.5 (portability).
Within it, the first-run model PROVISIONER was the open, hardware-free line.

1. Provisioner P3 (download + disk preflight + license gate + config wiring) -- built,
   tested (offline), and LIVE-CONFIRMED via `provision --dry-run` on Daemonic-PC.
2. ctx-preserve SAFEGUARD -- provision keeps a host-validated PERSONA_CTX over the
   matcher's conservative guess.
   [#1 and #2 were COMMITTED locally by Brandon mid-session.]
3. Provisioner P4 (first-run hook in cmd_up + installer --yes path) -- built + tested.
4. Serving-side VISION wiring -- start_llama now loads the mmproj; closes the
   provisioner vision loop end to end.
5. ROADMAP RE-SCOPE (structural, Brandon's call): Phases 0-8 target the two PRIMARY dev
   surfaces only (Windows x64 + AMD Linux via WSL); cross-arch/cross-accel/EVO-X2-native
   hardening relocated to the Phase 9/10 capstone. This UNBLOCKS Phase 0.5 from GREEN.
6. Research/design: an MCPJungle MCP-gateway evaluation, and a Matrix-style federation
   "prior art" section for the Phase 9 mesh.
7. DATE CORRECTION: the whole session was mis-stamped 2026-06-14 and re-dated to 06-18.

Items #3-#7 are LOCAL + UNCOMMITTED. Verify with `git status` / `git log`.

================================================================================
2. REPO + COMMIT STATE
================================================================================

- origin/main = aa145fa (unchanged this session; pushes are milestone-only).
- local main: Brandon committed the P3 + ctx-safeguard batch ONE commit on top of
  aa145fa mid-session (get the hash from `git log --oneline -5`). Everything after that
  (P4, vision wiring, roadmap re-scope, the two design docs, and the date correction) is
  UNCOMMITTED in the working tree.
- CAVEAT from the date fix: correcting 2026-06-14 -> 2026-06-18 also modified a few lines
  that were already committed (some changelog headers, the provisioner design doc, and a
  handoff that got RENAMED _20260614_ -> _20260618_). So `git status` will show both new
  work and date-only modifications to tracked files, plus a rename. This is expected.

UNCOMMITTED INVENTORY (logical; confirm with git status):
  Code:
  - manage.py -- P4 (_filter_playbook? no: _maybe_first_run, cmd_up first-run hook, `up`
    --yes/--hf-token) + vision (_truthy, _mmproj_args, start_llama --mmproj wiring,
    doctor vision line).
  - scripts/provision_fetch.py -- added model_resolvable() (P4) on top of the committed
    P3/resolve_ctx.
  - tests/test_provision_fetch.py -- +6 model_resolvable checks (now 42/42 offline).
  - tests/test_manage_pid.py -- +7 _truthy/_mmproj_args checks.
  - scripts/setup_native_stack.sh -- AUTO_PROVISION=1 gate + updated next-steps text.
  Docs:
  - roadmap.md -- P4 line; the re-scope (PLATFORM SCOPE block, Current position, Phase
    0.5 narrowed + Exit Gate, Phase 9 ownership note, Phase 10 Item 10.2); vision-done
    note; date fixes.
  - knowledge.md -- portability/Phase-9 scope sync + date.
  - todo.md -- stamps, "just finished", "next up".
  - changelog.md -- new entries (1721,1758 committed; 1816,1841,1858,1903 new) + date fixes.
  - docs/distributed_nodes.md -- NEW section 5c (Matrix/federation prior art) + date.
  - docs/mcp_gateway_eval_20260618_1831.md -- NEW (MCPJungle eval).
  - docs/model_provisioner_design_20260607_2158.md -- P3/P4 "CODE DONE" notes + date.
  - archive/handoffs/handoff_persona_20260618_1721.md, _1816.md, and THIS file.

================================================================================
3. WHAT WAS BUILT -- DETAIL BY AREA
================================================================================

--- 3A. Provisioner P3 (COMMITTED) -- scripts/provision_fetch.py + manage.py ---
The first-run model provisioner downloads a host-fitted, Apache-2.0 model and wires it
into config. P3 consumes a pick from scripts/provision_match.match() (P2, already done)
and provides:
  - disk_free_mb / preflight_disk: require free space >= file size + 20%.
  - license_gate: Apache-2.0/MIT/BSD ungated = happy path; a gated license needs an
    explicit HF_TOKEN (never auto-accept).
  - build_plan: base GGUF + matching mmproj when vision; skip-if-present; total MiB.
  - download: huggingface_hub.hf_hub_download (resumable; network branch only).
  - config_kv / config_block / wire_config: NON-DESTRUCTIVE [<os>] TOML edit; a changed
    PERSONA_MODEL is left as a `# was: ...` rollback breadcrumb; idempotent on rerun.
  - target_config_path: writes the active per-host run/config.<host>.toml if present
    (CONFIRMED by Brandon as the intended target), else run/config.toml.
manage.py gained the `provision` subcommand: match -> plan -> license gate -> (--dry-run
stops) -> disk preflight -> confirm (or --yes) -> download -> OPT-IN config wiring
(--write-config or --yes; default just prints the block so the live serving config is
never silently rewritten). Flags: --yes --model --text-only --dry-run --write-config
--hf-token.
LIVE-CONFIRMED 2026-06-18 on Daemonic-PC (RX 9060 XT): `provision --dry-run` ->
qwen3.6-35b Q5_K_XL pick, weights [present] (0 MiB), per-host target
config.daemonic-pc.toml [windows], vision off (no camera), nothing written.

--- 3B. ctx-preserve safeguard (COMMITTED) ---
The matcher's tight-budget ctx step-down proposed PERSONA_CTX=8192 on a host that runs
16384. Root cause: ctx is penalized when the MODEL FILE exceeds 0.85*budget, but KV
headroom is a separate pool. Fix: provision_fetch.resolve_ctx() + config_kv(existing_ctx);
cmd_provision passes the EFFECTIVE merged cfg PERSONA_CTX and PRESERVES it over the
matcher's guess (a note is printed). Fresh hosts (no existing ctx) keep the matcher's
conservative value -- under-setting is the safe direction (won't OOM).

--- 3C. Provisioner P4 (UNCOMMITTED) -- first-run hook + installer ---
- scripts/provision_fetch.py: model_resolvable(models_dir, configured) -- quiet mirror
  of manage.resolve_model()'s usable cases (configured PERSONA_MODEL present, or exactly
  one GGUF) used as the trigger predicate.
- manage.py: _maybe_first_run(root, cfg, args) at the top of cmd_up. No servable model
  -> interactive "[Y/n] run first-run provisioning now?" or, under `up --yes`, auto-runs
  cmd_provision (yes + write_config). Reloads cfg after wiring so start_llama sees the
  new PERSONA_MODEL; aborts cleanly (return 1) on decline/failure. `up` gained
  --yes/--hf-token.
- scripts/setup_native_stack.sh: AUTO_PROVISION=1 env gate runs `manage.py provision
  --yes` at the end (headless install path); next-steps text points at `manage.py
  provision`. Content-only edit -> the .sh keeps its +x bit (no chmod needed); `bash -n`
  clean.

--- 3D. Serving-side vision wiring (UNCOMMITTED) -- manage.py start_llama ---
Closes the loop: provision writes MMPROJ_PATH + VISION_ENABLED; start_llama now consumes
them. New _truthy + _mmproj_args helpers; start_llama appends `--mmproj
<models/MMPROJ_PATH>` (verified flag `-mm/--mmproj` in llama_cpp/common/arg.cpp) when
VISION_ENABLED is truthy AND the projector file exists. GATED: the mmproj may be on disk
(provisioner fetches it regardless) but a headless node stays text-only until vision is
opted in. doctor reports vision status. A missing projector warns + falls back to
text-only.

--- 3E. ROADMAP RE-SCOPE (UNCOMMITTED) -- structural; read roadmap.md ---
Brandon's decision: Phases 0-8 build a solid foundation on the two PRIMARY dev surfaces
ONLY -- Windows x64 + AMD Linux via WSL (CPU) on Daemonic-PC. Broader portability
(ARM64, non-Vulkan accel, EVO-X2-native GPU) is the multiplatform/troubleshooting
CAPSTONE, folded into Phase 9 (migration to EVO-X2 + other systems + mesh) and Phase 10
(full-system + cross-host validation). Concretely in roadmap.md:
  - Added a PLATFORM SCOPE framing block; rewrote Current position.
  - Phase 0.5 renamed to "Cross-OS foundation (Windows x64 + AMD Linux via WSL)"; its
    Exit Gate reduced to the two primary surfaces (Windows x64 [x] + AMD-Linux-via-WSL
    [~]); the ARM64 / non-Vulkan / EVO-X2-native checks RELOCATED to Phase 9 Item 9.0 +
    Phase 10 Item 10.2.
  - Net: Phase 0.5 is UNBLOCKED -- it locks GREEN once the WSL-Linux lifecycle gets a
    clean standalone `manage.py` pass (Windows x64 already done). It no longer waits on
    EVO-X2/ARM64 hardware.
knowledge.md was synced to match.

--- 3F. Research/design (UNCOMMITTED) ---
- docs/mcp_gateway_eval_20260618_1831.md: evaluation of MCPJungle (self-hosted MCP
  gateway) as the Phase 8/9 TOOL PLANE in front of Hermes' built-in MCP client. License
  = MPL-2.0 (OSI-open, AGPL-compatible, file-level copyleft -> clears the project bar;
  standalone-process use imposes nothing on our code). Verdict: adopt at Phase 8/9 when
  the local-MCP-server or node count grows, loopback-only + enterprise ACLs as the
  egress chokepoint; tools-not-resources for now; audit-log thinness is the one real
  caution. NOT now.
- docs/distributed_nodes.md section 5c "Prior art: federation models (Matrix et al.)":
  Brandon frames Phase 9 as "a federation of interconnectable yet independent systems" ==
  Matrix's model. Maps Matrix mechanisms onto the section 5/5b opens (signed event DAG ->
  node_id+keypair; m.room.server_acl -> deny-list/eviction; state resolution ->
  split-brain reconcile; power levels -> re-key quorum; backfill -> cutover/rejoin).
  "Chatroom-as-feature": for a hardware/OS-agnostic personal assistant a synced (E2EE)
  cross-device conversation timeline is a FEATURE, elevating Matrix from prior-art toward
  candidate substrate. Parked fork (sec 9): reimplement on NATS+token vs run a light
  homeserver vs hybrid; plus an offline/P2P survey (Briar/SSB/libp2p/Iroh/Veilid) that
  NEEDS a current-status web search before any bet.

================================================================================
4. VERIFICATION STATUS
================================================================================

Done (offline, sandbox-verified):
- tests/test_provision_fetch.py: 42/42 (preflight, license gate, plan, kv/block, wiring,
  per-host target, resolve_ctx, model_resolvable, download dry-run + verify).
- tests/test_manage_pid.py: the new _truthy/_mmproj_args logic verified (7/7 in a
  standalone harness; the checks are appended to the suite).
- cmd_provision + cmd_up first-run control paths smoke-verified with fakes.
- wire_config eyeballed against a real config.toml replica.
- setup_native_stack.sh new block `bash -n` clean.
- The cmd_provision / cmd_up / _mmproj_args bodies compiled in isolation.

OWED (you can do these natively now):
- `git status` + `git log --oneline -5` to confirm the commit boundary, then COMMIT the
  uncommitted batch (local only; do NOT push -- pushes are milestone-only).
- Run the offline suite natively to re-confirm: `.\portable\python\python.exe
  tests\run_all_offline.py` (Windows) -- it auto-discovers tests/test_*.py. NOTE:
  test_provision_match.py needs Python 3.11+ (tomllib); the portable 3.11.9 is fine.
- `.\portable\python\python.exe -m py_compile manage.py` (a full syntax check I could
  not run in the sandbox).
- Phase 0.5 GREEN: a clean `manage.py status/doctor/up/down/test` pass in the WSL clone
  (the AMD-Linux-via-WSL Exit-Gate check).
- A live vision smoke: provision/serve a vision model + send an image, confirm --mmproj
  loaded (the "Vision input" feature itself stays parked).

================================================================================
5. NEXT STEPS (recommended order for the next agent)
================================================================================

1. Orient: read roadmap.md (Current position + Phase 0.5 + Phase 9/10) and todo.md.
2. `git status`; reconcile against section 2; `py_compile manage.py`; run
   tests/run_all_offline.py. Fix anything red BEFORE building.
3. COMMIT the uncommitted batch locally (suggested message: "Phase 0.5: provisioner P4 +
   vision serving wiring + roadmap re-scope to primary surfaces + design notes; dates
   corrected to 2026-06-18"). Local only.
4. Pick the next rung UP the 0-8 ladder (all hardware-free, primary surfaces):
   - Per-OS egress baseline (WireGuard + host firewall, Win+Linux) -- design call first.
   - Cross-OS installer/doctor parity (Win + Debian/Linux). OPEN QUESTION for Brandon:
     setup_native_stack.sh still writes the legacy run/llama-servers.env while
     run/config.toml is the committed source of truth -- decide whether to keep the env
     fallback or drop it.
   - (PARKED, needs data) deeper KV-aware ctx sizing in provision_match: the current
     0.85*budget step-down is crude, but a real KV estimate needs per-model metadata
     (GQA ratio, n_layers, cache type) or hardware measurement -- do NOT guess constants.
5. To actually LOCK Phase 0.5 GREEN: run the WSL-Linux lifecycle pass (Brandon's box).
6. Phase 9/8 work (H2d EVO-X2 exit gate, mesh) is DEFERRED by Brandon until the 0-8
   foundation is done, and needs the EVO-X2 hardware.

================================================================================
6. KEY FILES / POINTERS
================================================================================

- Launcher: manage.py (provision, up + first-run hook, start_llama + mmproj, doctor).
- Provisioner: scripts/provision_match.py (P1/P2 matcher), scripts/provision_fetch.py
  (P3/P4), run/model_playbook.toml (catalog, all Apache-2.0).
- Config: run/config.toml ([base]/[runtime]/[<os>]) + per-host run/config.<host>.toml
  (merged last; daemonic-pc = Qwen2.5-7B CPU-WSL exception).
- Tests: tests/run_all_offline.py (runner), test_provision_fetch.py, test_manage_pid.py,
  test_provision_match.py, test_api_offline.py, test_hermes_bridge.py.
- Status/scope/history: roadmap.md, knowledge.md, changelog.md, todo.md.
- Design notes: docs/model_provisioner_design_20260607_2158.md,
  docs/mcp_gateway_eval_20260618_1831.md, docs/distributed_nodes.md (mesh, +5c),
  docs/llama_build_matrix.md, docs/portability_audit.md.

================================================================================
7. GOTCHAS / NOTES CARRIED FORWARD
================================================================================

- DATE: the Cowork sandbox clock was frozen ~4 days behind this session (reported
  2026-06-14; real date 2026-06-18). All of this session's stamps were corrected to
  06-18 and 3 files renamed _20260614_ -> _20260618_; prior-session 06-14 content was
  left intact. Trust the environment's "today" over a shell `date` for stamping.
- Windows: invoke via `.\portable\python\python.exe` (bare `python` = MS Store stub).
- The "stale/truncated D:\ mount" warning in older handoffs was Cowork-sandbox-specific
  and does NOT apply to you running natively.
- powershell 5.1 (not pwsh) for the WSL sim scripts/wsl_h2_sim.ps1; WSL on Daemonic-PC
  is CPU-only (no GPU; ~15-20 min/agent-turn for a 7B); GPU lives on EVO-X2.
- manage.py up SKIPS a live llama-server; reliable liveness = /health + a `ps ... gguf`
  grep (the pidfile fix makes down/status agree, but the manual check still holds).
- PortableGit push prints a red NativeCommandError even on success -- judge by the
  ref-update line, not the error (only relevant if/when you push a milestone).
- config wiring is OPT-IN (--write-config/--yes); vision serving is GATED on
  VISION_ENABLED; both are deliberate so a node stays lean/safe by default.
