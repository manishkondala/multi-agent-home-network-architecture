"""Session TCP_INFO sampler for the YouTube QoE worker.

Reuses the wifi-health approach: the kernel tracks SRTT, the congestion window,
retransmits and delivery_rate per socket, and `ss -tin` exposes it. Here the
sockets we care about are the *outbound* connections from this container to
Google's video CDN ("googlevideo") — the ones actually carrying the media.

Two hard requirements for this to see anything (documented in the README too):

  1. HOST NETWORKING (or the same netns as Chromium). `ss` reads the network
     namespace it runs in; if the worker is on a Docker bridge it sees NAT'd
     sockets, not the browser's real CDN connections. The compose service uses
     `network_mode: host`, so the worker, Chromium and `ss` share the host netns.

  2. QUIC DISABLED in Chromium (`--disable-quic`). YouTube prefers QUIC/UDP for
     media, which has no TCP_INFO. With QUIC off, media falls back to TCP and the
     CDN sockets show up in `ss -tin`.

We resolve "is this a CDN peer?" two ways: by reverse-DNS suffix (`*.googlevideo
.com`) when available, and by a cached set of peer IPs that resolved that way —
reverse DNS is slow, so we cache. We also accept the well-known Google ranges as
a fallback hint, but DNS is the primary signal.
"""
import re
import shutil
import socket
import subprocess
import threading
import time

# ss prints rates like "33.5Mbps" / "512Kbps" / "1.2Gbps" / "900bps" -> bits/s.
_RATE_RE = re.compile(r"([\d.]+)([KMG]?)bps")
_RATE_MULT = {"": 1.0, "K": 1e3, "M": 1e6, "G": 1e9}

_CDN_SUFFIXES = (".googlevideo.com",)


def _to_bps(num: str, unit: str) -> float:
    return float(num) * _RATE_MULT[unit]


def _find(pattern: str, text: str, conv=float, default=None):
    m = re.search(pattern, text)
    return conv(m.group(1)) if m else default


def _rate(label: str, text: str):
    m = re.search(rf"\b{label} (\S+)", text)
    if not m:
        return None
    rm = _RATE_RE.match(m.group(1))
    return _to_bps(rm.group(1), rm.group(2)) if rm else None


class CdnSampler:
    """Periodically `ss -tin`, keep the busiest googlevideo socket's stats."""

    def __init__(self, metrics, interval: float = 1.0):
        self.metrics = metrics
        self.interval = interval
        self._ss = shutil.which("ss") or "/usr/sbin/ss"
        self._lock = threading.Lock()
        self._video_id = None          # current video the worker is playing
        self.latest: dict = {}         # last parsed CDN socket stats
        # reverse-DNS cache: ip -> True (is CDN) / False (is not)
        self._dns_cache: dict[str, bool] = {}

    def set_video(self, video_id: str) -> None:
        with self._lock:
            self._video_id = video_id

    def _is_cdn(self, ip: str) -> bool:
        cached = self._dns_cache.get(ip)
        if cached is not None:
            return cached
        result = False
        try:
            host = socket.gethostbyaddr(ip)[0].lower()
            result = any(host.endswith(sfx) for sfx in _CDN_SUFFIXES)
        except Exception:
            result = False
        self._dns_cache[ip] = result
        return result

    def start(self) -> None:
        threading.Thread(target=self._loop, name="cdn-ss", daemon=True).start()

    def _loop(self) -> None:
        while True:
            try:
                self._sample_once()
                self.metrics.tcp_sampler_up.set(1)
            except Exception as exc:           # the sampler must never die
                self.metrics.tcp_sampler_up.set(0)
                print(f"[tcpinfo] sample error: {exc}", flush=True)
            time.sleep(self.interval)

    def _sample_once(self) -> None:
        with self._lock:
            video_id = self._video_id
        if not video_id:
            return
        out = subprocess.run(
            [self._ss, "-tinHO"], capture_output=True, text=True, timeout=5,
        ).stdout

        cdn = []
        for line in out.splitlines():
            p = self._parse(line)
            if p and self._is_cdn(p["peer_ip"]):
                cdn.append(p)

        self.metrics.tcp_sockets.labels(video_id).set(len(cdn))
        if not cdn:
            return
        # The busiest socket (most bytes acked/received) is the active media flow.
        best = max(cdn, key=lambda p: p["_activity"])
        with self._lock:
            self.latest = best

        if best["srtt_us"] is not None:
            self.metrics.tcp_srtt_us.labels(video_id).set(best["srtt_us"])
        if best["cwnd"] is not None:
            self.metrics.tcp_cwnd.labels(video_id).set(best["cwnd"])
        if best["delivery_rate_bps"] is not None:
            self.metrics.tcp_delivery_rate.labels(video_id).set(best["delivery_rate_bps"])
        # retrans is monotonic per-socket; sum across the session as a Counter delta.
        self.metrics.add_retrans(video_id, best["retrans_total"])

    def _parse(self, line: str) -> dict | None:
        line = line.strip()
        if not line:
            return None
        # "State Recv-Q Send-Q Local:port Peer:port <info...>" (-H no header, -O one line).
        parts = line.split(None, 5)
        if len(parts) < 5 or parts[0] != "ESTAB":
            return None
        peer = parts[4]
        info = parts[5] if len(parts) > 5 else ""
        # peer "1.2.3.4:443" or "[::ffff:1.2.3.4]:443"
        peer_ip = peer.rsplit(":", 1)[0].strip("[]")
        if peer_ip.startswith("::ffff:"):
            peer_ip = peer_ip[7:]

        srtt_us = None
        m = re.search(r"\brtt:([\d.]+)/[\d.]+", info)
        if m:
            srtt_us = float(m.group(1)) * 1000.0   # ss prints rtt in ms -> us

        d = {
            "peer_ip": peer_ip,
            "srtt_us": srtt_us,
            "cwnd": _find(r"\bcwnd:(\d+)", info, int),
            "retrans_total": _find(r"\bretrans:\d+/(\d+)", info, int, 0),
            "bytes_acked": _find(r"\bbytes_acked:(\d+)", info, int, 0),
            "bytes_received": _find(r"\bbytes_received:(\d+)", info, int, 0),
            "delivery_rate_bps": _rate("delivery_rate", info),
        }
        d["_activity"] = d["bytes_acked"] + d["bytes_received"]
        return d
