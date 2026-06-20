#!/usr/bin/env python3
"""Offline tests for the Phase 3 API event publishing (services/api/server.py).

The API fires one-way fire-and-forget control-plane events to the daemon's EventBus and
must NEVER block or raise on a publish. Covers:

  - publish_event with no daemon listening does not raise (the scheduled LoopbackBus
    publish quietly returns False)
  - publish_event called outside an event loop returns gracefully
  - /agent/delegate emits a `task_ready` event (wiring, via a recorder)

Uses temp DBs; no llama-server, no daemon, no network.

    python tests/test_api_events.py     # exit 0 = pass, 1 = a failure
"""
import asyncio
import os
import sys
import tempfile
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

_TMP = Path(tempfile.mkdtemp(prefix="apievt_"))
os.environ["TASKS_DB"] = str(_TMP / "tasks.db")
os.environ["CONVERSATIONS_DB"] = str(_TMP / "conversations.db")
os.environ["JOBS_PERSIST_PATH"] = str(_TMP / "no_such_jobs.jsonl")

warnings.filterwarnings("ignore", message=r"Using .*starlette\.testclient.* is deprecated")

import server  # noqa: E402

checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def main() -> int:
    # publish_event outside any running loop -> graceful no-op, no raise
    raised = False
    try:
        server.publish_event("task_ready", {"job_id": "x"})
    except Exception:  # noqa: BLE001
        raised = True
    check("publish_event off-loop does not raise", raised is False)

    # publish_event inside a loop with no daemon -> schedules a publish that fails quietly
    async def _t():
        server.publish_event("task_ready", {"job_id": "y"})
        await asyncio.sleep(0.4)  # let the scheduled LoopbackBus publish run + fail
    raised2 = False
    try:
        asyncio.run(_t())
    except Exception:  # noqa: BLE001
        raised2 = True
    check("publish_event on-loop with no daemon does not raise", raised2 is False)

    # wiring: /agent/delegate emits task_ready (recorder replaces publish_event)
    recorded = []
    orig = server.publish_event
    server.publish_event = lambda event, payload=None: recorded.append((event, payload))
    try:
        from fastapi.testclient import TestClient
        client = TestClient(server.app)
        resp = client.post("/agent/delegate", json={"title": "Build the daemon"})
        check("/agent/delegate 200", resp.status_code == 200)
        job_id = resp.json().get("job_id")
        evt = next((p for e, p in recorded if e == "task_ready"), None)
        check("delegate emitted task_ready", evt is not None)
        check("task_ready carries job_id + status",
              evt is not None and evt.get("job_id") == job_id and evt.get("status") == "delegated")

        # /health advertises the eventbus block
        h = client.get("/health").json()
        check("/health has eventbus block",
              "eventbus" in h and h["eventbus"].get("enabled") is True and "port" in h["eventbus"])
    finally:
        server.publish_event = orig

    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
