# Persona Profiles (Multi-Profile “Clothing” Wrapper)

This project supports **multiple persona profiles** (different “clothes”) that all drive the **same underlying persona model** while optionally consulting silent experts.

## Root assumptions
- `AI_ROOT` defaults to: `~/AI`
- Persona root: `${AI_ROOT}/persona`

## Directory layout

### Global shared memory (universal topics)
- `${AI_ROOT}/persona/global_memory/`
  - `chroma/` (persistent vector DB)
  - `exports/` (optional exports/backups)

### Per-profile wrappers + per-profile memory
- `${AI_ROOT}/persona/profiles/<profile>/`
  - `persona.md`        (who they are)
  - `style.md`          (how they speak)
  - `system_rules.md`   (hard rules)
  - `memory/`
    - `chroma/`         (persistent per-profile vector DB)
    - `exports/`        (optional exports/backups)

## Default profile
- `default` (template you can copy/rename)

## Notes
- You can add additional profiles by copying `profiles/default` to a new folder name.
- The API accepts `profile` to select which wrapper + memory to use.
