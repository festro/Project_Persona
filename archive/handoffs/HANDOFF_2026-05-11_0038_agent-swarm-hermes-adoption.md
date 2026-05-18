# HANDOFF — Agent Swarm: Hermes Adoption Decision

**Date:** 2026-05-11 0038 UTC
**Session type:** Brainstorm → architectural decision (no code changes)
**Status:** Decision frozen. Implementation deferred until single-model migration (archive/handoffs/HANDOFF_2026-05-09_0950) completes.
**Predecessor:** `archive/handoffs/HANDOFF_2026-05-09_0950_single-model-migration.md`
**Knowledge.md sync:** `knowledge.md` updated same session — DECISION 2026-05-11 entry, Phase 2.5/8/9 marked superseded, Task Board schema extended, daemon child process list updated.

---

## Context

The single-model consolidation (DECISION 2026-05-09, Qwen3-30B-A3B with parallel slots and mode-switched prompts) is the necessary prerequisite for any "one model, many ephemeral workers" topology. With that migration sequenced and the brainstorm framing settled, the question this session addressed was:

> "What kind of agent swarm do we build on top of the consolidated model layer?"

A new variable surfaced this session: **Hermes Agent** (Nous Research, MIT, v0.13.0 May 2026) — an open-source persistent agent that overlaps roughly Phases 3, 6, 7, 8, and 9 of the existing roadmap simultaneously. Its existence forced a build-vs-adopt evaluation that was not on the table when Phases 8 (LangGraph) and 9 (CrewAI candidate) were originally specified.

---

## Decision Summary

**Adopt Hermes Agent as the agent-work backbone.** server.py remains the live conversation layer. Hermes runs as a daemon child process, picks work off the Task Board, executes with its own orchestration, writes results back. Persona surfaces results through the existing surfacing behavior.

**Roadmap effects:**
- Phase 2.5 (AG2 scientist↔critic loop): **DELETED** — superseded by Hermes
- Phase 8 (LangGraph agentic layer): **RESHAPED** — collapses into "Hermes integration + Task Board contract"
- Phase 9 (CrewAI candidate): **DELETED** — superseded by Hermes
- Phase 3 (Daemon): adds `hermes-agent` to child process list, gains a "Task Board → Hermes" dispatcher
- Task Board: gains heartbeat / reclaim / zombie / validation columns (Tenacity-style failure semantics)

---

## The Six Forks (Brainstorm Frame)

Before deciding, six independent design forks were laid out. Final position on each:

### Fork 1 — Build vs Adopt vs Hybrid

**Decision: Full adopt Hermes.**

Hermes uses neither AG2 nor CrewAI internally. Its `AIAgent` (run_agent.py) is its own synchronous orchestration engine with its own tool registry, session persistence (SQLite + FTS5), context compression, prompt assembly, and subagent delegation (`tools/delegate_tool.py`). Its Tenacity Kanban (heartbeat, reclaim, zombie detection, hallucination recovery) covers what CrewAI was wanted for.

The hybrid case (keep AG2 for in-process scientist↔critic, adopt Hermes for the larger swarm) was evaluated and rejected:
- IPC overhead is irrelevant at LLM-call timescales (microseconds vs hundreds of milliseconds)
- Hermes' agent loop can do tight critique loops natively — "Hermes is heavier" was a wrong mental model
- Two orchestrators = two failure surfaces, two prompt conventions, two debugging paths, two upgrade timelines
- The only remaining case for AG2 was "agent work returns synchronously inside the same /chat HTTP request," which is an antipattern given Task Board surfacing semantics

### Fork 2 — Swarm Pattern

**Decision: Fan-out / gather.**

Orchestrator decomposes a hard query into N sub-questions, dispatches in parallel against the unified model, gathers and synthesizes. Stateless workers, short-lived. Maps directly onto parallel slots on the consolidated llama-server (M3-M5 of the single-model migration).

Persistent specialized roles and pull-based pipeline workers were considered as alternative day-one MVPs. Both are useful patterns long-term but fan-out/gather is the right shape for the first implementation given the parallel-slot topology already being built.

### Fork 3 — Orchestrator Location

**Decision: Inside the Phase 3 daemon.**

Persistent asyncio loop, child process map already designed for it, Unix socket already present for IPC. Strongest architectural fit. Means daemon work has to land in parallel with or before agent swarm work.

Inside server.py (synchronous to request, dies with request) is wrong shape — workers can run for minutes. Separate process behind /agent/run is cleaner separation but adds moving parts the daemon already provides.

### Fork 4 — Worker Addressing

**Decision: Pure stateless slots, with deterministic role-prefix templates.**

Each request to the unified llama-server gets whichever slot is free. Slots have no identity between requests. Workers are pure functions of (prompt, params) → output.

**Critical implementation discipline:** every dispatch must use a stable role-prefix template + task-specific suffix, with `cache_prompt: true`. Without this, every fan-out re-prefills the ~9K-token system prefix and KV cache discipline collapses. With it, llama-server keeps N hot prefix caches that all parallel slots share.

This means the orchestrator maintains a fixed library of role-prefix templates (researcher / critic / summarizer / etc.) and constructs prompts as `[stable_role_prefix] + [task_specific_suffix]`. Sub-task variation lives in the user message, never the system prompt.

### Fork 5 — Failure Semantics

**Decision: Add Tenacity-style failure semantics to Task Board now, not later.**

The five failure modes in fan-out/gather:
1. Worker returns garbage (hallucination, schema validation failure)
2. Worker times out (request hung, slot occupied without progress)
3. Orchestrator dies mid-fan-out (RUNNING tasks become zombies)
4. Worker process exists but is wedged (no tokens generated within window)
5. Partial gather (4 of 5 results back, 1 still pending)

Hermes' Tenacity Kanban addresses all five via heartbeat, reclaim, zombie detection, auto-block on incomplete exit, per-task retries with backoff, and hallucination recovery. The current Task Board schema (`status`, `error`, `time_score`) does not.

Adding now: cheap (schema additions). Hitting in production and bolting on later: expensive (schema migration + orchestrator rewrite + lost task data).

**Schema additions required (see knowledge.md update):** `heartbeat_at`, `heartbeat_interval_s`, `claimed_by`, `reclaim_after`, `attempt`, `max_attempts`, `validation_status`, `validation_feedback`.

### Fork 6 — Worker Memory & Identity

**Decision: Stateless swarm under orchestrator. No per-worker persistent memory or persona.**

Workers don't have their own Qdrant collection scope, conversation log, or persona file. They are pure compute. All memory and identity lives in the orchestrator (Hermes' main agent) and the persona layer in server.py.

This deliberately gives up the "agent that grows with you" property at the worker level. That property is owned by Hermes' main loop (its SQLite/FTS5 session memory + your existing Chroma/Qdrant RAG). Subagents are ephemeral fan-out workers, not specialists with continuity.

---

## Architectural Shape (Post-Migration Target)

```
┌──────────────────────────────────────────────────────────────────────┐
│  /chat (live request cycle — server.py)                              │
│  ────────────────────────────────────────────────                    │
│   Persona response   (single llama call, in-band)                    │
│   RAG retrieval      (Chroma/Qdrant, in-band)                        │
│   Routing decision   (trivial → in-band; non-trivial → Task Board)   │
│   Surface results    (poll Task Board for READY items)               │
└─────────────────────────┬────────────────────────────────────────────┘
                          │ submit task
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Task Board  (data/tasks.db — SQLite + Tenacity-style columns)       │
│  ─────────────────────────────────────────────────────────────       │
│   status / heartbeat_at / claimed_by / reclaim_after / attempt /     │
│   validation_status / surface_priority / pending_surface / ...       │
└─────────────────────────┬────────────────────────────────────────────┘
                          │ pulled by daemon dispatcher
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Hermes Agent  (daemon child process)                                │
│  ──────────────────────────────────────                              │
│   AIAgent loop    (run_agent.py — synchronous orchestration)         │
│   Subagent fan-out via delegate_tool                                 │
│   Tool registry   (~70 tools, ~28 toolsets)                          │
│   Provider:       custom endpoint → unified llama-server :8080       │
└─────────────────────────┬────────────────────────────────────────────┘
                          │ parallel slots, cache_prompt: true
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Unified llama-server  (Qwen3-30B-A3B-Q5_K_M, port 8080)             │
│  ──────────────────────────────────────────────────────              │
│   --parallel N --cont-batching                                       │
│   Stateless slots, KV cache shared across role-prefix templates      │
└──────────────────────────────────────────────────────────────────────┘
```

Daemon child process map gains `hermes-agent`. Removes `llama-scientist` and never adds `llama-coder` (both already accounted for in single-model migration).

---

## Sequenced Migration Plan

**This work begins ONLY after the single-model migration (M1-M12 from archive/handoffs/HANDOFF_2026-05-09_0950) is complete and verified.** Do not interleave.

### H1 — Pre-flight (no code)
- [ ] **H1.1** Read Hermes architecture docs end-to-end (already started this session — see Sources)
- [ ] **H1.2** Verify Hermes accepts custom OpenAI-compatible endpoints — confirm `provider: custom` configuration accepts `http://127.0.0.1:8080` (the post-migration unified llama-server). **CONFIRMED 2026-05-11 from docs:** `provider: custom` is first-class for any OpenAI-compatible endpoint.
- [ ] **H1.3** Verify Hermes can run headless as a daemon child without requiring messaging-platform credentials (Telegram/Discord/etc. should be optional)
- [ ] **H1.4** Confirm Hermes' SQLite session storage path is configurable — must live under `data/` to remain portable with project folder
- [ ] **H1.5** **Network egress containment — integration test, not config check.** With the safe-config recipe (Appendix A) applied and `ANTHROPIC_TOKEN` / `CLAUDE_CODE_OAUTH_TOKEN` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` / `AI_GATEWAY_API_KEY` absent from daemon environment, run Hermes under packet capture (`tcpdump -i any 'not host 127.0.0.1' -w hermes_egress.pcap`) and force three scenarios:
  - (a) Normal long conversation that triggers automatic compression at 50% of context window
  - (b) Forced llama-server failure (`kill -9` the unified server mid-request, observe Hermes' retry behavior)
  - (c) Forced llama-server 500 response (configure llama-server to reject one request explicitly)

  **Acceptance:** zero outbound packets to non-localhost destinations across all three scenarios. Any egress is a hard fail and DECISION 2026-05-11 must be reopened.
- [ ] **H1.6** **Egress containment via network namespace or iptables.** Belt-and-suspenders. Run `hermes-agent` in a network namespace that allows only `127.0.0.1`, OR install iptables egress rules on the daemon's UID/process tree allowing only loopback. Even if config drift introduces a leak path, the kernel blocks it. Acceptance: same packet capture as H1.5 but with config intentionally broken (e.g., `auxiliary.compression.provider: openai` set deliberately) — egress must still be zero because the kernel blocks it.

### H2 — Task Board schema extension
- [ ] **H2.1** Extend `data/tasks.db` schema with Tenacity-style columns:
  - `heartbeat_at` TIMESTAMP — last worker heartbeat
  - `heartbeat_interval_s` INTEGER — expected heartbeat cadence
  - `claimed_by` TEXT — worker ID currently holding the task
  - `reclaim_after` TIMESTAMP — when to return task to QUEUED if no heartbeat
  - `attempt` INTEGER — current retry attempt
  - `max_attempts` INTEGER — retry cap
  - `validation_status` TEXT — PASSED | FAILED | PENDING
  - `validation_feedback` TEXT — feedback for retry on validation failure
- [ ] **H2.2** Add reclaim sweeper (asyncio task in daemon) — periodically scans for tasks past `reclaim_after`, returns to QUEUED with incremented `attempt`
- [ ] **H2.3** Add validation hook contract — workers must emit a structured result that the dispatcher validates before marking READY
- [ ] **H2.4** Update Task Board status enum if needed: QUEUED | CLAIMED | RUNNING | VALIDATING | READY | SURFACED | FAILED

### H3 — Daemon dispatcher
- [ ] **H3.1** Add `hermes-agent` to daemon child process list (`daemon.py` — Phase 3 work)
- [ ] **H3.2** Implement Task Board → Hermes dispatcher (asyncio task in daemon)
  - Pulls QUEUED tasks
  - Marks CLAIMED with `claimed_by=hermes`, sets `reclaim_after`
  - Submits to Hermes (mechanism TBD in H1.2 — direct API call, RPC, or file-based job spec)
  - Receives result, runs validation, marks READY or RETRY
- [ ] **H3.3** Heartbeat protocol — Hermes worker pings dispatcher (or updates `heartbeat_at` directly) on configurable interval
- [ ] **H3.4** Three-strike rule reuse — Hermes child uses same daemon restart policy as other children

### H4 — Role-prefix template library
- [ ] **H4.1** Define initial role-prefix templates: `researcher`, `critic`, `summarizer`, `coder`, `librarian`
  - Each is a stable system-prompt prefix designed for KV cache locality
  - Each pinned in version control under `persona/swarm_roles/`
  - Each tagged with the Qwen3 thinking-mode toggle expected for that role
- [ ] **H4.2** Hermes configuration — point its provider at unified llama-server with `cache_prompt: true` baked into request payload
- [ ] **H4.3** Wire orchestrator prompt assembly to use `[role_prefix] + [task_suffix]` shape consistently

### H5 — server.py routing
- [ ] **H5.1** Add routing decision in `/chat`: trivial query → in-band persona response; non-trivial → submit to Task Board with appropriate role tag
- [ ] **H5.2** Trivial / non-trivial classifier — initially a simple keyword + length heuristic, refinable later
- [ ] **H5.3** Persona surfacing already designed (knowledge.md Component: Task Board) — verify it picks up Hermes-produced READY tasks transparently

### H6 — Validation and acceptance
- [ ] **H6.1** End-to-end smoke: submit a research-grade query → confirm Hermes fans out → workers return → orchestrator synthesizes → persona surfaces
- [ ] **H6.2** Failure injection: kill Hermes mid-fan-out → confirm reclaim sweeper returns tasks to QUEUED
- [ ] **H6.3** Failure injection: force a worker to return malformed output → confirm validation triggers retry with feedback
- [ ] **H6.4** Performance: measure cache hit rate on role-prefix templates over a 50-task batch; confirm prefill cost amortizes

---

## Network Egress Risk Surface

Investigation 2026-05-11 (post-brainstorm, into Hermes provider-runtime / agent-loop / context-compression docs) identified seven distinct network egress paths in Hermes. Defaults are **not** safe for a local-only AGPLv3 self-hosted stack. All seven must be addressed in the safe-config recipe (Appendix A) and verified by H1.5/H1.6.

### Egress Point 1 — Primary model fallback
- **Mechanism:** `fallback_providers` list in `config.yaml`. `_try_activate_fallback()` triggers on HTTP 401/403/404, 429/500/502/503, or max retries on invalid responses.
- **Risk:** llama-server returning 500 (model crash, OOM, slot exhaustion) silently activates fallback. If configured to cloud, prompt leaves the box.
- **Mitigation:** `fallback_providers: []` (validation requires both `provider` and `model` non-empty — blank disables it).

### Egress Point 2 — Auxiliary model routing (HIGHEST RISK)
- **Mechanism:** Auxiliary tasks have *independent* provider/model routing. Tasks: vision, web extraction summarization, **context compression summaries**, session search summarization, skills hub operations, MCP helper operations, memory flushes.
- **Risk:** Default `provider: auto` auto-detects from env. Compression fires automatically at 50% of context window — every long conversation triggers it. With `OPENROUTER_API_KEY` or `OPENAI_API_KEY` in daemon env, auto-detect resolves to cloud and ships entire middle of conversation through it.
- **Mitigation:** Explicit `auxiliary.<task>.provider: main` for every auxiliary task. Belt-and-suspenders: never export those env vars to the daemon.

### Egress Point 3 — Auxiliary task fallback chains
- **Mechanism:** Each auxiliary task has its own fallback chain (vision, compression, web extraction, session search). Configurable independently via `auxiliary.*.fallback_providers`.
- **Risk:** Same as #1, multiplied across 7+ task types.
- **Mitigation:** `auxiliary.<task>.fallback_providers: []` for every auxiliary task.

### Egress Point 4 — Native Anthropic credential auto-detection (LOCAL-MACHINE-SPECIFIC RISK)
- **Mechanism:** Per provider-runtime docs: "Credential resolution for native Anthropic now prefers refreshable Claude Code credentials over copied env tokens when both are present."
- **Risk:** Brandon's machine has Claude Code installed (powering Cowork mode). If `hermes-agent` runs as `festro33` and provider ever resolves to `anthropic`, it'll find and use Claude Code credentials — sending prompts to Anthropic on Brandon's account.
- **Mitigation:** Never set `provider: anthropic`. Keep `ANTHROPIC_TOKEN` / `CLAUDE_CODE_OAUTH_TOKEN` out of daemon env. Run daemon under a clean systemd unit that explicitly sets only required env vars (no shell inheritance).

### Egress Point 5 — Tools that themselves call the network
- **Mechanism:** Web search tool, browser automation, MCP client, web_extract — these are tool-level network calls, not provider routing. They bypass all provider config.
- **Risk:** Any enabled tool that touches the network is an egress vector regardless of provider pinning.
- **Mitigation:** Tool whitelist via `tools.disabled` in config. Initially disable: `web_search`, `web_extract`, `browser_*`, plus any MCP tools that aren't explicitly local.

### Egress Point 6 — Gateway session hygiene (85% threshold)
- **Mechanism:** `gateway/run.py` runs auto-compression at 85% before agent processes message. Uses same auxiliary client as #2.
- **Risk:** Inherits all risks from #2. Path likely doesn't fire when running headless without messaging adapters, but verify.
- **Mitigation:** If running fully headless, gateway path may not be reached. Confirm in H1.3 (headless verification) — if gateway never starts, this point is moot. If it does start, mitigations from #2 apply.

### Egress Point 7 — Compression model context length silent failure
- **Mechanism:** Per context-compression docs: "The summary model must have a context window at least as large as the main agent model's." If smaller, returns context-length error → `_generate_summary()` catches it → drops middle turns *without* a summary → silently degraded conversation quality.
- **Risk:** Not a network leak — a silent quality degradation. Relevant when pinning compression to local Qwen3 endpoint.
- **Mitigation:** Use the same Qwen3 unified endpoint for compression (`auxiliary.compression.provider: main` already covers this). Verify Qwen3 context configuration matches main model's (default 32K, extendable to 128K with YaRN).

### Structural recommendations beyond the seven points

- **Run hermes-agent in a network namespace** (`ip netns`) or with iptables egress rules allowing only `127.0.0.1`. Belt-and-suspenders — kernel-level enforcement that survives config drift. Per AGPLv3+linking-exception ethos, this is the right default for the project. (See H1.6.)
- **Periodic egress audit in `doctor.sh`** — adds a synthetic "trigger compression" workload check that watches for non-localhost packets. Catches config drift on every health check, not just at H1.5/H1.6.

---

## Trade-offs Accepted

- **Loss of architectural ownership over orchestration layer.** Hermes' design choices become ours. Mitigation: MIT license allows forking; AGPLv3+linking exception cleanly absorbs MIT.
- **Loss of persona-first identity at worker level.** Workers are stateless. The "agent that grows with you" property lives only at the Hermes main-loop level, not per-role. Acceptable given the persona/SillyTavern/Godot stack already owns identity at the user-facing layer.
- **Hermes' SQLite/FTS5 session storage duplicates some of Chroma/Qdrant's role.** They serve different purposes (FTS5 for session lineage; vector RAG for semantic memory) but they overlap on "find what we discussed." Resolution deferred — both can coexist; if redundancy becomes a problem it can be pruned later.
- **Hermes upgrade cadence is theirs, not ours.** Breaking changes in Hermes will require integration work. Mitigation: pin Hermes version, evaluate each release before bumping.
- **One more daemon child to monitor.** Three-strike restart policy already covers it.
- **Network egress risk surface is non-trivial.** Hermes has seven independent egress paths and one local-machine-specific risk (Claude Code credential auto-detection). Defaults are not safe for AGPLv3 self-hosted operation. Mitigated by the safe-config recipe in Appendix A, H1.5 packet-capture verification, and H1.6 kernel-level egress containment. Adds operational discipline that wouldn't exist with a build-native orchestrator — but the alternative is months of building equivalent functionality from scratch.

---

## Rollback Path

Hermes is loosely coupled — it sits behind the Task Board contract. If Hermes integration proves untenable:

1. Revert daemon dispatcher to in-process workers (Python subprocess pool fanning out to llama-server directly)
2. Keep the Task Board schema extensions (Tenacity-style columns) — they're useful regardless of orchestrator
3. Revisit Phase 8/9 with build-native option

The Task Board boundary means the rollback doesn't touch server.py routing logic. Only the dispatcher implementation changes.

---

## Acceptance Criteria

The Hermes adoption migration is complete when:

1. Hermes runs as a daemon child, restarts under the three-strike rule, logs to `logs/hermes.log`
2. server.py `/chat` correctly routes trivial queries in-band and non-trivial queries to the Task Board
3. Hermes workers pull tasks from the Task Board, execute, write results back with validation
4. Heartbeat / reclaim sweeper handles a forced kill of Hermes mid-task without zombie tasks
5. Validation hook handles a forced malformed worker output by retrying with feedback
6. Persona surfaces Hermes-produced results via the existing surfacing behavior (no new surfacing path)
7. Role-prefix templates achieve >80% KV cache hit rate over a 50-task batch (measured via llama-server logs)
8. End-to-end research-grade query returns a synthesized persona response within target latency (TBD — establish baseline during M6 of single-model migration)

---

## Next-Session Entry Point

**Do not start H1 until single-model migration M1-M12 is complete.**

When ready: resume at H1.1 (read Hermes docs end-to-end). The brainstorm here covers the why; H1.1-H1.5 are pre-flight verification of assumptions before any code.

If any H1 check fails (Hermes can't accept custom endpoints, can't run headless, can't pin to local-only), this decision needs to be reopened. None of the failures are expected based on architecture docs reviewed this session, but H1 exists to catch documentation-vs-reality gaps before commitment.

---

## Appendix A — Safe Local-Only Hermes Config Recipe

Reference config.yaml shape for local-only operation. Derived from H1.5 investigation against Hermes v0.13.0 documentation. Validate against actual config schema during H1 — provider names, model identifiers, and exact key paths may shift between versions.

```yaml
# ── Primary model — pinned to local unified llama-server ──
provider: custom
model: qwen3-30b-a3b
custom_providers:
  - name: local-llama
    base_url: http://127.0.0.1:8080/v1
    api_key: not-needed

# ── No primary fallback — local-only means no cloud failover ──
fallback_providers: []

# ── Auxiliary tasks all routed through main (= local llama-server) ──
auxiliary:
  compression:
    provider: main
    fallback_providers: []
  vision:
    provider: main
    fallback_providers: []
  web_extraction:
    provider: main
    fallback_providers: []
  session_search:
    provider: main
    fallback_providers: []
  skills_hub:
    provider: main
    fallback_providers: []
  mcp_helper:
    provider: main
    fallback_providers: []
  memory_flush:
    provider: main
    fallback_providers: []

# ── Compression — keep enabled, ensure summary model context >= main ──
compression:
  enabled: true
  threshold: 0.50

# ── Tool whitelist — disable network-egress tools ──
tools:
  disabled:
    - web_search
    - web_extract
    - browser_*
```

### Daemon environment hygiene

The daemon process must NOT export any of:

- `ANTHROPIC_TOKEN`
- `CLAUDE_CODE_OAUTH_TOKEN`
- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `AI_GATEWAY_API_KEY`
- `GOOGLE_API_KEY` / `GEMINI_API_KEY`
- `HUGGINGFACE_TOKEN`
- Any other provider-specific cloud credential

Recommended: run `hermes-agent` from a systemd unit (or daemon.py-managed subprocess) that explicitly sets `Environment=` directives for only the variables it needs (`HERMES_HOME`, `PATH`, `HOME`, custom-endpoint base URL). Never inherit the user shell environment — that's the failure mode that lets stray cloud creds in.

### Session storage path

Per H1.4 — confirm `HERMES_HOME` or equivalent points under `data/hermes/` so session SQLite lives inside the project folder and remains portable. Default may be `~/.hermes/` which would scatter state outside the project.

### Tool whitelist refinement

Initial blanket disables above are conservative. As specific local-only tools become useful (file_tools, code_execution_tool with local sandbox, terminal_tool with `local` backend), enable them explicitly. MCP tools should be evaluated case-by-case — many MCP servers are themselves cloud APIs.

---

## Sources

- [Hermes Agent — Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)
- [Hermes Agent — Agent Loop Internals](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)
- [Hermes Agent — Provider Runtime Resolution](https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime)
- [Hermes Agent — Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)
- [Hermes Agent — Overview](https://hermes-agent.nousresearch.com/)
- [NousResearch/hermes-agent on GitHub](https://github.com/NousResearch/hermes-agent)
- [Hermes Agent Releases (Tenacity, May 2026)](https://github.com/NousResearch/hermes-agent/releases)
- `archive/handoffs/HANDOFF_2026-05-09_0950_single-model-migration.md` (predecessor — must complete first)
- `knowledge.md` (DECISION 2026-05-11 entry — same-session sync)

---

*Frozen decision record — do not edit. Future revisions create a new dated handoff.*
