#!/usr/bin/env sh
# Clone and run: builds the images and starts the app + mock SAP.
# Optional: LLM_PROVIDER=ollama ./start.sh --profile ollama   (see compose.yaml)
set -e
cd "$(dirname "$0")"
command -v docker >/dev/null 2>&1 || { echo "Docker is required: https://docs.docker.com/get-docker/"; exit 1; }
echo "Create Design -> http://localhost:${APP_PORT:-8000}  (Ctrl+C to stop)"
docker compose "$@" up --build
