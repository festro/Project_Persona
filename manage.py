#!/usr/bin/env python3
"""Project_Persona cross-platform lifecycle launcher.

One entrypoint that replaces the bash-only start/stop/status/doctor scripts so a
node can be brought up, torn down, and health-checked identically on Windows and
Linux (x86-64 / ARM64), with no bash required for core lifecycle.

Subcommands:
    up       Start llama-server then the FastAPI companion API.
    down     Stop the API then llama-server.
    status   Show pidfile/process/config/model state.
    doctor   Deep health check (filesystem, venv, live endpoints, safe-config).

Pure standard library (Python 3.8+). Apple/Metal is intentionally out of scope.
"""

import argparse
import ctypes
import json
import os
import platform
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

IS_WINDOWS = os.name == "nt"

GREEN = "" if IS_WINDOWS else "\033[0;32m"
RED = "" if IS_WINDOWS else "\033[0;31m"
YELLOW = "" if IS_WINDOWS else "\033[1;33m"
BLUE = "" if IS_WINDOWS else "\033[0;34m"
NC = "" if IS_WINDOWS else "\033[0m"


def ok(msg):
    print(f"{GREEN}[OK]{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}[--]{NC} {msg}")


def err(msg):
    print(f"{RED}[XX]{NC} {msg}")


def info(msg):
    print(f"{BLUE}==>{NC} {msg}")


def repo_root():
    env_root = os.environ.get("AI_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parent


def load_env_file(path, target):
    if not path.is_file():
        return target
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        target[key] = val
    return target


def load_config(root):
    cfg = {}
    load_env_file(root / "run" / "llama-servers.env", cfg)
    load_env_file(root / "run" / "config.env", cfg)
    return cfg


def pid_alive(pid):
    if pid is None:
        return False
    if IS_WINDOWS:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) == 0:
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_pid(pidfile):
    try:
        text = Path(pidfile).read_text(encoding="utf-8").strip()
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def write_pid(pidfile, pid):
    Path(pidfile).write_text(str(pid), encoding="utf-8")


def terminate_pid(pid, timeout=8.0):
    if not pid_alive(pid):
        return True
    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.25)
    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return True
    time.sleep(0.5)
    return not pid_alive(pid)


def spawn_detached(argv, logfile, cwd=None, extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    log = open(logfile, "ab")
    kwargs = dict(stdout=log, stderr=subprocess.STDOUT, cwd=cwd, env=env, close_fds=True)
    if IS_WINDOWS:
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(argv, **kwargs)
    return proc.pid


def http_get_json(url, timeout=2.0):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body), body
        except json.JSONDecodeError:
            return None, body
    except (urllib.error.URLError, OSError):
        return None, ""


def http_post_json(url, payload, timeout=12.0):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(body), body
        except json.JSONDecodeError:
            return None, body
    except (urllib.error.URLError, OSError):
        return None, ""


def llama_binary(root):
    override = os.environ.get("LLAMA_BIN")
    if override:
        return Path(override)
    if IS_WINDOWS:
        return root / "llama_cpp" / "windows" / "llama-server.exe"
    return root / "llama_cpp" / "build" / "bin" / "llama-server"


def find_api_python(root):
    candidates = []
    if IS_WINDOWS:
        candidates += [
            root / "portable" / "python" / "python.exe",
            root / "env" / "Scripts" / "python.exe",
        ]
    else:
        candidates += [root / "env" / "bin" / "python"]
    for cand in candidates:
        if cand.is_file():
            return cand
    return Path(sys.executable)


def api_env(root, cfg):
    persona_root = cfg.get("PERSONA_ROOT", str(root / "persona"))
    env = {
        "AI_ROOT": str(root),
        "PERSONA_ROOT": persona_root,
        "PROFILES_DIR": cfg.get("PROFILES_DIR", str(Path(persona_root) / "profiles")),
        "GLOBAL_MEMORY_DIR": cfg.get(
            "GLOBAL_MEMORY_DIR", str(Path(persona_root) / "global_memory")
        ),
        "DEFAULT_PROFILE": cfg.get("DEFAULT_PROFILE", "default"),
        "LLAMA_HOST": cfg.get("HOST", cfg.get("LLAMA_HOST", "127.0.0.1")),
        "PERSONA_PORT": cfg.get("PERSONA_PORT", "8090"),
        "RAG_ENABLED": cfg.get("RAG_ENABLED", "1"),
        "ASYNC_SCIENTIST_ENABLED": cfg.get("ASYNC_SCIENTIST_ENABLED", "0"),
        "PROFILE_WRAPPERS_ENABLED": cfg.get("PROFILE_WRAPPERS_ENABLED", "1"),
        "PERSONA_WRITEBACK_ENABLED": cfg.get("PERSONA_WRITEBACK_ENABLED", "1"),
        "JOBS_PERSIST_ENABLED": cfg.get("JOBS_PERSIST_ENABLED", "1"),
        "JOBS_PERSIST_PATH": cfg.get("JOBS_PERSIST_PATH", str(root / "run" / "jobs.jsonl")),
        "MEMORY_DISTILL_ENABLED": cfg.get("MEMORY_DISTILL_ENABLED", "1"),
        "RAG_TOP_K": cfg.get("RAG_TOP_K", "6"),
        "EMBED_MODEL": cfg.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5"),
        "EMBED_BACKEND": cfg.get("EMBED_BACKEND", "auto"),
        "ANONYMIZED_TELEMETRY": cfg.get("ANONYMIZED_TELEMETRY", "False"),
    }
    for key in (
        "THINKING_MODE_DEFAULT",
        "THINKING_MODE_TOPICS",
        "SAMPLING_DEFAULT_TEMP",
        "SAMPLING_DEFAULT_TOP_P",
        "SAMPLING_DEFAULT_TOP_K",
        "SAMPLING_DEFAULT_MIN_P",
        "SAMPLING_DEFAULT_PRESENCE_PENALTY",
        "SAMPLING_THINK_TEMP",
        "SAMPLING_THINK_TOP_P",
        "SAMPLING_THINK_TOP_K",
        "SAMPLING_THINK_MIN_P",
        "SAMPLING_THINK_PRESENCE_PENALTY",
    ):
        if key in cfg:
            env[key] = cfg[key]
    return env


def start_llama(root, cfg, wait):
    pidfile = root / "run" / "persona.pid"
    existing = read_pid(pidfile)
    if pid_alive(existing):
        ok(f"llama-server already running (pid {existing})")
        return True

    binpath = llama_binary(root)
    if not binpath.is_file():
        err(f"llama-server binary not found: {binpath}")
        if IS_WINDOWS:
            warn("Extract the Vulkan prebuilt into llama_cpp/windows/")
        else:
            warn("Build llama.cpp into llama_cpp/build/")
        return False

    model = cfg.get("PERSONA_MODEL", "")
    model_path = root / "models" / model
    if not model_path.is_file():
        err(f"model not found: {model_path}")
        return False

    host = cfg.get("HOST", "127.0.0.1")
    port = cfg.get("PERSONA_PORT", "8090")
    threads = cfg.get("THREADS", "0")
    if str(threads) == "0":
        threads = str(os.cpu_count() or 8)

    argv = [
        str(binpath),
        "--model", str(model_path),
        "--host", host,
        "--port", str(port),
        "--ctx-size", cfg.get("PERSONA_CTX", "32768"),
        "--threads", threads,
        "--batch-size", cfg.get("BATCH_SIZE", "512"),
        "--ubatch-size", cfg.get("UBATCH_SIZE", "512"),
        "--cache-type-k", cfg.get("CACHE_TYPE_K", "q8_0"),
        "--cache-type-v", cfg.get("CACHE_TYPE_V", "q8_0"),
        "--n-gpu-layers", cfg.get("GPU_LAYERS_PERSONA", "999"),
        "--parallel", cfg.get("PERSONA_PARALLEL", "4"),
        "--cont-batching",
        "--jinja",
    ]
    if IS_WINDOWS:
        argv += ["--device", "Vulkan0"]

    extra_env = {}
    if IS_WINDOWS:
        extra_env["GGML_VK_VISIBLE_DEVICES"] = "0"
    else:
        lib = cfg.get("LLAMA_LIB_DIR")
        if lib:
            extra_env["LD_LIBRARY_PATH"] = (
                lib + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
            )

    logfile = root / "logs" / "persona.log"
    info(f"Starting llama-server on http://{host}:{port}  (model={model})")
    pid = spawn_detached(argv, str(logfile), cwd=str(root), extra_env=extra_env)
    write_pid(pidfile, pid)
    time.sleep(2)
    if not pid_alive(pid):
        err(f"llama-server failed to start; see {logfile}")
        return False
    ok(f"llama-server pid={pid}  log={logfile}")

    if wait:
        if wait_for_health(f"http://{host}:{port}/health", timeout=120):
            ok("llama-server /health responding")
        else:
            warn("llama-server started but /health did not come up in time")
    return True


def start_api(root, cfg):
    pidfile = root / "run" / "api.pid"
    existing = read_pid(pidfile)
    if pid_alive(existing):
        ok(f"API already running (pid {existing})")
        return True

    pybin = find_api_python(root)
    if not pybin.is_file():
        err(f"API python interpreter not found: {pybin}")
        warn("Run scripts/bootstrap_portable_python.ps1 (Windows) or setup_native_stack.sh (Linux)")
        return False

    argv = [
        str(pybin),
        "-m", "uvicorn",
        "server:app",
        "--app-dir", str(root / "services" / "api"),
        "--host", "127.0.0.1",
        "--port", "8000",
    ]
    logfile = root / "logs" / "api.log"
    info("Starting FastAPI on http://127.0.0.1:8000")
    pid = spawn_detached(
        argv, str(logfile), cwd=str(root), extra_env=api_env(root, cfg)
    )
    write_pid(pidfile, pid)
    time.sleep(1.5)
    if not pid_alive(pid):
        err(f"API failed to start; see {logfile}")
        return False
    ok(f"API pid={pid}  log={logfile}")
    return True


def wait_for_health(url, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data, _ = http_get_json(url, timeout=2.0)
        if data is not None:
            return True
        time.sleep(1.5)
    return False


def ensure_dirs(root):
    for d in ("logs", "run"):
        (root / d).mkdir(parents=True, exist_ok=True)


def cmd_up(root, cfg, args):
    ensure_dirs(root)
    llama_ok = start_llama(root, cfg, wait=not args.no_wait)
    if not llama_ok and not args.api_only:
        err("Aborting: llama-server did not start. Use --api-only to start the API anyway.")
        return 1
    if args.llama_only:
        return 0
    api_ok = start_api(root, cfg)
    return 0 if api_ok else 1


def stop_named(root, name):
    pidfile = root / "run" / f"{name}.pid"
    pid = read_pid(pidfile)
    if pid is None:
        return
    if not pid_alive(pid):
        warn(f"{name}: stale pidfile, removing")
        try:
            pidfile.unlink()
        except OSError:
            pass
        return
    info(f"Stopping {name} (pid {pid})")
    if terminate_pid(pid):
        ok(f"{name} stopped")
    else:
        err(f"{name} did not stop")
    try:
        pidfile.unlink()
    except OSError:
        pass


def cmd_down(root, cfg, args):
    stop_named(root, "api")
    for name in ("persona", "scientist", "reasoning", "coder", "persona_win"):
        stop_named(root, name)
    ok("Shutdown complete")
    return 0


def cmd_status(root, cfg, args):
    print("=== Project_Persona status ===")
    print(f"AI_ROOT: {root}")
    print(f"OS: {platform.system()} {platform.machine()}")
    print()
    print("Processes:")
    for name in ("api", "persona"):
        pid = read_pid(root / "run" / f"{name}.pid")
        if pid_alive(pid):
            ok(f"{name}: running (pid {pid})")
        elif pid is not None:
            err(f"{name}: stale pidfile (pid {pid} not alive)")
        else:
            warn(f"{name}: not running")
    print()
    print("Config:")
    host = cfg.get("HOST", "127.0.0.1")
    port = cfg.get("PERSONA_PORT", "8090")
    model = cfg.get("PERSONA_MODEL", "<unset>")
    print(f"  host={host}  persona_port={port}  ctx={cfg.get('PERSONA_CTX', '<unset>')}")
    print(f"  model={model}")
    print()
    print("Model file:")
    mpath = root / "models" / model
    if model != "<unset>" and mpath.is_file():
        size_mb = mpath.stat().st_size / (1024 * 1024)
        ok(f"{model} ({size_mb:.0f} MB)")
    else:
        warn(f"{model} missing")
    print()
    print("Endpoints:")
    print(f"  API:     http://127.0.0.1:8000/docs")
    print(f"  Persona: http://{host}:{port}/health")
    return 0


SAFE_CONFIG_EGRESS_TOOLS = {"web_search", "web_extract", "web_crawl"}


def validate_safe_config_regex(cfg_path):
    import re

    text = cfg_path.read_text(encoding="utf-8")
    errors = []
    if not re.search(r"^[ \t]*provider:[ \t]*custom", text, re.MULTILINE):
        errors.append("model.provider: custom not found (regex fallback)")
    if not re.search(r"base_url:[ \t]*http://(127\.0\.0\.1|localhost):", text):
        errors.append("local base_url not found (regex fallback)")
    if not re.search(r"fallback_model:[ \t]*\{\}", text):
        errors.append("empty fallback_model not found (regex fallback)")
    for tool in sorted(SAFE_CONFIG_EGRESS_TOOLS):
        if not re.search(r"^[ \t]*-[ \t]*%s([ \t]|$)" % re.escape(tool), text, re.MULTILINE):
            errors.append("tools.disabled missing %s (regex fallback)" % tool)
    if not re.search(r"^[ \t]*-[ \t]*browser", text, re.MULTILINE):
        errors.append("tools.disabled missing browser_* tools (regex fallback)")
    return (len(errors) == 0), errors


def validate_safe_config(cfg_path):
    try:
        import yaml
    except ImportError:
        return validate_safe_config_regex(cfg_path)
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return False, [f"could not parse config.yaml: {exc}"]

    errors = []
    model = data.get("model") or {}
    if model.get("provider") != "custom":
        errors.append("model.provider must be 'custom'")
    base = str(model.get("base_url") or "")
    if not (base.startswith("http://127.0.0.1:") or base.startswith("http://localhost:")):
        errors.append("model.base_url must be a local endpoint")
    api_key = str(model.get("api_key") or "")
    if api_key and api_key not in ("not-needed", "local", "local-key") and not api_key.startswith("${"):
        errors.append("model.api_key looks like a real secret")
    fb = data.get("fallback_model")
    if fb not in (None, {}, "", [], False):
        errors.append("fallback_model must be empty (no cloud failover)")
    aux = data.get("auxiliary") or {}
    for name, spec in aux.items():
        spec = spec or {}
        if spec.get("provider") != "main":
            errors.append(f"auxiliary.{name}.provider must be 'main'")
    tools = data.get("tools") or {}
    disabled = set(tools.get("disabled") or [])
    missing = SAFE_CONFIG_EGRESS_TOOLS - disabled
    if missing:
        errors.append("tools.disabled missing egress tools: " + ",".join(sorted(missing)))
    if not any(str(t).startswith("browser") for t in disabled):
        errors.append("tools.disabled must disable browser_* tools")
    return (len(errors) == 0), errors


def cmd_doctor(root, cfg, args):
    info("Project_Persona doctor")
    print(f"AI_ROOT: {root}")
    print(f"OS: {platform.system()} {platform.machine()}  python={platform.python_version()}")
    print()

    info("Filesystem")
    if root.is_dir():
        ok("AI_ROOT exists")
    else:
        err(f"AI_ROOT missing: {root}")
        return 1
    for d in ("scripts", "services/api", "run", "logs", "models", "persona"):
        if (root / d).is_dir():
            ok(f"dir present: {d}")
        else:
            warn(f"dir missing: {d}")
    print()

    info("Interpreters / binaries")
    pybin = find_api_python(root)
    if pybin.is_file():
        ok(f"API python: {pybin}")
    else:
        warn(f"API python not found (looked for env/portable interpreter)")
    binpath = llama_binary(root)
    if binpath.is_file():
        ok(f"llama-server binary: {binpath}")
    else:
        warn(f"llama-server binary missing: {binpath}")
    print()

    info("Model file")
    model = cfg.get("PERSONA_MODEL", "")
    mpath = root / "models" / model
    if model and mpath.is_file():
        size_mb = mpath.stat().st_size / (1024 * 1024)
        ok(f"model present: models/{model} ({size_mb:.0f} MB)")
    else:
        warn(f"model missing: models/{model}")
    print()

    info("Profile files (default profile)")
    default_profile = cfg.get("DEFAULT_PROFILE", "default")
    pbase = root / "persona" / "profiles" / default_profile
    if pbase.is_dir():
        ok(f"default profile dir: {pbase}")
        for f in ("SOUL.md", ".hermes.md", "config.yaml"):
            if (pbase / f).is_file():
                ok(f"profile file present: {default_profile}/{f}")
            else:
                warn(f"profile file missing: {default_profile}/{f}")
    else:
        warn(f"default profile dir missing: {pbase}")
    print()

    info("Runtime processes")
    for name in ("persona", "api"):
        pid = read_pid(root / "run" / f"{name}.pid")
        if pid_alive(pid):
            ok(f"{name} running (pid {pid})")
        elif pid is not None:
            warn(f"{name} stale pidfile (pid {pid})")
        else:
            warn(f"{name} pidfile not found")
    print()

    info("Live health")
    host = cfg.get("HOST", "127.0.0.1")
    port = cfg.get("PERSONA_PORT", "8090")
    data, _ = http_get_json(f"http://{host}:{port}/health", timeout=2.0)
    if data is not None:
        ok(f"persona /health OK (http://{host}:{port}/health)")
    else:
        warn(f"persona /health not responding (http://{host}:{port}/health)")
    data, _ = http_get_json("http://127.0.0.1:8000/health", timeout=2.0)
    if data is not None:
        ok("API /health OK (http://127.0.0.1:8000/health)")
    else:
        warn("API /health not responding (http://127.0.0.1:8000/health)")
    print()

    if args.deep:
        info("Completion smoke test (live)")
        payload = {"prompt": "Say 'ok' and one short sentence.", "n_predict": 32, "temperature": 0.2}
        data, _ = http_post_json(f"http://{host}:{port}/completion", payload, timeout=12.0)
        if data is not None and "content" in data:
            ok("persona completion OK")
        else:
            warn("persona completion failed or timed out")
        print()

    info("Safe-config conformance (T1 gate)")
    cfg_path = pbase / "config.yaml"
    t1_gate = "unknown"
    if not cfg_path.is_file():
        warn(f"default profile config.yaml missing: {cfg_path}")
        t1_gate = "fail"
    else:
        passed, problems = validate_safe_config(cfg_path)
        if passed is None:
            warn(problems[0])
            t1_gate = "skipped"
        elif passed:
            ok("default profile config.yaml conforms to safe-config schema")
            t1_gate = "pass"
        else:
            err("default profile config.yaml FAILED safe-config conformance")
            for p in problems:
                print(f"    VIOLATION: {p}")
            t1_gate = "fail"
    print()

    hermes_installed = "no"
    hermes_py = root / ("env_hermes/Scripts/python.exe" if IS_WINDOWS else "env_hermes/bin/python")
    hermes_bin = root / ("env_hermes/Scripts/hermes.exe" if IS_WINDOWS else "env_hermes/bin/hermes")
    if hermes_py.is_file() and hermes_bin.is_file():
        hermes_installed = "yes"

    print(f"T1 GATE: env_hermes_installed={hermes_installed} safe_config={t1_gate}")
    if args.strict and (t1_gate != "pass" or hermes_installed != "yes"):
        err("--strict and T1 gate not fully green")
        return 2
    print()
    info("Doctor done")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="manage.py",
        description="Project_Persona cross-platform lifecycle launcher.",
    )
    p.add_argument("--root", help="Override AI_ROOT (defaults to this file's directory).")
    sub = p.add_subparsers(dest="command", required=True)

    up = sub.add_parser("up", help="Start llama-server then the API.")
    up.add_argument("--no-wait", action="store_true", help="Do not poll llama-server /health before starting the API.")
    up.add_argument("--llama-only", action="store_true", help="Start only llama-server.")
    up.add_argument("--api-only", action="store_true", help="Start the API even if llama-server is down.")

    sub.add_parser("down", help="Stop the API then llama-server.")
    sub.add_parser("status", help="Show pidfile/process/config state.")

    doc = sub.add_parser("doctor", help="Deep health check.")
    doc.add_argument("--deep", action="store_true", help="Include a live completion smoke test.")
    doc.add_argument("--strict", action="store_true", help="Exit non-zero unless the T1 gate is fully green.")

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.root:
        os.environ["AI_ROOT"] = args.root
    root = repo_root()
    cfg = load_config(root)
    handlers = {
        "up": cmd_up,
        "down": cmd_down,
        "status": cmd_status,
        "doctor": cmd_doctor,
    }
    return handlers[args.command](root, cfg, args)


if __name__ == "__main__":
    sys.exit(main())
