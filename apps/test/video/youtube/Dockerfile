# YouTube QoE tester — runs on pi-node2 (Mac mini 2014, Intel x86_64) under Colima.
# Built ON pi-node2 via Colima's Docker (never on the owner's Mac, never on the Pi).
#
# KEY FIX vs the old `vsc` tester: install `chromium` AND `chromium-driver` from the
# SAME Debian apt repo in one `apt-get install`, so the browser and the driver always
# share a major version. The old tester hand-pinned a chromedriver .deb/.zip and broke
# on every Chrome update (version drift). Debian's packages are co-released.
#
# `iproute2` provides `ss` for TCP_INFO sampling of the googlevideo CDN sockets.
# linux/amd64 base (pi-node2 is Intel) — Debian ships chromium for amd64.
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CHROMIUM_BIN=/usr/bin/chromium \
    CHROMEDRIVER=/usr/bin/chromedriver

# chromium + chromium-driver from the same repo (version-matched), ss for TCP_INFO,
# plus the runtime libs/fonts a headless Chromium needs to render.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        iproute2 \
        ca-certificates \
        fonts-liberation \
        fonts-noto-color-emoji \
        libnss3 \
        libxss1 \
        libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY metrics.py tcpinfo.py worker.py player.html videos.yml /app/

# Run as non-root where feasible. Chromium runs with --no-sandbox (set in worker.py),
# which is required for an unprivileged headless container.
RUN useradd --create-home --uid 10001 qoe \
    && chown -R qoe:qoe /app
USER qoe

EXPOSE 9621
ENTRYPOINT ["python", "-u", "worker.py"]
