# Project_Persona -- Distributed Cooperative Node Mesh (Design Note)

Status: DESIGN -- not started. Extended track (see `roadmap.md` Phase 10).
Last updated: 2026-06-06 0035 UTC by Claude
Origin: design discussion 2026-06-05/06 (Brandon + Claude). Decisions below are
Brandon's calls captured for the record; this note is handoff-quality on its own.

Keep ASCII (see `WORKFLOW.md`).

## 1. Vision

A decentralized, system-agnostic node mesh inspired by BOINC / Folding@home. Each
node runs the full portable Project_Persona stack, is fully self-sufficient
offline, and -- when networked -- joins a group that pools throughput and
specialized capabilities. The more systems that join, the more capacity the group
has. No node is statically privileged; nodes come and go freely.

## 2. Core reframe: distribute TASKS, not a single inference

- Splitting one model's forward pass across heterogeneous nodes over a network is
  bandwidth-bound and degrades to the weakest link. (llama.cpp has an RPC backend
  that shards layers across machines, but it wants a fast, homogeneous
  interconnect -- the opposite of "any personal device joins.") This is NOT the
  goal.
- What scales is task-level parallelism + specialization: each node runs the
  largest model it can locally, advertises what it is good at, and the mesh
  spreads independent work units and routes by capability. An AI companion
  generates plenty of this: RAG indexing, memory distillation, the Phase 7
  "sleep cycle" consolidation, file ingestion/OCR, embeddings, and Hermes
  fan-out/gather sub-tasks are all embarrassingly parallel.
- Volunteer-computing property: redundant execution + result validation is
  acceptable (even desirable). This removes the need for strong global consensus
  on task ownership and maps onto the existing Task Board `VALIDATING` state.

## 3. Transport / messaging: NATS + JetStream

Chosen over MQTT: MQTT is fine for the control plane only (no native work-queue
semantics). NATS does control plane AND a durable work queue in one small
portable Go binary, so we run one system, not two.

- Each node runs its OWN nats-server (small static binary; the local app connects
  to localhost). A node runs standalone with JetStream replica=1 and works fully
  offline.
- When networked, the per-node servers cluster as equals (full mesh, seed +
  auto-discovery). No central broker; losing any node does not take down the
  group. This is "embedded-coordinator-per-node," not a client/server hub.
- Durable layer (JetStream) uses Raft and needs an odd, stable-ish quorum (3 or
  5) for fault tolerance. Realistic shape: a small stable CORE of 3/5 peer
  servers holds the replicated streams; ephemeral nodes attach as cluster clients
  or leaf nodes and do work. Redundant execution keeps the core from being a
  per-task bottleneck.
- Control plane (identify / advertise / discover): core NATS pub/sub +
  request/reply, plus a JetStream KV bucket (TTL'd) for the live roster.
- Work plane: JetStream work-queue consumers. ack/nak, ack-wait (visibility
  timeout), and max-deliver map directly onto the Task Board lifecycle
  (QUEUED -> CLAIMED -> RUNNING -> VALIDATING) and its heartbeat / reclaim /
  attempt-max columns. A dead worker's unacked task is auto-redelivered = reclaim.
- 2-node start: a single nats-server is fine; fault-tolerant HA needs 3.

## 4. Authentication: shared admission token (DECISION)

- DECISION (Brandon): a single shared bearer token for admission. Rationale:
  friends / personal-devices group; token rotation is cheap; avoids the
  JWT/operator/PKI apparatus.
- Property: the token grants admission only -- it carries NO per-node identity.
  Anyone holding it is fully trusted at the door.
- Hard evict = rotate the token (cheap, accepted). A per-key deny-list (section 5)
  is only advisory because a banned node still holds the token and can re-key.
- Pair with TLS, or run the whole mesh over a WireGuard mesh (section 7), which
  also satisfies the egress-containment posture.

## 5. Identity, roster, and bad-actor tracking (on top of the token)

Because the token has no identity, add a lightweight identity/observability layer.

Connection log (free, server-side): NATS emits connect/disconnect events on the
system account (`$SYS.ACCOUNT.*.CONNECT` / `DISCONNECT`) and lists live
connections via the `/connz` monitoring endpoint -- IP, client-supplied
connection name, timestamps, per connection. Pipe those into an append-only log
for an automatic "who connected with the token, and when" record by hostname, no
app code required.

App roster (self-reported): each node writes a record into a TTL'd JetStream KV
bucket keyed by node id -- hostname, capabilities, version, last_seen -- so the
membership list is live and auto-expires offline nodes.

Audit stream: append-only log of joins, claims, and result submissions for
after-the-fact correlation of misbehavior to a node.

CAVEAT on hostnames: hostname and connection name are self-asserted and therefore
spoofable (a token-holder can claim any hostname, rotate it, or sybil). IP is more
grounded but NAT/DHCP blur it. So hostname = human-friendly LABEL, not a trust
anchor.

Trustworthy attribution: each node self-generates a keypair on first run (no
authority, no PKI), uses its public key as its node id, and signs heartbeats and
results. Hostname for humans, pubkey for identity. Signing also stops one
token-holder from impersonating another, so the roster/reputation point at the
right node.

Bad-actor handling: reputation comes from the validation layer, not from auth --
track per-key validation pass/fail, timeouts, and divergent results, then stop
assigning to / discard results from / advisory-deny bad keys. Two layers, stated
plainly: AUTH keeps strangers out; VALIDATION keeps bad RESULTS out (an
authenticated node can still lie). Hard evict remains token rotation.

## 6. Standalone autonomy (non-negotiable)

Every node runs the identical full portable stack and works with zero peers
(local nats-server, JetStream R=1, local model + RAG). Mesh participation is
ADDITIVE, never required. This is orthogonal to the coordination topology and is
already the project's portability posture (hence the portable-Python push).

## 7. Security / egress reconciliation

The project's offline + kernel-egress-lockdown posture conflicts with open
node-to-node networking. Resolve with a trusted mesh segment: run the mesh over
WireGuard (Tailscale, or self-hosted Netbird / headscale) so peers are reachable
only inside the mesh and the public internet stays sealed. The shared-token auth
then rides on an already-trusted network. The runtime egress-containment work
(H1.6) still applies to the model/agent layer.

## 8. Staged plan (each stage independently testable)

- Stage 0 -- cheap experiment, no new infra: the `LLAMA_HOST` offload. Point one
  node's companion API at another node's llama-server (flip the llama-server bind
  from 127.0.0.1 to the mesh address). Gate: node A returns a `/chat` reply
  generated on node B's GPU.
- Stage 1 -- 2 nodes, each running nats-server (single-server JetStream),
  shared-token admission, one work-queue stream. Gate: node B claims a task, runs
  it on its local model, returns a result; killing B mid-task triggers ack-wait
  redelivery (clean reclaim).
- Stage 2 -- identity + membership: connection log + self-generated node keys +
  TTL'd KV roster; dynamic join/advertise; capability-aware routing. Gate: a
  joining node appears in the roster by hostname+key with advertised
  capabilities and receives only work it can do.
- Stage 3 -- HA + trust: 3-server JetStream core (Raft, R=3) with ephemeral nodes
  as clients/leaf; reputation + advisory deny-list + token-rotation evict;
  redundant execution + validation/quorum for untrusted results. Gate: the core
  survives losing one member; a misbehaving key is reputation-flagged and its
  results discarded.
- Stage 4 -- optional/extended: WireGuard substrate; JetStream Object-store for
  artifact transfer; superclusters if scale demands.

## 9. Open decisions / parking lot

- Which nodes form the stable JetStream core (designated always-on boxes vs
  dynamic election).
- Capability schema (model id, VRAM, embeddings, tools, CPU class) and how a task
  declares its requirements.
- Sign results always, or only when a node's reputation is below threshold.
- Pure-gossip alternative (SWIM / libp2p, no broker at all) if the peer-cluster
  ever feels too privileged -- PARKED. NATS peer-cluster was chosen for Python
  client maturity and one-binary portability; py-libp2p is immature.

## 10. Dependencies and references

- Depends on roadmap Phase 1 (Task Board), Phase 2a (Qdrant as the networkable
  shared vector store), and Phase 3 (daemon as the node agent). Functionally a
  Phase 8-and-beyond extended track.
- Status + per-stage gates: `roadmap.md` Phase 10.
- Architecture context: `knowledge.md` (Task Board, single-model topology, egress
  posture, System components).
- NATS topics to read: clustering, JetStream (streams/consumers/KV/object-store),
  system events `$SYS`, `/connz` monitoring, token authentication.
- Inspiration: BOINC, Folding@home (centralized-coordinator volunteer computing;
  note both are client/server, not P2P).
