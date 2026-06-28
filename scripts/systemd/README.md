# Reboot-survival: persistent systemd --user units (EVO-X2 anchor node)

These are reference copies of the two `systemd --user` unit files that auto-start the stack on
boot. They live on the anchor node at `~/.config/systemd/user/` (OUTSIDE the repo, so they are not
deployed by `git pull`); these copies exist for backup, version control, and reproducibility.

Until 2026-06-28 the stack ran as **transient** `systemd-run --user` units: they survived SSH
logout (linger=yes) but NOT a reboot. After a reboot the stack was DOWN and had to be restarted by
hand. These persistent units fix that: with `WantedBy=default.target` + user linger enabled, the
user manager reaches `default.target` at boot and pulls both units up automatically.

- `persona-daemon.service` -- daemon.py (llama-server :8090 + persona API :8000 + Hermes), --with-hermes.
- `persona-webui.service`  -- OpenWebUI :3000 (LAN-bound, re-applies the web-search patch on start).

Paths are hard-coded to the EVO-X2 anchor (`/home/festro33/Git/Project_Persona`). Adjust the
`festro33` home and project path for any other host.

## Install / refresh (run on the anchor node, NOT over a clobbering pull)

```bash
# 1) confirm user linger is on (so the user manager runs at boot, no login needed)
loginctl show-user "$USER" | grep -i linger      # expect Linger=yes
loginctl enable-linger "$USER"                    # if it was not

# 2) copy the unit files into place
mkdir -p ~/.config/systemd/user
cp ~/Git/Project_Persona/scripts/systemd/persona-daemon.service ~/.config/systemd/user/
cp ~/Git/Project_Persona/scripts/systemd/persona-webui.service  ~/.config/systemd/user/

# 3) if transient units of the same name are currently running, STOP them first
#    (a transient unit shadows the on-disk file and blocks `enable`).
systemctl --user stop persona-webui.service persona-daemon.service 2>/dev/null

# 4) reload, enable (creates default.target.wants symlinks), start from disk
systemctl --user daemon-reload
systemctl --user enable persona-daemon.service persona-webui.service
systemctl --user start  persona-daemon.service        # wait for api:8000 healthy
systemctl --user start  persona-webui.service         # then :3000

# 5) verify
systemctl --user is-enabled persona-daemon persona-webui      # enabled / enabled
systemctl --user show persona-daemon -p FragmentPath          # must point at ~/.config/systemd/user
```

## Day-to-day

```bash
systemctl --user restart persona-daemon       # reload llama (~secs)
systemctl --user restart persona-webui        # re-applies the web-search patch
journalctl --user -u persona-daemon -f        # or tail logs/daemon.log / logs/webui.log
```

A true reboot is the ultimate proof; `is-enabled=enabled` + `Linger=yes` + the
`default.target.wants/` symlinks are the mechanism that makes it automatic.
