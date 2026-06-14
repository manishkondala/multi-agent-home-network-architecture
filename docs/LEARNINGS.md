# Learnings

Running log of things we learned the hard way (or just learned). Newest first.
`coach` appends here after reviews; everyone appends when they hit something non-obvious.

## 2026-06-13 (false "SENTINEL UNAVAILABLE" emails despite a working fix)
- **`sentinel-agent.sh` declared failure even when Claude succeeded.** SENTINEL.md step 7
  tells the agent to move a RESOLVED incident from `incidents/new/` to
  `incidents/archive/`. The wrapper's post-run check (`grep -q '## Sentinel fix report'
  "$INC"`) then grepped the now-missing `incidents/new/...` path, failed, and fell into
  the "Claude unavailable" branch — emailing "SENTINEL UNAVAILABLE, manual attention
  needed" for an incident Claude had *already fixed and verified* (the 12:06Z grafana
  outage: agent restarted grafana, confirmed `/api/health` 200, wrote a full RESOLVED
  report). Fix: after the run, fall back to `incidents/archive/<basename>` if `$INC`
  no longer exists at its original path before checking for the fix report
  (`deploy/sentinel/sentinel-agent.sh`).
- **Open mystery: something sent grafana a clean `docker stop`-equivalent (SIGTERM,
  signal=15, exitCode=0, RestartCount stays 0) twice on 2026-06-13** — once ~9 min after
  the stack came up (12:05:41Z) and again ~65s after Sentinel's restart (12:07:52Z),
  confirmed via `docker events --filter container=grafana`. No cron/systemd timer or
  repo script issues `docker stop`/`compose stop`/`compose down`. If this recurs, it'll
  cost a Claude invocation + email every cycle (now correctly "RESOLVED" instead of
  "UNAVAILABLE", but still noise). Check first whether it's a manual drill.

## 2026-06-13 (sentinel fully unblocked — Claude auth on the Pi)
- **`claude setup-token` output can pick up a stray newline+space when piped through
  `printf '...' > file` over ssh** — the long token wraps in the terminal and the wrap
  becomes a literal `\n` inside the single-quoted string, so `claude.env` ended up as two
  "lines" (`KEY=part1` / ` part2`) and `source` only set the truncated value. Symptom:
  `cut -d= -f1 file` prints the var name AND a second orphan line. Fix without ever
  retyping the secret: `tr -d '\n ' < file > file.fixed` (newlines and spaces are not
  legal inside `sk-ant-oat01-...` tokens, so stripping both is safe) then restore a
  trailing newline. Always sanity-check a freshly-written secrets file with
  `cut -d= -f1` before trusting it — same flow applies to the Mac Mini's
  `claude setup-token` setup later.
- Both v0.3 blockers are now cleared: Claude OAuth token in `secrets/claude.env`
  (verified `claude -p` → real response) and Gmail SMTP (already live since
  2026-06-12 22:18 UTC). Sentinel's Claude-fix path is live for the next real incident.

## 2026-06-12 (night, first real incident: Pi reboot)
- **A reboot resurrects `restart=always` containers — even ones the owner stopped on
  purpose.** jsms_worker-au came back at boot and spawned two new client containers
  (third zombie generation this week). A manual `docker stop` does NOT survive a dockerd
  restart when the policy is `always`. Fix: `docker update --restart=no jsms_worker-au`.
  Rule: "deliberately stopped" containers must have their restart policy neutralized, or
  the decision evaporates at the next reboot/power blip.
- **pi-node1 has no RTC and ntpd races pihole at boot** — the clock starts ~30 min in the
  past (fake-hwclock) and ntpd's first DNS lookups fail because pihole (the resolver) is
  still starting; `ntpq -p` shows `reach 0` and the clock never steps. Fix: restart ntp
  once the stack is up. A wrong clock backdates incident filenames (ordering broke) and
  will eventually kill Gmail SMTP (TLS). Note: systemd-timesyncd is masked *because* the
  ntp package owns time here — that's normal Debian, don't unmask it.
- **Detection needs a boot grace period.** loki legitimately 503s on /ready for ~2-3 min
  while warming after boot; the sentinel filed an "outage" for it. fleet-sentinel.sh now
  exits quietly when /proc/uptime < 180s.

## 2026-06-12 (evening, sentinel build)
- **Claude Code runs fine on a Pi 4** via the native installer (`curl -fsSL
  https://claude.ai/install.sh | bash` → `~/.local/bin/claude`, v2.1.175, arm64/glibc 2.31).
  Host node v16 is too old for the npm route — left untouched (owner's legacy projects).
  Headless auth: `ANTHROPIC_API_KEY` env (the stock-analysis key is on the box but has **no
  credit balance** — "Credit balance is too low") or a subscription via `claude setup-token`.
- **rsync --delete excludes are load-bearing on the Pi.** `~/pi-fleet/` now holds runtime
  state the repo doesn't know about (incidents/, secrets/, sentinel state/outbox,
  learnings-inbox.md) — every new Pi-side state dir MUST be added to deploy.sh's exclude
  list or the next deploy silently deletes it.
- **Debian cron + timedatectl**: restart cron after `timedatectl set-timezone` or jobs keep
  firing on the old timezone.
- **Drill the failure path, not just the happy path.** The controlled stock-frontend drill
  proved detect → incident → agent-invoke → fallback-email in 3 seconds, and confirmed the
  exact failure mode (credit balance) before the first real outage would have.

## 2026-06-12 (morning, CTO verification pass)
- **A container that orchestrates other containers leaves children behind.** The 2026-06-11
  22:26 `docker start jsms_worker-au` (watchdog's stale "must be Up" rule) ran only 6 min,
  but in that window the worker spawned `kind_volhard` + `pedantic_booth` via docker.sock.
  Stopping the worker did not stop them — they ran 9 h against the owner's "all jsms
  stopped" intent until the next-day verification caught them. Rule: after stopping any
  orchestrator container, diff `docker ps` against the expected set (compose services +
  known-stopped legacy list); auto-named containers (`adjective_noun`) on jsms images are
  its children. Both stopped 2026-06-12 ~07:45; whole jsms family now Exited.

## 2026-06-12 (RCA: dev agent token burn — see ops/reports/2026-06-12-0730-rca-dev-token-burn.md)
- **Never poll-spin on a slow remote job.** Waiting for the ~10-min `next build` on the Pi,
  dev issued ~15 wait constructs (`sleep 300`, six `until ssh …; do sleep N; done` variants,
  plus date/ps/temp checks) in 11 minutes — ~60% of its 375 turns, ~40M cache-read tokens.
  Rule: run a long remote command as ONE Bash call with `timeout: 600000`, or detach it on the
  Pi (`nohup … > build.log 2>&1`) and check the log once when other work is done.
- **A wait condition must distinguish the new artifact from the old.** `docker image inspect
  cc-points:0.1.0` succeeded instantly because the *previous* build's tag existed, so every
  until-loop exited immediately and proved nothing, breeding ever-hackier checks (Created
  timestamps, StartedAt regexes). Rule: tag each build uniquely (e.g. `:0.1.0-$(date +%s)` or
  git SHA) or watch the build log, not the tag.
- **Three strikes on permission denials.** 16 denied calls (rsync ×5, scp, tar, curl,
  security, chmod) were retried in variants before strategy changed. Rule: after 2 denials of
  the same operation class, stop probing — switch to a known-allowed pattern or end the run
  reporting the blocker.
- **Mega-tasks guarantee mega-contexts.** One spawn = port 2 apps + 4 Dockerfiles + compose +
  blackbox/Prometheus + Grafana dashboard + Homepage redesign ⇒ 214 tool calls, ~170k context,
  every late turn paying cache-read on all earlier output. CTO rule: split directives into
  sequential spawns with explicit scope; agents end the run (reporting done/remaining) rather
  than grind past ~100 tool calls.
- **(coach follow-up)** dev's denial thrash was partly self-inflicted: `dev.md` itself said
  "rsync the build context over" — a command the Mac's deny rules block. When a deny rule is
  added, grep `.claude/agents/*.md` for instructions that recommend the now-denied command
  and fix them the same session. dev.md now points at the git-snapshot-over-ssh pattern, and
  the allow/deny command list lives in dev.md and infra.md.

## 2026-06-12 (dev, app-porting session)
- **Prisma in slim build stages: install openssl BEFORE `prisma generate`** (and pin
  `PRISMA_CLI_BINARY_TARGETS`). node:22-bookworm-slim has no openssl, so generate guessed
  the openssl-1.1.x engine; the runtime stage had openssl 3 → every page 500'd with
  PrismaClientInitializationError. Logs in Loki surfaced it immediately.
- **Replicate the owner's install flags.** cc-points needs `npm ci --legacy-peer-deps`
  (next 15.0.3 peer-pins a react 19 RC; app uses react 19.2.x) — it's right there in the
  app's own start.sh. Read the start script before writing the Dockerfile.
- **A mounted prometheus.yml does not reload itself** — `docker compose restart prometheus`
  after deploys that change scrape config (lifecycle API is not enabled).
- **pi-node1's kernel has no memory cgroup** (`cgroup_memory=1 cgroup_enable=memory` absent
  from /boot/cmdline.txt) — compose `mem_limit` values are silently discarded on this host.
  Limits are still declared for when the cgroup gets enabled (owner/infra: needs a reboot).
- **Check the permission allow-list before picking command forms.** Roughly a dozen calls
  (rsync, scp, tar, chmod, cat-in-for-loops, `security` with command substitution, running
  a repo script via `bash`) auto-denied because they are not in
  `.claude/settings.local.json` and unattended prompts default to deny — pure token waste.
  Allowed broad forms: `ssh *` (so `ssh pi-node1 "..."` for anything remote), `git *`,
  plus specific pinned curls. Rule going forward: read the allow-list first, design the
  whole task around allowed forms, and after one denial escalate for the permission
  instead of probing variants. (Owner directive: coach to bake this into all agent files.)
- **`docker builder prune` freed 12.13GB on pi-node1** — 132 stale build-cache entries from
  old projects. Check `docker system df` before assuming the SD card is "full".
- **prom/blackbox-exporter:v0.25.0 verified linux/arm64** by pulling on the Pi (Docker Hub
  tag API curls are not on the allow-list; `ssh pi-node1 "docker pull ..."` is the
  always-available way to verify a tag+arch).

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

## 2026-06-13 (per-device DNS visibility + streaming dashboard, v0.4)
- **Per-device attribution was broken because the router proxies DNS.** In the FTL query log
  almost everything showed up as the router IP `192.168.1.1` — devices were querying the router,
  which forwarded to Pi-hole, collapsing every client into one. Fix is router-side: hand the Pi
  out as the DHCP DNS server so clients query it directly. Pi-hole *already captures* every
  domain (Netflix/ESPN/Samsung-TV/YouTube all visible) — the gap was attribution, not capture.
- **Reserve the Pi's IP BEFORE rebooting the router.** Once clients are told to use the Pi
  (`192.168.1.169`) as DNS, that IP must never move, or DNS dies house-wide. Set a DHCP
  reservation by MAC (`d8:3a:dd:5e:ab:97`) first. Done on the CR1000A 2026-06-13.
- **Verizon CR1000A** exposes the handed-out DNS as "IPv4 DNS Address 1/2"; leave #2 blank so
  devices can't fall back to a public resolver and bypass ad-block. Whether this field is the
  LAN-handout vs WAN-upstream DNS is firmware-ambiguous — verify empirically via the query log
  after a reboot; if clients still collapse to `192.168.1.1`, flip Pi-hole to run DHCP instead.
- **`sqlite3` and `pihole-FTL` are not on the host** — Pi-hole runs as a container here. Query
  the FTL DB with `docker exec pihole pihole-FTL sqlite3 /etc/pihole/pihole-FTL.db "<SQL>"`.
- **SQLite can't open a WAL database read-only.** A `:ro` bind mount of the pihole volume fails
  because SQLite must write the `-shm` wal-index. Mount RW and use `PRAGMA query_only=ON`.
- **mem_limit is silently discarded on this Pi kernel** ("kernel does not support memory limit
  capabilities") — harmless, but don't rely on cgroup memory caps on pi-node1.

## 2026-06-13 (Homepage mobile responsiveness)
- **Homepage auto-loads `custom.css`** placed in the config dir (`deploy/homepage/` →
  `/app/config`), but serves it at **`/api/config/custom.css`** (not `/custom.css`) — the
  rendered page links that path. Restart the container after adding it. Feature since v0.6.30.
- **Homepage is mostly responsive already** (header uses `flex-wrap`; row-style service grids
  collapse below the `lg` breakpoint). The squish on phones was the **header** cramming the
  greeting + 5-stat `resources` widget + clock (all `text_size: xl`) into one row. Fix was a
  `@media (max-width:640px)` block targeting `.information-widget-greeting/-datetime/-resource`,
  not a layout rewrite. Real DOM selectors come from the rendered HTML, not guesswork.
- **Owner apps' mobile layout is in their own repos** — a Homepage custom.css can't reach inside
  the cc-points/stock iframes-or-links; those are separate frontend fixes (owner deferred them).

## 2026-06-14 (Pi-hole exporter blank dashboard — v6 API + bind-mount inode)
- **ekofr/pihole-exporter is v5-only; it 401s against Pi-hole v6.** FTL v6 removed the legacy
  `/admin/api.php` (and `setupVars.conf`) in favour of a session REST API (`POST /api/auth` ->
  SID). ekofr `v1.2.0` (its newest release, Jul 2025) still hits the v5 endpoint, so it 401s
  then its `/metrics` hangs -> Prometheus scrape `context deadline exceeded` -> blank dashboard.
  Confirm the password is fine independently: `curl -s -X POST http://127.0.0.1:8081/api/auth -d
  '{"password":"<pw>"}'` should return `"valid":true`. (Pi-hole admin is on host **8081**;
  host **:80** is the Homepage Next.js app — do not test the API there, it 404s.)
- **Fix: swap to noobExtendsBot/pihole-exporter** (`ghcr.io/noobextendsbot/pihole-exporter`,
  multi-arch incl. arm64, same env vars + port 9617), pinned by digest. It speaks the v6 API
  with the same `PIHOLE_PASSWORD` (web password works; no app-password needed).
- **The fork renamed metrics/labels** vs the ekofr schema the Grafana dashboard expects.
  Normalised back in Prometheus `metric_relabel_configs` (not by editing 14 panels):
  `dns_queries_today`->`dns_queries_all_types`, `gravity_domains_being_blocked`->
  `domains_being_blocked`, `clients_ever_seen`->`unique_clients`, `query_type`->`querytypes`
  (+label `query_type`->`type`), `reply_type`->`reply` (+`reply_type`->`type`). Also the fork
  drops the `hostname` label ekofr emitted, which the dashboard `$node` var needs
  (`label_values(pihole_ads_blocked_today, hostname)`) — re-added via the static_configs target
  label `hostname: pi-node1`.
- **The fork emits a duplicate series** `pihole_upstream_queries{upstream="one.one.one.one"}`
  twice (IPv4+IPv6 reverse-resolve identically). Prometheus rolls back the **entire scrape** on
  any duplicate sample, so this one bug would blank everything — dropped that metric via
  relabel. Cost: the forward-destinations panel stays empty.
- **GOTCHA: single-file bind-mounted configs do not update on `compose up -d` after rsync.**
  `rsync` writes a temp file and renames it (new inode); the running container is bound to the
  **old inode**, so a SIGHUP reload re-reads the *stale* file (`prometheus_config_last_reload
  _successful=1` lies — it reloaded the old content). Verify with
  `docker exec prometheus grep -c metric_relabel_configs /etc/prometheus/prometheus.yml`. Fix is
  `docker compose up -d --force-recreate prometheus` so the bind mount re-resolves to the new
  file. `scripts/deploy.sh` does plain `compose up -d`, so **config-only changes to mounted
  files silently no-op** — force-recreate (or restart) the affected service after deploy.

## 2026-06-14 (streaming-exporter down on a non-UTF-8 domain — found while verifying the fleet)
- **A malformed FTL `domain` value can permanently down the streaming-exporter.** FTL logged a
  query whose `domain` held non-UTF-8 bytes (`192.168.1.198:443\xed http`). Python sqlite3's
  default `text_factory` decodes TEXT as **strict** UTF-8 and *raises*, aborting the whole
  scrape; because the bad row sits inside the 7-day baseline window, every cycle re-hit it ->
  `pihole_streaming_exporter_up=0` for ~7.6h (separate from, and predating, the v6 exporter
  fix). Fix: `con.text_factory = lambda b: b.decode("utf-8","replace")` in `connect()` — junk
  domains never match a service pattern, so tolerant decode just skips them. Rebuild with
  `scripts/deploy.sh --build streaming-exporter`.
- **Process note:** "is the pihole exporter fixed?" is not "is the fleet healthy?" — always sweep
  all Prometheus targets *and* exporter self-health gauges (`*_up`), not just container status.
  `streaming` target read `up` (its /metrics served fine) while `pihole_streaming_exporter_up`
  was 0 — container-level and target-level checks both missed it.
