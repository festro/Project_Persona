#!/usr/bin/env python3
"""Offline tests for the Phase 6 audit-fix memory endpoints (services/api/server.py):

  - GET  /memory/collections   -> list collections + counts
  - POST /memory/ingest_inbox  -> trigger a Sorting Line pass through the LIVE store
  - GET  /memory/search        -> query a collection

These exist so the single-writer embedded Qdrant store (held by the API) is inspectable +
ingest-triggerable without a second process fighting for the lock. Uses an isolated temp
GLOBAL_MEMORY_DIR + INBOX_DIR; real embedder, no llama, no network.

    python tests/test_memory_endpoints.py     # exit 0 = pass, 1 = a failure
"""
import os
import sys
import tempfile
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

_TMP = Path(tempfile.mkdtemp(prefix="memep_"))
os.environ["GLOBAL_MEMORY_DIR"] = str(_TMP / "global_memory")   # isolate the vector store
os.environ["INBOX_DIR"] = str(_TMP / "inbox")
os.environ["TASKS_DB"] = str(_TMP / "tasks.db")
os.environ["CONVERSATIONS_DB"] = str(_TMP / "conversations.db")
os.environ["JOBS_PERSIST_PATH"] = str(_TMP / "no_jobs.jsonl")
os.environ["SORTING_LINE_WATCH"] = "0"   # don't spin the background watcher
os.environ["SLEEP_CYCLE_ENABLED"] = "0"

warnings.filterwarnings("ignore", message=r"Using .*starlette\.testclient.* is deprecated")

import server  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def main():
    if not server._rag_ok:
        print("RAG store not available; skipping (rag_error:", server._rag_error, ")")
        return 0  # environment without the store -> not a failure of the endpoints

    from fastapi.testclient import TestClient
    client = TestClient(server.app)

    c0 = client.get("/memory/collections").json()
    check("/memory/collections ok", c0.get("ok") is True and isinstance(c0.get("collections"), list))

    # drop a code file in the (temp) inbox and trigger ingestion through the API
    inbox = Path(os.environ["INBOX_DIR"]); inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "snippet.py").write_text("def add(a, b):\n    import math\n    return a + b\n", encoding="utf-8")
    ing = client.post("/memory/ingest_inbox").json()
    check("/memory/ingest_inbox ingested the file", ing.get("ok") is True and ing.get("ingested") == 1)
    coll = ing["results"][0]["collection"]
    check("ingest routed to a provisional collection", coll.endswith("__provisional"))

    c1 = client.get("/memory/collections").json()
    names = {c["name"] for c in c1.get("collections", [])}
    check("new collection now listed with a count", coll in names
          and any(c["name"] == coll and c["count"] == 1 for c in c1["collections"]))

    s = client.get("/memory/search", params={"collection": coll, "q": "function that adds numbers", "k": 1}).json()
    check("/memory/search returns a hit", s.get("ok") is True and len(s.get("hits", [])) == 1)
    check("the hit is the ingested doc", "def add" in (s["hits"][0] if s.get("hits") else ""))

    bad = client.get("/memory/search", params={"collection": "does_not_exist", "q": "x"}).json()
    check("search on a missing collection is safe (ok + empty)", bad.get("ok") is True and bad.get("hits") == [])

    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
