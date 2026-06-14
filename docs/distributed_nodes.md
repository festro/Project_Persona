# Project_Persona -- Distributed Cooperative Node Mesh (Design Note)

Status: DESIGN -- not started. Extended line beyond the core ladder (see
`roadmap.md` Phase 9).
Last updated: 2026-06-14 1535 PDT by Claude (+section 5b coordinated eviction +
node_id, Brandon's proposal; renumbered to Phase 9 earlier)
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
- Hard evict = rotate the token (cheap, accepted). On its own a per-key deny-list
  (section 5) is only advisory: a banned node still holds the token and can
  self-generate a fresh key to dodge the deny entry. Section 5b (coordinated
  re-key + a hardware-anchored node id, Brandon 2026-06-14) upgrades this to an
  ENFORCEABLE eviction -- the honest nodes rotate the token among themselves
  (excluding the actor) and deny by stable node id, which survives a re-key.
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
authority, no PKI), signs heartbeats and results. Signing stops one token-holder
from impersonating another, so the roster/reputation point at the right node.

Stable node id (Meshtastic-style, Brandon 2026-06-14): a freshly generated keypair
is trivially regenerated, so a bad actor re-keys and a per-key deny entry misses.
Add a STABLE per-node id derived at `manage.py` first boot by hashing gathered
system specs (machine-id, board/CPU/disk serials where readable cross-OS, primary
NIC MAC) with a per-node salt, persisted alongside `run/node_capabilities.json`.
Embed this id in the message layer and BIND it to the signing keypair (the node
signs `node_id = X`). Three distinct roles: hostname = human label, keypair =
message authenticity, node_id = stable machine anchor. Because node_id does NOT
change when an actor re-keys, the deny-list can target it. CAVEAT: system specs are
spoofable, so node_id is a sybil / re-key DETERRENT, not proof -- token rotation
(section 5b) stays the hard guarantee, and a hardware change forces re-enrollment.
Salt + hash so raw specs are never exposed on the wire.

Bad-actor handling: reputation comes from the validation layer, not from auth --
track per-key validation pass/fail, timeouts, and divergent results, then stop
assigning to / discard results from / advisory-deny bad keys. Two layers, stated
plainly: AUTH keeps strangers out; VALIDATION keeps bad RESULTS out (an
authenticated node can still lie). Hard evict remains token rotation.

## 5b. Coordinated eviction + key rotation (proposal, Brandon 2026-06-14)

The concrete mechanism behind "hard evict = rotate the token" (section 4), built
on the token + the section 5 identity layer. Goal: omit a compromised node so it
cannot rejoin, without standing PKI.

1. Detect + gossip. The validation/reputation layer flags a bad node id. The
   honest nodes gossip the flag among themselves over the authenticated mesh; the
   flagged node is excluded from this exchange.
2. Joint re-key. Once a quorum of honest nodes agrees, they jointly rotate the
   shared admission token. The new token is distributed only to known-good node
   ids; the flagged node is disconnected and never receives it. Deny-by-node-id
   (section 5) means even a re-key by the actor does not get it back in.
3. Recovery for nodes that missed the rotation. A legitimate node that was OFFLINE
   during the re-key returns holding the old, now-invalid token. It is re-keyed
   OUT OF BAND from an already-updated node over NFC or Bluetooth (physical
   proximity = the trust gesture), with a QR-code / manual-paste fallback for
   headless nodes (e.g. EVO-X2) that have no NFC/BT radio.

Must be nailed down before this is safe (tracked in section 9):

- AUTHORIZATION QUORUM. A single compromised node must not be able to trigger a
  rotation that expels honest nodes (eviction-as-attack). Require a quorum to
  authorize a re-key -- e.g. the stable 3/5 JetStream core, or N reputation-weighted
  nodes.
- CUTOVER WINDOW. Push the new token to all currently-connected good nodes and
  disconnect the actor BEFORE invalidating the old token, so slow-but-honest nodes
  are not locked out mid-rotation.
- SPLIT-BRAIN. A network partition could let two halves independently evict and
  rotate to DIFFERENT tokens, then refuse to re-merge. The OOB proximity re-key
  (step 3) is the manual bridge; an automatic reconcile rule is still owed.

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

Stage <-> roadmap Item map (Phase 9): Stage 0 = Item 9.1, Stage 1 = 9.2,
Stage 2 = 9.3, Stage 3 = 9.4, Stage 4 = 9.5. Item 9.0 (EVO-X2 migration to the
anchor node) is the precondition for all of them. The roadmap is the status
source of truth; the "Stage" labels here are this design note's own narrative.

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
- Section 5b coordinated eviction: the re-key authorization quorum, the cutover
  window, and the split-brain reconcile rule (above).
- node_id derivation: which system specs are stable AND readable cross-OS
  (machine-id, DMI/board/disk serials, NIC MAC), the salt scheme, and the
  re-enrollment path on a hardware change.
- OOB re-key transport: NFC/BT where present vs the QR/manual fallback; treat that
  enrollment channel as a trust surface (proximity-gated).

## 10. Dependencies and references

- Depends on roadmap Phase 1 (Task Board), Phase 2a (Qdrant as the networkable
  shared vector store), and Phase 3 (daemon as the node agent). Functionally a
  Phase 8-and-beyond extended line.
- Status + per-Item gates: `roadmap.md` Phase 9 (Items 9.0-9.5).
- Architecture context: `knowledge.md` (Task Board, single-model topology, egress
  posture, System components).
- NATS topics to read: clustering, JetStream (streams/consumers/KV/object-store),
  system events `$SYS`, `/connz` monitoring, token authentication.
- Inspiration: BOINC, Folding@home (centralized-coordinator volunteer computing;
  note both are client/server, not P2P).
