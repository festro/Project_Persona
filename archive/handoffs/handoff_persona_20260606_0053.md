# Handoff -- Project_Persona -- roadmap.md + distributed-mesh design + portability audit

Date: 2026-06-06 0053 UTC
Authors: Brandon + Claude
Scope: everything after handoff_persona_20260605_2312 (which froze the API gap
fixes + env pins). This session added the phased roadmap, the decentralized
node-mesh design, and a cross-OS/arch portability audit with one code fix.
Status: all deliverables written and wired into the docs convention. One code
change (sys.executable) applied and parse-verified. Nothing committed yet.
Next: Phase 0.5 portability hardening is now the priority (Brandon's directive),
alongside the still-open Phase 1 live llama-server standup.

---

## 1. What this session produced (after 2312)

New docs:
- `roadmap.md` -- single source of truth for feature/track completion, as a phase
  ladder with a testable Exit Gate per phase. Phase 0 (Foundation, GREEN), Phase
  0.5 (portability hardening, IN PROGRESS), Phase 1 (core serving, IN PROGRESS),
  Phases 2-8 mirroring knowledge.md's architecture roadmap, Phase 9 deleted,
  Phase 10 (decentralized mesh, DESIGN/extended), plus Extended/deferred and
  Cross-cutting sections.
- `docs/distributed_nodes.md` -- design note for the decentralized cooperative node
  mesh (roadmap Phase 10).
- `docs/portability_audit.md` -- cross-OS/arch weak-link audit + action plan
  (roadmap Phase 0.5).

Docs boundary established (do not duplicate): `roadmap.md` owns status; `todo.md`
points at phase/track IDs; `changelog.md` records when a gate flips; `knowledge.md`
owns architecture. Pointers were wired into todo.md (header + rules), knowledge.md
(repo map + architecture-roadmap intro + Pointers), and WORKFLOW.md (project-local
fourth-file note).

Code change:
- `services/api/server.py` -- `/agent/run` spawned the worker as literal `python3`
  (fails on the Windows portable flow; interpreter is python.exe). Now uses
  `sys.executable` (+ added `import sys`). Parse-verified (full file 975 lines,
  AST OK). This is the only code change since 2312.

## 2. Decisions LOCKED this session (do not relitigate)

Distributed mesh (Phase 10):
- Distribute TASKS, not a single inference. Single-inference pooling across
  heterogeneous nodes is bandwidth-bound and off the table; pool throughput +
  specialization instead. Lean on redundant execution + result validation
  (BOINC/F@H style; both are coordinator/client, not P2P).
- Transport = NATS + JetStream. Every node runs its OWN nats-server, clustered as
  equals (no central broker; "embedded-coordinator-per-node"). Durable state on a
  3/5-node JetStream Raft core; ephemeral nodes attach as clients/leaf. JetStream
  work-queue ack/redelivery == the Task Board's reclaim/attempt semantics. MQTT was
  considered and dropped (control-plane only; no work-queue semantics).
- Auth = single shared admission token (personal-devices group; rotation is the
  hard evict). Identity/tracking layer on top: NATS connection log ($SYS/connz, by
  hostname) + self-generated per-node keypair (pubkey = node id, signs
  heartbeats/results) + TTL'd KV roster. Bad actors handled by validation/quorum +
  advisory key deny-list (auth keeps strangers out; validation keeps bad RESULTS
  out). Hostname is a human label, not a trust anchor.
- Egress reconciled by running the mesh over a WireGuard mesh (Tailscale /
  Netbird / headscale).

Portability (Phase 0.5):
- Support matrix: Windows + Linux, x86-64 + ARM64, CPU/CUDA/ROCm/Vulkan.
- Apple (macOS / Apple Silicon / Metal) is NOT A CONSIDERATION -- no effort spent,
  not tested, never a reason to add/change/hold back anything, and not
  deliberately broken either. Incidental compatibility is fine; it is simply never
  weighed. (Clarified by Brandon this session.)

## 3. Portability audit -- key findings (full detail in docs/portability_audit.md)

- Application code is already portable (pathlib/os.path/expanduser/shutil.which;
  no platform branching, no win32, no Unix-socket code in the running app).
- TOP blocker: the ops/lifecycle layer is bash-only (every start/stop/status/
  doctor/setup script is #!/usr/bin/env bash; even start_llama_server_win.sh is
  bash). A non-Linux node can run the API but not bring the stack up / health-check
  it without Git Bash/WSL. Fix: a single `manage.py up/down/status/doctor`.
- torch (via sentence-transformers, the FALLBACK embedder) is the heaviest,
  most arch-variable dep; chromadb drags native builds too. Fix: make
  torch/sentence-transformers an opt-in extra; default lean node to
  fastembed/onnxruntime; Qdrant (Phase 2a) moves the vector store out-of-process.
- GPU backend is per-node (each node needs its own llama.cpp build + GGUF for its
  accel; no Metal). Document a build matrix + surface accel/model as mesh
  capabilities.
- Phase 3 daemon's planned Unix-socket IPC is POSIX-only -> choose loopback TCP /
  NATS before building it.
- Egress netns/iptables is Linux-only -> WireGuard mesh + host firewall is the
  portable baseline; netns/iptables a Linux-only bonus.

## 4. Current state / verified

- Stack boots clean on the portable 3.11.9 (setuptools<82 + posthog<3 pins from
  earlier this session; no install bounce, no posthog telemetry errors).
- API offline test suite 15/15 (tests/test_api_offline.py, from 2312): /,
  favicon, /health, /v1/models, real prompt_tokens, SSE streaming envelope,
  /chat_submit removed.
- server.py parses clean after the sys.executable fix.
- NOT yet exercised live: end-to-end /chat with a model (needs llama-server on
  :8090). Unchanged from 2312.

## 5. NEXT SESSION -- entry points

PRIORITY (Brandon's 2026-06-06 directive) -- Phase 0.5 portability hardening:
1. `manage.py up/down/status/doctor` -- one cross-platform entrypoint that retires
   the bash-only lifecycle (absorbs the Debian-specific installer/doctor too).
2. Dependency tiers -- default lean node = fastembed/onnxruntime; torch +
   sentence-transformers become an opt-in extra.
3. llama.cpp build/acquire matrix per accel (CUDA/ROCm/Vulkan/CPU, no Metal) +
   capability-advertising hook.
Gate: a node bootstraps, runs, self-checks, and serves /chat on Win x64 / Linux
x64 / Linux ARM64 (CPU + one GPU accel) through one entrypoint, no bash for
lifecycle.

Still open from before (Phase 1):
- Stand up the Qwen3.6 llama-server on :8090 (Windows portable;
  start_llama_server_win.sh with --jinja; run FOREGROUND in a dedicated window --
  it does not survive `bash.exe scripts/...` from PowerShell). Then exercise live
  /chat + /v1 streaming + per-topic sampling (chat->no_think;
  science/coding/math/research->think via /chat debug sampling_preset).

Mesh (Phase 10) is extended; the only near-term piece is the Stage 0 LLAMA_HOST
offload experiment (point one node's API at another's llama-server; flip the
llama-server bind from 127.0.0.1) -- proves cross-node inference with no new infra.

## 6. Uncommitted files (git runs Windows-side -- the Linux mount corrupts the index)

    $env:Path = "D:\Projects\Tools\PortableGit\cmd;" + $env:Path
    cd D:\Projects\Git\Project_Persona
    git add services/api/server.py tests/test_api_offline.py roadmap.md ^
            knowledge.md todo.md changelog.md WORKFLOW.md ^
            docs/distributed_nodes.md docs/portability_audit.md ^
            scripts/bootstrap_portable_python.ps1 services/api/requirements.txt ^
            archive/handoffs/
    git status
    git commit -m "roadmap.md + distributed-mesh design + portability audit (Phase 0.5) + API gap fixes"

(The API gap fixes, bootstrap setuptools<82, and requirements posthog pin from
earlier this session may already be staged/committed -- check `git status` first.
The `^` line continuations above are cmd.exe style; drop them for PowerShell and
put the paths on one line.)

## 7. Pointers

- Status + gates: `roadmap.md` (Phase 0 / 0.5 / 1 ... 10).
- Mesh design: `docs/distributed_nodes.md`.
- Portability audit + matrix: `docs/portability_audit.md`.
- Architecture/scope: `knowledge.md`. Short-term state: `todo.md`. History:
  `changelog.md`. Prior handoff: `archive/handoffs/handoff_persona_20260605_2312.md`.

---

Frozen handoff record. Future revisions create a new dated handoff.
