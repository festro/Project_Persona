# Project_Persona -- llama.cpp Build / Acquire Matrix (per accel)

Status: REFERENCE + action plan. Covers roadmap Phase 0.5 item #3 (audit H2).
Last updated: 2026-06-06 1934 UTC by Claude
Driver: each node needs its own llama-server build matching its hardware
(CPU / CUDA / ROCm / Vulkan) plus a compatible GGUF. There is no single artifact
that runs everywhere; this doc makes that per-node onboarding step repeatable and
feeds the mesh capability schema (Phase 10).

Keep ASCII (see `WORKFLOW.md`). Status flips go in `changelog.md`; the action item
lives in `roadmap.md` Phase 0.5.

## Scope

Supported accel (can serve GGUF via llama.cpp): CPU (always), NVIDIA CUDA, AMD
ROCm/HIP, Intel GPU via SYCL, and Vulkan (cross-vendor: NVIDIA / AMD / Intel,
including AMD Strix Halo). Best-effort / niche llama.cpp backends: OpenCL (Adreno),
CANN (Huawei Ascend NPU), MUSA (Moore Threads). Supported OS/arch: Windows + Linux,
x86-64 + ARM64 (aarch64).

Apple (macOS / Apple Silicon / Metal) is not a consideration and is omitted by
decision (see `docs/portability_audit.md`).

Inference sits behind the HTTP API, so the rest of the stack does not care which
backend a node uses -- only that a `llama-server` binary and a loadable GGUF are
present. The companion API and `manage.py` treat the binary as opaque.

## Accelerator tiers (what can actually serve GGUF)

Detection has to answer two different questions: "what accelerators are on this
host?" and "which of them can run our llama-server?" Those are NOT the same set --
several popular AI accelerators cannot run GGUF at all. Classify every detected
device into one of three tiers:

Tier 1 -- llama.cpp-capable backends the bootstrap may SELECT for llama-server.
The selector picks the best Tier-1 backend present, but only if the installed
`llama-server` binary was actually built with it (see "select only what the binary
supports" below):
- NVIDIA GPU        -> CUDA (or Vulkan)
- AMD GPU           -> ROCm/HIP (or Vulkan)
- Intel GPU (Arc / Xe iGPU / Data Center Max/Flex) -> SYCL (or Vulkan)
- Qualcomm Adreno   -> OpenCL (or Vulkan)
- Huawei Ascend NPU -> CANN
- Moore Threads GPU -> MUSA
- Any of the above (NVIDIA/AMD/Intel) -> Vulkan as the universal fallback
- (none usable)     -> CPU

Tier 2 -- present but NOT a stable llama-server backend yet. Detect and record, do
not auto-select: Intel NPU (OpenVINO backend is in progress), Snapdragon Hexagon
(in progress), WebGPU, IBM zDNN. Revisit as these stabilize upstream.

Tier 3 -- present but CANNOT run GGUF/llama.cpp at all. These have their own
runtimes and are a different inference path entirely. Detect them for capability
advertising / future non-LLM task routing in the mesh, but NEVER select them as the
llama backend (doing so is the "vestigial/incompatible component" the bootstrap is
meant to deactivate):
- Hailo-8 / Hailo-10  -> HailoRT GenAI (HEF models), not GGUF. No llama.cpp support
  (upstream feature request open, unimplemented).
- Google Coral Edge TPU -> TFLite/EdgeTPU runtime only.
- Intel Gaudi (Habana) -> SynapseAI stack, not a llama.cpp backend.

Practical consequence: a node can have a Hailo-10 or a Gaudi card and still be a
CPU-only llama node. The capability descriptor must record those accelerators as
present-but-unusable-for-LLM (with their native runtime) so the mesh does not route
GGUF work to them and the operator is not misled into thinking they accelerate the
persona.

## Decision: prebuilt first, source when needed

Prefer an official prebuilt release when one exists for the node's OS + accel; it
is the fastest path and matches what the Windows portable flow already does.
Build from source when there is no prebuilt for the accel/arch (most Linux GPU
cases, all ARM64 GPU cases, or any non-default GPU target such as Strix Halo
gfx1151 under ROCm).

Official source for both: the ggml-org/llama.cpp Releases page (prebuilt zips) and
`docs/build.md` (source flags). Pin a known-good build number `b<NNNN>` per node so
a mesh can reason about version skew.

## Where the binary must land

`manage.py` resolves the binary per OS (see `llama_binary()`), so place builds
where it looks, or override with the `LLAMA_BIN` env var:

- Windows: `llama_cpp/windows/llama-server.exe` (the official Windows zip is flat;
  extract its contents directly into that folder, DLLs alongside the exe).
- Linux: `llama_cpp/build/bin/llama-server` (the default CMake out-of-source build
  tree). Shared libs: set `LLAMA_LIB_DIR` in `run/llama-servers.env` so the
  launcher exports `LD_LIBRARY_PATH`.

## Acquire matrix -- prebuilt (Windows x64)

Windows x64 has the broadest prebuilt coverage. Release assets follow
`llama-b<NNNN>-bin-win-<accel>-x64.zip`:

- Vulkan: `llama-b<NNNN>-bin-win-vulkan-x64.zip`. Cross-vendor, no CUDA/ROCm
  toolkit needed. This is the project's current Windows path (Strix Halo via
  Vulkan). Recommended default for Windows GPU nodes when the vendor backend is
  not required.
- CUDA: `llama-b<NNNN>-bin-win-cuda-<ver>-x64.zip` PLUS the matching runtime
  `cudart-llama-bin-win-cuda-<ver>-x64.zip` (extract both into the same folder).
  As of recent releases the CUDA 12.x and 13.x lines are shipped separately --
  match the line to the installed driver.
- CPU: `llama-b<NNNN>-bin-win-cpu-x64.zip` (or an AVX2/AVX512 variant). Use when no
  usable GPU backend is present.
- HIP (AMD): Windows HIP prebuilts now exist in recent releases; if absent for a
  given build or the GPU target is unsupported, fall back to the Vulkan zip.

Acquire flow (Windows): download the chosen zip (plus the `cudart-*` zip for CUDA),
extract into `llama_cpp/windows/`, confirm `llama-server.exe` is at the folder
root, then `manage.py status` / `manage.py up --llama-only`.

## Acquire matrix -- prebuilt (Linux / ARM64)

Linux GPU prebuilts on the official Releases page are limited (historically CPU and
Vulkan; CUDA/ROCm Linux are usually source). ARM64 prebuilts are limited to CPU on
Windows ARM64 and are generally absent for Linux ARM64 GPU. Treat Linux GPU and all
ARM64 GPU as build-from-source (below). Third-party prebuilt projects exist but are
not vetted here; prefer official source builds for reproducibility.

## Build from source -- per accel

Common prerequisites: a C/C++ toolchain, CMake (>= 3.14), and git. The pattern is
an out-of-source build into `build/`, then copy or symlink the tree to
`llama_cpp/build/` (Linux) or the binary to `llama_cpp/windows/` (Windows).

Clone once:

```
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
git checkout b<NNNN>
```

### CPU (always available)

```
cmake -B build
cmake --build build --config Release -j
```

### NVIDIA CUDA

Requires the CUDA Toolkit (nvcc) matching the driver.

```
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j
```

### AMD ROCm / HIP

Requires ROCm/HIP installed. Set the HIP compiler and target the exact GPU arch
with `GPU_TARGETS` (build only what the node has). Common targets: gfx1030 (RDNA2),
gfx1100 (RDNA3), gfx1151 (Strix Halo APU; ROCm support is recent and uneven -- if
it fails to build or run, use the Vulkan path instead).

```
HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" cmake -B build -DGGML_HIP=ON -DGPU_TARGETS=gfx1100 -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j
```

### Vulkan (cross-vendor)

Requires the Vulkan SDK / loader + headers. Works across NVIDIA, AMD, and Intel,
and is the recommended path for Strix Halo and any node where the vendor toolkit is
unavailable.

```
cmake -B build -DGGML_VULKAN=ON
cmake --build build --config Release -j
```

### Intel GPU (SYCL)

For Intel Arc, Xe iGPUs, and Data Center Max/Flex. Requires the Intel oneAPI base
toolkit; source its environment first (`setvars.sh` on Linux, `setvars.bat` on
Windows) so `icx`/`icpx` are on PATH. SYCL outperforms the OpenCL path on Intel and
covers more devices. Vulkan is the simpler fallback if oneAPI is not available.

```
cmake -B build -DGGML_SYCL=ON -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx
cmake --build build --config Release -j
```

### Niche backends (OpenCL / CANN / MUSA)

Build only on the matching hardware; see `docs/build.md` for the full prerequisites:
- Qualcomm Adreno: `-DGGML_OPENCL=ON` (OpenCL backend; legacy, at risk upstream --
  prefer Vulkan where the Adreno driver supports it).
- Huawei Ascend NPU: `-DGGML_CANN=ON` (CANN toolkit).
- Moore Threads GPU: `-DGGML_MUSA=ON` (MUSA toolkit).

### ARM64 (aarch64)

Build from source with the CPU recipe (NEON/dotprod auto-detected) or the Vulkan
recipe if the device exposes a Vulkan driver (e.g. some SBC/embedded GPUs). CUDA on
ARM64 applies only to Jetson/GH-class hardware with the ARM CUDA toolkit. ARM64
also widens the Python native-wheel surface (see `docs/portability_audit.md` H1);
the lean fastembed/onnxruntime tier keeps that surface small.

## Verify a build

```
llama_cpp/build/bin/llama-server --version
```

Then bring it up and health-check through the launcher (host-agnostic):

```
python manage.py up --llama-only
python manage.py doctor --deep
```

`doctor --deep` runs a live completion smoke test against `:8090` and reports the
persona `/health`. A clean result here is the per-node acceptance test for a build.

## Capability advertising hook (design)

The mesh (Phase 10) routes work to nodes by capability, so each node must publish
what it can run. Proposed: a single descriptor the launcher can emit, derived at
runtime, written to `run/node_capabilities.json` and surfaced on the API `/health`
(and later signed into the NATS KV roster).

Proposed schema. `accel_selected` is the Tier-1 backend the node actually serves
with; `accel_present` is the full inventory (every detected device + its tier and,
for Tier 3, its native runtime) so the mesh sees the real hardware without assuming
it can run GGUF:

```
{
  "node": "<hostname>",
  "os": "windows|linux",
  "arch": "x86_64|aarch64",
  "accel_selected": "cuda|rocm|sycl|vulkan|opencl|cann|musa|cpu",
  "accel_present": [
    {"vendor": "nvidia", "device": "RTX 4090", "tier": 1, "backends": ["cuda", "vulkan"], "usable_for_llm": true},
    {"vendor": "intel", "device": "Arc A770", "tier": 1, "backends": ["sycl", "vulkan"], "usable_for_llm": true},
    {"vendor": "hailo", "device": "Hailo-10", "tier": 3, "native_runtime": "hailort", "usable_for_llm": false},
    {"vendor": "intel", "device": "Core Ultra NPU", "tier": 2, "native_runtime": "openvino", "usable_for_llm": false}
  ],
  "llama_build": "b<NNNN>",
  "llama_backends_compiled": ["vulkan", "cpu"],
  "models": ["Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf"],
  "ctx_max": 32768,
  "embedder_backend": "fastembed",
  "endpoints": {"persona": "http://127.0.0.1:8090", "api": "http://127.0.0.1:8000"}
}
```

Detection plan (best-effort, ordered, no hard dependency on any vendor tool; absence
of a probe tool means "not detected", never an error). Probe broadly, then map each
hit to a tier:

Tier 1 (selectable):
- NVIDIA: `nvidia-smi`.
- AMD: `rocminfo` / `rocm-smi`; on Linux also the amdgpu sysfs nodes.
- Intel GPU: `sycl-ls` (oneAPI), `xpu-smi`, or an Intel vendor ID (0x8086) in
  `vulkaninfo --summary` / `clinfo`.
- Generic GPU sweep: `vulkaninfo --summary` enumerates NVIDIA/AMD/Intel GPUs by
  vendor ID in one shot -- the cheapest cross-vendor probe and the Vulkan-fallback
  confirmation.
- Adreno: `clinfo` (OpenCL) / Android props. Ascend: `npu-smi`. Moore Threads:
  `mthreads-gmi`.

Tier 2 (detect, do not select): Intel NPU via the `intel_vpu` driver
(`/dev/accel/accel*` on Linux) or device enumeration; Snapdragon Hexagon.

Tier 3 (detect, never select -- record native_runtime): Hailo via `hailortcli scan`
/ `hailortcli fw-control identify`; Google Coral Edge TPU via USB/PCIe ID or the
`edgetpu` runtime; Intel Gaudi via `hl-smi`.

Selection rule -- "select only what the binary supports": the chosen
`accel_selected` must be in BOTH the detected Tier-1 set AND
`llama_backends_compiled` (parsed from `llama-server --version`). A CUDA GPU with a
Vulkan-only binary selects `vulkan`, not `cuda`; a Tier-1 device with no matching
compiled backend falls back to CPU and the node should be pointed at the right build
(this doc's source matrix). This keeps probe optimism from selecting a backend the
binary cannot actually use.

Other fields:
- llama_build / llama_backends_compiled: parse `llama-server --version` (prints the
  build number and the compiled backends).
- models: list `models/*.gguf`. ctx_max / endpoints / embedder_backend: read from
  `run/*.env` + the API `/health` (which already reports `embedder_backend`).

Integration points (incremental, do not block Phase 0.5 exit on the full hook):

1. Add `manage.py capabilities` that prints the descriptor and writes
   `run/node_capabilities.json`. Pure detection; no mesh dependency.
2. Have the API `/health` include the descriptor (or a pointer to it).
3. Phase 10 Stage 2: sign it with the per-node key and publish to the TTL'd KV
   roster (`docs/distributed_nodes.md`).

Step 1 is the only near-term piece; steps 2-3 land with the mesh.

## References

- ggml-org/llama.cpp Releases (prebuilt zips): https://github.com/ggml-org/llama.cpp/releases
- ggml-org/llama.cpp build docs (source flags): https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md
- `docs/portability_audit.md` (H2, support matrix, ARM64 wheel surface).
- `docs/distributed_nodes.md` (mesh capability routing + KV roster).
- `manage.py` (`llama_binary()` resolution; `up`/`doctor` acceptance flow).
- `README_models_hardware.md` (model sourcing + hardware tiers).
