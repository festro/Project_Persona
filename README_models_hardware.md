# Models & Hardware

## Model Requirements

Project_Persona does not include or distribute model files. You provide your own.

All models must be in **GGUF format**. The project uses [llama.cpp](https://github.com/ggml-org/llama.cpp) for inference, which requires GGUF. Other formats (SafeTensors, PyTorch, etc.) are not supported directly — convert them first using llama.cpp's conversion scripts or a tool like `llama.cpp/convert_hf_to_gguf.py`.

---

## Where to Get Models

[HuggingFace](https://huggingface.co) is the recommended source. Search for models with GGUF files already prepared — many community quantizations are available for direct download.

When browsing, look for files ending in `.gguf`. The quantization level affects size, speed, and quality:

| Quantization | Size | Quality | Recommended for |
|---|---|---|---|
| Q8_0 | Largest | Highest | If you have the VRAM/RAM |
| Q5_K_M | Large | Very good | Best quality/size balance — recommended |
| Q4_K_M | Medium | Good | Good balance — works well on most hardware |
| Q3_K_M | Small | Acceptable | Low-memory systems |
| Q2_K | Smallest | Reduced | Last resort — noticeable quality loss |

For most setups **Q4_K_M** or **Q5_K_M** are the right starting point.

---

## Model Roles

The system uses three model slots. Each serves a distinct purpose:

### Persona model
The only model that speaks to the user. All responses come through this model regardless of which experts were consulted. Should be a strong conversational instruct model with natural language ability.

- Recommended size: 7B–13B parameters
- Recommended quantization: Q4_K_M or Q5_K_M
- Tested with: `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`
- Search terms: `llama instruct GGUF`, `mistral instruct GGUF`, `qwen instruct GGUF`

### Reasoning model
Silent expert for analysis, science, math, and complex reasoning tasks. Never speaks to the user directly — generates structured internal notes that the persona synthesizes. Benefits from a larger, more capable model.

- Recommended size: 14B+ parameters
- Recommended quantization: Q5_K_M
- Tested with: `Qwen2.5-14B-Instruct-Q5_K_M.gguf`
- Search terms: `qwen2.5 instruct GGUF`, `deepseek instruct GGUF`, `reasoning instruct GGUF`

### Coder model
Silent expert for programming tasks and code generation. Like the reasoning model, never speaks directly — output is folded into the persona's response. A code-specialist model outperforms a general model here.

- Recommended size: 7B–14B parameters
- Recommended quantization: Q4_K_M or Q5_K_M
- Not yet validated — community testing welcome
- Search terms: `qwen2.5-coder instruct GGUF`, `deepseek-coder instruct GGUF`

---

## Placing Model Files

Put your model files in the `models/` directory inside the project folder:

```
~/AI/
└── models/
    ├── your-persona-model.gguf
    ├── your-reasoning-model.gguf
    └── your-coder-model.gguf
```

Then update `run/config.env` to match your filenames:

```
PERSONA_MODEL=your-persona-model.gguf
REASONING_MODEL=your-reasoning-model.gguf
CODER_MODEL=your-coder-model.gguf
```

The system reads filenames from `config.env` — you can name your files anything as long as the config matches. The `models/` directory is excluded from version control and will never be committed to the repository.

---

## Hardware Requirements

Performance scales with available RAM and GPU VRAM. The system is designed to run fully locally with no cloud dependency.

### Minimum — Persona only
> Single model, CPU inference. Reasoning and coder experts disabled.

- RAM: 16GB
- GPU: Not required
- Storage: ~10GB for a single 8B Q4_K_M model
- Notes: Set `ASYNC_REASONING_ENABLED=0` in `config.env`. Functional for conversational use. Complex reasoning queries will be handled by the persona model alone.

### Recommended — Full stack, CPU inference
> All three models loaded simultaneously. Experts active.

- RAM: 32GB
- GPU: Not required (optional for offload)
- Storage: ~50GB for three models (varies by size and quantization)
- Notes: Reasoning tasks will be slow on CPU alone but will complete. Expect higher latency on expert-routed queries.

### Comfortable — Full stack, partial GPU offload
> GPU acceleration reduces latency significantly on persona and reasoning models.

- RAM: 32GB
- GPU: 8GB VRAM discrete (NVIDIA CUDA or Vulkan-compatible AMD)
- Storage: ~50GB
- Notes: Partial layer offload via `GPU_LAYERS_PERSONA` and `GPU_LAYERS_REASONING` in `config.env`. Tune based on your available VRAM. Start conservative and increase until VRAM is comfortably utilized.

### Tested configuration
> Reference hardware used during development.

- System: GMKtec EVO-X2 (96GB RAM variant)
- CPU/APU: AMD Ryzen AI HX-class APU with integrated GPU
- GPU backend: Vulkan
- GPU offload: Persona 35 layers, Reasoning 45 layers
- Models: Meta-Llama-3.1-8B-Instruct-Q4_K_M (persona), Qwen2.5-14B-Instruct-Q5_K_M (reasoning)

---

## Model Licenses

Model files are not part of this project and are not covered by the Project_Persona AGPLv3 license. Each model carries its own license terms set by its creator. You are responsible for reviewing and complying with the license of any model you use.

Common licenses you will encounter on HuggingFace:

- **Apache 2.0** — permissive, commercial use allowed (e.g. Qwen2.5 series)
- **MIT** — permissive, commercial use allowed
- **Meta Llama Community License** — permits most use cases, requires attribution, restrictions apply above 700M MAU
- **Llama 3.1 Community License** — similar to above, check the specific version

Always read the model card on HuggingFace before deploying a model in a production or publicly accessible context.
