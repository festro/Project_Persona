# HANDOFF — Stack Compatibility Re-Evaluation (Hermes + Qwen3.6, Tiered)

**Date:** 2026-05-15 0827 UTC
**Topic:** Stack-wide compatibility re-evaluation triggered by Hermes adoption (DECISION 2026-05-11) and the in-flight model swap consideration (Qwen3-30B-A3B-Instruct-2507 → Qwen3.6-35B-A3B)
**Status:** Re-evaluation complete. Tiered action plan (T0-T4) frozen. Implementation queued behind Tier 0 GO/NO-GO gate.
**Owner:** Brandon (festro3@gmail.com)
**Predecessors:**
- `HANDOFF_2026-05-09_0950_single-model-migration.md` — single-model topology decision
- `HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md` — Hermes Agent adoption decision
**Related:** `knowledge.md` rolling state (T0-T4 tiered TODO block + DECISION entries)

---

## Why this re-evaluation happened

DECISION 2026-05-09 locked single-model consolidation onto Qwen3-30B-A3B with parallel slots and mode-switched prompts. M1 (2026-05-14) initially picked **bartowski/Qwen3-30B-A3B-Instruct-2507** as the GGUF source. Investigation that same session surfaced two consequential findings:

1. **Instruct-2507 has no thinking mode** — the 2507 release split the original Qwen3-30B-A3B's dual-mode model into separate variants (`Instruct-2507` non-thinking only, `Thinking-2507` thinking only). The mode toggle that justified DECISION 2026-05-09's "single model serves both persona and reasoning" premise was abandoned in this lock.
2. **Qwen3.6-35B-A3B exists, has the toggle back** — Q5_K_XL Unsloth Dynamic GGUFs landed during this session; benchmarks materially better; thinking + `preserve_thinking` features map cleanly onto Hermes' multi-turn agent loops.

Combined with the parallel locking-in of Hermes Agent as the agent-work backbone (DECISION 2026-05-11), the stack faces *two* concurrent architectural shifts. A layer-by-layer re-evaluation became necessary before locking the model choice and proceeding into M3 (config edits).

---

## Re-Evaluation: Per-Layer Findings

For each layer, identified compatibility status, specific issues, and integration changes triggered by **Hermes adoption** and **Qwen3.6 swap** independently.

### Hardware / OS substrate

- **Hermes:** ✅ No interaction. Hermes is software, runs anywhere Python 3.11+ runs.
- **Qwen3.6:** ✅ No change. 26.6 GB Q5_K_XL fits comfortably in 96 GB unified memory. `bf16: 0` (verified in M2a) remains irrelevant for Q5 weights and q8_0 KV cache.

### Inference layer

- **Hermes:** ⚠️ Compatible with discipline required. Hermes points at llama-server via `provider: custom`, no inference changes. Role-prefix templates must use stable prefixes for KV cache amortization. If multimodal enabled, Hermes' vision pathway must coordinate with llama.cpp's `mmproj` pattern.
- **Qwen3.6:** ⚠️ **Several real concerns.**
  - `qwen3_5_moe` arch support in llama.cpp is unverified (Unsloth GGUF existence ≠ llama.cpp inference path)
  - `mmproj` files are a new pattern for this stack (~900 MB optional vision projector)
  - Sampling regime differs significantly: thinking mode wants `temp=1.0, top_p=0.95, top_k=20, presence_penalty=1.5`
  - Thinking mode toggle is back (`enable_thinking` flag) — restores DECISION 2026-05-09 premise that Instruct-2507 had abandoned
  - MTP-trained — vLLM/SGLang have native serving path, llama.cpp may not yet

### API layer

- **Hermes:** ⚠️ Substantial changes — `/chat` adds routing decision (trivial → in-band, non-trivial → Task Board); `/agent/run` reshapes from synchronous subprocess to Task Board submit; new endpoints or extensions for Task Board polling.
- **Qwen3.6:** ⚠️ Non-trivial server.py changes — sampling params overhaul, `enable_thinking` wiring through `chat_template_kwargs`, `preserve_thinking: true` for Hermes-originated requests, `<think>` stripping at persona surface graduates from "future" to "must-have day one."

### Vector store / RAG layer

- **Hermes:** ⚠️ Dual-memory situation surfaced. Hermes adds SQLite + FTS5 session search + `MEMORY.md`/`USER.md` files; functional overlap with Qdrant on "what did we discuss before?" Decision deferred — both can coexist (different scopes), revisit if friction emerges.
- **Qwen3.6:** ✅ No interaction.

### Agent layer

- **Hermes:** ✅ This layer IS Hermes by definition.
- **Qwen3.6:** ✅ Net positive. `preserve_thinking: true` aligns beautifully with Hermes' multi-turn delegation pattern. Per-profile `config.yaml` must include Qwen3.6 sampling params.

### Daemon layer (Phase 3)

- **Hermes:** ⚠️ Additive enhancements. New asyncio tasks (`task_dispatcher`, `reclaim_sweeper`); new IPC events (`task_ready`, `hermes_ready`); profile switch handling triggers Hermes child restart with new HERMES_HOME; egress containment (H1.6) requires daemon to launch hermes-agent inside ip netns or under iptables egress rules.
- **Qwen3.6:** ✅ No structural change. Single child process (llama-unified) regardless of which Qwen variant.

### Storage layer

- **Hermes:** ⚠️ New gitignore + sterilize-exclude entries needed. `data/tasks.db` Tenacity columns already documented; per-profile `MEMORY.md`, `USER.md`, `hermes_state.db` must be gitignored.
- **Qwen3.6:** ✅ No schema change.

### Frontend (OpenWebUI — locked)

- **Hermes:** ✅ No changes needed. OpenWebUI talks to FastAPI `/v1/chat/completions`, doesn't see Hermes directly.
- **Qwen3.6:** ✅ Net positive when vision enabled. OpenWebUI's native image-upload UI works against Qwen3.6's vision endpoint with no frontend changes.

### Embodiment layer (Phase 4)

- **Hermes:** ✅ Compatible. STATE channel vocabulary now lives in `.hermes.md` per profile. Hermes worker output is gathered + synthesized through Task Board → persona, where STATE/RESPONSE split happens.
- **Qwen3.6:** ✅ Bonus capability. Vision unlocks future avatar perception (webcam input, environmental context).

### Voice layer (Phase 5)

- Both: ✅ Independent of model and agent layer.

### Sorting Line (Phase 6)

- **Hermes:** ✅ Compatible. Two integration modes available (ingest worker direct OR Task Board jobs to librarian role); defer choice to Phase 6 implementation.
- **Qwen3.6:** ✅ Modest enhancement opportunity. PDF/image ingestion could use Qwen3.6 vision directly instead of OCR pre-processing.

### Sleep Cycle (Phase 7)

- Both: ✅ Compatible. No required interaction.

### Operational scripts

- **Hermes:** ⚠️ doctor.sh adds H6.5 egress audit + Hermes integration checks; setup_native_stack.sh adds env_hermes venv + Hermes install; init_profiles.sh scaffolds per-profile config.yaml + Hermes-managed file gitignore.
- **Qwen3.6:** ⚠️ unified_test.sh adds thinking-mode toggle + sampling preset + `<think>` stripping smoke tests.

### Languages / runtimes

- **Hermes:** ⚠️ New venv strongly recommended. `env_hermes/` separate venv (same isolation pattern as `env_webui/`).
- **Qwen3.6:** ✅ No new runtime requirements.

### License framework

- Both: ✅ Compatible. Hermes is MIT, Qwen3.6 is Apache 2.0; both clean against AGPLv3+linking exception.

### Configuration (run/config.env)

- **Hermes:** ⚠️ Two config surfaces now. `run/config.env` adds Hermes daemon-facing tunables (heartbeat interval, reclaim seconds, max attempts, venv path, log level, netns config). Per-profile `config.yaml` (Hermes' own) lives in HERMES_HOME, must be templated by daemon to enforce safe-config by construction.
- **Qwen3.6:** ⚠️ Several new keys. `PERSONA_MODEL` filename change; per-mode sampling presets; `VISION_ENABLED` toggle (default off); `MMPROJ_PATH` when vision enabled; `ASYNC_REASONING_ENABLED` becomes vestigial (replaced by `ENABLE_THINKING_FOR_NONTRIVIAL`).

### Known Issues intersections

- **`<think>` stripping (M8):** Graduates from future-work to immediate. Qwen3.6 always wraps reasoning in `<think>` when thinking mode on; persona must never expose to user.
- **Profile wrapper bloat:** Largely solved by 2-file profile + `cache_prompt`.
- **`bf16: 0`:** Continues to be irrelevant for Q5 + q8_0 cache.
- **`ASYNC_REASONING_ENABLED`:** Vestigial after Qwen3.6 + Hermes both adopted.

---

## Meta-Finding

**Qwen3.6 honors the DECISION 2026-05-09 design intent better than Instruct-2507 did.**

The May 9 DECISION justified single-model consolidation with: *"Native thinking-mode toggle maps directly onto the existing persona/reasoning split without needing two model files."*

- **Instruct-2507** (M1's original lock): no thinking mode. The toggle that justified the consolidation premise was abandoned. Adopting Instruct-2507 would have forced either (a) running two model files anyway (defeating the consolidation) or (b) abandoning the explicit thinking-mode role (defeating part of the design).
- **Qwen3.6:** thinking mode is back. `enable_thinking` flag works as the May 9 design assumed. Plus a new `preserve_thinking` feature that maps cleanly onto Hermes' multi-turn delegation, which DECISION 2026-05-09 didn't anticipate but which improves the design retroactively.

This is an architectural-coherence win, separate from raw benchmark deltas (GPQA 86 vs 70, LiveCodeBench v6 80 vs 43, etc.).

---

## Tiered Action Plan

Reorganized from convergent H7.x + Q1.x analytical labels into a discrete tier structure for incremental validation. Each tier is a verification gate. Issues surface in the tier they were introduced.

### Tier 0 — GO/NO-GO gate (≈30 min if both pass cleanly)

| ID | Item | Acceptance |
|---|---|---|
| T0.1 | Empirical llama.cpp arch test for `qwen3_5_moe`. Download `Qwen3.6-35B-A3B-UD-IQ1_M.gguf` (10 GB), load via llama-server. | Loads + generates coherent output |
| T0.2 | Tool-calling template verification for Qwen3.6. Round-trip test. | Parseable tool call emitted |

**Gate behavior on T0.1 failure:** Qwen3.6 work halts. Decision branch:
- Fall back to Instruct-2507 alone (no thinking mode, accept design compromise)
- Wait for llama.cpp `qwen3_5_moe` arch support (passive — possibly weeks-months)
- Stand up vLLM via gfx1101 override (operational complexity, performance/correctness uncertainty on novel arch)

### Tier 1 — Foundation (≈2-4 hours, parallel-safe)

| ID | Item | Acceptance |
|---|---|---|
| T1.1 | `env_hermes/` separate venv. Update setup_native_stack.sh, status.sh, doctor.sh awareness. | venv exists, hermes-agent installable, ops scripts aware |
| T1.2 | Per-profile Hermes `config.yaml` template. init_profiles.sh generates safe-config-conformant config (provider:custom → 127.0.0.1:8080, fallback_providers:[], all auxiliary provider:main, tool whitelist) AND Qwen3.6 sampling params. | doctor.sh validates default profile config.yaml against safe-config schema |

### Tier 2 — Core integration (≈4-8 hours, partial parallelism)

| ID | Item | Acceptance |
|---|---|---|
| T2.1 | Sampling defaults overhaul in run/config.env + server.py. Per-mode presets. | server.py selects preset based on routing + thinking-mode toggle |
| T2.2 | Wire `enable_thinking` toggle through `chat_template_kwargs`. Empirical risk if llama.cpp template engine doesn't read it. | Trivial query → no `<think>`; non-trivial → `<think>` present |
| T2.3 | Wire `preserve_thinking: true` for Hermes-originated requests. | Multi-turn agent loops preserve reasoning across iterations |
| T2.4 | `<think>...</think>` stripping at Task Board → persona surface boundary (one chokepoint). | User-facing responses contain zero `<think>` blocks regardless of source |

### Tier 3 — Operational hardening (≈2-4 hours, mostly independent)

| ID | Item | Acceptance |
|---|---|---|
| T3.1 | doctor.sh integration checks (HERMES_HOME, hermes-agent process, gitignore, env_hermes, per-profile config.yaml conformance, egress audit). | All checks pass |
| T3.2 | unified_test.sh Qwen3.6-specific tests. | All smoke tests green |
| T3.3 | Replace `ASYNC_REASONING_ENABLED` with `ENABLE_THINKING_FOR_NONTRIVIAL` semantic. | Vestigial removed |

### Tier 4 — Deferred / opt-in (no scheduled work)

| ID | Item | Trigger condition |
|---|---|---|
| T4.1 | Dual-memory resolution (Qdrant vs Hermes session_search unification) | User-facing query surfaces contradictory information from the two systems |
| T4.2 | Vision pathway (`VISION_ENABLED=1` + mmproj loading) | Specific use case explicitly demands it |
| T4.3 | MTP / speculative decoding for Qwen3.6 | llama.cpp adds MTP support OR draft model becomes available |

---

## Sequencing Rationale

The tiering is structured around three principles:

1. **Validate the foundational assumption first.** Tier 0 answers a yes/no question whose "no" answer changes the entire downstream plan. Doing T0 early prevents wasted work on an inference path that doesn't exist.

2. **Build foundations before integration.** Tier 1 sets up the venv and config-template infrastructure that all subsequent integration work depends on. Skipping straight to T2 would force foundation-level rework mid-integration.

3. **Operationalize after functional.** Tier 3 (doctor.sh, unified_test.sh, cleanup) only makes sense once core integration (T2) is producing results that need monitoring. Adding monitoring to a pre-functional system catches noise, not signal.

Within each tier, items are sequenced to fail-early on the highest-risk dependency.

---

## Acceptance Criteria — End-to-End

The compatibility re-evaluation work is complete when:

1. T0 passes — Qwen3.6 loads in llama.cpp; tool calls parse correctly
2. T1 passes — env_hermes installed; default profile config.yaml safe-config conformant
3. T2 passes — trivial query returns clean response with no `<think>`; non-trivial routes to Hermes, returns synthesized response with no `<think>` artifacts; sampling presets match config; tool calling round-trips correctly
4. T3 passes — doctor.sh + unified_test.sh both green; ASYNC_REASONING_ENABLED removed; per-profile config.yaml validates against safe-config schema
5. T4 items remain in Tier 4 unless triggers fire

The migration as a whole (M1-M12 + H1-H6 + T0-T4) is complete when all three blocks reach their acceptance criteria.

---

## Trade-offs Accepted

- **Vision deferred (T4.2)** — Qwen3.6's vision capability remains opt-in. Loses "free win" of multimodal but preserves security-conscious default and avoids untested attack surface.
- **Dual-memory deferred (T4.1)** — Hermes' SQLite/FTS5 session search and Qdrant typed-payload memory coexist. Accepts ~20% conceptual duplication for ~80% less integration code initially.
- **MTP deferred (T4.3)** — Qwen3.6's MTP-ready weights can't be exploited until llama.cpp adds support. Performance left on table.
- **Sampling regime change blast radius (T2.1)** — Qwen3.6's sampling differs significantly from Qwen3 family. Per-mode preset infrastructure adds config surface but enables future model swaps cleanly.
- **`chat_template_kwargs` plumbing risk (T2.2)** — If llama.cpp's template engine doesn't read this field, fallback is system-prompt injection. Slightly hacky but functional.

---

## Rollback Path

If Tier 0 fails, the rollback is conceptually simple — keep Qwen3-30B-A3B-Instruct-2507 as the locked M1 choice (the lock that was already encoded in knowledge.md and HANDOFF_2026-05-09 prior to this re-evaluation). The Tier 1-3 work (env_hermes, config.yaml templating, server.py wiring) still applies; only the model file changes. Most of the T2 changes (sampling, `<think>` stripping) become smaller-scope or inapplicable since Instruct-2507 has no thinking mode.

If Tier 0 partially fails (T0.1 passes, T0.2 fails — model loads but tool calling broken), a custom GBNF grammar can constrain output. ~1-2 hours of grammar work, no architectural change.

---

## Next-Session Entry Point

**Resume at T0.1** — download Qwen3.6-35B-A3B-UD-IQ1_M.gguf (10 GB) and attempt to load via the existing llama.cpp build 8157 with Vulkan. Capture:
- Architecture detection output (look for `qwen3_5_moe`)
- Whether load succeeds
- Output coherence on a basic prompt (e.g., "Explain what an LLM is in one sentence.")
- Any error messages

```
cd ~/Live/AIStack/Project_Persona/models/
huggingface-cli download unsloth/Qwen3.6-35B-A3B-GGUF \
    --include "Qwen3.6-35B-A3B-UD-IQ1_M.gguf" --local-dir .

LD_LIBRARY_PATH=$HOME/Live/AIStack/Project_Persona/llama_cpp/build/bin \
~/Live/AIStack/Project_Persona/llama_cpp/build/bin/llama-server \
    --model Qwen3.6-35B-A3B-UD-IQ1_M.gguf \
    --port 8090 --n-gpu-layers 0 -c 2048 2>&1 | tee /tmp/qwen36_load_test.log
```

Then in another shell, hit it with a quick generation test:

```
curl -s http://127.0.0.1:8090/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen3.6","messages":[{"role":"user","content":"Explain what an LLM is in one sentence."}],"max_tokens":100}'
```

Paste the relevant load log + the curl response in the next session — that's T0.1 done in five minutes.

---

## Sources

- `HANDOFF_2026-05-09_0950_single-model-migration.md` (predecessor)
- `HANDOFF_2026-05-11_0038_agent-swarm-hermes-adoption.md` (predecessor — Hermes adoption decision + safe-config recipe in Appendix A)
- `knowledge.md` rolling state (T0-T4 tiered TODO block, DECISION 2026-05-11 entry, Hermes Adoption + Single-Model Migration TODO blocks)
- [Hermes Agent — Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)
- [Hermes Agent — Prompt Assembly (file priority logic)](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)
- [Hermes Agent — Provider Runtime Resolution](https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime)
- [Hermes Agent — Context Compression and Caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)
- [unsloth/Qwen3.6-35B-A3B-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF)
- [Qwen/Qwen3.6-35B-A3B (model card via Unsloth)](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF)
- [Qwen/Qwen3-30B-A3B-Instruct-2507 (the M1 alternative)](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507)
- [bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF)

---

*Frozen decision record — do not edit. Future revisions create a new dated handoff.*
