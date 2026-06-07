#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$DIR/env/bin/python"
[ -x "$PY" ] || PY="$(command -v python3 || command -v python)"
exec "$PY" "$DIR/manage.py" toggle "$@"
