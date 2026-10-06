# Handoff -- Project_Persona

Date/time: 2026-10-06 1007 PDT (session began 2026-09-29 0438 PDT)
Author: Claude (Claude Code on the web, cloud container, driven from Brandon's phone)
Convention: dated handoff (handoff_persona_YYYYMMDD_HHMM). ASCII only.
To resume: "continue from handoff_persona_20261006_1007.md".
Prior handoff: handoff_persona_20260629_0415.md. This session was REMOTE-ACCESS plumbing only:
no code, config or stack changes. The repo is PUBLIC -- this file deliberately omits the
NetBird management domain, the home WAN IP and every credential.

================================================================================
0. ORIENTATION
================================================================================

- Goal: reach the home nodes (EVO-X2, Daemonic-PC) while away, from the phone, via NetBird.
- A Claude Code on the web session runs in an Anthropic cloud container. It is NOT on the home
  LAN and NOT on the NetBird mesh. Brandon's phone being on NetBird does not help: the phone only
  renders the chat, every command executes in the cloud.
- WORKING PATH (proven): `claude remote-control` on EVO-X2 inside tmux. That session shows up in
  the Claude app and has real LAN + NetBird reach.

================================================================================
1. WHAT WAS TRIED / FOUND
================================================================================

(A) Direct LAN from the cloud -> FAILED (expected). 192.168.8.114 :22/:8090/:8000 unreachable.

(B) Join the cloud container to NetBird -> FEASIBLE BUT NOT DONE.
  - Container has /dev/net/tun + full caps; netbird 0.79.0 installed from pkgs.netbird.io.
  - Needs a setup key (or an API token to mint one). Not completed because of (C).

(C) NetBird management API from the cloud -> BLOCKED BY DESIGN.
  - NetBird is SELF-HOSTED (not app.netbird.io); a PAT sent to the cloud API returns 404
    "token not found" (correct: it only exists on the self-hosted server).
  - Self-hosted management (:443 and :33073): TCP connects, TLS ClientHello is RESET by the far
    end. Cause = Brandon's IP filter on the domain. Cloud egress came from 160.79.106.132/.136
    (shared pool). Decision: DO NOT allowlist a shared cloud range just for this.

(D) Remote Control on EVO-X2 -> WORKING.
  - Steps that worked (in tmux session "claude"):
      claude            then /login (claude.ai subscription option), then /exit
      claude remote-control --spawn=same-dir
  - Gotcha: first attempt failed "401 OAuth access token is invalid" -> stale login; fixed by
    /login INSIDE claude (typing /login at bash gives "No such file or directory").
  - Registered session title seen: daemonic-evox2-prancy-cloud (connected, 2026-09-29 0532 PDT).
  - Reattach: `tmux attach -t claude`.

(E) Remote desktop to Daemonic-PC (Windows 11 PRO) -> PLANNED, NOT YET DONE.
  - Route: phone (NetBird) -> EVO-X2 as NetBird ROUTING PEER for 192.168.8.0/24 (masquerade) ->
    PC LAN IP :3389. RDP is never port-forwarded on the router.
  - Was blocked only because RDP had to be enabled at the PC with no physical access. Brandon is
    now home with the PC up, so this is unblocked.

================================================================================
2. SECURITY ITEMS (do these)
================================================================================

- [ ] REVOKE the NetBird PAT that was pasted into chat (prefix nbp_RpIg...). It expires on its
      own ~2026-10-02 but revoke explicitly in the dashboard (Team -> Service Users / Tokens).
      Cloud-side copies were shredded at the end of the 2026-09-29 session.
- [ ] Future tokens/keys go in environment settings or on the box, never in chat.

================================================================================
3. CHECKLIST -- finish remote access to Daemonic-PC
================================================================================

At the PC (physical, now possible):
- [ ] Settings -> System -> Remote Desktop: ON, keep "Require NLA" checked.
      Admin PowerShell equivalent:
        Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 0
        Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
- [ ] Sign-in: RDP needs the account PASSWORD, not the Hello PIN. If "only allow Windows Hello
      sign-in" is on, turn it off and sign in once with the password.
- [ ] Network profile = Private (the RDP firewall rule is scoped to Private).
- [ ] Optional: enable Wake-on-LAN (BIOS + NIC advanced properties) and note the PC MAC.
- [ ] Optional (recommended fallback): enable Windows OpenSSH Server so the PC can be managed
      from EVO-X2 next time without physical access.

On EVO-X2 (sudo is hard-deny for the remote agent -- Brandon runs these):
- [ ] sudo sysctl -w net.ipv4.ip_forward=1
- [ ] echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-netbird-forward.conf
- [ ] sudo chmod 644 /etc/sysctl.d/99-netbird-forward.conf

In the NetBird dashboard (or ask the EVO-X2 Remote Control session to do it via the API):
- [ ] Network route 192.168.8.0/24, routing peer Daemonic-evox2, masquerade ON, distribution
      group = the phone's group, plus an access policy allowing it.

Phone:
- [ ] Install Microsoft "Windows App", add PC by LAN IP, Wi-Fi OFF + NetBird ON, connect.

================================================================================
4. ROADMAP / FOLLOW-UPS
================================================================================

- Make the EVO-X2 remote-control session survive reboots (systemd --user unit wrapping
  `claude remote-control`, like persona-daemon / persona-webui) -- only if Brandon wants it
  always-on.
- Optionally run `claude remote-control` on Daemonic-PC too (earlier Windows remote-control
  sessions exist, so Claude Code is likely installed there already).
- Optional: WOL helper on EVO-X2 (`wakeonlan <PC-MAC>`).
