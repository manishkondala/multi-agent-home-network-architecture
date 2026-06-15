"""Prometheus metrics for the YouTube QoE tester.

All series are prefixed `youtube_qoe_*`. Per-playback gauges carry {video_id,
quality}; the TCP series carry {video_id} only (the googlevideo CDN peer is an
implementation detail and would explode cardinality). Counters are monotonic so
Grafana can `rate()`/`increase()` them.

We keep the live (gauge) cardinality bounded by clearing the per-(video,quality)
gauges between videos: only the currently-playing video should hold live series,
while the *_total counters accumulate across the whole run.
"""
from prometheus_client import Counter, Gauge, start_http_server


class Metrics:
    def __init__(self, port: int):
        self.port = port

        # ---- health / liveness ----
        self.up = Gauge("youtube_qoe_up", "1 while the QoE worker loop is alive")
        self.video_info = Gauge(
            "youtube_qoe_video_playing",
            "1 for the video_id currently playing (0 after it ends)",
            ["video_id", "category"],
        )
        self.plays_total = Counter(
            "youtube_qoe_plays_total",
            "Playback sessions started, by outcome",
            ["outcome"],   # ok | error | unavailable | timeout
        )

        # ---- startup / buffering ----
        self.startup_seconds = Gauge(
            "youtube_qoe_startup_seconds",
            "Initial load time: load() -> first PLAYING with currentTime>0",
            ["video_id", "quality"],
        )
        self.buffering_events_total = Counter(
            "youtube_qoe_buffering_events_total",
            "Rebuffering events (transitions into the BUFFERING state mid-play)",
            ["video_id"],
        )
        self.buffering_ratio = Gauge(
            "youtube_qoe_buffering_ratio",
            "Fraction of sampled seconds spent buffering during the session",
            ["video_id", "quality"],
        )
        self.buffering_seconds_total = Counter(
            "youtube_qoe_buffering_seconds_total",
            "Cumulative seconds observed in the BUFFERING state",
            ["video_id"],
        )

        # ---- picture quality ----
        self.resolution_height = Gauge(
            "youtube_qoe_resolution_height",
            "Decoded video height in pixels (from the <video> element)",
            ["video_id", "quality"],
        )
        self.fps = Gauge(
            "youtube_qoe_fps",
            "Reported frames per second",
            ["video_id", "quality"],
        )
        self.dropped_frames_total = Counter(
            "youtube_qoe_dropped_frames_total",
            "Dropped video frames (monotonic, summed across resets)",
            ["video_id"],
        )
        self.playback_quality = Gauge(
            "youtube_qoe_playback_quality",
            "Current playback quality as an ordinal (see QUALITY_ORDINAL)",
            ["video_id", "quality"],
        )

        # ---- bitrate ----
        self.bitrate_video = Gauge(
            "youtube_qoe_bitrate_video_bps", "Video bitrate (bits/s)", ["video_id", "quality"])
        self.bitrate_audio = Gauge(
            "youtube_qoe_bitrate_audio_bps", "Audio bitrate (bits/s)", ["video_id", "quality"])
        self.bitrate_total = Gauge(
            "youtube_qoe_bitrate_total_bps", "Total bitrate (bits/s)", ["video_id", "quality"])

        # ---- TCP_INFO (googlevideo CDN sockets, via ss -tin) ----
        self.tcp_srtt_us = Gauge(
            "youtube_qoe_tcp_srtt_us", "Smoothed RTT to the CDN (microseconds)", ["video_id"])
        self.tcp_cwnd = Gauge(
            "youtube_qoe_tcp_cwnd", "Congestion window (segments)", ["video_id"])
        self.tcp_retrans_total = Counter(
            "youtube_qoe_tcp_retrans_total", "Cumulative TCP retransmits to the CDN", ["video_id"])
        self.tcp_delivery_rate = Gauge(
            "youtube_qoe_tcp_delivery_rate_bps", "Kernel delivery_rate to the CDN (bits/s)", ["video_id"])
        self.tcp_sockets = Gauge(
            "youtube_qoe_tcp_sockets", "Active googlevideo TCP sockets observed", ["video_id"])
        self.tcp_sampler_up = Gauge(
            "youtube_qoe_tcp_sampler_up", "1 if the last ss capture succeeded")

        # internal: last-seen retrans/dropped so Counters get the delta, not the absolute
        self._last_retrans: dict[str, int] = {}
        self._last_dropped: dict[str, int] = {}

    def start_http(self) -> None:
        start_http_server(self.port)

    # ---- helpers that turn absolute kernel/player counters into Counter deltas ----
    def add_dropped(self, video_id: str, absolute: int) -> None:
        prev = self._last_dropped.get(video_id, 0)
        if absolute >= prev:
            self.dropped_frames_total.labels(video_id).inc(absolute - prev)
        else:                      # the <video> element reset (new media) -> count fresh
            self.dropped_frames_total.labels(video_id).inc(absolute)
        self._last_dropped[video_id] = absolute

    def add_retrans(self, video_id: str, absolute: int) -> None:
        prev = self._last_retrans.get(video_id, 0)
        if absolute >= prev:
            self.tcp_retrans_total.labels(video_id).inc(absolute - prev)
        else:
            self.tcp_retrans_total.labels(video_id).inc(absolute)
        self._last_retrans[video_id] = absolute

    def reset_session_counters(self, video_id: str) -> None:
        """Forget per-video absolute baselines at the start of a new play."""
        self._last_dropped.pop(video_id, None)
        self._last_retrans.pop(video_id, None)
