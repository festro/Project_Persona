# Project_Persona -- Roadmap

Single source of truth for completion status, organized as a Phase ladder from
basic functionality to extended functionality. Each Phase locks to a functional
state: it has an Exit Gate (a concrete, testable checklist) that must be green
before the next Phase starts.

Last updated: 2026-06-29 0346 PDT by Claude (BACKED UP the 5 H4 worker role profiles to git -- role CONFIG only (SOUL.md/.hermes.md/config.yaml; role prompts + scope contracts; no secrets; repo is PUBLIC so the vendored skills corpus, bin/, HOME-isolation dirs, and runtime state are .gitignore'd, not committed). Closes the handoff "untracked profiles not backed up" item for the worker roles; default+test stay untracked (locally modified). EARLIER 0147: HERMES WORKER CONTAINMENT -- per-role HOME ISOLATION delivered ("workspace confine only", Brandon's pick for the "HARD containment" follow-up). The sandboxed-backend path is RULED OUT on EVO-X2 (bwrap present but AppArmor blocks unprivileged userns; sysctl/profile fix = sudo = hard-deny). NEW scripts/apply_home_isolation.sh (idempotent; wired into init_profiles.sh) creates persona/profiles/<role>/home/ for each NON-default worker profile -> Hermes' native get_subprocess_home() redirects worker terminal-subprocess HOME there; identity-only .gitconfig seeded (no creds); 'default' (trusted persona) skipped. CWD half already native (workers spawn cwd=<per-task scratch workspace>). VERIFIED LIVE: get_subprocess_home->profiles/<role>/home, summarizer verify-gate ok (no regression), end-to-end coder shell self-check confirmed HOME inside profiles/coder/home + PWD in kanban/workspaces/<id>. Builds on the 2026-06-29 SOFT per-role scope contracts (.hermes.md). The containment stack is now: soft scope contracts + HOME/CWD confinement + egress-off (non-researcher) + daemon secret-stripping. Full detail: changelog 2026-06-29 0147 + todo.md. EARLIER 2026-06-22 0215 PDT (Claude): Phase 8 H3 + H4 + H5 + H6.1/6.2/6.3 all PROVEN LIVE on EVO-X2 over SSH; H6.4 deferred. H3: standing dispatcher (tools/hermes_dispatch_loop.py loops the SUPPORTED `dispatch`, not the deprecated `kanban daemon`/gateway) makes the H2d chain UNATTENDED -> hands-off delegate -> ok+summary. H6.2 reclaim+recovery, H6.3 failure-limit->blocked (fixed 2 bridge bugs: auto-blocked->error + archived-orphan churn), H6.1 swarm fan-out->verifier->synthesizer. H4: 5 role-prefix Hermes profiles + /agent/delegate `role` (role=researcher -> worker under `-p researcher`). H5: classifier + task-surfacing verified live; H5.1 auto-delegate superseded by explicit delegation. H6.4: cache_prompt ON but clean amortization measurement blocked by PARALLEL=1 single-slot contention + a llama rc=-6 instability (supervisor-recovered) -> deferred. FLAG: investigate the EVO-X2 35B/Vulkan rc=-6 crashes. Full detail: changelog.md. EARLIER 06-20 1915: EVO-X2 H2d EXIT GATE PROVEN: drove EVO-X2 over SSH -- pulled to a18a78f, fixed the same qdrant-client venv gap, re-baselined [offline 18/18, doctor green incl. T1 with env_hermes], brought up the 35B on real Vulkan GPU under a persistent systemd --user daemon, verified Phase 1 + messages-path on GPU, then proved the full UNATTENDED H2d chain: delegate -> bridge -> dispatcher spawns 35B worker -> kanban_complete -> bridge mirrors ok+summary to /jobs [h2d-001/002/003 all ok]. Key fix: worker shell tool uses a clean PATH so `hermes` was exit 127 -> shell_init_files puts env_hermes/bin on PATH. EARLIER 1510: WINDOWS VERIFICATION PASS [Phases 1,2,3,6,7 live; thinking-model fixes; messages-path default; daemon.py + qdrant fixes; pushed a70fe90+cf79270]. Remaining: Phase 8 H3-H6 + kernel egress [needs root] + manual OpenWebUI click-test.)

## Boundaries (do not duplicate)

- `roadmap.md` (this file) -- owns the cumulative Item list and completion state.
  The "what exists / what's done / what's next, and how we prove it."
- `todo.md` -- short-term only ("just finished" / "next up"); points at Phase or
  Item IDs here, does not restate them.
- `changelog.md` -- records WHEN an Item or Exit Gate flipped state.
- `knowledge.md` -- architecture and scope (the "what it is / how it works").
  Phase numbers and the architecture descriptions live there; this file mirrors
  the numbering and tracks status + Exit Gates only.

Keep ASCII (see `WORKFLOW.md`). When an Exit Gate flips, bump the stamp here and
add a `changelog.md` entry.

## Terms (one word, one meaning)

To stop the term-soup, this file uses exactly four nouns. The retired synonyms
("track", "milestone", "stage", "leg") no longer appear -- if you see them in
older `changelog.md` / handoff entries, read them as "Item" or "Exit Gate".

- **Phase** -- a numbered level on the ladder (0 through 10). The unit that locks.
- **Item** -- a unit of work inside a Phase (the checkboxes). Each Item keeps a
  stable ID for cross-reference. Some IDs are historical family labels and are
  kept verbatim so old entries still resolve: `T0-T4` (Qwen3.6 swap + core
  integration), `H1-H6` (Hermes adoption), `M*` (single-model migration). Newer
  Items use plain `Phase.N` numbering (e.g. `9.0`). These IDs are labels only --
  NOT a second hierarchy above the Phases.
- **Exit Gate** -- the single testable pass/fail checklist that closes a Phase.
  Each line is its own check with a Status marker. (Retired words for this:
  "gate", "milestone".)
- **Status** -- the marker on any Item or Exit-Gate check:
  - `[x]` done / verified
  - `[~]` in progress
  - `[ ]` planned, not started
  - `[-]` deferred / optional (has a documented trigger; not on the critical path)

Phase numbers 1-8 match `knowledge.md` "Architecture roadmap".

PLATFORM SCOPE (Brandon, 2026-06-18). Phases 0-8 build a solid working foundation
on the two PRIMARY dev surfaces ONLY: Windows x64, and AMD Linux exercised via WSL
(CPU) on Daemonic-PC. Broader portability -- cross-arch (ARM64), cross-accel
(non-Vulkan), and other-hardware / EVO-X2-native GPU bring-up -- is deliberately
OUT of 0-8 scope. It is the multiplatform / troubleshooting CAPSTONE, folded into
Phase 9 (migration to EVO-X2 and other systems + the mesh) and Phase 10 (full-system
+ cross-host validation). Phase 0.5 is narrowed accordingly to the Windows<->AMD-Linux
(WSL) cross-OS foundation; this UNBLOCKS it from the former hardware-gated checks.

Phase 0 covers the runtime/dev-env foundation that precedes Phase 1; Phase 0.5 covers
the Windows<->AMD-Linux(WSL) cross-OS foundation; Phase 9 is an extended line beyond
the core ladder for migration + the decentralized node mesh (see
`docs/distributed_nodes.md`); Phase 10 is the full-system / feature-test + cross-platform
capstone. The 2026-06-14 numbering swap (mesh -> Phase 9, full-system test -> Phase 10,
CrewAI Phase 9 deleted) is now reflected in `knowledge.md` + `docs/distributed_nodes.md`
as well -- all three docs agree. The ladder is a FUNCTIONAL / dependency order, not work
order -- current execution focus lives in `todo.md` and can span Phases.

## Current position

Phases 0, 0.5, and 1 are GREEN. The single Qwen3.6-35B-A3B model serves LIVE on :8090
behind the companion API on :8000 (thinking mode under --jinja), on Windows and on
EVO-X2. WINDOWS VERIFICATION PASS 2026-06-20: Phases 2, 3, 6, and 7 were also verified
LIVE on Windows (35B/Vulkan) -- both primary surfaces now exercise the full 0-8 stack.
Thinking-model handling was hardened (the stack had been validated in WSL on the
non-thinking 7B): the persona reply path now defaults to the messages path
(PERSONA_USE_MESSAGES=1) for reliable thinking control on the 35B, the distiller suppresses
thinking, and the daemon's Windows-start bug was fixed. See Phase 1 T2.4 + changelog
2026-06-20 1510. Phase 0.5 -- NARROWED 2026-06-18 to the Windows x64 + AMD-Linux(WSL) cross-OS
foundation -- LOCKED GREEN 2026-06-18: both Exit-Gate surface checks pass (Windows x64
2026-06-07; AMD-Linux-via-WSL standalone manage.py lifecycle pass 2026-06-18). The
former ARM64 / non-Vulkan / EVO-X2-native checks that blocked it are relocated to the
Phase 9/10 capstone. Its model provisioner (P1-P4) is code-done; two non-gating Items
(per-OS egress baseline; cross-OS installer/doctor parity) remain as design-gated
follow-ups (need a Brandon decision).

Execution focus is working UP the 0-8 ladder on the two primary surfaces (Windows +
AMD Linux via WSL). Phase 8 (Hermes) foundation is started -- the taskboard<->kanban
bridge (H2) is validated end to end in WSL on a capable model (delegate -> run ->
mirror reaches status=ok + summary); the EVO-X2 H2d Exit Gate is now PROVEN (2026-06-20,
driven over SSH: status=ok+summary on the real 35B GPU via the unattended dispatcher path).
Phase 8 remaining: H3-H6, the kernel egress layer (root), and doctor revisit. See `todo.md`.

---

## Phase 0 -- Foundation and portable runtime  [x] GREEN

Goal: a reproducible, offline-capable dev/run environment and a committed model.

- [x] T0 model swap to Qwen3.6 committed (T0.1 2026-05-18, T0.2 2026-06-03)
- [x] Interpreter decision: Python 3.11.9 embeddable (runs full stack incl.
      ChromaDB; `docs/py314_compatibility.md`)
- [x] Portable bootstrap: `scripts/bootstrap_portable_python.ps1` (+ `.bat`);
      full `services/api/requirements.txt` installs on 3.11.9, no source builds
- [x] Env config consolidation: `run/config.env` (THINKING_MODE_*, SAMPLING_*,
      RAG_ENABLED, ANONYMIZED_TELEMETRY); sourced after `llama-servers.env`
- [x] Dependency pins clean: `setuptools<82` (bootstrap), `posthog>=2.4.0,<3.0.0`
      (requirements) -- no install bounce, no posthog telemetry errors
- [x] Ops scripts modernized (`setup_native_stack.sh`, `init_profiles.sh`,
      `doctor.sh`) to single-server topology + 2-file profile convention

Exit Gate (MET):

- [x] bootstrap installs the full stack with no source builds
- [x] core import smoke test passes
- [x] the API process boots
- [x] the offline API suite (`tests/test_api_offline.py`) is green

## Phase 0.5 -- Cross-OS foundation (Windows x64 + AMD Linux via WSL)  [x] GREEN

GREEN 2026-06-18: both Exit-Gate surface checks are now green -- Windows x64
(2026-06-07) and AMD Linux via WSL (CPU, 2026-06-18: a clean standalone manage.py
status/doctor/up/test-health//chat/down pass in this WSL clone, Qwen2.5-7B on CPU).
Per the lock rule at the end of this Phase, that closes it. Two non-gating Items have
since progressed (2026-06-19): the per-OS egress baseline (design + Linux/Windows scripts
+ doctor report landed) and the installer .env decision (resolved + done); both are now
[~] with live / cross-distro verification owed. Neither is part of the Exit Gate or
blocks GREEN; tracked below and in `todo.md`.

Goal (NARROWED 2026-06-18): the stack runs identically on the two PRIMARY dev
surfaces -- Windows x64, and AMD Linux exercised via WSL (CPU) on Daemonic-PC --
through one launcher (`manage.py`), one config model, and one dependency posture.
Broader portability (ARM64, non-Vulkan accel, EVO-X2-native Linux+Vulkan GPU
lifecycle, other hardware) is OUT of 0-8 scope and RELOCATED to the Phase 9 migration
+ Phase 10 cross-host capstone (see the Exit Gate below and those Phases). Apple
(macOS / Apple Silicon / Metal) remains out of scope entirely. Full audit + support
matrix: `docs/portability_audit.md`.

- [x] /agent/run uses sys.executable (was literal python3; broke Windows portable)
- [x] Single cross-platform launcher `manage.py` (up/down/toggle/status/doctor/
      capabilities/test/panel) replacing the bash/ps1 split (no bash for core
      lifecycle). LIVE-VALIDATED on Windows (RX 9060 XT) 2026-06-07: toggle brought
      the full stack up on :8090/:8000 and tore it down cleanly; test playbook green
      incl. live /agent/run; web panel drove it. Pure stdlib. Bash lifecycle scripts
      archived to scripts/archive/ -- core lifecycle is now manage.py-only. Windows
      x64 VALIDATED 2026-06-07 (Daemonic-PC, RX 9060 XT): status/capabilities/doctor
      all green under portable 3.11.9 -- config.toml read, run/node_capabilities.json
      written, accel detect+select=vulkan; full live CLI lifecycle proven (up ->
      status -> doctor --deep -> test quick -> down -> clean). 2026-06-14: down/status
      hardened against the WSL stale-pidfile trap (resolve_live_pid + /health
      corroboration; tests/test_manage_pid.py; live-confirmed in WSL). 2026-06-18:
      a clean standalone WSL/AMD-Linux pass (status/doctor/up/test-health//chat/down,
      Qwen2.5-7B CPU) proved the full lifecycle on the second primary surface -- the
      launcher is now validated on both (Windows x64 + AMD-Linux-via-WSL). The
      EVO-X2-native / ARM64 / non-Vulkan live passes are relocated to Phase 9.
- [x] Dependency tiers: lean node = fastembed/onnxruntime default; torch +
      sentence-transformers become an opt-in extra. DONE 2026-06-06:
      requirements.txt lean (no sentence-transformers); opt-in
      requirements-embed-torch.txt; server.py EMBED_BACKEND selection +
      guarded sentence-transformers fallback + /health embedder_backend.
      VALIDATED Windows-side: AST OK + tests/test_api_offline.py ALL PASS
      (lean fastembed default proven). The sentence-transformers backend itself is
      only exercised once the opt-in torch extra is installed.
- [~] llama.cpp build/acquire matrix per accel (CUDA/ROCm/Vulkan/CPU, no Metal) +
      capability-advertising hook. Matrix DOCUMENTED 2026-06-06:
      `docs/llama_build_matrix.md` (prebuilt + source per accel, Win/Linux/ARM64,
      binary placement aligned to manage.py, build verify flow). Capability hook is
      DESIGNED there (descriptor schema + detection + `run/node_capabilities.json`),
      with a 3-tier accel classification (Tier 1 selectable CUDA/ROCm/SYCL/Vulkan/
      OpenCL/CANN/MUSA; Tier 2 in-progress; Tier 3 detect-but-never-select Hailo/
      Coral/Gaudi/Intel-NPU) + "select only what the binary supports". IMPLEMENTED
      2026-06-06 (changelog 2014): `manage.py capabilities` + detection layer +
      accel-aware `start_llama` (H3) + doctor accel section; Windows x64 VALIDATED
      2026-06-07 (capabilities + doctor green; node_capabilities.json written). The
      earlier capabilities `llama_build=null` flake was FIXED + verified-live 2026-06-07
      (`--version` probe bumped to 30s + one retry in llama_version_info; capabilities
      now reports b9219 -- see changelog/todo). Mesh wiring stays Phase 9.
- [~] H3 accel selection: `start_llama` backend-aware (no forced Vulkan on
      CUDA/ROCm/SYCL nodes); LLAMA_BACKEND override + capabilities detection.
      Done 2026-06-06; selection verified on the AMD/Vulkan host (selected=vulkan)
      2026-06-07. The "no forced Vulkan on CUDA/ROCm/SYCL" proof needs a non-Vulkan
      node and rides with the deferred Linux/ARM64 pass.
- [x] Cross-platform IPC decision (DONE 2026-06-06): NATS+JetStream is the primary
      control-plane bus (nats-server supervised as a Phase 3 daemon child, loopback,
      JetStream R=1) -- groundwork for the Phase 9 mesh -- with a stdlib loopback-TCP
      compatibility fallback, both behind one EventBus interface. Unix sockets ruled
      out (no asyncio AF_UNIX on the Windows ProactorEventLoop). See
      docs/ipc_decision.md.
- [~] First-run model auto-provisioning: on first launch, profile the host and
      consult a committed playbook (`run/model_playbook.toml`) that maps the
      resource envelope (RAM / VRAM / CPU / accel / arch) to a ranked, multi-family
      model catalog, then auto-download the best fit (huggingface_hub) and wire it
      into config.toml. Wide range: Raspberry-Pi-class / 8 GB CPU floor up to 96 GB
      unified / discrete-VRAM (Tier 4 primary = the committed Qwen3.6-35B-A3B).
      Vision capability is a PREFERRED (soft) requirement. DESIGN 2026-06-07:
      `docs/model_provisioner_design_20260607_2158.md`. Phased P1-P4. P1 (profiler:
      vram_mb/memory_model/NPU classify) + P2 (playbook + matcher,
      scripts/provision_match.py, 7/7) CODE DONE 2026-06-07. P3 (downloader + license
      gate + disk preflight + config wiring) CODE DONE 2026-06-18:
      scripts/provision_fetch.py + `manage.py provision [--dry-run/--yes/--model/
      --text-only/--write-config/--hf-token]` + tests/test_provision_fetch.py (30/30
      offline). Config wiring is OPT-IN (default prints the block; --write-config/--yes
      to apply) and targets the active per-host config.<host>.toml when one exists.
      LIVE-CONFIRMED 2026-06-18 on Daemonic-PC (RX 9060 XT): `provision --dry-run` ->
      qwen3.6-35b Q5_K_XL pick, weights [present] (0 MiB), per-host target
      config.daemonic-pc.toml [windows], vision off (no camera), nothing written.
      ctx SAFEGUARD landed 2026-06-18: provision preserves an existing effective
      PERSONA_CTX (host-validated) over the matcher's conservative guess (the
      tight-budget step-down had proposed 8192 on a host that runs 16384), printing a
      note; fresh hosts still take the safe conservative value. P4 CODE DONE 2026-06-18:
      cmd_up first-run hook (_maybe_first_run -> offer provisioning, or auto under
      `up --yes`; reload cfg after wiring; clean abort on decline/fail) + `up`
      --yes/--hf-token + setup_native_stack.sh AUTO_PROVISION=1 gate; tests 42/42.
      ALL FOUR PHASES P1-P4 now CODE DONE. Serving-side mmproj/VISION_ENABLED wiring
      also DONE 2026-06-18: start_llama passes `--mmproj <models/MMPROJ_PATH>` when
      VISION_ENABLED is truthy + the projector is present (gated so headless nodes stay
      text-only); doctor reports vision status; _truthy/_mmproj_args unit-tested
      (test_manage_pid.py). KV-AWARE CTX SIZING DONE 2026-06-19: replaced the crude
      0.85*budget step-down with a real KV-headroom estimate -- a stdlib GGUF metadata
      reader (provision_fetch.read_gguf_meta: arch/n_layers/n_head_kv/head_dim, header
      only) + kv_bytes_per_token (real ggml --cache-type-k/-v byte sizes, not invented
      constants) + max_ctx_for_budget (fits ctx to the free-for-KV pool: VRAM on full
      offload else RAM; clamps [min_ctx, ctx_default], floors to 1024). Two-stage:
      matcher keeps a pre-download guess; cmd_provision recomputes from the real GGUF
      after download. resolve_ctx precedence = existing-host-validated (capped to the
      GGUF fit) -> GGUF fit -> matcher guess. +23 offline checks (synthetic + real-GGUF
      validated: qwen2-7B 30464 B/tok). `--tier` flag RESOLVED (Brandon 2026-06-19): NOT
      needed -- selection is already hardware-driven (budget-fit + rank); the playbook's
      "Tier" headers are documentation, no manual taxonomy gate. OWED: Windows-side
      live-confirm of the `up` first-run path + a vision-model serving smoke.
- [~] Per-OS egress story: host firewall default-deny baseline (Windows + Linux);
      WireGuard mesh deferred to Phase 9; kernel netns/iptables worker-jail is the
      tighter Phase 8 layer. DECISION 2026-06-19 (Brandon): host firewall NOW, SCRIPTED
      (not auto-enforced by manage.py), allowlist = loopback + internet only during
      provisioning. LANDED 2026-06-19: docs/egress_baseline_design_20260619.md +
      scripts/egress_baseline.sh (nftables: plan/status/apply[--provision]/remove,
      root-guarded, established-first) + scripts/egress_baseline.ps1 (Windows Firewall;
      process-scoped default, -Strict host-wide) + a doctor read-only "Egress baseline"
      report (egress_posture, unit-tested). Windows PowerShell READ-ONLY paths VERIFIED
      2026-06-19 (PS 5.1.26100: -Plan / -Status / -Plan -Strict / -Plan -Provision all
      rc=0, valid output). OWED: live-apply test of the SERVE lock on a real box (Linux
      root, and Windows admin -Apply/-Remove); optional iptables (non-nft) fallback.
- [~] Cross-OS installer/doctor parity (Windows + Debian + other Linux). OPEN QUESTION
      RESOLVED 2026-06-19 (Brandon): KEEP manage.py's .env READ-fallback (portability
      hedge for a no-tomllib host) but STOP the installer writing it. DONE:
      setup_native_stack.sh no longer writes run/llama-servers.env by default (FORCE_ENV=1
      escape hatch retained; an existing file is left untouched). OWED: broader Debian /
      other-Linux installer + doctor parity passes (need those distros).

Exit Gate (one node bootstraps, runs, self-checks via doctor, and serves /chat
through one entrypoint with no bash for core lifecycle) -- on the two PRIMARY
surfaces only:

- [x] Windows x64 -- CPU + Vulkan (Daemonic-PC, 2026-06-07)
- [x] AMD Linux via WSL (CPU) -- `manage.py` lifecycle parity (status/doctor/up/down/
      test) green in the WSL clone. PROVEN 2026-06-18: a clean standalone pass --
      status, doctor (T1 safe-config + all checks green), up (llama 7B CPU + API, both
      /health responding), test health, /chat returned a real persona reply (no_think
      preset), down (clean teardown, no orphans, ports free). No bash; one entrypoint.

RELOCATED to the Phase 9/10 capstone (these no longer block 0.5):
- EVO-X2-native Linux x64 + Vulkan GPU lifecycle parity -> Phase 9 Item 9.0.
- Linux ARM64 bring-up -> Phase 9 (trigger: hardware available).
- non-Vulkan accel-selection proof (a CUDA/ROCm/SYCL node) -> Phase 9.
- cross-host behavioral parity across all surfaces -> Phase 10 Item 10.2.

0.5 LOCKED GREEN 2026-06-18: both primary-surface checks above are green.

## Phase 1 -- Core serving and companion API  [x] GREEN

Goal: a single local model behind the FastAPI companion API returns real
persona replies over both the native and OpenAI-compatible paths.

GREEN 2026-06-08: every Item below is `[x]` (M6 was the last to close) and the
Exit Gate was PROVEN 2026-06-07 (changelog 1222).

- [x] Unified llama-server topology on :8090; GPU offload verified (EVO-X2,
      49/49 layers, 4 slots, q8_0 KV)
- [x] Companion API on :8000: `/chat`, `/v1/chat/completions`, `/v1/models`,
      `/health`, `/`, `/favicon.ico`, `/jobs/{id}`
- [x] OpenAI-compat correctness: `stream` honored (SSE, [DONE]-terminated);
      `usage` reports real prompt/completion/total tokens
- [x] T2.1 per-mode sampling presets + thinking-mode toggle (resolve_think /
      sampling_for); /v1 still honors explicit request temperature
- [x] 2-file profile loader (SOUL.md / .hermes.md) applied to prompts
- [x] Global RAG wired (fastembed bge-small-en-v1.5 + Chroma global_memory) +
      memory distillation/writeback
- [x] /agent/run non-blocking (asyncio.to_thread) -- stopgap, pre-Task-Board
- [x] T2.2 thinking gate -- DECISION 2026-06-07 (Path A): keep the /think//no_think
      prefix on the raw /completion flow; add an OFF-by-default per-request
      triviality gate (THINKING_AUTO_GATE) that promotes a non-thinking-topic
      request to think when non-trivial. VALIDATED Windows-side: offline suite
      22/22 (real /chat + /v1 endpoints, gate logic live). The
      chat_template_kwargs/messages migration is folded into T2.4.
- [x] T2.3 preserve_thinking for Hermes-originated requests -- DONE 2026-06-07
      (Path A): preserve_thinking flag (req field + PRESERVE_THINKING_DEFAULT, off
      by default); split_reasoning() pulls in-band <think> out before sanitizing;
      preserve=true returns the answer un-sanitized + reasoning (`reasoning` on
      /chat, `reasoning_content` on /v1 incl. stream). VALIDATED Windows-side:
      offline suite 35/35. DESIGN NOTE: preserve mode also skips the lossy persona
      two-part sanitizer (agent loops want the full answer) -- revisit if persona
      formatting is ever wanted alongside preserved reasoning.
- [x] T2.4 --jinja messages migration -- CODE DONE 2026-06-07 (OFF by default,
      PERSONA_USE_MESSAGES). New query_llama_messages (POST /v1/chat/completions with
      chat_template_kwargs{enable_thinking}; parses content + reasoning_content +
      usage), build_persona_messages (system/user split, no /think prefix), and a
      persona_generate() helper that both /chat and /v1 call -- messages path when on,
      the proven raw /completion path (byte-identical) when off. LIVE VALIDATED
      2026-06-07 1746 (exit_gate_live [messages], PERSONA_USE_MESSAGES=1): reasoning
      came from the server reasoning_content and text was <think>-free. FOLLOW-UP DONE
      2026-06-08 0846: post-hoc sanitizer RETIRED on the messages path
      (PERSONA_SANITIZE_MESSAGES OFF-by-default escape hatch). Off-mount 72/72; raw
      /completion path unchanged. DEFAULT FLIPPED 2026-06-20 (cf79270): PERSONA_USE_MESSAGES=1
      is now the default (config.toml [runtime]; manage.api_env forwards it). On the thinking
      35B the raw /completion path errantly thinks even with /no_think and starves short
      replies (empty -> canned fallback ~1/3 of the time, measured live on Windows), while the
      messages path's enable_thinking reliably controls it: no_think 0/5 canned, think topics
      complete within the per-OS PERSONA_MAX_TOKENS budget (linux 4096 = 8192/slot, windows
      2048 = 4096/slot). Verified live on Windows 2026-06-20.
- [x] M6 single-model migration confirmed (M2b passed, M5 done) -- DONE 2026-06-08:
      EVO-X2 converged to Qwen3.6-35B-A3B-UD-Q5_K_XL on a fresh llama.cpp b9219 Vulkan
      build (old b8157 could not load qwen3_5_moe). Live-validated (/health green,
      thinking + reasoning_content via messages path, RAG live); Instruct-2507
      archived. Single model now on EVERY host (Windows + EVO-X2) per the 2026-06-07
      directive. config.toml [linux] committed + pushed from EVO-X2. See changelog
      1029. Build dep: spirv-headers (docs/llama_build_matrix.md). Tunable:
      PERSONA_MAX_TOKENS >= 4096 when thinking is on (raw default path unaffected).
- [x] Per-profile Chroma collections connected to the API -- CODE DONE 2026-06-07
      (OFF by default): RAG_PER_PROFILE routes memory_add/query to a per-profile
      collection ("mem_<profile>") via _get_collection; off = the single shared
      RAG_GLOBAL_COLLECTION exactly as before. LIVE VALIDATED 2026-06-07 1752
      (exit_gate_live [per-profile]): mem_alice/mem_bob collections created. CAVEAT:
      turning it on does not migrate existing global_memory rows. RESIDUE: the run
      also created untracked persona/profiles/alice/ + bob/ on disk -- gitignore or
      clean up.
- [x] Topic routing policy -- DONE 2026-06-07 (OFF by default): deterministic keyword
      classify_topic(text) + resolve_topic precedence (topic="auto" always classifies;
      explicit non-chat respected; "chat"/absent classifies only when TOPIC_ROUTING=1).
      Resolved topic drives thinking/sampling/RAG/inband downstream. VALIDATED: offline
      suite 56/56.
- [x] Task Board (`data/tasks.db`) replaces the in-memory jobs dict -- CODE DONE
      2026-06-07: stdlib-sqlite3 services/api/taskboard.py (init/task_set upsert-
      merge/task_get/task_list/delete/count + one-time jobs.jsonl migration); server
      wired (TASKS_DB config, init at startup, /agent/run records run->ok/error/
      timeout, /jobs list + /jobs/{id} from the board, /health task_store). LIVE
      VALIDATED 2026-06-07 1758: a real /agent/run recorded ok into the board; /jobs +
      /jobs/{id} returned the row with timestamps + returncode 0; /health
      task_store count=1.

Exit Gate (PROVEN 2026-06-07, changelog 1222, via tests/exit_gate_live.py):

- [x] llama-server live on :8090
- [x] `/chat` and `/v1/chat/completions` return real persona replies
- [x] a "chat" topic resolves no_think; science/coding/math/research resolve think
      (verify via `/chat` debug `sampling_preset`)
- [x] live `stream=true` produces SSE chunks + [DONE] and non-zero `prompt_tokens`
- [x] `/health` green with embedder_ok=true and chroma_ok=true

## Phase 2 -- Frontend and UX  [~] CODE-COMPLETE (2026-06-19; only a manual browser click-test owed)

Goal: a thin client over the API with durable conversation history.

- [~] OpenWebUI as thin client (port 3000). STOOD UP 2026-06-19: env_webui venv +
      open-webui==0.8.8 (pip route -- no docker on this box); scripts/start_webui.sh
      (AI_ROOT-relative) points OPENAI_API_BASE_URL at the API /v1. Serving on :3000
      (/health status:true) and WIRED -- OpenWebUI's startup GET /v1/models hit the API
      200. OWED: a human browser click-test (interactive admin signup) -- the only Phase 2
      step not doable headless.
      UPDATE 2026-06-22: live on EVO-X2 (0.9.6), LAN-bound, keyless DuckDuckGo web search ON
      (per-message toggle). Web-search-on-64K overflow FIXED: the persona persisted full web pages
      (injected into user turns while BYPASS was true) to conversations.db, and window_turns'
      HISTORY_MIN_RECENT floor dragged them into every request -> 112K-token overflow -> 500 ->
      model's "I can't browse" fallback. Fixed in windowing.py (max_turn_tokens/hard_cap_tokens caps;
      poisoned threads auto-recover) + a graceful ContextOverflowError -> 400 context_length_exceeded.
      THEN (0815) the request fit but the model still said "I can't browse": OpenWebUI injects the
      retrieved web data as a SYSTEM message (<context>...</context>) and the persona /v1 path dropped
      client system messages. Fixed: _v1_injected_context extracts <context> -> persona_generate
      external_context (grounded as authoritative). FINALLY (1850) the decisive one: OpenWebUI's
      get_sources_from_items IGNORES a web-search result's {type:"web_search", collection_name} as an
      "untrusted direct collection_name" unless BYPASS_RETRIEVAL_ACCESS_CONTROL=true (default false) --
      so chunks were stored but never injected. FIX (start_webui.sh): BYPASS_RETRIEVAL_ACCESS_CONTROL=
      true + RAG_SYSTEM_CONTEXT=true. WEB SEARCH NOW WORKS (verified: model answered with real web
      facts). Output format also made ADAPTIVE (defers to explicit per-message format requests). Saga =
      FOUR layers (BYPASS full-page / conversations.db poison+windowing / system-context drop /
      access-control gate). See changelog 2026-06-22 0640/0725/0815/1850.
      TUNING 2026-06-27: deeper retrieval (WEB_SEARCH_RESULT_COUNT 3->5, RAG_TOP_K 3->6) after a
      "latest news" query drew generic SEO pages; web search now DEFAULTS ON / context-based
      (PERSONA_WEB_SEARCH_DEFAULT=1 + an idempotent OpenWebUI patch -> the necessity check searches
      only when the question needs current info); + a persona helpfulness nudge (use thin results,
      don't refuse). See changelog 2026-06-27. FIX 2026-06-28: the patch used setdefault() which the
      browser's explicit web_search:false defeated (only manual-toggle searched); now ORs the flag
      with the default + the patch self-heals on upgrade. See changelog 2026-06-28 0115.
      INLINE-URL FETCH 2026-06-28 0200: pasted links are now READ (OpenWebUI's web_search only
      keyword-searches, never visits URLs in the message) -- scripts/webui_patches/persona_inline_urls.py
      + a middleware hook fetch them via /process/web and skip the keyword search that turn. Plus the
      persona DEFAULT response style is now fuller/well-developed (was "1 short paragraph"), still
      deferring to explicit brevity/format; PERSONA_MAX_TOKENS 192->800. See changelog 2026-06-28 0200.
      NECESSITY-CHECK TUNED 2026-06-28 0240: OpenWebUI's stock query-gen prompt is search-biased and
      fired failed searches on general-knowledge turns; start_webui.sh now exports a less-eager
      QUERY_GENERATION_PROMPT_TEMPLATE (search only for current/external facts). See changelog 0240.
      SELF-KNOWLEDGE 2026-06-28 0320: the project's own docs are chunked + embedded under kind
      project_doc (services/api/self_knowledge.py + POST /memory/ingest_self) so the persona reasons
      about its OWN architecture from fact (proven: it now cites daemon.py/Hermes/Qdrant/EVO-X2).
      STRUCTURED INTAKE prototype 0350: services/api/memory_intake.py + POST /memory/intake -- typed,
      schema-validated memory records (type/entities/date/confidence) with contradiction visibility;
      default distiller unchanged. See changelog 0320 + 0350.
      ECHO-CHAMBER FIX 0430: the distiller was storing the assistant's OWN proposals as USER facts
      (-> the model "defended the user's goals" and doubled down). memory_distiller.py DISTILL_PROMPT
      now has a provenance section (only user-stated facts); necessity check skips introspective/
      self-referential questions. Owed: purge the already-stored fabricated facts. See changelog 0430.
- [x] SQLite `conversations.db` as source of truth for history. STORE BUILT 2026-06-19:
      services/api/conversations.py (stdlib sqlite3, taskboard.py posture: conversations +
      turns tables, distilled/summary cols for windowing); server.py persists user+assistant
      turns on /chat (auto-creates + returns conversation_id), GET /conversations[/{id}] +
      DELETE reload/list, /health conversations block. tests/test_conversations.py 21 checks
      + live API persist/reload round-trip (4 turns, continuation, list). /v1 + UI
      conversation-id mapping DONE 2026-06-19: /v1/chat/completions now at parity with /chat
      -- HYBRID keying (explicit conversation_id wins; else an owui-<sha256[:16]> hash of the
      system+first-user prefix, with the OpenAI `user` field FOLDED INTO the hash to namespace it
      -- NOT used as the id directly; that was an audit bug, fixed 2026-06-20, that had merged a
      user's distinct threads), cold-thread seeding from the client array, windowed history from
      the DB (not the client array), user+assistant persist, conversation_id returned.
      tests/test_v1_history.py 29 checks +
      LIVE 2-turn (Qwen2.5-7B CPU): turn 2 recalled "teal" purely from reloaded DB history;
      4 ordered turns, no double-seed.
- [x] Persona task surfacing -- ALL THREE surfaces DONE 2026-06-19. Shared data: GET /tasks
      (tasks_summary: normalized board view) + server.py helpers (is_task_query gate,
      render_tasks_block). (1) IN-CHAT: tasks_block_for injects a live task-board block into
      the persona prompt when the message is task-related (threaded through build_persona_
      prompt/messages/persona_generate on /chat + /v1; TASKS_INCHAT_* config; /chat debug.tasks)
      -- LIVE: persona listed the 3 real board tasks. (2) OPENWEBUI TOOL: tools/openwebui/
      persona_tasks_tool.py (Tools class list_tasks/get_task, base-URL valve). (3) STATUS PANEL:
      manage.py panel gains a /api/tasks server-side proxy (API has no CORS) + a Task board
      section polling every 2s -- LIVE (proxy returned 3 tasks). tests/test_tasks_surface.py
      24 checks.
- [x] Hybrid conversation windowing -- DONE 2026-06-19: services/api/windowing.py
      (window_turns keeps newest verbatim within HISTORY_TOKEN_BUDGET, folds older into a
      summary; render_history_messages/_text for the two prompt paths; distilled turns
      contribute stored summaries, with a summarize() hook for the LLM distiller).
      Threaded through build_persona_messages/build_persona_prompt/persona_generate +
      /chat (windows PRIOR turns before recording the new one). tests/test_windowing.py
      16 checks + live 2-turn integration (turn 2's prompt carries turn 1). HISTORY_*
      config + /health + /chat debug.history.
- [~] Item 2a: migrate vector store ChromaDB -> Qdrant (Qdrant + fastembed are
      also the 3.14-unblock path). BUILT 2026-06-19: RagStore abstraction
      (services/api/ragstore.py: ChromaStore + QdrantStore, EMBEDDED local mode per
      Brandon -- on-disk, no server); server.py routes memory_add/query through it behind
      RAG_BACKEND (default chroma until live parity proven, then flip); scripts/
      migrate_chroma_to_qdrant.py (reuses stored vectors, no re-embed). VALIDATED:
      tests/test_ragstore.py (22 checks incl. Chroma<->Qdrant parity); real-data migration
      (4 collections / 61 points, exact counts); live server.py qdrant smoke (rag_ok, fact
      filter). DONE 2026-06-19: live parity proven (chroma vs qdrant top-3 identical across 5
      queries on the migrated 66-point corpus) -> RAG_BACKEND default FLIPPED chroma->qdrant;
      API restarts clean on qdrant (rag_ok, 4 collections). RAG_BACKEND=chroma still falls back.

Exit Gate:

- [~] a user holds a multi-turn conversation through the UI -- the /v1 path OpenWebUI
      calls is proven live (2-turn recall via DB history); browser click-test still owed
- [x] turns persist in `conversations.db` and reload correctly -- live on /chat and /v1
- [x] windowing keeps context within budget -- live (turn 2 recalled from reloaded history)
- [x] retrieval works against Qdrant with parity to the Chroma path -- live parity proven,
      RAG_BACKEND default flipped to qdrant

## Phase 3 -- Always-on daemon (daemon.py)  [x] COMPLETE on LoopbackBus (2026-06-19; NatsBus deferred to Phase 9)

Goal: one supervised entry point for all services.

Transport note (Brandon 2026-06-19): all Exit-Gate items are met on the stdlib LoopbackBus.
NatsBus + the nats-server child are DEFERRED to ride with the Phase 9 mesh unpark -- the
EventBus abstraction makes that a config swap, not a rewrite (docs/ipc_decision.md unchanged:
NATS stays the eventual default; LoopbackBus is the working single-host transport for now).

- [x] Single asyncio daemon with a child-process map -- DONE 2026-06-19: daemon.py
      (Supervisor + ChildSpec). Children run as REAL children (asyncio.create_subprocess_exec)
      so a death is seen instantly via proc.wait(). build_specs() wires llama-server + api
      from manage.py's shared argv builders (manage.llama_argv / api_argv, refactored out of
      start_llama/start_api so CLI + daemon spawn the byte-identical command). Writes
      run/<name>.pid so manage.py status/down stay compatible. (nats-server child: with NatsBus.)
- [x] Three-strike restart policy -- DONE: a dead child is relaunched; a child up longer than
      stable_reset_s (60s) is healthy and its strike count resets; after max_strikes (3) a
      further death STAYS DOWN. Live: killed the API child -> "restart 1/3" -> new pid -> /health
      200. Offline: a crash-looper gives up after exactly 4 starts (tests/test_daemon.py, 14 checks).
- [x] IPC bus (LoopbackBus) + API publishing -- DONE 2026-06-19. EventBus interface + stdlib
      LoopbackBus (services/api/eventbus.py: asyncio.start_server, length-prefixed JSON,
      shared-token gated, one-way fire-and-forget, never-block/never-raise; tests/test_eventbus.py
      12 checks). API publishes fire-and-forget via publish_event (server.py): task_ready on
      /agent/delegate + /agent/run, scheduled on the loop so it NEVER blocks/raises a request;
      /health eventbus block; tests/test_api_events.py 6 checks. LIVE E2E: /agent/delegate
      returned immediately AND the daemon logged "event task_ready: {...}". DEFERRED to Phase 9:
      NatsBus (nats-py, Core NATS) + nats-server child behind [ipc] transport=nats|loopback, and
      the remaining planned events (profile_switched, ingest_complete, tts_speaking).
- [x] Fresh-logs-on-start contract -- DONE: each child log truncated once at daemon start,
      restarts append (history preserved). Absorbs start/stop: SIGINT/SIGTERM -> graceful
      SIGTERM-then-SIGKILL shutdown of all children + bus (live: "all children stopped", ports freed).

Exit Gate:

- [x] daemon brings up and supervises all children -- live (llama + api, both /health 200);
      re-verified on Windows 2026-06-20 after fixing daemon.py's import-manage/sys.path bug that
      had blocked the daemon on the Windows embeddable Python (Phase 3 had only ever run on WSL)
- [x] killing a child triggers restart within policy; a fourth failure stays down -- live
      restart (API) + offline crash-loop give-up after 4 starts
- [x] IPC events deliver one-way (components -> daemon) without the API ever blocking on it --
      LIVE: /agent/delegate returned immediately while the daemon logged the task_ready event

## Phase 4 -- Embodied presence (Godot)  [-] OPTIONAL (persona side SCAFFOLDED 2026-06-20)

Goal: optional 3D/VR client driven by a two-channel protocol.

- [x] Persona emits RESPONSE (text/TTS) + STATE (JSON avatar directives) -- DONE 2026-06-20:
      services/api/avatar_state.py (derive_state: emotion/intensity/gesture/speaking/viseme, the
      STATE vocabulary; deterministic, dependency-free). /chat returns a `state` object alongside
      `text` (AVATAR_STATE_ENABLED), /health.avatar_state advertises the enums. Protocol:
      docs/avatar_protocol.md. tests/test_avatar_state.py 14 checks.
- [-] Godot client consumes the protocol -- the optional client (a 3D app) is not in this repo;
      the protocol + persona emitter are ready for it.

Exit Gate:

- [~] the avatar reflects STATE directives in sync with RESPONSE output for a scripted exchange --
      the persona STATE channel is live on /chat; the avatar-side sync is the (optional) Godot client

## Phase 5 -- Voice pipeline  [-] OPTIONAL (daemon wiring SCAFFOLDED 2026-06-20)

Goal: local speech in/out as daemon children (host-side compute only).

- [~] Whisper.cpp STT -- daemon child WIRED: daemon.py whisper_stt_spec() + stt_present() (guarded
      by binary+model; --with-voice / VOICE_DAEMON_ENABLED). Engine is host-provided (build
      whisper-server + a ggml model). docs/voice_pipeline.md.
- [~] Piper TTS (GPL-3.0) -- daemon child WIRED: daemon.py piper_tts_spec() + tts_present() (guarded;
      separate-process HTTP, GPL-3.0 respected). Engine + ONNX voice host-provided.
      tests/test_daemon_hermes.py covers the guarded spec building (None when absent; builds + both
      voice children included when the binaries/models are present).

Exit Gate:

- [-] spoken input is transcribed, answered, and spoken back end-to-end, fully offline -- needs the
      engines + an audio device on a host (headless WSL has no audio); the supervision wiring is done

## Phase 6 -- Auto-contextual RAG ("sorting line")  [x] COMPLETE (2026-06-19)

Goal: dropped files become retrievable, classified memory automatically.

All in services/api/sorting_line.py (pure pipeline; injected embed + RagStore, like
eventbus.py/conversations.py). tests/test_sorting_line.py 31 checks; live-proven on Qdrant.

- [x] `inbox/` file watcher -- API-hosted background poll loop (_inbox_watch_loop, server.py;
      stdlib, no watchdog dep; SORTING_LINE_WATCH/POLL_S/INBOX_DIR config). process_inbox scans
      inbox/, ingests, moves files to inbox/processed | inbox/failed, re-publishes ingest_complete
      on the loop. scripts/ingest_inbox.py is the one-shot/manual trigger.
- [x] Multi-format reader -- read_document: stdlib text family (txt/md/code/json/csv/html via
      html.parser), utf-8/utf-16/latin-1 fallback, size cap; optional pypdf/python-docx degrade
      gracefully (never a hard dep on the inference tier); unsupported/oversized/binary -> ok=False.
- [x] Semantic classifier + multi-bin routing -- classify(): deterministic keyword score per bin
      PLUS weighted cosine-to-prototype when an embedder is present (build_prototypes); DEFAULT_BINS
      = code/research/reference/personal/finance + misc fallback. Routes to the bin's collection.
- [x] Provisional/mature lifecycle with alias chains -- ingest lands in sl_<bin>__provisional;
      promote() graduates docs passing a trigger (default age_trigger) into sl_<bin> (mature) and
      deletes them from provisional; RagStore gained delete() + set_alias() (Qdrant alias; Chroma
      falls back). Alias sl_<bin>_current -> mature, queryable. LIVE: querying the alias hit the
      promoted doc.

Exit Gate:

- [x] a file dropped in `inbox/` is read, classified, and routed to the correct collection --
      LIVE: snippet.py -> sl_code__provisional, groceries.txt -> sl_personal__provisional
- [x] it is retrievable via RAG -- LIVE: semantic queries hit both docs
- [x] a provisional entry promotes to mature on the defined trigger -- LIVE: both promoted to
      sl_<bin> (mature), provisional emptied, retrievable from mature + via the alias

## Phase 7 -- Background consolidation ("sleep cycle")  [x] COMPLETE (2026-06-20)

Goal: idle-time memory maintenance.

Core in services/api/sleep_cycle.py (pure; injected convo/embed/store/distill, like
sorting_line.py). tests/test_sleep_cycle.py 14 checks; live-proven on Qwen + Qdrant.

- [x] Idle-triggered conversation distillation -- DONE: consolidate() pulls conversations with
      undistilled turns (conversations.py conversations_with_undistilled / undistilled_turns,
      new), distills each transcript -> facts + summary via the existing distiller template,
      stores facts to RAG, and mark_distilled()s the turns. server.py runs it from a background
      loop that fires only after SLEEP_CYCLE_IDLE_S of quiet.
- [x] Relationship discovery -- DONE: discover_links() records the k nearest existing memories
      to each new fact (embedding neighbours). Live: 4 + 2 links discovered across the two
      consolidated conversations.
- [x] Insight journaling -- DONE: build_insight() writes a per-conversation entry to the insight
      journal file (persona/global_memory/insight_journal.md) AND an insight RAG collection
      (insight_journal), both retrievable.

Exit Gate:

- [x] an idle period triggers a consolidation pass that distills recent conversations -- LIVE:
      after 5s idle, both undistilled conversations distilled (teal -> "favorite color is teal";
      the other -> the OpenWebUI/Qdrant tasks), undistilled count 2 -> 0; re-verified on Windows
      2026-06-20 after fixing the distiller (the 35B's <think> ate the token budget -> 0 facts;
      fixed with /no_think + <think>-strip + budget 96->256)
- [x] it links related memories and writes an insight journal entry -- LIVE: 2 journal entries
      (file + RAG collection, count=2, retrievable) with relationship-link counts
- [x] foreground responsiveness is not disrupted -- LIVE: a request during the window returned
      in 0.011s and reset idle; should_continue() stops consolidate() between conversations

## Phase 8 -- Agentic layer (Hermes Agent)  [~] H2d/H3/H4/H5/H6.1-6.3 PROVEN on EVO-X2 (2026-06-20/22); H6.4 (cache, deferred) + kernel egress (root) remain

Goal: Hermes runs as a daemon child pulling background work from the Task Board.
(Near-term in execution despite the late Phase number; depended on the Phase 1
single-model migration M6.)

- [x] T1: per-profile `config.yaml` safe-config (egress tools disabled, local
      model pinned, no cloud fallback) generated by `init_profiles.sh`; `doctor.sh`
      validates the default profile as the T1 check (implemented 2026-06-04).
      REGRESSION FOUND + FIXED 2026-06-18: Hermes' schema 0->28 migration (H1,
      2026-06-12) added 8 new auxiliary tasks (skills_hub/approval/mcp/title_generation/
      triage_specifier/kanban_decomposer/profile_describer/curator) with provider=auto,
      which the project-side safe-config gate (manage.py doctor) flags -- it requires
      auxiliary.*.provider=main (route all auxiliary inference to the local main model).
      Pinned them to main in persona/profiles/default/config.yaml; the doctor T1 gate is
      green again. The Hermes-side H1 validation (hermes config check) had passed; this
      is the separate project-side gate the migration silently regressed.
- [x] T1 close-out on a live host -- DONE 2026-06-12: hermes-agent v0.16.0 installed
      on EVO-X2 in `env_hermes/` (isolated/portable: uv + CPython 3.11.15 + editable
      clone ~/src/hermes-agent pinned 9b1e0d6f; no global mutations). env_hermes/bin/
      python exists -> detection satisfied. NOTE: NousResearch/hermes-agent installs
      via install.sh/uv, NOT `pip install hermes-agent`. Native Windows unsupported
      (WSL2 only) -> Hermes runs on EVO-X2.
- [x] H1: validate Hermes `config.yaml` key paths -- DONE 2026-06-12 (changelog 2311):
      against v0.16.0, HERMES_HOME resolves to the profile dir, model.sampling.default/
      thinking + tools.disabled all valid; config migrated in place 0->28 (safe-config
      preserved). Egress off via tools.disabled + API-key-gating + terminal.backend=
      local + browser.allow_private_urls=false + disabled_toolsets. Committed 70d7fb2.
- [~] H2: bridge taskboard.py <-> Hermes' native kanban. ARCH DECISION 2026-06-13
      (Brandon) = BRIDGE (taskboard.py / persona /jobs stay canonical; Hermes kanban =
      execution substrate; one loopback bridge on EVO-X2). Sub-items:
  - [x] H2a DESIGN (docs/h2_bridge_design_20260613_0204.md): public-CLI transport
        (kanban create/watch/runs --json, not raw DB), additive delegated/blocked
        statuses, job_id<->hermes_task_id correlation, Hermes owns retry.
  - [x] H2b: POST /agent/delegate writes a "delegated" row (no taskman2), /health
        delegate block, +~10 offline checks.
  - [x] H2c: tools/hermes_bridge.py (enqueue + mirror via Hermes public CLI, injected
        runner/board) + tests/test_hermes_bridge.py faked-CLI suite 44/44 ALL PASS;
        shapes confirmed via a source-dive into hermes-agent v0.16.0 @ 9b1e0d6f.
  - [x] H2 WSL validation: full chain delegate->card->claim->spawn->worker-runs->mirror
        confirmed LIVE in WSL (changelog 1458), then driven to status=ok + summary on a
        capable model (Qwen2.5-7B CPU; changelog 2112). The 1.5B floored on 0 tool
        calls = model-capability limit, not a bridge bug. Integration findings folded
        into knowledge.md + docs/wsl_h2_runbook_20260613_0311.md (default-assignee
        HERMES_HOME=ROOT; 64K ctx gate on main+aux; PERSONA_CTX/PARALLEL slot sizing;
        pin HERMES_KANBAN_HOME).
  - [x] H2d: DONE 2026-06-20 on EVO-X2 (real 35B + Vulkan GPU), driven over SSH. The full
        UNATTENDED chain proven: POST /agent/delegate -> bridge creates the kanban card ->
        `hermes kanban dispatch` spawns the worker -> the 35B worker runs the kanban-worker
        agent loop (tool calls) -> kanban_complete with a summary -> bridge mirrors ok+summary
        back to /jobs. THREE jobs landed status=ok + summary (h2d-001/002/003); dispatcher-
        spawned workers completed in ~105s (serialized on PARALLEL=1). This is the Phase 8
        Exit Gate evidence. KEY FIX: the worker's shell tool runs with a CLEAN PATH, so its
        `hermes kanban ...` calls hit exit 127 and floundered (the first dispatcher worker
        timed out); fixed by a shell_init_files entry (run/hermes_shell_init.sh) putting
        env_hermes/bin on the worker-shell PATH -> workers complete with no floundering.
        EVO-X2 H2d setup (runtime, EVO-X2-local): run/config.daemonic-evox2.toml (CTX 65536/
        PARALLEL 1 -- over-cautious; the worker prompt is ~750 tok not 20k, so PARALLEL=4 is
        fine), run/hermes.env pins, seeded persona/config.yaml (default-assignee root config),
        persona-daemon systemd --user service (survives SSH/logout via linger). Egress: config-
        level off (no provider keys, browser off, terminal local, llama loopback); kernel
        nftables layer still owed (needs root). FOLLOW-UPS: codify the PATH fix in
        init_profiles.sh (or env_passthrough:[PATH]); raise PARALLEL for worker concurrency.
        REBOOT-SURVIVAL DONE 2026-06-28: persistent ~/.config/systemd/user/{persona-daemon,
        persona-webui}.service enabled to default.target (linger -> auto-start on boot); refs +
        steps in scripts/systemd/, doc host_onboarding.md s9.
- [~] H2e SCAFFOLDED 2026-06-20 (WSL, all that can be done without the 35B/GPU): the
      persona-side H2 bridge now runs as a SUPERVISED DAEMON CHILD. daemon.py: hermes_present()
      + hermes_bridge_spec() (guarded by env_hermes/; launches env_hermes/bin/python
      tools/hermes_bridge.py --interval under the three-strike supervisor with HERMES_CLI/
      HERMES_KANBAN_HOME/HERMES_HOME/TASKS_DB env); build_specs(with_hermes=...) + `daemon.py
      --with-hermes` / HERMES_DAEMON_ENABLED (opt-in; default off so base behavior is unchanged).
      LIVE on WSL: the daemon spawned + supervised the bridge child (pid up, clean shutdown).
      tests/test_daemon_hermes.py 14 checks.
- [x] H3 standing dispatcher: the Hermes dispatch pass (manual in H2d) now runs as a
      SUPERVISED DAEMON CHILD. NEW tools/hermes_dispatch_loop.py (stdlib, mirrors the bridge)
      loops the SUPPORTED `hermes kanban dispatch` (reclaim stale + promote ready + spawn
      workers + `--failure-limit` auto-block) -- NOT `hermes kanban daemon` (v0.16.0
      DEPRECATED -> the messaging gateway, which needs an out-of-project systemd unit + creds,
      against the portability/egress rules). hermes_dispatcher_spec + build_specs supervise it
      alongside the bridge under one `--with-hermes` (the three-strike supervisor satisfies
      H3.1 daemon-child + H3.4; the 2026-05-10 spec's custom dispatcher/heartbeat H3.2/H3.3
      are Hermes-native under the 2026-06-13 bridge arch). CODE DONE + offline 18/18
      (2026-06-21); PROVEN LIVE on EVO-X2 the same day -- `manage.py daemon start --with-hermes`
      supervises FOUR children (llama/api/bridge/dispatcher); a hands-off POST /agent/delegate
      (NO manual dispatch) -> bridge card t_97ebe628 -> the dispatch loop spawned the 35B worker
      (spawned=[t_97ebe628]) -> kanban_complete -> bridge mirrored ok+summary to /jobs (~100s,
      attempts=1); daemon + both Hermes children persist across fresh SSH sessions. Also fixed
      the bridge log (flush=True) so the standing child is observable.
- [~] H4-H6 (GPU-bound -> EVO-X2). H3 + H4 + H5 + H6.1/6.2/6.3 DONE 2026-06-21/22; H6.4 deferred:
  - [x] H6.2 reclaim + recovery PROVEN live (killed worker mid-run -> dispatch loop reclaimed +
        re-dispatched in one tick -> /jobs ok, attempts=2).
  - [x] H6.3 failure-limit -> auto-block -> /jobs blocked PROVEN live (2 consecutive crashes ->
        auto_blocked=1). Surfaced + fixed two bridge mis-maps (auto-blocked mirrored as error;
        archived-orphan churn at running) -> derive_update treats settled columns
        (blocked/done/archived) as authoritative over a transient run outcome.
  - [x] H6.1 swarm fan-out -> verifier -> synthesizer PROVEN live (serialized on PARALLEL=1;
        synthesizer produced the combined output). Surfacing swarms via /agent/delegate is a
        later bridge feature (swarm cards are created directly, no /jobs row yet).
  - [x] H4 role-prefix template library: init_profiles.sh scaffolds 5 Hermes assignee profiles
        (researcher/critic/summarizer/coder/librarian = stable SOUL.md + .hermes.md prefixes,
        T1 safe-config inherited); POST /agent/delegate `role` -> assignee. cache_prompt defaults
        ON in llama.cpp. PROVEN LIVE 2026-06-22: delegate role=researcher -> worker ran under
        `-p researcher` -> ok, research-flavored reply.
  - [x] H5 server.py routing verify/close: H5.2 classifier (classify_triviality/THINKING_AUTO_GATE
        + topic routing + sorting_line) and H5.3 surfacing (GET /tasks + in-chat injection, proven
        live -- persona narrated the real board) already exist. H5.1 auto-delegate SUPERSEDED by
        the explicit role-delegation model (H4) -- auto-delegating chat queries is undesirable for
        a companion persona; explicit /agent/delegate is the clean path.
  - [~] H6.4 cache-amortization measurement: cache_prompt is ON, but a clean prefix-reuse
        measurement was not obtainable -- PARALLEL=1 single-slot contention + llama-server
        instability during the window (rc=-6 crashes, supervisor-recovered). Role-prefix
        KV-locality is gated on slot capacity + server stability; empirical 50-task hit-rate study
        DEFERRED to a multi-slot / role-batched config (Phase 9 scaling). FOLLOW-UP: investigate
        the 35B/Vulkan rc=-6 crashes on EVO-X2.
- [~] Runtime egress containment: DAEMON ENV HYGIENE DONE 2026-06-20 -- daemon.py sanitize_env()
      + ChildSpec.hygiene strip cloud/egress secrets (OPENAI/ANTHROPIC/AWS_*/AZURE_*/GOOGLE_*/
      LANGSMITH_* + a keyed list) from a supervised agent's env at launch; the hermes-bridge child
      runs hygiene=True. Proven with a real-subprocess test. STILL REQUIRED (host/root): the
      kernel netns/iptables half (scripts/egress_baseline.* applied live on the box).

Exit Gate:

- [x] Hermes runs as a daemon child -- DONE 2026-06-21 (EVO-X2): `--with-hermes` supervises BOTH
      the persona bridge (hermes_bridge_spec) AND the standing dispatcher (hermes_dispatcher_spec)
      under the three-strike supervisor; proven live + persistent across SSH sessions (H3)
- [x] it claims a Task Board task and executes it -- DONE 2026-06-20 (EVO-X2 35B+GPU): dispatcher
      claims the card + spawns the worker, which runs the kanban-worker agent loop on the 35B (H2d)
- [x] it writes results back for the persona to surface -- DONE 2026-06-20: bridge mirrors the
      worker's kanban_complete summary to /jobs (h2d-001/002/003 all status=ok + summary)
- [~] egress is contained at both config and kernel level -- config (T1 safe-config + no provider
      keys + browser off + terminal local + llama loopback) + the daemon env-hygiene runtime layer
      DONE; the kernel netns/nftables layer still host-applied (needs root; sudo unavailable to the
      remote agent)
- [~] `doctor.sh` is fully green -- EVO-X2 doctor green incl. T1 (env_hermes present). H3-H6 have
      landed (H6.4 cache-measurement deferred); still gated on the kernel egress layer (root) and a
      doctor revisit for the new standing dispatcher + role profiles + the llama rc=-6 stability item

## Phase 9 -- Decentralized cooperative node mesh  [ ] DESIGN (extended)

(Was Phase 10. The old Phase 9 was a deleted CrewAI placeholder, superseded by
Hermes in Phase 8; the slot now holds the mesh per the 2026-06-14 swap.)

Goal: system-agnostic nodes that run standalone and, when networked, pool
throughput and specialized capability BOINC-style. Depends on Phase 1 Task Board,
Phase 2 Qdrant (Item 2a), Phase 3 daemon. Full design + rationale:
`docs/distributed_nodes.md`. EVO-X2 is the mesh's anchor node, so its migration
(Item 9.0) is the precondition; the rollout Items 9.1-9.5 were formerly
"Stage 0-4" in `docs/distributed_nodes.md` (renamed here so "stage" no longer
collides with the orchestrator's `-Stage` flags).

MULTIPLATFORM HARDENING relocated from Phase 0.5 (2026-06-18): bringing the 0-8
foundation to EVO-X2 and other systems is exactly where cross-arch / cross-accel
portability is proven, so this migration line OWNS the formerly-0.5 checks --
EVO-X2-native Linux + Vulkan GPU lifecycle parity (Item 9.0), Linux ARM64 bring-up
(trigger: hardware), and a non-Vulkan (CUDA/ROCm/SYCL) accel-selection proof. The
cross-host BEHAVIORAL parity over these surfaces is validated in Phase 10 Item 10.2.

Decisions locked: distribute tasks not single inferences; NATS+JetStream with a
per-node server clustered as equals (3/5-node JetStream core for durable state,
ephemeral nodes as clients/leaf); shared-token admission with token-rotation as
the hard evict; self-generated per-node keys + NATS connection log ($SYS/connz)
+ TTL'd KV roster for identity/membership; validation/quorum + advisory key
deny-list for bad actors; WireGuard mesh for transport + egress containment.

- [~] 9.0: EVO-X2 migration -- consolidate the full stack onto EVO-X2 as the
      primary/anchor node (the endgame: everything on EVO-X2). In progress: EVO-X2
      already serves the Qwen3.6-35B (Vulkan, b9219) and has hermes-agent v0.16.0
      installed (env_hermes). Remaining: run persona + API + Hermes natively on EVO-X2
      as the canonical node (not via the WSL proxy), make it the source-of-truth
      dev/run surface, and prove the H2d Exit Gate there. Today the WSL clone is the
      primary dev surface as the closest EVO-X2 proxy and the D:\ repo is the redundant
      copy + Windows testbed + git gateway (see `WORKFLOW.md`). Also folds in the
      multiplatform hardening relocated from Phase 0.5: prove `manage.py` lifecycle
      parity on EVO-X2-native (Linux + Vulkan GPU), then Linux ARM64 (when hardware
      lands) and a non-Vulkan (CUDA/ROCm/SYCL) accel-selection proof.
- [ ] 9.1: `LLAMA_HOST` cross-node inference offload (no new infra)
- [ ] 9.2: 2-node NATS + JetStream work queue; claim -> execute -> result;
      clean reclaim on worker failure
- [ ] 9.3: connection log + self-gen node keys + KV roster; dynamic join +
      capability-aware routing. Includes the stable salted-system-spec node_id
      (manage.py first boot; bound to the keypair) -- see distributed_nodes.md sec 5.
- [ ] 9.4: 3-server JetStream core (R=3); reputation + deny-by-node-id +
      coordinated token-rotation evict (quorum-authorized, excluding the actor) +
      OOB re-key recovery for missed nodes; redundant-execution validation/quorum.
      Protocol in distributed_nodes.md sec 5b (opens: re-key quorum, cutover window,
      split-brain reconcile).
- [-] 9.5: WireGuard substrate; Object-store artifact transfer; superclusters
      at scale

Exit Gate:

- [~] the full stack (persona + API + Hermes) runs natively on EVO-X2 as the
      anchor node (Item 9.0)
- [ ] a node joins with only the shared token
- [ ] it appears in the roster by hostname+key with advertised capabilities
- [ ] it claims and runs capability-matched work and returns validated results
- [ ] a node loss reclaims cleanly; the durable core survives losing one member

## Phase 10 -- Full-system / feature test  [ ] NOT STARTED

Goal: prove the whole system works together, end to end, and keeps working -- a
capstone validation layer over every completed Phase, and a regression net as
features land. Runs on the canonical node (EVO-X2 once Phase 9 Item 9.0 lands);
the offline portions run on any host. Functionally last, but partial subsets can
run against whatever Phases are already green.

- [x] 10.0: One-command regression suite -- every offline suite
      (test_api_offline, test_hermes_bridge, test_manage_pid, test_provision_match,
      test_provision_fetch, + future) runs green from a single entrypoint on Windows
      x64 AND Linux x64.
      RUNNER BUILT 2026-06-14: tests/run_all_offline.py auto-discovers tests/test_*.py,
      runs each in its own process with the current interpreter, aggregates pass/fail.
      WINDOWS x64 GREEN 2026-06-14 1530 (portable 3.11.9): 4/4 suites PASS. LINUX x64
      GREEN 2026-06-18 (AMD-Linux via WSL, env venv 3.12.3): 5/5 suites PASS. Both
      primary surfaces green -> [x]. NOTE: this is only the hardware-free offline
      portion of Phase 10; the live / cross-host Items 10.1-10.5 remain and depend on
      Phase 9 (out of this scope).
- [ ] 10.1: Live system playbook -- a scripted end-to-end exercise on the canonical
      node: multi-turn conversation, topic routing + thinking mode, RAG recall +
      writeback, and an agent delegation round-trip (delegate -> Hermes runs ->
      /jobs ok + summary). Repeatable, pass/fail.
- [ ] 10.2: Cross-host parity -- the same playbook yields consistent behavior on
      Windows, EVO-X2, and a mesh node (incl. the cross-arch / non-Vulkan surfaces
      relocated from Phase 0.5); any difference is config, not code.
- [ ] 10.3: Resilience / failure injection -- daemon three-strike restart (Phase 3),
      mesh node-loss reclaim (Phase 9), and stale-pidfile recovery (manage.py) each
      recover within policy under deliberate faults.
- [ ] 10.4: Egress containment as a system check -- a delegated worker provably has
      NO outbound network (config + kernel level), verified at the system boundary,
      not just per component.
- [ ] 10.5: Performance baseline -- sustained-load throughput + latency captured on
      the canonical node and tracked against a target; regressions flagged.

Exit Gate:

- [ ] the one-command regression suite is green on Windows x64 + Linux x64
- [ ] the live system playbook passes end to end on the canonical node
- [ ] cross-host parity holds (behavior consistent across hosts)
- [ ] every failure-injection scenario recovers within policy
- [ ] worker egress containment is verified at the system boundary
- [ ] a performance baseline is captured and within target

---

## Extended / deferred (no active trigger)

- [-] Vision input
- [-] MTP / speculative decoding
- [-] Dual-memory unification (conversations.db + Chroma)
- [-] Next-gen Qwen (post-3.6) maturity re-evaluation after ~2026-08 (TODO #36).
      NOTE: Qwen3.6-35B-A3B is already the committed model; this is a forward-looking
      re-check of newer releases, not a pending adoption of 3.6.

## Cross-cutting components

These evolve across Phases rather than completing once (detail in `knowledge.md`
-> System components): Task Board (`data/tasks.db`), SQLite stores
(`conversations.db`), ChromaDB/RAG layer, NATS-based IPC (NATS+JetStream primary,
stdlib loopback-TCP fallback; Unix sockets were ruled out -- see Phase 0.5 IPC
decision). Their readiness is tracked inside the Phase whose Exit Gate first
depends on them (Task Board -> Phase 1/8; conversations.db -> Phase 2; IPC ->
Phase 3).
