# Roadmap

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
- [ ] **Claude auth on the Pi** — BLOCKED on owner: stock-analysis API key has no credit;
      either top up console.anthropic.com or `claude setup-token` (subscription billing).
- [ ] **Gmail SMTP** — BLOCKED on owner: app password → `~/pi-fleet/secrets/smtp.env`.
      Until then mail queues in `sentinel/outbox/` (nothing lost).
- [ ] **Learning loop close-out (CTO duty)**: each session drain `incidents/new/` +
      `learnings-inbox.md` → `docs/LEARNINGS.md` + curated `remediations.conf` in repo.

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
