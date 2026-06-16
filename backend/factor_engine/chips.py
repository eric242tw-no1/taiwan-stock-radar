"""籌碼因子計算：三大法人、融資融券、大戶集保。從 DB 讀取。"""
from __future__ import annotations
import logging
from datetime import date, timedelta

from db import get_conn
from .output_formatter import ChipsFactors

logger = logging.getLogger(__name__)


def compute(symbol: str, as_of: date | None = None) -> ChipsFactors:
    target = as_of or date.today()
    for delta in range(6):
        d = target - timedelta(days=delta)
        result = _fetch(symbol, d)
        if result is not None:
            return result

    logger.warning("chips.compute: no chip data found for %s within 5 days of %s", symbol, target)
    return ChipsFactors()


def _fetch(symbol: str, d: date) -> ChipsFactors | None:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT foreign_buy, investment_buy, dealer_buy, margin, short_interest "
            "FROM chip_data WHERE symbol = ? AND date = ?",
            (symbol, d.isoformat()),
        )
        chip_row = cur.fetchone()

        cur.execute(
            "SELECT holders_over_400 FROM large_holders_weekly "
            "WHERE symbol = ? AND week_end_date <= ? ORDER BY week_end_date DESC LIMIT 1",
            (symbol, d.isoformat()),
        )
        holder_row = cur.fetchone()
        conn.close()
    except Exception as exc:
        logger.warning("chips.compute DB error for %s %s: %s", symbol, d, exc)
        return None

    if chip_row is None:
        return None

    return ChipsFactors(
        foreign_net      = int(chip_row["foreign_buy"] or 0),
        investment_net   = int(chip_row["investment_buy"] or 0),
        dealer_net       = int(chip_row["dealer_buy"] or 0),
        margin_balance   = int(chip_row["margin"] or 0),
        short_balance    = int(chip_row["short_interest"] or 0),
        holders_over_400 = int(holder_row["holders_over_400"]) if holder_row else None,
        chips_date       = d.isoformat(),
    )
