#!/usr/bin/env python3
"""Project_Persona Phase 3 -- always-on supervised daemon.

ONE asyncio entry point that owns the whole local stack: it launches a child-process
map (llama-server, the API, and -- task 11 -- nats-server), supervises each child with a
three-strike restart policy, hosts the control-plane EventBus (docs/ipc_decision.md), and
brings everything down cleanly on a signal. It absorbs the start/stop scripts: `manage.py`
stays the operator CLI, but the daemon is the supervised runtime.

Design:
  - Children run as REAL children of this process (asyncio.create_subprocess_exec, not
    detached) so the loop is notified the instant one dies via proc.wait().
  - Three-strike policy: a child that dies is relaunched; a child that has been up longer
    than `stable_reset_s` is considered healthy and its strike count resets. After
    `max_strikes` (3) restarts a further death leaves it DOWN -- i.e. the fourth failure
    stays down (Phase 3 Exit Gate).
  - Fresh-logs-on-start: each child log is truncated once when the daemon starts; restarts
    within the same daemon session append (so restart history is preserved).
  - The argv/env for the real children come from manage.py (llama_argv / api_argv) so the
    daemon and the CLI spawn the byte-identical command.

The Supervisor class is transport/child-agnostic and unit-tested with dummy children
(tests/test_daemon.py); main() wires the real stack.
"""
import argparse
import asyncio
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "services" / "api"))

import eventbus as eb  # noqa: E402


def _log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


# Phase 8 daemon env hygiene: env vars stripped from a hygiene=True child's environment so a
# supervised agent (Hermes) inherits no cloud credential it could egress through. Exact names
# plus prefixes (any var starting with one of _SECRET_ENV_PREFIXES is dropped).
_SECRET_ENV_KEYS = {
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "GROQ_API_KEY", "MISTRAL_API_KEY", "COHERE_API_KEY", "HF_TOKEN",
    "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN", "REPLICATE_API_TOKEN",
    "OPENROUTER_API_KEY", "TOGETHER_API_KEY", "PERPLEXITY_API_KEY", "DEEPSEEK_API_KEY",
    "GITHUB_TOKEN", "GH_TOKEN", "SLACK_TOKEN", "SLACK_BOT_TOKEN", "NPM_TOKEN",
}
_SECRET_ENV_PREFIXES = (
    "AWS_", "AZURE_", "GOOGLE_", "GCP_", "GCLOUD_", "OPENAI_", "ANTHROPIC_",
    "OTEL_EXPORTER_", "LANGCHAIN_", "LANGSMITH_",
)
# ...but keep these even though they match a prefix above (they are not secrets).
_SECRET_ENV_KEEP = {"AWS_DEFAULT_REGION", "AWS_REGION", "GOOGLE_APPLICATION_CREDENTIALS_OK"}


def sanitize_env(env: Dict[str, str]) -> Dict[str, str]:
    """Return a copy of env with cloud/egress secrets removed (Phase 8 hygiene)."""
    out = {}
    for k, v in env.items():
        if k in _SECRET_ENV_KEEP:
            out[k] = v
            continue
        if k in _SECRET_ENV_KEYS or any(k.startswith(p) for p in _SECRET_ENV_PREFIXES):
            continue
        out[k] = v
    return out


class ChildSpec:
    """Static description of a supervised child. Pure config; runtime state lives in _Child."""

    def __init__(self, name: str, argv: List[str], *, cwd: Optional[str] = None,
                 env: Optional[Dict[str, str]] = None, logfile: Optional[str] = None,
                 pidfile: Optional[str] = None, hygiene: bool = False):
        self.name = name
        self.argv = list(argv)
        self.cwd = cwd
        self.env = dict(env or {})
        self.logfile = logfile
        self.pidfile = pidfile
        # hygiene=True -> launch this child with cloud/egress secrets stripped from the env
        # (Phase 8 runtime-egress-containment: a supervised agent inherits no API keys it could
        # exfiltrate through). The kernel netns/iptables half is host-applied (egress_baseline.*).
        self.hygiene = hygiene


class _Child:
    """A ChildSpec plus live supervision state."""

    def __init__(self, spec: ChildSpec):
        self.spec = spec
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.pid: Optional[int] = None
        self.strikes = 0
        self.starts = 0
        self.last_start = 0.0
        self.last_rc: Optional[int] = None
        self.state = "pending"  # pending -> running -> restarting -> failed | stopped


class Supervisor:
    """Launches and supervises a set of ChildSpecs with a three-strike restart policy.

    Optionally hosts an EventBus (started/stopped with the supervisor). Drive it with
    start() then await wait(); stop() tears everything down."""

    def __init__(self, specs: List[ChildSpec], *, max_strikes: int = 3,
                 stable_reset_s: float = 60.0, restart_backoff: float = 1.0,
                 stop_grace: float = 8.0, bus: Optional[eb.EventBus] = None, log=_log):
        self.children = [_Child(s) for s in specs]
        self.max_strikes = max_strikes
        self.stable_reset_s = stable_reset_s
        self.restart_backoff = restart_backoff
        self.stop_grace = stop_grace
        self.bus = bus
        self.log = log
        self._stopping = False
        self._tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        self._stopping = False
        if self.bus is not None:
            await self.bus.start()
            self.log("[daemon] event bus up")
        for c in self.children:
            if c.spec.logfile:  # fresh-logs-on-start (truncate once)
                try:
                    open(c.spec.logfile, "wb").close()
                except OSError:
                    pass
        self._tasks = [asyncio.create_task(self._supervise(c)) for c in self.children]

    async def wait(self) -> None:
        """Block until every supervise task has ended (all children stopped or failed)."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _launch(self, c: _Child) -> asyncio.subprocess.Process:
        full_env = os.environ.copy()
        full_env.update(c.spec.env)
        if c.spec.hygiene:  # Phase 8: strip cloud/egress secrets for supervised agents
            full_env = sanitize_env(full_env)
        logf = open(c.spec.logfile, "ab") if c.spec.logfile else None
        try:
            proc = await asyncio.create_subprocess_exec(
                *c.spec.argv,
                stdout=(logf or asyncio.subprocess.DEVNULL),
                stderr=asyncio.subprocess.STDOUT,
                cwd=c.spec.cwd,
                env=full_env,
            )
        finally:
            if logf is not None:
                logf.close()  # the child inherited the fd; drop the parent's copy
        if c.spec.pidfile:  # keep manage.py status/down compatible
            try:
                Path(c.spec.pidfile).write_text(str(proc.pid))
            except OSError:
                pass
        return proc

    async def _supervise(self, c: _Child) -> None:
        while not self._stopping:
            c.starts += 1
            c.last_start = time.monotonic()
            try:
                c.proc = await self._launch(c)
            except Exception as e:  # noqa: BLE001 -- launch failure counts as a strike
                self.log(f"[daemon] {c.spec.name} launch failed: {e!r}")
                c.proc = None
                rc = -1
            else:
                c.pid = c.proc.pid
                c.state = "running"
                self.log(f"[daemon] {c.spec.name} started pid={c.pid} (start #{c.starts})")
                rc = await c.proc.wait()
            c.last_rc = rc

            if self._stopping:
                c.state = "stopped"
                break

            uptime = time.monotonic() - c.last_start
            if uptime >= self.stable_reset_s:
                c.strikes = 0  # ran long enough to be considered healthy; forgive past blips
            c.strikes += 1
            if c.strikes <= self.max_strikes:
                c.state = "restarting"
                self.log(f"[daemon] {c.spec.name} exited rc={rc} after {uptime:.1f}s; "
                         f"restart {c.strikes}/{self.max_strikes}")
                await asyncio.sleep(self.restart_backoff)
                continue
            c.state = "failed"
            self.log(f"[daemon] {c.spec.name} exited rc={rc}; STAYS DOWN "
                     f"after {self.max_strikes} strikes")
            break

    async def stop(self) -> None:
        self._stopping = True
        # SIGTERM all live children, then SIGKILL any that overstay the grace window.
        live = [c for c in self.children if c.proc is not None and c.proc.returncode is None]
        for c in live:
            try:
                c.proc.terminate()
            except ProcessLookupError:
                pass
        if live:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[c.proc.wait() for c in live], return_exceptions=True),
                    timeout=self.stop_grace)
            except asyncio.TimeoutError:
                for c in live:
                    if c.proc.returncode is None:
                        try:
                            c.proc.kill()
                        except ProcessLookupError:
                            pass
        for c in self.children:
            if c.spec.pidfile:
                try:
                    Path(c.spec.pidfile).unlink()
                except OSError:
                    pass
        for t in self._tasks:
            t.cancel()
        if self.bus is not None:
            await self.bus.stop()
        self.log("[daemon] all children stopped")

    def status(self) -> Dict[str, Any]:
        return {
            "children": {
                c.spec.name: {
                    "state": c.state, "pid": c.pid, "strikes": c.strikes,
                    "starts": c.starts, "last_rc": c.last_rc,
                    "alive": bool(c.proc is not None and c.proc.returncode is None),
                }
                for c in self.children
            }
        }


# ---------------------------------------------------------------------------
# Real-stack wiring
# ---------------------------------------------------------------------------
def hermes_present(root: Path) -> bool:
    """True if the isolated Hermes venv + CLI are installed (env_hermes/)."""
    sub = "Scripts" if os.name == "nt" else "bin"
    exe = ".exe" if os.name == "nt" else ""
    return (root / "env_hermes" / sub / f"python{exe}").is_file() and \
           (root / "env_hermes" / sub / f"hermes{exe}").is_file()


def hermes_bridge_spec(root: Path) -> Optional[ChildSpec]:
    """Phase 8: supervise the persona-side H2 bridge (tools/hermes_bridge.py loop) as a daemon
    child. Stdlib-only, so it runs under the project python; it shells out to the Hermes public
    CLI (HERMES_CLI). Launched with hygiene=True (no cloud secrets) -- runtime egress containment.
    Returns None if Hermes is not installed. NOTE: this supervises OUR bridge; the Hermes
    dispatcher/worker (their process, GPU-bound) is the EVO-X2 H2d leg, wired separately there."""
    if not hermes_present(root):
        return None
    sub = "Scripts" if os.name == "nt" else "bin"
    exe = ".exe" if os.name == "nt" else ""
    py = root / "env_hermes" / sub / f"python{exe}"  # stdlib, but keep it in the Hermes venv
    interval = os.getenv("HERMES_BRIDGE_INTERVAL", "30")
    env = {
        "HERMES_CLI": str(root / "env_hermes" / sub / f"hermes{exe}"),
        "HERMES_KANBAN_HOME": os.getenv("HERMES_KANBAN_HOME", str(root / "run" / "hermes_kanban")),
        "HERMES_HOME": os.getenv("HERMES_HOME", str(root / "persona" / "profiles" / "default")),
        "TASKS_DB": os.getenv("TASKS_DB", str(root / "data" / "tasks.db")),
    }
    return ChildSpec("hermes-bridge",
                     [str(py), "tools/hermes_bridge.py", "--interval", interval],
                     cwd=str(root), env=env,
                     logfile=str(root / "logs" / "hermes_bridge.log"),
                     pidfile=str(root / "run" / "hermes_bridge.pid"),
                     hygiene=True)


def _voice_paths(root: Path) -> Dict[str, str]:
    """Conventional host-provided voice engine locations; all env-overridable. The engines
    themselves are host-side compute (Phase 5: "host-side compute only") -- this only wires
    them as supervised children when their binary + model are present."""
    return {
        "stt_bin": os.getenv("WHISPER_SERVER_BIN", str(root / "llama_cpp" / "build" / "bin" / "whisper-server")),
        "stt_model": os.getenv("WHISPER_MODEL", str(root / "models" / "ggml-base.en.bin")),
        "stt_port": os.getenv("WHISPER_PORT", "8120"),
        "tts_bin": os.getenv("PIPER_BIN", str(root / "tools" / "piper" / "piper")),
        "tts_model": os.getenv("PIPER_MODEL", str(root / "models" / "piper_voice.onnx")),
        "tts_port": os.getenv("PIPER_PORT", "8121"),
    }


def stt_present(root: Path) -> bool:
    p = _voice_paths(root)
    return Path(p["stt_bin"]).is_file() and Path(p["stt_model"]).is_file()


def tts_present(root: Path) -> bool:
    p = _voice_paths(root)
    return Path(p["tts_bin"]).is_file() and Path(p["tts_model"]).is_file()


def whisper_stt_spec(root: Path) -> Optional[ChildSpec]:
    """Phase 5: whisper.cpp STT HTTP server as a supervised child. None if the binary/model is
    absent (the engine is host-provided -- see docs/voice_pipeline.md)."""
    if not stt_present(root):
        return None
    p = _voice_paths(root)
    return ChildSpec("whisper-stt",
                     [p["stt_bin"], "--model", p["stt_model"], "--host", "127.0.0.1", "--port", p["stt_port"]],
                     cwd=str(root), logfile=str(root / "logs" / "whisper.log"),
                     pidfile=str(root / "run" / "whisper.pid"))


def piper_tts_spec(root: Path) -> Optional[ChildSpec]:
    """Phase 5: Piper TTS HTTP server as a supervised child. None if the binary/model is absent.
    (Piper is GPL-3.0 -- used as a separate process, never linked; see knowledge.md licensing.)"""
    if not tts_present(root):
        return None
    p = _voice_paths(root)
    return ChildSpec("piper-tts",
                     [p["tts_bin"], "--model", p["tts_model"], "--http", "--port", p["tts_port"]],
                     cwd=str(root), logfile=str(root / "logs" / "piper.log"),
                     pidfile=str(root / "run" / "piper.pid"))


def build_specs(root: Path, cfg: Dict[str, Any], *, with_llama: bool = True,
                with_api: bool = True, with_hermes: bool = False,
                with_voice: bool = False) -> List[ChildSpec]:
    """Build the real child map from manage.py's shared argv builders."""
    import manage  # imported here so the Supervisor stays importable without manage's deps
    specs: List[ChildSpec] = []
    runlog = root / "logs"
    runpid = root / "run"
    if with_llama:
        argv, env = manage.llama_argv(root, cfg)
        specs.append(ChildSpec("llama-server", argv, cwd=str(root), env=env,
                               logfile=str(runlog / "persona.log"),
                               pidfile=str(runpid / "persona.pid")))
    if with_api:
        argv, env = manage.api_argv(root, cfg)
        specs.append(ChildSpec("api", argv, cwd=str(root), env=env,
                               logfile=str(runlog / "api.log"),
                               pidfile=str(runpid / "api.pid")))
    if with_hermes:
        hspec = hermes_bridge_spec(root)
        if hspec is not None:
            specs.append(hspec)
        else:
            _log("[daemon] --with-hermes requested but env_hermes/ not found; skipping")
    if with_voice:  # Phase 5: STT/TTS engines, only if host-provided
        for builder, label in ((whisper_stt_spec, "whisper STT"), (piper_tts_spec, "piper TTS")):
            vspec = builder(root)
            if vspec is not None:
                specs.append(vspec)
            else:
                _log(f"[daemon] --with-voice: {label} engine not found; skipping")
    # nats-server child: DEFERRED to Phase 9 (NatsBus). The LoopbackBus needs no child.
    return specs


def make_bus() -> eb.EventBus:
    """Phase 3 bus. LoopbackBus for now (stdlib, no child); NatsBus selection lands with
    task 11 behind the [ipc] transport config key."""
    token = os.getenv("DAEMON_TOKEN", "")
    return eb.LoopbackBus(token=token)


async def _run(args) -> int:
    import manage
    root = REPO
    cfg = manage.load_config(root)
    (root / "logs").mkdir(exist_ok=True)
    (root / "run").mkdir(exist_ok=True)

    _on = lambda v: v.strip().lower() in ("1", "true", "yes", "on")  # noqa: E731
    with_hermes = args.with_hermes or _on(os.getenv("HERMES_DAEMON_ENABLED", "0"))
    with_voice = args.with_voice or _on(os.getenv("VOICE_DAEMON_ENABLED", "0"))
    specs = build_specs(root, cfg, with_llama=not args.no_llama, with_api=not args.no_api,
                        with_hermes=with_hermes, with_voice=with_voice)
    bus = make_bus()

    async def _on_event(event, payload):
        _log(f"[daemon] event {event}: {payload}")

    sup = Supervisor(specs, bus=bus)
    await bus.subscribe("*", _on_event)
    await sup.start()
    _log(f"[daemon] supervising {[s.name for s in specs]}; bus on "
         f"127.0.0.1:{eb.default_loopback_port()}")

    stop_evt = asyncio.Event()

    def _request_stop():
        _log("[daemon] signal received -> shutting down")
        stop_evt.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):  # Windows / no event loop signal support
            signal.signal(sig, lambda *_: _request_stop())

    # Run until a signal OR every child has given up (all failed/stopped).
    waiter = asyncio.create_task(sup.wait())
    stopper = asyncio.create_task(stop_evt.wait())
    await asyncio.wait({waiter, stopper}, return_when=asyncio.FIRST_COMPLETED)
    await sup.stop()
    for t in (waiter, stopper):
        t.cancel()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Project_Persona Phase 3 supervised daemon.")
    ap.add_argument("--no-llama", action="store_true", help="Do not supervise llama-server.")
    ap.add_argument("--no-api", action="store_true", help="Do not supervise the API.")
    ap.add_argument("--with-hermes", action="store_true",
                    help="Also supervise the Hermes H2 bridge (needs env_hermes/; or set HERMES_DAEMON_ENABLED=1).")
    ap.add_argument("--with-voice", action="store_true",
                    help="Also supervise the voice engines (Whisper STT / Piper TTS, if installed; or VOICE_DAEMON_ENABLED=1).")
    args = ap.parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
