#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"
API_CHAT="${API_CHAT:-$API_BASE/chat}"
PROFILE="${PROFILE:-default}"

# Prefer dialog; fall back to whiptail; else plain.
need() { command -v "$1" >/dev/null 2>&1; }
UI="plain"
if need dialog; then UI="dialog"
elif need whiptail; then UI="whiptail"
fi

# Temp log that peek uses
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
STEP_LOG="$TMP_DIR/unified_step.log"

reset_log(){ : > "$STEP_LOG"; }
log_now(){ echo "[$(date '+%F %T')] $*" >>"$STEP_LOG"; }

# If dialog is present, we can do tailboxbg; whiptail cannot.
PEEK_CAP="none"
if [ "$UI" = "dialog" ]; then
  # tailboxbg exists in dialog; we assume it works if dialog is installed.
  PEEK_CAP="tailboxbg"
fi

# Required tools
for cmd in bash curl jq python3 date; do
  if ! need "$cmd"; then
    echo "ERROR: missing required command: $cmd"
    echo "Install: sudo apt install -y curl jq python3 dialog"
    exit 1
  fi
done

ui_msg() {
  local title="$1"; shift
  local body="$*"
  case "$UI" in
    dialog)   dialog --backtitle "AI Unified Test" --title "$title" --msgbox "$body" 14 86 ;;
    whiptail) whiptail --title "$title" --msgbox "$body" 14 86 ;;
    plain)    echo -e "\n== $title ==\n$body\n" ;;
  esac
}

ui_textbox_file() {
  local title="$1" file="$2"
  case "$UI" in
    dialog)   dialog --backtitle "AI Unified Test" --title "$title" --textbox "$file" 28 100 ;;
    whiptail) whiptail --title "$title" --textbox "$file" 28 100 ;;
    plain)    echo -e "\n== $title ==\n"; tail -n 240 "$file" ;;
  esac
}

ui_peek_now() {
  # On-demand peek that works everywhere.
  ui_textbox_file "Peek-in (last output)" "$STEP_LOG"
}

# Background peek window (dialog only)
start_peek_bg() {
  local title="$1"
  if [ "$PEEK_CAP" != "tailboxbg" ]; then
    return 0
  fi
  dialog --backtitle "AI Unified Test" \
         --title "Peek-in: $title (live)" \
         --tailboxbg "$STEP_LOG" 28 100 &
  echo $!
}

stop_peek_bg() {
  local pid="${1:-}"
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
}

# Progress UI that works for dialog/whiptail/plain
run_with_progress() {
  local title="$1"
  local fn="$2"
  local fn_args="${3:-}"

  reset_log
  log_now "START: $title"
  log_now "UI=$UI  PEEK_CAP=$PEEK_CAP"
  log_now "API_BASE=$API_BASE  PROFILE=$PROFILE"
  log_now "----------------------------------------"

  local peek_pid=""
  peek_pid="$(start_peek_bg "$title" || true)"

  # Run task in background and write ALL output into STEP_LOG immediately
  set +e
  # shellcheck disable=SC2086
  ($fn $fn_args) >>"$STEP_LOG" 2>&1 &
  local work_pid=$!
  set -e

  # A spinner/progress indicator that never blocks the log
  if [ "$UI" = "dialog" ]; then
    (
      local pct=0 tick=0 hb=0
      echo "XXX"; echo 0; echo "Starting… (Peek window should show log)"; echo "XXX"

      while kill -0 "$work_pid" 2>/dev/null; do
        tick=$((tick+1))
        hb=$((hb+1))
        if [ $pct -lt 92 ]; then pct=$((pct+1)); fi

        case $((tick%4)) in
          0) msg="Running… |" ;;
          1) msg="Running… /" ;;
          2) msg="Running… -" ;;
          3) msg="Running… \\" ;;
        esac

        echo "XXX"; echo "$pct"; echo "$msg  (Press ESC to close this, use Peek menu to view output)"; echo "XXX"

        # HEARTBEAT to log so tailbox always moves
        if [ $((hb % 8)) -eq 0 ]; then
          log_now "…still running ($title)"
        fi
        sleep 0.25
      done

      wait "$work_pid"
      rc=$?
      echo "XXX"; echo 96; echo "Finalizing…"; echo "XXX"
      sleep 0.2
      if [ $rc -eq 0 ]; then
        echo "XXX"; echo 100; echo "Done."; echo "XXX"
      else
        echo "XXX"; echo 100; echo "Done (with warnings)."; echo "XXX"
      fi
      sleep 0.3
      exit $rc
    ) | dialog --backtitle "AI Unified Test" --title "$title" --gauge "Working…" 10 86 0 || true
  elif [ "$UI" = "whiptail" ]; then
    (
      local pct=0 tick=0 hb=0
      echo 0
      while kill -0 "$work_pid" 2>/dev/null; do
        tick=$((tick+1))
        hb=$((hb+1))
        if [ $pct -lt 92 ]; then pct=$((pct+1)); fi
        echo "$pct"
        if [ $((hb % 8)) -eq 0 ]; then log_now "…still running ($title)"; fi
        sleep 0.25
      done
      wait "$work_pid" || true
      echo 100
    ) | whiptail --title "$title" --gauge "Working… (use Peek menu to view output)" 10 86 0 || true
  else
    echo "==> $title (plain mode)"
    while kill -0 "$work_pid" 2>/dev/null; do
      log_now "…still running ($title)"
      sleep 2
    done
    wait "$work_pid" || true
  fi

  stop_peek_bg "$peek_pid"

  # Show final output
  ui_textbox_file "$title — Results" "$STEP_LOG"
}

# ---------------------------
# API helpers
# ---------------------------
http_ok() { curl -sf "$1" >/dev/null 2>&1; }

post_json() {
  local url="$1" payload="$2"
  curl -sS -X POST "$url" -H "Content-Type: application/json" -d "$payload"
}

chat_payload() {
  local topic="$1" text="$2" strict="$3" max_tokens="$4" temp="$5" debug="$6"
  jq -nc \
    --arg text "$text" \
    --arg topic "$topic" \
    --arg profile "$PROFILE" \
    --argjson strict "$strict" \
    --argjson debug "$debug" \
    --argjson max_tokens "$max_tokens" \
    --argjson temperature "$temp" \
    '{
      text:$text,
      topic:$topic,
      profile:$profile,
      strict:$strict,
      debug:$debug,
      max_tokens:$max_tokens,
      temperature:$temperature
    }'
}

# ---------------------------
# Tasks
# ---------------------------
do_ui_diagnostics() {
  echo "UI diagnostics"
  echo "----------------------------------------"
  echo "UI backend:          $UI"
  echo "Peek capability:     $PEEK_CAP"
  echo

  echo "Commands:"
  for c in dialog whiptail; do
    if need "$c"; then
      echo "  ✓ $c: $(command -v "$c")"
    else
      echo "  ✗ $c: not found"
    fi
  done
  echo

  echo "Dialog version (if available):"
  if need dialog; then
    dialog --version 2>&1 || true
  else
    echo "(dialog not installed)"
  fi
  echo

  echo "Log file being tailed:"
  echo "  $STEP_LOG"
  echo

  echo "Test writing to log (should appear immediately in peek):"
  for i in 1 2 3; do
    echo "line $i: $(date '+%T')" | tee -a "$STEP_LOG"
    sleep 0.4
  done
  echo
  echo "If you opened Peek and did NOT see these lines:"
  echo "- you're not using dialog tailboxbg (UI=$UI)"
  echo "- or you opened peek BEFORE the script created the log"
  echo "- or you're on whiptail/plain, which can't do a live background tail"
}

do_health() {
  echo "Health checks"
  echo "----------------------------------------"
  echo "API_BASE=$API_BASE"
  echo "PROFILE=$PROFILE"
  echo

  echo "llama.cpp ports:"
  for p in 8080 8081 8082; do
    if http_ok "http://127.0.0.1:${p}/health"; then
      echo "  ✓ :$p /health OK"
    else
      echo "  ⚠ :$p /health FAIL"
    fi
  done
  echo

  echo "API /health:"
  if http_ok "$API_BASE/health"; then
    curl -s "$API_BASE/health" | jq .
  else
    echo "  ⚠ API /health FAIL"
  fi
  echo

  echo "API /profiles:"
  if http_ok "$API_BASE/profiles"; then
    curl -s "$API_BASE/profiles" | jq .
  else
    echo "  ⚠ API /profiles FAIL"
  fi
}

do_ragless_convo() {
  local rounds="${1:-3}"
  if [ "$rounds" -lt 2 ]; then rounds=2; fi
  if [ "$rounds" -gt 3 ]; then rounds=3; fi

  local topics=("analysis" "biology" "coding" "general")
  local idx=$(( RANDOM % ${#topics[@]} ))
  local topic="${topics[$idx]}"

  echo "RAG-less convo"
  echo "----------------------------------------"
  echo "Topic:  $topic"
  echo "Rounds: $rounds"
  echo

  local prompt1="From scratch: invent a challenging but solvable question in topic '$topic' (no trivia, no browsing). Then answer it concisely."
  local p
  p="$(chat_payload "$topic" "$prompt1" true 260 0.35 true)"
  log_now "POST /chat round1 (topic=$topic)"
  post_json "$API_CHAT" "$p" | jq .
  echo

  local prompt2="Improve your previous answer: add one key insight and one caveat. Keep it brief."
  p="$(chat_payload "$topic" "$prompt2" true 240 0.35 true)"
  log_now "POST /chat round2 (topic=$topic)"
  post_json "$API_CHAT" "$p" | jq .
  echo

  if [ "$rounds" -ge 3 ]; then
    local prompt3="Provide a 3-bullet checklist to verify the answer."
    p="$(chat_payload "$topic" "$prompt3" true 220 0.35 true)"
    log_now "POST /chat round3 (topic=$topic)"
    post_json "$API_CHAT" "$p" | jq .
    echo
  fi
}

# ---------------------------
# Menu (selection-based)
# ---------------------------
menu() {
  while true; do
    local choice=""
    case "$UI" in
      dialog)
        choice="$(dialog --backtitle "AI Unified Test" \
          --title "Unified Test Menu" \
          --menu "Select an action (Peek is always available):" 20 86 12 \
          1 "UI diagnostics (detect dialog/whiptail/plain + peek capability)" \
          2 "Health checks (llama + API + profiles)" \
          3 "RAG-less convo (2 rounds, random topic)" \
          4 "RAG-less convo (3 rounds, random topic)" \
          5 "Peek-in NOW (show current/last output)" \
          6 "Quit" \
          3>&1 1>&2 2>&3)" || exit 0
        ;;
      whiptail)
        choice="$(whiptail --title "Unified Test Menu" \
          --menu "Select an action:" 20 86 12 \
          1 "UI diagnostics" \
          2 "Health checks" \
          3 "RAG-less convo (2 rounds)" \
          4 "RAG-less convo (3 rounds)" \
          5 "Peek-in NOW" \
          6 "Quit" \
          3>&1 1>&2 2>&3)" || exit 0
        ;;
      plain)
        echo "1) UI diag  2) Health  3) Convo2  4) Convo3  5) Peek  6) Quit"
        read -r -p "Select: " choice
        ;;
    esac

    case "$choice" in
      1) run_with_progress "UI diagnostics" "do_ui_diagnostics" ;;
      2) run_with_progress "Health checks" "do_health" ;;
      3) run_with_progress "RAG-less convo (2 rounds)" "do_ragless_convo" "2" ;;
      4) run_with_progress "RAG-less convo (3 rounds)" "do_ragless_convo" "3" ;;
      5) ui_peek_now ;;
      6) exit 0 ;;
      *) ui_msg "Invalid" "Unknown selection: $choice" ;;
    esac
  done
}

menu
