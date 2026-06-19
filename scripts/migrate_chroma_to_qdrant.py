#!/usr/bin/env python3
"""One-time migration: copy every ChromaDB collection into embedded Qdrant (Phase 2a).

Reuses the existing vectors (no re-embedding) so the move is exact: for each Chroma
collection it streams (id, document, vector, metadata) via RagStore.export_points and
upserts them into a QdrantStore at the same on-disk path the server uses. Idempotent
(Qdrant upsert by id). After this runs clean, set RAG_BACKEND=qdrant.

    python scripts/migrate_chroma_to_qdrant.py [--dry-run] [--chroma-dir D] [--qdrant-dir D]

Defaults mirror server.py: <persona/global_memory>/{chroma,qdrant}, overridable by the
same env (GLOBAL_MEMORY_DIR) or the flags. Exit 0 = ok (counts match), 1 = mismatch/error.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "api"))
import ragstore  # noqa: E402

DEFAULT_PERSONA_ROOT = os.getenv(
    "PERSONA_ROOT", str(ROOT / "persona"))
DEFAULT_MEM = os.getenv("GLOBAL_MEMORY_DIR", os.path.join(DEFAULT_PERSONA_ROOT, "global_memory"))


def main(argv):
    ap = argparse.ArgumentParser(description="Migrate ChromaDB -> embedded Qdrant.")
    ap.add_argument("--chroma-dir", default=os.path.join(DEFAULT_MEM, "chroma"))
    ap.add_argument("--qdrant-dir", default=os.path.join(DEFAULT_MEM, "qdrant"))
    ap.add_argument("--default-collection", default=os.getenv("RAG_GLOBAL_COLLECTION", "global_memory"))
    ap.add_argument("--dry-run", action="store_true", help="Report counts only; write nothing.")
    args = ap.parse_args(argv[1:])

    chroma = ragstore.ChromaStore(args.chroma_dir, args.default_collection)
    if not chroma.ok:
        print("ERROR: cannot open Chroma at %s (%s)" % (args.chroma_dir, chroma.error))
        return 1
    colls = chroma.list_collections() or [args.default_collection]
    print("chroma: %s  collections=%s" % (args.chroma_dir, colls))

    # Determine the embedding dimension from the first stored vector.
    dim = None
    for c in colls:
        for p in chroma.export_points(c):
            if p.get("vector"):
                dim = len(p["vector"])
                break
        if dim:
            break
    if dim is None:
        print("nothing to migrate (no vectors found in any Chroma collection)")
        return 0
    print("embedding dim = %d" % dim)

    if args.dry_run:
        for c in colls:
            print("  [dry-run] %-24s chroma_count=%d" % (c, chroma.count(c)))
        print("dry run -- nothing written")
        return 0

    qdrant = ragstore.QdrantStore(args.qdrant_dir, dim=dim)
    if not qdrant.ok:
        print("ERROR: cannot open Qdrant at %s (%s)" % (args.qdrant_dir, qdrant.error))
        return 1

    mismatches = 0
    for c in colls:
        moved = 0
        for p in chroma.export_points(c):
            if not p.get("vector"):
                continue
            qdrant.add(c, p["id"], p.get("document", ""), p["vector"], p.get("meta", {}))
            moved += 1
        src = chroma.count(c)
        dst = qdrant.count(c)
        ok = dst >= moved and dst >= src
        flag = "ok" if ok else "MISMATCH"
        if not ok:
            mismatches += 1
        print("  %-24s chroma=%d -> qdrant=%d (moved %d) [%s]" % (c, src, dst, moved, flag))

    if mismatches:
        print("FAILED: %d collection(s) did not fully migrate" % mismatches)
        return 1
    print("migration complete. Set RAG_BACKEND=qdrant to use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
