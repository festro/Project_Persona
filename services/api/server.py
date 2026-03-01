"""
AI Companion API (Native) — Persona + Silent Experts + RAG + AUTO_BUDGET (fixed)
- Persona always responds in-character.
- Optional silent expert consult (reasoning/coder).
- True persistent memory: profile + global (ChromaDB).
- AUTO_BUDGET:
    * Respects strict=false for chat/general (no expert).
    * Enforces expert timeouts (httpx timeout + asyncio.wait_for).
    * Picks budgets based on topic + prompt complexity.
"""

from __future__ import annotations

import os
import re
import time
import json
import uuid
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple, List

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# =============================================================================
# Logging
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("ai-api")

# =============================================================================
# Paths / Config
# =============================================================================
AI_ROOT = os.environ.get("AI_ROOT", os.path.expanduser("~/AI"))

PERSONA_DIR = os.path.join(AI_ROOT, "persona")
PROFILES_DIR = os.path.join(PERSONA_DIR, "profiles")
GLOBAL_DIR = os.path.join(PERSONA_DIR, "global_memory")

DEFAULT_PROFILE = os.environ.get("DEFAULT_PROFILE", "default")

# llama.cpp servers
HOST = os.environ.get("LLAMA_HOST", "127.0.0.1")
PERSONA_PORT = int(os.environ.get("PERSONA_PORT", "8080"))
REASONING_PORT = int(os.environ.get("REASONING_PORT", "8081"))
CODER_PORT = int(os.environ.get("CODER_PORT", "8082"))

# Embeddings / RAG
EMBEDDER_MODE = os.environ.get("EMBEDDER_MODE", "fastembed")  # "fastembed" recommended
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# Memory knobs
TOP_K_PROFILE = int(os.environ.get("TOP_K_PROFILE", "6"))
TOP_K_GLOBAL = int(os.environ.get("TOP_K_GLOBAL", "4"))
MIN_SCORE = float(os.environ.get("MIN_SCORE", "0.15"))

# AUTO_BUDGET knobs
PLANNER_ENABLED = os.environ.get("AUTO_BUDGET", "1").strip() not in ("0", "false", "False")
PLANNER_MAX_MS = int(os.environ.get("PLANNER_MAX_MS", "4000"))  # cap planner compute time (not LLM time)

# =============================================================================
# ChromaDB setup
# =============================================================================
chroma_client = None
try:
    import chromadb
    from chromadb.config import Settings

    os.makedirs(GLOBAL_DIR, exist_ok=True)
    chroma_client = chromadb.PersistentClient(
        path=os.path.join(GLOBAL_DIR, "chroma"),
        settings=Settings(anonymized_telemetry=False),
    )
    log.info("ChromaDB initialized (global) at %s", os.path.join(GLOBAL_DIR, "chroma"))
except Exception as e:
    chroma_client = None
    log.warning("ChromaDB not initialized (%s). RAG endpoints may fail.", e)

# =============================================================================
# Embedder (fastembed)
# =============================================================================
embedder = None
embed_dim = None

def _init_embedder():
    global embedder, embed_dim
    if embedder is not None:
        return
    if EMBEDDER_MODE == "fastembed":
        try:
            from fastembed import TextEmbedding
            embedder = TextEmbedding(model_name=EMBED_MODEL)
            # infer dim from a single embedding
            v = list(embedder.embed(["ping"]))[0]
            embed_dim = len(v)
            log.info("Embedder ready: %s (dim=%s)", EMBED_MODEL, embed_dim)
        except Exception as e:
            embedder = None
            embed_dim = None
            log.warning("fastembed not available (%s). Memory search will degrade.", e)
    else:
        log.warning("Unknown EMBEDDER_MODE=%s; memory search will degrade.", EMBEDDER_MODE)

def embed_texts(texts: List[str]) -> List[List[float]]:
    _init_embedder()
    if embedder is None:
        raise RuntimeError("Embedder unavailable. Install fastembed or set EMBEDDER_MODE properly.")
    return [list(v) for v in embedder.embed(texts)]

# =============================================================================
# Profile + global filesystem helpers
# =============================================================================
def ensure_profile(profile: str) -> str:
    profile = (profile or "").strip() or DEFAULT_PROFILE
    path = os.path.join(PROFILES_DIR, profile)
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Unknown profile: {profile}")
    return profile

def profile_paths(profile: str) -> Dict[str, str]:
    base = os.path.join(PROFILES_DIR, profile)
    return {
        "base": base,
        "persona_md": os.path.join(base, "persona.md"),
        "style_md": os.path.join(base, "style.md"),
        "rules_md": os.path.join(base, "system_rules.md"),
        "mem_dir": os.path.join(base, "memory"),
        "mem_chroma": os.path.join(base, "memory", "chroma"),
        "mem_exports": os.path.join(base, "memory", "exports"),
    }

def global_paths() -> Dict[str, str]:
    return {
        "base": GLOBAL_DIR,
        "mem_dir": os.path.join(GLOBAL_DIR, "exports"),
        "mem_chroma": os.path.join(GLOBAL_DIR, "chroma"),
        "mem_exports": os.path.join(GLOBAL_DIR, "exports"),
    }

def read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""
    except Exception as e:
        log.warning("Failed reading %s (%s)", path, e)
        return ""

# =============================================================================
# RAG collections
# =============================================================================
def get_collection(path: str, name: str):
    if chroma_client is None:
        raise RuntimeError("Chroma client unavailable")
    # NOTE: Chroma PersistentClient is bound to one base path.
    # For per-profile, we create separate PersistentClient instances.
    import chromadb
    from chromadb.config import Settings
    os.makedirs(path, exist_ok=True)
    c = chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
    return c.get_or_create_collection(name)

def safe_meta(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chroma metadata values must be str/int/float/bool.
    """
    out: Dict[str, Any] = {}
    for k, v in (meta or {}).items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = json.dumps(v, ensure_ascii=False)
    return out

def rag_add(where: str, profile: Optional[str], text: str, meta: Dict[str, Any]) -> str:
    """
    where: "global" or "profile"
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    doc_id = str(uuid.uuid4())
    emb = embed_texts([text])[0]
    meta = safe_meta(meta)

    if where == "global":
        g = global_paths()
        col = get_collection(g["mem_chroma"], "ai_global_memory")
        col.add(ids=[doc_id], documents=[text], embeddings=[emb], metadatas=[meta])
        # export
        os.makedirs(g["mem_exports"], exist_ok=True)
        with open(os.path.join(g["mem_exports"], f"{doc_id}.json"), "w", encoding="utf-8") as f:
            json.dump({"id": doc_id, "text": text, "meta": meta}, f, ensure_ascii=False, indent=2)
        return doc_id

    if where == "profile":
        prof = ensure_profile(profile or DEFAULT_PROFILE)
        p = profile_paths(prof)
        col = get_collection(p["mem_chroma"], f"ai_profile_memory_{prof}")
        col.add(ids=[doc_id], documents=[text], embeddings=[emb], metadatas=[meta])
        os.makedirs(p["mem_exports"], exist_ok=True)
        with open(os.path.join(p["mem_exports"], f"{doc_id}.json"), "w", encoding="utf-8") as f:
            json.dump({"id": doc_id, "text": text, "meta": meta}, f, ensure_ascii=False, indent=2)
        return doc_id

    raise HTTPException(status_code=400, detail="where must be 'global' or 'profile'")

def rag_search(where: str, profile: Optional[str], query: str, top_k: int, min_score: float) -> List[Dict[str, Any]]:
    if not query.strip():
        return []

    emb = embed_texts([query])[0]

    def _postprocess(res) -> List[Dict[str, Any]]:
        docs = res.get("documents", [[]])[0] or []
        metas = res.get("metadatas", [[]])[0] or []
        dists = res.get("distances", [[]])[0] or []
        out = []
        for doc, meta, dist in zip(docs, metas, dists):
            # Convert distance to a rough similarity in [0..1] for HNSW cosine-like spaces:
            # NOTE: Chroma distances vary by metric; we treat "smaller is better" and map to sim.
            sim = 1.0 / (1.0 + float(dist)) if dist is not None else 0.0
            if sim >= min_score:
                out.append({"text": doc, "meta": meta or {}, "score": round(sim, 4)})
        return out

    if where == "global":
        g = global_paths()
        col = get_collection(g["mem_chroma"], "ai_global_memory")
        res = col.query(
            query_embeddings=[emb],
            n_results=max(1, top_k),
            include=["documents", "metadatas", "distances"],
        )
        return _postprocess(res)

    if where == "profile":
        prof = ensure_profile(profile or DEFAULT_PROFILE)
        p = profile_paths(prof)
        col = get_collection(p["mem_chroma"], f"ai_profile_memory_{prof}")
        res = col.query(
            query_embeddings=[emb],
            n_results=max(1, top_k),
            include=["documents", "metadatas", "distances"],
        )
        return _postprocess(res)

    raise HTTPException(status_code=400, detail="where must be 'global' or 'profile'")

# =============================================================================
# Routing policy
# =============================================================================
TOPIC_POLICY: Dict[str, Dict[str, str]] = {
    "coding":      {"expert": "coder",     "confidence": "HIGH"},
    "code":        {"expert": "coder",     "confidence": "HIGH"},
    "programming": {"expert": "coder",     "confidence": "HIGH"},
    "biology":     {"expert": "reasoning", "confidence": "MEDIUM"},
    "science":     {"expert": "reasoning", "confidence": "MEDIUM"},
    "math":        {"expert": "reasoning", "confidence": "HIGH"},
    "reasoning":   {"expert": "reasoning", "confidence": "HIGH"},
    "analysis":    {"expert": "reasoning", "confidence": "HIGH"},
    "chat":        {"expert": "none",      "confidence": "HIGH"},
    "general":     {"expert": "none",      "confidence": "HIGH"},
}

def policy_for(topic: str) -> Dict[str, str]:
    return TOPIC_POLICY.get(topic, TOPIC_POLICY["chat"])

def body_cue_for(conf: str) -> str:
    return {"HIGH": "confident", "MEDIUM": "thoughtful", "LOW": "cautious"}.get(conf, "neutral")

def expert_port(expert: str) -> int:
    if expert == "reasoning":
        return REASONING_PORT
    if expert == "coder":
        return CODER_PORT
    raise ValueError(f"Unknown expert: {expert}")

# =============================================================================
# HTTP client
# =============================================================================
client: Optional[httpx.AsyncClient] = None

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    # keep a generous default; we override per-request timeouts explicitly
    client = httpx.AsyncClient(timeout=httpx.Timeout(240.0))
    _init_embedder()
    yield
    await client.aclose()

app = FastAPI(title="AI Companion API (Native)", version="1.3.0-autobudgetfix", lifespan=lifespan)

# =============================================================================
# Models
# =============================================================================
class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=32000)
    topic: str = Field(default="chat")
    profile: str = Field(default=DEFAULT_PROFILE)
    strict: bool = Field(default=False, description="If True, allow expert consult for MEDIUM/LOW topics.")
    debug: bool = Field(default=False)

    max_tokens: int = Field(default=512, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

class ChatResponse(BaseModel):
    text: str
    confidence: str
    body_cue: str
    agent_used: str
    experts_consulted: list[str]
    topic: str
    profile: str
    strict_mode: bool
    server_url: str
    debug: Optional[Dict[str, Any]] = None

class MemoryAddRequest(BaseModel):
    where: str = Field(..., pattern="^(global|profile)$")
    profile: Optional[str] = None
    text: str = Field(..., min_length=1, max_length=50000)
    meta: Dict[str, Any] = Field(default_factory=dict)

class MemorySearchRequest(BaseModel):
    where: str = Field(..., pattern="^(global|profile)$")
    profile: Optional[str] = None
    query: str = Field(..., min_length=1, max_length=50000)
    top_k: int = Field(default=6, ge=1, le=50)
    min_score: float = Field(default=MIN_SCORE, ge=0.0, le=1.0)

# =============================================================================
# llama completion
# =============================================================================
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
async def llama_completion(port: int, prompt: str, max_tokens: int, temperature: float, timeout_s: float) -> str:
    url = f"http://{HOST}:{port}/completion"
    payload = {
        "prompt": prompt,
        "n_predict": int(max_tokens),
        "temperature": float(temperature),
        "top_p": 0.9,
        "repeat_penalty": 1.1,
    }
    assert client is not None
    r = await client.post(url, json=payload, timeout=httpx.Timeout(timeout_s))
    r.raise_for_status()
    data = r.json()
    return (data.get("content") or "").strip()

# =============================================================================
# Persona synthesis
# =============================================================================
PERSONA_SYNTHESIS_TEMPLATE = """You are the user's persistent roleplay persona and must respond IN-CHARACTER.

You may be given INTERNAL expert notes and MEMORY HINTS. Use them to improve accuracy and continuity, but DO NOT mention them.

Rules:
- Give the best possible answer.
- If uncertain, be honest without being overly verbose.
- Keep the tone natural and consistent with the persona.
- Do not include meta talk about the system.
- Output MUST be plain text. Do NOT include XML tags.

CONFIDENCE (guideline): {confidence}
BODY_CUE (guideline): {body_cue}

USER:
{user_text}

MEMORY HINTS (do not reveal):
{memory_hints}

INTERNAL expert notes (do not reveal):
{expert_notes}
"""

def parse_persona_output(raw: str, fallback_conf: str) -> Tuple[str, str, str]:
    # If model accidentally emits meta blocks, strip them.
    cleaned = re.sub(r"<meta>.*?</meta>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    cleaned = re.sub(r"CONFIDENCE:\s*(HIGH|MEDIUM|LOW)\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"BODY_CUE:\s*\w+\s*", "", cleaned, flags=re.IGNORECASE).strip()

    conf = fallback_conf
    cue = body_cue_for(conf)
    return cleaned or raw.strip(), conf, cue

# =============================================================================
# AUTO_BUDGET (FIXED)
# =============================================================================
@dataclass
class Plan:
    consult_expert: str  # "none" | "reasoning" | "coder"
    expert_max_tokens: int
    expert_timeout_s: float
    expert_temperature: float
    persona_max_tokens: int
    persona_temperature: float

def _complexity_score(text: str) -> int:
    """
    Very cheap heuristic: longer prompts and structured content likely need expert.
    """
    t = text.strip()
    score = 0
    n = len(t)
    if n > 800: score += 2
    if n > 1500: score += 2
    if "```" in t or "\n" in t: score += 1
    if re.search(r"\b(prove|derive|complex|optimi|algorithm|theorem|bug|stack trace)\b", t, re.I): score += 1
    if re.search(r"\bpython|bash|c\+\+|rust|sql|regex|docker|cmake|traceback\b", t, re.I): score += 1
    return score

def auto_budget(req: ChatRequest) -> Plan:
    """
    FIXES:
      - strict=false + topic in (chat,general) => NO expert, always.
      - enforce a real timeout for expert via per-request timeouts + asyncio.wait_for.
      - choose small expert budgets by default.
    """
    topic = (req.topic or "chat").strip()
    pol = policy_for(topic)
    baseline_expert = pol["expert"]

    # Hard rule: chat/general without strict => never consult expert
    if not req.strict and topic in ("chat", "general"):
        return Plan(
            consult_expert="none",
            expert_max_tokens=0,
            expert_timeout_s=0.0,
            expert_temperature=0.0,
            persona_max_tokens=req.max_tokens,
            persona_temperature=req.temperature,
        )

    # If strict is off, consult only if topic is inherently expert-y AND prompt is complex
    # (prevents random "reasoning" consults on casual prompts)
    score = _complexity_score(req.text)
    consult = "none"

    if req.strict:
        # strict: follow topic policy (coding=>coder, analysis=>reasoning, etc.)
        consult = baseline_expert if baseline_expert != "none" else ("reasoning" if topic in ("analysis", "math", "reasoning", "biology", "science") else "none")
    else:
        # not strict: be conservative (avoid surprise expert calls)
        # coder: only if the prompt looks like it actually contains code/stack traces/etc.
        if topic in ("coding", "code", "programming") and score >= 2:
            consult = "coder"
        # reasoning: only if the prompt is clearly technical/analytical
        elif topic in ("analysis", "math", "reasoning", "biology", "science") and score >= 3:
            consult = "reasoning"
        else:
            consult = "none"

    # Expert budgets
    if consult == "none":
        return Plan(
            consult_expert="none",
            expert_max_tokens=0,
            expert_timeout_s=0.0,
            expert_temperature=0.0,
            persona_max_tokens=req.max_tokens,
            persona_temperature=req.temperature,
        )

    # Keep budgets small, scale slightly with complexity
    base_tokens = 64 if score <= 1 else 96 if score <= 3 else 128
    # Tight timeout. If reasoning is slow, we still cap it.
    timeout_s = 20.0 if score <= 1 else 30.0 if score <= 3 else 45.0

    # Expert temperature slightly higher to encourage idea coverage, but still controlled
    expert_temp = 0.6

    return Plan(
        consult_expert=consult,
        expert_max_tokens=base_tokens,
        expert_timeout_s=timeout_s,
        expert_temperature=expert_temp,
        persona_max_tokens=req.max_tokens,
        persona_temperature=req.temperature,
    )

# =============================================================================
# API endpoints
# =============================================================================
@app.get("/health")
async def health():
    assert client is not None
    servers = {}
    for name, port in [("persona", PERSONA_PORT), ("reasoning", REASONING_PORT), ("coder", CODER_PORT)]:
        url = f"http://{HOST}:{port}/health"
        ok = False
        latency_ms = None
        try:
            t0 = time.time()
            resp = await client.get(url, timeout=httpx.Timeout(2.5))
            latency_ms = round((time.time() - t0) * 1000, 1)
            ok = (resp.status_code == 200)
        except Exception:
            ok = False
        servers[name] = {"url": url, "healthy": ok, "latency_ms": latency_ms}
    status = "healthy" if all(s["healthy"] for s in servers.values()) else "degraded"
    return {"status": status, "servers": servers}

@app.get("/profiles")
def profiles():
    os.makedirs(PROFILES_DIR, exist_ok=True)
    names = sorted([d for d in os.listdir(PROFILES_DIR) if os.path.isdir(os.path.join(PROFILES_DIR, d))])
    return {"default_profile": DEFAULT_PROFILE, "profiles": names}

@app.post("/memory/add")
def memory_add(req: MemoryAddRequest):
    try:
        doc_id = rag_add(req.where, req.profile, req.text, req.meta)
        return {"ok": True, "id": doc_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/memory/search")
def memory_search(req: MemorySearchRequest):
    try:
        hits = rag_search(req.where, req.profile, req.query, req.top_k, req.min_score)
        return {"ok": True, "hits": hits}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    t_all0 = time.time()

    prof = ensure_profile(req.profile)
    pol = policy_for(req.topic)
    baseline_conf = pol["confidence"]

    # Memory retrieval (profile + global)
    mem_t0 = time.time()
    profile_hits: List[Dict[str, Any]] = []
    global_hits: List[Dict[str, Any]] = []
    try:
        profile_hits = rag_search("profile", prof, req.text, TOP_K_PROFILE, MIN_SCORE)
    except Exception as e:
        log.warning("Profile memory retrieval failed (%s): %s", prof, e)
        profile_hits = []
    try:
        global_hits = rag_search("global", None, req.text, TOP_K_GLOBAL, MIN_SCORE)
    except Exception as e:
        log.warning("Global memory retrieval failed: %s", e)
        global_hits = []
    memory_retrieval_ms = round((time.time() - mem_t0) * 1000, 1)

    def _format_hits(hits: List[Dict[str, Any]], label: str, max_items: int) -> str:
        if not hits:
            return f"{label}: (none)"
        lines = [f"{label}:"]
        for h in hits[:max_items]:
            txt = (h.get("text") or "").strip().replace("\n", " ")
            if len(txt) > 400:
                txt = txt[:400] + "…"
            lines.append(f"- ({h.get('score')}) {txt}")
        return "\n".join(lines)

    memory_hints = "\n\n".join([
        _format_hits(profile_hits, "PROFILE MEMORY", 6),
        _format_hits(global_hits, "GLOBAL MEMORY", 4),
    ])

    # Planner (AUTO_BUDGET)
    plan_t0 = time.time()
    plan = auto_budget(req) if PLANNER_ENABLED else Plan(
        consult_expert="none", expert_max_tokens=0, expert_timeout_s=0.0, expert_temperature=0.0,
        persona_max_tokens=req.max_tokens, persona_temperature=req.temperature
    )
    planner_ms = round((time.time() - plan_t0) * 1000, 1)

    consulted: List[str] = []
    expert_notes = "None."
    expert_ms = -1.0

    # Expert consult (enforced timeout)
    if plan.consult_expert != "none":
        consulted.append(plan.consult_expert)
        port = expert_port(plan.consult_expert)
        exp_t0 = time.time()
        try:
            # Enforce timeout at coroutine level too
            expert_text = await asyncio.wait_for(
                llama_completion(
                    port=port,
                    prompt=req.text,
                    max_tokens=plan.expert_max_tokens,
                    temperature=plan.expert_temperature,
                    timeout_s=plan.expert_timeout_s,
                ),
                timeout=plan.expert_timeout_s + 2.0,
            )
            expert_notes = expert_text.strip() if expert_text.strip() else "No useful expert notes."
        except (asyncio.TimeoutError, httpx.ReadTimeout):
            expert_notes = f"Expert timed out ({plan.consult_expert}). Proceed using best effort."
        except Exception as e:
            log.warning("Expert call failed (%s): %s", plan.consult_expert, e)
            expert_notes = f"Expert unavailable ({plan.consult_expert}). Proceed using best effort."
        expert_ms = round((time.time() - exp_t0) * 1000, 1)

    # Persona prompt
    persona_prompt = PERSONA_SYNTHESIS_TEMPLATE.format(
        confidence=baseline_conf,
        body_cue=body_cue_for(baseline_conf),
        user_text=req.text,
        memory_hints=memory_hints,
        expert_notes=expert_notes,
    )

    # Persona completion
    per_t0 = time.time()
    try:
        raw = await llama_completion(
            port=PERSONA_PORT,
            prompt=persona_prompt,
            max_tokens=plan.persona_max_tokens,
            temperature=plan.persona_temperature,
            timeout_s=240.0,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"persona llama server error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"persona llama server unreachable: {e}")
    persona_ms = round((time.time() - per_t0) * 1000, 1)

    reply, conf, cue = parse_persona_output(raw, fallback_conf=baseline_conf)

    # Writeback: store a compact “interaction” into PROFILE memory (keeps it useful)
    writeback_ok = 0
    try:
        snippet = reply.strip().replace("\n", " ")
        if len(snippet) > 800:
            snippet = snippet[:800] + "…"
        rag_add(
            "profile",
            prof,
            text=f"USER: {req.text.strip()}\nASSISTANT: {snippet}",
            meta={
                "kind": "interaction",
                "topic": req.topic,
                "profile": prof,
                "ts": int(time.time()),
            }
        )
        writeback_ok = 1
    except Exception as e:
        log.warning("Memory writeback failed: %s", e)
        writeback_ok = 0

    debug_obj: Optional[Dict[str, Any]] = None
    if req.debug:
        debug_obj = {
            "request_strict": req.strict,
            "planner_enabled": PLANNER_ENABLED,
            "planner": {"plan": plan.__dict__},
            "expert_used": plan.consult_expert,
            "memory": {
                "use_profile": True,
                "use_global": True,
                "top_k_profile": TOP_K_PROFILE,
                "top_k_global": TOP_K_GLOBAL,
                "min_score": MIN_SCORE,
            },
            "embedder_mode": EMBEDDER_MODE,
            "timings_ms": {
                "profile_hits": len(profile_hits),
                "global_hits": len(global_hits),
                "memory_retrieval_ms": memory_retrieval_ms,
                "planner_ms": planner_ms,
                "expert_ms": expert_ms,
                "persona_ms": persona_ms,
                "total_ms": round((time.time() - t_all0) * 1000, 1),
                "writeback_ok": writeback_ok,
            },
            "ports": {"persona": PERSONA_PORT, "reasoning": REASONING_PORT, "coder": CODER_PORT},
        }

    return ChatResponse(
        text=reply,
        confidence=conf,
        body_cue=cue,
        agent_used="persona",
        experts_consulted=consulted,
        topic=req.topic,
        profile=prof,
        strict_mode=False,  # strict_mode here is "routing escalation"; planner already decides consult
        server_url=f"http://{HOST}:{PERSONA_PORT}",
        debug=debug_obj,
    )

@app.get("/state")
def state():
    return {"status": "ok", "version": "1.3.0"}
