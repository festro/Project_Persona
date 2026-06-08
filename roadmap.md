# Project_Persona -- Roadmap

Single source of truth for FEATURE / TRACK completion status, organized as a
phase ladder from basic functionality to extended functionality. Each phase is
"locked" to a functional state: it has an Exit Gate (concrete, testable
acceptance criteria) that must be green before the next phase starts.

Last updated: 2026-06-07 1110 PDT by Claude

## Boundaries (do not duplicate)

- `roadmap.md` (this file) -- owns the cumulative feature list and completion
  state. The "what exists / what's done / what's next, and how we prove it."
- `todo.md` -- short-term only ("just finished" / "next up"); points at phase or
  track IDs here, does not restate them.
- `changelog.md` -- records WHEN a feature or gate flipped state.
- `knowledge.md` -- architecture and scope (the "what it is / how it works").
  Phase numbers and the architecture-roadmap descriptions live there; this file
  mirrors the numbering and tracks status + gates only.

Keep ASCII (see `WORKFLOW.md`). When a gate flips, bump the stamp here and add a
`changelog.md` entry.

## How to read this

Status markers:

- `[x]` done / verified
- `[~]` in progress
- `[ ]` planned, not started
- `[-]` deferred / optional (has a documented trigger; not on the critical path)

Phase numbers 1-9 match `knowledge.md` "Architecture roadmap". Phase 0 is added
here for the runtime/dev-env foundation that precedes Phase 1; Phase 0.5 tracks
cross-OS/arch portability hardening. Phase 10 is a new
extended track (decentralized node mesh) beyond that roadmap; see
`docs/distributed_nodes.md`. Phase numbering is
a FUNCTIONAL / dependency ladder, not necessarily work order -- current execution
focus is tracked in `todo.md` and can span phases (e.g. the Hermes H-track in
Phase 8 is near-term but functionally late).

Work tracks referenced: T0-T4 = Qwen3.6 model-swap + core integration; H1-H6 =
Hermes adoption; M-series = single-model migration milestones.

## Current position

Active: Phase 1 completion. Foundation (Phase 0) is green. Qwen3.6 llama-server now
stands up LIVE on :8090 (Windows, via manage.py, 2026-06-07) with the API on :8000
and a passing /agent/run smoke; thinking mode is active under --jinja. Remaining
Phase 1 proof: live /chat persona replies + streaming + per-topic sampling
(no_think vs think) and embedder_ok/chroma_ok on /health. See `todo.md`.

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

Exit Gate (MET): bootstrap installs the full stack with no source builds; core
import smoke test passes; the API process boots; the offline API test suite
(`tests/test_api_offline.py`) is green.

## Phase 0.5 -- Cross-OS / cross-arch portability hardening  [~] IN PROGRESS

Goal: any node runs the same way on Windows and Linux, x86-64 and ARM64, on
CPU/CUDA/ROCm/Vulkan. Apple (macOS / Apple Silicon / Metal) is not a
consideration -- no effort spent, not tested; incidental compatibility is fine,
but it is never weighed. Underpins everything, especially the Phase 10 mesh. Full
audit + support matrix:
`docs/portability_audit.md`.

- [x] /agent/run uses sys.executable (was literal python3; broke Windows portable)
- [~] Single cross-platform launcher `manage.py` (up/down/toggle/status/doctor/
      capabilities/test/panel) replacing the bash/ps1 split (no bash for core
      lifecycle). LIVE-VALIDATED on Windows (RX 9060 XT) 2026-06-07: toggle brought
      the full stack up on :8090/:8000 and tore it down cleanly; test playbook green
      incl. live /agent/run; web panel drove it. Pure stdlib. Bash lifecycle scripts
      archived to scripts/archive/ (Phase C 2026-06-07) -- core lifecycle is now
      manage.py-only. Windows-side VALIDATED 2026-06-07 (Daemonic-PC, RX 9060 XT):
      status/capabilities/doctor all green under portable 3.11.9 -- config.toml read,
      run/node_capabilities.json written, accel detect+select=vulkan, T1 safe-config
      pass; AST/syntax re-check clean; full live CLI lifecycle proven (up -> status
      -> doctor --deep live completion smoke -> test quick: offline 14/14 + health
      -> down -> clean). The Linux x64 + ARM64 live passes remain DEFERRED (no
      hardware on hand; trigger: hardware available).
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
      now with a 3-tier accel classification (Tier 1 selectable CUDA/ROCm/SYCL/
      Vulkan/OpenCL/CANN/MUSA; Tier 2 in-progress; Tier 3 detect-but-never-select
      Hailo/Coral/Gaudi/Intel-NPU) + "select only what the binary supports".
      IMPLEMENTED 2026-06-06 (changelog 2014): `manage.py capabilities` +
      detection layer + accel-aware `start_llama` (H3) + doctor accel section;
      Windows-side VALIDATED 2026-06-07 (capabilities + doctor green;
      node_capabilities.json written). Minor: capabilities reports llama_build=null
      while doctor detects build b9219 -- see todo fix-its. Mesh wiring stays
      Phase 10.
- [~] H3 accel selection: `start_llama` backend-aware (no forced Vulkan on
      CUDA/ROCm/SYCL nodes); LLAMA_BACKEND override + capabilities detection.
      Done 2026-06-06; selection verified on the AMD/Vulkan host (selected=vulkan)
      2026-06-07. The "no forced Vulkan on CUDA/ROCm/SYCL" proof needs a non-Vulkan
      node and rides with the deferred Linux/ARM64 pass.
- [x] Cross-platform IPC decision (DONE 2026-06-06): NATS+JetStream is the primary
      control-plane bus (nats-server supervised as a Phase 3 daemon child, loopback,
      JetStream R=1) -- groundwork for the Phase 10 mesh -- with a stdlib loopback-TCP
      compatibility fallback, both behind one EventBus interface. Unix sockets ruled
      out (no asyncio AF_UNIX on the Windows ProactorEventLoop). See
      docs/ipc_decision.md.
- [ ] Per-OS egress story: WireGuard mesh + host firewall baseline; netns/iptables
      as a Linux-only bonus
- [ ] Cross-OS installer/doctor parity (Windows + Debian + other Linux)

Exit Gate: a node bootstraps, runs, self-checks (doctor), and serves /chat on
Windows x64, Linux x64, and Linux ARM64 -- CPU plus at least one GPU accel --
through one entrypoint, with no bash required for core lifecycle.
NOTE 2026-06-06: the Linux x64 + ARM64 legs of this gate are DEFERRED pending
hardware (trigger: hardware available); the Windows x64 leg proceeds now. The
phase cannot go GREEN until the deferred legs are validated.

## Phase 1 -- Core serving and companion API  [~] IN PROGRESS

Goal: a single local model behind the FastAPI companion API returns real
persona replies over both the native and OpenAI-compatible paths.

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
      chat_template_kwargs/messages migration is folded into T2.4 (its --jinja
      reasoning_content split is the same world).
- [x] T2.3 preserve_thinking for Hermes-originated requests -- DONE 2026-06-07
      (Path A): preserve_thinking flag (req field + PRESERVE_THINKING_DEFAULT, off
      by default); split_reasoning() pulls in-band <think> out before sanitizing;
      preserve=true returns the answer un-sanitized + reasoning (`reasoning` on
      /chat, `reasoning_content` on /v1 incl. stream). VALIDATED Windows-side:
      offline suite 35/35 (preserve logic exercised through the real /chat + /v1
      endpoints). Live-model spot check folded into the Phase 1 Exit Gate proof.
      DESIGN NOTE: preserve mode also skips the lossy persona
      two-part sanitizer (agent loops want the full answer) -- revisit if persona
      formatting is ever wanted alongside preserved reasoning.
- [x] T2.4 --jinja messages migration -- CODE DONE 2026-06-07 (OFF by default,
      PERSONA_USE_MESSAGES). New query_llama_messages (POST /v1/chat/completions with
      chat_template_kwargs{enable_thinking}; parses content + reasoning_content +
      usage), build_persona_messages (system/user split, no /think prefix), and a
      persona_generate() helper that both /chat and /v1 call -- messages path when on,
      the proven raw /completion path (byte-identical) when off. Server reasoning_content
      preferred; split_reasoning is the in-band fallback. /health persona_use_messages
      + persona_chat_url. Off-mount verified (functions AST OK; parse logic 6/6; endpoint
      wiring balanced). LIVE VALIDATION REQUIRED -- the only piece that can't be proven
      offline (real --jinja reasoning_content split). LIVE VALIDATED 2026-06-07 1746
      (exit_gate_live [messages], PERSONA_USE_MESSAGES=1): reasoning came from the
      server reasoning_content and text was <think>-free. FOLLOW-UP: retire the
      post-hoc sanitizer on the messages path.
- [ ] M6 single-model migration milestone confirmed (M2b passed, M5 done)
- [x] Per-profile Chroma collections connected to the API -- CODE DONE 2026-06-07
      (OFF by default): RAG_PER_PROFILE routes memory_add/query to a per-profile
      collection ("mem_<profile>") via _get_collection; off = the single shared
      RAG_GLOBAL_COLLECTION exactly as before. /health rag_per_profile +
      rag_collections. VALIDATED: offline suite 56/56 (name logic + health). LIVE
      VALIDATED 2026-06-07 1752 (exit_gate_live [per-profile], RAG_PER_PROFILE=1 +
      RAG_ENABLED=1): mem_alice/mem_bob collections created. CAVEAT: turning it on
      does not migrate existing global_memory rows. RESIDUE: the run also created
      untracked persona/profiles/alice/ + bob/ on disk -- gitignore or clean up.
- [x] Topic routing policy -- DONE 2026-06-07 (OFF by default): deterministic keyword
      classify_topic(text) + resolve_topic precedence (topic="auto" always classifies;
      explicit non-chat respected; "chat"/absent classifies only when TOPIC_ROUTING=1).
      Resolved topic drives thinking/sampling/RAG/inband downstream. /health
      topic_routing(+topics); /chat debug topic_routing. VALIDATED: offline suite 56/56
      (auto->math drives the think preset through the real endpoint).
- [x] Task Board (`data/tasks.db`) replaces the in-memory jobs dict -- CODE DONE
      2026-06-07: stdlib-sqlite3 services/api/taskboard.py (init/task_set upsert-
      merge/task_get/task_list/delete/count + one-time jobs.jsonl migration); server
      wired (TASKS_DB config, init at startup, /agent/run records run->ok/error/
      timeout, /jobs list + /jobs/{id} from the board, /health task_store). Off-mount
      verified (taskboard 15/15; server AST+COMPILE OK). VALIDATED: offline suite
      56/56 (/jobs CRUD + health task_store). LIVE VALIDATED 2026-06-07 1758: a real
      /agent/run (smoke-taskboard, read-only job) ran taskman2 and recorded ok into
      the board; /jobs + /jobs/{id} returned the row with timestamps + returncode 0;
      /health task_store count=1.

Exit Gate: llama-server live on :8090; `/chat` and `/v1/chat/completions` return
real persona replies; a "chat" topic resolves no_think and
science/coding/math/research resolve think (verify via `/chat` debug
`sampling_preset`); live `stream=true` produces SSE chunks + [DONE] and non-zero
`prompt_tokens`; `/health` green with embedder_ok=true and chroma_ok=true.
PROVEN 2026-06-07 (changelog 1222) on Qwen3.6 via tests/exit_gate_live.py: ALL
REQUIRED PASS. Phase stays [~] until the remaining feature items below close.

## Phase 2 -- Frontend and UX  [ ] NOT STARTED

Goal: a thin client over the API with durable conversation history.

- [ ] OpenWebUI as thin client (currently dormant, port 3000)
- [ ] SQLite `conversations.db` as source of truth for history
- [ ] Persona task surfacing in the UI
- [ ] Hybrid conversation windowing
- [ ] Phase 2a: migrate vector store ChromaDB -> Qdrant (Qdrant + fastembed are
      also the 3.14-unblock path)

Exit Gate: a user can hold a multi-turn conversation through the UI; turns
persist in `conversations.db` and reload correctly; windowing keeps context
within budget; retrieval works against Qdrant with parity to the Chroma path.

## Phase 3 -- Always-on daemon (daemon.py)  [ ] NOT STARTED

Goal: one supervised entry point for all services.

- [ ] Single asyncio daemon with a child-process map (llama-server, API,
      nats-server, others)
- [ ] Three-strike restart policy
- [ ] NATS-based IPC (local nats-server child, loopback; stdlib loopback-TCP compat
      fallback; EventBus interface -- see docs/ipc_decision.md); events beyond `ping`
      (profile_switched, ingest_complete, tts_speaking, task_ready)
- [ ] Fresh-logs-on-start contract; absorbs the start/stop scripts

Exit Gate: daemon brings up and supervises all children; killing a child
triggers restart within policy and a fourth failure stays down; IPC events are
delivered one-way (components -> daemon) without the API ever blocking on it.

## Phase 4 -- Embodied presence (Godot)  [-] OPTIONAL

Goal: optional 3D/VR client driven by a two-channel protocol.

- [-] Persona emits RESPONSE (text/TTS) + STATE (JSON avatar directives)
- [-] Godot client consumes the protocol

Exit Gate: the avatar reflects STATE directives in sync with RESPONSE output for
a scripted exchange.

## Phase 5 -- Voice pipeline  [-] OPTIONAL

Goal: local speech in/out as daemon children (host-side compute only).

- [-] Whisper.cpp STT
- [-] Piper TTS (GPL-3.0)

Exit Gate: spoken input is transcribed, answered, and spoken back end-to-end,
fully offline.

## Phase 6 -- Auto-contextual RAG ("sorting line")  [ ] NOT STARTED

Goal: dropped files become retrievable, classified memory automatically.

- [ ] `inbox/` file watcher
- [ ] Multi-format reader
- [ ] Semantic classifier + multi-bin routing
- [ ] Provisional/mature collection lifecycle with alias chains

Exit Gate: a file dropped in `inbox/` is read, classified, routed to the correct
collection, and retrievable via RAG; provisional entries promote to mature on the
defined trigger.

## Phase 7 -- Background consolidation ("sleep cycle")  [ ] NOT STARTED

Goal: idle-time memory maintenance.

- [ ] Idle-triggered conversation distillation
- [ ] Relationship discovery + ontology maintenance
- [ ] Insight journaling

Exit Gate: an idle period triggers a consolidation pass that distills recent
conversations, links related memories, and writes an insight journal entry,
without disrupting foreground responsiveness.

## Phase 8 -- Agentic layer (Hermes Agent)  [~] FOUNDATION STARTED

Goal: Hermes runs as a daemon child pulling background work from the Task Board.
(Near-term in execution despite the late phase number; gated on single-model
migration M6.)

- [x] T1: per-profile `config.yaml` safe-config (egress tools disabled, local
      model pinned, no cloud fallback) generated by `init_profiles.sh`; `doctor.sh`
      validates the default profile as the T1 gate (implemented 2026-06-04)
- [ ] T1 close-out on a live host: create `env_hermes/` + install hermes-agent so
      `doctor.sh` reports env_hermes_installed=yes
- [ ] H1: validate Hermes `config.yaml` key paths (model.sampling.*,
      tools.disabled) against the installed hermes-agent (schema-provisional now)
- [ ] H2-H6: Hermes pulls from the Task Board (Tenacity-style failure semantics),
      role-prefix template library, cache_prompt amortization
- [ ] Runtime egress containment: kernel netns/iptables + daemon env hygiene
      (config-time half exists; runtime half H1.6 still required)

Exit Gate: Hermes runs as a daemon child, claims a Task Board task, executes it,
and writes results back for the persona to surface; egress is contained at both
config and kernel level; `doctor.sh` is fully green.

## Phase 9 -- DELETED

CrewAI candidate, superseded by Hermes (Phase 8). Kept as a numbering placeholder.

## Phase 10 -- Decentralized cooperative node mesh  [ ] DESIGN (extended track)

Goal: system-agnostic nodes that run standalone and, when networked, pool
throughput and specialized capability BOINC-style. New track (not in
knowledge.md's original architecture roadmap). Depends on Phase 1 Task Board,
Phase 2a Qdrant, Phase 3 daemon. Full design + rationale:
`docs/distributed_nodes.md`.

Decisions locked: distribute tasks not single inferences; NATS+JetStream with a
per-node server clustered as equals (3/5-node JetStream core for durable state,
ephemeral nodes as clients/leaf); shared-token admission with token-rotation as
the hard evict; self-generated per-node keys + NATS connection log ($SYS/connz)
+ TTL'd KV roster for identity/membership; validation/quorum + advisory key
deny-list for bad actors; WireGuard mesh for transport + egress containment.

- [ ] Stage 0: `LLAMA_HOST` cross-node inference offload (no new infra)
- [ ] Stage 1: 2-node NATS + JetStream work queue; claim -> execute -> result;
      clean reclaim on worker failure
- [ ] Stage 2: connection log + self-gen node keys + KV roster; dynamic join +
      capability-aware routing
- [ ] Stage 3: 3-server JetStream core (R=3); reputation + advisory deny-list +
      token-rotation evict; redundant-execution validation/quorum
- [-] Stage 4: WireGuard substrate; Object-store artifact transfer; superclusters
      at scale

Exit Gate (track): a node joins with only the shared token, appears in the roster
by hostname+key with advertised capabilities, claims and runs capability-matched
work, returns validated results, and a node loss reclaims cleanly; the durable
core survives losing one member.

---

## Extended / deferred (no active trigger)

- [-] Vision input
- [-] MTP / speculative decoding
- [-] Dual-memory unification (conversations.db + Chroma)
- [-] Qwen3.5/3.6 maturity re-evaluation after ~2026-08 (TODO #36)

## Cross-cutting components

These evolve across phases rather than completing once (detail in `knowledge.md`
-> System components): Task Board (`data/tasks.db`), SQLite stores
(`conversations.db`), ChromaDB/RAG layer, Unix-socket IPC. Their readiness is
tracked inside the phase whose Exit Gate first depends on them (Task Board ->
Phase 1/8; conversations.db -> Phase 2; IPC -> Phase 3).
