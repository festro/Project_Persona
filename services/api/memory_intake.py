"""Structured memory intake (prototype, Brandon 2026-06-28 -- task B).

The IBOS-integration assessment flagged the strongest idea: Persona's memory write path
distills facts to PLAIN TEXT and embeds them, with no typed validation (dates, entities,
source) and no awareness of contradictions. This module is a schema-first intake layer:
the model extracts ATOMIC, TYPED memory records (statement + type + entities + date +
source + confidence); we validate/coerce them against a schema before they are embedded,
and carry the structure into the point metadata (so memories become filterable, not just
semantically searchable).

Pure + stdlib-only (no LLM, no store) so the schema and parser are unit-testable offline.
server.py supplies the model call (to fill records) and the vector store (to embed + to
surface nearest existing facts for contradiction visibility).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Closed vocabulary of memory types. Anything else coerces to "other".
MEMORY_TYPES = (
    "preference",   # likes/dislikes, working style
    "identity",     # who the user is (role, location, name)
    "fact",         # a stable fact about the user/world
    "event",        # something that happened / is scheduled (usually dated)
    "task",         # a to-do / commitment
    "relationship", # people and how they relate to the user
    "skill",        # what the user knows / tools they use
    "project",      # ongoing work
    "other",
)

_STATEMENT_MAX = 200
_MAX_ENTITIES = 8
# Accept full ISO date or year-month; reject anything else (-> None, i.e. "not time-bound").
_DATE_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_YM = re.compile(r"^\d{4}-\d{2}$")


@dataclass
class MemoryRecord:
    statement: str
    type: str = "fact"
    entities: List[str] = field(default_factory=list)
    date: Optional[str] = None
    source: str = "conversation"
    confidence: float = 0.7


# -----------------------
# Schema coercion + validation (pure)
# -----------------------
def _coerce_entities(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, str):
        parts = re.split(r"[,;]", val)
    elif isinstance(val, (list, tuple)):
        parts = val
    else:
        return []
    out: List[str] = []
    seen = set()
    for p in parts:
        s = str(p).strip()
        if not s:
            continue
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
        if len(out) >= _MAX_ENTITIES:
            break
    return out


def _coerce_date(val: Any) -> Optional[str]:
    if not val:
        return None
    s = str(val).strip()
    if _DATE_FULL.match(s) or _DATE_YM.match(s):
        return s
    return None


def _coerce_confidence(val: Any) -> float:
    try:
        c = float(val)
    except (TypeError, ValueError):
        return 0.7
    return max(0.0, min(1.0, c))


def validate_record(raw: Dict[str, Any]) -> Tuple[Optional[MemoryRecord], List[str]]:
    """Coerce a raw dict into a MemoryRecord. Returns (record|None, errors).

    Only `statement` is strictly required; everything else is coerced to a safe default,
    so a partially-formed model output still yields a usable, typed record.
    """
    errors: List[str] = []
    if not isinstance(raw, dict):
        return None, ["not_an_object"]

    statement = str(raw.get("statement") or raw.get("fact") or "").strip()
    statement = re.sub(r"\s+", " ", statement)
    statement = re.sub(r"^([-*•]\s+)+", "", statement)
    if not statement:
        return None, ["missing_statement"]
    if len(statement) > _STATEMENT_MAX:
        statement = statement[:_STATEMENT_MAX].rstrip()

    rtype = str(raw.get("type") or "fact").strip().lower()
    if rtype not in MEMORY_TYPES:
        errors.append(f"unknown_type:{rtype}->other")
        rtype = "other"

    rec = MemoryRecord(
        statement=statement,
        type=rtype,
        entities=_coerce_entities(raw.get("entities")),
        date=_coerce_date(raw.get("date")),
        source=str(raw.get("source") or "conversation").strip().lower(),
        confidence=_coerce_confidence(raw.get("confidence")),
    )
    return rec, errors


def record_to_text(rec: MemoryRecord) -> str:
    """Embedding text. Statement leads (what we match on); entities appended for recall."""
    if rec.entities:
        return f"{rec.statement} (re: {', '.join(rec.entities)})"
    return rec.statement


def record_to_meta(rec: MemoryRecord, *, profile: Optional[str], topic: str) -> Dict[str, Any]:
    """Flat, store-safe metadata (scalars only) carrying the structure for later filtering."""
    return {
        "kind": "fact",
        "type": rec.type,
        "entities": ", ".join(rec.entities),
        "date": rec.date,
        "source": rec.source,
        "confidence": rec.confidence,
        "structured": True,
        "profile": profile,
        "topic": topic,
        "ts": int(time.time()),
    }


# -----------------------
# Prompt + model-output parsing (pure)
# -----------------------
# .format() template -> literal braces doubled.
INTAKE_PROMPT = """You are a structured memory intake for a local persona system.

From the user's message and the assistant's reply, extract 0-4 ATOMIC, durable memories
worth remembering long-term (preferences, identity, relationships, ongoing projects,
commitments, scheduled events). Skip ephemeral chatter, one-off questions, and instructions
to the assistant.

Return STRICT JSON only, in exactly this schema:

{{"memories":[
  {{"statement":"<one concise sentence, <=200 chars>",
    "type":"<one of: preference|identity|fact|event|task|relationship|skill|project|other>",
    "entities":["<proper nouns: people, projects, tools>"],
    "date":"<YYYY-MM-DD or YYYY-MM if the memory is time-bound, else null>",
    "confidence":<0.0-1.0>}}
]}}

Rules:
- Resolve relative dates ("next Tuesday", "tomorrow") against today: {today}.
- One idea per memory; no duplicates; no bullets or "Next actions" phrasing.
- entities = [] when none; date = null when not time-bound.
- If nothing is worth remembering, return {{"memories":[]}}.

User message:
{user}

Assistant reply:
{assistant}
"""


def build_intake_prompt(user_text: str, assistant_text: str, *, today: str) -> str:
    u = (user_text or "").strip()
    a = (assistant_text or "").strip()
    # Thinking is disabled by the caller via the messages API (enable_thinking=False) -- the
    # reliable Qwen3 control -- so no "/no_think" text suffix is needed here.
    return INTAKE_PROMPT.format(user=u, assistant=a, today=today)


def _strip_think(s: str) -> str:
    s = re.sub(r"(?is)<think>.*?</think>", "", s).strip()
    s = re.sub(r"(?is)<think>.*$", "", s).strip()
    return s


def _extract_json(s: str) -> str:
    # Prefer an object; fall back to a bare array.
    m = re.search(r"\{.*\}", s, flags=re.S)
    if m:
        return m.group(0)
    m = re.search(r"\[.*\]", s, flags=re.S)
    return m.group(0) if m else ""


def parse_intake(text: str) -> Tuple[List[Dict[str, Any]], str]:
    """Never raises. Returns (raw_records, error). error=='' on success.

    Accepts {"memories":[...]}, the legacy {"facts":[...]}, or a bare list; list items may
    be objects or plain strings (a string becomes {"statement": s}).
    """
    raw = _strip_think((text or "").strip())
    if not raw:
        return [], "empty"

    obj: Any = None
    try:
        obj = json.loads(raw)
    except Exception:
        j = _extract_json(raw)
        if not j:
            return [], "no_json"
        try:
            obj = json.loads(j)
        except Exception:
            return [], "json_parse_failed"

    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return [], "double_encoded_parse_failed"

    if isinstance(obj, dict):
        items = obj.get("memories")
        if items is None:
            items = obj.get("facts", [])
    elif isinstance(obj, list):
        items = obj
    else:
        return [], "json_not_object_or_list"

    if not isinstance(items, list):
        return [], "memories_not_list"

    out: List[Dict[str, Any]] = []
    for it in items:
        if isinstance(it, str):
            out.append({"statement": it})
        elif isinstance(it, dict):
            out.append(it)
    return out, ""
