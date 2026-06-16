"""FactorBundle — 統一輸出格式，序列化為 JSON 相容 dict 傳入 Agent。"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any


@dataclass
class TechnicalFactors:
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    kd_k: float | None = None
    kd_d: float | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    atr_14: float | None = None
    bias_20: float | None = None   # (close - MA20) / MA20 * 100


@dataclass
class ChipsFactors:
    foreign_net: int | None = None       # 外資買賣超（張）
    investment_net: int | None = None    # 投信買賣超（張）
    dealer_net: int | None = None        # 自營商買賣超（張）
    margin_balance: int | None = None    # 融資餘額（張）
    short_balance: int | None = None     # 融券餘額（張）
    holders_over_400: int | None = None  # 大戶集保（≥400張）
    chips_date: str | None = None        # 實際資料日期


@dataclass
class FactorBundle:
    symbol: str
    date: str                          # YYYY-MM-DD
    technical: TechnicalFactors = field(default_factory=TechnicalFactors)
    chips: ChipsFactors = field(default_factory=ChipsFactors)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        # 移除所有 None 值，保持 JSON 乾淨
        def _clean(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items() if v is not None}
            return obj
        return _clean(d)


def bundle(
    symbol: str,
    technical_factors: TechnicalFactors,
    chips_factors: ChipsFactors,
    as_of: date | None = None,
) -> FactorBundle:
    """組合 TechnicalFactors 與 ChipsFactors 為 FactorBundle。"""
    from datetime import date as _date
    d = (as_of or _date.today()).isoformat()
    return FactorBundle(symbol=symbol, date=d, technical=technical_factors, chips=chips_factors)
