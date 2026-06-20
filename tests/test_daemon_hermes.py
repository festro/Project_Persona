#!/usr/bin/env python3
"""Offline tests for the Phase 8 daemon scaffolding (daemon.py):

  - sanitize_env: cloud/egress secrets stripped, normal vars + KEEP exceptions retained
  - _launch honours ChildSpec.hygiene -- a hygiene child is spawned WITHOUT the secret env var,
    a non-hygiene child still sees it (real subprocess via the Supervisor)
  - hermes_present / hermes_bridge_spec -- spec shape + hygiene flag
  - build_specs(with_hermes=...) includes/excludes the hermes-bridge child

Pure asyncio + stdlib; no llama/api, no Hermes execution.

    python tests/test_daemon_hermes.py     # exit 0 = pass, 1 = a failure
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services" / "api"))

import daemon as dmn  # noqa: E402

PY = sys.executable
checks = 0
failures = []


def check(name, cond):
    global checks
    checks += 1
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


async def until(cond, timeout=10.0, interval=0.05):
    import time
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if cond():
            return True
        await asyncio.sleep(interval)
    return cond()


async def run():
    # --- sanitize_env -------------------------------------------------------
    env = {"PATH": "/bin", "OPENAI_API_KEY": "sk-x", "AWS_SECRET_ACCESS_KEY": "y",
           "AWS_REGION": "us-east-1", "ANTHROPIC_API_KEY": "z", "HOME": "/home/x",
           "LANGSMITH_API_KEY": "q", "NORMAL_VAR": "keep"}
    s = dmn.sanitize_env(env)
    check("strips OPENAI_API_KEY", "OPENAI_API_KEY" not in s)
    check("strips AWS_ prefix", "AWS_SECRET_ACCESS_KEY" not in s)
    check("strips ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY" not in s)
    check("strips LANGSMITH_ prefix", "LANGSMITH_API_KEY" not in s)
    check("keeps PATH/HOME/NORMAL", s.get("PATH") == "/bin" and s.get("HOME") == "/home/x" and s.get("NORMAL_VAR") == "keep")
    check("keeps AWS_REGION (KEEP exception)", s.get("AWS_REGION") == "us-east-1")

    # --- hygiene honoured at launch (real subprocess) -----------------------
    tmp = Path(tempfile.mkdtemp(prefix="hyg_"))
    os.environ["OPENAI_API_KEY"] = "should-be-stripped"
    os.environ["NORMAL_VAR"] = "kept-value"

    def probe_spec(name, outfile, hygiene):
        code = (f"import os;"
                f"open({str(outfile)!r},'w').write("
                f"'secret='+os.environ.get('OPENAI_API_KEY','MISSING')+"
                f"'|normal='+os.environ.get('NORMAL_VAR','MISSING'));")
        return dmn.ChildSpec(name, [PY, "-c", code], hygiene=hygiene)

    out_h = tmp / "hygiene.txt"
    sup = dmn.Supervisor([probe_spec("h", out_h, True)], max_strikes=1,
                         restart_backoff=0.05, log=lambda *_: None)
    await sup.start()
    await until(out_h.exists, timeout=8)
    await sup.stop()
    txt_h = out_h.read_text() if out_h.exists() else ""
    check("hygiene child: secret stripped", "secret=MISSING" in txt_h)
    check("hygiene child: normal var kept", "normal=kept-value" in txt_h)

    out_n = tmp / "plain.txt"
    sup2 = dmn.Supervisor([probe_spec("n", out_n, False)], max_strikes=1,
                          restart_backoff=0.05, log=lambda *_: None)
    await sup2.start()
    await until(out_n.exists, timeout=8)
    await sup2.stop()
    txt_n = out_n.read_text() if out_n.exists() else ""
    check("non-hygiene child still sees the secret", "secret=should-be-stripped" in txt_n)

    # --- hermes spec + build_specs -----------------------------------------
    present = dmn.hermes_present(ROOT)
    spec = dmn.hermes_bridge_spec(ROOT)
    if present:
        check("hermes spec built when env_hermes present", spec is not None and spec.name == "hermes-bridge")
        check("hermes spec runs the bridge", spec.argv[1] == "tools/hermes_bridge.py")
        check("hermes spec is hygiene + sets HERMES_CLI",
              spec.hygiene is True and spec.env.get("HERMES_CLI", "").endswith("hermes"))
    else:
        check("hermes spec is None when env_hermes absent", spec is None)

    # build_specs: hermes excluded by default, included on request (no llama/api to avoid manage deps)
    base = dmn.build_specs(ROOT, {}, with_llama=False, with_api=False, with_hermes=False)
    check("with_hermes=False excludes the bridge", all(s.name != "hermes-bridge" for s in base))
    withh = dmn.build_specs(ROOT, {}, with_llama=False, with_api=False, with_hermes=True)
    if present:
        check("with_hermes=True includes the bridge", any(s.name == "hermes-bridge" for s in withh))


def main():
    asyncio.run(run())
    print()
    print(f"RESULT: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("FAILURES:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
