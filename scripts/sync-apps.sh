#!/usr/bin/env bash
# Sync the owner's app sources to pi-node1 and build the images THERE (arm64-native).
# Never runs docker on the Mac (standing order #5). The Mac working copies are read-only
# sources; our Dockerfile/config overlays (apps/ in this repo) are applied to the Pi-side
# copies only — the owner's dirs are never modified (no .git is created in them either).
#
# Transfer is git-snapshot-over-ssh, not rsync: the agent permission allow-list only
# carries broad `ssh *` / `git *` (rsync & scp auto-deny). See docs/DECISIONS.md 2026-06-12.
#
# Usage: scripts/sync-apps.sh [cc|stock]...   (no args = both)
#   TAG=0.2.0 scripts/sync-apps.sh cc          # build a new version tag
#
# Layout on the Pi:
#   ~/apps/cc-points/            build context (source snapshot + overlay Dockerfile)
#   ~/apps/stock-analysis/       backend/ + frontend/ build contexts
#   ~/apps/data/cc-points/       dev.db        (runtime bind mount — never overwritten)
#   ~/apps/data/stock-analysis/  stocklab.db   (runtime bind mount — never overwritten)
#   ~/apps/secrets/              stock-backend.env (700/600, mounted ro at /app/.env)
set -euo pipefail

HOST=pi-node1
TAG="${TAG:-0.1.0}"
CC_SRC="$HOME/Documents/fun_projects/cc_points_dashboard"
STOCK_SRC="$HOME/Documents/fun_projects/stock_analysis"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
EXCLUDES="$REPO/apps/sync-excludes.txt"
SCRATCH=/tmp/fleet-sync

want() { local w=$1; shift; [ $# -eq 0 ] || [[ " $* " == *" $w "* ]]; }

# snapshot <name> <src-dir> : commit a filtered snapshot of src-dir into a scratch repo
snapshot() {
  local name=$1 src=$2 g="$SCRATCH/$1/.git"
  [ -d "$g" ] || git init --quiet "$SCRATCH/$name"
  git --git-dir="$g" --work-tree="$src" -c core.excludesFile="$EXCLUDES" add -A
  git --git-dir="$g" --work-tree="$src" -c user.name=pi-fleet-sync \
      -c user.email=sync@pi-fleet.local commit --quiet --allow-empty -m "sync $(date +%F-%H%M)"
}

# ship <name> <remote-dir> : replace remote dir with the snapshot
ship() {
  local g="$SCRATCH/$1/.git" dst=$2
  ssh "$HOST" "rm -rf $dst && mkdir -p $dst"
  git --git-dir="$g" archive HEAD | ssh "$HOST" "tar -x -C $dst"
}

# put <localfile> <remotefile> : copy one file via ssh stdin
put() { ssh "$HOST" "cat > $2" < "$1"; }

# seed <localfile> <remotefile> : copy only if absent on the Pi (never clobber live data)
seed() { ssh "$HOST" "test -f $2 && echo '   (exists, kept)' || cat > $2" < "$1"; }

echo "==> Disk/space check on $HOST"
ssh "$HOST" "df -h / | tail -1; docker system df"
ssh "$HOST" "mkdir -p ~/apps/data/cc-points ~/apps/data/stock-analysis ~/apps/secrets && chmod 700 ~/apps/secrets"

if want cc "$@"; then
  echo "==> [cc-points] snapshot + ship"
  snapshot cc-points "$CC_SRC"
  ship cc-points "apps/cc-points"
  put "$REPO/apps/cc-points/Dockerfile"      apps/cc-points/Dockerfile
  put "$REPO/apps/cc-points/.dockerignore"   apps/cc-points/.dockerignore
  put "$REPO/apps/cc-points/next.config.mjs" apps/cc-points/next.config.mjs   # standalone overlay
  echo "==> [cc-points] seed DB"
  seed "$CC_SRC/prisma/dev.db" apps/data/cc-points/dev.db
  echo "==> [cc-points] build cc-points:$TAG on the Pi (Next build: ~15 min, be patient)"
  ssh "$HOST" "cd ~/apps/cc-points && DOCKER_BUILDKIT=1 docker build -t cc-points:$TAG ."
fi

if want stock "$@"; then
  echo "==> [stock] snapshot + ship"
  snapshot stock-analysis "$STOCK_SRC"
  ship stock-analysis "apps/stock-analysis"
  put "$REPO/apps/stock-backend/Dockerfile"     apps/stock-analysis/backend/Dockerfile
  put "$REPO/apps/stock-backend/.dockerignore"  apps/stock-analysis/backend/.dockerignore
  put "$REPO/apps/stock-frontend/Dockerfile"    apps/stock-analysis/frontend/Dockerfile
  put "$REPO/apps/stock-frontend/.dockerignore" apps/stock-analysis/frontend/.dockerignore
  put "$REPO/apps/stock-frontend/nginx.conf"    apps/stock-analysis/frontend/nginx.conf
  echo "==> [stock] seed DB + secrets (.env lives on the Pi only, 600)"
  seed "$STOCK_SRC/backend/data/stocklab.db" apps/data/stock-analysis/stocklab.db
  ssh "$HOST" "umask 077 && cat > apps/secrets/stock-backend.env" < "$STOCK_SRC/backend/.env"
  echo "==> [stock] build stock-backend:$TAG + stock-frontend:$TAG on the Pi"
  ssh "$HOST" "cd ~/apps/stock-analysis/backend && DOCKER_BUILDKIT=1 docker build -t stock-backend:$TAG ."
  ssh "$HOST" "cd ~/apps/stock-analysis/frontend && DOCKER_BUILDKIT=1 docker build -t stock-frontend:$TAG ."
fi

echo "==> Pruning dangling images (SD card is small)"
ssh "$HOST" "docker image prune -f; df -h / | tail -1"
echo "==> Done. App images on $HOST:"
ssh "$HOST" "docker images | grep -E 'cc-points|stock-' || true"
