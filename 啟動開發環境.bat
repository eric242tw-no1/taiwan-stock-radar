@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo  台股AI雷達  開發環境啟動
echo ========================================
echo.

:: ── 0. 確認 Docker Desktop 已執行 ──────────────────────────────
echo [0/5] 檢查 Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
    echo      ^ Docker 未執行，正在啟動 Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo      ^ 等待 Docker 就緒（最多 60 秒）...
    set /a tries=0
    :wait_docker
    timeout /t 5 /nobreak >nul
    set /a tries+=1
    docker info >nul 2>&1
    if errorlevel 1 (
        if %tries% LSS 12 goto wait_docker
        echo      [WARN] Docker 未就緒，跳過 DB 容器，繼續啟動其他服務...
        goto skip_docker
    )
    echo      ^ Docker 已就緒
) else (
    echo      ^ Docker 已在執行
)

:: ── 1. 啟動 PostgreSQL + Redis ────────────────────────────────
echo.
echo [1/5] 啟動 PostgreSQL + Redis 容器...
docker-compose -f "%~dp0docker-compose.yml" up postgres redis -d

:: 等待 postgres 健康
echo      ^ 等待 PostgreSQL 就緒...
set /a db_tries=0
:wait_pg
timeout /t 3 /nobreak >nul
docker exec taiwan-stock-radar-postgres-1 pg_isready -U admin -d stockradar >nul 2>&1
if errorlevel 1 (
    set /a db_tries+=1
    if %db_tries% LSS 15 goto wait_pg
    echo      [WARN] PostgreSQL 可能未就緒，繼續...
) else (
    echo      ^ PostgreSQL OK
)

:: 等待 redis 健康
echo      ^ 等待 Redis 就緒...
set /a rd_tries=0
:wait_redis
docker exec taiwan-stock-radar-redis-1 redis-cli ping >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    set /a rd_tries+=1
    if %rd_tries% LSS 10 goto wait_redis
    echo      [WARN] Redis 可能未就緒，繼續...
) else (
    echo      ^ Redis OK
)
goto after_docker

:skip_docker
echo      [SKIP] 略過 PostgreSQL / Redis（Docker 未啟動）

:after_docker

:: ── 2. 啟動 FastAPI 後端 ──────────────────────────────────────
echo.
echo [2/5] 啟動 FastAPI 後端（port 8000）...
start "FastAPI Backend" powershell -NoExit -Command ^
  "cd 'C:\Users\ERIC\projects\taiwan-stock-radar\backend'; .\.venv\Scripts\python.exe -m uvicorn main:app --port 8000 --reload"

echo      ^ 等待後端就緒...
set /a api_tries=0
:wait_api
timeout /t 3 /nobreak >nul
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    set /a api_tries+=1
    if %api_tries% LSS 10 goto wait_api
    echo      [WARN] 後端可能尚未就緒，繼續...
) else (
    echo      ^ FastAPI OK
)

:: ── 3. 啟動 Next.js 前端 ──────────────────────────────────────
echo.
echo [3/5] 啟動 Next.js 前端（port 3002）...
start "Next.js Dev Server" powershell -NoExit -Command ^
  "cd 'C:\Users\ERIC\projects\taiwan-stock-radar\frontend'; npm run dev -- --hostname 127.0.0.1 -p 3002"

timeout /t 5 /nobreak >nul

:: ── 4. 啟動 ngrok 隧道 ────────────────────────────────────────
echo.
echo [4/5] 啟動 ngrok 隧道（port 3002）...
start "ngrok Tunnel" powershell -NoExit -Command "ngrok http 127.0.0.1:3002"

timeout /t 2 /nobreak >nul

:: ── 5. 完成 ──────────────────────────────────────────────────
echo.
echo [5/5] 全部啟動完成！
echo.
echo   服務清單：
echo   --------------------------------------------------
echo   前端    http://localhost:3002
echo   後端    http://localhost:8000
echo   API文件 http://localhost:8000/docs
echo   ngrok   https://exact-pupil-snowfield.ngrok-free.dev
echo   --------------------------------------------------
echo.
echo   如要停止所有服務，請執行：停止開發環境.bat
echo.
pause
endlocal
