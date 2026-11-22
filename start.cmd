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
rem Both ports must be free, or uvicorn fails with "[Errno 10048] ... only one usage of each
rem socket address". Usually an earlier run is still open; offer to stop it (Enter = yes).
call :freeport 8000 "the app" || exit /b 1
call :freeport 8100 "the mock SAP" || exit /b 1
rem Which model will answer? It checks Dahl, Groq and Ollama, suggests one and asks (Enter = suggestion).
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

rem If something listens on port %1, say what it is and ask before stopping it. Waits for the
rem answer; "n" stops start.cmd so nothing fails half-started. Exit code 1 = port still busy.
:freeport
call :portowner %1
if not defined BUSY_PID exit /b 0
echo.
echo Port %1 ^(%~2^) is already in use by %BUSY_NAME% ^(PID %BUSY_PID%^).
echo It is probably an earlier start.cmd that is still running.
if %BUSY_PID% LEQ 4 (
  echo That is a Windows system process and cannot be stopped from here. Free port %1 and run start.cmd again.
  exit /b 1
)
set "ANSWER=y"
set /p "ANSWER=Stop it and continue? [Y/n] "
if /i not "%ANSWER:~0,1%"=="y" (
  echo Not stopped. Close it, or stop PID %BUSY_PID%, then run start.cmd again.
  exit /b 1
)
taskkill /pid %BUSY_PID% /t /f >nul 2>&1
for /l %%i in (1,1,10) do (
  call :portowner %1
  if not defined BUSY_PID (echo   Stopped. Port %1 is free. & exit /b 0)
  ping -n 2 127.0.0.1 >nul
)
echo Port %1 is still in use ^(PID %BUSY_PID%^). Stop it by hand, then run start.cmd again.
exit /b 1

rem Sets BUSY_PID and BUSY_NAME to the process listening on port %1 (both empty if free).
:portowner
set "BUSY_PID="
set "BUSY_NAME="
for /f "tokens=1,2" %%a in ('powershell -NoProfile -Command "$c = @(Get-NetTCPConnection -LocalPort %1 -State Listen -ErrorAction SilentlyContinue)[0]; if ($c) { $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue; '{0} {1}' -f $c.OwningProcess, $p.ProcessName }"') do (
  set "BUSY_PID=%%a"
  set "BUSY_NAME=%%b"
)
if defined BUSY_PID if not defined BUSY_NAME set "BUSY_NAME=an unknown process"
exit /b 0

rem Open the browser once the app answers (waits up to 90 s). Set NO_BROWSER=1 to skip.
:openbrowser
if defined NO_BROWSER exit /b 0
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 90;$i++){try{Invoke-RestMethod http://127.0.0.1:%1/api/health -TimeoutSec 2|Out-Null;Start-Process http://localhost:%1;break}catch{Start-Sleep 1}}"
exit /b 0
