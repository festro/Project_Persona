#!/usr/bin/env bash
# Per-OS egress baseline (Linux / nftables) -- Project_Persona Phase 0.5.
# Default-deny OUTBOUND host firewall for the local-first stack. SCRIPTED, NOT enforced
# by manage.py -- you run this deliberately. See docs/egress_baseline_design_20260619.md.
#
# Postures:
#   SERVE     (locked)  : allow loopback + established; DROP all new outbound.
#   PROVISION (--provision): SERVE + DNS(53) + HTTPS(443) so model/pkg downloads work.
#
# Usage:
#   scripts/egress_baseline.sh plan [--provision]      # print the ruleset, change nothing (default)
#   scripts/egress_baseline.sh status                  # is the baseline loaded? which posture?
#   sudo scripts/egress_baseline.sh apply [--provision] --yes
#   sudo scripts/egress_baseline.sh remove --yes
#
# 'established,related' is accepted FIRST, so applying over SSH does not cut your session.
# Isolated in its own table (inet persona_egress) -> 'remove' is a clean, total rollback.
set -euo pipefail

TABLE="persona_egress"
FAMILY="inet"
CMD="${1:-plan}"
shift || true

PROVISION=0
ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    --provision) PROVISION=1 ;;
    --yes|-y)    ASSUME_YES=1 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

have_nft() { command -v nft >/dev/null 2>&1; }

require_nft() {
  if ! have_nft; then
    echo "ERROR: nft (nftables) not found." >&2
    echo "  Install it (Debian/Ubuntu: sudo apt install nftables), or use an iptables" >&2
    echo "  equivalent per docs/egress_baseline_design_20260619.md (sec 4)." >&2
    exit 3
  fi
}

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: '$CMD' changes firewall state and needs root. Re-run with sudo." >&2
    exit 4
  fi
}

confirm() {
  [ "$ASSUME_YES" = "1" ] && return 0
  if [ -t 0 ]; then
    read -r -p "$1 [y/N] " r; [ "$r" = "y" ] || [ "$r" = "yes" ] && return 0
    echo "aborted"; exit 0
  fi
  echo "ERROR: '$CMD' is not interactive; pass --yes to proceed." >&2
  exit 5
}

# Print the nftables ruleset for the requested posture. Pure text -- no nft invocation.
build_ruleset() {
  echo "table $FAMILY $TABLE {"
  echo "  chain output {"
  echo "    type filter hook output priority 0; policy drop;"
  echo "    oif \"lo\" accept"
  echo "    ct state established,related accept"
  if [ "$PROVISION" = "1" ]; then
    echo "    udp dport 53 accept"
    echo "    tcp dport 53 accept"
    echo "    tcp dport 443 accept"
  fi
  echo "  }"
  echo "}"
}

posture_label() { [ "$PROVISION" = "1" ] && echo "PROVISION (internet window)" || echo "SERVE (locked)"; }

case "$CMD" in
  plan)
    echo "# egress baseline -- posture: $(posture_label)"
    echo "# (this is a dry print; nothing is applied. apply with: sudo $0 apply [--provision] --yes)"
    build_ruleset
    ;;
  status)
    require_nft
    if nft list table "$FAMILY" "$TABLE" >/dev/null 2>&1; then
      if nft list table "$FAMILY" "$TABLE" 2>/dev/null | grep -q "dport 443"; then
        echo "egress baseline: LOADED -- posture PROVISION (DNS+HTTPS open)"
      else
        echo "egress baseline: LOADED -- posture SERVE (locked: loopback + established only)"
      fi
    else
      echo "egress baseline: NOT loaded (no $FAMILY $TABLE table)"
    fi
    ;;
  apply)
    require_nft; require_root
    echo "About to apply a default-deny OUTBOUND baseline -- posture: $(posture_label)."
    echo "Loopback + established flows stay allowed (your SSH session survives)."
    confirm "Proceed?"
    build_ruleset | nft -f -
    echo "OK: egress baseline applied ($(posture_label)). Roll back: sudo $0 remove --yes"
    ;;
  remove)
    require_nft; require_root
    if ! nft list table "$FAMILY" "$TABLE" >/dev/null 2>&1; then
      echo "nothing to remove ($FAMILY $TABLE not loaded)"; exit 0
    fi
    confirm "Remove the egress baseline (restore normal outbound)?"
    nft delete table "$FAMILY" "$TABLE"
    echo "OK: egress baseline removed."
    ;;
  *)
    echo "usage: $0 [plan|status|apply|remove] [--provision] [--yes]" >&2
    exit 2
    ;;
esac
