"""
Value checks for services/indicator_service._calc_indicators.

Each indicator is compared with a plain numpy/pandas reference of the textbook
definition (the same definitions pandas-ta and TA-Lib use):
  - RSI(14) and ATR(14): Wilder smoothing seeded with the simple mean
  - MACD(12, 26, 9): EMAs seeded with the SMA of the first `period` values
  - KD(9, 3, 3): raw %K over 9 bars, %K = SMA3(raw %K), %D = SMA3(%K)
"""
import numpy as np
import pandas as pd
import pytest

import services.indicator_service as ind


def _make_ohlcv(n: int = 250) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 2.0, n)
    low = close - rng.uniform(0.1, 2.0, n)
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _wilder(values: np.ndarray, length: int) -> np.ndarray:
    out = np.full(len(values), np.nan)
    out[length - 1] = values[:length].mean()
    for i in range(length, len(values)):
        out[i] = (out[i - 1] * (length - 1) + values[i]) / length
    return out


def _ema(values: np.ndarray, length: int) -> np.ndarray:
    out = np.full(len(values), np.nan)
    start = np.flatnonzero(~np.isnan(values))[0]
    out[start + length - 1] = values[start:start + length].mean()
    alpha = 2 / (length + 1)
    for i in range(start + length, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def _reference(df: pd.DataFrame) -> dict:
    close, high, low = (df[c].to_numpy() for c in ("close", "high", "low"))
    delta = np.diff(close)
    gain = _wilder(np.clip(delta, 0, None), 14)
    loss = _wilder(np.clip(-delta, 0, None), 14)
    rsi = 100 * gain / (gain + loss)

    macd = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd, 9)

    lowest = df["low"].rolling(9).min()
    highest = df["high"].rolling(9).max()
    k = (100 * (df["close"] - lowest) / (highest - lowest)).rolling(3).mean()
    d = k.rolling(3).mean()

    prev_close = np.concatenate([[np.nan], close[:-1]])
    tr = np.nanmax(np.vstack([high - low, np.abs(high - prev_close), np.abs(low - prev_close)]), axis=0)
    atr = _wilder(tr, 14)

    return {
        "rsi14": rsi[-1],
        "macd": macd[-1],
        "macd_signal": signal[-1],
        "macd_hist": macd[-1] - signal[-1],
        "k": k.iloc[-1],
        "d": d.iloc[-1],
        "atr14": atr[-1],
    }


def test_indicator_values_match_reference_definitions():
    df = _make_ohlcv()
    result = ind._calc_indicators(df)
    for key, expected in _reference(df).items():
        assert result[key] == pytest.approx(expected, abs=1e-9), key


def test_missing_bars_do_not_break_calculation():
    df = _make_ohlcv()
    df.iloc[100, df.columns.get_loc("close")] = np.nan
    result = ind._calc_indicators(df)
    assert result is not None
    assert all(result[k] is not None for k in ("rsi14", "macd", "macd_signal", "macd_hist", "k", "d", "atr14"))
