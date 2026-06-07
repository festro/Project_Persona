# Handoff -- Project_Persona -- 2026-06-07 1236 PDT

Author: Brandon + Claude. Branch: main. Base commit: 73d2e31 (origin/main).
Working-tree change -- NOT yet committed. Complements `todo.md` / `changelog.md` /
`roadmap.md`; does not replace them. Keep ASCII (see `WORKFLOW.md`).

## TL;DR

Phase 1 Task Board landed (code). A new stdlib-sqlite3 `services/api/taskboard.py`
replaces the in-memory `jobs` dict + `run/jobs.jsonl` event log, and `/agent/run`
now records each run into it so `/jobs` actually reflects agent work. Default DB is
`data/tasks.db` (already gitignored). Off-mount verified; the full FastAPI offline
suite + a live `/agent/run` smoke are the next step. Nothing committed yet.

## What was done this session (since commit 73d2e31)

1. `services/api/taskboard.py` (new, stdlib sqlite3, no deps): one row per job_id
   holding a merged JSON `state` + queryable `status` + created/updated timestamps.
   API: `init_db` (idempotent; one-time `jobs.jsonl` migration when empty),
   `task_set` (upsert-merge -- same semantics as the old
   `jobs.setdefault(id,{}).update(patch)`), `task_get`, `task_list`, `task_delete`,
   `count`, `migrate_from_jsonl`. Fresh connection per call + WAL + busy_timeout
   (the API reaches it from `to_thread` worker threads; sqlite3 forbids cross-thread
   connection sharing). FILE-backed by design -- `:memory:` would give each call its
   own empty DB.
2. server.py wiring:
   - Removed the in-memory `jobs` dict, `_load_persisted_jobs`, `_persist_job_event`.
   - `TASKS_DB` config (default `AI_ROOT/data/tasks.db`, env override).
     `JOBS_PERSIST_PATH` kept ONLY as the migration source. Dropped
     `JOBS_PERSIST_ENABLED` / `JOBS_PERSIST_MAX_LOAD`.
   - `taskboard.init_db(TASKS_DB, migrate_jsonl=JOBS_PERSIST_PATH)` at import.
   - `_job_set()` is now a thin `taskboard.task_set` wrapper.
   - `/agent/run` records run -> ok/error/timeout (+ returncode, started/finished_at).
   - New `GET /jobs` (list, `?limit`); `GET /jobs/{id}` reads the board; `/health`
     adds `task_store {db, count}`.
3. `.gitignore`: `data/` already ignored (covers the default DB); added `tasks.db` +
   `-wal`/`-shm` guards for `TASKS_DB` overrides.
4. tests/test_api_offline.py: +6 Task Board checks (health task_store; /jobs missing
   -> not_found; upsert-merge via /jobs/{id}; timestamps; /jobs list membership +
   status).

## Behavior change to verify

`/agent/run` now PERSISTS to the board (previously it returned synchronously and
never touched the jobs store). So after a real taskman2 run, `GET /jobs` and
`GET /jobs/{task_id}` should show it (status running -> ok/error/timeout). This is
the one user-visible behavior change; confirm with a live smoke.

## Verification done (off-mount)

- taskboard.py standalone harness 15/15: file creation, jsonl migration (incl. merge
  across events + bad-line skip), upsert-merge keep-old+new, get adds
  job_id/_created_at/_updated_at, status column tracks latest, list newest-first +
  bounded, count, delete (hit + miss), idempotent re-init (no dup migrate),
  nested/unicode round-trip.
- server.py AST + py_compile OK on a spliced authoritative full file (1118 lines;
  the D:\Projects mount truncates its copy at ~1074, the known staleness -- head was
  current with all edits, tail supplied via the Read tool). taskboard call sites
  confirmed placed (init 430, _job_set 879, /health 950, /jobs 1027/1032).
- test additions parse (AST OK). Full FastAPI suite needs the portable interpreter.

## Next (in order) -- start here next session

1. Validate Task Board Windows-side:
   - Offline suite: `.\portable\python\python.exe tests\test_api_offline.py`
     (expect ~40/40, ALL PASS).
   - Live smoke (stack up): POST a small job to `/agent/run`, then `GET /jobs` and
     `GET /jobs/{task_id}` -> the run shows with a terminal status; `/health`
     `task_store.count` increments; confirm `data/tasks.db` is created (+ -wal/-shm)
     and gitignored.
   - If green: roadmap Task Board -> [x]; commit + push (use `git commit -F <file>`,
     not `-F-`).
2. Remaining Phase 1 feature items: per-profile Chroma collections wired to the API;
   topic routing policy; M6 single-model migration confirmation.
3. T2.4: the `--jinja` messages migration (only remnant; shared with deferred T2.2
   Path-B) -- when it lands, split_reasoning becomes the in-band fallback.

## Open / watch (from todo Housekeeping)

- (low, CONFIRM) live persona.log showed `n_ctx = 4096` x4 slots on Qwen3.6 ->
  implies live --ctx-size ~16384, not the documented PERSONA_CTX=32768. Confirm vs
  run/config.toml (could be an intentional 16 GB VRAM fit).
- (info) recurring `erased invalidated context checkpoint` warnings = Qwen3.6 MTP
  speculative-decoding checkpoint churn under parallel mixed prompts. Expected.

## Gotchas / notes

- Default DB under `data/` (gitignored). Committing this is safe; runtime behavior
  changes only for `/agent/run` persistence + the new `/jobs` list.
- Environment unchanged: Windows-authoritative; the Linux mount is stale/truncating
  (cut server.py at ~1074 this session) and corrupts the git index -- validate at
  source via Read, run git + live checks Windows-side.
- Commit messages: `git commit -F <gitignored .log file>`, never `-F-`
  (interactive PowerShell does not pipe a pasted message to stdin).
