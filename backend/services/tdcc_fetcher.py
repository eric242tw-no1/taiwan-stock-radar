"""
TDCC 大戶集保週資料
來源：FinMind TaiwanStockHolding（每週六公布）
DB table: stock_holding_distribution (symbol, date, level, ratio)
"""
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")

_TW = timezone(timedelta(hours=8))
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cache.db")


def ensure_table() -> None:
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS stock_holding_distribution (
            symbol TEXT NOT NULL,
            date   TEXT NOT NULL,
            level  TEXT NOT NULL,
            ratio  REAL NOT NULL,
            PRIMARY KEY (symbol, date, level)
        )
    """)
    con.commit()
    con.close()


def fetch_tdcc(symbol: str) -> list[dict]:
    """抓單一股票最近一期集保分布，回傳 [{level, ratio}]。"""
    start = (datetime.now(_TW) - timedelta(days=30)).strftime("%Y-%m-%d")
    try:
        r = httpx.get(
            FINMIND_URL,
            params={
                "dataset": "TaiwanStockHolding",
                "data_id": symbol,
                "start_date": start,
                "token": FINMIND_TOKEN,
            },
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json().get("data", [])
    except Exception as e:
        logger.error("TDCC fetch failed [%s]: %s", symbol, e)
        return []

    if not rows:
        return []

    # 取最新日期
    latest_date = max(r["date"] for r in rows)
    day_rows = [r for r in rows if r["date"] == latest_date]

    result = []
    for row in day_rows:
        try:
            result.append({
                "level": str(row.get("HoldingSharesLevel", row.get("level", ""))),
                "ratio": float(row.get("percent", row.get("ratio", 0))),
                "date": latest_date,
            })
        except (KeyError, ValueError):
            continue

    _save_to_db(symbol, result)
    return result


def _save_to_db(symbol: str, rows: list[dict]) -> None:
    if not rows:
        return
    try:
        con = sqlite3.connect(_DB_PATH)
        con.executemany(
            "INSERT OR REPLACE INTO stock_holding_distribution VALUES (?,?,?,?)",
            [(symbol, r["date"], r["level"], r["ratio"]) for r in rows],
        )
        con.commit()
        con.close()
    except Exception as e:
        logger.error("TDCC DB save failed [%s]: %s", symbol, e)


def get_chip_distribution(symbol: str) -> list[dict]:
    """從 DB 讀取最新一期，若無資料則觸發即時抓取。"""
    try:
        con = sqlite3.connect(_DB_PATH)
        rows = con.execute(
            """SELECT date, level, ratio FROM stock_holding_distribution
               WHERE symbol=? ORDER BY date DESC, level""",
            (symbol,),
        ).fetchall()
        con.close()
        if rows:
            latest_date = rows[0][0]
            return [
                {"date": latest_date, "level": lv, "ratio": rt}
                for _, lv, rt in rows
                if _[0] == latest_date  # only latest date
            ]
    except Exception:
        pass

    return fetch_tdcc(symbol)


def fetch_all_pool_tdcc() -> None:
    """週批次：抓股票池所有股票的集保分布（APScheduler 呼叫）。"""
    try:
        con = sqlite3.connect(_DB_PATH)
        symbols = [r[0] for r in con.execute("SELECT symbol FROM stock_pool").fetchall()]
        con.close()
    except Exception:
        symbols = ["2330", "2317", "2454", "2412"]

    logger.info("TDCC batch: fetching %d symbols", len(symbols))
    for sym in symbols:
        try:
            fetch_tdcc(sym)
        except Exception as e:
            logger.error("TDCC batch error [%s]: %s", sym, e)
