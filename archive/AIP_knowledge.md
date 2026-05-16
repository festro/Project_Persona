# AIP_knowledge.md — Project_Persona
**Last Updated:** 2026-04-07 | Status: PHASE 1 COMPLETE — PHASE 2 ACTIVE
**Repo:** github.com/festro/Project_Persona
**Live:** ~/Live/AIStack/Project_Persona/
**Git Template:** ~/Git/Project_Persona/
**Domain:** layonet.org | **Target OS:** Debian Linux | **Daily Driver:** Windows
**License:** AGPL-3.0 with Section 7 Linking Exception

---

## Directory Convention

| Location | Purpose |
|---|---|
| `~/Live/AIStack/Project_Persona/` | Running personal instance — real config, real data, never pushed |
| `~/Live/AIStack/AI_TWIN/` | AIT_ running instance — separate, no shared resources |
| `~/Git/Project_Persona/` | Public template repo — sanitized, pushed to GitHub |
| `~/Git/AI_TWIN/` | AIT_ public template repo |

---

## System State (Confirmed 2026-04-06)

| Component | Status | Notes |
|---|---|---|
| llama-server (persona) port 8080 | ✅ Running | Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf — 35 GPU layers, ctx 8192 |
| llama-server (scientist) port 8083 | ✅ Running | Qwen2.5-14B-Instruct-Q5_K_M.gguf — 45 GPU layers, ctx 12288 |
| FastAPI Companion API port 8000 | ✅ Running | uvicorn via start_api.sh |
| ChromaDB RAG | ✅ Running | Fresh init 2026-04-06 — MIGRATION TARGET: Qdrant |
| /health endpoint | ✅ Verified | All components reporting ok |
| /chat endpoint | ✅ Verified | End-to-end chat confirmed working |
| /v1/chat/completions | ✅ Present | OpenAI-compatible — stream field exists but NOT implemented (SSE blocker) |
| Embedder | ✅ Running | BAAI/bge-small-en-v1.5 via fastembed — CUTTING: replaced by Qdrant built-in |
| SillyTavern frontend | ⏳ Not yet integrated | TARGET — decided this session |

**Port mapping (confirmed):**
| Server | Port | Notes |
|---|---|---|
| persona | 8080 | ✅ |
| scientist | 8083 | Changed from 8081 — BrandonNet conflict |
| API | 8000 | ✅ |
| Qdrant (target) | 6333 | Must confirm clear of BrandonNet before install |

**Known BrandonNet port conflicts:**
- 8081 — OTS (OpenTAK Server)
- 8082 — BrandonNet docker container
- 8088 / 8089 — BrandonNet docker containers

---

## Stack

### Current (running)
| Component | Detail |
|---|---|
| Persona server | llama-server, port 8080, Meta-Llama-3.1-8B Q4_K_M, 35 GPU layers, ctx 8192 |
| Scientist server | llama-server, port 8083, Qwen2.5-14B Q5_K_M, 45 GPU layers, ctx 12288 |
| FastAPI API | port 8000, uvicorn, services/api/server.py |
| ChromaDB | global_memory/chroma/ — fresh init 2026-04-06 |
| Embeddings | fastembed — BAAI/bge-small-en-v1.5 |
| venv | ~/Live/AIStack/Project_Persona/env/ — rebuilt 2026-04-06 |

### Target (post-migration)
| Component | Detail |
|---|---|
| Vector store | Qdrant (Apache 2.0) — replacing ChromaDB |
| Embeddings | Qdrant built-in FastEmbed — fastembed dependency cut |
| Frontend | SillyTavern (AGPL-3.0) — replacing OpenWebUI |
| Agent loop | AG2 (Apache 2.0) — scientist reasoning loop, Phase 2.5 |

### Requirements (exact pins)
```
fastapi==0.115.14
uvicorn[standard]==0.34.3
httpx==0.28.1
pydantic==2.12.5
tenacity==8.5.0
qdrant-client[fastembed]==1.16.2
```
Exact pins only — range pins invite dependency hell. qdrant-client pinned to control
FastEmbed version coupling (version drift = silent RAG quality degradation).

---

## Architectural Considerations
> Decisions locked this session — recorded to avoid re-litigating.

### Frontend — SillyTavern (AGPL-3.0) ✅ DECIDED
Chosen over OpenWebUI. AIP_ is persona-first — SillyTavern's design vocabulary
(character cards, world info, expressions) maps directly onto AIP_'s architecture.
OpenWebUI is a ChatGPT-replacement shape, which is the wrong shape for this project.

Key alignments:
- AGPL-3.0 matches AIP_ license ethos exactly
- Pure frontend — delegates all inference to backend, no competing RAG pipeline
- Official Extension-VRM with emotion-driven animation — working Phase 4 preview today
- classify → talkinghead → avatar state pipeline already exists
- World Info = AIP_ global_memory + per-profile context injection

UI vocabulary concern (minor): character card / lorebook terminology. Documentation
problem, not architecture problem.

### Vector Store — Qdrant (Apache 2.0) ✅ DECIDED
Chosen over ChromaDB. API stability, Rust performance, built-in debug web UI, native
SillyTavern vector storage support. ChromaDB has broken AIP_ twice already.

### Embeddings — Qdrant built-in FastEmbed ✅ DECIDED
fastembed removed as explicit dependency. qdrant-client[fastembed] manages it as
transitive dependency. Embedding via client.add() / client.query(query_text=...).

### Agent Orchestration — AG2 (Apache 2.0) ✅ DECIDED
Scientist reasoning loop: scientist → critic → re-evaluate.
AG2 is the active community fork of AutoGen (Apache 2.0).
AutoGen maintenance branch (MIT) is the fallback — frozen API is stable on local stack.
Microsoft Agent Framework rejected — cloud-first, not aligned with self-hosted ethos.

Stack position:
```
server.py (router + AUTO_BUDGET)
    ↓ invokes scientist for qualifying queries
AG2 loop (scientist ↔ critic ↔ re-evaluate)
    ↓ returns structured result
Persona synthesises final output
```

### Lightweight Architectural Rules ✅ DECIDED
1. Delegation constraint — workers never call workers. Router decides only.
2. Explicit state object — pipeline context as typed dict, not implicit prompt construction.
3. Decision logging — structured queryable log of every routing decision.

### Voice Pipeline ✅ DECIDED (Phase 5 — stack locked)
| Component | License | Role |
|---|---|---|
| OpenWakeWord | Apache 2.0 (code) / CC-BY-NC-SA (models) | Wake word detection |
| Whisper.cpp | MIT | STT |
| Piper TTS (OHF-Voice/piper1-gpl) | GPL-3.0 | TTS |
| Wyoming protocol | MIT | Voice pipeline coordination |

OpenWakeWord ships a pre-trained "hey jarvis" model. Custom wake words trainable on
synthetic Piper audio (~200KB ONNX). CC-BY-NC-SA does not restrict personal
self-hosted open source use. GPL-3.0 (Piper) compatible with AGPLv3 as dependency.

Pipeline:
```
OpenWakeWord → wake event
    → Whisper.cpp STT → text → FastAPI /chat
    → Persona response → Piper TTS → audio + phoneme timing
    → STATE channel → SillyTavern Talkinghead / Godot (Phase 4+)
```

---

## System Components
> Cross-cutting infrastructure. Not phases — no completion state. Evolve as system grows.

### Component: Task Board
> Persistent async work queue. Replaces in-memory jobs dict in server.py.
> All background work flows through one place — experts, ingest, sleep cycle, agents.
> Persona never delegates or coordinates. It only surfaces completed results naturally.

**Philosophy**
- Persona is a presence, not a coordinator
- MoEs and agents pull work and write results independently
- Persona checks board on each response cycle — surfaces results like notifications
- Results surface once, marked SURFACED — never shown again
- Attribution neutral — "this came in while we were talking"

**Self-Ordering Queue**
- Tasks ordered by estimated difficulty (low first)
- Difficulty auto-estimated at creation via lightweight embedding comparison
- Difficulty recalibrates from actual time_score of completed tasks
- Easy tasks complete fast, surface soon — heavy tasks run in background
- All async — persona never waits on any task

**Surfacing Behavior**
```
Result becomes READY
    → user present  → persona surfaces naturally in next response
    → user absent   → pending_surface = true, result waits
    → user returns  → pending results surfaced before responding to new input
    → surfaced      → status = SURFACED, never shown again

Surface priority
    → normal        → surfaced when contextually relevant
    → high          → floated to top of next interaction regardless of topic
```

**SQLite Schema — data/tasks.db**
```
tasks
    task_id             unique ID
    profile             which profile owns this task
    source              "user_request" | "sleep_cycle" | "ingest" | "agent"
    description         what needs doing
    assigned_to         "scientist" | "coder" | "agent" | null
    difficulty          estimated 1-5 (auto-assigned, recalibrates from time_score)
    status              QUEUED | RUNNING | READY | SURFACED | FAILED
    created_at          timestamp
    started_at          timestamp
    result_ready_at     timestamp
    completion_time     seconds (result_ready_at - started_at)
    time_score          normalised — low = fast = easier (feeds difficulty estimator)
    surfaced_at         timestamp
    result              completed output
    pending_surface     true if user was absent when result became READY
    surface_priority    normal | high
    error               failure detail if status = FAILED
```

**Performance Log**
Task board doubles as system performance profile. Query to see which task types run
longest, which models handle what, where bottlenecks appear.

**Config keys**
```
TASK_TIME_SCORE_WINDOW=100
TASK_SURFACE_PRIORITY_THRESHOLD=300
```

**Phase touchpoints**
```
Phase 1   → replaces jobs dict; scientist worker writes to task board
Phase 2   → persona checks task board on each response cycle
Phase 3   → daemon health monitor aware of task board state
Phase 6   → ingest worker creates tasks for classification jobs
Phase 7   → sleep cycle creates and consumes consolidation tasks
Phase 8   → AG2 agent creates and consumes tasks
```

### Component: SQLite Stores
> Two databases in data/. Both portable with the project folder.

**data/conversations.db**
```
conversations
    turn_id             unique ID per exchange
    profile             profile name
    timestamp           turn timestamp
    user_message        full user input
    assistant_response  full assistant response
    window_id           assigned when window closes (null until then)
    distilled           false until Sleep Cycle processes
    distilled_at        timestamp when processed
    summary_chunk_id    reference to resulting RAG chunk
```

**data/tasks.db** — see Task Board schema above.

### Component: RAG Layer (Qdrant — post-migration)
> Replacing ChromaDB. Hybrid search: BM25 sparse + dense vectors.

**Embedding model:** BAAI/bge-small-en-v1.5 via Qdrant built-in FastEmbed
(Nomic Embed benchmark candidate — better long-doc performance)

**Collections**
```
global_memory            shared across all profiles
profiles/<n>/memory      per-profile (not yet wired to API)
sorting_line/<slug>      auto-created by Phase 6 ingest pipeline
```

**Memory types (typed Qdrant payloads)**
```
kind: fact              distilled facts from conversations
kind: episode           timestamped summaries — "on [date] we discussed X"
kind: entity            named people, projects, concepts
kind: procedural        "to do X, the user prefers Y approach"
kind: chat_log          full turn audit (not retrieved by default)
kind: scientist_note    expert output (retrieved for science topics)
```

**Hybrid RAG**
Qdrant native sparse + dense. BM25 handles specific names, dates, precise terms where
pure semantic similarity fails. Collection config change only — no extra dependencies.

**Chunk Metadata Schema**
```
source_type         "conversation" | "ingest"
source_ref          window_id (conversation) | filename (ingest)
ingest_at           timestamp
collection_origin   collection where chunk first landed
collection_current  current collection slug
tags[]              topic/domain tags, updated by Sleep Cycle
provisional         true until parent collection reaches MATURE
rel_targets[]       related chunk IDs (populated by Sleep Cycle)
rel_types[]         relationship label per target
rel_confidence[]    confidence score per relationship
rel_discovered_at[] timestamp per relationship discovery
```

### Component: Unix Socket IPC
> Daemon-owned. run/daemon.sock. Wiped and recreated on every daemon start.
> API never blocks on socket — silently skips if unavailable.
> Dependency strictly one-way: components → daemon.

**Current events:** ping (API sends on every request, fire and forget)

**Planned events**
```
profile_switched    idle detector resets
ingest_complete     consolidation worker prioritises new chunks
tts_speaking        avatar layer knows not to interrupt
task_ready          task board notifies persona of completed result
```

### Component: Job System — Current State & Known Issues

**Two disconnected job systems in server.py (do not communicate):**

System 1 — JSONL-backed registry:
  - jobs dict + _job_set() + _persist_job_event() + _load_persisted_jobs()
  - Restart-safe. Only called from /chat_submit which is DISABLED — dead code.

System 2 — File-based job tracking:
  - /agent/run writes .job.json, expects .result.json
  - taskman2.py does not exist — endpoint has no executor

**Critical bug: /agent/run is synchronous**
  - subprocess.run() blocks the entire event loop for up to 300s
  - No other endpoint can respond during execution
  - Fix: asyncio.create_subprocess_exec()

**Bug: relative path in /agent/run**
  - Path("run") / "jobs" is relative to uvicorn cwd, not AI_ROOT
  - Fix: AI_ROOT-based absolute path

**taskman2.py contract (defined by endpoint, not yet implemented)**
- Input: job JSON at run/jobs/<task_id>.job.json
- Output: result JSON at run/jobs/<task_id>.result.json
- CLI: taskman2.py <job_path> --repo <path> --out <result_path> --yes
- Timeout: 300 seconds

**Target architecture (Phase 3)**
```
/agent/run (async submit)
    → register in jobs dict via _job_set()
    → write job.json
    → push to asyncio.Queue
    → return job_id immediately

Background worker (asyncio task, started at app startup)
    → consumes asyncio.Queue
    → runs taskman2.py via asyncio.create_subprocess_exec()
    → writes result.json
    → updates job status via _job_set()

/jobs/{job_id} → polls status (already works)
```

---

## Roadmap

### Phase 1 — Core API (COMPLETE)
- [x] llama.cpp multi-server setup (persona + scientist)
- [x] FastAPI Companion API — /health, /chat, /chat_submit, /jobs, /v1/chat/completions
- [x] Silent expert routing (scientist in-band)
- [x] ChromaDB RAG — global memory
- [x] Multi-profile persona wrapper (persona.md / system_rules.md)
- [x] GPU offload — persona 35 layers, scientist 45 layers
- [x] AUTO_BUDGET planner
- [x] Memory distillation pipeline
- [x] Operational scripts

**Phase 1 gaps carried forward (incomplete)**
- [ ] Wire persona.md + system_rules.md into build_persona_prompt()
- [ ] Wire per-profile memory into memory_query / memory_add
- [ ] Replace in-memory jobs dict with Task Board (data/tasks.db)
- [ ] Verify looks_degenerate() quality heuristic in current server.py
- [ ] Verify two-stage self-repair loop in current server.py
- [ ] Rename run/llama-servers.env → run/config.env

### Phase 2 — Frontend & Storage Migration (ACTIVE)

**2a — Qdrant Migration (do first)**
- [ ] Confirm port 6333 clear of BrandonNet conflicts
- [ ] Install Qdrant, add to start/stop scripts
- [ ] Migrate server.py: QdrantClient replaces ChromaClient
- [ ] Remove fastembed import and manual embedding generation
- [ ] Configure Qdrant collections with built-in FastEmbed
- [ ] Implement hybrid RAG (BM25 + dense) in collection config
- [ ] Implement typed memory payloads (fact, episode, entity, procedural, chat_log)
- [ ] Benchmark Nomic Embed vs bge-small-en-v1.5
- [ ] Validate /memory/add and /memory/search against Qdrant
- [ ] Update start/stop/status/doctor scripts for Qdrant

**2b — SillyTavern Integration (after Qdrant stable)**
- [ ] Implement SSE streaming in /v1/chat/completions — BLOCKER for SillyTavern UX
- [ ] Install SillyTavern, wire to FastAPI /chat as backend
- [ ] Configure character card mapping to AIP_ persona profiles
- [ ] Map World Info to global_memory + per-profile context injection
- [ ] Bypass ST internal vector storage — use Qdrant via FastAPI only
- [ ] Validate persona identity and RAG flow through ST frontend
- [ ] Evaluate Extension-VRM for avatar prototype (Phase 4 preview)

**2c — Conversations persistence**
- [ ] Implement data/conversations.db schema
- [ ] Wire turn logging to conversations table
- [ ] Window detection (time gap / topic shift / hard cap)

### Phase 2.5 — Scientist Reasoning Loop (AG2)
- [ ] Evaluate AG2 on existing stack
- [ ] Implement scientist ↔ critic loop for analytical queries
- [ ] Integrate with AUTO_BUDGET
- [ ] Structured scientist output (JSON schema via llama.cpp grammar)
- [ ] Scientist results written to Task Board
- [ ] Fallback: if AG2 unstable, assess AutoGen maintenance branch

### Phase 3 — Always-On Daemon
> Single entry point. Run once, stays alive, self-heals. No CLI arguments.

- [ ] daemon.py — asyncio loop, child process map, signal handling, Unix socket
- [ ] Four asyncio tasks: health_monitor, idle_detector, ingest_worker, consolidation_worker
- [ ] Startup: read config.env, wipe logs, clean stale pids/socket, spawn children
- [ ] Shutdown: SIGTERM/SIGINT → signal children → SHUTDOWN_TIMEOUT → force kill
- [ ] Three-strike restart policy per child (STRIKE_WINDOW, STRIKE_BACKOFF_BASE)
- [ ] Fix /agent/run: asyncio subprocess, unified job tracking, AI_ROOT path
- [ ] Implement taskman2.py executor honouring established contract
- [ ] Async taskboard queue (asyncio.Queue consuming data/tasks.db)

**Child process list**
```
llama-persona       port 8080
llama-scientist     port 8083
companion-api       port 8000
sillytavern         port TBD
whisper-stt         port TBD (Phase 5)
piper-tts           port TBD (Phase 5)
```

**Config keys**
```
SHUTDOWN_TIMEOUT=10
STRIKE_WINDOW=300
STRIKE_BACKOFF_BASE=5
IDLE_TIMEOUT=1800
```

**Scripts disposition on daemon completion**
```
Absorbed (retire): start/stop_llama_servers.sh, start/stop_api.sh, start/stop_all.sh
Retained + updated: status.sh, doctor.sh, unified_test.sh, init_profiles.sh,
                    setup_native_stack.sh, clean.sh
```

### Phase 4 — Embodied Presence (Godot)
> SillyTavern Extension-VRM bridges until Godot is ready.

**Two-channel response (breaking change to server.py)**
```
RESPONSE: → text → SillyTavern + TTS
STATE:    → JSON avatar directives → Godot / ST Talkinghead

{
    "state": "talking",
    "emotion": "curious",
    "gesture": "slow_nod",
    "intensity": 0.7
}
```
State vocabulary defined in system_rules.md per profile.
Malformed STATE → hold last known state, never crash.

- [ ] Godot Engine avatar — idle / talk / gesture states
- [ ] Lip-sync from Piper phoneme timing
- [ ] Emotion/state parsing from STATE channel → avatar controller
- [ ] Desktop 2D camera view
- [ ] OpenXR / VR camera (optional stretch)

### Phase 5 — Voice Pipeline
> All voice compute on host. Clients capture and play audio only.

- [ ] OpenWakeWord daemon child — pre-trained "hey jarvis" model as starting point
- [ ] Whisper.cpp STT daemon child
- [ ] Piper TTS daemon child — CC BY 4.0 voice models only
- [ ] Wyoming protocol as coordination layer
- [ ] Phoneme timing → SillyTavern Talkinghead / Godot lip-sync
- [ ] tts_speaking IPC event → daemon socket

**Config keys**
```
IDLE_WINDOW_TIMEOUT=1800
TOPIC_SHIFT_THRESHOLD=0.35
MAX_WINDOW_SIZE=50
```

### Phase 6 — Auto-Contextual RAG Pipeline ("Sorting Line")
> Drop file into inbox/ → auto-classify and route.

- [ ] File watcher (watchdog) on inbox/
- [ ] Multi-format reader: .txt, .md, .pdf, .py, .json, .csv
- [ ] Semantic classifier — embed + compare against collection centroids
- [ ] Multi-bin routing — file can land in multiple collections
- [ ] No match → new PROVISIONAL collection with LLM-generated slug
- [ ] Ingest manifest log with confidence scores

**Collection lifecycle:** PROVISIONAL → MATURE → (MERGED | SPLIT)
Alias chain preserved on every rename — old names always resolve.

**Config keys**
```
INBOX_PATH=inbox/
```

### Phase 7 — Background Cognitive Consolidation ("Sleep Cycle")
> Runs during idle periods. Reviews knowledge, finds connections, maintains ontology.

- [ ] Awaits idle_signal — yields immediately when cleared
- [ ] Conversation distillation: distilled=false turns → LLM summary → RAG
- [ ] Relationship discovery: cross-collection similarity sweep
- [ ] Ontology maintenance: PROVISIONAL name re-evaluation, merge/split detection
- [ ] Insight journal: data/insights/YYYY-MM-DD.md
- [ ] Persona surfaces insights via Task Board at session start

**Config keys**
```
CONSOLIDATION_SWEEP_DEPTH=500
```

### Phase 8 — Agentic Layer (AG2)
> Parallel /agent endpoint alongside /chat. Existing routing untouched.
> LangGraph evaluated and deferred — premature given current stack complexity.
> AG2 chosen for consistency with Phase 2.5.

**Agent graph**
```
/agent request
    → Planner → Research → Expert(s) → Evaluate → iterate or finalize
    → Persona node synthesizes output in-character
    → Result written to Task Board, surfaced by persona
```

- [ ] Tool calling: web search, sandboxed code execution, file reads, RAG queries
- [ ] Full scientist loop: Question → Hypothesis → Research → Evaluate → Answer
- [ ] Max iterations configurable, logged to logs/agent.log

**Phase 9 Candidate — CrewAI**
Potential observable multi-agent crew replacing silent MoE layer.
All crew results flow through Task Board. Evaluate when Phase 8 is mature.

---

## TODO (Active)

| # | Item | Priority | Notes |
|---|---|---|---|
| 1 | Run unified_test.sh — full validation | High | Do before touching server.py |
| 2 | Confirm port 6333 clear of BrandonNet | High | Required before Qdrant install |
| 3 | Qdrant migration — server.py (need current file) | High | Phase 2a |
| 4 | Implement SSE streaming in /v1/chat/completions | High | Phase 2b BLOCKER for SillyTavern |
| 5 | SillyTavern integration | High | Phase 2b — after Qdrant stable |
| 6 | Fix start_api.sh: MEMORY_DISTILL_ENABLED exported after uvicorn starts | High | Bug — env var never reaches server |
| 7 | Fix start_api.sh: source llama-servers.env before port exports | High | Bug — SCIENTIST_PORT defaults to 8081 |
| 8 | Fix /agent/run: asyncio.create_subprocess_exec | High | Bug — blocks entire event loop up to 300s |
| 9 | Fix /agent/run: AI_ROOT-based absolute path | Medium | Bug — relative path error |
| 10 | Unify two disconnected job systems in server.py | High | Phase 3 prerequisite |
| 11 | Verify looks_degenerate() + self-repair loop in current server.py | High | Listed as existing in old spec — not found in uploaded file |
| 12 | Wire persona.md + system_rules.md into build_persona_prompt() | High | Phase 1 gap |
| 13 | Wire per-profile memory into memory_query / memory_add | High | Phase 1 gap |
| 14 | Replace in-memory jobs dict with Task Board (data/tasks.db) | High | Phase 1 gap |
| 15 | Implement task difficulty estimator + time_score feedback loop | High | Task Board component |
| 16 | Rename run/llama-servers.env → run/config.env | Medium | Old spec decision — not yet done |
| 17 | Implement explicit state object in server.py | Medium | Architectural rule |
| 18 | Upgrade api.log to structured decision logging | Medium | Architectural rule |
| 19 | Encode delegation constraint in server.py | Low | Architectural rule |
| 20 | Evaluate AG2 for scientist loop | Medium | Phase 2.5 |
| 21 | Benchmark Nomic Embed vs bge-small-en-v1.5 | Low | During Qdrant migration |
| 22 | Suppress <think> tags from scientist output | Medium | Known issue |
| 23 | Confirm AGPL-3.0 + Linking Exception LICENSE at repo root | Medium | Housekeeping |
| 24 | Add AIP_ entry to ~/Git/sterilize.sh | Medium | Currently only Netstack covered |
| 25 | Update doctor.sh: Qdrant checks, port 8083, config.env refs | Medium | Stale references |
| 26 | Update status.sh: consistent scientist terminology | Medium | Mixed reasoning/scientist/coder refs |
| 27 | Update README_models_hardware.md: paths, terminology | Low | References ~/AI/ and old paths |
| 28 | Implement persona task surfacing on response cycle | High | Phase 2 |
| 29 | Implement topic routing policy — coding→coder, math→scientist | Medium | Phase 1 gap |
| 30 | Plan daemon.py — asyncio loop, child process map, socket | High | Phase 3 |
| 31 | Verify Qwen2.5-14B-Instruct exact license on HuggingFace | Low | License audit |
| 32 | Choose Piper voice model — verify CC BY 4.0, avoid Blizzard voices | Low | Phase 5 prereq |
| 33 | Review scripts/archive/ — prune if safe | Low | Housekeeping |
| 34 | Implement conversations.db schema and turn logging | High | Phase 2c |
| 35 | Verify tenacity usage in memory_distiller.py | Medium | In requirements but not in server.py |

---

## Issues & Fixes Log

| Date | Issue | Resolution |
|---|---|---|
| 2026-04-06 | AI_ROOT defaulting to $HOME/AI after directory migration | ✅ Fixed — sed updated all scripts |
| 2026-04-06 | Stale pid files for persona and scientist | ✅ Removed |
| 2026-04-06 | AIP_ running flat in ~/Live/AIStack/ | ✅ Moved to ~/Live/AIStack/Project_Persona/ |
| 2026-04-06 | Port 8081 conflict with OTS BrandonNet container | ✅ Scientist moved to 8083 |
| 2026-04-06 | llama-server missing libmtmd.so.0 at runtime | ✅ LD_LIBRARY_PATH injected in start_llama_servers.sh |
| 2026-04-06 | venv shebangs pointing to old $HOME/AI path | ✅ venv rebuilt with --clear |
| 2026-04-06 | server.py syntax error — escaped docstring quotes | ✅ Restored correct triple-quote docstring |
| 2026-04-06 | start_api.sh not sourcing llama-servers.env | ✅ Source block added before exports |
| 2026-04-06 | Chroma KeyError('_type') — version mismatch | ✅ Old sqlite3 data wiped, fresh init |
| 2026-04-06 | chromadb Settings() API changed in 0.6.x | ✅ Settings parameter removed from PersistentClient |
| 2026-04-07 | BAD_MEMORY_PATTERNS referenced chroma/fastembed | ✅ Updated to qdrant in server.py |
| 2026-04-07 | /agent/run uses subprocess.run() — blocks event loop | ⏳ Documented — fix in Phase 3 |
| 2026-04-07 | Two disconnected job systems in server.py | ⏳ Documented — unify in Phase 3 |
| 2026-04-07 | /agent/run uses relative Path("run")/jobs | ⏳ Documented — fix with AI_ROOT |
| 2026-04-07 | MEMORY_DISTILL_ENABLED exported after uvicorn in start_api.sh | ⏳ Fix before next restart |
| 2026-04-07 | taskman2.py does not exist | ⏳ Documented — implement in Phase 3 |

---

## File Change Tracker

| Session Date | Files Modified | Summary |
|---|---|---|
| 2026-04-06 | scripts/start_llama_servers.sh | LD_LIBRARY_PATH injection, AI_ROOT path fix |
| 2026-04-06 | scripts/start_api.sh | Source llama-servers.env, AI_ROOT path fix |
| 2026-04-06 | run/llama-servers.env | SCIENTIST_PORT changed 8081→8083 |
| 2026-04-06 | services/api/server.py | Syntax fix, chromadb Settings removed |
| 2026-04-06 | AIP_knowledge.md | Created — full session state captured |
| 2026-04-07 | services/api/server.py | BAD_MEMORY_PATTERNS: chroma/fastembed → qdrant |
| 2026-04-07 | requirements.txt | Rebuilt — Qdrant migration, exact pins |
| 2026-04-07 | AIP_knowledge.md | Full consolidation — merged old architecture spec with current session decisions |

---

## Key File Reference

| File | Purpose |
|---|---|
| `services/api/server.py` | FastAPI Companion API |
| `run/llama-servers.env` | Port / model / GPU layer config (→ rename to config.env) |
| `data/tasks.db` | SQLite — task board, job queue, difficulty scores, performance log |
| `data/conversations.db` | SQLite — chat history, windowing state, distillation tracking |
| `data/insights/` | Sleep Cycle journal — YYYY-MM-DD.md insight entries |
| `inbox/` | User-facing file drop folder — sorting line monitors this |
| `scripts/start_llama_servers.sh` | Brings up persona + scientist servers |
| `scripts/start_api.sh` | Starts uvicorn / FastAPI |
| `scripts/unified_test.sh` | Full end-to-end integration test |
| `scripts/doctor.sh` | Diagnostics + smoke tests |
| `scripts/status.sh` | Quick status summary |
| `persona/profiles/default/` | Default profile (persona.md / system_rules.md) |
| `persona/global_memory/` | Shared cross-profile Qdrant vector store (post-migration) |

---

## License Review

| Component | License | AGPLv3 Compatible | Notes |
|---|---|---|---|
| llama.cpp | MIT | ✅ | No restrictions |
| whisper.cpp | MIT | ✅ | No restrictions |
| FastAPI | MIT | ✅ | No restrictions |
| uvicorn / httpx / pydantic | MIT / BSD | ✅ | No restrictions |
| Qdrant | Apache 2.0 | ✅ | Replaces ChromaDB |
| qdrant-client | Apache 2.0 | ✅ | Pinned 1.16.2 |
| AG2 | Apache 2.0 | ✅ | AutoGen community fork |
| AutoGen (fallback) | MIT | ✅ | Maintenance mode — stable frozen API |
| SillyTavern | AGPL-3.0 | ✅ | Ethos match — same license as AIP_ |
| Godot Engine | MIT | ✅ | Engine license doesn't touch project content |
| SQLite | Public domain | ✅ | No restrictions |
| Piper TTS (OHF-Voice/piper1-gpl) | GPL-3.0 | ✅ | GPL compatible with AGPLv3 as dependency |
| OpenWakeWord | Apache 2.0 (code) / CC-BY-NC-SA (models) | ✅ | NC does not restrict personal self-hosted use |
| Qwen2.5-14B-Instruct | Apache 2.0 | ✅ | Verify exact model card on HuggingFace |
| Meta-Llama-3.1-8B-Instruct | Meta Community License | ⚠️ | Not in repo — user provided |
| Piper voice models | Varies (CC BY 4.0 / Blizzard) | ⚠️ | Not in repo. CC BY 4.0 requires attribution. Blizzard = research-only |
| Microsoft Agent Framework | MIT | ❌ | Rejected — Azure-first, cloud dependency |

---

## Git Milestone Log

| Tag | Description | Date |
|---|---|---|
| v1.1-post-migration | Full stack running at ~/Live/AIStack/Project_Persona/ | 2026-04-06 |

---

*This file is maintained as a living document. Update after every session.*
