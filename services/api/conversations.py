"""SQLite-backed conversation history (conversations.db) -- Phase 2 source of truth.

Stdlib sqlite3 only, same posture as taskboard.py: a fresh connection per call (the
API reaches this from asyncio.to_thread worker threads, and sqlite3 forbids sharing one
connection across threads), WAL + busy timeout, file-backed. Two tables:

  conversations -- one row per thread (id, profile, title, timestamps)
  turns         -- one row per message, chronological (role, content, topic, tokens)

A `distilled` flag + `summary` column let Phase 2 hybrid windowing fold older turns
into a short summary without losing the raw text (the summary is used in the prompt,
the original stays on disk). Pure storage; windowing/policy lives elsewhere.
"""
import os
import sqlite3
import time
import uuid
from contextlib import closing
from typing import Any, Dict, List, Optional

_DB_PATH: Optional[str] = None


def init_db(db_path: str) -> None:
    """Create the store (idempotent)."""
    global _DB_PATH
    _DB_PATH = db_path
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    with closing(_connect()) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS conversations ("
            " conversation_id TEXT PRIMARY KEY,"
            " profile TEXT,"
            " title TEXT,"
            " created_at INTEGER NOT NULL,"
            " updated_at INTEGER NOT NULL)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS turns ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " conversation_id TEXT NOT NULL,"
            " profile TEXT,"
            " role TEXT NOT NULL,"
            " content TEXT NOT NULL,"
            " topic TEXT,"
            " tokens INTEGER,"
            " distilled INTEGER NOT NULL DEFAULT 0,"
            " summary TEXT,"
            " ts INTEGER NOT NULL)"
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_turns_conv ON turns(conversation_id, id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_conv_profile ON conversations(profile, updated_at)")
        con.commit()


def _connect() -> sqlite3.Connection:
    if _DB_PATH is None:
        raise RuntimeError("conversations.init_db() has not been called")
    con = sqlite3.connect(_DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def new_conversation(profile: str = "default", title: Optional[str] = None,
                     conversation_id: Optional[str] = None) -> str:
    """Create a conversation (idempotent on an explicit id); return its id."""
    cid = conversation_id or uuid.uuid4().hex
    now = int(time.time())
    with closing(_connect()) as con:
        con.execute(
            "INSERT OR IGNORE INTO conversations(conversation_id, profile, title, created_at, updated_at)"
            " VALUES(?,?,?,?,?)", (cid, profile, title, now, now))
        con.commit()
    return cid


def _ensure_conversation(con, cid: str, profile: Optional[str], now: int) -> None:
    if not con.execute("SELECT 1 FROM conversations WHERE conversation_id=?", (cid,)).fetchone():
        con.execute(
            "INSERT INTO conversations(conversation_id, profile, title, created_at, updated_at)"
            " VALUES(?,?,?,?,?)", (cid, profile, None, now, now))


def add_turn(conversation_id: str, role: str, content: str, *,
             profile: str = "default", topic: Optional[str] = None,
             tokens: Optional[int] = None) -> int:
    """Append a turn (auto-creating the conversation); bump updated_at; return turn id."""
    now = int(time.time())
    with closing(_connect()) as con:
        _ensure_conversation(con, conversation_id, profile, now)
        cur = con.execute(
            "INSERT INTO turns(conversation_id, profile, role, content, topic, tokens, distilled, summary, ts)"
            " VALUES(?,?,?,?,?,?,0,NULL,?)",
            (conversation_id, profile, role, content, topic, tokens, now))
        con.execute("UPDATE conversations SET updated_at=? WHERE conversation_id=?", (now, conversation_id))
        con.commit()
        return int(cur.lastrowid)


def get_turns(conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Turns in chronological order. With `limit`, the most recent N (still chronological)."""
    with closing(_connect()) as con:
        if limit:
            rows = con.execute(
                "SELECT * FROM (SELECT * FROM turns WHERE conversation_id=? ORDER BY id DESC LIMIT ?)"
                " ORDER BY id ASC", (conversation_id, int(limit))).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM turns WHERE conversation_id=? ORDER BY id ASC",
                (conversation_id,)).fetchall()
    return [dict(r) for r in rows]


def list_conversations(profile: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Recent conversations, newest first; optionally scoped to a profile."""
    with closing(_connect()) as con:
        if profile:
            rows = con.execute(
                "SELECT * FROM conversations WHERE profile=? ORDER BY updated_at DESC LIMIT ?",
                (profile, int(limit))).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
                (int(limit),)).fetchall()
    return [dict(r) for r in rows]


def count_turns(conversation_id: str) -> int:
    with closing(_connect()) as con:
        return int(con.execute(
            "SELECT COUNT(*) AS c FROM turns WHERE conversation_id=?",
            (conversation_id,)).fetchone()["c"])


def conversations_with_undistilled(min_turns: int = 1, limit: int = 20,
                                   profile: Optional[str] = None) -> List[Dict[str, Any]]:
    """Phase 7 sleep cycle: conversations that hold >= min_turns un-distilled turns, newest
    activity first. Each row: {conversation_id, profile, pending} (pending = undistilled count)."""
    where = "t.distilled=0"
    args: List[Any] = []
    if profile:
        where += " AND c.profile=?"
        args.append(profile)
    sql = (
        "SELECT c.conversation_id AS conversation_id, c.profile AS profile, "
        "       COUNT(t.id) AS pending, MAX(c.updated_at) AS updated_at "
        "FROM turns t JOIN conversations c ON c.conversation_id=t.conversation_id "
        f"WHERE {where} "
        "GROUP BY c.conversation_id HAVING pending >= ? "
        "ORDER BY updated_at DESC LIMIT ?"
    )
    args += [int(min_turns), int(limit)]
    with closing(_connect()) as con:
        rows = con.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def undistilled_turns(conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Un-distilled turns for a conversation, chronological."""
    with closing(_connect()) as con:
        q = ("SELECT * FROM turns WHERE conversation_id=? AND distilled=0 ORDER BY id ASC"
             + (" LIMIT ?" if limit else ""))
        args = (conversation_id, int(limit)) if limit else (conversation_id,)
        rows = con.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def mark_distilled(turn_ids: List[int], summary: Optional[str] = None) -> int:
    """Flag turns as distilled and attach an optional summary. Returns rows updated."""
    ids = [int(t) for t in (turn_ids or [])]
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    with closing(_connect()) as con:
        cur = con.execute(
            f"UPDATE turns SET distilled=1, summary=? WHERE id IN ({placeholders})",
            [summary, *ids])
        con.commit()
        return cur.rowcount


def delete_conversation(conversation_id: str) -> bool:
    with closing(_connect()) as con:
        con.execute("DELETE FROM turns WHERE conversation_id=?", (conversation_id,))
        cur = con.execute("DELETE FROM conversations WHERE conversation_id=?", (conversation_id,))
        con.commit()
        return cur.rowcount > 0
