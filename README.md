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

Project_Persona is also a direct alternative to gaming-niche AI companions like Razer's Project Ava. The goal here is broad human utility, not a peripheral feature. This should work for a developer, a researcher, a writer, or anyone who wants a capable, private, always-on assistant.

---

## How It Works

### The Forward-Facing Agent

At the center of Project_Persona is a **forward-facing (FF) agent** — the persona the user actually interacts with. It manages conversation, maintains context, and presents a consistent, expressive identity. This is the layer that will eventually be embodied through a real-time Godot Engine avatar.

The FF agent does not try to do everything itself. Instead, it acts as a coordinator.

### Silent Experts

Behind the FF agent is a system of **silent expert agents** — specialized models that handle discrete tasks: deep reasoning, code generation, research, retrieval. The user never interacts with them directly. They are invoked automatically based on what the task demands, their responses folded back into the persona's reply.

This separation keeps the conversational layer fast and expressive while giving the system genuine depth where it counts.

### RAG & Memory

Project_Persona uses a **Chroma-backed retrieval system** and persistent **global memory** so the agent can build genuine context over time — not just within a session, but across them. It knows what you've discussed. It remembers what matters.

### The Embodied Layer

The avatar is not cosmetic. A **Godot Engine**-driven visual presence is a core goal of this project — a real-time, expressive face for the agent that makes interaction feel less like querying a system and more like talking to someone. This is in active development.

---

## Current Stack

| Component | Details |
|---|---|
| API | Python — `services/api/server.py` |
| Persona profiles | Per-persona config + `global_memory` |
| Silent experts | Modular specialist agent system |
| RAG | Chroma vector store (port 8000) |
| Inference | llama.cpp servers (ports 8080 / 8081 / 8082) |
| GPU offload | 25-layer offload for reasoning model |
| Config | `run/llama-servers.env` |

### Key Scripts

- `start_llama_servers.sh` — bring up inference backends
- `start_api.sh` — start the Python API
- `unified_test.sh` — end-to-end system validation

---

## Roadmap

- [x] Core API with persona + silent expert routing
- [x] Chroma RAG integration
- [x] GPU-offloaded reasoning
- [ ] OpenWebUI frontend integration
- [ ] Godot Engine avatar — real-time embodied presence
- [ ] Persistent always-on daemon with event-driven triggers

---

## License

Project_Persona is released under the **GNU Affero General Public License v3.0 (AGPLv3)** with an additional linking exception.

The AGPL was chosen deliberately. Unlike standard GPL, the AGPL's network interaction clause (Section 13) ensures that anyone running a modified version of this software as a service — even without distributing binaries — must still release their modifications. For a self-hosted, networked AI agent, this is the right protection.

### Linking Exception

A Section 7 additional permission is included to allow external components — models, frontends, tools, APIs — to interact with Project_Persona without that interaction triggering license propagation to those components. This means:

- You can connect proprietary or differently-licensed tools to Project_Persona via API or IPC without being required to relicense them.
- You **cannot** modify Project_Persona's source and claim the exception covers your modifications — modified source remains fully subject to AGPLv3, including the network interaction requirement.
- You **cannot** sublicense or incorporate Project_Persona into a proprietary work in a way that would otherwise require AGPLv3 compliance of that work.

In short: the core stays open. What talks to it is your business.
