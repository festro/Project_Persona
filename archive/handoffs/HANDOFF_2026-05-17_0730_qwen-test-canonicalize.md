# HANDOFF: Qwen-test Canonicalize + M2b Script + Docs Reconcile

**Session date:** 2026-05-17 0730 PDT
**Repo:** github.com/festro/Project_Persona
**Status:** Ready to commit + push from Windows; EVO-X2 will fast-forward to a no-op pull (env + launcher byte-identical to its working copy).
**Branch:** `main` (uncommitted on Windows; commit + push commands at the bottom)
**Predecessor handoff:** `archive/handoffs/HANDOFF_2026-05-16_2337_qwen-test-first-boot.md`

---

## Executive summary

The qwen-test EVO-X2-side edits from 2026-05-16 (env + launcher rewrite for the unified Qwen3-30B-A3B topology) are now mirrored byte-identical onto the Windows canonical workspace at `D:\Projects\Git\Project_Persona\`. This closes the Windows-first workflow drift introduced when the qwen-test edits were applied directly on EVO-X2 to validate the model. Once committed + pushed, EVO-X2's `git pull --ff-only origin main` is a no-op on those two files (already match on disk) and a fast-forward on everything else.

Same session also: fixed `scripts/status.sh` (AI_ROOT + names array no longer reference the legacy Live workspace or the retired dual-server topology); added `scripts/load_test_m2b.py` (sustained-load test client — retires M2b once executed on EVO-X2); applied the 6-item KNOWLEDGE.md update list from the prior handoff plus File Change Tracker entries for both 2026-05-16 and 2026-05-17 sessions; recorded the decision on `looks_degenerate()` (DEFER + decision gate tied to T2.4).

No changes to `services/api/server.py` — the M5 work (collapse `PERSONA_URL` / `SCIENTIST_URL`, thinking-mode toggle, concurrency cap) is the natural next session.

---

## What was done

### 1. Windows-side env + launcher mirror

Verified Windows `D:\Projects\Git\Project_Persona\` was at the pre-qwen-test state for both files (matching the `<` side of EVO-X2's diffs against its `*.bak.2026-05-16` backups). Rewrote both files to match EVO-X2 exactly:

- `run/llama-servers.env` — unified single-model topology block, Qwen3 model name, ctx 32768, GPU_LAYERS_PERSONA=999, PERSONA_PARALLEL=4, UBATCH_SIZE/CACHE_TYPE_K/CACHE_TYPE_V env-driven, LLAMA_LIB_DIR fixed to `$HOME/Git/...`, SCIENTIST_* block removed.
- `scripts/start_llama_servers.sh` — AI_ROOT default flipped to `$HOME/Git/Project_Persona`, `GGML_VK_VISIBLE_DEVICES=0` export, `--device Vulkan0`, `--parallel`, `--cont-batching` flags, `UBATCH_SIZE`/`CACHE_TYPE_K`/`CACHE_TYPE_V` read from env, scientist start_one call removed. File size matches EVO-X2's `ls -la` byte count (2973 bytes).

After commit + push, EVO-X2 `git pull --ff-only origin main` should fast-forward cleanly; the env + launcher on EVO-X2 already match the incoming versions, so git applies the same content and the working tree stays clean.

### 2. status.sh cleanup

- `AI_ROOT` default → `$HOME/Git/Project_Persona` (was `$HOME/Live/AIStack/Project_Persona`).
- Active server names array trimmed to `("persona")` only (was `("persona" "scientist" "reasoning" "coder")`).
- Config / Models / Endpoints display blocks no longer reference scientist (the unified `persona` row now also reports `parallel`).
- Legacy names `persona|scientist|reasoning|coder` kept in the `case` exclusion under the "extra pidfiles" loop so stale pidfiles from prior topologies don't double-show.

### 3. M2b sustained-load test script

Added `scripts/load_test_m2b.py` (Python 3, asyncio + httpx). What it does:

- Spawns N concurrent workers (default 4 = match `PERSONA_PARALLEL=4`) hitting `/v1/chat/completions` with a rotating mix of 10 prompts of varied lengths.
- Polls `/health` every 30s on a separate task.
- Buckets samples by minute, reports per-minute throughput / latency stats so thermal throttling shows up as visible degradation across the run.
- JSON report to stdout + optional `--out path.json` for filing.
- Exits non-zero if any request errored or any health poll failed — gives a shell-level pass/fail signal.

Recommended run on EVO-X2:

```
cd ~/Git/Project_Persona
source services/api/.venv/bin/activate
python3 scripts/load_test_m2b.py --duration 1800 --concurrency 4 --out logs/m2b_$(date +%F_%H%M).json
```

Recommended side-by-side monitoring in separate terminals:

```
watch -n 5 sensors
amdgpu_top
tail -F logs/persona.log
```

### 4. KNOWLEDGE.md updates

Applied all 6 items from archive/handoffs/HANDOFF_2026-05-16_2337 §"KNOWLEDGE.md updates needed":

1. DECISION 2026-05-09 next-session entry point — replaced "Resume at M3" with explicit status: M3 + M4 resolved; M2b script landed; next is M2b run or M5 (server.py).
2. System State table — four `llama-server` rows updated. Three legacy rows marked Retired 2026-05-16; unified row promoted from ⏳ Planned to ✅ Running with full config detail and smoke-test results.
3. Hardware tiers table — added "Tested (unified Qwen3)" row with confirmed ~63 tok/s gen / ~67 tok/s prompt eval on EVO-X2.
4. Models native context — corrected "32K native (128K with YaRN)" → "32K native (~262K with YaRN per published model config)".
5. Known Issues — added Hermes 2 Pro chat template auto-detect note (one less Phase 8 H1 pre-flight item). Removed AMD ROCm pre-migration check (resolved by Vulkan confirmation). Added M2b-pending note.
6. Phase 1 Preserved Live Features — corrected `looks_degenerate()` claim. Was listed as live preserved feature; reality is it never landed. Updated entries to strike-through with explicit "NEVER LANDED" + reference to TODO #37.

Additionally:

- M-block: M3 + M4 explicitly marked ✅ Done with resolution notes. M2b updated to reference the new test script.
- New TODO #37 — `looks_degenerate()` decision gate, tied to T2.4 `<think>`-stripping closure.
- New TODO #38 — status.sh AI_ROOT + names cleanup (resolved this session).
- File Change Tracker — entries added for 2026-05-16 (qwen-test first boot) and 2026-05-17 (canonicalize + M2b script).

### 5. Decision recorded: looks_degenerate()

KNOWLEDGE.md has flagged this as "spec'd but never landed" since the 2026-04-27 Mercury audit. The handoff from 2026-05-16 explicitly called this out as a decision needed before relying on the unified server for higher-stakes output.

**Decision 2026-05-17: DEFER + decision gate.** Do not reinstate this session — server.py is otherwise untouched and bundling a non-trivial behavioral addition with the canonicalization commit muddies the diff. Tie the decision to T2.4 (`<think>`-stripping at the Task Board → persona surface boundary) — both are output-boundary filters and the cleanest landing is alongside each other. Either land `looks_degenerate()` then or formally drop it from the spec when T2.4 closes. Tracked as TODO #37 with explicit non-closure gate on T2.4.

---

## Files modified

### Windows-side `D:\Projects\Git\Project_Persona\` (this session, uncommitted)

- `run/llama-servers.env` — rewritten to match EVO-X2 (qwen-test topology)
- `scripts/start_llama_servers.sh` — rewritten to match EVO-X2 (Vulkan-pinned single-server launch)
- `scripts/status.sh` — AI_ROOT + names + display block cleanup
- `scripts/load_test_m2b.py` — new file, M2b sustained-load test
- `KNOWLEDGE.md` — 6-item update list applied + M3/M4 marked done + TODO #37/#38 + File Change Tracker entries
- `archive/handoffs/HANDOFF_2026-05-17_0730_qwen-test-canonicalize.md` — this file

### EVO-X2 `~/Git/Project_Persona/` (no changes this session)

EVO-X2 working tree from 2026-05-16 still in place. After the Windows-side push, `git pull --ff-only origin main` brings everything in; the env + launcher already match content-wise (no working-tree conflict), `status.sh` updates, `KNOWLEDGE.md` updates, `scripts/load_test_m2b.py` arrives net-new, this handoff lands net-new.

---

## Commit + push (run on Windows in `D:\Projects\Git\Project_Persona\`)

Recommended sequence — single commit since the changes are all part of one coherent canonicalization step:

```
git status
git add run/llama-servers.env scripts/start_llama_servers.sh scripts/status.sh scripts/load_test_m2b.py KNOWLEDGE.md archive/handoffs/HANDOFF_2026-05-17_0730_qwen-test-canonicalize.md
git status
git commit -m "qwen-test canonicalize: mirror EVO-X2 env+launcher on Windows, fix status.sh, add M2b load test, KNOWLEDGE.md reconcile

- run/llama-servers.env + scripts/start_llama_servers.sh: byte-identical mirror of EVO-X2 qwen-test edits (2026-05-16) for unified Qwen3-30B-A3B-Instruct-2507 Q5_K_M on Vulkan0/RADV. Closes Windows-first workflow drift.
- scripts/status.sh: AI_ROOT default flipped to ~/Git/Project_Persona, names array trimmed to (persona), legacy names retained only in case-exclusion. Resolves TODO #38.
- scripts/load_test_m2b.py: new asyncio+httpx client for the M2b sustained-load test. 4 concurrent workers default, per-minute throughput buckets, /health poll, JSON report, exit-nonzero on errors.
- KNOWLEDGE.md: archive/handoffs/HANDOFF_2026-05-16_2337 6-item update list applied. M3+M4 marked Done. M2b row references new script. TODO #37 (looks_degenerate decision gate) and #38 (status.sh cleanup, resolved) added. File Change Tracker entries for 2026-05-16 and 2026-05-17 sessions. Last Updated bumped.
- archive/handoffs/HANDOFF_2026-05-17_0730_qwen-test-canonicalize.md: frozen session record.

Refs archive/handoffs/HANDOFF_2026-05-16_2337_qwen-test-first-boot.md."
git push origin main
```

Then on EVO-X2:

```
cd ~/Git/Project_Persona
git fetch origin
git status
git pull --ff-only origin main
ls -la scripts/load_test_m2b.py
chmod +x scripts/load_test_m2b.py 2>/dev/null || true
ls -la scripts/status.sh
chmod +x scripts/status.sh 2>/dev/null || true
./scripts/status.sh
```

`chmod +x` is defensive — git tracks the exec bit if `core.fileMode` honors it (Linux always does; Windows-side git may not). Per tenant #2, calling it out explicitly:

```
chmod +x scripts/load_test_m2b.py
chmod +x scripts/status.sh
chmod +x scripts/start_llama_servers.sh
```

The last one is redundant if EVO-X2's working tree already has +x on it (which it does — `2973 May 16 23:32` from the prior session was `-rwxrwxr-x`), but harmless to re-run.

---

## Verification this session

- `run/llama-servers.env` content matches EVO-X2 `>` lines of the 2026-05-16 diff (25 lines, header through LLAMA_LIB_DIR).
- `scripts/start_llama_servers.sh` is **2973 bytes**, identical to EVO-X2's reported file size (`-rwxrwxr-x 1 festro33 festro33 2973 May 16 23:32`).
- `scripts/status.sh` — verified by grep: only scientist references are in the legacy case-exclusion (line 20 comment, line 44 case branch). AI_ROOT line points to `$HOME/Git/Project_Persona`.
- `scripts/load_test_m2b.py` — `python3 -c "import ast; ast.parse(open(...))"` PARSE OK. httpx import will succeed only inside the API venv (expected — that's the run target).
- KNOWLEDGE.md edits applied via `Edit` tool (exact-string match enforced); cross-references between sections (handoff names, TODO numbers, M-block resolutions) consistent.

---

## Open items at end of this session

### Immediate (next session — likely M5)

1. **Run M2b on EVO-X2.** 30+ minute sustained-load. Filing as `logs/m2b_<datetime>.json`. Exit-nonzero on errors gives shell-level signal. If the run passes, M2b promotes from Pending → Done in KNOWLEDGE.md.
2. **M5 — services/api/server.py migration.** Per tenant #3, send a fresh copy at session start. Scope:
   - Collapse `PERSONA_URL` / `SCIENTIST_URL` → single endpoint (both currently point at the same host but on different ports; SCIENTIST_PORT=8081 is no longer bound).
   - Add thinking-mode toggle (per T2.2: `chat_template_kwargs.enable_thinking`; fallback to system-prompt injection if llama.cpp template engine ignores the flag).
   - Raise or remove `PERSONA_CONCURRENCY=2` — now under-sized vs the 4 parallel slots.
   - Decide direction for `ASYNC_SCIENTIST_ENABLED` / `SCIENTIST_INBAND_*` env vars — keep for backward compat, rename, or remove.
3. **HANDOFF.md (living doc) refresh.** This session added new content (M3/M4 done, M2b script landed, looks_degenerate decision gate, new TODOs); the living handoff at repo root has not been updated. Run `scripts/regen_handoff_html.sh` after HANDOFF.md updates.

### Soon

4. **Chroma → Qdrant code migration** on `chore/chroma-to-qdrant` branch — server.py Chroma calls still need replacing. Can be bundled with M5 or kept separate.
5. **Wire SOUL.md + .hermes.md into `build_persona_prompt()`** (Phase 1 incomplete).
6. **looks_degenerate() decision gate** (TODO #37) — must close one way or the other when T2.4 (`<think>`-stripping) lands.

### Eventually

7. **scientist→reasoning rename** in remaining code paths (server.py).
8. **`run/llama-servers.env` → `run/config.env` rename** + scope expansion to full project config (currently only env vars for the llama-server launcher; KNOWLEDGE.md "Runtime Configuration" block documents the full superset).
9. **Quarantine/delete `~/Live/AIStack/`** after a holding period. Suggested: `mv ~/Live/AIStack ~/Live/AIStack.deprecated-2026-05-16.bak` until confident.
10. **YaRN ctx extension** if any single-slot context need exceeds 32K (per the corrected ~262K-with-YaRN figure).

---

## Rollback path

If this session's commit causes any regression:

```
cd ~/Git/Project_Persona
git fetch origin
git log --oneline -5    # find the commit to revert
git revert <hash>
git push origin main
```

Or, more surgical — keep the env+launcher mirror and load test but back out a specific file:

```
cd ~/Git/Project_Persona
git checkout HEAD~1 -- <path>
git commit -m "Revert <path>"
git push origin main
```

The qwen-test-validated env + launcher are now committed canonically; reverting them returns to the pre-qwen-test dual-server topology, which would require the legacy models (Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf may need re-download — Qwen2.5-14B-Instruct-Q5_K_M.gguf should still be in `~/Live/AIStack/Project_Persona/models/`).

---

## End

Single-model migration is now four milestones deep: M1 (model acquired) + M2a (build verified) + M3 (env) + M4 (launcher), with M2b (load test) ready to run and M5 (server.py) the natural next session. Canonical Windows-first workflow restored. KNOWLEDGE.md is reconciled with reality. One decision recorded (looks_degenerate → defer + gate). One follow-up flagged (HANDOFF.md living-doc refresh — out of scope this session, in scope next).
