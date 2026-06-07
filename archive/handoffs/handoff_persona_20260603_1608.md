# Handoff -- Project_Persona

Date: 2026-06-03 1608 PDT
Author: Brandon + Claude
Prev handoff: handoff_persona_20260603_1420.md
Living docs: knowledge.md (scope/arch), todo.md (current state), changelog.md (history)

This is a frozen point-in-time record. For the authoritative current state always
read todo.md and changelog.md -- they are updated past this snapshot.

---

## 1. Session summary

Three things landed this session:

1. Fixed AI_ROOT drift in two ops scripts (Next #1 from the prior handoff).
2. Corrected an overstated "T0 PASSED" claim in the docs, then actually closed
   the gate: ran T0.2 (Qwen3.6 tool-calling) and it PASSED.
3. Wrote a reusable T0.2 test procedure + payload and patched the Windows
   launcher to support tool calls.

Net effect: the Qwen3.6 swap path is now fully unblocked. The open decision
(swap to Qwen3.6 vs. keep hardening Instruct-2507) is now a pure priority call
with no remaining gate.

---

## 2. Current state

Stack (EVO-X2, production): UP and healthy as of 2026-06-03 1418 PDT. Unified
Qwen3-30B-A3B-Instruct-2507 Q5_K_M on :8090, companion API on :8000, all health
checks green. This is the validated production model. No Qwen3.6 on EVO-X2.

Qwen3.6 prototype (Windows daily-driver): Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
(26.6 GB) runs under llama.cpp build b9219, Vulkan on an RX 9060 XT (16 GB),
35 GPU layers, ~14 t/s. Experimental only, no production role.

Gate status: T0 FULLY PASSED.
- T0.1 (loads + generates coherent output) -- passed 2026-05-18.
- T0.2 (tool-calling round-trip) -- passed 2026-06-03 this session.

---

## 3. Issues encountered and fixes

AI_ROOT drift. `scripts/stop_llama_servers.sh` and `scripts/clean.sh` defaulted
AI_ROOT to the legacy `$HOME/Live/AIStack/Project_Persona` while
`start_llama_servers.sh` used `$HOME/Git/Project_Persona`. Run without AI_ROOT
exported, the stop/clean scripts targeted the wrong workspace.
FIX: flipped both defaults to `$HOME/Git/Project_Persona`. All start/stop/clean
scripts now agree.

Overstated gate status. The 0439 reconciliation said "T0 PASSED" when only T0.1
had run. T0.2 (the sub-gate that actually unblocks Hermes Phase 8) had never been
executed.
FIX: split the claim in todo.md, then ran T0.2 to close it for real.

Tool-call template not active. The Windows launcher did not pass `--jinja`, so
llama.cpp would not apply the Hermes 2 Pro template's tool-call grammar; a tool
call would have surfaced as plain text instead of a `tool_calls` field.
FIX: added `--jinja` to `scripts/start_llama_server_win.sh`.

PowerShell routed `bash` to WSL. `bash scripts/...` from PowerShell invoked
`C:\Windows\System32\bash.exe` (WSL), not Git Bash.
FIX (workaround): call PortableGit bash explicitly --
`& "D:\Projects\Tools\PortableGit\bin\bash.exe" scripts/...` -- or run inside a
Git Bash terminal.

Launcher does not keep the server alive. Invoked as `bash.exe scripts/...` from
PowerShell, the backgrounded llama-server was torn down when the launching shell
exited (observed: server died mid-generation, task cancelled, empty curl body).
WORKAROUND: ran llama-server foreground in a dedicated window for the test.
OPEN: needs a real detach (nohup/disown equivalent) or a Windows service wrapper
if the Windows path ever becomes first-class. Logged in todo.md Notes.

---

## 4. Notable findings

`<think>` stripping may be cheaper than planned. Under `--jinja`, llama.cpp
returns reasoning in a separate `reasoning_content` field and leaves `content`
empty/clean. The user-facing channel is therefore already `<think>`-free
server-side. This de-risks T2.4 (`<think>` stripping at the persona boundary) on
the swap path -- re-scope whether a persona-side chokepoint is still needed
before building it.

T0.2 passing payload (for reference / regression): see
`scripts/t0_2_payload.json`. Response had `finish_reason=tool_calls`,
`tool_calls[0].function` = get_current_weather, `arguments={"city":"Tokyo"}`.

---

## 5. Checklist -- next actions (in priority order)

[ ] 1. DECISION: Qwen3.6 swap vs. harden Instruct-2507. No gate remains; this is
       a priority call. Record it as a dated decision in changelog.md.
       - Path A (swap): start at T1 (env_hermes venv + per-profile config.yaml
         template), then T2 (sampling presets, enable_thinking wiring,
         preserve_thinking, T2.4 re-scoped per finding above), then T3 (doctor.sh
         / unified_test.sh / retire ASYNC_REASONING_ENABLED).
       - Path B (harden): M6 (asyncio.gather parallel dispatch), then Hermes H1
         pre-flight (egress containment verification, no code).
[ ] 2. API gaps (from the 0439 code read of services/api/server.py): implement
       streaming in /v1/chat/completions or stop advertising `stream`; re-enable
       or remove /chat_submit; make /agent/run non-blocking (run_in_executor) or
       fold into the Task Board; fix hardcoded `usage.prompt_tokens: 0`.
[ ] 3. Housekeeping fix-its: load_test_m2b.py DEFAULT_ENDPOINT 8080 -> 8090;
       start_api.sh cosmetic SCIENTIST_* banner; min-1 bucket race in
       bucketize_by_minute.
[ ] 4. (If Windows goes first-class) real detach / service wrapper for
       start_llama_server_win.sh.

Blocked / waiting:
- Hermes H1-H6: gated on single-model migration; confirm M6 before H1.
- T4 deferred/opt-in (dual-memory unification, vision, MTP / speculative
  decoding): each has a documented trigger; none active.

---

## 6. Uncommitted changes (commit Windows-side, portable git)

git on D:\Projects repos must run Windows-side (the Linux sandbox mount corrupts
the index). Files changed/added this session:

```
scripts/stop_llama_servers.sh
scripts/clean.sh
scripts/start_llama_server_win.sh
scripts/t0_2_tool_calling_test.md
scripts/t0_2_payload.json
todo.md
changelog.md
archive/handoffs/handoff_persona_20260603_1608.md
```

If the executable bit is lost on the Linux target for the edited shell scripts:

```
chmod +x scripts/stop_llama_servers.sh scripts/clean.sh scripts/start_llama_server_win.sh
```

---

## 7. How to resume

1. Read todo.md (current state) and the changelog.md 2305 and 2308 entries.
2. Make the Next #1 decision (swap vs. harden) and log it dated.
3. To re-run T0.2 at any time: follow scripts/t0_2_tool_calling_test.md. Launch
   the Windows server foreground in its own window (see issue in section 3), not
   via the backgrounding launcher from PowerShell.
