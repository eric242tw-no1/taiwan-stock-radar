"""技術指標計算：RSI(14)、MACD(12/26/9)、KD(9)、MA(5/10/20/60)、ATR(14)、Bias(20)。"""
from __future__ import annotations
import logging

import pandas as pd

from .output_formatter import TechnicalFactors

logger = logging.getLogger(__name__)


def compute(symbol: str, ohlcv_df: pd.DataFrame) -> TechnicalFactors:
    """
    計算技術指標並回傳 TechnicalFactors。

    ohlcv_df 需包含欄位：close, high, low（volume 可選）。
    所有欄位須為 float，index 為時間序列（舊→新）。
    資料不足時相關欄位回傳 None。
    """
    df = ohlcv_df.copy()
    for col in ("close", "high", "low"):
        if col not in df.columns:
            logger.warning("factor_engine.technical: missing column '%s' for %s", col, symbol)
            return TechnicalFactors()
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["close"]).reset_index(drop=True)
    close = df["close"]
    n = len(close)

    result = TechnicalFactors()

    # ── RSI(14) ────────────────────────────────────────────
    if n >= 15:
        result.rsi_14 = _rsi(close, 14)

    # ── MACD(12/26/9) ──────────────────────────────────────
    if n >= 27:
        macd_line, signal_line, hist = _macd(close, 12, 26, 9)
        result.macd        = _r(macd_line)
        result.macd_signal = _r(signal_line)
        result.macd_hist   = _r(hist)

    # ── KD(9) — Stochastic Oscillator ──────────────────────
    if n >= 9 and "high" in df.columns and "low" in df.columns:
        k, d = _stochastic(df["high"], df["low"], close, 9)
        result.kd_k = _r(k)
        result.kd_d = _r(d)

    # ── MA(5/10/20/60) ─────────────────────────────────────
    for period, attr in ((5, "ma5"), (10, "ma10"), (20, "ma20"), (60, "ma60")):
        if n >= period:
            setattr(result, attr, _r(close.rolling(period).mean().iloc[-1]))

    # ── ATR(14) ────────────────────────────────────────────
    if n >= 15 and "high" in df.columns and "low" in df.columns:
        result.atr_14 = _r(_atr(df["high"], df["low"], close, 14))

    # ── Bias(20) — 乖離率 ──────────────────────────────────
    if n >= 20:
        ma20 = close.rolling(20).mean().iloc[-1]
        if ma20 and ma20 != 0:
            result.bias_20 = _r((close.iloc[-1] - ma20) / ma20 * 100)

    return result


# ── helpers ──────────────────────────────────────────────────────────────────

def _r(val: float | None, digits: int = 4) -> float | None:
    """Round to N decimal places, return None for NaN."""
    if val is None:
        return None
    try:
        import math
        if math.isnan(val) or math.isinf(val):
            return None
        return round(float(val), digits)
    except Exception:
        return None


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return _r(rsi.iloc[-1])


def _macd(close: pd.Series, fast: int, slow: int, signal: int):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], hist.iloc[-1]


def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9):
    low_min  = low.rolling(period).min()
    high_max = high.rolling(period).max()
    denom = (high_max - low_min).replace(0, float("nan"))
    k = ((close - low_min) / denom * 100).ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    return k.iloc[-1], d.iloc[-1]


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float | None:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return _r(tr.rolling(period).mean().iloc[-1])
