# Project_Persona -- Knowledge

Living reference for what Project_Persona is and how it works. See `todo.md` for
current state and `changelog.md` for history. Conventions: see `D:\Projects\WORKFLOW.md`.

Last updated: 2026-06-04 0755 UTC by Claude

## Elevator pitch

Project_Persona is a self-hosted, persona-driven AI companion stack. A single
local LLM (served by llama.cpp) sits behind a FastAPI companion API; a persona
layer presents results, an async Task Board carries background work, and a
ChromaDB/RAG layer plus SQLite stores give it memory. It is designed to run
fully offline on a single workstation and is released under AGPLv3 with a
Section 7 linking exception.

Repo: https://github.com/festro/Project_Persona
Target OS: Debian Linux. Daily driver: Windows. Reference hardware: GMKtec
EVO-X2 (AMD Ryzen AI MAX+ 395 / Radeon 8060S "Strix Halo", gfx1151, 96 GB
unified memory).

## Repo map

```
README.md                     external-facing project overview
README_models_hardware.md     model requirements, hardware tiers, sourcing guide
knowledge.md                  this file -- project reference
manage.py                     cross-platform launcher + bootstrap (up/down/toggle/status/doctor/capabilities/test/panel)
start-stop.{sh,bat} test.{sh,bat}  thin shims -> manage.py toggle / test
todo.md                       current short-term state
roadmap.md                    phased feature/completion tracker (status + gates)
changelog.md                  reverse-chronological history
WORKFLOW.md                   one-line pointer to D:\Projects\WORKFLOW.md
windows_portable_*.bat        zero-install Windows portable entry points
run/                          runtime config (config.toml primary, read via tomllib; llama-servers.env/config.env legacy fallback) + pidfiles + node_capabilities.json
scripts/                      setup/bootstrap + tests (init_profiles, setup_native_stack, bootstrap_portable_python, load_test); the bash lifecycle scripts were archived to scripts/archive/ (superseded by manage.py)
docs/                         design/reference notes (portability_audit, llama_build_matrix, distributed_nodes, py314_compatibility)
services/api/                 FastAPI companion API (server.py, memory_distiller.py)
services/chromadb/            ChromaDB RAG service code
persona/profiles/<name>/      per-profile identity; doubles as Hermes HERMES_HOME
persona/global_memory/        shared cross-profile Chroma vector store
models/                       user-provided GGUF files (gitignored)
data/                         SQLite stores + insights (conversations.db, tasks.db)
inbox/                        user file drop watched by the Phase 6 sorting line
llama_cpp/                    vendored llama.cpp source/build
portable/                     PortableGit + portable runtime (gitignored)
logs/                         per-service logs (wiped fresh on daemon start)
archive/                      superseded docs and cruft
archive/handoffs/             frozen dated handoff records
archive/pre-workflow/         pre-convention KNOWLEDGE.md / HANDOFF.md / HANDOFF.html
```

## Architecture

### Topology

Single unified llama-server instance serves all roles. Role differentiation is
done at the prompt layer (thinking-mode toggle, sampling parameters, system
prompt selection) rather than by routing to separate model servers. The earlier
multi-server split (persona 8080 + reasoning 8081 + coder 8082) is retired.

Request path: client -> FastAPI companion API (port 8000) -> unified
llama-server (port 8090). The API exposes OpenAI-compatible endpoints; a
front-end (OpenWebUI, currently dormant) connects through them.

API surface (verified against `services/api/server.py` 2026-06-05). The working
path is `/chat` (sync persona reply with RAG and optional in-band reasoning) and
`/v1/chat/completions` (OpenAI-compatible). The latter now honors the `stream`
field: when `stream=true` it emits Server-Sent Events as `chat.completion.chunk`
objects terminated by `data: [DONE]` (the reply is finalized through the sanitizer
first, then chunked -- a pseudo-stream, not token-by-token from the model);
`usage` reports real `prompt_tokens` (llama.cpp `tokens_evaluated`),
`completion_tokens`, and `total_tokens`. `/health` reports config and component
status; `/` returns a small status JSON (service/health/docs) and `/favicon.ico`
returns 204. `/agent/run` shells out to `tools/taskman2.py` via
`subprocess.run(timeout=300)` offloaded with `asyncio.to_thread`, so it no longer
blocks the event loop; it is a stopgap separate from the planned Task Board.
`/jobs/{id}` and `/v1/models` exist. The `/chat_submit` disabled stub was removed
2026-06-05 (the jobs persistence helpers remain for a future real async-job
implementation).

### Stable architectural decisions

Single-model topology (decided 2026-05-09). One Qwen3-30B-A3B-class MoE model
at Q5_K_M, served from one llama.cpp instance with parallel slots and continuous
batching. Chosen for fit to bandwidth-limited unified memory, a native
thinking-mode toggle that maps onto the persona/reasoning split, and a smaller
ops surface. Trade-off: loss of fault isolation between roles.

Hermes Agent as agent-work backbone (decided 2026-05-11, implementation
deferred). Hermes (Nous Research, MIT) runs as a daemon child, pulls work from
the Task Board, executes its own orchestration (fan-out / gather), and writes
results back. The persona layer surfaces results; it never coordinates. This
decision deleted the earlier AG2 (Phase 2.5) and CrewAI (Phase 9) plans and
reshaped the LangGraph agentic layer (Phase 8) into Hermes integration. Carries
a network-egress risk surface that must be contained by config plus
kernel-level enforcement (see Pointers -> egress handoff).

### System components

These are cross-cutting infrastructure with no completion state; they evolve as
the system grows.

Task Board (`data/tasks.db`). Persistent async work queue that replaces the
in-memory jobs dict. All background work (experts, ingest, sleep cycle, agents)
flows through it. The persona checks the board each response cycle and surfaces
READY results once, marking them SURFACED. Tasks are a self-ordering queue:
difficulty is auto-estimated at creation and recalibrated from observed
completion time. Schema carries Tenacity-style failure-semantics columns
(heartbeat, reclaim, attempt/max_attempts, validation_status) to support Hermes
worker recovery. Status enum: QUEUED, CLAIMED, RUNNING, VALIDATING, READY,
SURFACED, FAILED.

SQLite stores (`data/`). `conversations.db` holds full turns plus windowing and
distillation state. `tasks.db` is the Task Board. Both portable with the project
folder.

ChromaDB / RAG layer. Persistent vector store via fastembed with embedding
model `BAAI/bge-small-en-v1.5`. Global collection is wired; per-profile
collections exist on disk but are not yet connected to the API. Chunk and
collection metadata schemas support the Phase 6 sorting line and Phase 7
consolidation (alias chains, provisional/mature lifecycle, relationship links).
Qdrant is the planned replacement (Phase 2a).

Unix socket IPC. Daemon-owned single socket at `run/daemon.sock`, recreated on
each daemon start. Dependency is strictly one-way (components -> daemon); the
API never blocks on it. Current event: `ping`. Planned: `profile_switched`,
`ingest_complete`, `tts_speaking`, `task_ready`.

### Profile structure

Each profile lives at `persona/profiles/<name>/` and doubles as `HERMES_HOME`
for that profile (locked 2026-05-14). Two files using Hermes naming:
`SOUL.md` (identity, personality, communication style) and `.hermes.md` (hard
rules, output format, avatar STATE vocabulary; highest-priority Hermes context
file via tree-walk discovery). `MEMORY.md`, `USER.md`, and `memory/` are
Hermes-managed, gitignored, and excluded from sterilization.

Each profile also carries `config.yaml` (added T1, 2026-06-04): the Hermes-native
runtime config, generated by `init_profiles.sh` and safe-config-conformant by
construction (model pinned to the local llama-server, no cloud fallback, all
auxiliary tasks routed to the local main model, egress tools disabled, Qwen3.6
per-mode sampling). It is git-tracked (no secrets; Hermes secrets live in a
separate `.env`). `doctor.sh` validates the default profile's `config.yaml`
against the safe-config schema as the T1 acceptance gate. Exact Hermes key paths
for `model.sampling` and `tools.disabled` are schema-provisional pending H1
validation against the installed hermes-agent.

## Operational notes

Ports: companion API 8000, unified llama-server 8090 (moved from 8080 on
2026-05-19 to avoid a host-port collision with an unrelated co-tenant
container), OpenWebUI 3000 (dormant).

Unified llama-server config (verified working on EVO-X2): Qwen3-30B-A3B-Instruct
-2507 Q5_K_M, full GPU offload (49/49 layers on Vulkan0 / RADV GFX1151), 4
parallel slots at 8192 ctx each (32K total), q8_0 KV cache, Flash Attention on,
chat template auto-detected as Hermes 2 Pro. Vulkan backend reports bf16=0 on
this build, which does not affect Q5_K_M weights or the q8_0 cache but must be
flagged for any config that assumes bf16.

Runtime tunables live in `run/llama-servers.env` (llama-server flags) and
`scripts/start_api.sh` (API/reasoning vars). Consolidation into `run/config.env`
is underway: as of T2.1 (2026-06-05) `run/config.env` exists and holds the
thinking-mode (`THINKING_MODE_*`) and per-mode sampling (`SAMPLING_*`) tunables;
`start_api.sh` sources it after `llama-servers.env` (config.env overrides).
Sampling is no longer hardcoded -- server.py resolves think/no_think once
(`resolve_think`) and applies a matching `SAMPLING_PRESETS` preset
(temperature + top_p/top_k/min_p/presence_penalty) on `/chat` and
`/v1/chat/completions`; `/v1` still honors an explicit request `temperature`.
Defaults mirror the per-profile Hermes config.yaml (Qwen3.6 sampling guidance).
Target unified-topology values:

```
HOST=127.0.0.1
PERSONA_PORT=8090
PERSONA_MODEL=Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf
PERSONA_CTX=32768
GPU_LAYERS_PERSONA=999
PERSONA_PARALLEL=4
PERSONA_CONCURRENCY=4
CACHE_TYPE_K=q8_0
CACHE_TYPE_V=q8_0
THINKING_MODE_DEFAULT=auto
THINKING_MODE_TOPICS=science,biology,coding,math,research
API_PORT=8000
RAG_ENABLED=1
EMBED_MODEL=BAAI/bge-small-en-v1.5
```

Models are user-provided GGUF files in `models/` (gitignored, excluded from the
project license). Reasoning/thinking-mode env vars use canonical
`ASYNC_REASONING_*` / `REASONING_INBAND_*` names, with back-compat fallback to
the legacy `ASYNC_SCIENTIST_*` / `SCIENTIST_INBAND_*` names.

The `env/` directory is currently a transient symlink chain into a quarantined
legacy `~/Live/AIStack/` workspace; Project_Persona should eventually own a clean
Git-rooted venv. Not blocking.

Hermes runs in its own isolated `env_hermes/` venv (gitignored, same isolation
pattern as `env_webui/`), created by `setup_native_stack.sh` (SKIP_HERMES=1 to
skip). This keeps Hermes' dependency tree off the API venv. The daemon that
launches Hermes must set `HERMES_HOME` to the active profile dir and must never
inherit cloud credentials (see the egress handoff, Appendix A).

## Architecture roadmap

Planned shape changes, not immediate todos (those live in `todo.md`). This
section is the architectural description; per-phase completion status and test
gates live in `roadmap.md`.

Phase 1 -- Core API: largely in place (OpenAI-compatible endpoints, global RAG,
2-file profile loader, GPU offload). Remaining: per-profile Chroma, Task Board
replacing the jobs dict, topic routing policy.

Phase 2 -- Frontend and UX: OpenWebUI as thin client; SQLite conversation
history as source of truth; persona task surfacing; hybrid conversation
windowing. Phase 2a migrates the vector store from ChromaDB to Qdrant.

Phase 3 -- Always-on daemon (`daemon.py`): single asyncio entry point with a
child-process map, three-strike restart policy, Unix-socket IPC, and a
fresh-logs-on-start contract. Absorbs the start/stop scripts.

Phase 4 -- Embodied presence (Godot): optional 3D/VR client; persona emits a
two-channel RESPONSE (text/TTS) plus STATE (JSON avatar directives) protocol.

Phase 5 -- Voice pipeline: Whisper.cpp STT and Piper TTS (GPL-3.0) as daemon
children; host-side compute only.

Phase 6 -- Auto-contextual RAG ("sorting line"): inbox file watcher, multi-format
reader, semantic classifier, multi-bin routing, provisional/mature collection
lifecycle with alias chains.

Phase 7 -- Background consolidation ("sleep cycle"): idle-triggered conversation
distillation, relationship discovery, ontology maintenance, insight journaling.

Phase 8 -- Agentic layer (Hermes Agent): Hermes as daemon child pulling from the
Task Board with Tenacity-style failure semantics, role-prefix template library,
and cache_prompt amortization. Reshaped from the original LangGraph design.

Phase 9 -- DELETED (CrewAI candidate superseded by Hermes).

## License

Project_Persona is released under AGPLv3 with a Section 7 linking exception. The
linking exception lets external components (models, frontends, tools, APIs)
interact with the project without triggering license propagation. Model files
are excluded from the project license: they live in gitignored `models/` and
users comply with each model's upstream license. Component licenses are clean
against AGPLv3 (llama.cpp, whisper.cpp, FastAPI, ChromaDB Apache-2.0, LangGraph
MIT, Hermes MIT, SQLite public domain, Qwen Apache-2.0, Piper GPL-3.0).
OpenWebUI (BSD-3 + branding clause) is a dependency, not redistributed; users
deploying at scale comply with its branding terms independently.

## Pointers

- Conventions spec: `D:\Projects\WORKFLOW.md`
- Distributed cooperative node mesh design (NATS+JetStream, BOINC-style; status +
  gates in `roadmap.md` Phase 10): `docs/distributed_nodes.md`
- Cross-OS/arch portability audit + action plan (Win+Linux, x86-64+ARM64,
  CPU/CUDA/ROCm/Vulkan; Apple out; status in `roadmap.md` Phase 0.5):
  `docs/portability_audit.md`
- Python 3.14 stack compatibility + recommended interpreter version (use 3.12 for
  full RAG; 3.14 is API-only, ChromaDB blocked): `docs/py314_compatibility.md`.
  Portable embeddable-python bootstrap: `scripts/bootstrap_portable_python.ps1`.
- Frozen handoff records: `archive/handoffs/` (dated). Future handoffs use the
  `handoff_persona_<YYYYMMDD>_<HHMM>.md` naming from the workflow spec; existing
  records predate that convention and keep their `HANDOFF_<date>_<time>_*.md`
  names.
- Pre-convention source docs (split into this file, `todo.md`, `changelog.md`):
  `archive/pre-workflow/KNOWLEDGE.md`, `.../HANDOFF.md`, `.../HANDOFF.html`.
- Hermes egress risk surface + safe-config recipe (Appendix A):
  `archive/handoffs/HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md`.
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/
- Model cards: https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507 ;
  https://huggingface.co/bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF ;
  https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF
