#!/usr/bin/env python3
"""One-shot Sorting Line trigger: ingest everything currently in inbox/.

The embedded Qdrant store is single-writer and held by the API while it runs, so this script
ROUTES THROUGH THE API when it is up (POST /memory/ingest_inbox) and only opens the store
directly when the API is down. That way it never conflicts with the live store lock. The
always-on path is the API's background watcher (SORTING_LINE_WATCH); this is the manual trigger.

    env/bin/python scripts/ingest_inbox.py [inbox_dir]
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = os.getenv("PERSONA_API", "http://127.0.0.1:8000")


def _api_up() -> bool:
    try:
        with urllib.request.urlopen(API + "/health", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def _via_api() -> int:
    req = urllib.request.Request(API + "/memory/ingest_inbox", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.URLError as e:
        print(f"API ingest failed: {e}")
        return 1
    for r in data.get("results", []):
        if r.get("ok"):
            print(f"[ok]   {r.get('origin') or r.get('path')} -> bin={r['bin']} coll={r['collection']}")
        else:
            print(f"[skip] {r.get('path')} -> {r.get('error')}")
    print(f"ingested {data.get('ingested', 0)} file(s) via the live API ({API})")
    return 0 if data.get("ok") else 1


def _direct(inbox) -> int:
    os.environ.setdefault("AI_ROOT", str(ROOT))
    os.environ.setdefault("SORTING_LINE_WATCH", "0")
    os.environ.setdefault("SLEEP_CYCLE_ENABLED", "0")
    sys.path.insert(0, str(ROOT / "services" / "api"))
    import server  # noqa: E402  (builds the embedder + RAG store -- only safe when the API is down)
    import sorting_line as sl  # noqa: E402
    if not (server._rag_ok and server._embedder is not None):
        print(f"RAG not available (rag_ok={server._rag_ok}); cannot ingest.")
        return 1
    results = sl.process_inbox(inbox or server.INBOX_DIR, store=server._store, embed=server._embed,
                               prototypes=server._sl_prototypes)
    for r in results:
        if r.get("ok"):
            print(f"[ok]   {r.get('origin') or r.get('path')} -> bin={r['bin']} coll={r['collection']}")
        else:
            print(f"[skip] {r.get('path')} -> {r.get('error')}")
    print(f"ingested {sum(1 for r in results if r.get('ok'))} file(s) directly (API down)")
    return 0


def main(argv) -> int:
    inbox = argv[1] if len(argv) > 1 else None
    if _api_up():
        if inbox:
            print("note: API is up -> ingesting its configured INBOX_DIR (the dir arg is ignored).")
        return _via_api()
    return _direct(inbox)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
