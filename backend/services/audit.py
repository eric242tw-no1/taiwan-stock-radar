"""
AI Self Audit 自審計
record_prediction() — UZI/IC/辯論 API 呼叫後寫入預測
run_daily_audit()   — 每日 15:30 比對前日收盤，計算準確率
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

from db import get_conn

logger = logging.getLogger(__name__)

_TW = timezone(timedelta(hours=8))


def record_prediction(
    symbol: str,
    predicted_direction: str,   # "up" | "down" | "neutral"
    confidence: float,
    target_price: float | None = None,
) -> int:
    """寫入一筆 AI 預測紀錄，回傳新插入的 id。"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ai_audit (symbol, predicted_direction, target_price, confidence) "
        "VALUES (?, ?, ?, ?)",
        (symbol, predicted_direction, target_price, confidence),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def run_daily_audit() -> dict:
    """
    比對昨日收盤價與預測方向，更新 ai_audit.is_correct。
    回傳 {audited, correct, accuracy}。
    """
    from services.stock_quote_fetcher import fetch_stock_quote

    conn = get_conn()
    # 找出昨日（台灣時間）未稽核的預測
    yesterday = (datetime.now(_TW) - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT id, symbol, predicted_direction, target_price "
        "FROM ai_audit "
        "WHERE is_correct IS NULL AND date(predicted_at) <= ?",
        (yesterday,),
    ).fetchall()

    audited = 0
    correct = 0

    for row_id, symbol, direction, target_price in rows:
        try:
            quote = fetch_stock_quote(symbol)
            actual_close = float(quote.get("price") or 0)
            if actual_close == 0:
                continue

            # 取預測時的收盤（前一交易日收盤，用 target_price 作為基準）
            if target_price and target_price > 0:
                is_correct = int(
                    (direction == "up"      and actual_close > target_price) or
                    (direction == "down"    and actual_close < target_price) or
                    (direction == "neutral" and abs(actual_close - target_price) / target_price < 0.01)
                )
            else:
                is_correct = None

            conn.execute(
                "UPDATE ai_audit SET actual_close=?, is_correct=?, audited_at=datetime('now') WHERE id=?",
                (actual_close, is_correct, row_id),
            )
            audited += 1
            if is_correct:
                correct += 1
        except Exception as e:
            logger.warning("audit error [%s]: %s", symbol, e)

    conn.commit()
    conn.close()

    accuracy = round(correct / audited * 100, 1) if audited > 0 else None
    logger.info("Daily audit: %d audited, %d correct, accuracy=%s%%", audited, correct, accuracy)
    return {"audited": audited, "correct": correct, "accuracy": accuracy}


def get_accuracy_report(days: int = 30) -> dict:
    """回傳最近 N 天的準確率報表。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, predicted_direction, is_correct, confidence, predicted_at "
        "FROM ai_audit "
        "WHERE is_correct IS NOT NULL AND predicted_at >= datetime('now', ? || ' days') "
        "ORDER BY predicted_at DESC",
        (f"-{days}",),
    ).fetchall()
    conn.close()

    total = len(rows)
    correct = sum(1 for r in rows if r[2] == 1)
    by_symbol: dict[str, dict] = {}
    for symbol, direction, is_corr, confidence, predicted_at in rows:
        if symbol not in by_symbol:
            by_symbol[symbol] = {"total": 0, "correct": 0}
        by_symbol[symbol]["total"] += 1
        if is_corr:
            by_symbol[symbol]["correct"] += 1

    return {
        "days": days,
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total * 100, 1) if total > 0 else None,
        "by_symbol": {
            sym: {**v, "accuracy": round(v["correct"] / v["total"] * 100, 1)}
            for sym, v in by_symbol.items()
        },
        "recent": [
            {"symbol": r[0], "direction": r[1], "is_correct": r[2],
             "confidence": r[3], "predicted_at": r[4]}
            for r in rows[:20]
        ],
    }
