@echo off
chcp 65001 >nul
echo ========================================
echo  台股AI雷達  關閉開發環境
echo ========================================
echo.

echo [1/3] 關閉 FastAPI / Next.js / ngrok 視窗...
taskkill /FI "WINDOWTITLE eq FastAPI Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Next.js Dev Server" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ngrok Tunnel" /F >nul 2>&1
taskkill /IM ngrok.exe /F >nul 2>&1
echo      ^ 程序已終止

echo.
echo [2/3] 停止 Docker 容器（postgres + redis）...
docker-compose -f "%~dp0docker-compose.yml" stop postgres redis
echo      ^ 容器已停止

echo.
echo [3/3] 完成。
echo       容器資料已保留（volume 未刪除）。
echo.
pause
