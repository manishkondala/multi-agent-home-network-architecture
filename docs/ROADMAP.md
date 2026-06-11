# Roadmap

## Now (v0.1 — this build)
- [x] SSH key auth + Keychain secrets + `pi-node1` alias
- [x] Agent team chartered (`.claude/agents/`)
- [x] Pi-hole + Prometheus + Grafana + Loki + Homepage stack on pi-node1
- [ ] Tailscale on pi-node1 (needs owner auth click)
- [ ] Router DHCP DNS → Pi (owner; turns ad-block on house-wide)
- [ ] Router DHCP reservation for the Pi (owner; kills the moving-IP problem)

## Next (v0.2 — operate & harden)
- Scheduled watchdog runs (cron/`/loop`) producing daily reports in `ops/reports/`
- Grafana alerting (disk <3GB, temp >70°C, target down, DNS failure) → notification channel
- First coach review cycle after a week of reports
- Backup: pihole config volume + grafana volume → tarball pulled to the Mac (SD cards die)
- Docker engine upgrade on a maintenance window

## Later (v0.3+ — expand)
- **Wi-Fi health** (owner: "the wifi in my house sucks"): probe container (ping/speedtest/
  signal scan) → Prometheus → Grafana Wi-Fi dashboard; evidence-based recommendation on the
  range extender. Owner directive pending — netops leads.
- **Mac Mini enrollment**: power up, enroll like a node (docker, tailscale, exporters);
  becomes heavy-compute tier. Candidate for long-retention metrics/logs storage.
- **Owner's full-stack apps** ported onto the platform (dev agent; platform contract in
  `.claude/agents/dev.md`).
- **More Pis** if the fleet grows — enrollment recipe in `docs/ARCHITECTURE.md`.
