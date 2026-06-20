#!/usr/bin/env python3
"""Offline tests for the Phase 3 LoopbackBus (services/api/eventbus.py).

Exercises the EventBus contract on the stdlib transport: publish->subscribe round-trip,
the "*" wildcard, the small event vocabulary, shared-token rejection, and the two hard
guarantees -- one-way fire-and-forget and never-block/never-raise (a publish to a dead
endpoint returns False without raising). Pure asyncio + stdlib; no network, no server.

    python tests/test_eventbus.py     # exit 0 = pass, 1 = a failure
"""
import asyncio
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

import eventbus as eb  # noqa: E402

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


async def run() -> None:
    check("EVENTS vocabulary present", set(("ping", "task_ready", "profile_switched")) <= set(eb.EVENTS))

    port = free_port()
    token = "test-token-123"

    # daemon side: one bus binds + subscribes
    bus = eb.LoopbackBus(port=port, token=token)
    received = []

    async def handler(event, payload):
        received.append((event, payload))

    await bus.subscribe("ping", handler)
    await bus.subscribe("task_ready", handler)

    # wildcard subscribed up front -> must see every delivered event (dispatch is async,
    # so subscribe-vs-publish ordering is not an invariant; "saw all" is the real property)
    star_seen = []

    async def star(event, payload):
        star_seen.append(event)

    await bus.subscribe("*", star)
    await bus.start()

    # publisher side: a SEPARATE bus instance (as the API would use), same port+token
    pub = eb.LoopbackBus(port=port, token=token)
    ok1 = await pub.publish("ping", {"n": 1})
    ok2 = await pub.publish("task_ready", {"job_id": "j1"})
    ok3 = await pub.publish("profile_switched", {"profile": "default"})
    check("publish returns True on success", ok1 is True and ok2 is True and ok3 is True)

    # bad token: server must reject, no dispatch
    badpub = eb.LoopbackBus(port=port, token="WRONG-TOKEN")
    await badpub.publish("ping", {"n": 99})

    await asyncio.sleep(0.25)  # let the listener dispatch

    events = [e for e, _ in received]
    check("ping delivered with payload", ("ping", {"n": 1}) in received)
    check("task_ready delivered with payload", ("task_ready", {"job_id": "j1"}) in received)
    check("wildcard saw all three good events",
          set(star_seen) == {"ping", "task_ready", "profile_switched"})
    check("bad token rejected (no n:99)", ("ping", {"n": 99}) not in received)
    check("bad token rejected (wildcard saw only one ping)", star_seen.count("ping") == 1)
    check("exactly the two good handler events", events.count("ping") == 1 and events.count("task_ready") == 1)

    # never-block / never-raise: publish to a dead port returns False without raising
    dead_port = free_port()
    dead = eb.LoopbackBus(port=dead_port, token=token, connect_timeout=0.3)
    raised = False
    okdead = True
    try:
        okdead = await dead.publish("ping", {})
    except Exception:  # noqa: BLE001
        raised = True
    check("publish to dead endpoint did not raise", raised is False)
    check("publish to dead endpoint returned False", okdead is False)

    # oversized payload is refused, not raised
    big = {"blob": "x" * (eb._MAX_FRAME + 10)}
    okbig = await pub.publish("ping", big)
    check("oversized frame refused (False)", okbig is False)

    await bus.stop()

    # publish after stop is a clean False (endpoint gone), still no raise
    okafter = await pub.publish("ping", {"n": 2})
    check("publish after stop returns False (no raise)", okafter is False)


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
