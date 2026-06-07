# HANDOFF: Qwen3.6 Windows Prototype — T0.1 Smoke Test Runbook

**Session date:** 2026-05-17 1130 PDT
**Repo:** github.com/festro/Project_Persona
**Status:** Launcher script + .gitignore updates landed on Windows-side. Model + binary downloads + actual launch on user.
**Branch:** `main` (uncommitted; stacks on top of 1430 canonicalize + 1730 M5 commits)
**Predecessor handoff:** `archive/handoffs/HANDOFF_2026-05-17_1030_m5-server-py-migration.md`

---

## Executive summary

Opens the **T0.1 GO/NO-GO gate** from `archive/handoffs/HANDOFF_2026-05-15_0127_compat-reeval-tiered.md` — empirical test that llama.cpp's `qwen3_5_moe` architecture loads and generates coherent output. Target hardware: Windows daily-driver with a discrete AMD GPU (16 GB VRAM), Git Bash as the shell. Model: **Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf** (Unsloth Dynamic, 26.6 GB, native 262K context) from the main `unsloth/Qwen3.6-35B-A3B-GGUF` repo.

**Model file:** `Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf` (26.6 GB) from the main `unsloth/Qwen3.6-35B-A3B-GGUF` repo. After Windows smoke test passes, the file is `scp`'d to EVO-X2 so we don't have to re-download (Step 6).

> **MTP variant note (deferred):** Unsloth publishes a separate `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` repo with a `UD-Q5_K_M` variant (27.1 GB) plus multi-token-prediction draft tokens. That path unlocks `--spec-type mtp --spec-draft-n-max 3` for 1.5-2× speculative-decoding speedup, but the repo banner reads "Do not download yet" and the MTP flags require a custom llama.cpp build from the MTP PR branch. Out of scope for T0.1; revisit after the K_XL prototype proves the arch.

This is intentionally **just the llama-server smoke test** — no FastAPI Companion, no OpenWebUI. Once T0.1 passes the runbook below should run end-to-end in well under an hour (most of which is the 26.6 GB download).

Scope after this gate:

- T0.2 (tool-calling round-trip) — follow-up session, gates Hermes integration.
- Backporting Qwen3.6 + qwen3_5_moe support to EVO-X2 if performance is strong enough — separate decision.

---

## What landed in the repo this session

| File | Purpose |
|---|---|
| `windows_portable_setup.bat` | Double-click Stage 1 setup. Downloads PortableGit via Windows-bundled curl + GitHub API, extracts it to `portable/PortableGit/`, hands off to bash for Stage 2. |
| `windows_portable_run.bat` | Double-click launcher. Adds portable Git tools to PATH for this session only (no system PATH modification), opens bash, runs `scripts/start_llama_server_win.sh`. |
| `scripts/portable_setup_win.sh` | Stage 2 setup script. Downloads latest llama.cpp Windows-Vulkan zip + Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf (26.6 GB). Idempotent — re-running skips already-present files; partial downloads resume. |
| `scripts/start_llama_server_win.sh` | Git Bash launcher — runs `llama-server.exe` with Vulkan device pinning, 4 parallel slots, q8_0 KV cache, env-overridable knobs. Default `GPU_LAYERS=35` for 16 GB VRAM. Default `MODEL_FILE=Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf`. |
| `.gitignore` | Added `portable/` (PortableGit tree) and `llama_cpp/windows/` (extracted prebuilt binary tree). Existing `models/*.gguf`, `run/*.pid`, `logs/` already cover the rest. |
| This handoff | The runbook + verification list below. |

---

## Zero-install portable mode (recommended for daily use)

Everything self-contained inside `D:\Projects\Git\Project_Persona\`. No system installs, no Git for Windows install, no Python install. Two double-clicks: one to set up, one to run.

### One-time setup

Double-click `windows_portable_setup.bat`. It will:

1. Resolve the latest PortableGit release via the GitHub API (`api.github.com/repos/git-for-windows/git/releases/latest`).
2. Download the `PortableGit-*-64-bit.7z.exe` self-extractor (~55 MB) via Windows-bundled `curl.exe`.
3. Extract it silently into `portable/PortableGit/`.
4. Hand off to portable bash to download llama.cpp Windows-Vulkan binaries (~30 MB) and the Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf model (26.6 GB).

Total download: ~27 GB. Resumable — if interrupted, just re-run `windows_portable_setup.bat` and curl picks up where it left off (via `-C -` on the model file).

Prereqs (already on Windows 10 1803+ and Windows 11):

- `curl.exe` in PATH — bundled with Windows since 1803.
- `powershell.exe` in PATH — for one GitHub API call to find the PortableGit URL.
- Working AMD GPU driver — provides Vulkan runtime (`vulkan-1.dll`); no separate Vulkan SDK install needed.

The setup writes nothing outside the project tree. Removing the project folder fully removes the install.

### Run

Double-click `windows_portable_run.bat`. It:

1. Prepends `portable/PortableGit/bin`, `portable/PortableGit/usr/bin`, `portable/PortableGit/mingw64/bin` to `PATH` (session-scoped only — the change disappears when the window closes).
2. Converts the Windows project root to its POSIX path via portable `cygpath`.
3. Launches `scripts/start_llama_server_win.sh` under portable bash, exporting `AI_ROOT` so the script auto-locates everything.

llama-server.exe runs in the background. Pidfile at `run/persona_win.pid`. Log at `logs/persona_win.log`. The bash window stays open showing the launcher's exit status.

### Verify portable mode is working

Once `windows_portable_setup.bat` reports `SETUP COMPLETE`:

```
dir portable\PortableGit\bin\bash.exe
dir llama_cpp\windows\llama-server.exe
dir models\Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
```

All three should exist. Then double-click `windows_portable_run.bat` and follow Step 4 below to smoke-test against `http://127.0.0.1:8080/v1/chat/completions`.

### Why two .bat files (Stage 1 + Stage 2)?

`windows_portable_setup.bat` runs in `cmd.exe` and uses only Windows-bundled tooling (curl, PowerShell, the 7z self-extractor). Once PortableGit is on disk, the rest of setup (`scripts/portable_setup_win.sh`) runs under portable bash, which is far more comfortable for parsing GitHub API JSON, handling resumable downloads, and extracting zip files. The .bat is the bootstrap; bash is the workhorse.

### Manual flow (if you'd rather do it by hand)

The sections below (Pre-flight, Step 1-6) describe the same operations the .bat files automate. Use them if you want full control, are debugging a setup issue, or already have Git for Windows installed system-wide and don't need the portable copy.

---

## Pre-flight — confirm Windows host has the prerequisites

Open Git Bash (the one that ships with Git for Windows) and run:

```
which bash && bash --version | head -1
which curl
python --version || python3 --version
df -h /d/Projects/Git/Project_Persona | tail -1
```

Acceptance:

- Git Bash 4.x or newer
- `curl` resolves (Git Bash ships with it)
- Python 3.8+ available — needed only for the `huggingface-cli` model download
- ≥ 35 GB free on `D:\` for the 26.6 GB model + extracted binary

If `huggingface-cli` isn't installed: `python -m pip install --user huggingface_hub` (one-time).

---

## Step 1 — Download llama.cpp Windows-Vulkan prebuilt binary

Browse to https://github.com/ggml-org/llama.cpp/releases/latest in a browser.

Find the asset named `llama-b<NNNN>-bin-win-vulkan-x64.zip` (where `<NNNN>` is the build number — anything from b8157 onwards has Qwen3.5/3.6 architecture support; latest as of 2026-05-17 is ~b8770+).

Download into `D:\Downloads\` (or wherever you collect downloads), then extract into the project:

```
mkdir -p /d/Projects/Git/Project_Persona/llama_cpp/windows
cd /d/Projects/Git/Project_Persona/llama_cpp/windows
unzip /d/Downloads/llama-b*-bin-win-vulkan-x64.zip
ls -la llama-server.exe ggml-vulkan.dll
```

Acceptance:

- `llama_cpp/windows/llama-server.exe` exists and is executable.
- `ggml-vulkan.dll` (or similar Vulkan backend DLL) is alongside.

If the zip extracts into a subfolder (some releases nest the bins inside `build/bin/`), either move the files up or set `LLAMA_BIN_DIR=<extracted-subfolder>` when launching.

---

## Step 2 — Download the Qwen3.6 GGUF

26.6 GB download from the main `unsloth/Qwen3.6-35B-A3B-GGUF` repo. Resumable via `huggingface-cli`.

```
cd /d/Projects/Git/Project_Persona
huggingface-cli download unsloth/Qwen3.6-35B-A3B-GGUF \
  --include "Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf" \
  --local-dir models/
ls -la models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
```

Acceptance:

- File exists at `models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf`
- Size approximately 26.6 GB
- File is gitignored by the existing `models/*.gguf` pattern — no chance of accidental commit

(If you'd rather not install `huggingface-cli`, use the direct download from `https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf?download=true` — same file, no resume support in browser downloads.)

**Alternative (MTP variant, deferred):** the `unsloth/Qwen3.6-35B-A3B-MTP-GGUF` repo publishes `UD-Q5_K_M.gguf` (27.1 GB) with multi-token-prediction draft tokens, plus the option to use `--spec-type mtp --spec-draft-n-max 3` for ~1.5-2× speedup IF you also build llama.cpp from the MTP PR branch. Not for T0.1 — revisit after the K_XL prototype works.

---

## Step 3 — Launch llama-server

Dry-run first to confirm config without actually loading the 26.6 GB model:

```
cd /d/Projects/Git/Project_Persona
chmod +x scripts/start_llama_server_win.sh
./scripts/start_llama_server_win.sh --dry-run
```

Expected output shows:

```
Starting llama-server.exe (Windows / Vulkan) on http://127.0.0.1:8080
  bin       /d/Projects/Git/Project_Persona/llama_cpp/windows/llama-server.exe
  model     /d/Projects/Git/Project_Persona/models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
  ctx       16384  parallel=4  gpu_layers=35
  threads   <nproc>  batch=512  ubatch=512
  cache     k=q8_0  v=q8_0
  device    Vulkan0 (GGML_VK_VISIBLE_DEVICES=0)
  log       /d/Projects/Git/Project_Persona/logs/persona_win.log
  [DRY RUN] not launching
```

Then the actual launch:

```
./scripts/start_llama_server_win.sh
```

The script backgrounds the process, writes the pid to `run/persona_win.pid`, and tails the first few lines of the log. The first load takes 30-90 seconds depending on disk speed (24 GB read + GPU upload of 35 layers).

Watch the log live in a separate Git Bash window:

```
tail -F /d/Projects/Git/Project_Persona/logs/persona_win.log
```

Expected key lines in the log:

- `model loaded` somewhere before the server starts listening
- `print_info: model type      = 35B.A3B`
- `print_info: arch             = qwen3_5_moe`  ← **T0.1 gate: this string MUST appear**
- `Vulkan0 = AMD ...`
- `offloaded 35/N layers to GPU` where N is the model's total layer count
- `main: server is listening on http://127.0.0.1:8080`
- `Hermes 2 Pro` or `chatml` chat template auto-detected

If `arch = qwen3_5_moe` does NOT appear, **T0.1 FAILS** — llama.cpp build doesn't support this architecture yet, fall back to the decision branches in `archive/handoffs/HANDOFF_2026-05-15_0127`.

---

## Step 4 — Smoke test curls (T0.1 acceptance)

In a third Git Bash window:

```
curl -s http://127.0.0.1:8080/health
echo ""
```

Expected: `{"status":"ok"}` (or similar — llama-server's native /health, not server.py's).

```
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.6",
    "messages": [{"role":"user","content":"In one sentence: what is photosynthesis?"}],
    "max_tokens": 100,
    "temperature": 0.7,
    "stream": false
  }' | python -m json.tool
```

**T0.1 acceptance:** response is a coherent English sentence about photosynthesis. Not gibberish, not refusal, not `<think>` tag bleed (Qwen3.6 should auto-route trivial queries to non-thinking mode).

Thinking-mode test (should trigger `<think>` block):

```
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.6",
    "messages": [{"role":"user","content":"/think\n\nWhat are three non-obvious reasons MoE models are sensitive to quantization?"}],
    "max_tokens": 400,
    "temperature": 0.7,
    "stream": false
  }' | python -m json.tool
```

Expected: response contains `<think>` ... `</think>` block followed by the actual answer. This validates the prompt-level `/think` directive — same mechanism the M5 server.py rewrite uses for topic-based thinking-mode routing.

Tokens/sec note: on 16 GB VRAM with `GPU_LAYERS=35` you should see **5-15 tok/s** generation. If you see <2 tok/s the offload is too aggressive and VRAM is spilling to system RAM with thrashing — drop to `GPU_LAYERS=30` and restart. If you see no GPU activity at all in Task Manager → Performance → GPU, the Vulkan device pinning didn't take — check the log for which Vulkan device was selected.

---

## Step 5 — Stop the server

```
kill "$(cat /d/Projects/Git/Project_Persona/run/persona_win.pid)"
rm /d/Projects/Git/Project_Persona/run/persona_win.pid
```

Or close the Git Bash window that launched it — the process backgrounds via `&`, so closing the parent shell may or may not orphan it depending on Git Bash's behavior. Explicit kill is cleaner.

---

## Step 6 — scp the verified model to EVO-X2

Once the Windows smoke test passes (T0.1 acceptance — `arch = qwen3_5_moe` in the log + a coherent /v1/chat/completions response), copy the same file to EVO-X2 so we don't re-download 26.6 GB.

### 6a. Pre-flight on the Windows side

Make sure the server isn't currently reading the file (close llama-server.exe first if it's running) and capture a hash:

```
cd /d/Projects/Git/Project_Persona/models
sha256sum Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf | tee /d/Projects/Git/Project_Persona/run/qwen36_xl.sha256.local
```

The hash takes a couple of minutes on a 26.6 GB file. Save the output so we can compare both sides.

### 6b. Confirm EVO-X2 reachability

```
ssh festro33@Daemonic-evox2 'hostname && uname -a && df -h ~/Git/Project_Persona/models | tail -1'
```

Acceptance:

- ssh prompts succeed (key auth or password as you've configured)
- ≥ 30 GB free in `~/Git/Project_Persona/models/` on EVO-X2
- (Optional) confirm the legacy Qwen3-30B-A3B file is still in place: `ssh festro33@Daemonic-evox2 'ls -la ~/Git/Project_Persona/models/'`

### 6c. The transfer

Single scp command:

```
scp -p \
  /d/Projects/Git/Project_Persona/models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf \
  festro33@Daemonic-evox2:~/Git/Project_Persona/models/
```

`-p` preserves the mtime so EVO-X2 doesn't think it's "newer than HuggingFace" if you ever cross-check. Expect ~4-6 minutes on gigabit LAN, longer on slower links.

If scp drops mid-transfer (timeout, kernel sleep, etc.) and you have rsync available in Git Bash (or via MSYS2), use it for resume support:

```
rsync -av --progress --partial \
  /d/Projects/Git/Project_Persona/models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf \
  festro33@Daemonic-evox2:~/Git/Project_Persona/models/
```

### 6d. Verify checksum match

```
ssh festro33@Daemonic-evox2 \
  'cd ~/Git/Project_Persona/models && sha256sum Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf' \
  | tee /d/Projects/Git/Project_Persona/run/qwen36_xl.sha256.evox2
diff /d/Projects/Git/Project_Persona/run/qwen36_xl.sha256.local \
     /d/Projects/Git/Project_Persona/run/qwen36_xl.sha256.evox2
```

Acceptance: `diff` reports zero output (only the filename portion may differ due to `cd` context — compare just the hash hex if needed).

### 6e. What happens next on EVO-X2 — NOT in this session's scope

The file is on EVO-X2 but the unified llama-server is still pointed at Qwen3-30B-A3B-Instruct-2507. Switching to Qwen3.6 on EVO-X2 requires:

1. **llama.cpp version check.** EVO-X2 is at build b8157. Qwen3.5/3.6 (`qwen3_5_moe` arch) had day-1 support, so b8157 *should* work — but verify by checking the EVO-X2 build's git log or just attempt a load. If it fails, upgrade EVO-X2's llama.cpp to match Windows' build version (rebuild from source via the existing CMake setup, or pull a fresh Vulkan-Linux binary if one ships).
2. **Env/launcher swap.** Option (a) one-shot env override: `PERSONA_MODEL=Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf PERSONA_CTX=16384 GPU_LAYERS_PERSONA=999 PERSONA_PARALLEL=4 ./scripts/start_llama_servers.sh`. Option (b) permanent: edit `run/llama-servers.env` and re-launch.
3. **Smoke test on EVO-X2** with the M5 server.py + the same curl battery from Step 4.

Track these as a separate follow-up handoff once T0.1 + scp transfer are done.

---

## Tuning knobs (env vars on the launcher)

All overridable from the command line via `KEY=value ./scripts/start_llama_server_win.sh`:

| Env var | Default | Purpose |
|---|---|---|
| `AI_ROOT` | `/d/Projects/Git/Project_Persona` | Project root in POSIX style (Git Bash) |
| `LLAMA_BIN_DIR` | `$AI_ROOT/llama_cpp/windows` | Where `llama-server.exe` lives |
| `MODEL_FILE` | `Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf` | GGUF filename under `models/`. Override to point at any other variant on disk. |
| `HOST` | `127.0.0.1` | Bind address (don't expose externally) |
| `PORT` | `8080` | Bind port |
| `CTX` | `16384` | Total context across all slots |
| `GPU_LAYERS` | `35` | Layers offloaded to GPU. **Tune for VRAM.** |
| `PARALLEL` | `4` | Concurrent slots |
| `THREADS` | `0` (auto = nproc) | CPU threads |
| `BATCH_SIZE` | `512` | Prompt batch |
| `UBATCH_SIZE` | `512` | Micro-batch |
| `CACHE_TYPE_K` | `q8_0` | K cache quant |
| `CACHE_TYPE_V` | `q8_0` | V cache quant |

Example: more aggressive GPU offload if 16 GB is enough headroom after model load:

```
GPU_LAYERS=42 ./scripts/start_llama_server_win.sh
```

Example: smaller context to free up KV-cache VRAM:

```
CTX=8192 PARALLEL=2 GPU_LAYERS=40 ./scripts/start_llama_server_win.sh
```

---

## Files modified this session

- `scripts/start_llama_server_win.sh` — new, 106 lines, chmod +x.
- `.gitignore` — added `llama_cpp/windows/` line under the existing llama.cpp build artifacts block.
- This handoff.

Nothing on EVO-X2 changes. Existing `scripts/start_llama_servers.sh` (Linux/EVO-X2) is untouched.

---

## Open follow-ups

### Immediate (this session, on Windows)

1. Run pre-flight in Git Bash.
2. Download llama.cpp Windows-Vulkan zip → extract.
3. Download Qwen3.6 GGUF.
4. Dry-run + launch.
5. Smoke-test curls.
6. Report back whether T0.1 passed (model loaded + coherent response) — if it did, we proceed to T0.2 (tool calling).

### Soon (after T0.1)

7. **T0.2** — tool-calling round-trip test against Qwen3.6 on the Windows prototype. Submit an OpenAI-style tool-calling request, observe whether the model emits a parseable tool call. If not, write a GBNF grammar.
8. **MTP speedup (optional follow-up).** With the Q5_K_M file from the MTP repo already on disk, building llama.cpp from the MTP PR branch (`https://github.com/ggml-org/llama.cpp/pull/22673` per Unsloth's README, or the maintainer's `mtp-clean` branch) unlocks `--spec-type mtp --spec-draft-n-max 3` for ~1.5-2× generation speedup. Requires CMake build on Windows — separate scope.
9. **Decision: EVO-X2 backport.** If Windows numbers look strong, upgrade EVO-X2's llama.cpp to the same b<NNNN> release and swap the model. Move Qwen3-30B-A3B-Instruct-2507 to `models/archive/` first as rollback.

### Eventually

9. **Add a Windows-aware row to KNOWLEDGE.md** in the System State table once T0.1 + T0.2 pass — for now Windows is "experimental prototype, no production role."
10. **Mirror the env+launcher canonicalize work for the Windows path** — if Windows becomes a real deployment target (vs ad-hoc experiments), promote the Windows launcher to first-class and document its env file.

---

## Commit + push (run on Windows from `D:\Projects\Git\Project_Persona\`)

Stacks on the two earlier uncommitted commits from this session.

```
git add scripts/start_llama_server_win.sh .gitignore archive/handoffs/HANDOFF_2026-05-17_1130_qwen36-windows-prototype.md
git commit -m "Windows prototype: scripts/start_llama_server_win.sh for Qwen3.6 T0.1 smoke test

Opens the T0.1 GO/NO-GO gate from the 2026-05-15 compat re-eval — empirical test that
llama.cpp's qwen3_5_moe arch loads and generates coherent output. Target: Windows
daily-driver, AMD discrete GPU (16 GB VRAM), Git Bash shell.

- scripts/start_llama_server_win.sh: Git Bash launcher. Vulkan device pinning,
  4 parallel slots, q8_0 KV cache, GPU_LAYERS=35 default for 16GB VRAM. All knobs
  env-overridable. Dry-run support. Pidfile + log under run/ and logs/.
- .gitignore: add llama_cpp/windows/ (the extracted prebuilt binary tree).

Model: unsloth/Qwen3.6-35B-A3B-GGUF Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf (26.6 GB,
Unsloth Dynamic, 262K native context, qwen3_5_moe arch). MTP variant
(unsloth/Qwen3.6-35B-A3B-MTP-GGUF UD-Q5_K_M, 27.1 GB) deferred until after
K_XL prototype confirms the arch loads.

Out of scope here: T0.2 tool-calling, FastAPI Companion on Windows, OpenWebUI.

Refs archive/handoffs/HANDOFF_2026-05-17_1130_qwen36-windows-prototype.md,
archive/handoffs/HANDOFF_2026-05-15_0127_compat-reeval-tiered.md."
```

(You'll have already pushed the 1430 canonicalize + 1730 M5 commits per their respective handoff sections; this is the third commit on top.)

---

## Rollback

If anything in this session causes problems, just don't run the script. The launcher is a new isolated file; the only other change is the gitignore line.

If you've already extracted llama.cpp binaries into `llama_cpp/windows/` and want to wipe:

```
rm -rf /d/Projects/Git/Project_Persona/llama_cpp/windows/
```

The model file in `models/` is yours to keep or delete:

```
rm -i /d/Projects/Git/Project_Persona/models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
```

---

## End

T0.1 acceptance is binary — either `arch = qwen3_5_moe` shows in the log and the chat completion returns coherent English, or it doesn't. Report back which.

Sources:

- [unsloth/Qwen3.6-35B-A3B-GGUF · Hugging Face](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) (main repo — UD-Q5_K_XL 26.6 GB, used here)
- [unsloth/Qwen3.6-35B-A3B-MTP-GGUF · Hugging Face](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF) (MTP variant — UD-Q5_K_M 27.1 GB, deferred follow-up)
- [ggml-org/llama.cpp · Releases](https://github.com/ggml-org/llama.cpp/releases)
- [archive/handoffs/HANDOFF_2026-05-15_0127_compat-reeval-tiered.md] (in this repo)
