import json
import re
from typing import List, Tuple, Any

# IMPORTANT:
# This template uses Python .format(), so any literal { } must be escaped as {{ }}.
DISTILL_PROMPT = """You are a memory distiller for a local persona system.

Given the user's message and the assistant's reply, extract 1–3 ATOMIC FACTS that are:
- stable over time (preferences, identity, system configuration, ongoing projects)
- useful for future context
- NOT ephemeral (avoid one-off questions like "what can you do?")
- NOT instructions to the assistant
- NOT long explanations
- NOT formatted with bullets

Output MUST be strict JSON only, in this exact schema:

{{"facts":["fact 1","fact 2","fact 3"]}}

Rules:
- 1 to 3 facts max
- each fact <= 140 characters
- no duplicates
- no "Next actions" or list-like phrasing
- if no good facts exist, output {{"facts":[]}}

User message:
{user}

Assistant reply:
{assistant}
"""

def build_distill_prompt(user_text: str, assistant_text: str) -> str:
    u = (user_text or "").strip()
    a = (assistant_text or "").strip()
    return DISTILL_PROMPT.format(user=u, assistant=a)

def _cleanup_fact(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^[-*•]\s+", "", s).strip()
    if re.search(r"(?i)\bnext actions\b", s):
        return ""
    if len(s) > 140:
        s = s[:140].rstrip()
    return s

def _extract_json_object(s: str) -> str:
    m = re.search(r"\{.*\}", s, flags=re.S)
    return m.group(0) if m else ""

def parse_facts(text: str) -> Tuple[List[str], str]:
    """
    Never raises. Returns (facts, error_string). error_string=="" on success.
    Accepts:
      - direct JSON object
      - JSON embedded in other text
      - double-encoded JSON string
      - weird keys like '\"facts\"'
    """
    raw = (text or "").strip()
    if not raw:
        return [], "empty"

    obj: Any = None

    # 1) direct JSON
    try:
        obj = json.loads(raw)
    except Exception:
        # 2) extract JSON object
        j = _extract_json_object(raw)
        if not j:
            return [], "no_json_object"
        try:
            obj = json.loads(j)
        except Exception:
            return [], "json_parse_failed"

    # 3) handle double-encoded JSON (obj is a string containing JSON)
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return [], "double_encoded_json_parse_failed"

    if not isinstance(obj, dict):
        return [], "json_not_object"

    # 4) tolerate weird keys
    if "facts" in obj:
        facts_val = obj.get("facts")
    elif '"facts"' in obj:
        facts_val = obj.get('"facts"')
    elif '\\"facts\\"' in obj:
        facts_val = obj.get('\\"facts\\"')
    else:
        facts_val = []

    if facts_val is None:
        facts_val = []
    if not isinstance(facts_val, list):
        return [], "facts_not_list"

    out: List[str] = []
    seen = set()
    for f in facts_val:
        if not isinstance(f, str):
            continue
        cf = _cleanup_fact(f)
        if not cf:
            continue
        key = cf.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cf)

    return out[:3], ""
