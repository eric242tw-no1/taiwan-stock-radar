# Taiwan AI Stock Radar — Phase 2 Implementation Plan

> Branch: main | Date: 2026-06-13
> Scope: 4 OpenSpec Changes (A/B/C/D) — AI Core, Scheduling, Frontend UX, Webhook

---

## Context

Taiwan AI Stock Radar is a Next.js 15 + FastAPI + PostgreSQL + Redis + Claude API platform for Taiwan stock analysis. Sprint 1–6 are complete (39/40 tasks done). This plan covers the next major phase: upgrading the AI decision engine, scheduling infrastructure, frontend UX, and TradingView webhook integration.

**Success criteria:**
- Win rate: 55–62%
- Profit factor: 2:1
- Daily automation: 100% execution rate
- Morning Brief delivered by 08:30 daily

---

## Change A — AI決策核心 + Factor Engine

### Problem
The current AI engine (`backend/agents/ai_engine.py`) is a single-model rule-based scorer. It cannot support multi-perspective consensus, UZI-style IC memos, or strategy versioning. The 6-Agent architecture is planned but not wired.

### Scope

**A1. Factor Engine** (`backend/app/factor_engine/`)
- `technical.py`: pandas-ta unified technical factors (RSI, MACD, ATR, Bollinger, KD, OBV, CMF, VWAP, Stochastic)
- `chips.py`: Taiwan-specific chip factors — 三大法人 (FinMind `TaiwanStockInstitutionalInvestorsBuySell`), 融資融券 (`TaiwanStockMarginPurchaseShortSale`), TDCC weekly
- `output_formatter.py`: Unified dict format fed to all 6 Agents

**A2. 6-Agent Multi-Agent Engine** (`backend/agents/multi_agent_engine.py`)
- Factor Scanner → Technical Analyst → Chip Analyst → Risk Manager → Devil's Advocate → Final Arbiter
- Sequential execution, each Agent reads prior outputs
- `agent_results` DB table (symbol, date, agent_name, score, reasoning, JSON)

**A3. UZI-Skill Integration**
- 10-reviewer panel (Bull/Neutral/Bear × 3 perspectives)
- IC三情景備忘錄: Bull case / Base case / Bear case structured output
- 多空辯論循環: Devil's Advocate challenges Final Arbiter before commit

**A4. Strategy Versioning**
- `strategy_versions` DB table (id, name, config_json, is_active, created_at)
- `activate_strategy_version()` stored procedure (atomically swaps active version)
- `GET /api/strategy/versions`, `POST /api/strategy/versions`, `POST /api/strategy/versions/{id}/activate`

### Dependencies
- Existing: `backend/agents/ai_engine.py`, `backend/agents/screener_agent.py`
- New DB tables: `factor_scan_daily`, `agent_results`, `strategy_versions`
- New packages: `pandas-ta`, `vectorbt` (optional)

### Estimated effort
- Factor Engine: 3 days
- Multi-Agent Engine: 4 days
- UZI Integration: 2 days
- Strategy Versioning: 2 days
- **Total: ~11 days**

---

## Change B — 排程強化 + Morning Brief + New Agents

### Problem
Current scheduling (`backend/main.py` APScheduler) runs basic market data fetches and alert checks. There's no consolidated Morning Brief, no sector rotation analysis, no Celery for heavy async tasks.

### Scope

**B1. Morning Brief** (daily 08:30)
- `GET /api/reports/morning-brief`
- Content: market sentiment, top movers, watchlist alerts, AI top picks, macro indicators
- `daily_ai_report` DB table (date, report_json, sent_at)
- Telegram push at 08:30 weekdays

**B2. Sector Rotation Agent** (`backend/agents/sector_rotation_agent.py`)
- Weekly sector performance ranking (11 GICS sectors)
- Momentum score per sector using 4/8/13 week returns
- Output: sector heat map data → `GET /api/market/sector-rotation`

**B3. Market Anomaly Agent** (`backend/agents/market_anomaly_agent.py`)
- Detect: gap up/down >3%, volume spike >3× 20-day avg, price limit hits
- Runs every 10 minutes during market hours (09:00–13:30 TWN)
- Triggers Telegram alert if anomaly score > threshold

**B4. Celery Async Pipeline**
- `backend/celery_app.py` + Redis broker
- Move heavy tasks to Celery: AI scoring, screener runs, backtest jobs
- `docker-compose.yml` add `celery-worker` service
- Flower monitoring at port 5555

**B5. APScheduler Jobs Consolidation**
- 08:30: Morning Brief generation + Telegram
- 09:05: Market open — chip data fetch, anomaly agent start
- 13:35: Market close — daily factor scan, AI scoring batch
- 15:15: Correlation service (existing)
- 22:00: Sat — TDCC weekly fetch (existing)

### Dependencies
- Existing: `backend/main.py`, `backend/utils/telegram.py`, `backend/services/correlation_service.py`
- New packages: `celery[redis]`, `flower`
- New DB tables: `daily_ai_report`, `sector_performance`

### Estimated effort
- Morning Brief: 2 days
- Sector Rotation Agent: 2 days
- Market Anomaly Agent: 2 days
- Celery pipeline: 3 days
- **Total: ~9 days**

---

## Change C — Frontend UX

### Problem
Key frontend pages (watchlist, industry) use hardcoded demo data. There's no visual workflow editor, no trade journal, no analytics contribution charts, and no WebSocket real-time signal feed.

### Scope

**C1. React Flow Workflow Editor** (`frontend/app/workflow/page.tsx`)
- Library: `@xyflow/react`
- Node types: DataSourceNode (blue), FactorNode (purple), AgentNode (green), FilterNode (orange), SignalNode/NotifyNode (red)
- Backend: `WorkflowRunner` with topological sort, SSE streaming
- API: `POST /api/workflow/run`, `POST /api/workflow/save`, `GET /api/workflow/list`
- DB: `workflows` table (UUID, name, definition JSONB, created_at)

**C2. Watchlist & Industry Real Data**
- `frontend/app/watchlist/page.tsx`: replace demo with `GET /api/portfolio/watchlist`
- `frontend/app/industry/page.tsx`: replace demo with `GET /api/market/sector-rotation`

**C3. Analytics Page** (`frontend/app/analytics/page.tsx`)
- Agent contribution chart (bar chart per agent, win rate contribution)
- Strategy performance comparison (equity curves)
- Daily P&L calendar heatmap

**C4. WebSocket Real-Time Signal Feed**
- `backend/routers/ws.py`: Redis Pub/Sub → WebSocket bridge
- Frontend: signal ticker in navbar, live alert badge
- `WSManager` class managing connections

**C5. ATR Stop-Loss Calculator UI**
- Panel in stock detail page
- Input: symbol, entry price, ATR multiplier (default 2×)
- Output: stop-loss price, position size (fixed risk %), risk/reward ratio

### Dependencies
- Existing: `frontend/app/`, `backend/routers/`
- New packages: `@xyflow/react`, `socket.io-client`

### Estimated effort
- React Flow editor: 4 days
- Real data wiring: 1 day
- Analytics page: 2 days
- WebSocket: 2 days
- ATR calculator: 1 day
- **Total: ~10 days**

---

## Change D — TradingView Webhook + RiskManager + Yuanta Portfolio

### Problem
Current webhook (`backend/routers/webhook.py`) is action-based (buy/sell commands), which breaks on signal loss. Current RiskManager is coupled inside stop_loss_guard. Yuanta portfolio page shows demo data.

### Scope

**D1. State-Based TradingView Webhook**
- Payload: `{symbol, target_position, strategy_id, price_close, timestamp}`
- Logic: receive `target_position` → query actual position → compute diff → execute
- Redis dedup key: `tv_signal:{strategy_id}:{symbol}:{timestamp}` with 60s TTL
- Devil's Advocate review before execution (AI confirms signal validity)
- `tv_signals` DB table (signal log with dedup_key, diff, executed_at)
- `POST /api/webhook/tradingview` (replaces existing)

**D2. Standalone RiskManager** (`backend/services/risk_manager.py`)
- `RiskDecision` dataclass: action, position_size, stop_loss, take_profit, confidence
- Methods: `check_position_size()`, `check_max_drawdown()`, `check_correlation_risk()`
- Decoupled from `stop_loss_guard.py` — can be called from any agent or webhook
- `GET /api/risk/assessment/{symbol}` endpoint

**D3. Yuanta Portfolio Real Data** (`frontend/app/portfolio/page.tsx`)
- Connect to `YuantaBroker` simulation API
- Show real-time positions, P&L, margin usage
- WebSocket updates every 30s
- `GET /api/portfolio/positions`, `GET /api/portfolio/summary`

### Dependencies
- Existing: `backend/routers/webhook.py`, `backend/agents/stop_loss_guard.py`, `backend/services/yuanta_broker.py`
- New DB tables: `tv_signals`, `orders`, `account_snapshots`

### Estimated effort
- State-based webhook: 3 days
- RiskManager refactor: 2 days
- Portfolio real data: 2 days
- **Total: ~7 days**

---

## Overall Scope Summary

| Change | Focus | Days |
|--------|-------|------|
| A — AI Core | Factor Engine + 6-Agent + UZI + Strategy Versions | 11 |
| B — Scheduling | Morning Brief + Sector Agent + Celery | 9 |
| C — Frontend | React Flow + Analytics + WebSocket + ATR | 10 |
| D — Webhook | State-based TV + RiskManager + Yuanta | 7 |
| **Total** | | **~37 days** |

## Sequencing Recommendation
1. Change A (AI Core) — unblocks everything AI-related
2. Change D (Webhook + RiskManager) — risk-critical, can be parallelized with A
3. Change B (Scheduling) — depends on Change A for Morning Brief content
4. Change C (Frontend) — depends on B for sector rotation data, D for portfolio

## Autoplan Review Decisions (2026-06-13)

### Sequencing Change (AUTO)
Execute order: **D → B → A → C** (real portfolio validation first)

### Architecture Fixes (AUTO — Critical)
- **6-Agent pipeline**: Factor/Technical/Chip run in parallel; Risk→Devil's Advocate→Arbiter sequential. Per-agent hard timeout 30s. Cache partial results so re-run resumes.
- **Webhook HMAC auth**: Shared secret embedded in TV alert message. Reject unsigned requests before Redis/order logic.
- **APScheduler + Celery**: APScheduler for time triggers only; Celery for task execution only. No overlap.

### DB Fixes (AUTO)
- `daily_ai_report`: unique constraint on `(report_date)` to prevent double-write
- `agent_results`: add `strategy_version_id` column; partition by month; 90-day TTL
- `factor_scan_daily`: partition by month
- `strategy_versions`: use `valid_from` timestamp, not boolean flag
- `tv_signals`: log every deduped signal with `status=deduped`

### Frontend Standards (AUTO)
- **Taiwan color convention**: RED = 漲 (gain), GREEN = 跌 (loss) — enforced in all charts/tables
- **React Flow save**: Explicit Save button + dirty-state indicator (●)
- **WebSocket**: Auto-reconnect 3s backoff; connection-state chip in navbar; alert badge max 99 + dismiss-all
- **ATR defaults**: Period=14, Multiplier=2.0, adjusted OHLCV, show price + % both

### API Standards (AUTO)
- All new routers must declare `response_model=` for OpenAPI schema
- WebSocket message schema: `{type: "signal"|"alert"|"ping", payload: {...}, ts: ISO8601}`
- `GET /api/tasks/{task_id}` for async job polling

### Cost Control (AUTO)
- Claude API batch scan: $20/day ceiling; skip stocks already scored today (Redis cache check first)
- Backtest baseline report required before Change A begins

### Estimate Revision (AUTO)
- Change A: 11 → 7 days (existing services leverage: indicator_service, finmind_fetcher, sector_fetcher)
- Total: 37 → **32 days**

---

## Not in Scope (deferred)
- Alpha101 factor library (Phase 3)
- VectorBT integration (Phase 3)
- Sentiment analysis / FinBERT (Phase 3)
- Put/Call ratio data (Phase 3)
- Mobile native app (Tauri shell exists, not full-featured)
