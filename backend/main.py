import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()  # 讀取 backend/.env

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import market, stock, portfolio, alerts, analysis, backtest, screener, webhook, stock_pool, stream
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
from agents.self_audit import SelfAudit

_self_audit = SelfAudit()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="Asia/Taipei")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB setup
    ensure_pool_table()
    ensure_portfolio_table()
    ensure_table()
    load_cache_from_db()

    # warm up caches on startup
    for fn, name in [(fetch_us_indices, "us_indices"), (fetch_tw_market, "tw_market"), (fetch_futures_and_fx, "futures_fx"), (fetch_chip_summary, "chip"), (fetch_sectors, "sectors"), (fetch_gov_funds, "gov_funds"), (fetch_buffett, "buffett")]:
        try:
            fn()
        except Exception as exc:
            logger.warning("Startup warm-up failed [%s]: %s", name, exc)

    # US indices: every 5 minutes
    scheduler.add_job(fetch_us_indices, "interval", minutes=5, id="us_indices_refresh")
    # TW market: every 10 seconds during market hours (09:00–13:35 Taipei)
    scheduler.add_job(
        fetch_tw_market, "interval", seconds=10, id="tw_market_refresh",
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
    scheduler.start()
    logger.info("APScheduler started — us:5min  tw:10s  futures_fx:1min  chip:14:35  indicators:15:05  sectors:15:10  gov:15:15  audit:16:30")

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


@app.get("/")
async def root():
    return {"status": "ok", "service": "Taiwan AI Stock Radar API v0.2"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
