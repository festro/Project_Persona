"""Phase 6 -- the Sorting Line: dropped files become classified, retrievable memory.

A file dropped in inbox/ is READ (multi-format), CLASSIFIED into a content bin, and ROUTED
into that bin's PROVISIONAL Qdrant collection with metadata; later it promotes to the bin's
MATURE collection (lifecycle in task 16). This module is the pure pipeline -- it depends only
on an injected `embed(text)->vector` and a `store` with the RagStore interface (add/query/...),
exactly like eventbus.py / conversations.py depend on nothing project-specific. The watcher +
server wiring inject the real embedder, store, and EventBus.

Reader posture (lean): stdlib handles the text family (txt/md/code/json/csv/html, decoded with
a utf-8/latin-1 fallback); pdf/docx are read only if their optional libs are present, otherwise
the file is reported unsupported -- never a hard dependency on the inference tier.
"""
import html
import json
import os
import re
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Content bins (keyword prototypes). Each bin routes to its own provisional/mature collection.
# Keyword scoring is the deterministic baseline; an injected embedder adds semantic similarity.
DEFAULT_BINS: Dict[str, List[str]] = {
    "code": ["def", "class", "import", "function", "const", "return", "git", "python",
             "javascript", "typescript", "compile", "stack trace", "exception", "</", "());"],
    "research": ["abstract", "hypothesis", "experiment", "method", "results", "conclusion",
                 "figure", "dataset", "we propose", "this paper", "study", "benchmark"],
    "reference": ["documentation", "manual", "how to", "usage", "example",
                  "parameter", "configure", "install", "api reference", "guide", "cheat sheet"],
    # NB: bare pronouns (i/my/we) were dropped -- far too common, they swallowed everything;
    # personal now keys on specific cues + word-boundary matching (see _kw_hit).
    "personal": ["remember", "note to self", "todo", "to-do", "meeting", "reminder",
                 "appointment", "my favorite", "i need to", "don't forget", "my birthday",
                 "grocer", "i live", "i work at"],
    "finance": ["invoice", "payment", "receipt", "budget", "expense", "tax", "balance",
                "amount due", "subtotal", "$", "usd", "transaction"],
}
DEFAULT_BIN = "misc"


def _kw_hit(low: str, kw: str) -> bool:
    """Match a keyword: multi-word phrases and tokens with non-word chars use substring;
    single words use a WORD BOUNDARY so short cues ('git', 'tax') don't match inside other
    words ('digit', 'syntax') -- the old substring match made common tokens over-fire."""
    if " " in kw or not kw.isalnum():
        return kw in low
    return re.search(r"\b" + re.escape(kw) + r"\b", low) is not None

# Extensions read as plain text (decode + store as-is).
_TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json", ".jsonl",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".tex",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".c", ".h", ".cpp", ".hpp",
    ".java", ".rb", ".php", ".sh", ".bash", ".zsh", ".sql", ".css", ".scss",
}
_HTML_EXTS = {".html", ".htm", ".xhtml"}
_MAX_BYTES = int(os.getenv("SORTING_LINE_MAX_BYTES", str(8 << 20)))  # 8 MiB default cap


class ReadResult:
    def __init__(self, ok: bool, text: str = "", fmt: str = "", *, error: str = "",
                 nbytes: int = 0):
        self.ok = ok
        self.text = text
        self.fmt = fmt
        self.error = error
        self.nbytes = nbytes


class _TextHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        return html.unescape(" ".join(" ".join(self._chunks).split()))


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def read_document(path) -> ReadResult:
    """Read a file into text. ok=False (never raises) for unsupported/oversized/binary."""
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError as e:
        return ReadResult(False, error=f"stat_failed: {e}")
    if size > _MAX_BYTES:
        return ReadResult(False, error=f"too_large ({size} > {_MAX_BYTES})", nbytes=size)
    ext = p.suffix.lower()

    if ext in _TEXT_EXTS or ext == "":
        try:
            raw = p.read_bytes()
        except OSError as e:
            return ReadResult(False, error=f"read_failed: {e}")
        text = _decode(raw)
        if ext == "" and "\x00" in text[:1024]:
            return ReadResult(False, error="binary_no_ext", nbytes=size)
        return ReadResult(True, text.strip(), fmt=(ext.lstrip(".") or "text"), nbytes=size)

    if ext in _HTML_EXTS:
        try:
            parser = _TextHTMLParser()
            parser.feed(_decode(p.read_bytes()))
            return ReadResult(True, parser.text().strip(), fmt="html", nbytes=size)
        except Exception as e:  # noqa: BLE001
            return ReadResult(False, error=f"html_parse_failed: {e}", nbytes=size)

    if ext == ".pdf":
        try:
            import pypdf  # optional
        except ImportError:
            return ReadResult(False, error="pdf_unsupported (pip install pypdf)", nbytes=size)
        try:
            reader = pypdf.PdfReader(str(p))
            text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
            return ReadResult(True, text.strip(), fmt="pdf", nbytes=size)
        except Exception as e:  # noqa: BLE001
            return ReadResult(False, error=f"pdf_read_failed: {e}", nbytes=size)

    if ext in (".docx",):
        try:
            import docx  # optional (python-docx)
        except ImportError:
            return ReadResult(False, error="docx_unsupported (pip install python-docx)", nbytes=size)
        try:
            d = docx.Document(str(p))
            return ReadResult(True, "\n".join(par.text for par in d.paragraphs).strip(),
                              fmt="docx", nbytes=size)
        except Exception as e:  # noqa: BLE001
            return ReadResult(False, error=f"docx_read_failed: {e}", nbytes=size)

    return ReadResult(False, error=f"unsupported_format ({ext or 'none'})", nbytes=size)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def build_prototypes(embed: Callable[[str], List[float]],
                     bins: Optional[Dict[str, List[str]]] = None) -> Dict[str, List[float]]:
    """Embed each bin's keyword prototype once so classify() can add a semantic score."""
    bins = bins or DEFAULT_BINS
    return {name: embed(" ".join(kws)) for name, kws in bins.items()}


def classify(text: str, *, bins: Optional[Dict[str, List[str]]] = None,
             embed: Optional[Callable[[str], List[float]]] = None,
             prototypes: Optional[Dict[str, List[float]]] = None,
             kw_weight: float = 1.0, sem_weight: float = 3.0) -> Tuple[str, Dict[str, float]]:
    """Route text to a content bin. Deterministic keyword hits, plus -- when an embedder
    (and prototypes) are supplied -- a weighted cosine-to-prototype semantic score. Returns
    (bin, scores). Falls back to DEFAULT_BIN when nothing scores."""
    bins = bins or DEFAULT_BINS
    low = (text or "").lower()
    scores: Dict[str, float] = {}
    vec = None
    if embed is not None and prototypes:
        try:
            vec = embed(text)
        except Exception:  # noqa: BLE001
            vec = None
    for name, kws in bins.items():
        kw = sum(1 for kw_ in kws if _kw_hit(low, kw_))
        sem = _cosine(vec, prototypes.get(name, [])) if (vec is not None and prototypes) else 0.0
        scores[name] = kw_weight * kw + sem_weight * max(sem, 0.0)
    best = max(scores, key=lambda k: scores[k]) if scores else DEFAULT_BIN
    if not scores or scores[best] <= 0.0:
        return DEFAULT_BIN, scores
    return best, scores


def provisional_collection(bin_name: str) -> str:
    return f"sl_{bin_name}__provisional"


def mature_collection(bin_name: str) -> str:
    return f"sl_{bin_name}"


def ingest_text(text: str, *, store, embed: Callable[[str], List[float]],
                source: str = "inbox", bins: Optional[Dict[str, List[str]]] = None,
                prototypes: Optional[Dict[str, List[float]]] = None,
                on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                meta_extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Classify + embed + route text into its bin's PROVISIONAL collection. Returns a result
    dict; emits ingest_complete via on_event. Best-effort -- returns ok=False on empty text."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty"}
    bin_name, scores = classify(text, bins=bins, embed=embed, prototypes=prototypes)
    coll = provisional_collection(bin_name)
    doc_id = uuid.uuid4().hex
    vec = embed(text)
    meta: Dict[str, Any] = {
        "kind": "inbox_doc", "source": source, "bin": bin_name, "status": "provisional",
        "ingested_at": int(time.time()), "chars": len(text),
    }
    if meta_extra:
        meta.update(meta_extra)
    store.add(coll, doc_id, text, vec, meta)
    result = {"ok": True, "doc_id": doc_id, "bin": bin_name, "collection": coll,
              "chars": len(text), "source": source, "scores": scores}
    if on_event is not None:
        try:
            on_event("ingest_complete", {k: result[k] for k in ("doc_id", "bin", "collection", "chars", "source")})
        except Exception:  # noqa: BLE001 -- a publish must never break ingestion
            pass
    return result


def ingest_path(path, *, store, embed: Callable[[str], List[float]],
                bins: Optional[Dict[str, List[str]]] = None,
                prototypes: Optional[Dict[str, List[float]]] = None,
                on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    """Read a file then ingest_text it. Returns ok=False (never raises) on read failure."""
    p = Path(path)
    rr = read_document(p)
    if not rr.ok:
        return {"ok": False, "error": rr.error, "path": str(p), "fmt": rr.fmt}
    res = ingest_text(rr.text, store=store, embed=embed, source=str(p), bins=bins,
                      prototypes=prototypes, on_event=on_event,
                      meta_extra={"fmt": rr.fmt, "origin": p.name, "nbytes": rr.nbytes})
    res["path"] = str(p)
    return res


# Files the watcher manages but never ingests.
_RESERVED_SUBDIRS = ("processed", "failed")


def _move_unique(src: Path, dest_dir: Path) -> Path:
    """Move src into dest_dir, disambiguating on name collision. Returns the new path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / src.name
    if target.exists():
        target = dest_dir / f"{src.stem}.{uuid.uuid4().hex[:8]}{src.suffix}"
    src.rename(target)
    return target


def mature_alias(bin_name: str) -> str:
    return f"sl_{bin_name}_current"


def age_trigger(min_age_s: float, now: Optional[float] = None):
    """Default promotion trigger: a provisional doc graduates once it has survived min_age_s."""
    ref = time.time() if now is None else now

    def _select(meta: Dict[str, Any]) -> bool:
        return (ref - float(meta.get("ingested_at", 0) or 0)) >= min_age_s

    return _select


def promote(bin_name: str, *, store, select: Optional[Callable[[Dict[str, Any]], bool]] = None,
            min_age_s: float = 0.0, set_alias: bool = True,
            now: Optional[float] = None) -> Dict[str, Any]:
    """Promote provisional docs that pass `select` (default: age >= min_age_s) into the bin's
    MATURE collection -- re-add with status=mature + promoted_at, then delete from provisional.
    Optionally point the bin's alias at the mature collection (the alias chain, so retrieval can
    target a stable name while the physical collection is rebuilt). Returns a summary dict.
    Best-effort: a point with no stored vector is skipped (can't re-add it)."""
    prov = provisional_collection(bin_name)
    mat = mature_collection(bin_name)
    if select is None:
        select = age_trigger(min_age_s, now=now)
    promoted_ids: List[Any] = []
    for pt in list(store.export_points(prov)):
        meta = dict(pt.get("meta") or {})
        if not select(meta) or pt.get("vector") is None:
            continue
        new_meta = {**meta, "status": "mature", "promoted_at": int(time.time())}
        store.add(mat, uuid.uuid4().hex, pt.get("document", ""), pt["vector"], new_meta)
        promoted_ids.append(pt["id"])
    deleted = store.delete(prov, promoted_ids) if promoted_ids else 0
    alias_ok = False
    if set_alias and promoted_ids:
        try:
            alias_ok = bool(store.set_alias(mature_alias(bin_name), mat))
        except Exception:  # noqa: BLE001
            alias_ok = False
    return {"bin": bin_name, "promoted": len(promoted_ids), "deleted": deleted,
            "from": prov, "to": mat, "alias": mature_alias(bin_name) if alias_ok else None}


def process_inbox(inbox_dir, *, store, embed: Callable[[str], List[float]],
                  bins: Optional[Dict[str, List[str]]] = None,
                  prototypes: Optional[Dict[str, List[float]]] = None,
                  on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                  move: bool = True) -> List[Dict[str, Any]]:
    """One-shot: ingest every regular file currently in inbox_dir (skipping dotfiles and the
    processed/ + failed/ subdirs), then move each to inbox/processed (ok) or inbox/failed
    (read error). Returns the per-file results. Synchronous + side-effecting; the async
    watcher wraps this and re-publishes ingest_complete on the loop."""
    inbox = Path(inbox_dir)
    inbox.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    for p in sorted(inbox.iterdir()):
        if p.is_dir() or p.name.startswith(".") or p.name in _RESERVED_SUBDIRS:
            continue
        if not p.is_file():
            continue
        res = ingest_path(p, store=store, embed=embed, bins=bins, prototypes=prototypes,
                          on_event=on_event)
        if move:
            dest = inbox / ("processed" if res.get("ok") else "failed")
            try:
                res["moved_to"] = str(_move_unique(p, dest))
            except OSError as e:
                res["move_error"] = str(e)
        results.append(res)
    return results
