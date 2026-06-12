#!/bin/bash
# fleet-sentinel.sh — detection layer (cron, every 3 min, ON the Pi).
# Detects failures, writes an incident record, then invokes the Claude Sentinel agent
# (sentinel-agent.sh) to diagnose & FIX. This script never fixes anything itself —
# owner decision 2026-06-12: Claude-only fixes.
set -u
source "$(dirname "$0")/checks.lib.sh"

mkdir -p "$STATE_DIR" "$INCIDENT_DIR/new" "$INCIDENT_DIR/archive" "$SENTINEL_DIR/runs" "$SENTINEL_DIR/outbox"
exec 9>"$STATE_DIR/lock"; flock -n 9 || exit 0          # one instance
[ -f "$SENTINEL_DIR/pause" ] && exit 0                  # deploy in progress
pgrep -f "docker compose up|docker build" >/dev/null && exit 0
date -u +%FT%TZ > "$STATE_DIR/last-run"

NOW=$(date +%s)
COOLDOWN=900   # don't re-invoke the agent more than once per 15 min for an ongoing outage

past_incidents() {  # outage memory for $1
    local n last
    n=$(ls "$INCIDENT_DIR/new" "$INCIDENT_DIR/archive" 2>/dev/null | grep -c -- "-$1.md")
    last=$(ls "$INCIDENT_DIR/new" "$INCIDENT_DIR/archive" 2>/dev/null | grep -- "-$1.md" | sort | tail -1)
    echo "prior incidents for $1: $n${last:+ (last: $last)}"
}

FAILS=$(failed_services; host_issues | sed 's/^/host-/')
if [ -z "$FAILS" ]; then
    rm -f "$STATE_DIR"/outage-open 2>/dev/null
    exit 0
fi

# Ongoing outage already handed to the agent recently? Let it work / cool down.
if [ -f "$STATE_DIR/outage-open" ] && [ $(( NOW - $(stat -c %Y "$STATE_DIR/outage-open") )) -lt "$COOLDOWN" ]; then
    exit 0
fi
touch "$STATE_DIR/outage-open"

TS=$(date -u +%Y%m%dT%H%M%SZ)
INC=$INCIDENT_DIR/new/$TS-outage.md
{
    echo "# Incident $TS — detected by fleet-sentinel"
    echo "- time: $(date -u +%FT%TZ) (UTC) / $(date '+%F %T %Z') (local)"
    echo; echo "## Failing checks"
    echo "$FAILS" | sed 's/|/ — /;s/^/- /'
    echo; echo "## Outage memory"
    echo "$FAILS" | cut -d'|' -f1 | sort -u | while read -r s; do echo "- $(past_incidents "$s")"; done
    echo; echo "## Container state"
    docker ps -a --format '{{.Names}}\t{{.Status}}' | sed 's/^/    /'
    echo; echo "## Recent logs of failing services"
    echo "$FAILS" | cut -d'|' -f1 | sort -u | grep -v '^host-' | while read -r s; do
        echo "### $s"; echo '```'; docker logs "$s" --tail 40 2>&1 | tail -40; echo '```'
    done
    echo; echo "_Status: DETECTED — Sentinel agent invoked. It appends its fix + RCA below._"
} > "$INC"

echo "$(date -u +%FT%TZ) outage detected -> invoking sentinel agent ($INC)" >> "$SENTINEL_DIR/sentinel.log"
bash "$SENTINEL_DIR/sentinel-agent.sh" "$INC" >> "$SENTINEL_DIR/sentinel.log" 2>&1
exit 0
