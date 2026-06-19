# MCP Gateway Evaluation -- MCPJungle (for Phase 8/9)

Date: 2026-06-18 1831 PDT
Author: Claude (with Brandon)
Status: EVALUATION (no adoption decision yet). ASCII only.
Subject: github.com/mcpjungle/MCPJungle -- a self-hosted MCP gateway/registry.
Verdict in one line: a good fit as the Phase 8/9 TOOL PLANE for the Hermes agent,
license clears, slot it when the local-MCP-server or node count grows -- not now.

================================================================================
1. WHAT IT IS
================================================================================

A self-hosted MCP gateway. You register N upstream MCP servers in it once and it
exposes them behind ONE streamable-HTTP endpoint (`/mcp`, default :8080), with
canonical `<server>__<tool>` naming, central enable/disable, "tool groups"
(curated subsets at `/v0/groups/<name>/mcp`), and -- in enterprise mode --
per-client tokens + ACLs + Prometheus metrics.

Their own mental model is three layers, which maps cleanly onto ours:
  - Upstream MCP servers  = the capabilities          -> our LOCAL servers (Kiwix shim, filesystem, time, ...)
  - MCPJungle             = control plane + gateway    -> the per-node tool hub
  - AI clients            = the consumers              -> Hermes (already an MCP client)

Single Go binary (or Docker image). DB: SQLite by default (`mcpjungle start`),
PostgreSQL for shared deployments. Stateless connections by default; stateful is
an opt-in per-server mode for slow-starting STDIO servers.

KEY REALIZATION: we are not "adding MCP" -- it is already planned. Hermes ships a
built-in MCP client (its feature set lists MCP), `persona/profiles/default/
config.yaml` already has an `mcp:` block, and the T0.2 tool-calling gate was
explicitly "needed for the Hermes/MCP agent path". So the only question is whether
to put a GATEWAY in front of the MCP servers, not whether to speak MCP.

================================================================================
2. LICENSE -- CLEARS OUR BAR
================================================================================

Mozilla Public License 2.0 (MPL-2.0). OSI-approved and explicitly AGPL-compatible
(MPL "secondary license" clause), so it satisfies the project's underlying
open / AGPL-compatible criterion. It is NOT permissive like Apache/MIT -- it is
file-level WEAK COPYLEFT: the obligation only attaches to MCPJungle's own source
files if we modify them. Run as a standalone gateway process/binary alongside our
stack it imposes nothing on our code. Conclusion: fine to adopt.

================================================================================
3. WHERE IT FITS PROJECT_PERSONA
================================================================================

- Phase 8 (Hermes), as an AGGREGATION layer. Instead of listing every MCP server
  in Hermes' `mcp:` config, Hermes points at MCPJungle's single endpoint. Its
  TOOL GROUPS map almost exactly onto the whitelist discipline the 2026-05-10
  Hermes handoff already specified ("disable web_search/web_extract/browser_*, and
  any MCP tools that aren't explicitly local; many MCP servers are themselves
  cloud APIs"). The gateway becomes the one place we curate the safe local toolset.
- Phase 9 (mesh), as a per-node TOOL HUB -- not the transport. It has centralized
  DB state, so it is a per-node (or per-trust-domain) component. NATS/JetStream
  stays the decentralized control-plane bus (Phase 3 IPC decision); MCPJungle is
  the tool plane a node exposes. DO NOT conflate the two. (And MCPJungle is itself
  centralized, NOT federated -- see section 6 on the Matrix/federation thread.)
- Egress posture. Every registered server is an egress path, so a gateway
  CENTRALIZES that risk. Done right that REINFORCES deny-by-default: bind loopback
  only, register only local/LAN servers, use enterprise ACLs once more than one
  client touches it -- one chokepoint to audit.

================================================================================
4. MATURITY / SUPPORT SNAPSHOT (from docs.mcpjungle.com support-matrix, 2026-06)
================================================================================

Stable:   Streamable-HTTP + STDIO upstream transports; Tools; Prompts; Tool
          Groups; dev mode + enterprise mode; SQLite + Postgres; stateless +
          stateful sessions; upstream static bearer-token + custom headers;
          enterprise client auth + per-client allow-lists + user accounts;
          Prometheus `/metrics`; CLI.
Beta:     Resources (and tool groups may not fully support Resources yet);
          upstream OAuth; web dashboard GUI.
Limited:  SSE (deprecated upstream transport); audit logs.
Not yet:  downstream client OAuth/SSO/OIDC; OTLP metric export.

================================================================================
5. CAUTIONS FOR OUR POSTURE
================================================================================

- AUDIT LOGGING is "Limited" and there is no OTLP export (only a Prometheus scrape).
  For a privacy-posture stack that would want a full per-tool-call egress audit
  trail, this is the real weak spot today.
- RESOURCES are only Beta. If the Kiwix/offline-knowledge shim is pictured exposing
  MCP *Resources*, that path is the least mature -- expose it as TOOLS instead and
  stay on stable ground.
- MODE IS IMMUTABLE AFTER INIT (dev <-> enterprise cannot be switched without
  re-init). If a node will ever need per-client ACLs, initialize ENTERPRISE from
  the start. Dev mode gives every client on `/mcp` access to ALL registered servers.
- RUNTIME WEIGHT: a non-Python Go binary + a DB. Mitigated: `mcpjungle start` runs
  directly on SQLite (no Docker/Postgres), so manage.py could supervise it as a
  daemon child alongside nats-server/llama-server -- fits the lean-node portability
  goal (cross-platform binary, ARM64 included).
- OVERLAP WITH HERMES: Hermes already has its own skills/tool registry AND an MCP
  client. Need a clear division of labor -- Hermes for native skills, MCPJungle for
  external MCP servers -- to avoid two tool-management layers.

================================================================================
6. RELATION TO PHASE 9 / THE "FEDERATION" THREAD
================================================================================

MCPJungle is a CENTRALIZED per-node hub, not a federation layer -- so it is NOT the
answer to "a federation of interconnectable yet independent systems" (the Phase 9
goal). That federation question is a DIFFERENT axis (inter-node identity, shared
state, trust, eviction) and is better informed by the Matrix protocol's federation
model -- see docs/distributed_nodes.md. The clean layering:
  - tool plane (per node)      : MCPJungle  (this doc)
  - message bus (intra-cluster): NATS/JetStream
  - federation/identity fabric : Phase 9 mesh design (Matrix-style prior art)

================================================================================
7. RECOMMENDATION + ADOPTION NOTES
================================================================================

Slot as a PHASE 8/9 adoption, not a Phase 0.5 task. Most valuable once there are
several local MCP servers and/or multiple agent nodes. For a single node with one
or two local MCP servers, point Hermes at them directly -- a gateway is overkill
until the server/node count grows.

When adopted:
- Run loopback-bound; register only local/LAN servers (Kiwix shim, filesystem).
- Enterprise mode if ever multi-node/multi-client (immutable -- decide at init).
- Tools (and Prompts), not Resources, for now.
- Supervise via manage.py as a daemon child (SQLite, no Docker). Their roadmap's
  declarative-config / config-driven-reconciliation-at-startup item aligns with our
  "committed config = source of truth" model -- a committed server-registry file
  reconciled at boot would mirror config.toml / config.<host>.toml.
- Treat audit-log thinness as the gap to compensate for (e.g. firewall-level egress
  logging) until upstream improves it.

OPEN ITEMS:
- Confirm Hermes' MCP client speaks streamable-HTTP to an external `/mcp` (it
  should) and how its `mcp:` config block points at a gateway endpoint.
- Decide the Hermes-native-skills vs MCPJungle-external-tools division of labor.
