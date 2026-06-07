#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
CPU_ONLY="${CPU_ONLY:-0}"   # set CPU_ONLY=1 to force CPU
SKIP_DEPS="${SKIP_DEPS:-0}" # set SKIP_DEPS=1 to skip apt installs
SKIP_HERMES="${SKIP_HERMES:-0}" # set SKIP_HERMES=1 to skip the env_hermes venv

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
  git clone https://github.com/ggml-org/llama.cpp.git "$AI_ROOT/llama_cpp"
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

REQ_FILE="$AI_ROOT/services/api/requirements.txt"
if [ ! -f "$REQ_FILE" ]; then
  echo "ERROR: committed requirements file missing: $REQ_FILE"
  echo "       (run this installer from inside the cloned repo)"
  exit 1
fi
echo "==> Installing API dependencies into venv from the committed lean requirements"
echo "    $REQ_FILE"
pip install -r "$REQ_FILE"

if [ "${WITH_TORCH_EMBED:-0}" = "1" ]; then
  echo "==> WITH_TORCH_EMBED=1: installing the opt-in sentence-transformers/torch extra"
  pip install -r "$AI_ROOT/services/api/requirements-embed-torch.txt"
fi

deactivate || true

if [ "$SKIP_HERMES" != "1" ]; then
  echo "==> Creating isolated Hermes Agent venv (env_hermes)"
  HERMES_VENV="$AI_ROOT/env_hermes"
  python3 -m venv "$HERMES_VENV"
  # shellcheck disable=SC1091
  source "$HERMES_VENV/bin/activate"
  python -m pip install --upgrade pip wheel setuptools
  if pip install hermes-agent; then
    echo "OK: hermes-agent installed into $HERMES_VENV"
  else
    echo "WARN: 'pip install hermes-agent' failed. Install Hermes into $HERMES_VENV"
    echo "      manually, or use the git installer per the Hermes docs, then re-run doctor.sh."
  fi
  deactivate || true
else
  echo "==> SKIP_HERMES=1 set; skipping env_hermes venv"
fi

ENV_OUT="$AI_ROOT/run/llama-servers.env"
if [ -f "$ENV_OUT" ] && [ "${FORCE_ENV:-0}" != "1" ]; then
  echo "==> Existing $ENV_OUT found; leaving it untouched"
  echo "    (set FORCE_ENV=1 to overwrite; a timestamped .bak is kept)"
else
  if [ -f "$ENV_OUT" ]; then
    cp -a "$ENV_OUT" "$ENV_OUT.bak.$(date -u +%Y%m%d_%H%M%S)"
    echo "==> Backed up existing env to $ENV_OUT.bak.*"
  fi
  echo "==> Writing unified single-model llama server env config"
  cat > "$ENV_OUT" <<EOF
HOST=127.0.0.1
THREADS=0
BATCH_SIZE=512
UBATCH_SIZE=512
CACHE_TYPE_K=q8_0
CACHE_TYPE_V=q8_0
PERSONA_PORT=8090
PERSONA_MODEL=Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf
PERSONA_CTX=32768
GPU_LAYERS_PERSONA=999
PERSONA_PARALLEL=4
LLAMA_LIB_DIR=$AI_ROOT/llama_cpp/build/bin
EOF
fi

echo "==> Done."
echo ""
echo "Next steps:"
echo "  1) Put the unified GGUF model in: $AI_ROOT/models/"
echo "     - Qwen_Qwen3-30B-A3B-Instruct-2507-Q5_K_M.gguf"
echo "       (or edit PERSONA_MODEL in run/llama-servers.env)"
echo "  2) Init persona profiles:  $AI_ROOT/scripts/init_profiles.sh"
echo "  3) Start llama server:     $AI_ROOT/scripts/start_llama_servers.sh"
echo "  4) Start API:              $AI_ROOT/scripts/start_api.sh"
echo "  5) Health + T1 gate:       $AI_ROOT/scripts/doctor.sh"
echo "  6) Load test:              $AI_ROOT/scripts/load_test_m2b.py"
