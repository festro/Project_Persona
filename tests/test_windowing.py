#!/usr/bin/env python3
"""Offline tests for hybrid conversation windowing (services/api/windowing.py).

    python tests/test_windowing.py     # exit 0 = pass, 1 = a failure
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import windowing as w  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def turn(role, content, **kw):
    d = {"role": role, "content": content}
    d.update(kw)
    return d


def main():
    # empty
    e = w.window_turns([], 100)
    check("empty -> all empty", e == {"recent": [], "older": [], "summary": ""})

    # everything fits the budget -> all recent, no summary
    small = [turn("user", "hi", tokens=1), turn("assistant", "hello", tokens=1)]
    fit = w.window_turns(small, 100)
    check("all fits -> recent==input", [t["content"] for t in fit["recent"]] == ["hi", "hello"])
    check("all fits -> no older", fit["older"] == [])
    check("all fits -> no summary", fit["summary"] == "")

    # budget forces older turns to summarize; recent stays chronological
    turns = [
        turn("user", "oldest q", tokens=10),
        turn("assistant", "oldest a", tokens=10),
        turn("user", "mid q", tokens=10),
        turn("assistant", "recent a", tokens=10),
        turn("user", "newest q", tokens=10),
    ]
    win = w.window_turns(turns, budget_tokens=25, min_recent=2)
    # newest fit within 25 tokens: newest q(10)+recent a(10)=20, +mid q would be 30>25 -> stop
    check("recent are the newest, chronological",
          [t["content"] for t in win["recent"]] == ["recent a", "newest q"])
    check("older are the rest, chronological",
          [t["content"] for t in win["older"]] == ["oldest q", "oldest a", "mid q"])
    check("summary non-empty when older exist", bool(win["summary"]))
    check("summary mentions an older turn", "mid q" in win["summary"] or "oldest" in win["summary"])

    # min_recent is honored even if it blows the budget
    big = [turn("user", "a" * 400), turn("assistant", "b" * 400), turn("user", "c" * 400)]
    win2 = w.window_turns(big, budget_tokens=1, min_recent=2)
    check("min_recent kept despite tiny budget", len(win2["recent"]) >= 2)

    # distilled older turns contribute their stored summary
    older_distilled = [turn("user", "raw text", distilled=1, summary="user asked about X")]
    s = w._default_summary(older_distilled)
    check("distilled summary used", "user asked about X" in s)

    # summarize callback override
    win3 = w.window_turns(turns, budget_tokens=25, summarize=lambda older: f"CALLBACK:{len(older)}")
    check("summarize callback used", win3["summary"] == "CALLBACK:3")

    # render messages: summary system note + recent role messages
    msgs = w.render_history_messages(win)
    check("render_history_messages first is summary system",
          msgs[0]["role"] == "system" and "Summary of earlier" in msgs[0]["content"])
    check("render_history_messages includes recent roles",
          [m["role"] for m in msgs[1:]] == ["assistant", "user"])

    # render text: contains both blocks
    txt = w.render_history_text(win)
    check("render_history_text has summary block", "Summary of earlier conversation" in txt)
    check("render_history_text has conversation block", "Conversation so far:" in txt)
    check("render empty window -> empty text", w.render_history_text(w.window_turns([], 10)) == "")


main()
print("\n%d checks, %d failures" % (checks, len(failures)))
sys.exit(1 if failures else 0)
