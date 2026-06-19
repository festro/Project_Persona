#!/usr/bin/env python3
"""Offline tests for the RagStore abstraction (services/api/ragstore.py).

Exercises add / query / kind-filter / count / list_collections / export_points for
each available backend, and asserts Chroma<->Qdrant parity on deterministic vectors.
Chroma is always tested; Qdrant only when qdrant-client is installed (skipped, not
failed, otherwise). No network, no server (Qdrant runs :memory: embedded).

    python tests/test_ragstore.py        # exit 0 = pass, 1 = a failure
"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import ragstore  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# Deterministic, well-separated vectors: nearest is unambiguous under both l2
# (Chroma default) and cosine (Qdrant), so parity holds regardless of metric.
DIM = 4
DOCS = [
    ("id-a", "alpha fact", [1.0, 0.0, 0.0, 0.0], "fact"),
    ("id-b", "beta note", [0.0, 1.0, 0.0, 0.0], "note"),
    ("id-c", "gamma fact", [0.0, 0.0, 1.0, 0.0], "fact"),
]
COLL = "global_memory"


def _load(store):
    for doc_id, text, vec, kind in DOCS:
        store.add(COLL, doc_id, text, vec, {"kind": kind, "source": "test"})


def exercise(store, label):
    _load(store)
    check(f"[{label}] count == 3", store.count(COLL) == 3)
    check(f"[{label}] collection listed", COLL in store.list_collections())
    # nearest to alpha
    top = store.query(COLL, [1.0, 0.0, 0.0, 0.0], 3)
    check(f"[{label}] nearest doc is alpha", bool(top) and top[0] == "alpha fact")
    # kind filter: only 'fact' docs, nearest to gamma -> gamma fact
    filt = store.query(COLL, [0.0, 0.0, 1.0, 0.0], 3, kind_filter={"fact"})
    check(f"[{label}] kind filter returns only fact docs",
          set(filt) <= {"alpha fact", "gamma fact"})
    check(f"[{label}] kind-filtered nearest is gamma", bool(filt) and filt[0] == "gamma fact")
    check(f"[{label}] note excluded by fact filter", "beta note" not in filt)
    # k<=0 guard
    check(f"[{label}] k=0 returns []", store.query(COLL, [1.0, 0, 0, 0], 0) == [])
    # export round-trips the documents
    exported = {p["document"] for p in store.export_points(COLL)}
    check(f"[{label}] export_points round-trips docs",
          exported == {"alpha fact", "beta note", "gamma fact"})
    return top, filt


def make_chroma():
    d = tempfile.mkdtemp(prefix="chroma_")
    s = ragstore.ChromaStore(d, COLL)
    return s


def make_qdrant():
    try:
        import qdrant_client  # noqa: F401
    except Exception:
        return None
    return ragstore.QdrantStore(":memory:", dim=DIM)


def main():
    chroma = make_chroma()
    if not chroma.ok:
        check("chroma store init", False)
        print("chroma unavailable: %s" % chroma.error)
        return
    check("chroma store init", chroma.ok and chroma.backend == "chroma")
    c_top, c_filt = exercise(chroma, "chroma")

    qd = make_qdrant()
    if qd is None:
        print("SKIP: qdrant-client not installed -- Qdrant parity not exercised")
    elif not qd.ok:
        check("qdrant store init", False)
        print("qdrant init failed: %s" % qd.error)
    else:
        check("qdrant store init", qd.ok and qd.backend == "qdrant")
        q_top, q_filt = exercise(qd, "qdrant")
        # parity: same top doc + same kind-filtered top across backends
        check("PARITY nearest doc matches", c_top[0] == q_top[0])
        check("PARITY kind-filtered top matches", c_filt[0] == q_filt[0])

    # factory selects backend
    s2 = ragstore.make_store("qdrant", chroma_path="x", default_collection=COLL,
                             qdrant_path=":memory:", dim=DIM)
    check("make_store qdrant -> QdrantStore or graceful",
          s2.backend == "qdrant")
    s3 = ragstore.make_store("chroma", chroma_path=tempfile.mkdtemp(prefix="chroma2_"),
                             default_collection=COLL, qdrant_path=":memory:", dim=DIM)
    check("make_store chroma -> ChromaStore", s3.backend == "chroma")


main()
print("\n%d checks, %d failures" % (checks, len(failures)))
sys.exit(1 if failures else 0)
