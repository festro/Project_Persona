# AIP_knowledge.md — Project_Persona
**Last Updated:** 2026-04-06 | Status: PHASE 1 COMPLETE — PHASE 2 ACTIVE  
**Repo:** github.com/festro/Project_Persona  
**Live:** ~/Live/AIStack/Project_Persona/  
**Git Template:** ~/Git/Project_Persona/  
**Domain:** layonet.org | **Target OS:** Debian Linux | **Daily Driver:** Windows  
**License:** AGPL-3.0 with Linking Exception

---

## Directory Convention

| Location | Purpose |
|---|---|
| `~/Live/AIStack/Project_Persona/` | Running personal instance — real config, real data, never pushed |
| `~/Live/AIStack/AI_TWIN/` | AIT_ running instance — separate, no shared resources |
| `~/Git/Project_Persona/` | Public template repo — sanitized, pushed to GitHub |
| `~/Git/AI_TWIN/` | AIT_ public template repo |

---

## System State (Confirmed 2026-04-06)

| Component | Status | Notes |
|---|---|---|
| llama-server (persona) port 8080 | ✅ Running | Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf — 35 GPU layers, ctx 8192 |
| llama-server (scientist) port 8083 | ✅ Running | Qwen2.5-14B-Instruct-Q5_K_M.gguf — 45 GPU layers, ctx 12288 |
| FastAPI Companion API port 8000 | ✅ Running | uvicorn via start_api.sh |
| ChromaDB RAG | ✅ Running | Fresh init — global_memory/chroma/ wiped and reinitialised |
| /health endpoint | ✅ Verified | All components reporting ok |
| /chat endpoint | ✅ Verified | End-to-end chat confirmed working |
| Embedder | ✅ Running | BAAI/bge-small-en-v1.5 via fastembed |

**Port mapping (confirmed):**
| Server | Port | Notes |
|---|---|---|
| persona | 8080 | ✅ |
| scientist | 8083 | Changed from 8081 — conflict with OTS/BrandonNet docker container |
| API | 8000 | ✅ |

**Known conflicts:**
- Port 8081 — OTS (OpenTAK Server) docker container from BrandonNet
- Port 8082 — BrandonNet docker container
- Port 8088/8089 — BrandonNet docker containers

---

## Stack

| Component | Detail |
|---|---|
| Persona server | llama-server, port 8080, Meta-Llama-3.1-8B Q4_K_M, 35 GPU layers, ctx 8192 |
| Scientist server | llama-server, port 8083, Qwen2.5-14B Q5_K_M, 45 GPU layers, ctx 12288 |
| FastAPI API | port 8000, uvicorn, services/api/server.py |
| ChromaDB | global_memory/chroma/ — fresh init 2026-04-06 |
| Embeddings | fastembed — BAAI/bge-small-en-v1.5 |
| venv | ~/Live/AIStack/Project_Persona/env/ — rebuilt 2026-04-06 |

---

## Roadmap

### Phase 1 — Core API (COMPLETE)
- [x] llama.cpp multi-server setup (persona + scientist)
- [x] FastAPI Companion API with `/health`, `/chat`, `/profiles`, `/memory/*`, `/topics`, `/state`
- [x] Silent expert routing system
- [x] ChromaDB RAG — per-profile + global memory
- [x] Multi-profile persona wrapper (persona.md / style.md / system_rules.md)
- [x] GPU offload for both models
- [x] AUTO_BUDGET planner
- [x] Operational scripts (start/stop/status/doctor/unified_test)

### Phase 2 — Frontend & UX (ACTIVE)
- [ ] OpenWebUI integration — wire to FastAPI, must not bypass identity/RAG/planner
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
- [ ] OpenXR / VR camera (optional)

### Phase 5 — Voice Pipeline
- [ ] Whisper.cpp STT integration
- [ ] Piper or Coqui TTS integration
- [ ] TTS phoneme output → Godot lip-sync bridge

---

## TODO (Active)

| # | Item | Priority | Notes |
|---|---|---|---|
| 1 | Run unified_test.sh — full end-to-end validation | High | Stack just migrated, needs full test |
| 2 | OpenWebUI frontend — wire to FastAPI | High | Phase 2 |
| 3 | Suppress / strip `<think>` tags from scientist output | Medium | Known issue |
| 4 | Confirm AGPL-3.0 + Linking Exception LICENSE at repo root | Medium | Housekeeping |
| 5 | Review scripts/archive/ — prune if safe | Low | Housekeeping |
| 6 | Add AIP_ entry to ~/Git/sterilize.sh | Medium | Currently only Netstack is covered |

---

## Issues & Fixes Log

| Date | Issue | Resolution |
|---|---|---|
| 2026-04-06 | AI_ROOT defaulting to $HOME/AI after directory migration | ✅ Fixed — sed updated all scripts |
| 2026-04-06 | Stale pid files for persona and scientist | ✅ Removed |
| 2026-04-06 | AIP_ running flat in ~/Live/AIStack/ | ✅ Moved to ~/Live/AIStack/Project_Persona/ |
| 2026-04-06 | Port 8081 conflict with OTS BrandonNet container | ✅ Scientist moved to 8083 |
| 2026-04-06 | llama-server missing libmtmd.so.0 at runtime | ✅ LD_LIBRARY_PATH injected in start_llama_servers.sh |
| 2026-04-06 | venv shebangs pointing to old $HOME/AI path | ✅ venv rebuilt with --clear |
| 2026-04-06 | server.py syntax error — escaped docstring quotes | ✅ Restored correct triple-quote docstring |
| 2026-04-06 | start_api.sh not sourcing llama-servers.env | ✅ Source block added before exports |
| 2026-04-06 | Chroma KeyError('_type') — version mismatch | ✅ Old sqlite3 data wiped, fresh init |
| 2026-04-06 | chromadb Settings() API changed in 0.6.x | ✅ Settings parameter removed from PersistentClient call |

---

## File Change Tracker

| Session Date | Files Modified | Summary |
|---|---|---|
| 2026-04-06 | scripts/start_llama_servers.sh | LD_LIBRARY_PATH injection, AI_ROOT path fix |
| 2026-04-06 | scripts/start_api.sh | Source llama-servers.env, AI_ROOT path fix |
| 2026-04-06 | run/llama-servers.env | SCIENTIST_PORT changed 8081→8083 |
| 2026-04-06 | services/api/server.py | Syntax fix, chromadb Settings removed |
| 2026-04-06 | AIP_knowledge.md | Created — full session state captured |

---

## Key File Reference

| File | Purpose |
|---|---|
| `services/api/server.py` | FastAPI Companion API |
| `run/llama-servers.env` | Port / model / GPU layer config |
| `scripts/start_llama_servers.sh` | Brings up persona + scientist servers |
| `scripts/start_api.sh` | Starts uvicorn / FastAPI |
| `scripts/unified_test.sh` | Full end-to-end integration test |
| `scripts/doctor.sh` | Diagnostics + smoke tests |
| `scripts/status.sh` | Quick status summary |
| `persona/profiles/default/` | Default profile (persona.md / style.md / system_rules.md) |
| `persona/global_memory/` | Shared cross-profile Chroma vector store |

---

## Git Milestone Log

| Tag | Description | Date |
|---|---|---|
| v1.1-post-migration | Full stack running at ~/Live/AIStack/Project_Persona/ | 2026-04-06 |

---

*This file is maintained as a living document. Update after every session.*
