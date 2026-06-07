# HANDOFF: Qwen3-30B-A3B Single-Model First Boot — qwen-test Validated

**Session date:** 2026-05-16 2337 PDT
**Repo:** github.com/festro/Project_Persona
**Status:** ✅ MILESTONE COMPLETE — single-model topology functionally validated end-to-end
**Branch:** `main` (commit `57dad37` from this session's Windows push, plus EVO-X2-side env+launcher edits not yet committed)
**Parallel branch:** `chore/chroma-to-qdrant` parked on GitHub at commit `ec2c730` (Qdrant migration WIP, do not merge until server.py code migration lands)

---

## Executive summary

The single-model migration (DECISION 2026-05-09) reached its first validation milestone. Unified `llama-server` running **Qwen3-30B-A3B-Instruct-2507 Q5_K_M** is now serving OpenAI-compatible `/v1/chat/completions` on EVO-X2 at `127.0.0.1:8080` via Vulkan/RADV backend, with 4 parallel slots, q8_0 KV cache, Flash Attention enabled, and full 49/49 layer GPU offload. End-to-end smoke test returned a clean response at ~63 tok/s generation throughput. No `<think>`-tag bleed.

Path to this milestone consumed significant session time on repo-state reconciliation because of accumulated drift between the design spec (KNOWLEDGE.md), three distinct working copies of the project (Windows D:\Projects\Git, EVO-X2 ~/Live, EVO-X2 ~/Git), and the GitHub origin. All of that is now resolved.

---

## What was done (chronological)

### 1. Initial intent: M3 + launcher boot for qwen test

Picked up at the knowledge.md "Next-session entry point": resume at M3 (update `run/config.env`, scale `--ctx-size` to slot count, drop reasoning/coder sections). Per tenant #3, requested fresh copies of `run/config.env`, `start_llama_servers.sh`, `services/api/server.py` before any edits.

User uploaded `start_llama_servers.sh` and `status.sh`, noted there was no `run/config.env`. Investigation showed the file was still named `run/llama-servers.env` — the planned rename hadn't happened. First drift discovery.

### 2. Knowledge.md drift discoveries (catalogued during audit)

- **`config.env` rename**: planned in knowledge.md, not executed. File still named `llama-servers.env`. (Now whitelisted under both names in the new `.gitignore`.)
- **scientist→reasoning rename**: planned in knowledge.md Phase 1 list, not executed. Server still named `scientist`, port still 8083 (knowledge.md said 8081).
- **M1 status (Qwen3 download)**: knowledge.md said resolved 2026-05-14. Actual file was missing on EVO-X2; download was redone this session via `huggingface-cli` to the Live directory, then later moved to `~/Git/Project_Persona/models/`.
- **EVO-X2 deployment directory**: I initially audited `~/Live/AIStack/Project_Persona/` based on user-supplied paths. User clarified the canonical deployment is `~/Git/Project_Persona/`; `~/Live/AIStack/` is a legacy/divergent workspace (has its own broken AIStack-level `.git` and accidentally-tracked AI_TWIN submodule reference). Re-audited at the correct path.

### 3. Three-state repo reconciliation

Established that **canonical workflow is**: edit on Windows at `D:\Projects\Git\Project_Persona`, push to GitHub, pull on EVO-X2 at `~/Git/Project_Persona`. Confirmed:

- **EVO-X2 `~/Git/Project_Persona`**: clean working copy, was synced with GitHub origin/main at `af0db13` ("Sync Live -> Git: port server.py, env, scripts; sterilize template", tag `v1.2-live-sync`, 2026-04-27).
- **EVO-X2 `~/Live/AIStack/`**: legacy/divergent workspace. **Not** part of canonical workflow. Quarantine candidate; was the source of much initial confusion.
- **Windows D:\Projects\Git\Project_Persona**: substantial uncommitted work — Hermes adoption docs, Qwen3 design pivot, handoff convention rollout (dated HHMM, downloadable, HTML companion), profile scaffold 3-file → 2-file rename (SOUL.md + .hermes.md per 2026-05-14 lock), Chroma → Qdrant dependency migration (incomplete — `requirements.txt` updated but `server.py` Chroma calls not yet replaced).
- **GitHub origin**: had grown since the last Windows fetch; Windows was 1 commit behind on `origin/main`.

### 4. Windows-side commit + push (3 commits across 2 branches)

Sequence executed (Phases 0-9):

- **Phase 0**: pre-flight `git status -sb` + `git fetch origin` — confirmed Windows 1 behind.
- **Phase 1**: `git stash push --include-untracked` — preserved working tree (modifications + deletions + untracked items, except `archive/cruft/` which was respected by the modified .gitignore being active at stash time).
- **Phase 2**: `git pull --ff-only origin main` — fast-forwarded to `af0db13`.
- **Phase 3**: `git stash pop` — conflicts on `.gitignore` (UU) and `AIP_knowledge.md` (UD modify/delete). Resolved by `git checkout --theirs .gitignore` (stash version was a strict superset of af0db13's), `git rm AIP_knowledge.md` (we wanted it deleted; content merged into KNOWLEDGE.md). Auto-merges of KNOWLEDGE.md and server.py held cleanly with all changes preserved (verified by grep).
- **Phase 4** (took two attempts): created `chore/chroma-to-qdrant` branch. **First attempt** captured 14 files due to all previously-staged Phase 3 changes carrying over to the new branch. **Recovery**: `git reset --mixed HEAD~1`, surgical re-staging of only `services/api/requirements.txt` and `services/api/server.py`, re-committed. Resulting commit `ec2c730` is the clean 2-file Qdrant WIP.
- **Phase 5** (Commit B): `refactor(persona): profile scaffold 3-file -> 2-file (SOUL.md + .hermes.md)` — commit `3910a37`. Note: git auto-rename detection scrambled the labels for the `test/` profile because those files were 0 bytes (any two empty files match 100%); actual file contents on disk are correct.
- **Phase 6** (Commit C): `docs: consolidate KNOWLEDGE.md, add dated handoffs + html renderer, refresh READMEs, expand .gitignore` — initial commit hit a bash history-expansion bug (`!run/config.env` in a double-quoted commit message triggered `event not found`, truncating the message body). Recovered with `git commit --amend -m '...'` using single quotes. Resulting commit `57dad37`.
- **Phase 7**: pushed both branches. `origin/main` advanced `af0db13` → `57dad37`. New remote branch `origin/chore/chroma-to-qdrant` at `ec2c730`.

### 5. EVO-X2 sync + Qwen3 model relocation

- `git pull --ff-only origin main` on `~/Git/Project_Persona` — fast-forwarded to `57dad37`, 20 files changed, brought in handoffs, KNOWLEDGE.md expansion, profile rename, expanded .gitignore.
- `mv ~/Live/AIStack/Project_Persona/models/Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf ~/Git/Project_Persona/models/` — instant (same filesystem, inode update). File at `~/Git/Project_Persona/models/Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf`, 21744455680 bytes (20.25 GiB).
- Re-audited `~/Git/Project_Persona`. Confirmed Windows-side did NOT modify `run/llama-servers.env` or `scripts/start_llama_servers.sh` — qwen-test edits are net-new.

### 6. Vulkan device pinning verification

`vulkaninfo --summary` confirmed:
- **GPU0**: AMD Radeon Graphics (RADV GFX1151), `DRIVER_ID_MESA_RADV`, integrated — the target
- **GPU1**: llvmpipe (LLVM 20.1.2), `DRIVER_ID_MESA_LLVMPIPE`, CPU software fallback — catastrophically slow if accidentally picked

Pinned via `export GGML_VK_VISIBLE_DEVICES=0` + `--device Vulkan0` in launcher (belt-and-suspenders).

### 7. Qwen-test edits applied via heredoc

Two files modified on EVO-X2 (backups taken first: `run/llama-servers.env.bak.2026-05-16`, `scripts/start_llama_servers.sh.bak.2026-05-16`). Stale pidfiles from Apr 1 cleaned (`run/api.pid`, `run/persona.pid`, `run/scientist.pid`).

**`run/llama-servers.env`** (rewritten — see file for full content; key changes):
- `PERSONA_MODEL=Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf` (was Meta-Llama-3.1-8B-Instruct-Q4_K_M)
- `PERSONA_CTX=32768` (was 8192) — native Qwen3 context
- `GPU_LAYERS_PERSONA=999` (was 35) — full offload
- Added `PERSONA_PARALLEL=4` — slot count
- Added `UBATCH_SIZE`, `CACHE_TYPE_K`, `CACHE_TYPE_V` env-driven (were hardcoded in launcher)
- Dropped entire `SCIENTIST_*` block
- Fixed `LLAMA_LIB_DIR` to point at `~/Git/...` (was `~/Live/AIStack/...`)

**`scripts/start_llama_servers.sh`** (rewritten — see file for full content; key changes):
- `AI_ROOT` default → `$HOME/Git/Project_Persona` (was `$HOME/Live/AIStack/Project_Persona`)
- Single `start_one "persona" ...` call (was persona + scientist)
- Added `export GGML_VK_VISIBLE_DEVICES=0`
- Added `--device Vulkan0`, `--parallel "$parallel"`, `--cont-batching` flags
- `--ubatch-size`, `--cache-type-k`, `--cache-type-v` now read from env vars
- chmod +x preserved post-heredoc (per tenant #2)

### 8. Dry-run + actual launch + smoke test

- `./scripts/start_llama_servers.sh --dry-run` returned correct invocation summary (model path, ctx, parallel, GPU layers, batch, cache types, vulkan_device all correct).
- `./scripts/start_llama_servers.sh` (actual) launched cleanly. Log confirmed:
  - `offloaded 49/49 layers to GPU`
  - `Vulkan0 model buffer size = 20527.42 MiB`
  - `n_seq_max = 4`, `n_ctx = 32768`, `n_ctx_seq = 8192` per slot
  - `KV buffer size = 1632.00 MiB`, K/V both q8_0 (816 MiB each)
  - `Flash Attention was auto, set to enabled`
  - 4 slots initialized
  - `main: model loaded`, `main: server is listening on http://127.0.0.1:8080`
  - PID 2161613 alive
- Smoke test: `curl http://127.0.0.1:8080/v1/chat/completions` with simple prompt returned `{"content":"I am working."}`, `finish_reason: "stop"`, 5 tokens in 79ms = **63 tok/s generation**, prompt eval 67 tok/s. No `<think>` tag bleed. Chat format auto-detected as `Hermes 2 Pro`.

---

## Verified outcomes

| Item | Status | Detail |
|---|---|---|
| Model file on disk | ✅ | `~/Git/Project_Persona/models/Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf`, 20.25 GiB |
| llama.cpp build | ✅ | b8157-2943210c1, Vulkan backend, KHR_coopmat present, bf16=0 |
| Full GPU offload | ✅ | 49/49 layers on Vulkan0 (RADV GFX1151) |
| Vulkan device pinning | ✅ | GGML_VK_VISIBLE_DEVICES=0 + --device Vulkan0 — llvmpipe excluded |
| KV cache | ✅ | 1632 MiB, q8_0/q8_0, on GPU |
| Parallel slots | ✅ | 4 slots × 8192 ctx each (32K total) |
| Flash Attention | ✅ | Auto-enabled |
| Chat template | ✅ | Hermes 2 Pro auto-detected (ChatML superset, tool-calling compatible) |
| /health | ✅ | Returns `{"status":"ok"}` |
| /v1/chat/completions | ✅ | Returns valid OpenAI-format JSON |
| Generation throughput | ✅ | 63 tok/s (Q5_K_M MoE 30B/3B-active on Strix Halo iGPU) |
| Prompt eval throughput | ✅ | 67 tok/s |
| `<think>` bleed | ✅ | None — thinking mode off by default |

---

## Decisions made this session

- **Sweep scope** (after audit revealed three divergent project copies): "audit first, decide after" → ultimately "minimal in-place edits on EVO-X2 against the synced canonical state". No full sweep. Legacy `~/Live/AIStack/` workspace quarantined (left in place but ignored going forward).
- **Qdrant migration**: parked on feature branch `chore/chroma-to-qdrant`, NOT merged to main. Reason: `requirements.txt` switches deps but `server.py` Chroma calls aren't yet migrated — pip install would break the API. Resume on the branch when ready.
- **Profile scaffold rename**: committed (3910a37) per the 2026-05-14 lock — `SOUL.md` + `.hermes.md` replace `persona.md` + `style.md` + `system_rules.md`. Old files preserved under `archive/legacy_profile_files/` for reference.
- **Env file naming**: kept `run/llama-servers.env` (did NOT rename to `config.env`). Per "minimal scope" decision — defer rename + scope expansion to a dedicated session. Both names are gitignore-whitelisted in the new `.gitignore` for transition.
- **scientist→reasoning rename**: deferred. Server is now named `persona` (unified), but the rename of the old `scientist` reference in `status.sh` was skipped per minimal scope. `status.sh` still hardcodes `names=("persona" "scientist" "reasoning" "coder")`; redundant but harmless now that stale `scientist.pid` is cleaned.
- **Parallel slot count**: 4. Rationale: 1 for main convo + 3 for Hermes fan-out headroom. Easy to tune later via env file without launcher changes.
- **PERSONA_CTX**: 32768 (4 × 8192 per slot). Within Qwen3 native context, no YaRN needed. See follow-ups for when YaRN matters.

---

## Drift discovered (and either fixed or noted for next sweep)

### Fixed this session
- M1 status (model file missing — re-downloaded)
- EVO-X2 audit target (was wrong workspace; moved to `~/Git/`)
- Stale pidfiles from Apr 1 (cleaned)
- `AI_ROOT` default pointing at `~/Live/...` in launcher (fixed to `~/Git/...`)
- `LLAMA_LIB_DIR` in env pointing at `~/Live/...` (fixed to `~/Git/...`)
- 14 tracked-but-deleted files cleanup (committed deletions as part of Windows push)
- AI_TWIN accidental submodule reference at `~/Live/AIStack/.git` (no longer relevant — Live workspace abandoned)

### Noted for next session(s)
- **config.env rename** still pending — env file is still named `llama-servers.env`
- **scientist→reasoning rename** still pending in `status.sh`, `services/api/server.py` (`SCIENTIST_URL` references), and elsewhere
- **Chroma → Qdrant code migration** in `server.py` still pending — parked on `chore/chroma-to-qdrant` branch
- **KNOWLEDGE.md** internal claims need reconciliation:
  - System State table says "scientist port 8081" — actual was 8083, now n/a
  - Component: ChromaDB / RAG Layer — needs Qdrant migration note
  - M2b (sustained-load test) still "deferred" — should be promoted to a real test now that the model boots
  - YaRN extended ctx — currently says "128K with YaRN", actually 256K per model card
  - Reasoning quality guard (`looks_degenerate`) is still ❌ NOT present in live server.py — decision needed before any production-ish use
- **`status.sh` AI_ROOT** still defaults to `~/Live/AIStack/...` — read-only for qwen test, but should be fixed before relying on `status.sh` for monitoring the new `~/Git/...` deployment

---

## Files modified

### On EVO-X2 `~/Git/Project_Persona/` (NOT YET COMMITTED — see follow-ups)
- `run/llama-servers.env` — rewritten for unified Qwen3 topology (backup: `run/llama-servers.env.bak.2026-05-16`)
- `scripts/start_llama_servers.sh` — rewritten for unified launch with Vulkan device pinning (backup: `scripts/start_llama_servers.sh.bak.2026-05-16`)
- `run/persona.pid` — created by launcher (gitignored — `run/*.pid`)
- `logs/persona.log` — written by launcher (gitignored — `logs/`)

### On EVO-X2 `~/Git/Project_Persona/` (PULLED FROM ORIGIN — committed via Windows push)
- 20 files updated by `git pull` from origin/main `57dad37`

### On GitHub origin (PUSHED THIS SESSION FROM WINDOWS)
- `main`: `af0db13` → `3910a37` → `57dad37` (2 commits added)
- `chore/chroma-to-qdrant`: new branch at `ec2c730` (1 commit)

---

## KNOWLEDGE.md updates needed

To apply on Windows at `D:\Projects\Git\Project_Persona\KNOWLEDGE.md` in a future session (do NOT edit on EVO-X2 — preserve canonical workflow). Suggested changes:

1. **Next-session entry point** (top of file or in DECISION 2026-05-09 block):
   - Was: "Resume at M3 — update `run/config.env` for single-model topology"
   - Update to: "M3-M7 complete (env, launcher, Vulkan pinning, dry-run, launch, smoke test all PASS). Resume at decision point: commit env+launcher edits to EVO-X2 and push to GitHub, OR redo edits canonically on Windows and pull. See archive/handoffs/HANDOFF_2026-05-16_2337_qwen-test-first-boot.md."

2. **System State table**:
   - `llama-server (persona) port 8080` row: change status from `✅ Running — TO BE RETIRED` to `✅ Running — UNIFIED (Qwen3-30B-A3B-Q5_K_M, 4 parallel slots, 32K ctx, Flash Attention)`
   - `llama-server (reasoning) port 8081` row: change to `❌ Retired — superseded by unified Qwen3 (this session 2026-05-16)`
   - `llama-server (coder) port 8082` row: already shows cancelled; no change
   - `llama-server (unified) port 8080` row: change from `⏳ Planned` to `✅ Running` and link to this handoff

3. **Models section, Hardware tiers table**: add a confirmed throughput entry for EVO-X2 at Q5_K_M: ~63 tok/s gen, ~67 tok/s prompt eval on Strix Halo iGPU via Vulkan/RADV.

4. **Models section, native context note**: correct from "32K native (128K with YaRN)" to "32K native (262K with YaRN per Qwen team's published config)".

5. **Known Issues / Caveats**:
   - Add: "Chat template auto-detected as Hermes 2 Pro (ChatML superset with tool-calling). This is the expected format for Qwen3 and ready for Hermes Agent integration in Phase 8 — no chat template work needed."
   - Add: "`status.sh` still hardcodes `AI_ROOT=$HOME/Live/AIStack/...` and `names=('persona' 'scientist' 'reasoning' 'coder')` — needs update to `~/Git/...` path before relying on it; minor since stale pidfiles cleaned this session."
   - Remove: M1 caveat about model file missing
   - Remove: "Reasoning fallback to persona" if no longer relevant under single-model topology (worth checking — server.py logic may still reference REASONING_URL)

6. **Hermes adoption Phase 8 prep**: note that chat template = Hermes 2 Pro is already in place — one less thing to worry about for the H1 pre-flight checklist.

---

## Open follow-ups (priority-ordered)

### Immediate (next session)
1. **Decision: where to commit env+launcher edits.** Two options:
   - (a) Commit on EVO-X2, push from there. Bypasses Windows-first workflow but keeps the working test stable.
   - (b) Mirror the edits on Windows D:\Projects\Git, commit there, push, then re-pull on EVO-X2 (which would no-op since files would match). Preserves canonical workflow.
   - **Recommendation**: option (b) for workflow consistency.
2. **Apply KNOWLEDGE.md updates** (section above) on Windows.
3. **Update knowledge.md M1 entry** to reflect actual download path/date (May 16 to `~/Git/Project_Persona/models/`).

### Soon
4. **Sustained-load test (M2b)** — was deferred from initial M2a. Now that the model boots, run a longer / multi-slot test to verify Vulkan stability under load.
5. **Reasoning quality guard decision** — `looks_degenerate()` was spec'd but never landed. Decide: reinstate (recommended) or accept absence and remove the spec reference.
6. **Wire SOUL.md + .hermes.md into `build_persona_prompt()`** (Phase 1 incomplete item).
7. **Wire per-profile Chroma** (or transition this work into the Qdrant migration on the feature branch).

### Eventually
8. **scientist→reasoning rename** across `status.sh`, any remaining `services/api/server.py` references.
9. **`run/llama-servers.env` → `run/config.env` rename** + scope expansion (full project config, not just llama-server).
10. **Complete Chroma → Qdrant migration** on `chore/chroma-to-qdrant` branch — server.py Chroma calls need replacing with Qdrant client calls. Then merge.
11. **YaRN ctx extension** if any single-slot context need exceeds 32K (rare for now; relevant when long document ingestion via Phase 6 sorting line lands).
12. **Quarantine/delete `~/Live/AIStack/`** once confident nothing's needed from it. Suggested: `mv ~/Live/AIStack ~/Live/AIStack.deprecated-2026-05-16.bak` for a holding period before deletion.

---

## Rollback path

If the unified Qwen3 setup misbehaves and you need to revert:

```
cd ~/Git/Project_Persona
./scripts/stop_llama_servers.sh
cp run/llama-servers.env.bak.2026-05-16 run/llama-servers.env
cp scripts/start_llama_servers.sh.bak.2026-05-16 scripts/start_llama_servers.sh
chmod +x scripts/start_llama_servers.sh
```

That restores the dual-model (persona + scientist) configuration. You'd also need:
- The old models present in `models/`: Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf, Qwen2.5-14B-Instruct-Q5_K_M.gguf (the Qwen2.5 should still be in `~/Live/AIStack/...models/`; Llama 3.1 may need re-download)
- The launcher's old hardcoded path defaults to `~/Live/AIStack/...` for AI_ROOT — would still try to read from there. Override with `AI_ROOT=$HOME/Git/Project_Persona ./scripts/start_llama_servers.sh`.

Cleanest revert is at the git level once the new env/launcher are committed — `git revert` the env+launcher commits and you're back to af0db13's state.

---

## Network egress posture (relevant to Hermes integration)

No changes to network egress this session. Hermes integration (Phase 8) work hasn't begun. Existing egress notes from archive/handoffs/HANDOFF_2026-05-10_1738 still apply unchanged. When that work resumes, add:
- Project Nomad on NAS as a new LAN egress point (Hermes MCP shim target for offline knowledge — Kiwix HTTP via Nomad)
- AIT_ co-tenant on same EVO-X2 (no shared infrastructure but shared unified memory budget — relevant when both stacks run hot simultaneously)

---

## End

Qwen test PASSED. Next session can either (a) consolidate the env+launcher edits into the canonical Windows-side workflow and push, then move on to the sustained-load test (M2b), or (b) push directly from EVO-X2 if you prefer faster iteration. Knowledge.md updates listed above should land in the same window.
