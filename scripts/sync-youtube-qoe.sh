#!/usr/bin/env bash
# Sync the YouTube QoE tester to its host node, build the image THERE (native arch),
# and bring up the node-portable compose stack. Never runs docker on the Mac.
#
# Unlike scripts/sync-apps.sh (which snapshots the owner's EXTERNAL working copies),
# this app's source lives INSIDE this repo at apps/test/video/youtube, so we ship that
# subtree with `git archive` over ssh — same transport (allow-listed `ssh`/`git`, no
# rsync/scp). The compose file (deploy/docker-compose.youtube-qoe.yml) rides along in
# the normal `scripts/deploy.sh` rsync of deploy/, so run deploy.sh first (or it's fine
# to run this standalone; it only needs ~/pi-fleet/docker-compose.youtube-qoe.yml present).
#
# Layout on the node:
#   ~/apps/test/video/youtube/   build context (this repo subtree)
#   ~/pi-fleet/                  deploy dir (compose file lives here; synced by deploy.sh)
#
# HOST defaults to pi-node1 (today's host); override for pi-node3 when it lands:
#   HOST=pi-node3 scripts/sync-youtube-qoe.sh
set -euo pipefail

HOST="${HOST:-pi-node1}"
REMOTE_DIR=pi-fleet
APP_SUBTREE=apps/test/video/youtube
REMOTE_CTX="apps/test/video/youtube"   # must match `build:` (../apps/test/video/youtube) from ~/pi-fleet
cd "$(dirname "$0")/.."

echo "==> Disk/space check on $HOST"
ssh "$HOST" "df -h / | tail -1; docker system df"

echo "==> Shipping $APP_SUBTREE -> $HOST:~/$REMOTE_CTX (git archive over ssh)"
ssh "$HOST" "rm -rf $REMOTE_CTX && mkdir -p $REMOTE_CTX"
git archive HEAD "$APP_SUBTREE" | ssh "$HOST" "tar -x --strip-components=4 -C $REMOTE_CTX"

echo "==> Building youtube-qoe ON $HOST (arm64-native; chromium apt install is the slow part)"
ssh "$HOST" "cd $REMOTE_DIR && DOCKER_BUILDKIT=1 docker compose -f docker-compose.youtube-qoe.yml build"

echo "==> Bringing up youtube-qoe (capped: mem 1g, cpus 1.5, host net)"
ssh "$HOST" "cd $REMOTE_DIR && docker compose -f docker-compose.youtube-qoe.yml up -d"

echo "==> Pruning dangling images (SD card is small)"
ssh "$HOST" "docker image prune -f; df -h / | tail -1"

echo "==> youtube-qoe state on $HOST:"
ssh "$HOST" "docker ps --filter name=youtube-qoe --format 'table {{.Names}}\t{{.Status}}'"
