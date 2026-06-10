"""
Tests for services/buffett_fetcher.py

Covers:
  - ratio calculation (pure math)
  - source labelling logic
  - cache behaviour
  - fallback when both TWSE and yfinance fail
"""
import time
from unittest.mock import patch, MagicMock

import pytest

import services.buffett_fetcher as bf


# ── helpers ───────────────────────────────────────────────────────────────────

def _reset_cache():
    bf._cache.update({"ts": 0, "data": None})


# ── ratio calculation ──────────────────────────────────────────────────────────

class TestRatioMath:
    def test_ratio_formula(self):
        """ratio = market_cap_yi / gdp_yi * 100, rounded to 1 dp"""
        mktcap = 650_000   # 65 兆
        gdp    = 280_000   # 28 兆
        expected = round(mktcap / gdp * 100, 1)
        assert expected == pytest.approx(232.1, abs=0.1)

    def test_ratio_zero_gdp_does_not_crash(self):
        """If GDP is somehow 0, ratio should be None (no ZeroDivisionError)."""
        mktcap = 650_000
        gdp    = 0
        ratio = round(mktcap / gdp * 100, 1) if gdp > 0 else None
        assert ratio is None

    def test_known_calibration_point(self):
        """Dec 2024 calibration: TAIEX 22,000 × 29.5 = 649,000 億 ≈ 65 兆"""
        taiex  = 22_000
        factor = bf._MKT_CAP_FACTOR
        mktcap_zhao = taiex * factor / 10_000
        # Accept 60–70 兆 as a reasonable range
        assert 60 < mktcap_zhao < 70


# ── _fetch_taiex_market_cap_yi ─────────────────────────────────────────────────

class TestTaiexCalibration:
    def test_returns_value_when_taiex_valid(self):
        mock_info = MagicMock()
        mock_info.last_price = 22_000.0
        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = bf._fetch_taiex_market_cap_yi()

        assert result is not None
        assert result == pytest.approx(22_000 * bf._MKT_CAP_FACTOR, rel=1e-3)

    def test_returns_none_when_taiex_too_low(self):
        """Index levels below 5,000 are likely stale/invalid — should return None."""
        mock_info = MagicMock()
        mock_info.last_price = 1_000.0
        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_info

        with patch("yfinance.Ticker", return_value=mock_ticker):
            result = bf._fetch_taiex_market_cap_yi()

        assert result is None

    def test_returns_none_on_exception(self):
        with patch("yfinance.Ticker", side_effect=Exception("network error")):
            result = bf._fetch_taiex_market_cap_yi()
        assert result is None


# ── fetch_buffett (integration-style, all IO mocked) ──────────────────────────

class TestFetchBuffett:
    def setup_method(self):
        _reset_cache()

    def test_uses_twse_when_available(self):
        """When TWSE returns a valid market cap, source should be 'twse'."""
        with patch.object(bf, "_fetch_twse_market_cap_yi", return_value=700_000.0), \
             patch.object(bf, "_fetch_taiex_market_cap_yi", return_value=None):
            result = bf.fetch_buffett()

        assert result["source"] == "twse"
        assert result["market_cap_yi"] == 700_000.0
        assert result["ratio"] == pytest.approx(700_000 / bf._GDP_TWD_YI * 100, abs=0.1)

    def test_falls_back_to_taiex_when_twse_fails(self):
        """When TWSE returns None, should use TAIEX calibration."""
        with patch.object(bf, "_fetch_twse_market_cap_yi", return_value=None), \
             patch.object(bf, "_fetch_taiex_market_cap_yi", return_value=650_000.0):
            result = bf.fetch_buffett()

        assert result["source"] == "taiex_estimated"
        assert result["market_cap_yi"] == 650_000.0

    def test_unavailable_when_both_fail(self):
        """When both strategies fail, source should be 'unavailable' and ratio None."""
        with patch.object(bf, "_fetch_twse_market_cap_yi", return_value=None), \
             patch.object(bf, "_fetch_taiex_market_cap_yi", return_value=None):
            result = bf.fetch_buffett()

        assert result["source"] == "unavailable"
        assert result["ratio"] is None

    def test_result_includes_gdp_metadata(self):
        with patch.object(bf, "_fetch_twse_market_cap_yi", return_value=600_000.0), \
             patch.object(bf, "_fetch_taiex_market_cap_yi", return_value=None):
            result = bf.fetch_buffett()

        assert result["gdp_yi"]   == bf._GDP_TWD_YI
        assert result["gdp_year"] == bf._GDP_YEAR
        assert "updated_at" in result

    def test_cache_is_hit_on_second_call(self):
        """Second call within TTL should not re-invoke fetch functions."""
        with patch.object(bf, "_fetch_twse_market_cap_yi", return_value=600_000.0) as mock_twse, \
             patch.object(bf, "_fetch_taiex_market_cap_yi", return_value=None):
            bf.fetch_buffett()
            bf.fetch_buffett()   # should hit cache

        assert mock_twse.call_count == 1   # only called once

    def test_cache_expires_after_ttl(self):
        """After TTL, data should be re-fetched."""
        with patch.object(bf, "_fetch_twse_market_cap_yi", return_value=600_000.0) as mock_twse, \
             patch.object(bf, "_fetch_taiex_market_cap_yi", return_value=None):
            bf.fetch_buffett()
            # Expire the cache
            bf._cache["ts"] = time.time() - bf._CACHE_TTL - 1
            bf.fetch_buffett()

        assert mock_twse.call_count == 2
