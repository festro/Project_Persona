# Handoff -- Project_Persona  (track C: WSL sim model-swap)

Date/time: 2026-06-13 1617 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: one LOCAL edit this session (scripts/wsl_h2_sim.ps1) + doc updates.
Nothing pushed. git runs Windows-side (portable git); do NOT git or validate the
D:\ repo from the Linux sandbox. Continues from handoff_persona_20260613_1504.md.

================================================================================
WHAT THIS SESSION DID (track C -- optional WSL green)
================================================================================

Goal: let the everything-in-WSL H2 sim run a tool-calling-capable small model so
the chain can reach COMPLETION (the prior 1.5B floored at "0 tool calls" -- a model
floor, not a bridge defect). This de-risks H2d; it is NOT the H2 Exit Gate (that is
the EVO-X2 35B completing ok+summary).

Change (scripts/wsl_h2_sim.ps1 only; design unchanged):
- New params: -PersonaModel <gguf> / -PersonaCtx <n> / -PersonaParallel <n>
  / -ModelUrl <url>.
- New "model" stage, run after "sync" and before "setup" in the all-pipeline:
  1. If -PersonaModel given and models/<gguf> is absent, fetch it from -ModelUrl
     (curl -fL -C -, resumable). models/ is excluded from the sync tar, so the
     GGUF persists in the WSL clone across runs and downloads once.
  2. Patch the WSL clone's run/config.toml in place, table-aware: [linux]
     PERSONA_MODEL + (if set) PERSONA_CTX, and [base] PERSONA_PARALLEL (if set).
     [windows] and the D:\ repo config.toml are NOT touched -- the 35B stays the
     EVO-X2 target. Override is sim-only and lives in the WSL clone.
- Header log now records the model/ctx/parallel for the run.
- Default behavior unchanged when -PersonaModel is omitted (ctx/parallel guards
  skip on "0").

Why this works at the server: manage.py already starts llama-server with --jinja
+ --cont-batching (manage.py ~line 386), so tool calls are surfaced as long as the
GGUF carries a tool-aware chat template. Qwen2.5-7B-Instruct GGUFs do.

Verified off-mount: the embedded config.toml patcher round-trips a sample through
tomli -- [linux] model swapped, [base] PERSONA_PARALLEL=1, [windows] untouched,
output is valid TOML. (Patcher uses only stdlib re, so it runs on any python3, not
just 3.11+ tomllib.)

================================================================================
RECOMMENDED MODEL
================================================================================

bartowski/Qwen2.5-7B-Instruct-GGUF -> Qwen2.5-7B-Instruct-Q4_K_M.gguf
  - 4.68 GB, single file (no split-merge), Apache-2.0 (OSI-open; fits the
    model-license default -- not a gated Gemma/Llama).
  - Ships the Qwen2.5 tool-calling chat template (needed by --jinja).
  - URL (resolve, no auth):
    https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf

CAVEAT -- context: Qwen2.5-7B native context caps at 32K (128K only with YaRN rope
scaling, which we are NOT enabling). Run PERSONA_PARALLEL=1 so the whole 32K is one
KV slot for the ~22k worker prompt. The profiles stage still declares
context_length=65536 to Hermes to pass its >=64K gate; that declared value is
decoupled from the 32K llama-server actually serves and is fine as long as a single
request stays under 32K. If a prompt exceeds 32K, llama-server will error -- then
either trim the task or move to the 35B.

================================================================================
HOW TO RUN (Windows + WSL2, CPU)  -- run from the D:\ repo, Windows-side
================================================================================

Full staged run with the swap (downloads the GGUF on first run; CPU is slow on a
7B -- give ticks room):

  pwsh -File scripts\wsl_h2_sim.ps1 `
    -PersonaModel "Qwen2.5-7B-Instruct-Q4_K_M.gguf" `
    -PersonaParallel 1 -PersonaCtx 32768 `
    -ModelUrl "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf" `
    -DispatchTicks 12 -TickSleep 30

Notes:
- First run does preflight -> sync -> model (fetch+patch) -> setup -> profiles ->
  up -> smoke -> status, and leaves the stack UP.
- The big download happens once; later runs reuse models/<gguf>.
- Fetch the model only (no stack): add -Stage model.
- Re-run just the smoke after the stack is up: -Stage smoke. The stack can be torn
  down between WSL invocations, so if smoke says "API not responding", re-run
  -Stage up first.
- Tear down: -Stage down.
- GPU: add -Gpu for the Vulkan path (only if the WSL distro has a working Vulkan
  ICD); default is CPU.

SUCCESS = /jobs/sim-001 reaches status "ok" with a summary, and the worker log
shows tool calls (kanban_show / kanban_complete). That is the WSL-green milestone.

================================================================================
NEXT (pick up here)
================================================================================

1. Brandon runs the command above. Watch logs/wsl_h2_sim.log + the worker log tail
   the smoke stage prints. Expect: card created -> claimed -> worker calls tools ->
   bridge mirrors running -> ok + summary into /jobs/sim-001.
2. If it COMPLETES: WSL green is done -- record it; the remaining gap to the H2 Exit
   Gate is purely the EVO-X2 35B run (handoff 1504 section B), no bridge work left.
3. If it still floors (0 tool calls): try a slightly larger/cleaner tool-caller
   (e.g. -PersonaModel Qwen2.5-7B-Instruct-Q5_K_M.gguf, same repo) or inspect the
   worker prompt vs the served chat template. A 7B that still cannot tool-call would
   point at the template/jinja wiring, not the model size.
4. Then resume the A (Windows confirm+commit) and B (EVO-X2 Exit Gate) tracks from
   handoff_persona_20260613_1504.md.

================================================================================
OPERATING NOTES (unchanged from 1504, abbreviated)
================================================================================

- Bridge transport = Hermes PUBLIC CLI; never raw kanban.db writes.
- git: D:\ repo Windows-side only; the Linux sandbox mount serves stale/truncated
  reads -- validate off-mount by copying fresh into the sandbox-local fs.
- Push rule: milestones only. WSL-green is a de-risking milestone, not the Exit Gate.
- Docs: knowledge.md (scope) / todo.md (short-term) / changelog.md (history) /
  roadmap.md (phases). Stamps Pacific. To resume: "continue from
  handoff_persona_20260613_1617.md".
