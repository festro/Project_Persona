# Handoff -- Project_Persona -- 2026-06-07 1635 PDT

Author: Brandon + Claude. Branch: main. Base commit: 0923eef (origin/main).
Working-tree change -- NOT yet committed. Complements `todo.md` / `changelog.md` /
`roadmap.md`. Keep ASCII (see `WORKFLOW.md`).

## TL;DR

T2.4 -- the `--jinja` messages migration -- is implemented behind
`PERSONA_USE_MESSAGES` (OFF by default). Both endpoints now call a single
`persona_generate()` helper: off keeps the proven raw `/completion` + `/think`-prefix
path (byte-identical); on switches to `/v1/chat/completions` with `messages` +
`chat_template_kwargs{enable_thinking}`, where the server returns reasoning in
`reasoning_content`. This is the ONE change in this whole arc that genuinely cannot
be validated offline -- the real `--jinja` behavior needs the live server. Default
off keeps everything safe until you confirm it live.

## What was done this session (since commit 0923eef)

1. `query_llama_messages(url, messages, max_tokens, temperature, timeout_s, *,
   enable_thinking, extra)`: POSTs the OpenAI-compatible chat endpoint with
   `chat_template_kwargs{enable_thinking}`; parses `choices[0].message.content` +
   `reasoning_content` + `usage` (mapped to query_llama's stats keys).
2. `build_persona_messages()`: system/user split mirroring `build_persona_prompt`'s
   persona block, minus the `/think` prefix and trailing `Assistant:` (the chat
   template owns the assistant turn; thinking is the enable_thinking kwarg). Persona
   wording is ASCII here (the proven `/completion` path's exact bytes are untouched).
3. `persona_generate()`: the convergence helper both `/chat` and `/v1` call. Returns
   `(reasoning, answer, stats)`. Off -> raw `/completion` (unchanged). On -> messages;
   server `reasoning_content` preferred, `split_reasoning()` fallback. This also
   de-duplicates the generation call that used to be inline in each endpoint.
4. Config: `PERSONA_USE_MESSAGES` (default 0), `PERSONA_CHAT_URL`
   (`/v1/chat/completions` on PERSONA_PORT). Confirmed against the vendored server
   README (`llama_cpp/tools/server/README.md`): `--jinja` default-on,
   `--reasoning-format deepseek` -> `reasoning_content`,
   `chat_template_kwargs` accepts `{"enable_thinking": false}`.
5. `/health`: persona_use_messages + persona_chat_url.
6. tests/test_api_offline.py: +8 checks (messages structure + no think prefix;
   messages path via a monkeypatched query_llama_messages -> preserve surfaces server
   reasoning, default sanitizes, /v1 reasoning_content; health field).

## Design notes / decisions

- One flag, whole-path switch. `persona_generate` keeps the branch in one place so the
  two endpoints stay identical. The default path is byte-for-byte the old behavior
  (verified by construction: same build_persona_prompt + query_llama + split_reasoning).
- Streaming unchanged: `/v1` still pseudo-streams the finished `reply` token-by-token;
  I did NOT proxy llama's SSE. Lower blast radius; revisit if true streaming is wanted.
- `build_persona_messages` duplicates the persona wording rather than refactoring
  `build_persona_prompt` (which carries en/em-dash bytes) -- deliberate, to leave the
  proven path 100% untouched. If they ever drift, unify via a shared system-block
  helper.

## Verification done (off-mount)

- New functions parse: `head[1..1000]` (through the distill boundary) AST OK --
  covers query_llama_messages, build_persona_messages, persona_generate.
- query_llama_messages parse logic 6/6 standalone (thinking on -> content+reasoning;
  off -> empty reasoning; empty payload safe; usage->stats mapping).
- Both `persona_generate` call sites (/chat 1228, /v1 1318) read-back balanced.
- Full file AST could not be run through the mount (it now truncates at ~1000 lines --
  the file has outgrown the mount limit; known staleness). Run the real suite
  Windows-side.

## Next (in order) -- start here next session

1. Validate T2.4 Windows-side:
   - Offline suite: `.\portable\python\python.exe tests\test_api_offline.py`
     (expect ~64/64, ALL PASS) -- proves the wiring with a faked query_llama_messages.
   - LIVE (stack up, PERSONA_USE_MESSAGES=1; --jinja is the launcher default; ensure
     --reasoning-format deepseek if not default): POST `/chat` with a thinking topic +
     `preserve_thinking:true` + `debug:true`; confirm (a) `reasoning` is populated from
     the server's `reasoning_content`, (b) `text` is `<think>`-free, (c) default
     (preserve off) still returns the two-part persona surface. Compare a no_think
     topic (enable_thinking false) -> no reasoning. Sanity-check `/v1` parity +
     `usage.prompt_tokens > 0`.
   - If green: decide whether to retire the post-hoc sanitizer ON the messages path
     (the T2.4 payoff) or keep it as a belt-and-suspenders; roadmap T2.4 -> [x];
     commit + push (`git commit -F <file>`).
2. The two remaining Phase 1 live smokes (Task Board /agent/run; per-profile
   mem_<profile> under RAG_PER_PROFILE=1) to flip those [~] -> [x].
3. M6 single-model migration confirmation -> unblocks the Hermes H-track.

## Open / watch (unchanged)

- (low, CONFIRM) live `n_ctx=4096` x4 vs PERSONA_CTX=32768 -- confirm config.toml.
- (info) Qwen3.6 MTP speculative-decoding checkpoint churn under parallel prompts.
- Per-profile Chroma migration story (existing global_memory rows) still a follow-up.

## Gotchas / notes

- Default off -> committing changes nothing at runtime until PERSONA_USE_MESSAGES=1.
- The messages path needs `--jinja` (launcher default) AND a reasoning-format that
  populates reasoning_content (deepseek). If reasoning_content comes back empty with
  thinking on, check the server's --reasoning-format; split_reasoning still catches
  in-band `<think>` as a fallback.
- Environment unchanged: Windows-authoritative; the mount now truncates server.py at
  ~1000 lines -- validate via Read/segment-parse, run git + live checks Windows-side.
- Commit messages: `git commit -F <gitignored .log file>`, never `-F-`.
