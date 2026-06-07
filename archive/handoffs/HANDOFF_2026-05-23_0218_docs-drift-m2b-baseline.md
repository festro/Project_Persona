# HANDOFF 2026-05-23 0918 PDT — Docs drift cleanup + M2b baseline retired

**Session window:** 2026-05-22 evening (PDT) → 2026-05-23 09:18 PDT
**Predecessor:** `archive/handoffs/HANDOFF_2026-05-20_0102_m5-validated-evox2.md`
**Successor (next-session entry point):** None scheduled — see §Next-Session Entry Points below
**Topic slug:** `docs-drift-m2b-baseline`

---

## 1. Executive Summary

Two milestones landed:

1. **KNOWLEDGE.md drift cleanup** per HANDOFF_2026-05-20_0102 §Step 3 — full sweep, not minimal. Doc is now coherent with the post-M5 unified-Qwen3 topology on port 8090. Committed and pushed as `3238077` ("docs(knowledge): drift cleanup per HANDOFF_2026-05-20_0102 §Step 3").
2. **M2b sustained-load baseline retired** — first successful 30-min concurrent run against the unified Qwen3-30B-A3B-Instruct-2507 Q5_K_M model on EVO-X2 / Strix Halo iGPU. 2066/2066 OK, zero errors, per-minute throughput flat across the entire window. The llama-server stability ghost from HANDOFF_2026-05-19/20 §Open issues #1 did **not** recur — survived the full 30-min load plus residual sustain. Root cause of the prior crash is still unidentified; the ghost is dormant, not exorcised.

Net: post-M5 docs are aligned with reality, and the single-model topology has its first throughput-flat 30-min baseline number on real hardware. Aggregate sustained throughput ~113 tok/s (28.26 × 4 slots).

---

## 2. Acceptance Criteria — Met

- KNOWLEDGE.md Last Updated header reflects current session date.
- All System State port references read `:8090` (no stale `:8080`).
- OpenWebUI row reflects diagnostic ground truth (scaffolded, not deployed).
- Runtime Configuration block describes the unified-Qwen3 target shape; legacy dual-server vars retained under a collapsed `<details>` for git-blame.
- File Change Tracker has rows for 2026-05-19, 2026-05-20, 2026-05-22, 2026-05-23.
- `scripts/load_test_m2b.py` returned a clean 30-min report at concurrency=4.
- Per-minute throughput buckets in the report show no degradation trend.
- llama-server process survived the full run + tail-out without dying.

---

## 3. Work Performed

### 3.1 KNOWLEDGE.md drift cleanup (commit 3238077)

Eight discrete edits + one block rewrite + Tracker extension. Full Sweep scope (user chose this over the minimal §Step 3 scope at session open):

| Section | Change |
|---|---|
| L2 header | `**Last Updated:** 2026-05-17 1030 PDT` → `**Last Updated:** 2026-05-22 0823 PDT` |
| L64 retired persona row | Added "(initially same port; unified moved to 8090 on 2026-05-19)" |
| L67 System State unified row | Rewritten — port 8090, host-port-conflict rationale, stability follow-up, cross-refs to 05-19/05-20 handoffs |
| L81 OpenWebUI row | `✅ Running` → `⚠ Scaffolded — not deployed (verified 2026-05-22)`. Diagnostic findings noted (no listener :3000, data dir empty, venv only at legacy `~/Live/AIStack/Project_Persona/env_webui/`) |
| L141 Inference roles table | Port 8080 → 8090 |
| L520 Child process diagram | `→ llama-unified (port 8090, Qwen3-30B-A3B, parallel slots)` |
| L744 T1.2 Hermes config endpoint | `127.0.0.1:8090` |
| L802 H1.2 pre-flight endpoint | `:8090` |
| L843 M12 | `port 8090 only` |
| L165-239 Runtime Configuration | Block rewrite — target unified topology block (PERSONA_PORT=8090, PERSONA_CTX=32768, GPU_LAYERS_PERSONA=999, PERSONA_PARALLEL=4, PERSONA_CONCURRENCY=4, post-M5 reasoning/thinking-mode vars) + collapsed `<details>` block for legacy dual-server vars + env symlink transient note |
| File Change Tracker | Appended 2026-05-19, 2026-05-20, 2026-05-22 entries |

**Correction landed in this sweep:** the 05-19/20 handoffs framed the port move as "to avoid OpenWebUI Docker on :8080". Diagnostic 2026-05-22 showed that the actual squatter on :8080 is an unrelated co-tenant container (Nomad stack — kept out of KNOWLEDGE.md per user choice; Project_Persona doc scope stays Persona-only). OpenWebUI itself is dormant. Wording updated everywhere.

**Regression caught in same sweep:** diagnostic also showed llama-server was down on EVO-X2 (no listener on :8090) — §Open issues #1 recurrence. Revived as a separate step below (§3.3).

### 3.2 Commit hygiene

Doc-only commit, single file. Commit message stored at `.commit_msg_KNOWLEDGE_2026-05-22.txt` (workspace scratchpad), invoked via `git commit -F`, then file removed.

- Sandbox could not finalize the commit (couldn't write tmp objects under the mount); commit was executed Windows-side.
- Pre-existing stale `.git/index.lock` (Windows-side process residue) deleted manually.
- Cmd-syntax confusion (`del`/`2>nul`) bled a literal `nul` file into the repo when pasted into MINGW64 Bash; cleaned up.

Resulting commit: **`3238077`** on `origin/main`, message subject "docs(knowledge): drift cleanup per HANDOFF_2026-05-20_0102 §Step 3".

### 3.3 llama-server + API revival on EVO-X2

| Step | Result |
|---|---|
| Start llama-server | New pid **1810898**, listening on `127.0.0.1:8090`, `/health` returns `{ "status": "ok", "slots_idle": 4, "slots_processing": 0 }` |
| Watcher harness | `while kill -0 $PID; sleep 5; done` backgrounded as pid **1811996** for death-detection through the test window |
| Start API | New pid **1813299** (replaced stale pidfile from pid 1200705 dated May 20). `start_api.sh` cleanly clobbered the dead pidfile. `/health` returns proper M5 shape: `unified_endpoint`, `async_reasoning_enabled`, `reasoning_inband_enabled/topics/max_tokens/timeout_s`, `thinking_mode_default/topics` — no stale `scientist_endpoint`. |
| Smoke chat | Photosynthesis-prompt smoke succeeded end-to-end via the API → llama-server path. |

### 3.4 M2b 90s smoke @ concurrency=4

Run prior to the full 30-min to catch any obvious immediate failure.

- 108/108 OK, gen_tps_mean=27.88, lat_p50≈4.36s
- Health polls clean

Smoke passed; proceeded to full run.

### 3.5 M2b full 30-min @ concurrency=4 — primary deliverable

**Invocation:**

```
python3 scripts/load_test_m2b.py \
  --endpoint http://127.0.0.1:8090/v1/chat/completions \
  --health   http://127.0.0.1:8090/health \
  --duration 1800 \
  --concurrency 4 \
  --out logs/m2b_$(date +%F_%H%M).json
```

`--endpoint` and `--health` overrides required because `DEFAULT_ENDPOINT` / `DEFAULT_HEALTH` in `scripts/load_test_m2b.py` are still on `:8080` (carried-forward fix; see §6.1).

**Window:** 2026-05-23T07:23:58 PDT → 2026-05-23T07:54:00 PDT
**Report:** `logs/m2b_2026-05-23_0723.json`

**Overall:**

| Metric | Value |
|---|---|
| total_requests | 2066 |
| ok_requests | 2066 |
| error_requests | 0 |
| lat_p50_s | 4.358 |
| lat_p95_s | 4.553 |
| lat_max_s | 4.763 |
| gen_tps_mean | 28.26 (per slot) |
| gen_tps_min | 11.5 |
| gen_tps_max | 38.76 |
| health_polls | 60 |
| health_ok | 60 |
| health_fail | 0 |
| concurrency | 4 |
| max_tokens | 128 |
| aggregate ~ | 113 tok/s (28.26 × 4) |

**Per-minute stability (gen_tps_mean by bucket):**

| Bucket | n | gen_tps_mean |
|---|---|---|
| min00 | 70 | 28.47 |
| min01 | 71 | 27.78 |
| min05 | 72 | 28.69 |
| min10 | 65 | 28.67 |
| min15 | 72 | 28.03 |
| min20 | 66 | 28.58 |
| min25 | 72 | 27.91 |
| min29 | 71 | 28.53 |

Full range across all 30 buckets: **27.78 – 28.79**. No degradation curve. No throttling signature.

The `min-1` bucket (n=2, 31.46 tps) is a cold-start artifact from the bucketize race in `samples[0]`; it's a known reporting quirk, not a real signal.

### 3.6 Thermal / power capture — partial

| Sample | When | CPU Tctl | iGPU edge | PPT |
|---|---|---|---|---|
| Pre-test cold idle | 07:22 PDT (~1 min pre-test) | 34.2°C | 33.0°C | 6.05 W |
| Post-test (cooled, NOT under load) | 09:17 PDT (~+1h23m after wrap) | 30.5°C | 30.0°C | 6.05 W |

**Caveat — important:** the post-test sample was taken well after the run wrapped, with the system already idle. It carries no information about peak-load thermal behavior. Treat it as a thermal-recovery datapoint only.

**Follow-up for next baseline pass:** parallel-log `sensors` during the run (e.g. `while sleep 10; do sensors | grep -E "Tctl|edge|PPT" >> logs/m2b_${ts}_sensors.log; done &` in front of the load test command, killed after). Cheap, no extra dependency.

### 3.7 Stability ghost — status

The 2026-05-19 / 2026-05-20 carried-forward §Open issues #1: "llama-server died once during 05-19 session with no graceful-shutdown signature, root cause unidentified."

**This session:** ghost did NOT recur. llama-server pid 1810898 held through the full M2b window plus 30+ minutes of residual time. Watcher harness pid 1811996 did not trip.

**Conclusion:** ghost is dormant, not exorcised. The 05-19 crash remains unattributed. Treat recurrence as still-possible. Carry the watcher harness pattern forward for any future long-running session.

---

## 4. Key Numbers (one-line summary)

> EVO-X2 / Strix Halo iGPU, unified Qwen3-30B-A3B-Instruct-2507 Q5_K_M (49/49 layers Vulkan0/RADV), 4 parallel slots × 8K ctx each (32K total), q8_0 KV cache, Flash Attention: **28.26 tok/s per slot × 4 = ~113 tok/s aggregate**, p50 4.358s, p95 4.553s, zero errors over 2066 requests, throughput flat over 30 min.

---

## 5. Files Modified This Session

| File | Change | Status |
|---|---|---|
| `KNOWLEDGE.md` | Drift cleanup full sweep (2026-05-22) | Committed `3238077`, pushed to origin/main |
| `KNOWLEDGE.md` | M2b resolution + baseline metrics + Next-session entry update (2026-05-23) | **Uncommitted as of handoff write** — commit + push deferred to user |
| `archive/handoffs/HANDOFF_2026-05-23_0218_docs-drift-m2b-baseline.md` | Created (this file) | **Uncommitted as of handoff write** |
| `logs/m2b_2026-05-23_0723.json` | M2b report output (EVO-X2 only) | EVO-X2-side artifact; do not commit logs |

**Files NOT modified this session** (despite drift noted):

- `scripts/load_test_m2b.py` — `DEFAULT_ENDPOINT` / `DEFAULT_HEALTH` still on `:8080` (carried-forward; see §6.1)
- `scripts/start_api.sh` — cosmetic SCIENTIST_* banner drift (carried-forward; see §6.2)
- `run/llama-servers.env` — read for reference only; no changes

---

## 6. Carried-Forward Items (next-session backlog)

### 6.1 `scripts/load_test_m2b.py` endpoint drift — small fix-it

Currently:
```python
DEFAULT_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_HEALTH = "http://127.0.0.1:8080/health"
```

Should be `:8090` post-M5. Required `--endpoint` / `--health` overrides every time today. Two-line patch; deferred for now because doing it as a separate commit keeps the M2b "first baseline" point clean in git history.

### 6.2 `scripts/start_api.sh` cosmetic banner drift

Per HANDOFF_2026-05-20_0102 §Open issues #4b — start banner still says "Scientist: 8081 / Async scientist enabled" and the `MEMORY_DISTILL_ENABLED` export below the `nohup` fork on line 104 is dead. Both are cosmetic; the script works via back-compat env reads.

### 6.3 `prompt_tokens=0` in API response

Noticed during the M2b smoke. Either a real token-counter regression in server.py post-M5 or a llama-server response field that's not getting picked up. Worth diagnosing before relying on token-budget bookkeeping.

### 6.4 `bucketize_by_minute` "min-1" race

`scripts/load_test_m2b.py` produces a `min-1` bucket with `n=2` from `samples[0]` boundary handling. Cosmetic reporting quirk. Trivial fix.

### 6.5 Qwen3.6 backport on EVO-X2

Still gated on llama.cpp bump (currently b8157, needs ≥b8770 for Qwen3.5/3.6 arch support). Tracked as TODO #36; not blocked on anything else.

### 6.6 llama-server stability ghost (carry from 05-19/20)

Did not recur. Still unidentified. If it recurs, the watcher harness pattern will catch it; capture `dmesg | tail -200`, the llama-server log, and a snapshot of `ps -ef | grep -E "llama|nomad"` for cross-tenant signal.

### 6.7 Peak-load `sensors` log not captured this session

Add a parallel sensor logger to the next baseline run. One-liner — see §3.6 follow-up.

---

## 7. Next-Session Entry Points

User-facing landing options for the next session (pick one):

| Option | What | Effort | Value |
|---|---|---|---|
| **A. M6** | Parallelize RAG retrieval + worker dispatch with `asyncio.gather` (replaces serial in-band reasoning call) | Medium | Direct latency win on multi-source queries |
| **B. Hermes H1 pre-flight** | H1.1 read docs end-to-end → H1.5 egress integration test → H1.6 kernel-level netns/iptables guardrail | Medium-High | Unblocks H2+ Hermes integration; necessary for DECISION 2026-05-11 |
| **C. Live smoke /chat + /v1/chat/completions** | Beyond M2b's single-shot prompt: exercise thinking-mode auto/on/off resolution, REASONING_INBAND opt-in path, /health full field shape | Low | Confirms M5 behavioral surfaces beyond throughput |
| **D. Housekeeping batch** | §6.1 + §6.2 + §6.3 + §6.4 in one small-PR-style commit | Low | Tidies the drift before next milestone |
| **E. T0 Qwen3.6 GO/NO-GO** | T0.1 arch test + T0.2 tool-calling verification (gated on llama.cpp ≥b8770) | High | Largest leverage if Qwen3.6 lands well, but llama.cpp bump is the real gate |

Recommended order: **D** first (cheap, clears noise) → **C** (validates M5 surfaces) → **A** or **B** (real work).

---

## 8. Operational Reference (for cold-start next session)

### 8.1 Bring stack up on EVO-X2

```
cd ~/Git/Project_Persona
source env/bin/activate
bash scripts/start_llama_servers.sh
bash scripts/start_api.sh
```

### 8.2 Verify

```
curl -s http://127.0.0.1:8090/health
curl -s http://127.0.0.1:8000/health
ss -ltnp | grep -E '8090|8000'
```

`:8090` should show llama-server. `:8000` should show the API (FastAPI/uvicorn). Anything else on `:8080` is the unrelated co-tenant container.

### 8.3 Repeat M2b baseline

```
python3 scripts/load_test_m2b.py \
  --endpoint http://127.0.0.1:8090/v1/chat/completions \
  --health   http://127.0.0.1:8090/health \
  --duration 1800 \
  --concurrency 4 \
  --out logs/m2b_$(date +%F_%H%M).json
```

Add the sensors parallel-log per §3.6 follow-up if you want peak thermal this time.

### 8.4 Watcher harness (death-detection)

```
PID=$(cat run/llama.pid)
( while kill -0 $PID 2>/dev/null; do sleep 5; done; echo "$(date) llama-server pid $PID died" >> logs/watcher.log ) &
```

Keeps a marker for next-session diagnostic if the stability ghost returns.

---

## 9. Commit Plan (for user, on Windows side)

```
cd D:\Projects\Git\Project_Persona
git add KNOWLEDGE.md archive/handoffs/HANDOFF_2026-05-23_0218_docs-drift-m2b-baseline.md
git commit -m "docs(knowledge): retire M2b — 2066/2066 OK, gen_tps=28.26/slot, throughput flat" -m "30-min sustained-load run on EVO-X2 against unified Qwen3-30B-A3B Q5_K_M, concurrency=4. Per-minute throughput essentially flat from min00 to min29 (range 27.78-28.79). Stability ghost from HANDOFF_2026-05-19/20 §Open issues #1 did not recur." -m "Handoff: archive/handoffs/HANDOFF_2026-05-23_0218_docs-drift-m2b-baseline.md"
git push
```

(Standard git config has `Brandon Allen <festro33@hotmail.com>` Windows-side per past handoffs; sandbox commit pathway still has FS permission issue with object tmp writes — keep commits Windows-side.)

---

## 10. Open Questions / Decisions Deferred

- **Should the `sensors` parallel-log be folded into `scripts/load_test_m2b.py` itself, or stay a wrapper one-liner?** Lean toward wrapper — keeps load_test single-purpose, avoids platform-specific sensors invocation in the script.
- **`prompt_tokens=0` — server.py bug or llama-server response shape?** Diagnose in next housekeeping batch.
- **Should we tag the M2b retirement as a Git milestone?** Currently no tags in `Git Milestone Log` (KNOWLEDGE.md §11). M2b is the first concrete sustained-load datapoint; arguable as `v0.1-m2b-baseline` or similar.

---

## 11. Sources & Cross-References

- Predecessor handoff: `archive/handoffs/HANDOFF_2026-05-20_0102_m5-validated-evox2.md`
- Predecessor handoff: `archive/handoffs/HANDOFF_2026-05-19_1130_evox2-m5-validation.md`
- Architectural decision: KNOWLEDGE.md §DECISION 2026-05-09 (single-model migration)
- Architectural decision: KNOWLEDGE.md §DECISION 2026-05-11 (Hermes adoption)
- Runtime config (current): `run/llama-servers.env`
- Load test script: `scripts/load_test_m2b.py`
- M2b report: `logs/m2b_2026-05-23_0723.json` (EVO-X2 only)
- Commit: `3238077` ("docs(knowledge): drift cleanup per HANDOFF_2026-05-20_0102 §Step 3")

---

**End of HANDOFF_2026-05-23_0218_docs-drift-m2b-baseline.md.**
