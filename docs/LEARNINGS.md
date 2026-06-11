# Learnings

Running log of things we learned the hard way (or just learned). Newest first.
`coach` appends here after reviews; everyone appends when they hit something non-obvious.

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
