#!/usr/bin/env bash
#
# AI Infrastructure Setup Script (Enhanced Version)
# Sets up a local multi-model AI infrastructure with:
# - 3 llama.cpp server instances (persona, reasoning, coder)
# - FastAPI wrapper with intelligent routing
# - ChromaDB for vector storage
# - Docker orchestration
#
# Usage: ./ai-infrastructure-setup.sh [--skip-deps] [--skip-docker] [--cpu-only]
#
set -euo pipefail

# Color output helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}==> $1${NC}"; }
log_success() { echo -e "${GREEN}✓ $1${NC}"; }
log_warn()    { echo -e "${YELLOW}⚠ $1${NC}"; }
log_error()   { echo -e "${RED}✗ $1${NC}"; }

# Configuration
AI_ROOT="${AI_ROOT:-$HOME/AI}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
SKIP_DEPS=false
SKIP_DOCKER_INSTALL=false
CPU_ONLY=false
DOWNLOAD_MODELS=false

for arg in "$@"; do
  case $arg in
    --skip-deps)     SKIP_DEPS=true; shift ;;
    --skip-docker)   SKIP_DOCKER_INSTALL=true; shift ;;
    --cpu-only)      CPU_ONLY=true; shift ;;
    --download-models) DOWNLOAD_MODELS=true; shift ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --skip-deps        Skip system package installation"
      echo "  --skip-docker      Skip Docker installation (assume already installed)"
      echo "  --cpu-only         Build llama.cpp without GPU support"
      echo "  --download-models  Download sample models automatically"
      echo "  --help             Show this help message"
      exit 0
    ;;
    *)
      log_error "Unknown argument: $arg"
      exit 1
    ;;
  esac
done

# ============================================================================
# SECTION 1: Directory Structure
# ============================================================================
log_info "Creating AI root directory structure at: $AI_ROOT"

mkdir -p "$AI_ROOT"/{bin,models,persona,logs,services/{api,chromadb},docker,scripts,llama_cpp,run}

# Create .gitignore for models (they're large)
cat > "$AI_ROOT/models/.gitignore" <<'EOF'
# GGUF model files - download separately
*.gguf
*.bin
# Partial downloads
*.part
EOF

log_success "Directory structure created"

# ============================================================================
# SECTION 2: System Dependencies
# ============================================================================
if [ "$SKIP_DEPS" = false ]; then
  log_info "Installing system dependencies (Debian/Mint/Ubuntu)"
  
  # Detect if we're on a Debian-based system
  if [ ! -f /etc/debian_version ] && [ ! -f /etc/lsb-release ]; then
    log_warn "This script is designed for Debian/Ubuntu systems."
    log_warn "You may need to adapt package names for your distribution."
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      exit 1
    fi
  fi

  sudo apt update
  
  # Core build dependencies
  sudo apt install -y \
    build-essential cmake git curl wget unzip pkg-config ca-certificates \
    python3 python3-venv python3-pip \
    libssl-dev

  # GPU support dependencies (optional)
  if [ "$CPU_ONLY" = false ]; then
    log_info "Installing GPU acceleration dependencies (Vulkan)"
    
    # Check for Vulkan support first
    if command -v vulkaninfo &>/dev/null; then
      log_success "Vulkan detected: $(vulkaninfo --summary 2>/dev/null | head -3 || echo 'available')"
    else
      log_warn "Vulkan not detected. Installing Vulkan libraries anyway."
      log_warn "If GPU acceleration fails, re-run with --cpu-only"
    fi
    
    sudo apt install -y libgl1-mesa-dev libvulkan-dev || {
      log_warn "Failed to install Vulkan dependencies, falling back to CPU-only build"
      CPU_ONLY=true
    }
  fi

  log_success "System dependencies installed"
else
  log_warn "Skipping system dependency installation (--skip-deps)"
fi

# ============================================================================
# SECTION 3: Docker Setup
# ============================================================================
if [ "$SKIP_DOCKER_INSTALL" = false ]; then
  log_info "Installing Docker + Compose plugin"
  
  if command -v docker &>/dev/null; then
    log_warn "Docker already installed: $(docker --version)"
  else
    sudo apt install -y docker.io docker-compose-plugin
  fi

  # Add user to docker group
  if groups | grep -q '\bdocker\b'; then
    log_success "User already in docker group"
  else
    sudo usermod -aG docker "$USER"
    log_warn "Added user to docker group. You MUST log out/in or reboot for this to take effect."
  fi
else
  log_warn "Skipping Docker installation (--skip-docker)"
fi

# ============================================================================
# SECTION 4: llama.cpp Build
# ============================================================================
log_info "Cloning & building llama.cpp"

if [ ! -d "$AI_ROOT/llama_cpp/.git" ]; then
  git clone https://github.com/ggerganov/llama.cpp.git "$AI_ROOT/llama_cpp"
else
  log_info "llama.cpp already present, updating..."
  git -C "$AI_ROOT/llama_cpp" fetch origin
  LOCAL=$(git -C "$AI_ROOT/llama_cpp" rev-parse HEAD)
  REMOTE=$(git -C "$AI_ROOT/llama_cpp" rev-parse @{u} 2>/dev/null || echo "$LOCAL")
  if [ "$LOCAL" != "$REMOTE" ]; then
    git -C "$AI_ROOT/llama_cpp" pull
  else
    log_success "llama.cpp is up to date"
  fi
fi

# Build configuration
BUILD_OPTS=()
if [ "$CPU_ONLY" = false ]; then
  BUILD_OPTS+=(-DGGML_VULKAN=ON)
  log_info "Building with Vulkan GPU support"
else
  log_info "Building CPU-only version"
fi

mkdir -p "$AI_ROOT/llama_cpp/build"
cd "$AI_ROOT/llama_cpp/build"

log_info "Running cmake configuration..."
cmake .. "${BUILD_OPTS[@]}"

log_info "Building llama.cpp (this may take several minutes)..."
NPROC=$(nproc)
cmake --build . -j"$NPROC"

# Verify build
if [ -x "$AI_ROOT/llama_cpp/build/bin/llama-server" ]; then
  log_success "llama.cpp built successfully"
  log_info "Binary: $AI_ROOT/llama_cpp/build/bin/llama-server"
else
  log_error "Build failed - llama-server binary not found"
  exit 1
fi

# ============================================================================
# SECTION 5: Configuration Files
# ============================================================================
log_info "Writing configuration files"

# Server environment configuration
cat > "$AI_ROOT/run/llama-servers.env" <<'EOF'
# AI Server Configuration
# Override these by editing this file or setting environment variables

# Context window size (tokens) - adjust based on available RAM
CTX_SIZE=8192

# Number of threads (0 = auto-detect based on CPU cores)
THREADS=0

# Host binding (use 0.0.0.0 for external access, 127.0.0.1 for local only)
HOST=127.0.0.1

# Server ports - change if these conflict with existing services
PERSONA_PORT=8080
REASONING_PORT=8081
CODER_PORT=8082

# Model filenames (must exist in ~/AI/models/)
# These are GGUF format models - download from HuggingFace
PERSONA_MODEL=persona.gguf
REASONING_MODEL=reasoning.gguf
CODER_MODEL=coder.gguf

# GPU layers to offload (-1 = all, 0 = CPU only)
# Set to 0 if you built with --cpu-only
GPU_LAYERS=-1

# Additional llama-server options
BATCH_SIZE=512
EOF

log_success "Configuration file: $AI_ROOT/run/llama-servers.env"

# ============================================================================
# SECTION 6: Server Management Scripts
# ============================================================================
log_info "Writing server management scripts"

# Start script for llama servers
cat > "$AI_ROOT/scripts/start_llama_servers.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
#
# Start llama.cpp server instances
# Usage: ./start_llama_servers.sh [--dry-run]
#
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"
ENV_FILE="$AI_ROOT/run/llama-servers.env"
DRY_RUN=false

if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
fi

# Load configuration
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Missing env file: $ENV_FILE"
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

BIN="$AI_ROOT/llama_cpp/build/bin/llama-server"
if [ ! -x "$BIN" ]; then
  echo "ERROR: llama-server not found or not executable: $BIN"
  exit 1
fi

# Resolve auto-threads
THREADS_EFFECTIVE="${THREADS:-0}"
if [ "$THREADS_EFFECTIVE" = "0" ]; then
  THREADS_EFFECTIVE="$(nproc)"
fi

# Resolve GPU layers
GPU_LAYERS="${GPU_LAYERS:--1}"

# Defaults
CTX_SIZE="${CTX_SIZE:-8192}"
HOST="${HOST:-127.0.0.1}"
BATCH_SIZE="${BATCH_SIZE:-512}"

mkdir -p "$AI_ROOT/logs" "$AI_ROOT/run"

start_server() {
  local name="$1"
  local model_file="$2"
  local port="$3"
  local pidfile="$AI_ROOT/run/${name}.pid"
  local logfile="$AI_ROOT/logs/${name}.log"
  local model_path="$AI_ROOT/models/${model_file}"

  # Check if model exists
  if [ ! -f "$model_path" ]; then
    echo "ERROR: Model missing for ${name}: $model_path"
    echo "       Place a GGUF model file at that location."
    echo "       Suggested sources:"
    echo "       - https://huggingface.co/models?search=gguf"
    return 1
  fi

  # Check if already running
  if [ -f "$pidfile" ]; then
    local existing_pid
    existing_pid=$(cat "$pidfile")
    if kill -0 "$existing_pid" 2>/dev/null; then
      echo "SKIP: ${name} already running (pid $existing_pid)"
      return 0
    else
      echo "WARN: Stale pidfile found, removing..."
      rm -f "$pidfile"
    fi
  fi

  echo "Starting ${name} server..."
  echo "  Model: $model_path"
  echo "  URL:   http://${HOST}:${port}"
  echo "  Ctx:   $CTX_SIZE tokens, Threads: $THREADS_EFFECTIVE"

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY RUN - would start server]"
    return 0
  fi

  nohup "$BIN" \
    --model "$model_path" \
    --host "$HOST" \
    --port "$port" \
    --ctx-size "$CTX_SIZE" \
    --threads "$THREADS_EFFECTIVE" \
    --batch-size "$BATCH_SIZE" \
    --n-gpu-layers "$GPU_LAYERS" \
    --log-disable \
    > "$logfile" 2>&1 &

  local pid=$!
  echo $pid > "$pidfile"
  echo "  PID:   $pid"
  echo "  Log:   $logfile"

  # Brief wait and verify it started
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "  Status: OK"
  else
    echo "  Status: FAILED (check log: $logfile)"
    return 1
  fi
}

# Start all servers
echo "============================================"
echo "Starting llama.cpp servers"
echo "============================================"

FAILED=0
start_server "persona"   "$PERSONA_MODEL"   "$PERSONA_PORT"   || FAILED=$((FAILED + 1))
start_server "reasoning" "$REASONING_MODEL" "$REASONING_PORT" || FAILED=$((FAILED + 1))
start_server "coder"     "$CODER_MODEL"     "$CODER_PORT"     || FAILED=$((FAILED + 1))

echo "============================================"
if [ $FAILED -eq 0 ]; then
  echo "All llama servers started successfully."
else
  echo "WARNING: $FAILED server(s) failed to start"
fi
echo "============================================"
SCRIPT_EOF
chmod +x "$AI_ROOT/scripts/start_llama_servers.sh"

# Stop script for llama servers
cat > "$AI_ROOT/scripts/stop_llama_servers.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
#
# Stop llama.cpp server instances
# Usage: ./stop_llama_servers.sh [--force]
#
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"
FORCE=false

if [ "${1:-}" = "--force" ]; then
  FORCE=true
fi

stop_server() {
  local name="$1"
  local pidfile="$AI_ROOT/run/${name}.pid"
  
  if [ ! -f "$pidfile" ]; then
    echo "SKIP: ${name} not running (no pidfile)"
    return 0
  fi

  local pid
  pid=$(cat "$pidfile")

  if ! kill -0 "$pid" 2>/dev/null; then
    echo "SKIP: ${name} not running (stale pidfile)"
    rm -f "$pidfile"
    return 0
  fi

  echo "Stopping ${name} (pid $pid)..."
  
  # Try graceful shutdown first
  kill "$pid" 2>/dev/null || true
  
  # Wait up to 5 seconds for graceful shutdown
  for i in {1..10}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "  Stopped gracefully"
      rm -f "$pidfile"
      return 0
    fi
    sleep 0.5
  done

  # Force kill if still running
  if kill -0 "$pid" 2>/dev/null; then
    echo "  Force killing..."
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$pidfile"
    echo "  Force stopped"
  fi
}

echo "============================================"
echo "Stopping llama.cpp servers"
echo "============================================"

stop_server "persona"
stop_server "reasoning"
stop_server "coder"

echo "============================================"
echo "All llama servers stopped."
echo "============================================"
SCRIPT_EOF
chmod +x "$AI_ROOT/scripts/stop_llama_servers.sh"

# Status check script
cat > "$AI_ROOT/scripts/status.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
#
# Check status of AI infrastructure
#
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"

echo "============================================"
echo "AI Infrastructure Status"
echo "============================================"

# Check llama servers
echo ""
echo "llama.cpp Servers:"
for name in persona reasoning coder; do
  pidfile="$AI_ROOT/run/${name}.pid"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      port=$(grep -E "^${name^^}_PORT=" "$AI_ROOT/run/llama-servers.env" 2>/dev/null | cut -d= -f2 || echo "?")
      echo "  ✓ $name: running (pid $pid, port $port)"
    else
      echo "  ✗ $name: dead (stale pidfile)"
    fi
  else
    echo "  - $name: not running"
  fi
done

# Check Docker services
echo ""
echo "Docker Services:"
if command -v docker &>/dev/null; then
  if docker ps &>/dev/null; then
    for service in ai-api ai-chromadb; do
      if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
        status=$(docker inspect -f '{{.State.Status}}' "$service" 2>/dev/null || echo "unknown")
        echo "  ✓ $service: $status"
      else
        echo "  - $service: not running"
      fi
    done
  else
    echo "  (Cannot check - docker permission denied)"
  fi
else
  echo "  (Docker not installed)"
fi

# Check model files
echo ""
echo "Model Files:"
for model in persona.gguf reasoning.gguf coder.gguf; do
  path="$AI_ROOT/models/$model"
  if [ -f "$path" ]; then
    size=$(du -h "$path" | cut -f1)
    echo "  ✓ $model: $size"
  else
    echo "  ✗ $model: missing"
  fi
done

echo ""
echo "============================================"
SCRIPT_EOF
chmod +x "$AI_ROOT/scripts/status.sh"

# ============================================================================
# SECTION 7: FastAPI Service
# ============================================================================
log_info "Writing FastAPI service files"

# Requirements with version ranges
cat > "$AI_ROOT/services/api/requirements.txt" <<'EOF'
fastapi>=0.110.0,<1.0.0
uvicorn[standard]>=0.29.0,<1.0.0
pydantic>=2.7.0,<3.0.0
httpx>=0.27.0,<1.0.0
chromadb>=0.5.0,<1.0.0
logging-config>=1.0.0,<2.0.0
tenacity>=8.0.0,<9.0.0
EOF

# Enhanced Python server
cat > "$AI_ROOT/services/api/server.py" <<'PYTHON_EOF'
"""
AI Companion API Server
Routes requests to specialized llama.cpp model servers based on topic.
"""
import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
HOST_PRIMARY = os.environ.get("HOST_PRIMARY", "host.docker.internal")
HOST_FALLBACK = os.environ.get("HOST_FALLBACK", "172.17.0.1")
PERSONA_PORT = int(os.environ.get("PERSONA_PORT", "8080"))
REASONING_PORT = int(os.environ.get("REASONING_PORT", "8081"))
CODER_PORT = int(os.environ.get("CODER_PORT", "8082"))

# Topic routing configuration
TOPIC_ROUTING = {
    "coding": {"server": "coder", "port": "CODER_PORT", "confidence": "HIGH"},
    "code": {"server": "coder", "port": "CODER_PORT", "confidence": "HIGH"},
    "programming": {"server": "coder", "port": "CODER_PORT", "confidence": "HIGH"},
    "biology": {"server": "reasoning", "port": "REASONING_PORT", "confidence": "MEDIUM"},
    "science": {"server": "reasoning", "port": "REASONING_PORT", "confidence": "MEDIUM"},
    "math": {"server": "reasoning", "port": "REASONING_PORT", "confidence": "HIGH"},
    "reasoning": {"server": "reasoning", "port": "REASONING_PORT", "confidence": "HIGH"},
    "analysis": {"server": "reasoning", "port": "REASONING_PORT", "confidence": "HIGH"},
    "chat": {"server": "persona", "port": "PERSONA_PORT", "confidence": "HIGH"},
    "general": {"server": "persona", "port": "PERSONA_PORT", "confidence": "HIGH"},
}

# HTTP client (reused across requests)
http_client: Optional[httpx.AsyncClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage HTTP client lifecycle."""
    global http_client
    http_client = httpx.AsyncClient(timeout=180.0)
    logger.info("HTTP client initialized")
    yield
    await http_client.aclose()
    logger.info("HTTP client closed")

app = FastAPI(
    title="AI Companion API",
    description="Multi-model AI routing service with specialized servers",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=32000)
    topic: str = Field(default="chat", pattern="^(chat|coding|code|programming|biology|science|math|reasoning|analysis|general)$")
    strict: bool = Field(default=False, description="Force expert escalation on low confidence topics")
    max_tokens: int = Field(default=512, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

class ChatResponse(BaseModel):
    text: str
    confidence: str
    body_cue: str
    agent_used: str
    server_host: str
    model_topic: str

class HealthResponse(BaseModel):
    status: str
    servers: dict

class ServerStatus(BaseModel):
    url: str
    healthy: bool
    latency_ms: Optional[float] = None

def get_route_info(topic: str) -> dict:
    """Get routing information for a topic."""
    return TOPIC_ROUTING.get(topic, TOPIC_ROUTING["chat"])

def confidence_body_cue(confidence: str) -> str:
    """Map confidence level to body language cue."""
    cues = {
        "HIGH": "confident",
        "MEDIUM": "thoughtful", 
        "LOW": "cautious"
    }
    return cues.get(confidence, "neutral")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True
)
async def llama_completion(host: str, port: int, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
    """Call llama.cpp server completion endpoint with retry logic."""
    url = f"http://{host}:{port}/completion"
    payload = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": temperature,
        "top_p": 0.9,
        "repeat_penalty": 1.1,
    }
    
    logger.info(f"Calling llama server: {host}:{port}")
    
    try:
        response = await http_client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        content = (data.get("content") or "").strip()
        logger.info(f"Received response: {len(content)} chars")
        return content
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from llama server: {e.response.status_code}")
        raise

async def call_llama_with_fallback(port: int, prompt: str, max_tokens: int, temperature: float) -> tuple[str, str]:
    """Call llama server with primary host, fallback to gateway on failure."""
    hosts = [
        (HOST_PRIMARY, "primary"),
        (HOST_FALLBACK, "fallback")
    ]
    
    last_error = None
    for host, label in hosts:
        try:
            result = await llama_completion(host, port, prompt, max_tokens, temperature)
            return result, host
        except Exception as e:
            logger.warning(f"{label} host ({host}) failed: {e}")
            last_error = e
            continue
    
    # Both hosts failed
    raise HTTPException(
        status_code=503,
        detail=f"All llama servers unreachable. Last error: {last_error}"
    )

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint with server status."""
    servers = {}
    
    for name, port in [("persona", PERSONA_PORT), ("reasoning", REASONING_PORT), ("coder", CODER_PORT)]:
        servers[name] = {"url": f"http://{HOST_PRIMARY}:{port}", "healthy": False, "latency_ms": None}
        try:
            import time
            start = time.time()
            response = await http_client.get(f"http://{HOST_PRIMARY}:{port}/health", timeout=2.0)
            latency = (time.time() - start) * 1000
            servers[name]["healthy"] = response.status_code == 200
            servers[name]["latency_ms"] = round(latency, 1)
        except Exception:
            pass
    
    all_healthy = all(s["healthy"] for s in servers.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "servers": servers
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Main chat endpoint with intelligent routing."""
    route = get_route_info(req.topic)
    port_name = route["port"]
    
    # Map port name to actual port
    port_map = {
        "PERSONA_PORT": PERSONA_PORT,
        "REASONING_PORT": REASONING_PORT,
        "CODER_PORT": CODER_PORT
    }
    port = port_map[port_name]
    
    confidence = route["confidence"]
    
    # Handle strict mode - escalate low/medium confidence topics
    if req.strict and confidence in ("LOW", "MEDIUM"):
        logger.info(f"Strict mode: escalating {req.topic} to reasoning server")
        port = REASONING_PORT
        confidence = "HIGH"
    
    text, host = await call_llama_with_fallback(port, req.text, req.max_tokens, req.temperature)
    
    return ChatResponse(
        text=text,
        confidence=confidence,
        body_cue=confidence_body_cue(confidence),
        agent_used=route["server"],
        server_host=host,
        model_topic=req.topic
    )

@app.get("/state")
def state():
    """State endpoint for external polling (e.g., game engine integration)."""
    return {"status": "ok", "version": "2.0.0"}

@app.get("/topics")
def list_topics():
    """List available topics and their routing."""
    return {
        "topics": list(TOPIC_ROUTING.keys()),
        "routing": TOPIC_ROUTING
    }
PYTHON_EOF

# Dockerfile
cat > "$AI_ROOT/services/api/Dockerfile" <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application
COPY server.py /app/server.py

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

log_success "FastAPI service files written"

# ============================================================================
# SECTION 8: Docker Compose Configuration
# ============================================================================
log_info "Writing Docker Compose configuration"

cat > "$AI_ROOT/docker/docker-compose.yml" <<'EOF'
services:
  chromadb:
    image: chromadb/chroma:latest
    container_name: ai-chromadb
    restart: unless-stopped
    volumes:
      - ../services/chromadb:/chroma/chroma
    environment:
      - IS_PERSISTENT=TRUE
      - PERSIST_DIRECTORY=/chroma/chroma
      - ANONYMIZED_TELEMETRY=FALSE
    ports:
      - "8001:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3

  api:
    build:
      context: ../services/api
      dockerfile: Dockerfile
    container_name: ai-api
    restart: unless-stopped
    volumes:
      - ../services/api:/app:ro
      - ../persona:/persona:ro
      - ../logs:/logs
    environment:
      - HOST_PRIMARY=host.docker.internal
      - HOST_FALLBACK=172.17.0.1
      - PERSONA_PORT=8080
      - REASONING_PORT=8081
      - CODER_PORT=8082
    ports:
      - "8000:8000"
    depends_on:
      chromadb:
        condition: service_healthy
    extra_hosts:
      - "host.docker.internal:host-gateway"
EOF

log_success "Docker Compose configuration written"

# ============================================================================
# SECTION 9: Utility Scripts
# ============================================================================
log_info "Writing utility scripts"

# Docker up script
cat > "$AI_ROOT/scripts/up.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

cd "$AI_ROOT/docker"

echo "Starting Docker services..."
docker compose up -d --build

echo ""
echo "Waiting for services to be ready..."
sleep 3

# Health check
for i in {1..30}; do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "✓ API is ready"
    break
  fi
  echo "  Waiting... ($i/30)"
  sleep 1
done

echo ""
echo "Services:"
echo "  API:     http://localhost:8000"
echo "  Docs:    http://localhost:8000/docs"
echo "  Chroma:  http://localhost:8001"
SCRIPT_EOF
chmod +x "$AI_ROOT/scripts/up.sh"

# Docker down script
cat > "$AI_ROOT/scripts/down.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

cd "$AI_ROOT/docker"
docker compose down
echo "Docker services stopped"
SCRIPT_EOF
chmod +x "$AI_ROOT/scripts/down.sh"

# Start all script
cat > "$AI_ROOT/scripts/start_all.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

echo "Starting AI infrastructure..."
echo ""

# Check for models first
MODELS_OK=true
for model in persona.gguf reasoning.gguf coder.gguf; do
  if [ ! -f "$AI_ROOT/models/$model" ]; then
    echo "WARNING: Missing model: $model"
    MODELS_OK=false
  fi
done

if [ "$MODELS_OK" = false ]; then
  echo ""
  echo "Some models are missing. Servers may fail to start."
  echo "Download models to: $AI_ROOT/models/"
  read -p "Continue anyway? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

"$AI_ROOT/scripts/start_llama_servers.sh"
echo ""
"$AI_ROOT/scripts/up.sh"
echo ""
"$AI_ROOT/scripts/status.sh"
SCRIPT_EOF
chmod +x "$AI_ROOT/scripts/start_all.sh"

# Stop all script
cat > "$AI_ROOT/scripts/stop_all.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
set -euo pipefail
AI_ROOT="${AI_ROOT:-$HOME/AI}"

echo "Stopping AI infrastructure..."
"$AI_ROOT/scripts/down.sh" || true
"$AI_ROOT/scripts/stop_llama_servers.sh" || true
echo ""
echo "All services stopped."
SCRIPT_EOF
chmod +x "$AI_ROOT/scripts/stop_all.sh"

# Model download helper
cat > "$AI_ROOT/scripts/download_models.sh" <<'SCRIPT_EOF'
#!/usr/bin/env bash
#
# Download sample GGUF models
# These are small, quantized models suitable for testing
#
set -euo pipefail

AI_ROOT="${AI_ROOT:-$HOME/AI}"
MODELS_DIR="$AI_ROOT/models"

mkdir -p "$MODELS_DIR"

# Sample models (small, suitable for testing)
# You should replace these with your preferred models
declare -A MODELS=(
  ["persona.gguf"]="https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf"
  ["reasoning.gguf"]="https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
  ["coder.gguf"]="https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
)

echo "============================================"
echo "Model Download Helper"
echo "============================================"
echo ""
echo "Downloading sample models to: $MODELS_DIR"
echo "Note: These are ~4GB each. Ensure you have disk space."
echo ""

for model_name in "${!MODELS[@]}"; do
  url="${MODELS[$model_name]}"
  dest="$MODELS_DIR/$model_name"
  
  if [ -f "$dest" ]; then
    echo "✓ $model_name already exists, skipping"
    continue
  fi
  
  echo "Downloading $model_name..."
  echo "  From: $url"
  
  # Download with progress
  wget --progress=bar:force -O "$dest.tmp" "$url" && mv "$dest.tmp" "$dest" || {
    echo "  FAILED to download $model_name"
    rm -f "$dest.tmp"
  }
done

echo ""
echo "============================================"
echo "Download complete"
echo "============================================"
ls -lh "$MODELS_DIR"/*.gguf 2>/dev/null || echo "No models downloaded"
SCRIPT_EOF
chmod +x "$AI_ROOT/scripts/download_models.sh"

# ============================================================================
# SECTION 10: Model Download (Optional)
# ============================================================================
if [ "$DOWNLOAD_MODELS" = true ]; then
  log_info "Downloading sample models..."
  "$AI_ROOT/scripts/download_models.sh"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
log_success "Setup complete!"
echo ""
echo "============================================"
echo "AI Infrastructure Ready"
echo "============================================"
echo ""
echo "Directory: $AI_ROOT"
echo ""
echo "IMPORTANT: If this is your first run:"
if [ "$SKIP_DOCKER_INSTALL" = false ]; then
  echo "  1. Log out and back in (or reboot) to apply docker group membership"
fi
echo "  2. Download models to: $AI_ROOT/models/"
echo "     Run: $AI_ROOT/scripts/download_models.sh"
echo "     Or manually place GGUF files named:"
echo "       - persona.gguf (chat/persona)"
echo "       - reasoning.gguf (analysis, science)"
echo "       - coder.gguf (programming)"
echo ""
echo "Quick Start:"
echo "   Start everything:  $AI_ROOT/scripts/start_all.sh"
echo "   Check status:      $AI_ROOT/scripts/status.sh"
echo "   Stop everything:   $AI_ROOT/scripts/stop_all.sh"
echo ""
echo "API Endpoints (after starting):"
echo "   Health:  http://localhost:8000/health"
echo "   Chat:    POST http://localhost:8000/chat"
echo "   Docs:    http://localhost:8000/docs"
echo ""
echo "Configuration:"
echo "   Servers: $AI_ROOT/run/llama-servers.env"
echo ""
echo "For help, run any script with --help"
echo ""
