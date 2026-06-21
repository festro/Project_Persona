"""H3 standing dispatcher: loop the SUPPORTED `hermes kanban dispatch` primitive.

Phase 8 H3. The persona-side bridge (tools/hermes_bridge.py) is one half of the loop --
it enqueues delegated Task Board rows as Hermes kanban cards and mirrors their outcomes
back. This module is the OTHER half: it periodically runs Hermes' own dispatcher pass so
ready cards actually get workers spawned, UNATTENDED. In H2d that pass was invoked by hand
(`hermes kanban dispatch`); here it runs on an interval under daemon.py's three-strike
supervisor, so the full delegate -> card -> worker -> mirror chain needs no operator.

Built on `hermes kanban dispatch` -- the SUPPORTED one-shot ("reclaim stale, promote ready,
spawn workers" + `--failure-limit` auto-block) -- NOT `hermes kanban daemon`, which v0.16.0
marks DEPRECATED in favour of the messaging `gateway` (a separate out-of-project service
needing platform creds; we run egress-off/loopback, so we loop the primitive ourselves).

dispatch --json shape (v0.16.0):
  {"reclaimed": int, "crashed": [...], "timed_out": [...], "stale": [...],
   "auto_blocked": [...], "promoted": int, "spawned": [{task_id,assignee,workspace}, ...],
   "skipped_unassigned": [...], "skipped_nonspawnable": [...],
   "skipped_per_profile_capped": [...], "auto_assigned_default": [...]}

Runs on EVO-X2 (loopback only). Stdlib-only; it shells out to the Hermes public CLI
(HERMES_CLI, an absolute path -> no worker-shell PATH dependency for the dispatch call).

Design: docs/h2_bridge_design_20260613_0204.md (bridge architecture; Hermes owns dispatch).
"""
import json
import os
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# runner(args) -> (returncode, stdout, stderr)
Runner = Callable[[List[str]], Tuple[int, str, str]]

HERMES_CLI = os.getenv("HERMES_CLI", "hermes")
BRIDGE_BOARD = os.getenv("HERMES_BRIDGE_BOARD", "")  # "" = Hermes default board (as H2d/H2e)
# Auto-block a card after N consecutive non-success attempts (spawn_failed/timed_out/crashed).
# Matches Hermes' own default of 2; this is H6's "Tenacity-style" failure semantics, native.
DEFAULT_FAILURE_LIMIT = int(os.getenv("HERMES_DISPATCH_FAILURE_LIMIT", "2"))

# dispatch-result keys that mean the pass actually DID something (worth logging a tick for).
_INT_SIGNALS = ("reclaimed", "promoted")
_LIST_SIGNALS = ("crashed", "timed_out", "stale", "auto_blocked", "spawned",
                 "auto_assigned_default")


def build_dispatch_args(cli: str = HERMES_CLI, failure_limit: int = DEFAULT_FAILURE_LIMIT,
                        max_spawns: Optional[int] = None, board: str = BRIDGE_BOARD) -> List[str]:
    """Build the `hermes kanban [--board X] dispatch ... --json` argv for one pass.

    NOTE: `--board` is a kanban-level flag (before the subcommand), not a dispatch flag.
    """
    args = [cli, "kanban"]
    if board:
        args += ["--board", board]
    args += ["dispatch", "--failure-limit", str(failure_limit), "--json"]
    if max_spawns is not None:
        args += ["--max", str(max_spawns)]
    return args


def default_runner(args: List[str], timeout: int = 120) -> Tuple[int, str, str]:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout or "", p.stderr or ""


def _loads_lenient(stdout: str) -> Optional[Any]:
    """Parse JSON that may be surrounded by other CLI chatter (mirrors hermes_bridge)."""
    s = (stdout or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except ValueError:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(s[start:end + 1])
        except ValueError:
            return None
    return None


def dispatch_changed(result: Dict[str, Any]) -> bool:
    """True if a dispatch pass reclaimed/promoted/spawned/blocked/etc. anything."""
    if not isinstance(result, dict):
        return False
    if any(int(result.get(k, 0) or 0) > 0 for k in _INT_SIGNALS):
        return True
    return any(result.get(k) for k in _LIST_SIGNALS)


def summarize(result: Dict[str, Any]) -> str:
    """Compact one-line summary of a dispatch pass for the daemon log."""
    parts: List[str] = []
    for k in _INT_SIGNALS:
        v = int(result.get(k, 0) or 0)
        if v:
            parts.append("{}={}".format(k, v))
    for k in _LIST_SIGNALS:
        v = result.get(k) or []
        if not v:
            continue
        if k == "spawned":
            ids = ",".join(str(x.get("task_id")) for x in v if isinstance(x, dict))
            parts.append("spawned=[{}]".format(ids))
        else:
            parts.append("{}={}".format(k, len(v)))
    return " ".join(parts) or "idle"


def tick(runner: Runner = default_runner, cli: str = HERMES_CLI,
         failure_limit: int = DEFAULT_FAILURE_LIMIT, max_spawns: Optional[int] = None,
         board: str = BRIDGE_BOARD) -> Dict[str, Any]:
    """Run one dispatcher pass. Returns the parsed --json result, or {'error': ...}."""
    rc, out, err = runner(build_dispatch_args(cli, failure_limit, max_spawns, board))
    result = _loads_lenient(out)
    if not isinstance(result, dict):
        return {"error": (err or out or "no output").strip()[-500:], "rc": rc}
    if rc != 0 and "error" not in result:
        result["rc"] = rc
    return result


def main(argv: Optional[List[str]] = None, runner: Runner = default_runner) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="persona standing dispatcher (loops hermes kanban dispatch)")
    ap.add_argument("--interval", type=float, default=float(os.getenv("HERMES_DISPATCH_INTERVAL", "60")),
                    help="seconds between dispatch passes (default 60)")
    ap.add_argument("--failure-limit", type=int, default=DEFAULT_FAILURE_LIMIT, dest="failure_limit",
                    help="auto-block a card after N consecutive failed attempts (default 2)")
    ap.add_argument("--max", type=int, default=None, dest="max_spawns",
                    help="cap the number of worker spawns per pass")
    ap.add_argument("--once", action="store_true", help="run a single dispatch pass and exit")
    args = ap.parse_args(argv)
    while True:
        result = tick(runner=runner, cli=HERMES_CLI, failure_limit=args.failure_limit,
                      max_spawns=args.max_spawns)
        if result.get("error"):
            print("[hermes_dispatch] ERROR " + json.dumps(result), flush=True)
        elif dispatch_changed(result):
            print("[hermes_dispatch] " + summarize(result), flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
