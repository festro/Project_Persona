"""Offline unit test for tools/hermes_bridge.py.

Drives the bridge with a faked `hermes` CLI (canned --json) and an in-memory
board, so it needs no Hermes install and no network. Stdlib only.

    python3 tests/test_hermes_bridge.py

Exit code 0 = all pass, 1 = one or more failures.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))

import hermes_bridge as hb

checks_run = 0
failures = []


def check(name, cond):
    global checks_run
    checks_run += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


class FakeBoard:
    def __init__(self):
        self.rows = {}

    def task_set(self, job_id, patch):
        st = self.rows.setdefault(job_id, {"job_id": job_id})
        st.update(patch or {})
        return dict(st)

    def task_get(self, job_id):
        return dict(self.rows[job_id]) if job_id in self.rows else None

    def task_list(self, limit=200):
        return [{"job_id": k, "status": v.get("status")} for k, v in self.rows.items()][:limit]


class FakeHermes:
    """Mimics `hermes kanban create/show --json` (v0.16.0 shapes).

    create -> bare task dict {"id", "status", ...}. show -> wrapped payload
    {"task": {...}, "latest_summary": str|None, "runs": [...], "events": [...]}.
    """
    def __init__(self):
        self.tasks = {}
        self.create_calls = []
        self._ctr = 0

    def runner(self, args):
        if "create" in args:
            self._ctr += 1
            tid = "t_%04d" % self._ctr
            self.create_calls.append(args)
            self.tasks[tid] = {"status": "ready", "runs": [], "latest_summary": None}
            return (0, json.dumps({"id": tid, "status": "ready"}), "")
        if "show" in args:
            tid = args[3]
            t = self.tasks.get(tid)
            if not t:
                return (1, "", "not found")
            payload = {
                "task": {"id": tid, "status": t["status"]},
                "latest_summary": t.get("latest_summary"),
                "parents": [], "children": [], "comments": [], "events": [],
                "runs": t["runs"],
            }
            return (0, "noise line\n" + json.dumps(payload), "")
        return (1, "", "unknown command")

    def set(self, tid, status=None, runs=None, latest_summary=None):
        t = self.tasks[tid]
        if status is not None:
            t["status"] = status
        if runs is not None:
            t["runs"] = runs
        if latest_summary is not None:
            t["latest_summary"] = latest_summary


check("map completed -> ok", hb.map_hermes_status("completed") == "ok")
check("map blocked -> blocked", hb.map_hermes_status("blocked") == "blocked")
check("map gave_up -> error", hb.map_hermes_status("gave_up") == "error")
check("map crashed -> error", hb.map_hermes_status("crashed") == "error")
check("map timed_out -> timeout", hb.map_hermes_status("timed_out") == "timeout")
check("map claimed -> running", hb.map_hermes_status("claimed") == "running")
check("map active -> running", hb.map_hermes_status("active") == "running")
check("map spawn_failed -> None", hb.map_hermes_status("spawn_failed") is None)
check("map unknown -> None", hb.map_hermes_status("wat") is None)
check("map None -> None", hb.map_hermes_status(None) is None)
check("column done -> ok", hb.map_hermes_column("done") == "ok")
check("column ready -> None", hb.map_hermes_column("ready") is None)

args = hb.build_create_args("jobX", {"title": "Do thing", "assignee": "researcher",
                                     "tenant": "persona", "priority": 1, "body": "details"}, cli="hermes")
check("create args has subcommand", args[:3] == ["hermes", "kanban", "create"])
check("create args title", args[3] == "Do thing")
check("create args assignee", "--assignee" in args and args[args.index("--assignee") + 1] == "researcher")
check("create args json flag", "--json" in args)
check("create args body has backref", "persona-job: jobX" in args[args.index("--body") + 1])

check("parse id clean", hb.parse_created_id('{"id": "t_1"}') == "t_1")
check("parse id with chatter", hb.parse_created_id('created!\n{"id": "t_2"}\n') == "t_2")
check("parse id none", hb.parse_created_id("no json here") is None)

board = FakeBoard()
fake = FakeHermes()
board.task_set("d1", {"status": "delegated", "kind": "hermes_delegate", "title": "T1", "assignee": "default"})
board.task_set("d2", {"status": "delegated", "kind": "hermes_delegate", "title": "T2", "assignee": "default"})

created = hb.enqueue_delegated(board, runner=fake.runner)
check("enqueue created both", sorted(created) == ["d1", "d2"])
check("enqueue set hermes_task_id d1", bool(board.task_get("d1").get("hermes_task_id")))
check("enqueue cleared inflight d1", board.task_get("d1").get("delegate_inflight") == 0)

created2 = hb.enqueue_delegated(board, runner=fake.runner)
check("enqueue idempotent (no re-create)", created2 == [])
check("only two create calls total", len(fake.create_calls) == 2)

tid1 = board.task_get("d1")["hermes_task_id"]
fake.set(tid1, status="running", runs=[{"outcome": "active"}])
updated = hb.mirror_outcomes(board, runner=fake.runner)
check("mirror moved d1 to running", board.task_get("d1")["status"] == "running")
check("mirror set started_at", isinstance(board.task_get("d1").get("started_at"), int))
check("mirror reports d1 updated", "d1" in updated)

fake.set(tid1, status="done", runs=[{"outcome": "active", "ended_at": 100},
                                    {"outcome": "completed", "summary": "did it",
                                     "metadata": {"changed_files": ["a.py"]},
                                     "ended_at": 200}])
hb.mirror_outcomes(board, runner=fake.runner)
d1 = board.task_get("d1")
check("mirror completed -> ok", d1["status"] == "ok")
check("mirror carried summary", d1.get("summary") == "did it")
check("mirror carried metadata", d1.get("metadata", {}).get("changed_files") == ["a.py"])
check("mirror finished_at from ended_at", d1.get("finished_at") == 200)
check("mirror counted attempts", d1.get("attempts") == 2)

tid2 = board.task_get("d2")["hermes_task_id"]
fake.set(tid2, status="blocked",
         runs=[{"outcome": "blocked", "summary": "review-required: confirm scope"}])
hb.mirror_outcomes(board, runner=fake.runner)
d2 = board.task_get("d2")
check("mirror blocked -> blocked", d2["status"] == "blocked")
check("mirror block_reason from run summary", "review-required" in (d2.get("block_reason") or ""))

check("ok rows are terminal (mirror skips them)", "d1" not in hb.mirror_outcomes(board, runner=fake.runner))

# Real wrapped show payload: task fields under "task", runs at top level. A gave_up worker
# leaves the card running (gave_up is a deliberate terminal outcome, not a column).
fail_json = {"task": {"id": "t_x", "status": "running"},
             "runs": [{"outcome": "gave_up", "error": "AWS key missing"}]}
patch = hb.derive_update(fail_json)
check("derive gave_up -> error", patch.get("status") == "error")
check("derive gave_up finished_at", isinstance(patch.get("finished_at"), int))
check("derive gave_up error field", patch.get("error") == "AWS key missing")

to_json = {"task": {"id": "t_y", "status": "running"}, "runs": [{"outcome": "timed_out"}]}
check("derive timed_out -> timeout", hb.derive_update(to_json).get("status") == "timeout")

# H6.3 regression: a card auto-blocked after `dispatch --failure-limit` consecutive crashes is
# PARKED in the "blocked" column with a crashed latest run. The bridge must surface "blocked"
# (recoverable via `hermes kanban unblock`), NOT the "error" the crashed run alone would map to.
autoblocked = {"task": {"id": "t_ab", "status": "blocked"},
               "runs": [{"outcome": "crashed", "error": "worker died"},
                        {"outcome": "crashed", "error": "worker died again"}]}
abp = hb.derive_update(autoblocked)
check("derive auto-blocked (crashed run + blocked col) -> blocked", abp.get("status") == "blocked")
check("derive auto-blocked sets block_reason", abp.get("block_reason") == "worker died again")
check("derive auto-blocked counts attempts", abp.get("attempts") == 2)

# Done task with no run outcome still resolves ok via task.status; metadata as JSON string.
done_no_run = {"task": {"id": "t_z", "status": "done"},
               "latest_summary": "wrapped up", "runs": [{"outcome": None, "summary": "wrapped up",
                                                         "metadata": '{"k": 1}'}]}
dpatch = hb.derive_update(done_no_run)
check("derive done(col) -> ok", dpatch.get("status") == "ok")
check("derive parses metadata json string", dpatch.get("metadata") == {"k": 1})
check("derive review -> blocked", hb.map_hermes_column("review") == "blocked")
check("derive scheduled -> None", hb.map_hermes_column("scheduled") is None)

board2 = FakeBoard()
fake2 = FakeHermes()
board2.task_set("e1", {"status": "delegated", "kind": "hermes_delegate", "title": "E1"})
res = hb.tick(board2, runner=fake2.runner)
check("tick created e1", res["created"] == ["e1"])
fake2.set(board2.task_get("e1")["hermes_task_id"], status="done",
          runs=[{"outcome": "completed", "summary": "ok"}])
res2 = hb.tick(board2, runner=fake2.runner)
check("tick mirrored e1 to ok", board2.task_get("e1")["status"] == "ok" and "e1" in res2["updated"])

print()
print("RESULT:", "ALL PASS" if not failures else ("FAILURES: " + ", ".join(failures)))
print("scan : checks={} PASS={} FAIL={}".format(checks_run, checks_run - len(failures), len(failures)))
sys.exit(1 if failures else 0)
