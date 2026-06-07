# Handoff -- Project_Persona -- 2026-06-07 1151 PDT

Author: Brandon + Claude. Branch: main. Base commit: 8088ff2 (origin/main).
Working-tree change -- NOT yet committed. Complements `todo.md` / `changelog.md` /
`roadmap.md`; does not replace them. Keep ASCII (see `WORKFLOW.md`).

## TL;DR

T2.2 (thinking mode) landed on Path A: keep the `/think`//`/no_think` prefix on the
raw `/completion` flow and add an OFF-by-default per-request triviality gate
(`THINKING_AUTO_GATE`). The `chat_template_kwargs`/messages migration is explicitly
folded into T2.4 (same `--jinja` `reasoning_content` world -- do the messages rework
once). Code is written and offline-verified; LIVE `/chat` debug validation is the
next step (Brandon, with Qwen3.6 served). Nothing committed yet.

## Decision (Path A vs B)

`chat_template_kwargs.enable_thinking` only fires when llama.cpp owns template
application -- i.e. the `/chat/completions` messages format. The serving path today
sends a pre-rendered raw prompt to `/completion`, where the template is never
applied, so `chat_template_kwargs` has nothing to act on. Two paths:

- Path A (chosen): formalize the existing soft-switch prefix + add the triviality
  gate. Small blast radius; RAG injection, the `clean_to_two_parts` sanitizer, and
  token accounting are untouched.
- Path B (deferred to T2.4): migrate `query_llama` + `build_persona_prompt` to
  messages + `chat_template_kwargs` (hard switch). Under `--jinja`, reasoning moves
  to `reasoning_content`, which is exactly the T2.4 channel-split -- so the messages
  migration is done once there, with the sanitizer retirement as its payoff.

## What was done this session

1. server.py -- `classify_triviality(text) -> (is_nontrivial, signals)`: a
   deterministic, stdlib-only (no model call) classifier. Non-trivial signals:
   code fence / `def`/`class`/`import`, >=2 `?`, >=3 sentences, >= COMPLEX_MIN_WORDS
   words, or a reasoning-keyword hit. Trivial: <= TRIVIAL_MAX_WORDS -> `short`,
   else `default_trivial`. `signals` is returned so the verdict is auditable.
2. `resolve_think` / `thinking_prefix` / `sampling_for` gained an optional `text`
   arg. New precedence: explicit `on`/`off` override -> topic in
   `THINKING_MODE_TOPICS` -> think -> (gate on + text) triviality verdict ->
   else no_think. The gate only PROMOTES within the otherwise-flat "everything
   else -> no_think" bucket; explicit modes and the thinking topics stay
   deterministic.
3. Call sites threaded: `build_persona_prompt` passes `user_text`; `/chat` and
   `/v1/chat/completions` pass the request text into `sampling_for` /
   `thinking_prefix`.
4. Config (all env-overridable): `THINKING_AUTO_GATE` (default 0 = off),
   `THINKING_GATE_TRIVIAL_MAX_WORDS` (6), `THINKING_GATE_COMPLEX_MIN_WORDS` (30),
   `THINKING_GATE_KEYWORDS`.
5. Observability: `/health` adds `thinking_auto_gate`; `/chat` debug adds
   `thinking_gate` {enabled, is_nontrivial, signals}.
6. tests/test_api_offline.py: +8 gate checks (classify direct; gate-off keeps
   "chat" at no_think; gate-on promotes a non-trivial "chat" to think + think
   preset; trivial "chat" stays no_think; "science" stays deterministic think).
   Suite 14/14 -> 22/22 when run live.
7. Docs: roadmap T2.2 -> [~] with the Path A note; changelog 1151; todo.md Just
   finished + Next; knowledge.md gate paragraph + `THINKING_AUTO_GATE=0` in the
   target-env block.

## Verification done (off-mount)

- AST + `py_compile` OK on a completeness-verified off-mount copy of server.py
  (1087 lines; edit markers `THINKING_AUTO_GATE` x6 + `classify_triviality`
  present, so the mount served the edited file, not a stale one).
- Standalone logic harness 14/14 against the extracted `classify_triviality` /
  `resolve_think` (gate off/on, promote/demote, thinking-topic determinism,
  no-text fall-through).
- test_api_offline.py: AST OK (full run needs the portable interpreter + deps;
  run Windows-side).

## Next (in order) -- start here next session

1. LIVE T2.2 validation (Brandon, Qwen3.6 served on :8090, API :8000):
   - Gate OFF (default): POST `/chat` `{"text":"...complex...","topic":"chat",
     "debug":true}` -> `thinking_mode_resolved` == `/no_think` (exit-gate invariant).
   - Gate ON (`THINKING_AUTO_GATE=1`, restart API): a non-trivial "chat" prompt ->
     `/think` + `sampling_preset` `think`; `"hi"` -> `/no_think`; `topic":"science"`
     -> `/think` regardless. Check `debug.thinking_gate.signals` reads sensibly.
   - Run the offline suite: `.\portable\python\python.exe tests\test_api_offline.py`
     (expect 22/22).
   - If green: roadmap T2.2 -> [x]; commit + push.
2. T2.3: preserve_thinking for Hermes-originated requests.
3. Phase 1 Exit Gate proof (live): chat->no_think, science/coding/math/research->
   think; stream=true SSE + non-zero prompt_tokens; /health embedder_ok +
   chroma_ok.

## Gotchas / notes

- Tune-by-env, no code edit: widen/narrow promotion via
  `THINKING_GATE_COMPLEX_MIN_WORDS` / `_TRIVIAL_MAX_WORDS` / `_KEYWORDS`. With the
  gate ON, a long or keyword-bearing "chat" prompt now thinks -- intended, but it
  means "chat" is no longer a hard no_think guarantee while the gate is on.
- Default is OFF, so committing this changes no runtime behavior until Brandon
  flips the flag. The Phase 1 exit-gate proof is unaffected.
- Environment unchanged: repo is Windows-authoritative; the Linux mount is
  stale/truncating and corrupts the git index -- validate at source, git + live
  checks Windows-side (see `AGENTS.md`).
- server.py still can't be reliably parsed through the mount; this session's
  AST/compile used a completeness-verified off-mount copy (markers + tail matched).
