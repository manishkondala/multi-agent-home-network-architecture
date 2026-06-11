# Decisions (ADR-lite)

## 2026-06-11 — Pi-hole in Docker, not bare-metal install
The official `curl | bash` installer takes over the host. Docker keeps it portable, versionable,
and consistent with the "platform for many apps" goal. Trade-off: host DHCP-server feature is
harder from a container — fine, the router keeps DHCP.

## 2026-06-11 — Pinned image tags, no `latest`
Reproducible deploys; `latest` on arm64 has bitten many people (cAdvisor, Loki). Upgrades are
explicit PR-able diffs in `docker-compose.yml`.

## 2026-06-11 — Secrets in macOS Keychain → `.env` on the Pi at deploy time
Owner asked for a local key manager. Keychain is already there, scriptable
(`security find-generic-password`), and keeps secrets out of git. The deploy script writes
`.env` (mode 600) on the Pi; `.env` is gitignored everywhere.

## 2026-06-11 — Homepage (gethomepage) as the portal instead of a custom frontend
Owner wants a hosted website surfacing Grafana/Prometheus/Loki. Homepage gives tiles, live
container status, and a Pi-hole widget via YAML config we keep in git — zero code to maintain.
Custom frontend stays an option later (`dev` agent's job).

## 2026-06-11 — Pi keeps `--accept-dns=false` on Tailscale
The Pi *is* the DNS server. Letting Tailscale rewrite its resolv.conf risks loops/breakage.

## 2026-06-11 — Old Docker 20.10.14 left in place (for now)
It runs the owner's legacy `jsms_worker-au` container; an engine upgrade risks that workload
mid-build. Compose v2 plugin installed alongside. Revisit during a planned maintenance window.

## 2026-06-11 — Loki 7d / Prometheus 15d+2GB retention
The whole node lives on a 29GB SD card with ~9GB free. SD cards also die from write volume;
short retention is survival, not stinginess. Long-term storage can move to the Mac Mini later.
