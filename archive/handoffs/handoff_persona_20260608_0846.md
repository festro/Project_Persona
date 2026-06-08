# Handoff -- Project_Persona

Date/time: 2026-06-08 0846 PDT
Author: Claude
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Status of repo: working tree has UNCOMMITTED local changes (this session). Nothing
pushed -- per the push-at-milestones rule, this is mid-phase work, so LOCAL COMMIT
ONLY when committed, no push.

================================================================================
WHERE WE ARE
================================================================================

Phase 1 head item M6 (single-model migration confirmation) was already closed +
committed in the prior session (working tree was clean / up to date with
origin/main). This session cleared the next queued item: the T2.4 PAYOFF --
retiring the post-hoc persona sanitizer on the messages path. That follow-up was
the last loose end of the T2.4 --jinja messages migration.

Single change, fully scoped, OFF-by-default-safe. The proven raw /completion
default deployment is byte-identical; only the opt-in messages path
(PERSONA_USE_MESSAGES=1) changes behavior.

================================================================================
WHAT HAPPENED THIS SESSION (1 thread)
================================================================================

T2.4 PAYOFF -- retire the post-hoc sanitizer on the messages path
(changelog 2026-06-08 0846; roadmap T2.4 FOLLOW-UP closed; todo Next #2 cleared)

  WHY: T2.4 made the persona generate via /v1/chat/completions with
  chat_template_kwargs{enable_thinking}. Under --jinja + --reasoning-format
  deepseek the server returns clean, format-following `content` plus a separate
  `reasoning_content`. That was LIVE-PROVEN 2026-06-07 1746 (exit_gate_live
  [messages]). So on that path the lossy two-part `sanitize_persona_reply`
  reformatter (head paragraph + forced "Next actions:" bullets) is no longer
  needed and only risks mangling good model output.

  WHAT CHANGED (services/api/server.py):
  - NEW env flag PERSONA_SANITIZE_MESSAGES (OFF by default = sanitizer RETIRED on
    the messages path). Set =1 as an escape hatch to re-apply the sanitizer there
    if a model ignores the format contract.
  - NEW helpers:
      will_sanitize(preserve) -> bool   (single source of truth for the decision)
      finalize_persona_reply(answer, preserve) -> str
    Decision table:
      preserve_thinking set            -> never sanitize (unchanged)
      messages path (USE_MESSAGES on)  -> sanitize only if PERSONA_SANITIZE_MESSAGES
      raw /completion path             -> always sanitize (UNCHANGED)
  - /chat and /v1 both replaced the inline `answer if preserve else sanitize...`
    with `finalize_persona_reply(answer, preserve)`.
  - /health gains `persona_sanitize_messages`.
  - /chat debug gains `sanitizer_applied` (so a live POST can confirm the messages
    path skipped the sanitizer).

  TESTS (tests/test_api_offline.py): +8 checks, now 72/72.
  - messages path returns server content VERBATIM, no forced "Next actions:",
    debug sanitizer_applied=false; /v1 messages content verbatim too.
  - escape hatch (PERSONA_SANITIZE_MESSAGES=1) re-sanitizes; debug
    sanitizer_applied=true.
  - raw /completion path STILL sanitizes (locks the unchanged default).
  - /health persona_sanitize_messages present.

================================================================================
VALIDATION DONE / OWED
================================================================================

DONE:
  - off-mount (Linux sandbox, freshness-checked clean copy): py_compile OK +
    ast.parse OK on server.py; tests/test_api_offline.py -> 72/72 ALL PASS, exit 0
    (sandbox fastapi 0.136.3).
  - CANONICAL Windows-side (Brandon, portable 3.11.9): 72/72 ALL PASS. T2.4 payoff
    fully validated on the pinned chain.

LATE ADD (same session, 0856) -- offline self-test logging:
  - Brandon noted a direct `python tests\test_api_offline.py` writes nothing to logs/
    (only tests/run_logged.py emitted a log). Fixed: test_api_offline.py now tees its
    own logs/test_api_offline.log (header + footer + scan) on a direct run. stdout is
    restored before the log handle closes (else the interpreter-shutdown flush hits the
    closed tee -> ValueError + exit 120). run_logged.py sets RUN_LOGGED=1 so the
    self-test skips its own log under the wrapper (avoids the default-label path
    collision). Logging mechanism validated off-mount (direct -> log + exit 0;
    RUN_LOGGED=1 -> no self-log).
  - OWED: a Windows-side re-run AFTER these logging edits to reconfirm 72/72 + that
    logs/test_api_offline.log appears. Test LOGIC is unchanged from the green 72/72;
    only the logging wrapper code is new (proven in isolation).

NOTE on validation method: the sandbox mount served a TRUNCATED cached copy of
test_api_offline.py (cut at 13423 bytes / line 295) on the second copy attempt --
the documented "don't validate D:\Projects files from the sandbox" hazard. The real
Windows-side file is intact (verified via the authoritative read path through line
330). Canonical validation is Windows-side; the sandbox is only for isolated mechanism
checks.

NO live model needed for any of this (format/finalization + logging, not generation).
Optional live spot-check: PERSONA_USE_MESSAGES=1, served Qwen3.6, POST /chat
debug=true on a thinking topic, confirm debug.sanitizer_applied=false and the reply is
NOT reformatted into the forced two-part "Next actions:" shape.

================================================================================
COMMIT GUIDANCE
================================================================================

Mid-phase work -> LOCAL COMMIT ONLY, do NOT push (push-at-milestones rule).
Files touched this session:
  - services/api/server.py        (flag + helpers + /chat,/v1 wiring + /health + debug)
  - tests/test_api_offline.py     (+8 checks -> 72/72; + self-logging tee/header/footer)
  - tests/run_logged.py           (sets RUN_LOGGED=1 so the self-test skips its own log)
  - changelog.md                  (entries 2026-06-08 0846 + 0856)
  - roadmap.md                    (T2.4 FOLLOW-UP closed)
  - todo.md                       (stamp + Just finished + Next #2 cleared)
  - knowledge.md                  (finalize/sanitize prose + env reference + stream note)
  - archive/handoffs/handoff_persona_20260608_0846.md (this file)

Run git Windows-side (portable git at D:\Projects\Tools\PortableGit\cmd); the Linux
sandbox mount corrupts the index -- do NOT git from the sandbox.

================================================================================
NEXT (unchanged queue, see todo.md "Next (in order)" + roadmap)
================================================================================

  - EVO-X2 single-model CONVERGENCE (needs ssh/hardware; prereq: bump EVO-X2
    llama.cpp to a Qwen3.6-capable build >= b8770 BEFORE flipping config.toml).
  - MODEL PROVISIONER P3/P4 (Phase 0.5): HF downloader + license/disk preflight +
    config wiring (P3); manage.py `provision` cmd + first-run hook (P4). Re-verify
    run/model_playbook.toml repo IDs/filenames/quant sizes against real HF pages
    first.
  - Hermes H-track (H1...) is unblocked now that Phase 1 / M6 is closed.
