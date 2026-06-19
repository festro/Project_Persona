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
import collections
import contextlib
import ctypes
import http.server
import io
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
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


def os_tag():
    return "windows" if IS_WINDOWS else "linux"


def host_tag():
    """Lowercased short hostname used to select a committed per-host config override
    (run/config.<host>.toml). PERSONA_HOST env wins (escape hatch / testability)."""
    h = os.environ.get("PERSONA_HOST")
    if h:
        return h.strip().lower()
    return socket.gethostname().split(".")[0].lower()


def _merge_flat(cfg, table):
    for k, v in table.items():
        if isinstance(v, dict):
            continue
        if isinstance(v, bool):
            cfg[k] = "True" if v else "False"
        elif isinstance(v, (list, tuple)):
            cfg[k] = ",".join(str(x) for x in v)
        else:
            cfg[k] = str(v)


def load_config_toml(path):
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            warn("config.toml present but no TOML parser (need Python 3.11+); using .env")
            return None
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        warn(f"config.toml unreadable ({e}); falling back to .env")
        return None
    cfg = {}
    _merge_flat(cfg, data.get("base", {}))
    _merge_flat(cfg, data.get("runtime", {}))
    _merge_flat(cfg, data.get(os_tag(), {}))
    return cfg


def _merge_host_overrides(root, cfg):
    """Merge a committed per-host override file run/config.<host>.toml over cfg, LAST
    (after base/runtime/<os>), so D:\\ stays the single source of truth for per-host
    differences instead of an ephemeral patch on a disposable clone. Returns the file
    name applied, or None."""
    hpath = root / "run" / ("config.%s.toml" % host_tag())
    if not hpath.is_file():
        return None
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return None
    try:
        with open(hpath, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        warn(f"per-host config unreadable ({e}); ignoring {hpath.name}")
        return None
    _merge_flat(cfg, data.get("base", {}))
    _merge_flat(cfg, data.get("runtime", {}))
    _merge_flat(cfg, data.get(os_tag(), {}))
    return hpath.name


def load_config(root):
    toml_path = root / "run" / "config.toml"
    if toml_path.is_file():
        cfg = load_config_toml(toml_path)
        if cfg is not None:
            _merge_host_overrides(root, cfg)
            return cfg
    cfg = {}
    load_env_file(root / "run" / "llama-servers.env", cfg)
    load_env_file(root / "run" / f"llama-servers.{os_tag()}.env", cfg)
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


def http_health_up(url, timeout=2.0):
    if not url:
        return False
    try:
        data, _ = http_get_json(url, timeout=timeout)
    except Exception:
        return False
    return data is not None


def pids_by_cmdline(needles):
    if IS_WINDOWS or not needles:
        return []
    if isinstance(needles, str):
        needles = [needles]
    proc = Path("/proc")
    if not proc.is_dir():
        return []
    skip = {os.getpid(), os.getppid()}
    found = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        candidate = int(entry.name)
        if candidate in skip:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        cmd = raw.replace(b"\x00", b" ").decode("utf-8", "replace")
        if all(n in cmd for n in needles):
            found.append(candidate)
    return found


def resolve_live_pid(pid, health_url=None, needles=None):
    if pid_alive(pid):
        return pid
    if http_health_up(health_url):
        for candidate in pids_by_cmdline(needles):
            return candidate
    return None


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


def resolve_model(root, cfg):
    models_dir = root / "models"
    configured = cfg.get("PERSONA_MODEL", "")
    if configured:
        p = models_dir / configured
        if p.is_file():
            return p
        warn(f"configured model not found: {p}")
    present = sorted(models_dir.glob("*.gguf")) if models_dir.is_dir() else []
    if len(present) == 1:
        warn(f"falling back to the only GGUF present: {present[0].name}")
        return present[0]
    if not present:
        err(f"no GGUF model found in {models_dir} (set PERSONA_MODEL or add a .gguf)")
        return None
    names = ", ".join(p.name for p in present)
    err(f"PERSONA_MODEL unset/missing and multiple GGUFs present ({names}); set PERSONA_MODEL")
    return None


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _mmproj_args(root, cfg):
    """['--mmproj', <path>] when vision serving is enabled and the projector file is
    present, else []. VISION_ENABLED gates it: the mmproj may be on disk (the
    provisioner fetches it regardless) but a headless node stays text-only until
    vision is opted in. MMPROJ_PATH resolves under models/ if not absolute."""
    if not _truthy(cfg.get("VISION_ENABLED")):
        return []
    mm = (cfg.get("MMPROJ_PATH") or "").strip()
    if not mm:
        return []
    p = Path(mm)
    if not p.is_absolute():
        p = root / "models" / mm
    if not p.is_file():
        warn(f"VISION_ENABLED but mmproj not found: {p} (serving text-only)")
        return []
    return ["--mmproj", str(p)]


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

    model_path = resolve_model(root, cfg)
    if model_path is None:
        return False
    model = model_path.name

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
        "--parallel", cfg.get("PERSONA_PARALLEL", "4"),
        "--cont-batching",
        "--jinja",
    ]
    ngl = str(cfg.get("GPU_LAYERS_PERSONA", "auto")).strip().lower()
    if ngl and ngl != "auto":
        argv += ["--n-gpu-layers", ngl]
    else:
        info("GPU layers: auto (letting llama-server fit the offload to VRAM)")
    mmproj = _mmproj_args(root, cfg)
    if mmproj:
        argv += mmproj
        info(f"vision ON: loading mmproj {Path(mmproj[1]).name}")
    backend = (cfg.get("LLAMA_BACKEND") or ("vulkan" if IS_WINDOWS else "")).strip().lower()
    extra_env = {}
    if backend == "vulkan":
        argv += ["--device", "Vulkan0"]
        extra_env["GGML_VK_VISIBLE_DEVICES"] = cfg.get("GGML_VK_VISIBLE_DEVICES", "0")
    elif backend:
        info(f"llama backend '{backend}': letting the binary pick its device (no Vulkan flags)")
    if not IS_WINDOWS:
        lib = cfg.get("LLAMA_LIB_DIR") or str(root / "llama_cpp" / "build" / "bin")
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


def _maybe_first_run(root, cfg, args):
    """First-run hook (provisioner P4): if no model is servable, offer to provision
    one (interactive) or auto-provision under `up --yes`. Returns the (possibly
    reloaded) cfg to continue with, or None to abort the start."""
    sp = str(root / "scripts")
    if sp not in sys.path:
        sys.path.insert(0, sp)
    try:
        import provision_fetch as pf
    except Exception:
        return cfg  # no provisioner available; let start_llama report the missing model
    if pf.model_resolvable(root / "models", cfg.get("PERSONA_MODEL", "")):
        return cfg

    warn("no servable model (PERSONA_MODEL unset/missing and not exactly one GGUF present)")
    auto = getattr(args, "yes", False)
    if not auto:
        try:
            resp = input("run first-run model provisioning now? [Y/n] ").strip().lower()
        except EOFError:
            resp = "n"
        if resp in ("n", "no"):
            err("no model to serve; run `manage.py provision` or set PERSONA_MODEL")
            return None

    prov_args = argparse.Namespace(yes=True, write_config=True, dry_run=False,
                                   model=None, text_only=False,
                                   hf_token=getattr(args, "hf_token", None))
    rc = cmd_provision(root, cfg, prov_args)
    if rc != 0:
        err(f"first-run provisioning failed (rc {rc}); not starting")
        return None
    return load_config(root)  # reload so start_llama sees the wired PERSONA_MODEL


def cmd_up(root, cfg, args):
    ensure_dirs(root)
    cfg = _maybe_first_run(root, cfg, args)
    if cfg is None:
        return 1
    llama_ok = start_llama(root, cfg, wait=not args.no_wait)
    if not llama_ok and not args.api_only:
        err("Aborting: llama-server did not start. Use --api-only to start the API anyway.")
        return 1
    if args.llama_only:
        return 0
    api_ok = start_api(root, cfg)
    if api_ok and not args.no_wait:
        if wait_for_health("http://127.0.0.1:8000/health", timeout=120):
            ok("API /health responding")
        else:
            warn("API started but /health did not come up in time (embedder/Chroma init?)")
    return 0 if api_ok else 1


def stop_named(root, name, health_url=None, needles=None):
    pidfile = root / "run" / f"{name}.pid"
    pid = read_pid(pidfile)
    live = resolve_live_pid(pid, health_url, needles)
    if live is None:
        if pid is not None:
            warn(f"{name}: stale pidfile, removing")
            try:
                pidfile.unlink()
            except OSError:
                pass
        return
    if pid is None:
        warn(f"{name}: no pidfile but /health still up; killing real pid {live}")
    elif live != pid:
        warn(f"{name}: pidfile pid {pid} stale but /health up; killing real pid {live}")
    info(f"Stopping {name} (pid {live})")
    if terminate_pid(live):
        ok(f"{name} stopped")
    else:
        err(f"{name} did not stop")
    try:
        pidfile.unlink()
    except OSError:
        pass


def cmd_down(root, cfg, args):
    host = cfg.get("HOST", "127.0.0.1")
    pport = cfg.get("PERSONA_PORT", "8090")
    stop_named(root, "api", "http://127.0.0.1:8000/health", ["server:app"])
    stop_named(root, "persona", f"http://{host}:{pport}/health",
               ["llama-server", f"--port {pport}"])
    for name in ("scientist", "reasoning", "coder", "persona_win"):
        stop_named(root, name)
    ok("Shutdown complete")
    return 0


def cmd_status(root, cfg, args):
    host = cfg.get("HOST", "127.0.0.1")
    port = cfg.get("PERSONA_PORT", "8090")
    health_urls = {
        "api": "http://127.0.0.1:8000/health",
        "persona": f"http://{host}:{port}/health",
    }
    needles = {
        "api": ["server:app"],
        "persona": ["llama-server", f"--port {port}"],
    }
    print("=== Project_Persona status ===")
    print(f"AI_ROOT: {root}")
    print(f"OS: {platform.system()} {platform.machine()}")
    print()
    print("Processes:")
    for name in ("api", "persona", "panel"):
        pid = read_pid(root / "run" / f"{name}.pid")
        hurl = health_urls.get(name)
        up = http_health_up(hurl) if hurl else False
        if pid_alive(pid):
            if hurl and not up:
                ok(f"{name}: running (pid {pid}) -- WARN /health not responding")
            else:
                ok(f"{name}: running (pid {pid})")
        elif up:
            real = next(iter(pids_by_cmdline(needles.get(name))), None)
            if real is not None:
                warn(f"{name}: /health UP on real pid {real}; pidfile pid {pid} stale (WSL trap)")
            else:
                warn(f"{name}: /health UP but recorded pid {pid} not alive (stale pidfile)")
        elif pid is not None:
            err(f"{name}: stale pidfile (pid {pid} not alive)")
        else:
            warn(f"{name}: not running")
    print()
    print("Config:")
    model = cfg.get("PERSONA_MODEL", "<unset>")
    print(f"  host={host}  persona_port={port}  ctx={cfg.get('PERSONA_CTX', '<unset>')}")
    print(f"  model={model}")
    _hostcfg = root / "run" / ("config.%s.toml" % host_tag())
    if _hostcfg.is_file():
        print(f"  host_config={_hostcfg.name} (per-host override applied for '{host_tag()}')")
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


def egress_posture(present, provision_open):
    """Classify the host egress-baseline posture from a probe result. PURE (testable):
      present is None  -> cannot probe (e.g. nft absent)
      present is False -> no baseline loaded
      present is True  -> loaded; provision_open distinguishes the internet window.
    See docs/egress_baseline_design_20260619.md + scripts/egress_baseline.{sh,ps1}."""
    if present is None:
        return "unknown (cannot probe)"
    if not present:
        return "none (no baseline; scripted, not auto-applied)"
    return ("provision (internet window open: DNS+HTTPS)" if provision_open
            else "serve (locked: loopback + established only)")


def _probe_egress(root):
    """Read-only probe for the egress baseline -> (present, provision_open). present is
    None when it cannot be determined. NEVER changes firewall state (the baseline is
    scripted/operator-applied; doctor only reports it)."""
    try:
        if IS_WINDOWS:
            ps = ("if (Get-NetFirewallRule -Group 'PersonaEgress' "
                  "-ErrorAction SilentlyContinue) { 'present' } else { 'absent' }")
            try:
                out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                     capture_output=True, text=True, timeout=15)
            except FileNotFoundError:
                return (None, False)
            if out.returncode != 0:
                return (None, False)
            return (("present" in (out.stdout or "")), False)
        try:
            out = subprocess.run(["nft", "list", "table", "inet", "persona_egress"],
                                 capture_output=True, text=True, timeout=10)
        except FileNotFoundError:
            return (None, False)  # nftables not installed -> cannot probe
        if out.returncode != 0:
            return (False, False)  # nft present, table not loaded
        return (True, "dport 443" in (out.stdout or ""))
    except Exception:
        return (None, False)


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

    info("Accelerators")
    accels = detect_accelerators()
    build, compiled = llama_version_info(binpath)
    selected = (cfg.get("LLAMA_BACKEND") or select_backend(accels, compiled)).strip().lower()
    if not accels:
        warn("no accelerators detected (CPU-only node)")
    for a in accels:
        if a.get("usable_for_llm"):
            ok(f"tier {a['tier']} {a['vendor']} {a['device']} -> {','.join(a.get('backends', []))}")
        else:
            warn(f"tier {a['tier']} {a['vendor']} {a['device']} present but NOT used for LLM "
                 f"(needs {a.get('native_runtime', 'its own runtime')})")
    if compiled:
        ok(f"llama-server build {build or '?'} compiled backends: {','.join(compiled)}")
    else:
        warn("could not read compiled backends from llama-server --version")
    ok(f"selected backend: {selected}")
    print()

    info("Model file")
    model = cfg.get("PERSONA_MODEL", "")
    mpath = root / "models" / model
    if model and mpath.is_file():
        size_mb = mpath.stat().st_size / (1024 * 1024)
        ok(f"model present: models/{model} ({size_mb:.0f} MB)")
    else:
        warn(f"model missing: models/{model}")
    if _truthy(cfg.get("VISION_ENABLED")):
        mm = _mmproj_args(root, cfg)
        if mm:
            ok(f"vision ON: mmproj {Path(mm[1]).name} present")
        else:
            warn("VISION_ENABLED but mmproj missing/unset -> llama-server will serve text-only")
    else:
        info("vision OFF (VISION_ENABLED unset/0; mmproj loads only when enabled)")
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

    info("Egress baseline (host firewall; read-only report)")
    _eg_present, _eg_prov = _probe_egress(root)
    _eg_label = egress_posture(_eg_present, _eg_prov)
    if _eg_present:
        ok(f"egress posture: {_eg_label}")
    elif _eg_present is None:
        info(f"egress posture: {_eg_label}")
    else:
        warn(f"egress posture: {_eg_label}")
        info("apply with scripts/egress_baseline.sh (Linux) / egress_baseline.ps1 "
             "(Windows); see docs/egress_baseline_design_20260619.md")
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


BACKEND_PRIORITY = ["cuda", "rocm", "sycl", "vulkan", "opencl", "cann", "musa"]


def _which(name):
    return shutil.which(name) is not None


def _run(cmd, timeout=6):
    try:
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout, text=True, errors="replace",
        )
        return p.returncode, p.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None, ""


def detect_ram_mb():
    """Return (total_mb, available_mb). Available nets out RAM held by e.g. a
    ramdisk, so it -- not total -- reflects what a model can actually use."""
    try:
        if IS_WINDOWS:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return (int(stat.ullTotalPhys // (1024 * 1024)),
                        int(stat.ullAvailPhys // (1024 * 1024)))
        else:
            total = avail = None
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total = int(int(line.split()[1]) // 1024)
                    elif line.startswith("MemAvailable:"):
                        avail = int(int(line.split()[1]) // 1024)
            return (total, avail)
    except Exception:
        return (None, None)
    return (None, None)


def detect_vulkan_devices():
    if not _which("vulkaninfo"):
        return []
    rc, out = _run(["vulkaninfo", "--summary"])
    if rc is None:
        return []
    devices = []
    for line in out.splitlines():
        if "deviceName" in line and "=" in line:
            name = line.split("=", 1)[1].strip()
            low = name.lower()
            if "llvmpipe" in low or "software" in low:
                continue
            if "nvidia" in low:
                vendor = "nvidia"
            elif "amd" in low or "radeon" in low or "radv" in low:
                vendor = "amd"
            elif "intel" in low or "arc" in low or "xe" in low:
                vendor = "intel"
            else:
                vendor = "unknown"
            devices.append({"vendor": vendor, "device": name})
    return devices


def _classify_gpu_vendor(name):
    low = name.lower()
    if "llvmpipe" in low or "software" in low or "microsoft basic" in low or "basic display" in low:
        return None
    if "nvidia" in low:
        return "nvidia"
    if "amd" in low or "radeon" in low or "radv" in low or "ati " in low:
        return "amd"
    if "intel" in low or "arc" in low or " xe" in low:
        return "intel"
    return "unknown"


def detect_os_gpus():
    names = []
    if IS_WINDOWS:
        rc, out = _run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }"],
            timeout=15,
        )
        if rc == 0:
            names = [l.strip() for l in out.splitlines() if l.strip()]
    elif _which("lspci"):
        rc, out = _run(["lspci"])
        if rc == 0:
            for line in out.splitlines():
                if re.search(r"VGA compatible controller|3D controller|Display controller", line):
                    names.append(line.split(":", 2)[-1].strip())
    devices = []
    for n in names:
        vendor = _classify_gpu_vendor(n)
        if vendor:
            devices.append({"vendor": vendor, "device": n})
    return devices


def detect_accelerators():
    found = []
    seen_vendors = set()

    if _which("nvidia-smi"):
        rc, out = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
        names = [l.strip() for l in out.splitlines() if l.strip()] if rc == 0 else []
        for n in names or ["NVIDIA GPU"]:
            found.append({"vendor": "nvidia", "device": n, "tier": 1,
                          "backends": ["cuda", "vulkan"], "usable_for_llm": True})
            seen_vendors.add("nvidia")

    if _which("rocminfo") or _which("rocm-smi"):
        found.append({"vendor": "amd", "device": "AMD GPU (ROCm)", "tier": 1,
                      "backends": ["rocm", "vulkan"], "usable_for_llm": True})
        seen_vendors.add("amd")

    if _which("sycl-ls") or _which("xpu-smi"):
        found.append({"vendor": "intel", "device": "Intel GPU (SYCL)", "tier": 1,
                      "backends": ["sycl", "vulkan"], "usable_for_llm": True})
        seen_vendors.add("intel")

    generic = {}
    for vd in detect_vulkan_devices() + detect_os_gpus():
        generic.setdefault(vd["vendor"], vd["device"])
    for vendor, device in generic.items():
        if vendor in seen_vendors:
            continue
        found.append({"vendor": vendor, "device": device, "tier": 1,
                      "backends": ["vulkan"], "usable_for_llm": True})
        seen_vendors.add(vendor)

    if _which("npu-smi"):
        found.append({"vendor": "huawei", "device": "Ascend NPU", "tier": 1,
                      "backends": ["cann"], "usable_for_llm": True})
    if _which("mthreads-gmi"):
        found.append({"vendor": "moorethreads", "device": "MTT GPU", "tier": 1,
                      "backends": ["musa"], "usable_for_llm": True})

    accel_dir = Path("/dev/accel")
    if not IS_WINDOWS and accel_dir.is_dir() and any(accel_dir.glob("accel*")):
        found.append({"vendor": "intel", "device": "NPU", "tier": 2,
                      "native_runtime": "openvino", "usable_for_llm": False})

    if _which("hailortcli"):
        found.append({"vendor": "hailo", "device": "Hailo", "tier": 3,
                      "native_runtime": "hailort", "usable_for_llm": False})
    if _which("hl-smi"):
        found.append({"vendor": "intel", "device": "Gaudi", "tier": 3,
                      "native_runtime": "synapseai", "usable_for_llm": False})

    return found


def _vulkaninfo_max_device_local_mb():
    """Largest VK MEMORY_HEAP_DEVICE_LOCAL_BIT heap (MiB) across all GPUs, or None.
    Cross-vendor: vulkaninfo ships with the AMD/NVIDIA/Intel driver. The DEVICE_LOCAL
    heap is the card's VRAM (a RAM carve-out on integrated GPUs -- memory_model
    flags that case)."""
    if not _which("vulkaninfo"):
        return None
    rc, out = _run(["vulkaninfo"], timeout=30)
    if rc is None or not out:
        return None
    best = None
    in_heaps = False
    size = None
    for line in out.splitlines():
        if "memoryHeaps[" in line:
            in_heaps = True
            size = None
            continue
        if not in_heaps:
            continue
        if "memoryTypes" in line:          # heaps block ends
            in_heaps = False
            size = None
            continue
        m = re.search(r"size\s*=\s*(\d+)", line)
        if m:
            size = int(m.group(1))
            continue
        if "DEVICE_LOCAL" in line and size is not None:
            mb = size // (1024 * 1024)
            best = mb if best is None else max(best, mb)
            size = None
    return best


def detect_vram_mb():
    """Best-effort max dedicated VRAM (MiB) among usable GPUs, or None. Used by
    the model provisioner to size a download. On unified/integrated hosts this may
    be a RAM carve-out, not the real budget -- pair with memory_model so the
    matcher budgets against system RAM there instead of this value."""
    best = _vulkaninfo_max_device_local_mb()   # primary: cross-vendor
    if best is not None:
        return best
    # NVIDIA -- nvidia-smi, authoritative, already MiB
    if _which("nvidia-smi"):
        rc, txt = _run(["nvidia-smi", "--query-gpu=memory.total",
                        "--format=csv,noheader,nounits"])
        if rc == 0:
            vals = [int(x) for x in re.findall(r"\d+", txt or "")]
            if vals:
                best = max(vals)
    # AMD / Intel on Linux -- sysfs, bytes, no vendor tool required
    if not IS_WINDOWS:
        try:
            for p in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
                try:
                    mb = int(p.read_text().strip()) // (1024 * 1024)
                    best = mb if best is None else max(best, mb)
                except Exception:
                    pass
        except Exception:
            pass
    # Windows -- registry qwMemorySize per adapter, bytes. Reliable for >4 GB,
    # unlike Win32_VideoController.AdapterRAM (a 32-bit value that wraps).
    if IS_WINDOWS:
        rc, txt = _run(
            ["powershell", "-NoProfile", "-Command",
             "Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control"
             "\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}\\*' -Name "
             "'HardwareInformation.qwMemorySize' -EA SilentlyContinue | "
             "ForEach-Object { $_.'HardwareInformation.qwMemorySize' }"],
            timeout=15)
        if rc == 0:
            vals = [int(x) for x in re.findall(r"\d+", txt or "")]
            if vals:
                mb = max(vals) // (1024 * 1024)
                best = mb if best is None else max(best, mb)
    return best


def _vulkan_device_types():
    """deviceType strings from vulkaninfo --summary (one per GPU), lowercased."""
    if not _which("vulkaninfo"):
        return []
    rc, out = _run(["vulkaninfo", "--summary"])
    if rc is None:
        return []
    types = []
    for line in out.splitlines():
        if "deviceType" in line and "=" in line:
            types.append(line.split("=", 1)[1].strip().lower())
    return types


def detect_memory_model(accels):
    """unified | discrete | cpu. Drives whether the provisioner budgets against
    system RAM (APU/unified memory) or dedicated VRAM (discrete card)."""
    usable = [a for a in accels if a.get("usable_for_llm")]
    if not usable:
        return "cpu"
    types = _vulkan_device_types()
    if any("discrete" in t for t in types):
        return "discrete"
    if types and all(("integrated" in t or "cpu" in t or "virtual" in t) for t in types):
        return "unified"
    # Fallback heuristic on device names (integrated graphics / APUs)
    apu_hints = ("strix", "radeon graphics", "ryzen", "uhd graphics", "iris",
                 "vega ", "780m", "880m", "890m", "8060s", "integrated")
    names = " ".join((a.get("device") or "").lower() for a in usable)
    if any(h in names for h in apu_hints):
        return "unified"
    return "discrete"


def detect_camera():
    """True if a camera / video-capture input is present, False if not, None if
    undetermined. Drives the provisioner's vision default: VISION_ENABLED defaults
    on only when a camera exists (otherwise off, with opt-in)."""
    try:
        if IS_WINDOWS:
            rc, out = _run(
                ["powershell", "-NoProfile", "-Command",
                 "@(Get-CimInstance Win32_PnPEntity -EA SilentlyContinue | "
                 "Where-Object { $_.PNPClass -eq 'Camera' -or "
                 "$_.Service -eq 'usbvideo' }).Count"],
                timeout=15)
            if rc == 0:
                nums = re.findall(r"\d+", out or "")
                return bool(nums) and int(nums[-1]) > 0
            return None
        # Linux: V4L2 capture nodes
        return any(Path("/dev").glob("video*"))
    except Exception:
        return None


def _scan_backends(text):
    low = (text or "").lower()
    backends = []
    for tok, name in (("cuda", "cuda"), ("vulkan", "vulkan"), ("rocm", "rocm"),
                      ("hip", "rocm"), ("sycl", "sycl"), ("musa", "musa"),
                      ("cann", "cann"), ("opencl", "opencl")):
        if tok in low and name not in backends:
            backends.append(name)
    return backends


def llama_version_info(binpath):
    if not Path(binpath).is_file():
        return None, []
    build = None
    rc, out = _run([str(binpath), "--version"], timeout=30)
    if rc is None or not (out or "").strip():
        rc, out = _run([str(binpath), "--version"], timeout=30)
    if rc is not None:
        m = re.search(r"\bb?(\d{3,6})\b", out or "")
        if m:
            build = "b" + m.group(1)
    backends = _scan_backends(out)
    if not backends:
        rc2, out2 = _run([str(binpath), "--list-devices"], timeout=25)
        if rc2 is not None:
            backends = _scan_backends(out2)
    return build, backends


def select_backend(accels, compiled):
    available = set()
    for a in accels:
        if a.get("usable_for_llm"):
            for b in a.get("backends", []):
                available.add(b)
    candidates = [b for b in BACKEND_PRIORITY if b in available]
    if not candidates:
        return "cpu"
    if compiled:
        in_both = [b for b in candidates if b in compiled]
        return in_both[0] if in_both else "cpu"
    return candidates[0]


def detect_host(root, cfg):
    binpath = llama_binary(root)
    accels = detect_accelerators()
    build, compiled = llama_version_info(binpath)
    selected = cfg.get("LLAMA_BACKEND") or select_backend(accels, compiled)
    models = sorted(p.name for p in (root / "models").glob("*.gguf")) if (root / "models").is_dir() else []
    ram_total, ram_avail = detect_ram_mb()
    return {
        "node": platform.node() or socket.gethostname(),
        "os": "windows" if IS_WINDOWS else "linux",
        "arch": platform.machine(),
        "cpu_count": os.cpu_count(),
        "ram_mb": ram_total,
        "ram_available_mb": ram_avail,
        "vram_mb": detect_vram_mb(),
        "memory_model": detect_memory_model(accels),
        "accel_selected": selected,
        "accel_present": accels,
        "camera_present": detect_camera(),
        "llama_build": build,
        "llama_backends_compiled": compiled,
        "models": models,
        "ctx_max": cfg.get("PERSONA_CTX"),
        "embedder_backend": cfg.get("EMBED_BACKEND", "auto"),
        "endpoints": {
            "persona": f"http://{cfg.get('HOST', '127.0.0.1')}:{cfg.get('PERSONA_PORT', '8090')}",
            "api": "http://127.0.0.1:8000",
        },
    }


def cmd_capabilities(root, cfg, args):
    desc = detect_host(root, cfg)
    text = json.dumps(desc, indent=2)
    print(text)
    out = root / "run" / "node_capabilities.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    info(f"wrote {out}")
    return 0


def _filter_playbook(playbook, model_id=None, text_only=False):
    models = playbook.get("model", [])
    if model_id:
        models = [m for m in models if m.get("id") == model_id]
    if text_only:
        models = [m for m in models if not m.get("vision")]
    return {"meta": playbook.get("meta", {}), "model": models}


def _gguf_ctx_for(root, pick, cfg, pf):
    """KV-aware PERSONA_CTX from the on-disk GGUF + host budget, or None if the
    weights file is absent / not GGUF / metadata missing (caller then falls back to
    the matcher's pre-download guess). KV lives in VRAM on full GPU offload, else in
    system RAM, so the free-for-KV pool is sized from whichever the weights load into.
    --ctx-size is llama.cpp's TOTAL context (split across --parallel slots), so KV
    memory scales with ctx alone -- no per-slot multiply."""
    weights = root / "models" / (pick.get("file") or "")
    if not weights.is_file():
        return None
    meta = pf.read_gguf_meta(weights)
    if not meta:
        return None
    size_mb = pick.get("size_mb") or 0
    if pick.get("full_gpu_offload"):
        free_for_kv = max(0, (pick.get("vram_budget_mb") or 0) - size_mb)
    else:
        free_for_kv = max(0, (pick.get("budget_mb") or 0) - size_mb)
    kv_per_tok = pf.kv_bytes_per_token(
        meta, cfg.get("CACHE_TYPE_K", "q8_0"), cfg.get("CACHE_TYPE_V", "q8_0"))
    return pf.max_ctx_for_budget(
        free_for_kv, kv_per_tok,
        pick.get("min_ctx", 4096), pick.get("ctx_default", pick.get("ctx", 8192)))


def cmd_provision(root, cfg, args):
    sp = str(root / "scripts")
    if sp not in sys.path:
        sys.path.insert(0, sp)
    try:
        import provision_match as pm
        import provision_fetch as pf
    except Exception as e:
        err(f"provisioner modules unavailable: {e}")
        return 1
    playbook_path = root / "run" / "model_playbook.toml"
    if not playbook_path.is_file():
        err(f"missing model playbook: {playbook_path}")
        return 1
    try:
        playbook = pm.load_playbook(playbook_path)
    except Exception as e:
        err(f"cannot read playbook ({e}); needs Python 3.11+ for tomllib")
        return 1

    caps = detect_host(root, cfg)
    env = pm.envelope_from_caps(caps)
    pick = pm.match(env, _filter_playbook(playbook, getattr(args, "model", None),
                                          getattr(args, "text_only", False)))
    if not pick:
        suffix = f" for model '{args.model}'" if getattr(args, "model", None) else ""
        err("no compatible model fits this host" + suffix)
        info("envelope: ram=%s MiB vram=%s MiB mem=%s gpu=%s"
             % (env.get("ram_mb"), env.get("vram_mb"), env.get("memory_model"),
                env.get("has_gpu")))
        return 1

    info(pm.explain(pick))
    models_dir = root / "models"
    plan = pf.build_plan(pick, models_dir)
    print("download plan:")
    for f in plan["files"]:
        size = ("present" if f["present"]
                else (f"{f['size_mb']} MiB" if f["size_mb"] else "size?"))
        print(f"  {f['role']:<7} {f['filename']}  [{size}]")
    print(f"  total to download: {plan['download_mb']} MiB")

    existing_ctx = cfg.get("PERSONA_CTX")
    gguf_ctx = _gguf_ctx_for(root, pick, cfg, pf)   # None until the GGUF is on disk
    kv = pf.config_kv(pick, existing_ctx, gguf_ctx)
    if gguf_ctx is not None:
        info(f"ctx sized from GGUF KV footprint -> {gguf_ctx} "
             f"(model max {pick.get('ctx_default')}, floor {pick.get('min_ctx')}); "
             f"effective PERSONA_CTX={kv['PERSONA_CTX']}"
             + (f" (capped from existing {existing_ctx})"
                if existing_ctx and int(existing_ctx) > gguf_ctx else ""))
    elif existing_ctx:
        info(f"GGUF not yet on disk; provisional PERSONA_CTX={kv['PERSONA_CTX']} "
             f"(recomputed from the real GGUF after download)")
    target = pf.target_config_path(root, host_tag(), os_tag())
    print(f"config target: {target.name}  [{os_tag()}]")
    print(pf.config_block(os_tag(), kv))

    token = getattr(args, "hf_token", None) or os.environ.get("HF_TOKEN")
    gate = pf.license_gate(pick, hf_token=token)
    if not gate["allowed"]:
        err(f"license gate: {gate['reason']}")
        info("accept the model card, then re-run with --hf-token <token>")
        return 2

    if getattr(args, "dry_run", False):
        info("dry run -- nothing downloaded, config unchanged")
        return 0

    pre = pf.preflight_disk(models_dir, plan["download_mb"])
    if not pre["ok"]:
        err("disk preflight: need ~%d MiB free (size+%.0f%%), have %d MiB"
            % (pre["need_mb"], pre["margin"] * 100, pre["free_mb"]))
        return 3
    ok(f"disk preflight: {pre['free_mb']} MiB free >= {pre['need_mb']} MiB needed")

    if not getattr(args, "yes", False):
        try:
            resp = input("proceed with download? [y/N] ").strip().lower()
        except EOFError:
            resp = "n"
        if resp not in ("y", "yes"):
            info("aborted")
            return 0

    res = pf.download(plan, hf_token=token, dry_run=False)
    if not res.get("ok"):
        err(f"download failed: {res.get('error') or res.get('results')}")
        return 4
    ok("download complete")

    # Weights are now on disk -> size ctx from the real GGUF metadata (authoritative).
    post_ctx = _gguf_ctx_for(root, pick, cfg, pf)
    if post_ctx is not None and post_ctx != gguf_ctx:
        gguf_ctx = post_ctx
        kv = pf.config_kv(pick, existing_ctx, gguf_ctx)
        info(f"ctx sized from GGUF KV footprint -> {gguf_ctx}; "
             f"effective PERSONA_CTX={kv['PERSONA_CTX']}")

    if getattr(args, "write_config", False) or getattr(args, "yes", False):
        r = pf.wire_config(target, os_tag(), kv, dry_run=False)
        ok(f"wired {target.name}: {', '.join(r['changes'])}")
    else:
        info(f"config NOT modified (use --write-config or --yes). "
             f"Add under [{os_tag()}] of {target.name}:")
        print(pf.config_block(os_tag(), kv))
    info("next: python manage.py up")
    return 0


def _test_offline(root, cfg):
    pybin = find_api_python(root)
    suite = root / "tests" / "test_api_offline.py"
    if not suite.is_file():
        warn("offline suite missing: tests/test_api_offline.py")
        return 1
    return 0 if subprocess.call([str(pybin), str(suite)], cwd=str(root)) == 0 else 1


def _test_health(root, cfg):
    host = cfg.get("HOST", "127.0.0.1")
    port = cfg.get("PERSONA_PORT", "8090")
    rc = 0
    d, _ = http_get_json(f"http://{host}:{port}/health")
    if d is not None:
        ok(f"persona /health OK (:{port})")
    else:
        warn(f"persona /health FAIL (:{port})")
        rc = 1
    d, _ = http_get_json("http://127.0.0.1:8000/health")
    if d is not None:
        ok("API /health OK (:8000)")
    else:
        warn("API /health FAIL (:8000)")
        rc = 1
    return rc


def _test_smoke(root, cfg):
    d, _ = http_post_json("http://127.0.0.1:8000/agent/run", {"ping": "pong"}, timeout=30.0)
    if d is not None and "status" in d:
        ok("agent /agent/run smoke OK")
        return 0
    warn("agent /agent/run smoke FAIL (is the API up?)")
    return 1


def _test_load(root, cfg):
    pybin = find_api_python(root)
    script = root / "scripts" / "load_test_m2b.py"
    if not script.is_file():
        warn("load_test_m2b.py missing")
        return 1
    info("running sustained load test (Ctrl-C to stop)")
    return 0 if subprocess.call([str(pybin), str(script)], cwd=str(root)) == 0 else 1


TEST_PLAYBOOK = {
    "offline": ("Offline API suite (no server needed)", _test_offline),
    "health": ("Live /health for persona + API", _test_health),
    "smoke": ("Agent /agent/run smoke", _test_smoke),
    "load": ("Sustained load test (long-running)", _test_load),
}
TEST_SETS = {"quick": ["offline", "health"], "all": ["offline", "health", "smoke"]}


def cmd_test(root, cfg, args):
    which = (args.which or "quick").strip().lower()
    if which == "list":
        info("Test playbook (run one step, a set, or 'all'):")
        for name, (desc, _fn) in TEST_PLAYBOOK.items():
            print(f"  {name:9} {desc}")
        for k, v in TEST_SETS.items():
            print(f"  set {k:7} = {'+'.join(v)}")
        return 0
    if which in TEST_SETS:
        names = TEST_SETS[which]
    elif which in TEST_PLAYBOOK:
        names = [which]
    else:
        err(f"unknown test '{which}' (try: manage.py test list)")
        return 2
    rc = 0
    for name in names:
        desc, fn = TEST_PLAYBOOK[name]
        info(f"[test:{name}] {desc}")
        rc |= (fn(root, cfg) or 0)
        print()
    if rc == 0:
        ok("all tests passed")
    else:
        warn("some tests failed")
    return rc


def cmd_toggle(root, cfg, args):
    up_now = (pid_alive(read_pid(root / "run" / "persona.pid"))
              or pid_alive(read_pid(root / "run" / "api.pid")))
    if up_now:
        info("stack is UP -> stopping (toggle)")
        return cmd_down(root, cfg, args)
    info("stack is DOWN -> starting (toggle)")
    run_args = argparse.Namespace(
        no_wait=getattr(args, "no_wait", False), llama_only=False, api_only=False,
    )
    return cmd_up(root, cfg, run_args)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

PANEL_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Project_Persona control panel</title>
<style>
:root{--bg:#fff;--fg:#1a1a18;--mut:#6b6b66;--card:#fff;--bd:#e4e2da;--sec:#f4f2ec;--ok:#1d7a4d;--bad:#b3261e;--mono:ui-monospace,Menlo,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#1c1c1a;--fg:#ececec;--mut:#9a9a94;--card:#262624;--bd:#3a3a36;--sec:#222220;--ok:#4ade80;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,Segoe UI,Roboto,sans-serif;padding:20px;line-height:1.5}
.wrap{max-width:720px;margin:0 auto}.row{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:8px;font-size:13px;font-weight:500;background:var(--sec)}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;background:var(--mut)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px 16px}
.lbl{font-size:13px;color:var(--mut)}.big{font-size:20px;font-weight:500;margin:6px 0 2px}
.meta{font-family:var(--mono);font-size:12px;color:var(--mut)}
.caps{background:var(--sec);border-radius:12px;padding:14px 16px;margin-bottom:18px}
.capgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:18px}
button,select{font:inherit;font-size:14px;padding:8px 12px;border:1px solid var(--bd);border-radius:8px;background:var(--card);color:var(--fg);cursor:pointer}
button:hover{background:var(--sec)}button:disabled{opacity:.5;cursor:not-allowed}
.console{background:var(--sec);border-radius:8px;padding:12px 14px;font-family:var(--mono);font-size:12px;line-height:1.7;white-space:pre-wrap;max-height:220px;overflow:auto}
.foot{font-family:var(--mono);font-size:11px;color:var(--mut);text-align:center;margin-top:12px}
</style></head><body><div class="wrap">
<div class="row"><div><div style="font-size:18px;font-weight:500" id="title">Project_Persona - control panel</div><div class="meta" id="sub">connecting...</div></div>
<span class="pill"><span class="dot" id="stackDot"></span><span id="stackTxt">...</span></span></div>
<div class="grid">
<div class="card"><div class="row" style="margin:0"><span class="lbl">Persona - llama-server</span><span class="dot" id="pDot"></span></div><div class="big" id="pState">-</div><div class="meta" id="pMeta"></div></div>
<div class="card"><div class="row" style="margin:0"><span class="lbl">Companion API</span><span class="dot" id="aDot"></span></div><div class="big" id="aState">-</div><div class="meta" id="aMeta"></div></div>
</div>
<div class="caps"><div class="lbl" style="margin-bottom:10px">Host capabilities</div><div class="capgrid" id="caps"></div></div>
<div class="controls">
<button id="toggleBtn" onclick="act('toggle')" style="font-weight:500">Start</button>
<button onclick="act('restart')">Restart</button>
<span style="width:1px;height:22px;background:var(--bd)"></span>
<select id="test"><option>quick</option><option>offline</option><option>health</option><option>smoke</option><option>load</option><option>all</option></select>
<button onclick="act('test',document.getElementById('test').value)">Run test</button>
</div>
<div class="console" id="log">...</div>
<div class="foot">polling /api/status every 2s - manage.py panel</div>
</div>
<script>
function dot(id,good){document.getElementById(id).style.background=good?'var(--ok)':'var(--bad)'}
async function j(u,o){const r=await fetch(u,o);return r.json()}
async function loadCaps(){try{const c=await j('/api/capabilities');
document.getElementById('title').textContent='Project_Persona - '+(c.node||'node');
document.getElementById('sub').textContent=(c.os||'')+' / '+(c.arch||'')+' - manage.py panel';
const f=[['accelerator',c.accel_selected||'cpu'],['model',(c.models&&c.models[0])||'-'],['ctx / build',(c.ctx_max||'?')+' - '+(c.llama_build||'?')],['ram avail/total',(c.ram_available_mb?Math.round(c.ram_available_mb/1024):'?')+' / '+(c.ram_mb?Math.round(c.ram_mb/1024):'?')+' GB'],['cores',(c.cpu_count||'?')]];
document.getElementById('caps').innerHTML=f.map(x=>'<div><div class="meta">'+x[0]+'</div><div style="font-size:14px;margin-top:2px">'+x[1]+'</div></div>').join('')}catch(e){}}
function tile(p,d,s,m){const up=p.up&&p.health;dot(d,up);document.getElementById(s).textContent=p.up?(p.health?'Running':'Starting'):'Stopped';
document.getElementById(m).textContent=(p.pid?('pid '+p.pid):'no pid')+' - /health '+(p.health?'ok':'-')}
async function poll(){try{const s=await j('/api/status');
tile(s.persona,'pDot','pState','pMeta');tile(s.api,'aDot','aState','aMeta');
const up=(s.persona.up||s.api.up);dot('stackDot',up);
document.getElementById('toggleBtn').textContent=s.busy?'Working...':(up?'Stop':'Start');
document.getElementById('stackTxt').textContent='Stack: '+(s.busy?'working...':(up?'running':'stopped'));
document.getElementById('log').textContent=(s.log||[]).join('\n')||'(no output yet)';
document.querySelectorAll('button').forEach(b=>b.disabled=!!s.busy)}catch(e){document.getElementById('stackTxt').textContent='Stack: offline'}}
async function act(a,w){await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a,which:w||'quick'})});setTimeout(poll,300)}
loadCaps();poll();setInterval(poll,2000);
</script></body></html>"""


def cmd_panel(root, cfg, args):
    pidfile = root / "run" / "panel.pid"
    port = int(getattr(args, "port", 8765))
    url = f"http://127.0.0.1:{port}"
    if getattr(args, "stop", False):
        pid = read_pid(pidfile)
        if pid_alive(pid):
            terminate_pid(pid)
            ok(f"panel stopped (pid {pid})")
        else:
            warn("panel not running")
        try:
            pidfile.unlink()
        except OSError:
            pass
        return 0
    if getattr(args, "detach", False):
        ensure_dirs(root)
        existing = read_pid(pidfile)
        if pid_alive(existing):
            ok(f"panel already running (pid {existing}) on {url}")
            return 0
        child = [sys.executable, str(Path(__file__).resolve()), "panel", "--port", str(port), "--no-browser"]
        pid = spawn_detached(child, str(root / "logs" / "panel.log"), cwd=str(root))
        write_pid(pidfile, pid)
        ok(f"control panel detached (pid {pid}) on {url}")
        if not getattr(args, "no_browser", False):
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return 0
    caps = detect_host(root, cfg)
    state = {"busy": False, "log": collections.deque(maxlen=200)}
    lock = threading.Lock()

    def status():
        host = cfg.get("HOST", "127.0.0.1")
        pport = cfg.get("PERSONA_PORT", "8090")
        pd, _ = http_get_json(f"http://{host}:{pport}/health", timeout=1.0)
        ad, _ = http_get_json("http://127.0.0.1:8000/health", timeout=1.0)
        pp = read_pid(root / "run" / "persona.pid")
        ap = read_pid(root / "run" / "api.pid")
        return {
            "persona": {"up": pid_alive(pp), "pid": pp, "health": pd is not None},
            "api": {"up": pid_alive(ap), "pid": ap, "health": ad is not None},
            "busy": state["busy"], "log": list(state["log"])[-40:],
        }

    def run_action(action, which):
        state["busy"] = True
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                if action == "up":
                    cmd_up(root, cfg, argparse.Namespace(no_wait=False, llama_only=False, api_only=False))
                elif action == "down":
                    cmd_down(root, cfg, None)
                elif action == "toggle":
                    cmd_toggle(root, cfg, argparse.Namespace())
                elif action == "restart":
                    cmd_down(root, cfg, None)
                    cmd_up(root, cfg, argparse.Namespace(no_wait=False, llama_only=False, api_only=False))
                elif action == "test":
                    cmd_test(root, cfg, argparse.Namespace(which=which))
                else:
                    print(f"[XX] unknown action {action}")
        except Exception as e:
            buf.write(f"[XX] {e}\n")
        finally:
            for ln in buf.getvalue().splitlines():
                state["log"].append(_ANSI_RE.sub("", ln))
            state["busy"] = False

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, PANEL_HTML, "text/html; charset=utf-8")
            elif self.path == "/api/status":
                self._send(200, json.dumps(status()))
            elif self.path == "/api/capabilities":
                self._send(200, json.dumps(caps))
            else:
                self._send(404, "{}")

        def do_POST(self):
            if self.path != "/api/action":
                self._send(404, "{}")
                return
            n = int(self.headers.get("Content-Length", "0") or 0)
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                req = {}
            with lock:
                if state["busy"]:
                    self._send(409, json.dumps({"error": "busy"}))
                    return
            threading.Thread(target=run_action, args=(req.get("action"), req.get("which", "quick")), daemon=True).start()
            self._send(202, json.dumps({"accepted": True, "action": req.get("action")}))

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    write_pid(pidfile, os.getpid())
    ok(f"control panel on {url}  (Ctrl-C to stop)")
    if not getattr(args, "no_browser", False):
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        info("panel stopping")
    finally:
        httpd.shutdown()
        try:
            pidfile.unlink()
        except OSError:
            pass
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
    up.add_argument("--yes", action="store_true", help="Non-interactive: auto-provision a model on first run if none is servable.")
    up.add_argument("--hf-token", dest="hf_token", help="HF token passed to first-run provisioning (or set HF_TOKEN).")

    sub.add_parser("down", help="Stop the API then llama-server.")
    sub.add_parser("status", help="Show pidfile/process/config state.")

    doc = sub.add_parser("doctor", help="Deep health check.")
    doc.add_argument("--deep", action="store_true", help="Include a live completion smoke test.")
    doc.add_argument("--strict", action="store_true", help="Exit non-zero unless the T1 gate is fully green.")

    sub.add_parser("capabilities", help="Detect host accel/resources; write run/node_capabilities.json.")

    prov = sub.add_parser("provision", help="Profile the host, pick + download a model, opt-in wire config.")
    prov.add_argument("--yes", action="store_true", help="Non-interactive: skip the prompt AND write the config.")
    prov.add_argument("--model", help="Force a specific model id from the playbook.")
    prov.add_argument("--text-only", action="store_true", dest="text_only", help="Exclude vision models from selection.")
    prov.add_argument("--dry-run", action="store_true", dest="dry_run", help="Show pick + plan + config block; download nothing.")
    prov.add_argument("--write-config", action="store_true", dest="write_config", help="Wire the pick into config after download (implied by --yes).")
    prov.add_argument("--hf-token", dest="hf_token", help="HF token for gated/opt-in models (or set HF_TOKEN).")

    tog = sub.add_parser("toggle", help="Start the stack if down, stop it if up.")
    tog.add_argument("--no-wait", action="store_true", help="When starting, do not wait for llama /health.")

    tst = sub.add_parser("test", help="Run the test playbook (a step, a set, or 'list').")
    tst.add_argument("which", nargs="?", default="quick",
                     help="offline|health|smoke|load | quick|all | list")

    pan = sub.add_parser("panel", help="Serve the local web control panel (status + start/stop/test).")
    pan.add_argument("--port", type=int, default=8765, help="Port to bind on 127.0.0.1 (default 8765).")
    pan.add_argument("--no-browser", action="store_true", help="Do not auto-open a browser.")
    pan.add_argument("--detach", action="store_true", help="Run in the background (survives terminal close); writes run/panel.pid.")
    pan.add_argument("--stop", action="store_true", help="Stop a detached/running panel via run/panel.pid.")

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
        "capabilities": cmd_capabilities,
        "provision": cmd_provision,
        "toggle": cmd_toggle,
        "test": cmd_test,
        "panel": cmd_panel,
    }
    return handlers[args.command](root, cfg, args)


if __name__ == "__main__":
    sys.exit(main())
