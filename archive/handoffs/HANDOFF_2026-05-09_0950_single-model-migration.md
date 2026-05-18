# HANDOFF — Single-Model Consolidation Migration

**Date:** 2026-05-09
**Time:** 0950 UTC
**Topic:** Inference topology consolidation — multi-model → single-model
**Status:** Approved, migration in progress (M1 resolved 2026-05-14)
**Supersedes:** Three-model topology (persona 8080 / reasoning 8081 / coder 8082)
**Owner:** Brandon (festro3@gmail.com)
**Related:** `knowledge.md` (rolling state — see Active Architectural Decisions)

**M1 RESOLUTION ADDENDUM (2026-05-14 1701 UTC):**
GGUF source locked to **bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF Q5_K_M** (21.74GB, imatrix calibrated, llama.cpp release b6014, Apache 2.0). The "Instruct-2507" suffix is the July 2025 instruction-tuned update — more recent than the base Qwen3-30B-A3B referenced in the original decision. Path 2 (jump to Qwen3.5-35B-A3B / Qwen3.6-35B-A3B) evaluated and deferred to TODO #36 in knowledge.md — re-check in 2-3 months when llama.cpp `qwen3_5_moe` arch support and bartowski Q5_K_M imatrix GGUFs land. Download: `huggingface-cli download bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF --include "Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf" --local-dir ~/Live/AIStack/Project_Persona/models/`. Next-session entry point now M2 (Vulkan/ROCm verification on Strix Halo).

---

## Summary

Project_Persona is migrating from a multi-model inference topology (separate llama.cpp servers for persona, reasoning, and a planned coder role) to a single-model topology served by one llama.cpp instance with parallel slots. Role differentiation moves from URL-based dispatch to prompt-based mode switching, leveraging Qwen3-30B-A3B's native thinking-mode toggle.

This handoff is the frozen decision record for that change. Implementation work is tracked in `knowledge.md` under Migration items M1–M12.

---

## Decision

**Replace** the current and planned inference servers:

| Retired | Model | Quant |
|---|---|---|
| persona (8080) | Meta-Llama-3.1-8B-Instruct | Q4_K_M |
| reasoning (8081) | Qwen2.5-14B-Instruct | Q5_K_M |
| coder (8082, never built) | TBD | TBD |

**With** a single unified server:

| New | Model | Quant | Slot Plan |
|---|---|---|---|
| unified (8080) | Qwen3-30B-A3B | Q5_K_M | 4–6 parallel slots, continuous batching enabled |

Role differentiation strategy:

- **Persona role** — `enable_thinking: false`, temperature 0.7, persona system prompt
- **Reasoning role** — `enable_thinking: true`, temperature 0.2, structured-output system prompt (TL;DR / key points / risks / next actions)
- **Code role** — `enable_thinking: true`, temperature 0.1, code-specialist system prompt
- **Distillation role** — `enable_thinking: false`, temperature 0.2, fact-extraction system prompt

All four roles share weights, share the loaded model, share GPU. Workers are llama.cpp slots (ephemeral KV cache, fresh per request).

---

## Rationale

### Why a single model

The orchestrator-worker swarm pattern works best when workers are short-lived, bounded, and homogeneous. Project_Persona's existing FF-agent + silent-experts design is structurally that pattern, but with heterogeneous worker models (different weights per role) — which adds ops complexity, fault domains, and KV cache fragmentation without buying capability the unified topology can't deliver.

When the same model can competently handle persona, reasoning, code, and distillation roles, two-server deployment becomes pure overhead. Qwen3-30B-A3B can.

### Why Qwen3-30B-A3B specifically

- **Mixture-of-Experts with 3B active parameters.** On the EVO-X2's bandwidth-limited unified memory (~256 GB/s LPDDR5X), inference speed is bandwidth-bound. Active parameter count drives throughput — 3B active means roughly 5× the tokens/sec of a dense 14B at equivalent quality.
- **Native thinking-mode toggle.** Maps directly onto the persona/reasoning split. Same weights, same loaded model — only the request payload differs.
- **Native 32K context, extendable to 128K via YaRN.** Substantially relaxes the prompt-budget pressure flagged in `knowledge.md` Known Issues.
- **Apache 2.0 license.** Compatible with project's AGPLv3 + linking exception.
- **Mature GGUF ecosystem.** Stable builds available from bartowski, Unsloth, and the official Qwen team.
- **Strong on code, math, and structured output.** Removes the case for a separate coder server.

### Why Q5_K_M (not Q4_K_M, not IQ-variants)

The model is expected to perform research-grade reasoning (independent biology research is the stated use case). Three concerns push toward higher precision:

1. **Compounding error in long thinking traces.** A 2% per-step accuracy reduction over a 20-step reasoning chain is observable in output coherence even when single-token benchmarks look similar.
2. **Domain-specific terminology.** Biology and other specialized domains live in lower-probability tail tokens where quantization noise can substitute confident-sounding wrong terms.
3. **MoE router sensitivity.** The router's expert-selection projection layer is more affected by quantization noise than dense models — quantization can route domain queries to non-specialized experts.

The size delta (Q5_K_M ~21–22GB vs Q4_K_M ~17–18GB) is irrelevant on 96GB. The throughput delta (~20%) is acceptable for the harder workload. IQ-variants were considered and declined — performance and compatibility are the priorities, not marginal size savings.

### Why not other candidates

- **Mistral Small 3.2 24B (dense)** — dense architecture means significantly slower on bandwidth-limited APU; otherwise good but no upside over Qwen3.
- **Gemma 3 27B (dense)** — same speed concern; multimodal capability is interesting for a future roadmap item but not relevant today.
- **Llama 4 Scout (109B MoE, 17B active)** — 17B active is too slow on this hardware vs 3B active for Qwen3.
- **Qwen3-32B (dense)** — same Qwen lineage but dense; loses the speed advantage that justifies the migration in the first place.

---

## Trade-offs Accepted

| Trade-off | Mitigation |
|---|---|
| ~20% throughput cost vs Q4_K_M | Acceptable — research quality is the harder workload to satisfy |
| Loss of fault isolation between roles | Single server is well-monitored; daemon (Phase 3) handles restart policy |
| Migration effort across env, launcher, server.py | Bounded — three files; sequenced in M1–M12 |
| KV cache slots compete on one server (vs separate per role) | Continuous batching + slot count tuned to load profile |
| Cancels coder server work item | No work lost (was never built); coding tasks served by thinking mode |

---

## Migration Plan

Sequenced as `knowledge.md` items M1–M12. Compressed view here:

### Pre-flight (no code changes)
- **M1** — Acquire Qwen3-30B-A3B-Q5_K_M GGUF. Reputable sources: bartowski/Qwen3-30B-A3B-GGUF, Unsloth's quants, or the official Qwen team's GGUF release on HuggingFace. Verify SHA256 against source page.
- **M2** — Confirm `llama-server` build flags. Run `llama-server --version` and check for Vulkan vs ROCm linkage. Vulkan is the recommended backend on Strix Halo; if currently on ROCm and unstable, rebuild with Vulkan before proceeding.

### Configuration phase
- **M3** — Update `run/llama-servers.env` (or rename to `run/config.env` per general TODO #2). Replace persona/scientist split with single-model section: `MODEL`, `MODEL_CTX`, `GPU_LAYERS`, `PARALLEL_SLOTS`, `PORT`.
- **M4** — Update `start_llama_servers.sh`. Single `start_one` invocation. New flags: `--parallel ${PARALLEL_SLOTS} --cont-batching`. Important: `--ctx-size` becomes total across all slots — multiply per-slot context by slot count in the script.
- **chmod +x `start_llama_servers.sh`** after editing.

### API phase
- **M5** — Update `services/api/server.py`:
  - Collapse `PERSONA_URL` and `SCIENTIST_URL` into one endpoint.
  - Add `mode` parameter to request payloads (`persona` / `reasoning` / `code` / `distill`), each setting `enable_thinking`, `temperature`, `top_p`, and system prompt selection.
  - Remove or substantially raise `PERSONA_CONCURRENCY` semaphore — let llama.cpp's slot scheduler handle concurrency.
  - Add `cache_prompt: true` to all request payloads for static-prefix KV cache reuse.
- **M6** — Replace serial in-band scientist call with `asyncio.gather` parallel dispatch for RAG retrieval and worker invocation.
- **M7** — Already covered above.
- **M8** — Add `<think>` tag stripping in response post-processing for thinking-mode responses, before user-facing surface. Preserve in audit log.

### Polish phase
- **M9** — Trim profile wrappers. Audit current sizes; if any single file exceeds ~2KB, split into core (always loaded) and extended (loaded on demand by topic). Re-evaluate context budget against Qwen3's 32K native window.
- **M10** — Update `unified_test.sh`. Single endpoint, mode-toggle smoke tests, thinking-tag stripping verification, parallel dispatch latency assertions.
- **M11** — Decommission. Remove scientist server invocation from launcher. Archive (don't delete) old GGUFs to `models/archive/` for rollback.
- **M12** — Update README inference table to single-model topology.

---

## Rollback Plan

The migration is reversible at any phase up through M11 by:
1. Restoring the prior `run/llama-servers.env` (kept in git).
2. Restoring the prior `start_llama_servers.sh` (kept in git).
3. Reverting `services/api/server.py` (kept in git).
4. Restarting servers — old GGUFs remain in `models/` until M11.

Post-M11, rollback requires re-downloading the old Llama-3.1-8B and Qwen2.5-14B GGUFs. To soften this: M11 archives rather than deletes.

If the migration completes but throughput or quality is unacceptable in production:
- First fallback: re-quantize Qwen3-30B-A3B to Q4_K_M (30-minute job, no architecture change).
- Second fallback: revert to multi-model topology via the rollback above.

---

## Acceptance Criteria

The migration is considered successful when:

1. `unified_test.sh` passes end-to-end against the single-model topology.
2. Persona-mode latency (TTFB) is within 20% of pre-migration persona server.
3. Reasoning-mode quality on a held-out test set is at least equivalent to pre-migration scientist server (subjective check on biology / research / code prompts).
4. Parallel slot fan-out is observable in `llama-server` logs under load (multiple slots allocated, KV cache shared).
5. `<think>` tags do not leak to user-facing output.
6. RAG retrieval and worker dispatch run in parallel (verifiable via timing in debug payload).
7. `knowledge.md` System State table updated to reflect new topology.
8. README inference table updated.

---

## Open Questions

- **Slot count tuning.** Initial recommendation: 4 slots for the unified server. Revisit after observing real-world load — may want 6 if persona traffic is dominant, may want 2 if reasoning traffic dominates and KV cache pressure becomes the limit.
- **Profile wrapper budget.** Current `_read_text` cap is 12000 chars per file. Should be revisited as part of M9 — recommend lowering to ~3000 chars per file, with an overflow file for rarely-needed material loaded on demand.
- **Backend choice (Vulkan vs ROCm).** Pending M2 verification. If both work, Vulkan recommended for stability.
- **Speculative decoding.** Out of scope for this migration but a strong follow-on candidate. `docs/speculative.md` already in tree; small Qwen3 draft model paired with the main 30B-A3B could deliver 1.5–3× throughput on the hot path. Tracked in general TODO #25.

---

## Operational Notes

- After saving any modified shell script, restore execute permission:
  ```
  chmod +x start_llama_servers.sh
  ```
- All migration changes touch git-tracked files. Recommend a feature branch (`feature/single-model-consolidation`) to isolate the migration sequence and allow per-phase commits aligned to M1–M12.
- The current `run/llama-servers.env` should be preserved in git history before being overwritten — the rollback plan depends on it.

---

*This handoff is a frozen point-in-time record. Live state is maintained in `knowledge.md`.*
