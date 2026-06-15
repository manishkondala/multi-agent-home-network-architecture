# YouTube QoE tester (roadmap v0.6)

A single long-lived container that plays a curated list of public YouTube videos
headlessly, 24/7, and exports **video Quality-of-Experience metrics** (buffering,
resolution, bitrate, dropped frames, startup time) plus the **session TCP_INFO**
to Google's video CDN, as Prometheus series. pi-node1's Prometheus scrapes it
cross-node; Grafana (folder `pi-fleet/tests`) and the Homepage "YouTube Metrics"
tile visualise it.

This is a clean rebuild of the idea behind the old `/home/pi/vsc` tester — **no
code or secrets were copied** from it. The old tester respawned a Chrome container
per run and hand-pinned a `chromedriver` (constant version drift); this one is one
long-lived worker and installs `chromium` + `chromium-driver` from the **same apt
repo** so the browser and driver are always version-matched.

## How it works

1. `worker.py` serves `player.html` on `127.0.0.1:8731` (a tiny page that embeds
   YouTube via the **IFrame Player API**). Embedding dodges the consent/cookie wall
   and pre-roll ads of the watch page and exposes `movie_player.getStatsForNerds()`
   plus the underlying `<video>` element.
2. It loops over `videos.yml` forever. For each video: load it, play 5–15 min
   (default 7), and **poll once per second** via `window.__ytqoeSample()`:
   resolution height, fps, dropped frames, playback quality, buffering state,
   startup time, and whatever bitrate the player build exposes.
3. Chromium runs `--headless=new` with **`--disable-quic`**, forcing media onto
   TCP. A background thread (`tcpinfo.py`) runs `ss -tinHO` once per second and
   keeps the busiest **`*.googlevideo.com`** socket's TCP_INFO: SRTT, cwnd,
   retransmits, delivery_rate.
4. Errors (invalid/removed/embed-disabled videos, consent pages, wedged browser)
   are logged and the loop **skips to the next video — it never crashes**.

## Metrics (`:9621/metrics`, prefix `youtube_qoe_*`)

Labels: `{video_id, quality}` on per-playback gauges; `{video_id}` on TCP series.

| Metric | Type | Meaning |
|--------|------|---------|
| `youtube_qoe_up` | gauge | 1 while the worker loop is alive |
| `youtube_qoe_tcp_sampler_up` | gauge | 1 if the last `ss` capture succeeded |
| `youtube_qoe_video_playing{video_id,category}` | gauge | 1 for the currently-playing video |
| `youtube_qoe_plays_total{outcome}` | counter | sessions started (ok/error/unavailable/timeout) |
| `youtube_qoe_startup_seconds` | gauge | initial-load time (load → first playing frame) |
| `youtube_qoe_buffering_events_total{video_id}` | counter | rebuffering events |
| `youtube_qoe_buffering_ratio` | gauge | fraction of sampled seconds buffering |
| `youtube_qoe_buffering_seconds_total{video_id}` | counter | cumulative seconds buffering |
| `youtube_qoe_resolution_height` | gauge | decoded video height (px) |
| `youtube_qoe_fps` | gauge | reported frames per second |
| `youtube_qoe_dropped_frames_total{video_id}` | counter | dropped video frames |
| `youtube_qoe_playback_quality` | gauge | quality as an ordinal (144…4320) |
| `youtube_qoe_bitrate_video_bps` / `_audio_bps` / `_total_bps` | gauge | effective bitrate |
| `youtube_qoe_tcp_srtt_us{video_id}` | gauge | SRTT to the CDN (µs) |
| `youtube_qoe_tcp_cwnd{video_id}` | gauge | congestion window (segments) |
| `youtube_qoe_tcp_retrans_total{video_id}` | counter | retransmits to the CDN |
| `youtube_qoe_tcp_delivery_rate_bps{video_id}` | gauge | kernel delivery_rate to the CDN |
| `youtube_qoe_tcp_sockets{video_id}` | gauge | active googlevideo sockets observed |

## The `ss` / host-networking requirement (read before deploy)

`ss` reads the **network namespace it runs in**. For it to see the browser's real
CDN sockets, the worker, Chromium and `ss` must share one netns. The compose
service therefore uses **`network_mode: host`**. Two consequences:

- **QUIC must be off** (it is — `--disable-quic`), or media uses UDP/QUIC and has
  no TCP_INFO to read.
- **Colima caveat:** on macOS, Docker `network_mode: host` binds to the **Colima
  VM's** network, not macOS directly. At deploy, verify two things from pi-node1:
  (a) `:9621` is reachable across the LAN, and (b) `ss` inside the container
  actually lists `*.googlevideo.com` sockets (`docker exec youtube-qoe ss -tn | grep :443`).
  If Colima's host-net proves too isolated for either, run the worker inside the
  Colima VM's netns (e.g. `colima ssh` + run there, or a privileged sidecar) — this
  is the one deploy-time unknown for the Intel Mac mini target.

## Deploy (on pi-node2, once Colima is up — NOT yet)

This app is **code-only** for now; deployment waits on Colima being installed on
pi-node2 (roadmap v0.7). When ready:

```sh
# 1. Get the build context + compose onto pi-node2 (git-snapshot-over-ssh; extend
#    scripts/sync-apps.sh with a `youtube` target, or git-archive this subtree).
# 2. Build the image ON pi-node2 under Colima (x86_64) and start it:
ssh pi-node2 'cd ~/pi-fleet && docker compose -f docker-compose.pi-node2.yml up -d --build youtube-qoe'
# 3. Verify:
ssh pi-node2 'curl -s localhost:9621/metrics | grep youtube_qoe_up'
ssh pi-node2 'docker exec youtube-qoe ss -tn | grep :443 | head'   # CDN sockets visible?
# 4. Point the Prometheus `youtube-qoe` job at pi-node2's reachable name (Tailscale
#    MagicDNS or a DHCP-reserved LAN hostname) — replace the `pi-node2.PLACEHOLDER`
#    target in deploy/prometheus/prometheus.yml, then redeploy the Pi stack.
```

The Grafana dashboard and Homepage tile are already provisioned on pi-node1 and
will light up once the scrape target resolves.

## Known caveat: headless YouTube quality / bot detection

Headless Chromium can get **degraded quality ladders or playback-quality caps**,
and YouTube may surface consent walls or, occasionally, treat the session as a bot.
We mitigate by embedding via the IFrame API (no watch-page consent/ads), muting
audio, forcing a 1280×720 viewport, and requesting `hd1080`. We do **not** log in
or use cookies (owner directive: no login). Treat absolute quality numbers as a
**relative trend over time on this fixed setup**, not a guarantee of what a real
logged-in user on the same network would receive. If quality is consistently
capped, the deploy-time options are a persistent profile dir or a headful Xvfb
session on the Mac mini (it has a desktop) — revisit only if the data looks unusable.
