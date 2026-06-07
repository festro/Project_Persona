# HANDOFF: M5 — services/api/server.py Single-Model Migration

**Session date:** 2026-05-17 1030 PDT
**Repo:** github.com/festro/Project_Persona
**Status:** Edits applied to Windows-side server.py. PARSE OK. Live smoke test on EVO-X2 still pending.
**Branch:** `main` (uncommitted on Windows; stacks on top of the 1430 canonicalize work which is also uncommitted)
**Predecessor handoff:** `archive/handoffs/HANDOFF_2026-05-17_0730_qwen-test-canonicalize.md`

---

## Executive summary

M5 of the single-model migration (DECISION 2026-05-09) is complete on disk. `services/api/server.py` has been rewritten to remove the dual-server URL split, expose the new Qwen3 thinking-mode toggle at the prompt layer, and resize the API-side concurrency cap to match the four parallel slots the unified llama-server now serves.

Three decisions were locked at session start before edits began:

1. **Thinking mode via prompt-level `/think` and `/no_think` directives** rather than `chat_template_kwargs` — keeps the existing `/completion` + raw-prompt architecture intact. T2.2 may revisit if/when query_llama migrates to messages format.
2. **SCIENTIST_* → REASONING_* rename with back-compat env-var fallback** — the in-band expert-notes feature is preserved and useful (a structured prompt template is a different prompt, not a different model), repointed to PERSONA_URL.
3. **PERSONA_CONCURRENCY default raised 2 → 4** to match `PERSONA_PARALLEL=4`, and the gate added to `/v1/chat/completions` for invariant consistency with `/chat`. Env-driven so it remains tunable.

Server.py parses cleanly. End-to-end live test against the EVO-X2 llama-server is the natural next-session step.

---

## What changed in server.py

### Config block (lines 40-130)

Removed:

- `SCIENTIST_PORT = int(os.getenv("SCIENTIST_PORT", "8081"))`
- `SCIENTIST_URL = f"http://{LLAMA_HOST}:{SCIENTIST_PORT}/completion"`

Added:

- `ASYNC_REASONING_ENABLED` — replaces `ASYNC_SCIENTIST_ENABLED`; back-compat shim reads the old name if the new one isn't set.
- `REASONING_INBAND_ENABLED` / `REASONING_INBAND_TOPICS` / `REASONING_INBAND_MAX_TOKENS` / `REASONING_INBAND_TIMEOUT_S` — replace `SCIENTIST_INBAND_*` with the same back-compat fallback pattern.
- `THINKING_MODE_DEFAULT` — `"auto" | "on" | "off"` (default `"auto"`).
- `THINKING_MODE_TOPICS` — set of topics that auto-trigger `/think` when `THINKING_MODE_DEFAULT=auto` (default `science,biology,coding,math,research`).

### thinking_prefix() helper (new)

```python
def thinking_prefix(topic: str, mode: Optional[str] = None) -> str
```

Returns `"/think\n"` or `"/no_think\n"`. Called at prompt-build time. Per-call `mode` overrides the global default. Used by `build_persona_prompt()` and surfaced in `/chat` debug output as `thinking_mode_resolved`.

### build_persona_prompt() signature change

Old:

```python
def build_persona_prompt(user_text, rag_docs, *, profile, topic, scientist_notes="")
```

New:

```python
def build_persona_prompt(user_text, rag_docs, *, profile, topic, reasoning_notes="", thinking_mode=None)
```

Behavioral changes: prepends the `thinking_prefix(topic, thinking_mode)` directive to the assembled prompt before the persona prefix. All other prompt structure preserved.

### reasoning_template() / reasoning_notes_inband() (renamed from scientist_*)

The expert-notes prompt template (TL;DR / Key points / Risks / How to verify / Next actions) is unchanged in content. The internal description was generalized from "Scientist" to "careful research + reasoning assistant". The async function now POSTs to `PERSONA_URL` (was `SCIENTIST_URL`).

### Concurrency

- `PERSONA_CONCURRENCY` default: `2` → `4`.
- `persona_sem = asyncio.Semaphore(PERSONA_CONCURRENCY)` now also wraps the `/v1/chat/completions` route (previously only `/chat`).

### /health endpoint

Removed: `scientist_endpoint`, `async_scientist_enabled`.

Added: `unified_endpoint`, `async_reasoning_enabled`, `reasoning_inband_enabled`, `reasoning_inband_topics`, `thinking_mode_default`, `thinking_mode_topics`.

Existing fields preserved (rag, embedder, chroma, persona_concurrency, profile_wrappers, persona_writeback, memory_distill, chat_log_writeback, rag_kinds_for_chat, rag_kinds_for_science).

### /chat debug

Renamed `scientist_inband_used` → `reasoning_inband_used`, `scientist_inband_stats` → `reasoning_inband_stats`. New field: `thinking_mode_resolved` (the actual `/think` or `/no_think` string used for this request).

### Persona file loader — switched to 2-file Hermes naming (added mid-session)

The 2026-05-14 lock retired `style.md` entirely and renamed `persona.md` → `SOUL.md` / `system_rules.md` → `.hermes.md`. The on-disk profile content was renamed during the 2026-05-15 consolidation batch, but the loader in server.py kept reading the legacy filenames — so `ensure_profile_files()` was auto-creating empty `persona.md` / `style.md` / `system_rules.md` next to the real `SOUL.md` / `.hermes.md`, and the prompt builder was reading those empty placeholders. This is a latent correctness bug in the API.

Fixed in the same session:

- `ensure_profile_files()` now scaffolds only `SOUL.md` and `.hermes.md`. Docstring explicitly notes the retirement of the three legacy files.
- `load_profile_wrappers()` returns the 2-tuple `(soul_md, hermes_md)` instead of the 3-tuple.
- `build_persona_prompt()` prompt prefix uses "Soul (identity, personality, communication style — follow):" and "Hermes rules (hard rules + output format — must follow):" sections. The Style guide block is dropped entirely; communication-style content lives inside `SOUL.md` per the 2026-05-14 spec.

Closes TODO #3 and the Phase 1 "Wire SOUL.md + .hermes.md into build_persona_prompt()" incomplete item.

---

## What was NOT changed (out of M5 scope)

- **Chroma → Qdrant.** Parked on `chore/chroma-to-qdrant` branch.
- **`<think>`-tag stripping.** Deferred to T2.4 per KNOWLEDGE.md compatibility re-eval. M8 row marked superseded.
- **`looks_degenerate()` quality guard.** Per decision 2026-05-17 (prior handoff): defer + gate tied to T2.4.
- **`/agent/run`** — unchanged. Local taskman2 bridge stays as-is.
- **`scripts/unified_test.sh`** — still references the dual-server topology; flagged for a future cleanup pass.
- **`run/llama-servers.env` rename to `run/config.env`** — TODO #2, deferred.

---

## Verification this session

- Python AST parse: PASS.
- Endpoint presence (per `python3 ast` audit): `v1_chat_completions`, `v1_models`, `chat_submit`, `get_job`, `_messages_to_text`, `thinking_prefix`, `reasoning_template`, `reasoning_notes_inband` all present.
- `PERSONA_CONCURRENCY = 4` confirmed; semaphore wraps both `/chat` and `/v1/chat/completions`.
- Residual `SCIENTIST_*` references audited — only present in (a) two comment headers documenting the rename, (b) four `os.getenv("SCIENTIST_*", ...)` back-compat fallbacks inside the corresponding `REASONING_*` definitions. No active code path uses the old names.

Live smoke test against EVO-X2 was not run this session — that's the next-session entry point. Suggested smoke commands once committed and pulled on EVO-X2 (see Commit + push section):

```
curl -s http://127.0.0.1:8000/health | python3 -m json.tool | head -25
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{"text":"Briefly: what is photosynthesis?","topic":"chat","debug":true}' \
  | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{"text":"Explain Q5_K_M quantization tradeoffs for MoE models.","topic":"science","debug":true}' \
  | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"project_persona","messages":[{"role":"user","content":"hello"}]}' \
  | python3 -m json.tool
```

Acceptance:

- `/health` returns `unified_endpoint`, `thinking_mode_default`, `thinking_mode_topics`; no `scientist_endpoint`.
- chat topic="chat" → `thinking_mode_resolved: "/no_think"` in debug.
- chat topic="science" → `thinking_mode_resolved: "/think"` in debug.
- `/v1/chat/completions` returns clean OpenAI-format response.

---

## Files modified

### Windows-side `D:\Projects\Git\Project_Persona\` (this session, uncommitted)

- `services/api/server.py` — M5 edits (URL collapse, REASONING_* rename, thinking_prefix, concurrency).
- `KNOWLEDGE.md` — M5 marked ✅ Done, M8 superseded by T2.4, System State table extended (Reasoning in-band notes + Thinking-mode routing rows), Known Issues PERSONA_CONCURRENCY caveat resolved, File Change Tracker entry, Last Updated bumped to 2026-05-17 1030 PDT.
- `archive/handoffs/HANDOFF_2026-05-17_1030_m5-server-py-migration.md` — this file.

This stacks on top of the still-uncommitted 1430 canonicalize session work (env + launcher mirror + status.sh + load_test_m2b.py + KNOWLEDGE.md + 1430 handoff).

---

## Commit + push (run on Windows)

Recommended: two commits, single push. Keeps the canonicalize/code-migration split crisp in `git log`. Run from `D:\Projects\Git\Project_Persona\`.

**Commit 1 — qwen-test canonicalize (1430 session):**

```
git status
git add run/llama-servers.env scripts/start_llama_servers.sh scripts/status.sh scripts/load_test_m2b.py archive/handoffs/HANDOFF_2026-05-17_0730_qwen-test-canonicalize.md
git commit -m "qwen-test canonicalize: mirror EVO-X2 env+launcher on Windows, fix status.sh, add M2b load test

- run/llama-servers.env + scripts/start_llama_servers.sh: byte-identical mirror of EVO-X2 qwen-test edits (2026-05-16) for unified Qwen3-30B-A3B-Instruct-2507 Q5_K_M on Vulkan0/RADV. Closes Windows-first workflow drift.
- scripts/status.sh: AI_ROOT default flipped to ~/Git/Project_Persona, names array trimmed to (persona), legacy names retained only in case-exclusion.
- scripts/load_test_m2b.py: new asyncio+httpx client for the M2b sustained-load test. 4 concurrent workers default, per-minute throughput buckets, /health poll, JSON report, exit-nonzero on errors.
- archive/handoffs/HANDOFF_2026-05-17_0730_qwen-test-canonicalize.md: frozen session record.

Refs archive/handoffs/HANDOFF_2026-05-16_2337_qwen-test-first-boot.md."
```

**Commit 2 — M5 server.py migration (this 1730 session):**

```
git add services/api/server.py KNOWLEDGE.md archive/handoffs/HANDOFF_2026-05-17_1030_m5-server-py-migration.md
git commit -m "M5: services/api/server.py single-model migration

Single-model topology (DECISION 2026-05-09) finally reaches the API layer.

- SCIENTIST_URL/SCIENTIST_PORT removed; PERSONA_URL is the only llama-server endpoint.
- ASYNC_SCIENTIST_ENABLED -> ASYNC_REASONING_ENABLED (back-compat: old env name still read).
- SCIENTIST_INBAND_* -> REASONING_INBAND_* (4 vars, all with back-compat fallback).
- scientist_template() -> reasoning_template(); scientist_notes_inband() -> reasoning_notes_inband() routing to PERSONA_URL.
- New thinking_prefix(topic, mode) helper prepends Qwen3 /think or /no_think directive per THINKING_MODE_DEFAULT (auto/on/off) and THINKING_MODE_TOPICS.
- build_persona_prompt() gains thinking_mode kwarg; param renamed scientist_notes -> reasoning_notes.
- PERSONA_CONCURRENCY default 2 -> 4 to match PERSONA_PARALLEL=4 in run/llama-servers.env.
- persona_sem now wraps /v1/chat/completions as well as /chat (invariant: one in-flight request per slot).
- /health returns unified_endpoint, async_reasoning_enabled, reasoning_inband_enabled/topics, thinking_mode_default/topics (removes scientist_endpoint).
- /chat debug surfaces reasoning_inband_used/stats, thinking_mode_resolved.

Persona file loader switched to 2-file Hermes naming (2026-05-14 lock honored):
- ensure_profile_files() scaffolds SOUL.md + .hermes.md (drops persona.md/style.md/system_rules.md).
- load_profile_wrappers() returns (soul_md, hermes_md) 2-tuple.
- build_persona_prompt() prompt prefix uses Soul + Hermes sections; Style guide section dropped.
- Closes TODO #3 + Phase 1 incomplete 'Wire SOUL.md + .hermes.md into build_persona_prompt()'.

KNOWLEDGE.md: M5 + TODO #3 marked Done; M8 superseded by T2.4; System State Multi-profile row promoted to Loaded by API; PERSONA_CONCURRENCY and build_persona_prompt placeholder caveats resolved.

Out of scope (tracked separately):
- <think>-tag stripping at output boundary (T2.4).
- looks_degenerate() reinstate (TODO #37, gated on T2.4).

Refs archive/handoffs/HANDOFF_2026-05-17_1030_m5-server-py-migration.md."
```

**Push:**

```
git push origin main
```

**Pull on EVO-X2:**

```
cd ~/Git/Project_Persona
git fetch origin
git status
git pull --ff-only origin main
ls -la services/api/server.py scripts/load_test_m2b.py scripts/status.sh
chmod +x scripts/load_test_m2b.py scripts/status.sh scripts/start_llama_servers.sh 2>/dev/null || true
./scripts/status.sh
```

Per tenant #2, the explicit chmod +x calls. They're idempotent and harmless if the bits are already set.

**Restart the API on EVO-X2** so the new server.py takes effect:

```
./scripts/stop_api.sh 2>/dev/null || pkill -f 'uvicorn.*server:app' || true
./scripts/start_api.sh
sleep 3
curl -s http://127.0.0.1:8000/health | python3 -m json.tool | head -25
```

---

## Rollback path

If the M5 changes misbehave under live testing:

```
cd ~/Git/Project_Persona
./scripts/stop_api.sh
git log --oneline -5    # find the M5 commit
git revert <m5-commit-hash>
git push origin main
./scripts/start_api.sh
```

The canonicalize commit (env + launcher + status.sh + M2b script) is independently revertable. The unified llama-server itself doesn't care about server.py — it'll keep serving requests, just to the previous server.py code if you also revert this commit.

If only one field of /health misbehaves and a full revert is overkill: cherry-pick a targeted Edit to fix that one thing rather than reverting the whole commit. The semaphore, endpoint, and thinking-mode systems are independent — they can be patched separately.

---

## Open follow-ups (priority-ordered)

### Immediate (next session)

1. **Commit + push + pull + restart API** per the commands above.
2. **Live smoke test on EVO-X2** per the curl block in the Verification section. Confirm `/health` field shape, thinking-mode resolution for chat vs science topics, no regression on `/v1/chat/completions`.
3. **Run M2b sustained-load test** if not done yet: `python3 scripts/load_test_m2b.py --duration 1800 --concurrency 4 --out logs/m2b_$(date +%F_%H%M).json`. Retires the last open migration milestone.

### Soon

4. **M6** — Parallelize RAG retrieval + worker dispatch with `asyncio.gather` (replace the serial in-band reasoning call). Now that the inband call routes to the same unified server, parallelization is a clean cache-prompt win.
5. **TODO #3** — Wire SOUL.md + .hermes.md into `build_persona_prompt()`. The persona file loader still references legacy 3-file structure. The 2-file Hermes-naming scaffold (locked 2026-05-14) is on disk in `archive/legacy_profile_files/` waiting; init_profiles.sh creates the new structure for new profiles.
6. **TODO #37 looks_degenerate decision gate** — must land or be formally dropped before T2.4 closes.
7. **T2.4** — `<think>`-tag stripping at the Task Board → persona surface boundary. Natural neighbor of TODO #37; consider landing together.

### Eventually

8. **`scripts/unified_test.sh`** rewrite for the unified topology — currently references the retired dual-server endpoints.
9. **TODO #2** — `run/llama-servers.env` → `run/config.env` rename + scope expansion.
10. **Chroma → Qdrant** completion on `chore/chroma-to-qdrant` branch.
11. **Phase 8 Hermes adoption** — `<think>`-stripping (T2.4) + role-prefix templates + Task Board dispatcher.

---

## End

M5 closes the API-side dual-server vestige and lays foundations for both T2.4 (output-boundary filters) and Phase 8 (Hermes role-prefix templates). The unified server is now consistently the only llama-server endpoint server.py knows about; the in-band reasoning feature is preserved with new naming and routes to the same model with a different prompt. PERSONA_CONCURRENCY matches the slot count. Thinking-mode is wired and observable via /health and /chat debug.

Next session is short: commit, push, pull, restart, smoke-test. Then M2b or M6 are equally good next moves.
