#!/usr/bin/env python3
"""Offline tests for inline-URL extraction (scripts/webui_patches/persona_inline_urls.py).

The async fetch_inline_urls() needs OpenWebUI, but extract_urls() -- the part where the
real bugs live (curly quotes from copy-paste, trailing punctuation, markdown wrappers) --
is pure stdlib and tested here.

    python tests/test_inline_urls.py     # exit 0 = pass, 1 = a failure
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts" / "webui_patches"))

from persona_inline_urls import extract_urls  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# Brandon's actual symptom: URLs wrapped in smart/curly double quotes from copy-paste.
check(
    "curly-double-quoted url strips the quotes",
    extract_urls('how does it compare to this “https://github.com/festro/Project_Persona”?')
    == ["https://github.com/festro/Project_Persona"],
)
check(
    "curly-single-quoted url strips the quotes",
    extract_urls('explain ‘https://example.com/x’ please')
    == ["https://example.com/x"],
)
# Straight quotes / bare / trailing sentence punctuation.
check(
    "straight-quoted url",
    extract_urls('see "https://example.com/a"') == ["https://example.com/a"],
)
check(
    "trailing period stripped",
    extract_urls("docs at https://example.com/path.") == ["https://example.com/path"],
)
check(
    "trailing comma stripped",
    extract_urls("https://a.com/x, and more") == ["https://a.com/x"],
)
check(
    "markdown link paren not captured",
    extract_urls("[repo](https://github.com/festro/Project_Persona)")
    == ["https://github.com/festro/Project_Persona"],
)
# Multiple URLs, order preserved, de-duplicated.
check(
    "two distinct urls, order preserved",
    extract_urls("compare https://github.com/a/b and https://github.com/c/d")
    == ["https://github.com/a/b", "https://github.com/c/d"],
)
check(
    "duplicate url collapsed",
    extract_urls("https://x.com vs https://x.com") == ["https://x.com"],
)
# Query strings + fragments survive (only sentence punctuation is trailing-stripped).
check(
    "query string preserved",
    extract_urls("go to https://e.com/s?q=a&n=2 now") == ["https://e.com/s?q=a&n=2"],
)
# Negatives.
check("no url -> empty", extract_urls("just a plain question about mutexes") == [])
check("empty string -> empty", extract_urls("") == [])
check("non-http scheme ignored", extract_urls("ftp://host/file or mailto:a@b.com") == [])
# Limit.
check(
    "limit caps the count",
    extract_urls(
        "https://1.com https://2.com https://3.com https://4.com https://5.com", limit=4
    )
    == ["https://1.com", "https://2.com", "https://3.com", "https://4.com"],
)

print(f"\n{checks - len(failures)}/{checks} checks passed")
sys.exit(1 if failures else 0)
