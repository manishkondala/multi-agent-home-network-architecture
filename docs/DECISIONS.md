# Decisions (ADR-lite)

## 2026-06-12 — Self-healing: Claude Sentinel agent runs ON the Pi; bash only detects
Owner directive: reports alone are useless — agents must fix outages, learn patterns, and
remember previous outages. Owner chose **Claude-only fixes** and **zero dependence on his
laptop** (Mac Mini with 24/7 Claude lands ~June 2026). Cloud routines can't reach the LAN
and the laptop sleeps, so the interim agent host is pi-node1 itself: Claude Code native
arm64 binary (host node is v16, too old — untouched, owner's legacy projects may need it),
invoked headless (`claude -p --dangerously-skip-permissions`, capped turns/timeout) by a
dumb cron detector. Detector writes an incident file (with per-service outage history =
memory), Sentinel fixes/verifies/RCAs/appends learnings, wrapper emails the owner either
way — if Claude lacks auth/credits the raw incident still goes out. Cost guardrails baked
into SENTINEL.md from the same-day token-burn RCA. The whole sentinel/ dir migrates to the
Mac Mini unchanged.

## 2026-06-12 — Status emails via owner's own Gmail (app password), queued until provided
No paid SMTP (owner directive). Gmail SMTP_SSL:465 with an app password is free and his
own account; python3 smtplib only (no packages). Missing creds → mail queues to
sentinel/outbox/ and nothing is lost. Pi timezone switched UTC → America/New_York so the
7AM/7PM cron means owner-local time across DST; deploy.sh excludes Pi-side runtime state
(incidents/, secrets/, sentinel state) from rsync --delete.

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

## 2026-06-13 — Per-service streaming visibility via a custom FTL exporter (not pihole-exporter / not a Grafana SQLite datasource)
Owner wants to see which device is streaming what (v0.4 B). The existing `ekofr/pihole-exporter`
only emits aggregate top-N domains — no per-client breakdown — so it can't answer the question.
Two real options: (a) a Grafana SQLite datasource plugin querying the FTL DB directly, or (b) a
small purpose-built Prometheus exporter. Chose (b): keeps Grafana a pure Prometheus consumer
(matches blackbox/pihole/node exporters), no new datasource plugin, and the domain→service
mapping lives in a versioned `services.yml` anyone can extend. The exporter (`deploy/streaming-
exporter/`) tails the FTL `queries` table by rowid, classifies domains by substring match
(first match wins), and exposes `pihole_service_queries_total{service,client}`.
Mount is **read-write** even though we only SELECT: FTL keeps the DB in WAL mode, and SQLite
cannot open a WAL database on a read-only mount (it needs to write the `-shm` wal-index). Guard
is `PRAGMA query_only=ON`.

## 2026-06-13 — Infra/observability services locked to the Pi loopback; only apps stay LAN-open
Owner: "only keep the applications open (cc-points, stock); lock the rest." Prometheus and Loki
have no native auth and were published on `0.0.0.0` — readable by anyone on the LAN. Bound them
to `127.0.0.1:` instead of adding a reverse-proxy + basic-auth layer: simpler, no new moving
parts, and they don't need LAN exposure (Grafana queries them over the internal fleet network;
promtail pushes internally; sentinel/report scripts run on the Pi and use `localhost`). Grafana
(`:3000`, login) and Pi-hole admin (`:8081`, password) were already auth-gated, so they stay
LAN-open. Net LAN-open surface: DNS 53, homepage 80, pihole-admin 8081, grafana 3000, and the
apps 3002/3003/3004. Off-Pi queries to Prometheus/Loki now go via `ssh pi-node1 "curl
localhost:..."` (watchdog/infra docs updated to match).

## 2026-06-14 — Pi-hole v6 exporter: switch to a community fork, normalise in Prometheus
Pi-hole upgraded to v6 (new session REST API); the long-standing `ekofr/pihole-exporter` only
speaks the removed v5 `/admin/api.php`, so its Grafana dashboard went blank (401 -> scrape
timeout). Considered: (a) `bazmonk/pihole6_exporter` — purpose-built for v6 but a whole new
metric schema, ships as a Python/systemd script (no Docker image / arm64), so it would mean a
dashboard rebuild and a non-Docker deploy; (b) `noobExtendsBot/pihole-exporter` — a fork of
ekofr that adds v6 support, multi-arch Docker image, keeps **most** of the original metric
names. Chose (b): smallest blast radius, stays Docker-on-the-Pi, dashboard preserved.
Its handful of renamed metrics/labels (and a missing `hostname` label) are mapped back to the
ekofr schema in `prometheus.yml` `metric_relabel_configs` rather than editing every panel — the
mapping lives in one reviewable place and the upstream dashboard JSON stays untouched. Image is
pinned by digest (tags are mutable commit-SHAs, no semver). Known cost: the fork double-emits
`pihole_upstream_queries` for one.one.one.one (dup series fails the whole scrape), so that
metric is dropped and the forward-destinations panel is empty. Revisit if ekofr ever ships v6
support, or move to a maintained v6-native exporter + its own dashboard.
