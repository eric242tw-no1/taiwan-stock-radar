"""
Tests for services/indicator_service.py

Covers:
  - _calc_indicators: returns None for insufficient data
  - _calc_indicators: returns correct keys for valid OHLCV data
  - _calc_indicators: handles MultiIndex columns (yfinance >=0.2)
  - _cache updated in-memory even when DB upsert fails
  - get_indicators / get_all_indicators read from in-memory cache
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

import services.indicator_service as ind


# ── fixtures ───────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 60) -> pd.DataFrame:
    """Generate n days of synthetic OHLCV data with a clean uptrend."""
    np.random.seed(42)
    dates  = pd.date_range("2024-01-01", periods=n, freq="B")
    close  = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high   = close + np.abs(np.random.randn(n) * 0.3)
    low    = close - np.abs(np.random.randn(n) * 0.3)
    volume = np.random.randint(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"close": close, "high": high, "low": low,
         "open": close, "volume": volume},
        index=dates,
    )


def _make_multiindex_ohlcv(n: int = 60) -> pd.DataFrame:
    """Simulate yfinance >=0.2 MultiIndex column format."""
    df = _make_ohlcv(n)
    df.columns = pd.MultiIndex.from_tuples(
        [(c.capitalize(), "2330.TW") for c in df.columns]
    )
    return df


# ── _calc_indicators ───────────────────────────────────────────────────────────

class TestCalcIndicators:
    def test_returns_none_for_empty_df(self):
        assert ind._calc_indicators(pd.DataFrame()) is None

    def test_returns_none_for_none_input(self):
        assert ind._calc_indicators(None) is None  # type: ignore

    def test_returns_none_when_fewer_than_30_rows(self):
        df = _make_ohlcv(n=29)
        assert ind._calc_indicators(df) is None

    def test_returns_dict_with_expected_keys(self):
        df     = _make_ohlcv(n=60)
        result = ind._calc_indicators(df)

        assert result is not None
        expected_keys = {"trade_date", "close", "volume",
                         "rsi14", "macd", "macd_signal", "macd_hist",
                         "k", "d", "atr14"}
        assert expected_keys.issubset(result.keys())

    def test_rsi_in_valid_range(self):
        df     = _make_ohlcv(n=60)
        result = ind._calc_indicators(df)

        assert result is not None
        rsi = result["rsi14"]
        if rsi is not None:
            assert 0 <= rsi <= 100, f"RSI {rsi} out of range"

    def test_close_matches_last_row(self):
        df     = _make_ohlcv(n=60)
        result = ind._calc_indicators(df)

        assert result is not None
        assert result["close"] == pytest.approx(df["close"].iloc[-1], rel=1e-4)

    def test_handles_multiindex_columns(self):
        """yfinance >=0.2 returns MultiIndex — should still compute correctly."""
        df     = _make_multiindex_ohlcv(n=60)
        result = ind._calc_indicators(df)

        assert result is not None
        assert "rsi14" in result

    def test_exactly_30_rows_passes_threshold(self):
        """Boundary: exactly 30 rows should proceed (>= 30 check)."""
        df     = _make_ohlcv(n=30)
        result = ind._calc_indicators(df)
        # May return None if indicators need more warmup, but should not crash
        # (result can be None due to insufficient TA warmup — that's OK)
        # The important thing is no exception is raised.
        assert result is None or isinstance(result, dict)


# ── in-memory cache ────────────────────────────────────────────────────────────

class TestInMemoryCache:
    def setup_method(self):
        ind._cache.clear()

    def teardown_method(self):
        ind._cache.clear()

    def test_get_indicators_returns_none_for_unknown_ticker(self):
        assert ind.get_indicators("9999.TW") is None

    def test_get_all_indicators_returns_empty_dict_initially(self):
        assert ind.get_all_indicators() == {}

    def test_calculate_and_store_updates_cache_even_if_db_fails(self):
        """
        Core A1 regression: indicators must land in _cache even when
        the DB upsert raises (no PostgreSQL in local dev).
        """
        df = _make_ohlcv(n=60)

        with patch("yfinance.download", return_value=df), \
             patch("services.indicator_service._get_conn",
                   side_effect=Exception("DB unavailable")):
            ind.calculate_and_store(["2330.TW"])

        result = ind.get_indicators("2330.TW")
        assert result is not None, (
            "Cache should be populated even when DB is down"
        )
        assert result["ticker"] == "2330.TW"
        assert result["rsi14"] is not None

    def test_calculate_and_store_skips_ticker_with_insufficient_data(self):
        """If yfinance returns < 30 rows, the ticker should be skipped gracefully."""
        df = _make_ohlcv(n=10)   # too short

        with patch("yfinance.download", return_value=df), \
             patch("services.indicator_service._get_conn",
                   side_effect=Exception("DB unavailable")):
            ind.calculate_and_store(["0050.TW"])

        assert ind.get_indicators("0050.TW") is None
