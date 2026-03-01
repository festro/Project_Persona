#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"
CPU_ONLY="${CPU_ONLY:-0}"   # set CPU_ONLY=1 to force CPU
SKIP_DEPS="${SKIP_DEPS:-0}" # set SKIP_DEPS=1 to skip apt installs

echo "==> Creating AI root structure at $AI_ROOT"
mkdir -p "$AI_ROOT"/{bin,models,persona,logs,run,services/{api},scripts,llama_cpp}

if [ "$SKIP_DEPS" != "1" ]; then
  echo "==> Installing system dependencies (Debian/Mint/Ubuntu)"
  sudo apt update
  sudo apt install -y \
    build-essential cmake git curl wget unzip pkg-config ca-certificates \
    python3 python3-venv python3-pip \
    libssl-dev \
    tree
fi

# --- Vulkan capability detection / fallback ---
have_glslc=0
if command -v glslc >/dev/null 2>&1; then
  have_glslc=1
fi

if [ "$CPU_ONLY" = "1" ]; then
  echo "==> CPU_ONLY=1 set; will build llama.cpp without Vulkan"
  use_vulkan=0
else
  # Try to make Vulkan build possible
  if [ "$SKIP_DEPS" != "1" ]; then
    echo "==> Installing Vulkan build deps (best-effort)"
    # libvulkan-dev provides headers; glslc often comes via glslang-tools (or shaderc on some distros)
    sudo apt install -y libvulkan-dev libgl1-mesa-dev vulkan-tools || true
    sudo apt install -y glslang-tools || true
  fi

  if command -v glslc >/dev/null 2>&1; then
    use_vulkan=1
  else
    echo "WARN: glslc not found; Vulkan build will likely fail. Falling back to CPU build."
    use_vulkan=0
  fi
fi

echo "==> Cloning & building llama.cpp"
if [ ! -d "$AI_ROOT/llama_cpp/.git" ]; then
  git clone https://github.com/ggerganov/llama.cpp.git "$AI_ROOT/llama_cpp"
else
  git -C "$AI_ROOT/llama_cpp" pull
fi

mkdir -p "$AI_ROOT/llama_cpp/build"
cd "$AI_ROOT/llama_cpp/build"

if [ "$use_vulkan" = "1" ]; then
  echo "==> Configuring llama.cpp with Vulkan"
  cmake .. -DGGML_VULKAN=ON
else
  echo "==> Configuring llama.cpp CPU-only"
  cmake .. -DGGML_VULKAN=OFF
fi

cmake --build . -j"$(nproc)"

if [ ! -x "$AI_ROOT/llama_cpp/build/bin/llama-server" ]; then
  echo "ERROR: llama-server binary not found after build."
  exit 1
fi
echo "✓ llama.cpp built: $AI_ROOT/llama_cpp/build/bin/llama-server"

echo "==> Creating Python venv (native services)"
python3 -m venv "$AI_ROOT/env"
# shellcheck disable=SC1091
source "$AI_ROOT/env/bin/activate"
python -m pip install --upgrade pip wheel setuptools

echo "==> Writing API requirements"
cat > "$AI_ROOT/services/api/requirements.txt" <<'EOF'
fastapi>=0.110.0,<1.0.0
uvicorn[standard]>=0.29.0,<1.0.0
pydantic>=2.7.0,<3.0.0
httpx>=0.27.0,<1.0.0
chromadb>=0.5.0,<1.0.0
tenacity>=8.0.0,<9.0.0
fastembed>=0.3.3,<1.0.0
EOF

echo "==> Installing API dependencies into venv"
pip install -r "$AI_ROOT/services/api/requirements.txt"

echo "==> Writing llama server env config (safe defaults)"
cat > "$AI_ROOT/run/llama-servers.env" <<'EOF'
# Common settings
CTX_SIZE=8192
THREADS=0
BATCH_SIZE=256
HOST=127.0.0.1

# Ports
PERSONA_PORT=8080
REASONING_PORT=8081
CODER_PORT=8082

# Models (filenames under ~/AI/models)
PERSONA_MODEL=persona.gguf
REASONING_MODEL=reasoning.gguf
CODER_MODEL=coder.gguf

# Global GPU layers fallback
GPU_LAYERS=0

# Per-model context (recommended)
PERSONA_CTX=8192
CODER_CTX=8192
REASONING_CTX=4096

# Per-model GPU layers (start conservative; tune via benchmarking)
GPU_LAYERS_PERSONA=0
GPU_LAYERS_CODER=0
GPU_LAYERS_REASONING=0
EOF

echo "==> Done."
echo ""
echo "Next steps:"
echo "  1) Put GGUF models in: $AI_ROOT/models/"
echo "     - persona.gguf"
echo "     - reasoning.gguf"
echo "     - coder.gguf"
echo "  2) Start llama servers: $AI_ROOT/scripts/start_llama_servers.sh"
echo "  3) Start API:          $AI_ROOT/scripts/start_api.sh"
echo "  4) Bench:              $AI_ROOT/scripts/bench.sh"
