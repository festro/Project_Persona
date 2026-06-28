"""Self-knowledge ingestion (Brandon 2026-06-28).

Persona could compare *other* projects from fetched web pages but reasoned about ITSELF
from the outside -- it didn't know its own architecture (daemon, Hermes, profiles, the
memory pipeline), so self-referential answers understated what it already has. This module
chunks the project's own architecture docs (knowledge.md, roadmap.md, host_onboarding.md,
...) so server.py can embed them into the persona's memory under a dedicated `project_doc`
kind. Retrieval is vector-gated, so these surface only when a question is actually about
the project.

Only the stdlib is imported, so the chunker is unit-testable offline; server.py does the
embedding/storing/purging against the live (single-writer) Qdrant store.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

# Core architecture/status docs, repo-root-relative. Override with SELF_KNOWLEDGE_DOCS.
DEFAULT_SELF_DOCS = [
    "knowledge.md",            # architecture (the primary self-description)
    "README.md",
    "roadmap.md",              # phase status / what's done
    "docs/host_onboarding.md", # bring-up + EVO-X2 specifics
    "AGENTS.md",
    "WORKFLOW.md",
    "README_models_hardware.md",
]

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _breadcrumb(source: str, heading_path: str) -> str:
    head = f" :: {heading_path}" if heading_path else ""
    return f"[Project_Persona :: {source}{head}]"


def _flush(chunks: List[Dict], source: str, heading_path: str, buf: List[str], max_chars: int, min_chars: int) -> None:
    body = "\n".join(buf).strip()
    if not body:
        return
    # Drop tiny fragments that carry no heading context (e.g. a stray blank-ish line);
    # a fragment under a heading is kept because the breadcrumb gives it meaning.
    if len(body) < min_chars and not heading_path:
        return
    crumb = _breadcrumb(source, heading_path)
    # Reserve room for the breadcrumb + newline so the final chunk text stays within max_chars,
    # even when a section (or a single line) is far larger than the cap.
    budget = max(200, max_chars - len(crumb) - 1)
    start = 0
    while start < len(body):
        end = min(start + budget, len(body))
        if end < len(body):
            # Prefer to break on a newline/space late in the window to avoid mid-word cuts.
            window = body[start:end]
            brk = max(window.rfind("\n"), window.rfind(" "))
            if brk > budget * 0.6:
                end = start + brk
        piece = body[start:end].strip()
        if piece:
            chunks.append({"source": source, "heading": heading_path, "text": f"{crumb}\n{piece}"})
        start = end


def chunk_markdown(text: str, *, source: str, max_chars: int = 1200, min_chars: int = 60) -> List[Dict]:
    """Split markdown into heading-scoped, size-capped chunks.

    Each chunk is prefixed with a `[Project_Persona :: <file> :: <H1 > H2 > ...>]`
    breadcrumb so the embedding (and the model reading it) knows the chunk is about this
    project and where it came from. A section is accumulated whole, then split to max_chars
    (breaking on whitespace where possible); every piece keeps the same breadcrumb.
    """
    chunks: List[Dict] = []
    stack: List[tuple] = []  # (level, title) for the active heading path
    buf: List[str] = []

    def heading_path() -> str:
        return " > ".join(t for _, t in stack)

    for line in (text or "").splitlines():
        m = _HEADING.match(line)
        if m:
            _flush(chunks, source, heading_path(), buf, max_chars, min_chars)
            buf = []
            level = len(m.group(1))
            title = m.group(2).strip()
            stack = [(lvl, t) for (lvl, t) in stack if lvl < level]
            stack.append((level, title))
            continue
        buf.append(line)

    _flush(chunks, source, heading_path(), buf, max_chars, min_chars)
    return chunks


def iter_self_chunks(
    root: str,
    docs: Optional[List[str]] = None,
    *,
    max_chars: int = 1200,
    min_chars: int = 60,
) -> List[Dict]:
    """Read each doc under `root` and return all chunks (missing files are skipped)."""
    out: List[Dict] = []
    for rel in (docs or DEFAULT_SELF_DOCS):
        path = os.path.join(root, rel)
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        out.extend(chunk_markdown(text, source=rel, max_chars=max_chars, min_chars=min_chars))
    return out
