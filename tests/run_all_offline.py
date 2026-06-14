"""One-command offline regression runner (roadmap Phase 10 Item 10.0).

Discovers and runs every tests/test_*.py suite as a subprocess with the current
interpreter, aggregates pass/fail, and exits 0 only if all pass. No live server,
no network. Cross-platform (Windows portable 3.11.9 + Linux). Future test_*.py
files are picked up automatically.

    <python> tests/run_all_offline.py

Exit code 0 = all suites passed, 1 = one or more failed.
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def discover():
    return sorted(p for p in HERE.glob("test_*.py"))


def main():
    py = sys.executable
    suites = discover()
    if not suites:
        print(f"no test_*.py suites found in {HERE}")
        return 1
    print(f"=== offline regression: {len(suites)} suite(s) ===")
    print(f"python : {py}")
    print(f"started: {time.strftime('%Y-%m-%d %H%M %Z')}")
    print()
    results = []
    for suite in suites:
        start = time.time()
        proc = subprocess.run(
            [py, str(suite)],
            cwd=str(REPO),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        elapsed = time.time() - start
        ok = proc.returncode == 0
        results.append((suite.name, ok, proc.returncode, elapsed, proc.stdout))
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {suite.name}  ({elapsed:.1f}s, rc={proc.returncode})")
    print()
    failed = [r for r in results if not r[1]]
    for name, ok, rc, elapsed, out in failed:
        print(f"----- output: {name} (rc={rc}) -----")
        print(out.rstrip())
        print()
    total = len(results)
    print(f"RESULT: {total - len(failed)}/{total} suites passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
