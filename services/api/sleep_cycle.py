"""Phase 7 -- the Sleep Cycle: idle-time memory consolidation.

When the persona has been idle, a background pass distills recent un-distilled conversations
into durable facts, discovers relationships between memories, and writes an insight-journal
entry -- without disrupting the foreground (the caller passes a should_continue() that flips
the instant a request arrives, and consolidate() stops between conversations).

Pure pipeline, injected dependencies (like sorting_line.py / eventbus.py): a `convo` module
(conversations_with_undistilled / undistilled_turns / mark_distilled), an `embed`, a `store`
with the RagStore interface, an async `distill(text)->(facts, summary)`, and optional
journal/insight sinks. server.py wires the real LLM distiller + idle loop.
"""
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

DistillFn = Callable[[str], Awaitable[Tuple[List[str], str]]]


def render_turns(turns: List[Dict[str, Any]]) -> str:
    """Render conversation turns into a compact transcript for distillation."""
    parts = []
    for t in turns:
        role = t.get("role", "user")
        content = (t.get("content") or "").strip()
        if content:
            parts.append(f"[{role}] {content}")
    return "\n".join(parts).strip()


def discover_links(vec: List[float], *, store, collection: str, k: int = 3,
                   exclude: Optional[str] = None) -> List[str]:
    """Relationship discovery: the k nearest existing memories to a fact vector (excluding the
    fact itself). The RagStore query returns documents nearest in embedding space -- those ARE
    the related memories. Best-effort: returns [] on any store hiccup."""
    if k <= 0:
        return []
    try:
        hits = store.query(collection, vec, k=k + 1) or []
    except Exception:  # noqa: BLE001
        return []
    out = [h for h in hits if h and h != exclude]
    return out[:k]


def build_insight(conversation_id: str, profile: str, summary: str, facts: List[str],
                  links: int, now: float) -> str:
    """One human-readable insight-journal entry for a consolidated conversation."""
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    lines = [f"## {stamp} -- consolidated {conversation_id} (profile {profile})"]
    if summary:
        lines.append(f"summary: {summary}")
    if facts:
        lines.append(f"facts ({len(facts)}):")
        lines.extend(f"  - {f}" for f in facts)
    lines.append(f"relationship links discovered: {links}")
    return "\n".join(lines)


async def consolidate(*, convo, embed: Callable[[str], List[float]], store, distill: DistillFn,
                      fact_collection: str, insight_collection: Optional[str] = None,
                      journal_write: Optional[Callable[[str], None]] = None,
                      max_convos: int = 5, min_turns: int = 2, link_k: int = 3,
                      should_continue: Optional[Callable[[], bool]] = None,
                      now: Optional[float] = None) -> Dict[str, Any]:
    """Run one consolidation pass. For each conversation with >= min_turns un-distilled turns:
    distill -> facts + summary, store facts (with relationship links), mark the turns distilled,
    and write an insight-journal entry. Stops early (between conversations) if should_continue()
    returns False -- this is how the foreground stays responsive."""
    now = time.time() if now is None else now
    selected = convo.conversations_with_undistilled(min_turns=min_turns, limit=max_convos)
    results: List[Dict[str, Any]] = []
    total_facts = 0
    total_links = 0
    for row in selected:
        if should_continue is not None and not should_continue():
            break  # a request arrived -> yield the foreground
        cid = row["conversation_id"]
        profile = row.get("profile") or "default"
        turns = convo.undistilled_turns(cid)
        if len(turns) < min_turns:
            continue
        try:
            facts, summary = await distill(render_turns(turns))
        except Exception:  # noqa: BLE001 -- a distill failure must not wedge the cycle
            continue
        stored: List[str] = []
        links_found = 0
        for f in facts:
            f = (f or "").strip()
            if not f:
                continue
            vec = embed(f)
            store.add(fact_collection, uuid.uuid4().hex, f, vec,
                      {"kind": "fact", "source": "sleep_cycle", "profile": profile,
                       "conversation_id": cid, "ts": int(now)})
            links_found += len(discover_links(vec, store=store, collection=fact_collection,
                                              k=link_k, exclude=f))
            stored.append(f)
        # only mark distilled once the facts are safely stored
        convo.mark_distilled([t["id"] for t in turns], summary)
        entry = build_insight(cid, profile, summary, stored, links_found, now)
        if insight_collection:
            try:
                store.add(insight_collection, uuid.uuid4().hex, entry, embed(entry),
                          {"kind": "insight", "source": "sleep_cycle", "conversation_id": cid,
                           "ts": int(now)})
            except Exception:  # noqa: BLE001
                pass
        if journal_write is not None:
            try:
                journal_write(entry)
            except Exception:  # noqa: BLE001
                pass
        total_facts += len(stored)
        total_links += links_found
        results.append({"conversation_id": cid, "turns": len(turns),
                        "facts": len(stored), "links": links_found})
    return {"conversations": len(results), "facts": total_facts, "links": total_links,
            "results": results}
