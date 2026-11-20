@echo off
setlocal
rem Clone and run Create Design.
rem   start.cmd                run locally (default): Python + Node on this PC, no Docker
rem   start.cmd local          same as above
rem   start.cmd docker         run in Docker; extra arguments go to docker compose,
rem                            e.g. start.cmd docker --profile ollama
cd /d "%~dp0"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=local"
if /i "%MODE%"=="local" goto local
if /i "%MODE%"=="docker" goto docker
echo Usage: start.cmd [local^|docker]
exit /b 1

:local
where python >nul 2>&1 || (echo Python 3.11+ is required: https://www.python.org/downloads/ & exit /b 1)
where npm >nul 2>&1 || (echo Node 20+ is required: https://nodejs.org/ & exit /b 1)
if not exist backend\.venv\Scripts\python.exe (
  echo Setting up the backend ^(first run only^) ...
  python -m venv backend\.venv || exit /b 1
  backend\.venv\Scripts\python -m pip install -q -r backend\requirements.txt || exit /b 1
)
if not exist sap-mock\.venv\Scripts\python.exe (
  echo Setting up the mock SAP ^(first run only^) ...
  python -m venv sap-mock\.venv || exit /b 1
  sap-mock\.venv\Scripts\python -m pip install -q -r sap-mock\requirements.txt || exit /b 1
)
if not exist frontend\dist\index.html (
  echo Building the web app ^(first run only^) ...
  pushd frontend
  call npm ci --no-audit --no-fund || exit /b 1
  call npm run build || exit /b 1
  popd
)
rem Without a .env, pin the mock SAP's date so the demo numbers stay in 2026 (decision 0007).
if not exist .env if not defined SAP_TODAY set "SAP_TODAY=2026-11-17"
where kicad-cli >nul 2>&1 || findstr /b /c:"KICAD_CLI=" .env >nul 2>&1 || echo Note: PDF export needs KiCad 9. Install it, or set KICAD_CLI in .env.
rem Which model will answer? It checks Groq and Ollama, suggests one and asks (Enter = suggestion).
rem Run in this console (not in for /f) so the question can read the keyboard.
echo.
set "LLM_CHOICE=%TEMP%\hl-create-design-llm.txt"
del "%LLM_CHOICE%" >nul 2>&1
pushd backend
.venv\Scripts\python -m app.cli llm-check --out "%LLM_CHOICE%" >nul
popd
if exist "%LLM_CHOICE%" set /p LLM_PROVIDER=<"%LLM_CHOICE%"
del "%LLM_CHOICE%" >nul 2>&1
echo.
echo Starting the mock SAP on http://localhost:8100 ...
start "SAP mock (Create Design)" /min cmd /c "cd /d sap-mock && .venv\Scripts\python -m uvicorn app.main:app --port 8100"
ping -n 4 127.0.0.1 >nul
echo Create Design -^> http://localhost:8000  ^(Ctrl+C to stop^)
call :openbrowser 8000
cd backend
.venv\Scripts\python -m uvicorn app.main:app --port 8000
cd ..
taskkill /f /t /fi "WINDOWTITLE eq SAP mock (Create Design)*" >nul 2>&1
exit /b 0

:docker
where docker >nul 2>&1 || (echo Docker Desktop is required: https://docs.docker.com/get-docker/ & exit /b 1)
docker info >nul 2>&1 || (echo Docker is installed but not running. Start Docker Desktop, wait for "Engine running", then run this again. & exit /b 1)
set "EXTRA="
shift
:collect
if "%~1"=="" goto run
set "EXTRA=%EXTRA% %~1"
shift
goto collect
:run
set "PORT=%APP_PORT%"
if "%PORT%"=="" set "PORT=8000"
echo Create Design -^> http://localhost:%PORT%  ^(Ctrl+C to stop^)
call :openbrowser %PORT%
docker compose%EXTRA% up --build
exit /b %errorlevel%

rem Open the browser once the app answers (waits up to 90 s). Set NO_BROWSER=1 to skip.
:openbrowser
if defined NO_BROWSER exit /b 0
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 90;$i++){try{Invoke-RestMethod http://127.0.0.1:%1/api/health -TimeoutSec 2|Out-Null;Start-Process http://localhost:%1;break}catch{Start-Sleep 1}}"
exit /b 0
