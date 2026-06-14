# Handoff -- Project_Persona  (SESSION CLOSE)

Date/time: 2026-06-12 2339 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Repo state: origin/main = 0cb85bf. Windows clone, EVO-X2 clone, and origin are ALL in
sync at 0cb85bf. Working trees clean (modulo gitignored runtime/build/venv dirs).
Per-milestone detail lives in the three handoffs this session produced (0846, 1029,
2311) + the changelog; this is the consolidating session-close snapshot.

================================================================================
SESSION ARC (three milestones, all committed + pushed)
================================================================================

1. T2.4 PAYOFF (changelog 2026-06-08 0846/0856; handoff 0846; commit ccd4991)
   - Retired the lossy post-hoc persona sanitizer on the messages path. New
     PERSONA_SANITIZE_MESSAGES flag (OFF = retired; escape hatch to re-enable);
     will_sanitize()/finalize_persona_reply() helpers; /chat + /v1 route through them;
     /health + /chat-debug expose the state. Raw /completion path UNCHANGED.
   - tests/test_api_offline.py: +8 checks -> 72/72; the suite now self-logs to
     logs/test_api_offline.log on a direct run (run_logged.py sets RUN_LOGGED=1 to
     avoid double-logging). Validated Windows-side on portable 3.11.9: 72/72.

2. EVO-X2 SINGLE-MODEL CONVERGENCE / M6 (changelog 06-08 1029; handoff 1029; config
   commit from EVO-X2)
   - EVO-X2 (Strix Halo) now runs the single model Qwen3.6-35B-A3B-UD-Q5_K_XL, same as
     Windows -> "single model everywhere" directive complete; M6 closed.
   - Built llama.cpp b9219 from source for Vulkan (NEW dep: spirv-headers), symlinked
     llama_cpp/build, swapped config.toml [linux] -> Qwen3.6, refreshed the native
     venv, archived Instruct-2507. Validated end to end incl. reasoning_content via the
     messages path. Full repo sync M5-era -> latest first.

3. PHASE 8 HERMES -- T1 close-out + H1 (changelog 06-12 2311; handoff 2311; config
   commit 70d7fb2 + docs 0cb85bf)
   - hermes-agent v0.16.0 (NousResearch, MIT) installed on EVO-X2, isolated/portable:
     uv + CPython 3.11.15 + pinned editable clone (~/src/hermes-agent @ 9b1e0d6f) in
     env_hermes/. H1 validated against the real agent: HERMES_HOME -> profile dir;
     model.sampling.* + tools.disabled valid; config migrated 0 -> 28 (safe-config
     preserved). Egress off via 4 layers (disabled list + API-key-gating + local
     terminal + no private URLs).

================================================================================
CURRENT LIVE STATE
================================================================================

- EVO-X2: stack UP steady-state -- Qwen3.6 on llama-server (b9219 Vulkan, :8090) + the
  companion API (:8000), default mode (PERSONA_USE_MESSAGES off). RAG live (fastembed +
  chroma). hermes-agent installed in env_hermes/ but NOT yet wired into the stack.
- Windows (Daemonic-PC): Qwen3.6 via prebuilt b9219 Vulkan zip; portable 3.11.9 services
  env. Offline suite 72/72.
- Single model on every host. M6 + Phase 1 closed; Phase 8 H-track open at H2.

================================================================================
NEXT (pick up here)
================================================================================

PRIMARY -- H2 (Phase 8). Opens with a DECISION, not code: Hermes ships its OWN kanban +
worker dispatcher (HERMES_KANBAN_HOME/BOARD/DB/WORKSPACES_ROOT). The old plan said
"Hermes pulls from OUR taskboard.py". Decide: ride Hermes' native kanban, or bridge
taskboard.py <-> Hermes kanban. THEN wire Hermes to claim + execute a unit of work and
write results back for the persona to surface. (Leaning native-kanban; the persona
/jobs + taskboard.py already exist, so weigh a thin bridge vs re-plumbing.)

ALTERNATIVE -- Model Provisioner P3/P4 (Phase 0.5), a self-contained code track: P3 =
huggingface_hub downloader + license/disk preflight + write pick to config.toml; P4 =
manage.py `provision` + first-run hook. Re-verify run/model_playbook.toml repo IDs/
filenames/quant sizes vs live HF pages first.

================================================================================
CARRIED FIX-ITS (none blocking)
================================================================================

- scripts/setup_native_stack.sh still does `pip install hermes-agent` (wrong). Replace
  with the uv editable flow (clone + uv venv --python 3.11 + uv pip install -e).
- .gitignore: add models/archive/ (only models/*.gguf is ignored, so the archived
  Instruct gguf on EVO-X2 shows as untracked).
- EVO-X2 llama-server --version reads "1" (shallow-clone cosmetic; it's really b9219).
  Re-clone full depth or pass -DLLAMA_BUILD_NUMBER=9219 if mesh metadata needs it.
- Thinking on the messages path needs PERSONA_MAX_TOKENS >= ~4096 (192 default starves
  the answer). Raw default path unaffected.
- Raw /completion path occasionally returns an empty reply -> sanitizer placeholder
  (intermittent variance; watch).

================================================================================
OPERATING NOTES
================================================================================

- Git: D:\ Windows clone runs git Windows-side (portable git); EVO-X2 runs its own
  native git; do NOT git the D:\ repo from the sandbox (it corrupts the index / serves
  stale reads).
- EVO-X2 is headless -> all work over SSH (relay; no SSH MCP connector exists).
- Docs convention: knowledge.md (scope) / todo.md (short-term) / changelog.md (history)
  / roadmap.md (phases). Stamps in Pacific time. Push at milestones.
- Three machines synced at 0cb85bf. To resume: "continue from
  handoff_persona_20260612_2339.md".
