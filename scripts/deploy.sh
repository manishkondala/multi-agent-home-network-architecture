#!/usr/bin/env bash
# Deploy the pi-fleet stack to pi-node1.
# Usage: scripts/deploy.sh [service...]   (no args = whole stack)
set -euo pipefail

HOST=pi-node1
REMOTE_DIR=pi-fleet
cd "$(dirname "$0")/.."

echo "==> Fetching secrets from macOS Keychain"
PIHOLE_PASSWORD=$(security find-generic-password -s pi-fleet -a pihole-web -w)
GRAFANA_PASSWORD=$(security find-generic-password -s pi-fleet -a grafana-admin -w)
PI_IP=$(ssh "$HOST" "hostname -I | awk '{print \$1}'")
echo "==> pi-node1 LAN IP: $PI_IP"

echo "==> Pausing sentinel during deploy"
ssh "$HOST" "mkdir -p $REMOTE_DIR/sentinel && touch $REMOTE_DIR/sentinel/pause"
trap 'ssh "$HOST" "rm -f $REMOTE_DIR/sentinel/pause"' EXIT

echo "==> Syncing deploy/ -> $HOST:~/$REMOTE_DIR"
RSYNC_OUT=$(rsync -azi --delete --exclude .env --exclude homepage/logs \
      --exclude incidents --exclude secrets --exclude learnings-inbox.md \
      --exclude sentinel/state --exclude sentinel/runs --exclude sentinel/outbox \
      --exclude sentinel/pause --exclude 'sentinel/*.log' deploy/ "$HOST:$REMOTE_DIR/")
printf '%s\n' "$RSYNC_OUT"

# Single-file bind-mounted configs do NOT update on a plain `compose up -d`: rsync
# replaces the file's inode, but the running container stays bound to the old inode
# (even a SIGHUP reload then re-reads the stale file). Force-recreate any service
# whose config changed so its bind mount re-resolves. See docs/LEARNINGS.md 2026-06-14.
# NB: no `declare -A` — the Mac runs bash 3.2, which has no associative arrays.
config_owner() {  # changed-path -> service that single-file-mounts it (empty if none)
  case "$1" in
    prometheus/*) echo prometheus ;;
    loki/*)       echo loki ;;
    promtail/*)   echo promtail ;;
    blackbox/*)   echo blackbox-exporter ;;
  esac
}
RECREATE=""
# rsync itemize: '<f' = sent to remote (our push), '>f' = received, 'cf' = created.
while IFS= read -r changed; do
  [ -n "$changed" ] || continue
  svc=$(config_owner "$changed")
  [ -n "$svc" ] || continue
  case " $RECREATE " in *" $svc "*) ;; *) RECREATE="$RECREATE $svc" ;; esac
done < <(printf '%s\n' "$RSYNC_OUT" | awk '/^[<>c]f/{print $NF}')
RECREATE="${RECREATE# }"

echo "==> Writing .env on the Pi (secrets never touch the repo)"
ssh "$HOST" "cat > $REMOTE_DIR/.env && chmod 600 $REMOTE_DIR/.env" <<EOF
TZ=America/New_York
PIHOLE_PASSWORD=$PIHOLE_PASSWORD
GRAFANA_PASSWORD=$GRAFANA_PASSWORD
HOMEPAGE_VAR_HOST=$PI_IP
EOF

echo "==> docker compose up"
ssh "$HOST" "cd $REMOTE_DIR && docker compose up -d --remove-orphans $*"

if [ -n "$RECREATE" ]; then
  echo "==> Config files changed; force-recreating: $RECREATE"
  ssh "$HOST" "cd $REMOTE_DIR && docker compose up -d --force-recreate $RECREATE"
fi

echo "==> Sentinel cron (idempotent)"
ssh "$HOST" "bash $REMOTE_DIR/sentinel/install-cron.sh"

echo "==> Stack state"
ssh "$HOST" "cd $REMOTE_DIR && docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'"
