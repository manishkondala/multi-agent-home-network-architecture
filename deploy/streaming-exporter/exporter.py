#!/usr/bin/env python3
"""streaming-exporter — classify Pi-hole DNS queries into streaming/services and
expose per-service, per-client counters for Prometheus.

The ekofr pihole-exporter only emits aggregate top-N domains, so it can't answer
"which device is watching Netflix". This reads the FTL query database directly and
groups domains -> service (mapping in services.yml), labelled by client IP.

Design notes:
  * FTL keeps pihole-FTL.db in WAL mode, so a read-only bind mount can't open it
    (SQLite needs to write the -shm wal-index). We mount RW but only ever SELECT,
    with PRAGMA query_only as a guard.
  * On startup we baseline counters from the last 7 days so they're immediately
    populated, then tail new rows by rowid each cycle (cheap, bounded query).
"""
import os
import sqlite3
import time

import yaml
from prometheus_client import Counter, Gauge, start_http_server

DB = os.environ.get("FTL_DB", "/etc/pihole/pihole-FTL.db")
PORT = int(os.environ.get("PORT", "9618"))
INTERVAL = int(os.environ.get("INTERVAL", "30"))
MAP_FILE = os.environ.get("SERVICES_FILE", "/app/services.yml")
BASELINE_DAYS = int(os.environ.get("BASELINE_DAYS", "7"))

with open(MAP_FILE) as fh:
    _cfg = yaml.safe_load(fh)
# Flatten to (service, lowercase-pattern) preserving file order (first match wins).
PATTERNS = [(svc, p.lower()) for svc, pats in _cfg["services"].items() for p in pats]

QUERIES = Counter(
    "pihole_service_queries_total",
    "Pi-hole DNS queries classified into a streaming/service, by client",
    ["service", "client"],
)
UP = Gauge("pihole_streaming_exporter_up", "1 if the last FTL DB scrape succeeded")
LAST_TS = Gauge(
    "pihole_streaming_exporter_last_query_timestamp_seconds",
    "Unix timestamp of the most recent query row processed",
)


def classify(domain):
    d = domain.lower()
    for svc, pat in PATTERNS:
        if pat in d:
            return svc
    return None


def connect():
    con = sqlite3.connect(DB, timeout=15)
    # FTL occasionally logs a malformed query whose `domain` holds non-UTF-8 bytes
    # (seen: '192.168.1.198:443\xed http'). The default text_factory decodes TEXT as
    # strict UTF-8 and *raises*, which aborts the whole scrape — and because the bad
    # row sits in the baseline window, the exporter stays down permanently. Decode
    # tolerantly instead; such junk domains never match a service pattern anyway.
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    con.execute("PRAGMA query_only=ON;")
    con.execute("PRAGMA busy_timeout=15000;")
    return con


def baseline(cur):
    since = f"-{BASELINE_DAYS} days"
    cur.execute(
        "SELECT domain, client, COUNT(*) FROM queries "
        "WHERE timestamp > strftime('%s','now',?) GROUP BY domain, client",
        (since,),
    )
    for domain, client, cnt in cur.fetchall():
        svc = classify(domain)
        if svc:
            QUERIES.labels(svc, client).inc(cnt)
    cur.execute("SELECT MAX(id) FROM queries")
    return cur.fetchone()[0] or 0


def tail(cur, last_id):
    cur.execute(
        "SELECT id, domain, client, timestamp FROM queries WHERE id > ? ORDER BY id",
        (last_id,),
    )
    for rid, domain, client, ts in cur.fetchall():
        svc = classify(domain)
        if svc:
            QUERIES.labels(svc, client).inc()
        last_id = rid
        LAST_TS.set(ts)
    return last_id


def main():
    start_http_server(PORT)
    print(f"streaming-exporter listening on :{PORT}, db={DB}, "
          f"{len(PATTERNS)} patterns", flush=True)
    last_id = None
    while True:
        try:
            con = connect()
            cur = con.cursor()
            last_id = baseline(cur) if last_id is None else tail(cur, last_id)
            con.close()
            UP.set(1)
        except Exception as exc:  # keep serving last-known counters on transient errors
            UP.set(0)
            print(f"scrape error: {exc}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
