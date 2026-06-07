"""SQLite-backed Task Board -- replaces the in-memory jobs dict + run/jobs.jsonl.

Stdlib sqlite3 only (no extra deps). One row per job_id holding a merged JSON
`state` blob plus a queryable `status` column and created/updated timestamps.

Design notes:
- A fresh connection per call (not a shared module-level connection): the API
  reaches this from asyncio.to_thread worker threads, and sqlite3 forbids sharing
  one connection across threads. WAL + a busy timeout keep concurrent read/write
  safe. Because each call opens its own connection, the store must be FILE-backed
  (":memory:" would give every call its own empty DB).
- task_set merges a patch into the existing state (same semantics as the old
  jobs.setdefault(id, {}).update(patch) helper), so callers can accrete fields
  across a job's lifecycle.
"""
import json
import os
import sqlite3
import time
from contextlib import closing
from typing import Any, Dict, List, Optional

_DB_PATH: Optional[str] = None


def init_db(db_path: str, migrate_jsonl: Optional[str] = None) -> None:
    """Create the store (idempotent). Optionally one-time import an old jobs.jsonl."""
    global _DB_PATH
    _DB_PATH = db_path
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    with closing(_connect()) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            " job_id TEXT PRIMARY KEY,"
            " status TEXT,"
            " state TEXT NOT NULL DEFAULT '{}',"
            " created_at INTEGER NOT NULL,"
            " updated_at INTEGER NOT NULL)"
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at)")
        con.commit()
    if migrate_jsonl and os.path.isfile(migrate_jsonl) and count() == 0:
        migrate_from_jsonl(migrate_jsonl)


def _connect() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("taskboard.init_db() has not been called")
    con = sqlite3.connect(_DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def task_set(job_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert-merge `patch` into the job's state; return the merged state."""
    now = int(time.time())
    with closing(_connect()) as con:
        row = con.execute("SELECT state, created_at FROM tasks WHERE job_id=?", (job_id,)).fetchone()
        state: Dict[str, Any] = json.loads(row["state"]) if row else {}
        state.update(patch or {})
        status = state.get("status")
        status = str(status) if status is not None else None
        blob = json.dumps(state, ensure_ascii=False)
        if row:
            con.execute(
                "UPDATE tasks SET state=?, status=?, updated_at=? WHERE job_id=?",
                (blob, status, now, job_id),
            )
        else:
            con.execute(
                "INSERT INTO tasks(job_id, status, state, created_at, updated_at) VALUES(?,?,?,?,?)",
                (job_id, status, blob, now, now),
            )
        con.commit()
    return state


def task_get(job_id: str) -> Optional[Dict[str, Any]]:
    """Return the merged state for a job (with _created_at/_updated_at), or None."""
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT job_id, state, created_at, updated_at FROM tasks WHERE job_id=?",
            (job_id,),
        ).fetchone()
    if not row:
        return None
    state: Dict[str, Any] = json.loads(row["state"])
    state.setdefault("job_id", row["job_id"])
    state["_created_at"] = row["created_at"]
    state["_updated_at"] = row["updated_at"]
    return state


def task_list(limit: int = 50) -> List[Dict[str, Any]]:
    """Recent jobs (id/status/timestamps), newest first."""
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT job_id, status, created_at, updated_at FROM tasks "
            "ORDER BY updated_at DESC, created_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def task_delete(job_id: str) -> bool:
    with closing(_connect()) as con:
        cur = con.execute("DELETE FROM tasks WHERE job_id=?", (job_id,))
        con.commit()
        return cur.rowcount > 0


def count() -> int:
    with closing(_connect()) as con:
        return int(con.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()["c"])


def migrate_from_jsonl(path: str, max_lines: int = 50000) -> int:
    """Best-effort import of the legacy jobs.jsonl event log. Returns rows touched."""
    touched = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return 0
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except ValueError:
            continue
        jid = evt.get("job_id")
        patch = evt.get("patch") or {}
        if not jid:
            continue
        task_set(jid, patch)
        touched += 1
    return touched
