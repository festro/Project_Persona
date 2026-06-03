# Handoff -- Project_Persona -- 2026-06-03 0301 UTC

Author: Claude
Branch: main (last commit 3238077, pre-restructure)
Type: frozen snapshot. Living state is in `todo.md`; history in `changelog.md`.

## What this session did

Brought the project documentation into compliance with `D:\Projects\WORKFLOW.md`
(the three-file convention). Concretely:

- Split the pre-convention `KNOWLEDGE.md` (1022 lines, mixing scope + active
  TODOs + a dated File Change Tracker + git log) and the living `HANDOFF.md`
  into:
  - `knowledge.md` -- scope, repo map, architecture, operational notes,
    architecture roadmap, license, pointers.
  - `todo.md` -- current short-term state with rules-of-the-road box.
  - `changelog.md` -- reverse-chronological history reconstructed from the old
    File Change Tracker, plus a Pre-convention baseline block.
- Converted everything to ASCII (em-dashes, smart quotes, box-drawing rules and
  status emoji removed); verified 0 non-ASCII bytes across all four new files.
- Removed inline `#` comments from config code blocks (executable-code-only
  rule); verified none remain.
- Added the root `WORKFLOW.md` one-line pointer.
- Archived the originals to `archive/pre-workflow/` (KNOWLEDGE.md, HANDOFF.md,
  HANDOFF.html). README.md and README_models_hardware.md left in place
  (external-facing, separate concern per the workflow FAQ).

## State of the deliverable

- Files created: `knowledge.md`, `todo.md`, `changelog.md`, `WORKFLOW.md`.
- Files moved: `archive/pre-workflow/{KNOWLEDGE.md,HANDOFF.md,HANDOFF.html}`.
- VERIFIED: ASCII-only (grep, 0 hits); no inline comments in fenced code blocks
  (awk scan, 0 hits).
- NOT verified: nothing about the running system was tested this session; this
  was a docs-only restructure.

## What the next editor needs to know (cold pickup)

1. UNRESOLVED current-state discrepancy (now the top item in `todo.md`). The two
   archived living docs disagree:
   - `archive/pre-workflow/KNOWLEDGE.md` (2026-05-23): unified Qwen3-30B-A3B
     -INSTRUCT-2507 deployed on :8090, M2b passed, next is M6 / Hermes H1.
   - `archive/pre-workflow/HANDOFF.md` (2026-05-16): critical path is still the
     QWEN3.6 T0.1 GO/NO-GO arch test, OpenWebUI "running".
   They conflict on which model is deployed, whether T0.1 ran, and OpenWebUI
   status. Resolve against EVO-X2 reality before trusting either, then correct
   `todo.md`. Per the user's instruction this was deliberately left open, not
   guessed.

2. GIT INDEX IS CORRUPT. `git mv` failed mid-operation (an earlier interrupted
   sandbox call left `.git/index` half-written, "bad signature 0x00000000"), and
   a stale zero-byte `.git/index.lock` remains. The sandbox could not remove it
   ("Operation not permitted" -- the mount blocks writes under `.git/`). The file
   moves were completed with plain `mv`, so the working tree is correct; only the
   index needs rebuilding. Repair from a Windows shell at the repo root:

   ```
   del .git\index.lock
   del .git\index
   git reset
   git status
   git add -A
   git commit -m "docs: adopt three-file WORKFLOW convention; archive pre-workflow docs"
   ```

   No commits were lost; `git reset` rebuilds the index from HEAD. Review
   `git status` before committing.

## Carry-forward (from 2026-05-23, pre-restructure)

- M2b passed (30-min, 2066/2066 OK, ~113 tok/s aggregate); stability ghost did
  not recur. Peak-load thermal never captured.
- Housekeeping fix-its: `load_test_m2b.py` DEFAULT_ENDPOINT 8080 -> 8090;
  `start_api.sh` cosmetic SCIENTIST_* banner; `prompt_tokens=0` in API responses;
  min-1 bucket race in `bucketize_by_minute`.
- `looks_degenerate()` + self-repair loop: never landed; land with T2.4 `<think>`
  stripping or formally drop.
