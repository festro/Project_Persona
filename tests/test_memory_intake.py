#!/usr/bin/env python3
"""Offline tests for structured memory intake (services/api/memory_intake.py).

The model call + vector store live in server.py; the schema coercion/validation and the
model-output parser (where correctness actually matters) are pure and tested here.

    python tests/test_memory_intake.py     # exit 0 = pass, 1 = a failure
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import memory_intake as mi  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


# ---- validate_record ----
rec, errs = mi.validate_record(
    {"statement": "Brandon prefers local AI solutions", "type": "preference",
     "entities": ["Brandon"], "date": None, "confidence": 0.9}
)
check("valid record parses", rec is not None and not errs)
check("fields preserved", rec.type == "preference" and rec.entities == ["Brandon"] and rec.confidence == 0.9)

rec2, errs2 = mi.validate_record({"statement": "x", "type": "wizardry"})
check("unknown type -> other (+warning)", rec2.type == "other" and any("unknown_type" in e for e in errs2))

rec3, errs3 = mi.validate_record({"type": "fact"})
check("missing statement -> rejected", rec3 is None and "missing_statement" in errs3)

rec4, _ = mi.validate_record({"statement": "meet Sarah", "date": "2026-07-01"})
check("valid ISO date kept", rec4.date == "2026-07-01")
rec5, _ = mi.validate_record({"statement": "s", "date": "next Tuesday"})
check("non-ISO date -> None", rec5.date is None)
rec6, _ = mi.validate_record({"statement": "s", "date": "2026-07"})
check("year-month date kept", rec6.date == "2026-07")

rec7, _ = mi.validate_record({"statement": "s", "confidence": 5})
check("confidence clamped to <=1", rec7.confidence == 1.0)
rec8, _ = mi.validate_record({"statement": "s", "confidence": "high"})
check("non-numeric confidence -> default", rec8.confidence == 0.7)

rec9, _ = mi.validate_record({"statement": "s", "entities": "Brandon, EVO-X2, Brandon"})
check("string entities split + de-duped", rec9.entities == ["Brandon", "EVO-X2"])

rec10, _ = mi.validate_record({"statement": "- *  messy   whitespace  fact "})
check("statement cleaned (bullets + whitespace)", rec10.statement == "messy whitespace fact")

long = "x" * 300
rec11, _ = mi.validate_record({"statement": long})
check("overlong statement truncated to <=200", len(rec11.statement) <= 200)

check("not-an-object rejected", mi.validate_record(["nope"]) == (None, ["not_an_object"]))

# ---- record_to_text / record_to_meta ----
r = mi.MemoryRecord(statement="Uses Qdrant", type="fact", entities=["Qdrant"])
check("text appends entities", "Uses Qdrant" in mi.record_to_text(r) and "Qdrant" in mi.record_to_text(r))
meta = mi.record_to_meta(r, profile="default", topic="chat")
check("meta is flat + typed", meta["kind"] == "fact" and meta["type"] == "fact"
      and meta["entities"] == "Qdrant" and meta["structured"] is True
      and all(isinstance(v, (str, int, float, bool)) or v is None for v in meta.values()))

# ---- parse_intake ----
recs, e = mi.parse_intake('{"memories":[{"statement":"a","type":"fact"},{"statement":"b"}]}')
check("parses memories array", e == "" and len(recs) == 2)

recs2, e2 = mi.parse_intake('Here you go:\n{"memories":[{"statement":"a"}]}\nhope that helps')
check("extracts JSON embedded in prose", e2 == "" and len(recs2) == 1)

recs3, e3 = mi.parse_intake('<think>let me think...</think>{"memories":[{"statement":"a"}]}')
check("strips <think> block before JSON", e3 == "" and len(recs3) == 1)

recs4, e4 = mi.parse_intake('{"facts":["legacy fact one","legacy fact two"]}')
check("legacy facts[] strings -> statements", e4 == "" and recs4[0]["statement"] == "legacy fact one")

recs5, e5 = mi.parse_intake('[{"statement":"bare list item"}]')
check("bare top-level list accepted", e5 == "" and len(recs5) == 1)

recs6, e6 = mi.parse_intake('{"memories":[]}')
check("empty memories -> no records, no error", e6 == "" and recs6 == [])

recs7, e7 = mi.parse_intake("not json at all")
check("garbage -> error, no crash", recs7 == [] and e7 != "")

recs8, e8 = mi.parse_intake("")
check("empty input -> 'empty'", recs8 == [] and e8 == "empty")

# End-to-end (pure): parse -> validate yields usable typed records.
raws, _ = mi.parse_intake('{"memories":[{"statement":"Brandon runs Project_Persona on an EVO-X2","type":"project","entities":["Brandon","Project_Persona","EVO-X2"]}]}')
recA, errA = mi.validate_record(raws[0])
check("parse->validate end to end", recA is not None and recA.type == "project" and "EVO-X2" in recA.entities)

print(f"\n{checks - len(failures)}/{checks} checks passed")
sys.exit(1 if failures else 0)
