import os
import time
import uuid
import asyncio
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal, AsyncGenerator, Tuple

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from memory_distiller import build_distill_prompt, parse_facts

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
DEFAULT_PROFILE = os.getenv("DEFAULT_PROFILE", "default")

LLAMA_HOST = os.getenv("LLAMA_HOST", "127.0.0.1")
PERSONA_PORT = int(os.getenv("PERSONA_PORT", "8080"))
SCIENTIST_PORT = int(os.getenv("SCIENTIST_PORT", "8081"))

PERSONA_URL = f"http://{LLAMA_HOST}:{PERSONA_PORT}/completion"
SCIENTIST_URL = f"http://{LLAMA_HOST}:{SCIENTIST_PORT}/completion"

# Feature toggles
ASYNC_SCIENTIST_ENABLED = os.getenv("ASYNC_SCIENTIST_ENABLED", "0") == "1"
RAG_ENABLED = os.getenv("RAG_ENABLED", "0") == "1"
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

# Retrieval defaults: facts only (chat logs are audit-only)
RAG_KINDS_FOR_CHAT = {
    k.strip().lower()
    for k in os.getenv("RAG_KINDS_FOR_CHAT", "fact").split(",")
    if k.strip()
}
RAG_KINDS_FOR_SCIENCE = {
    k.strip().lower()
    for k in os.getenv("RAG_KINDS_FOR_SCIENCE", "fact,scientist_note").split(",")
    if k.strip()
}

RAG_FILTER_BAD_MEMORIES = os.getenv("RAG_FILTER_BAD_MEMORIES", "1") == "1"

PERSONA_MAX_TOKENS = int(os.getenv("PERSONA_MAX_TOKENS", "192"))
PERSONA_TIMEOUT_S = float(os.getenv("PERSONA_TIMEOUT_S", "120"))

PROFILE_WRAPPERS_ENABLED = os.getenv("PROFILE_WRAPPERS_ENABLED", "1") == "1"
PERSONA_WRITEBACK_ENABLED = os.getenv("PERSONA_WRITEBACK_ENABLED", "1") == "1"
MEMORY_WRITEBACK_FILTER_ENABLED = os.getenv("MEMORY_WRITEBACK_FILTER_ENABLED", "1") == "1"

# Memory distillation
MEMORY_DISTILL_ENABLED = os.getenv("MEMORY_DISTILL_ENABLED", "1") == "1"
MEMORY_DISTILL_MAX_FACTS = int(os.getenv("MEMORY_DISTILL_MAX_FACTS", "3"))
MEMORY_DISTILL_MAX_TOKENS = int(os.getenv("MEMORY_DISTILL_MAX_TOKENS", "96"))
MEMORY_DISTILL_TIMEOUT_S = float(os.getenv("MEMORY_DISTILL_TIMEOUT_S", "30"))

# Keep chat logs for audit/history (not retrieved by default)
CHAT_LOG_WRITEBACK_ENABLED = os.getenv("CHAT_LOG_WRITEBACK_ENABLED", "1") == "1"

# Jobs persistence
JOBS_PERSIST_ENABLED = os.getenv("JOBS_PERSIST_ENABLED", "1") == "1"
JOBS_PERSIST_PATH = os.getenv("JOBS_PERSIST_PATH", os.path.join(AI_ROOT, "run", "jobs.jsonl"))
JOBS_PERSIST_MAX_LOAD = int(os.getenv("JOBS_PERSIST_MAX_LOAD", "5000"))

# Scientist in-band (optional)
SCIENTIST_INBAND_ENABLED = os.getenv("SCIENTIST_INBAND_ENABLED", "0") == "1"
SCIENTIST_INBAND_TOPICS = {
    t.strip().lower()
    for t in os.getenv("SCIENTIST_INBAND_TOPICS", "science,biology,coding,math").split(",")
    if t.strip()
}
SCIENTIST_INBAND_MAX_TOKENS = int(os.getenv("SCIENTIST_INBAND_MAX_TOKENS", "256"))
SCIENTIST_INBAND_TIMEOUT_S = float(os.getenv("SCIENTIST_INBAND_TIMEOUT_S", "45"))

GLOBAL_CHROMA_DIR = os.path.join(GLOBAL_MEMORY_DIR, "chroma")
os.makedirs(GLOBAL_CHROMA_DIR, exist_ok=True)
os.makedirs(PROFILES_DIR, exist_ok=True)
os.makedirs(os.path.join(AI_ROOT, "run"), exist_ok=True)


# -----------------------
# Embeddings + Chroma
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
        safe_meta: Dict[str, Any] = {}
        for k, v in (meta or {}).items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                safe_meta[k] = v
            else:
                safe_meta[k] = str(v)
        _collection.add(
            ids=[str(uuid.uuid4())],
            documents=[text],
            embeddings=[vec],
            metadatas=[safe_meta],
        )
    except Exception:
        return


# -----------------------
# Retrieval filters
# -----------------------
BAD_MEMORY_PATTERNS = [
    r"\bi cannot provide\b",
    r"\bi can't provide\b",
    r"\bi cannot help\b",
    r"\bi can't help\b",
    r"\bi won't help\b",
    r"\bi am unable to\b",
    r"\binternal context\b",
    r"\bretrieved memory\b",
    r"\bexpert notes\b",
    r"\bchroma\b",
    r"\bfastembed\b",
    r"(?i)\bnext actions\s*:\b",
]

def is_bad_memory(doc: str) -> bool:
    t = (doc or "").strip().lower()
    if not t:
        return True
    for p in BAD_MEMORY_PATTERNS:
        if re.search(p, t):
            return True
    return False

def filter_bad_memories(docs: List[str]) -> List[str]:
    out: List[str] = []
    for d in docs:
        if not isinstance(d, str):
            continue
        s = d.strip()
        if not s:
            continue
        if RAG_FILTER_BAD_MEMORIES and is_bad_memory(s):
            continue
        out.append(s)
    return out

def memory_query(text: str, k: int, kind_filter: Optional[set[str]] = None) -> List[str]:
    if not _chroma_ok or _collection is None:
        return []
    if _embedder is None:
        return []
    if k <= 0:
        return []
    try:
        vec = _embed(text)
        where = None
        if kind_filter:
            kinds = sorted({x.strip().lower() for x in kind_filter if x.strip()})
            if len(kinds) == 1:
                where = {"kind": kinds[0]}
            elif len(kinds) > 1:
                where = {"$or": [{"kind": kk} for kk in kinds]}
        res = _collection.query(
            query_embeddings=[vec],
            n_results=k,
            include=["documents"],
            where=where,
        )
        docs = (res.get("documents") or [[]])[0]
        docs = filter_bad_memories(docs)
        return docs[:k]
    except Exception:
        return []


# -----------------------
# Profiles
# -----------------------
def _profile_path(profile: str) -> str:
    return os.path.join(PROFILES_DIR, profile)

def ensure_profile_files(profile: str) -> None:
    p = _profile_path(profile)
    Path(p).mkdir(parents=True, exist_ok=True)
    for fn, default in (
        ("persona.md", "# Persona\n(define persona here)\n"),
        ("style.md", "# Style\n(define style rules here)\n"),
        ("system_rules.md", "# System Rules\n(define hard rules here)\n"),
    ):
        fp = os.path.join(p, fn)
        if not os.path.isfile(fp):
            with open(fp, "w", encoding="utf-8") as f:
                f.write(default)

def _read_text(path: str, limit: int = 12000) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            s = f.read()
        s = s.strip()
        if len(s) > limit:
            s = s[:limit].rstrip() + "\n…"
        return s
    except FileNotFoundError:
        return ""

def load_profile_wrappers(profile: str) -> Tuple[str, str, str]:
    ensure_profile_files(profile)
    p = _profile_path(profile)
    return (
        _read_text(os.path.join(p, "persona.md")),
        _read_text(os.path.join(p, "style.md")),
        _read_text(os.path.join(p, "system_rules.md")),
    )


# -----------------------
# Jobs persistence
# -----------------------
def _persist_job_event(job_id: str, patch: Dict[str, Any]) -> None:
    if not JOBS_PERSIST_ENABLED:
        return
    try:
        event = {"ts": int(time.time()), "job_id": job_id, "patch": patch}
        Path(os.path.dirname(JOBS_PERSIST_PATH)).mkdir(parents=True, exist_ok=True)
        with open(JOBS_PERSIST_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        return

def _load_persisted_jobs() -> Dict[str, Dict[str, Any]]:
    if not JOBS_PERSIST_ENABLED:
        return {}
    if not os.path.isfile(JOBS_PERSIST_PATH):
        return {}
    jobs_local: Dict[str, Dict[str, Any]] = {}
    try:
        with open(JOBS_PERSIST_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > JOBS_PERSIST_MAX_LOAD:
            lines = lines[-JOBS_PERSIST_MAX_LOAD:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                jid = evt.get("job_id")
                patch = evt.get("patch") or {}
                if not jid:
                    continue
                jobs_local.setdefault(jid, {}).update(patch)
            except Exception:
                continue
    except Exception:
        return {}
    return jobs_local


# -----------------------
# Sanitizer (stable)
# -----------------------
def _canonicalize(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")

def _split_bullets_anywhere(text: str) -> List[str]:
    if not text:
        return []
    s = text.replace("•", "*")
    s = re.sub(r"\s+\*\s+", "\n* ", s)
    s = re.sub(r"\s+-\s+", "\n* ", s)
    out: List[str] = []
    for line in s.splitlines():
        line = line.strip()
        if re.match(r"^\*\s+", line):
            out.append(re.sub(r"^\*\s+", "", line).strip())
        elif re.match(r"^-\s+", line):
            out.append(re.sub(r"^-\s+", "", line).strip())
    return [b for b in out if b]

def _is_bad_bullet(b: str) -> bool:
    s = re.sub(r"\s+", " ", (b or "")).strip().lower()
    if not s:
        return True
    if re.fullmatch(r"next actions\s*:?", s):
        return True
    if s.startswith("next actions"):
        return True
    if len(s) < 3:
        return True
    return False

def sanitize_persona_reply(text: str) -> str:
    t = _canonicalize((text or "").strip())

    m = re.search(r"(?i)\bnext actions\s*:\b", t)
    if m:
        head_raw = t[:m.start()].strip()
        tail_raw = t[m.end():].strip()
    else:
        head_raw = t
        tail_raw = t

    head_raw = re.sub(r"(?i)\bnext actions\s*:\b.*$", "", head_raw).strip()
    head = re.split(r"\n\s*\n", head_raw, maxsplit=1)[0].strip()
    if not head:
        head = "I can help with local, offline assistance across research, coding, and planning."

    bullets_raw = _split_bullets_anywhere(tail_raw)

    seen = set()
    bullets: List[str] = []
    for b in bullets_raw:
        if _is_bad_bullet(b):
            continue
        key = re.sub(r"\s+", " ", b).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        bullets.append(b)

    bullets = bullets[:4]
    while len(bullets) < 2:
        bullets.append("Ask a specific question or describe the task you want help with.")
    bullets = bullets[:4]

    return (head + "\n\nNext actions:\n" + "\n".join([f"* {b}" for b in bullets])).strip()


def format_rag_context(docs: List[str]) -> str:
    if not docs:
        return ""
    out: List[str] = []
    for i, d in enumerate(docs, start=1):
        s = (d or "").strip()
        s = re.sub(r"\s+", " ", s)
        if len(s) > 280:
            s = s[:280].rstrip() + "…"
        out.append(f"{i}) {s}")
    return "\n".join(out)


_REFUSAL_PATTERNS = [
    r"\bi cannot provide\b",
    r"\bi can't provide\b",
    r"\bi cannot help\b",
    r"\bi can't help\b",
    r"\bi won't help\b",
    r"\bi am unable to\b",
]

def should_writeback_memory(_user_text: str, assistant_text: str) -> bool:
    if not MEMORY_WRITEBACK_FILTER_ENABLED:
        return True
    a = (assistant_text or "").strip().lower()
    if any(re.search(p, a) for p in _REFUSAL_PATTERNS):
        return False
    if len(a) < 80:
        return False
    return True


def rag_kinds_for_topic(topic: str) -> set[str]:
    t = (topic or "chat").strip().lower()
    if t in ("science", "biology", "math", "coding"):
        return set(RAG_KINDS_FOR_SCIENCE)
    return set(RAG_KINDS_FOR_CHAT)


# -----------------------
# Llama helpers
# -----------------------
async def query_llama(url: str, prompt: str, tokens: int, temperature: float, timeout_s: float,
                     extra: Optional[Dict[str, Any]] = None):
    payload: Dict[str, Any] = {"prompt": prompt, "n_predict": tokens, "temperature": temperature}
    if extra:
        payload.update(extra)
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    content = (data.get("content") or "").strip()
    tokens_generated = int(data.get("tokens_predicted") or 0)
    return content, {"tokens_generated": tokens_generated}


# -----------------------
# Prompt builder
# -----------------------
def build_persona_prompt(user_text: str, rag_docs: List[str], *, profile: str, topic: str, scientist_notes: str = "") -> str:
    persona_md = style_md = rules_md = ""
    if PROFILE_WRAPPERS_ENABLED:
        persona_md, style_md, rules_md = load_profile_wrappers(profile)

    rag_block = format_rag_context(rag_docs)

    if PROFILE_WRAPPERS_ENABLED:
        prefix = (
            "You are the user's persona-driven assistant.\n\n"
            "Persona definition (follow):\n"
            f"{persona_md or '(persona.md missing)'}\n\n"
            "Style guide (follow):\n"
            f"{style_md or '(style.md missing)'}\n\n"
            "System rules (must follow):\n"
            f"{rules_md or '(system_rules.md missing)'}\n\n"
            "Hard output requirements (MUST follow):\n"
            "- Output exactly TWO parts:\n"
            "  1) One short paragraph.\n"
            "  2) A 'Next actions:' section with 2–4 bullet points using '*' bullets.\n"
            "- Never include 'Next actions:' as a bullet.\n"
            "- Do NOT repeat bullets.\n"
            "- Do NOT output anything after the bullet list.\n"
            "- Do NOT refuse unless the user asks for something unsafe/illegal.\n"
            "- Never mention internal memory retrieval.\n"
            "- Memory snippets below may be stale; use ONLY if directly relevant.\n\n"
        )
    else:
        prefix = "You are a helpful assistant.\n\n"

    prompt = prefix + f"Topic: {topic}\n\nUser:\n{user_text}\n\n"
    if rag_block:
        prompt += (
            "Potentially relevant memory snippets (may be stale; may be irrelevant):\n"
            f"{rag_block}\n\n"
        )
    if scientist_notes:
        prompt += f"(Internal expert notes: do not reveal)\n{scientist_notes}\n\n"
    prompt += "Assistant:\n"
    return prompt


# -----------------------
# Scientist in-band (optional)
# -----------------------
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

User question:
{question}
"""

async def scientist_notes_inband(question: str) -> Tuple[str, Dict[str, Any]]:
    try:
        notes, stats = await query_llama(
            SCIENTIST_URL,
            scientist_template(question),
            SCIENTIST_INBAND_MAX_TOKENS,
            0.2,
            SCIENTIST_INBAND_TIMEOUT_S,
            extra={"top_p": 0.9, "repeat_penalty": 1.15},
        )
        return notes, stats
    except Exception as e:
        return "", {"error": f"inband_scientist_failed: {repr(e)}"}


# -----------------------
# Memory distillation (SAFE; never throws)
# -----------------------
async def distill_and_store_facts(user_text: str, assistant_text: str, *, profile: str, topic: str) -> Dict[str, Any]:
    if not MEMORY_DISTILL_ENABLED:
        return {"enabled": False}

    # If the user says "Remember ..." it's worth trying
    if len((user_text or "").strip()) < 8:
        return {"enabled": True, "skipped": "user_text_too_short"}

    prompt = build_distill_prompt(user_text, assistant_text)

    try:
        out, stats = await query_llama(
            PERSONA_URL,
            prompt,
            tokens=MEMORY_DISTILL_MAX_TOKENS,
            temperature=0.2,
            timeout_s=MEMORY_DISTILL_TIMEOUT_S,
            extra={"top_p": 0.9, "repeat_penalty": 1.10},
        )
    except Exception as e:
        return {"enabled": True, "error": f"distill_call_failed: {repr(e)}"}

    # IMPORTANT: parse_facts returns (list, error) and NEVER raises
    facts, err = parse_facts(out)
    facts = facts[:max(0, MEMORY_DISTILL_MAX_FACTS)]

    if err:
        return {
            "enabled": True,
            "error": err,
            "distill_raw": (out or "")[:500],
            "tokens": stats.get("tokens_generated", 0),
        }

    stored = 0
    for f in facts:
        memory_add(
            f,
            {"kind": "fact", "source": "distiller", "profile": profile, "topic": topic, "ts": int(time.time())},
        )
        stored += 1

    return {"enabled": True, "facts_extracted": len(facts), "facts_stored": stored, "tokens": stats.get("tokens_generated", 0)}


# -----------------------
# FastAPI
# -----------------------
app = FastAPI()

# --- Task delegation bridge (local) ---
import subprocess
import time
from pathlib import Path
# Minimal endpoint to allow a local task manager to coordinate repo work.
# You can evolve this into LangGraph/CrewAI routing later.

@app.post("/agent/run")
async def agent_run(payload: dict):
    \"\"\"Run a local taskman2 job.

    Expected payload: a job JSON object (same schema used by tools/taskman2.py).

    Writes:
      run/jobs/<task_id>.job.json
      run/jobs/<task_id>.result.json
    \"\"\"

    import json
    import subprocess
    import time
    from pathlib import Path

    task_id = str(payload.get("task_id") or f"job-{int(time.time())}")
    jobs_dir = Path("run") / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    job_path = jobs_dir / f"{task_id}.job.json"
    result_path = jobs_dir / f"{task_id}.result.json"

    job_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cmd = [
        "python3",
        "tools/taskman2.py",
        str(job_path),
        "--repo",
        ".",
        "--out",
        str(result_path),
        "--yes",
    ]

    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        stdout = (p.stdout or "")[-4000:]
        stderr = (p.stderr or "")[-4000:]
        return {
            "status": "ok" if p.returncode == 0 else "error",
            "task_id": task_id,
            "returncode": p.returncode,
            "job_file": str(job_path),
            "result_file": str(result_path),
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "task_id": task_id,
            "job_file": str(job_path),
            "result_file": str(result_path),
            "message": "taskman2 exceeded 300s timeout",
        }

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "internal_server_error", "detail": repr(exc)})

PERSONA_CONCURRENCY = int(os.getenv("PERSONA_CONCURRENCY", "2"))
persona_sem = asyncio.Semaphore(PERSONA_CONCURRENCY)

jobs: Dict[str, Dict[str, Any]] = _load_persisted_jobs()

def _job_set(job_id: str, patch: Dict[str, Any]) -> None:
    jobs.setdefault(job_id, {}).update(patch)
    _persist_job_event(job_id, patch)


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
        "profile_wrappers_enabled": PROFILE_WRAPPERS_ENABLED,
        "persona_writeback_enabled": PERSONA_WRITEBACK_ENABLED,
        "memory_distill_enabled": MEMORY_DISTILL_ENABLED,
        "chat_log_writeback_enabled": CHAT_LOG_WRITEBACK_ENABLED,
        "rag_kinds_for_chat": sorted(list(RAG_KINDS_FOR_CHAT)),
        "rag_kinds_for_science": sorted(list(RAG_KINDS_FOR_SCIENCE)),
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    profile = (req.profile or DEFAULT_PROFILE).strip()
    topic = (req.topic or "chat").strip().lower()
    ensure_profile_files(profile)

    rag_docs: List[str] = []
    rag_used = False
    if RAG_ENABLED:
        rag_docs = memory_query(req.text, k=RAG_TOP_K, kind_filter=rag_kinds_for_topic(topic))
        rag_used = bool(rag_docs)

    inband_notes = ""
    inband_stats: Dict[str, Any] = {}
    inband_used = False
    if SCIENTIST_INBAND_ENABLED and topic in SCIENTIST_INBAND_TOPICS:
        inband_notes, inband_stats = await scientist_notes_inband(req.text)
        inband_used = bool(inband_notes)

    prompt = build_persona_prompt(req.text, rag_docs, profile=profile, topic=topic, scientist_notes=inband_notes)

    async with persona_sem:
        reply, stats = await query_llama(PERSONA_URL, prompt, PERSONA_MAX_TOKENS, 0.7, PERSONA_TIMEOUT_S)

    reply = sanitize_persona_reply(reply)

    distill_dbg = await distill_and_store_facts(req.text, reply, profile=profile, topic=topic)

    # optional audit log
    if CHAT_LOG_WRITEBACK_ENABLED and PERSONA_WRITEBACK_ENABLED and should_writeback_memory(req.text, reply):
        memory_add(
            f"[chat_log]\n[user]\n{req.text}\n\n[assistant]\n{reply}",
            {"kind": "chat_log", "source": "persona", "profile": profile, "topic": topic, "ts": int(time.time())},
        )

    debug = {}
    if req.debug:
        debug = {
            "rag_used": rag_used,
            "rag_docs_count": len(rag_docs),
            "rag_kinds": sorted(list(rag_kinds_for_topic(topic))),
            "scientist_inband_used": inband_used,
            "scientist_inband_stats": inband_stats,
            "distill": distill_dbg,
        }

    return {"text": reply, "persona": True, "debug": debug}


@app.post("/chat_submit")
async def chat_submit(req: SubmitRequest):
    # kept for compatibility; simple job wrapper
    profile = (req.profile or DEFAULT_PROFILE).strip()
    topic = (req.topic or "chat").strip().lower()
    ensure_profile_files(profile)

    job_id = str(uuid.uuid4())
    _job_set(job_id, {"kind": "persona", "status": "complete", "result": "chat_submit is disabled in this build."})
    return {"persona_job": job_id}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


@app.get("/v1/models")
async def v1_models():
    return {"object": "list", "data": [{"id": "project_persona", "object": "model", "created": int(time.time()), "owned_by": "local"}]}


def _messages_to_text(messages: List[OA_Message]) -> str:
    parts: List[str] = []
    for m in messages:
        parts.append(f"[{m.role}]\n{m.content}")
    return "\n\n".join(parts).strip()


@app.post("/v1/chat/completions")
async def v1_chat_completions(req: OA_ChatCompletionsReq):
    user_text = _messages_to_text(req.messages)
    topic = ((req.topic or "chat") if req.topic is not None else "chat").strip().lower()
    profile = (req.profile or DEFAULT_PROFILE).strip()
    ensure_profile_files(profile)

    rag_docs: List[str] = []
    if RAG_ENABLED:
        rag_docs = memory_query(user_text, k=RAG_TOP_K, kind_filter=rag_kinds_for_topic(topic))

    prompt = build_persona_prompt(user_text, rag_docs, profile=profile, topic=topic)
    max_tokens = int(req.max_tokens or PERSONA_MAX_TOKENS)
    temperature = float(req.temperature) if req.temperature is not None else 0.7

    reply, stats = await query_llama(PERSONA_URL, prompt, max_tokens, temperature, PERSONA_TIMEOUT_S)
    reply = sanitize_persona_reply(reply)

    await distill_and_store_facts(user_text, reply, profile=profile, topic=topic)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model or "project_persona",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": int(stats.get("tokens_generated", 0)),
                  "total_tokens": int(stats.get("tokens_generated", 0))},
    }
