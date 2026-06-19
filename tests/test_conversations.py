#!/usr/bin/env python3
"""Offline tests for the conversation history store (services/api/conversations.py).

Stdlib sqlite3 only; uses a temp DB. Exercises add/get (chronological + recent-limit),
auto-creation, per-profile listing, count, distill-flagging, and delete.

    python tests/test_conversations.py     # exit 0 = pass, 1 = a failure
"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import conversations as cv  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def main():
    d = tempfile.mkdtemp(prefix="conv_")
    cv.init_db(str(Path(d) / "conversations.db"))

    cid = cv.new_conversation(profile="default", title="t1")
    check("new_conversation returns id", isinstance(cid, str) and len(cid) > 0)

    # add_turn auto-bumps + returns ids in order
    t1 = cv.add_turn(cid, "user", "hello", profile="default", topic="chat", tokens=2)
    t2 = cv.add_turn(cid, "assistant", "hi there", profile="default", topic="chat", tokens=3)
    t3 = cv.add_turn(cid, "user", "what's 2+2?", profile="default", topic="math", tokens=5)
    check("turn ids increase", t1 < t2 < t3)
    check("count_turns == 3", cv.count_turns(cid) == 3)

    turns = cv.get_turns(cid)
    check("get_turns chronological", [t["content"] for t in turns] == ["hello", "hi there", "what's 2+2?"])
    check("turn carries role", turns[0]["role"] == "user")
    check("turn carries topic", turns[2]["topic"] == "math")
    check("turn distilled defaults 0", turns[0]["distilled"] == 0)

    # recent-limit returns the last N, still chronological
    recent = cv.get_turns(cid, limit=2)
    check("limit returns recent-but-chronological",
          [t["content"] for t in recent] == ["hi there", "what's 2+2?"])

    # auto-create on add_turn to a fresh id
    cid2 = "explicit-id-123"
    cv.add_turn(cid2, "user", "new thread", profile="bob")
    check("add_turn auto-creates conversation", cv.count_turns(cid2) == 1)

    # per-profile listing, newest first
    conv_default = cv.list_conversations(profile="default")
    conv_bob = cv.list_conversations(profile="bob")
    check("list scoped to default", [c["conversation_id"] for c in conv_default] == [cid])
    check("list scoped to bob", [c["conversation_id"] for c in conv_bob] == [cid2])
    check("list all sees both", len(cv.list_conversations()) == 2)

    # distill flagging + summary
    n = cv.mark_distilled([t1, t2], summary="user greeted; assistant replied")
    check("mark_distilled updates 2 rows", n == 2)
    turns2 = cv.get_turns(cid)
    check("distilled flag set", turns2[0]["distilled"] == 1 and turns2[1]["distilled"] == 1)
    check("summary attached", turns2[0]["summary"] == "user greeted; assistant replied")
    check("undistilled untouched", turns2[2]["distilled"] == 0)
    check("mark_distilled([]) is 0", cv.mark_distilled([]) == 0)

    # delete cascades turns
    check("delete returns True", cv.delete_conversation(cid) is True)
    check("turns gone after delete", cv.count_turns(cid) == 0)
    check("conversation gone", cv.list_conversations(profile="default") == [])
    check("delete missing returns False", cv.delete_conversation("nope") is False)


main()
print("\n%d checks, %d failures" % (checks, len(failures)))
sys.exit(1 if failures else 0)
