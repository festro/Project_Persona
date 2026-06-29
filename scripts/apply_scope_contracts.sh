#!/usr/bin/env bash
# Idempotently append a per-role SOFT scope contract to each Hermes role's .hermes.md
# (Brandon 2026-06-29, proposal C). SOFT = the worker model follows it; HARD command/path
# containment is not achievable here -- every worker needs the local terminal to run
# `hermes kanban complete`, and terminal.backend=local has no command/path allowlist (a
# sandboxed backend would need docker, which EVO-X2 lacks). The CRITICAL vector is already
# covered: non-researcher roles are egress-off and the daemon strips cloud secrets from
# worker children; this just narrows in-task behaviour. Re-runnable (marker-guarded).
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
PERSONA_ROOT="${PERSONA_ROOT:-$AI_ROOT/persona}"
PROFILES_DIR="${PROFILES_DIR:-$PERSONA_ROOT/profiles}"
MARKER="# --- Scope contract (managed; do not edit below) ---"

common_block() {
  cat <<EOF

$MARKER
# Operating boundaries for delegated background work:
- You run as a delegated worker in an isolated workspace. Your ONLY intended side effects are
  producing your result and calling kanban_complete to finish the task.
- Do NOT run destructive or system-level commands (e.g. rm -rf, mkfs, chmod -R on system paths),
  and do NOT touch paths outside your task workspace (e.g. /etc, /usr, ~/.ssh, ~/.config, the
  daemon/model config).
- Do NOT send messages, schedule cron jobs, control the desktop, or delegate the task onward.
- Stay within the tools your role is given. If the task truly needs something outside your scope,
  stop and complete with a short note explaining what would be required.
EOF
}

role_line() {
  case "$1" in
    researcher) echo "- Researcher scope: gather facts via web search + reasoning; avoid shell beyond what completing the task requires." ;;
    coder)      echo "- Coder scope: read/write/build/test code WITHIN the workspace only; never modify system paths or delete outside it." ;;
    summarizer) echo "- Summarizer scope: text-only. Read the task and produce a summary; do not run shell, file, or network operations." ;;
    critic)     echo "- Critic scope: text-only review. Produce a verdict + key risks; do not run shell, file, or network operations." ;;
    librarian)  echo "- Librarian scope: organize/retrieve within the workspace; do not expect or modify host files." ;;
    *)          echo "- Default scope: keep actions minimal and within the task; prefer read-only steps." ;;
  esac
}

echo "==> Applying per-role scope contracts under: $PROFILES_DIR"
applied=0 skipped=0
for rdir in "$PROFILES_DIR"/*/; do
  [ -d "$rdir" ] || continue
  role="$(basename "$rdir")"
  hm="${rdir%/}/.hermes.md"
  [ -f "$hm" ] || continue
  if grep -qF "$MARKER" "$hm"; then
    echo "  $role: already present (skip)"; skipped=$((skipped+1)); continue
  fi
  { common_block; role_line "$role"; } >> "$hm"
  echo "  $role: scope contract appended"; applied=$((applied+1))
done
echo "==> Done. appended=$applied skipped=$skipped"
