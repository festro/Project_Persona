# Project_Persona -- Cross-OS / Cross-Arch Portability Audit

Status: AUDIT + action plan. Findings as of 2026-06-06.
Last updated: 2026-06-06 1934 UTC by Claude
Driver: the system-agnostic node goal (roadmap Phase 10 mesh). A node must run on
any supported OS/arch, not just the Debian/Windows reference hosts.

Keep ASCII (see `WORKFLOW.md`). Action items are tracked in `roadmap.md`
Phase 0.5; status flips are recorded in `changelog.md`.

## Support matrix (target)

Supported:
- OS: Linux (Debian/Ubuntu reference; other distros best-effort) and Windows
  (portable flow). Other BSD/Unix best-effort.
- Arch: x86-64 and ARM64 (aarch64).
- Accel (can serve GGUF): CPU (always), NVIDIA CUDA, AMD ROCm/HIP, Intel GPU via
  SYCL, Vulkan (cross-vendor: NVIDIA/AMD/Intel, incl. Strix Halo). Best-effort/
  niche llama.cpp backends: OpenCL (Adreno), CANN (Ascend), MUSA (Moore Threads).
  Accelerator tiering + detection: `docs/llama_build_matrix.md`.

Detected but NOT a llama.cpp inference path (record as node capabilities for
non-LLM/mesh routing; never selected for llama-server): Hailo-8/10 (HailoRT),
Google Coral Edge TPU (TFLite), Intel Gaudi (SynapseAI), Intel NPU (OpenVINO; the
llama.cpp backend is in progress). These have their own runtimes and cannot load
GGUF.

Not a consideration (by decision):
- Apple macOS, Apple Silicon, and the Metal backend. No effort is spent on Apple
  compatibility and it is not tested. If something happens to work on Apple, fine
  -- but Apple is never a reason to add, change, or hold back anything, and we do
  not go out of our way to break it either. It simply is not weighed.

Note: ARM64 widens the dependency-build surface (some native wheels need a
toolchain on aarch64); see High findings.

## Summary

The application code is already portable. The weak links are the operational
shell around it (bash-only lifecycle), two heavy/native dependencies, GPU-backend
heterogeneity, and one POSIX-only design choice that is still on the drawing
board. None are dead ends; the highest-leverage fix is replacing the
bash/PowerShell launcher split with a single Python CLI.

What was combed: `services/api/*.py`, `tools/taskman2.py`, `scripts/*`,
`run/*.env`, `requirements*.txt`, and the IPC/GPU assumptions.

## Findings by severity

### Critical -- breaks on a non-Linux node today

C1. Ops/lifecycle layer is bash-only. Every start/stop/status/doctor/setup script
is `#!/usr/bin/env bash` (start_all, stop_all, start_api, start_llama_servers,
start_llama_server_win.sh -- the "Windows" launcher is itself bash -- status,
doctor, init_profiles, setup_native_stack, smoke_agent, unified_test,
regen_handoff_html). They assume bash + POSIX tools (`source venv/bin/activate`,
`curl`, `jq`, `sudo apt`). A non-Linux node can run the API via portable Python
but cannot bring the stack up or health-check it without Git Bash/WSL. This is the
top blocker for "any device is a node."
Fix direction: a single cross-platform Python launcher (`manage.py
up/down/status/doctor`) that owns lifecycle; keep thin OS wrappers only.

C2. [FIXED 2026-06-06] `/agent/run` spawned the worker as literal `python3`
(server.py), which fails on the Windows portable flow (interpreter is
`python.exe`, `python3` not on PATH). Changed to `sys.executable`. Verified by the
offline reachability test.

### High -- structural / dependency tax

H1. Heavy, platform-variable dependencies. `torch` (pulled only by
`sentence-transformers`, the FALLBACK embedder) is the most portability-fragile
dep: arch-specific wheels, CPU/CUDA/ROCm variants, the `setuptools<82` pin, and
thinner aarch64 coverage. `chromadb` also drags native builds (`chroma-hnswlib`
C++, `onnxruntime`).
Fix direction: make `torch`/`sentence-transformers` an OPTIONAL extra; default a
"lean node" to `fastembed`+`onnxruntime` only. Let the Phase 2a Qdrant migration
move the vector store out-of-process so the in-proc native footprint shrinks.

H2. GPU backend heterogeneity. llama.cpp is vendored, but each node needs its own
llama-server build matching its hardware (CUDA / ROCm / Vulkan / CPU) plus a
compatible GGUF -- there is no single artifact. This is inherent (inference hides
behind the HTTP API) but is a real per-node onboarding step.
Fix direction: document a build/acquire matrix per accel (no Metal), and surface
accel + model as node capabilities in the mesh capability schema.

### Medium -- do not paint into a corner

M1. Phase 3 daemon's planned Unix-socket IPC (`run/daemon.sock`) is POSIX-only;
Windows AF_UNIX support is patchy in Python. Decide on a cross-platform transport
(loopback TCP, or reuse NATS) BEFORE building the daemon, or it becomes
Linux-only.

M2. Installer/doctor parity. `setup_native_stack.sh` is Debian-specific (`apt`,
`/etc/debian_version`) and assumes the POSIX venv layout (`env/bin/activate` vs
Windows `Scripts\`); `doctor.sh` looks for `env_hermes/bin/python`. Fine as the
Linux installer, but there is no cross-OS equivalent. Folds into the `manage.py`
work (C1).

M3. Egress containment runtime half is Linux-only. The H1.6 netns/iptables
enforcement has no Windows equivalent. On a mixed-OS mesh, rely on the WireGuard
mesh + per-OS host firewall instead, and treat netns/iptables as a Linux-only
hardening bonus rather than the portable baseline.

### Low -- cosmetic, no runtime impact

L1. `run/persona_win.pid` naming; a `~/Git/...` path in `load_test_m2b.py`'s
docstring; `D:\...` paths in commit-guidance docs. Clean up opportunistically.

## What is already good

- `server.py`, `memory_distiller.py`, `taskman2.py` use `pathlib` / `os.path` /
  `os.getenv` / `expanduser` / `shutil.which`; no platform branching, no `win32`,
  no Unix-socket code in the running app.
- `AI_ROOT` etc. are env-driven; the bootstrap sets them explicitly.
- Portable embeddable Python is already the per-node interpreter strategy -- the
  right foundation for a Python-CLI launcher.
- NATS (the chosen mesh transport) is a single cross-platform Go binary; WireGuard
  clients exist on all supported OSes.

## Action plan (-> roadmap Phase 0.5)

1. [DONE] C2: `/agent/run` uses `sys.executable`.
2. Cross-platform launcher: `manage.py up/down/status/doctor` replacing the
   bash/ps1 split (absorbs C1 + M2). One entrypoint, no bash for core lifecycle.
3. Dependency tiers: default lean node = fastembed/onnxruntime; `torch` +
   `sentence-transformers` become an opt-in extra (H1).
4. [DOC DONE 2026-06-06] llama.cpp build/acquire matrix per accel
   (CUDA/ROCm/Vulkan/CPU, no Metal) + capability advertising hook (H2). See
   `docs/llama_build_matrix.md`. Remaining: implement `manage.py capabilities`.
5. Cross-platform IPC decision for the daemon/mesh (loopback TCP or NATS, not Unix
   socket) before Phase 3 (M1).
6. Per-OS egress story: WireGuard mesh + host firewall as the portable baseline;
   netns/iptables as Linux-only bonus (M3).

Exit gate (Phase 0.5): a node bootstraps, runs, self-checks (`doctor`), and serves
`/chat` on Windows x64, Linux x64, and Linux ARM64 -- with CPU plus at least one
GPU accel -- through one cross-platform entrypoint, with no bash required for core
lifecycle.

## References

- `roadmap.md` Phase 0.5 (status + gate), Phase 10 (mesh that depends on this).
- `knowledge.md` (architecture, egress posture, components).
- `docs/py314_compatibility.md` (interpreter choice + ChromaDB 3.14 block).
- `docs/distributed_nodes.md` (mesh design; capability advertising).
