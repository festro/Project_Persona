# HANDOFF: EVO-X2 M5 Validation — API Side Confirmed, llama-server Stability TBD

**Session date:** 2026-05-19 1130 PDT (2026-05-19 1830 UTC)
**Repo:** github.com/festro/Project_Persona
**Status:** M5 server.py validated live on EVO-X2 via `/health` shape. End-to-end `/chat` smoke-test blocked — llama-server keeps dying after launch.
**Branch:** `main` (already pushed to origin through commit `8001746`; this session's tiny `stop_api.sh` patch and `PERSONA_PORT=8090` env edit are uncommitted)
**Predecessor handoff:** `archive/handoffs/HANDOFF_2026-05-17_1830_qwen36-windows-prototype.md`

---

## TL;DR for the next session

You can ask the next chat to **"continue from this handoff"** and it should be able to pick up without re-context.

State summary:

- ✅ Four commits pushed in the prior session (chore(docs) handoff relocation + canonicalize + M5 + Windows portable).
- ✅ Pulled cleanly to EVO-X2 (`8001746` is current `HEAD`).
- ✅ M5 server.py loaded on EVO-X2; `/health` returns the M5 field shape (`unified_endpoint`, `async_reasoning_enabled`, `reasoning_inband_*`, `thinking_mode_*`, `persona_concurrency: 4`, no `scientist_endpoint`).
- ✅ Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf landed on EVO-X2 via scp; sha256 matches Windows side.
- ⚠ **llama-server keeps dying after launching**. Cleanly (graceful SIGTERM, prints memory_breakdown then exits). Cause unknown. Without it, `/v1/chat/completions` returns `httpx.ConnectError`.
- ⚠ Port 8080 occupied by OpenWebUI Docker container (`pid 4090` from `~/Live/AIStack/...` workflow). llama-server moved to `PERSONA_PORT=8090` to avoid conflict.

### Next-session entry point

1. Read this handoff.
2. Run the **Immediate revival** block (Step 1 below).
3. If `/chat` returns a coherent answer, mark M5 fully validated; commit + push the two-line edits from this session.
4. If llama-server dies again, debug with the **llama-server stability** investigation in §"Open issues".

---

## What we tried this session (chronological)

1. On Windows: pushed four commits to origin/main:
   - `b2b2b87` chore(docs) handoff relocation
   - `cd157f2` qwen-test canonicalize
   - `9ba597c` M5 server.py + 2-file Hermes profile loader
   - `8001746` Windows zero-install portable + Qwen3.6 T0.1 prototype (PASSED)

2. On EVO-X2: `git fetch + git pull --ff-only` — pull initially failed because EVO-X2's `run/llama-servers.env` and `scripts/start_llama_servers.sh` were locally modified (from the 2026-05-16 first boot session). Content was byte-identical to incoming commit, so `git restore` discarded the local marks; subsequent `git pull --ff-only` succeeded. Three handoffs renamed (R100/98/97), four created, plus all the scripts/.bat/server.py updates landed.

3. **First API restart misfired.** `scripts/start_api.sh` hardcoded `AI_ROOT="${AI_ROOT:-$HOME/Live/AIStack/Project_Persona}"`. Result: even though M5 was on disk at `~/Git/Project_Persona/`, the API loaded the OLD server.py from `~/Live/AIStack/Project_Persona/services/api/server.py`. `/health` returned pre-M5 shape.

4. **Patched `start_api.sh`** via `sed -i 's|HOME/Live/AIStack/Project_Persona|HOME/Git/Project_Persona|g'`. Discovered `~/Git/Project_Persona/env/` was missing the venv; symlinked: `ln -s ~/Live/AIStack/Project_Persona/env ~/Git/Project_Persona/env`. (That symlink itself resolves through a second hop to `~/AI/env/` apparently — multiple legacy locations exist but the venv works fine through them.) Restarted API → `/health` returned proper M5 shape including all new fields.

5. **Identified port 8080 conflict.** `pid 4090` is OpenWebUI in a Docker container (cwd `/app`, Pipfile-based, classic OpenWebUI client/server layout). Decided to keep it running and move llama-server to port 8090.

6. **Edited `run/llama-servers.env`:** `PERSONA_PORT=8080` → `PERSONA_PORT=8090`.

7. **Started llama-server (pid 715269).** Log confirmed: model loaded (Qwen3-30B-A3B-Instruct-2507 Q5_K_M), 49/49 layers on Vulkan0, 4 parallel slots × 8192 ctx, `main: server is listening on http://127.0.0.1:8090`, all slots idle. **Reached steady state cleanly.**

8. **Patched `scripts/stop_api.sh`** with the same sed (it also hardcoded Live path). Without this patch, `stop_api.sh` couldn't find the api pidfile.

9. **Killed and restarted API.** New pid 1200705. `/health` correctly reported `unified_endpoint: "http://127.0.0.1:8090/completion"`.

10. **Smoke-test `/v1/chat/completions` returned `httpx.ConnectError('All connection attempts failed')`.**

11. **Investigation:** the log shows llama-server printed the graceful-shutdown sequence (`operator(): cleaning up before exit...` + `llama_memory_breakdown_print`) sometime between step 7 and now. Process is gone. Something killed it via SIGTERM.

---

## What's currently on EVO-X2 disk

- `services/api/server.py` — M5 version (matches origin/main `8001746`).
- `run/llama-servers.env` — qwen-test-rewrite version but with **`PERSONA_PORT=8090`** (uncommitted local edit).
- `scripts/start_api.sh` — patched to Git workspace (uncommitted local edit).
- `scripts/stop_api.sh` — patched to Git workspace (uncommitted local edit).
- `models/Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf` — legacy unified model (still in use today).
- `models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf` — new Qwen3.6 from scp, sha256-verified, **NOT being used yet**.
- `env/` — symlink to `~/Live/AIStack/Project_Persona/env` (which itself resolves further).
- `archive/handoffs/` — clean tree, all dated handoffs.

API process state at end of session: pid 1200705, listening on 8000, healthy via /health but cannot reach llama-server.

llama-server: dead.

---

## Open issues going into next session (priority order)

### 1. llama-server keeps dying after a clean steady-state launch (BLOCKER)

llama-server launches via `./scripts/start_llama_servers.sh`, reaches "model loaded" + "server is listening" + "all slots are idle", then is killed by SIGTERM after some interval. Memory breakdown is printed (graceful shutdown signature, not crash).

Suspected culprits — investigate in order:

1. **`pkill -f 'uvicorn server:app'`** — we ran this during the api restart. Should NOT have matched llama-server (different binary name). But verify with `pgrep -af llama-server` and `pgrep -af uvicorn` to confirm no accidental match.
2. **systemd-oom-killer or earlyoom** — under memory pressure, the system might kill the largest process. `journalctl -k | grep -iE 'oom|killed' | tail -20` will show. With 64 GB unified memory + the model only using ~22 GB, this seems unlikely but worth ruling out.
3. **The api itself spawned a child that interfered** — unlikely; api uses httpx for outbound, doesn't pkill anything.
4. **A cron job or watchdog** — `crontab -l` and `systemctl list-units --type=service | grep -i ai`.
5. **`nohup` not actually detaching properly** — the launcher does `nohup "$BIN" ... > "$LOG_FILE" 2>&1 &` then `echo $!` to the pidfile. If the parent shell that ran `./scripts/start_llama_servers.sh` exits, llama-server should survive via nohup. But: on some Linux configs, SIGHUP propagation works differently. Test by launching from a `setsid` or `disown` wrapper.

The cleanest diagnostic is: launch llama-server, immediately get its PID, run `strace -e trace=signal -p <pid>` in another shell, and watch which signal hits it and from which sender. That'll identify the killer definitively.

### 2. Open follow-ups deferred from prior sessions

- **M2b sustained-load test** (`scripts/load_test_m2b.py`) — run once #1 is resolved.
- **T0.2 tool-calling round-trip test** — gates Hermes Phase 8.
- **EVO-X2 swap to Qwen3.6** — separate decision. Requires bumping EVO-X2's llama.cpp from `b8157` to a recent build (≥ `b8770` ideally, to match what Windows used). Compat re-eval (`archive/handoffs/HANDOFF_2026-05-15_0827_compat-reeval-tiered.md`) flagged `qwen3_5_moe` arch support as "unverified" at b8157. Likely works, but worth confirming.
- **`looks_degenerate()` decision gate** (TODO #37) — must land or formally drop alongside T2.4 work.
- **`<think>`-tag stripping (T2.4)** — pairs with #5.
- **start_api.sh + stop_api.sh banner cleanup** — the `Persona/Scientist` echo lines are pre-M5. Currently cosmetic. Update when convenient.

### 3. Uncommitted edits this session

These need to be committed + pushed once #1 is resolved (or even before, since they're isolated fixes):

```
git diff run/llama-servers.env             # PERSONA_PORT 8080 -> 8090
git diff scripts/start_api.sh              # Live -> Git workspace
git diff scripts/stop_api.sh               # Live -> Git workspace
```

Plus this handoff (`archive/handoffs/HANDOFF_2026-05-19_1130_evox2-m5-validation.md`) needs adding.

---

## Step 1 — Immediate revival on EVO-X2 (run this first next session)

```
cd ~/Git/Project_Persona

# Clean stale pidfile
rm -f run/persona.pid

# Re-launch llama-server with the Qwen3-Instruct-2507 model on port 8090
./scripts/start_llama_servers.sh

# Wait for model load — 30-60s for 49-layer Vulkan offload
sleep 45

# Confirm it's bound and alive
ss -tlnp 2>/dev/null | grep 8090
ps -ef | grep llama-server | grep -v grep

# Direct hit on llama-server's own /health (bypasses api)
curl -s http://127.0.0.1:8090/health
echo ""

# Full stack smoke through M5 api -> llama-server
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3",
    "messages": [{"role":"user","content":"In one sentence: what is photosynthesis?"}],
    "max_tokens": 150,
    "temperature": 0.7,
    "stream": false
  }' | python3 -m json.tool
```

**Expected on success:**

- `ss` shows `LISTEN 0 ... 127.0.0.1:8090 ... users:(("llama-server",pid=<NNNN>,fd=<N>))`
- `ps` shows the llama-server process alive
- `curl :8090/health` returns `{"status":"ok"}` (llama-server's own health endpoint)
- Final curl returns a coherent JSON with `content` populated. Qwen3-Instruct-2507 has `thinking = 0` so `reasoning_content` will be absent.

**If llama-server dies again within minutes:**

```
# Watch the log live in a second ssh session
tail -F ~/Git/Project_Persona/logs/persona.log

# In the original session, launch again and immediately attach strace
./scripts/start_llama_servers.sh
sleep 2
LLAMA_PID="$(cat run/persona.pid)"
echo "llama-server pid=$LLAMA_PID"
strace -e trace=signal -p "$LLAMA_PID" 2>&1 | tee /tmp/llama-strace.log

# When it dies, the strace log will show which signal hit it
# (look for SIGTERM/SIGINT/SIGKILL/SIGHUP)
```

Also check the kernel log for OOM kills:

```
journalctl -k --since "1 hour ago" | grep -iE 'oom|killed' | tail -10
```

---

## Step 2 — Commit + push this session's small fixes (when M5 is validated)

```
cd ~/Git/Project_Persona
git status                                    # confirm working tree

# Add this session's edits + the new handoff
git add run/llama-servers.env \
        scripts/start_api.sh \
        scripts/stop_api.sh \
        archive/handoffs/HANDOFF_2026-05-19_1130_evox2-m5-validation.md

git commit -m "EVO-X2 M5 live: PERSONA_PORT 8090, start_api/stop_api Git-workspace paths

- run/llama-servers.env: PERSONA_PORT 8080 -> 8090 (avoid OpenWebUI Docker on 8080).
- scripts/start_api.sh: AI_ROOT default flipped from \$HOME/Live/AIStack/... to \$HOME/Git/Project_Persona/. Was reading the pre-M5 server.py from Live workspace.
- scripts/stop_api.sh: same path fix; without it, the api pidfile in Git workspace couldn't be found.
- archive/handoffs/HANDOFF_2026-05-19_1130_evox2-m5-validation.md: session record + llama-server-stability follow-up plan.

M5 /health now reports unified_endpoint http://127.0.0.1:8090/completion + thinking_mode_default auto + persona_concurrency 4 + reasoning_inband_* + thinking_mode_*. No scientist_endpoint.

Refs archive/handoffs/HANDOFF_2026-05-17_1730_m5-server-py-migration.md."

git push origin main
```

---

## Step 3 — KNOWLEDGE.md updates (next-next session, low priority)

These are tracking edits, not code work. Apply to `KNOWLEDGE.md` whenever convenient:

1. System State row for "llama-server (unified) port 8080" — port has shifted to **8090** on EVO-X2 (because OpenWebUI Docker is on 8080). Update accordingly.
2. New row for "OpenWebUI Docker (port 8080)" or update existing OpenWebUI row to reflect actual deployment (KNOWLEDGE.md currently says WEBUI_PORT=3000, but reality is OpenWebUI is in a container on 8080).
3. File Change Tracker entry for this session.
4. Acknowledge the symlink: `~/Git/Project_Persona/env → ~/Live/AIStack/Project_Persona/env → ~/AI/env`. Note as transient — eventually the project should have its own venv at `~/Git/Project_Persona/env/` (clean break from Live). Don't migrate this session.

---

## Performance snapshot (from earlier successful Windows-side T0.1)

For reference. Both proven on Windows with Qwen3.6-35B-A3B-UD-Q5_K_XL (NOT yet tested on EVO-X2):

| Hardware | Quant | Layers | Mode | Gen tok/s |
|---|---|---|---|---|
| RX 9060 XT 16GB, Ryzen 9 9900X | Q5_K_XL (26.6 GB) | 35/40 GPU | Vulkan, thinking on | ~13.5 |
| RX 9060 XT 16GB, Ryzen 9 9900X | Q5_K_XL (26.6 GB) | 35/40 GPU | Vulkan, thinking off | ~14.0 |

When EVO-X2 backports to Qwen3.6 (separate session), expect comparable or better numbers given Strix Halo's higher VRAM ceiling and full layer offload capacity.

---

## End

This session was the natural follow-up to the four-commit push: get the new code running on EVO-X2 and prove M5 end-to-end. Got 80% of the way — the api half is bulletproof (`/health` confirms M5 live), the llama-server half keeps falling over for reasons not yet diagnosed. The "Immediate revival" block at the top of this handoff gets the next session pointed at the right thing to check first.

If llama-server stays alive on the next launch attempt and the curl returns a real answer — M5 is officially done. If it dies again, the strace approach in Step 1's failure branch will identify what's killing it.

Sources:
- [archive/handoffs/HANDOFF_2026-05-17_1730_m5-server-py-migration.md] (M5 design + Windows-side verification)
- [archive/handoffs/HANDOFF_2026-05-17_1830_qwen36-windows-prototype.md] (T0.1 + scp transfer)
- [archive/handoffs/HANDOFF_2026-05-15_0827_compat-reeval-tiered.md] (tiered T0-T4 plan + Qwen3.6 backport gate)
