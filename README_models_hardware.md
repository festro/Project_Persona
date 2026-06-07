# Models & Hardware

## Model Requirements

Project_Persona does not include or distribute model files. You provide your own.

All models must be in **GGUF format**. The project uses [llama.cpp](https://github.com/ggml-org/llama.cpp) for inference, which requires GGUF. Other formats (SafeTensors, PyTorch, etc.) are not supported directly — convert them first using llama.cpp's conversion scripts or a tool like `llama.cpp/convert_hf_to_gguf.py`.

---

## Where to Get Models

[HuggingFace](https://huggingface.co) is the recommended source. Search for models with GGUF files already prepared — community quantizations are widely available.

Two maintainers consistently produce high-quality llama.cpp-compatible quantizations for popular models:

- **[bartowski](https://huggingface.co/bartowski)** — imatrix-calibrated K-quants and IQ-quants. Community standard for llama.cpp users.
- **[unsloth](https://huggingface.co/unsloth)** — Unsloth Dynamic 2.0 quants (UD-prefix), often outperforming standard K-quants of equivalent size.

When browsing, look for files ending in `.gguf`. The quantization level affects size, speed, and quality:

| Quantization | Size | Quality | Recommended for |
|---|---|---|---|
| Q8_0 | Largest | Near-lossless | If you have the VRAM/RAM and bandwidth |
| Q6_K / Q6_K_L | Large | Very high | Quality-first builds |
| Q5_K_M / Q5_K_XL | Large | High | **Recommended** for research-grade reasoning |
| Q4_K_M / Q4_K_L | Medium | Good | Best quality/speed balance for most setups |
| IQ4_XS | Smaller | Decent | When memory is tight |
| Q3_K_M / IQ3_M | Small | Acceptable | Low-memory systems |
| Q2_K | Smallest | Reduced | Last resort |

For most setups **Q4_K_M or Q5_K_M** are the right starting points. For independent-research-grade reasoning (biology, math, deep analysis), prefer Q5_K_M / Q5_K_XL — quantization noise compounds across long thinking traces and matters more than at casual-chat scale.

### MoE quantization note

Mixture-of-Experts (MoE) models (Qwen3-30B-A3B, Qwen3.5-35B-A3B, Qwen3.6-35B-A3B, etc.) are **slightly more sensitive to quantization noise than dense models** because the expert router uses a small projection layer that can mis-route under aggressive quantization. Default to Q5_K_M or higher for MoE models if quality matters.

---

## Model Roles (single-model topology)

Project_Persona migrated from a multi-model topology (separate persona / reasoning / coder servers) to a **single-model topology** in May 2026. One model file serves all roles via prompt engineering and the model's native thinking-mode toggle. See `HANDOFF_2026-05-09_0250_single-model-migration.md` for rationale.

The single model handles:

- **Persona role** — fast in-band conversational responses (thinking mode off)
- **Reasoning role** — research-grade analysis, math, biology, complex queries (thinking mode on)
- **Coder role** — code generation and analysis (thinking mode on, role-specific system prompt)

Role differentiation happens through:
1. The model's native `enable_thinking` toggle (Qwen3 family)
2. Per-role system prompt prefixes (consistent across requests for KV cache amortization via `cache_prompt: true`)
3. Per-role sampling parameter presets in `run/config.env`

### Recommended model

**Qwen3.6-35B-A3B** (or Qwen3-30B-A3B-Instruct-2507 as the more conservative fallback)

- 35B total / 3B activated parameters (MoE — well-matched to bandwidth-bound APUs)
- Apache 2.0 license
- Native thinking-mode toggle (`enable_thinking`)
- `preserve_thinking` flag for multi-turn agent loops
- 262K native context (extensible to ~1M via YaRN / DCA / MInference)
- Vision-Language model (image input optional, opt-in via `VISION_ENABLED`)

**Recommended quantization for the tested hardware:** Q5_K_XL (Unsloth Dynamic 2.0) — ~26 GB, comfortable on 96 GB unified memory, near-Q6 quality.

Alternative: Qwen3-30B-A3B-Instruct-2507 at Q5_K_M (bartowski imatrix) — ~22 GB, no thinking-mode toggle but otherwise current within the Qwen3 family.

The exact model lock is gated behind a llama.cpp arch-support empirical test (T0.1) — see `HANDOFF.md` Critical Path. Until that test passes, the fallback is Qwen3-30B-A3B-Instruct-2507.

---

## Placing Model Files

Put your model files in the `models/` directory inside the project folder:

```
~/Live/AIStack/Project_Persona/
└── models/
    └── Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf      ← unified model (or your choice)
```

If you enable vision (`VISION_ENABLED=1`), also include the multimodal projector:

```
└── models/
    ├── Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
    └── mmproj-F16.gguf                       ← vision projector (~900 MB)
```

Then update `run/config.env` to match your filenames:

```
PERSONA_MODEL=Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf
MMPROJ_PATH=models/mmproj-F16.gguf            # only when VISION_ENABLED=1
```

The system reads filenames from `config.env` — you can name your files anything as long as the config matches. The `models/` directory is excluded from version control.

---

## Hardware Requirements

Performance scales with available RAM and GPU bandwidth. The system is designed to run fully locally with no cloud dependency.

### Minimum — Persona only, small model

- RAM: 16 GB
- GPU: Not required
- Storage: ~10 GB for a single 8B-class Q4_K_M model
- Notes: Functional for conversational use. Use Qwen3-8B-class or smaller. Thinking mode disabled by default to save context budget.

### Recommended — Single MoE model, CPU inference

- RAM: 32 GB
- GPU: Not required (optional for offload)
- Storage: ~25 GB for Qwen3-30B-A3B Q5_K_M
- Notes: MoE models with low active-param counts (3B for Qwen3-A3B family) inference at acceptable speed on CPU because only the active experts run per token. Slower than GPU but functional.

### Comfortable — MoE model with GPU offload

- RAM: 32 GB
- GPU: 8 GB+ VRAM discrete (NVIDIA CUDA, or AMD via Vulkan/ROCm)
- Storage: ~25 GB
- Notes: Offload as many layers as fit in VRAM via `GPU_LAYERS` in `config.env`. Tune up until VRAM is ~85% utilized.

### Tested configuration (development reference)

- System: **GMKtec EVO-X2** (96 GB RAM variant)
- CPU/APU: **AMD RYZEN AI MAX+ 395** (Strix Halo, gfx1151)
- GPU backend: **Vulkan via Mesa/RADV** (native gfx1151 identification, uma=1, fp16=1, KHR_coopmat present, bf16=0)
- Memory architecture: Unified (no discrete VRAM split — full 96 GB available to both CPU and GPU)
- Tested model: Qwen3-30B-A3B Q5_K_M (target: Qwen3.6-35B-A3B Q5_K_XL pending T0.1)
- ROCm: 7.2.0 installed, used via `HSA_OVERRIDE_GFX_VERSION=11.0.1` (gfx1101 codegen workaround); Vulkan is the primary inference backend on this hardware

### Inference engine notes

llama.cpp via llama-server is the primary inference engine. **vLLM** is a documented fallback option for the case where llama.cpp doesn't support a target model architecture — vLLM has native ROCm support including for gfx1151 (with kernel 6.18.4+ for native, or via the gfx1101 override on older kernels). See `HANDOFF.md` for the inference-engine compatibility analysis.

---

## Model Licenses

Model files are not part of this project and are not covered by the Project_Persona AGPLv3 license. Each model carries its own license terms set by its creator. You are responsible for reviewing and complying with the license of any model you use.

Common licenses you will encounter on HuggingFace:

- **Apache 2.0** — permissive, commercial use allowed (Qwen3 / Qwen3.5 / Qwen3.6 series, many others)
- **MIT** — permissive, commercial use allowed
- **Meta Llama Community License** — permits most use cases, requires attribution, restrictions apply above 700M MAU
- **Llama 3.x Community License** — similar to above; check the specific version

Always read the model card on HuggingFace before deploying a model in a production or publicly accessible context.

### Vision projector

If you enable vision via `VISION_ENABLED=1`, you'll also load the multimodal projector (`mmproj-*.gguf`). These are typically published alongside the main GGUF by the same maintainer and inherit the same license. Verify on the model card.
