# Python 3.14 compatibility report -- Project_Persona stack

Last updated: 2026-06-05 0128 UTC by Claude

Context: a Windows embeddable CPython 3.14 was added at
`portable/python/` (python.exe + python314.dll + python314.zip + python314._pth).
This validates whether the stack's components run on 3.14 before a bootstrap is
built. Target platform: Windows x86-64 (win_amd64), matching the EVO-X2 and the
RX 9060 XT prototype.

## Headline

The FastAPI companion API and the T2.1 sampling work run on Python 3.14. The ONLY
hard blocker is ChromaDB (the RAG vector store), which cannot install/import on
3.14. Because server.py imports ChromaDB fail-soft, the API still runs on 3.14
with the Chroma RAG layer disabled.

Separately: Hermes Agent targets Python 3.11 (its installer provisions 3.11), so
`env_hermes` should NOT be pointed at this 3.14 interpreter. The 3.14 portable is
for the API/services only.

## Decision (2026-06-05)

Services interpreter: Python 3.11.9, Windows x86-64, embeddable zip, kept in
`portable/python/` (portable by design). 3.11.9 is the LAST 3.11 with official
binary packages -- 3.11 is in security-only / source-only mode since then (PEP
664, supported to Oct 2027), so 3.11.10+ have no python.org installers/embeddable.
3.11 runs the COMPLETE stack including ChromaDB RAG, and matches the version
Hermes uses (in its own isolated env_hermes). Acceptable security trade: this
stack is localhost-only and offline by design, so the post-3.11.9 CVEs (network
parsing, etc.) are largely out of the threat model.

Install path: the embeddable build has no pip/venv, so use
`scripts/bootstrap_portable_python.ps1` (enables site in python311._pth, get-pip,
installs the committed `services/api/requirements.txt` full stack; `-CoreOnly`
for an API-only install; `-Run` to launch uvicorn).

## Recommended interpreter version (analysis)

For COMPLETE single-interpreter support of the whole stack (API + ChromaDB RAG),
use Python 3.11 or 3.12, Windows x86-64. Every dependency -- chromadb,
onnxruntime, fastembed, pydantic-core, grpcio, tokenizers, numpy -- has clean
3.11/3.12 wheels with no caveats. 3.11 was chosen (see Decision above).

- 3.12 -- recommended. Rock-solid across the entire stack, RAG included.
- 3.13 -- likely works (chromadb 1.5.9 ships an abi3 core), but has documented
  rough edges with chromadb (numpy>2 issues, intermittent install failures on
  3.13.x). Acceptable, slightly riskier.
- 3.14 -- the build currently in portable/. API/services only; ChromaDB RAG is
  blocked (see below). Fine for the API + T2 work with RAG disabled.
- 3.11 -- what Hermes Agent uses (its own env_hermes, provisioned by the Hermes
  installer). Not the services interpreter.

Prefer the FULL Windows x64 build/installer over the embeddable package for the
services interpreter: the embeddable build has no pip/venv and needs a get-pip
bootstrap (handled by scripts/bootstrap_portable_python.ps1 if you keep the
portable/embeddable route). A full 3.12 install gives venv + pip out of the box.

## Per-dependency status (as of 2026-06-05, win_amd64)

Core (required to run server.py):
- fastapi -- pure Python. OK on 3.14.
- uvicorn[standard] -- OK. httptools 0.8.0 ships cp314 wheels; uvloop is
  non-Windows (skipped on Windows anyway); websockets has 3.14 wheels.
- pydantic / pydantic-core -- OK. pydantic-core 2.47.0 (2026-05-22) ships cp314
  Windows wheels; use pydantic >= 2.12.
- httpx -- pure Python (+ httpcore/h11). OK on 3.14.
- tenacity -- pure Python. OK on 3.14.

Optional (RAG):
- onnxruntime -- OK. 1.26.0 (2026-05-08) ships cp314 win_amd64 wheels
  (onnxruntime-1.26.0-cp314-cp314-win_amd64.whl).
- grpcio -- OK on 3.14 (since 2026-02).
- tokenizers -- OK. 0.22.2 ships cp39-abi3 wheels (stable ABI, forward-compatible
  with 3.14).
- numpy -- OK on 3.14 (2.x).
- fastembed -- OK now. Its only 3.14 blocker was onnxruntime, resolved by
  onnxruntime 1.26.0. Pulls onnxruntime + tokenizers + numpy, all 3.14-ready.
- chromadb -- BLOCKED on 3.14. Latest 1.5.9 (2026-05-05) still depends on
  `pypika`, which uses `ast.Str` (removed in Python 3.14), so it fails to
  install/import. No 3.14 wheels. This is the single hard blocker.

Other components (non-pip):
- llama.cpp -- standalone binary, no Python coupling. Unaffected by the Python
  version.
- Hermes Agent -- wants Python 3.11 (separate env_hermes). Not a 3.14 concern.

## Consequence for the stack

Running the API on 3.14 works with RAG's vector store off (fail-soft import).
fastembed (the embedder) imports fine, but RAG end-to-end needs a vector store;
ChromaDB is the blocker.

Mitigations, in order of preference:
1. Run core on 3.14 with Chroma RAG disabled (RAG_ENABLED gates it; the import is
   already fail-soft). Lets the API + T2 work proceed on the portable 3.14 now.
2. Accelerate the planned Qdrant migration (Phase 2a in knowledge.md). qdrant-client
   is pure Python and 3.14-OK, and fastembed (also by Qdrant) is 3.14-OK -- so
   Qdrant + fastembed is a fully-3.14-compatible RAG path, unlike Chroma. The 3.14
   block is a concrete nudge to bring Phase 2a forward.
3. Keep Chroma RAG on a Python 3.11/3.12 interpreter until chromadb/pypika ship a
   3.14 fix (upstream tracking exists; no ETA).

## requirements files

`services/api/requirements.txt` (committed) is the full tested stack: fastapi,
uvicorn[standard], pydantic, httpx, tenacity, chromadb, numpy, fastembed,
sentence-transformers. It installs cleanly on the chosen Python 3.11.9 -- this is
what the bootstrap installs. Note: `chromadb>=0.5.0,<1.0.0` is an INTENTIONAL API
pin (server.py targets the chromadb 0.5.x client API), not staleness; do not bump
it to 1.x without porting server.py's chromadb usage. `pydantic>=2.7,<3` is fine
on 3.11.

3.14-fallback only (NOT used on 3.11): `services/api/requirements-py314.txt`
(core: fastapi/uvicorn/pydantic/httpx/tenacity) and
`services/api/requirements-py314-rag.txt` (fastembed/onnxruntime, ChromaDB omitted
because it cannot install on 3.14). These exist solely as the reference set for
the API-only-on-3.14 scenario.

## Sources

- onnxruntime 1.26.0 cp314 win_amd64: https://pypi.org/project/onnxruntime/ ;
  https://github.com/microsoft/onnxruntime/issues/26473
- pydantic-core 2.47.0 cp314: https://pypi.org/project/pydantic-core/ ;
  https://pyreadiness.org/3.14/
- httptools 0.8.0 cp314: https://pypi.org/project/httptools/
- grpcio 3.14: https://pypi.org/project/grpcio/
- tokenizers 0.22.2 abi3: https://pypi.org/project/tokenizers/
- fastembed 3.14 (gated on onnxruntime): https://github.com/qdrant/fastembed/issues/576
- chromadb 1.5.9 / pypika ast.Str 3.14 block:
  https://github.com/chroma-core/chroma/issues/5643 ;
  https://github.com/basnijholt/agent-cli/issues/199
- Hermes Agent Python 3.11: https://hermes-agent.nousresearch.com/docs/getting-started/installation
