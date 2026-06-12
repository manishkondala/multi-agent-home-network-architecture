# checks.lib.sh — shared health checks for fleet-sentinel.sh / fleet-report.sh (runs ON the Pi)
# Sourced, not executed.

FLEET_DIR=/home/pi/pi-fleet
SENTINEL_DIR=$FLEET_DIR/sentinel
STATE_DIR=$SENTINEL_DIR/state
INCIDENT_DIR=$FLEET_DIR/incidents
COMPOSE="docker compose -f $FLEET_DIR/docker-compose.yml"

# Containers that are NEVER ours to manage (owner's legacy project, deliberately stopped).
DENYLIST="jsms_worker-au happy_shannon adoring_jones kind_volhard pedantic_booth"

# name|url|compose-service  (ok = HTTP 200-399)
HTTP_CHECKS="
homepage|http://localhost:80/|homepage
cc-points|http://localhost:3002/|cc-points
stock-frontend|http://localhost:3003/|stock-frontend
stock-backend|http://localhost:3004/api/health|stock-backend
grafana|http://localhost:3000/api/health|grafana
prometheus|http://localhost:9090/-/healthy|prometheus
loki|http://localhost:3100/ready|loki
pihole-admin|http://localhost:8081/admin/|pihole
"

DISK_MIN_KB=3145728   # 3GB
TEMP_MAX=70

http_code() { curl -s -m 8 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || echo 000; }
http_ok()   { local c; c=$(http_code "$1"); [ "$c" -ge 200 ] 2>/dev/null && [ "$c" -lt 400 ]; }

expected_services() { $COMPOSE config --services 2>/dev/null; }
running_services()  { $COMPOSE ps --services --status running 2>/dev/null; }

# echoes one "svc|reason" line per failure
failed_services() {
    local exp run svc line name url
    exp=$(expected_services); run=$(running_services)
    for svc in $exp; do
        echo "$run" | grep -qx "$svc" || echo "$svc|container not running"
    done
    while IFS='|' read -r name url svc; do
        [ -z "$name" ] && continue
        # only flag http if the container claims to run (else already flagged above)
        if echo "$run" | grep -qx "$svc" && ! http_ok "$url"; then
            echo "$svc|http check '$name' failed ($url -> $(http_code "$url"))"
        fi
    done <<< "$HTTP_CHECKS"
    # DNS (the actual product) -> pihole
    if echo "$run" | grep -qx "pihole"; then
        local r b
        r=$(dig +short +time=3 +tries=1 @127.0.0.1 google.com 2>/dev/null | head -1)
        b=$(dig +short +time=3 +tries=1 @127.0.0.1 doubleclick.net 2>/dev/null | head -1)
        [ -z "$r" ] && echo "pihole|DNS resolution failed (google.com -> empty)"
        [ -n "$b" ] && [ "$b" != "0.0.0.0" ] && echo "pihole|ad-blocking failed (doubleclick.net -> $b, expected 0.0.0.0)"
    fi
}

host_temp()    { vcgencmd measure_temp 2>/dev/null | grep -o '[0-9.]*' | head -1; }
disk_avail_kb(){ df --output=avail / | tail -1 | tr -d ' '; }

# host issues: "kind|detail"
host_issues() {
    local kb t
    kb=$(disk_avail_kb)
    [ "$kb" -lt "$DISK_MIN_KB" ] 2>/dev/null && echo "disk|only $((kb/1024))MB free (< 3GB)"
    t=$(host_temp)
    [ -n "$t" ] && [ "${t%.*}" -ge "$TEMP_MAX" ] 2>/dev/null && echo "temp|CPU at ${t}C (>= ${TEMP_MAX}C)"
}

send_mail() {  # $1=subject, body on stdin
    python3 $SENTINEL_DIR/send-mail.py "$1"
}
