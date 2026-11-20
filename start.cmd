@echo off
rem Clone and run: builds the images and starts the app + mock SAP.
rem Optional: start.cmd --profile ollama   (see compose.yaml)
cd /d "%~dp0"
where docker >nul 2>&1 || (echo Docker Desktop is required: https://docs.docker.com/get-docker/ & exit /b 1)
docker info >nul 2>&1 || (echo Docker is installed but not running. Start Docker Desktop, wait for "Engine running", then run this again. & exit /b 1)
if "%APP_PORT%"=="" (echo Create Design -^> http://localhost:8000  ^(Ctrl+C to stop^)) else (echo Create Design -^> http://localhost:%APP_PORT%)
docker compose %* up --build
