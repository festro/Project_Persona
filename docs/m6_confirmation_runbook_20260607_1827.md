# M6 Confirmation Runbook -- single-model migration sign-off

Prepared: 2026-06-07 1827 PDT by Claude
Target host: Windows, RX 9060 XT (16 GB), portable Python 3.11.9
Target build: Qwen3.6 (build e7bd3b3) on llama-server b9219, :8090
Run live with the stack UP. ASCII only.

## What M6 is (reframed)

The original M6 ("replace the serial in-band SCIENTIST call with asyncio.gather
parallel dispatch") is OBSOLETE -- the persona/reasoning/coder multi-server split
is retired; one llama-server serves all roles at the prompt layer (knowledge.md
"Topology"). There is no scientist call left to parallelize.

M6 is now the single-model migration SIGN-OFF: confirm the consolidated stack is
proven live, given M2b (sustained load) passed and M5 (server.py collapse) is done.
It is the last open Phase 1 item (roadmap L189) and gates the Hermes H-track
(H1-H6).

## Preconditions -- already satisfied

- M5 server.py collapse (single PERSONA_URL, no SCIENTIST_URL, thinking-mode
  toggle, concurrency cap): DONE + live-proven (Exit Gate 2026-06-07 1222/1746).
- Single-model topology: one llama-server on :8090 serving all roles (knowledge.md
  Topology).
- This session's live proofs on Qwen3.6: Exit Gate green, /chat persona + /v1
  stream + real prompt_tokens, T2.3 preserve, T2.4 messages (1746), per-profile
  Chroma (1752), Task Board /agent/run smoke (1758), offline suite 64/64.
- M2b PASSED previously -- but on EVO-X2 / Instruct-2507 / Strix Halo Vulkan, NOT
  on this Windows / Qwen3.6 / RX 9060 XT build. That re-run is the one owed piece.

## The three M6 confirmation checks

### Check A -- single-model topology (no dual-model residue)

With the stack up:

    python manage.py status

Expect exactly one llama-server (persona :8090) + the API :8000. Confirm no
scientist/reasoning/coder server and no SCIENTIST_URL in the serving config:

    findstr /I "SCIENTIST 8081 8082" run\config.toml run\llama-servers*.env

Expect: no hits. (PASS = single model, prompt-layer role switching only.)

### Check B -- all roles from one model (live)

Already green this session via exit_gate_live.py (thinking topic, persona chat,
messages path, per-profile RAG all answered by :8090). Re-affirm in one shot,
logged:

    python tests\run_logged.py --label m6_exit_gate -- python tests\exit_gate_live.py

Expect: ALL REQUIRED PASS, logs\m6_exit_gate.log scan clean (Error=0 / Traceback=0
/ truncated=0).

### Check C -- M2b sustained load on THIS build (the owed piece)

Run the sustained-load client against the live server, wrapped by the logger.
Pick a duration:

- Smoke (fast confidence, ~5 min):

      python tests\run_logged.py --label m6_loadtest_smoke -- python scripts\load_test_m2b.py --duration 300 --concurrency 4 --out logs\m2b_smoke.json

- Full M2b acceptance (recommended, 30 min):

      python tests\run_logged.py --label m6_loadtest -- python scripts\load_test_m2b.py --duration 1800 --concurrency 4 --out logs\m2b_full.json

Side-by-side monitoring while it runs (separate windows):

    REM GPU temp/util -- use your AMD tool of choice (e.g. amdgpu / HWiNFO)
    Get-Content logs\persona.log -Wait    REM PowerShell: tail the llama-server log

M2b acceptance criteria (from load_test_m2b.py docstring / DECISION 2026-05-09):

- No thermal throttling -- no throughput degradation across per-minute buckets.
- No driver hangs -- no per-request timeouts; /health stays responsive.
- No KV-cache corruption -- error rate ~0; completion lengths sane.
- Sustained throughput stable over the run.

The client exits non-zero on errors; the JSON report holds the per-minute buckets.

## On all-green -> close M6

1. roadmap.md L189: flip `- [ ] M6 ...` to `- [x] M6 single-model migration
   confirmed (M2b re-run PASS on Qwen3.6 e7bd3b3 / RX 9060 XT <date 1xxx>; topology
   single-model; M5 live-proven)`. Phase 1 then has every box checked.
2. todo.md: move M6 from "Next" to "Just finished"; new head becomes T2.4 payoff
   (retire the post-hoc sanitizer on the messages path) and the Hermes H-track
   (H1) is UNBLOCKED.
3. changelog.md: add a dated entry (HHMM PDT) with the load-test report path +
   bucket summary.
4. Commit Windows-side (portable git): the doc flips + the new logs are gitignored
   (*.log, logs/), so only roadmap/todo/changelog changes stage.
5. Prepare the milestone handoff (per workflow tenant #4/#5): Phase 1 COMPLETE,
   H-track unblocked.

## If Check C fails

- Throughput decays across buckets -> thermal/VRAM fit. Note the n_ctx=4096/slot
  observation (todo housekeeping) -- confirm run/config.toml ctx vs --parallel 4
  on 16 GB; a too-large ctx can force eviction churn under load.
- Timeouts / /health stalls -> driver or slot starvation; capture persona.log
  around the stall and drop concurrency to 2 to bisect.
- Either way: do NOT flip M6; log the failure in changelog + a fix-it in todo.
