## Why

The system currently lacks scheduled automation: no daily market brief, no sector rotation tracking, no anomaly detection, and AI scoring/screener tasks block the API request thread. Change B adds these time-driven agents and moves heavy computation to Celery workers so the API remains responsive.

## What Changes

- Add `GET /api/reports/morning-brief` endpoint + daily 08:30 Telegram push
- Add `backend/agents/sector_rotation_agent.py` with weekly sector momentum scores
- Add `GET /api/market/sector-rotation` endpoint
- Add `backend/agents/market_anomaly_agent.py` for intraday anomaly detection (gap >3%, volume >3×, limit-up/down)
- Add `backend/celery_app.py` + Celery tasks for AI scoring, screener, backtest
- Add `celery-worker` service + Flower monitor to `docker-compose.yml`
- Consolidate APScheduler jobs in `backend/main.py`: 08:30 brief, 09:05 open, 13:35 close, existing 15:15 correlation, Sat TDCC
- Add `daily_ai_report` DB table (date UNIQUE, report_json, sent_at)

## Capabilities

### New Capabilities

- `morning-brief`: Daily 08:30 AI-generated market summary pushed via Telegram and queryable via REST
- `sector-rotation`: Weekly sector performance ranking with 4/8/13-week momentum scores
- `market-anomaly`: Intraday anomaly scanner (gap, volume spike, limit moves) with Telegram alerts
- `celery-pipeline`: Async task queue for CPU-heavy operations (AI scoring, screener, backtest)

### Modified Capabilities

- `scheduler`: Existing APScheduler setup in main.py gains 3 new cron jobs and proper lifecycle management

## Impact

- **New files**: `backend/agents/sector_rotation_agent.py`, `backend/agents/market_anomaly_agent.py`, `backend/celery_app.py`, `backend/routers/reports.py`
- **Modified files**: `backend/main.py` (APScheduler jobs), `docker-compose.yml` (celery-worker, flower), `backend/schema.sql` (daily_ai_report table)
- **Dependencies added**: `celery[redis]`, `flower`
- **Redis**: already in docker-compose, now also serves as Celery broker
- **No breaking API changes** — all new endpoints, existing endpoints unchanged
