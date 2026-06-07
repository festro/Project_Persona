# Handoff -- Project_Persona -- T1 (Qwen3.6 swap foundation)

Date: 2026-06-04 0055 PDT
Authors: Brandon + Claude
Scope: T1.1 (env_hermes venv + ops-script awareness) and T1.2 (per-profile Hermes
safe-config config.yaml), plus the T1 acceptance gate in doctor.sh.
Status: IMPLEMENTED and verified in sandbox. One deploy-time step (actual
env_hermes install) and one H1 validation (Hermes key-path exactness) remain open.

---

## 1. Context / why this session

T0 closed fully on 2026-06-03 (T0.1 model-loads PASSED 2026-05-18; T0.2
tool-calling PASSED 2026-06-03). With both sub-gates green, the Qwen3.6 swap was a
pure priority call with no remaining test gate. This session committed to the swap
track and executed T1, the foundation tier:

- T1.1: stand up an isolated `env_hermes` venv (same isolation pattern as
  `env_webui`) and make the ops scripts aware of it.
- T1.2: generate a per-profile Hermes `config.yaml` that is safe-config-conformant
  by construction (local-only, no cloud egress) and carries Qwen3.6 sampling.

T1.1 and T1.2 are independent (parallel-OK per the tiered plan). The tier gate:
`doctor.sh` confirms env_hermes installed AND the default profile config.yaml
conforms to the safe-config schema.

## 2. What changed (files)

New (tracked):
- `persona/profiles/default/config.yaml` -- shipped safe-config artifact.
- `persona/profiles/test/config.yaml` -- same.
- `archive/handoffs/handoff_persona_20260604_0055.md` -- this file.

Edited:
- `scripts/init_profiles.sh` -- added `write_hermes_config()` and a call in the
  per-profile normalize loop. Idempotent (skips if config.yaml exists, so it never
  clobbers Hermes-managed edits). Parameterized by PERSONA_HOST (127.0.0.1),
  PERSONA_PORT (8090), PERSONA_HERMES_MODEL (qwen3.6-35b-a3b). AI_ROOT default
  flipped to `$HOME/Git/Project_Persona`.
- `scripts/setup_native_stack.sh` -- after the API venv, creates `env_hermes` and
  runs `pip install hermes-agent`. Guarded by SKIP_HERMES=1; non-fatal on failure
  (prints manual-install guidance). AI_ROOT default flipped.
- `scripts/status.sh` -- new "Hermes:" section: env_hermes venv presence, hermes
  binary presence, default profile config.yaml presence.
- `scripts/doctor.sh` -- new env_hermes venv check; new "Safe-config conformance
  (T1 gate)" section; AI_ROOT default flipped.

## 3. The safe-config schema (what doctor.sh enforces)

Invariants asserted against the default profile config.yaml:

1. `model.provider == custom`
2. `model.base_url` is local (http://127.0.0.1: or http://localhost:)
3. `model.api_key` is not a real secret (not-needed / local / ${VAR})
4. `fallback_model` is empty -- no cloud failover
5. every `auxiliary.<task>.provider == main` -- side tasks ride the local endpoint
6. `tools.disabled` includes web_search, web_extract, web_crawl and a browser_* entry

Checker prefers env_hermes python, then env python, then any python3 with PyYAML;
falls back to grep-based checks if no PyYAML is present. Output line:
`T1 GATE: env_hermes_installed=<yes/no> safe_config=<pass/fail>`. Set STRICT_GATE=1
to make a non-green gate exit 2 (for CI / pre-handoff verification).

Rationale: this is the construction-time half of the Hermes egress containment
strategy from HANDOFF_2026-05-11 (Appendix A). The runtime half (H1.6 kernel-level
egress containment via ip netns / iptables, plus daemon env hygiene that never
inherits cloud creds) is still required and is NOT in scope for T1.

## 4. Qwen3.6 sampling (in config.yaml under model.sampling)

- default (non-thinking): temperature 0.7, top_p 0.8, top_k 20, min_p 0.0,
  presence_penalty 1.5 (the presence_penalty helps the mild repetition seen in the
  2026-06-03 smoke test).
- thinking: temperature 0.6, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0
  (high penalties are avoided in thinking mode to prevent language mixing).

These follow Qwen3 upstream sampling guidance.

## 5. Verification performed (sandbox)

- `bash -n` syntax: all four edited scripts pass.
- PyYAML parse: both shipped config.yaml files parse.
- ASCII: shipped configs and the init_profiles heredoc are ASCII-clean.
- Generator dry-run (AI_ROOT=temp): init_profiles.sh produced conformant
  config.yaml for a fresh profile (alpha) and default; base_url and auxiliary
  providers correct.
- Gate positive: doctor.sh against the real default config -> `safe_config=pass`.
- Gate negative: a tampered config (cloud fallback + cloud auxiliary) ->
  VIOLATION lines + `safe_config=fail`.
- shellcheck: not installed in sandbox; only `bash -n` was run. Recommend running
  shellcheck on the four scripts on a dev box before commit.

## 6. Open items

T1 close-out (deploy-time, needs network + target host):
- Actually create env_hermes and install hermes-agent on the target
  (EVO-X2 native and/or the Windows portable host): run
  `scripts/setup_native_stack.sh` (or `SKIP_DEPS=1 SKIP_HERMES=0` to only add the
  venv). Then `doctor.sh` should report env_hermes_installed=yes. Until then the
  gate is "safe_config=pass, env_hermes_installed=no".

H1 validation (must confirm before trusting the config in production):
- Validate exact Hermes key paths against the installed hermes-agent:
  `model.sampling.{default,thinking}.*` and `tools.disabled` are
  schema-PROVISIONAL. Current docs confirm model.provider/base_url, auxiliary
  provider:main, fallback semantics, and secrets-in-.env; they did NOT confirm the
  per-mode sampling block or the exact tool-whitelist key. Run `hermes config
  check` against a profile to surface unrecognized keys, and reconcile.
- Confirm HERMES_HOME resolves to the profile dir (Hermes default is ~/.hermes;
  the daemon/launcher must set HERMES_HOME=persona/profiles/<name> per profile).

Pre-existing drift surfaced, NOT fixed here (logged in todo.md):
- `setup_native_stack.sh` still writes the retired multi-server llama-servers.env
  (PERSONA/REASONING/CODER on 8080/8081/8082). Running it as-is would overwrite the
  good unified `run/llama-servers.env` -- a clobber hazard. Modernize to the
  unified topology (single persona on 8090) before this script is used on a live
  host.
- `init_profiles.sh` still scaffolds the retired 3-file profile
  (persona.md/style.md/system_rules.md); `doctor.sh` still checks those files and a
  scientist port. The project moved to SOUL.md + .hermes.md in M5 (2026-05-17).
  These are warns, not gate failures, but should be modernized.

## 7. Next (swap track)

With T1 implemented, the swap proceeds to T2 (core integration: server.py / launch
wiring to consume the per-profile config and Qwen3.6 sampling; reasoning-channel
handling now that T0.2 showed llama.cpp puts reasoning in `reasoning_content` under
--jinja). T3 is hardening (doctor integration checks + egress audit incl. the H1.6
packet-capture). See knowledge.md "Architecture roadmap" and the tiered plan in
HANDOFF_2026-05-15_0127.

## 8. Commit guidance (git runs Windows-side)

Per the standing rule, run git from Windows portable git, not the sandbox mount:

    $env:Path = "D:\Projects\Tools\PortableGit\cmd;" + $env:Path
    cd D:\Projects\Git\Project_Persona
    git add scripts/init_profiles.sh scripts/setup_native_stack.sh scripts/doctor.sh scripts/status.sh persona/profiles/default/config.yaml persona/profiles/test/config.yaml archive/handoffs/handoff_persona_20260604_0055.md knowledge.md todo.md changelog.md
    git status
    git commit -m "T1: env_hermes venv + per-profile Hermes safe-config + doctor gate"

config.yaml is intentionally tracked (it carries no secrets; secrets live in
Hermes .env). env_hermes/ is already gitignored.

---

Frozen handoff record. Future revisions create a new dated handoff.
