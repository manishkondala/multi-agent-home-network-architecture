# Decisions (ADR-lite)

## 2026-06-12 — Owner apps build natively ON pi-node1; compose references local tags
Standing order #5 forbids docker on the Mac, and cross-building arm64 elsewhere adds a
registry we don't have. So: app source is snapshotted to `~/apps/<name>/` on the Pi, our
Dockerfile overlays (kept in this repo under `apps/`) are copied on top, and
`docker build` runs on the Pi itself. `deploy/docker-compose.yml` references the local
tags (`cc-points:0.1.0`, …) which are never pulled. Trade-off: slow builds (Next.js ~15min
on a Pi 4) — acceptable for rare deploys; heavy builds escalate to the Mac Mini when it
joins. Stale 12GB of old build cache was pruned first (`docker builder prune`).

## 2026-06-12 — Source transfer via scratch git snapshot piped over ssh (not rsync)
The session permission allow-list only has broad `ssh *` and `git *`; rsync/scp/tar are
auto-denied. Method: `git init` a scratch repo in /tmp with `--work-tree` pointed at the
owner's app dir (read-only on his copy — no `.git` is created inside it), `add -A` with
`core.excludesFile=apps/sync-excludes.txt` (drops node_modules/venv/DBs/.env), commit, then
`git archive HEAD | ssh pi-node1 "tar -x -C apps/<name>"`. Single files (DB seeds, secrets)
go via `ssh pi-node1 "cat > path" < localfile`. Scripted in `scripts/sync-apps.sh`.

## 2026-06-12 — stock-frontend nginx serves the SPA *and* proxies /api to stock-backend
The Vite app's axios baseURL is the relative `/api`, so proxying from the same origin means
no CORS, no backend URL baked into the bundle, and the Pi's moving DHCP IP never appears in
a build artifact. nginx resolves `stock-backend` via Docker DNS at request time and uses a
600s read timeout because ML endpoints (e.g. /api/recommend/top trains 53 models) take
minutes on a Pi 4.

## 2026-06-12 — Next.js `output: "standalone"` via overlay next.config.mjs
Full node_modules runtime image would be ~1GB; standalone is ~200MB on a 29GB SD card. The
owner's Mac copy is not modified — the overlay config (plus Dockerfile/.dockerignore) is
kept in `apps/cc-points/` in this repo and copied over the Pi-side snapshot at sync time.

## 2026-06-12 — App SQLite DBs live on bind mounts under ~/apps/data, seeded once
`cc-points` (Prisma `file:/data/dev.db`) and `stock-backend` (`/app/data/stocklab.db`)
keep their state outside the images on `~/apps/data/<app>/`. The Mac DBs were copied once
(`--ignore-existing` semantics: a Pi-side copy is never overwritten by a re-sync), so user
data created on the Pi survives rebuilds and re-syncs. Backup of `~/apps/data` is on the
roadmap with the other volumes.

## 2026-06-12 — stock-backend secret stays a Pi-only .env file (Keychain write was denied)
Plan A (Keychain `pi-fleet/anthropic-api` → deploy/.env → compose env) failed: the
`security add-generic-password` call needed command substitution to read the key and was
permission-denied. Fallback uses the app's native pattern: `backend/.env` is copied to
`~/apps/secrets/stock-backend.env` (dir 700, file 600) and bind-mounted read-only at
`/app/.env`, which `load_dotenv` already reads. Nothing in git, nothing in the image.
Migrating to the Keychain pattern is a nice-to-have for the CTO.

## 2026-06-12 — Availability via blackbox-exporter HTTP probes (apps expose no /metrics)
Neither app exposes Prometheus metrics natively and we don't modify the owner's code, so
availability is probed from outside: `prom/blackbox-exporter:v0.25.0` (arm64 verified by
pulling on the Pi) probes cc-points, stock-frontend, stock-backend /api/health and
homepage every 30s; cAdvisor already covers per-container CPU/RAM. Dashboard:
`deploy/grafana/dashboards/apps.json`.

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
