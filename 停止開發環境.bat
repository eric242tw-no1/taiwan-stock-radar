@echo off
chcp 65001 >nul
echo ========================================
echo  台股AI雷達  關閉開發環境
echo ========================================
echo.

echo [1/2] 關閉 App / FastAPI / Next.js / ngrok 視窗...
taskkill /IM taiwan-ai-stock-radar.exe /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq FastAPI Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Next.js Dev Server" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ngrok Tunnel" /F >nul 2>&1
taskkill /IM ngrok.exe /F >nul 2>&1
:: exe 帶起的服務沒有視窗標題，改用埠號清（8000=後端、3002=前端）
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,3002 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo      ^ 程序已終止

echo.
echo [2/2] 完成。
echo.
pause
