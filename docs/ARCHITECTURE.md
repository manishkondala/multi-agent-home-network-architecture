# Architecture

## Topology (2026-06-11)
```
Internet ── Router (192.168.1.1, DHCP+DNS today)
              │
              ├── pi-node1  (Pi 4B 8GB, Debian 11, DHCP 192.168.1.169)
              │     └── docker network "fleet"
              │           pihole(53,8081) prometheus(9090) grafana(3000) loki(3100)
              │           promtail node-exporter cadvisor pihole-exporter homepage(80)
              │           [legacy: jsms_worker-au — owner's old project, hands off]
              ├── range extender (known-bad Wi-Fi, future netops work)
              ├── Mac (CTO workstation)
              └── household devices ── will use pi-node1 as DNS once router is updated
Tailscale tailnet overlays all of this for remote access.
```

## Data flow
- **DNS/ad-block**: client → pihole:53 → upstream 1.1.1.1/1.0.0.1. Ads answered with 0.0.0.0.
- **Metrics**: node-exporter (host), cAdvisor (containers), pihole-exporter (blocking stats),
  grafana/loki self-metrics → Prometheus (30s scrape, 15d/2GB retention) → Grafana.
- **Logs**: every docker container (docker_sd) + /var/log/syslog → Promtail → Loki (7d
  retention) → Grafana Explore.
- **Portal**: Homepage on :80 — service tiles w/ live container status (docker.sock, ro),
  Pi-hole widget, host resources.

## Port registry (pi-node1) — claim here BEFORE binding
| Port | Owner | Notes |
|------|-------|-------|
| 53 tcp/udp | pihole | house DNS — breaking this breaks the internet |
| 80 | homepage | portal front door |
| 3000 | grafana | |
| 3100 | loki | push + query API |
| 8081 | pihole admin UI | container :80 |
| 9090 | prometheus | |
| (internal) 9100/8080/9617/9080 | exporters/promtail | fleet network only, not published |

## Design rules
1. Everything is Docker Compose under `deploy/`, one shared `fleet` network; new apps join it.
2. Images must be linux/arm64; pinned versions, not `latest`.
3. Every service: `restart: unless-stopped` + `mem_limit` (Pi has 8GB shared).
4. Apps log to stdout (auto-ships to Loki) and expose /metrics when feasible.
5. No hardcoded LAN IPs anywhere — the Pi is on DHCP. Use the `pi-node1` SSH alias,
   docker-network hostnames, or Tailscale MagicDNS. The deploy script injects the current IP
   into Homepage at deploy time.
6. Multi-node ready: Prometheus targets carry a `node` label; adding pi-node2/mac-mini means
   new scrape targets + SSH alias + (later) federation if needed.

## Scaling path
- **More Pis**: flash → ssh key → install docker+compose → join tailnet → add node-exporter/
  promtail via a slim "agent" compose profile → register targets in prometheus.yml.
- **Mac Mini**: same enrollment; becomes the heavy-compute node (builds, GPU-ish workloads).
- **Wi-Fi health**: probe containers on pi-node1 (+ future nodes) exporting to Prometheus.
