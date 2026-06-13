# Handoff -- Project_Persona

Date/time: 2026-06-12 2311 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Status of repo: origin/main = 70d7fb2 (EVO-X2 pushed the H1 config migration). This
handoff + the matching doc updates (changelog/roadmap/todo/knowledge) are the remaining
local edits to commit Windows-side.

================================================================================
MILESTONE: PHASE 8 HERMES -- T1 CLOSE-OUT + H1 (the H-track is live)
================================================================================

hermes-agent is installed on EVO-X2 and its config schema is validated against the
real agent. M6 (single model) had unblocked this; both the T1 close-out (install) and
H1 (config validation) are now done.

Done over SSH via relay. Hermes node = EVO-X2 (Linux); native Windows is unsupported.

================================================================================
WHAT HERMES ACTUALLY IS (corrected from the repo's sketch)
================================================================================

NousResearch/hermes-agent (github.com/NousResearch/hermes-agent, MIT, docs
hermes-agent.nousresearch.com). A full self-improving agent: terminal UI, messaging
gateway (Telegram/Discord/Slack/...), skills, memory, MCP, cron, subagents -- and its
OWN kanban board + worker dispatcher. Drives any OpenAI-compatible endpoint, so it
points at the persona's :8090/v1.

Corrections to the repo's assumptions:
- It is NOT a `pip install hermes-agent` package. Official install = `install.sh`
  (curl|bash; installs Python, Node.js, deps, edits ~/.bashrc) OR the dev/portable
  path: git clone + `uv venv --python 3.11` + `uv pip install -e ".[all,dev]"`.
  scripts/setup_native_stack.sh still does the wrong `pip install hermes-agent` --
  UPDATE IT to the uv flow below.
- Native Windows is UNSUPPORTED (WSL2 only). So the Hermes node is EVO-X2.
- Config lives at `$HERMES_HOME/config.yaml` (default `~/.hermes/`); `HERMES_HOME`
  overrides it (and scopes the gateway PID + systemd name, so multiple installs
  coexist). Pointing it at the per-profile dir is exactly the project's design.

================================================================================
T1 CLOSE-OUT -- the portable install (per Brandon's "portable + cross-compatible")
================================================================================

On EVO-X2, isolated + pinned, no global mutations:
- uv 0.11.19 installed user-local (~/.local/bin) via astral install.sh.
- Clone: ~/src/hermes-agent, pinned at commit 9b1e0d6f (record this for reproducibility).
- venv: `uv venv ~/Git/Project_Persona/env_hermes --python 3.11` (uv fetched CPython
  3.11.15).
- Install: `uv pip install --python env_hermes/bin/python -e "~/src/hermes-agent[all,dev]"`.
- Verified: `hermes --version` -> Hermes Agent v0.16.0, OpenAI SDK 2.24.0.
- node v18.19.1 + npm 9.2.0 already on the box (TUI dep covered).
- env_hermes/bin/python now exists -> manage.py's env_hermes detection is satisfied
  (T1 close-out gate).

Reproduce / rebuild: re-clone ~/src/hermes-agent (checkout 9b1e0d6f for a hard pin),
re-run the uv venv + editable install. To run: `env_hermes/bin/hermes ...` with
`HERMES_HOME` set to the target profile dir.

================================================================================
H1 -- config schema validation (PASSED)
================================================================================

Against hermes-agent v0.16.0, using the CLI (`hermes config path/show/check/migrate`):
- HERMES_HOME -> profile dir: CONFIRMED. `config path` resolved to
  persona/profiles/default/config.yaml, `env-path` to .../.env.
- model.sampling.default + thinking (temperature/top_p/top_k/min_p/presence_penalty):
  VALID -- parsed verbatim by `config show`. provider=custom, base_url=:8090/v1.
- tools.disabled (egress list): VALID + preserved (config check: no Required missing;
  the long "optional" list is just unconfigured provider API keys we don't use).
- Migrated the profile config in place: schema version 0 -> 28 (additive; model/
  sampling/tools.disabled/security all preserved). Committed + pushed from EVO-X2
  (70d7fb2, "1 file changed, 528 insertions, 23 deletions").

EGRESS POSTURE (defense in depth -- all confirmed in the migrated config):
1. tools.disabled = [web_search, web_extract, web_crawl, browser_navigate,
   browser_click, browser_screenshot].
2. egress tools are API-key-gated -- no EXA/TAVILY/FIRECRAWL/BROWSERBASE/etc. keys set,
   so those tools cannot activate.
3. terminal.backend: local.
4. browser.allow_private_urls: false  (+ coarse agent.disabled_toolsets).

================================================================================
ARCHITECTURE DECISION OWED AT H2
================================================================================

Hermes ships its OWN kanban + worker dispatcher (HERMES_KANBAN_HOME / _BOARD / _DB /
_WORKSPACES_ROOT; the dispatcher injects board scoping into worker subprocesses). The
Phase 8 plan said "Hermes pulls from OUR Task Board (services/api/taskboard.py)". H2
must decide: ride Hermes' native kanban, or bridge taskboard.py <-> Hermes kanban.
Leaning native-kanban (less custom glue), but the persona API's /jobs + taskboard.py
already exist, so a thin bridge may be cheaper than re-plumbing. Decide before building.

================================================================================
COMMIT STATE
================================================================================

PUSHED to origin/main:
  - 70d7fb2  H1: profile config.yaml migrated to schema v28 (EVO-X2).

LOCAL, to commit Windows-side (this handoff + doc updates): changelog.md (2311 entry),
roadmap.md (Phase 8 T1+H1 [x]), todo.md (stamp + just-finished + Hermes unblocked->H2),
knowledge.md (Hermes install corrected + H1 validated + egress), and this file.
On Windows: `git pull --ff-only` (gets 70d7fb2) THEN add+commit+push these docs.
EVO-X2 then `git pull` to sync.

Git: D:\ clone runs git Windows-side; EVO-X2 runs its own native git. Don't git the D:\
repo from the sandbox.

================================================================================
FOLLOW-UPS / FIX-ITS
================================================================================

- scripts/setup_native_stack.sh: replace `pip install hermes-agent` with the uv
  editable flow (clone + uv venv py3.11 + uv pip install -e). Currently misleading.
- models/archive/ not covered by .gitignore (only models/*.gguf) -- archived Instruct
  gguf shows as untracked; add models/archive/ (carried from the 06-08 handoff).
- Date note: earlier session work (T2.4, EVO-X2 convergence) is stamped 2026-06-08;
  this Hermes work resumed 2026-06-12. Same project arc, different sittings.

================================================================================
NEXT
================================================================================

- H2: resolve the kanban decision (native vs bridge), then wire Hermes to claim +
  execute a unit of work and write results back for the persona to surface.
- Alternatively, Model Provisioner P3/P4 (Phase 0.5) remains available as a
  self-contained code track.
