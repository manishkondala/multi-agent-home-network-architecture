# Roadmap

## Now (v0.2 — owner's apps, directive 2026-06-11)
Owner: get my apps off my Mac, onto the Pi, linked from the homepage, availability tracked
in Prometheus/Grafana/Loki — and make the homepage less boring (dark dashboard chosen).
- [ ] **Port `cc_points_dashboard`** (Next.js + Prisma, `~/Documents/fun_projects/cc_points_dashboard`)
      → dockerize for arm64, **build on the Pi** (never local docker), compose service, host port 3002
- [ ] **Port `stock_analysis`** (frontend + backend, `~/Documents/fun_projects/stock_analysis`)
      → host ports 3003 (frontend) / 3004 (backend)
- [ ] **Availability monitoring**: Prometheus probes/scrapes for both apps + homepage,
      Grafana panels; container logs already reach Loki via the existing log pipeline
- [ ] **Homepage redesign**: dark glassy theme, background image, live stats widgets
      (CPU/temp/DNS blocked), app tiles with health indicators, grouped sections
- [ ] **Coach review cycle is now standing practice** — CTO invokes coach after agent work
      lands (never ran before 2026-06-11; that was a CTO process failure)

## Carry-over (v0.1)
- [x] SSH key auth + Keychain secrets + `pi-node1` alias
- [x] Agent team chartered (`.claude/agents/`)
- [x] Pi-hole + Prometheus + Grafana + Loki + Homepage stack on pi-node1
- [ ] Tailscale on pi-node1 (needs owner auth click)
- [ ] Router DHCP DNS → Pi (owner; turns ad-block on house-wide)
- [ ] Router DHCP reservation for the Pi (owner; kills the moving-IP problem)

## Next (operate & harden)
- Scheduled watchdog runs (cron/`/loop`) producing daily reports in `ops/reports/`
- Grafana alerting (disk <3GB, temp >70°C, target down, DNS failure) → notification channel
- Backup: pihole config volume + grafana volume + app data volumes → tarball pulled off-node
  (SD cards die)
- Docker engine upgrade on a maintenance window
- Decide fate of the stopped legacy jsms containers (owner stopped them 2026-06-11; remove?)

## Later (expand)
- **Wi-Fi health** (owner: "the wifi in my house sucks"): probe container (ping/speedtest/
  signal scan) → Prometheus → Grafana Wi-Fi dashboard; evidence-based recommendation on the
  range extender. Owner directive pending — netops leads.
- **Mac Mini enrollment**: power up, enroll like a node (docker, tailscale, exporters);
  becomes heavy-compute tier. Candidate for long-retention metrics/logs storage.
- **More Pis** if the fleet grows — enrollment recipe in `docs/ARCHITECTURE.md`.
