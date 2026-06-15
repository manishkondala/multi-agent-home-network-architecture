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
5. **Owner directives are persisted the same session they're given** — into `docs/ROADMAP.md`
   (and memory) before anything else happens. A directive that lives only in a conversation
   transcript is considered lost (it happened once: the port-my-apps request).
6. **Nothing runs on the owner's Mac.** All Docker commands, builds, and services run on the
   fleet nodes over SSH (`ssh pi-node1 "docker ..."`). Never run `docker` locally or launch
   Docker Desktop on the Mac — images build on the Pi itself (or `docker buildx` *on the Pi*
   when cross-building is ever needed). Local deny rules enforce this.

## Fleet
| Node | Access | Hardware | Role |
|------|--------|----------|------|
| pi-node1 | `ssh pi-node1` (alias in ~/.ssh/config, key auth) | Pi 4B 8GB, Debian 11, 29GB SD | DNS/ad-block + observability + app host |
| pi-node2 | `ssh pi-node2` (alias, key auth — reuses `id_ed25519_pifleet`) | Mac mini 2014 (Macmini7,1), Intel i5-4278U 2c/4t, **8GB**, Intel Iris, **931GB disk**, macOS 12.7.6 | heavy/GUI tier: YouTube QoE 24/7, content-monetization, retention/backup, dead-Pi watcher (enrolled 2026-06-15) |
| mac-mini | — | — | renamed → **pi-node2** (same box) |

pi-node1's LAN IP is DHCP-assigned (192.168.1.169 as of 2026-06-11) — **never hardcode the IP**
in configs; use the `pi-node1` SSH alias or the Tailscale MagicDNS name. If the IP changes,
update `~/.ssh/config` and `deploy/.env` only.

pi-node2 (the Mac mini) is at 192.168.1.207 (DHCP — **never hardcode**; use the `pi-node2` alias).
It's Intel (x86-64), **not** Apple Silicon — no local ML; AI/content gen stays cloud (Higgsfield
MCP / APIs). Its value = stable x86 headful-Chrome + 931GB disk + a sacrificial always-on worker.
Sleep is **disabled** (`sudo pmset -a sleep 0 disablesleep 1 standby 0 powernap 0 womp 1
autorestart 1`, set 2026-06-15) — required or it suspends SSH/TCP while still answering ping.
Docker Desktop 4.78 **cannot run** on macOS 12 (needs 14) and this 2014 box can't upgrade past
Monterey → container runtime = **Colima** (docker CLI/compose parity with the Pi); bot-sensitive
social publishing runs **native macOS**, not in a container. The "nothing runs on the Mac" deny
rule is **laptop-only** — pi-node2 is a legitimate Docker/compute host.

⚠️ pi-node1 has three pre-existing containers from the owner's old project (`jsms_worker-au`,
`happy_shannon`, `adoring_jones`). The owner **deliberately stopped all three on 2026-06-11**
(they were eating CPU). Leave them stopped — do not restart them, and do not remove them
without the owner's say-so.

## Layout
- `deploy/` — docker compose stack + service configs (the source of truth; the Pi runs a copy at
  `~/pi-fleet/`). Deploy with `scripts/deploy.sh`.
- `docs/` — ARCHITECTURE, RUNBOOK, LEARNINGS, DECISIONS, ROADMAP. Keep them current.
- `ops/reports/` — timestamped status/check reports written by `watchdog`; `coach` reads these.
- `.claude/agents/` — the team. `coach` is the only agent allowed to edit other agents' files.

## SDLC conventions
- git for everything; small commits, imperative messages. Never commit `deploy/.env` or secrets.
- **Everything is version-controlled.** If a config, script, dashboard, or doc matters to the
  fleet, it lives in this repo — nothing important exists only on a node or in a transcript.
- **Branch-and-review git flow (owner directive 2026-06-14).** This is mandatory and assumes
  multiple Claude sessions on multiple nodes sharing one repo. Every change follows:
  1. **`git pull --rebase`** first — always start from the latest `main`. Never work on stale code.
  2. **Branch** (`feat/…` / `fix/…`); never edit `main` directly.
  3. Do the work → `scripts/deploy.sh` → verify (watchdog) → document.
  4. **CR review before committing** — the `cr` agent reviews the diff (`/code-review`); resolve
     every finding *before* `git commit`. No unreviewed code is ever committed.
  5. **Rebase on latest `main`, then push** the branch. Resolve conflicts on the branch, never
     leave them for `main`.
  6. **Merge to `main`** only after CR sign-off and a clean (conflict-free) rebase.
- **The `cr` agent is the gatekeeper:** all code from any agent/session must pass CR review,
  land as clean atomic commits, and merge without conflicts. CR owns "is this reviewed, clean,
  and mergeable?" Other code-writing agents (`dev`, `infra`, `netops`) must route through it.
- Record non-obvious choices in `docs/DECISIONS.md` (ADR-lite, one paragraph each).
