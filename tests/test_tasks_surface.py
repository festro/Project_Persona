#!/usr/bin/env python3
"""Offline tests for Phase 2 task surfacing (services/api/server.py).

Covers the data + in-chat surface shared by all three surfaces (in-chat persona, the
OpenWebUI Tool plugin, and the manage.py status panel both consume GET /tasks):

  - is_task_query        : the intent gate (positive/negative)
  - tasks_summary        : normalized board view (title/status, newest first)
  - render_tasks_block   : compact text block for the prompt
  - tasks_block_for      : gated injection (off when disabled or not a task query)
  - GET /tasks           : endpoint shape via TestClient
  - /chat injection      : the tasks block reaches persona_generate + debug.tasks

Uses temp TASKS_DB/CONVERSATIONS_DB (set before importing server); generation is
monkeypatched, so no llama-server and no network.

    python tests/test_tasks_surface.py     # exit 0 = pass, 1 = a failure
"""
import os
import sys
import tempfile
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
API = ROOT / "services" / "api"
sys.path.insert(0, str(API))

_TMP = Path(tempfile.mkdtemp(prefix="tasksurf_"))
os.environ["TASKS_DB"] = str(_TMP / "tasks.db")
os.environ["CONVERSATIONS_DB"] = str(_TMP / "conversations.db")
os.environ["JOBS_PERSIST_PATH"] = str(_TMP / "no_such_jobs.jsonl")  # avoid migrating real jobs.jsonl

warnings.filterwarnings("ignore", message=r"Using .*starlette\.testclient.* is deprecated")

import server  # noqa: E402
import taskboard as tb  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def main():
    # --- intent gate ---------------------------------------------------------
    for q in ["what tasks are running?", "what are you working on?",
              "show me the task board", "any pending jobs?", "what's in the backlog"]:
        check(f"is_task_query + : {q!r}", server.is_task_query(q))
    for q in ["what's the weather tomorrow?", "tell me a joke", "summarize this article"]:
        check(f"is_task_query - : {q!r}", not server.is_task_query(q))

    # --- seed the board + summary/render ------------------------------------
    tb.task_set("job-alpha", {"status": "running", "title": "Index the corpus", "kind": "agent_run"})
    tb.task_set("job-beta", {"status": "delegated", "title": "Draft release notes",
                             "kind": "hermes_delegate", "assignee": "default"})
    summ = server.tasks_summary(limit=10)
    check("tasks_summary count == 2", summ["count"] == 2)
    titles = {t["title"] for t in summ["tasks"]}
    check("tasks_summary carries titles", {"Index the corpus", "Draft release notes"} <= titles)
    check("tasks_summary carries status", {t["status"] for t in summ["tasks"]} == {"running", "delegated"})

    block = server.render_tasks_block(summ, limit=10)
    check("render_tasks_block lists titles", "Index the corpus" in block and "Draft release notes" in block)
    check("render_tasks_block shows status", "[running]" in block and "[delegated]" in block)
    check("render_tasks_block empty case",
          "no tasks" in server.render_tasks_block({"tasks": []}).lower())

    # --- gated injection -----------------------------------------------------
    check("tasks_block_for injects on a task query", bool(server.tasks_block_for("what are you working on?")))
    check("tasks_block_for skips a non-task query", server.tasks_block_for("tell me a joke") == "")
    orig_flag = server.TASKS_INCHAT_ENABLED
    server.TASKS_INCHAT_ENABLED = False
    try:
        check("tasks_block_for skips when disabled", server.tasks_block_for("what tasks are running?") == "")
    finally:
        server.TASKS_INCHAT_ENABLED = orig_flag

    # --- endpoint + /chat injection via TestClient --------------------------
    captured = {}

    async def fake_persona_generate(**kw):
        captured["tasks_block"] = kw.get("tasks_block", "")
        return ("", "a fake persona reply long enough to survive writeback filters", {"tokens_generated": 9, "tokens_evaluated": 20})

    async def fake_distill(*a, **k):
        return {}

    orig_gen, orig_distill, orig_rag = server.persona_generate, server.distill_and_store_facts, server.RAG_ENABLED
    server.persona_generate = fake_persona_generate
    server.distill_and_store_facts = fake_distill
    server.RAG_ENABLED = False
    try:
        from fastapi.testclient import TestClient
        client = TestClient(server.app)

        resp = client.get("/tasks")
        check("GET /tasks returns 200", resp.status_code == 200)
        td = resp.json()
        check("GET /tasks shape", td.get("count") == 2 and len(td.get("tasks", [])) == 2)

        # task-related /chat -> block injected
        captured.clear()
        r1 = client.post("/chat", json={"text": "what are you working on right now?", "debug": True})
        check("/chat task query 200", r1.status_code == 200)
        check("tasks block reached persona_generate", bool(captured.get("tasks_block")))
        check("/chat debug.tasks.injected true", r1.json()["debug"]["tasks"]["injected"] is True)

        # unrelated /chat -> no block
        captured.clear()
        r2 = client.post("/chat", json={"text": "tell me a joke", "debug": True})
        check("non-task query no injection", captured.get("tasks_block", "") == "")
        check("/chat debug.tasks.injected false", r2.json()["debug"]["tasks"]["injected"] is False)
    finally:
        server.persona_generate = orig_gen
        server.distill_and_store_facts = orig_distill
        server.RAG_ENABLED = orig_rag

    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
