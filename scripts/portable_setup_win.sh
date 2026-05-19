#!/usr/bin/env bash
# Stage 2 of the portable Windows setup — runs under the portable bash
# installed by Stage 1 (windows_portable_setup.bat).
#
# Idempotent: safe to re-run. Each step skips if the artifact is already in place.
#
# Downloads:
#   1. Latest llama.cpp Windows-Vulkan binary → llama_cpp/windows/
#   2. Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf (26.6 GB) → models/
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
AI_ROOT="$( dirname "$SCRIPT_DIR" )"
cd "$AI_ROOT"

echo "AI_ROOT: $AI_ROOT"
echo

# ----------------------------------------------------------------
# Step 2 — llama.cpp Windows-Vulkan binary
# ----------------------------------------------------------------
LLAMA_DIR="$AI_ROOT/llama_cpp/windows"
mkdir -p "$LLAMA_DIR"

if [ -f "$LLAMA_DIR/llama-server.exe" ]; then
  echo "[2/3] [SKIP] llama-server.exe already present at $LLAMA_DIR"
else
  echo "[2/3] Resolving latest llama.cpp Windows-Vulkan release URL..."
  LLAMA_URL="$( curl -sSL 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest' \
      | grep -oE '"browser_download_url":[[:space:]]*"[^"]*-bin-win-vulkan-x64\.zip"' \
      | head -n1 \
      | sed -E 's/.*"(https[^"]+)".*/\1/' )"
  if [ -z "$LLAMA_URL" ]; then
    echo "ERROR: could not resolve llama.cpp Vulkan-x64 URL via GitHub API."
    echo "       Check: https://github.com/ggml-org/llama.cpp/releases/latest"
    exit 1
  fi
  echo "      URL: $LLAMA_URL"

  LLAMA_ZIP="$LLAMA_DIR/llama-windows-vulkan.zip"
  echo "      Downloading (~30 MB)..."
  curl -L --fail --progress-bar -o "$LLAMA_ZIP" "$LLAMA_URL"

  echo "      Extracting..."
  if command -v unzip >/dev/null 2>&1; then
    ( cd "$LLAMA_DIR" && unzip -q -o "$LLAMA_ZIP" )
  else
    ( cd "$LLAMA_DIR" && tar -xf "$LLAMA_ZIP" )
  fi
  rm -f "$LLAMA_ZIP"

  # Some releases nest the binaries inside build/bin/ or similar — hoist them up.
  if [ ! -f "$LLAMA_DIR/llama-server.exe" ]; then
    FOUND="$( find "$LLAMA_DIR" -maxdepth 4 -name llama-server.exe 2>/dev/null | head -n1 )"
    if [ -n "$FOUND" ]; then
      FOUND_DIR="$( dirname "$FOUND" )"
      echo "      Hoisting bins from $FOUND_DIR up to $LLAMA_DIR"
      mv "$FOUND_DIR"/* "$LLAMA_DIR/" 2>/dev/null || true
    fi
  fi

  if [ ! -f "$LLAMA_DIR/llama-server.exe" ]; then
    echo "ERROR: llama-server.exe not found after extraction."
    echo "       Contents of $LLAMA_DIR:"
    ls -la "$LLAMA_DIR" || true
    exit 1
  fi
  echo "      llama-server.exe ready: $LLAMA_DIR/llama-server.exe"
fi

# ----------------------------------------------------------------
# Step 3 — Qwen3.6 model GGUF
# ----------------------------------------------------------------
MODEL_FILE="Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf"
MODEL_URL="https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/main/${MODEL_FILE}?download=true"
MODEL_DIR="$AI_ROOT/models"
mkdir -p "$MODEL_DIR"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"

# Helper: portable file size in bytes (GNU stat vs BSD stat)
size_bytes () {
  local p="$1"
  stat -c %s "$p" 2>/dev/null || stat -f %z "$p" 2>/dev/null || echo 0
}

EXPECTED_MIN_BYTES=25000000000

if [ -f "$MODEL_PATH" ] && [ "$( size_bytes "$MODEL_PATH" )" -ge "$EXPECTED_MIN_BYTES" ]; then
  echo "[3/3] [SKIP] Model file already present and full-sized:"
  echo "       $MODEL_PATH"
  echo "       size: $( size_bytes "$MODEL_PATH" ) bytes"
else
  if [ -f "$MODEL_PATH" ]; then
    echo "[3/3] Partial model file found ($( size_bytes "$MODEL_PATH" ) bytes) — resuming..."
  else
    echo "[3/3] Downloading model: $MODEL_FILE"
    echo "      ~26.6 GB — go get coffee, this takes a while."
    echo "      Resumable: if interrupted, just re-run windows_portable_setup.bat."
  fi
  echo "      URL: $MODEL_URL"
  curl -L --fail -C - --progress-bar -o "$MODEL_PATH" "$MODEL_URL"
  echo "      Download complete: $( size_bytes "$MODEL_PATH" ) bytes"
fi

# ----------------------------------------------------------------
# Summary
# ----------------------------------------------------------------
echo
echo "=============================================="
echo "  Portable setup complete"
echo "=============================================="
echo "  PortableGit:      $AI_ROOT/portable/PortableGit"
echo "  llama-server.exe: $LLAMA_DIR/llama-server.exe"
echo "  Model:            $MODEL_PATH"
echo
echo "  Launch via:       windows_portable_run.bat"
echo "  Or directly:      ./scripts/start_llama_server_win.sh"
echo "=============================================="
