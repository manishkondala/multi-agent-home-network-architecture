#!/bin/bash
# sentinel-agent.sh <incident-file> — invoke the Claude Sentinel agent ON the Pi (headless).
# The agent diagnoses & fixes, appends its report to the incident file, logs learnings.
# This wrapper guarantees the owner gets an email either way (agent report, or raw incident
# if Claude is unavailable — e.g. no auth/credits yet).
set -u
INC=${1:?usage: sentinel-agent.sh <incident-file>}
SENTINEL_DIR=/home/pi/pi-fleet/sentinel
export PATH=$HOME/.local/bin:$PATH

# Auth: dedicated env first (secrets/claude.env: ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN),
# fallback to the stock-analysis app key already on this box.
if [ -f "$HOME/pi-fleet/secrets/claude.env" ]; then set -a; . "$HOME/pi-fleet/secrets/claude.env"; set +a
elif [ -f "$HOME/apps/secrets/stock-backend.env" ]; then
    export "$(grep '^ANTHROPIC_API_KEY=' "$HOME/apps/secrets/stock-backend.env")"
fi

MODEL=${SENTINEL_MODEL:-claude-sonnet-4-6}
TS=$(date -u +%Y%m%dT%H%M%SZ)
RUNLOG=$SENTINEL_DIR/runs/$TS-sentinel.log

cd "$HOME/pi-fleet"
timeout 1500 claude -p "You are the Sentinel agent. Read your standing instructions in \
$SENTINEL_DIR/SENTINEL.md and the active incident in $INC, then diagnose and fix the outage. \
Follow SENTINEL.md exactly." \
    --model "$MODEL" --max-turns 40 --dangerously-skip-permissions \
    > "$RUNLOG" 2>&1
RC=$?

if [ $RC -eq 0 ] && grep -q '## Sentinel fix report' "$INC"; then
    STATUS=$(grep -o 'Status: [A-Z-]*' "$INC" | tail -1 | cut -d' ' -f2)
    python3 "$SENTINEL_DIR/send-mail.py" "[pi-fleet] INCIDENT — ${STATUS:-handled by Sentinel}" < "$INC"
    echo "$(date -u +%FT%TZ) sentinel agent finished: ${STATUS:-?} (run log: $RUNLOG)"
else
    {
        echo "The Claude Sentinel agent could NOT run (exit $RC — likely missing auth/credits,"
        echo "see $RUNLOG). Raw incident below; no automatic fix was attempted."
        echo; cat "$INC"
    } | python3 "$SENTINEL_DIR/send-mail.py" "[pi-fleet] INCIDENT — SENTINEL UNAVAILABLE, manual attention needed"
    echo "$(date -u +%FT%TZ) sentinel agent FAILED rc=$RC (see $RUNLOG)"
fi
