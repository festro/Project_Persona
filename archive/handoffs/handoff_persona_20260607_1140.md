# Handoff -- Project_Persona -- 2026-06-07 1140 PDT

Author: Brandon + Claude. Branch: main. Commit at handoff: 8088ff2 (pushed to
origin/main). Frozen snapshot -- complements `todo.md` / `changelog.md` /
`roadmap.md`; does not replace them. Keep ASCII (see `WORKFLOW.md`).

## TL;DR

A checkpoint session. No new feature code on the serving path -- the work was a
cross-project documentation-standard change, the Phase 0.5 #4 IPC decision, full
Windows-side validation of the `manage.py` launcher, and two small `manage.py`
fixes (verified live). All committed + pushed as 8088ff2. Next session climbs into
Phase 1 / T2.2.

## State at handoff

- Repo clean and pushed: 8088ff2 on origin/main (festro/Project_Persona).
- Stack NOT running (last `manage.py down` was clean). Model + binaries present on
  the Windows host (Daemonic-PC, RX 9060 XT): Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf,
  llama-server build b9219 (vulkan), portable Python 3.11.9.
- Phase position: Phase 0 GREEN; Phase 0.5 IN PROGRESS (Windows leg done, Linux/
  ARM64 deferred, two design items open); Phase 1 IN PROGRESS is the next climb.

## What was done this session

1. Timestamps UTC -> Pacific (PDT). Converted every UTC-labeled timestamp across 35
   project docs (-7h, date rollback where < 0700 UTC). Preserved non-timestamp
   "UTC" strings (the `date -u` command + comment in pre-workflow HANDOFF.md; the
   filename-origin meta-note in HANDOFF_2026-05-20_0102). Collapsed dual-labeled
   stamps to their PDT value. llama_cpp vendor submodule untouched.
2. Handoff filenames -> PDT. Renamed 17 UTC-named handoffs to PDT (git detected all
   as 95-99% renames); left the 3 already-PDT ones (2026-05-16_2337, 2026-05-19_1130,
   2026-05-20_0102). Rewrote 118 cross-references in lockstep -- 0 broken links.
3. Cross-project standard. `D:\Projects\WORKFLOW.md` revised: timestamps Pacific
   (PDT/PST), units imperial (Universal rules 2 + 8). New canonical
   `D:\Projects\AGENTS.md` (agent operating notes) with a thin per-project
   `AGENTS.md` pointer; WORKFLOW FAQ + adoption steps reference it. NOTE: the two
   D:\Projects-root files are OUTSIDE this git repo (no .git there) -- saved on disk
   only; version them in whatever holds the cross-project specs.
4. Phase 0.5 #4 IPC DECIDED. NATS+JetStream is the primary control-plane bus
   (nats-server supervised as a Phase 3 daemon child, loopback, JetStream R=1) --
   groundwork for the Phase 10 mesh -- with a stdlib loopback-TCP compatibility
   fallback, both behind one EventBus interface. Unix sockets ruled out (no asyncio
   AF_UNIX on the Windows ProactorEventLoop). Cross-platform support verified
   (nats-server binaries for Win/Linux/ARM64; nats-py official client). Full
   rationale: `docs/ipc_decision.md`. roadmap Phase 0.5 #4 -> [x]; Phase 3 +
   knowledge.md "Unix socket IPC" rewritten; nats-server added to the Phase 3 child
   map.
5. Phase 0.5 Linux/ARM64 deferred. No Linux/ARM64 hardware on hand -- launcher + H3
   live passes deferred with trigger = hardware available. roadmap launcher item +
   Exit Gate annotated (phase cannot GREEN until those legs validate).
6. manage.py Windows validation (end-to-end). On Daemonic-PC under portable 3.11.9:
   AST/syntax re-check (off-mount, completeness-verified) clean; status/capabilities/
   doctor green; config.toml read; node_capabilities.json written (accel select=
   vulkan, tier1 AMD, build b9219); live up -> status -> doctor --deep (persona
   completion smoke PASS) -> test quick (offline 14/14 + health persona+API OK) ->
   down (clean). Closes the Windows-side validation caveats on launcher, TOML
   migration, capabilities/detection.
7. manage.py fixes (VERIFIED LIVE):
   - cmd_up now polls API /health (timeout 120, respects --no-wait) after start_api
     -- fixes the readiness race where doctor --deep saw API down right after up.
     Confirmed: `up` prints "API /health responding".
   - llama_version_info: `--version` timeout 10 -> 30 + one retry on empty -- fixes
     capabilities llama_build=null on a cold Vulkan --version. Confirmed:
     capabilities now reports llama_build "b9219". (Build still parsed only from
     --version, not --list-devices, to avoid matching VRAM numbers.)
8. Committed + pushed: 8088ff2 (37 files, +543/-209).

## Next (in order) -- start here next session

1. Phase 1 / T2.2: wire `enable_thinking` via `chat_template_kwargs` in
   services/api/server.py (fallback: the existing `/think`//`/no_think` prefix).
   Gate: trivial -> no <think>, non-trivial -> <think>. Best exercised with Qwen3.6
   served (confirmed working this session). Claude drafts; Brandon validates live.
   Then T2.3 (preserve_thinking for Hermes-originated requests).
2. Phase 1 Exit Gate proof (live, Brandon): a "chat" topic resolves no_think,
   science/coding/math/research resolve think (verify via /chat debug
   `sampling_preset`); live stream=true SSE + non-zero prompt_tokens; /health green
   with embedder_ok=true + chroma_ok=true.
3. Phase 0.5 remaining (open, not deferred): #5 per-OS egress story (WireGuard +
   host firewall baseline) and cross-OS installer/doctor parity -- partly design.
4. Deferred (trigger = Linux/ARM64 hardware): launcher + H3 live passes on Linux x64
   and ARM64 to flip Phase 0.5 items to [x] and let the phase go GREEN.

## Blocked / waiting

- Linux/ARM64 live validation -- no hardware. Trigger documented.
- Hermes (H1-H6) -- gated on single-model migration; confirm M6 before H1. T1
   close-out needs env_hermes installed (doctor shows env_hermes_installed=no; needs
   a networked install on a live host).

## Open fix-its (todo.md Housekeeping)

- (low) Offline suite prints a StarletteDeprecationWarning (httpx vs httpx2 in the
  FastAPI TestClient). Cosmetic; needs a dependency change -- left for later.
- The two manage.py fixes above are DONE/verified; no open manage.py fix-its remain.

## Gotchas / notes for next editor

- Environment: this repo is on Windows; the Linux sandbox mount of D:\Projects is
  NOT authoritative (stale/truncated reads) and corrupts the git index. Validate at
  the Windows source; run git Windows-side; run live checks on the Windows host. Now
  codified in `AGENTS.md` -> `D:\Projects\AGENTS.md`.
- `manage.py` cannot be reliably parsed through the mount; AST-check a completeness-
  verified off-mount copy (byte/line/tail match), or just trust the Windows-side
  Read/Edit.
- Invoke the launcher with the bundled interpreter: `portable\python\python.exe
  manage.py <cmd>`. Subcommands: up/down/toggle/status/doctor/capabilities/test/
  panel. Live stack: llama-server :8090, API :8000.
- Timestamps are Pacific (PDT/PST) now, not UTC; bare un-labeled dates inside older
  prose were intentionally NOT chased (only labeled-UTC timestamps were converted).
- capabilities `ram_available_mb` reflects live RAM at run time (was 564 MB with the
  model loaded vs ~8.6 GB idle) -- expected, not a bug.
