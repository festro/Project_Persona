# Handoff -- Project_Persona -- API gap fixes (streaming, usage, /agent/run, /chat_submit, root)

Date: 2026-06-05 1612 PDT
Authors: Brandon + Claude
Scope: Closed the four API gaps from the 2026-06-03 code read, added a root/favicon
route, and validated the changes offline with a FastAPI TestClient suite. Also
records the env fixes applied earlier this session (setuptools + posthog pins).
Status: Code changes DONE and validated offline (15/15). Live generation unchanged
-- still needs the Qwen3.6 llama-server on :8090.
Next: entry point is unchanged from handoff 2248 (stand up the llama-server, then
exercise streaming + sampling presets end-to-end), now with streaming testable.

---

## 1. What changed (services/api/server.py)

All four items from todo.md "API gaps" (and the bare-URL 404) are closed.

1. `stream` honored in `/v1/chat/completions`. When `stream=true` the endpoint
   returns `text/event-stream` emitting OpenAI `chat.completion.chunk` deltas (a
   role chunk, then word-wise content chunks, then a `finish_reason:"stop"` chunk)
   terminated by `data: [DONE]`. DESIGN NOTE: this is a pseudo-stream. The reply is
   generated and run through `sanitize_persona_reply` first (the sanitizer
   restructures the whole reply into paragraph + "Next actions" bullets, so it
   fundamentally needs the complete text), then chunked. It is NOT token-by-token
   from the model. Memory distillation/writeback still runs before streaming begins.
   server.py:946-960.

2. Real `usage` token counts in `/v1/chat/completions`. `query_llama` now captures
   llama.cpp's `tokens_evaluated` (prompt tokens) alongside `tokens_predicted`.
   `prompt_tokens = tokens_evaluated`, `completion_tokens = tokens_predicted`,
   `total_tokens = sum` (previously `prompt_tokens` was hardcoded 0).
   server.py:513-515 (query_llama), 943-944 + 968-972 (endpoint).

3. `/agent/run` no longer blocks the event loop. The blocking
   `subprocess.run(..., timeout=300)` is offloaded with `asyncio.to_thread(...)`;
   `subprocess.TimeoutExpired` still propagates and is handled as before. Request
   and response shapes are unchanged. server.py:729-733.

4. `/chat_submit` removed. The disabled stub route and the `SubmitRequest` model
   were deleted (it only ever returned "disabled in this build"). The jobs
   persistence helpers (`_job_set`, `_persist_job_event`, `_load_persisted_jobs`)
   and `/jobs/{id}` were KEPT intentionally -- they are reusable scaffolding for a
   real async-job implementation later. `_job_set` is now unused (only the stub
   called it); left in place deliberately. Grep confirmed no code references outside
   docs/archive.

5. New `GET /` (small status JSON: service/status/docs/health) and `GET
   /favicon.ico` (204) so the bare base URL stops 404ing. The real `/health` was
   always present and remains the thorough liveness/config endpoint. Added `Response`
   to the fastapi.responses import. server.py:799-806 (and import line).

## 2. Validation (offline)

Method: FastAPI TestClient with `server.query_llama` monkeypatched to a canned
`(content, {"tokens_generated":11, "tokens_evaluated":42})`, RAG + distill +
writeback disabled via env, so nothing hits the network or the model.

Result: 15/15 PASS --
- GET / -> 200 + service json; GET /favicon.ico -> 204
- GET /health -> 200; GET /v1/models -> 200
- /v1 non-stream usage: prompt_tokens=42, completion_tokens=11, total_tokens=53
- /v1 stream: 200, content-type text/event-stream, contains chat.completion.chunk,
  ends with data: [DONE], delta content reconstructs to non-empty text
- POST /chat_submit -> 404 (route gone)
- POST /agent/run reachable without stalling (threadpool offload)

Reusable test: `tests/test_api_offline.py` (delivered this session; run from repo
root with the portable interpreter). It is self-contained and needs no llama-server.

NOTE on the sandbox: validation was done against a verified copy of server.py. The
agent's Linux mount of D:\ lagged/served a truncated copy mid-edit during testing;
the authoritative host file (974 lines) was confirmed complete and correct via the
editor. This only affected the agent's sandbox, not the real repo file.

## 3. What is NOT done / follow-ups

- True token-by-token streaming is not implemented (would require streaming from
  llama-server with `stream:true` and emitting deltas live, which conflicts with the
  post-hoc sanitizer; would need a sanitizer redesign or a "raw" stream mode).
- No real async-job endpoint yet; the jobs helpers remain for when one is wanted.
- Live end-to-end generation (/chat, /v1 with a real model) still requires the
  llama-server on :8090 -- unchanged entry point (see section 5).

## 4. Env fixes applied earlier this session (already live Windows-side)

- scripts/bootstrap_portable_python.ps1: pip-upgrade step pins `setuptools<82` so it
  no longer installs 82.x then gets downgraded by torch's `setuptools<82` pin
  (removes the wasteful bounce and the alarming pip resolver ERROR).
- services/api/requirements.txt: pins `posthog>=2.4.0,<3.0.0`. chromadb 0.6.3 calls
  posthog's old `capture()` signature; posthog 7.x changed it, which caused the
  "capture() takes 1 positional argument but 3 were given" telemetry errors at
  startup. This is the real fix (the ANONYMIZED_TELEMETRY=False env was already set
  but not honored for those events). Re-run confirmed: setuptools held at 81.0.0,
  posthog downgraded 7.17.0 -> 2.5.0, startup log clean.

## 5. NEXT SESSION -- entry point (unchanged from handoff 2248)

1. Stand up the Qwen3.6 llama-server on :8090 (Windows portable flow;
   scripts/start_llama_server_win.sh with --jinja). GOTCHA: it does NOT survive being
   launched via `bash.exe scripts/...` from PowerShell; run it FOREGROUND in a
   dedicated window.
2. With the API up (`bootstrap_portable_python.ps1 -Run`), exercise:
   - sampling presets: a "chat" topic -> no_think, science/coding/math/research ->
     think (verify via /chat debug `sampling_preset`).
   - NEW: streaming -- POST /v1/chat/completions with `stream:true` and confirm the
     SSE chunks + [DONE]; non-stream `usage.prompt_tokens` should now be > 0.
3. Then T2.2 (enable_thinking via chat_template_kwargs or keep the /think prefix).

## 6. Commit guidance (git runs Windows-side -- the Linux mount corrupts the index)

    $env:Path = "D:\Projects\Tools\PortableGit\cmd;" + $env:Path
    cd D:\Projects\Git\Project_Persona
    git add services/api/server.py knowledge.md todo.md changelog.md archive/handoffs/ tests/
    git status
    git commit -m "API gap fixes: stream, usage tokens, non-blocking /agent/run, drop /chat_submit, root route"

Note: scripts/bootstrap_portable_python.ps1 and services/api/requirements.txt
(setuptools/posthog pins) may already be staged/committed from earlier this session
-- check `git status` before committing.

---

Frozen handoff record. Future revisions create a new dated handoff.
