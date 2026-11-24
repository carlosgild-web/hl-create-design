#!/usr/bin/env sh
# Clone and run Create Design.
#   ./start.sh                run locally (default): Python + Node on this machine, no Docker
#   ./start.sh local          same as above
#   ./start.sh docker [args]  run in Docker; args go to docker compose (e.g. --profile ollama)
set -e
cd "$(dirname "$0")"
mode="${1:-local}"

# Open the browser once the app answers (waits up to 90 s). Set NO_BROWSER=1 to skip.
open_browser() {
  [ -n "${NO_BROWSER:-}" ] && return 0
  command -v curl >/dev/null 2>&1 || return 0
  (
    for _ in $(seq 1 90); do
      if curl -fs "http://127.0.0.1:$1/api/health" >/dev/null 2>&1; then
        (xdg-open "http://localhost:$1" || open "http://localhost:$1") >/dev/null 2>&1
        break
      fi
      sleep 1
    done
  ) &
}

# The PID listening on TCP port $1, or nothing (lsof on macOS/Linux, else ss on Linux).
port_owner() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | head -n 1
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnpH "sport = :$1" 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -n 1
  fi
}

# Port $1 must be free, or uvicorn fails with "address already in use". Usually an earlier
# run is still open: name it and ask before stopping it (Enter = yes; decision 0017 item 24).
free_port() {
  pid="$(port_owner "$1")"
  [ -z "$pid" ] && return 0
  name="$(ps -p "$pid" -o comm= 2>/dev/null || echo "an unknown process")"
  echo
  echo "Port $1 ($2) is already in use by $name (PID $pid)."
  echo "It is probably an earlier ./start.sh that is still running."
  if [ ! -t 0 ]; then
    echo "No terminal to ask on, so nothing was stopped. Stop PID $pid, then run ./start.sh again."
    return 1
  fi
  printf "Stop it and continue? [Y/n] "
  read -r answer || answer=n
  case "$answer" in
    ""|y|Y|yes|YES) ;;
    *) echo "Not stopped. Close it, or stop PID $pid, then run ./start.sh again."; return 1 ;;
  esac
  kill "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [ -z "$(port_owner "$1")" ] && { echo "  Stopped. Port $1 is free."; return 0; }
    sleep 1
  done
  echo "Port $1 is still in use (PID $pid). Stop it by hand, then run ./start.sh again."
  return 1
}

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
    free_port 8000 "the app" || exit 1
    free_port 8100 "the mock SAP" || exit 1
    # Which model will answer? It checks Dahl, Groq and Ollama, suggests one and asks (Enter = the
    # suggestion). Questions go to stderr and read the terminal; only the choice is captured.
    echo
    provider="$(cd backend && .venv/bin/python -m app.cli llm-check)" || provider=""
    [ -n "$provider" ] && export LLM_PROVIDER="$provider"
    echo
    echo "Starting the mock SAP on http://localhost:8100 ..."
    (cd sap-mock && exec .venv/bin/python -m uvicorn app.main:app --port 8100) &
    sap_pid=$!
    trap 'kill "$sap_pid" 2>/dev/null' EXIT INT TERM
    sleep 3
    echo "Create Design -> http://localhost:8000  (Ctrl+C to stop)"
    open_browser 8000
    cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000
    ;;
  docker)
    shift
    command -v docker >/dev/null 2>&1 || { echo "Docker is required: https://docs.docker.com/get-docker/"; exit 1; }
    docker info >/dev/null 2>&1 || { echo "Docker is installed but not running. Start Docker, then run this again."; exit 1; }
    echo "Create Design -> http://localhost:${APP_PORT:-8000}  (Ctrl+C to stop)"
    open_browser "${APP_PORT:-8000}"
    docker compose "$@" up --build
    ;;
  *)
    echo "Usage: ./start.sh [local|docker]"
    exit 1
    ;;
esac
