#!/usr/bin/env python3
"""One-shot Sorting Line trigger: ingest everything currently in inbox/ using the live RAG
store + embedder (reused from the API module). The always-on path is the API's background
watcher (SORTING_LINE_WATCH); this is the explicit/manual trigger and the Phase 6 Exit-Gate
driver.

    env/bin/python scripts/ingest_inbox.py [inbox_dir]
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("AI_ROOT", str(ROOT))          # inbox/data/persona resolve under the repo
os.environ.setdefault("SORTING_LINE_WATCH", "0")     # don't also spin the API watcher on import
sys.path.insert(0, str(ROOT / "services" / "api"))

import server  # noqa: E402  (builds the embedder + RAG store)
import sorting_line as sl  # noqa: E402


def main(argv) -> int:
    inbox = argv[1] if len(argv) > 1 else server.INBOX_DIR
    if not (server._rag_ok and server._embedder is not None):
        print(f"RAG not available (rag_ok={server._rag_ok}); cannot ingest.")
        return 1
    results = sl.process_inbox(inbox, store=server._store, embed=server._embed,
                               prototypes=server._sl_prototypes)
    for r in results:
        if r.get("ok"):
            print(f"[ok]   {r.get('origin') or r.get('path')} -> bin={r['bin']} "
                  f"coll={r['collection']} chars={r['chars']}")
        else:
            print(f"[skip] {r.get('path')} -> {r.get('error')}")
    n_ok = sum(1 for r in results if r.get("ok"))
    print(f"ingested {n_ok}/{len(results)} file(s) from {inbox}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
