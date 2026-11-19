# Create Design: one image with the API, the built UI and kicad-cli (Phase 7).
# Build:  docker build -t create-design .
# The KiCad image is Debian 12 with Python 3.11, so the backend runs on it directly.

# --- 1. Build the React app -------------------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. Runtime: official KiCad 9 image + Python backend --------------------------
FROM kicad/kicad:9.0
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# The backend finds the manual, the KiCad template and the UI relative to /app
# (REPO_ROOT = three levels above backend/app/core/config.py).
COPY backend/ backend/
COPY docs/manual/ docs/manual/
COPY kicad/ kicad/
COPY --from=frontend /build/dist/ frontend/dist/

# Persistent data (SQLite, traces, generated designs) lives in one volume.
ENV DATA_DIR=/data \
    DESIGNS_ROOT=/data/designs \
    KICAD_CLI=kicad-cli \
    PORT=8000
RUN mkdir -p /data && chown -R kicad:kicad /data /app
VOLUME /data
USER kicad

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os,urllib.request as u; u.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/api/health')"
WORKDIR /app/backend
ENTRYPOINT []
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
