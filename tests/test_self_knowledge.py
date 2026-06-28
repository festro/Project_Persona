#!/usr/bin/env python3
"""Offline tests for self-knowledge chunking (services/api/self_knowledge.py).

    python tests/test_self_knowledge.py     # exit 0 = pass, 1 = a failure
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import self_knowledge as skn  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


SAMPLE = """# Architecture
Top-level intro paragraph about the system.

## Memory
Persona uses Qdrant for vector memory.

### Distillation
Facts are distilled from conversations and embedded.

## Daemon
daemon.py supervises llama-server, the API, and Hermes.
"""

chunks = skn.chunk_markdown(SAMPLE, source="knowledge.md", max_chars=1200, min_chars=10)

check("produced multiple chunks", len(chunks) >= 3)
check(
    "every chunk carries a Project_Persona breadcrumb",
    all(c["text"].startswith("[Project_Persona :: knowledge.md") for c in chunks),
)
check(
    "nested heading path is captured (Architecture > Memory > Distillation)",
    any("Architecture > Memory > Distillation" in c["text"] for c in chunks),
)
check(
    "section body travels with its heading",
    any("daemon.py supervises" in c["text"] and "Daemon" in c["heading"] for c in chunks),
)
check("heading metadata is populated", all(c["heading"] for c in chunks))

# Size capping: a long single section splits into multiple chunks, breadcrumb preserved.
big = "# Big\n" + ("word " * 800)  # ~4000 chars under one heading
big_chunks = skn.chunk_markdown(big, source="x.md", max_chars=1000)
check("oversized section splits into several chunks", len(big_chunks) >= 3)
check(
    "split chunks all keep the breadcrumb",
    all(c["text"].startswith("[Project_Persona :: x.md :: Big]") for c in big_chunks),
)
check("no chunk grossly exceeds max_chars", all(len(c["text"]) < 1000 + 200 for c in big_chunks))

# Edge cases.
check("empty text -> no chunks", skn.chunk_markdown("", source="e.md") == [])
check(
    "preamble before any heading is still captured",
    any("preamble" in c["text"] for c in skn.chunk_markdown("preamble line here\n# H\nbody", source="p.md", min_chars=5)),
)

# iter_self_chunks reads real repo docs and skips missing ones.
real = skn.iter_self_chunks(str(ROOT), ["knowledge.md", "does_not_exist_xyz.md"], max_chars=1200)
check("iter_self_chunks ingests an existing repo doc", len(real) > 0)
check("iter_self_chunks tags source", all(c["source"] == "knowledge.md" for c in real))
check("missing files are skipped silently", isinstance(real, list))

print(f"\n{checks - len(failures)}/{checks} checks passed")
sys.exit(1 if failures else 0)
