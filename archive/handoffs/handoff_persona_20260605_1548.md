# Handoff -- Project_Persona -- T2.1 + portable 3.11.9 services env

Date: 2026-06-05 1548 PDT
Authors: Brandon + Claude
Scope: T2.1 (sampling presets), the Python interpreter decision (3.11.9
embeddable), the portable bootstrap, and live validation of the API on the
portable interpreter. Sets the entry point for standing up the Qwen3.6
llama-server and T2.2.
Status: T2.1 DONE and validated live. Portable services env OPERATIONAL.
Next: bring up the llama-server on :8090 for end-to-end /chat (Brandon will run it
and post results next session).

---

## 1. Where the swap track stands

- T0 fully passed (T0.1 2026-05-18, T0.2 2026-06-03). Qwen3.6 swap committed.
- T1 IMPLEMENTED 2026-06-04 (env_hermes venv + per-profile Hermes safe-config +
  doctor.sh gate). Full record: handoff_persona_20260604_0055. All script-drift
  closed (handoff_persona_20260604_1802).
- T2 (core integration) STARTED. T2.1 done + validated live (this handoff).
  T2.2-T2.4 remain (need Qwen3.6 actually serving).

## 2. T2.1 -- per-mode sampling presets (DONE, validated live)

server.py no longer hardcodes temperature=0.7. Single source of truth
`resolve_think(topic, mode) -> think|no_think` drives both the /think//no_think
directive and a `SAMPLING_PRESETS` preset. `sampling_for()` returns
(key, temperature, extra{top_p,top_k,min_p,presence_penalty}); both /chat and
/v1/chat/completions apply it via query_llama's existing `extra` arg. /v1 still
honors an explicit request temperature. Optional per-request `thinking_mode` added
to both request models. /health reports `sampling_presets`; /chat debug reports
the selected preset.

Presets (env-overridable; defaults mirror the per-profile config.yaml / Qwen3.6
guidance):
- no_think: temp 0.7, top_p 0.8, top_k 20, min_p 0.0, presence_penalty 1.5
- think:    temp 0.6, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0

Consolidation point `run/config.env` (git-allowlisted) now holds THINKING_MODE_*,
SAMPLING_*, RAG_ENABLED=1, ANONYMIZED_TELEMETRY=False. start_api.sh sources it
after llama-servers.env. server.py falls back to correct defaults if absent.

Live confirmation (2026-06-05 2229): /health returned the exact presets above.

## 3. Interpreter decision + portable services env

Decision: Python 3.11.9, Windows x64, EMBEDDABLE zip, in portable/python.
Rationale and full compatibility analysis: docs/py314_compatibility.md.
- 3.11 runs the COMPLETE stack incl. ChromaDB RAG; matches the Hermes interpreter
  (Hermes uses its own env_hermes on 3.11).
- 3.11.9 is the LAST 3.11 with official binaries (security-only/source-only after,
  PEP 664, to Oct 2027). Acceptable: localhost-only/offline posture.
- 3.14 (the build originally dropped in) is API-only -- ChromaDB is hard-blocked
  on 3.14 (pypika uses ast.Str, removed in 3.14). If 3.14 is ever revisited, the
  fix is the Qdrant migration (Phase 2a): Qdrant + fastembed are 3.14-OK.

Bootstrap: scripts/bootstrap_portable_python.ps1 (+ .bat wrapper).
- Enables `import site` in python311._pth, bootstraps pip via get-pip.py (the
  embeddable has no pip/venv), installs the committed services/api/requirements.txt
  full stack. Flags: -CoreOnly (API-only), -Run (launch uvicorn on :8000).
- .bat wrapper invokes `powershell -ExecutionPolicy Bypass` (default policy blocks
  the .ps1). Brandon also set CurrentUser RemoteSigned.
- The .ps1 must NOT use `$ErrorActionPreference = "Stop"`: under Stop, PowerShell
  treats any native-command stderr (pip's normal warnings, the expected "no pip
  yet" message) as terminating. It now routes native calls through an
  Invoke-Native helper that checks $LASTEXITCODE, with -ErrorAction Stop only on
  Invoke-WebRequest.

Install result (2026-06-05): full stack installed cleanly on 3.11.9 (all native
deps got 3.11 wheels, no source builds). Resolved versions of note: chromadb
0.6.3 (within the intentional <1.0.0 pin), pypika 0.51.1, chroma-hnswlib 0.7.6,
fastembed 0.8.0, onnxruntime 1.26.0, tokenizers 0.22.2, torch 2.12.0, numpy
2.4.6, fastapi 0.136.3, uvicorn 0.49.0, httptools 0.8.0, pydantic 2.13.4.

## 4. Live validation (2026-06-05 2229)

Booted uvicorn on the portable 3.11.9; GET /health -> 200 OK.
- T2.1 sampling_presets present and exactly correct.
- embedder_ok=true, chroma_ok=true: fastembed downloaded bge-small-en-v1.5-onnx
  and chromadb 0.6.3 initialized at runtime against server.py's code. No API drift
  from the 0.5.x assumption. RAG stack works on 3.11.9, not just imports.

Bug found + fixed: /health showed unified_endpoint on :8080, not :8090. Cause:
server.py defaults PERSONA_PORT=8080 and the -Run path only sourced config.env,
not llama-servers.env (which sets PERSONA_PORT=8090). Fix: -Run now sources
llama-servers.env THEN config.env (start_api.sh order), via a stricter env-var
regex that skips comments. Re-running -Run should show :8090.

Known cosmetic (not addressed): fastembed/HF symlink cache warning on Windows
(needs Developer Mode or admin for symlinks; harmless). Silence with
HF_HUB_DISABLE_SYMLINKS_WARNING=1 if desired.

## 5. How to run the API (portable)

    cd D:\Projects\Git\Project_Persona
    .\scripts\bootstrap_portable_python.ps1 -Run

Loads AI_ROOT + profile dirs, sources llama-servers.env + config.env, launches
uvicorn on 127.0.0.1:8000 (foreground). /health and /docs work without a model.
/chat and /v1/chat/completions need a llama-server on :8090.

## 6. NEXT SESSION -- entry point

Goal: end-to-end /chat, then T2.2.

1. Stand up the Qwen3.6 llama-server on :8090 (Windows portable llama flow). The
   llama.cpp Vulkan build + Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf are already on this
   host (portable prototype). Use scripts/start_llama_server_win.sh with --jinja
   (required for the Hermes 2 Pro template's tool-call + reasoning_content
   behavior -- see T0.2, changelog 2026-06-03 2305).
   GOTCHA (changelog 2026-06-03): start_llama_server_win.sh does NOT survive being
   launched via `bash.exe scripts/...` from PowerShell -- the backgrounded server
   is torn down when the launching shell exits. Run it FOREGROUND in a dedicated
   window until a real detach / service wrapper exists.
2. With both up, POST to /v1/chat/completions: a "chat" topic should apply the
   no_think preset; a "science"/"coding"/"math"/"research" topic should apply the
   think preset (verify via /chat debug `sampling_preset`).
3. Then T2.2: wire `enable_thinking` via `chat_template_kwargs` (or keep the
   current /think//no_think prefix as fallback). Gate: trivial query -> no
   <think>; non-trivial -> <think>. Note T0.2 showed llama.cpp puts reasoning in a
   separate `reasoning_content` field under --jinja, so re-scope T2.4 (the user
   channel is already <think>-free server-side).

Also still open (from earlier handoffs):
- T1 close-out on a live host: create env_hermes + install hermes-agent (so
  doctor.sh reports env_hermes_installed=yes). Note: Hermes wants Python 3.11, NOT
  the portable 3.14 -- and NOT the services interpreter either; it provisions its
  own env.
- H1 validation: confirm exact Hermes config.yaml key paths (model.sampling.*,
  tools.disabled) against the installed hermes-agent.
- API gaps (2026-06-03 code read): streaming vs `stream` field; /chat_submit stub;
  blocking /agent/run; prompt_tokens hardcoded 0.

## 7. Commit guidance (git runs Windows-side)

    $env:Path = "D:\Projects\Tools\PortableGit\cmd;" + $env:Path
    cd D:\Projects\Git\Project_Persona
    git add scripts/ services/api/server.py run/config.env docs/ knowledge.md todo.md changelog.md archive/handoffs/
    git status
    git commit -m "T2.1 sampling presets + portable 3.11.9 services env (validated) + compat report"

Notes: run/config.env is git-allowlisted (no secrets). portable/ and env_hermes/
are gitignored. The mount blocks deletes, so the now-superseded
requirements-py314*.txt files remain as 3.14-fallback reference only.

---

Frozen handoff record. Future revisions create a new dated handoff.
