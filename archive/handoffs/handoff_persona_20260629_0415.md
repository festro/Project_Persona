# Handoff -- Project_Persona

Date/time: 2026-06-29 0415 PDT
Author: Claude (Claude Code on Daemonic-PC, driving EVO-X2 over SSH, with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
To resume: "continue from handoff_persona_20260629_0415.md".
Prior handoff: handoff_persona_20260629_0125.md (set this session's priority: proposal C HARD
containment). This session DELIVERED that + backed up the persona profiles. Incremental detail in
changelog.md (2026-06-29 entries 0147 / 0346 / 0415).

================================================================================
0. ORIENTATION
================================================================================

- Two machines:
  * Daemonic-PC = Windows daily-driver. The git GATEWAY (D:\Projects\Git\Project_Persona) +
    Windows testbed. Portable python at portable\python\python.exe (runs the offline suite). EDIT
    HERE, commit, push; EVO-X2 pulls. EXCEPTION this session: files that live ONLY on EVO-X2 (the
    persona profiles) were committed ON EVO-X2 and pushed; D:\ then fast-forwarded.
  * EVO-X2 (Daemonic-evox2, 192.168.8.114, user festro33) = the always-on anchor (Qwen3.6-35B-A3B,
    UD Q5_K_XL, RADV GFX1151 Vulkan). Driven over SSH (`ssh evox2`). Repo ~/Git/Project_Persona;
    venvs env/ (persona API), env_hermes/ (Hermes v0.16.0), env_webui/ (OpenWebUI 0.9.6).
    sudo = HARD-DENY.
- Stack: llama-server (:8090) + FastAPI persona API (:8000) + Hermes agent layer, supervised by
  daemon.py (systemd --user unit persona-daemon, --with-hermes). OpenWebUI (:3000) = a SEPARATE
  persistent systemd --user unit persona-webui, LAN-bound. Both reboot-survive (linger + enabled).
- Persona name "Daemonic". Memory/RAG = Qdrant (embedded). knowledge.md = architecture, roadmap.md =
  phase status, ~/.claude/.../memory = operating gotchas.
- Git: D:\, origin/main, and EVO-X2 are all at HEAD (this session's final commit). Offline 23/23.
- The repo github.com/festro/Project_Persona is PUBLIC -- mind what gets committed.

================================================================================
1. WHAT THIS SESSION DELIVERED (all committed + pushed + synced; live-verified where noted)
================================================================================

(A) PROPOSAL C "HARD" CONTAINMENT for Hermes workers -> realized as per-role HOME ISOLATION.
  - Investigation first (handoff said to): path (b) a SANDBOXED terminal backend is RULED OUT on
    EVO-X2 -- bwrap IS installed but NOT setuid and the kernel sets
    kernel.apparmor_restrict_unprivileged_userns=1 (Ubuntu 24.04+), so every bwrap/unshare uid-map +
    loopback setup fails. Lifting it = sysctl flip or an AppArmor profile = sudo = hard-deny.
    firejail/nsjail/proot absent. Path (a) "allowlist shim via terminal.shell_init_files" does NOT
    gate per-command (per-cmd = `bash -c "<cmd>"` in tools/environments/local.py::_run_bash;
    shell_init_files only shape the LOGIN env-snapshot). The only per-command hook is winning
    shutil.which("bash") via PATH (a global shim) -- declined as too risky on the fragile chain.
  - Brandon chose WORKSPACE-CONFINE ONLY. Delivered via Hermes' NATIVE mechanism (no Hermes code
    change): hermes_constants.get_subprocess_home() redirects a worker's TERMINAL-subprocess HOME to
    {HERMES_HOME}/home/ WHEN THAT DIR EXISTS. NEW scripts/apply_home_isolation.sh (idempotent) creates
    persona/profiles/<role>/home/ for every NON-default worker profile + seeds an identity-only
    .gitconfig (no creds). Wired into init_profiles.sh. 'default' (trusted persona/bridge/dispatcher)
    intentionally NOT isolated. The CWD half was already native (workers spawn cwd=<per-task scratch
    workspace> under run/hermes_kanban/kanban/workspaces/<task_id>).
  - SAFE: only the terminal SUBPROCESS HOME changes; the worker's own hermes proc reads HERMES_HOME
    (not HOME) and kanban_complete is in-process -> delegate->complete chain untouched. A confined
    worker can no longer reach the host ~/.ssh, ~/.config, gh/aws tokens, shell history.
  - VERIFIED LIVE (no daemon restart -- dir existence is checked per shell spawn; workers are fresh
    procs): get_subprocess_home() -> profiles/<role>/home (default -> None); idempotent re-run skips
    all; summarizer verify-gate -> status=ok (also ok PRE-change); END-TO-END coder shell self-check
    reported HOME=.../persona/profiles/coder/home (isolated; only .gitconfig inside) and
    PWD=.../kanban/workspaces/<id> (per-task scratch CWD), status=ok.

(B) BACKED UP the persona PROFILES to git (closes the handoff s6 "untracked profiles" item).
  - Repo is PUBLIC -> tracked CONFIG ONLY: the 5 worker delegate profiles
    {coder,critic,librarian,researcher,summarizer}/{SOUL.md,.hermes.md,config.yaml} PLUS default +
    test (their .hermes.md scope-contract blocks + default config.yaml shell_init_files = the H2d
    PATH fix). No secrets. Content derives from the public init_profiles.sh + apply_scope_contracts.sh.
  - .gitignore HARDENED so a future `git add persona/profiles/` can't leak: ignores
    persona/profiles/*/{home,skills}/, persona/{skills,bin}/, and runtime state (state.db*, auth.lock,
    .skills_prompt_snapshot.json, .update_check) at profile + root level.
  - NOT committed (deliberate): the vendored Hermes skills corpus (large, credential-adjacent
    google-workspace OAuth, regenerable), persona/bin/tirith (binary), all runtime/state, and the
    per-role home/ HOME-isolation dirs (recreated by apply_home_isolation.sh).

(C) FIXED an init_profiles.sh BUG: it wrote persona/README.md UNCONDITIONALLY, so a re-run clobbered
    the detailed hand-maintained README with a short auto-gen stub (this had already happened on
    EVO-X2). Now scaffold-only (skips if README exists). RESTORED the detailed README on EVO-X2's
    working tree (git checkout). EVO-X2 now has ZERO modified tracked files.

================================================================================
2. CURRENT LIVE STATE (EVO-X2)
================================================================================

- persona-daemon (persistent, --with-hermes): ACTIVE. llama:8090 + api:8000 up. webui:3000 up.
  All delegates this session completed status=ok. (Confirm with the resume check in section 6.)
- Git D:\ = origin/main = EVO-X2 = HEAD (this session's final commit). Offline 23/23.
- EVO-X2 working tree: CLEAN of modified tracked files. Still UNTRACKED (by design, .gitignore'd or
  runtime): persona/profiles/*/{home,skills}/, persona/skills/, persona/bin/, state dbs, auth.locks,
  openwebui/, env/, archive/memory_backups/, run/hermes_shell_init.sh (generated).
- The per-role home/ isolation dirs exist live on the 6 non-default profiles (coder, critic,
  librarian, researcher, summarizer, test). NOT in git -> if the box is rebuilt, re-run
  scripts/apply_home_isolation.sh (idempotent) to recreate them.

================================================================================
3. WHERE THE NEW CODE / KNOBS LIVE
================================================================================

- scripts/apply_home_isolation.sh: per-role HOME isolation (creates {profile}/home/ + identity-only
  .gitconfig; skips 'default'). Called by init_profiles.sh after apply_scope_contracts.sh.
- scripts/init_profiles.sh: now also calls apply_home_isolation.sh; README scaffold is now guarded
  (skip-if-exists).
- .gitignore: new per-profile + persona-root runtime/skills/bin exclusions.
- Hermes mechanism (read-only ref, in ~/src/hermes-agent): get_subprocess_home() in
  hermes_constants.py (HOME redirect); _make_run_env()/_run_bash() in tools/environments/local.py
  (where it's applied + how per-command bash is invoked); _default_spawn in hermes_cli/kanban_db.py
  (worker spawn: cwd=<workspace>, env HERMES_HOME=profiles/<role>); dispatcher = gateway via
  tools/hermes_dispatch_loop.py.

================================================================================
4. VERIFY-GATE / DEBUG LOOP
================================================================================

- Containment verify gate (the official one): delegate a summarizer task and poll /jobs to ok.
  Reusable probes left on EVO-X2 at /tmp/delegate_probe.sh (role+summary) and /tmp/delegate_probe2.sh
  (role + literal $PBODY, e.g. a coder shell self-check). They POST /agent/delegate and poll
  /jobs/<id>. (NB: /tmp is ephemeral; re-create from the changelog/this handoff if gone.)
- OpenWebUI end-to-end: env_webui/bin/python tools/webui_probe.py [--web|--no-web]
  [--expect-sources|--expect-contains TXT] "PROMPT" (mints the HS256 JWT from .webui_secret_key).

================================================================================
5. OUTSTANDING (Brandon's call / sudo-gated)
================================================================================

- SUDO-GATED (Brandon): kernel egress baseline (scripts/egress_baseline.sh, nftables, root). Config-
  level egress is already off (non-researcher roles); this closes the "egress at config AND kernel"
  gate line. THE ONLY thing this session's work explicitly left for you.
- A HARDER containment tier (denylist/allowlist `bash` shim winning shutil.which("bash")) remains
  possible but was declined as too risky on the fragile complete-chain. Mechanism + why-soft are in
  changelog 0147 and memory evox2-ssh-operations. Current layers: soft scope contracts (.hermes.md) +
  HOME/CWD confinement + egress-off + daemon secret-stripping.
- Deferred / low-ROI (unchanged): B (Git-backed canon/ markdown memory); D-extension (in-sweep LLM
  contradiction pass beyond near-identical dedup); H6.4 cache hit-rate study (needs a multi-slot or
  role-batched config -- PARALLEL=1 contends the cache); EVO-X2 35B/Vulkan llama rc=-6 (root-caused;
  Brandon chose Option A: keep caching, supervisor auto-recovers).
- The vendored skills corpus + default-profile SOUL.md are tracked OR host-local as appropriate; the
  skills corpus is intentionally NOT in the public repo (regenerable via Hermes).

================================================================================
6. OPERATING EVO-X2 + ONE-LINER RESUME CHECK
================================================================================

- Health:  ssh evox2 'cd ~/Git/Project_Persona && env/bin/python manage.py daemon status'
- Restart persona stack:  ssh evox2 'systemctl --user restart persona-daemon'
- Restart OpenWebUI (re-applies middleware patches):  ssh evox2 'systemctl --user restart persona-webui'
- Re-apply containment to profiles (idempotent):  ssh evox2 'cd ~/Git/Project_Persona &&
    AI_ROOT="$PWD" bash scripts/apply_home_isolation.sh'
- Deploy a normal change: edit on D:\ -> py_compile + tests/run_all_offline.py -> update
  changelog+todo+roadmap (Brandon's rule: BEFORE commit) -> commit -> push -> ssh evox2 git pull
  --ff-only -> restart the relevant unit. (For files that live ONLY on EVO-X2, commit there + push,
  then D:\ git pull --ff-only.)

  ssh evox2 'cd ~/Git/Project_Persona && env/bin/python manage.py daemon status && \
    curl -s -o /dev/null -w "api:%{http_code} llama:%{http_code}\n" http://127.0.0.1:8000/health \
      http://127.0.0.1:8090/health && git rev-parse --short HEAD'

Expect: daemon ACTIVE, api+llama 200, HEAD == origin/main. Stack live.
