# WORKFLOW

See `D:\Projects\WORKFLOW.md` for the cross-project documentation conventions
this repo follows (the three-file system: `knowledge.md`, `todo.md`,
`changelog.md`, plus handoff naming and ASCII rules).

Project-local addition: `roadmap.md` is a fourth doc that owns the phased
feature/completion tracker -- the cumulative feature ladder plus per-phase test
gates that `todo.md` is too short-lived to carry. The three-file system is
otherwise unchanged; `roadmap.md` owns status, `todo.md` points at its IDs.

## Source of truth and sync (WSL primary, D:\ redundant, origin backstop)

Three roles, one synced tree (final framing 2026-06-13; full rationale in
`docs/workflow_patterns_review_20260613_2112.md`):

- `origin/main` on GitHub (git@github.com:festro/Project_Persona.git, LFS) is the
  durable OFFSITE backstop, reached via D:\ Windows-side git push.
- The WSL clone `~/Git/Project_Persona` is the PRIMARY dev/run surface -- native
  Linux, closest to the EVO-X2 target (endgame: everything on EVO-X2).
- This D:\ repo is the REDUNDANT copy + Windows multi-platform testbed + git gateway.
  It is on the D: drive (survives a Windows reinstall) and holds the only `.git`.

Two durability mechanisms, kept distinct:

1. LOCAL WSL <-> D:\ sync is FREQUENT -- this is the redundancy. Forward
   `wsl_h2_sim.ps1 -Stage sync` (D:\ -> WSL); reverse `-Stage pullback` (WSL -> D:\,
   rsync; `-Prune` for --delete; protects `.git`, `models/`, `env*`, `llama_cpp/`,
   `portable/`, runtime). Whoever changed last pushes to the other. After a WSL wipe,
   RESTORE WSL from the D:\ backup (D:\ -> WSL).
2. `git push` D:\ -> origin stays MILESTONES ONLY -- origin is the backstop if the
   D: drive itself dies, not routine redundancy. Don't push on every change.

Deferred upgrade: make the WSL clone a real git checkout of origin (needs
SSH-to-GitHub in WSL) so `git` could replace the folder sync.

## Per-host config (committed, hostname-selected)

Per-host differences (e.g., which model a host runs) live in a COMMITTED
`run/config.<host>.toml`, merged by `manage.py` AFTER `[base]/[runtime]/[<os>]`,
selected by `host_tag()` (lowercased short hostname; `PERSONA_HOST` env overrides).
The canonical `run/config.toml [linux]` is the EVO-X2 35B target; EVO-X2 needs no
file. `run/config.daemonic-pc.toml` is the CPU-WSL exception (Qwen2.5-7B). This keeps
one shared tree across all checkouts -- no clone-only patching. `manage.py status`
prints `host_config=...` when an override applies.

## WSL H2 sim operational gotchas (scripts/wsl_h2_sim.ps1)

- Windows PowerShell 5.1, not pwsh: `powershell -ExecutionPolicy Bypass -File <ABS path>`.
- `manage.py up` SKIPS a live llama-server -> after a model swap, down/kill first
  (`pkill -9 -f llama-server` if the pidfile doesn't match), then verify the served
  gguf. KNOWN BUG: `manage.py` pidfile/`pid_alive` is unreliable in WSL (reports stale
  while `/health` is up) -- the root of the stale-server trap; reliable checks are
  `/health` + the `ps ... gguf` grep.
- Hermes runs workers in an ISOLATED scratch workspace -- repo-relative file paths are
  invisible; WSL test tasks must be self-contained (or stage the file in).
- WSL diagnostics from PowerShell = one quoted call:
  `wsl -- bash -lc "ps aux | grep -E 'pat' | grep -v grep"` (not `wsl a | wsl grep ..`).
- Native commands in PowerShell: set `ErrorActionPreference=Continue` around the call
  so native stderr (e.g. curl progress) doesn't throw NativeCommandError under -Stop.
- WSL on this AMD box is CPU-only (no Vulkan GPU; ~15-20 min/agent-turn for a 7B). GPU
  lives on EVO-X2.

## Logs and session continuity (read, don't ask to paste)

Claude should read run output directly instead of asking Brandon to copy/paste
console output between turns or sessions.

- The WSL H2 orchestrator (`scripts/wsl_h2_sim.ps1`) writes a full, timestamped
  transcript of every run to `logs/wsl_h2_sim.log` in THIS repo (Windows side).
  It captures each stage, the smoke/mirror ticks, the final `/jobs` row, the
  Hermes card events, and the worker-log tail. Read it with the Read tool (the
  reliable path for D:\ files; do NOT parse D:\ files from the Linux sandbox --
  that mount serves stale/truncated reads).
- The persona stack runs in the SEPARATE WSL native-fs clone
  (`~/Git/Project_Persona`), so its live logs (`logs/persona.log` = llama-server,
  `logs/api.log`, and the Hermes worker logs under
  `run/hermes_kanban/kanban/logs/`) are NOT in this repo. To pull them onto the
  Windows side for Claude to read, run `wsl_h2_sim.ps1 -Stage logs [-JobId <id>]`;
  it tails those WSL logs into `logs/wsl_h2_sim.log`. The D:\ copies of
  `persona.log`/`api.log` (if present) are stale Windows-side artifacts -- ignore
  them; trust the `-Stage logs` surface.
- After a model swap, always confirm the served model before trusting a run:
  `manage.py up` skips starting if a llama-server is already alive, so a stale
  server keeps serving the old model. The `model` stage now tears the stack down
  after patching; otherwise verify with
  `wsl -- bash -lc "ps aux | grep -o 'models/[^ ]*\.gguf' | grep -v grep | head -1"`.
