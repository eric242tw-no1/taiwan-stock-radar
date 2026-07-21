"""
Change D — RiskManager

Three independent checks, each returns a RiskDecision.
All checks are synchronous (DB reads only).
"""
import logging
from dataclasses import dataclass

from db import get_conn

logger = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    detail: dict | None = None


class RiskManager:

    def check_position_size(self, symbol: str, size: int, capital: float) -> RiskDecision:
        """Reject if a single-stock position value exceeds 20% of total capital.

        size: shares to trade (not current holding)
        capital: total account capital in TWD
        """
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT close FROM daily_price WHERE symbol=? ORDER BY date DESC LIMIT 1",
                (symbol,),
            )
            row = cur.fetchone()
            conn.close()
        except Exception as exc:
            logger.warning("check_position_size DB error: %s", exc)
            return RiskDecision(approved=True, reason="無法取得價格，跳過檢查")

        if not row:
            return RiskDecision(approved=True, reason="無歷史價格，跳過檢查")

        price = float(row[0])
        position_value = price * size
        pct = position_value / capital if capital > 0 else 1.0

        if pct > 0.20:
            return RiskDecision(
                approved=False,
                reason=f"單股倉位 {pct:.1%} 超過上限 20%",
                detail={"symbol": symbol, "position_value": position_value, "capital": capital, "pct": pct},
            )
        return RiskDecision(approved=True, reason="倉位大小檢查通過")

    def check_max_drawdown(self, account: dict | None = None) -> RiskDecision:
        """Reject new positions if today's P&L loss exceeds 5% of capital.

        account: optional dict with keys total_value / daily_pnl.
        Falls back to latest account_snapshots row if account is None.
        """
        try:
            if account is None:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT total_value, daily_pnl FROM account_snapshots ORDER BY date DESC LIMIT 1")
                row = cur.fetchone()
                account = dict(row) if row else {}
                conn.close()
        except Exception as exc:
            logger.warning("check_max_drawdown DB error: %s", exc)
            return RiskDecision(approved=True, reason="無法取得帳戶資料，跳過檢查")

        total_value = float(account.get("total_value", 0) or 0)
        daily_pnl   = float(account.get("daily_pnl",   0) or 0)

        if total_value <= 0:
            return RiskDecision(approved=True, reason="無帳戶資料，跳過檢查")

        drawdown_pct = -daily_pnl / total_value  # positive when losing
        if drawdown_pct > 0.05:
            return RiskDecision(
                approved=False,
                reason=f"當日虧損 {drawdown_pct:.1%} 超過 5%，停止新倉",
                detail={"daily_pnl": daily_pnl, "total_value": total_value, "drawdown_pct": drawdown_pct},
            )
        return RiskDecision(approved=True, reason="最大虧損檢查通過")

    def check_correlation_risk(self, symbol: str, portfolio: list[str]) -> RiskDecision:
        """Reject if symbol's 60-day correlation with any held stock exceeds 0.8."""
        if not portfolio:
            return RiskDecision(approved=True, reason="無持倉，跳過相關性檢查")

        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT symbol_long, symbol_short, corr_60d
                    FROM pairs_config
                    WHERE (symbol_long = ? OR symbol_short = ?)
                      AND corr_60d > 0.8
                    """,
                    (symbol, symbol),
                )
                rows = cur.fetchall()
        except Exception as exc:
            logger.warning("check_correlation_risk DB error: %s", exc)
            return RiskDecision(approved=True, reason="無法查詢相關性，跳過檢查")

        for row in rows:
            sym_long, sym_short, corr = row
            counterpart = sym_short if sym_long == symbol else sym_long
            if counterpart in portfolio:
                return RiskDecision(
                    approved=False,
                    reason=f"{symbol} 與持倉 {counterpart} 相關性 {corr:.2f} > 0.8",
                    detail={"symbol": symbol, "counterpart": counterpart, "corr_60d": float(corr)},
                )

        return RiskDecision(approved=True, reason="相關性風險檢查通過")
