# Runbook

## Access
- SSH: `ssh pi-node1` (alias → current DHCP IP, key `~/.ssh/id_ed25519_pifleet`)
- Secrets (macOS Keychain, service `pi-fleet`):
  `security find-generic-password -s pi-fleet -a pihole-web -w` (Pi-hole admin UI)
  `security find-generic-password -s pi-fleet -a grafana-admin -w` (Grafana `admin` user)
  `security find-generic-password -s pi-fleet -a pi -w` (Pi password — fallback only)
- URLs (LAN; swap host for Tailscale name when remote): portal `http://<pi>/`,
  Pi-hole `http://<pi>:8081/admin`, Grafana `http://<pi>:3000`, Prometheus `http://<pi>:9090`

## Deploy / update
```bash
./scripts/deploy.sh            # whole stack
./scripts/deploy.sh grafana    # one service
```
Rollback = `git checkout <last-good> -- deploy/ && ./scripts/deploy.sh`.

## Health checks (what watchdog runs)
```bash
ssh pi-node1 'cd pi-fleet && docker compose ps'
dig +short @<pi> doubleclick.net   # expect 0.0.0.0 (blocked)
dig +short @<pi> google.com        # expect a real IP
curl -s http://<pi>:9090/api/v1/targets | python3 -c "import json,sys; [print(t['labels']['job'], t['health']) for t in json.load(sys.stdin)['data']['activeTargets']]"
curl -s http://<pi>:3100/ready && curl -s http://<pi>:3000/api/health
```

## Common incidents
| Symptom | First moves |
|---------|------------|
| "Internet down" complaints | Almost always DNS. `dig @<pi> google.com`. If dead: `ssh pi-node1 'cd pi-fleet && docker compose restart pihole'`. If Pi unreachable: point router DNS back to 1.1.1.1 (instant restore), then debug. |
| A container restart-looping | `ssh pi-node1 'docker logs --tail 100 <name>'`; check Loki for context; mem_limit OOM is the usual suspect on the Pi. |
| Disk filling (29GB SD!) | `ssh pi-node1 'docker system df && sudo du -xh / --max-depth=2 \| sort -rh \| head'` → `docker image prune -f`. Retention: Prometheus 15d/2GB, Loki 7d. |
| Pi IP changed (DHCP) | Update `HostName` in `~/.ssh/config`, re-run deploy (re-injects IP into Homepage), update router DNS setting. Permanent fix: DHCP reservation on router. |
| Grafana login broken | Password is env-driven; re-run deploy. Note: GF_SECURITY_ADMIN_PASSWORD only sets the password on first boot of a fresh volume. To force: `docker exec grafana grafana cli admin reset-admin-password <new>`. |

## One-time owner tasks (status)
- [ ] Router: set DHCP DNS server → Pi's IP (this is what turns on ad blocking house-wide)
- [ ] Router: DHCP reservation for the Pi's MAC so the IP stops moving
- [ ] Tailscale: authenticate the Pi (auth URL produced during setup)
