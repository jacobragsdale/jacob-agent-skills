---
name: jacob-home-server
description: "Operate Jacob's home server (desktop, 100.103.224.99): deploy or restart stacks, add/remove a service, edit SOPS secrets, check what's running vs declared, debug a container, rebuild or rehearse a rebuild. Use when a request touches the home server, its docker stacks (media-stack, caddy ingress, home-assistant, mealie, ntfy, radicale, romm, beszel, homepage, obsidian-livesync, jarvis), its secrets, host packages/config, backups, or server drift/cleanup."
disable-model-invocation: true
---

# Jacob's home server

Arch box `desktop` on Tailscale: `ssh 100.103.224.99` (user `jacob`, key
trusted, passwordless sudo). Everything it runs is declared in
`~/Development/home-server` **on the Mac** — that working tree is the source
of truth. `scripts/deploy.sh` rsyncs it to `~/home-server` on the server and
applies it (stacks + host-level codex sync). GitHub
(`jacobragsdale/home-server`, private) is backup only: the server never pulls
from it, and there is no CI and no registry anywhere.

The **host itself is declared too**: pacman packages (`host/packages.txt`),
sudoers/networkd/zram/sshd/resolved config (`host/etc/`), dotfiles
(`host/dotfiles/`), and the codex CLI + its ChatGPT-subscription auth seed
(`host/codex/`, sops-encrypted). `host/install.sh` converges all of it and is
idempotent; `scripts/drift.sh` reports both stack and package drift.

## Hard rules

- **Never edit compose files, scripts, or units on the server.** Edit the
  repo on the Mac and run `scripts/deploy.sh` — the rsync uses `--delete`,
  so server-side edits are silently lost on the next deploy.
- **Host state changes go through the repo too**: new package →
  `host/packages.txt` + `host/install.sh` run; host config → `host/etc/` +
  install.sh. Ad-hoc `pacman -S` on the server shows up as drift.
- **Never write a plaintext secret** — no `.env` files, no values inlined in
  compose, no decrypted output in your response. Secrets live in per-stack
  `secrets.sops.env` (SOPS + age, safe to commit). Edit with
  `sops stacks/<name>/secrets.sops.env`; inspect keys only
  (`sops decrypt ... | cut -d= -f1`). The one non-env secret is
  `host/codex/auth.sops.json` (codex subscription tokens) — refresh it with
  `scripts/codex-auth.sh pull` after any `codex login` on the server; deploys
  install it only when the server file is missing (codex refreshes tokens in
  place, the live file always wins).
- **Adding/removing a service is a two-file change** (stack dir +
  `docs/services.md`) — `host/scripts/healthcheck.sh` derives its container
  list from the stacks' `container_name:` lines automatically. Add an
  http/tcp check line in healthcheck.sh only for an endpoint worth probing.
  Public exposure additionally means a Caddyfile vhost (+ CrowdSec scenario
  if the app has its own login).
- **Data never goes under `~/home-server`** (the `--delete` rsync would own
  it). Bind-mount data from its own path; existing locations are in
  `docs/services.md`.
- Bind new UIs/ports to `100.103.224.99` (Tailscale-only) unless LAN
  exposure is the point.
- **The remote shell is zsh**: `echo ===` fails (`=word` expansion) — use
  `---` as a separator; unquoted `$var` does NOT word-split (a multiline
  list passed to `pacman -Rns $list` becomes ONE argument — use `$(...)`
  command substitution, xargs, or `bash -c`). A killed remote pacman can
  leave `/var/lib/pacman/db.lck`; check `pgrep -x pacman` then remove it.

## Workflow

1. Read the repo first: `README.md` for commands, `docs/services.md` for
   what runs where. Trust `scripts/drift.sh` output over any doc.
2. Make changes in the repo, then `scripts/deploy.sh <stack>` (or no args
   for everything). Verify with `docker ps` / the stack's healthcheck.
3. For host automation changes (`host/`): deploy, then run
   `bash ~/home-server/host/install.sh` on the server to reinstall units.
4. Commit and push when the change is verified — the push is the backup.

The personal site is separate: its own repo at
`~/Development/jacob-personal-site`, deployed with `make deploy` (rsync
working tree → native build on the server). Same rules, different repo.

## Rebuild + rehearsal (VM-proven 2026-07-06)

Fresh ISO → server: `archinstall --config host/archinstall/config.json`
(user/passwords interactive or a local creds file — never committed) →
reboot → restore age key → rsync repo → `bash bootstrap.sh` →
`sudo host/scripts/restore.sh` (restic pulls ~760MB of config/db dirs from
B2) → `scripts/deploy.sh`. Full runbook in the `bootstrap.sh` header. The
whole path, including the B2 restore with `--verify`, passed a QEMU
rehearsal on 2026-07-06.

**`REHEARSAL=1` is the safety knob** for practice rebuilds, honored by
bootstrap.sh (no tailnet join), host/install.sh (timers installed but never
armed), and deploy.sh (cloudflare-ddns scaled to 0). A rehearsal box that
runs the real timers **prunes the production B2 repo** (backup.sh does
`restic forget --prune`) and pages the phone (healthcheck/media-cleanup are
hourly) — never skip the knob. Deploy/drift point at a VM with
`SERVER=<ssh-alias> REHEARSAL=1`.

Rehearsal facts that will bite again:
- Compose files bind `100.103.224.99` and `192.168.8.233`; on a VM add both
  to loopback first: `ip addr add <ip>/32 dev lo` (not persistent — re-add
  after reboot).
- `restore.sh` restores `/home/jacob/.ssh` — it **overwrites
  authorized_keys** with the server's copy, so reach the box with Jacob's
  own key, not a rehearsal key.
- A fresh archinstall box has password-sudo only; the first
  `host/install.sh` run installs the NOPASSWD drop-in (prompts once).
- QEMU/slirp: run with `ipv6=off` or Docker builds (caddy's xcaddy stage)
  pick the unreachable `fec0::3` resolver; slirp's `10.0.2.3` UDP DNS can
  flake after boot — a networkd drop-in pinning `DNS=1.1.1.1` +
  `UseDNS=false` makes it deterministic.
- Driving the ISO over serial: ttyS0 is a **login prompt** (autologin is
  tty1-only; user `root`, empty password), and anything launched as a shell
  background job gets SIGTTIN-stopped when it touches the tty — run the
  installer with `setsid ... </dev/null`, poll an exit-marker file. A killed
  archinstall leaves the target pinned by a chroot `gpg-agent` and (until
  4.4's keymap step was avoided via `"kb_layout": ""`) an nspawn container —
  kill those before re-wiping.

## Media pipeline

sonarr/radarr/prowlarr run inside gluetun's network namespace (UIs on
:8989/:7878/:9696; API keys in `~/arr/*/config.xml` server-side). Add
content via the arrs (or Seerr), never via transmission directly.
1337x/EZTV need FlareSolverr (not installed); Knaben, TPB, YTS and
LimeTorrents work through the VPN. Transmission's `settings.json` is
server-side data: edit only while transmission is stopped (it rewrites the
file on shutdown). `docker exec` into linuxserver containers is root by
default but transmission runs hooks as uid 1000 — test with
`docker exec -u 1000` or root-owned files pollute the data dirs.

## Service quirks

- RomM bundles EmulatorJS whose `EJS_defaultControls` **replaces** the whole
  control map: when setting RomM `emulatorjs.controls`, provide a full
  per-core map; per-game browser localStorage can still override toggles
  like fastForward.
- HA's `configuration.yaml` + `known_devices.yaml` are repo-owned
  (`stacks/home-assistant/config/`, synced+restarted by deploy.sh); the rest
  of `~/home-assistant` is live app data.

## Debugging

- Logs: `make logs` (personal site) or
  `ssh 100.103.224.99 'docker logs --tail 100 <name>'`.
- Health history: `~/home-server/host/logs/{healthcheck,maintenance,backup}.log`
  on the server. Timers: healthcheck hourly, media-cleanup hourly at :40,
  maintenance 04:30 (pacman -Syu + docker prune), backup 05:30 (restic → B2),
  kitchen nudges 06:00/17:00 + Sun 10:00.
- Drift: `scripts/drift.sh` flags compose projects outside the repo,
  label-less containers, dangling volumes, and pacman drift vs
  `host/packages.txt`. Deleting flagged *data* (volumes, directories) always
  needs Jacob's explicit go-ahead.

## Hardware

Beelink SER8: Ryzen 7 8745HS (8C/16T), Radeon 780M iGPU only — **CPU-only
for ML inference** (no NVIDIA/ROCm/NPU), 27GB RAM. A Seeed reSpeaker
XVF3800 4-Mic Array (USB, 16kHz in/out, on-chip beamforming + AEC) and a
generic Jieli USB speaker are plugged in for the voice-assistant project
(`~/Development/jarvis`). Details: `docs/services.md` § Hardware detail.
Audio is ALSA-direct (`hw:CARD=Array`); PipeWire is installed but inactive.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
