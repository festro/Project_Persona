# Project_Persona — Knowledge & Task Tracker
**Last Updated:** 2026-05-15 0827 UTC
**Repo:** https://github.com/festro/Project_Persona
**Domain:** yourdomain.com | **Target OS:** Debian Linux | **Daily Driver:** Windows

---

## Active Architectural Decisions

### DECISION 2026-05-11: Adopt Hermes Agent as agent-work backbone

**Status:** Approved, implementation deferred until single-model migration completes.
**Reference handoff:** `HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md`
**Next-session entry point (after single-model migration M12 completes):** Resume at H1.1 (read Hermes architecture docs end-to-end). H1.1–H1.5 are pre-flight verification — confirm Hermes accepts custom OpenAI-compatible endpoints (unified llama-server), runs headless without messaging credentials, has configurable session storage path, and can be pinned to local-only.

**Decision:** Adopt Hermes Agent (Nous Research, MIT) as the agent-work backbone. server.py remains the live conversation layer; Hermes runs as a daemon child process, pulls work from the Task Board, executes with its own orchestration, writes results back. Persona surfaces results through existing surfacing behavior.

**Six brainstorm forks resolved:**
- Fork 1 (build vs adopt vs hybrid) → **Full adopt Hermes**. Hermes uses neither AG2 nor CrewAI internally; its `AIAgent` is its own synchronous orchestration with subagent delegation and Tenacity Kanban. Hybrid case rejected — IPC overhead negligible at LLM-call timescales; two orchestrators = vestigial moving parts.
- Fork 2 (swarm pattern) → **Fan-out / gather**. Orchestrator decomposes hard queries into N sub-questions, dispatches in parallel against unified model, gathers and synthesizes.
- Fork 3 (orchestrator location) → **Inside Phase 3 daemon**. Persistent asyncio loop, child process map already designed for it, Unix socket already present.
- Fork 4 (worker addressing) → **Pure stateless slots, with deterministic role-prefix templates**. Orchestrator constructs prompts as `[stable_role_prefix] + [task_suffix]` with `cache_prompt: true` so KV cache amortizes across fan-outs.
- Fork 5 (failure semantics) → **Add Tenacity-style columns to Task Board now**. Heartbeat / reclaim / zombie / validation logic added during H2, not after production failures.
- Fork 6 (worker memory) → **Stateless swarm under orchestrator**. No per-worker persistent memory or persona. Identity lives in Hermes' main loop and the persona layer in server.py.

**Roadmap impact:**
- **Phase 2.5 (AG2 scientist↔critic loop): DELETED** — superseded by Hermes' agent loop with subagent delegation
- **Phase 8 (LangGraph agentic layer): RESHAPED** — collapses into "Hermes integration + Task Board contract"
- **Phase 9 (CrewAI candidate): DELETED** — Hermes' Tenacity Kanban covers what CrewAI was wanted for
- **Phase 3 (Daemon): EXTENDED** — adds `hermes-agent` to child process list, gains a Task Board → Hermes dispatcher with reclaim sweeper
- **Task Board schema: EXTENDED** — adds heartbeat_at, heartbeat_interval_s, claimed_by, reclaim_after, attempt, max_attempts, validation_status, validation_feedback

**Trade-offs accepted:** Loss of architectural ownership over orchestration; loss of persona-first identity at worker level; SQLite/FTS5 (Hermes) and Chroma/Qdrant overlap on "find what we discussed"; Hermes upgrade cadence is theirs; one more daemon child to monitor; **non-trivial network egress risk surface (7 paths + 1 local-machine-specific Claude Code creds risk) requiring deliberate config + kernel-level containment + periodic audit — see handoff Network Egress Risk Surface section and Appendix A**.

**Rollback path:** Hermes is loosely coupled — it sits behind the Task Board contract. Revert dispatcher to in-process Python subprocess pool; keep Tenacity columns regardless; revisit Phase 8/9 with build-native option. server.py routing logic unchanged on rollback.

---

### DECISION 2026-05-09: Consolidate to single-model topology

**Status:** Approved, migration in progress. M1 resolved 2026-05-14. M2a resolved 2026-05-14 (build verified). M2b deferred to post-M5 (sustained-load test).
**Reference handoff:** `HANDOFF_2026-05-09_0950_single-model-migration.md`
**Next-session entry point:** Resume at **M3** — update `run/config.env` for single-model topology (drop reasoning/coder sections, add `PARALLEL_SLOTS`, scale `--ctx-size` to slot count). Send fresh copies of `run/config.env`, `start_llama_servers.sh`, and `services/api/server.py` next session per tenant #3 before any edits. M1 source: **bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF Q5_K_M** (download command in TODO M1). M2a verified: Vulkan via RADV on AMD Radeon Graphics RADV GFX1151, llama.cpp 8157, uma=1, fp16=1, bf16=0, KHR_coopmat present.

**Decision:** Replace the multi-model deployment (persona 8080 + reasoning 8081 + planned coder 8082) with a single Qwen3-30B-A3B model at Q5_K_M, served from one llama.cpp instance with `--parallel` slots and `--cont-batching`. Role differentiation moves from URL-based dispatch (`PERSONA_URL` vs `SCIENTIST_URL`) to prompt-based — thinking-mode toggle, sampling parameters, and system prompt selection per request.

**Rationale (summary):**
- Qwen3-30B-A3B is a Mixture-of-Experts model with 3B active parameters — well-matched to the EVO-X2's bandwidth-limited unified memory.
- Native thinking-mode toggle maps directly onto the existing persona/reasoning split without needing two model files.
- Q5_K_M chosen over Q4_K_M for research-grade reasoning quality (biology, independent research) where compounding errors over long thinking traces matter; MoE routers are also more sensitive to quantization noise than dense models.
- Apache 2.0 license, clean against AGPLv3 + linking exception.
- Single model reduces ops surface (one set of weights, one server, fewer failure modes).

**Trade-offs accepted:** ~20% throughput cost vs Q4_K_M; loss of fault isolation between roles; migration effort across env, launcher, API.

**Roadmap impact:** Coder server (port 8082) is superseded — coding tasks served by the same model in thinking mode with a code-specialist system prompt. Daemon child process list (Phase 3) collapses by one entry. See migration TODO items below.

---

## System State (Last Confirmed Working)

| Component | Status | Notes |
|---|---|---|
| llama-server (persona) port 8080 | ✅ Running — TO BE RETIRED | 35-layer GPU offload — Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf. Superseded by single-model consolidation (2026-05-09). |
| llama-server (reasoning) port 8081 | ✅ Running — TO BE RETIRED | 45-layer GPU offload — Qwen2.5-14B-Instruct-Q5_K_M.gguf. Superseded by single-model consolidation (2026-05-09). |
| llama-server (coder) port 8082 | ❌ Cancelled | Superseded by single-model consolidation. Coding tasks served by Qwen3-30B-A3B in thinking mode. |
| llama-server (unified) port 8080 | ⏳ Planned | Qwen3-30B-A3B-Q5_K_M.gguf, parallel slots, continuous batching. Replaces all three above. |
| FastAPI Companion API port 8000 | ✅ Running | uvicorn, OpenAI-compatible |
| /v1/chat/completions endpoint | ✅ Verified | OpenAI-compatible streaming — OpenWebUI connects here |
| /chat endpoint | ✅ Verified | Sync persona reply + optional async reasoning |
| /chat_submit endpoint | ✅ Verified | Async job submission — returns job ID for polling |
| /jobs/{job_id} endpoint | ✅ Verified | Job status + result polling — to be replaced by task board |
| /health endpoint | ✅ Verified | Reports per-server status |
| ChromaDB RAG | ⚠️ Partial | Global collection only — per-profile not yet wired to API |
| Reasoning quality guard | ❌ NOT present (was claimed) | `looks_degenerate()` + two-stage self-repair loop are NOT in live `services/api/server.py` (verified by Mercury addendum 2026-04-27 grep — zero matches for `looks_degenerate`, `repair_prompt`, `self.repair`). The original spec described it but it was never wired. **Decision needed:** reinstate (recommended for persona output safety) or accept absence. |
| Reasoning fallback to persona | ✅ Present | REASONING_FALLBACK_TO_PERSONA toggle — off by default |
| Async reasoning routing | ⚠️ Off by default | ASYNC_REASONING_ENABLED=0 — topics: science,biology,coding,math |
| Multi-profile folder structure | ⚠️ Partial | Profiles exist on disk — `SOUL.md` (was persona.md) / `.hermes.md` (was system_rules.md) not loaded by API yet. Folder doubles as Hermes `HERMES_HOME` per profile (locked 2026-05-14). |
| OpenWebUI | ✅ Running — **PRIMARY FRONTEND (locked 2026-05-14)** | Separate venv (env_webui/) — data at openwebui/ — port 3000. SillyTavern decision in AIP_knowledge.md superseded — out of scope for Project_Persona. |
| Hermes Agent | ⏳ Planned | Daemon child post-single-model migration. Pulls work from Task Board, executes agent orchestration, writes results back. Replaces Phase 2.5 (AG2) and Phase 9 (CrewAI candidate); reshapes Phase 8 (LangGraph). |

**Known Issues / Caveats**
- `build_persona_prompt()` is a placeholder — `SOUL.md` (was persona.md) and `.hermes.md` (was system_rules.md) not loaded by API yet
- Per-profile Chroma memory not wired — all reads/writes use global collection only
- Coder server cancelled — superseded by single-model consolidation (2026-05-09)
- Reasoning endpoint may emit raw `<think>` tag fragments — relevant after migration since Qwen3 thinking mode wraps thinking traces in `<think>` tags by default; will need stripping before user-facing surface
- ASYNC_REASONING_ENABLED defaults to 0 — reasoning expert off unless explicitly enabled
- Profile wrappers (`SOUL.md`, `.hermes.md`) loaded into every prompt — `_read_text` allows up to 12000 chars per file; worst-case ~6K tokens of static context (down from ~9K with the prior 3-file structure since `style.md` is being removed). Mitigation: trim aggressively and/or use `cache_prompt: true` on llama-server requests. Re-evaluate after single-model migration since Qwen3 has 32K native context (128K with YaRN).
- API-side `PERSONA_CONCURRENCY=2` semaphore gates parallelism upstream of llama.cpp's slot scheduler — moot today (servers run single-slot) but will be replaced during migration with parallel-slot dispatch.
- AMD ROCm stability on Strix Halo / RDNA 3.5 unverified under sustained load — pre-migration check: confirm whether current `llama-server` build uses Vulkan or ROCm; Vulkan is the more stable path on this hardware.
- **Vulkan backend reports `bf16: 0`** on this Strix Halo build (verified 2026-05-14). Has no impact on Q5_K_M weights or current `q8_0` KV cache config — but flag any future config that assumes bf16 capability (some experimental KV cache modes, some training/finetuning paths). Q4/Q5/Q6 K-quants and q8_0 cache are unaffected.
- **Hermes Claude Code credential auto-detection — local-machine-specific risk.** Per Hermes provider-runtime docs, native Anthropic credential resolution prefers refreshable Claude Code credentials over copied env tokens when both are present. Cowork mode (Claude Code) is installed as `festro33` on this machine. If `hermes-agent` runs as the same user and provider ever resolves to `anthropic`, it will find and use those creds, sending prompts to Anthropic on the user's account. Mitigation: never set `provider: anthropic` in Hermes config; never export `ANTHROPIC_TOKEN` / `CLAUDE_CODE_OAUTH_TOKEN` to daemon env; run daemon under systemd unit with explicit `Environment=` directives (no shell inheritance). See HANDOFF_2026-05-11_0038 Egress Point 4.

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
    assigned_to         → "hermes" | "reasoning" | "coder" | null
    role_tag            → role-prefix template tag (researcher | critic | summarizer | coder | librarian)
    difficulty          → estimated 1-5 (auto-assigned, recalibrates from time_score)
    status              → QUEUED | CLAIMED | RUNNING | VALIDATING | READY | SURFACED | FAILED
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

    # Tenacity-style failure semantics (DECISION 2026-05-11)
    heartbeat_at        → timestamp of last worker heartbeat
    heartbeat_interval_s → expected heartbeat cadence
    claimed_by          → worker ID currently holding the task ("hermes" | etc.)
    reclaim_after       → timestamp — when to return to QUEUED if no heartbeat
    attempt             → current retry attempt
    max_attempts        → retry cap before FAILED
    validation_status   → PASSED | FAILED | PENDING
    validation_feedback → feedback for retry on validation failure
```

**Performance Log**
> Task board doubles as a performance profile over time.
> Query to see which task types run longest, which models handle what, where bottlenecks appear.

**Phase Touchpoints**
```
Phase 1  → replaces jobs dict; reasoning worker writes to task board
Phase 2  → persona checks task board on each response cycle; surfaces pending results
Phase 3  → daemon health monitor aware of task board state; reclaim sweeper added
Phase 6  → ingest worker creates tasks for classification jobs
Phase 7  → sleep cycle creates and consumes tasks for consolidation work
Phase 8  → Hermes Agent (daemon child) pulls tasks, executes orchestration, writes results back
Phase 9  → DELETED (CrewAI candidate superseded by Hermes — DECISION 2026-05-11)
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
- [x] Async reasoning worker (per-quality-guard: see Known Issues — `looks_degenerate()` was spec'd but never landed in live code; reinstate decision pending)
- [x] Reasoning fallback to persona (REASONING_FALLBACK_TO_PERSONA toggle)
- [x] Global ChromaDB RAG — embed + query via fastembed
- [x] Multi-profile folder structure (`SOUL.md` / `.hermes.md` / `memory/`) — folder doubles as Hermes `HERMES_HOME` per profile
- [x] GPU offload — persona 35 layers, reasoning 45 layers
- [x] Operational scripts (status/doctor/unified_test/clean/init_profiles/setup)
- [x] OpenWebUI connected via /v1/chat/completions

**Incomplete — Active Work Needed**
- [ ] Wire `SOUL.md` + `.hermes.md` into build_persona_prompt() — currently placeholder
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
- [ ] Services: daemon, llama-unified, api, hermes, webui, stt, tts, critical

**Portability Contract**
- [ ] No host-level dependencies beyond Python + venv
- [ ] All paths relative to project root
- [ ] Models in `models/` — git ignored, user provided
- [ ] Migration = copy folder, activate venv, run `daemon.py`

**Child Process List** (post single-model + Hermes adoption)
```
daemon.py spawns:
    → llama-unified        (port 8080, Qwen3-30B-A3B, parallel slots)
    → companion-api        (port 8000)
    → hermes-agent         (no port — IPC via Task Board, headless mode)
    → open-webui           (port 3000, env_webui/ venv)
    → whisper-stt          (port TBD, Phase 5)
    → piper-tts            (port TBD, Phase 5)
```
Removed by DECISION 2026-05-09 (single-model): llama-reasoning (8081), llama-coder (8082).
Added by DECISION 2026-05-11 (Hermes adoption): hermes-agent.

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
    init_profiles.sh    → 2-file profile (SOUL.md + .hermes.md), remove style.md, scaffold gitignore for MEMORY.md/USER.md
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
- [ ] State vocabulary defined in `.hermes.md` per profile
- [ ] Malformed STATE → Godot holds last known state, never crashes

**Profile Structure (Hermes-naming, locked 2026-05-14)**
```
persona/profiles/<n>/        ← doubles as HERMES_HOME for this profile
    SOUL.md                  → identity, personality, emotional range, communication style
                                (Hermes loads from HERMES_HOME as agent identity)
    .hermes.md               → hard rules + output format + avatar STATE vocabulary
                                (Hermes loads via tree-walk from CWD; highest priority context file)
    MEMORY.md                → Hermes-managed persistent memory (gitignored)
    USER.md                  → Hermes-managed user model snapshot (gitignored)
    memory/                  → per-profile Qdrant persistence (gitignored)
```

**Operational launch (Hermes integration):** daemon spawns `hermes-agent` child with
`HERMES_HOME=<project_root>/persona/profiles/<active>/` and CWD set to the same path.
Profile switching = restart hermes-agent child with new HERMES_HOME (handled via the
existing three-strike machinery + new `profile_switched` IPC event).

**Sterilize.sh / .gitignore:** `MEMORY.md`, `USER.md`, and `memory/` accumulate
user-specific content over time. Must remain gitignored and excluded from sterilization.
Template repo only ships empty `SOUL.md` and `.hermes.md` placeholders for `default/`.

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

### Phase 8 — Agentic Layer (Hermes Agent)
> Reshaped by DECISION 2026-05-11. Original LangGraph design superseded.
> Hermes runs as daemon child, pulls tasks from Task Board, executes orchestration, writes results back.
> Uses: Task Board (Tenacity-style failure semantics), unified llama-server, role-prefix template library

**Architecture**
```
server.py /chat
    → trivial query  → in-band persona response
    → non-trivial    → submit task to Task Board with role_tag

Daemon dispatcher (asyncio task)
    → pulls QUEUED tasks
    → marks CLAIMED, sets reclaim_after
    → submits to Hermes
    → reclaim sweeper returns orphaned tasks to QUEUED if no heartbeat

Hermes Agent (daemon child)
    → AIAgent loop with tool calling
    → fan-out via delegate_tool to parallel slots on unified llama-server
    → role-prefix templates ([researcher | critic | summarizer | coder | librarian])
    → cache_prompt: true on every dispatch for KV cache amortization
    → returns synthesized result via Task Board

Persona node (server.py, next response cycle)
    → polls Task Board for READY tasks owned by user's profile
    → surfaces naturally via existing surfacing behavior
```

**Tool Calling Scope (provided by Hermes)**
- Terminal (5 backends — local / Docker / SSH / Singularity / Modal)
- Web search, browser automation, vision, image generation, text-to-speech
- File read/write/patch/search, code execution sandbox
- MCP client (dynamic external tools)
- Subagent delegation (delegate_tool — fan-out gather)

**Phase 8 deliverables — see `HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md` H1–H6**
- [ ] H1 — Pre-flight verification (5 checks)
- [ ] H2 — Task Board schema extension (Tenacity columns + reclaim sweeper + validation hook)
- [ ] H3 — Daemon dispatcher (Task Board → Hermes)
- [ ] H4 — Role-prefix template library
- [ ] H5 — server.py routing (trivial vs non-trivial)
- [ ] H6 — Validation and acceptance (smoke + failure injection + cache hit rate)

### Phase 9 — DELETED
> CrewAI candidate superseded by Hermes adoption (DECISION 2026-05-11).
> Hermes' Tenacity Kanban (heartbeat / reclaim / zombie detection / hallucination recovery) covers what CrewAI was wanted for.

---

## TODO (Active)

### Compatibility Re-Eval Action Items (DECISION 2026-05-14, tiered) — Hermes + Qwen3.6 swap

> Reference handoff: `HANDOFF_2026-05-15_0827_compat-reeval-tiered.md`
>
> Tiered for incremental validation — finish a tier, verify it works, then move to the next.
> Issues surface in the tier they were introduced rather than at end-of-migration.
>
> **TIER 0 IS A GO/NO-GO GATE.** If T0.1 fails, halt Qwen3.6 work entirely; fall back to Instruct-2507 (no thinking mode), wait for llama.cpp arch support, or stand up vLLM via gfx1101 override. Re-evaluate.

#### Tier 0 — GO/NO-GO (validate the foundational assumption)

| ID | Item | Acceptance | Priority |
|---|---|---|---|
| T0.1 | Empirical llama.cpp arch test for `qwen3_5_moe`. Download `Qwen3.6-35B-A3B-UD-IQ1_M.gguf` (10 GB), load via llama-server with `--n-gpu-layers 0 -c 2048 --port 8090`. | Loads + generates coherent output to a basic prompt | Critical (gate) |
| T0.2 | Tool-calling template verification for Qwen3.6. Submit a tool-calling request, observe whether model emits parseable tool call. If not, write GBNF grammar. | Round-trip: parseable tool call emitted | Critical (gates Hermes integration) |

**Sequencing within tier:** T0.1 → T0.2.
**Gate:** if T0.1 fails, decision branch (fallback paths). T0.2 unblocks Tier 1.
**Estimated effort:** 30 minutes if both pass cleanly.

#### Tier 1 — Foundation (enables everything downstream)

| ID | Item | Acceptance | Priority |
|---|---|---|---|
| T1.1 | `env_hermes/` separate venv pattern. Same isolation pattern as `env_webui/`. Update `setup_native_stack.sh`, `status.sh`, `doctor.sh` awareness. | venv exists, hermes-agent installable, ops scripts aware | High |
| T1.2 | Per-profile Hermes `config.yaml` template. `init_profiles.sh` generates safe-config-conformant config (provider:custom → 127.0.0.1:8080, fallback_providers:[], all auxiliary provider:main, tool whitelist) AND Qwen3.6 sampling params (temp/top_p/top_k/presence_penalty per mode). | doctor.sh validates default profile config.yaml against safe-config schema | High |

**Sequencing within tier:** T1.1 ‖ T1.2 (independent — parallel OK).
**Gate:** doctor.sh confirms env_hermes installed AND default profile config conforms.
**Estimated effort:** 2-4 hours including template authoring.

#### Tier 2 — Core integration (model + agent wiring)

| ID | Item | Acceptance | Priority |
|---|---|---|---|
| T2.1 | Sampling defaults overhaul in `run/config.env` + `services/api/server.py`. Per-mode presets: thinking (temp=1.0, top_p=0.95, top_k=20, presence_penalty=1.5) vs non-thinking (temp=0.7, top_p=0.8, top_k=20, presence_penalty=1.5). | server.py selects preset based on routing decision + thinking-mode toggle | High |
| T2.2 | Wire `enable_thinking` toggle through `chat_template_kwargs` in llama-server payloads. Default policy: trivial → false, non-trivial → true. **Empirical risk:** if llama.cpp's template engine doesn't read `chat_template_kwargs`, fall back to system-prompt injection. | Trivial query → no `<think>` block in raw model output; non-trivial → `<think>` block present | High |
| T2.3 | Wire `preserve_thinking: true` for Hermes-originated requests. Daemon task dispatcher sets the flag when forwarding Hermes work. Default off for direct chat. | Hermes-originated multi-turn requests preserve reasoning across iterations (verify via prompt cache hits or response inspection) | High |
| T2.4 | `<think>...</think>` stripping at Task Board → persona surface boundary (one chokepoint). Greedy regex strip, multi-line, multi-instance. Log stripped content to `logs/api.log`. Applies uniformly to direct llama-server responses AND Hermes worker outputs. | User-facing responses contain zero `<think>` blocks regardless of source | High |

**Sequencing within tier:** T2.1 → T2.2 → T2.3. T2.4 parallel to T2.2/T2.3.
**Gate:** end-to-end test — trivial query returns clean response; non-trivial routes to Hermes, returns synthesized response with no `<think>` artifacts.
**Estimated effort:** 4-8 hours. T2.2 carries empirical risk.

#### Tier 3 — Operational hardening (post-functional)

| ID | Item | Acceptance | Priority |
|---|---|---|---|
| T3.1 | `doctor.sh` integration checks. Cover: HERMES_HOME set per active profile, hermes-agent process responsive, gitignore entries (MEMORY.md / USER.md / hermes_state.db), env_hermes installed, per-profile config.yaml safe-config conformance, egress audit (synthetic compression-trigger workload + tcpdump). | All checks pass green | Medium |
| T3.2 | `unified_test.sh` Qwen3.6-specific tests. Cover: thinking toggle round-trip, sampling presets honored, `<think>` stripping, tool calling round-trip via Hermes, optional vision smoke (gated on T4.2). | Smoke test green across all new test points | Medium |
| T3.3 | Replace `ASYNC_REASONING_ENABLED` with `ENABLE_THINKING_FOR_NONTRIVIAL` semantic. Vestigial config — old toggle was meaningful when reasoning was a separate URL/model; post-Hermes + Qwen3.6 the new semantic is "should non-trivial queries use thinking mode." | Old toggle removed from config.env + server.py; new semantic in place | Low |

**Sequencing within tier:** T3.1 ‖ T3.2 ‖ T3.3 (mostly independent).
**Gate:** doctor.sh + unified_test.sh both green; no vestigial reasoning toggles in config.
**Estimated effort:** 2-4 hours.

#### Tier 4 — Deferred / opt-in (don't touch unless triggered)

| ID | Item | Trigger condition |
|---|---|---|
| T4.1 | Dual-memory resolution — Qdrant vs Hermes session_search unification. Recommended path if needed: build custom Hermes tool `qdrant_query`, then disable session_search via tool whitelist. | User-facing query surfaces contradictory information from the two systems, OR storage cost becomes problematic |
| T4.2 | Vision pathway — `VISION_ENABLED=1` + load `mmproj-F16.gguf` alongside main weights. Allow image inputs via OpenAI multimodal payload format. Document security implications near the toggle. | A specific use case explicitly demands it (avatar perception, OCR-free PDF ingest, etc.) |
| T4.3 | MTP / speculative decoding for Qwen3.6. Update under TODO #25 (speculative decoding). | llama.cpp adds MTP support, OR a draft model becomes available for paired speculative decoding |

**No acceptance criteria; no scheduled work.** Each has a documented trigger condition that promotes it out of Tier 4 when met.

#### Cumulative critical path estimate

If T0 passes: ~10-16 hours focused work to reach end-of-T3, broken into discrete tier-up checkpoints. Each tier independently verifiable and reversible.

#### Non-blocking forward-look

The `<think>` stripping work (T2.4) graduates the existing TODO M8 from "future concern" to "active priority"; M8 can be retired in favor of T2.4 once landed.

The vestigial `ASYNC_REASONING_ENABLED` toggle removal (T3.3) intersects with TODO M5/M6 of the original migration block — coordinate during execution.

---

### Hermes Adoption (DECISION 2026-05-11) — DO NOT START UNTIL SINGLE-MODEL MIGRATION COMPLETES

| # | Item | Priority | Source |
|---|---|---|---|
| H1.1 | Read Hermes architecture docs end-to-end | High | Pre-flight |
| H1.2 | Verify Hermes accepts custom OpenAI-compatible endpoint (unified llama-server :8080) | High | Pre-flight |
| H1.3 | Verify Hermes runs headless (no required messaging-platform credentials) | High | Pre-flight |
| H1.4 | Confirm Hermes session storage path is configurable (must live under `data/`) | Medium | Pre-flight |
| H1.5 | **Network egress containment — integration test, not config check.** Apply safe-config recipe (handoff Appendix A) + scrub daemon env of cloud creds + run under `tcpdump -i any 'not host 127.0.0.1'`. Force three scenarios: (a) long convo triggering 50% compression, (b) llama-server kill -9 mid-request, (c) llama-server forced 500. Acceptance: zero non-localhost packets across all three. Any egress = hard fail, decision reopened. | High | Pre-flight |
| H1.6 | **Egress containment via network namespace or iptables.** Belt-and-suspenders kernel-level enforcement. Run `hermes-agent` in `ip netns` allowing only 127.0.0.1, OR install iptables egress rules on daemon UID/process tree. Verify by intentionally breaking config (e.g., `auxiliary.compression.provider: openai`) — egress must still be zero. | High | Pre-flight |
| H2.1 | Extend `data/tasks.db` schema with Tenacity columns (heartbeat / reclaim / attempt / validation) | High | Task Board |
| H2.2 | Add reclaim sweeper (asyncio task in daemon) | High | Task Board |
| H2.3 | Add validation hook contract (workers emit structured result, dispatcher validates before READY) | High | Task Board |
| H2.4 | Update Task Board status enum (add CLAIMED, VALIDATING) | High | Task Board |
| H3.1 | Add `hermes-agent` to daemon child process list | High | Daemon |
| H3.2 | Implement Task Board → Hermes dispatcher (asyncio task in daemon) | High | Daemon |
| H3.3 | Heartbeat protocol — Hermes worker pings dispatcher on configurable interval | High | Daemon |
| H3.4 | Three-strike rule reuse — Hermes child uses same daemon restart policy | Medium | Daemon |
| H4.1 | Define role-prefix templates (researcher / critic / summarizer / coder / librarian) under `persona/swarm_roles/` | High | Templates |
| H4.2 | Configure Hermes provider with `cache_prompt: true` baked into request payload | High | Templates |
| H4.3 | Wire orchestrator prompt assembly to use `[role_prefix] + [task_suffix]` shape | High | Templates |
| H5.1 | Add routing decision in server.py `/chat` (trivial → in-band, non-trivial → Task Board) | High | Routing |
| H5.2 | Trivial / non-trivial classifier (initial heuristic — keyword + length) | Medium | Routing |
| H5.3 | Verify persona surfacing picks up Hermes-produced READY tasks transparently | Medium | Routing |
| H6.1 | End-to-end smoke: research-grade query → fan-out → synthesize → surface | High | Acceptance |
| H6.2 | Failure injection: kill Hermes mid-fan-out → confirm reclaim sweeper recovers | High | Acceptance |
| H6.3 | Failure injection: malformed worker output → confirm validation triggers retry | High | Acceptance |
| H6.4 | Performance: measure cache hit rate on role-prefix templates over 50-task batch (>80% target) | Medium | Acceptance |
| H6.5 | Add periodic egress audit to `doctor.sh` — synthetic "trigger compression" workload + `tcpdump` watch for non-localhost packets. Catches config drift on every health check. | Medium | Acceptance |

### Single-Model Migration (DECISION 2026-05-09)

| # | Item | Priority | Source |
|---|---|---|---|
| M1 | ~~Acquire Qwen3-30B-A3B-Q5_K_M GGUF~~ — **RESOLVED 2026-05-14**: chose **bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF Q5_K_M** (21.74GB, imatrix, llama.cpp b6014, Apache 2.0). Download: `huggingface-cli download bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF --include "Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf" --local-dir ~/Live/AIStack/Project_Persona/models/`. The "Instruct-2507" suffix is the July 2025 instruction-tuned update — more recent than the base Qwen3-30B-A3B referenced in the May 9 decision. Path 2 (jump to Qwen3.5-35B-A3B) deferred — see TODO #36. | ✅ Done | Migration |
| M2a | ~~Verify llama-server backend (Vulkan vs ROCm)~~ — **RESOLVED 2026-05-14**: Vulkan via RADV (Mesa) on AMD Radeon Graphics RADV GFX1151. llama.cpp build 8157 (2943210c1), GNU 13.3.0 Linux x86_64. Capabilities: `uma=1` (unified memory, no offload copy overhead), `fp16=1`, **`bf16=0`** (caveat — see Known Issues), `KHR_coopmat` matrix cores present, `int dot=0`, warp size 64. Vulkan was the recommended path on this hardware; no rebuild needed. Build version is well past bartowski's b6014 GGUF baseline. | ✅ Done | Migration |
| M2b | Sustained-load stability test on Strix Halo — verify no thermal throttling / driver hangs / KV cache corruption under 30+ minute parallel-slot dispatch. **Deferred** until post-M5 (when unified server is actually running). | High | Migration |
| M3 | Update `run/config.env` — single-model section, `PARALLEL_SLOTS`, drop reasoning/coder sections | High | Migration |
| M4 | Update `start_llama_servers.sh` — single server, `--parallel`, `--cont-batching`, ctx-size scaled by slot count | High | Migration |
| M5 | Update `services/api/server.py` — collapse PERSONA_URL/SCIENTIST_URL to one endpoint, add thinking-mode toggle in payload, remove or raise PERSONA_CONCURRENCY semaphore | High | Migration |
| M6 | Parallelize RAG retrieval and worker dispatch with `asyncio.gather` (replace serial in-band scientist call) | High | Migration |
| M7 | Add `cache_prompt: true` to llama-server request payloads | Medium | Migration |
| M8 | Strip `<think>` tags from Qwen3 thinking-mode output before user-facing surface | High | Migration |
| M9 | Trim profile wrappers (`SOUL.md`, `.hermes.md`) — `style.md` removal handled separately by TODO #12 | Medium | Migration |
| M10 | Update `unified_test.sh` — single-endpoint topology, mode-toggle smoke tests | Medium | Migration |
| M11 | Decommission scientist server, remove obsolete env vars, archive Llama-3.1-8B + Qwen2.5-14B GGUFs | Medium | Migration |
| M12 | Update README inference table — single-model topology, ports 8080 only | Medium | Migration |

### General Project TODO

| # | Item | Priority | Source |
|---|---|---|---|
| 1 | Rename scientist→reasoning across server.py, all scripts, env file (partially obsolete — see M5) | Medium | Audit |
| 2 | Rename run/llama-servers.env → run/config.env, expand with all documented vars | High | Decision |
| 3 | Wire `SOUL.md` + `.hermes.md` into build_persona_prompt() | High | Phase 1 gap |
| 4 | Wire per-profile Chroma into memory_query / memory_add | High | Phase 1 gap |
| 5 | Replace in-memory jobs dict with Task Board (data/tasks.db) | High | Component |
| 6 | Implement task difficulty estimator + time_score feedback loop | High | Component |
| 7 | Implement persona task surfacing on response cycle | High | Phase 2 |
| 8 | Implement topic routing policy (TOPIC_POLICY) — coding/math/research route to thinking mode with role-specific system prompts | Medium | Phase 1 gap |
| 9 | ~~Implement coder server (port 8082)~~ — **CANCELLED 2026-05-09**: superseded by single-model consolidation | — | — |
| 10 | Suppress / strip `<think>` tags from model output (now M8) | — | Migration |
| 11 | Update doctor.sh — 2-file profile, config.env references, single-model topology checks | Medium | Audit |
| 12 | Update init_profiles.sh — remove style.md, scaffold 2-file Hermes-naming profile (`SOUL.md` + `.hermes.md`), gitignore MEMORY.md/USER.md | Medium | Audit |
| 13 | Update setup_native_stack.sh — add inbox/, data/, openwebui/ | Medium | Audit |
| 14 | Update clean.sh — add daemon.sock cleanup | Low | Audit |
| 15 | Plan + build daemon.py — asyncio loop, child process map (now one llama-server child), signal handling, socket | High | Phase 3 |
| 16 | Add README model section (drafted — README_models_section.md) | Medium | Pre-publish |
| 17 | Add README license section noting model file exclusion and OpenWebUI terms | Medium | Pre-publish |
| 18 | Verify Qwen3-30B-A3B exact license on HuggingFace model card (expected Apache 2.0) | Low | License audit |
| 19 | Choose Piper voice model — verify CC BY 4.0, avoid Blizzard-trained voices | Low (future) | Phase 5 prereq |
| 20 | Deprecate direct memory writeback in reasoning_worker() when Phase 2/7 land | Low (future) | Phase 2 |
| 21 | Implement collection + chunk metadata schemas in Chroma layer before Phase 6 | Low (future) | Phase 6 prereq |
| 22 | Implement alias resolution layer before Phase 6 goes live | Low (future) | Phase 6 prereq |
| 23 | Define insight journal structure before Phase 7 build | Low (future) | Phase 7 prereq |
| 24 | Hierarchical memory: distiller summarizes fact clusters into higher-level claims so retrieval can pull summaries when context is tight | Low (future) | Architecture |
| 25 | Speculative decoding (`docs/speculative.md` already in tree) — pair tiny draft model with main for 1.5–3x throughput on the hot path | Low (future) | Architecture |
| 36 | **Re-evaluate Qwen3.5-35B-A3B / Qwen3.6-35B-A3B in 2-3 months** (after 2026-08). M1 investigation 2026-05-14 surfaced both as available with strict benchmark upgrades (GPQA 84.2, MMLU-Pro 85.3, 262K native context, multimodal-native, Gated DeltaNet hybrid arch). Deferred from M1 because: (a) llama.cpp `qwen3_5_moe` / Gated DeltaNet support unverified, (b) Q5_K_M GGUFs not yet published by primary maintainers (Unsloth had only BF16 at time of check, no bartowski variant found), (c) vision encoder memory cost in llama.cpp untested, (d) sampling parameter regime differs significantly (presence_penalty=1.5 default), (e) doubling migration scope mid-flight introduces risk. Re-check trigger: bartowski publishes Qwen3.5 imatrix Q5_K_M GGUF, AND llama.cpp release notes confirm qwen3_5_moe arch support. If both true, evaluate as a separate single-model-swap project, not a refactor. | Low (future) | Architecture |

---

## License Review

| Component | License | AGPLv3 Compatible | Notes |
|---|---|---|---|
| llama.cpp | MIT | ✅ | No restrictions |
| whisper.cpp | MIT | ✅ | No restrictions |
| FastAPI | MIT | ✅ | No restrictions |
| uvicorn / httpx / pydantic | MIT / BSD | ✅ | No restrictions |
| ChromaDB | Apache 2.0 | ✅ | Compatible with AGPLv3 |
| LangGraph | MIT | ✅ | Phase 8 originally specified LangGraph; superseded by Hermes adoption (DECISION 2026-05-11). Dependency may be removed. |
| Hermes Agent | MIT | ✅ | Adopted as agent-work backbone (DECISION 2026-05-11). Pulled into project as daemon child; no source modification required. |
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
| 2026-05-09 | knowledge.md | Single-model consolidation decision recorded. Active Architectural Decisions section added at top. System State table updated to flag retiring servers and planned unified server. Known Issues / Caveats expanded with profile wrapper bloat, semaphore concern, ROCm stability check. TODO restructured into Migration block (M1–M12) and General block. Coder server item cancelled. Linked HANDOFF_2026-05-09_0950_single-model-migration.md. |
| 2026-05-09 | HANDOFF_2026-05-09_0950_single-model-migration.md | Created — frozen decision record for the single-model consolidation milestone. |
| 2026-05-11 | knowledge.md | Hermes Agent adoption decision recorded (DECISION 2026-05-11) above single-model decision. Six brainstorm forks resolved. Phase 2.5 (AG2) and Phase 9 (CrewAI) deleted. Phase 8 (LangGraph agentic layer) reshaped into Hermes integration. Hermes added to System State as planned daemon child. Task Board schema extended with Tenacity-style failure semantics columns (heartbeat / reclaim / attempt / validation). Daemon child process list updated (added hermes-agent, removed llama-reasoning/coder). Daemon logging service list updated. Phase Touchpoints table updated. Hermes Adoption TODO block (H1.1–H6.4, 23 items) added at top of TODO. License Review extended with Hermes (MIT) and LangGraph supersession note. Linked HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md. |
| 2026-05-11 | HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md | Created — frozen decision record for Hermes adoption. Captures brainstorm context, six forks with rationale, target architecture diagram, sequenced H1–H6 migration plan, trade-offs, rollback path, acceptance criteria. |
| 2026-05-11 | HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md | Updated — H1.5 expanded from one-line config check to integration-test-with-packet-capture (three forced scenarios). H1.6 added (kernel-level egress containment via netns or iptables). New "Network Egress Risk Surface" section enumerates seven egress paths in Hermes (primary fallback, auxiliary routing, auxiliary fallback chains, Claude Code creds auto-detection, network-egress tools, gateway hygiene, compression silent failure) plus structural recommendations. Trade-offs updated to mention egress surface. Appendix A added with safe-config recipe + daemon environment hygiene + tool whitelist guidance. Sources extended with agent-loop / provider-runtime / context-compression docs. |
| 2026-05-11 | knowledge.md | Egress findings synced from handoff. H1.5 expanded in TODO. H1.6 added. H6.5 added (doctor.sh periodic egress audit). Known Issues / Caveats extended with Claude Code creds risk note. DECISION 2026-05-11 trade-offs updated to mention egress surface. |
| 2026-05-14 | knowledge.md | M1 resolved — bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF Q5_K_M selected (21.74GB, imatrix, b6014, Apache 2.0). Download command embedded in M1 row. DECISION 2026-05-09 next-session entry point bumped to M2 (Vulkan/ROCm verification on Strix Halo). New TODO #36 created — re-evaluate Qwen3.5-35B-A3B / Qwen3.6-35B-A3B in 2-3 months once llama.cpp arch support and bartowski Q5_K_M imatrix GGUFs land. Status field on M1 marked Done. |
| 2026-05-14 | knowledge.md | M2 split into M2a (build verification) and M2b (sustained-load test). M2a resolved — Vulkan via RADV on Strix Halo, llama.cpp 8157, uma=1 fp16=1 bf16=0 KHR_coopmat. M2b deferred to post-M5. Known Issues / Caveats extended with bf16=0 note. DECISION 2026-05-09 next-session entry point bumped to M3 (run/config.env rewrite). |
| 2026-05-14 | HANDOFF_2026-05-09_0950_single-model-migration.md | M1 Resolution Addendum appended in header. M2a verification result will be referenced via knowledge.md (no separate addendum needed — header is the canonical pointer for migration state). |
| 2026-05-14 | knowledge.md | Frontend lock + Hermes-naming cleanup batch. (1) OpenWebUI marked PRIMARY FRONTEND — locked; SillyTavern decision in AIP_knowledge.md superseded as out of scope. (2) Profile files renamed to Hermes conventions: `persona.md` → `SOUL.md`, `system_rules.md` → `.hermes.md`. AGENTS.md considered and rejected — `.hermes.md` is higher-priority Hermes-native context file with tree-walk discovery and YAML frontmatter support. (3) Profile folder doubles as `HERMES_HOME` per profile (matches Hermes' built-in profile system). (4) `MEMORY.md` and `USER.md` added as Hermes-managed files (gitignored, sterilization-excluded). (5) `style.md` outliers cleaned from Known Issues + M9. (6) Operational launch pattern documented: `HERMES_HOME=persona/profiles/<active>/` + matching CWD; profile switch via three-strike restart with new HERMES_HOME. Updates touched: System State (OpenWebUI + multi-profile rows), Known Issues, Phase 1 Complete + Incomplete, Phase 3 Scripts Disposition, Phase 4 State vocabulary + Profile Structure, M9, TODO #3 + #12, Key File Reference (default profile + init_profiles.sh). |
| 2026-05-15 | knowledge.md | Compatibility Re-Eval Action Items added as new tiered TODO block (T0-T4) at top of TODO section. Sits alongside existing Hermes Adoption (H1-H6) and Single-Model Migration (M1-M12) blocks. Supersedes the analytical H7.x and Q1.x labels from the re-eval (those were enumeration-only). Tiered for incremental validation — finish a tier, verify, move on. T0 is a GO/NO-GO gate (Qwen3.6 arch test + tool-calling verification). T1 is foundation (env_hermes + per-profile config.yaml templating). T2 is core integration (sampling, thinking-mode wiring, preserve_thinking, `<think>` stripping). T3 is operational hardening (doctor.sh, unified_test.sh, ASYNC_REASONING cleanup). T4 is deferred/opt-in (dual-memory, vision, MTP). Reference handoff: HANDOFF_2026-05-15_0827_compat-reeval-tiered.md. |
| 2026-05-15 | HANDOFF_2026-05-15_0827_compat-reeval-tiered.md | Created — frozen record of the stack compatibility re-evaluation against the Hermes adoption (DECISION 2026-05-11) and the in-flight Qwen3.6 swap consideration. Captures full per-layer findings, the meta-finding (Qwen3.6 honors DECISION 2026-05-09 design intent better than Instruct-2507 did), tiered T0-T4 action plan with acceptance criteria, sequencing rationale, fallback decision branches if Tier 0 fails. |
| 2026-05-15 | HANDOFF.md | Created — **living handoff document**, distinct from dated frozen records. Six sections: (1) System Status — feature/check/status table per layer, (2) Critical Path — single-paragraph "next action" with copy-paste commands, (3) Active Work & Issues — current focus + each issue with planned resolution, (4) Open Decisions & Deferred Items — things waiting on triggers (T4.1-T4.3, kernel upgrade, vLLM fallback, Phase 4-7), (5) Quick Reference — common commands + key paths + decision shortcuts + key URLs, (6) Handoff Changelog — one-line index of dated handoffs newest first. Includes Document Maintenance protocol at bottom describing when to update. Lives at repo root alongside `HANDOFF_YYYY-MM-DD_*.md` frozen records. |
| 2026-05-15 | HANDOFF.md | Restructured for collapsibility + added Section 7. (1) All seven top-level sections wrapped in `<details>`/`<summary>` HTML5 tags for native collapse. Sections 2 (Critical Path) and 3 (Active Work) open by default; everything else collapsed. (2) New Section 7 "Retired Ideas & Software" — comprehensive list of explicitly deprecated/deleted/out-of-scope choices grouped by domain (Inference & topology / Agent orchestration / Frontend / Profile structure / Storage RAG / Configuration API / Documentation artifacts), each with retirement date, reason, replacement, and reference handoff. (3) Three new issues added to Section 3 from consolidation review: knowledge.md falsely claims `looks_degenerate()` quality guard is present (Mercury addendum verified absent in live code); README.md and persona/README.md are stale; .gitignore doesn't reflect Hermes locked file conventions. |
| 2026-05-15 | HANDOFF.html | Generated via pandoc 2.9.2.1 — self-contained 23KB browser-portable view with embedded CSS (light/dark mode auto-switching), TOC with anchor links, native browser collapsibility from `<details>` tags. Generated by `scripts/regen_handoff_html.sh`. |
| 2026-05-15 | scripts/regen_handoff_html.sh | Created (chmod +x) — one-command regeneration of HANDOFF.html from HANDOFF.md. Auto-detects pandoc 2.x vs 3.x for `--self-contained` vs `--embed-resources` flag selection. Embedded CSS template includes light/dark mode via `prefers-color-scheme`. |
| 2026-05-15 | Multiple files | **Consolidation batch (12 actions executed).** (1-4) Cruft moved to `archive/cruft/` — `.txt` (63KB tree dump), `overview_prompt.txt`, `gitignore.proposed_*`, `sterilize.sh.proposed_*`. Sandbox couldn't `rm` directly so these were archived; user can `rm -rf archive/cruft/` to fully delete. (5-6) `AIP_knowledge.md` and `AIP_HANDOFF_mercury_integration_*.md` archived to `archive/` — superseded historical references kept for provenance. (7) README.md fully rewritten — reflects locked decisions (Hermes backbone, Qwen3.6 candidate, OpenWebUI primary, Qdrant target, 2-file Hermes-naming profile, single-model topology, AGPLv3+linking exception). (8) `persona/README.md` rewritten — describes 2-file Hermes-naming profile structure, HERMES_HOME mapping, sterilization conventions. (9) `.gitignore` rewritten — adds Hermes-managed paths (MEMORY.md / USER.md / hermes_state.db / sessions/), env_hermes/, data/, inbox/, run/*.sock, archive/cruft/; deduped legacy entries; allow-listed `run/llama-servers.env` and `run/config.env`. (10) knowledge.md `looks_degenerate()` claim corrected — System State row updated from ✅ Present to ❌ NOT present (Mercury addendum 2026-04-27 grep verified absence); Phase 1 Complete list updated; reinstate decision pending. (11) Profile content renamed — `persona.md` → `SOUL.md`, `system_rules.md` → `.hermes.md` in both `default/` and `test/` profiles; `style.md` files moved to `archive/legacy_profile_files/`. (12) `README_models_hardware.md` rewritten — single-model topology, MoE quantization sensitivity note, Qwen3.6 as recommended target (Q5_K_XL Unsloth Dynamic), Strix Halo / Vulkan / ROCm 7.2 / HSA_OVERRIDE realities documented, vLLM fallback inference engine documented. |

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
| `persona/profiles/default/` | Default profile (`SOUL.md` / `.hermes.md`) — also serves as Hermes `HERMES_HOME` per profile |
| `persona/global_memory/` | Shared cross-profile Chroma vector store |
| `scripts/status.sh` | Quick status summary — retain, update for daemon |
| `scripts/doctor.sh` | Diagnostics + smoke tests — retain, update |
| `scripts/unified_test.sh` | Full end-to-end integration test suite — retain |
| `scripts/init_profiles.sh` | Profile scaffold initializer — retain, update for 2-file Hermes-naming profile (`SOUL.md` + `.hermes.md`) + gitignore MEMORY.md/USER.md |
| `scripts/setup_native_stack.sh` | Bootstrap/setup automation — retain, update for new folders |
| `scripts/clean.sh` | Runtime state cleanup — retain, add daemon.sock |

---

## Git Milestone Log

| Tag | Description | Date |
|---|---|---|
| *(none yet tagged in this tracker)* | — | — |

---

*This file is maintained as a living document. Update after every session.*
