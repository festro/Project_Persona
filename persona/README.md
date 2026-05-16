# Persona Profiles

Project_Persona supports multiple persona profiles. Each profile is a folder under `persona/profiles/<name>/` that defines the persona's identity, behavioral rules, and per-profile memory. The same underlying inference model serves all profiles — profiles are "different clothes," not different brains.

## Folder layout

```
persona/
├── README.md                        ← this file
├── global_memory/                   ← shared across all profiles (Qdrant store, planned)
│   └── chroma/                      ← legacy ChromaDB (Phase 2a migration target)
└── profiles/
    ├── default/                     ← default profile (template)
    │   ├── SOUL.md                  ← personality, identity, communication style
    │   ├── .hermes.md               ← rules, output format, avatar STATE vocabulary
    │   ├── MEMORY.md                ← Hermes-managed persistent memory (gitignored)
    │   ├── USER.md                  ← Hermes-managed user model snapshot (gitignored)
    │   └── memory/                  ← per-profile vector store (gitignored)
    └── <other-profile>/             ← copy default/ to start a new profile
```

## File conventions

The two-file profile structure (locked 2026-05-14) defers to **Hermes' file naming conventions** so there's no mapping layer between Project_Persona's profile files and what Hermes loads natively for prompt assembly:

| File | Purpose | Where Hermes loads it |
|---|---|---|
| `SOUL.md` | Personality, identity, emotional range, communication style | Hermes loads from `HERMES_HOME` as the agent's identity (very first section of the system prompt) |
| `.hermes.md` | Hard rules, output format, avatar STATE channel vocabulary | Hermes loads via tree-walk discovery (CWD up to git root) — highest-priority context file in the lookup chain |
| `MEMORY.md` | What the agent has chosen to remember across sessions | Managed by Hermes — gitignored, never edited by hand |
| `USER.md` | Hermes' deepening model of the user across sessions | Managed by Hermes — gitignored, never edited by hand |
| `memory/` | Per-profile vector store (Qdrant collections post-Phase 2a; ChromaDB during transition) | Read/written by the FastAPI memory layer |

## Profile-folder = HERMES_HOME

Each profile folder doubles as Hermes' `HERMES_HOME` for that profile. Hermes' built-in profile system maps directly onto Project_Persona's:

```
hermes -p <profile_name>  →  HERMES_HOME = persona/profiles/<profile_name>/
```

The daemon launches the `hermes-agent` child process with `HERMES_HOME` and CWD both pointed at the active profile directory. Profile switching = restart the Hermes child with a new HERMES_HOME (handled via the `profile_switched` IPC event in Phase 3 daemon work).

## Default profile

Ships as a template. Copy to start a new one:

```
cp -r persona/profiles/default persona/profiles/<new-name>
```

Then edit `SOUL.md` and `.hermes.md` for the new persona. `init_profiles.sh` (planned) will scaffold this with safe defaults including the per-profile `config.yaml` for Hermes (safe-config-conformant — no fallback providers, all auxiliary tasks pinned to local `main`).

## Sterilization & gitignore

`MEMORY.md`, `USER.md`, `hermes_state.db`, `sessions/`, and `memory/` are all gitignored — they accumulate user-specific content over time and must remain local. The template repo only ships empty `SOUL.md` and `.hermes.md` placeholders for the `default/` profile.

## Selecting a profile via API

The FastAPI Companion API accepts a `profile` parameter on `/chat` requests to select which profile to use for that request. Default falls back to `default` if not specified.

## Background

Profile structure was 3 files (`persona.md` / `style.md` / `system_rules.md`) until 2026-05-14 when the design was simplified to 2-file Hermes-naming. The legacy filenames are retired — see `HANDOFF.md` Section 7 for the full rationale and migration trail.
