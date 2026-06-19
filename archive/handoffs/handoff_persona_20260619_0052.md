# Handoff -- Project_Persona

Date/time: 2026-06-19 0052 PDT
Author: Claude (Claude Code, native WSL session, with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Continues from: handoff_persona_20260618_2245.md (same session, after Brandon's two
  design decisions). Read _2245 first for the Phase 0.5 GREEN / T1 / Item-10.0 context;
  this file covers what was built AFTER those decisions.
To resume: "continue from handoff_persona_20260619_0052.md".

================================================================================
0. ORIENTATION (unchanged from _2245 -- short version)
================================================================================

- Local-first stack: llama-server (:8090) + FastAPI (:8000) via the stdlib launcher
  manage.py. roadmap.md = status truth, knowledge.md = scope, changelog.md = history,
  todo.md = short-term.
- THIS is the WSL clone (/home/festro33/Git/Project_Persona). NO .git here (D:\ is the
  git gateway) -> edit/run/test only; ALL commits owed to Brandon. Interpreter:
  env/bin/python (venv 3.12.3, has API deps). manage.py self-locates it + the CPU
  llama-server at llama_cpp/build/bin.

================================================================================
1. TL;DR -- THIS CHUNK
================================================================================

After _2245 (Phase 0.5 GREEN + T1 restore + Item 10.0), Brandon locked the two open
Phase 0.5 design decisions and I implemented both:

1. EGRESS BASELINE (Phase 0.5 "Per-OS egress story" Item, was [ ] -> now [~]).
   Decision: host firewall default-deny NOW (Windows + Linux), SCRIPTED not
   auto-enforced, WireGuard -> Phase 9, allowlist = loopback + internet only during
   provisioning. Built: design doc + Linux nft script + Windows PS script + a read-only
   doctor report (+ unit tests).
2. INSTALLER .env (Phase 0.5 "installer/doctor parity" Item, was [ ] -> now [~]).
   Decision: KEEP manage.py's .env read-fallback, STOP the installer writing it. Done in
   setup_native_stack.sh.

Both LOCAL + UNCOMMITTED (no git here). Offline suite 5/5; py_compile OK.

================================================================================
2. WHAT WAS BUILT -- DETAIL
================================================================================

--- 2A. Egress baseline (host firewall) ---
Design: docs/egress_baseline_design_20260619.md. Threat model = the NETWORK-level half
of egress containment (config-level half already exists via Hermes safe-config). Two
postures: SERVE (locked: loopback + established only) and PROVISION (SERVE + DNS/HTTPS
for downloads). Per-OS, scripted, operator-applied; manage.py only REPORTS.

scripts/egress_baseline.sh (Linux/nftables):
- isolated table `inet persona_egress`, output chain policy drop.
- subcommands: plan (default; PURE TEXT print, no nft call) / status / apply
  [--provision] / remove. apply+remove need root + --yes (or TTY confirm).
- established,related accepted FIRST -> applying over SSH won't cut the session.
- remove = `nft delete table inet persona_egress` (clean total rollback).
- VERIFIED: bash -n clean; `plan` and `plan --provision` print valid nftables rulesets.
  NOT live-applied here (would risk cutting the dev box's own network).

scripts/egress_baseline.ps1 (Windows Firewall):
- -Status / -Plan / -Apply / -Remove, plus -Provision and -Strict.
- default = process-scoped outbound BLOCK for llama-server.exe (group PersonaEgress).
- -Strict = host-wide DefaultOutboundAction=Block + allow rules (loopback/DNS/HTTPS).
- -Remove restores Allow + deletes the group.
- STATUS: written + reviewed; LIVE WINDOWS VERIFY OWED (no PowerShell on this surface).

manage.py:
- egress_posture(present, provision_open) -- PURE classifier (serve/provision/none/
  unknown), unit-tested.
- _probe_egress(root) -- READ-ONLY probe (nft list / Get-NetFirewallRule); returns
  (present, provision_open); never mutates firewall state; None when it cannot probe.
- doctor: new read-only "Egress baseline" section reporting posture + pointing at the
  scripts when none is loaded.
- tests/test_manage_pid.py: +5 egress_posture checks. Offline suite 5/5.

--- 2B. Installer .env: keep read, stop writing ---
scripts/setup_native_stack.sh no longer writes run/llama-servers.env by default. An
existing file is left untouched; FORCE_ENV=1 regenerates it (the no-tomllib escape
hatch). Rationale (verified in code): load_config (manage.py:165) reads the .env files
ONLY as a fallback (config.toml present -> never read); server.py reads os.environ that
manage.py fills FROM config.toml; the bash scripts that used to source .env are archived.
So real hosts lose nothing; only the stale written file goes away. bash -n clean.
Scope: only llama-servers.env was auto-written (config.env is committed/fallback-read
only; start_api.sh is archived).

================================================================================
3. VERIFICATION
================================================================================

Verified this chunk:
- py_compile manage.py OK.
- tests/run_all_offline.py 5/5 (test_manage_pid now +5 egress checks).
- egress_baseline.sh: bash -n clean; plan/plan --provision output = valid nftables.
- setup_native_stack.sh: bash -n clean.
- egress_posture returns the four expected labels.

OWED (need a real box / Windows / other distros):
- Live-apply the SERVE lock on a real Linux box (apply --yes -> a curl should fail ->
  remove --yes). Not done here to avoid cutting the dev surface's own connectivity.
- Windows PowerShell verify of egress_baseline.ps1 (process-scoped + -Strict + -Remove).
- (optional) an iptables fallback script for hosts without nftables.
- Broader Debian / other-Linux installer + doctor parity passes.
- COMMIT everything (no git here). See _2245 sec 4 + todo.md "Next up" for the file list;
  this chunk adds: scripts/egress_baseline.{sh,ps1}, docs/egress_baseline_design_20260619.md,
  manage.py (egress bits), tests/test_manage_pid.py, scripts/setup_native_stack.sh.

================================================================================
4. STILL OPEN (need Brandon / hardware)
================================================================================

MINOR decisions (deferred to avoid guessing intent):
- provisioner --tier: needs a tier taxonomy first (the playbook's "Tier 1 / 0" group is
  combined; a 14B is grouped under "SBC/Pi"). Decide the tier->model mapping and it's a
  quick add (tier field in run/model_playbook.toml + a --tier filter in
  manage._filter_playbook + offline tests).
- KV-aware ctx sizing: the matcher's 0.85*budget step-down is crude; a real KV estimate
  needs per-model metadata or HW measurement -- do NOT invent constants (your rule).

HARDWARE / Phase 9 (out of this scope, deferred by you): H2d EVO-X2 Exit Gate;
EVO-X2-native + ARM64 + non-Vulkan accel passes; the mesh.

LARGER 0-8 work available (your call, not started): Phase 2 (OpenWebUI thin client,
conversations.db history, ChromaDB->Qdrant migration). Sizeable new feature.

================================================================================
5. STATE OF THE LADDER (after this session)
================================================================================

- Phase 0  GREEN.
- Phase 0.5 GREEN (locked 2026-06-18; both primary-surface Exit-Gate checks [x]). Two
  non-gating Items now [~] (egress baseline design+scripts; installer .env done) with
  live/cross-distro verification owed.
- Phase 1  GREEN.
- Phase 8  foundation started; H2 bridge validated in WSL; T1 safe-config gate restored
  this session; H2d (EVO-X2) + H3-H6 owed (hardware/Phase 9).
- Phase 10 Item 10.0 [x] (offline suite green on both primary surfaces); 10.1-10.5 need
  Phase 9.
- Phases 2-7 not started (2/6/7) or optional (4/5); Phase 9 not started (hardware).

The 0-8 ladder is taken as far as it goes on the primary surfaces without hardware or a
further Brandon decision. Next real progress is gated on: the minor decisions above, the
owed live verifications, hardware (Phase 9), or an explicit go-ahead on Phase 2.
