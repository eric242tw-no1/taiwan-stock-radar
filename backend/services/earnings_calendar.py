"""財報日曆服務 — FinMind 除息/除權/法說日期，每日 08:00 更新"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx

from db import get_conn

logger = logging.getLogger(__name__)
_TW = timezone(timedelta(hours=8))
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
TTL_HOURS = 23


def _is_fresh() -> bool:
    """確認 earnings_calendar 最後更新時間是否在 TTL 內。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT MAX(updated_at) FROM earnings_calendar"
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return False
    try:
        last = datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last).total_seconds() < TTL_HOURS * 3600
    except Exception:
        return False


def _fetch_finmind(dataset: str, start_date: str) -> list[dict]:
    token = os.environ.get("FINMIND_TOKEN", "")
    params: dict = {"dataset": dataset, "start_date": start_date}
    if token and token != "placeholder":
        params["token"] = token
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(FINMIND_URL, params=params)
        data = resp.json()
        if data.get("status") == 200:
            return data.get("data", [])
    except Exception as exc:
        logger.warning("FinMind fetch [%s] error: %s", dataset, exc)
    return []


def fetch_and_store_calendar(days: int = 30) -> int:
    """取得未來 days 天的財報/除息/除權日曆，寫入 DB。回傳寫入筆數。"""
    if _is_fresh():
        logger.info("earnings_calendar: cache still fresh, skip fetch")
        return 0

    today = datetime.now(_TW).date()
    end = today + timedelta(days=days)
    start_str = str(today)

    events: list[tuple] = []

    # 除息 TaiwanStockDividend
    for row in _fetch_finmind("TaiwanStockDividend", start_str):
        d = row.get("ex_dividend_date") or row.get("date", "")
        if d and d >= start_str and d <= str(end):
            events.append((
                row.get("stock_id"), row.get("stock_name", ""),
                "dividend", d,
                f"現金股利 {row.get('cash_dividend', '')} 元",
                datetime.now(timezone.utc).isoformat(),
            ))

    # 除權 TaiwanStockRightsDistribution
    for row in _fetch_finmind("TaiwanStockRightsDistribution", start_str):
        d = row.get("ex_rights_date") or row.get("date", "")
        if d and d >= start_str and d <= str(end):
            events.append((
                row.get("stock_id"), row.get("stock_name", ""),
                "rights", d,
                f"股票股利 {row.get('stock_dividend', '')} 股",
                datetime.now(timezone.utc).isoformat(),
            ))

    if not events:
        logger.info("earnings_calendar: no events from FinMind (token may be missing)")
        # 仍寫入一筆 sentinel 使 _is_fresh() 成立，避免重複呼叫
        conn = get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO earnings_calendar (symbol, name, event_type, event_date, description) "
            "VALUES ('_sentinel', '', 'sentinel', ?, 'no data')",
            (str(today),)
        )
        conn.commit()
        conn.close()
        return 0

    conn = get_conn()
    conn.execute("DELETE FROM earnings_calendar WHERE event_type != 'sentinel'")
    conn.executemany(
        "INSERT INTO earnings_calendar (symbol, name, event_type, event_date, description, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        events,
    )
    conn.commit()
    conn.close()
    logger.info("earnings_calendar: stored %d events", len(events))
    return len(events)


def get_events(days: int = 30) -> list[dict]:
    """從 DB 讀取未來 days 天事件，不含 sentinel。"""
    today = datetime.now(_TW).strftime("%Y-%m-%d")
    end = (datetime.now(_TW) + timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, name, event_type, event_date, description FROM earnings_calendar "
        "WHERE event_type != 'sentinel' AND event_date BETWEEN ? AND ? "
        "ORDER BY event_date ASC",
        (today, end),
    ).fetchall()
    conn.close()
    return [
        {"symbol": r[0], "name": r[1], "event_type": r[2], "date": r[3], "description": r[4]}
        for r in rows
    ]
