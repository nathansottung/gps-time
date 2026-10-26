# GPS Time coordinator (SKELETON). Build: docker build -t gps-time-coordinator:0.1.0 coordinator/
FROM python:3.13-slim

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r /tmp/requirements.txt && rm /tmp/requirements.txt

WORKDIR /app
COPY gps_time_coordinator /app/gps_time_coordinator

# TrueNAS SCALE's apps user and group (568); the config and data datasets belong to it.
USER 568:568
ENV GTC_CONFIG=/config/coordinator.toml PYTHONUNBUFFERED=1
EXPOSE 8090
HEALTHCHECK --interval=60s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/v1/health', timeout=4)"
CMD ["python", "-m", "gps_time_coordinator", "serve"]
