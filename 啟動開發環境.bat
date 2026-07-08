@echo off
setlocal

echo ========================================
echo  Taiwan AI Stock Radar - Dev Startup
echo ========================================
echo.

:: ── 1. Start FastAPI Backend ─────────────────────────────────────
echo [1/3] Starting FastAPI backend (port 8000)...
start "FastAPI Backend" powershell -NoExit -Command ^
  "cd 'C:\Users\ERIC\projects\taiwan-stock-radar\backend'; .\.venv\Scripts\python.exe -m uvicorn main:app --port 8000 --reload"

:: ── 2. Start Next.js Frontend ────────────────────────────────────
echo [2/3] Starting Next.js frontend (port 3002)...
start "Next.js Dev Server" powershell -NoExit -Command ^
  "cd 'C:\Users\ERIC\projects\taiwan-stock-radar\frontend'; npm run dev -- --hostname 127.0.0.1 -p 3002"

echo.
echo       Waiting for backend...
set /a api_tries=0
:wait_api
timeout /t 3 /nobreak >nul
curl -s http://localhost:8000/api/health >nul 2>&1
if errorlevel 1 (
    set /a api_tries+=1
    if %api_tries% LSS 20 goto wait_api
    echo       [WARN] Backend may not be ready. Continuing...
) else (
    echo       FastAPI OK
)

echo       Waiting for frontend...
set /a fe_tries=0
:wait_fe
timeout /t 3 /nobreak >nul
curl -s http://localhost:3002 >nul 2>&1
if errorlevel 1 (
    set /a fe_tries+=1
    if %fe_tries% LSS 20 goto wait_fe
    echo       [WARN] Frontend may not be ready. Continuing...
) else (
    echo       Next.js OK
)

:: ── 3. Open desktop window ───────────────────────────────────────
echo.
echo [3/3] Opening app window...
set "TAURI_EXE=%~dp0frontend\src-tauri\target\release\taiwan-ai-stock-radar.exe"
if exist "%TAURI_EXE%" (
    start "" "%TAURI_EXE%"
) else (
    echo       Tauri exe not found, opening browser instead...
    start "" http://localhost:3002
)

echo.
echo All services started!
echo.
echo   Services:
echo   --------------------------------------------------
echo   Frontend   http://localhost:3002
echo   Backend    http://localhost:8000
echo   API Docs   http://localhost:8000/docs
echo   DB File    backend\data\stockradar.db
echo   --------------------------------------------------
echo.
echo   To stop, run: 停止開發環境.bat
echo.
pause
endlocal
