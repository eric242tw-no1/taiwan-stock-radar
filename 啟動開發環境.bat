@echo off
setlocal

echo ========================================
echo  Taiwan AI Stock Radar - Dev Startup
echo ========================================
echo.

:: ── 0. Check Docker Desktop ─────────────────────────────────────
echo [0/4] Checking Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
    echo       Docker not running. Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo       Waiting for Docker Engine (up to 120s)...
    set /a tries=0
    :wait_docker
    timeout /t 5 /nobreak >nul
    set /a tries+=1
    docker info >nul 2>&1
    if errorlevel 1 (
        if %tries% LSS 24 goto wait_docker
        echo       [WARN] Docker not ready. Skipping Redis container...
        goto skip_docker
    )
    echo       Docker ready.
) else (
    echo       Docker already running.
)

:: ── 1. Start Redis ────────────────────────────────────────────────
echo.
echo [1/4] Starting Redis...
docker-compose -f "%~dp0docker-compose.yml" up redis -d

:: Wait for redis
echo       Waiting for Redis...
set /a rd_tries=0
:wait_redis
docker exec taiwan-stock-radar-redis-1 redis-cli ping >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    set /a rd_tries+=1
    if %rd_tries% LSS 10 goto wait_redis
    echo       [WARN] Redis may not be ready. Continuing...
) else (
    echo       Redis OK
)
goto after_docker

:skip_docker
echo       [SKIP] Redis skipped (Docker not available)

:after_docker

:: ── 2. Start FastAPI Backend ─────────────────────────────────────
echo.
echo [2/4] Starting FastAPI backend (port 8000)...
start "FastAPI Backend" powershell -NoExit -Command ^
  "cd 'C:\Users\ERIC\projects\taiwan-stock-radar\backend'; .\.venv\Scripts\python.exe -m uvicorn main:app --port 8000 --reload"

echo       Waiting for backend...
set /a api_tries=0
:wait_api
timeout /t 3 /nobreak >nul
curl -s http://localhost:8000/api/health >nul 2>&1
if errorlevel 1 (
    set /a api_tries+=1
    if %api_tries% LSS 10 goto wait_api
    echo       [WARN] Backend may not be ready. Continuing...
) else (
    echo       FastAPI OK
)

:: ── 3. Start Next.js Frontend ────────────────────────────────────
echo.
echo [3/4] Starting Next.js frontend (port 3002)...
start "Next.js Dev Server" powershell -NoExit -Command ^
  "cd 'C:\Users\ERIC\projects\taiwan-stock-radar\frontend'; npm run dev -- --hostname 127.0.0.1 -p 3002"

timeout /t 5 /nobreak >nul

:: ── 4. Done ──────────────────────────────────────────────────────
echo.
echo [4/4] All services started!
echo.
echo   Services:
echo   --------------------------------------------------
echo   Frontend   http://localhost:3002
echo   Backend    http://localhost:8000
echo   API Docs   http://localhost:8000/docs
echo   Flower     http://localhost:5555
echo   DB File    backend\data\stockradar.db
echo   --------------------------------------------------
echo.
echo   To stop all services, run: stop-dev.bat
echo.
pause
endlocal
