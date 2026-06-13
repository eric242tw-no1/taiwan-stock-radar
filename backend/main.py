import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()  # 讀取 backend/.env

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import market, stock, portfolio, alerts, analysis, backtest, screener, webhook, stock_pool, stream
import routers.risk as risk_router
from services.data_fetcher import fetch_us_indices
from services.twse_fetcher import fetch_tw_market
from services.taifex_fetcher import fetch_futures_and_fx
from services.finmind_fetcher import fetch_chip_summary
from services.indicator_service import ensure_table, load_cache_from_db, calculate_and_store
from services.stock_pool_service import ensure_table as ensure_pool_table
from services.portfolio_service import ensure_table as ensure_portfolio_table
from services.sector_fetcher import fetch_sectors
from services.gov_fund_fetcher import fetch_gov_funds
from services.buffett_fetcher import fetch_buffett
from services.tdcc_fetcher import ensure_table as ensure_tdcc_table, fetch_all_pool_tdcc
from services.correlation_service import ensure_table as ensure_macro_table, calculate_and_store as calc_correlation
from services.webhook_tables import ensure_tables as ensure_webhook_tables
from agents.self_audit import SelfAudit
from agents.alert_agent import run_check_alerts_sync
from brokers.yuanta import YuantaBroker
from agents.stop_loss_guard import StopLossGuard

_self_audit = SelfAudit()

# StopLossGuard 全域單例（simulation=true by default via env）
_broker = YuantaBroker()
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


def _take_account_snapshot() -> None:
    """13:35 每日帳戶快照 — 收盤後寫入 account_snapshots 表。"""
    import asyncio, os, psycopg2
    from datetime import date

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
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (date) DO UPDATE
            SET total_value=EXCLUDED.total_value, cash=EXCLUDED.cash,
                daily_pnl=EXCLUDED.daily_pnl, margin_usage=EXCLUDED.margin_usage
        """
        try:
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "postgres"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                dbname=os.getenv("POSTGRES_DB", "stockradar"),
                user=os.getenv("POSTGRES_USER", "admin"),
                password=os.getenv("POSTGRES_PASSWORD", "stockradar_pass"),
            )
            with conn, conn.cursor() as cur:
                cur.execute(sql, (date.today(), total_value, cash, daily_pnl, margin_usage))
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Taipei")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB setup
    ensure_pool_table()
    ensure_portfolio_table()
    ensure_table()
    ensure_tdcc_table()
    ensure_macro_table()
    ensure_webhook_tables()
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
    # 帳戶快照：收盤後 13:35 寫入 account_snapshots（Change D）
    scheduler.add_job(
        _take_account_snapshot, "cron",
        hour=13, minute=35, day_of_week="mon-fri", id="account_snapshot",
    )
    scheduler.start()
    logger.info("APScheduler started — us:5min  tw:10s  futures_fx:1min  chip:14:35  indicators:15:05  sectors:15:10  gov:15:15  corr:15:15  audit:16:30  tdcc:sat10:00  stoploss:1min  snapshot:13:35")

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Taiwan AI Stock Radar API",
    description="台股 AI 投資決策平台後端",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:3001",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001",
        "http://frontend:3000",
        "https://exact-pupil-snowfield.ngrok-free.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/")
async def root():
    return {"status": "ok", "service": "Taiwan AI Stock Radar API v0.2"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
