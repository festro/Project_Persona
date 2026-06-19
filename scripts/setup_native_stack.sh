#!/usr/bin/env bash
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/Git/Project_Persona}"
CPU_ONLY="${CPU_ONLY:-0}"   # set CPU_ONLY=1 to force CPU
SKIP_DEPS="${SKIP_DEPS:-0}" # set SKIP_DEPS=1 to skip apt installs
SKIP_HERMES="${SKIP_HERMES:-0}" # set SKIP_HERMES=1 to skip the env_hermes venv
AUTO_PROVISION="${AUTO_PROVISION:-0}" # set AUTO_PROVISION=1 to auto-download a fitted model at the end

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
  echo "==> Installing Hermes Agent (NousResearch/hermes-agent) editable via uv, isolated in env_hermes"
  HERMES_VENV="$AI_ROOT/env_hermes"
  HERMES_SRC="${HERMES_SRC:-$HOME/src/hermes-agent}"
  HERMES_REPO="${HERMES_REPO:-https://github.com/NousResearch/hermes-agent.git}"
  HERMES_REF="${HERMES_REF:-9b1e0d6f}"

  if ! command -v uv >/dev/null 2>&1; then
    echo "==> uv not found; installing user-local uv into ~/.local/bin"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi

  if command -v uv >/dev/null 2>&1; then
    if [ ! -d "$HERMES_SRC/.git" ]; then
      git clone "$HERMES_REPO" "$HERMES_SRC"
    fi
    git -C "$HERMES_SRC" fetch --all --tags
    git -C "$HERMES_SRC" checkout "$HERMES_REF"
    uv venv "$HERMES_VENV" --python 3.11
    if uv pip install --python "$HERMES_VENV/bin/python" -e "$HERMES_SRC[all,dev]"; then
      echo "OK: hermes-agent installed editable into $HERMES_VENV (ref $HERMES_REF)"
    else
      echo "WARN: 'uv pip install -e $HERMES_SRC[all,dev]' failed. Install Hermes into"
      echo "      $HERMES_VENV manually per the Hermes docs, then re-run doctor.sh."
    fi
  else
    echo "WARN: uv unavailable; skipping Hermes install. Install it manually:"
    echo "      uv venv $HERMES_VENV --python 3.11"
    echo "      uv pip install -e $HERMES_SRC[all,dev]   (then re-run doctor.sh)"
  fi
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
PERSONA_MODEL=Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
PERSONA_CTX=32768
GPU_LAYERS_PERSONA=999
PERSONA_PARALLEL=4
LLAMA_LIB_DIR=$AI_ROOT/llama_cpp/build/bin
EOF
fi

if [ "$AUTO_PROVISION" = "1" ]; then
  echo "==> AUTO_PROVISION=1: profiling host and downloading a fitted model"
  python3 "$AI_ROOT/manage.py" provision --yes
fi

echo "==> Done."
echo ""
echo "Next steps (lifecycle is now manage.py; the old bash scripts are archived):"
echo "  1) Get a model (pick one):"
echo "     - auto:   python3 $AI_ROOT/manage.py provision        (host-fitted, Apache-2.0)"
echo "     - manual: drop a GGUF in $AI_ROOT/models/ and set PERSONA_MODEL in run/config.toml"
echo "       (or re-run this installer with AUTO_PROVISION=1)"
echo "  2) Init persona profiles:  $AI_ROOT/scripts/init_profiles.sh"
echo "  3) Start the stack:        python3 $AI_ROOT/manage.py up   (first run auto-offers provisioning; --yes to auto-accept)"
echo "  4) Status / health gate:   python3 $AI_ROOT/manage.py status   (deep: manage.py doctor)"
echo "  5) Run tests:              python3 $AI_ROOT/manage.py test"
