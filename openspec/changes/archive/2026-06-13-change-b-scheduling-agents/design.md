## Context

The backend uses FastAPI + APScheduler (in-process) + Redis + PostgreSQL. Redis is already in docker-compose. AI scoring and screener run synchronously in API handlers, causing request timeouts under load. There are no scheduled agents for market summaries or anomaly detection. Celery with Redis broker is the standard solution for offloading compute without adding a new broker.

## Goals / Non-Goals

**Goals:**
- Morning Brief generated and pushed at 08:30 Taiwan time, persisted in DB
- Sector Rotation Agent produces weekly rankings queryable via REST
- Market Anomaly Agent runs every 10 min intraday, alerts on anomalies
- Celery workers handle AI scoring / screener / backtest so API handlers return immediately
- APScheduler cron consolidation: all scheduled jobs in one place

**Non-Goals:**
- Frontend UI for sector rotation or anomalies (REST endpoints only, Change C scope)
- Distributed multi-worker Celery setup (single worker is sufficient)
- Replacing APScheduler with Celery Beat (APScheduler stays for lightweight crons)

## Decisions

**D1: Celery broker = Redis (already present)**
Using the existing Redis instance avoids adding a RabbitMQ service. Tradeoff: Redis message persistence is weaker than RabbitMQ, but for AI scoring tasks loss is acceptable — the scheduler will retry next cycle.

**D2: APScheduler stays alongside Celery**
APScheduler handles time-based triggers (cron). Celery handles task execution. APScheduler cron callbacks call `task.delay()` to enqueue rather than executing inline. This keeps the two concerns separate and avoids Celery Beat configuration overhead.

**D3: Morning Brief = Claude API call aggregating market data**
The brief calls existing data endpoints (market summary, screener top picks, alert counts) then sends one Claude API call to produce a prose summary. Stored in `daily_ai_report` with `date UNIQUE` to prevent duplicates.

**D4: Sector Rotation uses existing market data endpoints**
No new data source — pulls from existing `GET /api/market/overview` or direct DB queries for OHLCV. Computes 4/8/13-week returns per GICS sector (11 sectors mapped to TWSE industry codes).

**D5: Market Anomaly Agent is stateless per run**
Each 10-min run fetches current quotes, computes anomaly conditions, and fires Telegram if threshold exceeded. No state stored between runs (no false-positive dedup needed at this stage).

## Risks / Trade-offs

- [Celery worker crash] → APScheduler cron still enqueues tasks; tasks fail silently. Mitigation: Flower monitor at port 5555 exposes worker health; add health-check in docker-compose.
- [Morning Brief Claude API timeout] → Mitigation: wrap in `asyncio.timeout(30)`; on failure log and skip — no partial report stored.
- [Sector data gaps on holidays] → Mitigation: agent checks if market was open before computing; skips on holidays.
- [Redis OOM if tasks back up] → Mitigation: set `CELERY_TASK_SERIALIZER=json` and `task_acks_late=False`; tasks are small JSON payloads.

## Migration Plan

1. Add `daily_ai_report` table via `ALTER TABLE` or new migration script (no existing data to migrate)
2. Add `celery[redis]` and `flower` to `requirements.txt`
3. Deploy new `celery_app.py` and agent files
4. Add `celery-worker` + `flower` services to `docker-compose.yml`
5. Update `backend/main.py` APScheduler jobs
6. Restart: `docker-compose up -d --build`

Rollback: remove celery-worker service, revert main.py scheduler; API endpoints remain functional without worker (tasks enqueue but don't execute).
