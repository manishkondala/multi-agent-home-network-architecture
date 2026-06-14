#!/usr/bin/env python3
"""wifi-rf-exporter — continuous RF/channel-occupancy sensing from the Pi's radio.

eth0 carries DNS, so wlan0 is free to dedicate to sensing. We periodically run
`iw dev <iface> scan` and turn the neighbour-AP picture into Prometheus series:
which channels are crowded, how strong the competing APs are, how many stations
they carry. This is co-channel / adjacent-channel *interference* — the thing that
makes a channel slow even when your signal is fine.

We also *attempt* `iw survey dump` each cycle for the channel noise floor and
busy/active airtime (the real tell for non-Wi-Fi interference like a microwave).
The Pi's onboard Broadcom chip returns nothing for survey while the interface is
dormant (verified 2026-06-14), so those series stay empty until a survey-capable
radio (USB adapter / Mac-mini) is added. We export what we can and degrade quietly.
"""
import os
import re
import subprocess
import time

from prometheus_client import Gauge, start_http_server

IFACE = os.environ.get("WIFI_IFACE", "wlan0")
PORT = int(os.environ.get("PORT", "9620"))
INTERVAL = int(os.environ.get("SCAN_INTERVAL", "60"))

SCAN_UP = Gauge("wifi_rf_scan_up", "1 if the last iw scan succeeded")
LAST_SCAN = Gauge("wifi_rf_last_scan_timestamp_seconds", "Unix time of the last successful scan")
NEIGHBORS = Gauge("wifi_rf_neighbor_aps", "Visible neighbour APs, by band", ["band"])
CH_APS = Gauge("wifi_rf_channel_ap_count", "Neighbour APs on a channel", ["channel", "band"])
CH_DBM = Gauge("wifi_rf_channel_strongest_dbm", "Strongest neighbour signal on a channel", ["channel", "band"])
CH_STA = Gauge("wifi_rf_channel_station_count", "Stations on neighbour APs on a channel (BSS Load)", ["channel", "band"])
SURVEY_NOISE = Gauge("wifi_rf_survey_noise_dbm", "Channel noise floor (if the radio supports survey)", ["channel"])
SURVEY_BUSY = Gauge("wifi_rf_survey_busy_ratio", "Channel busy/active airtime ratio (if supported)", ["channel"])
EXPORTER_UP = Gauge("wifi_rf_exporter_up", "1 while the exporter process is alive")


def freq_to_channel(mhz):
    if 2412 <= mhz <= 2472:
        return (mhz - 2407) // 5
    if mhz == 2484:
        return 14
    if 5000 <= mhz < 5900:
        return (mhz - 5000) // 5
    if 5925 <= mhz <= 7125:
        return (mhz - 5950) // 5
    return 0


def band_of(mhz):
    if mhz < 2500:
        return "2.4GHz"
    if mhz < 5925:
        return "5GHz"
    return "6GHz"


def run_iw(*args):
    return subprocess.run(["iw", "dev", IFACE, *args],
                          capture_output=True, text=True, timeout=30).stdout


def parse_scan(text):
    """Return list of {freq, channel, band, signal, stations} per BSS."""
    aps, cur, in_load = [], None, False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("BSS "):
            if cur:
                aps.append(cur)
            cur = {"freq": None, "signal": None, "stations": 0}
            in_load = False
            continue
        if cur is None:
            continue
        if line.startswith("freq:"):
            cur["freq"] = int(float(line.split(":", 1)[1]))
        elif line.startswith("signal:"):
            m = re.search(r"(-?\d+(?:\.\d+)?)", line)
            if m:
                cur["signal"] = float(m.group(1))
        elif line.startswith("BSS Load"):
            in_load = True
        elif in_load and "station count" in line:
            m = re.search(r"station count:\s*(\d+)", line)
            if m:
                cur["stations"] = int(m.group(1))
            in_load = False
    if cur:
        aps.append(cur)
    for ap in aps:
        if ap["freq"]:
            ap["channel"] = freq_to_channel(ap["freq"])
            ap["band"] = band_of(ap["freq"])
    return [a for a in aps if a["freq"]]


def publish_scan(aps):
    CH_APS.clear(); CH_DBM.clear(); CH_STA.clear(); NEIGHBORS.clear()
    per_band, per_ch = {}, {}
    for ap in aps:
        ch, band = str(ap["channel"]), ap["band"]
        per_band[band] = per_band.get(band, 0) + 1
        key = (ch, band)
        agg = per_ch.setdefault(key, {"aps": 0, "dbm": -120.0, "sta": 0})
        agg["aps"] += 1
        agg["sta"] += ap["stations"]
        if ap["signal"] is not None:
            agg["dbm"] = max(agg["dbm"], ap["signal"])
    for band, n in per_band.items():
        NEIGHBORS.labels(band).set(n)
    for (ch, band), agg in per_ch.items():
        CH_APS.labels(ch, band).set(agg["aps"])
        CH_STA.labels(ch, band).set(agg["sta"])
        if agg["dbm"] > -120:
            CH_DBM.labels(ch, band).set(agg["dbm"])


def publish_survey(text):
    """Best-effort; empty on radios without survey support."""
    SURVEY_NOISE.clear(); SURVEY_BUSY.clear()
    freq = noise = active = busy = None

    def flush():
        if freq is None:
            return
        ch = str(freq_to_channel(freq))
        if noise is not None:
            SURVEY_NOISE.labels(ch).set(noise)
        if active and busy is not None:
            SURVEY_BUSY.labels(ch).set(round(busy / active, 4))

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("frequency:"):
            flush()
            freq = int(re.search(r"(\d+)", line).group(1))
            noise = active = busy = None
        elif line.startswith("noise:"):
            noise = float(re.search(r"(-?\d+)", line).group(1))
        elif "channel active time" in line:
            active = int(re.search(r"(\d+)", line).group(1))
        elif "channel busy time" in line:
            busy = int(re.search(r"(\d+)", line).group(1))
    flush()


def main():
    start_http_server(PORT)
    EXPORTER_UP.set(1)
    # Best-effort: bring the (free) radio up so it can scan/survey. Ignore if managed.
    subprocess.run(["ip", "link", "set", IFACE, "up"], capture_output=True)
    print(f"wifi-rf-exporter on :{PORT}, iface={IFACE}, every {INTERVAL}s", flush=True)
    while True:
        try:
            publish_scan(parse_scan(run_iw("scan")))
            SCAN_UP.set(1)
            LAST_SCAN.set(time.time())
        except Exception as exc:
            SCAN_UP.set(0)
            print(f"scan error: {exc}", flush=True)
        try:
            publish_survey(run_iw("survey", "dump"))
        except Exception as exc:
            print(f"survey error (expected on Broadcom): {exc}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
