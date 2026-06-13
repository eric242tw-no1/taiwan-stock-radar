import logging

from fastapi import APIRouter, Query

from services.risk_manager import RiskDecision, RiskManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/risk", tags=["risk"])

_rm = RiskManager()


@router.get("/watching")
async def get_watching():
    """StopLossGuard 目前監控中的股票清單（Layer 2 輪詢備援）"""
    from main import stop_loss_guard
    return {"watching": stop_loss_guard.watching}


@router.get("/assessment/{symbol}")
async def get_risk_assessment(
    symbol: str,
    size: int = Query(1000, description="計劃交易股數"),
    capital: float = Query(1_000_000, description="總資金（元）"),
    portfolio: str = Query("", description="逗號分隔的已持倉股票代號"),
):
    """
    對指定股票執行三項風控檢查，回傳 RiskDecision 彙整結果。

    - check_position_size：單股倉位不超過總資金 20%
    - check_max_drawdown：當日虧損不超過 5%
    - check_correlation_risk：與持倉股票相關性 < 0.8
    """
    held = [s.strip() for s in portfolio.split(",") if s.strip()]

    checks = {
        "position_size":    _rm.check_position_size(symbol, size, capital),
        "max_drawdown":     _rm.check_max_drawdown(),
        "correlation_risk": _rm.check_correlation_risk(symbol, held),
    }

    overall_approved = all(d.approved for d in checks.values())
    failed = [name for name, d in checks.items() if not d.approved]

    return {
        "symbol":           symbol,
        "overall_approved": overall_approved,
        "failed_checks":    failed,
        "checks": {
            name: {"approved": d.approved, "reason": d.reason, "detail": d.detail}
            for name, d in checks.items()
        },
    }
