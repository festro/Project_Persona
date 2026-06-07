# Handoff -- Project_Persona -- 2026-06-07 1208 PDT

Author: Brandon + Claude. Branch: main. Base commit: 0d90532 (origin/main).
Working-tree change -- NOT yet committed. Complements `todo.md` / `changelog.md` /
`roadmap.md`; does not replace them. Keep ASCII (see `WORKFLOW.md`).

## TL;DR

T2.3 (preserve_thinking) implemented on Path A. A new `split_reasoning()` pulls
the in-band Qwen3 `<think>...</think>` out of the raw reply before the persona
sanitizer runs, and a `preserve_thinking` flag (default off) decides whether the
reasoning is surfaced to the caller or discarded. As a side effect it closes the
latent leak where `<think>` would bleed into the persona paragraph once Qwen3.6
thinking fires, and it advances T2.4 (the in-band strip is now done; only the
`--jinja` messages migration remains). Code is offline-verified; the full suite +
live validation are the next step. Nothing committed yet.

## What was done this session (since commit 0d90532)

1. server.py `split_reasoning(text) -> (reasoning, answer)`: extracts in-band
   `<think>...</think>` (normal wrap, multiple blocks, case-insensitive, and a
   truncated unclosed `<think>` -> remainder is reasoning, answer empty). No-op
   (`("", text)`) when no tag is present -- the future `--jinja` reasoning_content
   path passes straight through.
2. `preserve_thinking` flag: `Optional[bool]` on ChatRequest + OA_ChatCompletionsReq;
   `PRESERVE_THINKING_DEFAULT` env (off); `resolve_preserve_thinking()` = req value
   else default. Intended for the Phase 3 daemon to set on Hermes-forwarded work.
3. /chat + /v1 split reasoning BEFORE sanitizing:
   - Default (preserve off): reasoning stripped, then the persona two-part
     sanitizer runs on the answer -- persona surface is now `<think>`-free.
   - Preserve on: answer returned un-sanitized; reasoning surfaced as `reasoning`
     (/chat) and `reasoning_content` on the /v1 message (+ a reasoning_content
     delta chunk on the stream).
4. Observability: /health `preserve_thinking_default`; /chat debug
   `preserve_thinking` {resolved, reasoning_chars}.
5. tests/test_api_offline.py: +9 checks (split_reasoning units; /chat default strip
   + empty reasoning; /chat preserve reasoning + un-sanitized answer; /v1 preserve
   reasoning_content; /v1 default none). Suite 22 -> 31 when run live.
6. Docs: roadmap T2.3 -> [~] + T2.4 note; changelog 1208; todo; knowledge (gate
   paragraph extended + PRESERVE_THINKING_DEFAULT=0 in the target-env block).

## Design decision (flag for review)

Preserve mode skips the lossy two-part persona sanitizer entirely -- agent loops
want the whole answer, not a paragraph + "Next actions" bullets. So
`preserve_thinking` currently couples two things: keep reasoning AND skip persona
formatting. If a future case wants preserved reasoning WITH persona formatting,
split them into two flags. Noted in roadmap T2.3.

## Verification done (off-mount)

- Authoritative server.py complete + balanced through the /v1 return (Read, line
  1141). The sandbox mount truncated its copy at ~1084 lines (the known D:\Projects
  mount staleness) so py_compile could not run there -- expected, not a real error.
- Standalone logic harness 12/12 against the extracted split_reasoning /
  resolve_preserve_thinking (wrap, whitespace, none, unclosed, multi-block, case,
  empty; resolve default/override both polarities).
- Full offline suite needs the portable interpreter -> run Windows-side.

## Next (in order) -- start here next session

1. Validate T2.3 Windows-side:
   - Offline suite: `.\portable\python\python.exe tests\test_api_offline.py`
     (expect 31/31, ALL PASS).
   - LIVE (Qwen3.6 served, /think firing): POST /chat and /v1 with
     `preserve_thinking` true vs false; confirm reasoning is returned under
     preserve (`reasoning` / `reasoning_content`) and absent + stripped from the
     default persona text. Spot-check the stream emits a reasoning_content delta
     under preserve.
   - If green: roadmap T2.3 -> [x]; commit + push (use `git commit -F <file>`,
     not `-F-`).
2. Phase 1 Exit Gate proof (live, Brandon): chat->no_think,
   science/coding/math/research->think; stream=true SSE + non-zero prompt_tokens;
   /health embedder_ok + chroma_ok. Roll the T2.2 gate-on + T2.3 preserve checks
   into this pass.
3. T2.4: only the `--jinja` messages migration remains (shared with the deferred
   T2.2 Path-B work) -- when that lands, split_reasoning becomes the in-band
   fallback and the post-hoc sanitizer can retire on that path.

## Blocked / waiting

- Hermes (H1-H6) gated on single-model migration; confirm M6 before H1. The daemon
  that would set preserve_thinking=true on Hermes work is Phase 3 (not built) -- for
  now the flag is exercised via the request field / env default.
- Linux/ARM64 live validation -- no hardware (Phase 0.5 deferral).

## Gotchas / notes

- Default off -> committing T2.3 changes no runtime behavior until the flag/env is
  set; the Phase 1 exit-gate invariant is unaffected.
- Environment unchanged: Windows-authoritative; the Linux mount is
  stale/truncating (it cut server.py at ~1084 lines this session) and corrupts the
  git index -- validate at source via Read, run git + live checks Windows-side.
- Commit messages: use `git commit -F <gitignored .log file>`; interactive
  PowerShell does not pipe a pasted message to `-F-` (the commit silently no-ops;
  a later push says "Everything up-to-date").
