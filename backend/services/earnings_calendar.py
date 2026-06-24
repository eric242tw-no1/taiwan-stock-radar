"""財報日曆服務 — TWSE 除權息預告表（免費、不需 token），每日 08:00 更新"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

import httpx

from db import get_conn

logger = logging.getLogger(__name__)
_TW = timezone(timedelta(hours=8))
# TWSE 上市股票除權除息預告表（含未來日期，民國年格式）
_TWSE_DIVIDEND_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL"
TTL_HOURS = 23


def _fmt_num(s: str) -> str:
    """去除多餘小數零：'0.600000' → '0.6'，'0.000000'/'' → ''。"""
    try:
        f = float(s)
        return "" if f == 0 else f"{f:g}"
    except (ValueError, TypeError):
        return s


def _roc_to_iso(roc: str) -> str | None:
    """民國日期 '1150709' → '2026-07-09'。"""
    roc = (roc or "").strip()
    if len(roc) != 7 or not roc.isdigit():
        return None
    year = int(roc[:3]) + 1911
    return f"{year:04d}-{roc[3:5]}-{roc[5:7]}"


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


def _fetch_twse_dividend() -> list[dict]:
    """TWSE 除權除息預告表（免費、無 token）。"""
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(_TWSE_DIVIDEND_URL)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("TWSE 除權息預告抓取失敗: %s", exc)
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
    now_iso = datetime.now(timezone.utc).isoformat()

    # TWSE 除權除息預告表（Exdividend: 息=除息, 權=除權, 權息=兩者）
    for row in _fetch_twse_dividend():
        d = _roc_to_iso(row.get("Date", ""))
        if not d or d < start_str or d > str(end):
            continue
        symbol = (row.get("Code") or "").strip()
        name = (row.get("Name") or "").strip()
        kind = row.get("Exdividend") or ""
        cash = _fmt_num((row.get("CashDividend") or "").strip())
        stock_ratio = _fmt_num((row.get("StockDividendRatio") or "").strip())

        if "權" in kind:
            desc = f"除權 股票股利率 {stock_ratio}" if stock_ratio else "除權"
            events.append((symbol, name, "rights", d, desc, now_iso))
        if "息" in kind:
            desc = f"除息 現金股利 {cash} 元" if cash else "除息"
            events.append((symbol, name, "dividend", d, desc, now_iso))

    if not events:
        logger.info("earnings_calendar: TWSE 無未來 %d 天除權息事件", days)
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
