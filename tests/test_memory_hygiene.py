#!/usr/bin/env python3
"""Offline tests for memory hygiene helpers (services/api/memory_hygiene.py).

    python tests/test_memory_hygiene.py     # exit 0 = pass, 1 = a failure
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import memory_hygiene as mh  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# ---- cosine ----
check("cosine identical = 1", abs(mh.cosine([1, 0, 0], [1, 0, 0]) - 1.0) < 1e-9)
check("cosine orthogonal = 0", abs(mh.cosine([1, 0], [0, 1])) < 1e-9)
check("cosine scale-invariant", abs(mh.cosine([1, 1], [2, 2]) - 1.0) < 1e-9)
check("cosine empty -> 0", mh.cosine([], [1, 2]) == 0.0)
check("cosine zero-vector -> 0", mh.cosine([0, 0], [1, 1]) == 0.0)

# ---- cluster_duplicates ----
items = [
    {"id": "a", "vector": [1.0, 0.0], "ts": 10, "document": "prefers dark mode"},
    {"id": "b", "vector": [0.999, 0.04], "ts": 30, "document": "prefers dark mode (newer)"},  # ~dup of a
    {"id": "c", "vector": [0.0, 1.0], "ts": 20, "document": "lives in Denver"},               # distinct
    {"id": "d", "vector": [0.998, 0.06], "ts": 5, "document": "prefers dark mode (oldest)"},   # ~dup of a
]
clusters = mh.cluster_duplicates(items, threshold=0.95)
check("one duplicate cluster found", len(clusters) == 1)
check("cluster has the 3 near-dups", {x["id"] for x in clusters[0]} == {"a", "b", "d"})
check("cluster sorted newest-first (b has ts=30)", clusters[0][0]["id"] == "b")
check("distinct item not clustered", all("c" not in {x["id"] for x in cl} for cl in clusters))

# keep newest, drop the rest
keep, drop = clusters[0][0], clusters[0][1:]
check("keep newest + drop 2", keep["id"] == "b" and {d["id"] for d in drop} == {"a", "d"})

# high threshold -> nothing clusters
check("strict threshold leaves no clusters", mh.cluster_duplicates(items, threshold=0.99999) == [])
check("empty input -> no clusters", mh.cluster_duplicates([], 0.97) == [])
check("missing vectors -> no clusters", mh.cluster_duplicates(
    [{"id": "x", "vector": None, "ts": 1, "document": "a"},
     {"id": "y", "vector": [], "ts": 2, "document": "b"}], 0.5) == [])

# ---- find_orphans ----
facts = [
    {"id": "1", "conversation_id": "live", "document": "from a live convo"},
    {"id": "2", "conversation_id": "deleted", "document": "from a deleted convo"},
    {"id": "3", "conversation_id": None, "document": "distiller fact, no convo"},
    {"id": "4", "conversation_id": "", "document": "empty convo id"},
]
orphans = mh.find_orphans(facts, valid_conversation_ids={"live"})
check("only the deleted-convo fact is orphan", [o["id"] for o in orphans] == ["2"])
check("no-conversation facts are not orphans", all(o["id"] not in ("3", "4") for o in orphans))
check("no orphans when all valid", mh.find_orphans(facts, {"live", "deleted"}) == [])

print(f"\n{checks - len(failures)}/{checks} checks passed")
sys.exit(1 if failures else 0)
