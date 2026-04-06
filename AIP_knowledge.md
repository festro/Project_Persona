# AIP_knowledge.md — Project_Persona
**Last Updated:** 2026-04-06 | Status: PHASE 1 COMPLETE — PHASE 2 ACTIVE  
**Repo:** github.com/festro/Project_Persona  
**Live:** ~/Live/AIStack/  
**Domain:** layonet.org | **Target OS:** Debian Linux | **Daily Driver:** Windows  
**License:** AGPL-3.0 with Linking Exception

---

## System State (Last Confirmed Working)

| Component | Status | Notes |
|---|---|---|
| llama-server (persona) port 8080 | ✅ Running | CPU inference — primary bottleneck |
| llama-server (reasoning) port 8081 | ✅ Running | 25-layer GPU offload |
| llama-server (coder) port 8082 | ✅ Running | CPU inference |
| FastAPI Companion API port 8000 | ✅ Running | uvicorn via start_api.sh |
| ChromaDB RAG | ✅ Running | Per-profile + global collections |
| /health endpoint | ✅ Verified | Reports latency per server |
| /chat endpoint | ✅ Verified | Persona reply + optional expert consult |
| Silent expert routing | ✅ Verified | coding→coder, reasoning→reasoning |
| Multi-profile support | ✅ Verified | default + test profiles confirmed |
| AUTO_BUDGET planner | ✅ Present | Integrated in server.py |

**Known Issues / Caveats**
- Reasoning endpoint may emit raw `<think>` tag fragments depending on model/chat template settings
- Persona server latency is the primary end-to-end bottleneck (CPU-only inference)

---

## Roadmap

### Phase 1 — Core API (COMPLETE)
- [x] llama.cpp multi-server setup (persona / reasoning / coder)
- [x] FastAPI Companion API with `/health`, `/chat`, `/profiles`, `/memory/*`, `/topics`, `/state`
- [x] Silent expert routing system
- [x] ChromaDB RAG — per-profile + global memory
- [x] Multi-profile persona wrapper (persona.md / style.md / system_rules.md)
- [x] GPU offload for reasoning model (25 layers)
- [x] AUTO_BUDGET planner
- [x] Operational scripts (start/stop/status/doctor/unified_test)

### Phase 2 — Frontend & UX (ACTIVE)
- [ ] OpenWebUI integration — wire up to FastAPI companion API (not raw model calls)
- [ ] Chat history persistence across sessions
- [ ] User-facing profile switching via UI

### Phase 3 — Always-On Daemon
- [ ] Persistent background daemon (event-driven triggers)
- [ ] Wake-word or event hook support
- [ ] Proactive memory surfacing / scheduled tasks

### Phase 4 — Embodied Presence (Godot)
- [ ] Godot Engine avatar — real-time 3D rendering
- [ ] Idle / talk / gesture animation states
- [ ] Lip-sync driven by local TTS output
- [ ] Emotion/state parsing from LLM output → avatar controller
- [ ] Desktop 2D camera view
- [ ] OpenXR / VR camera (optional, stretch goal)

### Phase 5 — Voice Pipeline
- [ ] Whisper.cpp STT integration
- [ ] Piper or Coqui TTS integration
- [ ] TTS phoneme output → Godot lip-sync bridge

---

## TODO (Active)

| # | Item | Priority | Notes |
|---|---|---|---|
| 1 | Suppress / strip `<think>` tags from reasoning model output | Medium | Known issue |
| 2 | Benchmark persona server — evaluate partial GPU offload impact on latency | High | Bottleneck |
| 3 | OpenWebUI frontend — wire to FastAPI, must not bypass identity/RAG/planner | High | Phase 2 |
| 4 | Confirm AGPL-3.0 + Linking Exception LICENSE present at repo root | Medium | Housekeeping |
| 5 | Review scripts/archive/ — determine what can be pruned | Low | Housekeeping |
| 6 | Document ChromaDB service directory in overview / README | Low | Housekeeping |
| 7 | Run unified_test.sh to validate full stack end-to-end | High | Stack health check |

---

## Issues & Fixes Log

| Date | Issue | Resolution |
|---|---|---|
| — | *(No entries yet)* | — |

---

## File Change Tracker

| Session Date | Files Modified | Summary |
|---|---|---|
| 2026-04-05 | AIP_knowledge.md | Created — initial tracker |
| 2026-04-06 | AIP_knowledge.md | Updated — renamed to AIP_ prefix, added MASTER_TODO items |

---

## Key File Reference

| File | Purpose |
|---|---|
| `services/api/server.py` | FastAPI Companion API — main application logic |
| `run/llama-servers.env` | Port / model / flag config for all llama servers |
| `scripts/start_llama_servers.sh` | Brings up all three llama-server instances |
| `scripts/start_api.sh` | Starts uvicorn / FastAPI |
| `scripts/unified_test.sh` | Full end-to-end integration test suite |
| `scripts/doctor.sh` | Diagnostics + smoke tests |
| `scripts/status.sh` | Quick status summary |
| `persona/profiles/default/` | Default profile (persona.md / style.md / system_rules.md) |
| `persona/global_memory/` | Shared cross-profile Chroma vector store |

---

## Git Milestone Log

| Tag | Description | Date |
|---|---|---|
| *(none yet tagged in this tracker)* | — | — |

---

*This file is maintained as a living document. Update after every session.*
