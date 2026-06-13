"""
台美滾動相關係數
下載 ^GSPC（S&P500）與台灣加權指數（^TWII），計算 30/60/90 日 Pearson r
結果存入 macro_indicators table，每日 15:15 更新
"""
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_TW = timezone(timedelta(hours=8))
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cache.db")


def ensure_table() -> None:
    con = sqlite3.connect(_DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS macro_indicators (
            date            TEXT PRIMARY KEY,
            tw_us_corr_30d  REAL,
            tw_us_corr_60d  REAL,
            tw_us_corr_90d  REAL,
            updated_at      TEXT
        )
    """)
    con.commit()
    con.close()


def calculate_and_store() -> dict | None:
    """下載近 120 天資料，計算三個滾動相關係數，寫入 DB，回傳最新結果。"""
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        logger.error("yfinance / pandas not installed")
        return None

    try:
        end = datetime.now(_TW)
        start = end - timedelta(days=180)

        sp500 = yf.download("^GSPC", start=start.strftime("%Y-%m-%d"),
                             end=end.strftime("%Y-%m-%d"), progress=False)
        twii  = yf.download("^TWII", start=start.strftime("%Y-%m-%d"),
                             end=end.strftime("%Y-%m-%d"), progress=False)

        if sp500.empty or twii.empty:
            logger.warning("Correlation: empty data from yfinance")
            return None

        sp_close = sp500["Close"].squeeze().rename("sp500")
        tw_close = twii["Close"].squeeze().rename("twii")

        merged = pd.concat([sp_close, tw_close], axis=1).dropna()
        if len(merged) < 30:
            logger.warning("Correlation: not enough data (%d rows)", len(merged))
            return None

        r30 = merged["sp500"].tail(30).corr(merged["twii"].tail(30))
        r60 = merged["sp500"].tail(60).corr(merged["twii"].tail(60)) if len(merged) >= 60 else None
        r90 = merged["sp500"].tail(90).corr(merged["twii"].tail(90)) if len(merged) >= 90 else None

        today = end.strftime("%Y-%m-%d")
        _save(today, r30, r60, r90)
        logger.info("Correlation updated: 30d=%.3f 60d=%s 90d=%s", r30, r60, r90)
        return {"date": today, "tw_us_corr_30d": r30, "tw_us_corr_60d": r60, "tw_us_corr_90d": r90}

    except Exception as e:
        logger.error("Correlation calculation failed: %s", e)
        return None


def _save(date: str, r30: float, r60: float | None, r90: float | None) -> None:
    con = sqlite3.connect(_DB_PATH)
    con.execute(
        """INSERT OR REPLACE INTO macro_indicators
           (date, tw_us_corr_30d, tw_us_corr_60d, tw_us_corr_90d, updated_at)
           VALUES (?,?,?,?,datetime('now'))""",
        (date, round(r30, 4), round(r60, 4) if r60 else None, round(r90, 4) if r90 else None),
    )
    con.commit()
    con.close()


def get_latest() -> dict | None:
    """讀取最新一筆相關係數（前端 API 使用）。"""
    try:
        con = sqlite3.connect(_DB_PATH)
        row = con.execute(
            "SELECT date, tw_us_corr_30d, tw_us_corr_60d, tw_us_corr_90d FROM macro_indicators ORDER BY date DESC LIMIT 1"
        ).fetchone()
        con.close()
        if row:
            return {"date": row[0], "tw_us_corr_30d": row[1], "tw_us_corr_60d": row[2], "tw_us_corr_90d": row[3]}
    except Exception:
        pass
    return None
