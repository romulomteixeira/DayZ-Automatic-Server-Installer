FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl lib32gcc-s1 && rm -rf /var/lib/apt/lists/*

RUN useradd -m appuser
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# SteamCMD para Linux
RUN mkdir -p /opt/steamcmd && \
    curl -sSL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz | tar -xz -C /opt/steamcmd

COPY backend /app/backend
COPY config /app/config
COPY manager /app/manager

ENV PYTHONPATH=/app/backend
ENV PORT=8000
ENV PATH="/opt/steamcmd:${PATH}"

CMD ["python", "/app/backend/app.py"]
