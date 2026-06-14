# Built ON pi-node1 (arm64) via docker compose — never pulled, never built on the Mac.
FROM python:3.12-alpine
WORKDIR /app
RUN pip install --no-cache-dir prometheus_client==0.21.0 PyYAML==6.0.2
COPY exporter.py services.yml /app/
EXPOSE 9618
ENTRYPOINT ["python", "-u", "exporter.py"]
