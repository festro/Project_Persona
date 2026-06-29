"""Memory hygiene sweep (proposal D, Brandon 2026-06-29).

Intake-time contradiction resolution (memory_intake) keeps NEW writes clean; this batch pass
cleans up what's already there: collapses near-duplicate facts (keeping the newest) and flags
facts orphaned from a deleted conversation. Pure + stdlib-only so the clustering/orphan logic is
unit-testable; server.py supplies the vector store (export_points) and the valid conversation ids.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sa = sb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        sa += x * x
        sb += y * y
    if sa <= 0.0 or sb <= 0.0:
        return 0.0
    return dot / math.sqrt(sa * sb)


def cluster_duplicates(items: List[Dict[str, Any]], threshold: float = 0.97) -> List[List[Dict[str, Any]]]:
    """Group items whose vectors are >= threshold cosine-similar (union-find).

    items: [{"id", "vector", "ts", "document"}]. Returns only multi-member clusters, each sorted
    newest-first (by "ts"), so caller can keep clusters[0] and drop the rest.
    """
    n = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    vecs = [it.get("vector") or [] for it in items]
    for i in range(n):
        if not vecs[i]:
            continue
        for j in range(i + 1, n):
            if vecs[j] and cosine(vecs[i], vecs[j]) >= threshold:
                union(i, j)

    groups: Dict[int, List[Dict[str, Any]]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(items[i])
    clusters = [
        sorted(g, key=lambda x: x.get("ts") or 0, reverse=True)
        for g in groups.values() if len(g) > 1
    ]
    # Stable order: largest clusters first, then by newest member.
    clusters.sort(key=lambda c: (len(c), c[0].get("ts") or 0), reverse=True)
    return clusters


def find_orphans(facts: List[Dict[str, Any]], valid_conversation_ids: Set[str]) -> List[Dict[str, Any]]:
    """Facts whose conversation_id is set but no longer exists (the conversation was deleted).

    Facts with no conversation_id (e.g. per-turn distiller facts) are NOT orphans.
    """
    out = []
    for f in facts:
        cid = f.get("conversation_id")
        if cid and cid not in valid_conversation_ids:
            out.append(f)
    return out
