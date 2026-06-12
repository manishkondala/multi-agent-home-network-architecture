# Learnings

Running log of things we learned the hard way (or just learned). Newest first.
`coach` appends here after reviews; everyone appends when they hit something non-obvious.

## 2026-06-11 (first coach review)
Reviewed both watchdog reports, git log, and three incidents. Findings → instruction-file fixes:
- **A stopped container is not an outage.** watchdog flagged `jsms_worker-au` as "must be Up"
  and recommended an urgent restart; the CTO restarted it — but the owner had stopped it
  deliberately an hour earlier (shell history showed a high-CPU hunt ending in `docker stop`).
  The evidence was even in watchdog's own report (`restart: always` yet down = explicit stop)
  but the conclusion didn't follow. Fix: watchdog.md got a stopped-container triage section
  (inspect → `last` + shell history → classify crashed vs stopped-by-human; human stop =
  ask the owner, never auto-restore). infra.md got the same "ask, don't revert" rule.
- **Agent files must track standing-order changes.** watchdog.md still required the legacy
  container Up after CLAUDE.md flipped to "stays stopped"; dev.md still said "heavy builds
  happen on the Mac" and "test locally first" after standing order #5 banned local docker.
  Stale instructions are how the same incident recurs. Both corrected; expected state of the
  three jsms containers (stopped) is now in watchdog.md and infra.md.
- **Owner directives must be persisted the moment they're heard.** The port-2-apps + homepage
  redesign directive was nearly lost because no session wrote it to ROADMAP. Every agent file
  now carries: a directive received directly goes into `docs/ROADMAP.md` immediately.
- **Don't report guessed names.** The watchdog file shipped with invented Prometheus metric
  names (`pihole_query_*_today`); CTO's fix to the real names was correct — generalized in
  watchdog.md: empty query result → list real metrics via `/api/v1/label/__name__/values`.

## 2026-06-11 (evening)
- **Never run Docker on the owner's Mac.** A session launched Docker Desktop locally
  (`open -a Docker`, `docker version/info/buildx` probing) and the owner flagged it: everything
  is hosted on the Pi, nothing on the PC. Now enforced via deny rules in
  `.claude/settings.local.json` and standing order #5 in CLAUDE.md. All docker commands go
  through `ssh pi-node1 "docker ..."`; images build on the Pi.
- **Containers that write into bind-mounted config dirs break `rsync --delete`.** Homepage
  writes `homepage/logs/` as root on the Pi, so the next deploy's rsync failed with Permission
  denied. Fix: `--exclude homepage/logs` in deploy.sh. Watch for this with any future app that
  logs into its config mount.

## 2026-06-11 (initial build)
- **Verify image tags exist before deploying.** `ekofr/pihole-exporter:v1.1.1` was a guessed
  tag and didn't exist (real: v1.2.0); first compose pull failed. Rule: check
  `hub.docker.com/v2/repositories/<repo>/tags` (or the GitHub releases page) when pinning.
- **Bash working directory drifts.** A `cd` in one tool call persists into later commands; the
  first deploy attempt failed with `./scripts/deploy.sh: no such file`. Rule: scripts and
  background jobs always start with `cd <absolute project root>` or use absolute paths.
- **The Pi's userland is Debian 11 but the kernel is aarch64** — compose plugin must be the
  `linux-aarch64` binary; placed at `/usr/local/lib/docker/cli-plugins/docker-compose`.
- **Port 53 was genuinely free** on this Pi (no systemd-resolved stub like on Ubuntu) — one
  less fight. Don't assume this on future nodes; check `ss -tulpn` first.
- **Grafana community dashboards ship with `${DS_*}` template placeholders** that break file
  provisioning; sed-replace them with the provisioned datasource UIDs at download time.
- **Pi-hole v6 image** uses `FTLCONF_webserver_api_password` (not the old `WEBPASSWORD`).
- **GF_SECURITY_ADMIN_PASSWORD only applies on first boot** of an empty grafana volume.
- Pre-existing container `jsms_worker-au` (2yrs old, up 3 weeks) — confirmed owner workload,
  left untouched; constrains us from upgrading the Docker engine casually.
