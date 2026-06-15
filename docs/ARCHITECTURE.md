# Architecture

## Topology (2026-06-11)
```
Internet ── Router (192.168.1.1, DHCP+DNS today)
              │
              ├── pi-node1  (Pi 4B 8GB, Debian 11, DHCP 192.168.1.169)
              │     └── docker network "fleet"
              │           pihole(53,8081) prometheus(9090) grafana(3000) loki(3100)
              │           promtail node-exporter cadvisor pihole-exporter homepage(80)
              │           blackbox-exporter (internal probes)
              │           apps: cc-points(3002) stock-frontend(3003) stock-backend(3004)
              │           [legacy: jsms_* — owner's old project, hands off]
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
- **Portal**: Homepage on :80 — dark glassy dashboard, Apps/Network/Platform groups, tiles
  w/ live container status (docker.sock, ro) + siteMonitor health dots, Pi-hole widget,
  host resources.
- **Availability**: blackbox-exporter (internal :9115) HTTP-probes cc-points,
  stock-frontend, stock-backend /api/health and homepage every 30s → Prometheus →
  Grafana "Apps — availability" dashboard (uid `pi-fleet-apps`).

## Owner apps (ported off the Mac 2026-06-12)
| App | Containers | Source of truth | State |
|-----|------------|-----------------|-------|
| Pointly (cc_points_dashboard) | `cc-points` :3002 | Mac working copy, synced to Pi `~/apps/cc-points/` by `scripts/sync-apps.sh` | SQLite `~/apps/data/cc-points/dev.db` (bind mount `/data`) |
| Stock Analysis | `stock-frontend` :3003, `stock-backend` :3004 | Mac working copy → `~/apps/stock-analysis/` | SQLite `~/apps/data/stock-analysis/stocklab.db` (`/app/data`); secret `~/apps/secrets/stock-backend.env` → `/app/.env` ro |

Build/deploy cycle: `scripts/sync-apps.sh` (snapshot source → ship → docker build on the Pi,
images stay local, e.g. `cc-points:0.1.0`) → bump tag in `deploy/docker-compose.yml` if
changed → `scripts/deploy.sh`. The stock frontend's nginx proxies `/api` to `stock-backend`
over the fleet network, so no backend URL or LAN IP is baked into any bundle. Heavy ML calls
(e.g. first `/api/recommend/top`, trains 53 models) take minutes on the Pi 4 — candidates
for the Mac Mini when it joins.

## Port registry (pi-node1) — claim here BEFORE binding
| Port | Owner | Notes |
|------|-------|-------|
| 53 tcp/udp | pihole | house DNS — breaking this breaks the internet |
| 80 | homepage | portal front door |
| 3000 | grafana | |
| 3100 | loki | push + query API |
| 8081 | pihole admin UI | container :80 |
| 9090 | prometheus | |
| 3002 | cc-points (Pointly) | owner app, Next.js, container :3000 |
| 3003 | stock-frontend | owner app, nginx serving Vite SPA, proxies /api → stock-backend |
| 3004 | stock-backend | owner app, FastAPI/uvicorn, container :8765 |
| (internal) 9100/8080/9617/9080/9115 | exporters/promtail/blackbox | fleet network only, not published |

### Port registry (pi-node2 — Mac mini, Docker via Colima)
| Port | Owner | Notes |
|------|-------|-------|
| 9621 | youtube-qoe | YouTube QoE tester `/metrics` (host-net); scraped cross-node by pi-node1 Prometheus (job `youtube-qoe`) |

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
