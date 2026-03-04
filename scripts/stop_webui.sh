#!/usr/bin/env bash
set -euo pipefail

# Stop any open-webui server process (current user)
pkill -f "open-webui serve" >/dev/null 2>&1 || true
echo "OpenWebUI stopped."
