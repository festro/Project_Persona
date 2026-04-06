# AIP_knowledge.md — Project_Persona
**Last Updated:** 2026-04-06 | Status: PHASE 1 COMPLETE — PHASE 2 ACTIVE  
**Repo:** github.com/festro/Project_Persona  
**Live:** ~/Live/AIStack/Project_Persona/  
**Git:** ~/Git/Project_Persona/ (TBD — verify exists)  
**Domain:** layonet.org | **Target OS:** Debian Linux | **Daily Driver:** Windows  
**License:** AGPL-3.0 with Linking Exception

---

## Directory Convention

| Location | Purpose |
|---|---|
| `~/Live/AIStack/Project_Persona/` | Running personal instance — real config, real data, never pushed |
| `~/Live/AIStack/AI_TWIN/` | AIT_ running instance — separate, no shared resources |
| `~/Git/Project_Persona/` | Public template repo — sanitized, pushed to GitHub |

---

## System State (Confirmed 2026-04-06)

| Component | Status | Notes |
|---|---|---|
| llama-server (persona) port 8080 | ⚠️ Not running | Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf — 35 GPU layers |
| llama-server (scientist) port 8081 | ⚠️ Not running | Qwen2.5-14B-Instruct-Q5_K_M.gguf — 45 GPU layers, ctx 12288 |
| FastAPI Companion API port 8000 | ⚠️ Not running | uvicorn via start_api.sh |
| ChromaDB RAG | ⚠️ Unknown | Per-profile + global collections |
| Models present | ✅ Confirmed | Both GGUF files verified on disk |
| Path migration | ✅ Complete | AI_ROOT updated to ~/Live/AIStack/Project_Persona |

**Corrections from previous knowledge (ChatGPT handoff was stale):**

| Item | Was | Actual |
|---|---|---|
| Persona model | `persona.gguf` generic | `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` (4.6G) |
| Second server role | `coder` + `reasoning` | `scientist` only |
| Second model | `reasoning.gguf` / `coder.gguf` | `Qwen2.5-14B-Instruct-Q5_K_M.gguf` (9.8G) |
| GPU layers (persona) | 25 | 35 |
| GPU layers (scientist) | — | 45 |
| Third server (coder 8082) | Listed | Not present |
| AI_ROOT default | `$HOME/AI` | `$HOME/Live/AIStack/Project_Persona` |

---

## Stack

| Component | Detail |
|---|---|
| Persona server | llama-server, port 8080, Meta-Llama-3.1-8B Q4_K_M, 35 GPU layers, ctx 8192 |
| Scientist server | llama-server, port 8081, Qwen2.5-14B Q5_K_M, 45 GPU layers, ctx 12288 |
| FastAPI API | port 8000, uvicorn, services/api/server.py |
| ChromaDB | Per-profile + global Chroma collections |
| Embeddings | fastembed — BAAI/bge-small-en-v1.5 |

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
| 1 | Start stack and verify all endpoints responding | High | Not run since path migration |
| 2 | Run unified_test.sh to validate full stack | High | Confirm nothing broke in migration |
| 3 | OpenWebUI frontend — wire to FastAPI | High | Phase 2 |
| 4 | Suppress / strip `<think>` tags from scientist output | Medium | Known issue |
| 5 | Confirm AGPL-3.0 + Linking Exception LICENSE at repo root | Medium | Housekeeping |
| 6 | Review scripts/archive/ — prune if safe | Low | Housekeeping |
| 7 | Verify Git template repo exists at ~/Git/Project_Persona/ | Medium | Unclear if present |

---

## Issues & Fixes Log

| Date | Issue | Resolution |
|---|---|---|
| 2026-04-06 | AI_ROOT defaulting to $HOME/AI after move to ~/Live/AIStack/ | ✅ Fixed — sed updated all scripts |
| 2026-04-06 | Stale pid files for persona and scientist | ✅ Removed |
| 2026-04-06 | AIP_ running flat in ~/Live/AIStack/ | ✅ Moved to ~/Live/AIStack/Project_Persona/ |

---

## File Change Tracker

| Session Date | Files Modified | Summary |
|---|---|---|
| 2026-04-06 | AIP_knowledge.md | Full rewrite — actual stack confirmed, path migration documented |
| 2026-04-06 | scripts/*.sh | AI_ROOT default updated to ~/Live/AIStack/Project_Persona |

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
| *(none yet tagged in this tracker)* | — | — |

---

*This file is maintained as a living document. Update after every session.*
