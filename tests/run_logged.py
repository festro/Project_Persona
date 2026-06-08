"""Run a Project_Persona test script and capture a full low-level log.

Usage:
    python tests/run_logged.py [--label NAME] <target.py> [target args...]

Runs <target.py> with the SAME interpreter that launched this wrapper
(so the portable python is preserved), tees the child's merged
stdout+stderr to the console in real time, and writes a timestamped log
to <repo>/logs/<label>.log (overwritten each run; latest only). Output is
captured in true chronological order (stderr folded into stdout), as-is,
with no warning filtering changed.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(REPO_ROOT, "logs")

FLAG_KEYS = [
    "PERSONA_USE_MESSAGES",
    "RAG_PER_PROFILE",
    "RAG_ENABLED",
    "TOPIC_ROUTING",
    "THINKING_AUTO_GATE",
    "PRESERVE_THINKING_DEFAULT",
    "EMBED_BACKEND",
    "PERSONA_PORT",
    "API_PORT",
]


def pacific_now():
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Los_Angeles")), "PT"
    except Exception:
        return datetime.now().astimezone(), "local"


def stamp(dt, tzlabel):
    name = dt.tzname() or tzlabel
    if " " in name:
        name = "".join(w[0] for w in name.split())
    return dt.strftime("%Y-%m-%d %H%M ") + name


def git_info():
    def run(args):
        try:
            out = subprocess.run(
                args,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return out.stdout.strip()
        except Exception:
            return ""

    head = run(["git", "rev-parse", "--short", "HEAD"]) or "unknown"
    dirty = "dirty" if run(["git", "status", "--porcelain"]) else "clean"
    return head, dirty


def parse_args(argv):
    label = None
    rest = list(argv)
    if rest and rest[0] == "--label":
        if len(rest) < 2:
            sys.exit("run_logged: --label needs a value")
        label = rest[1]
        rest = rest[2:]
    if not rest:
        sys.exit(__doc__)
    target = rest[0]
    target_args = rest[1:]
    if label is None:
        label = os.path.splitext(os.path.basename(target))[0]
    return label, target, target_args


def main():
    label, target, target_args = parse_args(sys.argv[1:])

    if not os.path.isabs(target):
        target_abs = os.path.join(REPO_ROOT, target)
    else:
        target_abs = target
    if not os.path.exists(target_abs):
        sys.exit("run_logged: target not found: " + target_abs)

    os.makedirs(LOG_DIR, exist_ok=True)
    start, tzlabel = pacific_now()
    log_name = "{}.log".format(label)
    log_path = os.path.join(LOG_DIR, log_name)

    head, dirty = git_info()
    cmd = [sys.executable, target_abs] + list(target_args)

    flags = []
    for k in FLAG_KEYS:
        if k in os.environ:
            flags.append("{}={}".format(k, os.environ[k]))
    flags_line = " ".join(flags) if flags else "(none set)"

    header = [
        "=" * 72,
        "Project_Persona test log",
        "label       : " + label,
        "started     : " + stamp(start, tzlabel),
        "command     : " + " ".join(cmd),
        "cwd         : " + REPO_ROOT,
        "python      : " + sys.version.split()[0] + "  (" + sys.executable + ")",
        "platform    : " + sys.platform,
        "git HEAD    : " + head + " (" + dirty + ")",
        "env flags   : " + flags_line,
        "=" * 72,
        "",
    ]

    child_env = dict(os.environ)
    child_env["PYTHONUNBUFFERED"] = "1"

    counts = {"PASS": 0, "FAIL": 0, "Traceback": 0, "Warning": 0, "Error": 0}

    with open(log_path, "w", encoding="utf-8", newline="\n") as log:
        for line in header:
            print(line)
            log.write(line + "\n")
        log.flush()

        proc = subprocess.Popen(
            cmd,
            cwd=REPO_ROOT,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            for key in counts:
                if key in line:
                    counts[key] += 1
        proc.wait()

        end, tzlabel2 = pacific_now()
        duration = (end - start).total_seconds()
        footer = [
            "",
            "=" * 72,
            "finished    : " + stamp(end, tzlabel2),
            "duration    : {:.1f}s".format(duration),
            "exit code   : " + str(proc.returncode),
            "scan        : PASS={PASS} FAIL={FAIL} Error={Error} "
            "Traceback={Traceback} Warning={Warning}".format(**counts),
            "log file    : " + log_path,
            "=" * 72,
        ]
        for line in footer:
            print(line)
            log.write(line + "\n")

    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
