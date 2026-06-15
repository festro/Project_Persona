# Model Provisioner -- design (first-run profile + auto-download)

Prepared: 2026-06-07 2158 PDT by Claude
Status: DESIGN (Phase 0.5). Implements the roadmap item "First-run model
auto-provisioning". ASCII only.

## Goal

On first run, `manage.py` profiles the host, consults a playbook that maps the
detected resource envelope (RAM / VRAM / CPU / accel / arch) to a ranked list of
compatible models, and downloads the best fit -- writing the model + ctx into
`run/config.toml` so the stack self-configures with no manual model fetch. Covers
a wide hardware range, from Raspberry-Pi-class SBCs (8 GB ARM, CPU-only) up to
96 GB unified / discrete-VRAM workstations. Vision capability is a PREFERRED (not
hard) requirement.

## Pipeline

```
manage.py provision  (or first-run hook)
  1. PROFILE   -> resource envelope        (extends the existing detect_* layer)
  2. MATCH     -> ranked model candidates  (playbook + matcher)
  3. CONFIRM   -> show pick + size, y/n     (--yes bypass for unattended)
  4. DOWNLOAD  -> GGUF (+ mmproj) into models/   (huggingface_hub, resumable)
  5. WIRE      -> write PERSONA_MODEL + PERSONA_CTX into run/config.toml [<os>]
```

Defaults (override-able): step 3 confirms before pulling tens of GB; step 4 uses
the `huggingface_hub` library.

## 1. Profiler enhancements

`manage.py` already detects os/arch, `cpu_count`, `ram_mb`/`ram_available_mb`,
and `accel_present[]` (vendor/device/tier/backends/usable_for_llm) -> writes
`run/node_capabilities.json` (functions: detect_ram_mb, detect_vulkan_devices,
detect_os_gpus, detect_accelerators, select_backend, detect_host). Gaps to close
for model SIZING:

- VRAM AMOUNT per accelerator (the schema names the GPU but not its memory).
  Sources: Vulkan `VkPhysicalDeviceMemoryProperties` (DEVICE_LOCAL heap), NVML /
  `nvidia-smi --query-gpu=memory.total`, ROCm `rocm-smi --showmeminfo`, Windows
  DXGI `DedicatedVideoMemory` / CIM `AdapterRAM`. Add `vram_mb` to each
  `accel_present[]` entry.
- UNIFIED vs DISCRETE memory. APUs (Strix Halo, Apple-not-supported, Pi) share
  system RAM; a discrete GPU has its own pool. Add `memory_model:
  "unified"|"discrete"` so the matcher uses total unified RAM as the budget on
  APUs but VRAM as the hard cap on discrete cards. (Vulkan `uma=1` already hints
  this; surface it.)
- NPU detect + classify (informational for model choice). Per the existing
  3-tier accel rule (`docs/llama_build_matrix.md`) and verified 2026-06:
  - Intel NPU is USABLE via the OpenVINO backend now upstream in llama.cpp (GGUF
    on Intel CPU/GPU/NPU) -> Tier 1-ish, selectable when the binary has OpenVINO.
  - Hailo / Coral NPUs are NOT usable for GGUF (own HEF/runtime) -> Tier 3,
    detect-but-never-select; never drives model choice. Surface as
    `npu_present[]` with `usable_for_llm: false`.
- RAM HEADROOM. Budget against TOTAL `ram_mb` minus a fixed OS/stack reserve
  (~3-4 GB for the API + embedder + Chroma), NOT the transient `ram_available_mb`
  -- the latter fluctuates with whatever else is running (e.g. the RX 9060 XT host
  read 2458 MB available of 31858 total while busy, which would wrongly starve the
  pick). Leave additional headroom for KV cache (grows with ctx x parallel).
- CAMERA / VIDEO INPUT. `detect_camera()` (Windows: CIM Win32_PnPEntity PNPClass
  Camera / service usbvideo; Linux: /dev/video* V4L2 nodes) -> `camera_present`.
  Drives the vision DEFAULT (section 6): vision on only when a camera exists.

### Resource envelope (matcher input)

A normalized struct derived from `node_capabilities.json`:

```
arch            x86_64 | arm64
os              windows | linux
accel           cuda | rocm | vulkan | sycl | openvino | cpu
memory_model    unified | discrete
budget_mb       discrete: min(vram_mb, ram_mb-reserve) ; unified: ram_mb-reserve
cpu_count
npu_usable      bool   (Intel/OpenVINO only)
camera_present  bool   (gates the vision default)
```

## 2. Playbook (data file, committed + human-editable)

`run/model_playbook.toml` -- an ordered catalog, NOT hardcoded in manage.py, so
picks can be curated without code changes. Each entry is a candidate with the
metadata the matcher needs:

```
[[model]]
id            = "gemma3-4b-it"
family        = "gemma3"
repo          = "ggml-org/gemma-3-4b-it-GGUF"   # HF repo id
file          = "gemma-3-4b-it-Q4_K_M.gguf"      # or a quant ladder (see below)
mmproj        = "mmproj-gemma-3-4b-it-f16.gguf"  # omit for text-only
vision        = true
license       = "gemma"                          # for the accept gate
min_ram_mb    = 8000
min_vram_mb   = 0        # 0 = CPU-capable
ctx_default   = 8192
accel_any     = ["cpu","vulkan","cuda","rocm","sycl","openvino"]
notes         = "fits 8 GB; multimodal; good Pi-class+ floor"
```

A model may list a QUANT LADDER (`Q5_K_XL -> Q4_K_M -> IQ4_XS -> ...`) so the
matcher can pick the largest quant that fits `budget_mb`, with per-quant
min_ram/min_vram. Keeps one logical model spanning several hardware tiers.

## 3. Matching algorithm

1. FILTER: keep candidates where `arch`/`os`/`accel` are compatible and the
   largest affordable quant's `min_ram_mb`/`min_vram_mb` <= envelope budget.
2. RANK: prefer (a) vision=true when a vision model fits the budget, else fall
   back to the best text-only; (b) higher capability (param count / quant); (c)
   leaving KV-cache headroom (penalize models that fill > ~80% of budget at the
   default ctx x parallel).
3. PICK top candidate; choose the largest quant that fits; choose ctx so
   `ctx x parallel` KV fits remaining budget (this is how the 16384 windows /
   32768 linux split already arises).
4. EMIT the pick + total download size for the confirm step.

Vision is a soft tie-breaker, never a hard filter: an 8 GB CPU host still gets a
working model even if the best-fitting one in budget is text-only.

## 4. Licensing principle (default catalog = open only)

Brandon's preference (2026-06-07): prefer open-source / copyleft-compatible models.
NOTE: true copyleft (GPL/AGPL) model WEIGHTS barely exist; the practical, AGPL-
project-compatible target is OSI-approved PERMISSIVE open licenses -- Apache 2.0
and MIT -- which are freely redistributable and ungated. The DEFAULT playbook
ships ONLY such models. This also removes first-run friction: no HF token, no
license click-through.

EXCLUDED from the default catalog (restrictive / gated; not OSI-open):
- Gemma (custom "Gemma Terms", use restrictions, gated download)
- Llama (Llama Community License, MAU clause, gated)
- Qwen2.5-VL-3B and -72B (Qwen license, NOT Apache -- only the 7B/32B are Apache)

These can live in an OPTIONAL `[extras]` catalog the user opts into with HF_TOKEN +
explicit license acceptance, but are never auto-selected by default.

## 4b. Seeded catalog (ALL Apache-2.0; verify repo/quant at build time)

Grounded + license-verified 2026-06-07 against llama.cpp multimodal support. Treat
as SEED DATA to curate; HF repos/filenames/quants drift and must be re-checked at
implementation (add a "catalog verified <date>" stamp in the playbook).

| Tier | Hardware envelope | Primary (vision, Apache-2.0) | Text fallback (Apache-2.0) |
|------|-------------------|------------------------------|----------------------------|
| 0 SBC/Pi | arm64/x86 CPU, 4-8 GB, no usable GPU | SmolVLM2-2.2B Q4 (Apache) | Qwen3-1.7B Q4 |
| 1 Low | 8-16 GB RAM, CPU or small iGPU | SmolVLM2-2.2B (8 GB) / Qwen2.5-VL-7B Q4 (16 GB) | Qwen3-4B Q4 |
| 2 Mainstream | 16-32 GB RAM, ~8 GB VRAM | Qwen2.5-VL-7B Q5 / Pixtral-12B Q4 | Qwen3-14B Q4 |
| 3 Enthusiast | 32-64 GB, 16 GB+ VRAM | Mistral-Small-3.1-24B (vision) / Qwen2.5-VL-32B | Qwen3-32B Q4 |
| 4 Workstation | 64-96 GB unified or 24 GB+ VRAM | Qwen3.6-35B-A3B-UD-Q5_K_XL (VL, committed model) | -- |

Every default pick is Apache-2.0 and ungated. Tier 4's primary IS the project's
committed model, so a capable host converges on exactly the current single-model
topology; smaller hosts get a sensible Apache-licensed vision substitute (SmolVLM
at the Pi/8 GB floor, Qwen2.5-VL / Pixtral / Mistral Small in the middle).

## 5. Download flow

- `huggingface_hub.hf_hub_download` (or `snapshot_download` for repo subsets):
  resumable, revision-pinned, honors `HF_TOKEN` for gated repos. Adds one dep to
  the lean tier (acceptable; embedder already pulls fastembed).
- Pull the base GGUF AND the matching mmproj (when vision); place both in
  `models/` (gitignored).
- Verify size / sha256 against the HF metadata; fail loud on mismatch.
- LICENSE GATE: the DEFAULT catalog is all Apache-2.0 + ungated, so the happy path
  needs no token or acceptance. The gate only applies to the optional `[extras]`
  catalog (Gemma/Llama/etc.): surface the license id, and on a gated 401/403 print
  the model-card URL and ask the user to accept + supply `HF_TOKEN`. Never
  auto-accept on their behalf.
- Disk preflight: check free space >= file size + 20% before starting.

## 6. Config wiring

After a successful download, write into `run/config.toml` under the active
`[<os>]` table: `PERSONA_MODEL`, `PERSONA_CTX` (from the matcher), and for vision
models `MMPROJ_PATH`. Preserve the existing fallback model in a comment for easy
rollback. (config.toml is the primary source per knowledge.md.)

VISION DEFAULT (resolved 2026-06-07, applies at EVERY tier): `VISION_ENABLED=1`
iff `camera_present` is true, else `VISION_ENABLED=0` with opt-in available. So a
webcam/capture-equipped host turns vision on automatically; a headless server
stays lean (the vision-capable model is still chosen -- preferred -- so the user
can flip VISION_ENABLED on later without re-downloading). The mmproj is fetched
alongside the base GGUF regardless, so opt-in needs no extra download.

## 7. CLI surface

- `manage.py provision [--yes] [--tier N] [--model <id>] [--text-only] [--dry-run]`
  -- run the full pipeline; `--dry-run` prints the pick + size without downloading.
- First-run hook: `cmd_up` detects no model present + no PERSONA_MODEL resolvable
  -> offers `provision` (or auto-runs it under `--yes`).
- `manage.py capabilities` keeps writing node_capabilities.json (now with vram/npu).

## 8. Open decisions (for Brandon)

- AUTOMATION DEFAULT: confirm-then-download (recommended) vs fully silent. Current
  design = confirm with `--yes` bypass. (You leaned "preferably automatically" --
  `--yes` in the installer path gets that without surprising interactive users.)
- CATALOG OWNERSHIP: who curates `run/model_playbook.toml` and how often it is
  re-verified against HF (models/quants drift). Suggest a dated "catalog verified"
  stamp in the file.
- VISION DEFAULT: RESOLVED 2026-06-07 -- camera-gated at every tier (see section 6).
  VISION_ENABLED defaults on iff a camera/capture device is detected, else off with
  opt-in; the vision-capable model + mmproj are fetched regardless. (Open sub-item:
  confirm the committed Qwen3.6 actually ships a usable vision mmproj for Tier 4.)
- GATED MODELS: RESOLVED 2026-06-07 -- default catalog is OSI-open (Apache-2.0/MIT)
  and ungated only (SmolVLM, Qwen2.5-VL 7B/32B, Pixtral, Mistral Small, Qwen3/3.6),
  which is AGPL-compatible per Brandon. Gemma/Llama/Qwen-licensed variants are an
  optional opt-in `[extras]` catalog requiring HF_TOKEN + explicit acceptance;
  never auto-selected.
- INTEL NPU: include an OpenVINO path in selection now, or defer with the rest of
  the deferred Linux/accel work?

## 9. Phasing

- P1: profiler enhancements (vram_mb, memory_model, npu classify) -- standalone,
  testable via `capabilities` on each host. CODE DONE 2026-06-07: manage.py gains
  detect_vram_mb() (nvidia-smi / Linux sysfs mem_info_vram_total / Windows registry
  qwMemorySize) + detect_memory_model() (vulkaninfo deviceType + APU-name
  heuristic); detect_host() emits vram_mb + memory_model. NPU classify already
  existed (Intel/OpenVINO tier 2 usable=false, Hailo/Gaudi tier 3). New-function
  syntax + logic verified off-host (discrete/unified/cpu correct). VALIDATED
  2026-06-07 on the RX 9060 XT (Daemonic-PC): vram_mb=16304, memory_model=discrete
  live via `manage.py capabilities`. (detect_vram_mb pivoted to a vulkaninfo
  DEVICE_LOCAL-heap parse -- cross-vendor, present in system32.) STILL PENDING: an
  EVO-X2 run to confirm memory_model "unified" on the Strix Halo APU.
- P2: playbook file + matcher. CODE DONE 2026-06-07: run/model_playbook.toml
  (10 Apache-2.0 models, quant ladders, vision flags, ranks) + scripts/
  provision_match.py (budget = max(RAM-reserve, VRAM-reserve); unified uses RAM;
  largest-fitting-quant; rank + vision/camera scoring; cpu file cap) +
  tests/test_provision_match.py (7/7 PASS offline). Picks validated: RX 9060 XT ->
  qwen3.6-35b (matches the live config), EVO unified -> qwen3.6-35b full-offload,
  mid+camera -> pixtral-12b vision, Pi headless -> qwen3-4b text, Pi+camera ->
  smolvlm2 vision, 4GB -> none. TUNABLE: the tight-budget ctx step-down (size >
  0.85*budget -> min_ctx) drops the RX 9060 XT pick to ctx 8192 vs the working
  16384 -- refine the KV-aware ctx sizing in P3/P4.
- P3: downloader + license/disk preflight + config wiring. CODE DONE 2026-06-14:
  scripts/provision_fetch.py (disk preflight = free >= size+20%; license_gate =
  Apache/MIT/BSD ungated happy path, gated needs HF_TOKEN; build_plan = base GGUF +
  mmproj when vision, skip-if-present; download via huggingface_hub, resumable, network
  branch only; verify_download light post-check on top of HF's own blob-hash verify;
  config_kv/config_block/wire_config = non-destructive [<os>] TOML edit, changed
  PERSONA_MODEL left as a `# was:` rollback breadcrumb; target_config_path prefers the
  per-host config.<host>.toml) + `manage.py provision` subcommand (match -> plan ->
  license gate -> dry-run stop / disk preflight -> confirm (or --yes) -> download ->
  OPT-IN config wiring via --write-config/--yes) + tests/test_provision_fetch.py
  (30/30 offline, stdlib-only). CONFIG-WRITE TARGET note: the design predates the
  per-host config.<host>.toml convention; wiring now writes the per-host file when one
  exists (it is that host's source of truth), else config.toml [<os>]. CONFIRMED by
  Brandon 2026-06-14: per-host file is the intended target. LIVE-CONFIRMED 2026-06-14
  on Daemonic-PC (`provision --dry-run`: qwen3.6-35b pick, weights present, per-host
  [windows] target, nothing written). ctx SAFEGUARD added (resolve_ctx + config_kv
  existing_ctx): provision preserves an existing effective PERSONA_CTX over the
  matcher's conservative tight-budget guess (which had under-set ctx to 8192 on a host
  that runs 16384); fresh hosts still take the safe conservative value. STILL OWED:
  serving-side consumption of MMPROJ_PATH/VISION_ENABLED (not yet wired into
  start_llama); `--tier` (needs a tier field added to the playbook); the deeper
  KV-aware ctx sizing (replace the section-3 0.85*budget step-down with a real KV
  headroom estimate).
- P4: first-run hook in `cmd_up` + `--yes` installer path. NOT STARTED.

Each phase lands behind the others without blocking the stack (the manual
PERSONA_MODEL path stays the fallback throughout).
