# Project_Persona

> *An open, self-hosted AI agent with an embodied presence — built for everyone, owned by no one.*

---

## What This Is

Project_Persona is a general-purpose, always-on AI assistant designed to live on your own hardware, speak in your own space, and answer to no corporation's terms of service. It is not a chatbot. It is not a product. It is a foundation for a new kind of human-computer relationship.

Where commercial AI assistants are locked behind subscriptions, usage caps, and data harvesting, Project_Persona is yours — fully self-hosted, fully inspectable, and fully under your control.

This project was inspired by the vision of a Jarvis-style assistant: one that thinks, coordinates, and responds not just as a text box on a screen, but as a present, expressive entity you can interact with naturally. That vision is what drives every architectural decision here.

---

## The Philosophy

This project is released under a copyleft license — deliberately.

The belief behind that choice is simple: technology should be accessible, and the work of open communities should not be strip-mined to build closed, proprietary walls. If you build on this, what you build must remain open. That is not a restriction — it is an invitation to contribute to something that belongs to everyone.

Project_Persona is a direct alternative to gaming-niche AI companions like Razer's Project Ava. The goal here is broad human utility, not a peripheral feature. This should work for a developer, a researcher, a writer, or anyone who wants a capable, private, always-on assistant.

---

## How It Works

### The Forward-Facing Persona

At the center of Project_Persona is a **forward-facing persona** — the consistent identity the user actually interacts with. It manages conversation, maintains context, and presents an expressive identity. This layer is designed to eventually be embodied through a real-time Godot Engine avatar.

The persona handles trivial queries directly through a fast in-band response cycle. For non-trivial work — research, multi-step reasoning, code generation, long-running agentic tasks — it routes through a Task Board to a separate agent backbone.

### The Agent Backbone (Hermes)

Heavy work is delegated to **[Hermes Agent](https://hermes-agent.nousresearch.com)** (Nous Research, MIT-licensed) running as a daemon child process. Hermes has its own multi-step orchestration, subagent delegation (fan-out/gather), tool registry, and durable Kanban-style work tracking. The persona never waits — Hermes processes asynchronously and the persona surfaces results when ready.

This separation keeps the conversational layer fast and expressive while giving the system genuine depth where it counts.

### Single Unified Model

Inference is served by a single **Qwen3-family MoE model** via llama.cpp with parallel slots and continuous batching. Role differentiation (persona / reasoning / coder) happens through prompt engineering and the model's native thinking-mode toggle, not through separate model deployments. This gives the throughput of slot-based concurrency with the simplicity of one set of weights.

### Memory & Context

Project_Persona uses **Qdrant** for typed semantic memory — facts, episodes, entities, decisions — built up over time across sessions. Combined with Hermes' own session-lineage memory, this gives the agent both knowledge depth and conversational continuity.

A **Sorting Line** auto-classifies files dropped into `inbox/` and routes them into the right memory collections. A **Sleep Cycle** runs during idle periods to consolidate, summarize, and discover relationships across memory.

### The Embodied Layer

A **Godot Engine** avatar is a core goal — a real-time, expressive face for the agent that makes interaction feel less like querying a system and more like talking to someone. The two-channel response protocol (text response + JSON state directives) supports lip-sync from voice synthesis phoneme timing and emotion/gesture state for the avatar.

---

## Current Stack

| Layer | Component | License | Status |
|---|---|---|---|
| Inference | llama.cpp via llama-server (Vulkan backend) | MIT | ✅ Working |
| Model | Qwen3-family MoE (Q5_K_M/Q5_K_XL) | Apache 2.0 | ⏳ Migrating to single-model topology |
| API | FastAPI Companion API (Python, port 8000, OpenAI-compatible) | MIT | ✅ Running |
| Vector store | Qdrant (planned) — replacing ChromaDB | Apache 2.0 | ⏳ Phase 2a |
| Agent backbone | Hermes Agent (Nous Research) | MIT | ⏳ Planned daemon child |
| Frontend | OpenWebUI (port 3000) | BSD-3 + branding clause | ✅ Running |
| Voice (planned) | Whisper.cpp (STT) + Piper TTS + Wyoming protocol | MIT / GPL-3.0 / MIT | ⏳ Phase 5 |
| Avatar (planned) | Godot Engine | MIT | ⏳ Phase 4 |
| Profile structure | 2-file per profile: `SOUL.md` + `.hermes.md` (Hermes naming) | — | ✅ Convention locked |

### Hardware reference

Tested on a **GMKtec EVO-X2** (AMD RYZEN AI MAX+ 395, Strix Halo iGPU, 96GB unified memory, Vulkan via Mesa/RADV). See `README_models_hardware.md` for hardware tier guidance.

### Key files

- `HANDOFF.md` — living "where are we right now and what's next" document; open this first when resuming work
- `HANDOFF.html` — same content, browser-renderable with TOC and collapsible sections
- `knowledge.md` — long-form rolling project state, system components, full roadmap, all TODO blocks
- `HANDOFF_YYYY-MM-DD_HHMM_*.md` — frozen decision records for major milestones
- `archive/` — superseded historical docs (AIP_knowledge.md, Mercury borrow plan addendum, etc.)

---

## Roadmap

The project is organized into phases and tiered work blocks. Current state and detailed acceptance criteria live in `HANDOFF.md` (current state) and `knowledge.md` (long-form roadmap). High-level summary:

- ✅ Core API with persona response + per-profile structure
- ✅ ChromaDB RAG (global memory)
- ✅ GPU offload via Vulkan on tested hardware
- ✅ OpenWebUI frontend integration (locked as primary)
- 🔄 Single-model migration (Qwen3-family with parallel slots; replaces multi-model topology)
- 🔄 Hermes Agent integration as daemon-managed agent backbone
- ⏳ Qdrant vector store migration (replaces ChromaDB)
- ⏳ Always-on daemon with three-strike restart, asyncio child process management
- ⏳ Godot Engine avatar — real-time embodied presence
- ⏳ Voice pipeline (Whisper.cpp + Piper TTS via Wyoming)
- ⏳ Auto-Contextual RAG ("Sorting Line") — drop file into `inbox/`, system classifies and routes
- ⏳ Background Cognitive Consolidation ("Sleep Cycle") — idle-triggered memory maintenance

---

## License

Project_Persona is released under the **GNU Affero General Public License v3.0 (AGPLv3)** with an additional Section 7 linking exception.

The AGPL was chosen deliberately. Unlike standard GPL, the AGPL's network interaction clause (Section 13) ensures that anyone running a modified version of this software as a service — even without distributing binaries — must still release their modifications. For a self-hosted, networked AI agent, this is the right protection.

### Linking Exception

A Section 7 additional permission is included to allow external components — models, frontends, tools, APIs — to interact with Project_Persona without that interaction triggering license propagation to those components. This means:

- You can connect proprietary or differently-licensed tools to Project_Persona via API or IPC without being required to relicense them.
- You **cannot** modify Project_Persona's source and claim the exception covers your modifications — modified source remains fully subject to AGPLv3, including the network interaction requirement.
- You **cannot** sublicense or incorporate Project_Persona into a proprietary work in a way that would otherwise require AGPLv3 compliance of that work.

In short: the core stays open. What talks to it is your business.

### Component licenses

Each upstream dependency carries its own license. See the License Review section of `knowledge.md` for a full per-component table. Notable points:

- **Models are not part of this project's license.** Model files are user-provided, gitignored, and subject to the upstream model's license terms. See `README_models_hardware.md`.
- **OpenWebUI** has a BSD-3 + branding clause — used as a dependency, not redistributed.
- **Hermes Agent** is MIT — cleanly absorbed by AGPLv3 + linking exception when used as an integrated component.
