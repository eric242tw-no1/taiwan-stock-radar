"""Scheduler task functions extracted from main.py for a clean boundary."""
import asyncio
import logging
import os

from brokers.yuanta import YuantaBroker
from brokers.sinopac import SinopacBroker
from agents.stop_loss_guard import StopLossGuard

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run coroutine from APScheduler thread context. Returns coro's result."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        try:
            asyncio.get_event_loop().create_task(coro)
        except Exception:
            pass
        return None


def _create_broker():
    broker_type = os.getenv("BROKER", "yuanta").lower()
    if broker_type == "sinopac":
        try:
            return SinopacBroker()
        except Exception as e:
            logger.warning("SinopacBroker 初始化失敗，fallback 至 YuantaBroker: %s", e)
    return YuantaBroker()


_broker = _create_broker()
stop_loss_guard = StopLossGuard(_broker)


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
    from agents.morning_brief_agent import generate_morning_brief
    _run_async(generate_morning_brief())


def _chip_and_anomaly_sync() -> None:
    """09:05 weekdays — fetch chip data then scan anomalies."""
    from agents.market_anomaly_agent import scan_anomalies
    from services.finmind_fetcher import fetch_chip_summary
    try:
        fetch_chip_summary()
    except Exception as exc:
        logger.warning("chip fetch at 09:05: %s", exc)
    _run_async(scan_anomalies())


def _scan_anomalies_sync() -> None:
    """09:10–13:20 every 10 min weekdays — anomaly scan."""
    from agents.market_anomaly_agent import scan_anomalies
    _run_async(scan_anomalies())


def _factor_scan_and_batch_score() -> None:
    """13:35 weekdays — factor scan + AI batch scoring (in-process 循序) + account snapshot."""
    from agents.ai_engine import get_ai_analysis
    from services.stock_pool_service import get_pool

    async def _score_all(symbols: list[str]) -> int:
        done = 0
        for sym in symbols:
            try:
                await get_ai_analysis(sym, force=True)
                done += 1
            except Exception as exc:
                logger.warning("batch score %s: %s", sym, exc)
        return done

    try:
        symbols = [s["symbol"] for s in get_pool()]
        done = _run_async(_score_all(symbols))
        logger.info("factor_scan: AI scored %d/%d symbols", done, len(symbols))
    except Exception as exc:
        logger.warning("factor_scan: %s", exc)
    _take_account_snapshot()


def _take_account_snapshot() -> None:
    """13:35 每日帳戶快照 — 收盤後寫入 account_snapshots 表。"""
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

    _run_async(_snapshot())


def _stop_loss_polling_sync() -> None:
    """每分鐘：StopLossGuard Layer2 輪詢。"""
    _run_async(stop_loss_guard.polling_monitor())


def _run_daily_audit_sync() -> None:
    """15:30 weekdays：AI 自審計（同步包裝）。"""
    from services.audit import run_daily_audit
    try:
        run_daily_audit()
    except Exception as exc:
        logger.warning("daily audit error: %s", exc)
