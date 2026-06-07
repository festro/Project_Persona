# Handoff -- Project_Persona -- 2026-06-07 1243 PDT

Author: Brandon + Claude. Branch: main. Base commit: 8b2a5d8 (origin/main).
Working-tree change -- NOT yet committed. Complements `todo.md` / `changelog.md` /
`roadmap.md`; does not replace them. Keep ASCII (see `WORKFLOW.md`).

## TL;DR

Per-profile Chroma is now wired (OFF by default). RAG retrieval + writeback can be
scoped to a per-persona collection (`mem_<profile>`) via `RAG_PER_PROFILE`; off keeps
the single shared `global_memory` collection and the exact prior behavior. The one
caveat: enabling it does not migrate existing rows out of `global_memory`. Off-mount
verified; full offline suite + live smoke pending. Nothing committed yet.

## What was done this session (since commit 8b2a5d8)

1. server.py RAG layer made profile-aware:
   - Replaced the single module-global `_collection` with a `_collections` dict +
     `_collection_name(profile)` and `_get_collection(profile)` (lazy get-or-create
     + cache). The shared collection is created at startup; per-profile ones lazily.
   - `memory_add` / `memory_query` gained a keyword-only `profile`; `/chat`, `/v1`,
     `distill_and_store_facts`, and the chat-log writeback now pass the active
     profile.
2. Config: `RAG_PER_PROFILE` (default 0) and `RAG_GLOBAL_COLLECTION` (default
   `global_memory`). Off -> everything uses the shared collection exactly as before.
   On -> `mem_<sanitized-profile>` (regex-sanitized, length-capped, always a valid
   Chroma name).
3. Observability: `/health` adds `rag_per_profile` + `rag_collections` (cached names).
4. tests/test_api_offline.py: +6 checks (collection_name off/on/None/sanitize; health
   fields). Env-independent -- no chroma required.

## Caveat to decide on

`RAG_PER_PROFILE=1` does NOT move existing `global_memory` rows into per-profile
collections. So flipping it on makes prior memory invisible to per-profile queries
until migrated. Options for the follow-up: (a) a one-time splitter that re-files
`global_memory` rows by their `profile` metadata into `mem_<profile>`; (b) query
BOTH the profile collection and the shared one (union) during a transition. Left as a
deliberate decision -- default-off means no surprise today.

## Verification done (off-mount)

- `_collection_name` standalone harness 8/8 (off->global, on->mem_<p>, None/empty->
  global, unsafe-char sanitize, valid-name prefix, length cap).
- server.py AST + py_compile OK on a spliced authoritative full file (1161 lines; the
  D:\Projects mount truncates its copy at ~1063 -- the known staleness). All
  per-profile call sites confirmed placed. No dangling `_collection` references.
- Full FastAPI offline suite needs the portable interpreter -> run Windows-side.

## Next (in order) -- start here next session

1. Validate per-profile Chroma Windows-side:
   - Offline suite: `.\portable\python\python.exe tests\test_api_offline.py`
     (expect ~46/46, ALL PASS).
   - Live smoke (stack up, RAG_ENABLED=1): default (off) -> `/health` shows
     `rag_per_profile=false`, `rag_collections=["global_memory"]`. Then restart with
     `RAG_PER_PROFILE=1`, POST `/chat` with `profile=alice` and `profile=bob`, and
     confirm `/health` `rag_collections` grows `mem_alice`/`mem_bob` and that a fact
     stored under alice is not retrieved under bob.
   - If green: roadmap per-profile Chroma -> [x]; commit + push (`git commit -F
     <file>`, not `-F-`). Decide the migration story (caveat above).
2. Topic routing policy (last Phase 1 feature item I can draft solo).
3. M6 single-model migration confirmation; then the Hermes H-track unblocks.
4. T2.4 `--jinja` messages migration.

## Open / watch (unchanged from 1236)

- (low, CONFIRM) live `n_ctx=4096` x4 slots vs documented PERSONA_CTX=32768 -- confirm
  run/config.toml.
- (info) Qwen3.6 MTP speculative-decoding checkpoint churn under parallel prompts.

## Gotchas / notes

- Default off -> committing changes no runtime behavior until `RAG_PER_PROFILE=1`.
- Environment unchanged: Windows-authoritative; the mount is stale/truncating (cut
  server.py at ~1063 this session) and corrupts the git index -- validate at source
  via Read, git + live checks Windows-side.
- Commit messages: `git commit -F <gitignored .log file>`, never `-F-`.
