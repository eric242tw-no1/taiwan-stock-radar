## Why

Change-H 完成後，系統核心功能已完備，但仍有五項使用者體驗缺口：券商串接僅元大（Yuanta）、行動裝置版面破版、選股工作流無法利用新的 K 線形態與主力意圖條件、缺乏財報日曆提醒，以及 Telegram 警報沒有歷史管理介面。本 Change 一次補齊這五項改善。

## What Changes

- **財報日曆**：新增 `/calendar` 頁面，顯示未來 30 天的除息除權、法說會、財報公布日；資料來自 FinMind，每日早上更新
- **通知中心**：新增 `/notifications` 頁面，列出歷史 Telegram 警報紀錄（訊息內容、時間、觸發來源），支援已讀/未讀標記
- **選股進階篩選**：在選股工作流（`/screener`）加入 K 線形態 與 主力意圖 兩個新篩選條件，串接已有的 `candlestick-patterns` 與 `market-maker-intent` 服務
- **行動裝置 RWD 優化**：修正 `/stock`、`/screener`、`/portfolio` 在 < 768px 時的排版問題（溢出、表格、Modal）
- **元大證券 API 整合完善**：補強 `backend/brokers/yuanta.py` 的錯誤處理與模擬/正式模式切換，確保持倉格式正確（股→張），下單失敗有統一錯誤回報

## Capabilities

### New Capabilities
- `earnings-calendar`: 財報/除息/法說日曆，FinMind 資料，每日更新，前端 `/calendar` 頁
- `notification-center`: 警報歷史紀錄，DB 寫入、已讀標記、前端 `/notifications` 頁
- `screener-advanced-filter`: 選股工作流新增 K 線形態 & 主力意圖條件篩選
- `yuanta-api`: 元大 Open API 完整整合，含認證、模擬/正式切換、持倉格式轉換、統一錯誤回報

### Modified Capabilities

## Impact

- **後端**：新增 `routers/calendar.py`、`routers/notifications.py`；修改 `brokers/yuanta.py`（錯誤處理強化）、`utils/telegram.py`（寫入警報紀錄）
- **前端**：新增 `app/calendar/page.tsx`、`app/notifications/page.tsx`；修改 `app/screener/page.tsx`、`app/stock/page.tsx`（RWD）、`app/portfolio/page.tsx`（RWD）、`components/layout/Sidebar.tsx`
- **DB**：新增 `notifications` 表（`schema_sqlite.sql`）
- **依賴**：`shioaji` Python 套件（`requirements.txt`）
