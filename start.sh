#!/usr/bin/env sh
# Clone and run Create Design.
#   ./start.sh                run locally (default): Python + Node on this machine, no Docker
#   ./start.sh local          same as above
#   ./start.sh docker [args]  run in Docker; args go to docker compose (e.g. --profile ollama)
set -e
cd "$(dirname "$0")"
mode="${1:-local}"

case "$mode" in
  local)
    command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ is required: https://www.python.org/downloads/"; exit 1; }
    command -v npm >/dev/null 2>&1 || { echo "Node 20+ is required: https://nodejs.org/"; exit 1; }
    if [ ! -x backend/.venv/bin/python ]; then
      echo "Setting up the backend (first run only) ..."
      python3 -m venv backend/.venv
      backend/.venv/bin/pip install -q -r backend/requirements.txt
    fi
    if [ ! -x sap-mock/.venv/bin/python ]; then
      echo "Setting up the mock SAP (first run only) ..."
      python3 -m venv sap-mock/.venv
      sap-mock/.venv/bin/pip install -q -r sap-mock/requirements.txt
    fi
    if [ ! -f frontend/dist/index.html ]; then
      echo "Building the web app (first run only) ..."
      (cd frontend && npm ci --no-audit --no-fund && npm run build)
    fi
    # Without a .env, pin the mock SAP's date so the demo numbers stay in 2026 (decision 0007).
    [ -f .env ] || export SAP_TODAY="${SAP_TODAY:-2026-11-17}"
    command -v kicad-cli >/dev/null 2>&1 || grep -q '^KICAD_CLI=' .env 2>/dev/null \
      || echo "Note: PDF export needs KiCad 9. Install it, or set KICAD_CLI in .env."
    echo "Starting the mock SAP on http://localhost:8100 ..."
    (cd sap-mock && exec .venv/bin/python -m uvicorn app.main:app --port 8100) &
    sap_pid=$!
    trap 'kill "$sap_pid" 2>/dev/null' EXIT INT TERM
    sleep 3
    echo "Create Design -> http://localhost:8000  (Ctrl+C to stop)"
    cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000
    ;;
  docker)
    shift
    command -v docker >/dev/null 2>&1 || { echo "Docker is required: https://docs.docker.com/get-docker/"; exit 1; }
    docker info >/dev/null 2>&1 || { echo "Docker is installed but not running. Start Docker, then run this again."; exit 1; }
    echo "Create Design -> http://localhost:${APP_PORT:-8000}  (Ctrl+C to stop)"
    docker compose "$@" up --build
    ;;
  *)
    echo "Usage: ./start.sh [local|docker]"
    exit 1
    ;;
esac
