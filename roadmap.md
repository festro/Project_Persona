# Project_Persona -- Roadmap

Single source of truth for completion status, organized as a Phase ladder from
basic functionality to extended functionality. Each Phase locks to a functional
state: it has an Exit Gate (a concrete, testable checklist) that must be green
before the next Phase starts.

Last updated: 2026-06-14 1500 PDT by Claude

## Boundaries (do not duplicate)

- `roadmap.md` (this file) -- owns the cumulative Item list and completion state.
  The "what exists / what's done / what's next, and how we prove it."
- `todo.md` -- short-term only ("just finished" / "next up"); points at Phase or
  Item IDs here, does not restate them.
- `changelog.md` -- records WHEN an Item or Exit Gate flipped state.
- `knowledge.md` -- architecture and scope (the "what it is / how it works").
  Phase numbers and the architecture descriptions live there; this file mirrors
  the numbering and tracks status + Exit Gates only.

Keep ASCII (see `WORKFLOW.md`). When an Exit Gate flips, bump the stamp here and
add a `changelog.md` entry.

## Terms (one word, one meaning)

To stop the term-soup, this file uses exactly four nouns. The retired synonyms
("track", "milestone", "stage", "leg") no longer appear -- if you see them in
older `changelog.md` / handoff entries, read them as "Item" or "Exit Gate".

- **Phase** -- a numbered level on the ladder (0 through 10). The unit that locks.
- **Item** -- a unit of work inside a Phase (the checkboxes). Each Item keeps a
  stable ID for cross-reference. Some IDs are historical family labels and are
  kept verbatim so old entries still resolve: `T0-T4` (Qwen3.6 swap + core
  integration), `H1-H6` (Hermes adoption), `M*` (single-model migration). Newer
  Items use plain `Phase.N` numbering (e.g. `9.0`). These IDs are labels only --
  NOT a second hierarchy above the Phases.
- **Exit Gate** -- the single testable pass/fail checklist that closes a Phase.
  Each line is its own check with a Status marker. (Retired words for this:
  "gate", "milestone".)
- **Status** -- the marker on any Item or Exit-Gate check:
  - `[x]` done / verified
  - `[~]` in progress
  - `[ ]` planned, not started
  - `[-]` deferred / optional (has a documented trigger; not on the critical path)

Phase numbers 1-8 match `knowledge.md` "Architecture roadmap". Phase 0 covers the
runtime/dev-env foundation that precedes Phase 1; Phase 0.5 covers cross-OS/arch
portability hardening; Phase 9 is an extended line beyond the core ladder for the
decentralized node mesh (see `docs/distributed_nodes.md`); Phase 10 is the
full-system / feature-test capstone that validates everything end to end. NOTE:
`knowledge.md` + `docs/distributed_nodes.md` still call the mesh "Phase 10" and
keep a CrewAI "Phase 9" -- they need a sync to this numbering (swap done here
2026-06-14). The ladder is a FUNCTIONAL / dependency order, not work order --
current execution focus lives in `todo.md` and can span Phases (e.g. the Hermes
Items in Phase 8 are near-term but functionally late).

## Current position

Phases 0 and 1 are GREEN. The single Qwen3.6-35B-A3B model serves LIVE on :8090
behind the companion API on :8000 (thinking mode under --jinja), on Windows and on
EVO-X2. Phase 0.5 (portability) is in progress: the Windows x64 target is proven
and Linux x64 is largely exercised on EVO-X2, but the Linux ARM64 check is deferred
pending hardware, so 0.5 cannot lock yet.

Active execution focus is Phase 8 (Hermes). The taskboard<->kanban bridge (H2) is
validated end to end in WSL on a capable model (delegate -> run -> mirror reaches
status=ok + summary). The one remaining step is the H2 Exit Gate check on EVO-X2
with the real 35B + GPU + egress-off (Item H2d) -- the next true lock. See
`todo.md`.

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

Exit Gate (MET):

- [x] bootstrap installs the full stack with no source builds
- [x] core import smoke test passes
- [x] the API process boots
- [x] the offline API suite (`tests/test_api_offline.py`) is green

## Phase 0.5 -- Cross-OS / cross-arch portability hardening  [~] IN PROGRESS

Goal: any node runs the same way on Windows and Linux, x86-64 and ARM64, on
CPU/CUDA/ROCm/Vulkan. Apple (macOS / Apple Silicon / Metal) is not a
consideration -- no effort spent, not tested; incidental compatibility is fine,
but it is never weighed. Underpins everything, especially the Phase 9 mesh. Full
audit + support matrix: `docs/portability_audit.md`.

- [x] /agent/run uses sys.executable (was literal python3; broke Windows portable)
- [~] Single cross-platform launcher `manage.py` (up/down/toggle/status/doctor/
      capabilities/test/panel) replacing the bash/ps1 split (no bash for core
      lifecycle). LIVE-VALIDATED on Windows (RX 9060 XT) 2026-06-07: toggle brought
      the full stack up on :8090/:8000 and tore it down cleanly; test playbook green
      incl. live /agent/run; web panel drove it. Pure stdlib. Bash lifecycle scripts
      archived to scripts/archive/ -- core lifecycle is now manage.py-only. Windows
      x64 VALIDATED 2026-06-07 (Daemonic-PC, RX 9060 XT): status/capabilities/doctor
      all green under portable 3.11.9 -- config.toml read, run/node_capabilities.json
      written, accel detect+select=vulkan; full live CLI lifecycle proven (up ->
      status -> doctor --deep -> test quick -> down -> clean). 2026-06-14: down/status
      hardened against the WSL stale-pidfile trap (resolve_live_pid + /health
      corroboration; tests/test_manage_pid.py; live-confirmed in WSL). The Linux x64 +
      ARM64 live passes remain owed (see the Exit Gate).
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
      with a 3-tier accel classification (Tier 1 selectable CUDA/ROCm/SYCL/Vulkan/
      OpenCL/CANN/MUSA; Tier 2 in-progress; Tier 3 detect-but-never-select Hailo/
      Coral/Gaudi/Intel-NPU) + "select only what the binary supports". IMPLEMENTED
      2026-06-06 (changelog 2014): `manage.py capabilities` + detection layer +
      accel-aware `start_llama` (H3) + doctor accel section; Windows x64 VALIDATED
      2026-06-07 (capabilities + doctor green; node_capabilities.json written). The
      earlier capabilities `llama_build=null` flake was FIXED + verified-live 2026-06-07
      (`--version` probe bumped to 30s + one retry in llama_version_info; capabilities
      now reports b9219 -- see changelog/todo). Mesh wiring stays Phase 9.
- [~] H3 accel selection: `start_llama` backend-aware (no forced Vulkan on
      CUDA/ROCm/SYCL nodes); LLAMA_BACKEND override + capabilities detection.
      Done 2026-06-06; selection verified on the AMD/Vulkan host (selected=vulkan)
      2026-06-07. The "no forced Vulkan on CUDA/ROCm/SYCL" proof needs a non-Vulkan
      node and rides with the deferred Linux/ARM64 pass.
- [x] Cross-platform IPC decision (DONE 2026-06-06): NATS+JetStream is the primary
      control-plane bus (nats-server supervised as a Phase 3 daemon child, loopback,
      JetStream R=1) -- groundwork for the Phase 9 mesh -- with a stdlib loopback-TCP
      compatibility fallback, both behind one EventBus interface. Unix sockets ruled
      out (no asyncio AF_UNIX on the Windows ProactorEventLoop). See
      docs/ipc_decision.md.
- [~] First-run model auto-provisioning: on first launch, profile the host and
      consult a committed playbook (`run/model_playbook.toml`) that maps the
      resource envelope (RAM / VRAM / CPU / accel / arch) to a ranked, multi-family
      model catalog, then auto-download the best fit (huggingface_hub) and wire it
      into config.toml. Wide range: Raspberry-Pi-class / 8 GB CPU floor up to 96 GB
      unified / discrete-VRAM (Tier 4 primary = the committed Qwen3.6-35B-A3B).
      Vision capability is a PREFERRED (soft) requirement. DESIGN 2026-06-07:
      `docs/model_provisioner_design_20260607_2158.md`. Phased P1-P4. P1 (profiler:
      vram_mb/memory_model/NPU classify) + P2 (playbook + matcher,
      scripts/provision_match.py, 7/7) CODE DONE 2026-06-07. P3 (downloader + license
      gate + disk preflight + config wiring) CODE DONE 2026-06-14:
      scripts/provision_fetch.py + `manage.py provision [--dry-run/--yes/--model/
      --text-only/--write-config/--hf-token]` + tests/test_provision_fetch.py (30/30
      offline). Config wiring is OPT-IN (default prints the block; --write-config/--yes
      to apply) and targets the active per-host config.<host>.toml when one exists.
      LIVE-CONFIRMED 2026-06-14 on Daemonic-PC (RX 9060 XT): `provision --dry-run` ->
      qwen3.6-35b Q5_K_XL pick, weights [present] (0 MiB), per-host target
      config.daemonic-pc.toml [windows], vision off (no camera), nothing written.
      ctx SAFEGUARD landed 2026-06-14: provision preserves an existing effective
      PERSONA_CTX (host-validated) over the matcher's conservative guess (the
      tight-budget step-down had proposed 8192 on a host that runs 16384), printing a
      note; fresh hosts still take the safe conservative value. OWED: P4 (first-run hook
      in cmd_up + --yes installer path); serving-side mmproj/VISION_ENABLED wiring;
      `--tier` flag (needs a tier field in the playbook); the deeper KV-aware ctx
      sizing (replace the 0.85*budget step-down with a real KV-headroom estimate).
- [ ] Per-OS egress story: WireGuard mesh + host firewall baseline; netns/iptables
      as a Linux-only bonus
- [ ] Cross-OS installer/doctor parity (Windows + Debian + other Linux)

Exit Gate (one node bootstraps, runs, self-checks via doctor, and serves /chat
through one entrypoint with no bash for core lifecycle):

- [x] Windows x64 -- CPU + Vulkan (Daemonic-PC, 2026-06-07)
- [~] Linux x64 -- CPU + Vulkan (EVO-X2 serves /chat; doctor/lifecycle parity
      confirm via manage.py still owed)
- [ ] Linux ARM64 -- DEFERRED, no hardware on hand (trigger: hardware available)
- [ ] non-Vulkan accel selection proof (a CUDA/ROCm/SYCL node)

The Phase cannot lock GREEN until the deferred checks above are met.

## Phase 1 -- Core serving and companion API  [x] GREEN

Goal: a single local model behind the FastAPI companion API returns real
persona replies over both the native and OpenAI-compatible paths.

GREEN 2026-06-08: every Item below is `[x]` (M6 was the last to close) and the
Exit Gate was PROVEN 2026-06-07 (changelog 1222).

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
      chat_template_kwargs/messages migration is folded into T2.4.
- [x] T2.3 preserve_thinking for Hermes-originated requests -- DONE 2026-06-07
      (Path A): preserve_thinking flag (req field + PRESERVE_THINKING_DEFAULT, off
      by default); split_reasoning() pulls in-band <think> out before sanitizing;
      preserve=true returns the answer un-sanitized + reasoning (`reasoning` on
      /chat, `reasoning_content` on /v1 incl. stream). VALIDATED Windows-side:
      offline suite 35/35. DESIGN NOTE: preserve mode also skips the lossy persona
      two-part sanitizer (agent loops want the full answer) -- revisit if persona
      formatting is ever wanted alongside preserved reasoning.
- [x] T2.4 --jinja messages migration -- CODE DONE 2026-06-07 (OFF by default,
      PERSONA_USE_MESSAGES). New query_llama_messages (POST /v1/chat/completions with
      chat_template_kwargs{enable_thinking}; parses content + reasoning_content +
      usage), build_persona_messages (system/user split, no /think prefix), and a
      persona_generate() helper that both /chat and /v1 call -- messages path when on,
      the proven raw /completion path (byte-identical) when off. LIVE VALIDATED
      2026-06-07 1746 (exit_gate_live [messages], PERSONA_USE_MESSAGES=1): reasoning
      came from the server reasoning_content and text was <think>-free. FOLLOW-UP DONE
      2026-06-08 0846: post-hoc sanitizer RETIRED on the messages path
      (PERSONA_SANITIZE_MESSAGES OFF-by-default escape hatch). Off-mount 72/72; raw
      /completion path unchanged.
- [x] M6 single-model migration confirmed (M2b passed, M5 done) -- DONE 2026-06-08:
      EVO-X2 converged to Qwen3.6-35B-A3B-UD-Q5_K_XL on a fresh llama.cpp b9219 Vulkan
      build (old b8157 could not load qwen3_5_moe). Live-validated (/health green,
      thinking + reasoning_content via messages path, RAG live); Instruct-2507
      archived. Single model now on EVERY host (Windows + EVO-X2) per the 2026-06-07
      directive. config.toml [linux] committed + pushed from EVO-X2. See changelog
      1029. Build dep: spirv-headers (docs/llama_build_matrix.md). Tunable:
      PERSONA_MAX_TOKENS >= 4096 when thinking is on (raw default path unaffected).
- [x] Per-profile Chroma collections connected to the API -- CODE DONE 2026-06-07
      (OFF by default): RAG_PER_PROFILE routes memory_add/query to a per-profile
      collection ("mem_<profile>") via _get_collection; off = the single shared
      RAG_GLOBAL_COLLECTION exactly as before. LIVE VALIDATED 2026-06-07 1752
      (exit_gate_live [per-profile]): mem_alice/mem_bob collections created. CAVEAT:
      turning it on does not migrate existing global_memory rows. RESIDUE: the run
      also created untracked persona/profiles/alice/ + bob/ on disk -- gitignore or
      clean up.
- [x] Topic routing policy -- DONE 2026-06-07 (OFF by default): deterministic keyword
      classify_topic(text) + resolve_topic precedence (topic="auto" always classifies;
      explicit non-chat respected; "chat"/absent classifies only when TOPIC_ROUTING=1).
      Resolved topic drives thinking/sampling/RAG/inband downstream. VALIDATED: offline
      suite 56/56.
- [x] Task Board (`data/tasks.db`) replaces the in-memory jobs dict -- CODE DONE
      2026-06-07: stdlib-sqlite3 services/api/taskboard.py (init/task_set upsert-
      merge/task_get/task_list/delete/count + one-time jobs.jsonl migration); server
      wired (TASKS_DB config, init at startup, /agent/run records run->ok/error/
      timeout, /jobs list + /jobs/{id} from the board, /health task_store). LIVE
      VALIDATED 2026-06-07 1758: a real /agent/run recorded ok into the board; /jobs +
      /jobs/{id} returned the row with timestamps + returncode 0; /health
      task_store count=1.

Exit Gate (PROVEN 2026-06-07, changelog 1222, via tests/exit_gate_live.py):

- [x] llama-server live on :8090
- [x] `/chat` and `/v1/chat/completions` return real persona replies
- [x] a "chat" topic resolves no_think; science/coding/math/research resolve think
      (verify via `/chat` debug `sampling_preset`)
- [x] live `stream=true` produces SSE chunks + [DONE] and non-zero `prompt_tokens`
- [x] `/health` green with embedder_ok=true and chroma_ok=true

## Phase 2 -- Frontend and UX  [ ] NOT STARTED

Goal: a thin client over the API with durable conversation history.

- [ ] OpenWebUI as thin client (currently dormant, port 3000)
- [ ] SQLite `conversations.db` as source of truth for history
- [ ] Persona task surfacing in the UI
- [ ] Hybrid conversation windowing
- [ ] Item 2a: migrate vector store ChromaDB -> Qdrant (Qdrant + fastembed are
      also the 3.14-unblock path)

Exit Gate:

- [ ] a user holds a multi-turn conversation through the UI
- [ ] turns persist in `conversations.db` and reload correctly
- [ ] windowing keeps context within budget
- [ ] retrieval works against Qdrant with parity to the Chroma path

## Phase 3 -- Always-on daemon (daemon.py)  [ ] NOT STARTED

Goal: one supervised entry point for all services.

- [ ] Single asyncio daemon with a child-process map (llama-server, API,
      nats-server, others)
- [ ] Three-strike restart policy
- [ ] NATS-based IPC (local nats-server child, loopback; stdlib loopback-TCP compat
      fallback; EventBus interface -- see docs/ipc_decision.md); events beyond `ping`
      (profile_switched, ingest_complete, tts_speaking, task_ready)
- [ ] Fresh-logs-on-start contract; absorbs the start/stop scripts

Exit Gate:

- [ ] daemon brings up and supervises all children
- [ ] killing a child triggers restart within policy; a fourth failure stays down
- [ ] IPC events deliver one-way (components -> daemon) without the API ever
      blocking on it

## Phase 4 -- Embodied presence (Godot)  [-] OPTIONAL

Goal: optional 3D/VR client driven by a two-channel protocol.

- [-] Persona emits RESPONSE (text/TTS) + STATE (JSON avatar directives)
- [-] Godot client consumes the protocol

Exit Gate:

- [-] the avatar reflects STATE directives in sync with RESPONSE output for a
      scripted exchange

## Phase 5 -- Voice pipeline  [-] OPTIONAL

Goal: local speech in/out as daemon children (host-side compute only).

- [-] Whisper.cpp STT
- [-] Piper TTS (GPL-3.0)

Exit Gate:

- [-] spoken input is transcribed, answered, and spoken back end-to-end, fully
      offline

## Phase 6 -- Auto-contextual RAG ("sorting line")  [ ] NOT STARTED

Goal: dropped files become retrievable, classified memory automatically.

- [ ] `inbox/` file watcher
- [ ] Multi-format reader
- [ ] Semantic classifier + multi-bin routing
- [ ] Provisional/mature collection lifecycle with alias chains

Exit Gate:

- [ ] a file dropped in `inbox/` is read, classified, and routed to the correct
      collection
- [ ] it is retrievable via RAG
- [ ] a provisional entry promotes to mature on the defined trigger

## Phase 7 -- Background consolidation ("sleep cycle")  [ ] NOT STARTED

Goal: idle-time memory maintenance.

- [ ] Idle-triggered conversation distillation
- [ ] Relationship discovery + ontology maintenance
- [ ] Insight journaling

Exit Gate:

- [ ] an idle period triggers a consolidation pass that distills recent
      conversations
- [ ] it links related memories and writes an insight journal entry
- [ ] foreground responsiveness is not disrupted

## Phase 8 -- Agentic layer (Hermes Agent)  [~] FOUNDATION STARTED

Goal: Hermes runs as a daemon child pulling background work from the Task Board.
(Near-term in execution despite the late Phase number; depended on the Phase 1
single-model migration M6.)

- [x] T1: per-profile `config.yaml` safe-config (egress tools disabled, local
      model pinned, no cloud fallback) generated by `init_profiles.sh`; `doctor.sh`
      validates the default profile as the T1 check (implemented 2026-06-04)
- [x] T1 close-out on a live host -- DONE 2026-06-12: hermes-agent v0.16.0 installed
      on EVO-X2 in `env_hermes/` (isolated/portable: uv + CPython 3.11.15 + editable
      clone ~/src/hermes-agent pinned 9b1e0d6f; no global mutations). env_hermes/bin/
      python exists -> detection satisfied. NOTE: NousResearch/hermes-agent installs
      via install.sh/uv, NOT `pip install hermes-agent`. Native Windows unsupported
      (WSL2 only) -> Hermes runs on EVO-X2.
- [x] H1: validate Hermes `config.yaml` key paths -- DONE 2026-06-12 (changelog 2311):
      against v0.16.0, HERMES_HOME resolves to the profile dir, model.sampling.default/
      thinking + tools.disabled all valid; config migrated in place 0->28 (safe-config
      preserved). Egress off via tools.disabled + API-key-gating + terminal.backend=
      local + browser.allow_private_urls=false + disabled_toolsets. Committed 70d7fb2.
- [~] H2: bridge taskboard.py <-> Hermes' native kanban. ARCH DECISION 2026-06-13
      (Brandon) = BRIDGE (taskboard.py / persona /jobs stay canonical; Hermes kanban =
      execution substrate; one loopback bridge on EVO-X2). Sub-items:
  - [x] H2a DESIGN (docs/h2_bridge_design_20260613_0204.md): public-CLI transport
        (kanban create/watch/runs --json, not raw DB), additive delegated/blocked
        statuses, job_id<->hermes_task_id correlation, Hermes owns retry.
  - [x] H2b: POST /agent/delegate writes a "delegated" row (no taskman2), /health
        delegate block, +~10 offline checks.
  - [x] H2c: tools/hermes_bridge.py (enqueue + mirror via Hermes public CLI, injected
        runner/board) + tests/test_hermes_bridge.py faked-CLI suite 44/44 ALL PASS;
        shapes confirmed via a source-dive into hermes-agent v0.16.0 @ 9b1e0d6f.
  - [x] H2 WSL validation: full chain delegate->card->claim->spawn->worker-runs->mirror
        confirmed LIVE in WSL (changelog 1458), then driven to status=ok + summary on a
        capable model (Qwen2.5-7B CPU; changelog 2112). The 1.5B floored on 0 tool
        calls = model-capability limit, not a bridge bug. Integration findings folded
        into knowledge.md + docs/wsl_h2_runbook_20260613_0311.md (default-assignee
        HERMES_HOME=ROOT; 64K ctx gate on main+aux; PERSONA_CTX/PARALLEL slot sizing;
        pin HERMES_KANBAN_HOME).
  - [ ] H2d: run on EVO-X2 with the real 35B + GPU + egress-off (no sim overrides) ->
        expect status=ok + summary. THIS IS THE Phase 8 Exit Gate evidence; deferred
        until the rest of the near-term work is finished (Brandon, 2026-06-14).
- [ ] H3-H6: Hermes claims + executes end to end, then role-prefix template library,
      cache_prompt amortization, Tenacity-style failure semantics.
- [ ] Runtime egress containment: kernel netns/iptables + daemon env hygiene
      (config-time half exists; runtime half H1.6 still required)

Exit Gate:

- [ ] Hermes runs as a daemon child
- [ ] it claims a Task Board task and executes it
- [ ] it writes results back for the persona to surface (H2d on EVO-X2 35B)
- [ ] egress is contained at both config and kernel level
- [ ] `doctor.sh` is fully green

## Phase 9 -- Decentralized cooperative node mesh  [ ] DESIGN (extended)

(Was Phase 10. The old Phase 9 was a deleted CrewAI placeholder, superseded by
Hermes in Phase 8; the slot now holds the mesh per the 2026-06-14 swap.)

Goal: system-agnostic nodes that run standalone and, when networked, pool
throughput and specialized capability BOINC-style. Depends on Phase 1 Task Board,
Phase 2 Qdrant (Item 2a), Phase 3 daemon. Full design + rationale:
`docs/distributed_nodes.md`. EVO-X2 is the mesh's anchor node, so its migration
(Item 9.0) is the precondition; the rollout Items 9.1-9.5 were formerly
"Stage 0-4" in `docs/distributed_nodes.md` (renamed here so "stage" no longer
collides with the orchestrator's `-Stage` flags).

Decisions locked: distribute tasks not single inferences; NATS+JetStream with a
per-node server clustered as equals (3/5-node JetStream core for durable state,
ephemeral nodes as clients/leaf); shared-token admission with token-rotation as
the hard evict; self-generated per-node keys + NATS connection log ($SYS/connz)
+ TTL'd KV roster for identity/membership; validation/quorum + advisory key
deny-list for bad actors; WireGuard mesh for transport + egress containment.

- [~] 9.0: EVO-X2 migration -- consolidate the full stack onto EVO-X2 as the
      primary/anchor node (the endgame: everything on EVO-X2). In progress: EVO-X2
      already serves the Qwen3.6-35B (Vulkan, b9219) and has hermes-agent v0.16.0
      installed (env_hermes). Remaining: run persona + API + Hermes natively on EVO-X2
      as the canonical node (not via the WSL proxy), make it the source-of-truth
      dev/run surface, and prove the H2d Exit Gate there. Today the WSL clone is the
      primary dev surface as the closest EVO-X2 proxy and the D:\ repo is the redundant
      copy + Windows testbed + git gateway (see `WORKFLOW.md`).
- [ ] 9.1: `LLAMA_HOST` cross-node inference offload (no new infra)
- [ ] 9.2: 2-node NATS + JetStream work queue; claim -> execute -> result;
      clean reclaim on worker failure
- [ ] 9.3: connection log + self-gen node keys + KV roster; dynamic join +
      capability-aware routing. Includes the stable salted-system-spec node_id
      (manage.py first boot; bound to the keypair) -- see distributed_nodes.md sec 5.
- [ ] 9.4: 3-server JetStream core (R=3); reputation + deny-by-node-id +
      coordinated token-rotation evict (quorum-authorized, excluding the actor) +
      OOB re-key recovery for missed nodes; redundant-execution validation/quorum.
      Protocol in distributed_nodes.md sec 5b (opens: re-key quorum, cutover window,
      split-brain reconcile).
- [-] 9.5: WireGuard substrate; Object-store artifact transfer; superclusters
      at scale

Exit Gate:

- [~] the full stack (persona + API + Hermes) runs natively on EVO-X2 as the
      anchor node (Item 9.0)
- [ ] a node joins with only the shared token
- [ ] it appears in the roster by hostname+key with advertised capabilities
- [ ] it claims and runs capability-matched work and returns validated results
- [ ] a node loss reclaims cleanly; the durable core survives losing one member

## Phase 10 -- Full-system / feature test  [ ] NOT STARTED

Goal: prove the whole system works together, end to end, and keeps working -- a
capstone validation layer over every completed Phase, and a regression net as
features land. Runs on the canonical node (EVO-X2 once Phase 9 Item 9.0 lands);
the offline portions run on any host. Functionally last, but partial subsets can
run against whatever Phases are already green.

- [~] 10.0: One-command regression suite -- every offline suite
      (test_api_offline, test_hermes_bridge, test_manage_pid, test_provision_match,
      + future) runs green from a single entrypoint on Windows x64 AND Linux x64.
      RUNNER BUILT 2026-06-14: tests/run_all_offline.py auto-discovers tests/test_*.py,
      runs each in its own process with the current interpreter, aggregates pass/fail.
      WINDOWS x64 GREEN 2026-06-14 1530 (portable 3.11.9): 4/4 suites PASS. Flips to
      [x] once also green on Linux x64 (EVO-X2 or a WSL clone with the API deps).
- [ ] 10.1: Live system playbook -- a scripted end-to-end exercise on the canonical
      node: multi-turn conversation, topic routing + thinking mode, RAG recall +
      writeback, and an agent delegation round-trip (delegate -> Hermes runs ->
      /jobs ok + summary). Repeatable, pass/fail.
- [ ] 10.2: Cross-host parity -- the same playbook yields consistent behavior on
      Windows, EVO-X2, and a mesh node; any difference is config, not code.
- [ ] 10.3: Resilience / failure injection -- daemon three-strike restart (Phase 3),
      mesh node-loss reclaim (Phase 9), and stale-pidfile recovery (manage.py) each
      recover within policy under deliberate faults.
- [ ] 10.4: Egress containment as a system check -- a delegated worker provably has
      NO outbound network (config + kernel level), verified at the system boundary,
      not just per component.
- [ ] 10.5: Performance baseline -- sustained-load throughput + latency captured on
      the canonical node and tracked against a target; regressions flagged.

Exit Gate:

- [ ] the one-command regression suite is green on Windows x64 + Linux x64
- [ ] the live system playbook passes end to end on the canonical node
- [ ] cross-host parity holds (behavior consistent across hosts)
- [ ] every failure-injection scenario recovers within policy
- [ ] worker egress containment is verified at the system boundary
- [ ] a performance baseline is captured and within target

---

## Extended / deferred (no active trigger)

- [-] Vision input
- [-] MTP / speculative decoding
- [-] Dual-memory unification (conversations.db + Chroma)
- [-] Next-gen Qwen (post-3.6) maturity re-evaluation after ~2026-08 (TODO #36).
      NOTE: Qwen3.6-35B-A3B is already the committed model; this is a forward-looking
      re-check of newer releases, not a pending adoption of 3.6.

## Cross-cutting components

These evolve across Phases rather than completing once (detail in `knowledge.md`
-> System components): Task Board (`data/tasks.db`), SQLite stores
(`conversations.db`), ChromaDB/RAG layer, NATS-based IPC (NATS+JetStream primary,
stdlib loopback-TCP fallback; Unix sockets were ruled out -- see Phase 0.5 IPC
decision). Their readiness is tracked inside the Phase whose Exit Gate first
depends on them (Task Board -> Phase 1/8; conversations.db -> Phase 2; IPC ->
Phase 3).
