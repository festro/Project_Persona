"""Offline unit test for manage.py pid robustness (the WSL stale-pidfile trap).

Monkeypatches pid_alive / http_health_up / pids_by_cmdline / terminate_pid so it
needs no running services and no network. Proves resolve_live_pid corroborates a
dead recorded pid against /health, and that stop_named kills the real server
instead of orphaning it. Stdlib only.

    python3 tests/test_manage_pid.py

Exit code 0 = all pass, 1 = one or more failures.
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import manage

checks_run = 0
failures = []


def check(name, cond):
    global checks_run
    checks_run += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def patch(alive_set, health_up, scan_pids):
    manage.pid_alive = lambda p: p in alive_set
    manage.http_health_up = lambda url=None, timeout=2.0: bool(health_up)
    manage.pids_by_cmdline = lambda needles=None: list(scan_pids)
    killed = []
    manage.terminate_pid = lambda pid, timeout=8.0: (killed.append(pid) or True)
    return killed


def make_root():
    root = Path(tempfile.mkdtemp(prefix="pp_pid_"))
    (root / "run").mkdir(parents=True, exist_ok=True)
    return root


def write_pidfile(root, name, pid):
    (root / "run" / f"{name}.pid").write_text(str(pid), encoding="utf-8")


def pidfile_exists(root, name):
    return (root / "run" / f"{name}.pid").exists()


patch({100}, False, [])
check("resolve: live pid returns itself", manage.resolve_live_pid(100) == 100)

patch(set(), True, [4321])
check("resolve: dead pid + health up -> real pid", manage.resolve_live_pid(999, "URL", ["x"]) == 4321)

patch(set(), False, [4321])
check("resolve: dead pid + health down -> None", manage.resolve_live_pid(999, "URL", ["x"]) is None)

patch(set(), True, [4321])
check("resolve: no pidfile + health up -> real pid", manage.resolve_live_pid(None, "URL", ["x"]) == 4321)

root = make_root()
write_pidfile(root, "persona", 999)
killed = patch(set(), True, [4321])
manage.stop_named(root, "persona", "URL", ["llama-server"])
check("stop: stale pidfile but up -> kills real pid", killed == [4321])
check("stop: stale-but-up removes pidfile", not pidfile_exists(root, "persona"))

root = make_root()
write_pidfile(root, "persona", 999)
killed = patch(set(), False, [4321])
manage.stop_named(root, "persona", "URL", ["llama-server"])
check("stop: dead + health down -> no kill", killed == [])
check("stop: dead + down removes pidfile", not pidfile_exists(root, "persona"))

root = make_root()
killed = patch(set(), True, [4321])
manage.stop_named(root, "persona", "URL", ["llama-server"])
check("stop: orphan (no pidfile) + up -> kills real pid", killed == [4321])

root = make_root()
write_pidfile(root, "persona", 100)
killed = patch({100}, True, [])
manage.stop_named(root, "persona", "URL", ["llama-server"])
check("stop: normal alive -> kills recorded pid", killed == [100])
check("stop: normal removes pidfile", not pidfile_exists(root, "persona"))

# --- vision serving wiring (_truthy / _mmproj_args) ---
check("truthy: 1/true/yes/on", manage._truthy("1") and manage._truthy("True")
      and manage._truthy("yes") and manage._truthy("ON"))
check("truthy: 0/false/empty", not manage._truthy("0") and not manage._truthy("False")
      and not manage._truthy(""))

root = make_root()
(root / "models").mkdir(parents=True, exist_ok=True)
mm = root / "models" / "mmproj-x.gguf"
mm.write_text("x", encoding="utf-8")

check("mmproj: vision off -> no args",
      manage._mmproj_args(root, {"VISION_ENABLED": "0", "MMPROJ_PATH": "mmproj-x.gguf"}) == [])
check("mmproj: vision on + present -> --mmproj <abs>",
      manage._mmproj_args(root, {"VISION_ENABLED": "1", "MMPROJ_PATH": "mmproj-x.gguf"})
      == ["--mmproj", str(mm)])
check("mmproj: vision on, no MMPROJ_PATH -> []",
      manage._mmproj_args(root, {"VISION_ENABLED": "1"}) == [])
check("mmproj: vision on, missing file -> [] (text-only)",
      manage._mmproj_args(root, {"VISION_ENABLED": "1", "MMPROJ_PATH": "nope.gguf"}) == [])
check("mmproj: absolute MMPROJ_PATH honored",
      manage._mmproj_args(root, {"VISION_ENABLED": "true", "MMPROJ_PATH": str(mm)})
      == ["--mmproj", str(mm)])

print()
print(f"{checks_run - len(failures)}/{checks_run} passed")
sys.exit(1 if failures else 0)
