# Handoff -- Project_Persona -- 2026-06-07 1613 PDT

Author: Brandon + Claude. Branch: main. Base commit: per-profile Chroma commit
(expected on origin; this builds on it). Working-tree change -- NOT yet committed.
Complements `todo.md` / `changelog.md` / `roadmap.md`. Keep ASCII (see `WORKFLOW.md`).

## TL;DR

Topic routing landed (OFF by default) -- the last Phase 1 feature item that could be
drafted offline. A deterministic `classify_topic(text)` + `resolve_topic` precedence
let an unlabeled request route to the right thinking/sampling/RAG path instead of
always defaulting to "chat". Off by default, so behavior is unchanged until enabled.
Off-mount verified; full offline suite + a live smoke are the next step.

## What was done this session (since the per-profile Chroma commit)

1. server.py: `classify_topic(text)` -- deterministic keyword classifier over
   coding/math/biology/science/research (else "chat"). Scores keyword hits; the first
   topic in `TOPIC_PRIORITY` with the strict-max score wins (ties -> higher priority).
2. `resolve_topic(req_topic, text)` precedence: `"auto"` always classifies; an
   explicit non-chat topic is respected as-is; `""`/`"chat"` classifies only when
   `TOPIC_ROUTING` is on, else stays `"chat"`.
3. `/chat` and `/v1` resolve the topic via `resolve_topic` BEFORE everything
   downstream (RAG kinds, thinking/sampling, in-band reasoning, metadata).
4. Config: `TOPIC_ROUTING` (default 0), `TOPIC_KEYWORDS`, `TOPIC_PRIORITY`.
5. Observability: `/health` adds `topic_routing` + `topic_routing_topics`; `/chat`
   debug adds `topic_routing {enabled, requested, resolved}`.
6. tests/test_api_offline.py: +8 checks (classify coding/chat; explicit respected;
   /chat auto->math drives the think preset; routing off keeps chat; routing on
   classifies chat->coding; /health fields).

## Design notes

- Default off keeps the contract: callers that pass a topic (or rely on the "chat"
  default) see no change. Routing is opt-in per request (`topic:"auto"`) or globally
  (`TOPIC_ROUTING=1`).
- When `TOPIC_ROUTING=1`, a literal `topic:"chat"` is treated as "route it" -- there
  is no way to force the chat path while global routing is on (send a specific topic
  to override). Acceptable; documented.
- Keyword sets are intentionally small/curated; tune via TOPIC_KEYWORDS if a domain
  is mis-routed. Classifier is heuristic, not a model call (cheap, deterministic).

## Verification done (off-mount)

- Standalone topic harness 14/14: each topic classified, chat fallback, priority
  tie-break (coding before math), and resolve_topic precedence both polarities.
- server.py AST + py_compile OK on a spliced authoritative full file (1238 lines; the
  mount truncates its copy at ~1057 -- known staleness). classify_topic/resolve_topic
  + both call sites confirmed placed.
- Full FastAPI offline suite needs the portable interpreter -> Windows-side.

## Next (in order) -- start here next session

1. Validate topic routing Windows-side:
   - Offline suite: `.\portable\python\python.exe tests\test_api_offline.py`
     (expect ~54/54, ALL PASS).
   - Live smoke (stack up): POST `/chat` with `topic:"auto"` and a coding/math/science
     prompt + `debug:true`; confirm `debug.topic_routing.resolved` and that
     `sampling_preset`/`thinking_mode_resolved` follow (think for the routed topics).
     Default off: an unlabeled prompt stays `chat`.
   - If green: roadmap Topic routing -> [x]; commit + push (`git commit -F <file>`).
2. Phase 1 now has all four feature items at [~] (Task Board, per-profile Chroma,
   topic routing) + the Exit Gate PROVEN; only M6 (live single-model migration
   confirmation) and T2.4 remain to close the phase.
3. T2.4: the `--jinja` messages migration (largest remaining T2 piece; shared with the
   deferred T2.2 Path-B). When it lands, split_reasoning becomes the in-band fallback
   and the post-hoc sanitizer can retire on that path.

## Open / watch (unchanged)

- (low, CONFIRM) live `n_ctx=4096` x4 slots vs PERSONA_CTX=32768 -- confirm config.toml.
- (info) Qwen3.6 MTP speculative-decoding checkpoint churn under parallel prompts.
- Per-profile Chroma migration story (existing global_memory rows) still a follow-up.

## Gotchas / notes

- Default off -> committing changes no runtime behavior until `TOPIC_ROUTING=1` or a
  `topic:"auto"` request.
- Environment unchanged: Windows-authoritative; mount stale/truncating (cut server.py
  at ~1057 this session); validate via Read, git + live checks Windows-side.
- Commit messages: `git commit -F <gitignored .log file>`, never `-F-`.
