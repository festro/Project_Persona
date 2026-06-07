# Handoff -- Project_Persona -- manage.py cross-platform launcher (Phase 0.5 #1)

Date: 2026-06-06 1138 PDT
Authors: Brandon + Claude
Scope: everything after handoff_persona_20260605_1753 (roadmap + mesh design +
portability audit + the sys.executable fix). This session built the first
Phase 0.5 deliverable: the cross-platform `manage.py` lifecycle launcher.
Status: launcher written and offline-validated; docs updated. Nothing committed
yet (git runs Windows-side -- see Section 6).
Next: live-host test `manage.py up/down`, then Phase 0.5 #2 (dependency tiers).

---

## 1. What this session produced

New file:
- `manage.py` (repo root, 702 lines, pure standard library, Python 3.8+) -- one
  cross-platform entrypoint that retires the bash-only core lifecycle. Subcommands:
  - `up`    -- start llama-server, optionally wait for /health, then start the API.
              Flags: `--no-wait`, `--llama-only`, `--api-only`.
  - `down`  -- stop the API then llama-server (and any legacy pidfiles).
  - `status`-- pidfile/process/config/model summary.
  - `doctor`-- filesystem + interpreter/binary + model + profile + live-health
              checks, plus the safe-config T1-gate check. Flags: `--deep` (live
              completion smoke test), `--strict` (non-zero exit unless T1 green).
  - Global: `--root` / `AI_ROOT` env override.

Docs updated (no duplication; each file in its lane):
- `roadmap.md` -- Phase 0.5 launcher item flipped `[ ]` -> `[~]` with status note;
  stamp bumped.
- `changelog.md` -- new top entry `2026-06-06 1138 PDT`.
- `todo.md` -- new "Just finished" block; Phase 0.5 priority note updated to point
  past the launcher; stamp bumped.
- `knowledge.md` -- `manage.py` added to the repo map; `scripts/` line notes it
  supersedes the start/stop/status/doctor scripts.

## 2. Design decisions (how it maps to the old scripts)

- Sources `run/llama-servers.env` then `run/config.env` via a built-in dotenv
  parser (handles `export `, quotes, comments) -- no shell sourcing, so no bash.
- Process model is the cross-platform crux:
  - Spawn detached: Windows `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`; POSIX
    `start_new_session=True`. This is the intended fix for the known Windows gotcha
    where `bash.exe scripts/start_llama_server_win.sh` tore the server down on shell
    exit (manage.py owns the detach instead of relying on bash job control).
  - Liveness: Windows uses `OpenProcess` + `GetExitCodeProcess` via ctypes --
    deliberately NOT `os.kill(pid, 0)`, which on Windows CPython calls
    TerminateProcess (would kill the process it is checking). POSIX uses
    `os.kill(pid, 0)`.
  - Stop: Windows `taskkill /PID <pid> /T` then `/T /F`; POSIX SIGTERM then SIGKILL
    after an 8s grace window.
- Per-OS resolution: llama binary = `llama_cpp/windows/llama-server.exe` (Win,
  `--device Vulkan0` + `GGML_VK_VISIBLE_DEVICES=0`) vs `llama_cpp/build/bin/llama-server`
  (Linux, honors `LLAMA_LIB_DIR` -> `LD_LIBRARY_PATH`). API interpreter =
  `portable/python/python.exe` or `env/Scripts` (Win) vs `env/bin/python` (Linux),
  falling back to the running interpreter. Overrides: `LLAMA_BIN`, `AI_ROOT`.
- llama-server launch args mirror `start_llama_server_win.sh` exactly (ctx, threads
  with nproc->os.cpu_count() fallback, batch/ubatch, q8_0 KV, n-gpu-layers,
  parallel, --cont-batching, --jinja). API launch = `python -m uvicorn server:app
  --app-dir services/api --host 127.0.0.1 --port 8000` with the full env block from
  `start_api.sh` (RAG_ENABLED, writeback, jobs persistence, sampling/thinking vars,
  ANONYMIZED_TELEMETRY, etc.).
- Safe-config T1 gate reimplemented natively: a PyYAML path mirroring the doctor.sh
  embedded Python check, plus a regex fallback for hosts without PyYAML (doctor.sh
  had a grep fallback). The T1 GATE line reports
  `env_hermes_installed` + `safe_config`, same as doctor.sh.

## 3. Validation done (and its limits)

Done in the Linux sandbox against the live repo:
- `python3 -c "ast.parse(...)"` -- parses clean.
- `manage.py --help`, `up --help` -- argparse wiring correct.
- `manage.py --root <repo> status` -- correct config/model/endpoint read-out with
  services down.
- `manage.py --root <repo> doctor` -- all filesystem/profile checks correct;
  safe-config PASS; T1 GATE line correct.
- Both safe-config paths (PyYAML and regex) return `(True, [])` on the default
  profile -- agrees with doctor.sh's PASS.
- Install integrity: md5 of repo copy == source copy (an earlier `cp` truncated the
  file at 673 lines and silently produced a no-op binary with no `main()`; re-copied
  and md5-verified at 702 lines -- watch for this if editing via the sandbox mount).

NOT yet done (needs a live host; cannot run in the sandbox -- no model, no
llama-server, no Windows):
- `manage.py up` actually starting llama-server + API and the /health wait loop.
- `manage.py down` actually killing them (taskkill path is Windows-only, untested).
- The Windows detached-spawn surviving a parent PowerShell exit (the whole point of
  the launcher) -- must be confirmed on the Windows portable host.

## 4. Checklist / roadmap

Phase 0.5 (cross-OS/arch portability hardening) -- in progress:
- [x] /agent/run uses sys.executable (prior session)
- [~] manage.py up/down/status/doctor -- WRITTEN + offline-validated this session.
      To reach [x]: live-host pass on Windows (Vulkan) AND Linux:
      1. `python manage.py up` -> llama-server on :8090 + API on :8000, /health green
      2. `python manage.py status` shows both running
      3. `python manage.py doctor --deep` -> persona completion OK, T1 gate as expected
      4. `python manage.py down` stops both cleanly, no orphan processes/pidfiles
      5. Confirm the server survives closing the launching shell (Windows)
- [ ] Dependency tiers: lean node = fastembed/onnxruntime default; torch +
      sentence-transformers opt-in extra (Phase 0.5 #2)
- [ ] llama.cpp build/acquire matrix per accel + capability-advertising hook
- [ ] Cross-platform IPC decision (loopback TCP / NATS, not Unix socket)
- [ ] Per-OS egress story (WireGuard + host firewall baseline)
- [ ] Cross-OS installer/doctor parity

Still open from before (Phase 1): stand up the Qwen3.6 llama-server on :8090
(Windows portable; `--jinja`; run FOREGROUND in a dedicated window -- or now via
`manage.py up --llama-only` once that path is host-verified), then exercise live
/chat + /v1 streaming + per-topic sampling.

## 5. Known issues / watch items

- Sandbox mount can truncate files on copy without erroring (hit once this session;
  caught by md5). Verify line count / hash after any mount-side `cp` or write.
- manage.py `up`/`down` are unproven on a real OS; treat the first run as a test,
  not a deploy. The bash scripts remain in `scripts/` as the fallback and are not
  removed.
- `find_api_python` falls back to the running interpreter if no env/portable python
  is found, so `doctor` can report an "API python" that lacks uvicorn -- that is a
  fallback convenience, not a guarantee the API will start.
- Windows liveness/stop uses ctypes + taskkill; if a host restricts taskkill,
  `down` will fall through to the force path.

## 6. Commit guidance (git runs Windows-side)

Per project convention, git on D:\Projects repos runs with portable git on Windows
(`D:\Projects\Tools\PortableGit\cmd`); the Linux sandbox mount corrupts the index.
Nothing this session is committed. Recommended: snapshot the prior WIP first, then
this session. Exact commands are in the session chat (Section "Commit commands").
New/changed paths this session: `manage.py` (new), `knowledge.md`, `roadmap.md`,
`changelog.md`, `todo.md`, and this handoff.
