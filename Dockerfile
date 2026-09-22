# ── Micher Server Container ──────────────────────────────────────────────── #
# Runs the bonded receiver (server mode) for accepting multi-link transfers.
#
# Build:  docker build -t micher-server .
# Run:    docker run -p 9191:9191 micher-server
# ────────────────────────────────────────────────────────────────────────── #

FROM python:3.12-slim AS base

LABEL maintainer="micher contributors"
LABEL description="Micher network bonding receiver server"

WORKDIR /app

# Install only runtime deps (no GUI)
COPY pyproject.toml README.md ./
COPY micher/ ./micher/

RUN pip install --no-cache-dir . \
    && rm -rf /root/.cache

EXPOSE 9191

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',9191)); s.close()" || exit 1

ENTRYPOINT ["micher", "receive"]
CMD ["--port", "9191"]
