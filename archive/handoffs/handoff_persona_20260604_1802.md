# Handoff -- Project_Persona -- T1 close-out + T2 entry point

Date: 2026-06-04 1802 PDT
Authors: Brandon + Claude
Scope: closes the script-drift items left open by handoff_persona_20260603_1608
and handoff_persona_20260604_0055 (the T1 record), and sets the entry point for
T2 (core integration).
Status: T1 IMPLEMENTED + verified. All four ops scripts modernized. T2 not yet
started.

---

## 1. Where the swap track stands

- T0 fully passed (T0.1 2026-05-18, T0.2 2026-06-03). Qwen3.6 swap committed.
- T1 implemented 2026-06-04 (env_hermes venv + per-profile Hermes safe-config +
  doctor.sh gate). See handoff_persona_20260604_0055 for the full T1 record and
  the safe-config schema. Two T1 follow-ups remain OPEN (carried below).
- 2026-06-04..05: closed all script drift surfaced during T1. The four ops scripts
  (setup_native_stack, init_profiles, doctor, status) are now coherent with the
  unified single-server, 2-file-profile, Hermes-ready topology.

## 2. What changed since the 0755 handoff

setup_native_stack.sh (changelog 2026-06-04 1017):
- Env writer no longer emits the retired multi-server llama-servers.env
  (8080/8081/8082 persona/reasoning/coder). Writes the validated unified topology
  (PERSONA_PORT=8090, Instruct-2507 Q5_K_M, ctx 32768, 4 slots, q8_0 KV cache).
- Non-destructive: existing env left untouched; FORCE_ENV=1 overwrites after a
  timestamped .bak. Footer "Next steps" corrected to real script names.

init_profiles.sh + doctor.sh (changelog 2026-06-05 0058):
- init_profiles.sh scaffolds SOUL.md + .hermes.md (M5 convention), not the retired
  persona.md/style.md/system_rules.md. README heredoc lists SOUL.md / .hermes.md /
  config.yaml. config.yaml generation (T1.2) unchanged.
- doctor.sh profile check verifies SOUL.md + .hermes.md + config.yaml; the retired
  scientist port/model removed from every check (env load, model presence, pidfile,
  health, smoke).

Verification (all green): bash -n clean on all four scripts; grep confirms no
remaining persona.md/style.md/system_rules.md or scientist references; init_profiles
dry-run scaffolds SOUL.md/.hermes.md/config.yaml; doctor.sh reports all profile
files present and `T1 GATE: safe_config=pass` (env_hermes_installed=no until the
venv is created on a live host).

Ops note (recurring): the Linux sandbox mount of D:\ repeatedly served stale,
mid-line-truncated views of freshly-edited files and was slow to converge. Trust
the Windows-side file API for content; verify syntax there or via reconstructed
fragments. Reinforces the standing "operate on D:\Projects Windows-side" rule.

## 3. Open items carried into T2

T1 close-out (deploy-time, needs network + target host):
- Create env_hermes and install hermes-agent on EVO-X2 and/or the Windows portable
  host (run setup_native_stack.sh). Until then doctor.sh shows
  env_hermes_installed=no, safe_config=pass.

H1 validation (gates trusting the config.yaml in production):
- Confirm exact Hermes key paths: model.sampling.{default,thinking}.* and
  tools.disabled are schema-PROVISIONAL. Run `hermes config check` against a
  profile; reconcile. Confirm HERMES_HOME resolves to the profile dir.

## 4. T2 -- core integration (next)

Source: tiered plan in HANDOFF_2026-05-15_0127. Sub-items and gates:

- T2.1 Sampling presets in run/config.env + server.py. Per-mode presets; server.py
  selects a preset based on routing + thinking-mode toggle.
  Gate: sampling preset applied matches the per-mode config.
- T2.2 Wire `enable_thinking` through `chat_template_kwargs` to llama.cpp.
  Gate: trivial query -> no `<think>`; non-trivial -> `<think>` present.
  Risk: if llama.cpp's template engine ignores the field, fall back to
  system-prompt injection.
- T2.3 Wire `preserve_thinking: true` for Hermes-originated requests.
  Gate: multi-turn agent loops preserve reasoning across iterations.
- T2.4 `<think>...</think>` stripping at the Task Board -> persona surface
  boundary (single chokepoint). Gate: zero user-facing `<think>`.
  RE-SCOPE: T0.2 showed llama.cpp emits reasoning in a separate
  `reasoning_content` field under `--jinja`, so the user channel is already
  `<think>`-free server-side. Decide whether a persona-side chokepoint is still
  needed (only for non-jinja paths / in-band reasoning) before building it.

Model-state caveat: the live EVO-X2 server runs Instruct-2507, which has NO
thinking mode. T2.2/T2.3/T2.4 only fully exercise once Qwen3.6 is the served
model (Windows portable flow). T2.1 (sampling presets) is model-agnostic and the
natural first increment.

Key code to read first (services/api/server.py): `thinking_prefix()` (/think vs
/no_think by topic), `build_persona_prompt` (gained reasoning_notes + thinking_mode
in M5), the /chat handler, and /v1/chat/completions (currently non-streaming,
ignores `stream`, prompt_tokens hardcoded 0). Sampling currently lives in
llama-server flags (run/llama-servers.env) and start_api.sh env; T2.1 introduces
run/config.env as the consolidation point (see knowledge.md "Runtime tunables").

Suggested T2 order: T2.1 first (config.env + server.py presets, model-agnostic),
then T2.2 (thinking toggle plumbing) once Qwen3.6 is loadable on the test host,
then T2.3, then the T2.4 re-scope decision.

## 5. Commit guidance (git runs Windows-side)

    $env:Path = "D:\Projects\Tools\PortableGit\cmd;" + $env:Path
    cd D:\Projects\Git\Project_Persona
    git add scripts/ persona/profiles/ knowledge.md todo.md changelog.md archive/handoffs/
    git status
    git commit -m "T1 close-out: modernize ops scripts to unified 2-file topology + handoff"

config.yaml is intentionally tracked (no secrets; Hermes secrets live in .env).
env_hermes/ is gitignored.

---

Frozen handoff record. Future revisions create a new dated handoff.
