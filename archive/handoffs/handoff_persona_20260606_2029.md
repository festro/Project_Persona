# Handoff -- Project_Persona -- manage.py bootstrap consolidation (Phase 0.5 + B/C)

Date: 2026-06-06 2029 PDT
Authors: Brandon + Claude
Scope: everything after handoff_persona_20260606_1138 (the manage.py launcher v1).
This session turned manage.py into the single cross-platform bootstrap, migrated
config to TOML, added detection + toggle + a test playbook + a web control panel,
validated the whole stack live on Windows hardware, and retired the bash lifecycle.
Status: ALL committed + pushed to origin/main (commits b75a853, then 5649466).
Working tree clean. Next session is forward-roadmap, not cleanup.

---

## 1. What shipped this session (in order)

Docs / design:
- `docs/llama_build_matrix.md` -- per-accel build + acquire guide (prebuilt +
  source: CPU/CUDA/ROCm/Vulkan/SYCL/OpenCL/CANN/MUSA, no Metal), binary placement
  aligned to manage.py, build-accept flow, and the capability-advertising hook
  design with a 3-tier accelerator classification.
- `docs/script_consolidation_review.md` -- full pre-commit audit of every config
  file + script vs the manage.py-as-bootstrap goal (C/H/M/L findings + the Phase
  A/B/C consolidation plan + the Phase C archive mapping).
- Accel detection scope broadened (Intel SYCL added as first-class; Hailo/Coral/
  Gaudi/Intel-NPU classified detect-but-never-select). `docs/portability_audit.md`
  support matrix updated.

manage.py (the bootstrap -- pure stdlib, single file at repo root):
- Host detection: `detect_accelerators` (3 tiers; vendor CLIs + an OS-GPU fallback
  via PowerShell Win32_VideoController / lspci so a GPU is seen even without vendor
  CLIs or vulkaninfo), `llama_version_info` (build + compiled backends via
  `--list-devices`), `select_backend` (select-only-what-the-binary-supports),
  `detect_ram_mb` (total AND available -- available nets out a ramdisk),
  `detect_host` -> the capability descriptor. `manage.py capabilities` writes
  run/node_capabilities.json.
- Per-host run profile: TOML config (below) + model auto-detect; backend-aware
  start_llama (only forces Vulkan flags when the backend is vulkan).
- `toggle` (start-if-down / stop-if-up), `test` playbook (named steps offline/
  health/smoke/load + sets quick/all + `test list`), and `panel` (below).
- GPU auto-fit: `GPU_LAYERS_PERSONA = "auto"` (or unset) -> OMIT `--n-gpu-layers`
  so llama-server fits the offload to VRAM itself.

Config -> TOML:
- `run/config.toml` is the typed single source, read via stdlib tomllib (3.11+).
  Structure [base] + [linux]/[windows] overlays + [runtime]; manage.py flattens
  [base]+[runtime]+[<os>] (OS wins) into the existing KEY names. Legacy run/*.env
  kept as a fallback (whitelisted overlays). Machine-written files stay JSON.

Web control panel (`manage.py panel`):
- stdlib http.server on 127.0.0.1:8765 (no deps, no Tkinter). Live status/health/
  capabilities dashboard + ONE relabeling Start/Stop button + Restart + the test
  runner. Endpoints: GET / , /api/status (cheap poll), /api/capabilities (cached),
  POST /api/action (worker thread, stdout captured to a live log, busy-lock).
- `--detach` runs it in the background (survives terminal close, run/panel.pid),
  `--stop` stops it; `manage.py status` lists `panel`.

Entry shims (repo root, ~thin, zero logic): `start-stop.sh`/`.bat` -> toggle,
`test.sh`/`.bat` -> test; `windows_portable_run.bat` rewritten to call
`manage.py up` (no more bash).

Phase A config-hygiene fixes (also this session): setup_native_stack.sh no longer
clobbers requirements.txt (installs -r the committed lean file; WITH_TORCH_EMBED=1
for the extra); server.py + win launcher port 8080->8090; --jinja added to the
(now-archived) Linux launcher; ggerganov->ggml-org; load_test port.

Phase C: archived 11 bash lifecycle scripts to scripts/archive/ (start_all,
stop_all, start_llama_servers, start_llama_server_win, start_api, stop_api,
stop_llama_servers, status, doctor, smoke_agent, unified_test). Core lifecycle is
manage.py-only now. Reference cleanup in setup_native_stack.sh + bootstrap ps1.

## 2. LIVE validation (the milestone)

On the Windows host (AMD Radeon RX 9060 XT 16 GB / Ryzen 9 9900X), via the panel
toggle and manage.py:
- llama-server up on :8090 (Qwen3.6-35B-A3B-UD-Q5_K_XL from the TOML windows
  overlay), API on :8000; clean toggle-down (incl. sweeping stale persona_win.pid).
- `manage.py test` green: offline suite + live /health + live /agent/run smoke.
- Real generation ~25.4 tok/s sustained over 1607 tokens; `thinking = 1` active
  under --jinja.
- GPU auto-fit confirmed: after the "auto" change, the old `n_gpu_layers set to 35,
  abort` warning is gone -- llama now fits the offload to the 16 GB card.
- Detached panel verified (survives terminal close; status shows it).

This closes the long-open "stand up Qwen3.6 on :8090" entry point and is the
live-host proof the launcher needed (Windows; Linux/ARM64 still to confirm).

## 3. Decisions locked this session

- Launcher stays Python (the node already needs Python; bundled interpreter runs
  everywhere; pure-stdlib). A Go/Rust static bootstrap is only worth it for a future
  Python-free inference-only node tier.
- Config format = TOML (stdlib tomllib, no deps) for human-edited config; JSON for
  machine-written artifacts.
- Accelerators are 3-tier: Tier 1 selectable (CUDA/ROCm/Intel-SYCL/Vulkan/OpenCL/
  CANN/MUSA), Tier 2 in-progress (Intel NPU OpenVINO, Hexagon, WebGPU), Tier 3
  detect-but-never-select (Hailo/Coral/Gaudi -- own runtimes, cannot load GGUF).
- GPU layers default to "auto" (let llama fit VRAM); Linux stays 999 (EVO-X2 full
  offload).
- --no-mmap NOT adopted: host RAM is ~21 GB usable (10 GB ramdisk of 31 GB), so the
  mmap default is the safe choice here.

## 4. Known issues / watch items

- The Linux sandbox mount serves STALE/TRUNCATED reads of D:\Projects files (hit
  repeatedly). Do NOT validate (AST/wc/md5/test) D:\Projects files from the sandbox;
  the Read/Edit/Write tools are authoritative, and real parses/tests must run
  Windows-side. (Memory: git-runs-windows-side.)
- Vulkan lacks the fused Gated Delta Net for this Qwen3.6 arch -> disabled, falls
  back (llama.cpp/Vulkan limitation, not ours). Possible perf cost.
- n_ctx_seq = 4096 = PERSONA_CTX 16384 / 4 parallel slots (vs 262K train). Tune
  PERSONA_PARALLEL / PERSONA_CTX in config.toml for longer single conversations.
- llama_version_info parses `--list-devices`; if a future build changes that output
  the compiled-backends field may go empty (selection then trusts detection).
- config.toml needs Python 3.11+ (tomllib). On <3.11 it falls back to the .env
  files (base only; OS overlay via .env is whitelisted but linux overlay file does
  not exist). The node standardizes on 3.11.9, so this is the intended path.

## 5. Checklist / roadmap (what's next)

Phase 0.5 (portability hardening) -- near done:
- [x] manage.py launcher + detection + toggle/test/panel (Windows live-validated)
- [x] Dependency tiers; [x] build matrix doc; [x] accel detection scope
- [ ] Linux x64 + Linux ARM64 live pass to flip the launcher to [x]
- [ ] Phase 0.5 #4: cross-platform IPC decision (loopback TCP vs NATS) BEFORE the
      Phase 3 daemon
- [ ] M5: `manage.py setup` absorbing portable_setup_win.sh + the Debian bits of
      setup_native_stack.sh -- removes the last bash (in the setup path)

Phase 1 (core serving) -- nearly there:
- Live /chat persona reply seen (the lizard answer); remaining gate proof: per-topic
  sampling (chat->no_think, science/coding/math/research->think via /chat debug
  sampling_preset), live stream=true SSE, and /health embedder_ok + chroma_ok.

Beyond: Phase 8 Hermes (H1 config.yaml schema validation), Phase 10 mesh (the
capability descriptor + node_capabilities.json are the Stage-0 groundwork).

## 6. State / how to run

- Clean working tree; origin/main at 5649466.
- Start everything:  `portable\python\python.exe manage.py up`  (or the panel:
  `manage.py panel --detach`, or double-click windows_portable_run.bat).
- Stop: `manage.py down` (or `toggle`). Status: `manage.py status`. Health/T1:
  `manage.py doctor [--deep]`. Tests: `manage.py test [step|set|list]`.
- Config: edit `run/config.toml`. Capabilities: `manage.py capabilities`.
- git runs Windows-side (portable git); do not run git or validate D:\Projects
  files from the sandbox.

## References
- `changelog.md` entries 2026-06-06 1902 through 2026-06-07 0323.
- `roadmap.md` Phase 0.5 / Phase 1; `todo.md` "Next options".
- `docs/llama_build_matrix.md`, `docs/script_consolidation_review.md`,
  `docs/portability_audit.md`, `docs/distributed_nodes.md`.
- `manage.py` (the bootstrap); `run/config.toml` (config).
