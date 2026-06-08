# Handoff -- Project_Persona

Date/time: 2026-06-08 1029 PDT
Author: Claude (with Brandon)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
Status of repo: origin/main advanced this session (T2.4 + provisioner bundle pushed;
config.toml [linux] -> Qwen3.6 pushed from EVO-X2). EVO-X2 and Windows both on the
single model. Doc updates for THIS handoff are the remaining local edits to commit
Windows-side.

================================================================================
MILESTONE: EVO-X2 SINGLE-MODEL CONVERGENCE (M6 closed)
================================================================================

EVO-X2 (Daemonic-evox2, AMD Strix Halo) now runs the single model
Qwen3.6-35B-A3B-UD-Q5_K_XL -- the same model as Windows -- completing the
2026-06-07 "single model everywhere" directive. M6 is closed; the Hermes H-track
is unblocked.

Whole thing was done over SSH via relay (no SSH MCP connector exists in the
registry; relay = Claude writes command blocks, Brandon runs + pastes).

================================================================================
WHAT WAS DONE (in order)
================================================================================

1. CODE SYNC. EVO-X2 was on M5-era code (61790de). Fast-forwarded to origin/main
   (8e4b92b), then to 11e2948 after Windows pushed: (a) the T2.4 payoff + offline
   self-test logging (commit ccd4991), and (b) the previously-uncommitted 06-07
   bundle -- Model Provisioner P1/P2, doc reconciliation, manage.py detection,
   .gitignore tools/*.json. Both were one-off authorized push exceptions to converge
   EVO-X2. tools/taskman.py + taskman2.py confirmed tracked.

2. LLAMA.CPP BUMP (the gate). EVO-X2's old llama-server was stale/broken (Apr-1
   binary, missing libmtmd.so.0, build < b8770 so no qwen3_5_moe arch). The in-repo
   llama_cpp/ source is old vintage and NOT updated by the sync, so:
   - Fresh clone: ~/src/llama.cpp at tag b9219 (matches Windows; proven on Qwen3.6).
   - Build: cmake -B build -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release; cmake --build.
   - NEW BUILD DEP (Ubuntu 24.04): configure failed at find_package(SPIRV-Headers).
     Fix: `sudo apt-get install -y spirv-headers spirv-tools`. (cmake 3.30.5, gcc
     13.3, vulkan-dev 1.3.275, glslc were already present.) Recorded in
     docs/llama_build_matrix.md.
   - Wire: symlink llama_cpp/build -> ~/src/llama.cpp/build (old tree moved to
     llama_cpp/build.stale.<ts>). manage.py finds it via the default
     llama_cpp/build/bin path + LD_LIBRARY_PATH; no config edit needed.

3. MODEL SWAP. config.toml [linux] PERSONA_MODEL -> Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
   (PERSONA_CTX kept 32768, GPU_LAYERS 999). Committed + PUSHED from EVO-X2.

4. VENV REFRESH. EVO-X2 API runs from env/bin/python (native py3.12.3). Reinstalled
   services/api/requirements.txt (lean fastembed tier) -- pip exit 0.

5. VALIDATED LIVE (EVO-X2):
   - llama-server loads qwen3_5_moe (the whole point of the bump), /health green.
   - API /health green: embedder_ok (fastembed) + chroma_ok true; persona_use_messages
     + persona_sanitize_messages present (= running the T2.4 server.py).
   - default /chat (messages OFF): coherent persona answers in the Daemonic voice +
     2-part format.
   - messages path (PERSONA_USE_MESSAGES=1) /chat with preserve_thinking: reasoning
     populated from server reasoning_content, sanitizer_applied=false -> T2.4
     live-proven on EVO-X2 too. Profiles (SOUL.md) load.

6. Instruct-2507 moved to models/archive/ as rollback. Stack left UP steady-state
   (messages OFF default), Qwen3.6.

================================================================================
FINDINGS / GOTCHAS (carry forward)
================================================================================

- HARDWARE: EVO-X2 is 96 GB unified, but the BIOS carves out iGPU VRAM so the OS /
  `free -h` shows ~62 GiB system RAM. Size GPU memory from manage.py capabilities
  vram_mb; system RAM from free separately. (knowledge.md corrected.)
- THINKING TOKEN BUDGET (tunable): with thinking ON (messages path / enable_thinking),
  the default PERSONA_MAX_TOKENS=192 STARVES the answer -- the CoT eats the whole
  budget and `text` returns empty. Needs >= ~4096 (at 4096 the reasoning concluded and
  a full answer emitted; 192 and 1024 both truncated mid-thought). The default raw
  path (messages OFF) is unaffected and stays short. Decide whether to raise the
  default or document per-deployment.
- SHALLOW-CLONE COSMETIC: `--depth 1` makes llama-server --version report
  `version: 1 (45b455e)`; 45b455e IS tag b9219. Functionally correct; only the mesh
  capability metadata string is wrong. Fix via full clone or -DLLAMA_BUILD_NUMBER=9219
  if/when mesh version-skew tracking matters.
- RAW-PATH VARIANCE (watch): the raw /completion path occasionally returns an
  empty/unusable reply -> sanitize_persona_reply emits its placeholder ("I can help
  with local, offline assistance..."). Intermittent (2 of 3 retries clean). Matches
  the documented advisory-/think variance; not a defect.
- HOUSEKEEPING: models/archive/*.gguf is not covered by the `models/*.gguf` ignore
  (only top-level). Consider adding `models/archive/` (or `models/**/*.gguf`) to
  .gitignore so the archived 21 GB Instruct file can't be accidentally staged.

================================================================================
COMMIT STATE
================================================================================

PUSHED to origin/main this session:
  - ccd4991  T2.4 payoff + offline self-test logging (Windows).
  - 11e2948  06-07 provisioner P1/P2 + doc reconciliation bundle (Windows).
  - (EVO-X2) config.toml [linux] -> Qwen3.6 convergence commit.

LOCAL, to commit Windows-side (this handoff's doc updates): changelog.md (1029 entry),
roadmap.md (M6 [x]), todo.md (stamp + just-finished + EVO-X2 state + Next #3 done),
knowledge.md (hardware carve-out + convergence + thinking tunable),
docs/llama_build_matrix.md (spirv-headers dep + shallow-clone note), and this file.
On Windows: `git pull --ff-only` (gets the EVO-X2 config commit) THEN commit + push
these docs.

Git: D:\ Windows clone runs git Windows-side (portable git). EVO-X2 runs its own
native git (used for the config push). Do NOT git the D:\ repo from the sandbox.

================================================================================
NEXT (queue, see todo.md "Next (in order)")
================================================================================

- MODEL PROVISIONER P3/P4 (Phase 0.5): HF downloader + license/disk preflight +
  config wiring (P3); manage.py `provision` + first-run hook (P4). Re-verify
  run/model_playbook.toml repo IDs/filenames/quant sizes vs live HF pages first.
- Hermes H-track (H1...) -- now UNBLOCKED (M6 closed). H1 owns the config.yaml schema
  validation against the installed hermes-agent.
- Optional tuning: decide on the PERSONA_MAX_TOKENS thinking budget; the b9219
  shallow-clone version string; models/archive gitignore.
