#!/usr/bin/env python3
"""Offline tests for the Phase 6 Sorting Line core (services/api/sorting_line.py).

Covers the pure pipeline with a fake store + fake embedder (no Qdrant, no real model):

  - read_document: stdlib text/markdown/json/html read; unsupported/oversized/binary -> ok=False
  - classify: deterministic keyword routing, embedding-only routing (no keyword hits),
    and the DEFAULT_BIN fallback
  - ingest_text: routes to the bin's PROVISIONAL collection, stores metadata, emits
    ingest_complete via on_event
  - ingest_path: reads a temp file + ingests; read failure -> ok=False (no raise)

    python tests/test_sorting_line.py     # exit 0 = pass, 1 = a failure
"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import sorting_line as sl  # noqa: E402

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
        self.added = []
        self.aliases = {}

    def add(self, collection, doc_id, text, vec, meta):
        self.added.append({"collection": collection, "doc_id": doc_id, "text": text,
                           "vec": vec, "meta": meta})

    def export_points(self, collection):
        for a in self.added:
            if a["collection"] == collection:
                yield {"id": a["doc_id"], "document": a["text"], "vector": a["vec"], "meta": a["meta"]}

    def delete(self, collection, ids):
        ids = set(ids)
        before = len(self.added)
        self.added = [a for a in self.added if not (a["collection"] == collection and a["doc_id"] in ids)]
        return before - len(self.added)

    def set_alias(self, alias, collection):
        self.aliases[alias] = collection
        return True

    def in_(self, collection):
        return [a for a in self.added if a["collection"] == collection]


def fake_embed(text):
    # cheap deterministic 3-vector; only used where the value is stored, not compared
    low = (text or "").lower()
    return [float(len(low)), float(low.count("e")), 1.0]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="sl_"))

    # --- read_document ------------------------------------------------------
    f_txt = tmp / "note.txt"; f_txt.write_text("hello sorting line", encoding="utf-8")
    r = sl.read_document(f_txt)
    check("txt read ok", r.ok and r.text == "hello sorting line" and r.fmt == "txt")

    f_json = tmp / "data.json"; f_json.write_text('{"a": 1}', encoding="utf-8")
    check("json read ok", sl.read_document(f_json).ok)

    f_html = tmp / "page.html"
    f_html.write_text("<html><body><h1>Title</h1><script>x=1</script><p>Body text</p></body></html>",
                      encoding="utf-8")
    rh = sl.read_document(f_html)
    check("html stripped to text", rh.ok and "Title" in rh.text and "Body text" in rh.text and "x=1" not in rh.text)

    f_pdf = tmp / "doc.pdf"; f_pdf.write_bytes(b"%PDF-1.4 fake")
    rp = sl.read_document(f_pdf)
    # pypdf may or may not be installed; either way it must not raise and must report a fmt/error
    check("pdf handled without raising", rp.ok or "pdf" in rp.error.lower())

    f_unknown = tmp / "blob.xyz"; f_unknown.write_bytes(b"\x00\x01\x02binary")
    check("unsupported ext -> ok=False", sl.read_document(f_unknown).ok is False)

    f_big = tmp / "big.txt"; f_big.write_bytes(b"x" * (sl._MAX_BYTES + 1))
    check("oversized -> ok=False", sl.read_document(f_big).ok is False)

    # --- classify -----------------------------------------------------------
    code_text = "def foo():\n    import os\n    return os.getcwd()"
    cbin, _ = sl.classify(code_text)
    check("code text -> code bin", cbin == "code")

    fin_text = "Invoice #42: amount due $1,200 subtotal, please remit payment."
    fbin, _ = sl.classify(fin_text)
    check("finance text -> finance bin", fbin == "finance")

    check("no-match text -> DEFAULT_BIN", sl.classify("zzz qqq")[0] == sl.DEFAULT_BIN)

    # embedding-only routing: keywords match nothing, semantics decide
    bins = {"x": ["foo"], "y": ["bar"]}
    table = {"foo": [1.0, 0.0], "bar": [0.0, 1.0], "zzz": [0.0, 1.0]}
    emb = lambda t: table.get(t, [0.0, 0.0])  # noqa: E731
    protos = sl.build_prototypes(emb, bins)
    sbin, sscores = sl.classify("zzz", bins=bins, embed=emb, prototypes=protos)
    check("embedding-only routing picks the semantically-near bin", sbin == "y")
    check("semantic score beat the zero keyword score", sscores["y"] > sscores["x"])

    # --- ingest_text --------------------------------------------------------
    store = FakeStore()
    events = []
    res = sl.ingest_text(code_text, store=store, embed=fake_embed, source="inbox/test",
                         on_event=lambda e, p: events.append((e, p)))
    check("ingest_text ok", res["ok"] and res["bin"] == "code")
    check("routed to provisional collection",
          res["collection"] == "sl_code__provisional" and len(store.added) == 1)
    meta = store.added[0]["meta"]
    check("stored metadata", meta["kind"] == "inbox_doc" and meta["status"] == "provisional"
          and meta["bin"] == "code" and meta["source"] == "inbox/test")
    check("emitted ingest_complete",
          events and events[0][0] == "ingest_complete" and events[0][1]["doc_id"] == res["doc_id"])
    check("empty text -> ok=False", sl.ingest_text("   ", store=store, embed=fake_embed)["ok"] is False)

    # --- ingest_path --------------------------------------------------------
    store2 = FakeStore()
    f_ing = tmp / "ingest_me.md"
    f_ing.write_text("# Reference guide\nstep 1: install. step 2: configure the api parameter.",
                     encoding="utf-8")
    pres = sl.ingest_path(f_ing, store=store2, embed=fake_embed)
    check("ingest_path ok + routed", pres["ok"] and len(store2.added) == 1)
    check("ingest_path carries origin meta",
          store2.added[0]["meta"].get("origin") == "ingest_me.md" and store2.added[0]["meta"].get("fmt") == "md")
    bad = sl.ingest_path(tmp / "blob.xyz", store=store2, embed=fake_embed)
    check("ingest_path read failure -> ok=False", bad["ok"] is False and "unsupported" in bad["error"])

    # --- process_inbox ------------------------------------------------------
    inbox = Path(tempfile.mkdtemp(prefix="inbox_"))
    (inbox / "good.txt").write_text("def f(): import sys; return sys.argv", encoding="utf-8")
    (inbox / "bad.xyz").write_bytes(b"\x00\x01 binary unsupported")
    (inbox / ".hidden").write_text("ignore me", encoding="utf-8")
    (inbox / "processed").mkdir()  # reserved subdir must be skipped
    store3 = FakeStore()
    evts = []
    results = sl.process_inbox(inbox, store=store3, embed=fake_embed,
                               on_event=lambda e, p: evts.append(e))
    oks = [r for r in results if r.get("ok")]
    check("process_inbox ingested exactly the good file", len(oks) == 1 and len(store3.added) == 1)
    check("good file moved to processed/", (inbox / "processed" / "good.txt").exists())
    check("bad file moved to failed/", (inbox / "failed" / "bad.xyz").exists())
    check("dotfile + reserved subdir skipped", (inbox / ".hidden").exists())
    check("ingest_complete emitted once", evts == ["ingest_complete"])

    # --- promote (provisional -> mature + alias chain) ----------------------
    pstore = FakeStore()
    sl.ingest_text("def g(): return 1  # code snippet import os", store=pstore, embed=fake_embed)
    check("doc starts provisional", len(pstore.in_("sl_code__provisional")) == 1
          and len(pstore.in_("sl_code")) == 0)

    # age trigger excludes a just-ingested doc
    young = sl.promote("code", store=pstore, min_age_s=9999)
    check("young doc not promoted", young["promoted"] == 0 and len(pstore.in_("sl_code")) == 0)

    # min_age_s=0 promotes it: moves to mature, leaves provisional, sets the alias
    res_p = sl.promote("code", store=pstore, min_age_s=0)
    check("promote moved 1 doc", res_p["promoted"] == 1 and res_p["deleted"] == 1)
    check("doc now in mature collection", len(pstore.in_("sl_code")) == 1)
    check("doc removed from provisional", len(pstore.in_("sl_code__provisional")) == 0)
    check("mature doc marked status=mature", pstore.in_("sl_code")[0]["meta"]["status"] == "mature")
    check("alias points at the mature collection",
          pstore.aliases.get("sl_code_current") == "sl_code" and res_p["alias"] == "sl_code_current")

    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
