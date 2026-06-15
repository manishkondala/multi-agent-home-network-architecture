#!/usr/bin/env python3
"""YouTube QoE worker — ONE long-lived process, loops over a curated video list
forever, playing each headless for 5-15 min and exporting Prometheus QoE metrics.

Design (roadmap v0.6):
  * Single long-lived worker, NOT container spawn/teardown (lighter than the old
    `vsc` controller that respawned Chrome per run).
  * Play via the YouTube IFrame Player API on a tiny local page (player.html),
    which dodges the consent/cookie wall and pre-roll ads of the watch page and
    gives us movie_player.getStatsForNerds() + the <video> element.
  * Poll once per second: resolution, fps, dropped frames, bitrate, buffering,
    startup time, playback quality.
  * QUIC disabled so media uses TCP; a background `ss -tin` sampler reads TCP_INFO
    for the googlevideo CDN sockets (needs host networking — see tcpinfo.py).
  * Robust: player errors / unavailable videos / consent pages -> log + skip to
    the next video. The loop NEVER crashes (every play wrapped in try/except).

No secrets, no login, no search. Pure public embed playback.
"""
import http.server
import os
import socketserver
import sys
import threading
import time

import yaml
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from metrics import Metrics
from tcpinfo import CdnSampler

# ---- config (env-overridable) ----
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9621"))
PLAY_SECONDS = int(os.environ.get("PLAY_SECONDS", "420"))      # default 7 min, within 5-15
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "1.0"))
STARTUP_TIMEOUT = int(os.environ.get("STARTUP_TIMEOUT", "60")) # give up if it won't start
VIDEOS_FILE = os.environ.get("VIDEOS_FILE", "/app/videos.yml")
PAGE_PORT = int(os.environ.get("PAGE_PORT", "8731"))           # local http for player.html
CHROMEDRIVER = os.environ.get("CHROMEDRIVER", "/usr/bin/chromedriver")
CHROMIUM_BIN = os.environ.get("CHROMIUM_BIN", "/usr/bin/chromium")

# YT.PlayerState
ENDED, PLAYING, PAUSED, BUFFERING, CUED = 0, 1, 2, 3, 5
# Quality ordinals so a gauge can plot "quality over time".
QUALITY_ORDINAL = {
    "tiny": 144, "small": 240, "medium": 360, "large": 480,
    "hd720": 720, "hd1080": 1080, "hd1440": 1440, "hd2160": 2160,
    "highres": 4320, "auto": 0, "unknown": 0,
}


def load_videos():
    with open(VIDEOS_FILE) as fh:
        data = yaml.safe_load(fh) or {}
    vids = data.get("videos", [])
    if not vids:
        raise SystemExit(f"no videos in {VIDEOS_FILE}")
    return vids


def serve_player_page():
    """Serve the directory containing player.html on 127.0.0.1:PAGE_PORT.

    A real http origin (not file://) keeps the IFrame API's origin check happy
    and matches how a browser would load an embed."""
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):  # don't spam stdout
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", PAGE_PORT), Quiet)
    threading.Thread(target=httpd.serve_forever, name="player-http", daemon=True).start()
    return f"http://127.0.0.1:{PAGE_PORT}/player.html"


def build_driver():
    opts = Options()
    opts.binary_location = CHROMIUM_BIN
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")                 # required as non-root in many bases
    opts.add_argument("--disable-dev-shm-usage")      # avoid /dev/shm exhaustion on small boxes
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,720")
    opts.add_argument("--autoplay-policy=no-user-gesture-required")
    opts.add_argument("--mute-audio")
    # *** Force media onto TCP so ss -tin can read TCP_INFO of the CDN sockets. ***
    # --disable-quic stops QUIC negotiation; pair with the feature-disable so the
    # network stack never opens a UDP/QUIC media flow (which has no TCP_INFO).
    opts.add_argument("--disable-quic")
    opts.add_argument("--disable-features=UseDnsHttpsSvcb,AsyncDns")
    opts.add_argument("--enable-logging=stderr")
    opts.add_argument("--log-level=2")
    service = Service(executable_path=CHROMEDRIVER)
    return webdriver.Chrome(service=service, options=opts)


def parse_bitrates(sample):
    """Best-effort bitrate extraction. getStatsForNerds() field names drift across
    player builds; try the common ones, fall back to bandwidth_kbps, else None."""
    sfn = sample.get("sfn") or {}
    video = audio = total = None

    # Some builds expose explicit codec/bitrate strings; many only give bandwidth.
    bw = sfn.get("bandwidth_kbps") or sfn.get("bandwidth")
    try:
        if bw is not None:
            total = float(str(bw).split()[0]) * 1000.0   # kbps -> bps
    except (ValueError, IndexError):
        total = None

    # "optimal_format"/"current" sometimes carry "1280x720@30 / avc1..." — not a bitrate.
    # If the build exposes vfmt/afmt with bitrate we'd parse here; absent, leave None.
    for key in ("video_bitrate", "vbr"):
        if key in sfn:
            try:
                video = float(sfn[key])
            except (TypeError, ValueError):
                pass
    for key in ("audio_bitrate", "abr"):
        if key in sfn:
            try:
                audio = float(sfn[key])
            except (TypeError, ValueError):
                pass
    if total is None and video is not None and audio is not None:
        total = video + audio
    return video, audio, total


def play_one(driver, page_url, video, metrics, sampler):
    """Play a single video for PLAY_SECONDS, polling QoE each second.
    Returns an outcome string for the plays_total counter. Never raises."""
    vid = str(video["id"])
    category = str(video.get("category", "unknown"))
    play_for = int(video.get("play_seconds", PLAY_SECONDS))

    metrics.reset_session_counters(vid)
    sampler.set_video(vid)
    metrics.video_info.labels(vid, category).set(1)

    try:
        driver.get(page_url)
        # wait for the IFrame API to be ready
        deadline = time.time() + 30
        while time.time() < deadline:
            if driver.execute_script("return window.YTQOE && window.YTQOE.ready === true"):
                break
            time.sleep(0.5)
        driver.execute_script("window.YTQOE.load(arguments[0]);", vid)
    except Exception as exc:
        print(f"[{vid}] launch error: {exc}", flush=True)
        metrics.video_info.labels(vid, category).set(0)
        return "error"

    started = False
    buffering_samples = 0
    total_samples = 0
    t_end = time.time() + play_for
    startup_deadline = time.time() + STARTUP_TIMEOUT
    prev_state = None

    while time.time() < t_end:
        time.sleep(POLL_SECONDS)
        try:
            s = driver.execute_script("return window.__ytqoeSample ? window.__ytqoeSample() : null;")
        except Exception as exc:
            print(f"[{vid}] sample error: {exc}", flush=True)
            continue
        if not s:
            continue

        err = s.get("error")
        if err in (2, 5, 100, 101, 150):
            print(f"[{vid}] player error code {err} -> skip", flush=True)
            metrics.video_info.labels(vid, category).set(0)
            return "unavailable"

        state = s.get("state")
        total_samples += 1

        # ---- buffering accounting ----
        if state == BUFFERING:
            buffering_samples += 1
            metrics.buffering_seconds_total.labels(vid).inc(POLL_SECONDS)
            # a fresh transition into BUFFERING after we'd started = a rebuffer
            if prev_state is not None and prev_state != BUFFERING and started:
                metrics.buffering_events_total.labels(vid).inc()
        prev_state = state

        # ---- startup ----
        # ---- picture quality (computed first so startup_seconds is labelled with
        # the quality actually achieved at first frame, not the stale "unknown") ----
        quality = s.get("playback_quality") or "unknown"

        if not started:
            started_at = s.get("started_at")
            requested_at = s.get("requested_at")
            ct = s.get("current_time") or 0
            if started_at and requested_at and ct > 0:
                started = True
                metrics.startup_seconds.labels(vid, quality).set(
                    (started_at - requested_at) / 1000.0)
                metrics.plays_total.labels("ok").inc()
            elif time.time() > startup_deadline:
                print(f"[{vid}] startup timeout ({STARTUP_TIMEOUT}s) -> skip", flush=True)
                metrics.video_info.labels(vid, category).set(0)
                return "timeout"

        height = s.get("video_height")
        if height:
            metrics.resolution_height.labels(vid, quality).set(height)
        metrics.playback_quality.labels(vid, quality).set(
            QUALITY_ORDINAL.get(quality, height or 0))

        # fps + dropped frames from getStatsForNerds / the media element
        sfn = s.get("sfn") or {}
        fps = sfn.get("fps") or sfn.get("framerate")
        if fps:
            try:
                metrics.fps.labels(vid, quality).set(float(str(fps).split()[0]))
            except (ValueError, IndexError):
                pass
        dropped = s.get("dropped_frames")
        if dropped is not None:
            metrics.add_dropped(vid, int(dropped))

        # ---- bitrate ----
        vbr, abr, tbr = parse_bitrates(s)
        if vbr is not None:
            metrics.bitrate_video.labels(vid, quality).set(vbr)
        if abr is not None:
            metrics.bitrate_audio.labels(vid, quality).set(abr)
        if tbr is not None:
            metrics.bitrate_total.labels(vid, quality).set(tbr)

        # ---- buffering ratio (running) ----
        if total_samples:
            metrics.buffering_ratio.labels(vid, quality).set(buffering_samples / total_samples)

        # natural end of a short clip
        if state == ENDED:
            print(f"[{vid}] video ended early", flush=True)
            break

    metrics.video_info.labels(vid, category).set(0)
    return "ok" if started else "error"


def clear_live_gauges(metrics):
    """Between videos, clear the per-(video,quality) live gauges so only the
    currently-playing video holds live series. *_total counters persist."""
    for g in (metrics.resolution_height, metrics.fps, metrics.playback_quality,
              metrics.bitrate_video, metrics.bitrate_audio, metrics.bitrate_total,
              metrics.buffering_ratio, metrics.startup_seconds,
              metrics.tcp_srtt_us, metrics.tcp_cwnd, metrics.tcp_delivery_rate,
              metrics.tcp_sockets):
        try:
            g.clear()
        except Exception:
            pass


def main():
    print("youtube-qoe worker starting", flush=True)
    videos = load_videos()
    page_url = serve_player_page()

    metrics = Metrics(METRICS_PORT)
    metrics.start_http()
    metrics.up.set(0)

    sampler = CdnSampler(metrics, interval=POLL_SECONDS)
    sampler.start()

    driver = None
    idx = 0
    while True:
        video = videos[idx % len(videos)]
        idx += 1
        try:
            if driver is None:
                driver = build_driver()
            metrics.up.set(1)
            outcome = play_one(driver, page_url, video, metrics, sampler)
            print(f"[{video['id']}] outcome={outcome}", flush=True)
            if outcome in ("error", "timeout"):
                # a wedged browser: recycle it so the next video starts clean
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None
        except Exception as exc:
            metrics.up.set(0)
            print(f"loop error on {video.get('id')}: {exc}", flush=True)
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            driver = None
            time.sleep(5)
        finally:
            clear_live_gauges(metrics)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
