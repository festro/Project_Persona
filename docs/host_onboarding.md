# Project_Persona -- Host Onboarding Checklist

Bring a NEW machine (EVO-X2, another Linux box, Windows, or a fresh WSL) up to a working
Project_Persona stack. Ordered, copy-pasteable, ASCII (see `WORKFLOW.md`).

Background you should skim first:
- `WORKFLOW.md`        -- repo roles (origin = offsite backstop; WSL clone = primary dev/run;
                          D:\ = redundant copy + Windows testbed + git gateway) and per-host config.
- `README_models_hardware.md` -- GGUF models, the committed model, where to place files.
- `docs/ipc_decision.md`, `docs/avatar_protocol.md`, `docs/voice_pipeline.md` -- phase-specific.

Endgame target is the EVO-X2 (Vulkan GPU, the canonical `[linux]` config). WSL on the AMD box is
CPU-only and slow (~15-20 min/agent-turn for a 7B) -- fine for dev, not the inference target.

---

## 0. Prerequisites

- Linux/WSL2 (Debian/Mint/Ubuntu family) OR Windows 10 1803+. Native Windows builds via the
  portable installer; Hermes (Phase 8) is WSL2/Linux only.
- git + git-lfs (the repo uses LFS), a C/C++ toolchain (the installer apt-installs these on Linux).
- Disk: ~15-30 GB (llama.cpp build + a 35B Q5 GGUF + venvs).

---

## 1. SSH to GitHub (per-host key -- recommended)

Generate a key ON the new host (do NOT copy one host's private key around unless you must --
per-host keys give per-machine revocation and never travel):

```bash
ssh-keygen -t ed25519 -C "$(whoami)@$(hostname -s) (Project_Persona)" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub          # add this line at github.com -> Settings -> SSH and GPG keys
ssh -T git@github.com              # expect: "Hi festro! You've successfully authenticated"
```

(Reuse path, if you really want one key: `scp ~/.ssh/id_ed25519{,.pub} <user>@<host>:~/.ssh/`
host-to-host, then `chmod 600 ~/.ssh/id_ed25519`. The pubkey is already registered, so it just
works. Never paste a private key into a chat/log.)

---

## 2. Clone the repo (with LFS)

```bash
git lfs install
git clone git@github.com:festro/Project_Persona.git ~/Git/Project_Persona
cd ~/Git/Project_Persona
git lfs pull                        # fetch any LFS-tracked blobs
```

`~/Git/Project_Persona` is the path the installer + scripts default to (AI_ROOT). Use it unless
you have a reason not to.

---

## 3. Build the native stack

### Linux / WSL

`scripts/setup_native_stack.sh` creates the dir structure, apt-installs build deps, clones +
builds llama.cpp (Vulkan if `glslc` is present, else CPU), creates the `env/` venv and installs
`services/api/requirements.txt`, and (unless skipped) sets up the isolated Hermes venv via uv.

```bash
# GPU box (EVO-X2): let it build Vulkan
bash scripts/setup_native_stack.sh

# CPU-only box (e.g. WSL on the AMD host):
CPU_ONLY=1 bash scripts/setup_native_stack.sh
```

Useful env knobs: `AI_ROOT`, `CPU_ONLY=1`, `SKIP_DEPS=1` (no apt), `SKIP_HERMES=1` (no env_hermes),
`AUTO_PROVISION=1` (pick + download a fitted model at the end), `HERMES_SRC`/`HERMES_REPO`.

Optional embedding tier (local RAG embeddings via torch -- heavier):
`pip install -r services/api/requirements-embed-torch.txt` inside `env/`.

### Windows (native)

Run `windows_portable_setup.bat` (downloads PortableGit, hands off to bash for the rest; uses the
Vulkan prebuilt + portable Python under `portable/`). Native Windows does NOT run Hermes.

---

## 4. Provide a model

Models are NOT in the repo (`models/` is gitignored). The committed target is
**Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf** on a GPU box; the `daemonic-pc` CPU/WSL exception runs
Qwen2.5-7B. Either let the provisioner fit + fetch one, or drop a GGUF in `models/` yourself:

```bash
env/bin/python manage.py provision        # profiles the host, picks + downloads a fitted GGUF,
                                          # opt-in wires the config (KV-aware ctx sizing)
# or place models/<your-model>.gguf manually and point the config at it (README_models_hardware.md)
```

---

## 5. Per-host config (only if this host differs)

Config is one committed tree: `run/config.toml` (`[base]` + `[runtime]` + `[<os>]`) plus an
optional **committed** `run/config.<host>.toml` merged on top, selected by `host_tag()` (lowercased
short hostname; `PERSONA_HOST` env overrides). The canonical `[linux]` block IS the EVO-X2 35B
target -- EVO-X2 needs no override file. Add `run/config.<thishost>.toml` only if this host runs a
different model / ports / accel (see `run/config.daemonic-pc.toml` for the CPU-7B example), then:

```bash
env/bin/python manage.py status           # prints host_config=... when an override applies
```

---

## 6. Verify

```bash
env/bin/python manage.py capabilities      # detect accel/RAM/cores -> run/node_capabilities.json
env/bin/python manage.py status            # config + process state
env/bin/python manage.py doctor            # deep health check incl. the T1 safe-config gate
env/bin/python tests/run_all_offline.py    # full offline regression (expect 18/18 suites)
```

Then a live lifecycle:

```bash
env/bin/python manage.py up                # llama-server + API, both /health
curl -sS http://127.0.0.1:8000/health      # rag_backend, task_store, eventbus, sorting_line,
                                          # sleep_cycle, avatar_state blocks all present
env/bin/python manage.py test health
env/bin/python manage.py down
```

---

## 7. Run it

Two ways to bring the stack up:

```bash
# A) operator CLI (what you'll use day to day)
env/bin/python manage.py up                # ... manage.py down to stop

# B) supervised daemon (Phase 3): one asyncio entry point, three-strike restart, fresh logs,
#    hosts the control-plane EventBus on 127.0.0.1:8791
env/bin/python daemon.py                    # Ctrl-C / SIGTERM for a clean shutdown
```

Phase opt-ins on the daemon (off by default):
- `daemon.py --with-hermes`  (or `HERMES_DAEMON_ENABLED=1`) -- supervise the standing Hermes layer:
  the H2 bridge + the H3 dispatcher loop (tools/hermes_dispatch_loop.py, loops the supported
  `hermes kanban dispatch`). Needs `env_hermes/`; both children launched with cloud secrets
  stripped. Makes delegate -> worker -> mirror fully unattended. Phase 8.
- `daemon.py --with-voice`   (or `VOICE_DAEMON_ENABLED=1`)  -- supervise Whisper STT / Piper TTS
  IF their binaries+models are installed (host-side; `docs/voice_pipeline.md`). Phase 5.

---

## 8. Optional surfaces

- OpenWebUI (Phase 2 browser chat UI): `python3 -m venv env_webui && env_webui/bin/pip install
  open-webui==0.9.6`, then `AI_ROOT="$PWD" bash scripts/start_webui.sh` -> http://127.0.0.1:3000
  (points `OPENAI_API_BASE_URL` at the API `/v1`; model id `project_persona`; first visit = admin
  signup). The script defaults DATA_DIR=$AI_ROOT/openwebui (accounts/chats persist in the project),
  ENABLE_OLLAMA_API=false, and keyless DuckDuckGo web search ON (per-message toggle in the chat).
  Set WEBUI_HOST=0.0.0.0 to reach it on the LAN. On EVO-X2 it runs as a systemd --user unit
  (persona-webui), like the persona-daemon.
- Agentic web research: the `researcher` role is web-enabled (keyless ddgs -- install with
  `env_hermes/bin/python -m pip install -U ddgs`); `POST /agent/delegate {"role":"researcher",...}`
  and the worker searches the web when current facts help. Every other role stays egress-off.
- Memory inspection while the API holds the (single-writer) Qdrant store:
  `GET /memory/collections`, `GET /memory/search?collection=..&q=..`, `POST /memory/ingest_inbox`.
  `scripts/ingest_inbox.py` auto-routes through the API when it's up, direct when it's down.
- Sorting Line: drop files in `inbox/` -> the API's background watcher classifies + routes them
  (Phase 6). Sleep Cycle consolidates idle conversations into `persona/global_memory/
  insight_journal.md` (Phase 7).
- Egress containment: `scripts/egress_baseline.sh` (nftables host firewall; root-guarded, scripted
  -- NOT auto-enforced). The daemon already strips cloud secrets from supervised agent children.

---

## 9. EVO-X2 specifics (the inference target)

- Vulkan GPU; serves the committed Qwen3.6-35B-A3B (the `[linux]` config -- no host override file).
- Runs Hermes (Phase 8): env_hermes via uv, GPU-bound worker. The H2d Exit-Gate evidence (delegate
  -> Hermes claims + executes the 35B + writes back, egress-off) is gathered HERE, not on CPU-WSL.
- Apply the kernel egress layer here (`scripts/egress_baseline.sh apply`) for the Phase 8 "egress
  contained at config + kernel level" gate; combine with the daemon env-hygiene runtime layer.

---

## 10. If something's off

- `manage.py doctor` first; it surfaces most setup gaps (missing binary, model, T1 config).
- llama-server not found -> the build failed; re-run the setup script (check `glslc` for Vulkan).
- API /health slow on first boot -> embedder/store init; give it a few seconds.
- Stale-pidfile/orphan quirks under WSL -> see the `WORKFLOW.md` "operational gotchas"; trust
  `/health` + a `ps ... gguf` grep over the pidfile.
- Hermes install needs uv + WSL2/Linux; native Windows is unsupported (run Hermes on EVO-X2).
