import os
import time
import httpx
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel

LLAMA_HOST = os.getenv("LLAMA_HOST", "127.0.0.1")

PERSONA_PORT = int(os.getenv("PERSONA_PORT", "8080"))
SCIENTIST_PORT = int(os.getenv("SCIENTIST_PORT", "8081"))

PERSONA_URL = f"http://{LLAMA_HOST}:{PERSONA_PORT}/completion"
SCIENTIST_URL = f"http://{LLAMA_HOST}:{SCIENTIST_PORT}/completion"

# IMPORTANT: default OFF to avoid CPU contention / stalls
ASYNC_SCIENTIST_ENABLED = os.getenv("ASYNC_SCIENTIST_ENABLED", "0") == "1"

# Topics that qualify for async deep work (when enabled)
ASYNC_SCIENTIST_TOPICS = {
    t.strip().lower()
    for t in os.getenv("ASYNC_SCIENTIST_TOPICS", "science,biology,coding,math").split(",")
    if t.strip()
}

app = FastAPI()
client = httpx.AsyncClient(timeout=300)

# Allow only 1 scientist job at a time
scientist_lock = asyncio.Semaphore(1)


class ChatRequest(BaseModel):
    text: str
    topic: str = "chat"
    profile: str = "default"
    debug: bool = False


async def query_llama(url: str, prompt: str, tokens: int):
    start = time.time()
    r = await client.post(url, json={
        "prompt": prompt,
        "n_predict": tokens,
        "temperature": 0.7,
    })
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


async def scientist_worker(question: str):
    async with scientist_lock:
        prompt = f"""You are a scientific research and coding assistant.

Write concise bullet-point notes. Focus on correctness and actionable detail.

Question:
{question}
"""
        # scientist can be longer
        await query_llama(SCIENTIST_URL, prompt, tokens=512)


@app.post("/chat")
async def chat(req: ChatRequest):
    topic = (req.topic or "chat").strip().lower()

    scientist_started = False
    scientist_reason = "disabled"
    notes = ""

    should_deep = (topic in ASYNC_SCIENTIST_TOPICS)

    if ASYNC_SCIENTIST_ENABLED and should_deep:
        # fire-and-forget (but concurrency-limited)
        asyncio.create_task(scientist_worker(req.text))
        scientist_started = True
        scientist_reason = "enabled_and_topic_match"
        notes = "Background analysis started."
    else:
        if not ASYNC_SCIENTIST_ENABLED:
            scientist_reason = "disabled"
        elif not should_deep:
            scientist_reason = "topic_not_in_allowlist"

    # Keep persona prompt minimal to reduce wasted tokens + leakage
    persona_prompt = f"""You are a helpful assistant.

User:
{req.text}

Assistant:
"""

    reply, stats = await query_llama(PERSONA_URL, persona_prompt, tokens=192)

    debug = {}
    if req.debug:
        debug = {
            "persona_stats": stats,
            "async_scientist_enabled": ASYNC_SCIENTIST_ENABLED,
            "async_scientist_topics": sorted(list(ASYNC_SCIENTIST_TOPICS)),
            "scientist_async_started": scientist_started,
            "scientist_reason": scientist_reason,
            "persona_endpoint": PERSONA_URL,
            "scientist_endpoint": SCIENTIST_URL,
        }

    return {
        "text": reply,
        "persona": True,
        "scientist_async": scientist_started,
        "debug": debug
    }
