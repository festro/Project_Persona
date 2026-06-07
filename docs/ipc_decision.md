# Project_Persona -- Cross-Platform IPC Decision (Phase 0.5 #4)

Status: DECISION -- ratified by Brandon 2026-06-06. NATS+JetStream is the primary
IPC / coordination backbone starting at the Phase 3 daemon, with a more-compatible
fallback transport behind a shared interface for any node where NATS is a problem.
Last updated: 2026-06-06 2105 PDT by Claude
Origin: Phase 0.5 portability hardening (roadmap.md). Settles the transport for the
Phase 3 daemon's local IPC and deliberately lays the groundwork for the Phase 10
mesh, which is already locked to NATS+JetStream (see docs/distributed_nodes.md).

Keep ASCII (see `WORKFLOW.md`).

## 1. The question

Phase 0.5 #4: pick the IPC transport for the Phase 3 always-on daemon --
"loopback TCP or NATS, not Unix socket" -- before `daemon.py` is built.

## 2. What the Phase 3 IPC has to carry

From knowledge.md ("Unix socket IPC") and roadmap Phase 3:

- One-way: components -> daemon. The API never blocks on it; a missed message must
  never stall a request.
- Local at first: same host, loopback. (NATS makes the SAME bus extend to the mesh
  later without a second mechanism -- that is the point of choosing it now.)
- Small, fixed event vocabulary: `ping` today; `profile_switched`,
  `ingest_complete`, `tts_speaking`, `task_ready` planned. Fire-and-forget
  notifications.
- Low volume, fresh-on-start (the daemon owns the endpoint each start).

## 3. Why Unix sockets are out (the constraint, restated)

AF_UNIX exists on Windows 10 1803+ as a filesystem object, but Python's asyncio
does not expose `loop.create_unix_server` / `create_unix_connection` on the Windows
ProactorEventLoop -- those APIs are Unix-only. An asyncio daemon therefore cannot
drive an AF_UNIX socket on Windows without a divergent second code path, defeating
the single-entrypoint goal of Phase 0.5. Ruled out.

## 4. Decision

Primary: NATS + JetStream. The Phase 3 daemon supervises a local `nats-server`
(JetStream replica=1) as one of its child processes and speaks to it over loopback.
The persona/API/ingest components publish events as NATS subjects. This is the same
substrate the Phase 10 mesh is already locked to, so building on it now means the
control/resource-share layer grows continuously instead of being migrated onto
later.

Fallback: a stdlib loopback-TCP bus (`LoopbackBus`, `asyncio.start_server` +
length-prefixed JSON) for any node/arch where running `nats-server` is undesirable
or unsupported. Both implement one `EventBus` interface (section 7), so the choice
is configuration, not a code fork.

Rationale:

1. Groundwork, not throwaway. NATS+JetStream is the decided mesh backbone (control
   plane + durable work queue + roster). Adopting it at the daemon means the Phase
   10 work queue, KV roster, and `$SYS`/`connz` observability land on infrastructure
   that already exists and is already supervised -- no transport migration on the
   critical path.
2. Cross-platform risk is low (section 6). `nats-server` has first-class binaries
   for every target (Win x64, Linux x64, Linux ARM64); `nats-py` is pure-Python.
   So NATS-primary does not compromise the portability posture.
3. The fallback de-risks the one soft spot. If a locked-down or exotic node cannot
   run the server binary, `LoopbackBus` keeps the daemon fully functional
   single-host. Insurance, behind the same interface.
4. One bus, not two. Using NATS for the local control plane now avoids inventing a
   local mechanism that would be retired the moment the mesh arrives.

## 5. What "NATS at Phase 3" concretely means

- `nats-server` becomes an entry in the Phase 3 daemon's child-process map, under
  the same three-strike supervision as llama-server and the API. JetStream R=1, data
  dir under `run/`, bound to loopback (mesh listeners are added only at Phase 10).
- Acquire it the portable way: a pinned `nats-server` binary placed alongside the
  other portable runtime bits (see `docs/llama_build_matrix.md` placement pattern),
  or the pip-installable `nats-server-bin` inside the portable-Python env. Pick one
  in implementation; do not require a system package.
- Add `nats-py` to the API/daemon dependency tier (NOT the lean inference-only tier
  -- it belongs with the daemon, same way torch-embed is an opt-in tier).
- Admission: reuse the shared-token shape the mesh already specifies; on a single
  host the token is loopback-scoped. On Linux restrict the token file:

```
chmod 600 run/daemon.token
```

## 6. Cross-platform verification (June 2026)

- `nats-server` publishes standalone release binaries for Windows (amd64, arm64),
  Linux (amd64, arm64, arm6/7, plus others), and macOS (amd64, arm64). All three
  Project_Persona targets -- Windows x64, Linux x64, Linux ARM64 -- are first-class.
  A pip-installable `nats-server-bin` also exists, which fits the portable-Python
  acquisition flow.
- `nats-py` (pip `nats-py`, import `nats`) is the official asyncio client (Python
  3.8+) with full JetStream, KeyValue, and ObjectStore support -- the same maturity
  cited in `docs/distributed_nodes.md` section 9 for choosing NATS over a libp2p
  gossip mesh.

Sources: see the bottom of this file.

## 7. The EventBus abstraction (keeps the fallback honest)

Call sites depend on an interface, never on a transport:

```
class EventBus:
    async def publish(self, event, payload): ...
    async def subscribe(self, event, handler): ...
```

- `NatsBus` -- default. Events map to subjects (`persona.profile_switched`,
  `persona.task_ready`, ...). At Phase 10 the same object gains the cluster /
  JetStream work-queue wiring; call sites do not change.
- `LoopbackBus` -- fallback. `asyncio.start_server` on 127.0.0.1 + length-prefixed
  JSON, token-gated, pure stdlib. Single-host only; no mesh path.

Selection: a `run/config.toml` key (e.g. `[ipc] transport = "nats" | "loopback"`,
default `nats`), with the daemon falling back to `loopback` and logging loudly if
`nats-server` is configured but cannot be started on the host.

## 8. Downstream edits (made with this decision)

- roadmap.md Phase 0.5 #4: [ ] -> [x] (NATS+JetStream primary, loopback-TCP compat
  fallback, EventBus interface).
- roadmap.md Phase 3: "Unix-socket IPC (run/daemon.sock)" -> NATS-based IPC; add
  `nats-server` to the supervised child map.
- knowledge.md "Unix socket IPC" paragraph: rewrite to the NATS-primary + fallback
  shape, keeping one-way / never-block / fresh-on-start.
- changelog.md: decision entry.
- todo.md: drop Phase 0.5 #4 from "next"; point Phase 3 work at this doc.

## 9. Open sub-questions (non-blocking)

- `nats-server` acquisition: pinned binary vs `nats-server-bin` in portable-Python.
  Resolve when the Phase 3 daemon is built.
- Whether single-host runs JetStream at all, or starts on Core NATS pub/sub and adds
  JetStream only when the Task Board / mesh needs durability. (Leaning: Core NATS for
  the Phase 3 notification bus; JetStream enters with the Task Board / Phase 10.)
- Subject namespace + event schema (shared with the Phase 10 subject design).

## Sources

- NATS server installation / platforms: https://docs.nats.io/running-a-nats-service/introduction/installation
- nats-server releases (per-platform binaries): https://github.com/nats-io/nats-server/releases
- nats-server-bin (pip): https://pypi.org/project/nats-server-bin/
- nats.py (official asyncio client): https://github.com/nats-io/nats.py
