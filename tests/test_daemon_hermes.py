#!/usr/bin/env python3
"""Offline tests for the Phase 8 daemon scaffolding (daemon.py):

  - sanitize_env: cloud/egress secrets stripped, normal vars + KEEP exceptions retained
  - _launch honours ChildSpec.hygiene -- a hygiene child is spawned WITHOUT the secret env var,
    a non-hygiene child still sees it (real subprocess via the Supervisor)
  - hermes_present / hermes_bridge_spec / hermes_dispatcher_spec -- spec shape + hygiene flag
  - build_specs(with_hermes=...) includes/excludes BOTH hermes children (bridge + dispatcher)
  - tools/hermes_dispatch_loop.py -- argv builder, dispatch_changed/summarize, tick + --once

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

    # --- hermes specs + build_specs ----------------------------------------
    present = dmn.hermes_present(ROOT)
    spec = dmn.hermes_bridge_spec(ROOT)
    dspec = dmn.hermes_dispatcher_spec(ROOT)
    if present:
        check("hermes spec built when env_hermes present", spec is not None and spec.name == "hermes-bridge")
        check("hermes spec runs the bridge", spec.argv[1] == "tools/hermes_bridge.py")
        check("hermes spec is hygiene + sets HERMES_CLI",
              spec.hygiene is True and spec.env.get("HERMES_CLI", "").endswith("hermes"))
        # H3 dispatcher spec (mirrors the bridge)
        check("dispatcher spec built when env_hermes present",
              dspec is not None and dspec.name == "hermes-dispatcher")
        check("dispatcher spec runs the dispatch loop", dspec.argv[1] == "tools/hermes_dispatch_loop.py")
        check("dispatcher spec is hygiene + sets HERMES_CLI",
              dspec.hygiene is True and dspec.env.get("HERMES_CLI", "").endswith("hermes"))
    else:
        check("hermes spec is None when env_hermes absent", spec is None)
        check("dispatcher spec is None when env_hermes absent", dspec is None)

    # build_specs: hermes excluded by default, included on request (no llama/api to avoid manage deps)
    base = dmn.build_specs(ROOT, {}, with_llama=False, with_api=False, with_hermes=False)
    check("with_hermes=False excludes the bridge", all(s.name != "hermes-bridge" for s in base))
    check("with_hermes=False excludes the dispatcher", all(s.name != "hermes-dispatcher" for s in base))
    withh = dmn.build_specs(ROOT, {}, with_llama=False, with_api=False, with_hermes=True)
    if present:
        check("with_hermes=True includes the bridge", any(s.name == "hermes-bridge" for s in withh))
        check("with_hermes=True includes the dispatcher", any(s.name == "hermes-dispatcher" for s in withh))

    # --- H3 dispatch loop (tools/hermes_dispatch_loop.py) ------------------
    sys.path.insert(0, str(ROOT / "tools"))
    import hermes_dispatch_loop as hdl  # noqa: E402

    da = hdl.build_dispatch_args(cli="/x/hermes", failure_limit=3)
    check("dispatch argv targets kanban dispatch", da[:3] == ["/x/hermes", "kanban", "dispatch"])
    check("dispatch argv carries --failure-limit + --json",
          "--failure-limit" in da and da[da.index("--failure-limit") + 1] == "3" and "--json" in da)
    check("dispatch argv adds --max only when set",
          "--max" not in hdl.build_dispatch_args(cli="h") and
          "--max" in hdl.build_dispatch_args(cli="h", max_spawns=2))
    check("dispatch --board goes before the subcommand",
          hdl.build_dispatch_args(cli="h", board="b")[:4] == ["h", "kanban", "--board", "b"])

    # dispatch_changed / summarize on the real v0.16.0 dispatch --json shape
    idle = {"reclaimed": 0, "promoted": 0, "crashed": [], "timed_out": [], "stale": [],
            "auto_blocked": [], "spawned": [], "auto_assigned_default": []}
    busy = dict(idle, reclaimed=2, spawned=[{"task_id": "t_1"}, {"task_id": "t_2"}])
    check("dispatch_changed False on an idle pass", hdl.dispatch_changed(idle) is False)
    check("dispatch_changed True when it reclaims/spawns", hdl.dispatch_changed(busy) is True)
    check("summarize idle -> 'idle'", hdl.summarize(idle) == "idle")
    sm = hdl.summarize(busy)
    check("summarize busy names reclaimed + spawned ids", "reclaimed=2" in sm and "t_1" in sm and "t_2" in sm)

    # tick parses lenient JSON from an injected runner; main --once runs exactly one pass
    fake_out = ('{"reclaimed":1,"crashed":[],"timed_out":[],"stale":[],"auto_blocked":[],'
                '"promoted":0,"spawned":[],"skipped_unassigned":[],"skipped_nonspawnable":[],'
                '"skipped_per_profile_capped":[],"auto_assigned_default":[]}')
    calls = []

    def fake_runner(a):
        calls.append(a)
        return (0, "noise\n" + fake_out + "\ntrailing", "")

    res = hdl.tick(runner=fake_runner)
    check("tick parses dispatch JSON amid CLI chatter", res.get("reclaimed") == 1)
    rc_once = hdl.main(["--once"], runner=fake_runner)
    check("main --once returns 0 and runs exactly one pass", rc_once == 0 and len(calls) == 2)
    errres = hdl.tick(runner=lambda a: (1, "boom", "stderr-msg"))
    check("tick reports error on non-JSON output", "error" in errres)

    # --- Phase 5 voice spec scaffolding ------------------------------------
    # No real engines on this box -> specs are None and with_voice adds nothing.
    check("stt absent -> whisper spec None", dmn.whisper_stt_spec(ROOT) is None)
    check("tts absent -> piper spec None", dmn.piper_tts_spec(ROOT) is None)
    base_v = dmn.build_specs(ROOT, {}, with_llama=False, with_api=False, with_voice=True)
    check("with_voice but no engines -> no voice children",
          all(s.name not in ("whisper-stt", "piper-tts") for s in base_v))

    # Point the env at fake binary+model files -> the guarded specs build with the right argv.
    fake = Path(tempfile.mkdtemp(prefix="voice_"))
    for n in ("whisper-server", "piper", "ggml.bin", "voice.onnx"):
        (fake / n).write_text("x")
    os.environ["WHISPER_SERVER_BIN"] = str(fake / "whisper-server")
    os.environ["WHISPER_MODEL"] = str(fake / "ggml.bin")
    os.environ["PIPER_BIN"] = str(fake / "piper")
    os.environ["PIPER_MODEL"] = str(fake / "voice.onnx")
    try:
        check("stt present (fake) -> spec built", dmn.stt_present(ROOT) and dmn.whisper_stt_spec(ROOT).name == "whisper-stt")
        sp = dmn.piper_tts_spec(ROOT)
        check("tts present (fake) -> piper spec + model argv",
              sp is not None and sp.name == "piper-tts" and str(fake / "voice.onnx") in sp.argv)
        vv = dmn.build_specs(ROOT, {}, with_llama=False, with_api=False, with_voice=True)
        check("with_voice + engines -> both voice children",
              {"whisper-stt", "piper-tts"} <= {s.name for s in vv})
    finally:
        for k in ("WHISPER_SERVER_BIN", "WHISPER_MODEL", "PIPER_BIN", "PIPER_MODEL"):
            os.environ.pop(k, None)


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
