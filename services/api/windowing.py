"""Hybrid conversation windowing -- fit prior turns into a token budget (Phase 2).

The newest turns are kept verbatim until the history budget fills; everything older is
folded into a single short summary block. Older turns that were already distilled
(conversations.py mark_distilled) contribute their stored `summary`; the rest fall back
to a truncated snippet, or an injected summarize(older_turns)->str callback (e.g. the
LLM distiller). Pure + unit-tested (tests/test_windowing.py); server.py renders the
result into the persona prompt / messages.

Turn dict shape (from conversations.get_turns): {role, content, tokens?, distilled?,
summary?}. Only role/content are required; tokens is estimated when absent.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def estimate_tokens(text: str) -> int:
    """~4 chars/token; matches server.estimate_tokens. Good enough for budget math."""
    return max(1, len((text or "").strip()) // 4)


def _tok(turn: Dict[str, Any]) -> int:
    t = turn.get("tokens")
    if isinstance(t, int) and t > 0:
        return t
    return estimate_tokens(turn.get("content", ""))


def _truncate_turn(turn: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
    """Return `turn` unchanged, or a shallow copy whose content is clipped to ~max_tokens
    (head+tail kept, a marker in between). Bounds any single historical turn so one oversized
    turn -- e.g. a full web page a chat UI injected into an earlier message -- cannot dominate
    or blow the model's context window. Only ever applied to PRIOR-turn context, never the
    current question being answered, so the live input is never clipped."""
    if max_tokens <= 0 or _tok(turn) <= max_tokens:
        return turn
    body = turn.get("content") or ""
    max_chars = max_tokens * 4  # ~4 chars/token, matches estimate_tokens
    half = max(1, max_chars // 2)
    clipped = body[:half].rstrip() + "\n...[earlier turn truncated to fit context]...\n" + body[-half:].lstrip()
    out = dict(turn)
    out["content"] = clipped
    out["tokens"] = estimate_tokens(clipped)
    return out


def _snippet(turn: Dict[str, Any], max_chars: int = 160) -> str:
    role = turn.get("role", "?")
    if turn.get("distilled") and turn.get("summary"):
        return f"{role}: {turn['summary']}"
    body = (turn.get("content") or "").strip().replace("\n", " ")
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "..."
    return f"{role}: {body}"


def _default_summary(older: List[Dict[str, Any]], max_chars: int = 800) -> str:
    if not older:
        return ""
    lines = [_snippet(t) for t in older]
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[-max_chars:]  # keep the most recent of the older block
    return text


def window_turns(turns: List[Dict[str, Any]], budget_tokens: int, *,
                 min_recent: int = 2,
                 max_turn_tokens: Optional[int] = None,
                 hard_cap_tokens: Optional[int] = None,
                 summarize: Optional[Callable[[List[Dict[str, Any]]], str]] = None) -> Dict[str, Any]:
    """Split chronological `turns` into recent (verbatim) + older (summarized).

    Walks newest->oldest, keeping turns verbatim until the next would exceed
    budget_tokens (but always keeps at least min_recent). Everything older is summarized
    via `summarize` if given, else a built-in truncating heuristic. Returns
    {recent: [...chronological], older: [...chronological], summary: str}.

    `max_turn_tokens` clips any single recent turn (head+tail) so one oversized prior turn
    cannot dominate. `hard_cap_tokens` is an ABSOLUTE ceiling on the recent block that
    `min_recent` may NOT override -- without it, min_recent forces the last N turns in
    regardless of size and a few huge turns blow the model context. Both default None
    (disabled) -> behaviour identical to the pre-cap version.
    """
    if not turns:
        return {"recent": [], "older": [], "summary": ""}
    recent_rev: List[Dict[str, Any]] = []
    used = 0
    older: List[Dict[str, Any]] = []
    for i in range(len(turns) - 1, -1, -1):
        t = turns[i]
        if max_turn_tokens:
            t = _truncate_turn(t, max_turn_tokens)
        tok = _tok(t)
        over_hard = hard_cap_tokens is not None and used + tok > hard_cap_tokens
        over_budget = used + tok > budget_tokens and len(recent_rev) >= min_recent
        if recent_rev and (over_hard or over_budget):
            older = turns[:i + 1]
            break
        recent_rev.append(t)
        used += tok
    recent = list(reversed(recent_rev))
    summary = ""
    if older:
        summary = summarize(older) if summarize else _default_summary(older)
    return {"recent": recent, "older": older, "summary": summary}


def render_history_messages(window: Dict[str, Any]) -> List[Dict[str, str]]:
    """OpenAI-style messages for the recent turns, preceded by a summary system note
    when older turns were folded. Roles pass through (user/assistant)."""
    out: List[Dict[str, str]] = []
    summary = (window or {}).get("summary") or ""
    if summary:
        out.append({"role": "system",
                    "content": "Summary of earlier conversation (context only):\n" + summary})
    for t in (window or {}).get("recent", []):
        role = t.get("role", "user")
        if role not in ("user", "assistant", "system"):
            role = "user"
        out.append({"role": role, "content": t.get("content", "")})
    return out


def render_history_text(window: Dict[str, Any]) -> str:
    """Plain-text history block for the raw /completion prompt path."""
    parts: List[str] = []
    summary = (window or {}).get("summary") or ""
    if summary:
        parts.append("Summary of earlier conversation (context only):\n" + summary)
    recent = (window or {}).get("recent", [])
    if recent:
        lines = []
        for t in recent:
            role = t.get("role", "user")
            label = "User" if role == "user" else ("Assistant" if role == "assistant" else role)
            lines.append(f"{label}: {(t.get('content') or '').strip()}")
        parts.append("Conversation so far:\n" + "\n".join(lines))
    return "\n\n".join(parts)
