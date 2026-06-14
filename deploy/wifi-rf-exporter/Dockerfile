# Built ON pi-node1 (arm64) by docker compose. Needs `iw` (scan/survey) + `ip` (iproute2).
# Runs host-networked + privileged so it can reach the wlan0 radio (see docker-compose.yml).
FROM python:3.12-alpine
RUN apk add --no-cache iw iproute2
WORKDIR /app
RUN pip install --no-cache-dir prometheus_client==0.21.0
COPY rf_exporter.py /app/
EXPOSE 9620
ENTRYPOINT ["python", "-u", "rf_exporter.py"]
