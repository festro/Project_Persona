#!/usr/bin/env bash
# Idempotently activate per-role HOME isolation for Hermes WORKER profiles (Brandon 2026-06-29,
# proposal C -- "workspace confine only"). This is the HARD-containment increment Brandon chose
# after the sandboxed-backend path (bwrap/firejail) was ruled out: bwrap IS installed on EVO-X2
# but AppArmor blocks unprivileged user namespaces (kernel.apparmor_restrict_unprivileged_userns=1)
# and the sysctl/profile fix needs sudo, which is hard-denied. See changelog 2026-06-29.
#
# Mechanism (Hermes-native, no code change): tools/environments/local.py::_make_run_env() calls
# hermes_constants.get_subprocess_home(), which redirects a worker's TERMINAL-subprocess HOME to
# {HERMES_HOME}/home/ WHEN THAT DIRECTORY EXISTS. Activation is purely directory-based -- so simply
# creating persona/profiles/<role>/home/ confines every shell command a worker runs to an isolated
# HOME, keeping it out of the human's real ~ (~/.ssh, ~/.config, gh/aws tokens, shell history).
#
# Scope / safety:
#   - Only the terminal SUBPROCESS HOME is affected. The worker's own `hermes` process reads its
#     config from HERMES_HOME (not HOME), and kanban_complete is an in-process tool -- so the
#     delegate -> dispatch -> worker -> complete -> bridge-mirror chain is untouched.
#   - The 'default' profile is the TRUSTED persona (it runs the bridge + dispatcher and the
#     interactive persona's own tools); it is intentionally NOT isolated.
#   - An identity-only .gitconfig is seeded so worker `git commit` keeps an author. NO credentials
#     are copied -- a confined worker therefore cannot reach the host's ssh keys or gh/aws tokens.
# Re-runnable: existing home/ dirs (and their .gitconfig) are left untouched.
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
PERSONA_ROOT="${PERSONA_ROOT:-$AI_ROOT/persona}"
PROFILES_DIR="${PROFILES_DIR:-$PERSONA_ROOT/profiles}"

# Derive the worker git identity from the host's global identity so commits stay attributable,
# but label provenance ("... (<role> worker)"). Fall back to sane defaults if git has none.
host_name="$(git config --global user.name 2>/dev/null || true)"
host_email="$(git config --global user.email 2>/dev/null || true)"
[ -n "$host_name" ] || host_name="Daemonic"
[ -n "$host_email" ] || host_email="persona@localhost"

echo "==> Activating per-role HOME isolation under: $PROFILES_DIR"
activated=0 skipped=0
for rdir in "$PROFILES_DIR"/*/; do
  [ -d "$rdir" ] || continue
  role="$(basename "$rdir")"
  if [ "$role" = "default" ]; then
    echo "  $role: trusted persona profile -- HOME isolation intentionally skipped"
    continue
  fi
  home_dir="${rdir%/}/home"
  if [ -d "$home_dir" ]; then
    echo "  $role: home/ already present (skip)"; skipped=$((skipped+1)); continue
  fi
  mkdir -p "$home_dir"
  # Identity-only .gitconfig (no credentials). safe.directory=* so git won't refuse to operate on
  # a same-user workspace it flags as "dubious ownership" once HOME is redirected.
  cat > "$home_dir/.gitconfig" <<EOF
[user]
	name = $host_name ($role worker)
	email = $host_email
[safe]
	directory = *
EOF
  echo "  $role: HOME isolation activated -> $home_dir"; activated=$((activated+1))
done
echo "==> Done. activated=$activated skipped=$skipped"
