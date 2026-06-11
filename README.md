# multi-agent-home-network-architecture (pi-fleet)

A multi-agent-operated home infrastructure platform. A Claude Code "CTO" session and a team of
sub-agents (`.claude/agents/`) build and operate services on a Raspberry Pi fleet.

**Product #1:** network-wide ad blocking ([Pi-hole](https://github.com/pi-hole/pi-hole)) with a
full observability stack (Prometheus + Grafana + Loki) and a web portal — built as a shared
platform for future apps (Wi-Fi health monitoring, owner's full-stack apps, a Mac Mini node).

## The team
| Agent | Role |
|-------|------|
| CTO (main session) | Oversees everything; the owner's single point of contact |
| `watchdog` | Runs health checks (SSH + Prometheus/Loki/Grafana APIs), reports status |
| `coach` | Reviews other agents' work, updates their instruction files — the team self-improves |
| `infra` | Deploys/operates the Docker stack on the nodes |
| `netops` | Tailscale, DNS architecture, Wi-Fi health |
| `dev` | Ports/builds applications onto the platform |

## What runs where (pi-node1, Raspberry Pi 4 8GB)
| Service | Port | What |
|---------|------|------|
| Homepage portal | 80 | Front door — links + live status for everything |
| Pi-hole | 53 (DNS), 8081 (admin) | Ad blocking for every device on the LAN |
| Grafana | 3000 | Dashboards (node, Pi-hole, containers, logs) |
| Prometheus | 9090 | Metrics |
| Loki | 3100 | Logs (shipped by Promtail from all containers + syslog) |
| node-exporter / cAdvisor / pihole-exporter | internal | Metric exporters |

## Quick start
```bash
ssh pi-node1                 # key auth; alias in ~/.ssh/config
./scripts/deploy.sh          # rsync configs + docker compose up (secrets from macOS Keychain)
```
Secrets: macOS Keychain, service `pi-fleet` (`security find-generic-password -s pi-fleet -a <account> -w`).

Docs live in [`docs/`](docs/): architecture, runbook, decisions, learnings, roadmap.
