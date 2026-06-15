# Roadmap

## Standing process change (owner directive 2026-06-14)
Owner: branch-per-feature + a **CR agent** that reviews changes before they're committed, because
multiple Claude sessions run on multiple nodes against one shared repo. Full intended flow per
node: **pull (rebase) → branch → work → CR review → rebase → push → merge**, with the CR agent
responsible for making sure all code from every agent is reviewed, cleanly committed, and merges
**without conflicts**. And **everything everywhere is version-controlled** — nothing important
lives only on a node or in a transcript.
- [x] Recorded in `CLAUDE.md` (SDLC conventions) + memory.
- [ ] **`coach` to create a `cr` agent** (`.claude/agents/cr.md`) and update `dev`/`infra`/`netops`
      to route through it. Until then, the main session runs `/code-review` before each commit.
- [ ] Decide CR mechanism at scale: `/code-review` skill vs a dedicated reviewer agent vs
      `/code-review ultra` on PRs; and whether nodes push to a shared remote (origin) or sync via
      one hub node. (Today: single node `pi-node1`, local repo on the Mac.)

## Now (v0.5 — Wi-Fi health application, owner directive 2026-06-14)
Owner (a Wi-Fi engineer): the house Wi-Fi (Verizon CR1000A router + extender) is bad on multiple
devices. Build a **Wi-Fi health-check web app**, code in
`~/Documents/fun_projects/wifi_health_check_home_application/`, hosted on the Pi and linked from
the `192.168.1.169` homepage. Users open it on phone/laptop from different rooms and **run a health
check**; the UI must be modern and tech-savvy. Requested metrics: **Avg RTT, Avg SRTT, link
capacity, congestion window (tx + rx side)**, awareness of **RF interference/noise** degrading PHY
rate (e.g. microwave on/off), a **regular 7AM/7PM report of the health of all currently-connected
devices**, and an **admin-only Wi-Fi-sensing "map the house structure" view** (the CSI / "WiFi sees
through walls" research). **Stats collected always** (continuous), not just on demand. The Mac Mini
(more compute) is nearly enrolled.

**Privacy model (owner directive):** a regular user sees **only their own session stats** when they
run a check. The **admin/owner** sees **historic, device-level / device-centric stats** (from
Prometheus/Grafana).

**CTO feasibility notes (so the ask isn't lost to physics):**
- A browser **cannot** read OS/kernel Wi-Fi internals (RSSI, channel, 802.11 standard, PHY rate,
  cwnd, SRTT). The honest browser-side "session check" = a **local network-quality test against the
  Pi**: RTT/jitter/loss, down/up throughput (≈ link capacity), DNS time, plus a **self-reported
  room + device label**.
- **SRTT + congestion window are kernel TCP_INFO** — captured on the **Pi** (server side of the
  test socket) via `ss -tin` (rtt/rttvar→SRTT, snd/rcv cwnd, retrans, delivery_rate, pacing_rate).
  The Pi is the measurement anchor. (Test backend likely needs host networking so it sees the real
  client sockets, not NAT'd bridge sockets.)
- **Per-device RSSI / PHY rate / channel / 802.11 standard** live on the **AP**, not the Pi or the
  browser. Source = the **CR1000A local API station list** (netops to probe what RF fields it
  exposes — Fios gateways are stingy) keyed by MAC. May be partial/unavailable.
- **RF interference / noise / channel occupancy** = continuous **`iw dev wlan0 scan`** (or
  monitor-mode capture) from the Pi's radio (eth0 carries DNS, so wlan0 can be dedicated). Microwave
  events show as PHY-rate drop / retry spikes / noise-floor rise. Robust monitor mode may want a USB
  adapter; onboard Broadcom is flaky.
- **House structural mapping** = **CSI sensing** (Nexmon-CSI on the Pi / ESP32-CSI / DensePose-from-
  WiFi). Full 3D/skeletal reconstruction is **research-grade** (needs trained models + labeled data)
  — **parked**. Achievable near-term: **CSI motion/presence** ("room occupied / motion detected"),
  experimental, on a dedicated radio (Nexmon flash is risky on the prod DNS Pi → dedicated Pi or
  Mac-Mini era). Admin-only.

**Phased plan (CTO):**
- [x] **P1 — Session check + Pi-side TCP_INFO** — built & deployed 2026-06-14. `wifi-health`
      (host-net, `:3005`, image built on the Pi via `sync-apps.sh wifi`), homepage tile, Grafana
      `pi-fleet-wifi`. Browser measures RTT/jitter/loss + down/up throughput + DNS; the Pi reads
      SRTT/cwnd/retrans/delivery_rate from the kernel (`ss -tin`, captured in-handler so fast/closed
      sockets aren't missed) and serves it back per-client. Per-session SQLite + Prometheus
      (`wifi_health_*`, labels device/room). Verified: target up, session capture working.
- [x] **P2 — Continuous RF exporter** — built & deployed 2026-06-14. `wifi-rf-exporter` (host-net +
      privileged, `iw dev wlan0 scan`, `:9620`) → `wifi_rf_*` (neighbour APs per channel/band,
      strongest signal, station load). Live: ch1 is congested (7 APs). **Gap (hardware):** onboard
      Broadcom returns nothing for `iw survey dump`, so channel **noise-floor / airtime-busy** —
      i.e. **microwave / non-Wi-Fi interference detection** — is **not** available; needs a
      survey-capable radio (USB adapter / Mac-mini). The exporter attempts survey each cycle and
      will light up automatically when such a radio exists.
- [~] **P3 — Per-device stats from the AP.** *Recon 2026-06-14 (from the Pi):* gateway
      `192.168.1.1` = "Fios Router", 80/443 open, **no REST API** (`/api/*` → 404). It's CGI-based
      and **auth-gated** (`/cgi/cgi_owl.js`, `/index.cgi` → 403 unauthenticated). Path forward =
      an **authenticated scrape** (community `quantum-gateway` / Home-Assistant `quantum_gateway`
      approach: log in with the admin password → session cookie → read the connected-devices page)
      → `wifi-router-exporter` keyed by MAC. Likely yields **device presence + IP/hostname + band
      (2.4/5 GHz)**, possibly negotiated link rate on some firmware, but **probably NOT RSSI /
      802.11 standard** (Fios UI doesn't surface them). **Blocked on the owner:** put the CR1000A
      **admin password** in Keychain (`security add-generic-password -s pi-fleet -a cr1000a-admin
      -w '<pw>'`); then netops builds + verifies the scraper, documenting whatever RF fields the
      firmware actually exposes.
- [x] **P4 — 7AM/7PM Wi-Fi section** — done 2026-06-14. `fleet-report.sh` now has a `## Wi-Fi
      health (per-device)` block: all currently-connected devices' latest check (RTT/loss/↓↑/room)
      from the admin API + the busiest RF channels (`topk wifi_rf_channel_ap_count`) + the survey/
      microwave gap note. Reuses the v0.3 SMTP pipeline; verified live.
- [x] **In-app admin (per-device) view** — done 2026-06-14 (the "Both" decision's in-app half).
      `/admin` on the wifi-health app, **password-locked** (`WIFI_ADMIN_PASSWORD`, from Keychain
      `pi-fleet/wifi-admin` else reuses `grafana-admin`; sent as `X-Admin-Token`). Lists **all
      devices on the LAN** — discovered by an **unprivileged TCP connect ARP-sweep** of the Pi's /24
      (host-net container reads `ip neigh`), enriched with Pi-hole FTL hostnames/vendor + each
      device's latest health check + live TCP_INFO. Verified: 18 LAN devices, auth-gated, docker
      IPs filtered. Hostnames fill in as v0.4 per-device DNS + P3 land.
- [ ] **P5 (experimental) — CSI motion/presence**, admin-only, on a dedicated radio / Mac-Mini era.
      House structural reconstruction stays parked as research.

**Owner decisions 2026-06-14:** admin view = **Both** (Grafana `pi-fleet-wifi` now; curated in-app
admin view — room heatmap etc. — later). First scope = **P1 + P2** (session app + Pi TCP_INFO **and**
the continuous RF/interference exporter). Wi-Fi sensing (P5) = **parked as research** until the
Mac Mini lands.

Routes through the standard flow: `dev` builds the app, `infra` deploys, `netops` owns the
Wi-Fi/RF/router side, `cr` reviews before commit. Mac-Mini, when enrolled, hosts the heavy/CSI work.

## Now (v0.6 — continuous YouTube QoE testing, owner directive 2026-06-14)
Owner: there's a dir **`vsc` on the Pi** (do NOT change it) that continuously spawns/tears down
containers, each running YouTube for 5–15 min and collecting **video-only QoE stats** (buffering,
resolution, bitrate, etc.). It uses an **old chromedriver**. Take the *idea*, refactor into NEW
code under **`apps/test/video/youtube/`** on the Pi (create `apps/test`, then `video`, then
`youtube`). Requirements:
- Run YouTube playback tests **continuously** across **different videos**, capturing **all video
  QoE metrics** (buffering events/ratio, startup time, resolution, bitrate, dropped frames, …) and,
  **if possible, the session's TCP metrics too** (reuse the wifi-health `ss -tin` TCP_INFO idea).
- Write metrics to **Grafana under `pi-fleet/tests/`** (new dashboard folder/uid) — buffering,
  resolution, other video metrics.
- Homepage: under **Network**, add a tile **"YouTube Metrics"** → the dashboard, **locked** (only
  the owner has the password — same gating approach as the v0.5 admin view / Grafana login).
- The old `vsc` chromedriver is stale → **do what's needful** (modern Selenium/headless Chromium for
  arm64, or the YouTube IFrame Player API + `movie_player.getStatsForNerds()` which exposes buffer
  health/res/bitrate without scraping).

**CTO notes (scope before building):** (1) Read `vsc` on the Pi first — reuse its approach. (2)
arm64 headless Chromium + chromedriver is the classic pain point; the IFrame API / Stats-for-nerds
JSON is likely more robust than scraping and lighter on the Pi. (3) Continuous container spawn/
teardown is heavy on a Pi 4 — consider a single long-lived worker looping over videos, or cap
concurrency; the **Mac-mini** is the natural home when enrolled. (4) TCP metrics: capture via `ss`
in the test container's netns keyed to the googlevideo CDN peers. (5) Lock = Grafana login
(already admin-gated) is the cheap path; an in-app locked view reuses the v0.5 admin-password
pattern. Phasing TBD after reading `vsc`. Routes through dev(build)/infra(deploy)/cr(review).

## Now (v0.4 — per-device network visibility + streaming dashboard, owner directive 2026-06-13)
Owner: "I want to see what domains are being accessed on my network — if I'm watching YouTube
or Peacock, I want to know." Decision: **option C** — fix per-device visibility first, then
build the streaming dashboard.
- [~] **A. Per-device visibility** (CR1000A is a Verizon Fios gateway). Today most clients hide
      behind the router (192.168.1.1) because it forwards DNS on their behalf.
      1. [x] **DHCP reservation** for pi-node1 (MAC `d8:3a:dd:5e:ab:97` → `192.168.1.169`) —
         done on the CR1000A 2026-06-13 (set to static).
      2. [x] **Handed-out DNS** set to `192.168.1.169`, secondary blank (CR1000A "IPv4 DNS
         Address 1").
      3. [ ] **Reboot the router** (owner, tonight 2026-06-13) → devices renew leases → verify
         per-device client IPs appear in the FTL query log. If they still collapse to
         `192.168.1.1`, the CR1000A locked the LAN-DNS field → flip Pi-hole to run DHCP.
      *Supersedes the two v0.1 carry-over router TODOs below.*
- [x] **B. "Streaming by service" dashboard** — built & deployed 2026-06-13. Custom
      `deploy/streaming-exporter/` (FTL DB → `pihole_service_queries_total{service,client}`,
      mapping in `services.yml`), Prometheus job `streaming` (up=1), Grafana dashboard
      `pi-fleet-streaming` ("Streaming by service", 4 panels). Already classifying live traffic
      (Disney+/ESPN, Netflix, Samsung TV, YouTube); per-device split populates after A's reboot.

## Now (v0.2 — owner's apps, directive 2026-06-11)
Owner: get my apps off my Mac, onto the Pi, linked from the homepage, availability tracked
in Prometheus/Grafana/Loki — and make the homepage less boring (dark dashboard chosen).
- [x] **Port `cc_points_dashboard`** (Next.js + Prisma, `~/Documents/fun_projects/cc_points_dashboard`)
      → dockerize for arm64, **build on the Pi** (never local docker), compose service, host port 3002
      *(done 2026-06-12: cc-points:0.1.0 on :3002, HTTP 200, probe green)*
- [x] **Port `stock_analysis`** (frontend + backend, `~/Documents/fun_projects/stock_analysis`)
      → host ports 3003 (frontend) / 3004 (backend)
      *(done 2026-06-12: stock-frontend :3003 / stock-backend :3004, HTTP 200, probes green)*
- [x] **Availability monitoring**: Prometheus probes/scrapes for both apps + homepage,
      Grafana panels; container logs already reach Loki via the existing log pipeline
      *(done 2026-06-12: blackbox-exporter, 4 probes all up, Grafana dashboard `pi-fleet-apps`)*
- [x] **Homepage redesign**: dark glassy theme, background image, live stats widgets
      (CPU/temp/DNS blocked), app tiles with health indicators, grouped sections
      *(done 2026-06-12: deployed, serving on :80, healthy)*
- [x] **Coach review cycle is now standing practice** — CTO invokes coach after agent work
      lands (never ran before 2026-06-11; that was a CTO process failure)
- [x] **Coach: token-waste post-mortem (owner directive 2026-06-12)** — the dev session
      burned many calls on commands that auto-denied (rsync/scp/tar/chmod/security-with-
      substitution are not on the `.claude/settings.local.json` allow-list; unattended
      prompts default to deny). Coach must update every agent file so agents (a) read the
      allow/deny list before choosing command forms, (b) prefer allowed forms (`ssh
      pi-node1 …`, `git …`) instead of trial-and-error, (c) after ONE denial stop probing
      variants and either switch to an allowed form or surface the needed permission to
      the CTO/owner — never a chain of failed retries.
      *(done 2026-06-12: RCA in ops/reports/2026-06-12-0730-rca-dev-token-burn.md; coach
      updated all four agent files — see ops/reports/2026-06-12-0734-coach-rca-followup.md)*

## Now (v0.3 — self-healing ops, owner directive 2026-06-12)
Owner: status email to kondalamanish@gmail.com every day at 7AM and 7PM (full report incl.
hosted apps), free SMTP (no paid service). Reporting alone is useless ("I'm not going to fix
it") — agents must FIX failures, learn the patterns, and log learnings so the next outage is
handled with awareness of previous ones.
Owner decision: **Claude-only fixes** (no dumb auto-restarts), nothing depends on the
owner's laptop. Interim host for the Sentinel agent: **Claude Code headless on pi-node1
itself** (installed 2026-06-12, v2.1.175); migrates wholesale to the Mac Mini when it
arrives (~June 2026, 24/7 Claude with sudo on the LAN).
- [x] **Detection layer on the Pi** (cron */3): finds failures, writes incident record with
      outage memory + logs to `~/pi-fleet/incidents/new/`, invokes the Sentinel agent.
      Fixes nothing itself. Validated by controlled drill 2026-06-12 (stock-frontend).
- [x] **Sentinel agent** (`claude -p` on the Pi; `deploy/sentinel/SENTINEL.md` = canonical
      instructions; `.claude/agents/sentinel.md` = Mac-side twin): diagnose → fix → verify
      → RCA into incident → learning into `learnings-inbox.md` → playbook update. Emails
      owner; if Claude can't run, raw incident is emailed instead (fallback validated).
- [x] **Twice-daily full status email** (cron 7:00/19:00, Pi tz now America/New_York):
      raw report generator validated; Claude writes the executive summary when available.
- [x] **Claude auth on the Pi** — resolved 2026-06-13: owner ran `claude setup-token`,
      OAuth token lives in `~/pi-fleet/secrets/claude.env` (sourced by sentinel-agent.sh
      and fleet-report.sh). Verified live (`claude -p` → AUTH_OK).
- [x] **Gmail SMTP** — resolved (smtp.env populated 2026-06-12, confirmed live — sentinel
      has been emailing kondalamanish@gmail.com since 22:18 UTC 2026-06-12).
- [x] **Learning loop close-out (CTO duty)**: `learnings-inbox.md` empty; one stale
      incident (`20260612T234807Z-outage.md`, reboot-recovery noise, already covered by
      the 2026-06-12 reboot RCA in LEARNINGS.md) archived 2026-06-13.

v0.3 is now fully live end-to-end: detection → Claude diagnose/fix → email, both auth
paths working. The next real outage gets an actual Claude-authored fix + RCA, not just a
fallback email.

## Carry-over (v0.1)
- [x] SSH key auth + Keychain secrets + `pi-node1` alias
- [x] Agent team chartered (`.claude/agents/`)
- [x] Pi-hole + Prometheus + Grafana + Loki + Homepage stack on pi-node1
- [ ] Tailscale on pi-node1 (needs owner auth click)
- [ ] Router DHCP DNS → Pi (owner; turns ad-block on house-wide) — *now tracked under v0.4 A*
- [ ] Router DHCP reservation for the Pi (owner; kills the moving-IP problem) — *now v0.4 A*

## Next (operate & harden)
- **Off-board dead-Pi watcher** (gap found in owner's 2026-06-12 pull-the-plug test): every
  alert path (sentinel, SMTP) lives ON the Pi, so a dead Pi is silent. Needs a second
  vantage point — Mac Mini when enrolled (ping + own email path), or an external uptime
  service (e.g. free healthchecks.io ping from the 7AM/7PM cron: missed ping = email) in
  the interim.
- Scheduled watchdog runs (cron/`/loop`) producing daily reports in `ops/reports/`
- Grafana alerting (disk <3GB, temp >70°C, target down, DNS failure) → notification channel
- Backup: pihole config volume + grafana volume + app data volumes → tarball pulled off-node
  (SD cards die)
- Docker engine upgrade on a maintenance window
- Decide fate of the stopped legacy jsms containers (owner stopped them 2026-06-11; remove?)

## Later (expand)
- **Wi-Fi health** — *promoted to a full directive: see "Now (v0.5)" above.*
- **Mac Mini enrollment**: power up, enroll like a node (docker, tailscale, exporters);
  becomes heavy-compute tier. Candidate for long-retention metrics/logs storage.
- **More Pis** if the fleet grows — enrollment recipe in `docs/ARCHITECTURE.md`.
