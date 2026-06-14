# Workflow & Response Patterns -- Keep/Pass Review

Date/time: 2026-06-13 2112 PDT
Author: Claude (with Brandon)
Scope: patterns observed across the 2026-06-13 sessions (H2 bridge code + reconcile +
WSL live validation, and this session's track C: 7B model swap to WSL-green).
Purpose: triage what should become standing workflow vs. one-offs. Brandon marks the
KEEPs he approves; approved items get folded into the official WORKFLOW.md. ASCII only.

Legend: [KEEP] adopt as standing workflow   [PASS] drop / one-off / anti-pattern
Tier:  (X) = belongs in cross-project D:\Projects\WORKFLOW.md
       (P) = belongs in the project-local Project_Persona\WORKFLOW.md
Items already saved to memory are marked (mem).

================================================================================
0. SOURCE OF TRUTH & SYNC  (amendment, Brandon 2026-06-13) -- OVERRIDES BELOW
================================================================================

[KEEP] (P)(mem) Three roles, one synced tree. (Final framing after discussion.)
  - GitHub origin/main (git@github.com:festro/Project_Persona.git, LFS) is the DURABLE
    BACKSTOP -- survives everything. Reached via D:\ Windows-side git push.
  - WSL clone ~/Git/Project_Persona is the PRIMARY dev/run surface -- native Linux,
    closest to the EVO-X2 target (endgame: everything on EVO-X2). Develop + run here.
  - D:\Projects\Git\Project_Persona is the REDUNDANT copy + Windows multi-platform
    testbed + git gateway to origin. On the D: drive (survives a Windows reinstall,
    which Brandon does often) and holds the only .git, so pushes happen here.
  - Goal: keep BOTH folders synced so a WSL wipe loses nothing and the EVO-X2 port has
    no "which copy is correct" confusion.
  - SYNC is bidirectional via wsl_h2_sim.ps1: -Stage sync (D:\ -> WSL, forward) and
    -Stage pullback (WSL -> D:\, reverse rsync; -Prune for --delete). Pullback protects
    .git, models/, env*, llama_cpp/, portable/, runtime. Direction is manual -- whoever
    changed last pushes to the other. Claude edits D:\ only, so: pullback at session
    start if WSL changed; forward sync after Claude edits; pullback after WSL work.
  - TWO DURABILITY MECHANISMS, do not conflate (#15): (1) LOCAL WSL<->D:\ sync is
    FREQUENT = the redundancy; D:\ survives a Windows reinstall and RESTORES WSL after a
    wipe. (2) git push D:\ -> origin stays MILESTONES ONLY -- origin is the offsite
    backstop if the D: drive dies, not routine redundancy. Don't push on every change.
  - DEFERRED UPGRADE: make the WSL clone a real git checkout of origin (needs SSH-to-
    GitHub in WSL, not set up yet) so git could replace the folder sync.
  - EXCEPTION: large GGUFs are a reproducible cache (gitignored, re-downloadable via
    -ModelUrl); fine to live only in models/ on either side.
  - CONSEQUENCE: item #18 ("sim-only overrides isolated to the WSL clone") is REVISED
    -- host differences live in COMMITTED run/config.<host>.toml shared across all
    checkouts. See "RESOLVED: host-aware config" below.

================================================================================
A. SESSION CONTINUITY  (the "reset to zero" fix)
================================================================================

1. [KEEP] (X)(mem) Read run output directly; don't ask Brandon to paste.
   The orchestrator writes a full transcript to logs/wsl_h2_sim.log (Windows side);
   Claude reads it with the Read tool. -Stage logs surfaces the WSL-only stack/worker
   logs into that same file. Rationale: pasting console output is the single biggest
   time sink and the thing that "resets" each session.

2. [KEEP] (X) Surface un-readable state into a readable transcript.
   When state lives where Claude can't see it (WSL clone, a remote host), add a
   mechanism to push it where Claude can (the -Stage logs / -Stage caps pattern), not
   a request for a copy/paste. Generalizes #1.

3. [KEEP] (X)(mem) Record durable findings -- including NEGATIVE results -- to memory
   + changelog so they're never re-investigated. (e.g., "WSL2+AMD has no Vulkan GPU".)
   Rationale: prevents the exact "ground zero" rediscovery Brandon flagged.

4. [KEEP] (P)(mem) The three/four-doc convention + dated handoffs.
   knowledge.md (scope) / todo.md (short-term) / changelog.md (history) /
   roadmap.md (phases); handoffs named handoff_persona_YYYYMMDD_HHMM, dated, ASCII,
   downloadable; resume with "continue from <handoff>". This is working well -- the
   resume pointer is how a fresh session boots with context.

5. [KEEP] (X) At a milestone, write the handoff BEFORE ending, and bump the doc
   stamps. Don't let a session end without the next-session breadcrumb.

================================================================================
B. RESPONSE STYLE
================================================================================

6. [KEEP] (X) Concise and direct; lead with the result/answer, minimal preamble.
   Per Brandon's stated preference. Honest self-check: a few responses this session
   ran long -- tighten.

7. [PASS] Long preamble/postamble and re-explaining what was just done.
   Drop. State the outcome and the one next action.

8. [KEEP] (X) Explain the WHY behind each error/fix in one line, not just the fix.
   (NativeCommandError = PS turns native stderr into a terminating error; manage.py up
   skips a live server; Hermes scratch workspace.) Brandon acts on the reasoning, not
   just the command.

9. [KEEP] (X) Ground every diagnosis in the actual code/logs, not a guess.
   This session: read manage.py to confirm --jinja, read setup_native_stack.sh to
   explain the "hang", read persona.log to prove CPU-throughput. Assertions about
   behavior cite the file/line or the log line.

10. [KEEP] (X) Comments out of chat code blocks -- only runnable lines in the block;
    rationale goes in prose. (Brandon's standing preference; held this session.)

================================================================================
C. DECISIONS & PLANNING
================================================================================

11. [KEEP-with-discipline] (X) AskUserQuestion at GENUINE forks only.
    Used well this session (which track / environment / GPU fallback) -- each answer
    changed the next action. PASS the habit of asking when Claude can just proceed
    from context or a sensible default. Net: keep the tool, raise the bar for using it.

12. [KEEP -- Brandon, 2026-06-14] In-session TaskCreate task list (the Cowork progress
    widget) -- NOT todo.md. (todo.md is the committed project doc, KEEP per #4; this is
    the per-conversation tracker.) Brandon: keep it -- it's useful for tracking SIDE
    TANGENTS. The fix for the staleness I hit this session is to MAINTAIN it, not drop
    it: add a task whenever a tangent spawns (this session that would have been fix
    NativeCommandError -> fix stale-server -> diagnose CPU throughput -> probe GPU ->
    per-host config -> pullback), and close them as you go. It is most valuable exactly
    on multi-tangent debug sessions, where it maps what's in flight and what's owed. The
    failure mode was not updating it, not the tool.

13. [KEEP] (X) One-command-then-I-read loop.
    Give Brandon exactly ONE command, he runs it, Claude reads the resulting log and
    decides the next single command. This was the core efficiency win once adopted.

================================================================================
D. ENGINEERING / SAFETY HYGIENE
================================================================================

14. [KEEP] (X)(mem) git runs Windows-side only; never parse/validate D:\ files from
    the Linux sandbox (stale/truncated reads). Validate off-mount by copying fresh.

15. [KEEP, clarified by Brandon] (X/P)(mem) Two separate mechanisms: git push D:\ ->
    origin stays MILESTONES ONLY (commit locally as you go); the WSL<->D:\ LOCAL sync is
    frequent (the redundancy). D:\ is the backup that restores WSL after a wipe; origin
    is the offsite backstop if the D: drive dies. Do not conflate them; don't push to
    origin on every change.

16. [KEEP] (P)(mem) Model picks default to OSI-open (Apache/MIT); exclude gated/
    research-license models. (Caught Qwen2.5-3B = research license this session.)

17. [KEEP] (X) Verify RUNTIME state after a config change before trusting it.
    The stale-1.5B-server trap: config said 7B, server still served 1.5B. Always
    confirm the live process reflects the change (verify the served gguf), don't
    assume the edit took effect.

18. [KEEP, DONE] Host/runtime differences live in COMMITTED run/config.<host>.toml,
    shared across all checkouts (merged by manage.py by hostname) -- NOT an ephemeral
    clone patch. Implemented + revalidated 2026-06-13 (sim-004 ok via
    config.daemonic-pc.toml). See "RESOLVED: host-aware config".

19. [KEEP] (X) When wrapping native commands in PowerShell, account for stderr.
    Set ErrorActionPreference=Continue around native calls; quiet noisy meters.
    (curl progress aborted the run under -ErrorAction Stop.)

================================================================================
E. PROJECT_PERSONA / WSL OPERATIONAL GOTCHAS  (to codify so they stop recurring)
================================================================================
All [KEEP] (P)(mem -> consolidated):

20. The box has Windows PowerShell 5.1, not pwsh. Invoke scripts as:
    powershell -ExecutionPolicy Bypass -File <ABSOLUTE path> ...

21. manage.py up SKIPS starting if a llama-server is already alive. After any model
    swap: down/kill first (pkill -9 -f llama-server if the pidfile doesn't match),
    then verify the served model:
    wsl -- bash -lc "ps aux | grep -o 'models/[^ ]*\.gguf' | grep -v grep | head -1"
    (The -Stage model step now auto-downs after patching.)

22. Hermes runs workers in an ISOLATED scratch workspace; repo-relative file paths are
    invisible to the agent. WSL test tasks must be self-contained (or stage the file
    into the workspace). A task asking to read docs/..md self-blocks (correctly).

23. WSL diagnostics from PowerShell must be one quoted call:
    wsl -- bash -lc "ps aux | grep -E 'pat' | grep -v grep"
    NOT  wsl ps aux | wsl grep ...  (PS strips quotes; bash re-parses | as pipes).

24. CPU-only in WSL on this AMD box (~15-20 min/agent-turn for a 7B). GPU lives on
    EVO-X2. (mem: wsl-amd-no-gpu.)

================================================================================
RESOLVED: host-aware config (Option A implemented 2026-06-13 ~2200)
================================================================================

Brandon chose A. Implemented:
  - manage.py: host_tag() (lowercased short hostname; PERSONA_HOST env overrides) +
    _merge_host_overrides() merges a committed run/config.<host>.toml AFTER
    [base]/[runtime]/[<os>]. `status` now prints host_config=... when one applies.
  - run/config.daemonic-pc.toml (COMMITTED): the Windows+WSL2 box's override
    (Qwen2.5-7B, ctx 32768, PERSONA_PARALLEL=1, ngl 0). The canonical run/config.toml
    [linux] stays the EVO-X2 35B target, so EVO-X2 needs NO file (inherits 35B).
  - .gitignore: note that run/config.toml + run/config.<host>.toml are tracked source
    of truth (don't add a broad run/*.toml ignore).
  - wsl_h2_sim.ps1: the "model" stage no longer patches the clone's config.toml
    (divergence gone). It only ensures the GGUF is cached (-PersonaModel/-ModelUrl),
    reloads the stack, and prints the effective merged config. Dropped -PersonaCtx /
    -PersonaParallel (they live in the committed per-host file now).
  - Verified off-mount: daemonic-pc merges to 7B/parallel=1/ngl=0; a host with no
    override stays canonical 35B.
  ADOPTION: run -Stage sync once (carries the updated manage.py + config.daemonic-pc
    .toml into the clone), then -Stage up; confirm status shows
    host_config=config.daemonic-pc.toml and model=Qwen2.5-7B.

================================================================================
PROPOSED ADOPTION
================================================================================

If you approve, I will:
  - Fold the (X) KEEPs into D:\Projects\WORKFLOW.md (cross-project).
  - Fold the (P) KEEPs, especially section E, into Project_Persona\WORKFLOW.md.
  - Leave memory as updated this session (entries noted (mem) already persist).
Tell me which numbers to PASS that I marked KEEP, or vice versa, and I'll adjust
before writing into the official files.
