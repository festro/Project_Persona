#!/usr/bin/env bash
set -u

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
PIDFILE="$ROOT/run/persona.pid"

fails=0
note() { printf '%s\n' "$*"; }
pass() { printf 'PASS %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*"; fails=$((fails+1)); }

note "=== verify_pid_recovery on $(hostname) at $(date '+%Y-%m-%d %H%M %Z') ==="

"$PY" manage.py up --llama-only >/dev/null 2>&1
PORT="$("$PY" manage.py status 2>/dev/null | sed -n 's/.*persona_port=\([0-9]*\).*/\1/p' | head -1)"
[ -z "$PORT" ] && PORT=8090
note "persona_port=$PORT"

REAL="$(cat "$PIDFILE" 2>/dev/null)"
if [ -n "$REAL" ] && kill -0 "$REAL" 2>/dev/null; then
    pass "server up, real pid=$REAL"
else
    fail "server did not start (no live pid in $PIDFILE) -- aborting"
    pkill -9 -f -- "--port $PORT" 2>/dev/null
    exit 1
fi

if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    pass "/health responding"
else
    fail "/health not responding -- aborting"
    kill -9 "$REAL" 2>/dev/null
    exit 1
fi

sleep 0.2 & BOGUS=$!; wait "$BOGUS" 2>/dev/null
printf '%s' "$BOGUS" > "$PIDFILE"
note "injected stale pid=$BOGUS into $PIDFILE (real server still up on $PORT)"

STATUS_OUT="$("$PY" manage.py status 2>&1)"
if printf '%s' "$STATUS_OUT" | grep -q "real pid $REAL"; then
    pass "status: corroborated /health UP on real pid $REAL"
else
    fail "status did not surface the WSL trap (expected real pid $REAL)"
    note "$STATUS_OUT"
fi

DOWN_OUT="$("$PY" manage.py down 2>&1)"
note "$DOWN_OUT"
if printf '%s' "$DOWN_OUT" | grep -q "killing real pid $REAL"; then
    pass "down: recovered and killed real pid $REAL"
else
    fail "down did not report killing the real pid $REAL"
fi

sleep 1
if kill -0 "$REAL" 2>/dev/null; then
    fail "ORPHAN: real server pid $REAL still alive after down"
    kill -9 "$REAL" 2>/dev/null
else
    pass "no orphan: real server pid $REAL is gone"
fi

if pgrep -af "llama-server" 2>/dev/null | grep -q -- "--port $PORT"; then
    fail "ORPHAN: a llama-server still listening on --port $PORT"
    pkill -9 -f -- "--port $PORT" 2>/dev/null
else
    pass "no llama-server left on --port $PORT"
fi

note ""
if [ "$fails" -eq 0 ]; then
    note "RESULT: ALL PASS"
    exit 0
else
    note "RESULT: $fails FAIL"
    exit 1
fi
