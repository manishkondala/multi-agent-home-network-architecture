# Learnings

Running log of things we learned the hard way (or just learned). Newest first.
`coach` appends here after reviews; everyone appends when they hit something non-obvious.

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
