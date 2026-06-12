# stock_analysis backend — FastAPI + sklearn/pandas ML engine.
# Built natively on pi-node1 (linux/arm64); all deps ship aarch64 manylinux wheels (no compile).
# Build context: ~/apps/stock-analysis/backend on the Pi (synced by scripts/sync-apps.sh).
# SQLite (data/stocklab.db) lives on a bind mount at /app/data; ANTHROPIC_API_KEY comes from
# compose environment (Keychain -> deploy/.env -> compose), never baked into the image.

FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8765
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765", "--log-level", "info"]
