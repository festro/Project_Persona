# Project_Persona -- Script / Config Review for manage.py-as-Bootstrap

Status: REVIEW + action plan. Findings as of 2026-06-06.
Last updated: 2026-06-06 2213 UTC by Claude
Driver: pre-commit evaluation of every config file and lifecycle script, ahead of
consolidating the bash/ps1/bat sprawl into conditional logic with `manage.py` as
the single bootstrap that detects OS / arch / resources, runs a compatible stack,
and deactivates vestigial or incompatible components.

Keep ASCII (see `WORKFLOW.md`). Pairs with `docs/portability_audit.md` (the
why/what) and `docs/llama_build_matrix.md` (per-accel builds). Status flips go in
`changelog.md`.

## Target architecture (what we are building toward)

`manage.py` becomes the only entry point. On invocation it:

1. Locates the repo (self-locating; it already does this) and is the SINGLE source
   of AI_ROOT for every child process.
2. Detects host facts: OS, arch, available accel (CUDA / ROCm / Vulkan / CPU),
   present interpreter (portable vs venv), present GGUF model(s), and resources
   (RAM/VRAM, core count).
3. Selects a compatible profile: model file, ctx, n-gpu-layers, device/backend,
   embedder backend, thread count -- per host, not per hardcoded script.
4. Starts only the components that apply and skips/deactivates the rest (no
   scientist/dual-server, no torch tier on a lean node, no Vulkan flags on a CUDA
   node, no bash).

The findings below are the gaps between that target and the current tree. Severity
is from the consolidation's point of view (what will silently do the wrong thing),
not just "is it broken today."

## Findings by severity

### Critical -- will silently misbehave under a single bootstrap

C1. AI_ROOT default drift across scripts. Five different defaults exist:
- `start_all.sh`, `stop_all.sh`: `$HOME/Live/AIStack/Project_Persona`
- `start_api.sh`, `stop_api.sh`, `start_llama_servers.sh`, `status.sh`,
  `doctor.sh`, `init_profiles.sh`, `setup_native_stack.sh`: `$HOME/Git/Project_Persona`
- `start_llama_server_win.sh`: `/d/Projects/Git/Project_Persona`
- `server.py`: `~/AI`
- `manage.py`, `bootstrap_portable_python.ps1`: self-locating (correct)
Only the two newest entry points self-locate; the bash layer carries stale
guesses. Under the bootstrap model this MUST collapse to one rule: manage.py
computes AI_ROOT from its own location and exports it; nothing else guesses.
server.py's `~/AI` default in particular is wrong for every real host and only
works because a launcher always sets AI_ROOT first.

C2. setup_native_stack.sh REGENERATES services/api/requirements.txt inline, and
the inline copy is stale. It heredocs `fastapi/uvicorn/pydantic/httpx/chromadb/
tenacity/fastembed>=0.3.3` with NO `posthog>=2.4.0,<3.0.0` pin, NO `numpy` pin,
and none of the dependency-tier structure just landed. Running the Linux installer
silently overwrites the committed, carefully-pinned file -- reintroducing the
posthog-3 telemetry break and undoing Phase 0.5 #2. The Windows installer
(`bootstrap_portable_python.ps1`) does the right thing: `pip install -r` the
committed file. Fix: the installer must NEVER write requirements; install from the
committed `requirements.txt` (+ optional `requirements-embed-torch.txt`), same as
the ps1.

C3. Host-specific model/params are not detected; manage.py flattened two flows into
the Linux one. Reality is two profiles:
- Linux/EVO-X2 (via `run/llama-servers.env`): `Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf`,
  ctx 32768, n-gpu-layers 999 (full offload).
- Windows portable (hardcoded in `start_llama_server_win.sh` +
  `portable_setup_win.sh`): `Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf`, ctx 16384,
  n-gpu-layers 35 (partial offload for the Strix Halo iGPU).
`manage.py start_llama` reads PERSONA_MODEL/PERSONA_CTX/GPU_LAYERS_PERSONA from the
env for BOTH OSes. On a Windows host with the committed env it will look for the
Instruct-2507 file (absent there) and, if found, request ctx 32768 + 999 layers on
an iGPU -- wrong model and likely OOM/over-offload. This is the central bootstrap
gap: model + ctx + gpu_layers + device must be selected by host detection (or a
per-host env overlay), not a single shared env. The old win launcher dodged this
by ignoring the env and hardcoding its own values.

### High -- correctness/feature drift that survives consolidation if not fixed

H1. Port drift 8080 vs 8090. `start_llama_server_win.sh` defaults PORT=8080 and
`server.py` defaults PERSONA_PORT=8080, while `run/*.env`, `doctor.sh`,
`start_llama_servers.sh`, and `manage.py` use 8090. If the env is not sourced, the
API talks to 8080 but the server listens on 8090. One source of truth (the env,
injected by the bootstrap) + delete the 8080 fallbacks.

H2. `--jinja` missing on the Linux launcher. `start_llama_server_win.sh` and
`manage.py` pass `--jinja`; `start_llama_servers.sh` (Linux) does not. The
reasoning_content channel separation (T2.4) and the jinja chat template depend on
it, so the Linux bash path serves a subtly different model contract. The bootstrap
should always pass `--jinja` (manage.py already does); the bash launcher is the
outlier.

H3. Accel is hardcoded to Vulkan. Both bash launchers pass `--device Vulkan0` and
`export GGML_VK_VISIBLE_DEVICES=0` unconditionally; `manage.py` adds `--device
Vulkan0` on Windows only. On a CUDA or ROCm node these are wrong or inert. This is
exactly what host detection must drive: choose `--device`/visible-devices from the
detected accel (and the llama-server build's reported backend), or omit and let the
build default. Ties into the `docs/llama_build_matrix.md` capability hook.

H4. pidfile name divergence. Windows path writes `run/persona_win.pid`; Linux and
manage.py use `run/persona.pid`; `status.sh`/`doctor.sh` only check `persona.pid`.
A server started by the legacy Windows `.bat` is invisible to status/doctor and to
`manage.py status` (manage.py `down` does clean persona_win as a courtesy). Pick
one pidfile name regardless of OS.

### Medium -- cleanup that prevents future foot-guns

M1. llama.cpp clone URL is the deprecated org. `setup_native_stack.sh` clones
`github.com/ggerganov/llama.cpp.git`; everything newer uses `ggml-org/llama.cpp`.
ggerganov currently redirects, but pin the canonical `ggml-org` URL.

M2. Naming half-migration: scientist -> reasoning. `start_api.sh` still exports
`ASYNC_SCIENTIST_ENABLED` + `SCIENTIST_*`; `server.py` reads
`ASYNC_REASONING_ENABLED` with `ASYNC_SCIENTIST_ENABLED` as back-compat;
`manage.py` passes `ASYNC_SCIENTIST_ENABLED`; `status.sh`/`stop_llama_servers.sh`
still reference scientist/reasoning/coder pidfiles. All vestigial of the retired
dual-server topology. Settle on the reasoning names and drop the scientist
aliases during consolidation.

M3. Two interpreter strategies. Linux installer builds a venv at `env/` from system
python3; Windows uses the `portable/python` embeddable. `doctor.sh`/`start_api.sh`
look for `env/bin/uvicorn`. manage.py's `find_api_python` already abstracts this
(portable -> env/Scripts -> env/bin -> running interpreter). Fine to keep per-OS,
but the bootstrap should be the only resolver; the bash assumptions retire with the
scripts.

M4. 3.14 fallback requirements are out of sync. `requirements-py314.txt` (core) and
`requirements-py314-rag.txt` (onnxruntime + fastembed, unbounded) predate the
dependency tiers and have no upper bounds. They are explicitly reference-only
(`docs/py314_compatibility.md`), but when 3.14 is revisited, regenerate them from
the tiered `requirements.txt` rather than hand-maintaining.

M5. Setup is still bash on Windows. `windows_portable_setup.bat` downloads
PortableGit then hands off to `portable_setup_win.sh` (bash) to fetch the llama.cpp
prebuilt + model. To make the node truly bash-free, the bootstrap eventually needs
a Python `manage.py setup` that absorbs `portable_setup_win.sh` (resolve latest
release asset, download, extract, hoist, fetch GGUF) and the Debian bits of
`setup_native_stack.sh`. Larger effort; flag now so it is planned, not discovered.

### Low -- cosmetic / known

L1. `load_test_m2b.py` DEFAULT_ENDPOINT still 8080 (already tracked in `todo.md`
housekeeping; move to 8090).
L2. `init_profiles.sh` sets `PERSONA_HERMES_MODEL=qwen3.6-35b-a3b` and the default
profile `config.yaml` carries `model: qwen3.6-35b-a3b`, while the Linux deployment
serves Instruct-2507. Cosmetic for a custom provider (the field is a passthrough
label), but inconsistent with the served model on Linux.
L3. OpenWebUI scripts (`start_webui.sh`/`stop_webui.sh`) are Phase 2 dormant; keep
but exclude from the core lifecycle the bootstrap manages.

## What is already good (keep)

- Application code (`server.py`, `memory_distiller.py`, `taskman2.py`) is portable
  (pathlib/os/shutil.which; no platform branching). The drift is all in the ops
  layer, exactly as `portability_audit.md` found.
- `bootstrap_portable_python.ps1` is the model installer behavior: install from the
  committed requirements, self-locate the root, load env files, smoke-test imports.
- `setup_native_stack.sh` already has a CPU_ONLY / Vulkan capability probe (glslc
  check + CPU fallback) -- the right shape to lift into the Python detection layer
  (extend it to CUDA/ROCm).
- `init_profiles.sh` config.yaml generation is safe-config-conformant and
  idempotent; matches the doctor/manage.py validators.
- `portable_setup_win.sh` already resolves the latest `ggml-org` Vulkan asset and
  is idempotent + resumable -- good source material for `manage.py setup`.

## Consolidation plan (proposed)

Phase A -- pre-commit quick wins (low risk) -- APPLIED 2026-06-06 (changelog 1925):
- C2: make `setup_native_stack.sh` install `-r` the committed requirements; delete
  the inline heredoc.
- C3 (manage.py half): teach `manage.py start_llama` to pick model/ctx/gpu_layers
  per host (detect from `models/` + an OS overlay) instead of trusting the Linux
  env on Windows. This is in the uncommitted manage.py, so best fixed before it is
  committed.
- H1: drop the 8080 fallbacks (server.py PERSONA_PORT default -> 8090; win launcher
  PORT -> 8090 or env-only).
- M1: ggerganov -> ggml-org clone URL.
- L1: load_test endpoint 8080 -> 8090.

Phase B -- the bootstrap detection layer (the real consolidation) -- APPLIED
2026-06-06 (changelog 2014):
- Detection module in `manage.py`: os/arch, accel (3-tier; vendor CLIs + a
  PowerShell/lspci OS-GPU fallback + vulkaninfo), `llama-server --list-devices`
  compiled backends, models, RAM/cores. `manage.py capabilities` writes
  `run/node_capabilities.json`; `doctor` gained an Accelerators section.
- Per-host run profile via OS overlay (`run/llama-servers.<os>.env`) + model
  auto-detect (C3, Phase A). Backend-aware `start_llama` (H3): no forced Vulkan on
  non-Vulkan nodes (LLAMA_BACKEND override).
- status/doctor/start/stop already fully in manage.py. Remaining: retire the bash
  duplicates (Phase C).

Phase C -- retire / deactivate (the bash scripts manage.py now duplicates):

Mapping (retire once manage.py up/down is host-verified):

| bash script                | manage.py equivalent          | action  |
|----------------------------|-------------------------------|---------|
| start_all.sh               | manage.py up                  | archive |
| stop_all.sh                | manage.py down                | archive |
| start_llama_servers.sh     | manage.py up --llama-only     | archive |
| start_llama_server_win.sh  | manage.py up --llama-only     | archive |
| start_api.sh               | manage.py up --api-only       | archive |
| stop_api.sh                | manage.py down                | archive |
| stop_llama_servers.sh      | manage.py down                | archive |
| status.sh                  | manage.py status              | archive |
| doctor.sh                  | manage.py doctor [--deep]     | archive |
| smoke_agent.sh             | manage.py test smoke          | archive |
| unified_test.sh            | manage.py test health (+TUI dropped) | archive |

New entry points (2026-06-06, changelog 2213): `manage.py toggle` + the test
playbook (`manage.py test offline|health|smoke|load|quick|all|list`), with thin
shims at repo root `start-stop.sh`/`.bat` and `test.sh`/`.bat`. unified_test.sh's
interactive dialog/whiptail TUI is dropped (Linux-only, stale $HOME/Live paths +
8080-8082 ports); its health/convo checks live in `manage.py test`.

Keep (not lifecycle, or no Python equivalent yet): setup_native_stack.sh,
bootstrap_portable_python.ps1/.bat, portable_setup_win.sh, init_profiles.sh,
load_test_m2b.py (invoked by `test load`), regen_handoff_html.sh, clean.sh,
start_webui.sh/stop_webui.sh (Phase 2, out of core lifecycle).

Execution (git mv runs Windows-side; the sandbox mount corrupts the index):

```
git mv scripts/start_all.sh scripts/stop_all.sh scripts/start_llama_servers.sh scripts/start_llama_server_win.sh scripts/start_api.sh scripts/stop_api.sh scripts/stop_llama_servers.sh scripts/status.sh scripts/doctor.sh scripts/smoke_agent.sh scripts/unified_test.sh scripts/archive/
```

Then:
- Update `windows_portable_run.bat` to call `python manage.py up --llama-only`
  instead of the archived `start_llama_server_win.sh` (removes a bash dependency).
- Drop the now-redundant `-Run` path note in `bootstrap_portable_python.ps1` (point
  it at `manage.py up --api-only`).
- The scientist/reasoning/coder pidfile + SCIENTIST_* handling (M2) leaves with the
  archived stop/status scripts; nothing in manage.py carries it.

Deferred (own effort): `manage.py setup` absorbing portable_setup_win.sh + the
Debian bits of setup_native_stack.sh (M5) to remove the last bash dependency.

## Pre-commit recommendation

The uncommitted set is sound to commit EXCEPT for one item that is best fixed
before manage.py ships: C3 (manage.py would load the wrong model / over-offload on
a Windows host). C2/H1/M1/L1 touch already-committed bash + server.py and can be a
separate small "config hygiene" commit. Everything else is the planned Phase B/C
work, not a blocker.

## References

- `docs/portability_audit.md` (C1/H1 origin; support matrix).
- `docs/llama_build_matrix.md` (accel detection + capability hook for H3/C3).
- `roadmap.md` Phase 0.5 (#1 launcher, #2 tiers done; this review scopes the rest).
- `manage.py` (`repo_root`, `start_llama`, `find_api_python`, `api_env`).
