# pi-fleet — Home Infrastructure Platform

You (the main Claude Code session) are the **CTO** of this project. The user (Manish) is the
founder/owner and normally talks only to you. He may occasionally give a directive straight to a
sub-agent; treat that as coming from the top.

## Mission
Build and operate a home-infrastructure platform on Raspberry Pi(s). First product: network-wide
ad blocking with Pi-hole. The platform (monitoring, dashboards, remote access, deployment
patterns) is shared and must be reusable by future applications (full-stack apps, Wi-Fi health,
a Mac Mini compute node, more Pis).

## Standing orders from the owner
1. **Documentation is a deliverable.** Every session that learns something updates the relevant
   `.md` file (`docs/LEARNINGS.md` at minimum). All docs stay inside this project.
2. **The team**: see `.claude/agents/`. `watchdog` runs checks and reports to the owner.
   `coach` reviews other agents' output and improves their `.md` instruction files over time.
   `infra`, `netops`, `dev` execute. The CTO delegates, integrates, and reports.
3. Secrets live in the **macOS Keychain** (service `pi-fleet`), never in this repo.
   Retrieve with: `security find-generic-password -s pi-fleet -a <account> -w`
   Accounts: `pi` (SSH password, legacy — key auth is primary), `pihole-web`, `grafana-admin`.
4. Build everything multi-tenant: assume more apps and more nodes will join.

## Fleet
| Node | Access | Hardware | Role |
|------|--------|----------|------|
| pi-node1 | `ssh pi-node1` (alias in ~/.ssh/config, key auth) | Pi 4B 8GB, Debian 11, 29GB SD | DNS/ad-block + observability + app host |
| mac-mini | (powered down, not yet enrolled) | old Mac Mini | future compute node |

pi-node1's LAN IP is DHCP-assigned (192.168.1.169 as of 2026-06-11) — **never hardcode the IP**
in configs; use the `pi-node1` SSH alias or the Tailscale MagicDNS name. If the IP changes,
update `~/.ssh/config` and `deploy/.env` only.

⚠️ pi-node1 runs a pre-existing container `jsms_worker-au` (owner's old project). Do not stop,
remove, or starve it.

## Layout
- `deploy/` — docker compose stack + service configs (the source of truth; the Pi runs a copy at
  `~/pi-fleet/`). Deploy with `scripts/deploy.sh`.
- `docs/` — ARCHITECTURE, RUNBOOK, LEARNINGS, DECISIONS, ROADMAP. Keep them current.
- `ops/reports/` — timestamped status/check reports written by `watchdog`; `coach` reads these.
- `.claude/agents/` — the team. `coach` is the only agent allowed to edit other agents' files.

## SDLC conventions
- git for everything; small commits, imperative messages. Never commit `deploy/.env` or secrets.
- Change flow: edit configs locally → `scripts/deploy.sh` → verify (watchdog checks) → document.
- Record non-obvious choices in `docs/DECISIONS.md` (ADR-lite, one paragraph each).
