# Project_Persona — Knowledge & Task Tracker
**Last Updated:** 2026-04-05 12:00 UTC
**Repo:** https://github.com/festro/Project_Persona
**Domain:** layonet.org | **Target OS:** Debian Linux | **Daily Driver:** Windows

---

## System State (Last Confirmed Working)

| Component | Status | Notes |
|---|---|---|
| llama-server (persona) port 8080 | ✅ Running | 35-layer GPU offload — Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf |
| llama-server (reasoning) port 8081 | ✅ Running | 45-layer GPU offload — Qwen2.5-14B-Instruct-Q5_K_M.gguf |
| llama-server (coder) port 8082 | ❌ Not implemented | Planned — model file TBD |
| FastAPI Companion API port 8000 | ✅ Running | uvicorn, OpenAI-compatible |
| /v1/chat/completions endpoint | ✅ Verified | OpenAI-compatible streaming — OpenWebUI connects here |
| /chat endpoint | ✅ Verified | Sync persona reply + optional async reasoning |
| /chat_submit endpoint | ✅ Verified | Async job submission — returns job ID for polling |
| /jobs/{job_id} endpoint | ✅ Verified | Job status + result polling — to be replaced by task board |
| /health endpoint | ✅ Verified | Reports per-server status |
| ChromaDB RAG | ⚠️ Partial | Global collection only — per-profile not yet wired to API |
| Reasoning quality guard | ✅ Present | looks_degenerate() + two-stage self-repair loop in server.py |
| Reasoning fallback to persona | ✅ Present | REASONING_FALLBACK_TO_PERSONA toggle — off by default |
| Async reasoning routing | ⚠️ Off by default | ASYNC_REASONING_ENABLED=0 — topics: science,biology,coding,math |
| Multi-profile folder structure | ⚠️ Partial | Profiles exist on disk — persona.md/system_rules.md not loaded by API yet |
| OpenWebUI | ✅ Running | Separate venv (env_webui/) — data at openwebui/ — port 3000 |

**Known Issues / Caveats**
- `build_persona_prompt()` is a placeholder — persona.md and system_rules.md not loaded by API yet
- Per-profile Chroma memory not wired — all reads/writes use global collection only
- Coder server not implemented — port 8082 referenced in spec but nothing exists yet
- Reasoning endpoint may emit raw `<think>` tag fragments
- ASYNC_REASONING_ENABLED defaults to 0 — reasoning expert off unless explicitly enabled

---

## License

Project_Persona is released under **AGPLv3 with a Section 7 linking exception**.

The linking exception allows external components — models, frontends, tools, APIs — to interact with Project_Persona without that interaction triggering license propagation to those components. Model files, OpenWebUI, and other dependencies each operate under their own licenses.

**Component license summary**

| Component | License | Compatibility |
|---|---|---|
| llama.cpp | MIT | ✅ Clean |
| whisper.cpp | MIT | ✅ Clean |
| FastAPI | MIT | ✅ Clean |
| uvicorn / httpx / pydantic | MIT / BSD | ✅ Clean |
| ChromaDB | Apache 2.0 | ✅ Clean |
| LangGraph | MIT | ✅ Clean |
| Godot Engine | MIT | ✅ Clean |
| SQLite | Public domain | ✅ Clean |
| Qwen2.5-14B-Instruct | Apache 2.0 | ✅ Clean — verify exact model card |
| Piper TTS (OHF-Voice/piper1-gpl) | GPL-3.0 | ✅ Compatible with AGPLv3 |
| OpenWebUI | BSD-3 + branding clause | ⚠️ Not redistributed — dependency only. Users deploying at scale must comply with branding terms independently |
| Meta-Llama-3.1-8B-Instruct | Meta Community License | ⚠️ Not part of repo — user provided. Subject to Meta's license independently |

**Model files are excluded from this project's license.** Models live in `models/` which is git-ignored. Users provide their own models and are responsible for complying with each model's upstream license.

---

## Models

Models are not included in the repository. Users provide their own GGUF files and configure `run/config.env` to point to them.

**Format requirement:** GGUF only. Obtain from HuggingFace or convert from PyTorch/SafeTensors using llama.cpp conversion scripts.

**Quantization guidance**
- `Q4_K_M` — good quality, lowest practical memory footprint
- `Q5_K_M` — better quality, moderate memory increase
- `Q8_0` — near-lossless, highest memory requirement

**Model roles and tested configs**

| Role | Port | Size | Quant | Tested With |
|---|---|---|---|---|
| Persona | 8080 | 7B–13B | Q4_K_M / Q5_K_M | Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf |
| Reasoning | 8081 | 14B–32B | Q5_K_M / Q8_0 | Qwen2.5-14B-Instruct-Q5_K_M.gguf |
| Coder | 8082 | 7B–14B | Q4_K_M / Q5_K_M | Not yet validated |

**Naming** — any filename. Set in `run/config.env`:
```
PERSONA_MODEL=your-persona-model.gguf
REASONING_MODEL=your-reasoning-model.gguf
CODER_MODEL=your-coder-model.gguf
```

**Hardware tiers**

| Tier | RAM | GPU | Config | Notes |
|---|---|---|---|---|
| Minimum | 16GB | None | Persona only | ASYNC_REASONING_ENABLED=0. Functional, slow on complex queries |
| Recommended | 32GB | None | Full stack CPU | All models loaded. Reasoning slow but functional |
| Comfortable | 32GB + 8GB VRAM | Discrete (Vulkan/CUDA) | Full stack + offload | Significant latency improvement |
| Tested | 96GB | AMD Ryzen AI APU (Vulkan) | 35+45 layer offload | GMKtec EVO-X2 |

---

## Runtime Configuration (run/config.env)
> Renamed from llama-servers.env — scope expanded to cover all runtime config.
> All tunables live here. Daemon reads on start. No hardcoded values in scripts or server.py.

```
# ── Network ──────────────────────────────────────────
HOST=127.0.0.1

# ── Persona server ───────────────────────────────────
PERSONA_PORT=8080
PERSONA_MODEL=Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
PERSONA_CTX=8192
GPU_LAYERS_PERSONA=35
PERSONA_MAX_TOKENS=192
PERSONA_TIMEOUT_S=120
PERSONA_CONCURRENCY=2

# ── Reasoning server ─────────────────────────────────
REASONING_PORT=8081
REASONING_MODEL=Qwen2.5-14B-Instruct-Q5_K_M.gguf
REASONING_CTX=12288
GPU_LAYERS_REASONING=45
REASONING_MAX_TOKENS=512
REASONING_TIMEOUT_S=600
REASONING_FALLBACK_TO_PERSONA=0
ASYNC_REASONING_ENABLED=0
ASYNC_REASONING_TOPICS=science,biology,coding,math

# ── Coder server (not yet implemented) ───────────────
CODER_PORT=8082
CODER_MODEL=coder.gguf
CODER_CTX=8192
GPU_LAYERS_CODER=0

# ── Common llama-server flags ────────────────────────
THREADS=0
BATCH_SIZE=512
UBATCH_SIZE=512
CACHE_TYPE_K=q8_0
CACHE_TYPE_V=q8_0

# ── API ──────────────────────────────────────────────
API_PORT=8000
RAG_ENABLED=1
RAG_TOP_K=6
EMBED_MODEL=BAAI/bge-small-en-v1.5

# ── OpenWebUI ────────────────────────────────────────
WEBUI_PORT=3000
OPENAI_API_BASE_URL=http://127.0.0.1:8000/v1
OPENAI_API_KEY=local-anything

# ── Daemon ───────────────────────────────────────────
SHUTDOWN_TIMEOUT=10
STRIKE_WINDOW=300
STRIKE_BACKOFF_BASE=5

# ── Idle detection ───────────────────────────────────
IDLE_TIMEOUT=1800

# ── Conversation windowing ───────────────────────────
IDLE_WINDOW_TIMEOUT=1800
TOPIC_SHIFT_THRESHOLD=0.35
MAX_WINDOW_SIZE=50

# ── Sorting line ─────────────────────────────────────
INBOX_PATH=inbox/

# ── Sleep Cycle ──────────────────────────────────────
CONSOLIDATION_SWEEP_DEPTH=500

# ── Task Board ───────────────────────────────────────
TASK_TIME_SCORE_WINDOW=100
TASK_SURFACE_PRIORITY_THRESHOLD=300
```

---

## System Components
> Cross-cutting infrastructure that every phase builds on.
> These are not phases — they have no completion state. They evolve as the system grows.

---

### Component: Task Board
> Persistent async work queue. Replaces the in-memory jobs dict in server.py.
> All background work flows through one place — experts, ingest, sleep cycle, agents.
> Persona never delegates or coordinates. It only surfaces completed results naturally.

**Philosophy**
- Persona is a presence, not a coordinator
- MoEs and agents pull work and write results independently
- Persona checks the board on each response cycle — surfaces results like notifications
- If user is absent when a result is ready, it waits and surfaces on next interaction
- Results surface once and are marked SURFACED — never shown again
- Attribution is neutral — "this came in while we were talking" not false first-person or internal exposure

**Self-Ordering Queue**
- Tasks ordered by estimated difficulty (low difficulty first)
- Difficulty auto-estimated at creation via lightweight embedding comparison
- Difficulty recalibrates over time using actual `time_score` from completed tasks
- Easy tasks complete fast, surface soon — heavy tasks run deep in background
- All async — persona never waits on any task

**Surfacing Behavior**
```
Result becomes READY
    → user present    → persona surfaces naturally in next response
    → user absent     → pending_surface = true, result waits
    → user returns    → pending results surfaced before responding to new input
    → surfaced        → status = SURFACED, never shown again

Surface priority
    → normal          → surfaced when contextually relevant
    → high            → floated to top of next interaction regardless of topic
```

**SQLite Schema — tasks table**
```
tasks
    task_id             → unique ID
    profile             → which profile owns this task
    source              → "user_request" | "sleep_cycle" | "ingest" | "agent"
    description         → what needs doing
    assigned_to         → "reasoning" | "coder" | "agent" | null
    difficulty          → estimated 1-5 (auto-assigned, recalibrates from time_score)
    status              → QUEUED | RUNNING | READY | SURFACED | FAILED
    created_at          → timestamp
    started_at          → timestamp
    result_ready_at     → timestamp
    completion_time     → seconds (result_ready_at - started_at)
    time_score          → normalized — low = fast = easier (feeds difficulty estimator)
    surfaced_at         → timestamp
    result              → completed output
    pending_surface     → true if user was absent when result became READY
    surface_priority    → normal | high
    error               → failure detail if status = FAILED
```

**Performance Log**
> Task board doubles as a performance profile over time.
> Query to see which task types run longest, which models handle what, where bottlenecks appear.

**Phase Touchpoints**
```
Phase 1  → replaces jobs dict; reasoning worker writes to task board
Phase 2  → persona checks task board on each response cycle; surfaces pending results
Phase 3  → daemon health monitor aware of task board state
Phase 6  → ingest worker creates tasks for classification jobs
Phase 7  → sleep cycle creates and consumes tasks for consolidation work
Phase 8  → LangGraph agent creates and consumes tasks
Phase 9  → CrewAI crew members write results to task board
```

---

### Component: SQLite Stores
> Two databases, both in `data/`. Both portable with the project folder.

**data/conversations.db**
```
conversations
    turn_id             → unique ID per exchange
    profile             → profile name
    timestamp           → turn timestamp
    user_message        → full user input
    assistant_response  → full assistant response
    window_id           → assigned when window closes (null until then)
    distilled           → false until Sleep Cycle processes
    distilled_at        → timestamp when processed
    summary_chunk_id    → reference to resulting RAG chunk
```

**data/tasks.db** — see Task Board schema above.

---

### Component: ChromaDB / RAG Layer
> Persistent vector store. Per-profile + global collections.

**Current state:** Global collection only wired. Per-profile exists on disk, not yet connected.

**Embedding model:** `BAAI/bge-small-en-v1.5` via fastembed

**Collections**
```
global_memory            → shared across all profiles
profiles/<n>/memory      → per-profile (not yet wired)
sorting_line/<slug>      → auto-created by Phase 6 ingest pipeline
```

**Chunk Metadata Schema**
```
source_type         → "conversation" | "ingest"
source_ref          → window_id (conversation) | filename (ingest)
ingest_at           → timestamp
collection_origin   → collection where chunk first landed
collection_current  → current collection slug
tags[]              → topic/domain tags, updated by Sleep Cycle
provisional         → true until parent collection reaches MATURE
rel_targets[]       → related chunk IDs (populated by Sleep Cycle)
rel_types[]         → relationship label per target
rel_confidence[]    → confidence score per relationship
rel_discovered_at[] → timestamp per relationship discovery
```

**Collection Metadata Schema**
```
current_slug        → active collection name
aliases[]           → ordered history of all previous names
status              → PROVISIONAL | MATURE | MERGED | SPLIT
created_at          → timestamp
last_renamed_at     → timestamp
merged_into         → absorbing collection slug (if MERGED)
split_from          → parent collection slug (if SPLIT)
```

---

### Component: Unix Socket IPC
> Daemon-owned. Single file at `run/daemon.sock`. Wiped and recreated on every daemon start.

**Current events**
```
ping        → API sends on every request (fire and forget)
```

**Planned extensions**
```
profile_switched    → idle detector resets, consolidation notes context change
ingest_complete     → consolidation worker can prioritize newly arrived chunks
tts_speaking        → avatar layer knows not to interrupt
task_ready          → task board notifies persona layer of completed result
```

**Rules**
- Daemon owns and binds socket on start
- API never blocks on socket — silently skips if unavailable
- Dependency strictly one-way: components → daemon

---

## Roadmap

### Phase 1 — Core API (PARTIALLY COMPLETE)

**Complete**
- [x] llama.cpp persona + reasoning servers (ports 8080/8081)
- [x] FastAPI Companion API — /health, /chat, /chat_submit, /jobs, /v1/chat/completions
- [x] OpenAI-compatible streaming endpoint (OpenWebUI compatible)
- [x] Async reasoning worker with quality guard (looks_degenerate + two-stage self-repair loop)
- [x] Reasoning fallback to persona (REASONING_FALLBACK_TO_PERSONA toggle)
- [x] Global ChromaDB RAG — embed + query via fastembed
- [x] Multi-profile folder structure (persona.md / system_rules.md / memory/)
- [x] GPU offload — persona 35 layers, reasoning 45 layers
- [x] Operational scripts (status/doctor/unified_test/clean/init_profiles/setup)
- [x] OpenWebUI connected via /v1/chat/completions

**Incomplete — Active Work Needed**
- [ ] Wire persona.md + system_rules.md into build_persona_prompt() — currently placeholder
- [ ] Wire per-profile Chroma into memory_query/memory_add — currently global only
- [ ] Replace in-memory jobs dict with Task Board (data/tasks.db)
- [ ] Implement topic routing policy (TOPIC_POLICY) — coding→coder, math→reasoning
- [ ] Implement coder server (port 8082) — model, routing, worker
- [ ] Rename scientist→reasoning across server.py, scripts, env (in progress)

**Preserved Live Features (must survive all refactors)**
- `looks_degenerate()` — quality heuristic: length, quote ratio, word uniqueness, bigram/trigram repetition
- Two-stage self-repair loop — degenerate output triggers repair prompt at temp 0.0
- `reasoning_lock` — one reasoning job at a time
- `persona_sem` — persona concurrency cap (PERSONA_CONCURRENCY=2) — keeps persona responsive while experts run
- Streaming fallback — chunks one-shot response in 50-char pieces if upstream stream fails

### Phase 2 — Frontend & UX
> OpenWebUI as thin client. API owns all state. Uses: Task Board, SQLite conversations, ChromaDB RAG.

**OpenWebUI Integration**
- [x] OpenWebUI connected via /v1/chat/completions
- [ ] Profile switching via API endpoint from UI
- [ ] Health/status display via `/health` (optional UI panel)
- [ ] OpenWebUI absorbed into daemon as managed child process (Phase 3 dependency)

**Chat History**
- [ ] SQLite at `data/conversations.db` — full turns, source of truth
- [ ] Nothing written to RAG directly — Sleep Cycle handles distillation
- [ ] Deprecate direct global memory writeback in reasoning_worker()

**Task Surfacing**
- [ ] Persona checks Task Board on each response cycle
- [ ] READY results surfaced naturally in next response
- [ ] Absent-user results flagged pending_surface, surfaced on next interaction
- [ ] Surfaced results marked SURFACED, never shown again

**Conversation Windowing — Hybrid**
- [ ] Window closes on: time gap, topic shift, or hard cap — all configurable in `run/config.env`
- [ ] On close → LLM distillation pass → summary into RAG via sorting line

### Phase 3 — Always-On Daemon
> Single entry point. Run once, stays alive, self-heals. No CLI arguments.
> Uses: Unix Socket IPC, Task Board (health monitor awareness)

**Internal Event Architecture**
- [ ] Four asyncio Tasks:
  - `health_monitor` — polls child processes, drives restart policy
  - `idle_detector` — listens on Unix socket, manages idle_signal
  - `ingest_worker` — consumes file events from inbox queue
  - `consolidation_worker` — awaits idle_signal, suspends immediately when cleared
- [ ] Communication via asyncio primitives only — no shared mutable state
  - `asyncio.Event` → `idle_signal`
  - `asyncio.Queue` → `ingest_queue`

**Startup Sequence**
- [ ] Read `run/config.env`
- [ ] Wipe all `logs/` → fresh slate
- [ ] Remove stale `run/daemon.sock`, `run/daemon.pid`, `run/*.pid`
- [ ] Bind new `run/daemon.sock`, write `run/daemon.pid`
- [ ] Spawn all child processes, write individual PID files
- [ ] Start all asyncio tasks

**Shutdown Sequence**
- [ ] SIGTERM/SIGINT → signal all children
- [ ] Wait `SHUTDOWN_TIMEOUT` seconds → force kill stragglers
- [ ] Remove `run/daemon.sock`, all PID files
- [ ] Exit clean

**Restart Policy — Three Strike Rule**
- [ ] Per-child strike counter + timestamp window
- [ ] Exponential backoff (`STRIKE_BACKOFF_BASE`)
- [ ] 3 strikes within `STRIKE_WINDOW` → FAILED state + `logs/critical.log` entry
- [ ] FAILED visible in `scripts/status.sh`

**Logging**
- [ ] One log per service — overwritten fresh on every daemon start
- [ ] Services: daemon, persona, reasoning, coder, api, webui, stt, tts, agent, critical

**Portability Contract**
- [ ] No host-level dependencies beyond Python + venv
- [ ] All paths relative to project root
- [ ] Models in `models/` — git ignored, user provided
- [ ] Migration = copy folder, activate venv, run `daemon.py`

**Child Process List**
```
daemon.py spawns:
    → llama-persona        (port 8080)
    → llama-reasoning      (port 8081)
    → llama-coder          (port 8082, when implemented)
    → companion-api        (port 8000)
    → open-webui           (port 3000, env_webui/ venv)
    → whisper-stt          (port TBD, Phase 5)
    → piper-tts            (port TBD, Phase 5)
```

**Scripts Disposition**
```
Absorbed into daemon (retire after audit):
    start_llama_servers.sh / stop_llama_servers.sh
    start_api.sh / stop_api.sh
    start_webui.sh / stop_webui.sh
    start_all.sh / stop_all.sh

Retained and updated:
    status.sh           → daemon awareness + FAILED state
    doctor.sh           → 2-file profile, config.env, new folders
    unified_test.sh     → scientist→reasoning references
    init_profiles.sh    → 2-file profile, remove style.md
    setup_native_stack.sh → add inbox/, data/, openwebui/
    clean.sh            → add daemon.sock cleanup
```

### Phase 4 — Embodied Presence (Godot)
> Optional immersive client for capable hardware. WebUI embedded as viewport panel.
> Low-end hardware runs WebUI standalone in browser.

**Client Tier Model**
```
Capable hardware  → Godot (3D/VR + embedded WebUI panel)
Low-end hardware  → WebUI only (direct browser)
Both             → same API, same persona, same history, same memory
```

**Avatar State Stream — Parallel Channel**
> Phase 4 breaking change to server.py — replaces placeholder BODY_CUE approach.
- [ ] Persona produces two channels:
  - `RESPONSE:` → text → WebUI + TTS
  - `STATE:` → JSON avatar directives → Godot
- [ ] State schema:
```json
{
    "state": "talking",
    "emotion": "curious",
    "gesture": "slow_nod",
    "intensity": 0.7
}
```
- [ ] State vocabulary defined in `system_rules.md` per profile
- [ ] Malformed STATE → Godot holds last known state, never crashes

**Profile Structure (2 files)**
```
persona/profiles/<n>/
    persona.md       → identity, personality, emotional range, communication style
    system_rules.md  → hard rules + output format + avatar state vocabulary
    memory/          → per-profile Chroma persistence
```

### Phase 5 — Voice Pipeline
> All voice compute on host. Clients capture and play audio only.
> Uses: Task Board (TTS jobs), Unix Socket IPC (tts_speaking event)

```
Client → audio → host
Host: Whisper.cpp → text → /chat
Host: Persona → RESPONSE → Piper TTS → audio + phoneme timing
               → STATE → Godot
Host: audio + phoneme timing → client
Client: plays audio, Godot drives lip sync
```

- [ ] Whisper.cpp STT — daemon child, own log, three strike rule
- [ ] Piper TTS (OHF-Voice/piper1-gpl, GPL-3.0) — daemon child, own log, three strike rule
- [ ] Choose CC BY 4.0 licensed voices only — verify each voice model card on HuggingFace
- [ ] Coqui as fallback if Piper unavailable

### Phase 6 — Auto-Contextual RAG Pipeline ("Sorting Line")
> Drop file into inbox/ → system classifies and routes automatically.
> Uses: ChromaDB RAG, Task Board, Sleep Cycle (ontology maintenance)

**Ingest Pipeline**
- [ ] File watcher (`watchdog`) on `inbox/`
- [ ] Multi-format reader: `.txt`, `.md`, `.pdf`, `.py`, `.json`, `.csv` (extensible)
- [ ] Semantic classifier — embed + compare against collection centroids
- [ ] Multi-bin routing — file can land in multiple collections
- [ ] No match → immediate new collection, LLM slug, PROVISIONAL status
- [ ] Ingest manifest log with confidence scores

**Collection Lifecycle**
- [ ] `PROVISIONAL` → `MATURE` → (`MERGED` | `SPLIT`)
- [ ] Alias chain preserved on every rename — old names always resolve
- [ ] Sleep Cycle handles renaming, merging, splitting

**Collection Naming**
- [ ] LLM-generated normalized slug — topic-level not document-level
- [ ] Sleep Cycle re-evaluates PROVISIONAL names as content accumulates
- [ ] All renames append to alias chain, never overwrite

### Phase 7 — Background Cognitive Consolidation ("Sleep Cycle")
> Runs during idle periods. Reviews knowledge, finds connections, maintains ontology.
> Uses: idle_signal from daemon, Task Board, ChromaDB RAG, SQLite conversations

**Consolidation Worker**
- [ ] Awaits `idle_signal` — no independent idle detection
- [ ] Yields immediately when `idle_signal` cleared
- [ ] Sweep depth via `CONSOLIDATION_SWEEP_DEPTH`
- [ ] Deduplication guard on chunk pairs

**Conversation Distillation**
- [ ] Pulls `distilled = false` turns from SQLite
- [ ] Closes windows on time gap / topic shift / hard cap
- [ ] LLM distillation pass → summary into RAG via sorting line
- [ ] Marks turns `distilled = true`, writes back `window_id` and `summary_chunk_id`

**Relationship Discovery**
- [ ] Cross-collection similarity sweep
- [ ] Writes relationships into chunk metadata
- [ ] LLM-assisted labeling for confident matches

**Ontology Maintenance**
- [ ] Re-evaluates PROVISIONAL collection names as content grows
- [ ] Detects overlapping → merge (re-embed, preserve alias chains)
- [ ] Detects over-broad → split (child collections reference parent alias chain)
- [ ] Alias resolution transparent at query time regardless of restructuring

**Insight Surface**
- [ ] Journal written to `data/insights/YYYY-MM-DD.md`
- [ ] Persona surfaces insights via Task Board at session start

### Phase 8 — Agentic Layer (LangGraph)
> Parallel `/agent` endpoint alongside `/chat`. Existing routing untouched.
> Uses: Task Board, ChromaDB RAG, all expert models

**Agent Graph**
```
/agent request
    → Planner → Research → Expert(s) → Evaluate → iterate or finalize
    → Persona node synthesizes output in-character
    → Result written to Task Board, surfaced by persona
```

**Tool Calling Scope**
- [ ] Web search, sandboxed code execution, file reads, RAG queries, external APIs, system monitoring

**Scientist Loop**
- [ ] Question → Hypothesis → Research → Evaluate → Iterate → Answer
- [ ] Max iterations configurable, logged to `logs/agent.log`

**CrewAI — Phase 9 Candidate**
> Potential replacement for silent MoE layer — observable multi-agent crew.
> All crew results flow through Task Board. Persona surfaces, never coordinates.
> Evaluate when Phase 8 is mature.

---

## TODO (Active)

| # | Item | Priority | Source |
|---|---|---|---|
| 1 | Rename scientist→reasoning across server.py, all scripts, env file | High | Audit |
| 2 | Rename run/llama-servers.env → run/config.env, expand with all documented vars | High | Decision |
| 3 | Wire persona.md + system_rules.md into build_persona_prompt() | High | Phase 1 gap |
| 4 | Wire per-profile Chroma into memory_query / memory_add | High | Phase 1 gap |
| 5 | Replace in-memory jobs dict with Task Board (data/tasks.db) | High | Component |
| 6 | Implement task difficulty estimator + time_score feedback loop | High | Component |
| 7 | Implement persona task surfacing on response cycle | High | Phase 2 |
| 8 | Implement topic routing policy (TOPIC_POLICY) — coding→coder, math→reasoning | Medium | Phase 1 gap |
| 9 | Implement coder server (port 8082) — model, daemon child, routing | Medium | Phase 1 gap |
| 10 | Suppress / strip `<think>` tags from reasoning model output | Medium | Known issue |
| 11 | Update doctor.sh — 2-file profile, config.env references, new folder checks | Medium | Audit |
| 12 | Update init_profiles.sh — remove style.md, 2-file profile scaffold | Medium | Audit |
| 13 | Update setup_native_stack.sh — add inbox/, data/, openwebui/ | Medium | Audit |
| 14 | Update clean.sh — add daemon.sock cleanup | Low | Audit |
| 15 | Plan + build daemon.py — asyncio loop, child process map, signal handling, socket | High | Phase 3 |
| 16 | Add README model section (drafted — README_models_section.md) | Medium | Pre-publish |
| 17 | Add README license section noting model file exclusion and OpenWebUI terms | Medium | Pre-publish |
| 18 | Verify Qwen2.5-14B-Instruct exact license on HuggingFace model card | Low | License audit |
| 19 | Choose Piper voice model — verify CC BY 4.0, avoid Blizzard-trained voices | Low (future) | Phase 5 prereq |
| 20 | Deprecate direct memory writeback in reasoning_worker() when Phase 2/7 land | Low (future) | Phase 2 |
| 21 | Implement collection + chunk metadata schemas in Chroma layer before Phase 6 | Low (future) | Phase 6 prereq |
| 22 | Implement alias resolution layer before Phase 6 goes live | Low (future) | Phase 6 prereq |
| 23 | Define insight journal structure before Phase 7 build | Low (future) | Phase 7 prereq |

---

## License Review

| Component | License | AGPLv3 Compatible | Notes |
|---|---|---|---|
| llama.cpp | MIT | ✅ | No restrictions |
| whisper.cpp | MIT | ✅ | No restrictions |
| FastAPI | MIT | ✅ | No restrictions |
| uvicorn / httpx / pydantic | MIT / BSD | ✅ | No restrictions |
| ChromaDB | Apache 2.0 | ✅ | Compatible with AGPLv3 |
| LangGraph | MIT | ✅ | Confirmed on GitHub |
| Godot Engine | MIT | ✅ | Engine license doesn't touch project content |
| SQLite | Public domain | ✅ | No restrictions |
| Qwen2.5-14B-Instruct | Apache 2.0 | ✅ | Verify exact model card on HuggingFace |
| Piper TTS (active fork) | GPL-3.0 | ✅ | OHF-Voice/piper1-gpl — GPL-3.0 compatible with AGPLv3 |
| OpenWebUI | BSD-3 + branding clause | ⚠️ | Not redistributed — used as dependency. Users deploying at scale must comply with branding clause independently. Document in README. |
| Meta Llama 3.1 model weights | Meta Community License | ⚠️ | Not in repo (git ignored). Users accept Meta's license independently. Document in README. |
| Piper voice models | Varies (CC BY 4.0 / Blizzard) | ⚠️ | Not in repo. CC BY 4.0 voices require attribution. Blizzard-trained voices are research-only. |

**Project license:** AGPLv3 + Section 7 linking exception — correctly chosen. Linking exception allows models, frontends, and tools to interact without license propagation.

**Publishing requirements:**
- Model files excluded from repo — users provide their own (documented in README)
- README clearly states model files are not covered by project license
- README notes OpenWebUI has its own license — users responsible for compliance in their deployments

---



| Date | Issue | Resolution |
|---|---|---|
| — | *(No entries yet)* | — |

---

## File Change Tracker

| Session Date | Files Modified | Summary |
|---|---|---|
| 2026-04-05 | KNOWLEDGE.md | Created — initial tracker |
| 2026-04-05 | KNOWLEDGE.md | Phases 2-8 fully spec'd across session |
| 2026-04-05 | KNOWLEDGE.md | Full consolidation — uploaded files as ground truth, stale data purged, config.env documented |
| 2026-04-05 | KNOWLEDGE.md | Task Board added as system component — schema, surfacing behavior, difficulty/time_score, phase touchpoints |
| 2026-04-05 | KNOWLEDGE.md | License audit complete — component table added, model exclusion policy documented, hardware tiers and model naming guidance added |
| 2026-04-05 | README_models_hardware.md | Created — GGUF requirement, HuggingFace sourcing, quantization guide, per-role specs, four hardware tiers, model license note |

---

## Key File Reference

| File | Purpose |
|---|---|
| `README.md` | Project overview, philosophy, license |
| `README_models_hardware.md` | Model requirements, hardware tiers, HuggingFace sourcing guide |
| `run/config.env` | All runtime config — ports, models, GPU layers, timeouts, feature toggles, daemon settings |
| `daemon.py` | Single entry point launcher + live service monitor (Phase 3) |
| `models/` | User-provided GGUF model files — git ignored, not part of project license |
| `inbox/` | User-facing file drop folder — sorting line monitors this |
| `data/conversations.db` | SQLite — chat history, windowing state, distillation tracking |
| `data/tasks.db` | SQLite — task board, job queue, difficulty scores, performance log |
| `data/insights/` | Sleep Cycle journal — `YYYY-MM-DD.md` insight entries |
| `openwebui/` | OpenWebUI persistent data directory |
| `env_webui/` | OpenWebUI isolated Python venv |
| `persona/profiles/default/` | Default profile (persona.md / system_rules.md) |
| `persona/global_memory/` | Shared cross-profile Chroma vector store |
| `scripts/status.sh` | Quick status summary — retain, update for daemon |
| `scripts/doctor.sh` | Diagnostics + smoke tests — retain, update |
| `scripts/unified_test.sh` | Full end-to-end integration test suite — retain |
| `scripts/init_profiles.sh` | Profile scaffold initializer — retain, update for 2-file profile |
| `scripts/setup_native_stack.sh` | Bootstrap/setup automation — retain, update for new folders |
| `scripts/clean.sh` | Runtime state cleanup — retain, add daemon.sock |

---

## Git Milestone Log

| Tag | Description | Date |
|---|---|---|
| *(none yet tagged in this tracker)* | — | — |

---

*This file is maintained as a living document. Update after every session.*
