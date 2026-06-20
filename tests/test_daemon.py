#!/usr/bin/env python3
"""Offline tests for the Phase 3 daemon supervisor (daemon.py Supervisor).

Drives the Supervisor with cheap dummy children (python one-liners) so the restart
policy is exercised with no real services:

  - a stable child stays up, strikes stay 0
  - a crash-looping child is restarted up to max_strikes, then the next death STAYS DOWN
    (the "fourth failure stays down" Exit-Gate property)
  - a killed child is restarted automatically
  - a hosted EventBus is up between start() and stop() (ping round-trips)

Pure asyncio + stdlib; no network, no llama/api.

    python tests/test_daemon.py     # exit 0 = pass, 1 = a failure
"""
import asyncio
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services" / "api"))

import daemon as dmn  # noqa: E402
import eventbus as eb  # noqa: E402

PY = sys.executable
checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


async def until(cond, timeout=10.0, interval=0.05) -> bool:
    import time
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if cond():
            return True
        await asyncio.sleep(interval)
    return cond()


def spec(name, code, **kw):
    return dmn.ChildSpec(name, [PY, "-c", code], **kw)


async def test_stable():
    s = spec("stable", "import time; time.sleep(30)")
    sup = dmn.Supervisor([s], restart_backoff=0.02, log=lambda *_: None)
    await sup.start()
    ok = await until(lambda: sup.status()["children"]["stable"]["alive"])
    st = sup.status()["children"]["stable"]
    check("stable child is alive", ok and st["state"] == "running")
    check("stable child started once", st["starts"] == 1)
    check("stable child has 0 strikes", st["strikes"] == 0)
    await sup.stop()
    check("stable child not alive after stop",
          not sup.status()["children"]["stable"]["alive"])


async def test_crashloop():
    logs = []
    s = spec("crasher", "import sys; sys.exit(1)")
    # stable_reset high so strikes accumulate; tiny backoff for a fast test
    sup = dmn.Supervisor([s], max_strikes=3, stable_reset_s=100.0,
                         restart_backoff=0.02, log=lambda m: logs.append(m))
    await sup.start()
    # supervise task ends when the child is given up on -> wait() returns
    try:
        await asyncio.wait_for(sup.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        pass
    st = sup.status()["children"]["crasher"]
    check("crasher gave up (state failed)", st["state"] == "failed")
    check("crasher started max_strikes+1 times (4)", st["starts"] == 4)
    check("crasher strikes == max_strikes+1", st["strikes"] == 4)
    check("daemon logged STAYS DOWN", any("STAYS DOWN" in m for m in logs))
    await sup.stop()


async def test_max_total_starts():
    # stable_reset_s=0 -> every death resets the strike count, so the 3-strike rule NEVER
    # fires (a "slow crash-loop"). The max_total_starts ceiling must still stop it.
    logs = []
    s = spec("slowcrash", "import sys; sys.exit(1)")
    sup = dmn.Supervisor([s], max_strikes=3, stable_reset_s=0.0, restart_backoff=0.02,
                         max_total_starts=5, log=lambda m: logs.append(m))
    await sup.start()
    try:
        await asyncio.wait_for(sup.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        pass
    st = sup.status()["children"]["slowcrash"]
    check("slow crash-loop gave up despite strike resets", st["state"] == "failed")
    check("stopped exactly at max_total_starts (5)", st["starts"] == 5)
    check("logged the max_total_starts reason", any("max_total_starts" in m for m in logs))
    await sup.stop()


async def test_kill_restarts():
    s = spec("sleeper", "import time; time.sleep(30)")
    sup = dmn.Supervisor([s], stable_reset_s=100.0, restart_backoff=0.02,
                         log=lambda *_: None)
    await sup.start()
    await until(lambda: sup.status()["children"]["sleeper"]["alive"])
    child = sup.children[0]
    first_pid = child.pid
    child.proc.kill()  # external death -> supervisor must relaunch
    restarted = await until(
        lambda: sup.status()["children"]["sleeper"]["starts"] == 2
        and sup.status()["children"]["sleeper"]["alive"])
    st = sup.status()["children"]["sleeper"]
    check("killed child was restarted (starts==2)", restarted and st["starts"] == 2)
    check("restarted child is alive again", st["alive"] and st["state"] == "running")
    check("restart took a new pid", sup.children[0].pid != first_pid)
    check("one death -> one strike", st["strikes"] == 1)
    await sup.stop()


async def test_bus_hosted():
    port = free_port()
    token = "daemon-tok"
    bus = eb.LoopbackBus(port=port, token=token)
    got = []
    await bus.subscribe("ping", lambda e, p: got.append(p))
    s = spec("sleeper", "import time; time.sleep(30)")
    sup = dmn.Supervisor([s], restart_backoff=0.02, bus=bus, log=lambda *_: None)
    await sup.start()
    pub = eb.LoopbackBus(port=port, token=token)
    ok = await pub.publish("ping", {"hello": 1})
    await until(lambda: len(got) == 1, timeout=3.0)
    check("bus up while supervising (ping delivered)", ok and got == [{"hello": 1}])
    await sup.stop()
    # bus down after stop -> publish fails cleanly (no raise)
    after = await pub.publish("ping", {"hello": 2})
    check("bus down after stop (publish returns False)", after is False)


async def run():
    await test_stable()
    await test_crashloop()
    await test_max_total_starts()
    await test_kill_restarts()
    await test_bus_hosted()


def main() -> int:
    asyncio.run(run())
    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
