# 台股AI雷達 — 專案開發計劃

## 專案架構

- **前端**：Next.js 14 (App Router) + Recharts + React Flow + Tailwind
- **後端**：FastAPI + APScheduler + Celery + Redis + PostgreSQL
- **AI 層**：DeepSeek API（OpenAI 相容）/ Gemini 備援
- **部署**：Docker Compose（本地開發）+ Nginx + Let's Encrypt + GitHub Actions

---

## 開發階段總覽

### ✅ Phase 0 — Backlog 基礎建設
> `taiwan-stock-radar-backlog`（38/39，剩 1 項手動 Telegram 測試）

- ANTHROPIC_API_KEY、Telegram Bot 接入
- AI 快取：Redis `ai:score:{symbol}:{date}`，TTL 至隔日 09:00
- Telegram 警報：alert_agent → 手機推播
- TDCC 大戶集保（FinMind 週資料）
- 台美連動：30/60/90 日 Pearson r，每日 15:15 更新
- StopLossGuard：元大券商輪詢備援
- 回測引擎：MA黃金交叉 / RSI 超買超賣 + equity curve
- 選股工作流、警報設定頁、PWA

---

### ✅ Phase 1 — Change B：排程代理人
> `change-b-scheduling-agents`（已 archive 2026-06-13）

- Celery + Redis Worker 基礎設施（docker-compose）
- MorningBriefAgent（DeepSeek）08:30 排程
- MarketAnomalyAgent（RSI/成交量/籌碼異常偵測）09:05 排程
- SectorRotationAgent（產業輪動分析）
- 任務監控頁 `/tasks`

---

### ✅ Phase 2 — Change D：Webhook + RiskManager
> `change-d-webhook-riskmanager`（已 archive 2026-06-13）

- TradingView Webhook（HMAC 驗證 + Redis dedup 60s）
- RiskManager 三道風控（倉位/回撤/相關性）
- DevilsAdvocate Agent（反向質疑進場）
- StopLossGuard Layer2 輪詢備援
- YuantaBroker 元大券商 API 整合
- `/tradingview-legacy` 相容端點

---

### ✅ Phase 3 — Change A：AI 決策核心 + Factor Engine
> `change-a-ai-factor-engine`（42/44，剩 2 項手動測試）

- **Factor Engine**：RSI/MACD/KD/MA/ATR/Bias + 籌碼 FactorBundle
- **Multi-Agent Orchestrator**：6 Agent 並行+串行
  - 技術/籌碼/總經（並行）→ 風控/執行/魔鬼代言（串行）
- **UZI 評審團**：動能派/價值派/風控派（0.35/0.35/0.30）
- **IC 備忘錄**：Bull/Base/Bear 三情境 + 期望值，DB 快取
- **多空辯論**：BullAgent → BearAgent → ArbiterAgent（asyncio.gather 並行）
- **策略版本化**：strategy_versions 表，動態 prompt

---

### ✅ Phase 4 — Change C：前端 UX + 分析工具
> `change-c-frontend-ux`（58/65，剩 7 項手動測試）

- DB：trade_journal、workflow_definitions 兩張新表
- 後端：workflow / journal / analytics / ATR stop / SSE signals
- **工作流編輯器** `/workflow`：React Flow 節點面板
- **交易日誌** `/journal`：CRUD + 情緒 BarChart + 分頁統計
- **策略分析** `/analytics`：Sharpe + 多策略權益曲線比較
- **ATR 停損計算器**：Redis TTL 300s + Modal
- **部位計算器**：純前端，嵌入持倉頁
- **即時訊號流**：Redis Pub/Sub → SSE → useSignalStream
- Sidebar：新增 🔧工作流 / 📝日誌 / 📉分析

---

### ✅ Phase 5 — Change E：AI 前端整合
> `change-e-ai-frontend`（已 archive 2026-06-13）

- `/stock` 頁面新增三個 AI Tab（UZI 評審 / IC 備忘錄 / 多空辯論）
- UZI Tab：POST `/api/analysis/uzi/{symbol}`，三位評審評分卡
- IC 備忘錄 Tab：GET `/api/analysis/ic-memo/{symbol}`，Bull/Base/Bear 情境卡
- 多空辯論 Tab：POST `/api/analysis/debate/{symbol}`，辯論流程面板
- 新增 `/strategy` 策略版本管理頁面
- Next.js proxy timeout 調整至 120s
- 全面切換為 DeepSeek API（移除 Anthropic 依賴）

---

### ✅ Phase 6 — Change F：生產部署
> `change-f-production-deploy`（完成，VPS 驗證項目 N/A — 本地桌面架構）

- Health Check 端點：`GET /api/health`（db + redis 狀態）
- Docker Compose 生產配置：restart always + 資源限制 + healthcheck
- Next.js standalone 模式 + 生產 Dockerfile
- Nginx 反向代理 + Let's Encrypt SSL 自動更新
- PostgreSQL 每日備份腳本（保留 7 天）
- GitHub Actions CI/CD：lint → build → push GHCR → SSH deploy
- 部署說明文件 `DEPLOY.md`

---

## 核心資料流

```
TradingView Webhook
  → HMAC驗證 → Redis dedup → RiskManager → DevilsAdvocate
  → 下單(YuantaBroker) → Redis publish → SSE → 前端badge

APScheduler 08:30
  → MorningBriefAgent(DeepSeek) → daily_ai_report

POST /api/analysis/debate/{symbol}
  → FactorBundle → BullAgent ─┐
                               ├→ asyncio.gather → ArbiterAgent
                 BearAgent ────┘

GET /api/analysis/ic-memo/{symbol}
  → DB cache → DeepSeek → ic_memo table

GET /api/risk/atr-stop/{symbol}
  → daily_price → ATR計算 → Redis TTL 300s → 前端Modal
```
