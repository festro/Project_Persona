# Project_Persona — Living Handoff

**Last Updated:** 2026-05-15 2133 PDT
**Type:** Living document — overwritten as state changes (NOT a frozen handoff record)
**Frozen records:** dated `HANDOFF_YYYY-MM-DD_HHMM_*.md` files (see changelog)
**Long-form rolling state:** `knowledge.md`
**Browser-friendly view:** `HANDOFF.html` (regenerate via `scripts/regen_handoff_html.sh`)

> **Document purpose.** This is the "where are we right now and what's next" view. Open this first when resuming work. For full project state see `knowledge.md`. For frozen decision rationale see the dated handoff matching the relevant decision.
>
> **Section collapsibility.** Sections wrap in `<details>`/`<summary>` HTML5 tags. Collapsed sections show only the header until clicked; expanded sections show contents. Renders natively in browsers (HANDOFF.html), GitHub, VS Code Markdown Preview, Obsidian, Typora, and most HTML-pass-through markdown viewers. Section 2 (Critical Path) and Section 3 (Active Work) open by default — everything else collapsed.

---

<details>
<summary><strong>1. System Status</strong> (current state per layer)</summary>

### Inference layer
| Component | Status | Notes |
|---|---|---|
| llama.cpp build 8157 (Vulkan) | ✅ Working | RADV identifies hardware as `GFX1151` native; uma=1, fp16=1, bf16=0, KHR_coopmat present |
| llama-server (persona) port 8080 | ✅ Running — TO BE RETIRED | Llama-3.1-8B-Q4_K_M; superseded by single-model consolidation |
| llama-server (reasoning) port 8081 | ✅ Running — TO BE RETIRED | Qwen2.5-14B-Q5_K_M; superseded by single-model consolidation |
| llama-server (coder) port 8082 | ❌ Cancelled | Superseded by single-model consolidation 2026-05-09 |
| llama-server (unified) port 8080 | ⏳ Planned | Target: Qwen3.6-35B-A3B-UD-Q5_K_XL **(pending T0.1 arch test)** |
| Model file in models/ | ⏳ Not yet downloaded | Awaiting T0 GO/NO-GO with IQ1_M smoke test first |

### API layer
| Component | Status | Notes |
|---|---|---|
| FastAPI Companion API port 8000 | ✅ Running | uvicorn, OpenAI-compatible |
| `/v1/chat/completions` | ⚠️ Streaming claimed but NOT implemented | server.py accepts `stream` field, ignores it, returns single JSONResponse — see HANDOFF_2026-05-11 H4 / Mercury addendum §4.4 |
| `/chat`, `/jobs/{id}`, `/health` | ✅ Verified | Existing surface |
| `/chat_submit` | ❌ Disabled | Returns "chat_submit is disabled in this build." |
| `/agent/run` | ⚠️ Broken (synchronous, blocks event loop up to 300s) | Fix queued in Hermes adoption work — reshape to Task Board submit |
| Routing decision (trivial → in-band, non-trivial → Task Board) | ⏳ Planned | T2 work, post-Tier-0 |

### Storage / RAG
| Component | Status | Notes |
|---|---|---|
| ChromaDB RAG (global only) | ⚠️ Partial | Per-profile not wired; Qdrant migration planned (Phase 2a) |
| Qdrant | ⏳ Planned | Phase 2a — replaces ChromaDB |
| `data/conversations.db` | ⏳ Not yet implemented | Phase 2c |
| `data/tasks.db` (Task Board) | ⏳ Not yet implemented | Replaces in-memory jobs dict; Tenacity-extended schema documented |

### Agent layer
| Component | Status | Notes |
|---|---|---|
| Hermes Agent | ⏳ Planned daemon child | DECISION 2026-05-11 — see HANDOFF_2026-05-11. Implementation queued behind T0 + T1. |
| AG2 / LangGraph / CrewAI / Mercury | ❌ Deleted | All superseded by Hermes adoption — see Section 7 |

### Frontend
| Component | Status | Notes |
|---|---|---|
| OpenWebUI (port 3000) | ✅ Running — **PRIMARY (locked 2026-05-14)** | Separate venv `env_webui/`, data at `openwebui/`, BSD-3+branding clause |
| SillyTavern | ❌ Out of scope | AIP_knowledge.md decision superseded 2026-05-14 |

### Embodiment / Voice / Pipelines
| Component | Status | Notes |
|---|---|---|
| Phase 4 Godot avatar | ⏳ Planned | Two-channel RESPONSE/STATE protocol |
| Phase 5 Whisper.cpp + Piper TTS | ⏳ Planned | Wyoming protocol coordination |
| Phase 6 Sorting Line | ⏳ Planned | watchdog + semantic classifier |
| Phase 7 Sleep Cycle | ⏳ Planned | Idle-triggered consolidation |

### Daemon (Phase 3)
| Component | Status | Notes |
|---|---|---|
| `daemon.py` | ⏳ Not yet implemented | Single asyncio loop, child process map, three-strike restart |
| Unix socket IPC | ⏳ Not yet implemented | `run/daemon.sock` |

### Hardware / OS
| Component | Status | Notes |
|---|---|---|
| AMD RYZEN AI MAX+ 395 / Radeon 8060S | ✅ | Strix Halo, gfx1151 native, 96GB unified |
| ROCm 7.2.0 | ✅ Installed | Operating via `HSA_OVERRIDE_GFX_VERSION=11.0.1` (gfx1101 codegen workaround) |
| Kernel 6.17.0-22-generic | ✅ Running | HWE rolling track; -23 installed waiting for reboot |
| Mesa/RADV Vulkan | ✅ Native gfx1151 |  |

</details>

---

<details open>
<summary><strong>2. Critical Path — Next Action</strong> (open by default)</summary>

**Run T0.1: Empirical llama.cpp arch test for `qwen3_5_moe`.**

This is the GO/NO-GO gate for the entire compatibility re-evaluation work. Five-minute test, blocks all Tier 1+ work.

```
cd ~/Live/AIStack/Project_Persona/models/

huggingface-cli download unsloth/Qwen3.6-35B-A3B-GGUF \
    --include "Qwen3.6-35B-A3B-UD-IQ1_M.gguf" --local-dir .

LD_LIBRARY_PATH=$HOME/Live/AIStack/Project_Persona/llama_cpp/build/bin \
~/Live/AIStack/Project_Persona/llama_cpp/build/bin/llama-server \
    --model Qwen3.6-35B-A3B-UD-IQ1_M.gguf \
    --port 8090 --n-gpu-layers 0 -c 2048 2>&1 | tee /tmp/qwen36_load_test.log
```

Then in another shell:

```
curl -s http://127.0.0.1:8090/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"qwen3.6","messages":[{"role":"user","content":"Explain what an LLM is in one sentence."}],"max_tokens":100}'
```

**Acceptance:** loads + generates coherent output → proceed to T0.2 (tool-calling verification), then Tier 1.
**Failure:** halt Qwen3.6 path. Decision branch — fall back to Instruct-2507 (no thinking mode), wait for llama.cpp arch support, or stand up vLLM via gfx1101 override. See HANDOFF_2026-05-15 "Rollback Path" section.

</details>

---

<details open>
<summary><strong>3. Active Work & Issues</strong> (open by default)</summary>

### Currently focused on
**Pre-implementation: validating the foundational assumption (T0).** All migration work (single-model M1-M12, Hermes adoption H1-H6, compat re-eval T1-T3) is queued behind T0 GO/NO-GO. Nothing else moves until T0.1 returns a clear yes/no.

### Issues encountered (with planned resolution)

**Issue: `/agent/run` synchronous subprocess blocks event loop up to 300s**
- *Encountered:* prior session, recorded in knowledge.md Known Issues; verified by Mercury addendum 2026-04-27
- *Resolution path:* reshape `/agent/run` to Task Board submit endpoint (T2 work). Eliminates the synchronous subprocess entirely — Hermes pulls from Task Board asynchronously.

**Issue: M1 picked Instruct-2507 which has no thinking mode (defeats DECISION 2026-05-09 design intent)**
- *Encountered:* same session as M1 lock, surfaced during compat re-eval
- *Resolution path:* swap target to Qwen3.6-35B-A3B (has thinking mode + new `preserve_thinking` for agent loops). T0 gates this.
- *Frozen analysis:* HANDOFF_2026-05-15 "Meta-Finding"

**Issue: `<think>` tag stripping graduates from M8 future-work to immediate**
- *Encountered:* identified in compat re-eval — Qwen3.6 always wraps reasoning in `<think>` when thinking mode on
- *Resolution path:* T2.4 — implement at Task Board → persona surface boundary (one chokepoint, applies to direct llama-server AND Hermes worker outputs uniformly)

**Issue: Hermes has 7 network egress paths + Claude Code creds risk on this machine**
- *Encountered:* H1.5 investigation 2026-05-11
- *Resolution path:* safe-config recipe enforced by construction via T1.2 (per-profile config.yaml template); kernel-level egress containment via H1.6 (ip netns or iptables rules). Verified by H1.5 packet-capture integration test before production.

**Issue: Vulkan reports `bf16: 0`**
- *Encountered:* M2a verification 2026-05-14
- *Resolution path:* No action needed for Q5 weights / q8_0 KV cache. Flag-only — guard against future configs that assume bf16.

**Issue: Hermes auxiliary model routing defaults to `provider: auto` (cloud-leak risk)**
- *Encountered:* H1.5 investigation
- *Resolution path:* T1.2 config template explicitly pins all `auxiliary.*.provider: main` and empties `fallback_providers`. Belt-and-suspenders via H1.6 kernel egress containment.

**Issue: knowledge.md claims `looks_degenerate()` quality guard is present, but it's not in live code**
- *Encountered:* Mercury addendum 2026-04-27 grep verification — zero matches in live `services/api/server.py`
- *Resolution path:* documentation corrected 2026-05-16 (knowledge.md System State now reflects ❌ NOT present). **Open decision:** reinstate the guard (recommended for persona output safety — catches length / quote-ratio / word-uniqueness / n-gram repetition issues and triggers a two-stage self-repair loop at temp 0.0) OR accept absence. Tracked in Section 4 Open Decisions.

**Issue: README.md and persona/README.md were stale (April-era topology)** ✅ RESOLVED 2026-05-16
- *Resolution:* both READMEs rewritten to reflect locked decisions (Hermes backbone, Qwen3.6 target, OpenWebUI primary, Qdrant target, 2-file Hermes-naming profile, single-model topology). Consolidation batch 2026-05-16.

**Issue: `.gitignore` didn't reflect Hermes-locked file conventions** ✅ RESOLVED 2026-05-16
- *Resolution:* `.gitignore` rewritten to add Hermes-managed paths (MEMORY.md / USER.md / hermes_state.db / sessions/), env_hermes/, data/, inbox/, run/*.sock, archive/cruft/; legacy duplicates removed; `run/llama-servers.env` and `run/config.env` allow-listed. Consolidation batch 2026-05-16.

**Issue: Stale cruft and superseded docs at repo root (`.txt`, `overview_prompt.txt`, two `*.proposed_*` files, `AIP_knowledge.md`, `AIP_HANDOFF_mercury_*`)** ✅ RESOLVED 2026-05-16
- *Resolution:* AIP_ files archived to `archive/`; cruft moved to `archive/cruft/` (sandbox couldn't `rm` directly — user can `rm -rf archive/cruft/` to fully delete when ready). Profile `style.md` files moved to `archive/legacy_profile_files/`. Profile files renamed: `persona.md` → `SOUL.md`, `system_rules.md` → `.hermes.md` in `default/` and `test/` profiles. Repo root now clean. Consolidation batch 2026-05-16.

### Plans for resolving issues
Most issues map to specific tier work (T2.4 stripping, T1.2 config template, etc.). The dispatcher pattern is: each issue has a documented Tier item or TODO entry; tier execution closes the issue; doctor.sh + unified_test.sh additions catch regressions.

</details>

---

<details>
<summary><strong>4. Open Decisions & Deferred Items</strong> (waiting on triggers)</summary>

Things waiting on something, not actively being worked on. Each has a documented trigger to promote it to active work.

| Item | Status | Trigger to revisit |
|---|---|---|
| **T4.1 — Dual-memory unification** (Qdrant vs Hermes session_search) | Deferred; coexistence accepted | User-facing query surfaces contradictory information from the two systems, OR storage cost becomes problematic |
| **T4.2 — Vision pathway** (`VISION_ENABLED=1` + mmproj loading) | Deferred; off by default | Specific use case explicitly demands it (avatar perception, OCR-free PDF ingest) |
| **T4.3 — MTP / speculative decoding for Qwen3.6** | Deferred | llama.cpp adds MTP support OR draft model becomes available |
| **TODO #36 — Re-evaluate Qwen3.5/3.6** at full quant maturity | **Active** as of 2026-05-15 — being addressed by current re-eval | (already being done) |
| **Kernel upgrade to 6.18.4+** for vLLM native gfx1151 path | Deferred; low-friction when needed | vLLM becomes critical path (only if T0 fails AND vLLM is the chosen fallback) |
| **vLLM as inference engine fallback** | Available via gfx1101 override (now), or kernel upgrade for native (later) | T0.1 fails AND a fallback path is needed |
| **`looks_degenerate()` quality guard reinstate** | Open question | Decision needed — reinstate (recommended) or accept absence |
| **Phase 4-7 implementation** | Sequenced behind T0-T3 | Compat re-eval work completes |

</details>

---

<details>
<summary><strong>5. Quick Reference</strong> (commands, paths, URLs, decision shortcuts)</summary>

### Common commands

```
# Get current UTC timestamp
date -u +"%Y-%m-%d %H%M UTC"

# Run llama-server with the LD_LIBRARY_PATH inject (avoids libmtmd.so.0 error)
LD_LIBRARY_PATH=$HOME/Live/AIStack/Project_Persona/llama_cpp/build/bin \
~/Live/AIStack/Project_Persona/llama_cpp/build/bin/llama-server \
    --model <path> --port <port> --n-gpu-layers <n> -c <ctx>

# Verify llama.cpp build
LD_LIBRARY_PATH=$HOME/Live/AIStack/Project_Persona/llama_cpp/build/bin \
~/Live/AIStack/Project_Persona/llama_cpp/build/bin/llama-server --version

# Check ROCm + GPU recognition
uname -r && rocminfo 2>/dev/null | grep -E "Name:|gfx" | head -20
printenv | grep -i HSA

# Apt kernel state
apt-cache policy linux-image-$(uname -r)
dpkg -l | grep -E "linux-(image|headers|generic|oem|hwe)" | head -20

# Sterilize before push (cross-repo script)
~/Git/sterilize.sh --repo Project_Persona --check    # dry-run
~/Git/sterilize.sh --repo Project_Persona            # apply

# Download GGUF to local model dir
huggingface-cli download <repo> --include "<filename>" \
    --local-dir ~/Live/AIStack/Project_Persona/models/

# Regenerate HANDOFF.html from HANDOFF.md
~/Git/Project_Persona/scripts/regen_handoff_html.sh
```

### Key paths

```
~/Live/AIStack/Project_Persona/         → live running instance (real config, real data)
~/Git/Project_Persona/                  → public template repo (sanitized, pushed)
~/Live/AIStack/Project_Persona/models/  → GGUF model files (gitignored)
~/Live/AIStack/Project_Persona/llama_cpp/build/bin/  → llama.cpp binaries
persona/profiles/<name>/                → per-profile (becomes HERMES_HOME)
persona/profiles/<name>/SOUL.md         → personality (Hermes naming, was persona.md)
persona/profiles/<name>/.hermes.md      → rules + STATE vocab (Hermes naming, was system_rules.md)
data/                                   → conversations.db, tasks.db, insights/
inbox/                                  → user file drop (Phase 6 sorting line)
run/config.env                          → all runtime tunables (renamed from llama-servers.env, pending)
run/daemon.sock                         → Unix socket IPC (Phase 3)
archive/                                → superseded historical docs (AIP_knowledge.md, Mercury borrow plan)
archive/cruft/                          → stale files moved out of repo root (safe to rm -rf)
archive/legacy_profile_files/           → retired style.md content (safe to rm -rf)
```

### Active model decision

| Slot | Locked | Pending |
|---|---|---|
| Family | Qwen3 / Qwen3.6 (under re-eval) | T0.1 outcome |
| Quant | Q5_K_XL (Unsloth Dynamic) if Qwen3.6, else Q5_K_M (bartowski imatrix) for Qwen3-30B-A3B-Instruct-2507 | — |
| File | Pending T0.1 result | — |

### Key URLs

- [Hermes Agent docs root](https://hermes-agent.nousresearch.com/docs/)
- [Hermes Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)
- [Hermes Prompt Assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly)
- [Hermes Provider Runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime)
- [bartowski Qwen3-30B-A3B-Instruct-2507 GGUF](https://huggingface.co/bartowski/Qwen_Qwen3-30B-A3B-Instruct-2507-GGUF)
- [unsloth Qwen3.6-35B-A3B GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF)
- [Qwen3-30B-A3B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507)

### Decision shortcuts (all locked)

- **Frontend:** OpenWebUI (locked 2026-05-14; SillyTavern out of scope)
- **Inference engine:** llama.cpp Vulkan (primary); vLLM via gfx1101 override (fallback if needed)
- **Vector store target:** Qdrant (Phase 2a, replaces ChromaDB)
- **Profile structure:** 2 files using Hermes naming — `SOUL.md` + `.hermes.md` (locked 2026-05-14)
- **Profile location:** `persona/profiles/<name>/` doubles as Hermes `HERMES_HOME`
- **Agent backbone:** Hermes Agent as daemon child (DECISION 2026-05-11)
- **Project license:** AGPLv3 + Section 7 linking exception

</details>

---

<details>
<summary><strong>6. Handoff Changelog</strong> (frozen records, newest first)</summary>

| Date | Document | Summary |
|---|---|---|
| 2026-05-15 | [archive/handoffs/HANDOFF_2026-05-15_0127_compat-reeval-tiered.md](archive/handoffs/HANDOFF_2026-05-15_0127_compat-reeval-tiered.md) | Stack-wide compatibility re-evaluation against Hermes + Qwen3.6 swap. Per-layer findings, meta-finding (Qwen3.6 honors DECISION 2026-05-09 design intent), tiered T0-T4 action plan with acceptance criteria, sequencing rationale, fallback decision branches. |
| 2026-05-11 | [archive/handoffs/HANDOFF_2026-05-10_1738_agent-swarm-hermes-adoption.md](archive/handoffs/HANDOFF_2026-05-10_1738_agent-swarm-hermes-adoption.md) | Adopt Hermes Agent (Nous Research, MIT) as agent-work backbone. Six brainstorm forks resolved. AG2/LangGraph/CrewAI deleted. Network egress risk surface (7 paths + Claude Code creds risk) + safe-config recipe + H1.6 kernel-level containment. H1-H6 sequenced migration plan. |
| 2026-05-09 | [archive/handoffs/HANDOFF_2026-05-09_0250_single-model-migration.md](archive/handoffs/HANDOFF_2026-05-09_0250_single-model-migration.md) | Consolidate from multi-model topology (persona 8080 + reasoning 8081 + planned coder 8082) to single Qwen3-30B-A3B model with parallel slots and mode-switched prompts. M1-M12 sequenced migration. M1 resolution addendum (2026-05-14): bartowski/Qwen3-30B-A3B-Instruct-2507-GGUF Q5_K_M chosen, Path 2 Qwen3.5/3.6 deferred (later promoted to active by 2026-05-15 compat re-eval). |

</details>

---

<details>
<summary><strong>7. Retired Ideas & Software</strong> (what we explicitly left behind, with reasons)</summary>

> Things that were on the table or in the design at some point and have been explicitly deprecated, deleted, or moved out of scope. Captured here so future-you doesn't reconsider something that was already evaluated and dropped.

### Inference & topology

**Multi-model topology** (persona 8080 + reasoning 8081 + planned coder 8082)
- *Retired:* 2026-05-09
- *Reason:* Three model files = 3× ops surface, fault propagation, KV cache competition, and a generation gap as Qwen3-30B-A3B (MoE, 3B active) became the right shape for the EVO-X2's bandwidth-limited unified memory.
- *Replaced by:* Single unified llama-server on port 8080 with `--parallel` slots and mode-switched prompts (DECISION 2026-05-09).
- *Reference:* archive/handoffs/HANDOFF_2026-05-09_0250

**Coder server (port 8082)**
- *Retired:* 2026-05-09 (cancelled before implementation)
- *Reason:* Same model-consolidation rationale; coding tasks now served by Qwen3 (or Qwen3.6) in thinking mode with code-specialist system prompt.
- *Replaced by:* Same single-model dispatch with role-tagged prompts.

**Qwen3-30B-A3B-Instruct-2507** as M1 lock
- *Retired:* 2026-05-15 (pending T0.1 arch test verification)
- *Reason:* The 2507 release split the original Qwen3-30B-A3B's dual-mode model into separate `Instruct-2507` (non-thinking only) and `Thinking-2507` (thinking only) variants. The thinking-mode toggle that justified DECISION 2026-05-09's "single model serves both persona and reasoning" premise was abandoned in this lock.
- *Replaced by:* Qwen3.6-35B-A3B (toggle is back, plus `preserve_thinking` for agent loops, plus better benchmarks). Pending T0.1 empirical validation.
- *Reference:* archive/handoffs/HANDOFF_2026-05-15_0127 "Meta-Finding"

### Agent orchestration

**AG2** (Phase 2.5 scientist↔critic loop, originally Phase 8)
- *Retired:* 2026-05-11
- *Reason:* Hermes' agent loop with subagent delegation handles iterative reasoning natively. Two orchestrators = two failure surfaces, two prompt conventions, two debugging paths. Hybrid case evaluated and rejected — IPC overhead is irrelevant at LLM-call timescales.
- *Replaced by:* Hermes Agent (DECISION 2026-05-11).
- *Reference:* archive/handoffs/HANDOFF_2026-05-10_1738

**AutoGen** (planned fallback for AG2)
- *Retired:* 2026-05-11 (moot)
- *Reason:* AG2 retirement made this fallback meaningless.

**LangGraph** (Phase 8 original agentic layer)
- *Retired:* 2026-05-11 (reshaped into Hermes integration)
- *Reason:* Hermes' delegate_tool fan-out and tool registry cover what LangGraph would have provided.
- *Replaced by:* Hermes Agent (Phase 8 reshapes to Hermes integration via Task Board).

**CrewAI** (Phase 9 candidate — observable multi-agent)
- *Retired:* 2026-05-11
- *Reason:* Hermes' Tenacity Kanban (heartbeat / reclaim / zombie detection / hallucination recovery) covers what CrewAI was wanted for, with deeper integration than the alternative.
- *Replaced by:* Hermes Agent.

**Microsoft Agent Framework**
- *Retired:* before 2026-05-09 (rejected during AIP_knowledge.md era evaluation)
- *Reason:* Cloud-first, Azure-dependent — incompatible with Project_Persona's self-hosted ethos and AGPLv3 design. Never seriously considered after initial evaluation.
- *Reference:* AIP_knowledge.md (archived)

**Mercury (`@cosmicstack/mercury-agent`)** — borrow plan
- *Retired:* 2026-05-11 (silently deprecated by Hermes adoption)
- *Reason:* Mercury was an upstream agent framework whose architectural patterns (Second Brain memory, daemon, blocklist, Telegram integration) were going to be selectively borrowed (B1-B4 specs). Hermes Agent provides equivalent (or better) capability across all of them as a complete drop-in. The April borrow plan (`AIP_HANDOFF_mercury_integration_*`) is obsolete.
- *Replaced by:* Hermes Agent (full backbone, not selective borrow).
- *Reference:* AIP_HANDOFF_mercury_integration_20260427_1545_addendum_2108.md (archived/retired)

### Frontend

**SillyTavern** as primary frontend
- *Retired:* 2026-05-14 (out of scope)
- *Reason:* AIP_knowledge.md had marked SillyTavern as "✅ DECIDED" based on persona/character-card vocabulary alignment, but that decision predated Hermes adoption. With Hermes covering the agent layer + OpenWebUI handling the frontend cleanly + Phase 4 Godot covering embodiment, SillyTavern's specific value collapsed. Could be used for another project.
- *Replaced by:* OpenWebUI as primary frontend (locked).

### Profile structure

**3-file profile** (`persona.md` + `style.md` + `system_rules.md`)
- *Retired:* 2026-05-14
- *Reason:* `style.md` content folded into the personality definition. Two files cover the persona/rules split cleanly with less prompt-token bloat (~6K tokens of static prefix vs ~9K).
- *Replaced by:* 2-file profile.

**`persona.md` filename**
- *Retired:* 2026-05-14
- *Reason:* Defer to Hermes naming convention to eliminate a mapping layer between Project_Persona files and Hermes prompt-assembly file expectations.
- *Replaced by:* `SOUL.md` (Hermes' personality file convention).

**`system_rules.md` filename**
- *Retired:* 2026-05-14
- *Reason:* Same rationale as persona.md rename.
- *Replaced by:* `.hermes.md` (Hermes' highest-priority context file convention with tree-walk discovery and YAML frontmatter support).

**`style.md` profile file**
- *Retired:* 2026-05-14
- *Reason:* Content folded into SOUL.md (personality including style) and .hermes.md (output format rules).

**`AGENTS.md`** as candidate for system_rules.md replacement
- *Retired:* 2026-05-14 (rejected during naming evaluation)
- *Reason:* Lower priority in Hermes' context-file lookup (AGENTS.md is CWD-only, lower priority than `.hermes.md` which walks to git root); no YAML frontmatter support; AGENTS.md is more of a cross-tool convention while `.hermes.md` is Hermes-native.
- *Replaced by:* `.hermes.md` chosen instead.
- *Reference:* archive/handoffs/HANDOFF_2026-05-15_0127 (Hermes adoption work)

### Storage / RAG

**ChromaDB** as RAG vector store
- *Retired:* in progress (planned for Phase 2a migration)
- *Reason:* API stability concerns (broke twice during AIP_ era), Rust performance, built-in debug web UI, native sparse + dense hybrid search. Decision recorded in AIP_knowledge.md, carried forward to knowledge.md.
- *Replaced by:* Qdrant (Apache 2.0).
- *Status:* not yet migrated — Phase 2a work pending.

### Configuration / API

**`PERSONA_URL` / `SCIENTIST_URL`** URL-based dispatch
- *Retired:* in progress (M5 of single-model migration)
- *Reason:* With single unified model serving both persona and reasoning roles via thinking-mode toggle, two URLs collapse to one endpoint with mode parameter in payload.
- *Replaced by:* Single endpoint `http://127.0.0.1:8080/v1` + `enable_thinking` flag.

**`PERSONA_CONCURRENCY=2`** API-side semaphore
- *Retired:* in progress (M5 of single-model migration)
- *Reason:* Gates parallelism upstream of llama.cpp's slot scheduler — wasteful when llama-server's `--parallel N --cont-batching` provides smarter slot management. Should only exist as backpressure above slot count, not as primary parallelism gate.
- *Replaced by:* llama.cpp parallel slots + continuous batching.

**`ASYNC_REASONING_ENABLED`** toggle
- *Retired:* in progress (T3.3 cleanup, post-Hermes adoption)
- *Reason:* Vestigial post-Hermes — all "reasoning" is either trivial in-band or non-trivial via Task Board. The toggle was meaningful when reasoning was a separate URL/model.
- *Replaced by:* `ENABLE_THINKING_FOR_NONTRIVIAL=1` semantic (the new question is "should non-trivial queries use thinking mode," not "should the reasoning expert run").

**scientist→reasoning rename effort**
- *Retired:* 2026-04-27 (per Mercury addendum verification — superseded by single-model migration)
- *Reason:* Live code uses `SCIENTIST` consistently throughout. The single-model migration (M5) collapses URL distinction entirely, making the rename moot. Remaining cosmetic occurrences should adopt "scientist" as canonical.
- *Reference:* AIP_HANDOFF_mercury_integration_*

### Documentation artifacts

**AIP_knowledge.md** as authoritative state document
- *Retired:* 2026-05-14 (superseded; archive recommended)
- *Reason:* Older April snapshot of project state. Has been overridden multiple times in 2026-05 sessions (SillyTavern decision, 3-file profile decision, etc.) and caused confusion when consulted. knowledge.md is the rolling source of truth going forward.
- *Replaced by:* `knowledge.md` (current rolling state).

**`AIP_HANDOFF_mercury_integration_*`** Mercury borrow plan
- *Retired:* 2026-05-11 (silently obsoleted by Hermes adoption; archive recommended)
- *Reason:* The borrow plan was Project_Persona-selective adoption from Mercury (B1 Second Brain memory, B2 daemon, B3 command blocklist, B4 Telegram integration). Hermes Agent now provides all of those as a complete integrated system rather than scattered borrows.
- *Replaced by:* archive/handoffs/HANDOFF_2026-05-10_1738 Hermes adoption.

</details>

---

<details>
<summary><strong>Document Maintenance</strong> (when and how to update)</summary>

This is a **living document**. Update on:
- Status changes (component goes green/red)
- New active work begins or current work completes
- New issues encountered
- Decisions get locked
- New handoff record gets created
- Critical Path changes
- New retired item to capture in Section 7

Do **not** update for minor edits or routine work — that's what `knowledge.md` File Change Tracker is for.

When creating a new dated handoff:
1. Create the dated `HANDOFF_YYYY-MM-DD_HHMM_*.md` (frozen record, never edited after)
2. Update this file's section 6 changelog with one-line summary + link
3. Update sections 1-5 to reflect new state (Critical Path especially)
4. If anything got retired, add to section 7 with the retirement reason
5. Bump Last Updated timestamp at top
6. Regenerate HANDOFF.html: `~/Git/Project_Persona/scripts/regen_handoff_html.sh`

When the source markdown changes, regenerate the HTML view so the browser-friendly artifact stays in sync.

</details>
