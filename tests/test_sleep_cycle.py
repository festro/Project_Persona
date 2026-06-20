#!/usr/bin/env python3
"""Offline tests for the Phase 7 Sleep Cycle (services/api/sleep_cycle.py) + the new
conversations.py consolidation queries.

Uses the REAL conversations store on a temp DB (so conversations_with_undistilled /
undistilled_turns / mark_distilled are exercised) plus a fake RAG store, fake embedder, and
a fake async distiller. No llama-server, no network.

    python tests/test_sleep_cycle.py     # exit 0 = pass, 1 = a failure
"""
import asyncio
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import conversations as cv  # noqa: E402
import sleep_cycle as sc  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


class FakeStore:
    def __init__(self):
        self.cols = {}

    def add(self, collection, doc_id, text, vec, meta):
        self.cols.setdefault(collection, []).append({"id": doc_id, "text": text, "meta": meta})

    def query(self, collection, vec, k, kind_filter=None):
        # stand-in for "nearest": return the docs in the collection (most recent first)
        return [d["text"] for d in reversed(self.cols.get(collection, []))][:k]


def fake_embed(text):
    low = (text or "").lower()
    return [float(len(low)), float(low.count("e")), 1.0]


async def fake_distill(text):
    return (["user's favorite color is teal", "user has a meeting on tuesday"],
            "user shared a color preference and a meeting time")


def main():
    d = tempfile.mkdtemp(prefix="sleepcyc_")
    cv.init_db(str(Path(d) / "conversations.db"))

    # seed a conversation with un-distilled turns
    cid = cv.new_conversation(profile="default", title="t")
    cv.add_turn(cid, "user", "My favorite color is teal and I have a meeting tuesday", profile="default")
    cv.add_turn(cid, "assistant", "Noted: teal, and a meeting on tuesday", profile="default")

    # --- conversations queries ---------------------------------------------
    pending = cv.conversations_with_undistilled(min_turns=2)
    check("conversations_with_undistilled finds the convo", any(r["conversation_id"] == cid for r in pending))
    check("pending count is 2", next(r["pending"] for r in pending if r["conversation_id"] == cid) == 2)
    check("undistilled_turns returns both", len(cv.undistilled_turns(cid)) == 2)

    # --- consolidate full pass ---------------------------------------------
    store = FakeStore()
    journal = []
    res = asyncio.run(sc.consolidate(
        convo=cv, embed=fake_embed, store=store, distill=fake_distill,
        fact_collection="facts", insight_collection="insights",
        journal_write=journal.append, min_turns=2, link_k=3))

    check("one conversation consolidated", res["conversations"] == 1)
    check("two facts stored", res["facts"] == 2 and len(store.cols.get("facts", [])) == 2)
    check("facts marked source=sleep_cycle", all(d["meta"]["source"] == "sleep_cycle" for d in store.cols["facts"]))
    check("turns now marked distilled", cv.undistilled_turns(cid) == [])
    check("relationship links discovered", res["links"] >= 1)
    check("insight stored to insight collection", len(store.cols.get("insights", [])) == 1)
    check("insight journal entry written", len(journal) == 1 and "consolidated" in journal[0])
    check("journal entry carries a fact", "teal" in journal[0])

    # second pass finds nothing left to do
    res2 = asyncio.run(sc.consolidate(convo=cv, embed=fake_embed, store=store, distill=fake_distill,
                                      fact_collection="facts", min_turns=2))
    check("nothing left to consolidate", res2["conversations"] == 0)

    # --- should_continue=False yields immediately (foreground safety) -------
    cid2 = cv.new_conversation(profile="default")
    cv.add_turn(cid2, "user", "another thing to remember for later", profile="default")
    cv.add_turn(cid2, "assistant", "ok noted", profile="default")
    res3 = asyncio.run(sc.consolidate(convo=cv, embed=fake_embed, store=store, distill=fake_distill,
                                      fact_collection="facts", min_turns=2,
                                      should_continue=lambda: False))
    check("should_continue=False does no work", res3["conversations"] == 0)
    check("its turns stay undistilled (not consumed)", len(cv.undistilled_turns(cid2)) == 2)

    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
