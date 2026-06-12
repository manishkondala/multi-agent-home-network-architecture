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
rsync -az --delete --exclude .env --exclude homepage/logs \
      --exclude incidents --exclude secrets --exclude learnings-inbox.md \
      --exclude sentinel/state --exclude sentinel/runs --exclude sentinel/outbox \
      --exclude sentinel/pause --exclude 'sentinel/*.log' deploy/ "$HOST:$REMOTE_DIR/"

echo "==> Writing .env on the Pi (secrets never touch the repo)"
ssh "$HOST" "cat > $REMOTE_DIR/.env && chmod 600 $REMOTE_DIR/.env" <<EOF
TZ=America/New_York
PIHOLE_PASSWORD=$PIHOLE_PASSWORD
GRAFANA_PASSWORD=$GRAFANA_PASSWORD
HOMEPAGE_VAR_HOST=$PI_IP
EOF

echo "==> docker compose up"
ssh "$HOST" "cd $REMOTE_DIR && docker compose up -d --remove-orphans $*"

echo "==> Sentinel cron (idempotent)"
ssh "$HOST" "bash $REMOTE_DIR/sentinel/install-cron.sh"

echo "==> Stack state"
ssh "$HOST" "cd $REMOTE_DIR && docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'"
