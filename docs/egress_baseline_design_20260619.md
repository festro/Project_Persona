# Per-OS egress baseline -- design

Status: DESIGN + first scripts. Date: 2026-06-19 0047 PDT. Author: Claude + Brandon.
Roadmap: Phase 0.5 "Per-OS egress story" Item; relates to Phase 8 runtime egress
containment (Hermes worker-jail, H1.6) and the Phase 9 WireGuard mesh.

## 1. Decision (Brandon, 2026-06-19)

- SCOPE NOW: a per-OS HOST FIREWALL default-deny-outbound baseline on the two primary
  surfaces (Windows x64 + AMD Linux via WSL). WireGuard mesh transport is DEFERRED to
  Phase 9 (it only matters once there are multiple nodes).
- DELIVERY: SCRIPTED + DOCUMENTED, NOT auto-enforced by manage.py. The launcher must
  never silently apply a default-deny firewall -- that is how you block your own model
  download. The operator runs the baseline script deliberately; manage.py only REPORTS
  posture (read-only) via doctor.

## 2. What this contains (threat model)

GOAL: a local-first assistant must not be able to phone home or exfiltrate data. The
config-level half already exists (Hermes safe-config: no cloud providers, egress tools
disabled, auxiliary.*.provider=main). This adds the NETWORK-level half: even if a
component is misconfigured or an agent tries, the OS drops the packets.

IN SCOPE: outbound connections from this host to non-loopback destinations during
steady-state serving.
OUT OF SCOPE (explicitly): inbound hardening (the services already bind 127.0.0.1 only);
a kernel sandbox / container escape (that is the Phase 8 worker-jail, sec 7); covert
channels that ride an allowed flow (e.g. DNS tunnelling -- noted, not solved here);
multi-node transport security (Phase 9 WireGuard).

This is a BLUNT, auditable baseline, not a complete sandbox. It raises the floor.

## 3. Postures

Two postures, switchable:

- SERVE (locked, the steady state): allow loopback + already-established flows; DROP all
  new outbound. The API <-> llama-server traffic is 127.0.0.1 (loopback) so it is
  unaffected; nothing new reaches the internet.
- PROVISION (temporary, during model download / setup): SERVE plus DNS (53) and HTTPS
  (443) so huggingface_hub / pip / apt can fetch. Revert to SERVE when done.

Rationale for the split: the locked allowlist the decision named is "loopback :8090/:8000
plus internet only during provisioning/setup." SERVE is the loopback-only lock; PROVISION
is the timeboxed internet window. Keeping them distinct means the normal running state is
fully contained and the internet window is explicit and short.

NOTE on DNS/HTTPS in PROVISION: allowing 443 broadly (not pinned to HF IPs) is deliberate
-- HF/CDN IP ranges drift and pinning them is brittle. DNS (53) is required for name
resolution. Both are exfil-capable while PROVISION is active; that is the accepted cost
of a download window. Mitigation: keep PROVISION on only while downloading.

## 4. Per-OS mechanism

### Linux (scripts/egress_baseline.sh -- nftables)

A dedicated table `inet persona_egress` with an `output` hook chain, policy drop:
  - `oif lo accept`                         (loopback)
  - `ct state established,related accept`   (keeps existing/SSH sessions alive)
  - PROVISION only: `udp dport 53 accept; tcp dport 53 accept; tcp dport 443 accept`
  - else: drop (the chain policy)
Isolated in its own table so `remove` is a clean `nft delete table inet persona_egress`
with zero effect on other firewalling. nftables preferred over iptables (modern default;
atomic rulesets; a `-c` dry-run check). iptables fallback is documented but not scripted
(trigger: a host without nft).

Subcommands: `plan` (default; print the ruleset, change nothing), `status` (is the table
loaded?), `apply [--provision]`, `remove`. `apply`/`remove` need root and an explicit
`--yes` (or a TTY confirm). `established,related` is accepted FIRST so applying over SSH
does not cut the session.

### Windows (scripts/egress_baseline.ps1 -- Windows Firewall)

Windows default outbound is ALLOW. Two ways to flip it, with very different blast radius:
  - SAFER (default): process-scoped block. Outbound BLOCK rules in group
    `PersonaEgress` for the stack's own binaries (llama-server.exe; optionally the API
    python.exe), with loopback/established implicitly allowed by Windows. Contains the
    persona stack specifically without touching the rest of the machine.
  - STRICT (-Strict, opt-in): set the active profile's DefaultOutboundAction=Block + add
    allow rules. True host-wide default-deny -- powerful but it can lock out the whole
    box; only for a dedicated appliance host.
Subcommands/flags: `-Status`, `-Plan`, `-Apply [-Provision] [-Strict]`, `-Remove`.
`-Remove` restores DefaultOutboundAction=Allow (if -Strict was used) and deletes the
`PersonaEgress` group. STATUS: written + reviewed; LIVE WINDOWS VERIFY IS OWED (could
not run PowerShell from the Linux dev surface).

## 5. manage.py doctor integration (read-only)

doctor gains an "Egress baseline" section that REPORTS posture and never changes it:
  - probes the OS for the persona_egress table (Linux) / PersonaEgress group (Windows),
  - classifies via the pure helper `egress_posture(present, provision_open)` ->
    one of: `serve (locked)`, `provision (internet window open)`, `none (no baseline)`,
    `unknown (cannot probe)`.
The classifier is pure + unit-tested offline; the probe runs only at the operator's
doctor invocation. doctor stays advisory -- it prints guidance ("run
scripts/egress_baseline.sh apply") when no baseline is present, but applies nothing.

## 6. How the pieces fit (now -> Phase 9)

- NOW (Phase 0.5): host firewall baseline (this doc) = the per-node egress floor.
- Phase 8 (H1.6 worker-jail): a TIGHTER, per-process containment for Hermes workers
  (kernel netns/iptables) so a delegated worker has NO network even if the host baseline
  is in PROVISION. The host baseline and the worker-jail are complementary layers.
- Phase 9 (WireGuard mesh): inter-node transport. The host firewall's allowlist will gain
  the WireGuard interface/peers as the only sanctioned non-loopback path; cross-node
  traffic rides the encrypted mesh, the internet stays denied. Designed for here: the
  nft table is the natural place to later add `oif wg0 accept`.

## 7. Verification + rollback

- Linux: `egress_baseline.sh plan` (review), `... apply --yes` (root), verify with
  `nft list table inet persona_egress` and a deliberate `curl https://example.com`
  (should hang/fail in SERVE), then `... remove --yes`. `nft -c -f <plan>` validates
  ruleset syntax without applying.
- Windows: `egress_baseline.ps1 -Plan`, `-Apply`, test an outbound call, `-Remove`.
- doctor: `manage.py doctor` shows the posture line on either OS.
- ROLLBACK is always one command (`remove` / `-Remove`); the table/group is isolated.

## 8. Owed / open

- Live-apply test of the SERVE lock on a real box (Linux apply+verify+remove); not done on
  the dev surface to avoid cutting its own connectivity.
- Windows PowerShell live verify (process-scoped + -Strict).
- iptables (non-nft) fallback script, if a target host lacks nftables.
- Decide whether PROVISION should be auto-driven by `manage.py provision` (open it for the
  download, close it after) -- NICE-TO-HAVE; deliberately NOT auto-enforced yet (keeps the
  "no silent firewalling" rule). Flag for Brandon.
