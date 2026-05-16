# AIP_HANDOFF — Mercury Integration Addendum

**Document:** `AIP_HANDOFF_mercury_integration_20260427_1545_addendum_2108.md`
**Project:** Project_Persona (AIP_)
**Date / Time:** 2026-04-27 21:08
**Author:** Brandon (festro) + Claude (Opus 4.7)
**Status:** ADDENDUM — supersedes specific sections of `AIP_HANDOFF_mercury_integration_20260427_1545.md`
**Scope:** Reconcile the original handoff against (a) Mercury source pulled from npm registry, (b) live `services/api/server.py`, `start_api.sh`, and `run/llama-servers.env` from the EVO-X2.
**Repo:** github.com/festro/Project_Persona

---

## 1. TL;DR

Two reconciliations completed since the 1545 handoff:

- **Mercury source verified.** Pulled `@cosmicstack/mercury-agent@1.2.0` from the npm registry. Most architectural claims in the original handoff hold up. Several numeric specifics were wrong or unsourced; corrections in §3.
- **Live EVO-X2 files reviewed.** All four previously-documented bugs in `/agent/run` and `start_api.sh` are still present. One "Preserved Live Feature" listed in KNOWLEDGE.md (`looks_degenerate()`) does not exist in the live code at all. Two listed Phase 1 TODOs are actually complete. Details in §4.

The four borrows (B1–B4) remain valid choices. Their implementation specs need the corrections in §5 before any code is written.

The Git-template `run/llama-servers.env` is stale (port 8081); the live file on EVO-X2 is correct (port 8083). Workflow to fix this and consolidate Live → Git is in §7.

---

## 2. Mercury Source — Verification Method

Pulled the published npm package directly:

```
curl -sL https://registry.npmjs.org/@cosmicstack/mercury-agent/-/mercury-agent-1.2.0.tgz -o mercury.tgz
tar -xzf mercury.tgz
```

The package ships a bundled `dist/index.js` (12,712 lines) plus `package.json`, `LICENSE`, `README.md`, and `web/static/` assets. Source-level `.ts` files are not published — bundle constants are extracted via grep.

License confirmed: **MIT © Cosmic Stack** (`package/LICENSE`).
Node engine: **`>=20.0.0`** — original handoff said Node 18+. Correction below.

---

## 3. Mercury Source — Corrections to Original Handoff

### 3.1 Verified verbatim
- 10 memory categories: `identity, preference, goal, project, habit, decision, constraint, relationship, episode, reflection` ✓
- SQLite + FTS5 storage ✓
- `evidence_count >= 3` for active→durable promotion ✓
- 21-day and 120-day window constants present in source ✓
- 900-char recall budget (`maxChars: 900`) ✓
- `~/.mercury/` per-user data path ✓
- `SECOND_BRAIN_ENABLED` env toggle ✓
- `mercury.service` systemd unit with `Restart=on-failure` ✓
- `systemctl --user enable | start | stop | status | daemon-reload` command set ✓
- `approve_command` and `approve_scope` tools both exist ✓ (earlier README-only fact-check incorrectly flagged `approve_scope` as missing)
- Telegram via grammY ✓
- Multi-provider list `anthropic, openai, deepseek, ollama, grok/xAI` ✓ (all five present; original handoff was right)

### 3.2 Refuted — original handoff numbers were wrong

| Claim in original handoff | Mercury source value | Correction |
|---|---|---|
| Confidence reject < **0.55** | DEFAULT confidence = **0.7**; reject branch fires at `confidence < 0.3` | **Use 0.7 default, reject below 0.3.** Drop the 0.55 reference entirely. |
| "Tighten confidence floor to 0.65 for PP" | Mercury default already 0.7 | Recommendation is incoherent — 0.65 would be a loosening, not tightening. **Delete this guidance.** |
| Node.js **18+** | `engines.node: >=20.0.0` | Document Node 20 if any tooling parity matters; PP itself doesn't run Node so impact is zero. |
| Telegram uses **long polling** only | Both long polling and webhook are supported in the bundle | Pick one explicitly for B4. Long polling is correct for NAT'd self-hosted; webhook needs an inbound endpoint. |

### 3.3 Missed in original handoff — additions required

| Item | Source evidence | Action for PP |
|---|---|---|
| `SECOND_BRAIN_MAX_RECORDS` env var | Found in bundle alongside `SECOND_BRAIN_ENABLED` | Add equivalent record cap to PP's Second Brain to prevent unbounded fact growth. |
| Day-window ladder is wider than 21/120 | Bundle contains 7, 14, 21, 42, **and** 120 day constants | Either replicate the full 5-tier ladder or document why PP collapses to two thresholds. |
| Blocklist includes `chmod 777` | Confirmed verbatim alongside `sudo`, `rm -rf`, `mkfs`, `dd if` | Add `chmod 777` to PP's B3 blocklist. |
| Configuration is YAML, not env vars | `~/.mercury/mercury.yaml`, `permissions.yaml`, `schedules.yaml` | PP's B1–B4 specs use env-var toggles. Either match Mercury (YAML) or document the divergence. |
| macOS launchd support | `com.cosmicstack.mercury.plist`, `launchctl load/unload` paths in bundle | B2 framing as "systemd-only" is incomplete for cross-platform parity. PP can stay Linux-only — but call it a deliberate scope choice. |
| Mercury web UI / dashboard | Hono + HTMX + Alpine.js + sql.js, served via `@hono/node-server`, assets under `dist/web/static/` | Not a borrow candidate, but worth noting Mercury has observability surface PP doesn't. Consider for future PP roadmap. |
| Token budgeting via `js-tiktoken` (real BPE) | Confirmed in deps | Skip decision unchanged (PP is local-only) — but the rationale is "no token cost," not "Mercury uses regex counting." |
| `bcryptjs` for credential hashing | In deps | If B4 stores the Telegram pairing code, hash it — original handoff didn't specify storage form. |

### 3.4 Refuted — claims that don't appear in Mercury at all

- **"GitHub companion (PRs, issues, co-author)"** in the skip list: **not present** in repo or bundle. No octokit, no `gh` shell-out, no companion code path. The skip-list line item is built on a feature Mercury doesn't have. Harmless (PP wasn't going to borrow it) but the citation should be removed from the original handoff.

---

## 4. Live Code Reconciliation (EVO-X2)

Files reviewed: `services/api/server.py` (831 lines), `scripts/start_api.sh` (104 lines), `run/llama-servers.env` (45 lines).

### 4.1 Bugs confirmed still present

| Bug | Location | TODO ref |
|---|---|---|
| `/agent/run` uses `subprocess.run()` — blocks event loop up to 300s | `services/api/server.py:632` | AIP TODO #8 |
| `/agent/run` uses relative `Path("run") / "jobs"` | `services/api/server.py:612` | AIP TODO #9 |
| `MEMORY_DISTILL_ENABLED` exported AFTER `nohup uvicorn` — never reaches server | `scripts/start_api.sh:104` (uvicorn launches at line 88-91) | AIP TODO #6 |
| `taskman2.py` referenced but does not exist | `services/api/server.py:622` (`"tools/taskman2.py"`) | AIP TODO #5 (related), missing executor |
| `SCIENTIST_PORT` default fallback is 8081 (BrandonNet OTS) in both server and script | `services/api/server.py:42`, `scripts/start_api.sh:41` | New — flag as silent foot-gun |
| `AI_ROOT` default points to `~/AI` (dead post-migration) | `services/api/server.py:34` | New — minor; script overrides correctly |

### 4.2 Regression — was claimed present, is actually gone

**`looks_degenerate()` and the two-stage self-repair loop do not exist in the live `services/api/server.py`.**

- KNOWLEDGE.md → "Preserved Live Features (must survive all refactors)" → lists `looks_degenerate()` and two-stage self-repair as live.
- Original Mercury handoff → §2 Background → asserts the same.
- Live grep: zero matches for `looks_degenerate`, `repair_prompt`, `two.stage`, `self.repair`.

AIP TODO #11 said "Verify looks_degenerate() in current server.py — Listed as existing in old spec — not found in uploaded file." That verification is now complete: **it is not there.** PP currently has no degeneracy guard on the persona output path. Either reinstate it or accept its absence — but stop documenting it as a feature.

### 4.3 TODOs that are actually complete

These should be marked done in whichever knowledge doc is kept:

- **`build_persona_prompt()` is fully wired.** server.py line 450 loads `persona.md` and `system_rules.md` from `PROFILES_DIR/<profile>/` and threads them into the prompt. Closes KNOWLEDGE.md TODO #3 and AIP TODO #12.

### 4.4 Endpoint reality

| Line | Endpoint | Live status |
|---|---|---|
| 594 | `POST /agent/run` | Live but bug-laden (sync subprocess + relative path + missing executor) |
| 700 | `GET /health` | Live |
| 722 | `POST /chat` | Live, primary path |
| 771 | `POST /chat_submit` | **Disabled** — returns `"chat_submit is disabled in this build."` |
| 783 | `GET /jobs/{job_id}` | Live, reads in-memory `jobs` dict |
| 791 | `GET /v1/models` | Live |
| 803 | `POST /v1/chat/completions` | Live, **non-streaming only** — accepts `stream` field, ignores it, always returns single `JSONResponse` |

KNOWLEDGE.md's "✅ Verified — OpenAI-compatible streaming" claim is wrong. AIP TODO #4 (SillyTavern blocker) is the correct framing.

### 4.5 Naming question — settled by code

Live code uses **`SCIENTIST`** consistently throughout: `SCIENTIST_PORT`, `SCIENTIST_URL`, `SCIENTIST_INBAND_*`, `ASYNC_SCIENTIST_*`. AIP_knowledge.md aligns. KNOWLEDGE.md's "rename scientist → reasoning" TODO and the original handoff's "Reasoning server (8083)" framing are both backwards relative to the code.

**Action:** Treat `scientist` as canonical going forward. Strike the rename TODO from KNOWLEDGE.md. Update Mercury handoff §2 reference to "Reasoning server" → "Scientist server."

---

## 5. Env-File Resolution

**Live (EVO-X2):** `run/llama-servers.env` has `SCIENTIST_PORT=8083` ✓ and an extra line:

```
LLAMA_LIB_DIR=$HOME/Live/AIStack/Project_Persona/llama_cpp/build/bin
```

**Git template (`D:\Projects\Git\Project_Persona\run\llama-servers.env`):** has `SCIENTIST_PORT=8081` (stale), and is missing the `LLAMA_LIB_DIR` line entirely.

**Root cause:** AIP TODO #24 — `~/Git/sterilize.sh` does not yet handle Project_Persona, so hand-edits in Live don't propagate to the Git template. Until sterilize is updated, this drift will keep happening.

Resolution sequence is in §7 below.

---

## 6. Updated Borrow Specs — Deltas Only

Only the deltas from the original handoff §5 are restated here. Anything not mentioned stands as originally written.

### B1 — Second Brain (deltas)

- **Confidence default: 0.7. Reject branch: < 0.3.** Drop 0.55 / 0.65 references.
- **Add `SECOND_BRAIN_MAX_RECORDS` equivalent** — a hard cap on stored facts to prevent unbounded growth.
- **Day-window ladder:** decide between Mercury's 5-tier (7/14/21/42/120) and PP's simplified 2-tier. Document either choice.
- **Configuration model:** decide YAML (Mercury parity, lives at `~/.mercury/mercury.yaml` analogue) or env var (PP's existing pattern). The original handoff used env vars by default — confirm or override.

### B2 — Daemon (deltas)

- Restart policy: `Restart=on-failure` confirmed verbatim from Mercury.
- Cross-platform scope: PP can stay Linux-only systemd; macOS launchd is out of scope **as a deliberate decision**, not an oversight.
- "Fail open" definition still owed (raised in original review).

### B3 — Permission Hardening (deltas)

- **Add `chmod 777` to blocklist.** Updated full list: `sudo`, `rm -rf /`, `mkfs`, `dd if=`, `chmod 777`, `:(){`.
- `approve_scope` and `approve_command` both confirmed real — original handoff design stands.
- Bundle B3 with **all four** `/agent/run` bugs in §4.1, not just the async fix:
  1. `subprocess.run` → `asyncio.create_subprocess_exec`
  2. Relative path → AI_ROOT-based absolute
  3. Implement `tools/taskman2.py` per the contract in AIP_knowledge.md (input/output paths, CLI signature, 300s timeout)
  4. Unify with the `_job_set` / `_load_persisted_jobs` jobs dict (System 1) so there's one job system, not two

### B4 — Telegram (deltas)

- Pick polling vs webhook **explicitly** in the spec — both are supported. Recommend long polling for self-hosted/NAT.
- If pairing code is persisted, **hash it with bcrypt or equivalent** (Mercury uses `bcryptjs`).

---

## 7. Live → Git Port and Sterilize Workflow

This consolidates the EVO-X2 Live state into the public Git template in one pass and updates `sterilize.sh` to handle Project_Persona going forward.

**Files needed before this can be finalized:**
- Current `~/Git/sterilize.sh` (per tenant #3 — do not modify without a recent copy)
- Current `~/Git/Project_Persona/.gitignore` (to confirm models/, data/, run/*.pid, run/*.sock, env/, openwebui/, logs/ are excluded)
- Current `scripts/start_llama_servers.sh` (to confirm `LLAMA_LIB_DIR` use is consistent)

### 7.1 Pre-flight verification (run on EVO-X2)

```
cd ~/Live/AIStack/Project_Persona && git status
cd ~/Git/Project_Persona && git status
diff -rq ~/Live/AIStack/Project_Persona ~/Git/Project_Persona | grep -vE "^Only in.*(\.git|env|env_webui|openwebui|models|data|logs|run/.*\.(pid|sock|jsonl)|services/chromadb)" | head -40
```

The diff command excludes runtime state, virtualenvs, models, ChromaDB data, logs, and PID/socket/jobs.jsonl files. What's left is real source drift between Live and Git that needs porting.

### 7.2 Port files Live → Git (rsync, dry-run first)

```
rsync -avn --delete \
  --exclude=".git/" \
  --exclude="env/" \
  --exclude="env_webui/" \
  --exclude="openwebui/" \
  --exclude="models/" \
  --exclude="data/" \
  --exclude="logs/" \
  --exclude="services/chromadb/" \
  --exclude="run/*.pid" \
  --exclude="run/*.sock" \
  --exclude="run/jobs.jsonl" \
  --exclude="run/jobs/" \
  --exclude="*.pyc" \
  --exclude="__pycache__/" \
  ~/Live/AIStack/Project_Persona/ ~/Git/Project_Persona/
```

Review the dry-run output. When it looks right, drop `-n`:

```
rsync -av --delete \
  --exclude=".git/" \
  --exclude="env/" \
  --exclude="env_webui/" \
  --exclude="openwebui/" \
  --exclude="models/" \
  --exclude="data/" \
  --exclude="logs/" \
  --exclude="services/chromadb/" \
  --exclude="run/*.pid" \
  --exclude="run/*.sock" \
  --exclude="run/jobs.jsonl" \
  --exclude="run/jobs/" \
  --exclude="*.pyc" \
  --exclude="__pycache__/" \
  ~/Live/AIStack/Project_Persona/ ~/Git/Project_Persona/
```

### 7.3 Sterilize pass

Once `sterilize.sh` is updated to handle Project_Persona (see §7.5), run it:

```
cd ~/Git
./sterilize.sh Project_Persona
```

Without that update, manual sterilization needed for at least:

- `run/llama-servers.env` line 44: `LLAMA_LIB_DIR=$HOME/Live/AIStack/Project_Persona/llama_cpp/build/bin` → replace `$HOME/Live/AIStack/Project_Persona` with `<PROJECT_ROOT>` placeholder
- Any hardcoded `festro33` or `~/Live/` references in scripts → replace with `<OWNER_NAME>` and `<PROJECT_ROOT>` tokens per AIP_knowledge.md convention
- Verify `.gitignore` covers `models/`, `data/`, `run/*.pid`, `run/*.sock`, `run/daemon.sock`, `run/jobs.jsonl`, `run/jobs/`, `env/`, `env_webui/`, `openwebui/`, `logs/`, `services/chromadb/`, `*.pyc`, `__pycache__/`

### 7.4 Verification before commit

```
cd ~/Git/Project_Persona
grep -rE "(festro33|/home/festro|~/Live/AIStack)" \
  --include="*.sh" --include="*.py" --include="*.env" --include="*.md" \
  --exclude-dir=.git . || echo "Clean — no live paths leaked"
git diff --stat
git diff run/llama-servers.env
```

The grep should return no matches if sterilization is complete. The diff should show:
- `run/llama-servers.env`: `SCIENTIST_PORT 8081 → 8083`, `LLAMA_LIB_DIR` line added (with placeholder)
- `services/api/server.py`: any divergence between Live and Git template (likely several lines)
- AIP_knowledge.md / KNOWLEDGE.md: TODO closures from §4.3 above
- Any other source drift identified in §7.1

### 7.5 Updated `sterilize.sh` for Project_Persona

**This requires the current `~/Git/sterilize.sh` before I can write the patch.** Per tenant #3, I will not modify a config/script file without a recent copy.

Outline of what the AIP_ entry needs to do:

1. Replace `/home/festro33`, `$HOME/Live/AIStack/Project_Persona`, and any `festro33`/`festro` username references with the existing `<OWNER_NAME>` and `<PROJECT_ROOT>` token convention used for Netstack
2. Reset `run/llama-servers.env` ports to canonical Git values (8083 confirmed correct, 8081 bug fix retained)
3. Strip any local-only env exports from `start_*.sh` if present
4. Verify `.gitignore` coverage matches §7.3
5. Optionally: validate that no `models/`, `data/`, or `services/chromadb/` content exists in the Git template after rsync (these are runtime-only, never templated)

**Send me the current `sterilize.sh` and I'll write the patch.**

### 7.6 Commit + tag

```
cd ~/Git/Project_Persona
git add -A
git status
git commit -m "Sync Live → Git: port server.py, env, scripts; close obsolete TODOs"
git tag -a v1.2-live-sync -m "Live state consolidated into Git template 2026-04-27"
git push origin main --tags
```

### 7.7 Permissions

After rsync, executable bits on `*.sh` should be preserved by rsync `-a`, but verify:

```
chmod +x ~/Git/Project_Persona/scripts/*.sh
chmod +x ~/Git/Project_Persona/run/persona.sh 2>/dev/null || true
```

---

## 8. TODO Reconciliation

### 8.1 Close as obsolete / done

| Doc | TODO | Reason |
|---|---|---|
| KNOWLEDGE.md | #3 — Wire persona.md + system_rules.md into build_persona_prompt() | Verified done in live server.py:450 |
| AIP_knowledge.md | #12 — Same as above | Same |
| KNOWLEDGE.md | #1 — Rename scientist → reasoning | Reverse direction; code is canonical "scientist" |

### 8.2 Upgrade priority — confirmed regressions or live bugs

| Doc | TODO | Update |
|---|---|---|
| AIP_knowledge.md | #11 — Verify looks_degenerate() | Now confirmed gone. Reframe as: **decide reinstate vs accept absence**. Mercury work should not assume it exists. |
| AIP_knowledge.md | #6 — start_api.sh MEMORY_DISTILL_ENABLED ordering | Still present in live; **High** priority unchanged |
| AIP_knowledge.md | #8, #9 — /agent/run async + path | Still present; bundle with B3 per §6 |
| AIP_knowledge.md | #5 (implied) — taskman2.py | Endpoint still references missing executor; B3 must implement it |
| New | SCIENTIST_PORT fallback hardening | server.py:42 and start_api.sh:41 default to 8081. Either change to 8083 or fail loud if unset. |
| New | AI_ROOT default in server.py:34 points to `~/AI` | Stale post-migration |

### 8.3 New from this addendum

| # | Item | Priority | Source |
|---|---|---|---|
| A1 | Update `~/Git/sterilize.sh` to handle Project_Persona | High | §7.5 — needed before any further Live→Git syncs |
| A2 | Run Live → Git rsync per §7.2 | High | §7 |
| A3 | Decide: reinstate `looks_degenerate()` or document its absence | Medium | §4.2 |
| A4 | SSE streaming in `/v1/chat/completions` (AIP TODO #4) | High | SillyTavern blocker; precedes Mercury work |
| A5 | Decide: B1 config = YAML or env vars | Medium | §3.3 |
| A6 | Decide: B1 day-window ladder = 5-tier or 2-tier | Medium | §3.3 |
| A7 | Add `SECOND_BRAIN_MAX_RECORDS` equivalent to B1 design | Medium | §3.3 |
| A8 | Add `chmod 777` to B3 blocklist | Low (small) | §3.3 |
| A9 | Pick Telegram transport (polling vs webhook) for B4 | Low | §3.2 |

---

## 9. Open Questions Pending (still owed from original handoff §9)

- **Q1** — Second Brain scope (global / per-profile / hybrid). Recommendation stands: hybrid.
- **Q2** — Extraction model choice. Recommendation stands: scientist (port 8083).
- **Q3** — Telegram ownership model. Recommendation stands: single owner.
- **Q4** — Daemon orchestration scope. Recommendation stands: Option B (llama servers as independent systemd units; daemon.py manages API + workers + channels). **Note:** if Q4 lands on Option B, KNOWLEDGE.md / AIP_knowledge.md daemon.py spec needs amendment — current spec lists llama servers as daemon children.

New question added by this addendum:

- **Q5** — Knowledge-doc consolidation: KNOWLEDGE.md and AIP_knowledge.md have diverged. AIP_knowledge.md aligns with the live code. Either retire KNOWLEDGE.md or merge into AIP_knowledge.md as the single source of truth. **Recommendation:** retire KNOWLEDGE.md, keep AIP_knowledge.md.

---

## 10. Sign-off Status

**Approval needed before implementation begins:**
- [ ] Q1 — Second Brain scope (global vs per-profile vs hybrid)
- [ ] Q2 — Extraction model choice (persona vs scientist)
- [ ] Q3 — Telegram ownership model
- [ ] Q4 — Daemon orchestration scope (and resulting KNOWLEDGE.md amendment if Option B)
- [ ] Q5 — Knowledge-doc consolidation (retire KNOWLEDGE.md or merge)
- [ ] A5 — B1 config: YAML or env vars
- [ ] A6 — B1 day-window ladder
- [ ] Lemonade benchmark sequencing — unchanged from original

**Files Brandon should provide before next session:**
- Current `~/Git/sterilize.sh` (required for §7.5 patch)
- Current `~/Git/Project_Persona/.gitignore` (verification for §7.3)
- Current `scripts/start_llama_servers.sh` (consistency check on `LLAMA_LIB_DIR`)

**Recommended first session focus (revised from original):**
A1 (sterilize.sh update) + A2 (rsync Live → Git) — closes the env-file drift permanently and consolidates the source of truth before any Mercury code lands. M5 (`/agent/run` async + path fix bundled into B3) follows.

---

*End of addendum. Both this document and the original 1545 handoff should be retained — this addendum amends, it does not replace.*
