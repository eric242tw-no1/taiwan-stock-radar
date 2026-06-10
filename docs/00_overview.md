# Taiwan AI Stock Radar — 00 專案總覽
> 給 Claude Code 的背景文件，每次開新對話先丟這份

## 專案定位
台股專用 AI 投資決策平台，整合 Bloomberg + TradingView + Finviz 風格。
交易風格：波段操作（持股數天到數週），AI 輔助信號，人工最終決策。

## 硬體環境
- 主機：Asus Flow Z13（i9-12900H / RTX 3050 Ti / 16GB RAM，焊死無法升級）
- 外接：硬碟櫃（歷史資料存放）
- 開發工具：Claude Code + VS Code + WSL2 Ubuntu

## 技術堆疊
```
前端：Next.js 15 + TypeScript + TailwindCSS + ShadCN UI
後端：FastAPI + SQLAlchemy + Pydantic
資料庫：PostgreSQL + Redis
資料來源：TWSE + FinMind + Yahoo Finance + 期交所 + TDCC
AI 引擎：Claude API（claude-sonnet-4）
K 線圖：TradingView Lightweight Charts Widget
量化計算：pandas-ta
部署：Docker Compose
通知：Telegram Bot
版控：GitHub
PWA：next-pwa（安卓 APP 打包）
```

## 系統架構
```
使用者瀏覽器 / 安卓 PWA
    ↓
Next.js 15 前端（左側導覽列 + 多頁面）
    ↓
FastAPI 後端（REST API + WebSocket）
    ↓
Redis（即時快取 + Claude API 結果快取）
    ↓
PostgreSQL（所有歷史與預算資料）
    ↓
Data Agents（定時排程）
    ├── 每日 14:30 — TWSE + FinMind + 期交所爬取
    ├── 每日 15:30 — pandas-ta 指標預算
    ├── 每日 16:00 — 宏觀連動係數計算
    └── 每週六    — TDCC 大戶集保更新
```

## 左側導覽列結構
```
🟢 台股AI雷達（Logo）
─────────────────
🏠 市場總覽
📈 個股分析
🔄 選股工作流
💼 持倉追蹤
📊 回測
🔔 警報設定
─────────────────
⚙️ 設定
🌙 主題
```

## 三階段目標
- Phase 1（6-8週）：看盤 + AI 信號，手動下單
- Phase 2（+2個月）：元大 API 半自動下單，手機確認
- Phase 3（+2個月）：Claude Code Agent 全自動下單

## RAM 保護原則
16GB 焊死，所有技術指標在收盤後背景預算完畢存入 DB。
前端 API 只做 SELECT，不做即時運算。
Claude API 結果快取至 Redis，每日只呼叫一次。

## 開源參考專案
- whale-quant：資料爬取 + 因子模型 + 回測框架
- UZI-Skill：AI 評審團規則 + IC 備忘錄 + 多空辯論

## Sprint 規劃
- Sprint 1：環境建置（Docker + DB Schema）
- Sprint 2：Data Agent（爬蟲 + 指標預算）
- Sprint 3：市場總覽頁前端
- Sprint 4：個股分析頁 + AI 串接
- Sprint 5：整合測試 + PWA
- Sprint 6：回測模組
