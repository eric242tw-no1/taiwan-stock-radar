@echo off
chcp 65001 >nul
echo ========================================
echo  台股AI雷達 開發環境啟動
echo ========================================

:: ── 1. 確保 PostgreSQL 容器在跑 ──────────────────────────────
echo [1/4] 檢查 PostgreSQL 容器...
docker inspect taiwan-stock-radar-postgres-1 --format "{{.State.Running}}" 2>nul | findstr "true" >nul
if errorlevel 1 (
    echo      → 啟動 postgres 容器...
    docker-compose -f "%~dp0docker-compose.yml" up postgres -d
    echo      → 等待 DB 就緒...
    timeout /t 6 /nobreak >nul
) else (
    echo      → 已在執行，跳過
)

:: ── 2. 啟動 FastAPI 後端 ──────────────────────────────────────
echo [2/4] 啟動 FastAPI 後端（port 8000）...
start "FastAPI Backend" powershell -NoExit -Command ^
  "cd 'C:\Users\ERIC\projects\taiwan-stock-radar\backend'; .\.venv\Scripts\python.exe -m uvicorn main:app --port 8000 --reload"

timeout /t 4 /nobreak >nul

:: ── 3. 啟動 Next.js 前端 ──────────────────────────────────────
echo [3/4] 啟動 Next.js 前端（port 3001）...
start "Next.js Dev Server" powershell -NoExit -Command ^
  "cd 'C:\Users\ERIC\projects\taiwan-stock-radar\frontend'; npm run dev -- --hostname 127.0.0.1 -p 3001"

timeout /t 3 /nobreak >nul

:: ── 4. 啟動 ngrok ─────────────────────────────────────────────
echo [4/4] 啟動 ngrok 隧道...
start "ngrok Tunnel" powershell -NoExit -Command "ngrok http 127.0.0.1:3001"

echo.
echo ✅ 全部啟動完成
echo    前端：http://localhost:3001
echo    後端：http://localhost:8000
echo    手機：https://exact-pupil-snowfield.ngrok-free.dev
echo.
pause
