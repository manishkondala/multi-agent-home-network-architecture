#!/bin/bash
# install-cron.sh — idempotent sentinel setup ON the Pi (run by deploy.sh after sync).
set -eu
SENTINEL_DIR=/home/pi/pi-fleet/sentinel
mkdir -p "$SENTINEL_DIR/state" "$SENTINEL_DIR/runs" "$SENTINEL_DIR/outbox" \
         /home/pi/pi-fleet/incidents/new /home/pi/pi-fleet/incidents/archive \
         /home/pi/pi-fleet/secrets
chmod 700 /home/pi/pi-fleet/secrets

# Owner-local timezone so "0 7,19" means 7AM/7PM for the owner (DST-proof).
if [ "$(timedatectl show -p Timezone --value 2>/dev/null)" != "America/New_York" ]; then
    sudo timedatectl set-timezone America/New_York && echo "timezone -> America/New_York"
fi

MARK="# pi-fleet-sentinel"
( crontab -l 2>/dev/null | grep -v "$MARK" || true
  echo "*/3 * * * * /bin/bash $SENTINEL_DIR/fleet-sentinel.sh >> $SENTINEL_DIR/cron.log 2>&1 $MARK"
  echo "0 7,19 * * * /bin/bash $SENTINEL_DIR/fleet-report.sh email >> $SENTINEL_DIR/cron.log 2>&1 $MARK"
) | crontab -
echo "cron installed:"; crontab -l | grep "$MARK"
