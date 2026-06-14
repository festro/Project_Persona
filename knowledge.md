# Project_Persona -- Knowledge

Living reference for what Project_Persona is and how it works. See `todo.md` for
current state and `changelog.md` for history. Conventions: see `D:\Projects\WORKFLOW.md`.

Last updated: 2026-06-07 1827 PDT by Claude

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
unified memory -- but the BIOS carves out a chunk as dedicated iGPU VRAM, so the
OS / `free -h` shows only ~62 GiB system RAM; size GPU memory from
`manage.py capabilities` vram_mb, system RAM from free separately. Ubuntu 24.04,
Python 3.12.3, ~/Git/Project_Persona, headless/SSH).

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
objects terminated by `data: [DONE]` (the reply is finalized via
`finalize_persona_reply` first -- sanitized or not per the path, see below -- then
chunked: a pseudo-stream, not token-by-token from the model);
`usage` reports real `prompt_tokens` (llama.cpp `tokens_evaluated`),
`completion_tokens`, and `total_tokens`. `/health` reports config and component
status; `/` returns a small status JSON (service/health/docs) and `/favicon.ico`
returns 204. `/agent/run` shells out to `tools/taskman2.py` via
`subprocess.run(timeout=300)` offloaded with `asyncio.to_thread`, so it no longer
blocks the event loop; it is a stopgap orchestration entry, narrower than the
planned Phase 3 daemon. As of 2026-06-07 it RECORDS each run into the Task Board
(running -> ok/error/timeout). `/jobs` (list) + `/jobs/{id}` and `/v1/models`
exist. The `/chat_submit` disabled stub was removed 2026-06-05.

Task Board persistence (2026-06-07): `services/api/taskboard.py` -- a stdlib
sqlite3 store at `TASKS_DB` (default `AI_ROOT/data/tasks.db`) -- replaces the old
in-memory jobs dict + `run/jobs.jsonl` event log. One row per job_id with a merged
JSON `state` + queryable `status` + timestamps; `task_set` upsert-merges. Fresh
connection per call + WAL (the API touches it from `to_thread` worker threads, so
no shared connection; file-backed by design). On startup `init_db` one-time
migrates an existing `jobs.jsonl` (kept only as the migration source). This is the
near-term store; the broader Phase 3/10 Task Board semantics build on it.

### Stable architectural decisions

Single-model topology (decided 2026-05-09; model locked 2026-05-15). One
Qwen3.6-35B-A3B MoE model (UD Q5_K_XL), served from one llama.cpp instance with
parallel slots and continuous batching, on EVERY host. Chosen for fit to
bandwidth-limited unified memory, a native thinking-mode toggle that maps the
"light casual chat" role (thinking off) and the "heavy lifting" role (thinking
on) onto one set of weights, and a smaller ops surface. Concurrency / sub-agents
(Hermes fan-out, Phase 8) run across the parallel slots of this single model, not
a second model. Trade-off: loss of fault isolation between roles.

Model lock history: M1 (2026-05-14) first picked Qwen3-30B-A3B-Instruct-2507, but
the 2507 release SPLIT the dual-mode model (Instruct-2507 = non-thinking only),
breaking the thinking-toggle premise. The 2026-05-15 re-eval moved to
Qwen3.6-35B-A3B, which restores `enable_thinking` and adds `preserve_thinking`
(maps onto Hermes delegation). Instruct-2507 was kept as the known-good
rollback-only fallback against two Qwen3.6 risks gated in T0: T0.1 (llama.cpp
`qwen3_5_moe` arch support -- load/generate) and T0.2 (tool-calling template
round-trip, needed for the Hermes/MCP agent path). BOTH PASSED -- T0.1 2026-05-18,
T0.2 2026-06-03 -- so Qwen3.6 is confirmed on the arch and tool-calling axes and
the Instruct-2507 fallback (no thinking mode) is not in use. (Had T0.2 alone
failed, the planned mitigation was a GBNF grammar, not the fallback.) The earlier multi-server persona/reasoning/coder split and
a two-distinct-model-files arrangement were both evaluated and dropped (either
defeats the single-model consolidation).

Hermes Agent as agent-work backbone (decided 2026-05-11, implementation
deferred). Hermes (Nous Research, MIT) runs as a daemon child, pulls work from
the Task Board, executes its own orchestration (fan-out / gather), and writes
results back. The persona layer surfaces results; it never coordinates. This
decision deleted the earlier AG2 (Phase 2.5) and CrewAI (the former Phase 9; that
slot now holds the node mesh after the 2026-06-14 renumber) plans and reshaped the
LangGraph agentic layer (Phase 8) into Hermes integration. Carries
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

Hermes bridge (`tools/hermes_bridge.py`, Phase 8 H2). The Task Board stays the
canonical board the persona surfaces; Hermes' own kanban is the execution
substrate for delegated work. `POST /agent/delegate` writes a `delegated` row
(no taskman2 run); the bridge (loopback, on EVO-X2) creates the Hermes card via
`hermes kanban create --json`, then mirrors the outcome back onto the same row
(`delegated -> running -> ok|error|timeout|blocked`) by reading
`hermes kanban show --json`. Transport is Hermes' public CLI, never raw kanban.db
writes; Hermes owns retry/circuit-breaker. Design + open questions:
`docs/h2_bridge_design_20260613_0204.md`.

Bridge validated LIVE in WSL 2026-06-13 (everything-in-WSL: llama 1.5B + API +
Hermes + bridge). The full chain works; integration constraints learned (apply on
EVO-X2; the sub-64K overrides are sim-only):
- Hermes resolves the "default" kanban assignee's HERMES_HOME to the ROOT (the dir
  holding `profiles/`), reading `<root>/config.yaml` -- NOT
  `profiles/default/config.yaml`. Seed `<root>/config.yaml` for the default
  assignee, or use NAMED profiles (`profiles/<name>/`) which Hermes resolves directly.
- Hermes enforces >=64K context on the MAIN model AND every auxiliary model
  (compression/decomposer/...), each detected separately; override per-model with
  `model.context_length` + `auxiliary.<name>.context_length` for smaller models.
- The served `PERSONA_CTX` is split across `PERSONA_PARALLEL` slots (per-slot =
  CTX/PARALLEL); a Hermes worker prompt is ~20k+ tokens, so it needs one large slot
  (`PERSONA_PARALLEL=1` or a big CTX).
- Pin `HERMES_KANBAN_HOME` so dispatcher + bridge share one board.
- The worker must drive a tool-calling agent loop (kanban_show/complete); a 1.5B
  model fails (0 tool calls). Use a capable model -- EVO-X2's Qwen3.6-35B is the
  target Hermes' 64K floor is built for. For a WSL completion check without the 35B,
  the committed per-host config `run/config.daemonic-pc.toml` selects a tool-calling
  small model (Qwen2.5-7B-Instruct-Q4_K_M, Apache-2.0; ctx 32K, PERSONA_PARALLEL=1)
  -- NOT a clone patch (see the per-host config note below). `wsl_h2_sim.ps1 -Stage
  model -PersonaModel <gguf> -ModelUrl <url>` only caches the gguf + reloads.
  Reproducible harness: `scripts/wsl_h2_sim.ps1` + `docs/wsl_h2_runbook_20260613_0311.md`.
  PROVEN 2026-06-13: the 7B drives the tool loop the 1.5B couldn't, but on CPU it is
  ~15-20 min/turn (re-prefilling the ~22k Hermes orientation prompt at ~18 tok/s),
  ~1-2h/task. GPU offload is NOT reachable in WSL2 for an AMD card -- WSL2 exposes only
  /dev/dxg, so RADV (needs /dev/dri) finds nothing and vulkaninfo shows only llvmpipe;
  the shipped llama.cpp is CPU-only. AMD GPU acceleration belongs on the EVO-X2 (real
  Ubuntu, /dev/dri, RADV), or a Windows-native llama-server + WSL Hermes split (WSL
  mirrored networking so model.base_url stays 127.0.0.1 for the safe-config gate).

SQLite stores (`data/`). `conversations.db` holds full turns plus windowing and
distillation state. `tasks.db` is the Task Board. Both portable with the project
folder.

ChromaDB / RAG layer. Persistent vector store via fastembed with embedding
model `BAAI/bge-small-en-v1.5`. The shared collection (`RAG_GLOBAL_COLLECTION`,
default `global_memory`) is always wired. As of 2026-06-07 per-profile collections
are connected behind `RAG_PER_PROFILE` (default OFF): when on, `memory_add`/
`memory_query` route through `_get_collection(profile)` to `mem_<profile>`, so each
persona retrieves only its own memory; off keeps the single shared collection and
prior behavior. Enabling does NOT migrate existing `global_memory` rows -- a
one-time per-profile migration is a follow-up. Chunk and collection metadata schemas
support the Phase 6 sorting line and Phase 7 consolidation (alias chains,
provisional/mature lifecycle, relationship links). Qdrant is the planned
replacement (Phase 2a).

NATS-based IPC. The Phase 3 daemon supervises a local nats-server (JetStream R=1,
loopback) as a child process and uses it as the control-plane bus; a stdlib
loopback-TCP transport is the compatibility fallback, both behind one EventBus
interface (see `docs/ipc_decision.md`). Chosen to lay groundwork for the Phase 9
NATS+JetStream mesh. Dependency is strictly one-way (components -> daemon); the
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
against the safe-config schema as the T1 acceptance gate. H1 VALIDATED 2026-06-12
against the installed hermes-agent v0.16.0: `model.sampling.default/thinking` and
`tools.disabled` are valid key paths (parsed verbatim), and `HERMES_HOME` resolves
config to the profile dir. The config was migrated in place to schema version 28
(additive; safe-config preserved). Egress is off via four independent layers:
`tools.disabled` + egress tools being API-key-gated (no provider keys set) +
`terminal.backend: local` + `browser.allow_private_urls: false` (+ coarse
`agent.disabled_toolsets`). See changelog 2026-06-12 2311.

## Operational notes

Ports: companion API 8000, unified llama-server 8090 (moved from 8080 on
2026-05-19 to avoid a host-port collision with an unrelated co-tenant
container), OpenWebUI 3000 (dormant).

Process liveness (2026-06-14; changelog 1407): a recorded pid is not trusted
alone -- in WSL it could read dead while /health was still up, so `status` once
lied ("stale pidfile") and `down` orphaned the live server. manage.py now
corroborates: resolve_live_pid() trusts the pidfile pid, else if /health is up
recovers the real pid from a /proc cmdline scan (pids_by_cmdline; Linux/WSL only,
no-op on Windows). `down` kills the resolved live pid (recovers an orphan with no
pidfile too); `status` reports the health-corroborated state. Reliable manual
checks remain /health + `ps ... gguf`; hard hammer `pkill -9 -f llama-server`.

Unified llama-server config: Qwen3.6-35B-A3B-UD-Q5_K_XL, full GPU offload, 4
parallel slots, q8_0 KV cache, Flash Attention on, `--jinja` (thinking-mode
chat template). LIVE on Windows / RX 9060 XT (16 GB) this week via manage.py
(build e7bd3b3 on llama-server b9219); GPU auto-fit omits --n-gpu-layers so the
model fits VRAM. EVO-X2 CONVERGED 2026-06-08: now runs the same Qwen3.6 on a fresh
llama.cpp b9219 Vulkan build (built from source -- prereq `spirv-headers`; see
docs/llama_build_matrix.md), at 8192 ctx/slot (32768/4), full offload. The prior
Instruct-2507 fallback (49/49 layers on RADV GFX1151) is archived in models/archive/
as rollback. Single model now on every host. Vulkan backends may report bf16=0, which
does not affect Q5_K weights or the q8_0 cache but must be flagged for any config that
assumes bf16. TUNABLE: with thinking ON (messages path / enable_thinking) the
PERSONA_MAX_TOKENS=192 default starves the answer (CoT eats the budget) -- raise to
>= ~4096 for thinking deployments; the default raw path (messages OFF) is unaffected.

Runtime tunables: `run/config.toml` is the primary typed source (base + runtime +
per-OS overlays), read by manage.py via stdlib tomllib (2026-06-06; changelog
2028). Per-host differences use a COMMITTED override `run/config.<host>.toml`
(2026-06-13), merged by manage.py AFTER [base]/[runtime]/[<os>], selected by
host_tag() (lowercased short hostname; PERSONA_HOST env overrides). Canonical
[linux] is the EVO-X2 35B target; run/config.daemonic-pc.toml is the CPU-WSL
exception (Qwen2.5-7B). This keeps the D:\ repo the single source of truth (both
hosts read committed config; no ephemeral clone patching -- the WSL clone is
disposable/derived). See `WORKFLOW.md` + `docs/workflow_patterns_review_20260613_2112.md`. The legacy `run/llama-servers.env` (llama-server flags), `run/config.env`,
and `scripts/start_api.sh` (API vars) remain as the .env fallback path. The
env-side consolidation that preceded the TOML migration: as of T2.1 (2026-06-05)
`run/config.env` holds the
thinking-mode (`THINKING_MODE_*`) and per-mode sampling (`SAMPLING_*`) tunables;
`start_api.sh` sources it after `llama-servers.env` (config.env overrides).
Sampling is no longer hardcoded -- server.py resolves think/no_think once
(`resolve_think`) and applies a matching `SAMPLING_PRESETS` preset
(temperature + top_p/top_k/min_p/presence_penalty) on `/chat` and
`/v1/chat/completions`; `/v1` still honors an explicit request `temperature`.
As of T2.2 (2026-06-07) an OFF-by-default thinking gate (`THINKING_AUTO_GATE`)
can refine the coarse topic bucket: `classify_triviality()` gives a deterministic
per-request verdict (keywords, length, code/multi-question cues) and, in the
`auto` path, promotes a non-thinking-topic request to think when non-trivial.
Explicit on/off and `THINKING_MODE_TOPICS` stay deterministic; gate off = prior
behavior. T2.3 (2026-06-07) adds `preserve_thinking` (req flag +
`PRESERVE_THINKING_DEFAULT`, off): `split_reasoning()` pulls the in-band
`<think>...</think>` out of the raw reply before the sanitizer runs (so the
persona surface is `<think>`-free by default once Qwen3.6 thinking fires); when
preserve is on -- intended for the Phase 3 daemon's Hermes-forwarded work -- the
answer is returned un-sanitized with the reasoning surfaced (`reasoning` on
`/chat`, `reasoning_content` on `/v1`). Topic routing (2026-06-07, off by default
via `TOPIC_ROUTING`): `classify_topic(text)` is a deterministic keyword classifier
and `resolve_topic` decides the effective topic -- `topic="auto"` always
classifies, an explicit non-chat topic is respected, and a missing/`chat` topic
classifies only when routing is on. The resolved topic then drives the
thinking/sampling preset, RAG kinds, and in-band reasoning selection. Generation
path (T2.4, off by default via `PERSONA_USE_MESSAGES`): both endpoints call
`persona_generate()`, which off keeps the raw `/completion` + `/think`-prefix flow
and on switches to `/v1/chat/completions` with `messages` +
`chat_template_kwargs{enable_thinking}` (needs `--jinja`); under
`--reasoning-format deepseek` the server returns reasoning in `reasoning_content`,
with `split_reasoning()` as the in-band fallback. Reply finalization (T2.4 payoff,
2026-06-08) runs through `finalize_persona_reply()` / `will_sanitize()`: the lossy
two-part `sanitize_persona_reply` is retired on the messages path (the server already
returns clean, format-following content there), so `/chat` + `/v1` return the content
as-is; `PERSONA_SANITIZE_MESSAGES=1` is an off-by-default escape hatch to re-apply it.
The raw `/completion` path always sanitizes (unchanged), and `preserve_thinking`
bypasses sanitizing on both paths. `/health` reports `persona_sanitize_messages`;
`/chat` debug reports `sanitizer_applied`.
Defaults mirror the per-profile Hermes config.yaml (Qwen3.6 sampling guidance).
The authoritative values live in `run/config.toml` ([base] + per-OS [linux] /
[windows] overlays); the block below is a flat reference. Note PERSONA_CTX is
per-OS: 32768 on linux/EVO-X2, 16384 on windows (= 4096/slot at PERSONA_PARALLEL=4,
a deliberate 16 GB VRAM fit -- this is the live `n_ctx=4096` seen in persona.log,
not drift). Reference values:

```
HOST=127.0.0.1
PERSONA_PORT=8090
PERSONA_MODEL=Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
PERSONA_CTX=32768
GPU_LAYERS_PERSONA=999
PERSONA_PARALLEL=4
PERSONA_CONCURRENCY=4
CACHE_TYPE_K=q8_0
CACHE_TYPE_V=q8_0
THINKING_MODE_DEFAULT=auto
THINKING_MODE_TOPICS=science,biology,coding,math,research
TOPIC_ROUTING=0
PERSONA_USE_MESSAGES=0
PERSONA_SANITIZE_MESSAGES=0
THINKING_AUTO_GATE=0
PRESERVE_THINKING_DEFAULT=0
API_PORT=8000
RAG_ENABLED=1
EMBED_MODEL=BAAI/bge-small-en-v1.5
```

Models are user-provided GGUF files in `models/` (gitignored, excluded from the
project license). PLANNED (Phase 0.5, see `roadmap.md` +
`docs/model_provisioner_design_20260607_2158.md`): a first-run auto-provisioner
that profiles the host and consults a committed playbook
(`run/model_playbook.toml`) mapping the resource envelope (RAM/VRAM/CPU/accel/arch)
to a ranked multi-family catalog -- Raspberry-Pi/8 GB floor up to the committed
Qwen3.6-35B-A3B at the top, vision-capable preferred -- then auto-downloads the
best fit (huggingface_hub) and wires it into config.toml, so a fresh host
self-configures without a manual model fetch. Reasoning/thinking-mode env
vars use canonical
`ASYNC_REASONING_*` / `REASONING_INBAND_*` names, with back-compat fallback to
the legacy `ASYNC_SCIENTIST_*` / `SCIENTIST_INBAND_*` names.

The `env/` directory is currently a transient symlink chain into a quarantined
legacy `~/Live/AIStack/` workspace; Project_Persona should eventually own a clean
Git-rooted venv. Not blocking.

Hermes runs in its own isolated `env_hermes/` venv (gitignored, same isolation
pattern as `env_webui/`). This keeps Hermes' dependency tree off the API venv. The
daemon that launches Hermes must set `HERMES_HOME` to the active profile dir and must
never inherit cloud credentials (see the egress handoff, Appendix A).
INSTALL (corrected 2026-06-12): hermes-agent = NousResearch/hermes-agent (MIT), a full
agent (TUI/gateway/skills/memory/MCP/cron/subagents) with its OWN kanban + dispatcher.
It does NOT install via `pip install hermes-agent` (the old setup_native_stack.sh path,
now wrong) -- use install.sh OR the portable path proven on EVO-X2: `uv venv env_hermes
--python 3.11` + `uv pip install -e ~/src/hermes-agent[all,dev]` from a pinned clone
(isolated, no global mutations). Native Windows is UNSUPPORTED (WSL2 only) -> the Hermes
node is EVO-X2. ARCH NOTE (H2): Hermes' native kanban (`HERMES_KANBAN_*`) likely
supersedes / should bridge the project's `taskboard.py` for agent work.

## Architecture roadmap

Planned shape changes, not immediate todos (those live in `todo.md`). This
section is the architectural description; per-phase completion status and test
gates live in `roadmap.md`.

Phase 1 -- Core API: largely in place (OpenAI-compatible endpoints, global RAG,
2-file profile loader, GPU offload). Per-profile Chroma, the Task Board replacing
the jobs dict, and topic routing policy are all DONE (2026-06-07). Remaining: M6
single-model migration sign-off (see `roadmap.md` Phase 1).

Phase 2 -- Frontend and UX: OpenWebUI as thin client; SQLite conversation
history as source of truth; persona task surfacing; hybrid conversation
windowing. Phase 2a migrates the vector store from ChromaDB to Qdrant.

Phase 3 -- Always-on daemon (`daemon.py`): single asyncio entry point with a
child-process map, three-strike restart policy, NATS-based IPC (local nats-server
child, loopback; loopback-TCP compat fallback), and a fresh-logs-on-start
contract. Absorbs the start/stop scripts.

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

Phase 9 -- Decentralized cooperative node mesh (extended): system-agnostic nodes
that run standalone and, when networked, pool throughput + specialized capability
BOINC-style (NATS+JetStream). EVO-X2 migration to the canonical/anchor node is the
precondition (Item 9.0). Reuses the slot of the deleted CrewAI Phase 9 (superseded
by Hermes in Phase 8) after the 2026-06-14 renumber. Design: `docs/distributed_nodes.md`.

Phase 10 -- Full-system / feature test: capstone end-to-end + regression validation
over every completed Phase -- one-command regression suite, live system playbook,
cross-host parity, failure injection, system-level egress check, performance baseline.

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
  gates in `roadmap.md` Phase 9): `docs/distributed_nodes.md`
- Cross-OS/arch portability audit + action plan (Win+Linux, x86-64+ARM64,
  CPU/CUDA/ROCm/Vulkan; Apple out; status in `roadmap.md` Phase 0.5):
  `docs/portability_audit.md`
- Python 3.14 stack compatibility + recommended interpreter version (DECIDED:
  Python 3.11.9 embeddable runs the full RAG stack; 3.14 is API-only, ChromaDB
  blocked): `docs/py314_compatibility.md`.
  Portable embeddable-python bootstrap: `scripts/bootstrap_portable_python.ps1`.
- Frozen handoff records: `archive/handoffs/` (dated). Future handoffs use the
  `handoff_persona_<YYYYMMDD>_<HHMM>.md` naming from the workflow spec; existing
  records predate that convention and keep their `HANDOFF_<date>_<time>_*.md`
  names.
- Pre-convention source docs (split into this file, `todo.md`, `changelog.md`):
  `archive/pre-workflow/KNOWLEDGE.md`, `.../HANDOFF.md`, `.../HANDOFF.html`.
- Hermes egress risk surface + safe-config recipe (Appendix A):
  `archive/handoffs/HANDOFF_2026-05-10_1738_agent-swarm-hermes-adoption.md`.
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/
- Model card (canonical): https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF
  (Qwen3.6-35B-A3B-UD-Q5_K_XL). Dropped fallback (no thinking mode):
  https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507 ;
  https://huggingface.co/bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF
