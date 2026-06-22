"""H2 bridge: persona Task Board <-> Hermes native kanban.

Keeps taskboard.py (data/tasks.db) canonical and uses Hermes' kanban as the
execution substrate for delegated work. Two flows:

  Flow A (enqueue): scan the Task Board for status="delegated" rows that have no
    hermes_task_id yet, create a Hermes card via `hermes kanban create --json`,
    and record the returned id back on the row.
  Flow B (mirror): for delegated/running rows that DO have a hermes_task_id, read
    the card via `hermes kanban show <id> --json` and merge the mapped outcome
    (running -> ok|error|timeout|blocked, plus summary/metadata) back onto the row.

Transport is Hermes' PUBLIC CLI surface, never raw kanban.db writes (Hermes routes
all mutation through its tools/CLI). The `runner` and `board` collaborators are
injected so the logic is unit-testable with a faked CLI and an in-memory board.

Design: docs/h2_bridge_design_20260613_0204.md. Runs on EVO-X2 (loopback only).
This module is stdlib-only.
"""
import json
import os
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# runner(args) -> (returncode, stdout, stderr)
Runner = Callable[[List[str]], Tuple[int, str, str]]

HERMES_CLI = os.getenv("HERMES_CLI", "hermes")
BRIDGE_BOARD = os.getenv("HERMES_BRIDGE_BOARD", "")  # "" = Hermes default board
BRIDGE_TENANT = os.getenv("HERMES_BRIDGE_TENANT", "persona")
BACKREF_PREFIX = "persona-job:"

# Hermes run outcomes / event kinds -> persona Task Board status.
# None = leave the persona status unchanged (transient/ignorable signal).
_RUNNING = "running"
_STATUS_MAP: Dict[str, Optional[str]] = {
    "active": _RUNNING,
    "claimed": _RUNNING,
    "promoted": _RUNNING,
    "heartbeat": _RUNNING,
    "reclaimed": _RUNNING,
    "claim_extended": _RUNNING,
    "completed": "ok",
    "blocked": "blocked",
    "gave_up": "error",
    "crashed": "error",
    "timed_out": "timeout",
    "spawn_failed": None,
}
# Hermes task.status fallback when there is no run outcome yet.
# VALID_STATUSES (hermes_cli/kanban_db.py v0.16.0): triage, todo, scheduled,
# ready, running, blocked, review, done, archived.
_COLUMN_MAP: Dict[str, Optional[str]] = {
    "triage": None,
    "todo": None,
    "scheduled": None,
    "ready": None,
    "running": _RUNNING,
    "blocked": "blocked",
    "review": "blocked",
    "done": "ok",
    "archived": "ok",
}


def map_hermes_status(signal: Optional[str]) -> Optional[str]:
    """Map a Hermes run outcome or event kind to a persona status (or None)."""
    if not signal:
        return None
    return _STATUS_MAP.get(str(signal).strip().lower(), None)


def map_hermes_column(column: Optional[str]) -> Optional[str]:
    if not column:
        return None
    return _COLUMN_MAP.get(str(column).strip().lower(), None)


def _backref_body(job_id: str, body: str) -> str:
    return "{} {}\n\n{}".format(BACKREF_PREFIX, job_id, body or "").rstrip() + "\n"


def build_create_args(job_id: str, state: Dict[str, Any],
                      cli: str = HERMES_CLI, board: str = BRIDGE_BOARD) -> List[str]:
    """Build the `hermes kanban create ... --json` argv for a delegated row."""
    title = str(state.get("title") or job_id)
    assignee = str(state.get("assignee") or "default")
    tenant = str(state.get("tenant") or BRIDGE_TENANT)
    priority = int(state.get("priority", 2))
    args = [cli, "kanban", "create", title,
            "--assignee", assignee,
            "--tenant", tenant,
            "--priority", str(priority),
            "--body", _backref_body(job_id, str(state.get("body") or "")),
            "--json"]
    if board:
        args += ["--board", board]
    return args


def _loads_lenient(stdout: str) -> Optional[Any]:
    """Parse JSON that may be surrounded by other CLI chatter."""
    s = (stdout or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except ValueError:
        pass
    for line in reversed(s.splitlines()):
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line)
            except ValueError:
                continue
    start = s.find("{")
    end = s.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(s[start:end + 1])
        except ValueError:
            return None
    return None


def parse_created_id(stdout: str) -> Optional[str]:
    obj = _loads_lenient(stdout)
    if isinstance(obj, dict):
        return obj.get("id") or obj.get("task_id")
    return None


def default_runner(args: List[str], timeout: int = 60) -> Tuple[int, str, str]:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout or "", p.stderr or ""


def _finished_ts(run: Dict[str, Any]) -> int:
    ended = run.get("ended_at") if isinstance(run, dict) else None
    return int(ended) if isinstance(ended, (int, float)) else int(time.time())


def derive_update(show_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Map a `hermes kanban show --json` payload onto a Task Board patch.

    show --json (v0.16.0) is wrapped: {"task": {...}, "latest_summary": str|None,
    "runs": [{id, outcome, summary, error, metadata, ended_at, ...}], "events": [...]}.
    Hermes leaves tasks.result NULL and hands off via the latest run summary, so a
    completed task's text comes from runs[-1].summary (or latest_summary). A blocked
    task carries its reason in the blocked run's summary/error (no block_reason field).
    """
    payload = show_payload or {}
    task = payload.get("task")
    if not isinstance(task, dict):
        # Tolerate a bare task dict (e.g. create output reused).
        task = payload if "status" in payload else {}
    runs = payload.get("runs")
    if not isinstance(runs, list):
        runs = []
    latest = runs[-1] if runs and isinstance(runs[-1], dict) else {}
    outcome = latest.get("outcome")

    patch: Dict[str, Any] = {}
    if runs:
        patch["attempts"] = len(runs)

    # Status precedence: normally the latest run OUTCOME wins (ok/error/timeout), falling back
    # to the column when there is no terminal run yet (running/etc.). EXCEPTION: a card parked
    # in the literal "blocked" column -- e.g. auto-blocked after `dispatch --failure-limit`
    # consecutive crashes -- is authoritative and must surface as "blocked" (awaiting attention,
    # recoverable via `hermes kanban unblock`), NOT the "error" its last crashed run would map to.
    # (H6.3 2026-06-21: without this an auto-blocked card mirrored to /jobs as error, hiding that
    # it is parked and recoverable rather than dead.)
    if str(task.get("status") or "").strip().lower() == "blocked":
        status = "blocked"
    else:
        status = map_hermes_status(outcome) or map_hermes_column(task.get("status"))
    if status:
        patch["status"] = status

    meta = latest.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except ValueError:
            pass

    if status == "ok":
        summary = latest.get("summary") or payload.get("latest_summary")
        if summary is not None:
            patch["summary"] = summary
        if meta is not None:
            patch["metadata"] = meta
        patch["finished_at"] = _finished_ts(latest)
    elif status in ("error", "timeout"):
        patch["finished_at"] = _finished_ts(latest)
        if latest.get("error") is not None:
            patch["error"] = latest.get("error")
    elif status == "blocked":
        reason = latest.get("summary") or latest.get("error") or payload.get("latest_summary")
        if reason is not None:
            patch["block_reason"] = reason
    return patch


def create_card(board: Any, job_id: str, state: Dict[str, Any],
                runner: Runner = default_runner,
                cli: str = HERMES_CLI, board_slug: str = BRIDGE_BOARD) -> Optional[str]:
    """Flow A for one row. Returns the new hermes_task_id, or None on failure."""
    board.task_set(job_id, {"delegate_inflight": int(time.time())})
    rc, out, err = runner(build_create_args(job_id, state, cli=cli, board=board_slug))
    if rc != 0:
        board.task_set(job_id, {"delegate_error": (err or "")[-500:]})
        return None
    tid = parse_created_id(out)
    if not tid:
        board.task_set(job_id, {"delegate_error": "create returned no id"})
        return None
    board.task_set(job_id, {"hermes_task_id": tid,
                            "hermes_board": board_slug or "default",
                            "delegate_inflight": 0,
                            "delegate_error": None})
    return tid


def fetch_task(tid: str, runner: Runner = default_runner,
               cli: str = HERMES_CLI, board_slug: str = BRIDGE_BOARD) -> Optional[Dict[str, Any]]:
    args = [cli, "kanban", "show", tid, "--json"]
    if board_slug:
        args += ["--board", board_slug]
    rc, out, err = runner(args)
    if rc != 0:
        return None
    obj = _loads_lenient(out)
    return obj if isinstance(obj, dict) else None


OPEN_STATUSES = ("delegated", "running")


def enqueue_delegated(board: Any, runner: Runner = default_runner,
                      cli: str = HERMES_CLI, board_slug: str = BRIDGE_BOARD,
                      limit: int = 200) -> List[str]:
    """Create Hermes cards for delegated rows lacking a hermes_task_id."""
    created: List[str] = []
    for row in board.task_list(limit=limit):
        if row.get("status") != "delegated":
            continue
        full = board.task_get(row["job_id"]) or {}
        if full.get("hermes_task_id"):
            continue
        tid = create_card(board, row["job_id"], full, runner=runner, cli=cli, board_slug=board_slug)
        if tid:
            created.append(row["job_id"])
    return created


def mirror_outcomes(board: Any, runner: Runner = default_runner,
                    cli: str = HERMES_CLI, board_slug: str = BRIDGE_BOARD,
                    limit: int = 200) -> List[str]:
    """Merge Hermes card state back onto open delegated/running rows."""
    updated: List[str] = []
    for row in board.task_list(limit=limit):
        if row.get("status") not in OPEN_STATUSES:
            continue
        full = board.task_get(row["job_id"]) or {}
        tid = full.get("hermes_task_id")
        if not tid:
            continue
        task_json = fetch_task(tid, runner=runner, cli=cli, board_slug=board_slug)
        if not task_json:
            continue
        patch = derive_update(task_json)
        if patch.get("status") == _RUNNING and not full.get("started_at"):
            patch["started_at"] = int(time.time())
        if patch:
            board.task_set(row["job_id"], patch)
            updated.append(row["job_id"])
    return updated


def tick(board: Any, runner: Runner = default_runner,
         cli: str = HERMES_CLI, board_slug: str = BRIDGE_BOARD) -> Dict[str, List[str]]:
    """One bridge cycle: enqueue new delegations, then mirror outcomes."""
    return {
        "created": enqueue_delegated(board, runner=runner, cli=cli, board_slug=board_slug),
        "updated": mirror_outcomes(board, runner=runner, cli=cli, board_slug=board_slug),
    }


def _load_board():
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    api = os.path.join(repo, "services", "api")
    if api not in sys.path:
        sys.path.insert(0, api)
    import taskboard
    db = os.getenv("TASKS_DB", os.path.join(repo, "data", "tasks.db"))
    taskboard.init_db(db)
    return taskboard


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="persona <-> Hermes kanban bridge")
    ap.add_argument("--interval", type=float, default=float(os.getenv("HERMES_BRIDGE_INTERVAL", "30")))
    ap.add_argument("--once", action="store_true", help="run a single tick and exit")
    args = ap.parse_args(argv)
    board = _load_board()
    while True:
        result = tick(board)
        if result["created"] or result["updated"]:
            # flush=True: under the daemon supervisor stdout is a pipe (block-buffered), so
            # without this the bridge log stays empty until the buffer fills -- an unattended
            # standing child must log promptly to be observable (H3). (hermes_dispatch_loop
            # already flushes.)
            print("[hermes_bridge] " + json.dumps(result), flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
