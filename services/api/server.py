import os
import sys
import time
import uuid
import asyncio
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Literal, AsyncGenerator, Tuple

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response
from pydantic import BaseModel

import taskboard
import conversations as convo
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

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None


# -----------------------
# Config
# -----------------------
AI_ROOT = os.getenv("AI_ROOT", os.path.expanduser("~/AI"))
PERSONA_ROOT = os.getenv("PERSONA_ROOT", os.path.join(AI_ROOT, "persona"))
PROFILES_DIR = os.getenv("PROFILES_DIR", os.path.join(PERSONA_ROOT, "profiles"))
GLOBAL_MEMORY_DIR = os.getenv("GLOBAL_MEMORY_DIR", os.path.join(PERSONA_ROOT, "global_memory"))
DEFAULT_PROFILE = os.getenv("DEFAULT_PROFILE", "default")

LLAMA_HOST = os.getenv("LLAMA_HOST", "127.0.0.1")
PERSONA_PORT = int(os.getenv("PERSONA_PORT", "8090"))

# Unified llama-server endpoint (single-model topology, DECISION 2026-05-09).
# SCIENTIST_URL/SCIENTIST_PORT retired 2026-05-17 — role differentiation now happens
# at the prompt layer (thinking-mode toggle + reasoning_template), not via separate URLs.
PERSONA_URL = f"http://{LLAMA_HOST}:{PERSONA_PORT}/completion"
# T2.4 messages path. PERSONA_CHAT_URL is the OpenAI-compatible chat endpoint on the
# same llama-server. With PERSONA_USE_MESSAGES=1 the persona generates via messages +
# chat_template_kwargs{enable_thinking} (needs --jinja, which is the launcher default);
# under --reasoning-format deepseek the server returns reasoning in reasoning_content.
# OFF by default -> the proven raw /completion + /think-prefix path is unchanged.
PERSONA_CHAT_URL = f"http://{LLAMA_HOST}:{PERSONA_PORT}/v1/chat/completions"
PERSONA_USE_MESSAGES = os.getenv("PERSONA_USE_MESSAGES", "0").strip().lower() in ("1", "true", "yes", "on")
# T2.4 payoff (2026-06-08): the messages path is live-proven to deliver clean
# content + reasoning_content server-side (reasoning split into reasoning_content
# under --jinja + --reasoning-format deepseek), so the lossy post-hoc two-part
# sanitizer is RETIRED on that path -- the chat template's system "Hard output
# requirements" own the format. With PERSONA_USE_MESSAGES on, /chat + /v1 return the
# server content as-is. PERSONA_SANITIZE_MESSAGES is an OFF-by-default escape hatch:
# set it to 1 to re-apply sanitize_persona_reply on the messages path if a model
# ignores the format contract. The proven raw /completion path is unaffected and
# still sanitizes (preserve_thinking still bypasses sanitizing on both paths).
PERSONA_SANITIZE_MESSAGES = os.getenv("PERSONA_SANITIZE_MESSAGES", "0").strip().lower() in ("1", "true", "yes", "on")

# Feature toggles
# ASYNC_REASONING_ENABLED replaces ASYNC_SCIENTIST_ENABLED (back-compat: old name still read).
ASYNC_REASONING_ENABLED = (
    os.getenv("ASYNC_REASONING_ENABLED",
              os.getenv("ASYNC_SCIENTIST_ENABLED", "0"))
    == "1"
)
RAG_ENABLED = os.getenv("RAG_ENABLED", "0") == "1"
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))
# Per-profile RAG (2026-06-07). OFF by default: all add/query use the single shared
# collection (RAG_GLOBAL_COLLECTION) exactly as before. With RAG_PER_PROFILE=1,
# add/query are scoped to a per-profile collection ("mem_<profile>") so each persona
# retrieves only its own memory. NOTE: turning this on does NOT move existing rows
# out of the shared collection -- pre-existing memory stays in RAG_GLOBAL_COLLECTION
# and is not seen under per-profile scoping until migrated.
RAG_PER_PROFILE = os.getenv("RAG_PER_PROFILE", "0").strip().lower() in ("1", "true", "yes", "on")
RAG_GLOBAL_COLLECTION = os.getenv("RAG_GLOBAL_COLLECTION", "global_memory")
# Phase 2a vector backend: chroma (default) | qdrant (embedded local mode, no server).
# Both go through the RagStore abstraction (services/api/ragstore.py); server.py keeps
# computing embeddings and passes vectors in. Default stays chroma until Qdrant parity
# is proven live, then flip. Migrate existing rows with scripts/migrate_chroma_to_qdrant.py.
RAG_BACKEND = os.getenv("RAG_BACKEND", "chroma").strip().lower()

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
# Embedding backend selection (Phase 0.5 dependency tiers):
#   auto                  -> try fastembed (lean/onnxruntime), then sentence-transformers
#   fastembed             -> fastembed only (lean node default; no torch)
#   sentence-transformers -> sentence-transformers only (requires the torch extra)
# sentence-transformers is an OPT-IN extra (services/api/requirements-embed-torch.txt).
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "auto").strip().lower()

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

# Task Board (SQLite) -- replaces the in-memory jobs dict + run/jobs.jsonl.
TASKS_DB = os.getenv("TASKS_DB", os.path.join(AI_ROOT, "data", "tasks.db"))
# Conversation history (SQLite) -- Phase 2 source of truth for multi-turn history.
CONVERSATIONS_DB = os.getenv("CONVERSATIONS_DB", os.path.join(AI_ROOT, "data", "conversations.db"))
# Persist turns to conversations.db on /chat + /v1 (Phase 2). On by default.
CONVO_PERSIST_ENABLED = os.getenv("CONVO_PERSIST_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
# Legacy event-log path, kept only as a one-time migration source for the board.
JOBS_PERSIST_PATH = os.getenv("JOBS_PERSIST_PATH", os.path.join(AI_ROOT, "run", "jobs.jsonl"))

# Reasoning in-band (optional) — was SCIENTIST_INBAND_* pre-2026-05-17.
# Routes to the unified llama-server (PERSONA_URL) with a structured prompt template;
# generates an internal expert-notes block woven into the persona reply.
REASONING_INBAND_ENABLED = (
    os.getenv("REASONING_INBAND_ENABLED",
              os.getenv("SCIENTIST_INBAND_ENABLED", "0"))
    == "1"
)
REASONING_INBAND_TOPICS = {
    t.strip().lower()
    for t in os.getenv("REASONING_INBAND_TOPICS",
                       os.getenv("SCIENTIST_INBAND_TOPICS", "science,biology,coding,math")).split(",")
    if t.strip()
}
REASONING_INBAND_MAX_TOKENS = int(
    os.getenv("REASONING_INBAND_MAX_TOKENS",
              os.getenv("SCIENTIST_INBAND_MAX_TOKENS", "256"))
)
REASONING_INBAND_TIMEOUT_S = float(
    os.getenv("REASONING_INBAND_TIMEOUT_S",
              os.getenv("SCIENTIST_INBAND_TIMEOUT_S", "45"))
)

# Thinking-mode toggle (DECISION 2026-05-09 / Qwen3 prompt-level directives).
# THINKING_MODE_DEFAULT: "auto" | "on" | "off".
#   "auto" → /think for topics in THINKING_MODE_TOPICS, /no_think otherwise.
#   "on"   → /think prepended unconditionally.
#   "off"  → /no_think prepended unconditionally.
# Prepended at prompt-build time per Qwen3's documented `/think` and `/no_think` directives.
# Future T2.2 work may switch to chat_template_kwargs once query_llama migrates to messages format.
THINKING_MODE_DEFAULT = os.getenv("THINKING_MODE_DEFAULT", "auto").strip().lower()
THINKING_MODE_TOPICS = {
    t.strip().lower()
    for t in os.getenv("THINKING_MODE_TOPICS", "science,biology,coding,math,research").split(",")
    if t.strip()
}

def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)

def _env_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)

SAMPLING_PRESETS: Dict[str, Dict[str, Any]] = {
    "no_think": {
        "temperature": _env_float("SAMPLING_DEFAULT_TEMP", "0.7"),
        "top_p": _env_float("SAMPLING_DEFAULT_TOP_P", "0.8"),
        "top_k": _env_int("SAMPLING_DEFAULT_TOP_K", "20"),
        "min_p": _env_float("SAMPLING_DEFAULT_MIN_P", "0.0"),
        "presence_penalty": _env_float("SAMPLING_DEFAULT_PRESENCE_PENALTY", "1.5"),
    },
    "think": {
        "temperature": _env_float("SAMPLING_THINK_TEMP", "0.6"),
        "top_p": _env_float("SAMPLING_THINK_TOP_P", "0.95"),
        "top_k": _env_int("SAMPLING_THINK_TOP_K", "20"),
        "min_p": _env_float("SAMPLING_THINK_MIN_P", "0.0"),
        "presence_penalty": _env_float("SAMPLING_THINK_PRESENCE_PENALTY", "0.0"),
    },
}

# T2.2 thinking gate (2026-06-07). A deterministic per-request triviality
# classifier that refines the coarse THINKING_MODE_TOPICS bucket in "auto" mode.
# OFF by default: with the gate off, resolve_think behaves exactly as before
# (explicit on/off override, then topic-in-THINKING_MODE_TOPICS -> think, else
# no_think) so the Phase 1 exit-gate proof is unchanged. With THINKING_AUTO_GATE=1
# the gate may PROMOTE a non-thinking-topic request (e.g. "chat") to think when the
# text is non-trivial. Explicit on/off and the thinking topics keep their
# deterministic mapping -- the gate only refines the otherwise-flat "everything
# else -> no_think" bucket.
THINKING_AUTO_GATE = os.getenv("THINKING_AUTO_GATE", "0").strip().lower() in ("1", "true", "yes", "on")
THINKING_GATE_TRIVIAL_MAX_WORDS = _env_int("THINKING_GATE_TRIVIAL_MAX_WORDS", "6")
THINKING_GATE_COMPLEX_MIN_WORDS = _env_int("THINKING_GATE_COMPLEX_MIN_WORDS", "30")
THINKING_GATE_KEYWORDS = {
    t.strip().lower()
    for t in os.getenv(
        "THINKING_GATE_KEYWORDS",
        "why,how,explain,compare,contrast,analyze,analyse,derive,prove,calculate,"
        "compute,debug,optimize,optimise,design,plan,evaluate,reason,implications,"
        "trade-off,tradeoff,pros and cons,step by step,step-by-step,"
        "difference between,walk me through,break down",
    ).split(",")
    if t.strip()
}

# T2.3 preserve_thinking (2026-06-07). OFF by default (direct chat strips reasoning
# to the persona surface). Hermes-originated requests -- forwarded by the Phase 3
# daemon's task dispatcher -- set preserve_thinking=true so the model's reasoning
# survives the response (returned in `reasoning` on /chat and `reasoning_content`
# on /v1) instead of being discarded by the persona sanitizer. Per-request flag
# overrides this default.
PRESERVE_THINKING_DEFAULT = os.getenv("PRESERVE_THINKING_DEFAULT", "0").strip().lower() in ("1", "true", "yes", "on")

# Topic routing (2026-06-07). A deterministic keyword classifier that picks the
# request topic from the text. OFF by default: a request's topic is taken as given
# (default "chat"), so downstream thinking/sampling/RAG paths are unchanged. A
# per-request topic of "auto" ALWAYS classifies; with TOPIC_ROUTING=1 a missing or
# "chat" topic is classified too. An explicit non-chat topic is always respected.
TOPIC_ROUTING_DEFAULT = os.getenv("TOPIC_ROUTING", "0").strip().lower() in ("1", "true", "yes", "on")
# topic -> keyword set, checked in this priority order (first strict-max score wins).
TOPIC_KEYWORDS: Dict[str, set] = {
    "coding": {
        "code", "function", "bug", "compile", "compiler", "debug", "regex",
        "stack trace", "exception", "traceback", "variable", "async", "git",
        "refactor", "python", "javascript", "typescript", "rust", "java", "sql",
        "api", "endpoint", "import", "syntax", "runtime", "null pointer",
    },
    "math": {
        "calculate", "equation", "integral", "derivative", "theorem", "proof",
        "algebra", "geometry", "probability", "matrix", "vector", "factorial",
        "polynomial", "logarithm", "summation", "modulo", "factorize",
    },
    "biology": {
        "cell", "dna", "rna", "protein", "gene", "genome", "organism", "enzyme",
        "neuron", "evolution", "species", "bacteria", "virus", "mitochondria",
        "photosynthesis", "chromosome", "metabolism",
    },
    "science": {
        "physics", "chemistry", "molecule", "atom", "quantum", "energy",
        "experiment", "hypothesis", "reaction", "thermodynamics", "velocity",
        "electron", "compound", "isotope", "gravity", "voltage",
    },
    "research": {
        "research", "paper", "citation", "literature", "survey", "methodology",
        "peer-reviewed", "study", "meta-analysis", "abstract", "findings",
        "references",
    },
}
TOPIC_PRIORITY = ["coding", "math", "biology", "science", "research"]

GLOBAL_CHROMA_DIR = os.path.join(GLOBAL_MEMORY_DIR, "chroma")
GLOBAL_QDRANT_DIR = os.path.join(GLOBAL_MEMORY_DIR, "qdrant")
os.makedirs(GLOBAL_CHROMA_DIR, exist_ok=True)
os.makedirs(PROFILES_DIR, exist_ok=True)
os.makedirs(os.path.join(AI_ROOT, "run"), exist_ok=True)


# -----------------------
# Embeddings + Chroma
# -----------------------
_embedder = None
_embedder_backend: Optional[str] = None
_embedder_error: Optional[str] = None


def _init_fastembed():
    if TextEmbedding is None:
        return None, "fastembed_not_available"
    try:
        emb = TextEmbedding(model_name=EMBED_MODEL)
        _ = list(emb.embed(["warmup"]))[0]
        return emb, None
    except Exception as e:
        return None, f"fastembed_init_failed: {repr(e)}"


def _init_sentence_transformers():
    if SentenceTransformer is None:
        return None, "sentence_transformers_not_available"
    try:
        emb = SentenceTransformer(EMBED_MODEL)
        _ = emb.encode(["warmup"])[0]
        return emb, None
    except Exception as e:
        return None, f"sentence_transformers_init_failed: {repr(e)}"


_init_errors = []
if EMBED_BACKEND in ("auto", "fastembed"):
    _embedder, _err = _init_fastembed()
    if _embedder is not None:
        _embedder_backend = "fastembed"
    elif _err:
        _init_errors.append(_err)

if _embedder is None and EMBED_BACKEND in ("auto", "sentence-transformers", "sentence_transformers", "st"):
    _embedder, _err = _init_sentence_transformers()
    if _embedder is not None:
        _embedder_backend = "sentence-transformers"
    elif _err:
        _init_errors.append(_err)

if _embedder is None:
    _embedder_error = "; ".join(_init_errors) or f"no_embedder_for_backend:{EMBED_BACKEND}"

def _collection_name(profile: Optional[str]) -> str:
    """Resolve the Chroma collection name for a profile.

    RAG_PER_PROFILE off (or no profile) -> the shared RAG_GLOBAL_COLLECTION.
    On -> "mem_<sanitized-profile>" so each persona is isolated.
    """
    if not RAG_PER_PROFILE or not profile:
        return RAG_GLOBAL_COLLECTION
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", profile.strip())[:200] or "default"
    return f"mem_{safe}"


def _embed(text: str) -> List[float]:
    if _embedder is None:
        raise RuntimeError(_embedder_error or "embedder_unavailable")
    if _embedder_backend == "sentence-transformers":
        return _embedder.encode([text])[0].tolist()
    return list(_embedder.embed([text]))[0].tolist()


# Vector store (Phase 2a): RagStore over chroma|qdrant, selected by RAG_BACKEND.
# Qdrant needs the embedding dimension up front -> probe the live embedder (fallback
# to bge-small-en-v1.5's 384). server.py owns embeddings; the store owns persistence.
_embed_dim = 384
if _embedder is not None:
    try:
        _embed_dim = len(_embed("dimension probe"))
    except Exception:
        pass

try:
    import ragstore
except Exception:  # noqa: BLE001 -- allow running from an odd cwd
    from services.api import ragstore  # type: ignore

_store = ragstore.make_store(
    RAG_BACKEND,
    chroma_path=GLOBAL_CHROMA_DIR,
    default_collection=RAG_GLOBAL_COLLECTION,
    qdrant_path=GLOBAL_QDRANT_DIR,
    dim=_embed_dim,
)
_rag_ok = bool(getattr(_store, "ok", False))
_rag_error = getattr(_store, "error", None)
_rag_backend = getattr(_store, "backend", RAG_BACKEND)


def memory_add(text: str, meta: Dict[str, Any], *, profile: Optional[str] = None) -> None:
    if not _rag_ok or _embedder is None:
        return
    try:
        vec = _embed(text)
        safe_meta: Dict[str, Any] = {}
        for k, v in (meta or {}).items():
            if isinstance(v, (str, int, float, bool)) or v is None:
                safe_meta[k] = v
            else:
                safe_meta[k] = str(v)
        _store.add(_collection_name(profile), str(uuid.uuid4()), text, vec, safe_meta)
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

def memory_query(text: str, k: int, kind_filter: Optional[set[str]] = None, *, profile: Optional[str] = None) -> List[str]:
    if not _rag_ok or _embedder is None or k <= 0:
        return []
    try:
        vec = _embed(text)
        docs = _store.query(_collection_name(profile), vec, k, kind_filter=kind_filter)
        return filter_bad_memories(docs)[:k]
    except Exception:
        return []


# -----------------------
# Profiles
# -----------------------
def _profile_path(profile: str) -> str:
    return os.path.join(PROFILES_DIR, profile)

def ensure_profile_files(profile: str) -> None:
    """Scaffold the 2-file Hermes-naming profile (locked 2026-05-14).

    SOUL.md   — identity, personality, emotional range, communication style.
                Also serves as Hermes agent identity when this folder is HERMES_HOME.
    .hermes.md — hard rules, output format, avatar STATE vocabulary.
                Highest-priority Hermes context file (tree-walk discovery from CWD).

    style.md / persona.md / system_rules.md are retired — their content collapses
    into the two files above. Legacy copies live under archive/legacy_profile_files/.
    """
    p = _profile_path(profile)
    Path(p).mkdir(parents=True, exist_ok=True)
    for fn, default in (
        ("SOUL.md", "# Soul\n(identity, personality, emotional range, communication style)\n"),
        (".hermes.md", "# Hermes Rules\n(hard rules + output format + avatar STATE vocabulary)\n"),
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

def load_profile_wrappers(profile: str) -> Tuple[str, str]:
    """Return (soul_md, hermes_md) for the 2-file Hermes-naming profile."""
    ensure_profile_files(profile)
    p = _profile_path(profile)
    return (
        _read_text(os.path.join(p, "SOUL.md")),
        _read_text(os.path.join(p, ".hermes.md")),
    )


# -----------------------
# Task Board (SQLite) -- see services/api/taskboard.py
# -----------------------
taskboard.init_db(TASKS_DB, migrate_jsonl=JOBS_PERSIST_PATH)

# Conversation history (SQLite) -- see services/api/conversations.py
_convo_ok = False
_convo_error: Optional[str] = None
try:
    convo.init_db(CONVERSATIONS_DB)
    _convo_ok = True
except Exception as e:  # noqa: BLE001
    _convo_error = f"conversations_init_failed: {repr(e)}"


def estimate_tokens(text: str) -> int:
    """Cheap, model-agnostic token estimate (~4 chars/token) for history windowing
    and the stored `tokens` column. Good enough for budget arithmetic; not exact."""
    return max(1, len((text or "").strip()) // 4)


def _persist_turn(conversation_id, role, content, *, profile, topic=None):
    """Best-effort: record a turn in conversations.db (never breaks a chat request)."""
    if not (_convo_ok and CONVO_PERSIST_ENABLED and conversation_id):
        return
    try:
        convo.add_turn(conversation_id, role, content, profile=profile, topic=topic,
                       tokens=estimate_tokens(content))
    except Exception:  # noqa: BLE001
        return


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

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


def split_reasoning(text: str) -> Tuple[str, str]:
    """Split in-band Qwen3 reasoning from the user-facing answer.

    Returns (reasoning, answer). Handles the normal <think>...</think> wrap and a
    truncated open <think> with no close (the remainder is treated as reasoning,
    answer empty). No-op -- ("", text) -- when no think tag is present, e.g. the
    --jinja path where reasoning already arrives in reasoning_content (T2.4).
    """
    t = text or ""
    blocks = _THINK_RE.findall(t)
    if blocks:
        reasoning = "\n\n".join(b.strip() for b in blocks).strip()
        answer = _THINK_RE.sub("", t).strip()
        return reasoning, answer
    m = re.search(r"<think>", t, re.IGNORECASE)
    if m:
        return t[m.end():].strip(), ""
    return "", t.strip()


def resolve_preserve_thinking(flag: Optional[bool]) -> bool:
    """Resolve the preserve-thinking flag: explicit request value, else the env default."""
    return PRESERVE_THINKING_DEFAULT if flag is None else bool(flag)


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


def will_sanitize(preserve: bool) -> bool:
    """Whether the post-hoc persona sanitizer applies to this reply.

    False when preserve_thinking is set (agent/Hermes path wants the full answer).
    False on the messages path unless PERSONA_SANITIZE_MESSAGES re-enables it (T2.4
    payoff -- the server already returns clean, format-following content there).
    True otherwise (the proven raw /completion path).
    """
    if preserve:
        return False
    if PERSONA_USE_MESSAGES and not PERSONA_SANITIZE_MESSAGES:
        return False
    return True


def finalize_persona_reply(answer: str, preserve: bool) -> str:
    """Resolve the user-facing reply from the model answer per will_sanitize()."""
    return sanitize_persona_reply(answer) if will_sanitize(preserve) else answer


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


def classify_topic(text: str) -> str:
    """Deterministic keyword classifier -> a topic label, "chat" if none match.

    Scores each topic by keyword hits and returns the first topic (in
    TOPIC_PRIORITY order) holding the strict-max score, so ties resolve to the
    higher-priority topic.
    """
    low = (text or "").lower()
    best, best_score = "chat", 0
    for topic in TOPIC_PRIORITY:
        score = sum(1 for kw in TOPIC_KEYWORDS.get(topic, ()) if kw in low)
        if score > best_score:
            best, best_score = topic, score
    return best


def resolve_topic(req_topic: Optional[str], text: str) -> str:
    """Resolve the effective topic from the request value + text.

    - "auto"            -> always classify from text.
    - explicit non-chat -> respected as given.
    - "" / "chat"       -> classify only when TOPIC_ROUTING is on, else "chat".
    """
    rt = (req_topic or "").strip().lower()
    if rt == "auto":
        return classify_topic(text)
    if rt and rt != "chat":
        return rt
    if TOPIC_ROUTING_DEFAULT:
        return classify_topic(text)
    return rt or "chat"


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
    tokens_evaluated = int(data.get("tokens_evaluated") or 0)
    return content, {"tokens_generated": tokens_generated, "tokens_evaluated": tokens_evaluated}


async def query_llama_messages(url: str, messages: List[Dict[str, str]], max_tokens: int,
                               temperature: float, timeout_s: float, *, enable_thinking: bool,
                               extra: Optional[Dict[str, Any]] = None):
    """T2.4 chat-completions call. Returns (content, reasoning_content, stats).

    POSTs the OpenAI-compatible /v1/chat/completions on the llama-server with
    chat_template_kwargs{enable_thinking}. Under --jinja + --reasoning-format
    deepseek the server splits reasoning into message.reasoning_content; content is
    the user-facing answer. stats mirror query_llama's keys for downstream parity.
    """
    payload: Dict[str, Any] = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": bool(enable_thinking)},
        "stream": False,
    }
    if extra:
        payload.update(extra)
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s)) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or "").strip()
    usage = data.get("usage") or {}
    stats = {
        "tokens_generated": int(usage.get("completion_tokens") or 0),
        "tokens_evaluated": int(usage.get("prompt_tokens") or 0),
    }
    return content, reasoning, stats


# -----------------------
# Prompt builder
# -----------------------
def classify_triviality(text: str) -> Tuple[bool, List[str]]:
    """Classify a request as non-trivial (reasoning-worthy) or trivial.

    Deterministic and stdlib-only -- runs per request, so no model call. Returns
    (is_nontrivial, signals); `signals` lists the cues that fired so the decision
    is auditable from /chat debug. Drives the T2.2 thinking gate.
    """
    t = (text or "").strip()
    low = t.lower()
    words = re.findall(r"\w+", low)
    n = len(words)
    signals: List[str] = []

    if "```" in t or re.search(r"\bdef \w+\s*\(|\bclass \w+\s*[:(]|\bimport \w+", t):
        signals.append("code")
    if t.count("?") >= 2:
        signals.append("multi_question")
    if len(re.findall(r"[.!?]+", t)) >= 3:
        signals.append("multi_sentence")
    if n >= THINKING_GATE_COMPLEX_MIN_WORDS:
        signals.append("long")
    hits = sorted(k for k in THINKING_GATE_KEYWORDS if k in low)
    if hits:
        signals.append("keyword:" + ",".join(hits))

    if signals:
        return True, signals
    if n <= THINKING_GATE_TRIVIAL_MAX_WORDS:
        return False, ["short"]
    return False, ["default_trivial"]


def resolve_think(topic: str, mode: Optional[str] = None, text: Optional[str] = None) -> str:
    """Resolve the thinking mode to "think" or "no_think".

    Single source of truth for both the Qwen3 directive and the sampling preset.
    `mode` overrides THINKING_MODE_DEFAULT when explicitly passed. `text`, when
    supplied and THINKING_AUTO_GATE is on, lets the triviality gate promote a
    non-thinking-topic request to think in the "auto" path.
    """
    m = (mode or THINKING_MODE_DEFAULT or "auto").strip().lower()
    if m == "on":
        return "think"
    if m == "off":
        return "no_think"
    if (topic or "").strip().lower() in THINKING_MODE_TOPICS:
        return "think"
    if THINKING_AUTO_GATE and text:
        return "think" if classify_triviality(text)[0] else "no_think"
    return "no_think"


def thinking_prefix(topic: str, mode: Optional[str] = None, text: Optional[str] = None) -> str:
    """Return the Qwen3 thinking-mode directive line ("/think\\n" or "/no_think\\n")."""
    return "/think\n" if resolve_think(topic, mode, text) == "think" else "/no_think\n"


def sampling_for(topic: str, mode: Optional[str] = None, text: Optional[str] = None) -> Tuple[str, float, Dict[str, Any]]:
    """Return (preset_key, temperature, extra) for the resolved thinking mode.

    `extra` carries top_p/top_k/min_p/presence_penalty for query_llama.
    """
    key = resolve_think(topic, mode, text)
    preset = SAMPLING_PRESETS[key]
    temperature = float(preset["temperature"])
    extra = {k: preset[k] for k in ("top_p", "top_k", "min_p", "presence_penalty")}
    return key, temperature, extra


def build_persona_prompt(
    user_text: str,
    rag_docs: List[str],
    *,
    profile: str,
    topic: str,
    reasoning_notes: str = "",
    thinking_mode: Optional[str] = None,
) -> str:
    soul_md = hermes_md = ""
    if PROFILE_WRAPPERS_ENABLED:
        soul_md, hermes_md = load_profile_wrappers(profile)

    rag_block = format_rag_context(rag_docs)

    if PROFILE_WRAPPERS_ENABLED:
        prefix = (
            "You are the user's persona-driven assistant.\n\n"
            "Soul (identity, personality, communication style — follow):\n"
            f"{soul_md or '(SOUL.md missing)'}\n\n"
            "Hermes rules (hard rules + output format — must follow):\n"
            f"{hermes_md or '(.hermes.md missing)'}\n\n"
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

    prompt = thinking_prefix(topic, thinking_mode, user_text) + prefix + f"Topic: {topic}\n\nUser:\n{user_text}\n\n"
    if rag_block:
        prompt += (
            "Potentially relevant memory snippets (may be stale; may be irrelevant):\n"
            f"{rag_block}\n\n"
        )
    if reasoning_notes:
        prompt += f"(Internal expert notes: do not reveal)\n{reasoning_notes}\n\n"
    prompt += "Assistant:\n"
    return prompt


def build_persona_messages(
    user_text: str,
    rag_docs: List[str],
    *,
    profile: str,
    topic: str,
    reasoning_notes: str = "",
) -> List[Dict[str, str]]:
    """T2.4 messages form of build_persona_prompt (system/user split).

    Mirrors build_persona_prompt's persona block as the system message and the
    Topic/User/RAG block as the user message. No /think prefix and no trailing
    "Assistant:" -- the chat template owns the assistant turn, and thinking is
    controlled by chat_template_kwargs{enable_thinking}.
    """
    if PROFILE_WRAPPERS_ENABLED:
        soul_md, hermes_md = load_profile_wrappers(profile)
        system = (
            "You are the user's persona-driven assistant.\n\n"
            "Soul (identity, personality, communication style - follow):\n"
            f"{soul_md or '(SOUL.md missing)'}\n\n"
            "Hermes rules (hard rules + output format - must follow):\n"
            f"{hermes_md or '(.hermes.md missing)'}\n\n"
            "Hard output requirements (MUST follow):\n"
            "- Output exactly TWO parts:\n"
            "  1) One short paragraph.\n"
            "  2) A 'Next actions:' section with 2-4 bullet points using '*' bullets.\n"
            "- Never include 'Next actions:' as a bullet.\n"
            "- Do NOT repeat bullets.\n"
            "- Do NOT output anything after the bullet list.\n"
            "- Do NOT refuse unless the user asks for something unsafe/illegal.\n"
            "- Never mention internal memory retrieval.\n"
            "- Memory snippets below may be stale; use ONLY if directly relevant."
        )
    else:
        system = "You are a helpful assistant."

    rag_block = format_rag_context(rag_docs)
    user = f"Topic: {topic}\n\nUser:\n{user_text}\n\n"
    if rag_block:
        user += (
            "Potentially relevant memory snippets (may be stale; may be irrelevant):\n"
            f"{rag_block}\n\n"
        )
    if reasoning_notes:
        user += f"(Internal expert notes: do not reveal)\n{reasoning_notes}\n\n"
    return [{"role": "system", "content": system.strip()}, {"role": "user", "content": user.strip()}]


async def persona_generate(
    *,
    profile: str,
    topic: str,
    user_text: str,
    rag_docs: List[str],
    reasoning_notes: str,
    thinking_mode: Optional[str],
    temperature: float,
    max_tokens: int,
    sampling_extra: Dict[str, Any],
) -> Tuple[str, str, Dict[str, Any]]:
    """Generate a persona reply; returns (reasoning, answer, stats).

    PERSONA_USE_MESSAGES off (default): raw /completion with the /think prefix;
    reasoning is in-band and pulled out by split_reasoning. On (T2.4): messages +
    chat_template_kwargs{enable_thinking} against /v1/chat/completions, with the
    server's reasoning_content preferred and split_reasoning as the fallback.
    """
    if PERSONA_USE_MESSAGES:
        messages = build_persona_messages(
            user_text, rag_docs, profile=profile, topic=topic, reasoning_notes=reasoning_notes
        )
        enable_thinking = resolve_think(topic, thinking_mode, user_text) == "think"
        async with persona_sem:
            content, server_reasoning, stats = await query_llama_messages(
                PERSONA_CHAT_URL, messages, max_tokens, temperature, PERSONA_TIMEOUT_S,
                enable_thinking=enable_thinking, extra=sampling_extra,
            )
        if server_reasoning:
            return server_reasoning, content, stats
        reasoning, answer = split_reasoning(content)
        return reasoning, answer, stats

    prompt = build_persona_prompt(
        user_text, rag_docs, profile=profile, topic=topic,
        reasoning_notes=reasoning_notes, thinking_mode=thinking_mode,
    )
    async with persona_sem:
        raw_reply, stats = await query_llama(
            PERSONA_URL, prompt, max_tokens, temperature, PERSONA_TIMEOUT_S, extra=sampling_extra,
        )
    reasoning, answer = split_reasoning(raw_reply)
    return reasoning, answer, stats


# -----------------------
# Reasoning in-band (optional) — was Scientist in-band pre-2026-05-17.
# Routes to the unified llama-server with a structured "expert notes" prompt template.
# -----------------------
def reasoning_template(question: str) -> str:
    return f"""You are a careful research + reasoning assistant producing internal expert notes.

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

async def reasoning_notes_inband(question: str) -> Tuple[str, Dict[str, Any]]:
    try:
        notes, stats = await query_llama(
            PERSONA_URL,
            reasoning_template(question),
            REASONING_INBAND_MAX_TOKENS,
            0.2,
            REASONING_INBAND_TIMEOUT_S,
            extra={"top_p": 0.9, "repeat_penalty": 1.15},
        )
        return notes, stats
    except Exception as e:
        return "", {"error": f"inband_reasoning_failed: {repr(e)}"}


# -----------------------
# Memory distillation (SAFE; never throws)
# -----------------------
async def distill_and_store_facts(user_text: str, assistant_text: str, *, profile: str, topic: str) -> Dict[str, Any]:
    if not MEMORY_DISTILL_ENABLED:
        return {"enabled": False}

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
            profile=profile,
        )
        stored += 1

    return {"enabled": True, "facts_extracted": len(facts), "facts_stored": stored, "tokens": stats.get("tokens_generated", 0)}


# -----------------------
# FastAPI
# -----------------------
app = FastAPI()

import subprocess
from pathlib import Path

@app.post("/agent/run")
async def agent_run(payload: dict):
    """Run a local taskman2 job.

    Expected payload: a job JSON object (same schema used by tools/taskman2.py).

    Writes:
      run/jobs/<task_id>.job.json
      run/jobs/<task_id>.result.json
    """
    task_id = str(payload.get("task_id") or f"job-{int(time.time())}")
    jobs_dir = Path("run") / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    job_path = jobs_dir / f"{task_id}.job.json"
    result_path = jobs_dir / f"{task_id}.result.json"

    job_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _job_set(task_id, {
        "status": "running", "kind": "agent_run",
        "job_file": str(job_path), "result_file": str(result_path),
        "started_at": int(time.time()),
    })

    cmd = [
        sys.executable,
        "tools/taskman2.py",
        str(job_path),
        "--repo",
        ".",
        "--out",
        str(result_path),
        "--yes",
    ]

    try:
        p = await asyncio.to_thread(
            subprocess.run, cmd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300,
        )
        stdout = (p.stdout or "")[-4000:]
        stderr = (p.stderr or "")[-4000:]
        result = {
            "status": "ok" if p.returncode == 0 else "error",
            "task_id": task_id,
            "returncode": p.returncode,
            "job_file": str(job_path),
            "result_file": str(result_path),
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        }
        _job_set(task_id, {"status": result["status"], "returncode": p.returncode,
                           "finished_at": int(time.time())})
        return result
    except subprocess.TimeoutExpired:
        result = {
            "status": "timeout",
            "task_id": task_id,
            "job_file": str(job_path),
            "result_file": str(result_path),
            "message": "taskman2 exceeded 300s timeout",
        }
        _job_set(task_id, {"status": "timeout", "finished_at": int(time.time())})
        return result

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": "internal_server_error", "detail": repr(exc)})

PERSONA_CONCURRENCY = int(os.getenv("PERSONA_CONCURRENCY", "4"))
persona_sem = asyncio.Semaphore(PERSONA_CONCURRENCY)

def _job_set(job_id: str, patch: Dict[str, Any]) -> None:
    taskboard.task_set(job_id, patch)


# -----------------------
# Request Models
# -----------------------
class ChatRequest(BaseModel):
    text: str
    topic: str = "chat"
    profile: str = "default"
    debug: bool = False
    thinking_mode: Optional[str] = None
    preserve_thinking: Optional[bool] = None
    conversation_id: Optional[str] = None  # Phase 2: continue a thread; new one if absent

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
    thinking_mode: Optional[str] = None
    preserve_thinking: Optional[bool] = None


# -----------------------
# Routes
# -----------------------
@app.get("/")
async def root():
    return {"service": "project_persona", "status": "ok", "docs": "/docs", "health": "/health"}


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "unified_endpoint": PERSONA_URL,
        "async_reasoning_enabled": ASYNC_REASONING_ENABLED,
        "reasoning_inband_enabled": REASONING_INBAND_ENABLED,
        "reasoning_inband_topics": sorted(list(REASONING_INBAND_TOPICS)),
        "thinking_mode_default": THINKING_MODE_DEFAULT,
        "thinking_mode_topics": sorted(list(THINKING_MODE_TOPICS)),
        "thinking_auto_gate": THINKING_AUTO_GATE,
        "preserve_thinking_default": PRESERVE_THINKING_DEFAULT,
        "topic_routing": TOPIC_ROUTING_DEFAULT,
        "topic_routing_topics": TOPIC_PRIORITY,
        "persona_use_messages": PERSONA_USE_MESSAGES,
        "persona_sanitize_messages": PERSONA_SANITIZE_MESSAGES,
        "persona_chat_url": PERSONA_CHAT_URL,
        "sampling_presets": SAMPLING_PRESETS,
        "rag_enabled": RAG_ENABLED,
        "embedder_ok": _embedder is not None,
        "embedder_backend": _embedder_backend,
        "embedder_error": _embedder_error,
        "rag_backend": _rag_backend,
        "rag_ok": _rag_ok,
        "rag_error": _rag_error,
        # chroma_ok kept for back-compat (Phase 1 live gate): true only on the chroma backend.
        "chroma_ok": _rag_ok and _rag_backend == "chroma",
        "chroma_error": _rag_error if _rag_backend == "chroma" else None,
        "rag_per_profile": RAG_PER_PROFILE,
        "rag_collections": sorted(_store.list_collections()),
        "persona_concurrency": PERSONA_CONCURRENCY,
        "profile_wrappers_enabled": PROFILE_WRAPPERS_ENABLED,
        "persona_writeback_enabled": PERSONA_WRITEBACK_ENABLED,
        "memory_distill_enabled": MEMORY_DISTILL_ENABLED,
        "chat_log_writeback_enabled": CHAT_LOG_WRITEBACK_ENABLED,
        "rag_kinds_for_chat": sorted(list(RAG_KINDS_FOR_CHAT)),
        "rag_kinds_for_science": sorted(list(RAG_KINDS_FOR_SCIENCE)),
        "task_store": {"db": TASKS_DB, "count": taskboard.count()},
        "conversations": {"db": CONVERSATIONS_DB, "ok": _convo_ok, "error": _convo_error,
                          "persist_enabled": CONVO_PERSIST_ENABLED},
        "delegate": {
            "default_assignee": os.getenv("DELEGATE_DEFAULT_ASSIGNEE", "default"),
            "default_tenant": os.getenv("DELEGATE_DEFAULT_TENANT", "persona"),
        },
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    profile = (req.profile or DEFAULT_PROFILE).strip()
    topic = resolve_topic(req.topic, req.text)
    ensure_profile_files(profile)

    # Phase 2: resolve/auto-create the conversation and record the user turn.
    conversation_id = req.conversation_id
    if _convo_ok and CONVO_PERSIST_ENABLED and not conversation_id:
        conversation_id = convo.new_conversation(profile=profile)
    _persist_turn(conversation_id, "user", req.text, profile=profile, topic=topic)

    rag_docs: List[str] = []
    rag_used = False
    if RAG_ENABLED:
        rag_docs = memory_query(req.text, k=RAG_TOP_K, kind_filter=rag_kinds_for_topic(topic), profile=profile)
        rag_used = bool(rag_docs)

    inband_notes = ""
    inband_stats: Dict[str, Any] = {}
    inband_used = False
    if REASONING_INBAND_ENABLED and topic in REASONING_INBAND_TOPICS:
        inband_notes, inband_stats = await reasoning_notes_inband(req.text)
        inband_used = bool(inband_notes)

    preset_key, temperature, sampling_extra = sampling_for(topic, req.thinking_mode, req.text)

    reasoning, answer, stats = await persona_generate(
        profile=profile, topic=topic, user_text=req.text,
        rag_docs=rag_docs, reasoning_notes=inband_notes,
        thinking_mode=req.thinking_mode, temperature=temperature,
        max_tokens=PERSONA_MAX_TOKENS, sampling_extra=sampling_extra,
    )
    preserve = resolve_preserve_thinking(req.preserve_thinking)
    reply = finalize_persona_reply(answer, preserve)

    _persist_turn(conversation_id, "assistant", reply, profile=profile, topic=topic)

    distill_dbg = await distill_and_store_facts(req.text, reply, profile=profile, topic=topic)

    if CHAT_LOG_WRITEBACK_ENABLED and PERSONA_WRITEBACK_ENABLED and should_writeback_memory(req.text, reply):
        memory_add(
            f"[chat_log]\n[user]\n{req.text}\n\n[assistant]\n{reply}",
            {"kind": "chat_log", "source": "persona", "profile": profile, "topic": topic, "ts": int(time.time())},
            profile=profile,
        )

    debug = {}
    if req.debug:
        gate_nontrivial, gate_signals = classify_triviality(req.text)
        debug = {
            "rag_used": rag_used,
            "rag_docs_count": len(rag_docs),
            "rag_kinds": sorted(list(rag_kinds_for_topic(topic))),
            "reasoning_inband_used": inband_used,
            "reasoning_inband_stats": inband_stats,
            "thinking_mode_resolved": thinking_prefix(topic, req.thinking_mode, req.text).strip() or "(none)",
            "sampling_preset": preset_key,
            "sampling": {"temperature": temperature, **sampling_extra},
            "thinking_gate": {
                "enabled": THINKING_AUTO_GATE,
                "is_nontrivial": gate_nontrivial,
                "signals": gate_signals,
            },
            "preserve_thinking": {
                "resolved": preserve,
                "reasoning_chars": len(reasoning),
            },
            "sanitizer_applied": will_sanitize(preserve),
            "topic_routing": {
                "enabled": TOPIC_ROUTING_DEFAULT,
                "requested": (req.topic or "chat"),
                "resolved": topic,
            },
            "distill": distill_dbg,
        }

    return {"text": reply, "persona": True, "conversation_id": conversation_id,
            "reasoning": reasoning if preserve else "", "debug": debug}


# -----------------------
# Conversation history (Phase 2) -- conversations.db is the source of truth
# -----------------------
@app.get("/conversations")
async def list_conversations_route(profile: Optional[str] = None, limit: int = 50):
    if not _convo_ok:
        return {"conversations": [], "ok": False, "error": _convo_error}
    return {"conversations": convo.list_conversations(profile=profile, limit=limit), "ok": True}


@app.get("/conversations/{conversation_id}")
async def get_conversation_route(conversation_id: str, limit: Optional[int] = None):
    if not _convo_ok:
        return {"conversation_id": conversation_id, "turns": [], "ok": False, "error": _convo_error}
    turns = convo.get_turns(conversation_id, limit=limit)
    return {"conversation_id": conversation_id, "turns": turns,
            "count": convo.count_turns(conversation_id), "ok": True}


@app.delete("/conversations/{conversation_id}")
async def delete_conversation_route(conversation_id: str):
    if not _convo_ok:
        return {"ok": False, "error": _convo_error}
    return {"ok": convo.delete_conversation(conversation_id)}


@app.get("/jobs")
async def list_jobs(limit: int = 50):
    return {"jobs": taskboard.task_list(limit=limit)}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = taskboard.task_get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


# H2 bridge: delegate a unit of work to the Hermes kanban (executed by a Hermes
# worker on EVO-X2, mirrored back by tools/hermes_bridge.py). Unlike /agent/run
# this does NOT execute taskman2 -- it only writes a "delegated" Task Board row.
# The bridge picks up delegated rows, creates the Hermes card, and mirrors the
# outcome back into this same row (statuses: delegated -> running -> ok|error|
# timeout|blocked). See docs/h2_bridge_design_20260613_0204.md.
DELEGATE_DEFAULT_ASSIGNEE = os.getenv("DELEGATE_DEFAULT_ASSIGNEE", "default")
DELEGATE_DEFAULT_TENANT = os.getenv("DELEGATE_DEFAULT_TENANT", "persona")


@app.post("/agent/delegate")
async def agent_delegate(payload: dict):
    title = str(payload.get("title") or "").strip()
    if not title:
        return JSONResponse(status_code=400, content={"error": "title_required"})
    job_id = str(payload.get("job_id") or payload.get("task_id") or f"delegate-{uuid.uuid4().hex[:12]}")
    existing = taskboard.task_get(job_id)
    if existing is not None:
        return JSONResponse(status_code=409, content={"error": "job_exists", "job_id": job_id})
    state = taskboard.task_set(job_id, {
        "status": "delegated",
        "kind": "hermes_delegate",
        "title": title,
        "body": str(payload.get("body") or ""),
        "assignee": str(payload.get("assignee") or DELEGATE_DEFAULT_ASSIGNEE),
        "tenant": str(payload.get("tenant") or DELEGATE_DEFAULT_TENANT),
        "priority": int(payload.get("priority", 2)),
        "delegated_at": int(time.time()),
    })
    return {"status": "delegated", "job_id": job_id, "job": state}


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
    topic = resolve_topic(req.topic, user_text)
    profile = (req.profile or DEFAULT_PROFILE).strip()
    ensure_profile_files(profile)

    rag_docs: List[str] = []
    if RAG_ENABLED:
        rag_docs = memory_query(user_text, k=RAG_TOP_K, kind_filter=rag_kinds_for_topic(topic), profile=profile)

    max_tokens = int(req.max_tokens or PERSONA_MAX_TOKENS)
    preset_key, preset_temp, sampling_extra = sampling_for(topic, req.thinking_mode, user_text)
    temperature = float(req.temperature) if req.temperature is not None else preset_temp

    reasoning, answer, stats = await persona_generate(
        profile=profile, topic=topic, user_text=user_text,
        rag_docs=rag_docs, reasoning_notes="",
        thinking_mode=req.thinking_mode, temperature=temperature,
        max_tokens=max_tokens, sampling_extra=sampling_extra,
    )
    preserve = resolve_preserve_thinking(req.preserve_thinking)
    reply = finalize_persona_reply(answer, preserve)

    await distill_and_store_facts(user_text, reply, profile=profile, topic=topic)

    cmpl_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    model = req.model or "project_persona"
    prompt_tokens = int(stats.get("tokens_evaluated", 0))
    completion_tokens = int(stats.get("tokens_generated", 0))

    if req.stream:
        def _sse(obj: Dict[str, Any]) -> str:
            return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

        async def event_stream() -> AsyncGenerator[str, None]:
            base = {"id": cmpl_id, "object": "chat.completion.chunk", "created": created, "model": model}
            yield _sse({**base, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]})
            if preserve and reasoning:
                yield _sse({**base, "choices": [{"index": 0, "delta": {"reasoning_content": reasoning}, "finish_reason": None}]})
            for piece in re.findall(r"\S+\s*|\s+", reply):
                if not piece:
                    continue
                yield _sse({**base, "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]})
            yield _sse({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    message: Dict[str, Any] = {"role": "assistant", "content": reply}
    if preserve and reasoning:
        message["reasoning_content"] = reasoning

    return {
        "id": cmpl_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
