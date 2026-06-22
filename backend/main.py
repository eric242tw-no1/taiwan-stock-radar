import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()  # 讀取 backend/.env

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import market, stock, portfolio, alerts, analysis, backtest, screener, webhook, stock_pool, stream, reports, tasks as tasks_router, health as health_router
import routers.risk as risk_router
import routers.strategies as strategies_router
import routers.workflow as workflow_router
import routers.journal as journal_router
import routers.analytics as analytics_router
import routers.audit as audit_router
import routers.calendar as calendar_router
import routers.notifications as notifications_router
from services.data_fetcher import fetch_us_indices
from services.twse_fetcher import fetch_tw_market
from services.taifex_fetcher import fetch_futures_and_fx
from services.finmind_fetcher import fetch_chip_summary
from services.indicator_service import load_cache_from_db, calculate_and_store
from services.sector_fetcher import fetch_sectors
from services.gov_fund_fetcher import fetch_gov_funds
from services.buffett_fetcher import fetch_buffett
from services.tdcc_fetcher import ensure_table as ensure_tdcc_table, fetch_all_pool_tdcc
from services.correlation_service import calculate_and_store as calc_correlation
from agents.self_audit import SelfAudit
from agents.alert_agent import run_check_alerts_sync
from brokers.yuanta import YuantaBroker
from brokers.sinopac import SinopacBroker
from agents.stop_loss_guard import StopLossGuard


def _init_db() -> None:
    """Run schema_sqlite.sql on startup to create all tables (idempotent)."""
    from db import get_conn
    schema_path = os.path.join(os.path.dirname(__file__), "schema_sqlite.sql")
    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()
    conn = get_conn()
    try:
        conn.executescript(sql)
        conn.commit()
        logger.info("SQLite schema initialised")
    finally:
        conn.close()

_self_audit = SelfAudit()


def _create_broker():
    broker_type = os.getenv("BROKER", "yuanta").lower()
    if broker_type == "sinopac":
        try:
            return SinopacBroker()
        except Exception as e:
            logger.warning("SinopacBroker 初始化失敗，fallback 至 YuantaBroker: %s", e)
    return YuantaBroker()


# StopLossGuard 全域單例（broker 由 BROKER 環境變數決定）
_broker = _create_broker()
stop_loss_guard = StopLossGuard(_broker)


def _tw_market_and_alerts() -> None:
    """每 10 秒：更新台股市場資料 + 警報條件檢查。"""
    fetch_tw_market()
    try:
        from routers.alerts import get_watchlist
        watchlist = get_watchlist()
        if watchlist:
            run_check_alerts_sync(watchlist)
    except Exception as exc:
        logger.warning("Alert check error: %s", exc)


def _fetch_earnings_calendar_sync() -> None:
    """08:00 每日：取得財報/除息/除權日曆。"""
    from services.earnings_calendar import fetch_and_store_calendar
    try:
        fetch_and_store_calendar()
    except Exception as exc:
        logger.warning("earnings_calendar fetch error: %s", exc)


def _cleanup_notifications_sync() -> None:
    """每週日 02:00：清理舊通知，保留最近 1000 筆。"""
    from db import get_conn
    try:
        conn = get_conn()
        total = conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
        if total > 1000:
            conn.execute(
                "DELETE FROM notifications WHERE id NOT IN "
                "(SELECT id FROM notifications ORDER BY id DESC LIMIT 1000)"
            )
            conn.commit()
            logger.info("notifications cleanup: removed %d rows", total - 1000)
        conn.close()
    except Exception as exc:
        logger.warning("notifications cleanup error: %s", exc)


def _morning_brief_sync() -> None:
    """08:30 weekdays — generate morning brief via Claude API."""
    import asyncio
    from agents.morning_brief_agent import generate_morning_brief
    asyncio.run(generate_morning_brief())


def _chip_and_anomaly_sync() -> None:
    """09:05 weekdays — fetch chip data then scan anomalies."""
    import asyncio
    from agents.market_anomaly_agent import scan_anomalies
    try:
        fetch_chip_summary()
    except Exception as exc:
        logger.warning("chip fetch at 09:05: %s", exc)
    asyncio.run(scan_anomalies())


def _scan_anomalies_sync() -> None:
    """09:10–13:20 every 10 min weekdays — anomaly scan."""
    import asyncio
    from agents.market_anomaly_agent import scan_anomalies
    asyncio.run(scan_anomalies())


def _factor_scan_and_batch_score() -> None:
    """13:35 weekdays — factor scan + AI batch scoring via Celery + account snapshot."""
    from celery_tasks import score_symbol
    from services.stock_pool_service import get_pool
    try:
        symbols = [s["symbol"] for s in get_pool()]
        for sym in symbols:
            score_symbol.delay(sym)
        logger.info("factor_scan: enqueued %d symbols for AI scoring", len(symbols))
    except Exception as exc:
        logger.warning("factor_scan: %s", exc)
    _take_account_snapshot()


def _take_account_snapshot() -> None:
    """13:35 每日帳戶快照 — 收盤後寫入 account_snapshots 表。"""
    import asyncio
    from datetime import date
    from db import get_conn

    async def _snapshot():
        try:
            balance = await _broker.get_balance()
        except Exception as exc:
            logger.warning("account snapshot: broker error — %s", exc)
            return

        total_value  = float(balance.get("total_value", 0) or 0)
        cash         = float(balance.get("cash", 0) or 0)
        daily_pnl    = float(balance.get("daily_pnl", 0) or 0)
        margin_usage = float(balance.get("margin_usage", 0) or 0)

        sql = """
        INSERT INTO account_snapshots (date, total_value, cash, daily_pnl, margin_usage)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (date) DO UPDATE SET
            total_value=excluded.total_value, cash=excluded.cash,
            daily_pnl=excluded.daily_pnl, margin_usage=excluded.margin_usage
        """
        try:
            conn = get_conn()
            conn.execute(sql, (str(date.today()), total_value, cash, daily_pnl, margin_usage))
            conn.commit()
            conn.close()
            logger.info("account snapshot saved: total_value=%.0f", total_value)
        except Exception as exc:
            logger.error("account snapshot DB error: %s", exc)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_snapshot())
        else:
            asyncio.run(_snapshot())
    except Exception:
        asyncio.run(_snapshot())


def _stop_loss_polling_sync() -> None:
    """每分鐘：StopLossGuard Layer2 輪詢（同步包裝）。"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(stop_loss_guard.polling_monitor())
        else:
            asyncio.run(stop_loss_guard.polling_monitor())
    except Exception:
        asyncio.run(stop_loss_guard.polling_monitor())


def _run_daily_audit_sync() -> None:
    """15:30 weekdays：AI 自審計（同步包裝）。"""
    from services.audit import run_daily_audit
    try:
        run_daily_audit()
    except Exception as exc:
        logger.warning("daily audit error: %s", exc)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Taipei")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB setup — single SQLite schema init replaces all per-service ensure_* calls
    _init_db()
    ensure_tdcc_table()
    load_cache_from_db()

    # warm up caches on startup
    for fn, name in [(fetch_us_indices, "us_indices"), (fetch_tw_market, "tw_market"), (fetch_futures_and_fx, "futures_fx"), (fetch_chip_summary, "chip"), (fetch_sectors, "sectors"), (fetch_gov_funds, "gov_funds"), (fetch_buffett, "buffett")]:
        try:
            fn()
        except Exception as exc:
            logger.warning("Startup warm-up failed [%s]: %s", name, exc)

    # US indices: every 5 minutes
    scheduler.add_job(fetch_us_indices, "interval", minutes=5, id="us_indices_refresh")
    # TW market: every 10 seconds + alert check
    scheduler.add_job(
        _tw_market_and_alerts, "interval", seconds=10, id="tw_market_refresh",
    )
    scheduler.add_job(
        fetch_futures_and_fx, "interval", minutes=1, id="futures_fx_refresh",
    )
    # FinMind 三大法人：收盤後 14:35 觸發，平日執行
    scheduler.add_job(
        fetch_chip_summary, "cron",
        hour=14, minute=35, day_of_week="mon-fri", id="chip_refresh",
    )
    # 技術指標 + daily_price：收盤後 15:05 計算（等資料落地），平日執行
    scheduler.add_job(
        calculate_and_store, "cron",
        hour=15, minute=5, day_of_week="mon-fri", id="indicator_refresh",
    )
    # 產業指數 + 八大官股：收盤後 15:10 更新
    scheduler.add_job(
        fetch_sectors, "cron",
        hour=15, minute=10, day_of_week="mon-fri", id="sectors_refresh",
    )
    scheduler.add_job(
        fetch_gov_funds, "cron",
        hour=15, minute=15, day_of_week="mon-fri", id="gov_funds_refresh",
    )
    # Self Audit：每日 16:30 執行六大稽核
    scheduler.add_job(
        _self_audit.run, "cron",
        hour=16, minute=30, day_of_week="mon-fri", id="self_audit",
    )
    # 台美連動：收盤後 15:15 計算
    scheduler.add_job(
        calc_correlation, "cron",
        hour=15, minute=15, day_of_week="mon-fri", id="correlation_refresh",
    )
    # TDCC 大戶集保：每週六 10:00 更新
    scheduler.add_job(
        fetch_all_pool_tdcc, "cron",
        day_of_week="sat", hour=10, minute=0, id="tdcc_refresh",
    )
    # StopLossGuard Layer2：每分鐘輪詢（sync wrapper）
    scheduler.add_job(
        _stop_loss_polling_sync, "interval", minutes=1, id="stop_loss_polling",
    )
    # AI Self Audit：每日 15:30 比對前日收盤
    scheduler.add_job(
        _run_daily_audit_sync, "cron",
        hour=15, minute=30, day_of_week="mon-fri", id="ai_self_audit",
        misfire_grace_time=300,
    )
    # 帳戶快照：由 _factor_scan_and_batch_score 在 13:35 呼叫（Change B）

    # Change I: 財報日曆 — 08:00 每日
    scheduler.add_job(
        _fetch_earnings_calendar_sync, "cron",
        hour=8, minute=0, id="earnings_calendar_refresh",
        misfire_grace_time=300,
    )
    # Change I: 通知清理 — 每週日 02:00
    scheduler.add_job(
        _cleanup_notifications_sync, "cron",
        day_of_week="sun", hour=2, minute=0, id="notifications_cleanup",
    )
    # Change B: Morning Brief — 08:30 週一～週五
    scheduler.add_job(
        _morning_brief_sync, "cron",
        hour=8, minute=30, day_of_week="mon-fri", id="morning_brief",
        misfire_grace_time=300,
    )
    # Change B: 09:05 Chip fetch + 首次異常掃描
    scheduler.add_job(
        _chip_and_anomaly_sync, "cron",
        hour=9, minute=5, day_of_week="mon-fri", id="chip_and_anomaly_open",
        misfire_grace_time=300,
    )
    # Change B: 09:10–13:20 每 10 分鐘異常掃描
    scheduler.add_job(
        _scan_anomalies_sync, "cron",
        hour="9-13", minute="10,20,30,40,50", day_of_week="mon-fri", id="anomaly_intraday",
        misfire_grace_time=300,
    )
    # Change B: 13:35 Factor scan + AI batch scoring + account snapshot
    scheduler.add_job(
        _factor_scan_and_batch_score, "cron",
        hour=13, minute=35, day_of_week="mon-fri", id="factor_scan_and_snapshot",
        misfire_grace_time=300,
    )
    # Apply misfire_grace_time=300 to existing jobs
    for job_id in ["chip_refresh", "indicator_refresh", "sectors_refresh", "gov_funds_refresh",
                   "self_audit", "correlation_refresh", "tdcc_refresh"]:
        try:
            scheduler.modify_job(job_id, misfire_grace_time=300)
        except Exception:
            pass
    scheduler.start()
    logger.info(
        "APScheduler started — us:5min  tw:10s  futures_fx:1min  "
        "morning_brief:08:30  chip+anomaly:09:05  anomaly:09:10-13:20×10min  "
        "factor+snapshot:13:35  chip:14:35  indicators:15:05  sectors:15:10  "
        "gov:15:15  corr:15:15  audit:16:30  tdcc:sat10:00  stoploss:1min"
    )

    # Broker 連線（YUANTA_SIMULATION=false 時才真正連線）
    broker_type = os.getenv("BROKER", "yuanta").lower()
    simulation = os.getenv("YUANTA_SIMULATION", "true").lower() == "true"
    if broker_type == "yuanta" and not simulation:
        try:
            await _broker.connect()
        except Exception as exc:
            logger.warning("YuantaBroker connect 失敗（非致命，繼續啟動）: %s", exc)

    # Telegram Bot polling（asyncio background task）
    from utils.telegram_bot import run_polling as _tg_run_polling
    _tg_task = asyncio.create_task(_tg_run_polling())

    yield

    _tg_task.cancel()
    try:
        await _tg_task
    except asyncio.CancelledError:
        pass
    scheduler.shutdown(wait=False)
    if broker_type == "yuanta" and not simulation:
        try:
            await _broker.disconnect()
        except Exception as exc:
            logger.warning("YuantaBroker disconnect 例外: %s", exc)


app = FastAPI(
    title="Taiwan AI Stock Radar API",
    description="台股 AI 投資決策平台後端",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3002",
        "http://frontend:3000",
        "https://exact-pupil-snowfield.ngrok-free.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router.router, prefix="/api")
app.include_router(market.router)
app.include_router(stock.router)
app.include_router(portfolio.router)
app.include_router(alerts.router)
app.include_router(analysis.router)
app.include_router(backtest.router)
app.include_router(screener.router)
app.include_router(webhook.router)
app.include_router(stock_pool.router)
app.include_router(stream.router)
app.include_router(risk_router.router)
app.include_router(reports.router)
app.include_router(tasks_router.router)
app.include_router(strategies_router.router)
app.include_router(workflow_router.router, prefix="/api/workflow")
app.include_router(journal_router.router, prefix="/api/journal")
app.include_router(analytics_router.router, prefix="/api/analytics")
app.include_router(audit_router.router)
app.include_router(calendar_router.router)
app.include_router(notifications_router.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "Taiwan AI Stock Radar API v0.2"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
