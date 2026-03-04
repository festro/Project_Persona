import os
import time
import uuid
import asyncio
import re
import json
from typing import Dict, Any, Optional, List, Literal, AsyncGenerator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Optional deps (fail soft)
try:
    import chromadb
    from chromadb.config import Settings
except Exception:
    chromadb = None
    Settings = None

try:
    from fastembed import TextEmbedding
except Exception:
    TextEmbedding = None


# -----------------------
# Config
# -----------------------
AI_ROOT = os.getenv("AI_ROOT", os.path.expanduser("~/AI"))
PERSONA_ROOT = os.getenv("PERSONA_ROOT", os.path.join(AI_ROOT, "persona"))
PROFILES_DIR = os.getenv("PROFILES_DIR", os.path.join(PERSONA_ROOT, "profiles"))
GLOBAL_MEMORY_DIR = os.getenv("GLOBAL_MEMORY_DIR", os.path.join(PERSONA_ROOT, "global_memory"))

LLAMA_HOST = os.getenv("LLAMA_HOST", "127.0.0.1")
PERSONA_PORT = int(os.getenv("PERSONA_PORT", "8080"))
SCIENTIST_PORT = int(os.getenv("SCIENTIST_PORT", "8081"))

PERSONA_URL = f"http://{LLAMA_HOST}:{PERSONA_PORT}/completion"
SCIENTIST_URL = f"http://{LLAMA_HOST}:{SCIENTIST_PORT}/completion"

# Feature toggles
ASYNC_SCIENTIST_ENABLED = os.getenv("ASYNC_SCIENTIST_ENABLED", "0") == "1"
ASYNC_SCIENTIST_TOPICS = {
    t.strip().lower()
    for t in os.getenv("ASYNC_SCIENTIST_TOPICS", "science,biology,coding,math").split(",")
    if t.strip()
}

RAG_ENABLED = os.getenv("RAG_ENABLED", "0") == "1"
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

PERSONA_MAX_TOKENS = int(os.getenv("PERSONA_MAX_TOKENS", "192"))
SCIENTIST_MAX_TOKENS = int(os.getenv("SCIENTIST_MAX_TOKENS", "512"))

PERSONA_TIMEOUT_S = float(os.getenv("PERSONA_TIMEOUT_S", "120"))
SCIENTIST_TIMEOUT_S = float(os.getenv("SCIENTIST_TIMEOUT_S", "600"))

# If scientist fails, optionally fall back to persona to produce structured notes
SCIENTIST_FALLBACK_TO_PERSONA = os.getenv("SCIENTIST_FALLBACK_TO_PERSONA", "0") == "1"

GLOBAL_CHROMA_DIR = os.path.join(GLOBAL_MEMORY_DIR, "chroma")
os.makedirs(GLOBAL_CHROMA_DIR, exist_ok=True)
os.makedirs(PROFILES_DIR, exist_ok=True)

# -----------------------
# Safe init: embeddings + chroma
# -----------------------
_embedder = None
_embedder_error: Optional[str] = None

if TextEmbedding is None:
    _embedder_error = "fastembed_not_available"
else:
    try:
        _embedder = TextEmbedding(model_name=EMBED_MODEL)
        _ = list(_embedder.embed(["warmup"]))[0]
    except Exception as e:
        _embedder = None
        _embedder_error = f"embedder_init_failed: {repr(e)}"

_chroma_ok = False
_chroma_error: Optional[str] = None
_collection = None

if chromadb is None:
    _chroma_error = "chromadb_not_available"
else:
    try:
        _client_chroma = chromadb.PersistentClient(
            path=GLOBAL_CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False) if Settings else None
        )
        _collection = _client_chroma.get_or_create_collection("global_memory")
        _chroma_ok = True
    except Exception as e:
        _chroma_ok = False
        _chroma_error = f"chroma_init_failed: {repr(e)}"


def _embed(text: str) -> List[float]:
    if _embedder is None:
        raise RuntimeError(_embedder_error or "embedder_unavailable")
    return list(_embedder.embed([text]))[0].tolist()


def memory_add(text: str, meta: Dict[str, Any]) -> None:
    if not _chroma_ok or _collection is None:
        return
    if _embedder is None:
        return
    try:
        vec = _embed(text)
        _collection.add(
            ids=[str(uuid.uuid4())],
            documents=[text],
            embeddings=[vec],
            metadatas=[meta],
        )
    except Exception:
        return


def memory_query(text: str, k: int) -> str:
    if not _chroma_ok or _collection is None:
        return ""
    if _embedder is None:
        return ""
    try:
        vec = _embed(text)
        res = _collection.query(query_embeddings=[vec], n_results=k, include=["documents"])
        docs = (res.get("documents") or [[]])[0]
        docs = [d.strip() for d in docs if isinstance(d, str) and d.strip()]
        return "\n".join(docs[:k])
    except Exception:
        return ""


# -----------------------
# FastAPI
# -----------------------
app = FastAPI()

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": repr(exc)},
    )

http = httpx.AsyncClient()

# Prevent runaway: one scientist job at a time
scientist_lock = asyncio.Lock()

# Allow multiple persona jobs concurrently, but cap to avoid overload
PERSONA_CONCURRENCY = int(os.getenv("PERSONA_CONCURRENCY", "2"))
persona_sem = asyncio.Semaphore(PERSONA_CONCURRENCY)

# In-memory job store (persona + scientist)
jobs: Dict[str, Dict[str, Any]] = {}


# -----------------------
# Request Models
# -----------------------
class ChatRequest(BaseModel):
    text: str
    topic: str = "chat"
    profile: str = "default"
    debug: bool = False

class SubmitRequest(BaseModel):
    text: str
    topic: str = "chat"
    profile: str = "default"
    debug: bool = False

# Minimal OpenAI-compatible schema (enough for OpenWebUI)
class OA_Message(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str

class OA_ChatCompletionsReq(BaseModel):
    model: str = "project_persona"
    messages: List[OA_Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    topic: Optional[str] = None
    profile: Optional[str] = None
    debug: Optional[bool] = False


# -----------------------
# Llama helpers
# -----------------------
async def query_llama(
    url: str,
    prompt: str,
    tokens: int,
    temperature: float,
    timeout_s: float,
    extra: Optional[Dict[str, Any]] = None
):
    start = time.time()
    payload: Dict[str, Any] = {"prompt": prompt, "n_predict": tokens, "temperature": temperature}
    if extra:
        payload.update(extra)

    r = await http.post(url, json=payload, timeout=httpx.Timeout(timeout_s))
    r.raise_for_status()
    latency = time.time() - start
    data = r.json()
    content = (data.get("content") or "").strip()
    tokens_generated = int(data.get("tokens_predicted") or 0)
    tps = (tokens_generated / latency) if latency > 0 else 0.0
    return content, {
        "latency_ms": round(latency * 1000, 2),
        "tokens_generated": tokens_generated,
        "tokens_per_second": round(tps, 2),
    }


async def stream_llama(
    url: str,
    prompt: str,
    tokens: int,
    temperature: float,
    timeout_s: float,
    extra: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[str, None]:
    """
    Streams llama-server /completion output.
    Modern llama.cpp server supports JSON SSE-like lines when {"stream": true}.
    We yield text deltas as they arrive.

    If the upstream doesn't actually stream, caller may fall back to non-streaming.
    """
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "n_predict": tokens,
        "temperature": temperature,
        "stream": True,
    }
    if extra:
        payload.update(extra)

    timeout = httpx.Timeout(timeout_s, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            # Read line-by-line. llama.cpp often sends "data: {...}" lines.
            async for raw in resp.aiter_lines():
                if not raw:
                    continue
                line = raw.strip()
                if line.startswith("data:"):
                    line = line[len("data:"):].strip()

                if line == "[DONE]":
                    break

                # Some builds send pure JSON per line; others may send partials.
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                # Try common keys
                delta = obj.get("content")
                if delta is None:
                    # Sometimes: {"choices":[{"delta":{"content":"..."}}]}
                    choices = obj.get("choices")
                    if isinstance(choices, list) and choices:
                        delta = (choices[0].get("delta") or {}).get("content")
                if not delta:
                    continue
                yield str(delta)


def build_persona_prompt(user_text: str, rag_context: str) -> str:
    prompt = f"""You are a helpful assistant.

User:
{user_text}

"""
    if rag_context:
        prompt += f"\n(Internal context: retrieved memory)\n{rag_context}\n\n"
    prompt += "Assistant:\n"
    return prompt


def _normalize(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def looks_degenerate(text: str) -> bool:
    t = _normalize(text)
    if len(t) < 120:
        return True
    quote_ratio = (t.count('"') + t.count("'")) / max(1, len(t))
    if quote_ratio > 0.02:
        return True
    words = t.split()
    if len(words) < 25:
        return True
    uniq_ratio = len(set(words)) / max(1, len(words))
    if uniq_ratio < 0.45:
        return True
    bigrams = [" ".join(words[i:i+2]) for i in range(len(words) - 1)]
    if bigrams and max(bigrams.count(x) for x in set(bigrams)) >= 6:
        return True
    trigrams = [" ".join(words[i:i+3]) for i in range(len(words) - 2)]
    if trigrams and max(trigrams.count(x) for x in set(trigrams)) >= 4:
        return True
    for w in ("gene", "user", "system", "crispr", "c2"):
        if f"{w} {w} {w}" in t:
            return True
    return False


def has_required_scientist_sections(md: str) -> bool:
    needed = ["## TL;DR", "## Key points", "## Risks / pitfalls", "## How to verify", "## Next actions"]
    return all(s in md for s in needed)


def scientist_template(question: str) -> str:
    return f"""You are "Scientist", a careful research + reasoning assistant.

Output MUST be Markdown with these exact sections:

## TL;DR
- (1–3 bullets)

## Key points
- (5–10 bullets)

## Risks / pitfalls
- (3–8 bullets)

## How to verify
- (3–8 bullets)

## Next actions
- (3–6 bullets)

Rules:
- NO repetition or filler.
- If uncertain about a claim, say so briefly.

User question:
{question}
"""


# -----------------------
# Workers
# -----------------------
async def persona_worker(job_id: str, profile: str, topic: str, question: str):
    async with persona_sem:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_ts"] = int(time.time())

        rag_context = ""
        rag_used = False
        if RAG_ENABLED:
            rag_context = memory_query(question, k=RAG_TOP_K)
            rag_used = bool(rag_context)

        persona_prompt = build_persona_prompt(question, rag_context)
        reply, stats = await query_llama(PERSONA_URL, persona_prompt, PERSONA_MAX_TOKENS, 0.7, PERSONA_TIMEOUT_S)

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["completed_ts"] = int(time.time())
        jobs[job_id]["result"] = reply
        jobs[job_id]["stats"] = stats
        jobs[job_id]["rag_used"] = rag_used


async def scientist_worker(job_id: str, profile: str, topic: str, question: str):
    async with scientist_lock:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_ts"] = int(time.time())

        base_prompt = scientist_template(question)

        notes, _ = await query_llama(
            SCIENTIST_URL, base_prompt, SCIENTIST_MAX_TOKENS, 0.2, SCIENTIST_TIMEOUT_S,
            extra={"top_p": 0.9, "repeat_penalty": 1.15},
        )

        if looks_degenerate(notes) or (not has_required_scientist_sections(notes)):
            repair_prompt = f"""Rewrite the following into the required Markdown template EXACTLY.

You MUST output ONLY Markdown with these sections, in this order:
## TL;DR
## Key points
## Risks / pitfalls
## How to verify
## Next actions

Remove repetition, remove nonsense, keep it factual and concise.

SOURCE TEXT:
{notes}

QUESTION:
{question}
"""
            notes2, _ = await query_llama(
                SCIENTIST_URL, repair_prompt, SCIENTIST_MAX_TOKENS, 0.0, SCIENTIST_TIMEOUT_S,
                extra={"top_p": 0.7, "repeat_penalty": 1.25},
            )
            notes = notes2

        if looks_degenerate(notes) or (not has_required_scientist_sections(notes)):
            if SCIENTIST_FALLBACK_TO_PERSONA:
                fb_prompt = scientist_template(question) + "\n(Important: follow the template strictly.)\n"
                fb, _ = await query_llama(
                    PERSONA_URL, fb_prompt, SCIENTIST_MAX_TOKENS, 0.2, PERSONA_TIMEOUT_S,
                    extra={"top_p": 0.9, "repeat_penalty": 1.15},
                )
                if (not looks_degenerate(fb)) and has_required_scientist_sections(fb):
                    notes = fb
                    jobs[job_id]["fallback_used"] = "persona"
                else:
                    jobs[job_id]["status"] = "failed"
                    jobs[job_id]["completed_ts"] = int(time.time())
                    jobs[job_id]["error"] = "degenerate_or_unstructured_scientist_output"
                    jobs[job_id]["result"] = None
                    return
            else:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["completed_ts"] = int(time.time())
                jobs[job_id]["error"] = "degenerate_or_unstructured_scientist_output"
                jobs[job_id]["result"] = None
                return

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["completed_ts"] = int(time.time())
        jobs[job_id]["result"] = notes

        memory_add(
            f"[scientist_notes]\n{notes}",
            {"source": "scientist", "job_id": job_id, "profile": profile, "topic": topic, "ts": int(time.time())},
        )


# -----------------------
# Routes
# -----------------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "persona_endpoint": PERSONA_URL,
        "scientist_endpoint": SCIENTIST_URL,
        "async_scientist_enabled": ASYNC_SCIENTIST_ENABLED,
        "rag_enabled": RAG_ENABLED,
        "embedder_ok": _embedder is not None,
        "embedder_error": _embedder_error,
        "chroma_ok": _chroma_ok,
        "chroma_error": _chroma_error,
        "persona_concurrency": PERSONA_CONCURRENCY,
        "scientist_fallback_to_persona": SCIENTIST_FALLBACK_TO_PERSONA,
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    profile = (req.profile or "default").strip()
    topic = (req.topic or "chat").strip().lower()

    rag_context = ""
    rag_used = False
    if RAG_ENABLED:
        rag_context = memory_query(req.text, k=RAG_TOP_K)
        rag_used = bool(rag_context)

    persona_prompt = build_persona_prompt(req.text, rag_context)
    reply, stats = await query_llama(PERSONA_URL, persona_prompt, PERSONA_MAX_TOKENS, 0.7, PERSONA_TIMEOUT_S)

    scientist_job = None
    scientist_reason = "disabled"
    if ASYNC_SCIENTIST_ENABLED and topic in ASYNC_SCIENTIST_TOPICS:
        if scientist_lock.locked():
            scientist_reason = "busy_inflight"
        else:
            scientist_job = str(uuid.uuid4())
            jobs[scientist_job] = {
                "kind": "scientist",
                "status": "queued",
                "question": req.text,
                "profile": profile,
                "topic": topic,
                "created_ts": int(time.time()),
                "result": None,
            }
            asyncio.create_task(scientist_worker(scientist_job, profile, topic, req.text))
            scientist_reason = "started"

    debug = {}
    if req.debug:
        debug = {
            "persona_stats": stats,
            "rag_enabled": RAG_ENABLED,
            "rag_used": rag_used,
            "scientist_job": scientist_job,
            "scientist_reason": scientist_reason,
        }

    return {"text": reply, "persona": True, "scientist_job": scientist_job, "debug": debug}


@app.post("/chat_submit")
async def chat_submit(req: SubmitRequest):
    profile = (req.profile or "default").strip()
    topic = (req.topic or "chat").strip().lower()

    persona_job = str(uuid.uuid4())
    jobs[persona_job] = {
        "kind": "persona",
        "status": "queued",
        "question": req.text,
        "profile": profile,
        "topic": topic,
        "created_ts": int(time.time()),
        "result": None,
    }
    asyncio.create_task(persona_worker(persona_job, profile, topic, req.text))

    scientist_job = None
    scientist_reason = "disabled"
    if ASYNC_SCIENTIST_ENABLED and topic in ASYNC_SCIENTIST_TOPICS:
        if scientist_lock.locked():
            scientist_reason = "busy_inflight"
        else:
            scientist_job = str(uuid.uuid4())
            jobs[scientist_job] = {
                "kind": "scientist",
                "status": "queued",
                "question": req.text,
                "profile": profile,
                "topic": topic,
                "created_ts": int(time.time()),
                "result": None,
            }
            asyncio.create_task(scientist_worker(scientist_job, profile, topic, req.text))
            scientist_reason = "started"

    debug = {}
    if req.debug:
        debug = {
            "persona_job": persona_job,
            "scientist_job": scientist_job,
            "scientist_reason": scientist_reason,
        }

    return {"persona_job": persona_job, "scientist_job": scientist_job, "debug": debug}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


# -----------------------
# OpenAI-compatible endpoints (for OpenWebUI)
# -----------------------
@app.get("/v1/models")
async def v1_models():
    return {
        "object": "list",
        "data": [
            {"id": "project_persona", "object": "model", "created": int(time.time()), "owned_by": "local"},
        ],
    }


def _messages_to_text(messages: List[OA_Message]) -> str:
    parts: List[str] = []
    for m in messages:
        if m.role == "system":
            parts.append(f"[system]\n{m.content}")
        elif m.role == "user":
            parts.append(f"[user]\n{m.content}")
        elif m.role == "assistant":
            parts.append(f"[assistant]\n{m.content}")
    return "\n\n".join(parts).strip()


def _sse(data: str) -> str:
    return f"data: {data}\n\n"


@app.post("/v1/chat/completions")
async def v1_chat_completions(req: OA_ChatCompletionsReq):
    user_text = _messages_to_text(req.messages)

    rag_context = ""
    if RAG_ENABLED:
        rag_context = memory_query(user_text, k=RAG_TOP_K)
    persona_prompt = build_persona_prompt(user_text, rag_context)

    max_tokens = int(req.max_tokens or PERSONA_MAX_TOKENS)
    temperature = float(req.temperature) if req.temperature is not None else 0.7

    model_id = req.model or "project_persona"
    created = int(time.time())
    resp_id = f"chatcmpl-{uuid.uuid4().hex}"

    # Streaming path (OpenAI SSE)
    if req.stream:
        async def gen() -> AsyncGenerator[str, None]:
            # First chunk: establish assistant role
            first = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_id,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            yield _sse(json.dumps(first))

            # Try true upstream streaming
            streamed_any = False
            try:
                async for delta in stream_llama(
                    PERSONA_URL,
                    persona_prompt,
                    tokens=max_tokens,
                    temperature=temperature,
                    timeout_s=PERSONA_TIMEOUT_S,
                    extra={"top_p": 0.9, "repeat_penalty": 1.10},
                ):
                    streamed_any = True
                    chunk = {
                        "id": resp_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_id,
                        "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                    }
                    yield _sse(json.dumps(chunk))
            except Exception:
                # If upstream streaming fails, fall back to non-streaming but still emit chunks so UI doesn't break.
                streamed_any = False

            if not streamed_any:
                # Fallback: one-shot completion, then chunk it (best-effort UX)
                full, _ = await query_llama(
                    PERSONA_URL, persona_prompt, max_tokens, temperature, PERSONA_TIMEOUT_S,
                    extra={"top_p": 0.9, "repeat_penalty": 1.10},
                )
                # chunk into ~50 char pieces
                step = 50
                for i in range(0, len(full), step):
                    piece = full[i:i+step]
                    chunk = {
                        "id": resp_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_id,
                        "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
                    }
                    yield _sse(json.dumps(chunk))

            # Final chunk
            final = {
                "id": resp_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_id,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield _sse(json.dumps(final))
            yield _sse("[DONE]")

        return StreamingResponse(gen(), media_type="text/event-stream")

    # Non-streaming path
    reply, stats = await query_llama(
        PERSONA_URL,
        persona_prompt,
        max_tokens,
        temperature,
        PERSONA_TIMEOUT_S,
        extra={"top_p": 0.9, "repeat_penalty": 1.10},
    )

    return {
        "id": resp_id,
        "object": "chat.completion",
        "created": created,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": int(stats.get("tokens_generated", 0)),
            "total_tokens": int(stats.get("tokens_generated", 0)),
        },
    }
